from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from kagami.core.services.world.emu_world_service import get_emu_world_service
from kagami.forge.modules.world.provider_types import WorldGenerationResult

from .base import WorldGenerationProvider

logger = logging.getLogger(__name__)


class EmuWorldProvider(WorldGenerationProvider):
    """Primary Emu3.5-based world generation provider."""

    name = "emu"

    def __init__(self) -> None:
        self._service = None
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._service = get_emu_world_service()  # type: ignore[assignment]
        await self._service.initialize()  # type: ignore[attr-defined]
        self._initialized = True
        logger.info("✅ EmuWorldProvider initialized")

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
        await self.initialize()
        if self._service is None:
            return WorldGenerationResult(
                False,
                None,
                None,
                "emu_service_unavailable",
                {"provider": self.name},
                provider=self.name,
            )

        job_id = await self._service.generate_world(  # type: ignore[unreachable]
            prompt=prompt or "A peaceful world",
            image_path=image_path,
            mode=mode,
            wait=wait,
            timeout=timeout,
        )

        if not wait:
            return WorldGenerationResult(
                True,
                None,
                None,
                None,
                {"job_id": job_id, "provider": self.name},
                provider=self.name,
            )

        result = await self._service.get_result(job_id)

        # Check for timeout (result is None if job timed out/still running)
        if result is None:
            return WorldGenerationResult(
                False,
                None,
                None,
                f"Timeout waiting for Emu3.5 generation (job {job_id})",
                {"job_id": job_id, "provider": self.name},
                provider=self.name,
            )

        if result and result.success:
            metadata = result.metadata or {}
            metadata.setdefault("provider", self.name)
            narrative = getattr(result, "narrative_data", None)
            if narrative and "narrative" not in metadata:
                metadata["narrative"] = narrative
            return WorldGenerationResult(
                True,
                result.panorama_path,
                result.world_output_dir,
                None,
                metadata,
                provider=self.name,
            )

        error_message = result.error if result else "Unknown error"
        return WorldGenerationResult(
            False,
            None,
            None,
            error_message,
            {"provider": self.name},
            provider=self.name,
        )
