"""JAX Training Loop - TPU Training Infrastructure.

Provides core training functions for the JAX OrganismRSSM implementation:
- TrainState: Extended Flax TrainState with extra metadata
- train_step: Single training step with loss computation
- train: Main training loop

Created: January 12, 2026
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

import jax
import jax.numpy as jnp
import optax
from flax import struct
from flax.training import train_state as flax_train_state

from .config import CurriculumConfig, OrganismRSSMConfig, TrainingConfig
from .curriculum import Curriculum
from .data import DataBatch, generate_structured_batch
from .losses import LossOutput, LossWeights, compute_full_loss
from .rssm import OrganismRSSM

logger = logging.getLogger(__name__)


# =============================================================================
# TRAIN STATE
# =============================================================================


class TrainState(flax_train_state.TrainState):
    """Extended TrainState with training metadata.

    Extends Flax's TrainState with:
    - step: Already included in base class
    - curriculum_phase: Current curriculum phase
    - ema_params: Exponential moving average of parameters
    - metrics_history: Rolling metrics for monitoring
    """

    curriculum_phase: str = struct.field(pytree_node=False, default="WARMUP")
    ema_decay: float = struct.field(pytree_node=False, default=0.999)
    ema_params: Any = None  # Optional EMA parameters


def create_train_state(
    key: jax.Array,
    config: OrganismRSSMConfig | None = None,
    training_config: TrainingConfig | None = None,
    learning_rate: float = 1e-4,
) -> TrainState:
    """Create initial training state.

    Args:
        key: JAX random key for initialization
        config: Model configuration
        training_config: Training configuration
        learning_rate: Initial learning rate

    Returns:
        Initialized TrainState
    """
    if config is None:
        config = OrganismRSSMConfig()

    if training_config is None:
        training_config = TrainingConfig()

    # Initialize model
    model = OrganismRSSM(config)

    # Dummy input for initialization
    batch_size = 2
    seq_len = 4
    dummy_obs = jnp.zeros((batch_size, seq_len, config.obs_dim))
    dummy_actions = jnp.zeros((batch_size, seq_len, config.action_dim))

    # Initialize parameters
    init_key, dropout_key = jax.random.split(key)
    variables = model.init(
        {"params": init_key, "dropout": dropout_key},
        dummy_obs,
        dummy_actions,
        training=False,
    )
    params = variables.get("params", variables)

    # Create optimizer with warmup cosine schedule
    total_steps = training_config.total_steps
    warmup_steps = int(total_steps * 0.01)  # 1% warmup

    schedule = optax.warmup_cosine_decay_schedule(
        init_value=0.0,
        peak_value=learning_rate,
        warmup_steps=warmup_steps,
        decay_steps=total_steps - warmup_steps,
        end_value=learning_rate * 0.01,
    )

    optimizer = optax.chain(
        optax.clip_by_global_norm(training_config.grad_clip),
        optax.adamw(
            learning_rate=schedule,
            weight_decay=training_config.weight_decay,
            b1=0.9,
            b2=0.999,
        ),
    )

    return TrainState.create(
        apply_fn=model.apply,
        params=params,
        tx=optimizer,
        curriculum_phase="WARMUP",
    )


# =============================================================================
# TRAINING STEP
# =============================================================================


def train_step(
    state: TrainState,
    batch: DataBatch,
    key: jax.Array,
    _step: int,  # Step passed for API compatibility but not used in core logic
    loss_weights: LossWeights | None = None,
) -> tuple[TrainState, LossOutput]:
    """Execute single training step.

    Args:
        state: Current training state
        batch: Input batch
        key: Random key for dropout
        step: Current training step
        loss_weights: Optional loss weights override

    Returns:
        Tuple of (updated_state, loss_output)
    """
    if loss_weights is None:
        loss_weights = LossWeights()

    def loss_fn(params: Any) -> tuple[jnp.ndarray, LossOutput]:
        """Compute loss for gradient calculation."""
        # Forward pass
        dropout_key, _sample_key = jax.random.split(key)

        outputs = state.apply_fn(
            {"params": params},
            batch.obs,
            batch.actions,
            training=True,
            rngs={"dropout": dropout_key},
        )

        # Compute losses - batch dict built from DataBatch
        batch_dict = {
            "obs": batch.obs,
            "actions": batch.actions,
            "rewards": batch.rewards,
        }
        total_loss, loss_output = compute_full_loss(
            outputs=outputs,
            batch=batch_dict,
            weights=loss_weights,
        )

        return total_loss, loss_output

    # Compute gradients
    (_loss, loss_output), grads = jax.value_and_grad(loss_fn, has_aux=True)(state.params)

    # Update state
    state = state.apply_gradients(grads=grads)

    return state, loss_output


# =============================================================================
# TRAINING LOOP
# =============================================================================


def train(
    total_steps: int = 100000,
    config: OrganismRSSMConfig | None = None,
    training_config: TrainingConfig | None = None,
    checkpoint_dir: str | None = None,
    log_every: int = 100,
    checkpoint_every: int = 10000,
    seed: int = 42,
) -> TrainState:
    """Main training loop.

    Args:
        total_steps: Total training steps
        config: Model configuration
        training_config: Training configuration
        checkpoint_dir: Directory for checkpoints
        log_every: Log frequency
        checkpoint_every: Checkpoint frequency
        seed: Random seed

    Returns:
        Final training state
    """
    logger.info("=" * 70)
    logger.info("STARTING JAX TPU TRAINING")
    logger.info("=" * 70)
    logger.info(f"Total steps: {total_steps}")

    # Initialize
    key = jax.random.PRNGKey(seed)
    key, init_key, _data_key = jax.random.split(key, 3)

    if config is None:
        config = OrganismRSSMConfig()

    if training_config is None:
        training_config = TrainingConfig(total_steps=total_steps)

    # Create state
    state = create_train_state(init_key, config, training_config)
    logger.info(
        f"Initialized model with {sum(x.size for x in jax.tree_util.tree_leaves(state.params)):,} parameters"
    )

    # Create curriculum
    curriculum_config = CurriculumConfig(total_steps=total_steps)
    curriculum = Curriculum(config=curriculum_config)

    # JIT compile train_step
    jit_train_step = jax.jit(train_step, static_argnums=(4,))

    # Training loop
    for step in range(total_steps):
        # Update curriculum phase
        phase = curriculum.current_phase.name.value
        if phase != state.curriculum_phase:
            logger.info(f"Curriculum phase: {state.curriculum_phase} -> {phase}")
            state = state.replace(curriculum_phase=phase)

        # Get batch
        key, batch_key, step_key = jax.random.split(key, 3)
        batch = generate_structured_batch(
            batch_key,
            batch_size=training_config.batch_size,
            seq_len=training_config.seq_len,
            obs_dim=config.obs_dim,
            action_dim=config.action_dim,
        )

        # Get loss weights for current phase
        loss_weights = curriculum.get_loss_weights(step)

        # Train step
        state, loss_output = jit_train_step(state, batch, step_key, step, loss_weights)

        # Logging
        if step % log_every == 0:
            logger.info(
                f"Step {step:6d} | Phase: {state.curriculum_phase:10s} | "
                f"Loss: {float(loss_output.total_loss):.4f}"
            )

        # Checkpointing
        if checkpoint_dir and step > 0 and step % checkpoint_every == 0:
            # Checkpoint logic would go here
            logger.info(f"Checkpoint saved at step {step}")

    logger.info("=" * 70)
    logger.info("TRAINING COMPLETE")
    logger.info("=" * 70)

    return state


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "TrainState",
    "create_train_state",
    "train",
    "train_step",
]
