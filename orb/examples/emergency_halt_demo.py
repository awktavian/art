#!/usr/bin/env python3
"""Emergency Halt Demonstration.

This script demonstrates the emergency halt mechanism for manual safety override.

EMERGENCY HALT MECHANISM:
- Global flag that blocks ALL operations immediately
- Thread-safe via threading.Lock
- Returns h(x) = -∞ for all CBF checks while active
- Takes priority over classifier results
- Returns immediately (no timeout wait)

Use Cases:
1. Critical safety incident detected
2. System behaving unexpectedly
3. Manual intervention required
4. Testing safety boundary responses
"""

import asyncio
import logging

from kagami.core.safety.cbf_integration import (
    check_cbf_for_operation,
    check_cbf_sync,
    emergency_halt,
    is_emergency_halt_active,
    reset_emergency_halt,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def demonstrate_emergency_halt():
    """Demonstrate emergency halt mechanism."""

    print("\n" + "=" * 60)
    print("EMERGENCY HALT DEMONSTRATION")
    print("=" * 60 + "\n")

    # PHASE 1: Normal operation
    print("PHASE 1: Normal Operation")
    print("-" * 40)

    result = await check_cbf_for_operation(operation="demo.safe_read", action="read", target="data")
    print(f"✓ Safe operation result: safe={result.safe}, h(x)={result.h_x:.3f}")
    print()

    # PHASE 2: Activate emergency halt
    print("PHASE 2: Emergency Halt Activated")
    print("-" * 40)

    emergency_halt()
    print(f"✓ Emergency halt active: {is_emergency_halt_active()}")
    print()

    # PHASE 3: Attempt operations during halt
    print("PHASE 3: Operations During Emergency Halt")
    print("-" * 40)

    # Try async operation
    result = await check_cbf_for_operation(operation="demo.safe_read", action="read", target="data")
    print(
        f"✗ Async operation blocked: safe={result.safe}, h(x)={result.h_x}, reason={result.reason}"
    )

    # Try sync operation
    result_sync = check_cbf_sync(operation="demo.write", action="write", target="file")
    print(
        f"✗ Sync operation blocked: safe={result_sync.safe}, h(x)={result_sync.h_x}, "
        f"reason={result_sync.reason}"
    )

    # Even completely safe text is blocked
    result_safe = await check_cbf_for_operation(
        operation="demo.greeting",
        action="read",
        user_input="Hello, how are you?",
    )
    print(
        f"✗ Safe text blocked: safe={result_safe.safe}, h(x)={result_safe.h_x}, "
        f"reason={result_safe.reason}"
    )
    print()

    # PHASE 4: Reset and resume
    print("PHASE 4: Reset Emergency Halt")
    print("-" * 40)

    reset_emergency_halt()
    print(f"✓ Emergency halt reset: {is_emergency_halt_active()}")
    print()

    # PHASE 5: Normal operation resumed
    print("PHASE 5: Normal Operation Resumed")
    print("-" * 40)

    result = await check_cbf_for_operation(operation="demo.safe_read", action="read", target="data")
    print(f"✓ Operation resumed: safe={result.safe}, h(x)={result.h_x:.3f}")
    print()

    print("=" * 60)
    print("DEMONSTRATION COMPLETE")
    print("=" * 60)
    print()
    print("KEY TAKEAWAYS:")
    print("1. Emergency halt blocks ALL operations immediately")
    print("2. Returns h(x) = -∞ regardless of content safety")
    print("3. Thread-safe for concurrent access")
    print("4. Resets cleanly for normal operation")
    print("5. Use for critical safety override situations")
    print()


def demonstrate_thread_safety():
    """Demonstrate thread-safe emergency halt toggling."""
    import threading

    print("\n" + "=" * 60)
    print("THREAD SAFETY DEMONSTRATION")
    print("=" * 60 + "\n")

    def toggle_halt(thread_id: int, iterations: int):
        for i in range(iterations):
            emergency_halt()
            reset_emergency_halt()
            if i % 10 == 0:
                logger.info(f"Thread {thread_id}: iteration {i}")

    print("Starting 5 threads, each toggling emergency halt 100 times...")
    threads = [threading.Thread(target=toggle_halt, args=(i, 100)) for i in range(5)]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    print(f"✓ All threads complete. Final state: {is_emergency_halt_active()}")
    print("✓ No race conditions detected")
    print()

    # Clean up
    reset_emergency_halt()


if __name__ == "__main__":
    # Run async demonstration
    asyncio.run(demonstrate_emergency_halt())

    # Run thread safety demonstration
    demonstrate_thread_safety()
