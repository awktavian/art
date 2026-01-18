"""Unified Safety System - Control Barrier Functions + LLM Classification.

ARCHITECTURE (December 22, 2025):
=================================
Single unified safety system with tiered caching:
1. Exact hash cache (~0.01ms)
2. Embedding centroid cache (~5ms)
3. Full WildGuard LLM inference (~900ms)

CANONICAL ENTRY POINT:
======================
    from kagami.core.safety import check_safety, warmup_safety

    # Warmup at startup
    await warmup_safety()

    # Check any operation
    result = await check_safety(
        text="user query",
        operation="api_request",
    )

SAFETY GUARANTEE:
=================
- ALL paths use full LLM intelligence (no keyword heuristics)
- Only SAFE results are cached
- h(x) >= 0 invariant enforced at all levels
"""

import logging
import os
from pathlib import Path

# get_cbf_filter removed - use get_safety_filter directly
# Configuration and constants
# Users should import from the unified config:
#   from kagami.core.config.unified_config import SafetyConfig
# Training integration
# Embedding cache (semantic similarity)
from typing import TYPE_CHECKING, Any, Optional

# Advanced CBF components (December 27, 2025)
from kagami.core.safety.cbf_advanced import (
    CBFQP,
    ActuatorFaultConfig,
    FaultTolerantNCBF,
    SpectralNormalizedBarrier,
    create_cbf_qp,
    create_fault_tolerant_cbf,
    create_spectral_cbf,
)

# Decorators for safety enforcement
from kagami.core.safety.cbf_decorators import (
    CBFRequiredViolation,
    CBFViolation,
    cbf_required,
    enforce_cbf,
    enforce_cbf_timed,
    enforce_tier1,
    enforce_tier2,
    enforce_tier3,
    monitor_cbf,
)

# Initialization and verification
from kagami.core.safety.cbf_init import (
    get_social_cbf,
    initialize_cbf_system,
    initialize_social_cbf,
    verify_cbf_system,
)
from kagami.core.safety.cbf_integration import (
    check_cbf_for_operation,
    get_safety_filter,
)
from kagami.core.safety.cbf_loss import (
    CBFCombinedLoss,
    CBFMSELoss,
    CBFReLULoss,
    create_cbf_loss,
)
from kagami.core.safety.cbf_monitor import CBFMonitor
from kagami.core.safety.cbf_registry import CBFRegistry
from kagami.core.safety.control_barrier_function import extract_safety_state

# Ethical framework
from kagami.core.safety.ethical_framework import (
    ConstitutionalViolation,
    EthicalAssessment,
    EthicalFramework,
    FairnessAssessment,
    MoralVerdict,
)

# Composition and advanced features
from kagami.core.safety.fano_cbf_composition import FanoCompositionChecker

# Safety messages (unified, consistent messaging)
from kagami.core.safety.messages import (
    SafetyContext,
    SafetyMessage,
    SafetyMessageFormatter,
    SafetyViolationType,
    format_safety_message,
    format_safety_quick,
    get_safety_explanation,
)

# Core CBF classes
from kagami.core.safety.optimal_cbf import (
    DifferentiableQPSolver,
    DynamicsEnsemble,
    HighOrderCBF,
    LipschitzRegularizer,
    OptimalCBF,
    OptimalCBFConfig,
    get_optimal_cbf,
)
from kagami.core.safety.organism_barriers import OrganismBarriers

# Safety cache (LLM results only - no heuristics)
from kagami.core.safety.safety_cache import (
    SafetyClassificationCache,
    get_safety_cache,
)

# Social CBF (December 2025 - Symbiote Module)
from kagami.core.safety.social_cbf import (
    SocialCBF,
    SocialSafetyCheck,
    SocialViolationType,
    create_social_cbf,
    integrate_social_cbf,
)

# Unified safety system (CANONICAL ENTRY POINT)
from kagami.core.safety.unified_safety import (
    check_safety,
    check_safety_batch,
    get_safety_metrics,
    warmup_safety,
)

if TYPE_CHECKING:
    from kagami.core.safety.embedding_cache import (
        EmbeddingCentroidCache,
        get_embedding_cache,
    )
else:
    try:
        from kagami.core.safety.embedding_cache import (
            EmbeddingCentroidCache,
            get_embedding_cache,
        )

        _EMBEDDING_AVAILABLE = True
    except ImportError:
        _EMBEDDING_AVAILABLE = False
        EmbeddingCentroidCache: Any = None
        get_embedding_cache: Any = None

# Formal Verification (December 24, 2025 - LBP-based)
from kagami.core.safety.formal_verification import (
    NeuralCBFVerifier,
    VerificationConfig,
    VerificationResult,
    VerificationStatus,
    create_verified_cbf,
    verify_optimal_cbf,
)

# Safety Zones (December 27, 2025 - Zone-aware API)
from kagami.core.safety.safety_zones import (
    CAUTION_THRESHOLD,
    OPTIMAL_THRESHOLD,
    SAFETY_BUFFER,
    OODRisk,
    SafetyZone,
    ZoneAwareSafetyResult,
    assess_ood_risk,
    check_epistemic_safety,
    classify_h_value,
    get_routing_hints_for_zone,
)

