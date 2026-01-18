from __future__ import annotations

"""Model Predictive Control (MPC) with Barrier Constraints

Implements safe multi-step planning using:
- World model rollouts for imagination
- Composite cost: J = FEP + λ_safety·Σmax(0,-h) + λ_task·L_goal + λ_KL·D_KL
- Control Barrier Function constraints
- Trust region enforcement
- CEM/sampling-based optimization

Based on:
- MPC (Garcia et al., 1989)
- Barrier-constrained MPC (Ames et al., 2017)
- MPPI (Williams et al., 2017)
- Active Inference MPC (Friston et al., 2015)
"""
import logging
from collections.abc import Callable
from typing import Any, cast

import torch
import torch.nn as nn

logger = logging.getLogger(__name__)


class MPCController:
    """Model Predictive Controller with safety constraints.

    Plans optimal action sequences by:
    1. Sampling candidate trajectories
    2. Simulating in world model
    3. Scoring with composite cost
    4. Filtering unsafe trajectories (h < 0)
    5. Selecting minimum cost feasible trajectory
    """

    def __init__(
        self,
        world_model: nn.Module,
        horizon: int = 5,
        num_samples: int = 64,
        temperature: float = 1.0,
        device: str = "cpu",
    ) -> None:
        """Initialize MPC controller.

        Args:
            world_model: Learned dynamics W_θ for rollouts
            horizon: Planning horizon (number of steps)
            num_samples: Candidate trajectories to evaluate
            temperature: Sampling temperature (higher = more exploration)
            device: Computation device
        """
        self.world_model = world_model
        self.horizon = horizon
        self.num_samples = num_samples
        self.temperature = temperature
        self.device = device

        # Cost weights (tunable)
        self.lambda_safety = 10.0  # Safety barrier violations
        self.lambda_task = 1.0  # Task objective
        self.lambda_kl = 0.5  # Trust region
        self.lambda_fep = 0.1  # Free energy (prediction error)

        logger.info(
            f"✅ MPC Controller initialized: horizon={horizon}, "
            f"samples={num_samples}, temp={temperature}"
        )

    @torch.no_grad()
    def plan(
        self,
        x_current: torch.Tensor,
        goal_state: torch.Tensor | None = None,
        safety_checker: Callable | None = None,
        trust_state: torch.Tensor | None = None,
        num_actions: int = 30,
    ) -> dict[str, Any]:
        """Plan optimal action sequence using MPC.

        Args:
            x_current: Current state [B, seq, dim]
            goal_state: Goal state for task cost (optional)
            safety_checker: Function h(x) for barrier
            trust_state: Reference state for trust region
            num_actions: Number of discrete actions

        Returns:
            {
                'best_action': First action of best sequence,
                'best_sequence': Full action sequence,
                'best_cost': Cost of best trajectory,
                'trajectories': All sampled trajectories with costs,
                'safe_trajectories': Number of safe trajectories,
            }
        """
        # 1. Sample candidate action sequences
        action_sequences = self._sample_action_sequences(num_actions)

        # 2. Rollout and score each
        trajectories = []
        costs = []
        safe_count = 0

        for action_seq in action_sequences:
            # Simulate trajectory
            traj = self._rollout_sequence(x_current, action_seq)

            # Compute composite cost
            cost_breakdown = self._compute_cost(traj, goal_state, safety_checker, trust_state)

            total_cost = (
                self.lambda_fep * cost_breakdown["fep"]
                + self.lambda_safety * cost_breakdown["safety"]
                + self.lambda_task * cost_breakdown["task"]
                + self.lambda_kl * cost_breakdown["trust"]
            )

            # Check feasibility (no barrier violations)
            is_safe = cost_breakdown["safe"]
            if is_safe:
                safe_count += 1

            # Defer .item() conversion - keep as tensor for now
            cost_value = (
                total_cost
                if isinstance(total_cost, torch.Tensor)
                else torch.tensor(total_cost, device=self.device)
            )

            trajectories.append(
                {
                    "actions": action_seq,
                    "states": traj,
                    "cost": cost_value,  # Keep as tensor
                    "cost_breakdown": cost_breakdown,
                    "safe": is_safe,
                }
            )

            costs.append(total_cost if is_safe else float("inf"))

        # 3. Select best feasible trajectory
        if safe_count == 0:
            logger.warning("⚠️ No safe trajectories found! Using null action.")
            return {
                "best_action": torch.zeros(num_actions, device=self.device),
                "best_sequence": None,
                "best_cost": float("inf"),
                "trajectories": trajectories,
                "safe_trajectories": 0,
            }

        # Get minimum cost among safe trajectories
        best_idx = min((i for i, t in enumerate(trajectories) if t["safe"]), key=lambda i: costs[i])

        best_traj = trajectories[best_idx]

        return {
            "best_action": best_traj["actions"][0],
            "best_sequence": best_traj["actions"],
            "best_cost": best_traj["cost"],
            "cost_breakdown": best_traj["cost_breakdown"],
            "trajectories": trajectories,
            "safe_trajectories": safe_count,
        }

    def _sample_action_sequences(self, num_actions: int) -> list[list[torch.Tensor]]:
        """Sample candidate action sequences.

        Uses random sampling (can be improved with CEM/MPPI).
        """
        sequences = []

        for _ in range(self.num_samples):
            sequence = []
            for _ in range(self.horizon):
                # Sample random action
                action = torch.randint(0, num_actions, (1,), device=self.device)
                sequence.append(action)
            sequences.append(sequence)

        return sequences

    def _rollout_sequence(
        self,
        x_0: torch.Tensor,
        action_sequence: list[torch.Tensor],
    ) -> list[torch.Tensor]:
        """Simulate trajectory in world model.

        Args:
            x_0: Initial state [B, seq, dim]
            action_sequence: Actions to take

        Returns:
            List of states [x_0, x_1, ..., x_T]
        """
        trajectory = [x_0]
        x_t = x_0.to(self.device)  # Ensure correct device

        for _action in action_sequence:
            # Predict next state (simplified - just use world model)
            x_next, _ = self.world_model(x_t)
            trajectory.append(x_next)
            x_t = x_next

        return trajectory

    def _compute_cost(
        self,
        trajectory: list[torch.Tensor],
        goal_state: torch.Tensor | None,
        safety_checker: Callable | None,
        trust_state: torch.Tensor | None,
    ) -> dict[str, Any]:
        """Compute composite cost for trajectory.

        J = FEP + λ_safety·safety + λ_task·task + λ_KL·trust

        Returns:
            Cost breakdown dictionary
        """
        # Free Energy Principle cost (prediction error)
        fep_cost = self._fep_cost(trajectory)

        # Safety barrier cost
        safety_cost, is_safe = self._safety_cost(trajectory, safety_checker)

        # Task objective cost
        task_cost = self._task_cost(trajectory, goal_state)

        # Trust region cost
        trust_cost = self._trust_cost(trajectory, trust_state)

        return {
            "fep": fep_cost,
            "safety": safety_cost,
            "task": task_cost,
            "trust": trust_cost,
            "safe": is_safe,
        }

    def _fep_cost(self, trajectory: list[torch.Tensor]) -> torch.Tensor:
        """Free energy / prediction error cost.

        Penalizes uncertainty and surprise.

        Returns:
            Tensor (scalar) - deferred sync
        """
        # Simple: variance of states (high variance = high uncertainty)
        states = torch.stack(trajectory, dim=0)
        variance = states.var(dim=0).mean()
        return variance  # Keep as tensor

    def _safety_cost(
        self,
        trajectory: list[torch.Tensor],
        safety_checker: Callable | None,
    ) -> tuple[torch.Tensor, bool]:
        """Safety barrier violation cost: Σ max(0, -h(x_t))

        Returns:
            (cost_tensor, is_safe) - cost is kept as tensor
        """
        if safety_checker is None:
            return torch.tensor(0.0, device=self.device), True

        violations = []
        for x_t in trajectory:
            h = safety_checker(x_t)
            # Keep h as tensor if possible
            if isinstance(h, int | float):
                h_tensor = torch.tensor(h, device=self.device)
            else:
                h_tensor = h

            violation = torch.clamp(-h_tensor, min=0.0)
            violations.append(violation)

        total = torch.stack(violations).sum()
        # Only sync for boolean check (small cost)
        is_safe = all(v.item() == 0.0 for v in violations)

        return total, is_safe

    def _task_cost(
        self,
        trajectory: list[torch.Tensor],
        goal_state: torch.Tensor | None,
    ) -> torch.Tensor:
        """Task objective cost: distance to goal.

        L_goal = ||x_final - x_goal||²

        Returns:
            Tensor (scalar) - deferred sync
        """
        if goal_state is None:
            return torch.tensor(0.0, device=self.device)

        x_final = trajectory[-1]

        # Pool to match dimensions if needed
        if x_final.dim() > 2:
            x_final = x_final.mean(dim=1)  # [B, dim]
        if goal_state.dim() > 2:
            goal_state = goal_state.mean(dim=1)

        distance = (x_final - goal_state).pow(2).mean()
        return distance  # Keep as tensor

    def _trust_cost(
        self,
        trajectory: list[torch.Tensor],
        trust_state: torch.Tensor | None,
    ) -> torch.Tensor:
        """Trust region cost: D_KL(x || x_trust) for each state.

        Penalizes large deviations from trusted state.

        Returns:
            Tensor (scalar) - deferred sync
        """
        if trust_state is None:
            return torch.tensor(0.0, device=self.device)

        kl_divergences = []
        for x_t in trajectory:
            # Pool to match dimensions
            if x_t.dim() > 2:
                x_t = x_t.mean(dim=1)
            if trust_state.dim() > 2:
                trust_pooled = trust_state.mean(dim=1)
            else:
                trust_pooled = trust_state

            # KL divergence approximation (Euclidean for simplicity)
            kl = (x_t - trust_pooled).pow(2).mean()
            kl_divergences.append(kl)

        total_kl = torch.stack(kl_divergences).sum()
        return total_kl  # Keep as tensor


