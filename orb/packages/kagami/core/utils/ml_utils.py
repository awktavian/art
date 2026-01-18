"""Common ML Utilities and Patterns.

EXTRACTED FOR CONSOLIDATION (December 13, 2025):
================================================
Common ML patterns found across 218 files with torch imports.
This module consolidates repeated PyTorch utilities, layer creation,
and training patterns to reduce duplication.

Contains:
- Common torch imports and aliases
- Standard layer factories
- Common training utilities
- Tensor operations
- Model utilities
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

# Consolidated torch imports (most common patterns)
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.optim.lr_scheduler import (
    CosineAnnealingLR,
    ExponentialLR,
    LinearLR,
    SequentialLR,
    StepLR,
)

logger = logging.getLogger(__name__)

# Common type aliases for ML
TensorLike = torch.Tensor | float | int
DeviceType = str | torch.device
OptimizerType = optim.Adam | optim.AdamW | optim.SGD
SchedulerType = CosineAnnealingLR | LinearLR | SequentialLR | StepLR | ExponentialLR


class MLUtils:
    """Common ML utilities and patterns."""

    @staticmethod
    def get_device(prefer_gpu: bool = True) -> torch.device:
        """Get appropriate device for computation.

        REFACTORED (December 25, 2025): Delegates to canonical device module.
        """
        from kagami.core.utils.device import get_device as _get_device

        return _get_device()

    @staticmethod
    def count_parameters(model: nn.Module, only_trainable: bool = True) -> int:
        """Count model parameters."""
        if only_trainable:
            return sum(p.numel() for p in model.parameters() if p.requires_grad)
        else:
            return sum(p.numel() for p in model.parameters())

    @staticmethod
    def get_model_size_mb(model: nn.Module, dtype: torch.dtype = torch.float32) -> float:
        """Get model size in MB."""
        param_count = MLUtils.count_parameters(model, only_trainable=False)
        bytes_per_param = torch.finfo(dtype).bits // 8
        return param_count * bytes_per_param / (1024**2)

    @staticmethod
    def move_to_device(obj: Any, device: DeviceType) -> Any:
        """Move object to device if it's a tensor."""
        if isinstance(obj, torch.Tensor):
            return obj.to(device)
        elif isinstance(obj, (list, tuple)):  # ruff: noqa: UP038
            return type(obj)(MLUtils.move_to_device(item, device) for item in obj)
        elif isinstance(obj, dict):
            return {key: MLUtils.move_to_device(value, device) for key, value in obj.items()}
        else:
            return obj

    @staticmethod
    def safe_softmax(x: torch.Tensor, dim: int = -1, temperature: float = 1.0) -> torch.Tensor:
        """Safe softmax with temperature and numerical stability."""
        x = x / temperature
        # Subtract max for numerical stability
        x = x - torch.max(x, dim=dim, keepdim=True)[0]
        return F.softmax(x, dim=dim)

    @staticmethod
    def safe_log_softmax(x: torch.Tensor, dim: int = -1, temperature: float = 1.0) -> torch.Tensor:
        """Safe log softmax with temperature and numerical stability."""
        x = x / temperature
        return F.log_softmax(x, dim=dim)

    @staticmethod
    def clip_gradients(model: nn.Module, max_norm: float = 1.0) -> float:
        """Clip gradients and return the norm."""
        return float(nn.utils.clip_grad_norm_(model.parameters(), max_norm))

    @staticmethod
    def get_lr(optimizer: OptimizerType) -> float:
        """Get current learning rate from optimizer."""
        lr = optimizer.param_groups[0]["lr"]
        return float(lr) if isinstance(lr, (int, float)) else lr  # ruff: noqa: UP038

    @staticmethod
    def set_lr(optimizer: OptimizerType, lr: float) -> None:
        """Set learning rate for optimizer."""
        for param_group in optimizer.param_groups:
            param_group["lr"] = lr


