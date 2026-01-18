from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class Claim:
    """Normalized definition of a claim requiring verification."""

    statement: str
    evidence_type: str
    data_source: str
    required_fields: list[str] | None = None
    expected_value: Any = None
    tolerance: float = 0.1


@dataclass(slots=True)
class VerificationResult:
    """Common result payload for honesty/safety verifiers."""

    claim: Claim
    verified: bool
    evidence_found: bool
    confidence: float = 0.0
    evidence_value: Any = None
    error: str | None = None


__all__ = ["Claim", "VerificationResult"]
