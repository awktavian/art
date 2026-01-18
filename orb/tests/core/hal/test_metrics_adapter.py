from __future__ import annotations


from typing import Any

from types import SimpleNamespace

from kagami_hal import metrics_adapter
from kagami_hal.manager import HALStatus, Platform
from kagami_hal.metrics_adapter import emit_hal_status


class DummyGauge:
    def __init__(self) -> None:
        self.calls: list[tuple[dict, float]] = []

    class _Child:
        def __init__(self, parent: DummyGauge, labels: dict) -> None:
            self._parent = parent
            self._labels = labels

        def set(self, value: float) -> None:
            self._parent.calls.append((self._labels, value))

    def labels(self, **labels):
        return DummyGauge._Child(self, labels)


class DummyCounter(DummyGauge):
    class _Child(DummyGauge._Child):
        def inc(self, value: float = 1.0) -> None:
            self._parent.calls.append((self._labels, value))

    def labels(self, **labels):
        return DummyCounter._Child(self, labels)


def test_emit_hal_status_updates_metrics(monkeypatch) -> None:
    status = HALStatus(
        platform=Platform.LINUX,
        display_available=True,
        audio_available=False,
        input_available=True,
        sensors_available=False,
        power_available=True,
        mock_mode=False,
        adapters_initialized=3,
        adapters_failed=2,
    )

    status_metric = DummyGauge()
    success_metric = DummyGauge()
    error_metric = DummyCounter()

    monkeypatch.setattr(metrics_adapter, "HAL_ADAPTER_STATUS", status_metric)
    monkeypatch.setattr(metrics_adapter, "HAL_INIT_SUCCESS", success_metric)
    monkeypatch.setattr(metrics_adapter, "HAL_ERRORS", error_metric)

    emit_hal_status(status)

    label_sets = [labels for labels, _ in status_metric.calls]
    assert {"platform": "linux", "adapter_type": "audio"} in label_sets
    assert any(labels["adapter"] == "aggregate" for labels, _ in error_metric.calls)
