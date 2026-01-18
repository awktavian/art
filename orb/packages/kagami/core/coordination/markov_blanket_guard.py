"""Markov Blanket Guard - Enforce Discipline in Consensus.

ARCHITECTURAL PRINCIPLE:
=======================
Markov blanket discipline is INVIOLABLE:
    η (external) → s (sensory) → μ (internal) → a (active) → η

CRITICAL INVARIANTS:
====================
1. Internal state μ is HIDDEN from all external observers
2. Consensus can ONLY access:
   - Sensory state (z-state from RSSM)
   - Action proposals (but not direct action execution)
3. No colony can modify another colony's internal state
4. Actions flow through active state (never bypass to direct η modification)

INTEGRATION:
============
Used by KagamiConsensus to validate proposals before aggregation.
Prevents Markov blanket violations at the coordination layer.

Created: December 15, 2025
"""

# Standard library imports
import ast
import inspect
import logging
from dataclasses import (
    dataclass,
    field,
)
from enum import Enum
from typing import Any

# Third-party imports
from prometheus_client import Counter

# Local imports
from kagami.core.exceptions import SafetyError

logger = logging.getLogger(__name__)

# =============================================================================
# METRICS
# =============================================================================

markov_blanket_checks_total = Counter(
    "markov_blanket_checks_total",
    "Total number of Markov blanket validation checks",
    ["validation_type"],
)

markov_blanket_violations_total = Counter(
    "markov_blanket_violations_total",
    "Total number of Markov blanket violations detected",
    ["violation_type", "colony_id"],
)

# =============================================================================
# VIOLATION TYPES
# =============================================================================


class ViolationType(Enum):
    """Types of Markov blanket violations."""

    # Accessing internal state μ (FORBIDDEN)
    INTERNAL_ACCESS = "internal_access"

    # Directly modifying neighbor colony state (FORBIDDEN)
    NEIGHBOR_MODIFY = "neighbor_modify"

    # Bypassing active state to modify external η (FORBIDDEN)
    BYPASS_ACTIVE = "bypass_active"

    # Accessing private attributes (suspicious)
    PRIVATE_ACCESS = "private_access"

    # Creating circular references (suspicious)
    CIRCULAR_REFERENCE = "circular_reference"


# =============================================================================
# EXCEPTIONS
# =============================================================================


class MarkovBlanketViolation(SafetyError):
    """Raised when Markov blanket discipline violated.

    This is a SafetyError because Markov blanket violations compromise
    the fundamental architectural invariants of the system.
    """

    error_code = "MARKOV_BLANKET_VIOLATION"

    def __init__(
        self,
        violation_type: ViolationType,
        colony_id: int,
        details: str,
        *,
        context: dict[str, Any] | None = None,
    ):
        """Initialize Markov blanket violation.

        Args:
            violation_type: Type of violation
            colony_id: Which colony violated the discipline
            details: Human-readable description
            context: Additional diagnostic context
        """
        self.violation_type = violation_type
        self.colony_id = colony_id
        self.details = details

        message = (
            f"Markov blanket violation ({violation_type.value}) in colony {colony_id}: {details}"
        )

        super().__init__(message, context=context)

        # Emit metric
        markov_blanket_violations_total.labels(
            violation_type=violation_type.value,
            colony_id=str(colony_id),
        ).inc()


# =============================================================================
# VALIDATION STATE
# =============================================================================


