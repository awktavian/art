"""JAX Intrinsic Motivation Modules — Empowerment & Information Bottleneck.

Ports from PyTorch:
1. MultiStepEmpowerment — Intrinsic reward via mutual information
2. InformationBottleneck — VIB compression
3. InfoNCEEstimator — MI lower bound estimation
4. EgoModel — Self-prediction model

References:
- Klyubin et al. (2005): Empowerment
- Alemi et al. (2017): Deep Variational Information Bottleneck
- Oord et al. (2018): Contrastive Predictive Coding
- LeCun (2022): A Path Towards Autonomous Machine Intelligence

Created: January 12, 2026
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import NamedTuple

import jax
import jax.numpy as jnp
from flax import linen as nn
from jax import random

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATIONS
# =============================================================================


@dataclass(frozen=True)
class EmpowermentConfig:
    """Configuration for multi-step empowerment."""

    state_dim: int = 512
    action_dim: int = 8
    hidden_dim: int = 256
    latent_dim: int = 64

    max_horizon: int = 10
    default_horizon: int = 5

    num_action_samples: int = 50
    num_state_samples: int = 20
    variational_samples: int = 10

    ema_decay: float = 0.99
    normalize_empowerment: bool = True


@dataclass(frozen=True)
class InformationBottleneckConfig:
    """Configuration for information bottleneck."""

    input_dim: int = 512
    bottleneck_dim: int = 64
    output_dim: int = 512
    hidden_dim: int = 256

    beta: float = 0.1  # KL weight
    free_bits: float = 1.0  # Minimum KL

    beta_schedule: str = "constant"  # "constant", "linear", "cosine"
    beta_min: float = 0.01
    beta_max: float = 1.0


@dataclass(frozen=True)
class EgoModelConfig:
    """Configuration for ego model."""

    world_state_dim: int = 512
    proprio_dim: int = 64
    ego_state_dim: int = 256
    action_dim: int = 64
    mu_self_dim: int = 7  # S7 dimension

    hidden_dim: int = 256
    n_layers: int = 3
    dropout: float = 0.1

    action_optim_steps: int = 10
    action_optim_lr: float = 0.1


# =============================================================================
# OUTPUT TYPES
# =============================================================================


class EmpowermentOutput(NamedTuple):
    """Output from empowerment computation."""

    empowerment: jnp.ndarray  # [B] empowerment values
    empowerment_normalized: jnp.ndarray  # [B] normalized [0, 1]
    forward_loss: jnp.ndarray  # Forward model loss
    inverse_loss: jnp.ndarray  # Inverse model loss


class IBOutput(NamedTuple):
    """Output from information bottleneck."""

    z: jnp.ndarray  # [B, bottleneck_dim] compressed representation
    z_mean: jnp.ndarray  # [B, bottleneck_dim] mean
    z_logvar: jnp.ndarray  # [B, bottleneck_dim] log variance
    reconstruction: jnp.ndarray  # [B, output_dim] decoded output
    kl_loss: jnp.ndarray  # KL divergence
    recon_loss: jnp.ndarray  # Reconstruction loss


class EgoOutput(NamedTuple):
    """Output from ego model."""

    ego_state: jnp.ndarray  # [B, ego_state_dim]
    action_pred: jnp.ndarray  # [B, action_dim] predicted action
    action_logvar: jnp.ndarray  # [B, action_dim] uncertainty
    effect_pred: jnp.ndarray  # [B, ego_state_dim] predicted next state
    cost_pred: jnp.ndarray  # [B] predicted cost


# =============================================================================
# INFONCE MUTUAL INFORMATION ESTIMATOR
# =============================================================================


class InfoNCEEstimator(nn.Module):
    """InfoNCE-based mutual information lower bound estimator.

    JAX port of PyTorch information_bottleneck.py:InfoNCEEstimator

    Provides I(X;Z) ≥ log(K) - L_NCE where K is number of negatives.
    """

    x_dim: int
    z_dim: int
    hidden_dim: int = 64
    temperature: float = 0.07

    @nn.compact
    def __call__(
        self,
        x: jnp.ndarray,
        z: jnp.ndarray,
        return_accuracy: bool = False,
    ) -> jnp.ndarray | tuple[jnp.ndarray, jnp.ndarray]:
        """Estimate I(X;Z) lower bound.

        Args:
            x: [B, x_dim] input
            z: [B, z_dim] latent
            return_accuracy: If True, also return accuracy

        Returns:
            MI lower bound estimate
        """
        batch_size = x.shape[0]

        # Project to shared space
        x_proj = nn.Dense(self.hidden_dim, name="x_proj_1")(x)
        x_proj = nn.gelu(x_proj)
        x_proj = nn.Dense(self.hidden_dim, name="x_proj_2")(x_proj)

        z_proj = nn.Dense(self.hidden_dim, name="z_proj_1")(z)
        z_proj = nn.gelu(z_proj)
        z_proj = nn.Dense(self.hidden_dim, name="z_proj_2")(z_proj)

        # Normalize
        x_emb = x_proj / (jnp.linalg.norm(x_proj, axis=-1, keepdims=True) + 1e-8)
        z_emb = z_proj / (jnp.linalg.norm(z_proj, axis=-1, keepdims=True) + 1e-8)

        # Similarity matrix [B, B]
        logits = jnp.matmul(x_emb, z_emb.T) / self.temperature

        # Labels: diagonal elements are positive pairs
        labels = jnp.arange(batch_size)

        # InfoNCE loss
        log_softmax = jax.nn.log_softmax(logits, axis=-1)
        loss = -jnp.mean(jnp.take_along_axis(log_softmax, labels[:, None], axis=-1))

        # MI lower bound
        mi_estimate = jnp.log(batch_size) - loss

        if return_accuracy:
            preds = jnp.argmax(logits, axis=-1)
            accuracy = jnp.mean(preds == labels)
            return mi_estimate, accuracy

        return mi_estimate


# =============================================================================
# ACTION SEQUENCE ENCODER
# =============================================================================


class ActionSequenceEncoder(nn.Module):
    """Encode action sequences using GRU.

    JAX port of PyTorch multi_step_empowerment.py:ActionSequenceEncoder
    """

    config: EmpowermentConfig

    @nn.compact
    def __call__(
        self,
        actions: jnp.ndarray,
    ) -> jnp.ndarray:
        """Encode action sequence.

        Args:
            actions: [B, H, action_dim] action sequence

        Returns:
            [B, latent_dim] encoded representation
        """
        cfg = self.config
        B, H, _ = actions.shape

        # Simple transformer-style encoding instead of GRU for JAX efficiency
        # Positional encoding
        pos = jnp.arange(H)[None, :, None]  # [1, H, 1]
        pos_enc = jnp.sin(pos * jnp.pi / H)

        # Project actions
        x = nn.Dense(cfg.hidden_dim, name="action_proj")(actions)
        x = x + pos_enc * 0.1  # Add positional info

        # Self-attention pooling
        x = nn.LayerNorm(name="ln1")(x)

        # Attention weights
        query = nn.Dense(cfg.hidden_dim, name="query")(x[:, -1:, :])  # Use last position
        keys = nn.Dense(cfg.hidden_dim, name="keys")(x)

        attn_weights = jax.nn.softmax(
            jnp.matmul(query, keys.transpose(0, 2, 1)) / jnp.sqrt(cfg.hidden_dim),
            axis=-1,
        )

        # Weighted sum
        pooled = jnp.matmul(attn_weights, x).squeeze(1)  # [B, hidden_dim]

        # Project to latent
        out = nn.Dense(cfg.latent_dim, name="out_proj")(pooled)

        return out


# =============================================================================
# STATE TRANSITION MODEL
# =============================================================================


class StateTransitionModel(nn.Module):
    """Predict final state from initial state and action sequence.

    JAX port of PyTorch multi_step_empowerment.py:StateTransitionModel
    """

    config: EmpowermentConfig

    def setup(self):
        self.action_encoder = ActionSequenceEncoder(self.config)

    @nn.compact
    def __call__(
        self,
        state: jnp.ndarray,
        actions: jnp.ndarray,
    ) -> tuple[jnp.ndarray, jnp.ndarray]:
        """Predict final state distribution.

        Args:
            state: [B, state_dim] initial state
            actions: [B, H, action_dim] action sequence

        Returns:
            mu: [B, state_dim] predicted mean
            logvar: [B, state_dim] predicted log variance
        """
        cfg = self.config

        # Encode state and actions
        state_enc = nn.Dense(cfg.hidden_dim, name="state_enc")(state)
        action_enc = self.action_encoder(actions)

        # Combine
        combined = jnp.concatenate([state_enc, action_enc], axis=-1)

        # Predict
        h = nn.Dense(cfg.hidden_dim, name="pred_1")(combined)
        h = nn.LayerNorm(name="pred_ln")(h)
        h = nn.relu(h)
        h = nn.Dense(cfg.hidden_dim, name="pred_2")(h)
        h = nn.relu(h)

        mu = nn.Dense(cfg.state_dim, name="mu")(h)
        logvar = nn.Dense(cfg.state_dim, name="logvar")(h)

        return mu, logvar


# =============================================================================
# INVERSE TRANSITION MODEL
# =============================================================================


class InverseTransitionModel(nn.Module):
    """Infer action sequence from state transition.

    JAX port of PyTorch multi_step_empowerment.py:InverseTransitionModel
    """

    config: EmpowermentConfig

    @nn.compact
    def __call__(
        self,
        initial_state: jnp.ndarray,
        final_state: jnp.ndarray,
        horizon: int | None = None,
    ) -> jnp.ndarray:
        """Infer action sequence from transition.

        Args:
            initial_state: [B, state_dim]
            final_state: [B, state_dim]
            horizon: Sequence length to predict

        Returns:
            [B, H, action_dim] action logits
        """
        cfg = self.config
        horizon = horizon or cfg.default_horizon
        B = initial_state.shape[0]

        # Combine states
        combined = jnp.concatenate([initial_state, final_state], axis=-1)

        h = nn.Dense(cfg.hidden_dim, name="fc_1")(combined)
        h = nn.LayerNorm(name="ln")(h)
        h = nn.relu(h)
        h = nn.Dense(cfg.hidden_dim, name="fc_2")(h)
        h = nn.relu(h)

        # Generate action sequence with simple MLP (for JAX efficiency)
        # In JAX, we avoid RNN autoregressive for simplicity
        action_logits = []
        for t in range(horizon):
            # Time embedding
            t_emb = jnp.sin(jnp.array([t]) * jnp.pi / horizon)
            t_emb = jnp.broadcast_to(t_emb, (B, 1))

            h_t = jnp.concatenate([h, t_emb], axis=-1)
            logits_t = nn.Dense(cfg.action_dim, name=f"action_{t}")(h_t)
            action_logits.append(logits_t[:, None, :])

        return jnp.concatenate(action_logits, axis=1)


# =============================================================================
# MULTI-STEP EMPOWERMENT
# =============================================================================


class MultiStepEmpowerment(nn.Module):
    """Multi-step empowerment estimator.

    JAX port of PyTorch multi_step_empowerment.py:MultiStepEmpowerment

    Computes Eₙ(s) = I(A₁:ₙ; Sₙ | S₀=s) using variational bounds.
    """

    config: EmpowermentConfig

    def setup(self):
        self.forward_model = StateTransitionModel(self.config)
        self.inverse_model = InverseTransitionModel(self.config)

    @nn.compact
    def __call__(
        self,
        state: jnp.ndarray,
        horizon: int | None = None,
        key: jax.Array | None = None,
    ) -> EmpowermentOutput:
        """Estimate multi-step empowerment.

        Args:
            state: [B, state_dim] current state
            horizon: Prediction horizon
            key: Random key for sampling

        Returns:
            EmpowermentOutput
        """
        cfg = self.config
        horizon = horizon or cfg.default_horizon
        B = state.shape[0]

        if key is None:
            key = random.PRNGKey(0)

        # Sample action sequences
        key, sample_key = random.split(key)
        actions = random.normal(sample_key, (B, horizon, cfg.action_dim))
        actions = jnp.tanh(actions)  # Bound actions

        # Forward model: predict final state
        mu, logvar = self.forward_model(state, actions)

        # Sample final states
        key, noise_key = random.split(key)
        std = jnp.exp(0.5 * logvar)
        eps = random.normal(noise_key, mu.shape)
        final_state = mu + std * eps

        # Inverse model: infer actions
        action_logits = self.inverse_model(state, final_state, horizon)

        # Forward loss (reconstruction)
        forward_loss = jnp.mean(jnp.square(mu - final_state))

        # Inverse loss (cross-entropy style)
        inverse_loss = jnp.mean(jnp.square(action_logits - actions))

        # Empowerment estimate: log|A|^n - H(A|S,S')
        # Simplified: use inverse loss as proxy for conditional entropy
        action_entropy = horizon * jnp.log(2.0)  # log|A|^n for bounded actions
        empowerment = action_entropy - inverse_loss

        # Normalize to [0, 1]
        empowerment_max = horizon * jnp.log(2.0)
        empowerment_normalized = jnp.clip(empowerment / empowerment_max, 0.0, 1.0)

        return EmpowermentOutput(
            empowerment=empowerment,
            empowerment_normalized=empowerment_normalized,
            forward_loss=forward_loss,
            inverse_loss=inverse_loss,
        )


# =============================================================================
# GAUSSIAN ENCODER (for VIB)
# =============================================================================


class GaussianEncoder(nn.Module):
    """Gaussian encoder for variational bottleneck.

    JAX port of PyTorch information_bottleneck.py:GaussianEncoder
    """

    config: InformationBottleneckConfig

    @nn.compact
    def __call__(
        self,
        x: jnp.ndarray,
        key: jax.Array,
    ) -> tuple[jnp.ndarray, jnp.ndarray, jnp.ndarray]:
        """Encode input to Gaussian distribution.

        Args:
            x: [B, input_dim] input
            key: Random key for sampling

        Returns:
            z: [B, bottleneck_dim] sampled latent
            mu: [B, bottleneck_dim] mean
            logvar: [B, bottleneck_dim] log variance
        """
        cfg = self.config

        h = nn.Dense(cfg.hidden_dim, name="fc_1")(x)
        h = nn.LayerNorm(name="ln_1")(h)
        h = nn.gelu(h)
        h = nn.Dense(cfg.hidden_dim, name="fc_2")(h)
        h = nn.gelu(h)

        mu = nn.Dense(cfg.bottleneck_dim, name="mu")(h)
        logvar = nn.Dense(cfg.bottleneck_dim, name="logvar")(h)
        logvar = jnp.clip(logvar, -10.0, 2.0)  # Stability

        # Reparameterization trick
        std = jnp.exp(0.5 * logvar)
        eps = random.normal(key, mu.shape)
        z = mu + std * eps

        return z, mu, logvar


# =============================================================================
# PREDICTIVE DECODER
# =============================================================================


class PredictiveDecoder(nn.Module):
    """Decoder for information bottleneck.

    JAX port of PyTorch information_bottleneck.py:PredictiveDecoder
    """

    config: InformationBottleneckConfig

    @nn.compact
    def __call__(self, z: jnp.ndarray) -> jnp.ndarray:
        """Decode latent to output.

        Args:
            z: [B, bottleneck_dim] latent

        Returns:
            [B, output_dim] decoded output
        """
        cfg = self.config

        h = nn.Dense(cfg.hidden_dim, name="fc_1")(z)
        h = nn.LayerNorm(name="ln_1")(h)
        h = nn.gelu(h)
        h = nn.Dense(cfg.hidden_dim, name="fc_2")(h)
        h = nn.gelu(h)

        out = nn.Dense(cfg.output_dim, name="out")(h)

        return out


# =============================================================================
# INFORMATION BOTTLENECK
# =============================================================================


class InformationBottleneck(nn.Module):
    """Variational Information Bottleneck.

    JAX port of PyTorch information_bottleneck.py:InformationBottleneck

    min I(X;Z) - β·I(Z;Y)
    """

    config: InformationBottleneckConfig

    def setup(self):
        self.encoder = GaussianEncoder(self.config)
        self.decoder = PredictiveDecoder(self.config)

    @nn.compact
    def __call__(
        self,
        x: jnp.ndarray,
        target: jnp.ndarray | None = None,
        key: jax.Array | None = None,
    ) -> IBOutput:
        """Apply information bottleneck.

        Args:
            x: [B, input_dim] input
            target: [B, output_dim] target (optional, uses x if None)
            key: Random key

        Returns:
            IBOutput
        """
        cfg = self.config

        if key is None:
            key = random.PRNGKey(0)

        if target is None:
            target = x

        # Encode
        z, mu, logvar = self.encoder(x, key)

        # Decode
        recon = self.decoder(z)

        # KL divergence: KL[N(mu, var) || N(0, 1)]
        kl_raw = -0.5 * jnp.sum(1 + logvar - jnp.square(mu) - jnp.exp(logvar), axis=-1)
        kl_loss = jnp.maximum(kl_raw, cfg.free_bits)  # Free bits
        kl_loss = jnp.mean(kl_loss)

        # Reconstruction loss
        recon_loss = jnp.mean(jnp.square(recon - target))

        return IBOutput(
            z=z,
            z_mean=mu,
            z_logvar=logvar,
            reconstruction=recon,
            kl_loss=kl_loss,
            recon_loss=recon_loss,
        )

    def compute_loss(
        self,
        output: IBOutput,
        beta: float | None = None,
    ) -> jnp.ndarray:
        """Compute VIB loss.

        Args:
            output: IBOutput from forward pass
            beta: Override beta (uses config.beta if None)

        Returns:
            Total loss
        """
        if beta is None:
            beta = self.config.beta

        return output.recon_loss + beta * output.kl_loss


# =============================================================================
# EGO STATE ENCODER
# =============================================================================


class EgoStateEncoder(nn.Module):
    """Encode world state + proprioception into ego state.

    JAX port of PyTorch ego_model.py:EgoStateEncoder
    """

    config: EgoModelConfig

    @nn.compact
    def __call__(
        self,
        world_state: jnp.ndarray,
        proprio: jnp.ndarray | None = None,
        mu_self: jnp.ndarray | None = None,
    ) -> jnp.ndarray:
        """Encode ego state.

        Args:
            world_state: [B, world_state_dim]
            proprio: [B, proprio_dim] (optional)
            mu_self: [B, mu_self_dim] Strange Loop representation (optional)

        Returns:
            [B, ego_state_dim]
        """
        cfg = self.config
        B = world_state.shape[0]

        if proprio is None:
            proprio = jnp.zeros((B, cfg.proprio_dim))

        inputs = [world_state, proprio]

        if mu_self is not None:
            inputs.append(mu_self)

        x = jnp.concatenate(inputs, axis=-1)

        for i in range(cfg.n_layers):
            x = nn.Dense(cfg.hidden_dim, name=f"fc_{i}")(x)
            x = nn.LayerNorm(name=f"ln_{i}")(x)
            x = nn.gelu(x)

        ego_state = nn.Dense(cfg.ego_state_dim, name="out")(x)

        return ego_state


# =============================================================================
# ACTION PREDICTOR
# =============================================================================


class ActionPredictor(nn.Module):
    """Predict action distribution from ego state.

    JAX port of PyTorch ego_model.py:ActionPredictor
    """

    config: EgoModelConfig

    @nn.compact
    def __call__(
        self,
        ego_state: jnp.ndarray,
    ) -> tuple[jnp.ndarray, jnp.ndarray]:
        """Predict action.

        Args:
            ego_state: [B, ego_state_dim]

        Returns:
            action_mean: [B, action_dim]
            action_logvar: [B, action_dim]
        """
        cfg = self.config

        h = nn.Dense(cfg.hidden_dim, name="fc_1")(ego_state)
        h = nn.LayerNorm(name="ln")(h)
        h = nn.gelu(h)
        h = nn.Dense(cfg.hidden_dim, name="fc_2")(h)
        h = nn.gelu(h)

        action_mean = nn.Dense(cfg.action_dim, name="mean")(h)
        action_logvar = nn.Dense(cfg.action_dim, name="logvar")(h)

        return action_mean, action_logvar


# =============================================================================
# EFFECT PREDICTOR
# =============================================================================


class EffectPredictor(nn.Module):
    """Predict effect of action on ego state.

    JAX port of PyTorch ego_model.py:EffectPredictor
    """

    config: EgoModelConfig

    @nn.compact
    def __call__(
        self,
        ego_state: jnp.ndarray,
        action: jnp.ndarray,
    ) -> jnp.ndarray:
        """Predict next ego state.

        Args:
            ego_state: [B, ego_state_dim]
            action: [B, action_dim]

        Returns:
            [B, ego_state_dim] predicted next state
        """
        cfg = self.config

        x = jnp.concatenate([ego_state, action], axis=-1)

        h = nn.Dense(cfg.hidden_dim, name="fc_1")(x)
        h = nn.LayerNorm(name="ln_1")(h)
        h = nn.gelu(h)
        h = nn.Dense(cfg.hidden_dim, name="fc_2")(h)
        h = nn.gelu(h)

        # Residual prediction
        delta = nn.Dense(cfg.ego_state_dim, name="delta")(h)
        next_ego = ego_state + delta

        return next_ego


# =============================================================================
# COST PREDICTOR
# =============================================================================


class CostPredictor(nn.Module):
    """Predict cost of action.

    JAX port of PyTorch ego_model.py:CostPredictor
    """

    config: EgoModelConfig

    @nn.compact
    def __call__(
        self,
        ego_state: jnp.ndarray,
        action: jnp.ndarray,
    ) -> jnp.ndarray:
        """Predict action cost.

        Args:
            ego_state: [B, ego_state_dim]
            action: [B, action_dim]

        Returns:
            [B] predicted cost
        """
        cfg = self.config

        x = jnp.concatenate([ego_state, action], axis=-1)

        h = nn.Dense(cfg.hidden_dim, name="fc_1")(x)
        h = nn.LayerNorm(name="ln")(h)
        h = nn.gelu(h)
        h = nn.Dense(cfg.hidden_dim // 2, name="fc_2")(h)
        h = nn.gelu(h)

        cost = nn.Dense(1, name="cost")(h).squeeze(-1)

        return cost


# =============================================================================
# EGO MODEL
# =============================================================================


class EgoModel(nn.Module):
    """Deterministic self-predictor.

    JAX port of PyTorch ego_model.py:EgoModel

    LeCun (2022): "The ego model is a model of the cost as a function
    of action given the current state."
    """

    config: EgoModelConfig

    def setup(self):
        self.state_encoder = EgoStateEncoder(self.config)
        self.action_predictor = ActionPredictor(self.config)
        self.effect_predictor = EffectPredictor(self.config)
        self.cost_predictor = CostPredictor(self.config)

    @nn.compact
    def __call__(
        self,
        world_state: jnp.ndarray,
        proprio: jnp.ndarray | None = None,
        mu_self: jnp.ndarray | None = None,
        action: jnp.ndarray | None = None,
    ) -> EgoOutput:
        """Forward pass.

        Args:
            world_state: [B, world_state_dim]
            proprio: [B, proprio_dim] (optional)
            mu_self: [B, mu_self_dim] Strange Loop (optional)
            action: [B, action_dim] (optional, predicts if None)

        Returns:
            EgoOutput
        """
        _cfg = self.config  # For documentation / future use
        _B = world_state.shape[0]  # Batch size (for documentation)

        # Encode ego state
        ego_state = self.state_encoder(world_state, proprio, mu_self)

        # Predict action if not provided
        action_pred, action_logvar = self.action_predictor(ego_state)

        if action is None:
            action = action_pred

        # Predict effect
        effect_pred = self.effect_predictor(ego_state, action)

        # Predict cost
        cost_pred = self.cost_predictor(ego_state, action)

        return EgoOutput(
            ego_state=ego_state,
            action_pred=action_pred,
            action_logvar=action_logvar,
            effect_pred=effect_pred,
            cost_pred=cost_pred,
        )

    def optimize_action(
        self,
        world_state: jnp.ndarray,
        proprio: jnp.ndarray | None = None,
        mu_self: jnp.ndarray | None = None,
        params: dict | None = None,
        n_steps: int | None = None,
        lr: float | None = None,
    ) -> jnp.ndarray:
        """Optimize action via gradient descent on cost.

        Args:
            world_state: [B, world_state_dim]
            proprio: [B, proprio_dim] (optional)
            mu_self: [B, mu_self_dim] (optional)
            params: Model parameters
            n_steps: Optimization steps
            lr: Learning rate

        Returns:
            [B, action_dim] optimized action
        """
        cfg = self.config
        n_steps = n_steps or cfg.action_optim_steps
        lr = lr or cfg.action_optim_lr

        _B = world_state.shape[0]  # Batch size (for documentation)

        # Initialize from prediction
        ego_state = self.state_encoder.apply(params, world_state, proprio, mu_self)
        action, _ = self.action_predictor.apply(params, ego_state)

        # Gradient descent on cost
        for _ in range(n_steps):

            def cost_fn(a):
                c = self.cost_predictor.apply(params, ego_state, a)
                return jnp.mean(c)

            grad = jax.grad(cost_fn)(action)
            action = action - lr * grad
            action = jnp.clip(action, -1.0, 1.0)  # Bound actions

        return action


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================


def create_empowerment(
    config: EmpowermentConfig | None = None,
) -> MultiStepEmpowerment:
    """Create multi-step empowerment module."""
    if config is None:
        config = EmpowermentConfig()
    return MultiStepEmpowerment(config)


def create_information_bottleneck(
    config: InformationBottleneckConfig | None = None,
) -> InformationBottleneck:
    """Create information bottleneck module."""
    if config is None:
        config = InformationBottleneckConfig()
    return InformationBottleneck(config)


def create_ego_model(
    config: EgoModelConfig | None = None,
) -> EgoModel:
    """Create ego model."""
    if config is None:
        config = EgoModelConfig()
    return EgoModel(config)


# =============================================================================
# EXPORTS
# =============================================================================


__all__ = [
    # Configs
    "EmpowermentConfig",
    "InformationBottleneckConfig",
    "EgoModelConfig",
    # Outputs
    "EmpowermentOutput",
    "IBOutput",
    "EgoOutput",
    # Modules
    "InfoNCEEstimator",
    "ActionSequenceEncoder",
    "StateTransitionModel",
    "InverseTransitionModel",
    "MultiStepEmpowerment",
    "GaussianEncoder",
    "PredictiveDecoder",
    "InformationBottleneck",
    "EgoStateEncoder",
    "ActionPredictor",
    "EffectPredictor",
    "CostPredictor",
    "EgoModel",
    # Factories
    "create_empowerment",
    "create_information_bottleneck",
    "create_ego_model",
]