class LayerFactory:
    """Factory for common neural network layers."""

    @staticmethod
    def linear_block(
        in_features: int,
        out_features: int,
        activation: str = "relu",
        dropout: float = 0.0,
        batch_norm: bool = False,
        bias: bool = True,
    ) -> nn.Sequential:
        """Create a standard linear block with activation and optional dropout/batch norm."""
        layers: list[nn.Module] = [nn.Linear(in_features, out_features, bias=bias)]

        if batch_norm:
            layers.append(nn.BatchNorm1d(out_features))

        # Add activation
        if activation.lower() == "relu":
            layers.append(nn.ReLU(inplace=True))
        elif activation.lower() == "gelu":
            layers.append(nn.GELU())
        elif activation.lower() == "silu":
            layers.append(nn.SiLU())
        elif activation.lower() == "tanh":
            layers.append(nn.Tanh())
        elif activation.lower() == "none":
            pass  # No activation
        else:
            raise ValueError(f"Unknown activation: {activation}")

        if dropout > 0:
            layers.append(nn.Dropout(dropout))

        return nn.Sequential(*layers)

    @staticmethod
    def mlp(
        input_dim: int,
        hidden_dims: list[int],
        output_dim: int,
        activation: str = "relu",
        final_activation: str | None = None,
        dropout: float = 0.0,
        batch_norm: bool = False,
    ) -> nn.Sequential:
        """Create a multi-layer perceptron."""
        layers: list[nn.Module] = []

        # Input to first hidden
        if hidden_dims:
            layers.append(
                LayerFactory.linear_block(
                    input_dim, hidden_dims[0], activation, dropout, batch_norm
                )
            )

            # Hidden layers
            for i in range(1, len(hidden_dims)):
                layers.append(
                    LayerFactory.linear_block(
                        hidden_dims[i - 1], hidden_dims[i], activation, dropout, batch_norm
                    )
                )

            # Final layer
            final_layer: nn.Module = nn.Linear(hidden_dims[-1], output_dim)
        else:
            # Direct input to output
            final_layer = nn.Linear(input_dim, output_dim)

        layers.append(final_layer)

        # Final activation
        if final_activation and final_activation.lower() != "none":
            if final_activation.lower() == "softmax":
                layers.append(nn.Softmax(dim=-1))
            elif final_activation.lower() == "sigmoid":
                layers.append(nn.Sigmoid())
            elif final_activation.lower() == "tanh":
                layers.append(nn.Tanh())

        return nn.Sequential(*layers)

    @staticmethod
    def conv_block(
        in_channels: int,
        out_channels: int,
        kernel_size: int = 3,
        stride: int = 1,
        padding: int | None = None,
        activation: str = "relu",
        batch_norm: bool = True,
        dropout: float = 0.0,
    ) -> nn.Sequential:
        """Create a standard convolutional block."""
        if padding is None:
            padding = kernel_size // 2

        layers: list[nn.Module] = [
            nn.Conv2d(in_channels, out_channels, kernel_size, stride, padding)
        ]

        if batch_norm:
            layers.append(nn.BatchNorm2d(out_channels))

        # Add activation
        if activation.lower() == "relu":
            layers.append(nn.ReLU(inplace=True))
        elif activation.lower() == "gelu":
            layers.append(nn.GELU())
        elif activation.lower() == "silu":
            layers.append(nn.SiLU())

        if dropout > 0:
            layers.append(nn.Dropout2d(dropout))

        return nn.Sequential(*layers)

    @staticmethod
    def attention_layer(
        embed_dim: int, num_heads: int, dropout: float = 0.1, batch_first: bool = True
    ) -> nn.MultiheadAttention:
        """Create a standard multi-head attention layer."""
        return nn.MultiheadAttention(
            embed_dim=embed_dim, num_heads=num_heads, dropout=dropout, batch_first=batch_first
        )


