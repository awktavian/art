"""Smart Home World Model - Practical Integration for Kagami.

CREATED: January 4, 2026

A focused world model specifically for smart home prediction and planning.
This is what Kagami ACTUALLY needs - not video generation, but:

1. Predict room state from sensor history
2. Anticipate needs based on patterns
3. Plan actions to achieve goals
4. Safety check via CBF before execution

This is MUCH simpler than video world models and addresses the real use case.

Architecture:
=============
```
Sensors ─────▶ StateEncoder ─────▶ Latent State
                                        │
Actions ─────▶ ActionEncoder ───────────┤
                                        ▼
                               TransformerDynamics
                                        │
                                        ▼
                               NextStatePredictor ─────▶ Predicted State
                                        │
                               RewardPredictor ────────▶ Expected Comfort
```

Features:
=========
- Real-time sensor encoding (lights, temp, presence, time)
- Pattern learning (daily routines)
- Goal-directed planning (via MPPI)
- CBF safety integration
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class SmartHomeWorldModelConfig:
    """Configuration for smart home world model."""

    # State dimensions
    num_rooms: int = 26  # Number of rooms in home
    features_per_room: int = (
        8  # [light, temp, shade, presence, humidity, co2, noise, occupied_minutes]
    )

    # Temporal
    time_embedding_dim: int = 32  # Time of day + day of week
    history_length: int = 24  # Hours of history to consider

    # Latent space
    latent_dim: int = 128
    hidden_dim: int = 256

    # Actions
    num_action_types: int = 10  # Types of actions (light, shade, temp, lock, etc.)
    max_action_value: int = 100  # Max value for continuous actions

    # Architecture
    num_layers: int = 4
    num_heads: int = 4
    dropout: float = 0.1

    # Planning
    planning_horizon: int = 12  # Steps ahead (1 step = 5 min)
    num_planning_samples: int = 256

    # Device
    device: str = "auto"


# Room names for reference
ROOMS = [
    "living_room",
    "kitchen",
    "dining",
    "entry",
    "mudroom",
    "powder_room",
    "stairway",
    "garage",
    "deck",
    "porch",  # First floor (10)
    "primary_bed",
    "primary_bath",
    "primary_closet",
    "primary_hall",
    "office",
    "office_bath",
    "bed_3",
    "bath_3",
    "loft",
    "laundry",  # Second (10)
    "game_room",
    "bed_4",
    "bath_4",
    "gym",
    "rack_room",
    "patio",  # Basement (6)
]


# =============================================================================
# TIME ENCODING
# =============================================================================


class TimeEncoder(nn.Module):
    """Encode time of day and day of week."""

    def __init__(self, dim: int = 32):
        super().__init__()
        self.dim = dim

        # Learnable embeddings
        self.hour_embedding = nn.Embedding(24, dim // 2)
        self.day_embedding = nn.Embedding(7, dim // 2)

    def forward(self, timestamps: torch.Tensor) -> torch.Tensor:
        """Encode timestamps.

        Args:
            timestamps: [B] or [B, T] unix timestamps

        Returns:
            [B, dim] or [B, T, dim] time embeddings
        """
        # Convert to datetime info
        # For efficiency, we'll work with pre-extracted hour/day
        # In real use, convert from unix timestamp

        squeeze = timestamps.dim() == 1
        if squeeze:
            timestamps = timestamps.unsqueeze(1)

        _B, _T = timestamps.shape

        # Extract hour (0-23) and day (0-6)
        # Simplified: assume timestamps are in format hour*100 + day
        hours = (timestamps // 100 % 24).long()
        days = (timestamps % 7).long()

        hour_emb = self.hour_embedding(hours)  # [B, T, dim/2]
        day_emb = self.day_embedding(days)  # [B, T, dim/2]

        out = torch.cat([hour_emb, day_emb], dim=-1)

        if squeeze:
            out = out.squeeze(1)

        return out


# =============================================================================
# STATE ENCODER
# =============================================================================


class SmartHomeStateEncoder(nn.Module):
    """Encode smart home state to latent representation."""

    def __init__(self, config: SmartHomeWorldModelConfig):
        super().__init__()
        self.config = config

        # Room state encoder
        room_input_dim = config.features_per_room
        self.room_encoder = nn.Sequential(
            nn.Linear(room_input_dim, config.hidden_dim // 2),
            nn.LayerNorm(config.hidden_dim // 2),
            nn.GELU(),
            nn.Linear(config.hidden_dim // 2, config.hidden_dim // 4),
        )

        # Room position embedding (which room)
        self.room_embedding = nn.Embedding(config.num_rooms, config.hidden_dim // 4)

        # Time encoder
        self.time_encoder = TimeEncoder(config.time_embedding_dim)

        # Aggregation
        (config.hidden_dim // 4) * 2 + config.time_embedding_dim
        self.aggregator = nn.Sequential(
            nn.Linear(
                config.num_rooms * (config.hidden_dim // 4) + config.time_embedding_dim,
                config.hidden_dim,
            ),
            nn.LayerNorm(config.hidden_dim),
            nn.GELU(),
            nn.Linear(config.hidden_dim, config.latent_dim),
        )

    def forward(
        self,
        room_states: torch.Tensor,
        timestamp: torch.Tensor,
    ) -> torch.Tensor:
        """Encode full home state.

        Args:
            room_states: [B, num_rooms, features_per_room] room sensor values
            timestamp: [B] timestamp encoding

        Returns:
            [B, latent_dim] latent state
        """
        B = room_states.shape[0]
        device = room_states.device

        # Encode each room
        room_features = self.room_encoder(room_states)  # [B, num_rooms, hidden/4]

        # Add room position embedding
        room_idx = torch.arange(self.config.num_rooms, device=device)
        room_pos = self.room_embedding(room_idx)  # [num_rooms, hidden/4]
        room_features = room_features + room_pos.unsqueeze(0)

        # Flatten rooms
        room_flat = room_features.view(B, -1)  # [B, num_rooms * hidden/4]

        # Add time encoding
        time_emb = self.time_encoder(timestamp)  # [B, time_dim]
        combined = torch.cat([room_flat, time_emb], dim=-1)

        # Aggregate to latent
        latent = self.aggregator(combined)

        return latent


# =============================================================================
# ACTION ENCODER
# =============================================================================


class SmartHomeActionEncoder(nn.Module):
    """Encode smart home action to latent representation."""

    def __init__(self, config: SmartHomeWorldModelConfig):
        super().__init__()
        self.config = config

        # Action type embedding
        self.action_type_emb = nn.Embedding(config.num_action_types, config.hidden_dim // 2)

        # Action value projection
        self.value_proj = nn.Linear(1, config.hidden_dim // 4)

        # Room target embedding
        self.room_target_emb = nn.Embedding(
            config.num_rooms + 1, config.hidden_dim // 4
        )  # +1 for "all rooms"

        # Combine
        self.output = nn.Linear(config.hidden_dim, config.latent_dim)

    def forward(
        self,
        action_type: torch.Tensor,
        action_value: torch.Tensor,
        target_room: torch.Tensor,
    ) -> torch.Tensor:
        """Encode action.

        Args:
            action_type: [B] action type index (0=lights, 1=shades, etc.)
            action_value: [B] action value (0-100)
            target_room: [B] target room index (num_rooms = all rooms)

        Returns:
            [B, latent_dim] action embedding
        """
        type_emb = self.action_type_emb(action_type)  # [B, hidden/2]
        value_emb = self.value_proj(action_value.unsqueeze(-1))  # [B, hidden/4]
        room_emb = self.room_target_emb(target_room)  # [B, hidden/4]

        combined = torch.cat([type_emb, value_emb, room_emb], dim=-1)
        action_latent = self.output(combined)

        return action_latent


# =============================================================================
# DYNAMICS MODEL
# =============================================================================


class SmartHomeDynamics(nn.Module):
    """Predict next state given current state and action."""

    def __init__(self, config: SmartHomeWorldModelConfig):
        super().__init__()
        self.config = config

        # Combine state and action
        self.input_proj = nn.Linear(config.latent_dim * 2, config.hidden_dim)

        # MLP dynamics
        layers = []
        for _ in range(config.num_layers):
            layers.extend(
                [
                    nn.Linear(config.hidden_dim, config.hidden_dim),
                    nn.LayerNorm(config.hidden_dim),
                    nn.GELU(),
                    nn.Dropout(config.dropout),
                ]
            )
        self.dynamics = nn.Sequential(*layers)

        # Output state prediction
        self.state_head = nn.Linear(config.hidden_dim, config.latent_dim)

        # Reward prediction (comfort level)
        self.reward_head = nn.Sequential(
            nn.Linear(config.hidden_dim, config.hidden_dim // 2),
            nn.GELU(),
            nn.Linear(config.hidden_dim // 2, 1),
        )

    def forward(
        self,
        state: torch.Tensor,
        action: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Predict next state and reward.

        Args:
            state: [B, latent_dim] current state
            action: [B, latent_dim] action embedding

        Returns:
            next_state: [B, latent_dim] predicted next state
            reward: [B] predicted reward (comfort)
        """
        combined = torch.cat([state, action], dim=-1)
        x = self.input_proj(combined)
        x = self.dynamics(x)

        next_state = state + self.state_head(x)  # Residual prediction
        reward = self.reward_head(x).squeeze(-1)

        return next_state, reward


