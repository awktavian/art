"""K os Cognitive Metrics.

Auto-generated metrics for cognitive domain.
"""

from kagami_observability.metrics.core import Counter, Gauge, Histogram

ATTENTION_CONTROLLER_ADJUSTMENTS_TOTAL = Counter(
    "kagami_attention_controller_adjustments_total",
    "Attention Controller Adjustments Total",
)
ATTENTION_DWELL_SECONDS = Histogram(
    "kagami_attention_dwell_seconds",
    "Attention Dwell Seconds",
)
ATTENTION_FOCUS_CONFIDENCE = Gauge(
    "kagami_attention_focus_confidence",
    "Attention Focus Confidence",
)
ATTENTION_SWITCH_TOTAL = Counter(
    "kagami_attention_switch_total",
    "Attention Switch Total",
)
WORKSPACE_IGNITIONS_TOTAL = Counter(
    "kagami_workspace_ignitions_total",
    "Workspace ignition events (global workspace broadcast)",
)
VALUED_ATTENTION_PREFERENCE_NORM = Gauge(
    "kagami_valued_attention_preference_norm",
    "Valued Attention Preference Norm",
)
VALUED_ATTENTION_SESSIONS_TOTAL = Counter(
    "kagami_valued_attention_sessions_total",
    "Valued Attention Sessions Total",
)
VALUED_ATTENTION_TD_ERROR = Gauge(
    "kagami_valued_attention_td_error",
    "Valued Attention Td Error",
)
VALUED_ATTENTION_VALUE_LOSS = Gauge(
    "kagami_valued_attention_value_loss",
    "Valued Attention Value Loss",
)
WORKSPACE_BROADCAST_DURATION = Histogram(
    "kagami_workspace_broadcast_duration",
    "Workspace Broadcast Duration",
)
WORKSPACE_BROADCAST_TOTAL = Counter(
    "kagami_workspace_broadcast_total",
    "Workspace Broadcast Total",
)

# Consciousness metrics (used by dashboards)
CONSCIOUSNESS_THREAT_SCORE = Gauge(
    "kagami_consciousness_threat_score",
    "Threat score from consciousness subsystem (0-1)",
)

CONSCIOUSNESS_VALENCE = Gauge(
    "kagami_consciousness_valence",
    "Emotional valence from consciousness (-1 to 1)",
)

CONSCIOUSNESS_AROUSAL = Gauge(
    "kagami_consciousness_arousal",
    "Arousal level from consciousness (-1 to 1)",
)

CONSCIOUSNESS_ETHICAL_BLOCKS_TOTAL = Counter(
    "kagami_consciousness_ethical_blocks_total",
    "Operations blocked by ethical reasoning",
    ["reason"],
)

CONSCIOUSNESS_PREDICTION_ERROR_MS = Histogram(
    "kagami_consciousness_prediction_error_ms",
    "Prediction error in milliseconds",
    buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000],
)

# Agent aggregate metrics (for dashboards that expect this naming)
AGENTS_ACTIVE = Gauge(
    "kagami_agents_active",
    "Number of active agents (alias for colony population)",
    ["colony"],
)

# Reflection/Introspection metrics (used by kagami.core.debugging.manager)
REFLECTION_DURATION_SECONDS = Histogram(
    "kagami_reflection_duration_seconds",
    "Duration of reflection operations in seconds",
    ["kind"],  # post_intent, periodic
)

REFLECTIONS_TOTAL = Counter(
    "kagami_reflections_total",
    "Total reflection operations",
    ["kind", "outcome"],  # kind: post_intent/periodic, outcome: queued/completed/skipped/error
)

__all__ = [
    "AGENTS_ACTIVE",
    "ATTENTION_CONTROLLER_ADJUSTMENTS_TOTAL",
    "ATTENTION_DWELL_SECONDS",
    "ATTENTION_FOCUS_CONFIDENCE",
    "ATTENTION_SWITCH_TOTAL",
    "CONSCIOUSNESS_AROUSAL",
    "CONSCIOUSNESS_ETHICAL_BLOCKS_TOTAL",
    "CONSCIOUSNESS_PREDICTION_ERROR_MS",
    "CONSCIOUSNESS_THREAT_SCORE",
    "CONSCIOUSNESS_VALENCE",
    "REFLECTIONS_TOTAL",
    "REFLECTION_DURATION_SECONDS",
    "VALUED_ATTENTION_PREFERENCE_NORM",
    "VALUED_ATTENTION_SESSIONS_TOTAL",
    "VALUED_ATTENTION_TD_ERROR",
    "VALUED_ATTENTION_VALUE_LOSS",
    "WORKSPACE_BROADCAST_DURATION",
    "WORKSPACE_BROADCAST_TOTAL",
    "WORKSPACE_IGNITIONS_TOTAL",
]
