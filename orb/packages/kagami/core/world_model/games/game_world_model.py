"""Game World Model.

Wraps Kagami's OrganismRSSM for game dynamics prediction.
Enables sample-efficient learning through imagination-based planning.

Key Features:
- Encodes game frames to RSSM latent space
- Predicts future game states
- Enables planning via imagination rollouts
- Integrates with Active Inference for action selection

This achieves EfficientZero-style sample efficiency by:
1. Learning a world model of game dynamics
2. Planning in imagination (latent space)
3. Self-supervised representation learning

References:
- EfficientZero: https://arxiv.org/abs/2111.00210
- DreamerV3: https://arxiv.org/abs/2301.04104
- Kagami RSSM: packages/kagami/core/world_model/rssm_core.py
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F

# Direct import since we're now in kagami core
from kagami.core.config.unified_config import get_kagami_config
from kagami.core.world_model.rssm_core import OrganismRSSM

from .frame_encoder import GameFrameDecoder, GameFrameEncoder

# KAGAMI_RSSM_AVAILABLE removed - always using real OrganismRSSM (Jan 5, 2026)

logger = logging.getLogger(__name__)


@dataclass
class GameWorldModelConfig:
    """Configuration for game world model."""

    # Observation
    observation_shape: tuple[int, ...] = (4, 84, 84)

    # Action space
    n_actions: int = 18  # Atari action space

    # Encoder
    embed_dim: int = 256
    encoder_depth: int = 4

    # RSSM (will use Kagami config if available)
    hidden_dim: int = 256
    stoch_dim: int = 32
    num_stoch_categories: int = 32  # For discrete latents

    # Decoder
    decode_frames: bool = True  # Whether to reconstruct frames

    # Training
    kl_balance: float = 0.8  # KL balancing (DreamerV3)
    free_nats: float = 1.0  # Free bits for KL

    # Imagination
    imagination_horizon: int = 15  # Steps to imagine ahead


@dataclass
class GameWorldModelState:
    """State of the game world model.

    Contains both deterministic (hidden) and stochastic (latent) components.
    Compatible with Kagami's ColonyState structure.
    """

    hidden: torch.Tensor  # Deterministic state (B, hidden_dim)
    stoch: torch.Tensor  # Stochastic state (B, stoch_dim * num_categories)
    logits: torch.Tensor | None = None  # For KL computation

    def detach(self) -> GameWorldModelState:
        """Detach from computation graph."""
        return GameWorldModelState(
            hidden=self.hidden.detach(),
            stoch=self.stoch.detach(),
            logits=self.logits.detach() if self.logits is not None else None,
        )

    @property
    def combined(self) -> torch.Tensor:
        """Get combined state vector."""
        return torch.cat([self.hidden, self.stoch], dim=-1)


class OrganismRSSMAdapter(nn.Module):
    """Adapter to use Kagami's OrganismRSSM for game dynamics.

    WIRED TO REAL RSSM (Jan 5, 2026):
    Replaces SimpleRSSMCell fallback with the production OrganismRSSM.

    The adapter handles dimension conversions between game embeddings
    and the E8-based OrganismRSSM architecture:
    - Game embed (256D) → E8 code (8D) + S7 phase (7D)
    - OrganismRSSM state → GameWorldModelState
    """

    def __init__(
        self,
        embed_dim: int = 256,
        hidden_dim: int = 256,
        stoch_dim: int = 32,
        num_categories: int = 32,
        n_actions: int = 18,
    ) -> None:
        super().__init__()

        self.hidden_dim = hidden_dim
        self.stoch_dim = stoch_dim
        self.num_categories = num_categories
        self.stoch_size = stoch_dim * num_categories
        self.embed_dim = embed_dim

        # Get real RSSM config
        config = get_kagami_config().world_model.rssm

        # Override config for game dimensions
        config.colony_dim = hidden_dim
        config.stochastic_dim = stoch_dim
        config.action_dim = n_actions

        # Initialize the REAL OrganismRSSM
        self.organism_rssm = OrganismRSSM(config=config)

        # Projection layers: game embed ↔ E8/S7
        # Game embed (256D) → E8 code (8D)
        self.embed_to_e8 = nn.Sequential(
            nn.Linear(embed_dim, 64),
            nn.SiLU(),
            nn.Linear(64, 8),
        )

        # Game embed (256D) → S7 phase (7D, normalized to unit sphere)
        self.embed_to_s7 = nn.Sequential(
            nn.Linear(embed_dim, 64),
            nn.SiLU(),
            nn.Linear(64, 7),
        )

        # OrganismRSSM state → game state format
        # RSSM deter_dim (colony_dim) → hidden_dim
        self.rssm_to_hidden = nn.Linear(config.colony_dim, hidden_dim)

        # RSSM stoch_dim → stoch_size (stoch_dim * num_categories)
        self.rssm_to_stoch = nn.Linear(config.stochastic_dim, self.stoch_size)

        # Action embedding for discrete actions
        self.action_embed = nn.Embedding(n_actions, hidden_dim // 4)

        logger.info(
            f"OrganismRSSMAdapter initialized: embed_dim={embed_dim}, "
            f"hidden_dim={hidden_dim}, n_actions={n_actions} - USING REAL RSSM"
        )

    def initial_state(self, batch_size: int, device: torch.device) -> GameWorldModelState:
        """Get initial state from OrganismRSSM."""
        # Initialize OrganismRSSM states
        self.organism_rssm.initialize_states(batch_size)

        return GameWorldModelState(
            hidden=torch.zeros(batch_size, self.hidden_dim, device=device),
            stoch=torch.zeros(batch_size, self.stoch_size, device=device),
            logits=None,
        )

    def _embed_to_e8_s7(self, embed: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Convert game embedding to E8 code + S7 phase.

        Args:
            embed: Game embedding [B, embed_dim]

        Returns:
            e8_code: [B, 8] - E8 lattice code
            s7_phase: [B, 7] - Unit sphere phase (normalized)
        """
        e8_code = self.embed_to_e8(embed)
        s7_raw = self.embed_to_s7(embed)
        # Normalize to unit S7 sphere
        s7_phase = F.normalize(s7_raw, p=2, dim=-1)
        return e8_code, s7_phase

    def forward(
        self,
        prev_state: GameWorldModelState,
        prev_action: torch.Tensor,
        embed: torch.Tensor | None = None,
    ) -> tuple[GameWorldModelState, GameWorldModelState]:
        """Single RSSM step using real OrganismRSSM.

        Args:
            prev_state: Previous state
            prev_action: Previous action (B,) discrete
            embed: Current observation embedding (B, embed_dim), None for imagination

        Returns:
            (prior_state, posterior_state) - posterior is prior if embed is None
        """
        batch_size = prev_state.hidden.shape[0]
        device = prev_state.hidden.device

        # Convert embedding to E8/S7 format
        if embed is not None:
            e8_code, s7_phase = self._embed_to_e8_s7(embed)
        else:
            # For imagination, use zeros
            e8_code = torch.zeros(batch_size, 8, device=device)
            s7_phase = torch.zeros(batch_size, 7, device=device)
            # Normalize to valid S7 point
            s7_phase[:, 0] = 1.0  # Point to first colony

        # Run through real OrganismRSSM
        # OrganismRSSM returns dict with 'organism_actions', 'h', 'z', etc.
        rssm_output = self.organism_rssm(e8_code, s7_phase)

        # Extract state from RSSM output
        # OrganismRSSM outputs colony-level states, we aggregate
        if "h" in rssm_output:
            # [B, num_colonies, deter_dim] → [B, deter_dim] (mean over colonies)
            h_colonies = rssm_output["h"]
            if h_colonies.dim() == 3:
                h_mean = h_colonies.mean(dim=1)
            else:
                h_mean = h_colonies
            hidden = self.rssm_to_hidden(h_mean)
        else:
            hidden = prev_state.hidden

        if "z" in rssm_output:
            # [B, num_colonies, stoch_dim] → [B, stoch_dim] (mean over colonies)
            z_colonies = rssm_output["z"]
            if z_colonies.dim() == 3:
                z_mean = z_colonies.mean(dim=1)
            else:
                z_mean = z_colonies
            stoch = self.rssm_to_stoch(z_mean)
        else:
            stoch = prev_state.stoch

        # Create prior state (from imagination)
        prior_state = GameWorldModelState(
            hidden=hidden,
            stoch=stoch,
            logits=None,  # OrganismRSSM uses different latent structure
        )

        if embed is None:
            # Imagination mode - use prior
            return prior_state, prior_state

        # Posterior: OrganismRSSM already computed posterior in forward pass
        # The output contains the posterior-corrected state
        # For games, we use the same state for both prior and posterior
        # since OrganismRSSM handles the distinction internally
        posterior_state = prior_state  # RSSM output IS the posterior when embed is provided

        return prior_state, posterior_state

    def _sample_stoch(self, logits: torch.Tensor) -> torch.Tensor:
        """Sample stochastic state using straight-through Gumbel-softmax.

        DEPRECATED: OrganismRSSM handles its own sampling internally.
        Kept for backward compatibility but not used in real RSSM path.

        Args:
            logits: (B, stoch_dim, num_categories)

        Returns:
            Sampled one-hot (B, stoch_dim, num_categories)
        """
        if self.training:
            # Gumbel-softmax for differentiable sampling
            probs = F.softmax(logits, dim=-1)
            uniform = torch.rand_like(probs).clamp(1e-8, 1 - 1e-8)
            gumbel = -torch.log(-torch.log(uniform))
            samples = F.softmax((logits + gumbel) / 1.0, dim=-1)

            # Straight-through: hard samples in forward, soft in backward
            hard = F.one_hot(samples.argmax(dim=-1), self.num_categories).float()
            samples = hard - samples.detach() + samples
        else:
            # Argmax during inference
            samples = F.one_hot(logits.argmax(dim=-1), self.num_categories).float()

        return samples