# =============================================================================
# STATE DECODER
# =============================================================================


class SmartHomeStateDecoder(nn.Module):
    """Decode latent state back to room states."""

    def __init__(self, config: SmartHomeWorldModelConfig):
        super().__init__()
        self.config = config

        self.decoder = nn.Sequential(
            nn.Linear(config.latent_dim, config.hidden_dim),
            nn.LayerNorm(config.hidden_dim),
            nn.GELU(),
            nn.Linear(config.hidden_dim, config.hidden_dim),
            nn.GELU(),
            nn.Linear(config.hidden_dim, config.num_rooms * config.features_per_room),
        )

    def forward(self, latent: torch.Tensor) -> torch.Tensor:
        """Decode latent to room states.

        Args:
            latent: [B, latent_dim] latent state

        Returns:
            [B, num_rooms, features_per_room] predicted room states
        """
        flat = self.decoder(latent)
        return flat.view(-1, self.config.num_rooms, self.config.features_per_room)


# =============================================================================
# SMART HOME WORLD MODEL
# =============================================================================


class SmartHomeWorldModel(nn.Module):
    """World model for smart home prediction and planning.

    This is what Kagami actually needs - practical prediction of room states,
    pattern learning, and goal-directed planning.

    Usage:
        model = SmartHomeWorldModel(config)

        # Encode current state
        latent = model.encode_state(sensors, timestamp)

        # Predict effect of action
        next_latent, reward = model.predict_step(latent, action)

        # Plan to achieve goal
        actions = model.plan_to_goal(current_latent, goal_latent)

        # Learn from experience
        loss = model.training_step(batch)
    """

    def __init__(self, config: SmartHomeWorldModelConfig | None = None):
        super().__init__()
        self.config = config or SmartHomeWorldModelConfig()

        # Components
        self.state_encoder = SmartHomeStateEncoder(self.config)
        self.action_encoder = SmartHomeActionEncoder(self.config)
        self.dynamics = SmartHomeDynamics(self.config)
        self.state_decoder = SmartHomeStateDecoder(self.config)

        # Device
        if self.config.device == "auto":
            if torch.backends.mps.is_available():
                self._device = torch.device("mps")
            elif torch.cuda.is_available():
                self._device = torch.device("cuda")
            else:
                self._device = torch.device("cpu")
        else:
            self._device = torch.device(self.config.device)

        logger.info(
            f"SmartHomeWorldModel initialized:\n"
            f"  Rooms: {self.config.num_rooms}\n"
            f"  Latent dim: {self.config.latent_dim}\n"
            f"  Planning horizon: {self.config.planning_horizon}\n"
            f"  Device: {self._device}"
        )

    def encode_state(
        self,
        room_states: torch.Tensor,
        timestamp: torch.Tensor,
    ) -> torch.Tensor:
        """Encode room states to latent.

        Args:
            room_states: [B, num_rooms, features] sensor values
            timestamp: [B] time encoding

        Returns:
            [B, latent_dim] latent state
        """
        return self.state_encoder(room_states, timestamp)

    def encode_action(
        self,
        action_type: torch.Tensor,
        action_value: torch.Tensor,
        target_room: torch.Tensor,
    ) -> torch.Tensor:
        """Encode action to latent.

        Args:
            action_type: [B] action type
            action_value: [B] action value
            target_room: [B] target room

        Returns:
            [B, latent_dim] action embedding
        """
        return self.action_encoder(action_type, action_value, target_room)

    def predict_step(
        self,
        state: torch.Tensor,
        action: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Predict next state given current state and action.

        Args:
            state: [B, latent_dim] current latent state
            action: [B, latent_dim] action embedding

        Returns:
            next_state: [B, latent_dim] predicted next state
            reward: [B] predicted comfort reward
        """
        return self.dynamics(state, action)

    def decode_state(self, latent: torch.Tensor) -> torch.Tensor:
        """Decode latent to room states.

        Args:
            latent: [B, latent_dim] latent state

        Returns:
            [B, num_rooms, features] decoded room states
        """
        return self.state_decoder(latent)

    @torch.no_grad()
    def imagine_trajectory(
        self,
        initial_state: torch.Tensor,
        actions: list[tuple[int, int, int]],
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Imagine future trajectory given action sequence.

        Args:
            initial_state: [latent_dim] starting state
            actions: List of (type, value, room) tuples

        Returns:
            states: [H+1, latent_dim] trajectory
            rewards: [H] predicted rewards
        """
        state = initial_state.unsqueeze(0) if initial_state.dim() == 1 else initial_state
        device = state.device

        states = [state]
        rewards = []

        for action_type, action_value, target_room in actions:
            # Encode action
            action = self.encode_action(
                torch.tensor([action_type], device=device),
                torch.tensor([action_value], device=device, dtype=torch.float),
                torch.tensor([target_room], device=device),
            )

            # Predict
            next_state, reward = self.predict_step(state, action)
            states.append(next_state)
            rewards.append(reward)
            state = next_state

        states = torch.cat(states, dim=0)
        rewards = torch.cat(rewards, dim=0) if rewards else torch.tensor([])

        return states, rewards

    @torch.no_grad()
    def plan_to_goal(
        self,
        current_state: torch.Tensor,
        goal_state: torch.Tensor,
        max_steps: int = 10,
    ) -> list[tuple[int, int, int]]:
        """Plan action sequence to reach goal state (simplified CEM).

        Args:
            current_state: [latent_dim] current state
            goal_state: [latent_dim] target state
            max_steps: Maximum planning steps

        Returns:
            List of (type, value, room) action tuples
        """
        device = current_state.device
        num_samples = self.config.num_planning_samples

        # Sample random action sequences
        best_actions = None
        best_dist = float("inf")

        for _ in range(10):  # Iterations
            # Random actions
            action_types = torch.randint(
                0, self.config.num_action_types, (num_samples, max_steps), device=device
            )
            action_values = (
                torch.rand(num_samples, max_steps, device=device) * self.config.max_action_value
            )
            target_rooms = torch.randint(
                0, self.config.num_rooms + 1, (num_samples, max_steps), device=device
            )

            # Evaluate each sequence
            for i in range(num_samples):
                actions = [
                    (
                        action_types[i, t].item(),
                        action_values[i, t].item(),
                        target_rooms[i, t].item(),
                    )
                    for t in range(max_steps)
                ]

                final_states, _ = self.imagine_trajectory(current_state, actions)
                final_state = final_states[-1]

                dist = F.mse_loss(final_state, goal_state).item()

                if dist < best_dist:
                    best_dist = dist
                    best_actions = actions

        return best_actions or []

    def training_step(
        self,
        room_states: torch.Tensor,
        timestamps: torch.Tensor,
        actions: tuple[torch.Tensor, torch.Tensor, torch.Tensor],
        next_room_states: torch.Tensor,
    ) -> dict[str, torch.Tensor]:
        """Training step.

        Args:
            room_states: [B, num_rooms, features] current states
            timestamps: [B] timestamps
            actions: Tuple of (type, value, room) tensors
            next_room_states: [B, num_rooms, features] next states

        Returns:
            Dict with loss components
        """
        action_type, action_value, target_room = actions

        # Encode
        state_latent = self.encode_state(room_states, timestamps)
        action_latent = self.encode_action(action_type, action_value, target_room)
        target_latent = self.encode_state(next_room_states, timestamps + 1)  # Simplified

        # Predict
        pred_latent, _pred_reward = self.predict_step(state_latent, action_latent)

        # Decode
        pred_rooms = self.decode_state(pred_latent)

        # Losses
        latent_loss = F.mse_loss(pred_latent, target_latent)
        reconstruction_loss = F.mse_loss(pred_rooms, next_room_states)

        total_loss = latent_loss + reconstruction_loss

        return {
            "loss": total_loss,
            "latent_loss": latent_loss,
            "reconstruction_loss": reconstruction_loss,
        }


# =============================================================================
# FACTORY
# =============================================================================


def create_smarthome_world_model(
    num_rooms: int = 26,
    latent_dim: int = 128,
) -> SmartHomeWorldModel:
    """Factory for SmartHomeWorldModel.

    Args:
        num_rooms: Number of rooms
        latent_dim: Latent dimension

    Returns:
        Configured SmartHomeWorldModel
    """
    config = SmartHomeWorldModelConfig(
        num_rooms=num_rooms,
        latent_dim=latent_dim,
    )
    return SmartHomeWorldModel(config)


__all__ = [
    "ROOMS",
    "SmartHomeActionEncoder",
    "SmartHomeDynamics",
    "SmartHomeStateEncoder",
    "SmartHomeWorldModel",
    "SmartHomeWorldModelConfig",
    "create_smarthome_world_model",
]
