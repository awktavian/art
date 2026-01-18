"""Training Validation Module.

CREATED: January 8, 2026

Provides MANDATORY validation checks for world model training:
- KL collapse detection (root cause of v6e failure)
- Plateau detection with automatic LR intervention
- Gradient health monitoring
- Divergence detection

These validations are ALWAYS enabled. They are not optional.
Lessons learned from TPU training failures (Jan 5-6, 2026):
- v6e_production: KL collapsed from 0.113 to -1.49e-7, lost 100K steps
- ultimate: 9 LR reductions, never converged

Usage:
    from kagami.core.training.validation import TrainingValidator

    validator = TrainingValidator()

    # In training loop:
    result = validator.validate_step(
        loss=loss,
        kl_divergence=kl_loss,
        gradient_norm=grad_norm,
        step=step,
        learning_rate=lr,
    )

    if result.should_reduce_lr:
        # Reduce learning rate
        ...

    if result.should_stop:
        raise RuntimeError(result.stop_reason)
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ValidationLevel(str, Enum):
    """Validation severity levels."""

    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"
    FATAL = "fatal"


@dataclass
class ValidationResult:
    """Result of training validation step."""

    level: ValidationLevel = ValidationLevel.OK

    # KL health
    kl_collapsed: bool = False
    kl_warning: bool = False
    kl_value: float = 0.0
    kl_consecutive_warnings: int = 0

    # Plateau detection
    plateau_detected: bool = False
    should_reduce_lr: bool = False
    recommended_lr: float | None = None
    loss_velocity: float = 0.0

    # Gradient health
    gradient_explosion: bool = False
    gradient_vanishing: bool = False
    gradient_norm: float = 0.0

    # Divergence
    loss_diverged: bool = False

    # Actions
    should_stop: bool = False
    stop_reason: str = ""

    # Messages
    messages: list[str] = field(default_factory=list)

    def add_message(self, msg: str, level: ValidationLevel = ValidationLevel.WARNING) -> None:
        """Add a validation message."""
        self.messages.append(f"[{level.value.upper()}] {msg}")
        # Upgrade overall level if needed
        if level == ValidationLevel.FATAL:
            self.level = ValidationLevel.FATAL
        elif level == ValidationLevel.CRITICAL and self.level != ValidationLevel.FATAL:
            self.level = ValidationLevel.CRITICAL
        elif level == ValidationLevel.WARNING and self.level == ValidationLevel.OK:
            self.level = ValidationLevel.WARNING


@dataclass
class KLCollapseDetector:
    """Detect KL divergence collapse.

    Root cause from v6e training (Jan 6, 2026):
    - KL went from 0.113 to -1.49e-7 (negative = numerical underflow)
    - No warning was raised during training
    - This caused posterior collapse and learning failure

    Prevention:
    1. Set kl_free_nats = 3.0 (55% of max entropy for 240-class)
    2. Set unimix = 0.01 (1% uniform mixing)
    3. Monitor KL and raise immediate warnings
    """

    collapse_threshold: float = 1e-4  # KL below this is collapse
    warning_threshold: float = 0.1  # KL below this triggers warning
    consecutive_limit: int = 100  # Fatal after this many consecutive warnings

    _consecutive_warnings: int = 0
    _history: list[float] = field(default_factory=list)

    def check(self, kl_value: float, step: int) -> tuple[bool, bool, int]:
        """Check KL health.

        Returns:
            (collapsed, warning, consecutive_warnings)
        """
        self._history.append(kl_value)
        if len(self._history) > 1000:
            self._history = self._history[-1000:]

        collapsed = False
        warning = False

        if kl_value < self.collapse_threshold:
            collapsed = True
            self._consecutive_warnings += 1
            logger.error(
                f"KL COLLAPSE at step {step}: KL={kl_value:.2e} < {self.collapse_threshold}. "
                f"Consecutive: {self._consecutive_warnings}/{self.consecutive_limit}"
            )
        elif kl_value < self.warning_threshold:
            warning = True
            self._consecutive_warnings += 1
            if step % 100 == 0:
                logger.warning(f"KL low at step {step}: {kl_value:.4f}")
        else:
            self._consecutive_warnings = 0

        return collapsed, warning, self._consecutive_warnings


@dataclass
class PlateauDetector:
    """Detect loss plateaus and trigger LR reduction.

    Root cause from v6e training (Jan 6, 2026):
    - Loss plateaued at 0.4-0.45 for 40K steps
    - No plateau detection or LR adaptation
    - JAX run achieved 0.003 loss in only 5K steps
    """

    window_size: int = 1000
    velocity_threshold: float = 1e-6
    reduction_factor: float = 0.5
    min_lr: float = 1e-7
    cooldown_steps: int = 2000

    _loss_history: list[float] = field(default_factory=list)
    _last_reduction_step: int = 0
    _num_reductions: int = 0

    def check(
        self, loss: float, step: int, current_lr: float
    ) -> tuple[bool, bool, float | None, float]:
        """Check for plateau.

        Returns:
            (plateau_detected, should_reduce_lr, new_lr, loss_velocity)
        """
        self._loss_history.append(loss)
        if len(self._loss_history) > self.window_size:
            self._loss_history = self._loss_history[-self.window_size :]

        if len(self._loss_history) < self.window_size // 2:
            return False, False, None, 0.0

        # Compute loss velocity
        recent = self._loss_history[-self.window_size :]
        window_mean = sum(recent) / len(recent)
        window_std = (sum((x - window_mean) ** 2 for x in recent) / len(recent)) ** 0.5

        if len(recent) >= 100:
            first_half = sum(recent[: len(recent) // 2]) / (len(recent) // 2)
            second_half = sum(recent[len(recent) // 2 :]) / (len(recent) // 2)
            loss_velocity = (second_half - first_half) / (len(recent) // 2)
        else:
            loss_velocity = 0.0

        # Plateau: low velocity + low variance
        is_plateau = abs(loss_velocity) < self.velocity_threshold and window_std < window_mean * 0.1

        should_reduce = False
        new_lr = None

        if is_plateau:
            in_cooldown = (step - self._last_reduction_step) < self.cooldown_steps
            at_minimum = current_lr <= self.min_lr

            if not in_cooldown and not at_minimum:
                new_lr = max(current_lr * self.reduction_factor, self.min_lr)
                should_reduce = True
                self._last_reduction_step = step
                self._num_reductions += 1

                logger.warning(
                    f"PLATEAU at step {step}: velocity={loss_velocity:.2e}, "
                    f"reducing LR {current_lr:.2e} -> {new_lr:.2e} (#{self._num_reductions})"
                )

        return is_plateau, should_reduce, new_lr, loss_velocity


@dataclass
class GradientHealthMonitor:
    """Monitor gradient health."""

    explosion_threshold: float = 100.0
    vanishing_threshold: float = 1e-7
    history_size: int = 100

    _history: list[float] = field(default_factory=list)

    def check(self, gradient_norm: float, step: int) -> tuple[bool, bool]:
        """Check gradient health.

        Returns:
            (explosion, vanishing)
        """
        self._history.append(gradient_norm)
        if len(self._history) > self.history_size:
            self._history = self._history[-self.history_size :]

        explosion = gradient_norm > self.explosion_threshold
        vanishing = gradient_norm < self.vanishing_threshold

        if explosion:
            logger.error(f"GRADIENT EXPLOSION at step {step}: norm={gradient_norm:.2e}")
        if vanishing:
            logger.warning(f"Vanishing gradient at step {step}: norm={gradient_norm:.2e}")

        return explosion, vanishing


@dataclass
class DivergenceDetector:
    """Detect loss divergence."""

    spike_threshold: float = 10.0  # Loss > 10x recent average
    window_size: int = 100

    _history: list[float] = field(default_factory=list)

    def check(self, loss: float, step: int) -> bool:
        """Check for divergence.

        Returns:
            diverged
        """
        self._history.append(loss)
        if len(self._history) > self.window_size:
            self._history = self._history[-self.window_size :]

        if len(self._history) < 10:
            return False

        avg = sum(self._history[:-1]) / (len(self._history) - 1)
        diverged = loss > avg * self.spike_threshold

        if diverged:
            logger.error(
                f"LOSS DIVERGENCE at step {step}: {loss:.4f} > {avg:.4f} * {self.spike_threshold}"
            )

        return diverged


class TrainingValidator:
    """Unified training validator.

    ALWAYS use this in training loops. Not optional.

    Example:
        validator = TrainingValidator()

        for step, batch in enumerate(dataloader):
            loss, kl_loss = model(batch)
            grad_norm = clip_gradients(...)

            result = validator.validate_step(
                loss=loss,
                kl_divergence=kl_loss,
                gradient_norm=grad_norm,
                step=step,
                learning_rate=optimizer.param_groups[0]['lr'],
            )

            if result.should_reduce_lr:
                for pg in optimizer.param_groups:
                    pg['lr'] = result.recommended_lr

            if result.should_stop:
                raise RuntimeError(result.stop_reason)
    """

    def __init__(
        self,
        kl_collapse_threshold: float = 1e-4,
        kl_warning_threshold: float = 0.1,
        kl_consecutive_limit: int = 100,
        plateau_window: int = 1000,
        plateau_velocity_threshold: float = 1e-6,
        lr_reduction_factor: float = 0.5,
        min_lr: float = 1e-7,
        cooldown_steps: int = 2000,
        gradient_explosion_threshold: float = 100.0,
        divergence_threshold: float = 10.0,
    ):
        """Initialize validator with all detection parameters."""
        self.kl_detector = KLCollapseDetector(
            collapse_threshold=kl_collapse_threshold,
            warning_threshold=kl_warning_threshold,
            consecutive_limit=kl_consecutive_limit,
        )

        self.plateau_detector = PlateauDetector(
            window_size=plateau_window,
            velocity_threshold=plateau_velocity_threshold,
            reduction_factor=lr_reduction_factor,
            min_lr=min_lr,
            cooldown_steps=cooldown_steps,
        )

        self.gradient_monitor = GradientHealthMonitor(
            explosion_threshold=gradient_explosion_threshold,
        )

        self.divergence_detector = DivergenceDetector(
            spike_threshold=divergence_threshold,
        )

        self._step = 0

    def validate_step(
        self,
        loss: float,
        kl_divergence: float,
        gradient_norm: float,
        step: int,
        learning_rate: float,
    ) -> ValidationResult:
        """Validate a training step.

        Args:
            loss: Current loss value
            kl_divergence: KL divergence component
            gradient_norm: Gradient norm after clipping
            step: Current training step
            learning_rate: Current learning rate

        Returns:
            ValidationResult with all checks and recommended actions
        """
        self._step = step
        result = ValidationResult()

        # 1. KL collapse detection (CRITICAL - root cause of v6e failure)
        collapsed, warning, consecutive = self.kl_detector.check(kl_divergence, step)
        result.kl_collapsed = collapsed
        result.kl_warning = warning
        result.kl_value = kl_divergence
        result.kl_consecutive_warnings = consecutive

        if collapsed:
            result.add_message(
                f"KL COLLAPSED: {kl_divergence:.2e}. Check kl_free_nats (should be 3.0) and unimix (should be 0.01)",
                ValidationLevel.CRITICAL,
            )

        if consecutive >= self.kl_detector.consecutive_limit:
            result.should_stop = True
            result.stop_reason = f"KL collapse: {consecutive} consecutive warnings"
            result.add_message(result.stop_reason, ValidationLevel.FATAL)

        # 2. Plateau detection
        plateau, reduce_lr, new_lr, velocity = self.plateau_detector.check(
            loss, step, learning_rate
        )
        result.plateau_detected = plateau
        result.should_reduce_lr = reduce_lr
        result.recommended_lr = new_lr
        result.loss_velocity = velocity

        if plateau:
            result.add_message(
                f"Plateau detected: velocity={velocity:.2e}", ValidationLevel.WARNING
            )

        # 3. Gradient health
        explosion, vanishing = self.gradient_monitor.check(gradient_norm, step)
        result.gradient_explosion = explosion
        result.gradient_vanishing = vanishing
        result.gradient_norm = gradient_norm

        if explosion:
            result.add_message(f"Gradient explosion: {gradient_norm:.2e}", ValidationLevel.CRITICAL)

        # 4. Divergence detection
        diverged = self.divergence_detector.check(loss, step)
        result.loss_diverged = diverged

        if diverged:
            result.add_message(f"Loss diverged: {loss:.4f}", ValidationLevel.CRITICAL)
            result.should_stop = True
            result.stop_reason = f"Loss divergence at step {step}"

        return result

    def get_summary(self) -> dict[str, Any]:
        """Get validation summary."""
        return {
            "step": self._step,
            "kl_consecutive_warnings": self.kl_detector._consecutive_warnings,
            "plateau_reductions": self.plateau_detector._num_reductions,
            "last_kl": self.kl_detector._history[-1] if self.kl_detector._history else None,
            "last_loss": self.plateau_detector._loss_history[-1]
            if self.plateau_detector._loss_history
            else None,
        }


__all__ = [
    "DivergenceDetector",
    "GradientHealthMonitor",
    "KLCollapseDetector",
    "PlateauDetector",
    "TrainingValidator",
    "ValidationLevel",
    "ValidationResult",
]
