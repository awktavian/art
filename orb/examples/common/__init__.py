"""Common utilities for Kagami examples.

This module provides shared infrastructure for all examples:
- output: Rich terminal output, progress bars, formatting
- metrics: Timing, memory, throughput measurement
- export: JSON, CSV export utilities
"""

from common.output import (
    print_header,
    print_section,
    print_success,
    print_error,
    print_metrics,
    print_footer,
    print_separator,
)
from common.metrics import (
    Timer,
    MemoryTracker,
    MetricsCollector,
    measure_throughput,
)
from common.export import (
    export_json,
    export_csv,
    export_metrics,
)

__all__ = [
    "MemoryTracker",
    "MetricsCollector",
    # Metrics
    "Timer",
    "export_csv",
    # Export
    "export_json",
    "export_metrics",
    "measure_throughput",
    "print_error",
    "print_footer",
    # Output
    "print_header",
    "print_metrics",
    "print_section",
    "print_separator",
    "print_success",
]
