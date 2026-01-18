"""Curriculum learning components for training.

CREATED: December 21, 2025

This package contains modular curriculum learning components extracted
from UnifiedCurriculumScheduler to reduce god class complexity.

Components:
-----------
- CurriculumCatastropheDetector: Phase-specific catastrophe detection
"""

from kagami.core.training.curriculum.catastrophe_detector import (
    CurriculumCatastropheDetector,
)

__all__ = [
    "CurriculumCatastropheDetector",
]