class TrainingUtils:
    """Common training utilities and patterns."""

    @staticmethod
    def create_optimizer(  # type: ignore[no-untyped-def]
        model: nn.Module,
        optimizer_type: str = "adamw",
        learning_rate: float = 1e-3,
        weight_decay: float = 0.01,
        **kwargs,
    ) -> OptimizerType:
        """Create optimizer with standard configurations."""
        if optimizer_type.lower() == "adamw":
            return optim.AdamW(
                model.parameters(),
                lr=learning_rate,
                weight_decay=weight_decay,
                eps=kwargs.get("eps", 1e-8),
                betas=kwargs.get("betas", (0.9, 0.999)),
            )
        elif optimizer_type.lower() == "adam":
            return optim.Adam(
                model.parameters(),
                lr=learning_rate,
                weight_decay=weight_decay,
                eps=kwargs.get("eps", 1e-8),
                betas=kwargs.get("betas", (0.9, 0.999)),
            )
        elif optimizer_type.lower() == "sgd":
            return optim.SGD(
                model.parameters(),
                lr=learning_rate,
                momentum=kwargs.get("momentum", 0.9),
                weight_decay=weight_decay,
            )
        else:
            raise ValueError(f"Unknown optimizer type: {optimizer_type}")

    @staticmethod
    def create_scheduler(  # type: ignore[no-untyped-def]
        optimizer: OptimizerType,
        scheduler_type: str = "cosine_with_warmup",
        warmup_steps: int = 1000,
        total_steps: int = 10000,
        **kwargs,
    ) -> SchedulerType:
        """Create learning rate scheduler with standard configurations."""
        if scheduler_type == "cosine_with_warmup":
            # Warmup phase
            warmup = LinearLR(
                optimizer, start_factor=kwargs.get("start_factor", 0.01), total_iters=warmup_steps
            )

            # Cosine annealing phase
            cosine = CosineAnnealingLR(
                optimizer, T_max=total_steps - warmup_steps, eta_min=kwargs.get("eta_min", 0.0)
            )

            return SequentialLR(optimizer, schedulers=[warmup, cosine], milestones=[warmup_steps])
        elif scheduler_type == "cosine":
            return CosineAnnealingLR(
                optimizer, T_max=total_steps, eta_min=kwargs.get("eta_min", 0.0)
            )
        elif scheduler_type == "step":
            return StepLR(
                optimizer, step_size=kwargs.get("step_size", 1000), gamma=kwargs.get("gamma", 0.1)
            )
        elif scheduler_type == "exponential":
            return ExponentialLR(optimizer, gamma=kwargs.get("gamma", 0.95))
        else:
            raise ValueError(f"Unknown scheduler type: {scheduler_type}")

    @staticmethod
    def compute_loss_with_reduction(
        predictions: torch.Tensor,
        targets: torch.Tensor,
        loss_fn: Callable[[torch.Tensor, torch.Tensor], torch.Tensor] = F.mse_loss,
        reduction: str = "mean",
    ) -> torch.Tensor:
        """Compute loss with specified reduction."""
        if reduction == "none":
            return loss_fn(predictions, targets, reduction="none")  # type: ignore[call-arg]
        elif reduction == "mean":
            return loss_fn(predictions, targets, reduction="mean")  # type: ignore[call-arg]
        elif reduction == "sum":
            return loss_fn(predictions, targets, reduction="sum")  # type: ignore[call-arg]
        else:
            raise ValueError(f"Unknown reduction: {reduction}")

    @staticmethod
    def initialize_weights(model: nn.Module, init_type: str = "xavier") -> None:
        """Initialize model weights with standard patterns."""
        for _name, module in model.named_modules():
            if isinstance(module, nn.Linear):
                if init_type == "xavier":
                    nn.init.xavier_uniform_(module.weight)
                elif init_type == "kaiming":
                    nn.init.kaiming_uniform_(module.weight, nonlinearity="relu")
                elif init_type == "normal":
                    nn.init.normal_(module.weight, mean=0, std=0.02)

                if module.bias is not None:
                    nn.init.zeros_(module.bias)

            elif isinstance(module, nn.Conv2d):
                if init_type == "xavier":
                    nn.init.xavier_uniform_(module.weight)
                elif init_type == "kaiming":
                    nn.init.kaiming_uniform_(module.weight, nonlinearity="relu")

                if module.bias is not None:
                    nn.init.zeros_(module.bias)

            elif isinstance(module, (nn.BatchNorm1d, nn.BatchNorm2d, nn.LayerNorm)):  # ruff: noqa: UP038
                nn.init.ones_(module.weight)
                nn.init.zeros_(module.bias)

            elif isinstance(module, nn.Embedding):
                nn.init.normal_(module.weight, mean=0, std=0.02)


