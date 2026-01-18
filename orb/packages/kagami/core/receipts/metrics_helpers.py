"""Receipt metrics helpers.

Provides lightweight metric updates for receipt emission tracking.
Gracefully degrades if metrics infrastructure is unavailable.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def update_all_receipt_metrics(receipt: dict[str, Any], phase: str, status: str) -> None:
    """Update Prometheus metrics for receipt.

    Gracefully handles cases where metrics are unavailable (e.g., during testing).
    """
    try:
        # Canonical counter used by Grafana dashboard:
        # monitoring/grafana/dashboards/receipt_flow_dashboard.json
        from kagami_observability.metrics.receipts import KAGAMI_RECEIPTS_TOTAL

        # NOTE: This counter is intentionally low-cardinality (phase only).
        # Status is tracked elsewhere (and should not be added to this metric name).
        KAGAMI_RECEIPTS_TOTAL.labels(phase=str(phase).upper()).inc()
    except ImportError:
        # Metrics not installed - acceptable during minimal deployments
        pass
    except Exception as e:
        # Don't let metrics failures disrupt receipt emission
        logger.debug(f"Metrics update failed: {e}")