__all__ = [
    "CAUTION_THRESHOLD",
    "CBFQP",
    "OPTIMAL_THRESHOLD",
    "SAFETY_BUFFER",
    "ActuatorFaultConfig",
    "CBFCombinedLoss",
    "CBFMSELoss",
    "CBFMonitor",
    # Training
    "CBFReLULoss",
    "CBFRegistry",
    "CBFRequiredViolation",
    # Decorators
    "CBFViolation",
    "ConstitutionalViolation",
    "DifferentiableQPSolver",
    "DynamicsEnsemble",
    # Embedding cache
    "EmbeddingCentroidCache",
    "EthicalAssessment",
    # Ethical
    "EthicalFramework",
    "FairnessAssessment",
    # Advanced
    "FanoCompositionChecker",
    "FaultTolerantNCBF",
    "HighOrderCBF",
    "LipschitzRegularizer",
    "MoralVerdict",
    "NeuralCBFVerifier",
    "OODRisk",
    # Core CBF classes
    "OptimalCBF",
    "OptimalCBFConfig",
    "OrganismBarriers",
    # Safety cache (LLM results only)
    "SafetyClassificationCache",
    # Safety Messages (December 31, 2025)
    "SafetyContext",
    "SafetyMessage",
    "SafetyMessageFormatter",
    "SafetyViolationType",
    # Safety Zones (December 27, 2025)
    "SafetyZone",
    # Social CBF (Symbiote)
    "SocialCBF",
    "SocialSafetyCheck",
    "SocialViolationType",
    # Advanced CBF (December 27, 2025)
    "SpectralNormalizedBarrier",
    "VerificationConfig",
    "VerificationResult",
    # Formal Verification (LBP-based)
    "VerificationStatus",
    "ZoneAwareSafetyResult",
    "assess_ood_risk",
    "cbf_required",
    "check_cbf_for_operation",
    "check_epistemic_safety",
    # Unified safety (CANONICAL - use these)
    "check_safety",
    "check_safety_batch",
    "classify_h_value",
    # Audit logging
    "configure_audit_logging",
    "create_cbf_loss",
    "create_cbf_qp",
    "create_fault_tolerant_cbf",
    "create_social_cbf",
    "create_spectral_cbf",
    "create_verified_cbf",
    "enforce_cbf",
    "enforce_cbf_timed",
    "enforce_tier1",
    "enforce_tier2",
    "enforce_tier3",
    "extract_safety_state",
    "format_safety_message",
    "format_safety_quick",
    "get_embedding_cache",
    "get_optimal_cbf",
    "get_routing_hints_for_zone",
    "get_safety_cache",
    "get_safety_explanation",
    "get_safety_filter",
    "get_safety_metrics",
    "get_social_cbf",
    # Initialization
    "initialize_cbf_system",
    "initialize_social_cbf",
    "integrate_social_cbf",
    "monitor_cbf",
    "verify_cbf_system",
    "verify_optimal_cbf",
    "warmup_safety",
]


# =============================================================================
# AUDIT LOGGING CONFIGURATION
# =============================================================================


def configure_audit_logging(
    log_file: str | None = None,
    log_level: int = logging.WARNING,
    json_format: bool = True,
) -> None:
    """Configure audit logging for CBF enforcement bypass events.

    This function sets up a dedicated audit logger for security-sensitive
    CBF enforcement events, particularly bypass operations via
    cbf_enforcement_disabled() context manager.

    Args:
        log_file: Path to audit log file. Defaults to "logs/cbf_audit.log".
                 Parent directory will be created if it doesn't exist.
        log_level: Logging level. Defaults to WARNING (captures bypass events).
        json_format: If True, use JSON-structured logging for machine parsing.
                    If False, use human-readable format.

    Usage:
        # Configure at application startup
        from kagami.core.safety import configure_audit_logging
        configure_audit_logging(log_file="logs/cbf_audit.log")

        # Then use context manager with reason
        from kagami.core.safety.universal_cbf_enforcer import cbf_enforcement_disabled
        with cbf_enforcement_disabled(reason="controlled_exploration"):
            # Bypass event is logged to audit log
            unsafe_operation()

    Audit Log Events:
        - CBF_ENFORCEMENT_DISABLED: When enforcement is bypassed
        - CBF_ENFORCEMENT_RESTORED: When enforcement is restored

    Audit Log Fields:
        - timestamp: ISO 8601 UTC timestamp
        - event: Event name (CBF_ENFORCEMENT_DISABLED, etc.)
        - reason: Justification provided by caller
        - stack_trace: Last 5 stack frames (for bypass events)
        - thread_id: Thread identifier
    """
    # Default log file path
    if log_file is None:
        log_file = "logs/cbf_audit.log"

    # Ensure parent directory exists
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Get the audit logger
    audit_logger = logging.getLogger("kagami.security.audit")
    audit_logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates
    audit_logger.handlers.clear()

    # Create file handler
    handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")

    # Configure formatter
    if json_format:
        # JSON format for machine parsing
        # Use a custom formatter that properly serializes the extra dict[str, Any]
        import json as json_module

        class JSONFormatter(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:
                log_data = {
                    "timestamp": self.formatTime(record, self.datefmt),
                    "level": record.levelname,
                    "event": record.getMessage(),
                    "context": {
                        k: v
                        for k, v in record.__dict__.items()
                        if k not in logging.LogRecord("", 0, "", 0, "", (), None).__dict__
                    },
                }
                return json_module.dumps(log_data)

        formatter: logging.Formatter = JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S%z")
    else:
        # Human-readable format
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s - %(reason)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    handler.setFormatter(formatter)
    audit_logger.addHandler(handler)

    # Prevent propagation to root logger
    audit_logger.propagate = False

    logging.info(f"✅ CBF audit logging configured: {log_file}")