class TensorOps:
    """Common tensor operations and utilities."""

    @staticmethod
    def masked_mean(x: torch.Tensor, mask: torch.Tensor, dim: int | None = None) -> torch.Tensor:
        """Compute mean over masked elements."""
        masked_x = x * mask
        if dim is not None:
            return masked_x.sum(dim=dim) / (mask.sum(dim=dim) + 1e-8)
        else:
            return masked_x.sum() / (mask.sum() + 1e-8)

    @staticmethod
    def gaussian_sample(mean: torch.Tensor, logvar: torch.Tensor) -> torch.Tensor:
        """Sample from Gaussian distribution using reparameterization trick."""
        std = torch.exp(0.5 * logvar)
        eps = torch.randn_like(std)
        return mean + eps * std

    @staticmethod
    def kl_divergence(mean: torch.Tensor, logvar: torch.Tensor) -> torch.Tensor:
        """Compute KL divergence for Gaussian distributions."""
        return -0.5 * torch.sum(1 + logvar - mean.pow(2) - logvar.exp(), dim=-1)

    @staticmethod
    def stable_log(x: torch.Tensor, eps: float = 1e-8) -> torch.Tensor:
        """Numerically stable logarithm."""
        return torch.log(torch.clamp(x, min=eps))

    @staticmethod
    def gumbel_softmax(
        logits: torch.Tensor, temperature: float = 1.0, hard: bool = False
    ) -> torch.Tensor:
        """Gumbel softmax for differentiable discrete sampling."""
        # Sample Gumbel noise
        gumbel_noise = -torch.log(-torch.log(torch.rand_like(logits) + 1e-8) + 1e-8)

        # Apply Gumbel softmax
        y = F.softmax((logits + gumbel_noise) / temperature, dim=-1)

        if hard:
            # Straight-through estimator
            index = y.max(dim=-1, keepdim=True)[1]
            y_hard = torch.zeros_like(y).scatter_(-1, index, 1.0)
            y = (y_hard - y).detach() + y

        return y


class ModelUtils:
    """Model-level utilities and common patterns."""

    @staticmethod
    def freeze_parameters(model: nn.Module, freeze: bool = True) -> None:
        """Freeze or unfreeze model parameters."""
        for param in model.parameters():
            param.requires_grad = not freeze

    @staticmethod
    def freeze_layers(model: nn.Module, layer_names: list[str]) -> None:
        """Freeze specific layers by name."""
        for name, module in model.named_modules():
            if any(layer_name in name for layer_name in layer_names):
                for param in module.parameters():
                    param.requires_grad = False

    @staticmethod
    def get_layer_by_name(model: nn.Module, layer_name: str) -> nn.Module | None:
        """Get layer by name."""
        for name, module in model.named_modules():
            if name == layer_name:
                return module  # type: ignore[no-any-return]
        return None

    @staticmethod
    def replace_layer(model: nn.Module, layer_name: str, new_layer: nn.Module) -> bool:
        """Replace a layer in the model."""
        parts = layer_name.split(".")
        current_module = model

        # Navigate to parent module
        for part in parts[:-1]:
            if hasattr(current_module, part):
                current_module = getattr(current_module, part)
            else:
                return False

        # Replace the final layer
        final_part = parts[-1]
        if hasattr(current_module, final_part):
            setattr(current_module, final_part, new_layer)
            return True

        return False

    @staticmethod
    def get_model_summary(model: nn.Module) -> dict[str, Any]:
        """Get comprehensive model summary."""
        total_params = MLUtils.count_parameters(model, only_trainable=False)
        trainable_params = MLUtils.count_parameters(model, only_trainable=True)

        # Count layer types
        layer_counts: dict[str, int] = {}
        for module in model.modules():
            layer_type = type(module).__name__
            layer_counts[layer_type] = layer_counts.get(layer_type, 0) + 1

        return {
            "total_parameters": total_params,
            "trainable_parameters": trainable_params,
            "non_trainable_parameters": total_params - trainable_params,
            "model_size_mb": MLUtils.get_model_size_mb(model),
            "layer_counts": layer_counts,
            "layer_count": sum(layer_counts.values()),
        }


