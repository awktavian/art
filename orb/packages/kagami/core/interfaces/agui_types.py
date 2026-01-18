from __future__ import annotations

"""Core AGUI protocol types.

Why this exists:
- `kagami.core.*` must not import `kagami_api.*` (breaks layering and creates cycles).
- Some core subsystems (e.g. Markov blanket) still need to *speak* in AGUI-shaped
  messages, without depending on the API implementation.

This module provides:
- `AGUIMessage`: the canonical message payload (Pydantic model) used by
  `kagami_api.protocols.agui.AGUIProtocolAdapter.send_message(...)`.
- `AGUIProtocolAdapter`: a Protocol describing the *minimum* interface core needs.

Created: Dec 13, 2025
"""

from typing import Any, Protocol

from pydantic import BaseModel, Field


class AGUIMessage(BaseModel):
    """AG-UI message format for agent responses."""

    role: str = Field(..., description="Message role (agent/user/system)")
    content: str | None = Field(None, description="Text content")
    ui: dict[str, Any] | None = Field(None, description="UI descriptor for generative UI")
    tools: list[dict[str, Any]] | None = Field(None, description="Tool calls made")
    metadata: dict[str, Any] = Field(default_factory=dict[str, Any])


class AGUIProtocolAdapter(Protocol):
    """Minimal adapter interface core needs for sending AGUI messages."""

    async def send_message(self, message: AGUIMessage, stream: bool = False) -> str: ...


__all__ = ["AGUIMessage", "AGUIProtocolAdapter"]
