"""Worker Components - Extracted from GeometricWorker.

This package contains components extracted to reduce god class complexity:
- ProgramSelector: MDL-based program selection
- WorkerLifecycle: Hibernation, retirement, division
- CatastropheExecutor: Catastrophe-driven execution
- WorkerMetrics: Performance tracking

Created: December 21, 2025
"""

from kagami.core.unified_agents.worker.catastrophe_executor import CatastropheExecutor
from kagami.core.unified_agents.worker.lifecycle import WorkerLifecycle
from kagami.core.unified_agents.worker.metrics import WorkerMetrics
from kagami.core.unified_agents.worker.program_selector import ProgramSelector

__all__ = [
    "CatastropheExecutor",
    "ProgramSelector",
    "WorkerLifecycle",
    "WorkerMetrics",
]
