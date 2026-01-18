"""Kagami Learning Module — Pattern learning and adaptation.

Provides general-purpose pattern learning that works across all domains:
- Travel patterns (departures, commutes)
- Presence patterns (home/away)
- Sleep patterns (bedtime, wake)
- Activity patterns (work, exercise)
- Usage patterns (devices, rooms)

Usage:
    from kagami.core.learning import get_pattern_learner, TimeGranularity

    # Get or create a learner
    learner = get_pattern_learner("my_domain", TimeGranularity.HOUR)

    # Record events/values
    learner.record_event()  # Binary event occurred
    learner.record_value(25.5)  # Continuous value

    # Query patterns
    prob = learner.get_probability()
    expected = learner.get_expected_value()

    # Predict
    prediction = learner.predict(datetime.now() + timedelta(hours=2))
"""

from kagami.core.learning.pattern_learner import (
    PatternLearner,
    PatternSlot,
    SemanticPatternLearner,
    TimeGranularity,
    TimeSlot,
    get_activity_learner,
    get_pattern_learner,
    get_presence_learner,
    get_semantic_pattern_learner,
    get_sleep_learner,
    get_travel_departure_learner,
    get_travel_duration_learner,
    save_all_patterns,
)
from kagami.core.learning.receipt_learning import (
    LearningUpdate,
    ReceiptLearningEngine,
    get_receipt_learner,
    reset_receipt_learner,
)

__all__ = [
    # Receipt learning
    "LearningUpdate",
    "PatternLearner",
    "PatternSlot",
    "ReceiptLearningEngine",
    "SemanticPatternLearner",
    "TimeGranularity",
    "TimeSlot",
    "get_activity_learner",
    "get_pattern_learner",
    "get_presence_learner",
    "get_receipt_learner",
    "get_semantic_pattern_learner",
    "get_sleep_learner",
    "get_travel_departure_learner",
    "get_travel_duration_learner",
    "reset_receipt_learner",
    "save_all_patterns",
]
