"""Execution layer for SmartHome — Receipt-first action execution."""

from kagami_smarthome.execution.receipted_executor import (
    Action,
    ActionResult,
    ReceiptedExecutor,
    get_executor,
)

__all__ = [
    "Action",
    "ActionResult",
    "ReceiptedExecutor",
    "get_executor",
]
