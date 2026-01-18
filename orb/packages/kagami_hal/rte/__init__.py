"""鏡 Real-Time Executor (RTE) Subsystem.

The RTE provides deterministic timing guarantees for hardware I/O operations
that Linux cannot reliably perform. It is a pluggable backend for the HAL's
embedded adapters.

The HAL is the VM. The RTE is the Executor. The Protocol is the Bytecode.

Key Components:
- RTEBackend: Protocol for all RTE implementations
- RTECommand: Enum of supported commands
- PicoRTE: UART-based Pico coprocessor backend
- NativeRTE: Direct hardware access (Linux timing)
- VirtualRTE: Testing/simulation backend

Usage:
    from kagami_hal.rte import get_rte_backend, RTECommand

    # Auto-select best available backend
    rte = await get_rte_backend()

    # Send commands
    await rte.send_command(RTECommand.LED_PATTERN, 1)  # Breathing
    await rte.send_command(RTECommand.LED_BRIGHTNESS, 200)

    # Get status
    status = await rte.get_status()
    print(f"Pattern: {status.pattern}")

Architecture:
    SafeHAL (h(x) >= 0) → HAL Protocols → RTE Backend → Hardware

Safety:
    h(x) >= 0 is enforced by SafeHAL BEFORE commands reach RTE.
    RTE does not validate - it trusts upper layers.

Created: January 2, 2026
Colony: Nexus (e₄) — Bridge between realms
"""

from kagami_hal.rte.native import NativeRTE
from kagami_hal.rte.pico import PicoRTE
from kagami_hal.rte.protocol import (
    RTEBackend,
    RTECommand,
    RTEError,
    RTEResponse,
    encode_command,
    parse_response,
)
from kagami_hal.rte.types import (
    LEDPattern,
    RTEEvent,
    RTEEventType,
    RTEStatus,
)
from kagami_hal.rte.virtual import VirtualRTE


async def get_rte_backend(
    prefer_pico: bool = True,
    pico_port: str | None = None,
) -> RTEBackend:
    """Get the best available RTE backend.

    Attempts to connect to backends in order of preference:
    1. PicoRTE (if prefer_pico and available)
    2. NativeRTE (if hardware available)
    3. VirtualRTE (always available, for testing)

    Args:
        prefer_pico: Whether to prefer Pico over native
        pico_port: Specific port for Pico (auto-discover if None)

    Returns:
        Initialized RTE backend

    Example:
        >>> rte = await get_rte_backend()
        >>> await rte.send_command(RTECommand.LED_PATTERN, 1)
    """
    # Try Pico first
    if prefer_pico:
        try:
            pico = PicoRTE(pico_port)
            if await pico.initialize():
                return pico
        except Exception:
            pass

    # Try Native
    try:
        native = NativeRTE()
        if await native.initialize():
            return native
    except Exception:
        pass

    # Fall back to Virtual
    virtual = VirtualRTE()
    await virtual.initialize()
    return virtual


__all__ = [
    # Types
    "LEDPattern",
    "NativeRTE",
    # Backends
    "PicoRTE",
    # Protocol
    "RTEBackend",
    "RTECommand",
    "RTEError",
    "RTEEvent",
    "RTEEventType",
    "RTEResponse",
    "RTEStatus",
    "VirtualRTE",
    "encode_command",
    # Factory
    "get_rte_backend",
    "parse_response",
]
