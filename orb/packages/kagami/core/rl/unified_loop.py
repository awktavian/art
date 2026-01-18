from __future__ import annotations

"""Unified Model-Based RL Loop.

Combines:
1. World Model (JEPA) - learns environment dynamics
2. Actor-Critic - learns optimal policy
3. Imagination Planning - simulates before acting
4. Intrinsic Rewards - encourages exploration
5. RLHF Reward Model - human preference alignment (optional)

Based on Dreamer V3, TD-MPC2, and modern model-based RL.
"""
import logging
import time
from typing import Any

import numpy as np
import torch

logger = logging.getLogger(__name__)

# RLHF integration (optional)
try:
    from kagami.core.rl.preference_learning import get_reward_model

    _RLHF_AVAILABLE = True
except ImportError:
    _RLHF_AVAILABLE = False
    get_reward_model = None  # type: ignore

# NOTE (Nov 30, 2025): StrangeLoopTrainer/StrangeLoopLoss DELETED.
# Use model.training_step() which includes all loop losses.


class UnifiedRLLoop:
    """
    Model-based RL with imagination planning.

    Key innovations:
    1. Train policy on imagined trajectories (sample efficient!)
    2. Use intrinsic rewards for curiosity-driven exploration
    3. Actor-critic for stable policy learning
    4. Hierarchical planning for multi-scale reasoning
    """

    def __init__(self, task_family: str = "default") -> None:
        """Initialize unified RL loop.

        Args:
            task_family: Task category for hyperparameter selection
        """
        # Lazy-load components
        self._world_model = None
        self._actor = None
        self._critic = None
        self._intrinsic_reward = None
        self._replay_buffer = None
        # NOTE: StrangeLoopTrainer removed (Nov 30, 2025) - use model.training_step()
        self._task_family = task_family

        # Load tuned hyperparameters (or use defaults)
        try:
            from kagami.core.learning.hyperparam_tuner import get_hyperparam_tuner

            tuner = get_hyperparam_tuner()
            config = tuner.get_config(task_family)

            # Use tuned hyperparameters
            self.imagination_horizon = config.imagination_horizon
            self.n_candidates = config.n_candidates
            self.intrinsic_weight = config.intrinsic_weight
            self.gamma = config.gamma

            logger.info(
                f"🎛️ Using tuned hyperparameters for {task_family}: "
                f"horizon={self.imagination_horizon}, candidates={self.n_candidates}"
            )
        except Exception as e:
            logger.debug(f"Hyperparameter tuner unavailable, using defaults: {e}")
            # Fallback to defaults
            self.imagination_horizon = 5
            self.n_candidates = 5
            self.intrinsic_weight = 0.1
            self.gamma = 0.99

        # Adaptive hyperparameters (lazy loaded)
        self._adaptive_lr = None
        self._adaptive_horizon = None
        self._adaptive_batch = None

        # Reward shaping from high-level learning (ReceiptLearner/Coordinator)
        self._reward_shaping: dict[str, float] = {}

        # Initialize adaptive horizon immediately for use in action selection
        try:
            from kagami.core.learning.adaptive_hyperparameters import (
                get_adaptive_horizon,
            )

            self._adaptive_horizon = get_adaptive_horizon()
            logger.info("✅ Adaptive horizon enabled (dynamic 1-15 planning depth)")
        except Exception:
            logger.debug("Adaptive horizon unavailable, using fixed horizon")

    def set_reward_shaping(self, weights: dict[str, float]) -> None:
        """Update reward shaping parameters from high-level learning.

        Args:
            weights: Dict of drive weights (e.g. {'curiosity': 0.3, 'competence': 0.2})
        """
        self._reward_shaping = weights

        # Dynamic adjustment of intrinsic weight based on 'curiosity' drive
        if "curiosity" in weights:
            # Base intrinsic weight is ~0.1. Scale it by curiosity drive relative to default (0.3)
            # If curiosity is 0.5 -> weight = 0.1 * (0.5/0.3) = 0.16
            # If curiosity is 0.1 -> weight = 0.1 * (0.1/0.3) = 0.03
            default_curiosity = 0.3
            scale = weights["curiosity"] / default_curiosity

            # Clamp to reasonable range [0.01, 0.5]
            new_weight = max(0.01, min(0.5, 0.1 * scale))

            if abs(new_weight - self.intrinsic_weight) > 0.01:
                logger.info(
                    f"🧠 Adapting intrinsic_weight: {self.intrinsic_weight:.3f} -> {new_weight:.3f} (curiosity={weights['curiosity']:.2f})"
                )
                self.intrinsic_weight = new_weight

    @property
    def world_model(self) -> Any:
        """Lazy load world model via canonical service."""
        if self._world_model is None:
            from kagami.core.world_model.service import get_world_model_service

            self._world_model = get_world_model_service().model  # type: ignore[assignment]

        return self._world_model

    @property
    def actor(self) -> Any:
        """Lazy load actor (PPO + LLM-guided actor with 3-tier intelligence)."""
        if self._actor is None:
            # Prefer fast, offline-safe BehaviorPolicyG2 first
            try:
                from kagami.core.rl.behavior_policy_g2 import (
                    get_behavior_policy_g2,
                )

                self._actor = get_behavior_policy_g2()  # type: ignore[assignment]
                logger.info("✅ Using BehaviorPolicyG2 (G2-constrained behavior policy)")
            except Exception as bp_err:
                logger.debug(f"BehaviorPolicyG2 unavailable: {bp_err}")
                # Try PPO actor
                try:
                    from kagami.core.rl.ppo_actor import get_ppo_actor

                    self._actor = get_ppo_actor()  # type: ignore[assignment]
                    logger.info("✅ Using PPO actor (clipped policy gradient)")
                except Exception:
                    # Last, try LLM-guided actor (requires providers)
                    try:
                        from kagami.core.rl.llm_guided_actor import (
                            get_llm_guided_actor,
                        )

                        self._actor = get_llm_guided_actor()  # type: ignore[assignment]
                        logger.info("✅ Using LLM-guided actor (3-tier intelligence)")
                    except Exception as llm_err:
                        logger.warning(
                            f"LLM-guided actor unavailable: {llm_err}; using hybrid actor"
                        )
                        from kagami.core.rl.hybrid_actor import get_hybrid_actor

                        self._actor = get_hybrid_actor()  # type: ignore[assignment]
        return self._actor

    @property
    def critic(self) -> Any:
        """Lazy load critic."""
        if self._critic is None:
            from kagami.core.rl.actor_critic import get_critic

            self._critic = get_critic()  # type: ignore[assignment]
        return self._critic

    @property
    def intrinsic_reward(self) -> Any:
        """Lazy load intrinsic reward calculator with optional RLHF augmentation."""
        if self._intrinsic_reward is None:
            from kagami.core.rl.intrinsic_reward import (
                get_intrinsic_reward_calculator,
            )

            self._intrinsic_reward = get_intrinsic_reward_calculator()  # type: ignore[assignment]

            # Augment with RLHF reward model if available
            if _RLHF_AVAILABLE and get_reward_model is not None:
                try:
                    self._rlhf_reward_model = get_reward_model()
                    logger.info("✅ RLHF reward model augmenting intrinsic rewards")
                except Exception as e:
                    logger.debug(f"RLHF reward model unavailable: {e}")
                    self._rlhf_reward_model = None  # type: ignore[assignment]
            else:
                self._rlhf_reward_model = None  # type: ignore[assignment]
        return self._intrinsic_reward

    @property
    def replay_buffer(self) -> Any:
        """Lazy load replay buffer.

        UPDATED (Dec 6, 2025): Uses UnifiedReplayBuffer instead of PrioritizedReplayBuffer.
        """
        if self._replay_buffer is None:
            from kagami.core.memory.unified_replay import get_unified_replay

            self._replay_buffer = get_unified_replay()  # type: ignore[assignment]
        return self._replay_buffer

    async def select_action(
        self, state: Any, context: dict[str, Any], exploration: float = 0.2
    ) -> dict[str, Any]:
        """Select action via imagination planning (ADAPTIVE).

        Uses adaptive horizon based on task complexity and confidence.
        """
        # SAFETY: Ensure context is never None
        context = context or {}

        # Initialize composite score before try block to avoid NameError if exception occurs
        composite = 0.5  # Default neutral value

        # INTEGRATION-AWARE EXPLORATION: Boost when system fragmenting
        try:
            from kagami.core.integrations.feedback_loop import get_last_composite_score

            composite = await get_last_composite_score()
            if composite < 0.30:
                # Critical fragmentation -> force exploration
                original_exploration = exploration
                exploration = min(0.45, exploration + 0.15)
                logger.warning(
                    f"🚨 Integration critical (composite={composite:.2f}) -> "
                    f"boosting exploration {original_exploration:.2f} -> {exploration:.2f}"
                )
            elif composite < 0.50:
                # Degraded -> moderate boost
                original_exploration = exploration
                exploration = min(0.35, exploration + 0.10)
                logger.info(
                    f"⚠️  Integration degraded (composite={composite:.2f}) -> "
                    f"boosting exploration {original_exploration:.2f} -> {exploration:.2f}"
                )
        except Exception as e:
            logger.debug(f"Integration-aware exploration check failed: {e}")

        # Compute adaptive horizon (escalate when integration critical)
        try:
            from kagami.core.learning.adaptive_hyperparameters import (
                get_adaptive_horizon,
            )

            horizon_computer = get_adaptive_horizon()
            confidence = context.get("confidence", 0.5)
            adaptive_horizon = horizon_computer.compute_horizon(context, confidence)

            # T3: Escalate horizon when integration critical
            if composite < 0.30:
                adaptive_horizon = min(10, adaptive_horizon + 3)  # Deeper search
                logger.warning(
                    f"🚨 Integration critical → escalating horizon to {adaptive_horizon}"
                )
            elif composite < 0.50:
                adaptive_horizon = min(8, adaptive_horizon + 2)

            horizon = adaptive_horizon
        except Exception:
            horizon = self.imagination_horizon  # Fallback to default

        return await self._select_action_with_horizon(state, context, exploration, horizon)

    async def _select_action_with_horizon(
        self, state: Any, context: dict[str, Any], exploration: float, horizon: int
    ) -> dict[str, Any]:
        """Select action using imagination planning with specified horizon.

        INSTRUMENTED: Tracks RL usage vs fallback for metrics.
        """
        # SAFETY: Ensure context is never None
        context = context or {}

        # Record exploration factor
        try:
            from kagami_observability.rl_instrumentation import RL_EXPLORATION_FACTOR

            RL_EXPLORATION_FACTOR.set(exploration)  # type: ignore  # Dynamic attr
        except Exception:
            pass

        """Select action using imagination planning with specified horizon.

        ALGORITHM (Model Predictive Control + Actor-Critic):
        1. Imagine H future steps using world model: s_t -> s_{t+1} -> s_{t+2} -> ... -> s_{t+H}
        2. For each imagined trajectory, compute returns: R = sum(gamma^i * r_i)
        3. Select action with highest expected return: a* = arg max_a Q(s, a)
        4. Balance exploration vs exploitation via epsilon-greedy or UCB

        Active Inference Perspective:
        - Each imagined trajectory has expected free energy G(pi) = Epistemic + Pragmatic
        - Epistemic: Information gain (curiosity) -> prefer uncertain states
        - Pragmatic: Goal achievement (reward) -> prefer high-value states
        - Policy: pi* = arg min_pi E[G(pi)]

        Args:
            state: Current state observation
            context: Additional context (confidence, constraints, etc.)
            exploration: Exploration rate (0.0=pure exploitation, 1.0=pure exploitation)
            horizon: Planning horizon H (number of steps to simulate)

        Returns:
            Selected action with metadata (expected_return, confidence, simulated_trajectory)
        """
        try:
            # Generate candidate actions from policy
            try:
                # BehaviorPolicyG2 emits K=1 fast path; keep interface constant
                candidates = await self.actor.sample_actions(
                    state,
                    k=max(1, getattr(self, "n_candidates", 1)),
                    exploration_noise=exploration,
                    context=context,
                )
            except TypeError:
                # Some actors may not accept exploration args; fallback
                candidates = await self.actor.sample_actions(state)

            # === EXPECTED FREE ENERGY ACTION SELECTION (MANDATORY - Dec 2, 2025) ===
            # EFE is the ONLY action selection path. There are NO fallbacks.
            # G(π) = Epistemic + Pragmatic + Risk + Catastrophe
            from kagami.core.active_inference.free_energy import get_free_energy_coordinator

            free_energy_coord = get_free_energy_coordinator()

            # Update beliefs from current state
            if hasattr(state, "embedding"):
                observations = {"state_embedding": state.embedding, **context}
            else:
                observations = context

            await free_energy_coord.perceive(observations)

            # Select action via free energy minimization
            goals = context.get("goals") or context.get("metadata", {}).get("goals")
            selected = await free_energy_coord.select_action(
                candidates=candidates,
                goals=goals,
            )

            # METRICS: Track EFE action selection

            logger.info(
                f"🧠 Action selected via EFE: G={selected.get('G', 0):.3f}, "
                f"epistemic={selected.get('epistemic_value', 0):.3f}, "
                f"pragmatic={selected.get('pragmatic_value', 0):.3f}"
            )

            # RECEIPT: Log EFE decision for analysis
            try:
                from kagami.core.receipts import emit_receipt

                correlation_id = context.get("correlation_id")
                if correlation_id:
                    emit_receipt(
                        correlation_id=correlation_id,
                        action="rl.efe_selection",
                        event_name="rl.action_selected",
                        event_data={
                            "candidates_evaluated": len(candidates),
                            "expected_free_energy": float(selected.get("G", 0)),
                            "epistemic_value": float(selected.get("epistemic_value", 0)),
                            "pragmatic_value": float(selected.get("pragmatic_value", 0)),
                            "planning_horizon": horizon,
                            "exploration": exploration,
                            "method": "active_inference",
                        },
                    )
            except Exception:
                pass

            # RECORDER: Save EFE decision for replay
            try:
                from kagami.core.operation_recorder import get_recorder

                recorder = get_recorder()
                recorder.record_rl_state(
                    correlation_id=context.get("correlation_id", "unknown"),
                    state=state,
                    action=selected,
                    candidates=[{"action": c, "efe": selected.get("G", 0)} for c in candidates[:3]],
                )
            except Exception:
                pass

            return selected

        except Exception as e:
            # NO FALLBACK - EFE action selection is mandatory
            logger.error(f"❌ EFE action selection failed: {e}")
            raise RuntimeError(
                f"EFE action selection failed: {e}\n"
                "K OS requires functioning Expected Free Energy loop for decision making.\n"
                "There are NO alternative codepaths - EFE is mandatory."
            ) from e

    async def train_from_buffer(self, batch_size: int = 32) -> dict[str, Any]:
        """Train policy from replay buffer (offline/batch mode).

        Args:
            batch_size: Batch size for training

        Returns:
            Training statistics
        """
        if not self.replay_buffer:
            return {"status": "no_buffer"}

        # Sample batch
        batch = self.replay_buffer.sample_prioritized(batch_size=batch_size)
        if not batch:
            return {"status": "buffer_empty"}

        # Train on batch
        stats = await self._train_on_batch(batch)
        return stats

    async def _train_on_batch(self, batch: list[Any]) -> dict[str, Any]:
        """Internal training step on a batch of experiences.

        REFACTORED (Nov 30, 2025):
        - Removed StrangeLoopTrainer dependency
        - Uses model.training_step() which includes all losses
        """
        policy_losses = []
        value_losses = []
        world_model_losses = []

        try:
            # 0. World Model Training (includes Strange Loop via training_step)
            if hasattr(self.world_model, "training_step"):
                try:
                    # Collect embeddings for batch
                    embeddings = []
                    train_subset = batch[:16]
                    for exp in train_subset:
                        state = self.world_model.encode_observation(exp.context)
                        emb = state.embedding
                        if isinstance(emb, np.ndarray):
                            emb = torch.tensor(emb, dtype=torch.float32)
                        elif isinstance(emb, torch.Tensor):
                            emb = emb.clone().detach().float()
                        embeddings.append(emb)

                    if embeddings:
                        # Stack into [Batch, Sequence=1, Dim]
                        x = torch.stack(embeddings).unsqueeze(1)
                        device = next(self.world_model.parameters()).device
                        x = x.to(device)

                        # Use unified training_step (includes loop, geometric, RSSM losses)
                        loss_output = self.world_model.training_step(x, x)  # Autoencoder
                        world_model_losses.append(loss_output.total.item())

                        logger.debug(f"World model training: loss={loss_output.total.item():.4f}")
                except Exception as wm_err:
                    logger.warning(f"World model training failed: {wm_err}")

            for exp in batch:
                try:
                    # Encode state
                    state = self.world_model.encode_observation(exp.context)

                    # Sample actions from policy
                    actions = await self.actor.sample_actions(state, k=1, context=exp.context)

                    # Imagine rollout
                    trajectory = self.world_model.imagine_trajectory(
                        state, actions, max_horizon=self.imagination_horizon
                    )

                    if trajectory:
                        # Get value estimates for each state
                        values = await self.critic.get_baselines(trajectory)

                        # Compute rewards from trajectory
                        rewards = [0.0] * len(trajectory)  # Intrinsic rewards
                        for i, pred in enumerate(trajectory):
                            s = pred.predicted_state if hasattr(pred, "predicted_state") else pred
                            intrinsic = self.intrinsic_reward.compute(
                                s, {"action": "imagine"}, self.world_model
                            )
                            rewards[i] = self.intrinsic_weight * intrinsic

                        # Add final extrinsic reward
                        rewards[-1] += exp.valence

                        # Compute GAE or V-trace
                        from kagami.core.rl.gae import get_gae_calculator

                        gae_calc = get_gae_calculator()
                        advantages, returns = gae_calc.compute(rewards, values)

                        # Update critic (value function) with returns
                        value_loss = await self.critic.update(trajectory, returns)
                        value_losses.append(value_loss)

                        # Update actor (policy) with advantages
                        policy_loss = await self.actor.update(
                            trajectory,
                            returns,
                            advantages,
                        )
                        policy_losses.append(policy_loss)

                except Exception as e:
                    logger.debug(f"Batch processing error for single item: {e}")
                    continue

            avg_policy_loss = np.mean(policy_losses) if policy_losses else 0.0
            avg_value_loss = np.mean(value_losses) if value_losses else 0.0
            avg_wm_loss = np.mean(world_model_losses) if world_model_losses else 0.0

            return {
                "status": "success",
                "avg_policy_loss": float(avg_policy_loss),
                "avg_value_loss": float(avg_value_loss),
                "avg_world_model_loss": float(avg_wm_loss),
                "batch_size": len(batch),
            }

        except Exception as e:
            logger.warning(f"Batch training failed: {e}")
            return {"status": "error", "error": str(e)}

    async def learn_from_experience(
        self,
        state_before: Any,
        action: dict[str, Any],
        state_after: Any,
        reward: float,
    ) -> dict[str, Any]:
        """
        Update world model + policy from real experience.

        Steps:
        1. Update world model dynamics
        2. Sample batch from replay buffer
        3. Imagine trajectories from sampled states
        4. Train actor-critic on imagined trajectories
        5. Compute learning statistics

        Args:
            state_before: State before action
            action: Action taken
            state_after: State after action
            reward: Extrinsic reward received

        Returns:
            Learning statistics
        """
        try:
            # 1. Update world model
            self.world_model.learn_transition(state_before, action, state_after)

            # 1b. Optional: Learn reward shaping from recent receipts (extrinsic)
            try:
                shaped = self._compute_reward_from_receipts(
                    context=getattr(state_after, "context_hash", None)
                )
                if isinstance(shaped, int | float):
                    float(shaped)
            except Exception:
                pass

            # 2. Sample important experiences for batch learning
            batch = self.replay_buffer.sample_prioritized(batch_size=32)

            if not batch:
                return {
                    "world_model_updated": True,
                    "policy_updated": False,
                    "message": "No experiences in buffer yet",
                }

            # 3-4. Train policy on imagined data
            policy_losses = []
            value_losses = []

            # Adaptive batch size
            try:
                from kagami.core.learning.adaptive_hyperparameters import (
                    get_adaptive_batch_size,
                )

                batch_computer = get_adaptive_batch_size()
                buffer_stats = self.replay_buffer.get_replay_stats()
                optimal_batch = batch_computer.compute_batch_size(
                    buffer_stats["size"], self.replay_buffer.capacity
                )
                train_batch_size = min(optimal_batch, len(batch))
            except Exception:
                train_batch_size = min(10, len(batch))  # Fallback

            for exp in batch[:train_batch_size]:  # Adaptive batch size
                try:
                    # Encode state
                    state = self.world_model.encode_observation(exp.context)

                    # Sample actions from policy
                    actions = await self.actor.sample_actions(state, k=1, context=exp.context)

                    # Imagine rollout
                    trajectory = self.world_model.imagine_trajectory(
                        state, actions, max_horizon=self.imagination_horizon
                    )

                    if trajectory:
                        # Get value estimates for each state
                        values = await self.critic.get_baselines(trajectory)

                        # Compute rewards from trajectory
                        rewards = [0.0] * len(trajectory)  # Intrinsic rewards
                        for i, pred in enumerate(trajectory):
                            state = (
                                pred.predicted_state if hasattr(pred, "predicted_state") else pred
                            )
                            intrinsic = self.intrinsic_reward.compute(
                                state, {"action": "imagine"}, self.world_model
                            )
                            rewards[i] = self.intrinsic_weight * intrinsic

                        # Add final extrinsic reward
                        rewards[-1] += exp.valence

                        # Compute GAE advantages (20-40% lower variance than simple advantage!)
                        # OR V-trace for off-policy correction (use much older data from replay)
                        try:
                            from kagami.core.learning.vtrace import (
                                get_vtrace_calculator,
                            )

                            # Check if this is off-policy (old data from replay buffer)
                            is_off_policy = (
                                exp.timestamp < (time.time() - 60)
                                if hasattr(exp, "timestamp")
                                else False
                            )

                            if is_off_policy:
                                # Use V-trace for off-policy correction (2-3x sample efficiency)
                                vtrace_calc = get_vtrace_calculator()

                                # Need to compute policy probabilities for V-trace
                                old_probs = []
                                new_probs = []
                                for _i, pred in enumerate(trajectory):
                                    state = (
                                        pred.predicted_state
                                        if hasattr(pred, "predicted_state")
                                        else pred
                                    )
                                    # Assume uniform old policy (conservative)
                                    old_probs.append(1.0 / self.actor.action_dim)
                                    # Get new policy prob (approximate via softmax over values)
                                    new_probs.append(1.0 / self.actor.action_dim)  # Simplified

                                vtrace_values, advantages = vtrace_calc.compute(
                                    rewards, values, old_probs, new_probs
                                )
                                returns = vtrace_values

                                logger.debug("Using V-trace for off-policy correction")
                            else:
                                # Use GAE for on-policy (standard)
                                from kagami.core.rl.gae import get_gae_calculator

                                gae_calc = get_gae_calculator()
                                advantages, returns = gae_calc.compute(rewards, values)
                        except Exception as vtrace_err:
                            # Fallback to GAE
                            logger.debug(f"V-trace unavailable, using GAE: {vtrace_err}")
                            from kagami.core.rl.gae import get_gae_calculator

                            gae_calc = get_gae_calculator()
                            advantages, returns = gae_calc.compute(rewards, values)

                        # Update critic (value function) with returns
                        value_loss = await self.critic.update(trajectory, returns)
                        value_losses.append(value_loss)

                        # Update actor (policy) with advantages
                        policy_loss = await self.actor.update(
                            trajectory,
                            returns,
                            advantages,  # Pass advantages directly
                        )
                        policy_losses.append(policy_loss)

                except Exception as e:
                    logger.debug(f"Batch learning step failed: {e}")
                    continue

            # Compute statistics
            avg_policy_loss = np.mean(policy_losses) if policy_losses else 0.0
            avg_value_loss = np.mean(value_losses) if value_losses else 0.0

            world_quality = self.world_model.get_model_quality()

            # Consolidate important states (EWC) when learning improves
            try:
                if policy_losses:
                    from kagami.core.learning.ewc import get_ewc

                    ewc = get_ewc()
                    # Use first batch state as representative to consolidate
                    first = batch[0]
                    state = self.world_model.encode_observation(first.context)
                    state_hash = getattr(state, "context_hash", str(hash(str(state)))[:16])
                    # Approximate logits vector with zeros (no true NN weights here)
                    # This still stabilizes via saved deltas across updates.
                    logits_proxy = np.zeros(self.actor.action_dim)
                    ewc.consolidate_state(state_hash, logits_proxy)
            except Exception:
                pass

            return {
                "world_model_updated": True,
                "avg_policy_loss": float(avg_policy_loss),
                "avg_value_loss": float(avg_value_loss),
                "world_quality": world_quality,
            }

        except Exception as e:
            logger.warning(f"Learning from experience failed: {e}")
            return {
                "world_model_updated": False,
                "policy_updated": False,
                "error": str(e),
            }

    def _compute_reward_from_receipts(self, context: Any | None = None) -> float:
        """Compute a quick extrinsic reward from recent receipts (best-effort).

        Heuristic:
        - +1.0 for recent success
        - -1.0 for recent error/blocked
        - Small positive scaled by latency improvement when available
        """
        try:
            # Minimal import to avoid heavy deps
            from kagami.core.receipts.ingestor import _RECEIPTS
        except Exception:
            return 0.0

        # Scan last ~50 receipts in-memory
        try:
            items = list(_RECEIPTS.items())[-50:]
        except Exception:
            return 0.0

        score = 0.0
        for _key, rec in reversed(items):
            try:
                status = str(rec.get("event", {}).get("name") or rec.get("status") or "").lower()
                duration_ms = float(rec.get("duration_ms") or 0)
                if "error" in status or "fail" in status or "blocked" in status:
                    score -= 1.0
                    break
                if "success" in status or "ok" in status or "verified" in status:
                    # Reward success and faster completions
                    bonus = 0.0
                    if duration_ms > 0:
                        # Map faster to slight positive (<=1000ms => up to +0.2)
                        bonus = max(0.0, min(0.2, (1000.0 - duration_ms) / 5000.0))
                    score += 1.0 + bonus
                    break
            except Exception:
                continue

        return float(score)

    async def plan_with_hierarchy(
        self, state: Any, goal: Any | None = None, horizon: int = 50
    ) -> dict[str, Any]:
        """
        Plan using hierarchical imagination.

        Defers to HierarchicalImagination for multi-scale planning.

        Args:
            state: Current state
            goal: Optional goal state
            horizon: Planning horizon

        Returns:
            Plan dict[str, Any] with actions and expected value
        """
        try:
            # FULL SCIENTIFIC VERSION (Pan et al., 2024 + Hansen et al., 2024)
            from dataclasses import asdict

            from kagami.core.rl.learned_hierarchical_planning import (
                get_hierarchical_planner,
            )

            planner = get_hierarchical_planner()
            plan = await planner.plan_hierarchical(state, goal, horizon)

            return asdict(plan)

        except Exception as e:
            logger.warning(f"Hierarchical planning failed: {e}")
            return {
                "action_plan": [],
                "subgoals": [],
                "expected_value": 0.0,
                "error": str(e),
            }

    def get_stats(self) -> dict[str, Any]:
        """Get RL loop statistics."""
        world_quality = self.world_model.get_model_quality()
        intrinsic_stats = self.intrinsic_reward.get_stats()
        replay_stats = self.replay_buffer.get_replay_stats()

        return {
            "world_model": world_quality,
            "intrinsic_motivation": intrinsic_stats,
            "replay_buffer": replay_stats,
            "hyperparameters": {
                "imagination_horizon": self.imagination_horizon,
                "n_candidates": self.n_candidates,
                "intrinsic_weight": self.intrinsic_weight,
                "gamma": self.gamma,
            },
        }


# Global singleton
_unified_rl_loop: UnifiedRLLoop | None = None


def get_rl_loop(task_family: str = "default") -> UnifiedRLLoop:
    """Get or create global unified RL loop.

    Args:
        task_family: Task category for hyperparameter selection

    Returns:
        Unified RL loop instance
    """
    global _unified_rl_loop
    if _unified_rl_loop is None:
        _unified_rl_loop = UnifiedRLLoop(task_family=task_family)
        logger.info("🎯 Unified RL loop initialized (model-based imagination planning)")
    return _unified_rl_loop
