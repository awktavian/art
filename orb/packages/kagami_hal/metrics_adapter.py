from __future__ import annotations

import logging
from typing import Any

# Import shared types to break circular dependency
from kagami_hal.types import HALStatus

HAL_ADAPTER_STATUS: Any = None
HAL_ERRORS: Any = None
HAL_INIT_SUCCESS: Any = None

try:
    from kagami.observability.metrics.hal import (
        HAL_ADAPTER_STATUS as _STATUS,
    )
    from kagami.observability.metrics.hal import (
        HAL_ERRORS as _ERRORS,
    )
    from kagami.observability.metrics.hal import (
        HAL_INIT_SUCCESS as _SUCCESS,
    )

    HAL_ADAPTER_STATUS = _STATUS
    HAL_ERRORS = _ERRORS
    HAL_INIT_SUCCESS = _SUCCESS
except Exception as exc:  # pragma: no cover - metrics optional in tests
    logging.getLogger(__name__).debug("HAL metrics unavailable: %s", exc)


def emit_hal_status(status: HALStatus) -> None:
    """Emit Gauges for current HAL adapter availability."""

    if HAL_ADAPTER_STATUS is None or HAL_INIT_SUCCESS is None:
        return

    platform = status.platform.value
    adapters = {
        "display": status.display_available,
        "audio": status.audio_available,
        "input": status.input_available,
        "sensors": status.sensors_available,
        "power": status.power_available,
    }

    for adapter_type, available in adapters.items():
        HAL_ADAPTER_STATUS.labels(platform=platform, adapter_type=adapter_type).set(
            1 if available else 0
        )
        HAL_INIT_SUCCESS.labels(platform=platform, adapter=adapter_type).set(1 if available else 0)

    if HAL_ERRORS is not None and status.adapters_failed:
        HAL_ERRORS.labels(
            platform=platform,
            adapter="aggregate",
            error_type="init_failed",
        ).inc(status.adapters_failed)


__all__ = ["emit_hal_status"]