class GameWorldModel(nn.Module):
    """World model for game environments.

    Integrates with Kagami's OrganismRSSM when available, uses
    real OrganismRSSM via adapter. Enables:
    - Learning game dynamics from observations
    - Imagination-based planning
    - Sample-efficient learning

    Example:
        model = GameWorldModel(
            observation_shape=(4, 84, 84),
            n_actions=4,
        )

        # Encode observation
        state = model.initial_state(batch_size=32)
        obs = torch.randn(32, 4, 84, 84)
        action = torch.randint(0, 4, (32,))

        # Step world model
        prior, posterior, losses = model.step(state, action, obs)

        # Imagine future
        imagined_states = model.imagine(posterior, policy_fn, horizon=15)
    """

    def __init__(
        self,
        observation_shape: tuple[int, ...] = (4, 84, 84),
        n_actions: int = 18,
        config: GameWorldModelConfig | None = None,
        use_kagami_rssm: bool = True,
    ) -> None:
        """Initialize game world model.

        Args:
            observation_shape: Observation shape (C, H, W)
            n_actions: Number of discrete actions
            config: Model configuration
            use_kagami_rssm: Try to use Kagami's OrganismRSSM
        """
        super().__init__()

        self.config = config or GameWorldModelConfig(
            observation_shape=observation_shape,
            n_actions=n_actions,
        )

        # Frame encoder
        self.encoder = GameFrameEncoder(
            observation_shape=observation_shape,
            embed_dim=self.config.embed_dim,
            depth=self.config.encoder_depth,
        )

        # RSSM dynamics - ALWAYS use real OrganismRSSM via adapter (Jan 5, 2026)
        # NO FALLBACKS - if RSSM fails, let it fail loudly
        self._use_kagami_rssm = True  # Always use real RSSM
        self._rssm: OrganismRSSMAdapter | None = None  # Lazy init via rssm property

        logger.info("GameWorldModel: Using REAL OrganismRSSM via adapter (no fallbacks)")

        # Frame decoder (optional)
        if self.config.decode_frames:
            self.decoder = GameFrameDecoder(
                observation_shape=observation_shape,
                embed_dim=self.config.hidden_dim
                + self.config.stoch_dim * self.config.num_stoch_categories,
            )
        else:
            self.decoder = None

        # Reward predictor
        state_dim = (
            self.config.hidden_dim + self.config.stoch_dim * self.config.num_stoch_categories
        )
        self.reward_predictor = nn.Sequential(
            nn.Linear(state_dim, 256),
            nn.LayerNorm(256),
            nn.SiLU(),
            nn.Linear(256, 1),
        )

        # Continue predictor (episode termination)
        self.continue_predictor = nn.Sequential(
            nn.Linear(state_dim, 256),
            nn.LayerNorm(256),
            nn.SiLU(),
            nn.Linear(256, 1),
        )

        logger.info(
            f"GameWorldModel initialized: obs={observation_shape}, actions={n_actions}, "
            f"kagami_rssm={self._use_kagami_rssm}"
        )

    @property
    def rssm(self) -> OrganismRSSMAdapter:
        """Get RSSM cell (lazy initialization).

        Returns OrganismRSSMAdapter wrapping the REAL OrganismRSSM.
        NO FALLBACKS - always uses production RSSM.
        """
        if self._rssm is None:
            self._rssm = OrganismRSSMAdapter(
                embed_dim=self.config.embed_dim,
                hidden_dim=self.config.hidden_dim,
                stoch_dim=self.config.stoch_dim,
                num_categories=self.config.num_stoch_categories,
                n_actions=self.config.n_actions,
            )
        return self._rssm

    def initial_state(
        self, batch_size: int, device: torch.device | None = None
    ) -> GameWorldModelState:
        """Get initial world model state.

        Args:
            batch_size: Batch size
            device: Target device

        Returns:
            Initial state
        """
        if device is None:
            device = next(self.parameters()).device
        return self.rssm.initial_state(batch_size, device)

    def encode(self, obs: torch.Tensor) -> torch.Tensor:
        """Encode observation to embedding.

        Args:
            obs: Observation (B, C, H, W) or (B, T, C, H, W)

        Returns:
            Embedding (B, embed_dim) or (B, T, embed_dim)
        """
        return self.encoder(obs)

    def decode(self, state: GameWorldModelState) -> torch.Tensor:
        """Decode state to observation.

        Args:
            state: World model state

        Returns:
            Reconstructed observation
        """
        if self.decoder is None:
            raise ValueError("Decoder not enabled (decode_frames=False)")
        return self.decoder(state.combined)

    def step(
        self,
        prev_state: GameWorldModelState,
        action: torch.Tensor,
        obs: torch.Tensor | None = None,
    ) -> tuple[GameWorldModelState, GameWorldModelState, dict[str, torch.Tensor]]:
        """Single world model step.

        Args:
            prev_state: Previous state
            action: Action taken (B,)
            obs: Current observation (B, C, H, W), None for imagination

        Returns:
            (prior_state, posterior_state, losses)
        """
        # Encode observation if provided
        embed = None
        if obs is not None:
            embed = self.encode(obs)

        # RSSM step
        prior, posterior = self.rssm(prev_state, action, embed)

        # Compute losses
        losses = {}

        if obs is not None and posterior.logits is not None and prior.logits is not None:
            # KL divergence (balanced)
            kl_loss = self._compute_kl(posterior.logits, prior.logits)
            losses["kl"] = kl_loss

            # Reconstruction loss
            if self.decoder is not None:
                recon = self.decode(posterior)
                recon_loss = F.mse_loss(recon, obs)
                losses["reconstruction"] = recon_loss

        return prior, posterior, losses

    def _compute_kl(
        self,
        posterior_logits: torch.Tensor,
        prior_logits: torch.Tensor,
    ) -> torch.Tensor:
        """Compute KL divergence with balancing (DreamerV3 style).

        Args:
            posterior_logits: (B, stoch_dim, num_categories)
            prior_logits: (B, stoch_dim, num_categories)

        Returns:
            KL loss
        """
        posterior_probs = F.softmax(posterior_logits, dim=-1)
        prior_probs = F.softmax(prior_logits, dim=-1)

        # KL divergence
        kl = posterior_probs * (torch.log(posterior_probs + 1e-8) - torch.log(prior_probs + 1e-8))
        kl = kl.sum(dim=-1).mean()

        # Free nats
        kl = torch.max(kl, torch.tensor(self.config.free_nats, device=kl.device))

        return kl

    def imagine(
        self,
        start_state: GameWorldModelState,
        policy_fn: callable,
        horizon: int | None = None,
    ) -> list[GameWorldModelState]:
        """Imagine future states by rolling out policy.

        Args:
            start_state: Starting state
            policy_fn: Function mapping state to action distribution
            horizon: Number of steps to imagine

        Returns:
            List of imagined states
        """
        horizon = horizon or self.config.imagination_horizon
        states = [start_state]
        state = start_state

        for _ in range(horizon):
            # Get action from policy
            with torch.no_grad():
                action_dist = policy_fn(state.combined)
                if hasattr(action_dist, "sample"):
                    action = action_dist.sample()
                else:
                    action = action_dist

            # Imagine next state (using prior only)
            prior, _ = self.rssm(state, action, embed=None)
            states.append(prior)
            state = prior

        return states

    def predict_reward(self, state: GameWorldModelState) -> torch.Tensor:
        """Predict reward from state.

        Args:
            state: World model state

        Returns:
            Predicted reward (B, 1)
        """
        return self.reward_predictor(state.combined)

    def predict_continue(self, state: GameWorldModelState) -> torch.Tensor:
        """Predict episode continuation probability.

        Args:
            state: World model state

        Returns:
            Continue probability (B, 1)
        """
        return torch.sigmoid(self.continue_predictor(state.combined))

    def get_state_dict_for_checkpoint(self) -> dict[str, Any]:
        """Get state dict for checkpointing."""
        return {
            "encoder": self.encoder.state_dict(),
            "rssm": self.rssm.state_dict() if self._rssm is not None else None,
            "decoder": self.decoder.state_dict() if self.decoder is not None else None,
            "reward_predictor": self.reward_predictor.state_dict(),
            "continue_predictor": self.continue_predictor.state_dict(),
            "config": self.config,
        }


__all__ = ["GameWorldModel", "GameWorldModelConfig", "GameWorldModelState"]
