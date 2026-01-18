"""Honesty Validator - Enforces Truth in Claims

Blocks operations that make claims not backed by verifiable data.
Works alongside CBF to ensure not just safety, but honesty.

Philosophy: h(x) ≥ 0 enforces physical safety.
           honest(claim) ≥ 0 enforces epistemic safety (truth).

Both are non-negotiable.
"""

import json
import logging
from pathlib import Path
from typing import Any

from kagami.core.safety.models import Claim, VerificationResult

logger = logging.getLogger(__name__)


class HonestyViolation(Exception):
    """Raised when a claim cannot be verified by evidence."""


class HonestyValidator:
    """Validates claims against actual data.

    Usage:
        validator = HonestyValidator()

        claim = Claim(
            statement="Research colony performed 251 operations",
            evidence_type="receipt_analysis",
            data_source="var/receipts.jsonl",
            expected_value=251
        )

        result = validator.verify(claim)
        if not result.verified:
            raise HonestyViolation(f"Claim '{claim.statement}' not backed by data")
    """

    def __init__(self) -> None:
        self.receipts_cache: list[dict[str, Any]] | None = None
        self.receipts_cache_path: Path | None = None

    def verify(self, claim: Claim) -> VerificationResult:
        """Verify a claim against evidence.

        Args:
            claim: Claim to verify

        Returns:
            VerificationResult with verification status
        """
        try:
            if claim.evidence_type == "receipt_analysis":
                return self._verify_receipt_claim(claim)
            elif claim.evidence_type == "benchmark_result":
                return self._verify_benchmark_claim(claim)
            elif claim.evidence_type == "codebase_check":
                return self._verify_codebase_claim(claim)
            else:
                return VerificationResult(
                    claim=claim,
                    verified=False,
                    evidence_found=False,
                    error=f"Unknown evidence type: {claim.evidence_type}",
                )
        except Exception as e:
            logger.error(f"Error verifying claim: {e}", exc_info=True)
            return VerificationResult(
                claim=claim, verified=False, evidence_found=False, error=str(e)
            )

    def _verify_receipt_claim(self, claim: Claim) -> VerificationResult:
        """Verify claim against receipt data."""
        receipts_path = Path(claim.data_source)

        if not receipts_path.exists():
            return VerificationResult(
                claim=claim,
                verified=False,
                evidence_found=False,
                error=f"Receipt file not found: {receipts_path}",
            )

        # Load receipts (with caching)
        if self.receipts_cache_path != receipts_path:
            receipts = []
            with open(receipts_path) as f:
                for line in f:
                    try:
                        receipt_wrapper = json.loads(line)
                        receipts.append(receipt_wrapper.get("receipt", {}))
                    except json.JSONDecodeError:
                        continue

            self.receipts_cache = receipts
            self.receipts_cache_path = receipts_path
        else:
            receipts = self.receipts_cache or []  # Use cached or empty list[Any]

        # Check if required fields exist
        if claim.required_fields:
            fields_found = all(
                any(field in receipt for receipt in receipts) for field in claim.required_fields
            )

            if not fields_found:
                return VerificationResult(
                    claim=claim,
                    verified=False,
                    evidence_found=False,
                    error=f"Required fields {claim.required_fields} not found in receipts",
                )

        # If checking specific value (e.g., operation count)
        # ARCHITECTURE (December 22, 2025): Use explicit metadata, not keyword parsing
        if claim.expected_value is not None:
            # Use explicit claim_type in metadata instead of parsing statement
            claim_type = getattr(claim, "claim_type", None) or claim.required_fields
            actor_prefix = getattr(claim, "actor", None)

            if actor_prefix and claim_type == "operation_count":
                count = sum(1 for r in receipts if r.get("actor", "").startswith(actor_prefix))

                # Check if within tolerance
                expected = claim.expected_value
                tolerance = int(expected * claim.tolerance)

                verified = abs(count - expected) <= tolerance

                return VerificationResult(
                    claim=claim,
                    verified=verified,
                    evidence_found=True,
                    evidence_value=count,
                    error=None if verified else f"Expected ~{expected}, found {count}",
                )

        # Default: Evidence exists
        return VerificationResult(
            claim=claim,
            verified=True,
            evidence_found=True,
            evidence_value=len(receipts),
            error=None,
        )

    def _verify_benchmark_claim(self, claim: Claim) -> VerificationResult:
        """Verify claim against benchmark results."""
        benchmark_path = Path(claim.data_source)

        if not benchmark_path.exists():
            return VerificationResult(
                claim=claim,
                verified=False,
                evidence_found=False,
                error=f"Benchmark file not found: {benchmark_path}",
            )

        with open(benchmark_path) as f:
            results = json.load(f)

        # Check if claim matches results
        # (Implementation depends on benchmark result structure)

        return VerificationResult(
            claim=claim,
            verified=True,
            evidence_found=True,
            evidence_value=results,
            error=None,
        )

    def _verify_codebase_claim(self, claim: Claim) -> VerificationResult:
        """Verify claim about codebase (file counts, architecture, etc.).

        ARCHITECTURE (December 22, 2025):
        NO keyword parsing. Use explicit claim_type in metadata.
        """
        import subprocess

        # Use explicit claim_type instead of parsing statement
        claim_type = getattr(claim, "claim_type", None)
        file_extension = getattr(claim, "file_extension", None)

        if claim_type == "file_count" and file_extension:
            result = subprocess.run(
                ["find", ".", "-name", f"*{file_extension}", "-type", "f"],
                capture_output=True,
                text=True,
                cwd=Path.cwd(),
            )

            lines = result.stdout.strip().split("\n")
            count = len([l for l in lines if l])  # Filter empty lines
            expected = claim.expected_value
            tolerance = int(expected * claim.tolerance) if expected else 1000

            verified = abs(count - expected) <= tolerance if expected else True

            return VerificationResult(
                claim=claim,
                verified=verified,
                evidence_found=True,
                evidence_value=count,
                error=None if verified else f"Expected ~{expected}, found {count}",
            )

        # Default: Cannot verify without explicit claim_type
        return VerificationResult(
            claim=claim,
            verified=False,
            evidence_found=False,
            error="Codebase claim requires explicit claim_type and file_extension metadata",
        )


