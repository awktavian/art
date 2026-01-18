"""K os Learning system metrics.

Domain-specific metrics for the Learning system.
"""

from .core import REGISTRY, Counter, Gauge, Histogram

# ==============================================================================
# COORDINATION & RL METRICS
# ==============================================================================

COORDINATION_LLM_USAGE_TOTAL = Counter(
    "kagami_coordination_llm_usage_total",
    "Total LLM usage in coordination layer",
    ["system"],
    registry=REGISTRY,
)

RL_ACTION_SELECTION_TOTAL = Counter(
    "kagami_rl_action_selection_total",
    "Total RL action selections",
    ["strategy"],
    registry=REGISTRY,
)

RL_WORLD_MODEL_ERROR = Gauge(
    "kagami_rl_world_model_error",
    "RL world model prediction error",
    registry=REGISTRY,
)

# Semantic Flow Kernel metrics (namespaced under learning)
SEMANTIC_FLOW_MULTIPLIER = Histogram(
    "kagami_semantic_flow_multiplier",
    "Distribution of Semantic Flow Kernel multipliers",
    ["source"],
    registry=REGISTRY,
)

SEMANTIC_FLOW_KERNEL_COMPUTATIONS = Counter(
    "kagami_semantic_flow_kernel_computations_total",
    "Total Semantic Flow Kernel multiplier computations",
    ["source"],
    registry=REGISTRY,
)

SEMANTIC_FLOW_COLONY_FACTOR = Histogram(
    "kagami_semantic_flow_colony_factor",
    "Colony flow factors used in morphogenesis",
    ["phase"],
    registry=REGISTRY,
)

SEMANTIC_SELF_KERNEL_SNAPSHOT = Histogram(
    "kagami_semantic_self_kernel_snapshot",
    "Trace-like self-kernel snapshot per homeostasis",
    registry=REGISTRY,
)

CURRICULUM_LEVEL = Gauge(
    "kagami_curriculum_level",
    "Curriculum Level",
)

GEOMETRIC_REASONING_CONFIDENCE = Gauge(
    "kagami_geometric_reasoning_confidence",
    "Geometric Reasoning Confidence",
)

GEOMETRIC_REASONING_QUERIES_TOTAL = Counter(
    "kagami_geometric_reasoning_queries_total",
    "Geometric Reasoning Queries Total",
)

HYPERDIMENSIONAL_MANIFOLD_SEARCH_DURATION = Histogram(
    "kagami_hyperdimensional_manifold_search_duration",
    "Hyperdimensional Manifold Search Duration",
)

HYPERDIMENSIONAL_QUERY_RESULTS_TOTAL = Counter(
    "kagami_hyperdimensional_query_results_total",
    "Hyperdimensional Query Results Total",
)

HYPERDIMENSIONAL_SEMANTIC_SEARCH_DURATION = Histogram(
    "kagami_hyperdimensional_semantic_search_duration",
    "Hyperdimensional Semantic Search Duration",
)

HYPERDIMENSIONAL_SUBSPACE_ACTIVATION = Gauge(
    "kagami_hyperdimensional_subspace_activation",
    "Hyperdimensional Subspace Activation",
)

HYPERDIMENSIONAL_THOUGHTS_TOTAL = Counter(
    "kagami_hyperdimensional_thoughts_total",
    "Hyperdimensional Thoughts Total",
)

KOOPMAN_ALERTS_TOTAL = Counter(
    "kagami_koopman_alerts_total",
    "Koopman Alerts Total",
)

KOOPMAN_DRIFT_SCORE = Gauge(
    "kagami_koopman_drift_score",
    "Koopman Drift Score",
)

# ==============================================================================
# TIER S SLO METRICS - Learning System (19/20 rating)
# ==============================================================================

# Learning improvement tracking (SLO: positive improvement)
LEARNING_IMPROVEMENT_PERCENTAGE = Gauge(
    "kagami_learning_improvement_percentage",
    "Learning improvement percentage over baseline",
)

# Learning velocity (improvement per training session)
LEARNING_VELOCITY = Gauge(
    "kagami_learning_velocity",
    "Learning velocity (improvement per training session)",
)

# Training frequency (SLO: fresh data < 30s)
LEARNING_TRAINING_FREQUENCY_HZ = Gauge(
    "kagami_learning_training_frequency_hz",
    "Learning training frequency in Hz",
)

# Prediction error tracking
LEARNING_PREDICTION_ERROR_MS = Gauge(
    "kagami_learning_prediction_error_ms",
    "Learning prediction error in milliseconds",
)

# Autonomous goals
LEARNING_AUTONOMOUS_GOALS_GENERATED = Counter(
    "kagami_learning_autonomous_goals_generated_total",
    "Total autonomous goals generated",
)

LEARNING_AUTONOMOUS_GOALS_PURSUED = Counter(
    "kagami_learning_autonomous_goals_pursued_total",
    "Total autonomous goals pursued",
    ["status", "priority"],
)

