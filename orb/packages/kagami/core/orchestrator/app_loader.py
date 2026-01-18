"""Canonical orchestrator app loader.

This replaces the legacy `kagami.core.orchestrator.app_shim` layer.

The orchestrator needs *something* that behaves like an "app" object with an
async `process_intent` method. For now we keep it intentionally small and
deterministic to satisfy routing contracts and tests without carrying legacy
AppV2/Fractal adapter logic.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class SimpleApp:
    """Minimal app interface used by IntentOrchestrator."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.app_type = "agent"
        self.description = ""
        self.features: dict[str, Any] = {}
        self.status = type("Status", (), {"value": "ready"})()
        self._initialized = True

    async def initialize(self) -> None:  # pragma: no cover (simple)
        self._initialized = True

    async def cleanup(self) -> None:  # pragma: no cover (simple)
        return None

    async def stop_background(self) -> None:  # pragma: no cover (simple)
        """Best-effort hook for control routes."""
        return None

    def get_capabilities(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.app_type,
            "description": self.description,
            "features": self.features,
        }

    async def process_intent(self, intent: Any) -> dict[str, Any]:
        """Process a wrapped intent.

        The orchestrator wraps dict[str, Any] intents into `_IntentEnvelope` and passes them
        here. We keep the result shape stable for tests: status + echo fields.
        """
        action = str(getattr(intent, "action", "") or "")
        params = getattr(intent, "target", None)
        metadata = getattr(intent, "metadata", None)
        try:
            app_hint = str(getattr(intent, "app", "") or self.name)
        except Exception:
            app_hint = self.name

        return {
            "status": "accepted",
            "app": app_hint,
            "action": action,
            "params": params if isinstance(params, dict) else {"value": params},
            "metadata": metadata if isinstance(metadata, dict) else {},
        }

    async def process_intent_v2(
        self, intent: Any, _sections: dict[str, Any], _suggestions: dict[str, Any]
    ) -> dict[str, Any]:
        return await self.process_intent(intent)


def get_app_class(app_name: str) -> type[SimpleApp]:
    """Return an app class for a given app key."""

    name = (app_name or "").strip().lower() or "app"

    class _NamedApp(SimpleApp):
        def __init__(self) -> None:
            super().__init__(name=name)

    _NamedApp.__name__ = f"App_{name}"
    return _NamedApp


__all__ = ["SimpleApp", "get_app_class"]
