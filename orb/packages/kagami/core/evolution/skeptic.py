"""Skeptic Agent - Critical Reviewer for Evolution Proposals.

This agent acts as the "Devil's Advocate" in the evolutionary loop.
It reviews proposed code changes and configuration updates with a critical eye,
looking for:
1. Safety violations (even if they pass formal checks)
2. Long-term risks (technical debt, complexity)
3. Alignment violations (drift from core values)
4. Evidence gaps (unproven claims)

The Skeptic does NOT have write access; it only approves or rejects (with reasons).
"""

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SkepticReview:
    """Result of a skeptic review."""

    approved: bool
    concerns: list[str]
    risk_score: float  # 0.0 (safe) to 1.0 (dangerous)
    confidence: float  # 0.0 to 1.0


class SkepticReviewer:
    """The Skeptic Agent implementation."""

    def __init__(self, strictness: float = 0.7) -> None:
        """Initialize the skeptic.

        Args:
            strictness: How strict to be (0.0-1.0). Higher = more rejections.
        """
        self.strictness = strictness

    async def review_proposal(self, proposal: dict[str, Any]) -> SkepticReview:
        """Review a proposed change.

        Args:
            proposal: Dictionary containing proposal details (rationale, code, etc.)

        Returns:
            SkepticReview object
        """
        # 1. Extract features
        rationale = str(proposal.get("rationale", "")).lower()
        risk_level = str(proposal.get("risk_level", "low")).lower()
        file_path = str(proposal.get("file_path", ""))

        concerns = []
        risk_score = 0.1  # Baseline risk

        # 2. Heuristic Checks (System 1)

        # Check for dangerous keywords in rationale
        danger_signals = [
            "disable safety",
            "bypass",
            "force",
            "delete all",
            "rewrite core",
            "experimental",
            "untested",
        ]
        for signal in danger_signals:
            if signal in rationale:
                concerns.append(f"High-risk signal detected: '{signal}'")
                risk_score += 0.3

        # Check for evidence gaps
        if "evidence" not in proposal and "benchmark" not in rationale:
            if risk_level in ["medium", "high"]:
                concerns.append("Missing evidence/benchmarks for medium/high risk change")
                risk_score += 0.2

        # Check scope creep (touching too many core files)
        if "core/safety" in file_path or "core/security" in file_path:
            risk_score += 0.2
            concerns.append("Modifies critical safety/security infrastructure")

        # 3. Logic/Reasoning (System 2 - Simulated)
        # In a full implementation, this would call an LLM with a "Critic" persona.
        # For now, we implement the "Pre-computation" logic.

        if risk_level == "high":
            risk_score += 0.3
        elif risk_level == "medium":
            risk_score += 0.1

        # 4. Decision
        approved = True

        # Strictness check
        # If strictness is high (0.7), we reject if risk > 0.3 (1.0 - 0.7)
        threshold = 1.0 - self.strictness

        if risk_score > threshold:
            approved = False
            if not concerns:
                concerns.append(
                    f"Risk score {risk_score:.2f} exceeds strictness threshold {threshold:.2f}"
                )

        # Log decision
        status = "APPROVED" if approved else "REJECTED"
        logger.info(f"Skeptic {status} proposal: risk={risk_score:.2f}, concerns={len(concerns)}")

        # Compute confidence based on concern severity and coverage
        if not concerns:
            confidence = 0.95  # High confidence when no concerns
        else:
            # More concerns = lower confidence
            concern_penalty = min(len(concerns) * 0.1, 0.4)
            confidence = 0.9 - concern_penalty

        return SkepticReview(
            approved=approved,
            concerns=concerns,
            risk_score=risk_score,
            confidence=confidence,
        )
