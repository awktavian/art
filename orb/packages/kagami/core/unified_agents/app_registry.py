"""Canonical app/agent registry.

This replaces the legacy `kagami.apps_v2.registry` facade.

Public surface:
- Registry data: APP_REGISTRY_V2, APP_MATURITY, APP_METADATA
- Introspection: list_apps_v2()
- Routing helper: infer_app_from_action()
"""

from __future__ import annotations

from kagami.core.unified_agents.core_types import (
    ACTION_TO_APP_MAP,
    AGENT_PERSONALITIES,
    APP_MATURITY,
    APP_METADATA,
    APP_REGISTRY_V2,
    CANONICAL_AGENTS_REGISTRY,
)

__all__ = [
    "ACTION_TO_APP_MAP",
    "AGENT_PERSONALITIES",
    "APP_MATURITY",
    "APP_METADATA",
    "APP_REGISTRY_V2",
    "CANONICAL_AGENTS_REGISTRY",
    "infer_app_from_action",
    "list_apps_v2",
]


def list_apps_v2() -> dict[str, dict[str, object]]:
    """Return metadata for all registered apps/agents.

    Mirrors the historical API shape expected by API consumers/tests.
    """
    apps: dict[str, dict[str, object]] = {}

    for app_name, persona in AGENT_PERSONALITIES.items():
        if isinstance(persona, dict):  # type: ignore[unreachable]
            meta: dict[str, object] = dict(persona)  # type: ignore[unreachable]
        else:
            meta = {"personality": persona, "name": app_name}

        meta.setdefault("registry_id", CANONICAL_AGENTS_REGISTRY.get(app_name, app_name))
        meta.setdefault("maturity", APP_MATURITY.get(app_name, "experimental"))
        meta.setdefault("metadata", APP_METADATA.get(app_name, {}))
        apps[app_name] = meta

    # Historical convenience: include action lookup index.
    apps["_action_index"] = dict(ACTION_TO_APP_MAP)
    return apps


def infer_app_from_action(action: str | None) -> str | None:
    """Infer canonical app from an action string.

    This function is intentionally deterministic and lightweight; it is used in
    routing hot paths and in tests.
    """
    if not action:
        return None

    a = str(action).strip().lower()
    if not a:
        return None

    # Explicit namespace hints: "plans.*" / "files.*" etc.
    if a.startswith("plans.") or a.startswith("plan."):
        return "plans"
    if a.startswith("files.") or a.startswith("file."):
        return "files"
    if a.startswith("forge."):
        return "forge"
    if a.startswith("research."):
        # Historically accepted by callers; "research" is treated as files-adjacent.
        return "research"

    # Planner-like verbs.
    if any(a.startswith(p) for p in ("plan", "create_plan", "generate_tasks", "planner")):
        return "plans"

    # File-ish verbs.
    if a in {"upload", "search", "scan", "get_context", "find_related", "list[Any].files"}:
        return "files"

    # Fall back to verb-based mapping (create/build/fix/etc.).
    # Prefer prefix matching so "create.something" routes.
    for verb, app in ACTION_TO_APP_MAP.items():
        try:
            if a == verb or a.startswith(f"{verb}.") or a.startswith(f"{verb}_"):
                return app
        except Exception:
            continue

    return None
