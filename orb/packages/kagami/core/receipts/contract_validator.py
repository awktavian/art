"""Receipt contract validation.

Validates receipts against the contract defined in monitoring/receipts_contract.json.
Ensures all required fields are present and valid.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Cache the contract
_CONTRACT: dict[str, Any] | None = None


def _load_contract() -> dict[str, Any]:
    """Load receipt contract from monitoring/receipts_contract.json."""
    global _CONTRACT

    if _CONTRACT is not None:
        return _CONTRACT

    try:
        # Find contract file
        contract_path = (
            Path(__file__).parent.parent.parent.parent / "monitoring" / "receipts_contract.json"
        )

        if not contract_path.exists():
            logger.warning(f"Receipt contract not found at {contract_path}")
            return {"required_fields": [], "phases": [], "recommended_fields": []}

        with open(contract_path) as f:
            _CONTRACT = json.load(f)

        return _CONTRACT

    except Exception as e:
        logger.warning(f"Failed to load receipt contract: {e}")
        return {"required_fields": [], "phases": [], "recommended_fields": []}


def validate_receipt_contract(receipt: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate receipt against contract.

    Args:
        receipt: Receipt dict[str, Any] to validate

    Returns:
        Tuple of (is_valid, missing_fields)
    """
    contract = _load_contract()
    required_fields = contract.get("required_fields", [])

    missing = []
    for field in required_fields:
        if field not in receipt or receipt[field] is None:
            missing.append(field)

    is_valid = len(missing) == 0

    # Emit metric for contract violations
    if not is_valid:
        try:
            from kagami_observability.metrics.receipts import RECEIPT_WRITE_ERRORS_TOTAL

            RECEIPT_WRITE_ERRORS_TOTAL.labels(error_type="contract_violation").inc()
        except Exception:
            pass

        logger.warning(f"Receipt contract violation: missing {missing}")

    return is_valid, missing


def check_recommended_fields(receipt: dict[str, Any]) -> list[str]:
    """Check for recommended fields that are missing.

    Args:
        receipt: Receipt dict[str, Any] to check

    Returns:
        List of missing recommended fields
    """
    contract = _load_contract()
    recommended_fields = contract.get("recommended_fields", [])

    missing = []
    for field in recommended_fields:
        if field not in receipt or receipt[field] is None:
            missing.append(field)

    if missing:
        logger.debug(f"Receipt missing recommended fields: {missing}")

    return missing


def validate_phase(receipt: dict[str, Any]) -> bool:
    """Validate receipt phase is one of the allowed values.

    Args:
        receipt: Receipt dict[str, Any] to validate

    Returns:
        True if phase is valid
    """
    contract = _load_contract()
    allowed_phases = contract.get("phases", ["PLAN", "EXECUTE", "VERIFY"])

    phase = receipt.get("phase")
    if phase is None:
        return False

    phase_upper = str(phase).upper()
    if phase_upper not in allowed_phases:
        logger.warning(f"Invalid receipt phase: {phase} (expected one of {allowed_phases})")
        try:
            from kagami_observability.metrics.receipts import RECEIPT_WRITE_ERRORS_TOTAL

            RECEIPT_WRITE_ERRORS_TOTAL.labels(error_type="invalid_phase").inc()
        except Exception:
            pass
        return False

    return True


__all__ = [
    "check_recommended_fields",
    "validate_phase",
    "validate_receipt_contract",
]