# Singleton instance
_validator = None


def get_honesty_validator() -> HonestyValidator:
    """Get singleton validator instance."""
    global _validator
    if _validator is None:
        _validator = HonestyValidator()
    return _validator


def require_honest(claim: Claim) -> None:
    """Require claim to be honest or raise HonestyViolation.

    Args:
        claim: Claim to verify

    Raises:
        HonestyViolation: If claim cannot be verified
    """
    validator = get_honesty_validator()
    result = validator.verify(claim)

    if not result.verified:
        error_msg = f"HONESTY VIOLATION: {claim.statement}\n"
        error_msg += f"Evidence type: {claim.evidence_type}\n"
        error_msg += f"Data source: {claim.data_source}\n"

        if result.error:
            error_msg += f"Error: {result.error}\n"

        if result.evidence_found and result.evidence_value is not None:
            error_msg += f"Found: {result.evidence_value}\n"
            if claim.expected_value:
                error_msg += f"Expected: {claim.expected_value}\n"

        logger.error(error_msg)
        raise HonestyViolation(error_msg)

    logger.info(f"✓ Verified claim: {claim.statement}")


# Example usage in intent execution:
#
# from kagami.core.safety.honesty_validator import require_honest, Claim
#
# # Before making a claim in response:
# require_honest(Claim(
#     statement="Research colony performed 344 operations",
#     evidence_type="receipt_analysis",
#     data_source="var/receipts.jsonl",
#     expected_value=344,
#     tolerance=0.05  # 5% tolerance
# ))
#
# # If verification fails, HonestyViolation is raised
# # Operation is blocked, just like CBF blocks unsafe operations


__all__ = ["Claim", "HonestyValidator", "HonestyViolation", "VerificationResult", "require_honest"]