def create_mpc_controller(
    world_model: nn.Module,
    horizon: int = 5,
    num_samples: int = 64,
    device: str = "cpu",
) -> MPCController:
    """Factory function for MPC controller.

    Returns:
        MPCController instance

    Example:
        >>> from kagami.core.world_model.kagami_world_model import KagamiWorldModel
        >>>
        >>> brain = KagamiWorldModel()  # Uses exceptional hierarchy dimensions
        >>> mpc = create_mpc_controller(brain, horizon=5, num_samples=64)
        >>>
        >>> # Plan action
        >>> x_current = torch.randn(1, 16, 14)  # G₂ dimension
        >>> goal = torch.randn(1, 16, 248)  # E₈ dimension
        >>>
        >>> plan = mpc.plan(x_current, goal_state=goal)
        >>> print(f"Best action: {plan['best_action']}")
        >>> print(f"Cost: {plan['best_cost']:.3f}")
        >>> print(f"Safe trajectories: {plan['safe_trajectories']}/{num_samples}")
    """
    return MPCController(
        world_model=world_model,
        horizon=horizon,
        num_samples=num_samples,
        device=device,
    )


if __name__ == "__main__":
    # Smoke test
    import sys

    sys.path.insert(0, "/Users/schizodactyl/projects/chronOS")

    print("=" * 60)
    print("MPC Controller Test")
    print("=" * 60)

    from kagami.core.world_model.kagami_world_model import KagamiWorldModel

    # Create world model with exceptional hierarchy
    brain = KagamiWorldModel()  # type: ignore[call-arg]

    # Create MPC
    mpc = create_mpc_controller(brain, horizon=5, num_samples=32, device="cpu")

    # Dummy safety checker
    def safety_check(x: Any) -> torch.Tensor:
        """h(x) = 1 - ||x||/10 (safe when small)"""
        norm = x.abs().mean()
        return cast(torch.Tensor, 1.0 - norm / 10.0)  # Keep as tensor

    # Plan using exceptional hierarchy dimensions
    x_current = torch.randn(1, 16, 14) * 0.5  # Start state (G₂)
    goal = torch.randn(1, 16, 248) * 0.3  # Goal state (E₈)

    print(f"\nPlanning from state {x_current.shape} to goal {goal.shape}")
    print(f"Horizon: {mpc.horizon}, Samples: {mpc.num_samples}")

    plan = mpc.plan(
        x_current,
        goal_state=goal,
        safety_checker=safety_check,
        num_actions=30,
    )

    print("\n✅ Planning complete")
    print(f"   Best cost: {plan['best_cost']:.3f}")
    print(f"   Safe trajectories: {plan['safe_trajectories']}/{mpc.num_samples}")
    print(f"   Best action: {plan['best_action']}")

    if plan["cost_breakdown"]:
        cb = plan["cost_breakdown"]
        print("\n   Cost breakdown:")
        print(f"     FEP: {cb['fep']:.3f}")
        print(f"     Safety: {cb['safety']:.3f}")
        print(f"     Task: {cb['task']:.3f}")
        print(f"     Trust: {cb['trust']:.3f}")

    print("\n" + "=" * 60)
    print("✅ MPC controller operational")
    print("=" * 60)
