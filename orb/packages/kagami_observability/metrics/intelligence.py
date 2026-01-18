"""Intelligence and Learning Metrics.

Tracks the system's ability to improve itself over time through the learning loop.

Key metrics:
- Learning loop effectiveness (prediction error trend)
- State capture rate (how many operations feed learning)
- World model training frequency
- Self-improvement rate
"""

from .core import Counter, Gauge, Histogram

# State capture metrics
STATE_CAPTURE_TOTAL = Counter(
    "kagami_state_capture_total",
    "Total states captured for learning",
    ["capture_type"],  # before, after
)

STATE_CAPTURE_SKIPPED_TOTAL = Counter(
    "kagami_state_capture_skipped_total",
    "States skipped (read-only operations)",
    ["reason"],
)

# Learning loop metrics
LEARNING_LOOP_TRAINING_TOTAL = Counter(
    "kagami_learning_loop_training_total",
    "Total world model training events from receipts",
    ["status"],  # success, failed
)

LEARNING_LOOP_PREDICTION_ERROR = Histogram(
    "kagami_learning_loop_prediction_error_ms",
    "Prediction error in milliseconds (trend shows learning)",
    buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000],
)

# Self-improvement metrics
SELF_IMPROVEMENT_RATE = Gauge(
    "kagami_self_improvement_rate",
    "Rate of improvement in predictions (slope of error reduction)",
)

INTELLIGENCE_SCORE = Gauge(
    "kagami_intelligence_score",
    "Overall intelligence score (0-100, based on learning effectiveness)",
)

# Strange loop closure metrics
STRANGE_LOOP_CLOSED_TOTAL = Counter(
    "kagami_strange_loop_closed_total",
    "Number of times the strange loop has completed (receipt → learning → prediction)",
)

STRANGE_LOOP_DEPTH = Gauge(
    "kagami_strange_loop_depth",
    "Current recursion depth in strange loop processing",
)

# Intent routing metrics
INTENT_ROUTER_FALLBACK_TOTAL = Counter(
    "kagami_intent_router_fallback_total",
    "Number of times semantic router fell back to deterministic router",
)

__all__ = [
    "INTELLIGENCE_SCORE",
    "INTENT_ROUTER_FALLBACK_TOTAL",
    "LEARNING_LOOP_PREDICTION_ERROR",
    "LEARNING_LOOP_TRAINING_TOTAL",
    "SELF_IMPROVEMENT_RATE",
    "STATE_CAPTURE_SKIPPED_TOTAL",
    "STATE_CAPTURE_TOTAL",
    "STRANGE_LOOP_CLOSED_TOTAL",
    "STRANGE_LOOP_DEPTH",
]