# Common loss functions
class CommonLosses:
    """Collection of commonly used loss functions."""

    @staticmethod
    def reconstruction_loss(
        pred: torch.Tensor, target: torch.Tensor, loss_type: str = "mse"
    ) -> torch.Tensor:
        """Compute reconstruction loss."""
        if loss_type == "mse":
            return F.mse_loss(pred, target)
        elif loss_type == "mae":
            return F.l1_loss(pred, target)
        elif loss_type == "huber":
            return F.huber_loss(pred, target)
        else:
            raise ValueError(f"Unknown loss type: {loss_type}")

    @staticmethod
    def contrastive_loss(
        embeddings: torch.Tensor, labels: torch.Tensor, temperature: float = 0.1
    ) -> torch.Tensor:
        """Compute InfoNCE contrastive loss."""
        # Normalize embeddings
        embeddings = F.normalize(embeddings, dim=-1)

        # Compute similarities
        similarities = torch.matmul(embeddings, embeddings.T) / temperature

        # Create positive pairs mask
        batch_size = embeddings.size(0)
        mask = torch.eye(batch_size, device=embeddings.device, dtype=torch.bool)

        # Compute InfoNCE loss
        exp_similarities = torch.exp(similarities)
        pos_similarities = exp_similarities.masked_select(mask)
        neg_similarities = exp_similarities.masked_fill(mask, 0).sum(dim=-1)

        loss = -torch.log(pos_similarities / (pos_similarities + neg_similarities))
        return loss.mean()

    @staticmethod
    def focal_loss(
        predictions: torch.Tensor, targets: torch.Tensor, alpha: float = 1.0, gamma: float = 2.0
    ) -> torch.Tensor:
        """Compute focal loss for imbalanced classification."""
        ce_loss = F.cross_entropy(predictions, targets, reduction="none")
        pt = torch.exp(-ce_loss)
        focal_loss = alpha * (1 - pt) ** gamma * ce_loss
        return focal_loss.mean()


# Convenience functions for most common patterns
def create_adamw_optimizer(
    model: nn.Module, lr: float = 1e-3, weight_decay: float = 0.01
) -> optim.AdamW:
    """Create AdamW optimizer with standard settings."""
    return TrainingUtils.create_optimizer(model, "adamw", lr, weight_decay)  # type: ignore[return-value]


def create_cosine_scheduler(
    optimizer: OptimizerType, warmup_steps: int, total_steps: int
) -> SequentialLR:
    """Create cosine scheduler with warmup."""
    return TrainingUtils.create_scheduler(
        optimizer, "cosine_with_warmup", warmup_steps, total_steps
    )  # type: ignore[return-value]


def safe_model_forward(model: nn.Module, *args: Any, **kwargs: Any) -> torch.Tensor:
    """Safe model forward with error handling."""
    try:
        return model(*args, **kwargs)  # type: ignore[no-any-return]
    except RuntimeError as e:
        if "out of memory" in str(e):
            logger.warning("GPU out of memory, trying CPU fallback")
            # Move inputs to CPU and retry
            cpu_args = [arg.cpu() if isinstance(arg, torch.Tensor) else arg for arg in args]
            cpu_kwargs = {
                k: v.cpu() if isinstance(v, torch.Tensor) else v for k, v in kwargs.items()
            }
            return model.cpu()(*cpu_args, **cpu_kwargs)  # type: ignore[no-any-return]
        else:
            raise


def get_activation_function(name: str) -> Callable[[torch.Tensor], torch.Tensor]:
    """Get activation function by name."""
    activations: dict[str, Callable[[torch.Tensor], torch.Tensor]] = {
        "relu": F.relu,
        "gelu": F.gelu,
        "silu": F.silu,
        "swish": F.silu,  # Alias
        "tanh": torch.tanh,
        "sigmoid": torch.sigmoid,
        "softmax": lambda x: F.softmax(x, dim=-1),
        "log_softmax": lambda x: F.log_softmax(x, dim=-1),
        "leaky_relu": lambda x: F.leaky_relu(x, 0.01),
        "elu": F.elu,
        "selu": F.selu,
    }

    if name.lower() not in activations:
        raise ValueError(f"Unknown activation function: {name}")

    return activations[name.lower()]
