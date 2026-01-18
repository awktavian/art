"""Feedback subsystem — Unified sound + haptic coordination.

This module provides:
- UnifiedFeedbackService: Coordinated feedback across platforms
- FeedbackEvent: Sound + haptic event pairs
- Predefined feedback pairs for common events

Usage:
    from kagami.core.feedback import get_unified_feedback

    feedback = await get_unified_feedback()
    await feedback.success()
    await feedback.scene_activated("Movie Mode")

Created: January 12, 2026
"""

from kagami.core.feedback.unified_feedback import (
    FEEDBACK_PAIRS,
    FeedbackEvent,
    FeedbackTarget,
    HapticIntensity,
    UnifiedFeedbackService,
    get_unified_feedback,
)

__all__ = [
    "FEEDBACK_PAIRS",
    "FeedbackEvent",
    "FeedbackTarget",
    "HapticIntensity",
    "UnifiedFeedbackService",
    "get_unified_feedback",
]
