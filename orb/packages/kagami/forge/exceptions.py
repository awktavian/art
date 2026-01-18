"""
Custom exceptions for Forge character generation system.

Provides specific exception types for different failure scenarios.
All Forge exceptions extend the core K os exception hierarchy.
"""

from typing import Any

from kagami.core.exceptions import (
    ForgeError,
    ProcessingError,
    ValidationError,
)

# Re-export core exceptions for convenience
__all__ = [
    "AnimationError",
    "ExportError",
    "ForgeError",
    "GenerationError",
    "GenerationTimeoutError",
    "ModuleInitializationError",
    "ModuleNotAvailableError",
    "NarrativeGenerationError",
    "PersonalityGenerationError",
    "ProcessingError",
    "RiggingError",
    "ValidationError",
    "VisualGenerationError",
    "VoiceGenerationError",
]


class ModuleInitializationError(ForgeError):
    """Raised when a module fails to initialize."""

    def __init__(self, module_name: str, reason: str) -> None:
        super().__init__(
            f"Failed to initialize module '{module_name}': {reason}",
            {"module": module_name, "reason": reason},
        )
        self.module_name = module_name
        self.reason = reason


class ModuleNotAvailableError(ForgeError):
    """Raised when a required module is not available."""

    def __init__(self, module_name: str) -> None:
        super().__init__(f"Module '{module_name}' is not available", {"module": module_name})
        self.module_name = module_name


class GenerationError(ForgeError):
    """Base class for character generation errors."""


class GenerationTimeoutError(GenerationError):
    """Raised when character generation exceeds time limit."""

    def __init__(self, phase: str, timeout_ms: float) -> None:
        super().__init__(
            f"Generation timed out in phase '{phase}' after {timeout_ms}ms",
            {"phase": phase, "timeout_ms": timeout_ms},
        )
        self.phase = phase
        self.timeout_ms = timeout_ms


class VisualGenerationError(GenerationError):
    """Raised when visual generation fails."""

    def __init__(self, reason: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            f"Visual generation failed: {reason}",
            {"component": "visual", "reason": reason, **(details or {})},
        )


class PersonalityGenerationError(GenerationError):
    """Raised when personality generation fails."""

    def __init__(self, reason: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            f"Personality generation failed: {reason}",
            {"component": "personality", "reason": reason, **(details or {})},
        )


class VoiceGenerationError(GenerationError):
    """Raised when voice synthesis fails."""

    def __init__(self, reason: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            f"Voice generation failed: {reason}",
            {"component": "voice", "reason": reason, **(details or {})},
        )


class NarrativeGenerationError(GenerationError):
    """Raised when narrative generation fails."""

    def __init__(self, reason: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            f"Narrative generation failed: {reason}",
            {"component": "narrative", "reason": reason, **(details or {})},
        )


class RiggingError(GenerationError):
    """Raised when character rigging fails."""

    def __init__(self, reason: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            f"Rigging failed: {reason}",
            {"component": "rigging", "reason": reason, **(details or {})},
        )


class AnimationError(GenerationError):
    """Raised when animation generation fails."""

    def __init__(self, reason: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            f"Animation failed: {reason}",
            {"component": "animation", "reason": reason, **(details or {})},
        )


class ExportError(GenerationError):
    """Raised when character export fails."""

    def __init__(
        self, reason: str, format: str | None = None, details: dict[str, Any] | None = None
    ) -> None:
        context = {"component": "export", "reason": reason, **(details or {})}
        if format:
            context["format"] = format
        super().__init__(
            f"Export failed: {reason}",
            context,
        )
