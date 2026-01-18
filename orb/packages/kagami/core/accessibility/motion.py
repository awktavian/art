"""Reduced Motion Utilities.

Provides utilities for respecting user preferences for reduced motion,
supporting users with vestibular disorders, motion sensitivity, or
those who simply prefer less animation.

Usage:
    from kagami.core.accessibility.motion import (
        should_reduce_motion,
        get_motion_config,
        MotionConfig,
    )

    # Check if motion should be reduced
    if should_reduce_motion():
        # Use instant transitions
        duration = 0
    else:
        # Use normal animation duration
        duration = 300

    # Get full motion configuration
    config = get_motion_config()
    transition_duration = config.get_duration("fade")

Created: January 1, 2026
Part of: Apps 100/100 Transformation - Phase 1.4
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MotionConfig:
    """Configuration for motion/animation settings.

    When reduce_motion is True, most animations should be either:
    - Removed entirely (instant transitions)
    - Reduced to simple opacity fades
    - Significantly shortened in duration
    """

    reduce_motion: bool = False

    # Normal animation durations (ms)
    duration_instant: int = 0
    duration_fast: int = 100
    duration_normal: int = 250
    duration_slow: int = 400
    duration_page_transition: int = 300

    # Reduced motion durations (ms)
    reduced_duration_instant: int = 0
    reduced_duration_fast: int = 0
    reduced_duration_normal: int = 50  # Minimal fade
    reduced_duration_slow: int = 100
    reduced_duration_page_transition: int = 0  # No page transitions

    # Animation types that should be completely removed
    disable_parallax: bool = True  # When reduce_motion=True
    disable_auto_play: bool = True  # Auto-playing animations
    disable_hover_effects: bool = False  # Keep simple hover
    disable_scroll_animations: bool = True  # Scroll-triggered
    disable_background_animations: bool = True  # Background effects

    def get_duration(self, type: str = "normal") -> int:
        """Get the appropriate duration for an animation type.

        Args:
            type: Animation type ("instant", "fast", "normal", "slow", "page_transition")

        Returns:
            Duration in milliseconds
        """
        if self.reduce_motion:
            durations = {
                "instant": self.reduced_duration_instant,
                "fast": self.reduced_duration_fast,
                "normal": self.reduced_duration_normal,
                "slow": self.reduced_duration_slow,
                "page_transition": self.reduced_duration_page_transition,
            }
        else:
            durations = {
                "instant": self.duration_instant,
                "fast": self.duration_fast,
                "normal": self.duration_normal,
                "slow": self.duration_slow,
                "page_transition": self.duration_page_transition,
            }

        return durations.get(type, self.duration_normal)

    def get_easing(self, type: str = "normal") -> str:
        """Get the appropriate easing function.

        When reduced motion is enabled, use linear or no easing.

        Args:
            type: Animation type

        Returns:
            CSS easing function string
        """
        if self.reduce_motion:
            return "linear"

        easings = {
            "instant": "linear",
            "fast": "ease-out",
            "normal": "ease-in-out",
            "slow": "ease-in-out",
            "page_transition": "cubic-bezier(0.4, 0, 0.2, 1)",  # Material Design
            "bounce": "cubic-bezier(0.68, -0.55, 0.265, 1.55)",
            "spring": "cubic-bezier(0.175, 0.885, 0.32, 1.275)",
        }

        return easings.get(type, "ease-in-out")

    def should_animate(self, animation_type: str) -> bool:
        """Check if a specific animation type should run.

        Args:
            animation_type: Type of animation

        Returns:
            True if animation should run
        """
        if not self.reduce_motion:
            return True

        # These animations are disabled when reduce_motion is True
        disabled_types = set()
        if self.disable_parallax:
            disabled_types.add("parallax")
        if self.disable_auto_play:
            disabled_types.update(["auto_play", "looping", "ambient"])
        if self.disable_hover_effects:
            disabled_types.update(["hover", "hover_scale", "hover_lift"])
        if self.disable_scroll_animations:
            disabled_types.update(["scroll", "scroll_reveal", "sticky"])
        if self.disable_background_animations:
            disabled_types.update(["background", "particles", "gradient"])

        return animation_type not in disabled_types

    def to_css_vars(self) -> dict[str, str]:
        """Generate CSS custom properties for motion settings.

        Returns:
            Dictionary of CSS variable names to values
        """
        return {
            "--motion-duration-instant": f"{self.get_duration('instant')}ms",
            "--motion-duration-fast": f"{self.get_duration('fast')}ms",
            "--motion-duration-normal": f"{self.get_duration('normal')}ms",
            "--motion-duration-slow": f"{self.get_duration('slow')}ms",
            "--motion-duration-page": f"{self.get_duration('page_transition')}ms",
            "--motion-easing-default": self.get_easing("normal"),
            "--motion-easing-bounce": self.get_easing("bounce")
            if not self.reduce_motion
            else "linear",
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "reduce_motion": self.reduce_motion,
            "durations": {
                "instant": self.get_duration("instant"),
                "fast": self.get_duration("fast"),
                "normal": self.get_duration("normal"),
                "slow": self.get_duration("slow"),
                "page_transition": self.get_duration("page_transition"),
            },
            "disabled": {
                "parallax": self.reduce_motion and self.disable_parallax,
                "auto_play": self.reduce_motion and self.disable_auto_play,
                "hover_effects": self.reduce_motion and self.disable_hover_effects,
                "scroll_animations": self.reduce_motion and self.disable_scroll_animations,
                "background_animations": self.reduce_motion and self.disable_background_animations,
            },
        }


# Global motion configuration
_motion_config = MotionConfig()


def get_motion_config() -> MotionConfig:
    """Get the current motion configuration.

    Returns:
        The global MotionConfig instance
    """
    return _motion_config


def set_reduce_motion(reduce: bool) -> None:
    """Set the global reduce motion preference.

    Args:
        reduce: True to reduce motion
    """
    _motion_config.reduce_motion = reduce
    logger.debug(f"Reduced motion set to: {reduce}")


def should_reduce_motion() -> bool:
    """Check if motion should be reduced.

    Returns:
        True if motion should be reduced
    """
    return _motion_config.reduce_motion


def get_animation_duration(type: str = "normal") -> int:
    """Get animation duration for the given type.

    Convenience function for getting duration.

    Args:
        type: Animation type

    Returns:
        Duration in milliseconds
    """
    return _motion_config.get_duration(type)


def get_animation_style(type: str = "normal") -> dict[str, str]:
    """Get CSS style properties for an animation.

    Args:
        type: Animation type

    Returns:
        Dictionary with 'transition-duration' and 'transition-timing-function'
    """
    return {
        "transition-duration": f"{_motion_config.get_duration(type)}ms",
        "transition-timing-function": _motion_config.get_easing(type),
    }


# CSS media query helper
def get_prefers_reduced_motion_css() -> str:
    """Get CSS for respecting prefers-reduced-motion.

    Returns:
        CSS string with reduced motion media query
    """
    return """
@media (prefers-reduced-motion: reduce) {
    *,
    *::before,
    *::after {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
        scroll-behavior: auto !important;
    }
}
"""


__all__ = [
    "MotionConfig",
    "get_animation_duration",
    "get_animation_style",
    "get_motion_config",
    "get_prefers_reduced_motion_css",
    "set_reduce_motion",
    "should_reduce_motion",
]
