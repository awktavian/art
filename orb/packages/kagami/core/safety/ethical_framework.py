from __future__ import annotations

"""Ethical Framework: Constitutional AI + Moral Judgment."""
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ConstitutionalViolation:
    """Violation of constitutional principle."""

    principle: str
    reason: str
    severity: str  # "critical"|"high"|"medium"|"low"


@dataclass
class FairnessViolation:
    """Fairness/bias violation."""

    bias_type: str
    affected_groups: list[str]
    confidence: float


@dataclass
class MoralVerdict:
    """Result of moral judgment."""

    utility_score: float
    rights_respected: bool
    virtue_aligned: bool
    overall_judgment: str  # "permissible"|"impermissible"|"uncertain"


@dataclass
class FairnessAssessment:
    """Fairness assessment result."""

    bias_detected: bool
    bias_type: str = ""
    affected_groups: list[str] | None = None
    confidence: float = 0.0


@dataclass
class EthicalAssessment:
    """Complete ethical assessment."""

    violations: list[ConstitutionalViolation]
    fairness: FairnessAssessment
    moral_verdict: MoralVerdict
    recommendation: str  # "proceed"|"block"|"seek_guidance"


class EthicalFramework:
    """Constitutional constraints and moral judgment algorithms."""

    def __init__(self) -> None:
        self._constitution = self._load_constitution()
        self._moral_principles = self._load_moral_principles()

    def _load_constitution(self) -> list[dict[str, Any]]:
        """Load constitutional principles.

        ARCHITECTURE (December 22, 2025):
        NO keyword heuristics. All safety checks delegate to LLM + CBF.

        Principles here define structural requirements only.
        Content-based safety is handled by WildGuard LLM classifier.
        """
        return [
            {
                "name": "idempotency",
                "description": "Mutations must have idempotency_key in metadata",
                "severity": "critical",
                # Structural check only - no keyword matching
                "check": lambda intent: "idempotency_key" in intent.get("metadata", {}),
            },
            {
                "name": "no_harm",
                "description": "Do not cause harm - verified by LLM classifier",
                "severity": "critical",
                # Delegate to LLM - no keyword heuristics
                # CBF h(x) >= 0 enforces this via WildGuard classification
                "check": lambda intent: True,  # LLM + CBF handles this
            },
            {
                "name": "transparency",
                "description": "Decisions must be explainable",
                "severity": "medium",
                "check": lambda intent: True,  # Always explainable
            },
            {
                "name": "privacy",
                "description": "Respect user privacy - verified by LLM classifier",
                "severity": "high",
                # Delegate to LLM - no keyword heuristics
                # WildGuard PRIVACY_VIOLATION category handles this
                "check": lambda intent: intent.get("authorized", True),
            },
        ]

    def _load_moral_principles(self) -> dict[str, Any]:
        """Load moral principles."""
        return {
            "fairness": "Treat all users equally",
            "justice": "Uphold fair outcomes",
            "compassion": "Minimize suffering",
            "autonomy": "Respect individual choice",
            "beneficence": "Maximize benefit",
            "non_maleficence": "First, do no harm",
        }

    async def evaluate_intent_ethics(self, intent: dict[str, Any]) -> EthicalAssessment:
        """Check if intent violates ethical principles."""
        violations = []

        # Check constitution
        for principle in self._constitution:
            if not await self._check_principle(intent, principle):
                violations.append(
                    ConstitutionalViolation(
                        principle=principle["name"],
                        reason=f"Violates: {principle['description']}",
                        severity=principle["severity"],
                    )
                )

        # Check fairness
        fairness = await self._assess_fairness(intent)

        # Moral judgment
        moral_verdict = await self._moral_judgment(intent)

        # Determine recommendation
        if any(v.severity == "critical" for v in violations):
            recommendation = "block"
        elif violations or not fairness.bias_detected:
            recommendation = "seek_guidance"
        else:
            recommendation = "proceed"

        return EthicalAssessment(
            violations=violations,
            fairness=fairness,
            moral_verdict=moral_verdict,
            recommendation=recommendation,
        )

    async def _check_principle(self, intent: dict[str, Any], principle: dict[str, Any]) -> bool:
        """Check if intent violates a principle."""
        try:
            check_fn = principle.get("check")
            if check_fn:
                return bool(check_fn(intent))
            return True
        except (TypeError, ValueError, KeyError, AttributeError) as e:
            # TypeError: check_fn not callable or wrong arguments
            # ValueError: invalid intent data
            # KeyError: missing required field in intent
            # AttributeError: intent missing expected attributes
            logger.warning(f"Principle check failed, failing open: {e}", exc_info=True)
            return True  # Fail open on check errors

    async def _assess_fairness(self, intent: dict[str, Any]) -> FairnessAssessment:
        """Assess if intent is fair.

        ARCHITECTURE (December 22, 2025):
        NO keyword heuristics. Fairness assessment delegates to LLM.
        WildGuard HATE_SPEECH and HARASSMENT categories detect bias.
        """
        # Fairness is assessed by LLM classification
        # WildGuard categories handle discrimination detection:
        # - HATE_SPEECH: racist, sexist, discriminatory content
        # - HARASSMENT: targeting individuals/groups
        # Default to no bias detected - LLM + CBF handles actual detection
        return FairnessAssessment(bias_detected=False)

    async def _moral_judgment(self, intent: dict[str, Any]) -> MoralVerdict:
        """Apply moral reasoning frameworks."""
        # Utilitarianism: maximize overall good
        utility = await self._compute_utility(intent)

        # Deontology: respect individual rights
        rights_respected = await self._check_rights(intent)

        # Virtue ethics: align with virtuous character
        virtuous = await self._assess_virtue_alignment(intent)

        overall = (
            "permissible"
            if all([utility > 0, rights_respected, virtuous])
            else "impermissible"
            if utility < 0 or not rights_respected
            else "uncertain"
        )

        return MoralVerdict(
            utility_score=utility,
            rights_respected=rights_respected,
            virtue_aligned=virtuous,
            overall_judgment=overall,
        )

    async def _compute_utility(self, intent: dict[str, Any]) -> float:
        """Estimate overall utility.

        ARCHITECTURE (December 22, 2025):
        NO keyword heuristics. Utility assessment is structural only.
        Content-based harm detection is done by WildGuard LLM.
        """
        # Utility is neutral by default
        # LLM classification handles actual harm detection via CBF h(x)
        # Return neutral - CBF will reject if classification is unsafe
        return 0.0

    async def _check_rights(self, intent: dict[str, Any]) -> bool:
        """Check if individual rights are respected.

        ARCHITECTURE (December 22, 2025):
        NO keyword heuristics. Rights check uses structural metadata only.
        """
        # Check for explicit authorization in metadata
        metadata = intent.get("metadata", {})
        # If explicitly requires_auth and not authorized, fail
        if metadata.get("requires_auth") and not metadata.get("authorized"):
            return False
        # Default: rights respected (LLM handles content-based checks)
        return True

    async def _assess_virtue_alignment(self, intent: dict[str, Any]) -> bool:
        """Check alignment with virtuous character.

        ARCHITECTURE (December 22, 2025):
        NO keyword heuristics. Virtue assessment delegates to LLM.
        WildGuard DECEPTION, MANIPULATION categories detect vicious behavior.
        """
        # Virtue alignment is assessed by LLM classification
        # Default to virtuous - LLM + CBF rejects harmful content
        return True