# World model integration metrics (used by world_model_integration)
LEARNING_WORLD_MODEL_UPDATES = Counter(
    "kagami_learning_world_model_updates_total",
    "World model updates triggered by learning loop",
    ["update_type"],
)

# SLO compliance
LEARNING_SLO_COMPLIANCE = Gauge(
    "kagami_learning_slo_compliance",
    "Learning system SLO compliance (1=compliant, 0=non-compliant)",
    ["slo_type"],
)

# ==============================================================================
# INTEGRATION BATCH 4: Evolution & Goal Pursuit Metrics (Nov 10, 2025)
# ==============================================================================

# Evolution cycle metrics
EVOLUTION_CYCLES_TOTAL = Counter(
    "kagami_evolution_cycles_total",
    "Evolution cycle completions",
    ["phase"],  # observe/learn/improve/act/verify/evolve
)

EVOLUTION_CYCLE_DURATION_SECONDS = Histogram(
    "kagami_evolution_cycle_duration_seconds",
    "Duration of evolution cycles",
    ["phase"],  # observe/learn/improve/act/verify/evolve
)

EVOLUTION_FITNESS_SCORE = Histogram(
    "kagami_evolution_fitness_score",
    "Fitness scores for evolution candidates",
    ["category"],
)

EVOLUTION_IMPROVEMENTS_PROPOSED_TOTAL = Counter(
    "kagami_evolution_improvements_proposed_total",
    "Total improvements proposed",
    ["category"],
)

EVOLUTION_IMPROVEMENTS_REJECTED_TOTAL = Counter(
    "kagami_evolution_improvements_rejected_total",
    "Total improvements rejected",
    ["reason"],  # governance/guardrail_violation/low_fitness/skeptic_rejected
)

EVOLUTION_IMPROVEMENTS_APPLIED_TOTAL = Counter(
    "kagami_evolution_improvements_applied_total", "Improvements actually applied to codebase"
)

EVOLUTION_IMPROVEMENTS_SUCCESSFUL_TOTAL = Counter(
    "kagami_evolution_improvements_successful_total", "Improvements that measured positive impact"
)

# Goal pursuit metrics
GOALS_PROPOSED_TOTAL = Counter(
    "kagami_goals_proposed_total",
    "Goals proposed by organism",
    ["type"],  # optimize_performance, improve_accuracy, etc
)

GOALS_COMPLETED_TOTAL = Counter(
    "kagami_goals_completed_total", "Goals successfully completed", ["type"]
)

GOAL_PURSUIT_DURATION_SECONDS = Histogram(
    "kagami_goal_pursuit_duration_seconds", "Time to complete goals", ["type"]
)

# ==============================================================================
# Unified Learning Coordinator Metrics
# ==============================================================================

LEARNING_BATCH_TRAINING_RUNS = Counter(
    "kagami_learning_batch_training_runs_total",
    "Total batch training cycles executed",
    registry=REGISTRY,
)

LEARNING_GENETIC_UPDATES = Counter(
    "kagami_learning_genetic_updates_total",
    "Total genetic memory updates",
    registry=REGISTRY,
)

LEARNING_POLICY_UPDATES = Counter(
    "kagami_learning_policy_updates_total",
    "Total policy updates",
    registry=REGISTRY,
)

LEARNING_COORDINATOR_LATENCY = Histogram(
    "kagami_learning_coordinator_latency_seconds",
    "Latency of online learning coordination",
    registry=REGISTRY,
)

