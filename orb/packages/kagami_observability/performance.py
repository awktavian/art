from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass


@dataclass
class PerformanceTimer:
    name: str
    start: float | None = None
    elapsed_ms: float | None = None

    def __enter__(self) -> PerformanceTimer:
        self.start = time.perf_counter()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self.start is not None:
            self.elapsed_ms = (time.perf_counter() - self.start) * 1000.0


@contextmanager
def monitor_performance(name: str) -> Iterator[PerformanceTimer]:
    t = PerformanceTimer(name=name)
    with t:
        yield t
