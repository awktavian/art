"""K os Kernel Layer - Core OS Services.

Provides foundational OS services for ambient computing:
- Fast syscall interface (replaces HTTP overhead)
- Preemptive agent scheduling
- Interrupt handling
- Power management
- Memory management

Created: November 10, 2025
Purpose: Bridge intelligence layer with hardware
"""

from kagami.core.kernel.scheduler import (
    PreemptiveAgentScheduler,
    Priority,
    get_scheduler,
    schedule_agent,
)
from kagami.core.kernel.syscalls import (
    KagamiOSSyscall,
    register_syscall,
    syscall_handler,
)

__all__ = [
    # Syscalls
    "KagamiOSSyscall",
    "PreemptiveAgentScheduler",
    # Scheduler
    "Priority",
    "get_scheduler",
    "register_syscall",
    "schedule_agent",
    "syscall_handler",
]
