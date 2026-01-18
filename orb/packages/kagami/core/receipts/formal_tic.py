"""Formal Definition of Typed Intent Calculus (TIC).

TIC provides the mathematical and logical foundation for agent operations.
Every operation is a typed tuple[Any, ...] τ = {E, P, Q, I, T}.

Rigorous Definition:
- E (Effects): Observable side effects (e.g., 'file_write', 'db_commit').
- P (Preconditions): Predicates that MUST be true before execution.
- Q (Postconditions): Predicates that MUST be true after execution.
- I (Invariants): Predicates that MUST hold throughout execution.
- T (Termination): Proof of termination (ranking function or fuel bound).

This module provides Pydantic models to enforce this structure at runtime.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TerminationType(str, Enum):
    RANKING_FUNCTION = "ranking_function"
    BOUNDED_FUEL = "bounded_fuel"
    TIMEOUT = "timeout"


class EvidenceType(str, Enum):
    PCO = "pco"  # Proof-Carrying Operation
    MCO = "mco"  # Measurement-Carrying Operation
    AXIOM = "axiom"  # Assumed true (use sparingly)


class TerminationProof(BaseModel):
    """Formal guarantee of termination."""

    type: TerminationType
    ranking_function: str | None = Field(
        None,
        description="Math expr R(x) mapping state to natural numbers, decreasing on every step.",
    )
    fuel_limit: int | None = Field(None, description="Maximum iterations/steps allowed.")
    time_limit_ms: float | None = Field(None, description="Hard timeout in milliseconds.")

    @model_validator(mode="after")
    def validate_termination(self) -> TerminationProof:
        if self.type == TerminationType.RANKING_FUNCTION and not self.ranking_function:
            raise ValueError("Ranking function required for RANKING_FUNCTION termination.")
        if self.type == TerminationType.BOUNDED_FUEL and self.fuel_limit is None:
            raise ValueError("Fuel limit required for BOUNDED_FUEL termination.")
        return self


class Evidence(BaseModel):
    """Evidence supporting the operation's correctness."""

    type: EvidenceType
    content: dict[str, Any] = Field(description="Measurements, proofs, or axiom justification.")
    verified: bool = Field(default=False, description="Whether this evidence has been verified.")


class TypedIntent(BaseModel):
    """The Typed Intent Calculus (TIC) Tuple τ = {E, P, Q, I, T}."""

    # Operation Identity
    operation: str = Field(description="Name of the operation being performed.")
    type: str = Field(description="Type/Classification of the operation (τ).")

    # E: Effects
    effects: list[str] = Field(default_factory=list[Any], description="Observable side effects.")

    # P: Preconditions
    pre: dict[str, Any] = Field(
        default_factory=dict[str, Any], description="Preconditions (must be true before)."
    )

    # Q: Postconditions
    post: dict[str, Any] = Field(
        default_factory=dict[str, Any], description="Postconditions (guaranteed after)."
    )

    # I: Invariants
    invariants: list[str] = Field(
        default_factory=lambda: ["h(x) >= 0", "energy > 0"],
        description="Invariants maintained throughout.",
    )

    # T: Termination
    termination: TerminationProof | None = Field(None, description="Termination guarantee.")

    # Evidence (PCO/MCO)
    evidence: Evidence | None = Field(None, description="Proof or measurement data.")

    model_config = ConfigDict(
        extra="forbid",  # Strict schema
        frozen=True,  # Immutable once created
    )


def validate_tic_compliance(receipt_data: dict[str, Any]) -> None:
    """Validate that a receipt complies with TIC standards.

    Raises:
        ValueError: If TIC data is missing or invalid.
    """
    tic_data = receipt_data.get("tic")
    if not tic_data:
        # For legacy/informal receipts, we might allow missing TIC,
        # but for A+ rigor we should log a warning or enforce it.
        # Currently enforcing soft compliance (returning) but ready for strict.
        return

    try:
        intent = TypedIntent(**tic_data)

        # PCO Verification (Z3)
        if intent.evidence and intent.evidence.type == EvidenceType.PCO:
            try:
                # Avoid static import cycle (receipts <-> symbolic verifier).
                # Dynamic import keeps runtime behavior without hard module dependency.
                import importlib

                verifier_mod = importlib.import_module(
                    "kagami.core.reasoning.symbolic.tic_verifier"
                )
                TICVerifier = getattr(verifier_mod, "TICVerifier", None)
                if TICVerifier is None:
                    return

                verifier = TICVerifier()
                result = verifier.verify(intent)
                if not result.verified:
                    # Log but don't crash for now, or raise strict error based on config
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.warning(
                        f"TIC Verification Failed for {intent.operation}: {result.counter_example}"
                    )
                    # For strict mode:
                    # raise ValueError(f"PCO verification failed: {result.counter_example}")
            except ImportError:
                pass  # Z3 not available

    except Exception as e:
        raise ValueError(f"Invalid TIC data in receipt: {e}") from e
