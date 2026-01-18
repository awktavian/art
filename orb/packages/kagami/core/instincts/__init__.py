"""Core Instincts: Universal adaptive mechanisms (not brittle heuristics).

MIGRATION NOTE (December 2025): Prefer importing from kagami.core.mind
for unified cognitive access.

Real instincts that work for ALL future cases:
- Prediction instinct: Learn patterns from observation
- Threat instinct: Avoid patterns that cause harm
- Learning instinct: Update from every experience
- Ethical instinct: Constitutional constraints (general principles)
- Self-preservation: Detect and repair failures
"""

from .ethical_instinct import JailbreakDetector
from .learning_instinct import LearningInstinct
from .prediction_instinct import PredictionInstinct
from .threat_instinct import ThreatInstinct

# Alias for backward compatibility (EthicalInstinct -> JailbreakDetector)
EthicalInstinct = JailbreakDetector

__all__ = [
    "EthicalInstinct",  # Alias for backward compatibility
    "JailbreakDetector",
    "LearningInstinct",
    "PredictionInstinct",
    "ThreatInstinct",
]
