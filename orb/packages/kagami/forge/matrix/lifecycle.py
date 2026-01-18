"""Lifecycle and initialization logic for ForgeMatrix."""

from __future__ import annotations

import logging
from typing import Any

from kagami.forge.matrix.config import get_cache_root
from kagami.forge.matrix.loader import LRUFileCache
from kagami.forge.matrix.registry import ComponentRegistry

logger = logging.getLogger(__name__)


class LifecycleManager:
    """Manages initialization and lifecycle of ForgeMatrix components."""

    def __init__(self, registry: ComponentRegistry, event_recorder: Any) -> None:
        self.registry = registry
        self._event_recorder = event_recorder
        self.initialized = False
        self.asset_cache: LRUFileCache | None = None

    def initialize(self) -> None:
        """Initialize all subsystems."""
        if self.initialized:
            return

        # Initialize modules via registry
        self.registry.initialize_all(self._event_recorder)

        # Initialize cache
        cache_root = get_cache_root()
        if LRUFileCache:
            self.asset_cache = LRUFileCache(cache_root, max_items=256)

        self.initialized = True
        logger.info("ForgeMatrix lifecycle initialized")

    @property
    def import_errors(self) -> dict[str, Any]:
        return self.registry.import_errors
