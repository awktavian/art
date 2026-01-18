from __future__ import annotations

"""Forge World Generation Module - Emu3.5 PRIMARY.

Emu3.5 is the ONLY world generation provider:
- World exploration (multi-step sequences, spatially consistent)
- Visual narrative (interleaved story + images)
- Any-to-Image (X2I editing)
- Superior text rendering (EN + ZH + formulas)
- 20× faster with DiDA acceleration
- Beats Gemini 2.5 Flash (65.5% win on world exploration)

No fallback providers. Emu3.5 or error (fail-fast).
"""
import logging
import os
import time
from typing import Any

from kagami.core.config import get_bool_config
from kagami.forge.modules.world.provider_types import WorldGenerationResult
from kagami.forge.modules.world.providers import (
    AgenticContextProvider,
    EmuWorldProvider,
    LatticeWorldProvider,
    WorldGenerationProvider,
)
from kagami_observability.metrics.forge import (
    WORLD_PROVIDER_GENERATIONS,
    WORLD_PROVIDER_LATENCY_MS,
)

logger = logging.getLogger(__name__)


class WorldGenerationModule:
    """Forge world generation with pluggable providers.

    Providers:
    - ``emu`` (default): Emu3.5 world exploration
    - ``latticeworld``: UE5 orchestration bridge (remote)
    - ``agentic``: Synthetic Agentic 3D context exporter
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        self.enabled = get_bool_config("WORLD_GEN_ENABLED", True)
        self.initialized = False
        self.providers: dict[str, WorldGenerationProvider] = {}
        env_provider = os.getenv("WORLD_GEN_PROVIDER")
        self.default_provider = (
            (self.config.get("provider") or env_provider or "emu").strip().lower()
        )
        self.register_provider(EmuWorldProvider())
        self.register_provider(LatticeWorldProvider())
        self.register_provider(AgenticContextProvider())

    async def initialize(self) -> None:
        if self.initialized:
            return
        if not self.enabled:
            logger.info("WorldGenerationModule disabled via env")
            self.initialized = True
            return

        provider = self.providers.get(self.default_provider)
        if provider is None:
            raise RuntimeError(f"Unknown world generation provider '{self.default_provider}'")
        await provider.initialize()
        logger.info(
            "✅ WorldGenerationModule initialized (default provider=%s)", self.default_provider
        )
        self.initialized = True

    def register_provider(self, provider: WorldGenerationProvider) -> None:
        """Register a provider instance."""

        self.providers[provider.name] = provider

    def list_providers(self) -> list[str]:
        """Return available provider names."""

        return sorted(self.providers.keys())

    async def generate(
        self,
        *,
        prompt: str | None = None,
        image_path: str | None = None,
        mode: str = "world_exploration",  # world_exploration, visual_narrative, x2i
        provider: str | None = None,
        wait: bool = True,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> WorldGenerationResult:
        """Generate a world using the requested provider.

        Args:
            prompt: Text description of world
            image_path: Optional reference image
            mode: Generation mode (world_exploration, visual_narrative, x2i)
            provider: Provider name (defaults to configured provider)
            wait: Wait for completion
            timeout: Max wait time

        Returns:
            WorldGenerationResult with paths to generated assets
        """
        if not self.initialized:
            await self.initialize()
        if not self.enabled:
            raise RuntimeError("World generation disabled")
        provider_name = (
            provider or kwargs.pop("provider_name", None) or self.default_provider
        ).lower()
        provider_instance = self.providers.get(provider_name)
        if provider_instance is None:
            raise ValueError(f"Unknown world generation provider '{provider_name}'")

        await provider_instance.initialize()
        started = time.perf_counter()
        result = await provider_instance.generate(
            prompt=prompt,
            image_path=image_path,
            mode=mode,
            wait=wait,
            timeout=timeout,
            extra=kwargs,
        )
        duration_ms = (time.perf_counter() - started) * 1000
        try:
            WORLD_PROVIDER_LATENCY_MS.labels(provider=provider_instance.name).observe(duration_ms)
            WORLD_PROVIDER_GENERATIONS.labels(
                provider=provider_instance.name,
                status="success" if result.success else "error",
            ).inc()
        except Exception:
            pass

        if result.metadata is None:
            result.metadata = {}
        result.metadata.setdefault("provider", provider_instance.name)
        result.provider = provider_instance.name

        plan_payload = kwargs.get("virtual_action_plan")
        if isinstance(plan_payload, dict):
            try:
                from kagami.core.self_improvement.embodied_loop import (
                    get_embodied_self_improvement_loop,
                )

                loop = get_embodied_self_improvement_loop()
                loop.record_session(plan_payload, result)
            except Exception as exc:  # pragma: no cover - metrics only
                logger.debug("Failed to record embodied session: %s", exc)

        return result