__all__ = [
    "BELIEF_ENTROPY",
    "CAUSAL_INTERVENTIONS_TOTAL",
    "COORDINATION_LLM_USAGE_TOTAL",
    "CURRICULUM_LEVEL",
    "EPISTEMIC_VALUE",
    "EVOLUTION_CYCLES_TOTAL",
    "EVOLUTION_CYCLE_DURATION_SECONDS",
    "EVOLUTION_FITNESS_SCORE",
    "EVOLUTION_IMPROVEMENTS_APPLIED_TOTAL",
    "EVOLUTION_IMPROVEMENTS_PROPOSED_TOTAL",
    "EVOLUTION_IMPROVEMENTS_REJECTED_TOTAL",
    "EVOLUTION_IMPROVEMENTS_SUCCESSFUL_TOTAL",
    "FREE_ENERGY_SCORE",
    "GEOMETRIC_REASONING_CONFIDENCE",
    "GEOMETRIC_REASONING_QUERIES_TOTAL",
    "GOALS_COMPLETED_TOTAL",
    "GOALS_PROPOSED_TOTAL",
    "GOAL_PURSUIT_DURATION_SECONDS",
    "HYPERDIMENSIONAL_MANIFOLD_SEARCH_DURATION",
    "HYPERDIMENSIONAL_QUERY_RESULTS_TOTAL",
    "HYPERDIMENSIONAL_SEMANTIC_SEARCH_DURATION",
    "HYPERDIMENSIONAL_SUBSPACE_ACTIVATION",
    "HYPERDIMENSIONAL_THOUGHTS_TOTAL",
    "INSTINCT_EXPERIENCE_COUNT",
    "KOOPMAN_ALERTS_TOTAL",
    "KOOPMAN_DRIFT_SCORE",
    "LEARNING_AUTONOMOUS_GOALS_GENERATED",
    "LEARNING_AUTONOMOUS_GOALS_PURSUED",
    "LEARNING_BATCH_TRAINING_RUNS",
    "LEARNING_COORDINATOR_LATENCY",
    "LEARNING_GENETIC_UPDATES",
    "LEARNING_IMPROVEMENT_PERCENTAGE",
    "LEARNING_POLICY_UPDATES",
    "LEARNING_PREDICTION_ERROR_MS",
    "LEARNING_SLO_COMPLIANCE",
    "LEARNING_TRAINING_FREQUENCY_HZ",
    "LEARNING_VELOCITY",
    "LEARNING_WORLD_MODEL_UPDATES",
    "LORA_ACTIVE_MODEL_VERSION",
    "LORA_DEPLOYMENTS_TOTAL",
    "LORA_TRAINING_CYCLES_TOTAL",
    "LORA_TRAINING_DURATION_SECONDS",
    "LORA_TRAINING_EXAMPLES",
    "LORA_TRAINING_LOSS",
    "META_LEARNING_PATTERN_REUSE_TOTAL",
    "META_PREDICTOR_LOSS",
    "PRAGMATIC_VALUE",
    "RL_ACTION_SELECTION_TOTAL",
    "RL_WORLD_MODEL_ERROR",
    "SEMANTIC_FLOW_COLONY_FACTOR",
    "SEMANTIC_FLOW_KERNEL_COMPUTATIONS",
    "SEMANTIC_FLOW_MULTIPLIER",
    "SEMANTIC_SELF_KERNEL_SNAPSHOT",
    "TEMPORAL_LAYER_ACCURACY",
]

# Active Inference Metrics
BELIEF_ENTROPY = Gauge(
    "kagami_belief_entropy",
    "Belief Entropy",
)
EPISTEMIC_VALUE = Gauge(
    "kagami_epistemic_value",
    "Epistemic Value",
)
FREE_ENERGY_SCORE = Gauge(
    "kagami_free_energy_score",
    "Free Energy Score",
)
PRAGMATIC_VALUE = Gauge(
    "kagami_pragmatic_value",
    "Pragmatic Value",
)
TEMPORAL_LAYER_ACCURACY = Gauge(
    "kagami_temporal_layer_accuracy",
    "Temporal Layer Accuracy",
)

# Causal Interventions
CAUSAL_INTERVENTIONS_TOTAL = Counter(
    "kagami_causal_interventions_total",
    "Causal Interventions Total",
)

# Meta Learning
META_LEARNING_PATTERN_REUSE_TOTAL = Counter(
    "kagami_meta_learning_pattern_reuse_total",
    "Meta Learning Pattern Reuse Total",
)
META_PREDICTOR_LOSS = Gauge(
    "kagami_meta_predictor_loss",
    "Meta Predictor Loss",
)

# Instinct Experience
INSTINCT_EXPERIENCE_COUNT = Counter(
    "kagami_instinct_experience_count",
    "Instinct Experience Count",
)

__all__.extend(
    [
        "BELIEF_ENTROPY",
        "CAUSAL_INTERVENTIONS_TOTAL",
        "EPISTEMIC_VALUE",
        "FREE_ENERGY_SCORE",
        "INSTINCT_EXPERIENCE_COUNT",
        "META_LEARNING_PATTERN_REUSE_TOTAL",
        "META_PREDICTOR_LOSS",
        "PRAGMATIC_VALUE",
        "TEMPORAL_LAYER_ACCURACY",
    ]
)

# LoRA Metrics
LORA_TRAINING_CYCLES_TOTAL = Counter(
    "kagami_lora_training_cycles_total",
    "Total LoRA training cycles",
    ["status"],  # success, failed, skipped
)
LORA_TRAINING_DURATION_SECONDS = Histogram(
    "kagami_lora_training_duration_seconds",
    "LoRA training duration",
    buckets=[60, 300, 600, 1800, 3600],
)
LORA_TRAINING_LOSS = Gauge(
    "kagami_lora_training_loss",
    "Current LoRA training loss",
)
LORA_DEPLOYMENTS_TOTAL = Counter(
    "kagami_lora_deployments_total",
    "LoRA model deployments",
    ["status", "version"],
)
LORA_ACTIVE_MODEL_VERSION = Gauge(
    "kagami_lora_active_model_version",
    "Active LoRA model version (hash)",
)
LORA_TRAINING_EXAMPLES = Histogram(
    "kagami_lora_training_examples",
    "Number of training examples per cycle",
    buckets=[50, 100, 200, 500, 1000, 2000],
)

__all__.extend(
    [
        "LORA_ACTIVE_MODEL_VERSION",
        "LORA_DEPLOYMENTS_TOTAL",
        "LORA_TRAINING_CYCLES_TOTAL",
        "LORA_TRAINING_DURATION_SECONDS",
        "LORA_TRAINING_EXAMPLES",
        "LORA_TRAINING_LOSS",
    ]
)
