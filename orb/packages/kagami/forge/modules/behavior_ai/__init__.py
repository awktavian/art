"""
Behavior AI Module - Character personality, emotions, and decision-making
Includes personality analysis, emotional processing, and decision matrices.
"""

from .decision_matrix import DecisionMatrix
from .emotional_processor import EmotionalProcessor
from .personality_engine import PersonalityEngine

__all__: list[str] = [
    "DecisionMatrix",
    "EmotionalProcessor",
    "PersonalityEngine",
]
