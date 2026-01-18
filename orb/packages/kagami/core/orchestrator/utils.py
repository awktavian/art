from __future__ import annotations

"""K os Central Orchestrator with A+ Production Systems Wiring.

Main orchestrator that coordinates all intents with 7 production systems integrated:
1. Ethical Instinct (jailbreak detection)
2. Prediction Instinct (outcome forecasting)
3. Learning Instinct (valence-weighted learning)
4. Threat Instinct (harm avoidance)
5. PrioritizedReplay (experience storage)
6. IntrospectionEngine (decision explanation)
7. JEPA World Model (state prediction)

Provides async intent routing to V2 apps with production systems coordination.

Enhanced with self-aware agent operations tracking:
- Phase tracking (PERCEIVE→MODEL→SIMULATE→ACT→VERIFY→CONVERGE)
- Loop depth and convergence detection
- Strategy declaration and selection
- Novelty tracking for search operations
- Production systems integration for all operations
"""
import logging
from dataclasses import dataclass
from typing import Any, cast

logger = logging.getLogger(__name__)


@dataclass
class _IntentEnvelope:
    """Lightweight object wrapper for dict[str, Any] intents used by tests.

    Apps expect attribute access like `intent.metadata` and sometimes `intent.target`.
    """

    action: str | None
    app: str | None
    metadata: dict[str, Any]
    target: Any | None = None


def _normalize_app_name(name: str | None) -> str | None:
    if not name:
        return None
    key = name.strip().lower()
    aliases: dict[str, str] = {
        "penny finance": "penny",
        "spark analytics": "spark",
        "luna marketing": "luna",
        "echo collaboration": "echo",
        "harmony v2": "harmony",
        "plans": "plans",
        "files": "files",
        "forge": "forge",
        "spark": "spark",
        "luna": "luna",
        "echo": "echo",
        "harmony": "harmony",
        "penny": "penny",
    }
    return aliases.get(key, key)


def _infer_app_from_action(action: str | None) -> str | None:
    """Infer app from action using registry configuration.

    This is now a thin wrapper around the registry's inference logic,
    removing hardcoded mappings from the orchestrator for better maintainability.
    """
    from kagami.core.unified_agents.app_registry import infer_app_from_action

    return cast(str | None, infer_app_from_action(action))  # type: ignore[redundant-cast]
