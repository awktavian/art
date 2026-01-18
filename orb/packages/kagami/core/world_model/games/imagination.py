"""Imagination-based Planning.

MCTS-style planning in world model latent space.
Enables sample-efficient action selection by:
1. Imagining future trajectories
2. Evaluating trajectories with value estimates
3. Selecting actions that maximize expected return

References:
- MuZero: https://arxiv.org/abs/1911.08265
- EfficientZero: https://arxiv.org/abs/2111.00210
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F

from .game_world_model import GameWorldModel, GameWorldModelState

logger = logging.getLogger(__name__)


@dataclass
class PlanningConfig:
    """Configuration for imagination-based planning."""

    # Tree search
    num_simulations: int = 50  # MCTS simulations per action
    max_depth: int = 5  # Maximum tree depth

    # UCB exploration
    c_puct: float = 1.25  # UCB exploration constant
    dirichlet_alpha: float = 0.3  # Root prior noise
    root_exploration_fraction: float = 0.25

    # Value estimation
    discount: float = 0.997
    use_gae: bool = True
    gae_lambda: float = 0.95

    # Temperature
    temperature: float = 1.0  # Action selection temperature


class MCTSNode:
    """Node in Monte Carlo Tree Search."""

    def __init__(
        self,
        state: GameWorldModelState,
        prior: float = 0.0,
        parent: MCTSNode | None = None,
        action: int | None = None,
    ) -> None:
        """Initialize MCTS node.

        Args:
            state: World model state at this node
            prior: Prior probability from policy
            parent: Parent node
            action: Action taken to reach this node
        """
        self.state = state
        self.prior = prior
        self.parent = parent
        self.action = action

        self.children: dict[int, MCTSNode] = {}
        self.visit_count = 0
        self.value_sum = 0.0
        self.reward = 0.0

    @property
    def value(self) -> float:
        """Mean value of this node."""
        if self.visit_count == 0:
            return 0.0
        return self.value_sum / self.visit_count

    def ucb_score(self, c_puct: float, total_visits: int) -> float:
        """Upper Confidence Bound score for selection.

        Args:
            c_puct: Exploration constant
            total_visits: Total visits to parent

        Returns:
            UCB score
        """
        exploration = c_puct * self.prior * math.sqrt(total_visits) / (1 + self.visit_count)
        return self.value + exploration

    def is_expanded(self) -> bool:
        """Check if node has been expanded."""
        return len(self.children) > 0

    def expand(
        self,
        world_model: GameWorldModel,
        policy_logits: torch.Tensor,
        n_actions: int,
    ) -> None:
        """Expand node by adding children for all actions.

        Args:
            world_model: World model for state prediction
            policy_logits: Policy logits (n_actions,)
            n_actions: Number of actions
        """
        priors = F.softmax(policy_logits, dim=-1).cpu().numpy()

        for action in range(n_actions):
            # Predict next state
            action_tensor = torch.tensor([action], device=self.state.hidden.device)
            next_state, _ = world_model.rssm(self.state, action_tensor, embed=None)

            # Predict reward
            reward = world_model.predict_reward(next_state).item()

            child = MCTSNode(
                state=next_state,
                prior=float(priors[action]),
                parent=self,
                action=action,
            )
            child.reward = reward
            self.children[action] = child

    def select_child(self, c_puct: float) -> MCTSNode:
        """Select child with highest UCB score.

        Args:
            c_puct: Exploration constant

        Returns:
            Selected child node
        """
        total_visits = sum(child.visit_count for child in self.children.values())

        best_score = float("-inf")
        best_child = None

        for child in self.children.values():
            score = child.ucb_score(c_puct, total_visits)
            if score > best_score:
                best_score = score
                best_child = child

        assert best_child is not None
        return best_child

    def backpropagate(self, value: float, discount: float) -> None:
        """Backpropagate value up the tree.

        Args:
            value: Value to propagate
            discount: Discount factor
        """
        node = self
        while node is not None:
            node.visit_count += 1
            node.value_sum += value
            value = node.reward + discount * value
            node = node.parent


class ImaginationPlanner:
    """MCTS-style planner using world model imagination.

    Performs tree search in latent space to select actions.
    Key benefits over model-free:
    - Plans ahead multiple steps
    - Uses learned dynamics model
    - More sample efficient

    Example:
        planner = ImaginationPlanner(
            world_model=game_world_model,
            policy_network=policy_net,
            value_network=value_net,
            n_actions=4,
        )

        state = world_model.initial_state(batch_size=1)
        action, info = planner.plan(state)
    """

    def __init__(
        self,
        world_model: GameWorldModel,
        policy_network: nn.Module,
        value_network: nn.Module,
        n_actions: int,
        config: PlanningConfig | None = None,
    ) -> None:
        """Initialize planner.

        Args:
            world_model: Game world model
            policy_network: Policy network (state -> action logits)
            value_network: Value network (state -> value)
            n_actions: Number of actions
            config: Planning configuration
        """
        self.world_model = world_model
        self.policy_network = policy_network
        self.value_network = value_network
        self.n_actions = n_actions
        self.config = config or PlanningConfig()

    @torch.no_grad()
    def plan(
        self,
        state: GameWorldModelState,
        add_exploration_noise: bool = True,
    ) -> tuple[int, dict[str, Any]]:
        """Plan action using MCTS.

        Args:
            state: Current world model state
            add_exploration_noise: Add Dirichlet noise to root

        Returns:
            (action, info_dict)
        """
        # Create root node
        root = MCTSNode(state=state.detach())

        # Get initial policy
        policy_logits = self.policy_network(state.combined)

        # Add exploration noise to root
        if add_exploration_noise:
            noise = torch.distributions.Dirichlet(
                torch.full((self.n_actions,), self.config.dirichlet_alpha)
            ).sample()
            noise = noise.to(policy_logits.device)
            policy_logits = (1 - self.config.root_exploration_fraction) * F.softmax(
                policy_logits, dim=-1
            ) + self.config.root_exploration_fraction * noise
            policy_logits = torch.log(policy_logits + 1e-8)

        # Expand root
        root.expand(self.world_model, policy_logits.squeeze(0), self.n_actions)

        # Run simulations
        for _ in range(self.config.num_simulations):
            node = root
            depth = 0

            # Selection: traverse to leaf
            while node.is_expanded() and depth < self.config.max_depth:
                node = node.select_child(self.config.c_puct)
                depth += 1

            # Expansion: expand leaf if not terminal
            if depth < self.config.max_depth:
                leaf_policy = self.policy_network(node.state.combined)
                node.expand(self.world_model, leaf_policy.squeeze(0), self.n_actions)

            # Evaluation: get value estimate
            value = self.value_network(node.state.combined).item()

            # Backpropagation
            node.backpropagate(value, self.config.discount)

        # Select action based on visit counts
        visits = torch.tensor(
            [
                root.children[a].visit_count if a in root.children else 0
                for a in range(self.n_actions)
            ],
            dtype=torch.float32,
        )

        if self.config.temperature > 0:
            # Sample proportional to visit counts
            probs = visits ** (1 / self.config.temperature)
            probs = probs / probs.sum()
            action = torch.multinomial(probs, 1).item()
        else:
            # Greedy
            action = visits.argmax().item()

        # Collect info
        info = {
            "visit_counts": visits.numpy(),
            "root_value": root.value,
            "action_values": {
                a: root.children[a].value if a in root.children else 0.0
                for a in range(self.n_actions)
            },
        }

        return int(action), info

    def get_policy_target(self, root_visits: torch.Tensor) -> torch.Tensor:
        """Convert visit counts to policy target for training.

        Args:
            root_visits: Visit counts for each action

        Returns:
            Policy target distribution
        """
        return root_visits / root_visits.sum()


class SimpleImagination:
    """Simple imagination-based planning (no MCTS).

    Faster alternative to full MCTS - just rolls out
    multiple trajectories and picks best first action.
    """

    def __init__(
        self,
        world_model: GameWorldModel,
        value_network: nn.Module,
        n_actions: int,
        horizon: int = 5,
        num_rollouts: int = 10,
        discount: float = 0.99,
    ) -> None:
        """Initialize simple imagination planner.

        Args:
            world_model: Game world model
            value_network: Value network
            n_actions: Number of actions
            horizon: Rollout horizon
            num_rollouts: Number of rollouts per action
            discount: Discount factor
        """
        self.world_model = world_model
        self.value_network = value_network
        self.n_actions = n_actions
        self.horizon = horizon
        self.num_rollouts = num_rollouts
        self.discount = discount

    @torch.no_grad()
    def plan(self, state: GameWorldModelState) -> tuple[int, dict[str, Any]]:
        """Plan by rolling out and evaluating trajectories.

        Args:
            state: Current state

        Returns:
            (action, info)
        """
        action_values = torch.zeros(self.n_actions)

        for action in range(self.n_actions):
            returns = []

            for _ in range(self.num_rollouts):
                # Take first action
                action_tensor = torch.tensor([action], device=state.hidden.device)
                next_state, _ = self.world_model.rssm(state, action_tensor, embed=None)

                # Accumulate reward
                total_return = self.world_model.predict_reward(next_state).item()
                discount = self.discount

                # Random rollout
                current_state = next_state
                for _ in range(self.horizon - 1):
                    rand_action = torch.randint(0, self.n_actions, (1,), device=state.hidden.device)
                    current_state, _ = self.world_model.rssm(current_state, rand_action, embed=None)
                    reward = self.world_model.predict_reward(current_state).item()
                    total_return += discount * reward
                    discount *= self.discount

                # Bootstrap with value
                value = self.value_network(current_state.combined).item()
                total_return += discount * value

                returns.append(total_return)

            action_values[action] = sum(returns) / len(returns)

        # Select best action
        action = action_values.argmax().item()

        return int(action), {"action_values": action_values.numpy()}


__all__ = [
    "ImaginationPlanner",
    "MCTSNode",
    "PlanningConfig",
    "SimpleImagination",
]