@dataclass
class ValidationResult:
    """Result of Markov blanket validation."""

    valid: bool
    violations: list[dict[str, Any]] = field(default_factory=list[Any])
    warnings: list[str] = field(default_factory=list[Any])

    def add_violation(
        self,
        violation_type: ViolationType,
        colony_id: int,
        details: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Add a violation to the result."""
        self.valid = False
        self.violations.append(
            {
                "type": violation_type,
                "colony_id": colony_id,
                "details": details,
                "context": context or {},
            }
        )

    def add_warning(self, message: str) -> None:
        """Add a warning to the result."""
        self.warnings.append(message)


# =============================================================================
# MARKOV BLANKET GUARD
# =============================================================================


class MarkovBlanketGuard:
    """Enforce Markov blanket discipline in consensus proposals.

    VALIDATION STRATEGY:
    ====================
    1. Static analysis: Check proposal structure for forbidden patterns
    2. Runtime checks: Validate proposal data at execution time
    3. AST inspection: Optionally analyze proposal generation code

    USAGE:
    ======
    ```python
    guard = MarkovBlanketGuard()

    # Validate proposal
    try:
        guard.validate_proposal(proposal)
    except MarkovBlanketViolation as e:
        logger.error(f"Proposal rejected: {e}")
    ```
    """

    # Forbidden attributes that indicate internal state access
    FORBIDDEN_INTERNAL_ATTRS = {
        "_internal_state",
        "_mu",
        "_hidden_state",
        "_private_state",
        "internal_",  # Prefix
        "_colony_internal",
    }

    # Forbidden methods that modify external state
    FORBIDDEN_MODIFY_METHODS = {
        "set_state",
        "modify_colony",
        "update_neighbor",
        "write_external",
        "direct_modify",
    }

    # Allowed sensory attributes (safe to access)
    ALLOWED_SENSORY_ATTRS = {
        "z_state",
        "sensory_state",
        "observation",
        "obs",
        "stochastic",  # z in RSSM
    }

    # Allowed action attributes (safe to propose)
    ALLOWED_ACTION_ATTRS = {
        "target_colonies",
        "action_proposal",
        "routing_decision",
        "confidence",
        "cbf_margin",
    }

    def __init__(
        self,
        strict_mode: bool = True,
        enable_ast_analysis: bool = False,
    ):
        """Initialize Markov blanket guard.

        Args:
            strict_mode: If True, raise on any violation. If False, log warnings.
            enable_ast_analysis: Enable AST inspection of proposal code (expensive)
        """
        self.strict_mode = strict_mode
        self.enable_ast_analysis = enable_ast_analysis

        logger.info(
            f"MarkovBlanketGuard initialized (strict={strict_mode}, ast={enable_ast_analysis})"
        )

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def validate_proposal(
        self,
        proposal: Any,  # CoordinationProposal
    ) -> ValidationResult:
        """Validate proposal respects Markov blanket discipline.

        CHECKS:
        =======
        1. Proposal only references sensory state (z_state), not internal (μ)
        2. Proposal doesn't modify neighbor colony state
        3. Actions flow through active state (not direct η modification)

        Args:
            proposal: CoordinationProposal to validate

        Returns:
            ValidationResult with violations (if any)

        Raises:
            MarkovBlanketViolation: If strict_mode and violations found
        """
        markov_blanket_checks_total.labels(validation_type="proposal").inc()

        result = ValidationResult(valid=True)

        # Run validation checks
        self._check_internal_access(proposal, result)
        self._check_neighbor_modification(proposal, result)
        self._check_active_bypass(proposal, result)
        self._check_private_attributes(proposal, result)

        # Optional: AST analysis
        if self.enable_ast_analysis:
            self._check_proposal_generation_code(proposal, result)

        # In strict mode, raise on first violation
        if not result.valid and self.strict_mode:
            violation = result.violations[0]
            raise MarkovBlanketViolation(
                violation_type=violation["type"],
                colony_id=violation["colony_id"],
                details=violation["details"],
                context=violation["context"],
            )

        # Log warnings
        for warning in result.warnings:
            logger.warning(f"Markov blanket warning: {warning}")

        return result

    def validate_state_access(
        self,
        colony_id: int,
        accessed_attributes: set[str],
    ) -> ValidationResult:
        """Validate colony only accesses allowed state attributes.

        Args:
            colony_id: Which colony is accessing state
            accessed_attributes: Set of attribute names accessed

        Returns:
            ValidationResult
        """
        markov_blanket_checks_total.labels(validation_type="state_access").inc()

        result = ValidationResult(valid=True)

        # Check for forbidden internal attributes
        forbidden = accessed_attributes & self.FORBIDDEN_INTERNAL_ATTRS
        if forbidden:
            result.add_violation(
                violation_type=ViolationType.INTERNAL_ACCESS,
                colony_id=colony_id,
                details=f"Accessed forbidden internal attributes: {forbidden}",
                context={"attributes": list(forbidden)},
            )

        # Check for private attribute access (warning only)
        private_attrs = {a for a in accessed_attributes if a.startswith("_")}
        private_attrs = private_attrs - self.FORBIDDEN_INTERNAL_ATTRS
        if private_attrs:
            result.add_warning(f"Colony {colony_id} accessed private attributes: {private_attrs}")

        return result

    # =========================================================================
    # INTERNAL VALIDATION CHECKS
    # =========================================================================

    def _check_internal_access(
        self,
        proposal: Any,
        result: ValidationResult,
    ) -> None:
        """Check proposal doesn't access internal state μ.

        ALLOWED: proposal.z_state, proposal.stochastic (sensory)
        FORBIDDEN: proposal._internal_state, proposal._mu (internal)
        """
        # Get all attributes accessed in proposal
        accessed = self._extract_accessed_attributes(proposal)

        # Check for forbidden internal attributes
        forbidden = accessed & self.FORBIDDEN_INTERNAL_ATTRS
        if forbidden:
            result.add_violation(
                violation_type=ViolationType.INTERNAL_ACCESS,
                colony_id=proposal.proposer.value if hasattr(proposal, "proposer") else -1,
                details=f"Proposal references forbidden internal state: {forbidden}",
                context={"attributes": list(forbidden)},
            )

    def _check_neighbor_modification(
        self,
        proposal: Any,
        result: ValidationResult,
    ) -> None:
        """Check proposal doesn't modify neighbor colony state.

        Proposals can only suggest actions for other colonies,
        not directly modify their state.
        """
        # Check task_decomposition (allowed - this is action suggestion)
        if hasattr(proposal, "task_decomposition"):
            decomp = proposal.task_decomposition
            if isinstance(decomp, dict):
                # This is OK - proposing subtasks for other colonies
                pass

        # Check for forbidden modification methods
        if hasattr(proposal, "__dict__"):
            for attr_name in proposal.__dict__.keys():
                if any(m in attr_name.lower() for m in ["modify", "set_state", "update"]):
                    # Suspicious - might be trying to modify state
                    result.add_warning(f"Proposal has suspicious attribute: {attr_name}")

    def _check_active_bypass(
        self,
        proposal: Any,
        result: ValidationResult,
    ) -> None:
        """Check actions flow through active state.

        Actions should be proposals (a_state), not direct external modifications.
        """
        # Check for direct external modification
        if hasattr(proposal, "direct_action"):
            result.add_violation(
                violation_type=ViolationType.BYPASS_ACTIVE,
                colony_id=proposal.proposer.value if hasattr(proposal, "proposer") else -1,
                details="Proposal attempts to bypass active state with direct_action",
            )

        # Check for external η modification
        if hasattr(proposal, "modify_external") or hasattr(proposal, "write_η"):
            result.add_violation(
                violation_type=ViolationType.BYPASS_ACTIVE,
                colony_id=proposal.proposer.value if hasattr(proposal, "proposer") else -1,
                details="Proposal attempts to directly modify external state η",
            )

    def _check_private_attributes(
        self,
        proposal: Any,
        result: ValidationResult,
    ) -> None:
        """Check for suspicious private attribute access."""
        if not hasattr(proposal, "__dict__"):
            return

        private_attrs = {k for k in proposal.__dict__.keys() if k.startswith("_")}
        # Filter out known safe private attributes
        safe_private = {"_fields", "_field_defaults"}  # dataclass internals
        suspicious = private_attrs - safe_private

        if suspicious:
            result.add_warning(f"Proposal has private attributes: {suspicious}")

    def _check_proposal_generation_code(
        self,
        proposal: Any,
        result: ValidationResult,
    ) -> None:
        """Static analysis of proposal generation code via AST inspection.

        EXPENSIVE: Only enable if needed for deep validation.
        """
        try:
            # Get the function that created this proposal
            frame = inspect.currentframe()
            if frame and frame.f_back and frame.f_back.f_back:
                caller_frame = frame.f_back.f_back
                caller_code = caller_frame.f_code
                source = inspect.getsource(caller_code)

                # Parse AST
                tree = ast.parse(source)

                # Check for forbidden patterns
                visitor = MarkovBlanketVisitor()
                visitor.visit(tree)

                if visitor.violations:
                    for violation in visitor.violations:
                        result.add_warning(f"AST analysis: {violation}")

        except Exception as e:
            logger.debug(f"AST analysis failed: {e}")
            # Not critical - continue without AST analysis

    # =========================================================================
    # UTILITIES
    # =========================================================================

    def _extract_accessed_attributes(self, obj: Any, visited: set[int] | None = None) -> set[str]:
        """Extract all attributes accessed in an object.

        Args:
            obj: Object to inspect
            visited: Set of object IDs already visited (for cycle detection)

        Returns:
            Set of attribute names
        """
        accessed = set()  # type: ignore[var-annotated]

        if not hasattr(obj, "__dict__"):
            return accessed

        # Track visited objects to prevent cycles
        if visited is None:
            visited = set()

        obj_id = id(obj)
        if obj_id in visited:
            return accessed  # Already processed

        visited.add(obj_id)

        for key, value in obj.__dict__.items():
            accessed.add(key)

            # Recursively check nested objects (with cycle detection)
            if hasattr(value, "__dict__") and not isinstance(value, type):
                accessed.update(self._extract_accessed_attributes(value, visited))

        return accessed


# =============================================================================
# AST VISITOR (for optional static analysis)
# =============================================================================


class MarkovBlanketVisitor(ast.NodeVisitor):
    """AST visitor to detect Markov blanket violations in code."""

    def __init__(self) -> None:
        self.violations: list[str] = []

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """Check attribute access for violations."""
        attr_name = node.attr

        # Check for forbidden internal state access
        if attr_name.startswith("_internal") or attr_name == "_mu":
            self.violations.append(f"Forbidden internal state access: {attr_name}")

        # Check for direct external modification
        if attr_name in {"modify_external", "write_η", "set_state"}:
            self.violations.append(f"Forbidden external modification: {attr_name}")

        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Check function calls for violations."""
        if isinstance(node.func, ast.Attribute):
            method_name = node.func.attr

            # Check for forbidden modification methods
            if method_name in {"set_state", "modify_colony", "update_neighbor"}:
                self.violations.append(f"Forbidden modification method: {method_name}")

        self.generic_visit(node)


# =============================================================================
# FACTORY
# =============================================================================


def create_markov_blanket_guard(
    strict_mode: bool = True,
    enable_ast_analysis: bool = False,
) -> MarkovBlanketGuard:
    """Create Markov blanket guard.

    Args:
        strict_mode: Raise on violations (True) or log warnings (False)
        enable_ast_analysis: Enable AST code inspection (expensive)

    Returns:
        MarkovBlanketGuard instance
    """
    return MarkovBlanketGuard(
        strict_mode=strict_mode,
        enable_ast_analysis=enable_ast_analysis,
    )


__all__ = [
    "MarkovBlanketGuard",
    "MarkovBlanketViolation",
    "ValidationResult",
    "ViolationType",
    "create_markov_blanket_guard",
]
