from __future__ import annotations

import abc
from collections.abc import Mapping
from typing import Any

from kagami.forge.modules.world.provider_types import WorldGenerationResult


class WorldGenerationProvider(abc.ABC):
    """Abstract base class for world generation providers."""

    name: str = "provider"

    async def initialize(self) -> None:
        """Providers may override to load heavy resources lazily."""
        return None

    @abc.abstractmethod
    async def generate(
        self,
        *,
        prompt: str | None,
        image_path: str | None,
        mode: str,
        wait: bool,
        timeout: float | None,
        extra: Mapping[str, Any] | None = None,
    ) -> WorldGenerationResult:
        """Generate a world or return a structured error."""
