"""Skill Compiler - Distill Mode-2 Planning into Mode-1 Reactive Policies.

LeCun: "Once an optimal action sequence is obtained through the planning/
inference/optimization process, one can use the actions as targets to train
a policy network. The policy network may subsequently be used to act quickly,
or merely to initialize the proposed action sequence to a good starting point
before the optimization phase."

This is AMORTIZED INFERENCE: expensive planning is "compiled" into fast
reactive policies that can be deployed in Mode-1.

Process:
    1. Run Mode-2 planning on various goals/situations
    2. Collect (state, optimal_action) pairs
    3. Train policy network to imitate optimal actions
    4. Deploy policy for fast Mode-1 execution

Benefits:
    - Fast inference (Mode-1) with quality of planning (Mode-2)
    - Generalizes planning to unseen situations
    - Multiple skills can execute in parallel (unlike Mode-2)

Created: December 6, 2025
Reference: LeCun (2022), Section 3.1.3 "From Mode-2 to Mode-1"
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


@dataclass
class SkillCompilerConfig:
    """Configuration for skill compilation."""

    # Policy network architecture
    state_dim: int = 256
    action_dim: int = 8
    hidden_dim: int = 256
    n_layers: int = 3

    # Training
    learning_rate: float = 3e-4
    batch_size: int = 64
    gradient_clip: float = 1.0

    # Distillation buffer
    buffer_size: int = 100_000
    min_buffer_size: int = 1000  # Min samples before training

    # Planning parameters
    planning_horizon: int = 20
    planning_episodes: int = 100  # Episodes to collect per skill

    # Skill management
    max_skills: int = 50
    skill_convergence_threshold: float = 0.01  # Loss threshold for "done"

    # Loss function
    loss_type: str = "mse"  # "mse", "huber", "kl"
    temperature: float = 1.0  # For KL divergence


@dataclass
class DistillationSample:
    """A single (state, optimal_action) pair from planning."""

    state: torch.Tensor
    optimal_action: torch.Tensor
    goal: torch.Tensor | None = None
    value_estimate: float = 0.0
    planning_confidence: float = 1.0


class DistillationBuffer:
    """Replay buffer for skill distillation.

    Stores (state, optimal_action) pairs from Mode-2 planning.
    """

    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self.buffer: deque[DistillationSample] = deque(maxlen=capacity)

    def add(self, sample: DistillationSample) -> None:
        """Add a sample to the buffer."""
        self.buffer.append(sample)

    def add_batch(
        self,
        states: torch.Tensor,
        actions: torch.Tensor,
        goals: torch.Tensor | None = None,
    ) -> None:
        """Add a batch of samples."""
        B = states.shape[0]
        for i in range(B):
            goal = goals[i] if goals is not None else None
            sample = DistillationSample(
                state=states[i].detach().cpu(),
                optimal_action=actions[i].detach().cpu(),
                goal=goal.detach().cpu() if goal is not None else None,
            )
            self.add(sample)

    def sample(self, batch_size: int) -> dict[str, torch.Tensor]:
        """Sample a batch of training data."""
        import random

        if len(self.buffer) < batch_size:
            batch_size = len(self.buffer)

        samples = random.sample(list(self.buffer), batch_size)

        states = torch.stack([s.state for s in samples])
        actions = torch.stack([s.optimal_action for s in samples])

        result = {"states": states, "actions": actions}

        # Include goals if available
        if samples[0].goal is not None:
            goals = torch.stack([s.goal for s in samples if s.goal is not None])
            if len(goals) == len(samples):
                result["goals"] = goals

        return result

    def __len__(self) -> int:
        return len(self.buffer)


class PolicyNetwork(nn.Module):
    """Reactive policy network for Mode-1 execution.

    Takes state (and optionally goal) and outputs action.

    LeCun: "The policy module can be seen as performing a form of
    amortized inference."
    """

    def __init__(self, config: SkillCompilerConfig, goal_conditioned: bool = False) -> None:
        super().__init__()
        self.config = config
        self.goal_conditioned = goal_conditioned

        input_dim = config.state_dim
        if goal_conditioned:
            input_dim += config.state_dim  # Concatenate goal

        # Build network
        layers = []
        current_dim = input_dim

        for _i in range(config.n_layers):
            layers.extend(
                [
                    nn.Linear(current_dim, config.hidden_dim),
                    nn.LayerNorm(config.hidden_dim),
                    nn.GELU(),
                ]
            )
            current_dim = config.hidden_dim

        self.encoder = nn.Sequential(*layers)
        self.action_head = nn.Linear(config.hidden_dim, config.action_dim)

        # Initialize output layer small for stable training
        nn.init.xavier_uniform_(self.action_head.weight, gain=0.01)
        nn.init.zeros_(self.action_head.bias)

    def forward(
        self,
        state: torch.Tensor,
        goal: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Compute action from state.

        Args:
            state: [B, state_dim] current state
            goal: [B, state_dim] optional goal (for goal-conditioned policy)

        Returns:
            [B, action_dim] action
        """
        if self.goal_conditioned:
            if goal is None:
                raise ValueError("Goal required for goal-conditioned policy")
            x = torch.cat([state, goal], dim=-1)
        else:
            x = state

        hidden = self.encoder(x)
        action = self.action_head(hidden)

        # Bound action (tanh for continuous, or softmax for discrete)
        action = torch.tanh(action)

        return action


class CompiledSkill:
    """A compiled skill - a trained policy for a specific task type."""

    def __init__(
        self,
        skill_id: str,
        policy: PolicyNetwork,
        task_type: str,
        training_loss: float,
        n_episodes: int,
    ) -> None:
        self.skill_id = skill_id
        self.policy = policy
        self.task_type = task_type
        self.training_loss = training_loss
        self.n_episodes = n_episodes
        self.usage_count = 0
        self.success_rate = 0.0

    def execute(
        self,
        state: torch.Tensor,
        goal: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Execute the skill (Mode-1)."""
        self.usage_count += 1
        with torch.no_grad():
            return self.policy(state, goal)


class SkillCompiler:
    """Compiles Mode-2 planning results into Mode-1 reactive policies.

    LeCun: "This process allows the agent to use the full power of its world
    model and reasoning capabilities to acquire new skills that are then
    'compiled' into a reactive policy module that no longer requires careful
    planning."

    Usage:
        compiler = SkillCompiler()

        # Compile a skill from planning
        skill = await compiler.compile_skill(
            task_type="navigate",
            world_model=world_model,
            planner=planner,
            n_episodes=100,
        )

        # Use skill for fast reactive execution
        action = skill.execute(current_state, goal)
    """

    def __init__(self, config: SkillCompilerConfig | None = None) -> None:
        self.config = config or SkillCompilerConfig()

        # Compiled skills registry
        self._skills: dict[str, CompiledSkill] = {}

        # World model and planner references (lazy loaded)
        self._world_model = None
        self._planner = None

        logger.info(
            f"SkillCompiler initialized: buffer={self.config.buffer_size}, "
            f"hidden={self.config.hidden_dim}"
        )

    def _ensure_planner(self) -> None:
        """Lazy load planner if not set[Any].

        Wires to ModelBasedPlanner for Mode-2 planning.
        """
        if self._planner is not None:
            return

        try:
            from kagami.core.reasoning.planning.model_based_planner import ModelBasedPlanner

            if self._world_model is None:
                self._ensure_world_model()

            self._planner = ModelBasedPlanner(  # type: ignore[assignment]
                world_model=self._world_model,
                horizon=self.config.planning_horizon,
                n_candidates=100,
                method="cem",
            )
            logger.info("SkillCompiler: Wired to ModelBasedPlanner")
        except ImportError:
            logger.warning("ModelBasedPlanner not available for SkillCompiler")

    def _ensure_world_model(self) -> None:
        """Lazy load world model if not set[Any]."""
        if self._world_model is not None:
            return

        try:
            from kagami.core.world_model.service import get_world_model_service

            service = get_world_model_service()
            self._world_model = service.model  # type: ignore[assignment]
            logger.info("SkillCompiler: Wired to KagamiWorldModel via service")
        except ImportError:
            logger.warning("WorldModelService not available for SkillCompiler")

    def set_world_model(self, world_model: Any) -> None:
        """Set reference to world model for planning."""
        self._world_model = world_model

    def set_planner(self, planner: Any) -> None:
        """Set reference to planner for Mode-2."""
        self._planner = planner

    async def collect_planning_trace(
        self,
        initial_state: torch.Tensor,
        goal: torch.Tensor,
    ) -> list[DistillationSample]:
        """Run Mode-2 planning and collect (state, action) pairs.

        Args:
            initial_state: Starting state
            goal: Goal state

        Returns:
            List of DistillationSample from the planning trace
        """
        # Ensure planner and world model are wired
        self._ensure_world_model()
        self._ensure_planner()

        if self._world_model is None or self._planner is None:
            raise RuntimeError("World model and planner must be set[Any]")

        trace = []

        try:
            # Run Mode-2 planning
            plan_result = await self._planner.plan(
                initial_state,
                goal,
                horizon=self.config.planning_horizon,
            )

            # Extract optimal actions
            if hasattr(plan_result, "low_level_actions"):
                optimal_actions = plan_result.low_level_actions
            elif isinstance(plan_result, list):
                optimal_actions = plan_result
            else:
                optimal_actions = [plan_result]

            # Simulate trajectory and collect (state, action) pairs
            current_state = initial_state.clone()

            for action in optimal_actions:
                # Convert action to tensor if needed
                if isinstance(action, dict):
                    action_tensor = torch.tensor(list(action.values()), dtype=torch.float32)
                elif isinstance(action, torch.Tensor):
                    action_tensor = action
                else:
                    continue

                # Store sample
                sample = DistillationSample(
                    state=current_state.clone(),
                    optimal_action=action_tensor,
                    goal=goal.clone(),
                )
                trace.append(sample)

                # Predict next state (for next iteration)
                if hasattr(self._world_model, "predict_next"):
                    try:
                        next_result = self._world_model.predict_next(
                            current_state.unsqueeze(0), action_tensor.unsqueeze(0)
                        )
                        if isinstance(next_result, dict):
                            current_state = next_result["x_next"].squeeze(0)
                        else:
                            current_state = next_result.squeeze(0)
                    except Exception:
                        break  # Can't continue without prediction
                else:
                    break

        except Exception as e:
            logger.warning(f"Planning trace collection failed: {e}")

        return trace

    def distill_step(
        self,
        policy: PolicyNetwork,
        optimizer: torch.optim.Optimizer,
        buffer: DistillationBuffer,
    ) -> dict[str, float]:
        """Execute one distillation training step.

        Args:
            policy: Policy network to train
            optimizer: Optimizer for policy
            buffer: Buffer with planning samples

        Returns:
            Training metrics
        """
        if len(buffer) < self.config.min_buffer_size:
            return {"status": "insufficient_data"}  # type: ignore[dict-item]

        # Sample batch
        batch = buffer.sample(self.config.batch_size)
        states = batch["states"]
        optimal_actions = batch["actions"]
        goals = batch.get("goals")

        # Move to device
        device = next(policy.parameters()).device
        states = states.to(device)
        optimal_actions = optimal_actions.to(device)
        if goals is not None:
            goals = goals.to(device)

        # Forward pass
        predicted_actions = policy(states, goals)

        # Compute loss
        if self.config.loss_type == "mse":
            loss = F.mse_loss(predicted_actions, optimal_actions)
        elif self.config.loss_type == "huber":
            loss = F.smooth_l1_loss(predicted_actions, optimal_actions)
        elif self.config.loss_type == "kl":
            # Treat as distributions and compute KL
            pred_log = F.log_softmax(predicted_actions / self.config.temperature, dim=-1)
            target_prob = F.softmax(optimal_actions / self.config.temperature, dim=-1)
            loss = F.kl_div(pred_log, target_prob, reduction="batchmean")
        else:
            loss = F.mse_loss(predicted_actions, optimal_actions)

        # Backward pass
        optimizer.zero_grad()
        loss.backward()

        # Gradient clipping
        if self.config.gradient_clip > 0:
            torch.nn.utils.clip_grad_norm_(policy.parameters(), self.config.gradient_clip)

        optimizer.step()

        return {
            "loss": loss.item(),
            "batch_size": len(states),
            "buffer_size": len(buffer),
        }

    async def compile_skill(
        self,
        task_type: str,
        n_episodes: int | None = None,
        goal_conditioned: bool = True,
        goal_sampler: Any = None,
        initial_state_sampler: Any = None,
    ) -> CompiledSkill:
        """Compile a skill from Mode-2 planning.

        LeCun: "Once an optimal action sequence is obtained through the
        planning/inference/optimization process, one can use the actions
        as targets to train a policy network."

        This is the main API for skill compilation. It:
        1. Runs Mode-2 planning multiple times
        2. Collects (state, optimal_action) pairs
        3. Trains policy network via behavioral cloning
        4. Returns compiled skill for Mode-1 use

        Args:
            task_type: Type of skill to compile
            n_episodes: Number of planning episodes (default from config)
            goal_conditioned: Whether policy should be goal-conditioned
            goal_sampler: Function to sample goals
            initial_state_sampler: Function to sample initial states

        Returns:
            CompiledSkill ready for Mode-1 execution
        """
        # Ensure planner is wired
        self._ensure_world_model()
        self._ensure_planner()

        if n_episodes is None:
            n_episodes = self.config.planning_episodes

        # Create policy network
        policy = PolicyNetwork(self.config, goal_conditioned=goal_conditioned)
        # Use unified device selection (MPS > CUDA > CPU)
        from kagami.core.utils.device import get_device

        device = get_device()
        policy = policy.to(device)

        # Create optimizer
        optimizer = torch.optim.AdamW(policy.parameters(), lr=self.config.learning_rate)

        # Create distillation buffer
        buffer = DistillationBuffer(self.config.buffer_size)

        # Collect planning traces
        logger.info(f"Compiling skill '{task_type}' from {n_episodes} episodes...")

        final_loss = float("inf")

        for episode in range(n_episodes):
            # Sample initial state and goal
            if initial_state_sampler:
                initial_state = initial_state_sampler()
            else:
                initial_state = torch.randn(self.config.state_dim)

            if goal_sampler:
                goal = goal_sampler()
            else:
                goal = torch.randn(self.config.state_dim)

            # Collect planning trace
            try:
                trace = await self.collect_planning_trace(initial_state, goal)

                # Add to buffer
                for sample in trace:
                    buffer.add(sample)

            except Exception as e:
                logger.debug(f"Episode {episode} failed: {e}")
                continue

            # Train if buffer has enough samples
            if len(buffer) >= self.config.min_buffer_size:
                for _ in range(5):  # Multiple gradient steps per episode
                    metrics = self.distill_step(policy, optimizer, buffer)
                    if "loss" in metrics:
                        final_loss = metrics["loss"]

            # Log progress
            if (episode + 1) % 10 == 0:
                logger.info(
                    f"Skill '{task_type}': episode {episode + 1}/{n_episodes}, "
                    f"buffer={len(buffer)}, loss={final_loss:.4f}"
                )

            # Early stopping if converged
            if final_loss < self.config.skill_convergence_threshold:
                logger.info(f"Skill '{task_type}' converged at episode {episode + 1}")
                break

        # Create compiled skill
        skill = CompiledSkill(
            skill_id=f"{task_type}_{len(self._skills)}",
            policy=policy,
            task_type=task_type,
            training_loss=final_loss,
            n_episodes=n_episodes,
        )

        # Register skill
        self._skills[skill.skill_id] = skill

        logger.info(
            f"Compiled skill '{skill.skill_id}': loss={final_loss:.4f}, episodes={n_episodes}"
        )

        return skill

    def get_skill(self, skill_id: str) -> CompiledSkill | None:
        """Get a compiled skill by ID."""
        return self._skills.get(skill_id)

    def get_skill_for_task(self, task_type: str) -> CompiledSkill | None:
        """Get best skill for a task type."""
        candidates = [s for s in self._skills.values() if s.task_type == task_type]
        if not candidates:
            return None

        # Return skill with lowest training loss
        return min(candidates, key=lambda s: s.training_loss)

    def list_skills(self) -> list[str]:
        """List all compiled skill IDs."""
        return list(self._skills.keys())


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_skill_compiler: SkillCompiler | None = None


def get_skill_compiler(config: SkillCompilerConfig | None = None) -> SkillCompiler:
    """Get or create the global SkillCompiler."""
    global _skill_compiler
    if _skill_compiler is None:
        _skill_compiler = SkillCompiler(config)
    return _skill_compiler


def reset_skill_compiler() -> None:
    """Reset the global skill compiler (for testing)."""
    global _skill_compiler
    _skill_compiler = None
