from __future__ import annotations

import json
import logging
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from uuid import uuid4

from kagami.forge.modules.world.provider_types import WorldGenerationResult

from .base import WorldGenerationProvider

logger = logging.getLogger(__name__)


class AgenticContextProvider(WorldGenerationProvider):
    """Synthetic provider that materializes structured spatial context locally."""

    name = "agentic"

    def __init__(self) -> None:
        base_dir = os.getenv(
            "AGENTIC_WORLD_CACHE",
            os.path.join(Path.home(), ".kagami_agentic_worlds"),
        )
        self.output_root = Path(base_dir)
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        try:
            self.output_root.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            logger.warning("Failed to create agentic cache directory: %s", exc)
        self._initialized = True

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
        world_id = uuid4().hex[:12]
        world_dir = self.output_root / world_id
        world_dir.mkdir(parents=True, exist_ok=True)

        plan = {}
        if extra:
            plan = dict(extra.get("virtual_action_plan") or {})

        scene_graph = {
            "world_id": world_id,
            "prompt": prompt,
            "mode": mode,
            "action_plan": plan,
        }
        (world_dir / "scene_graph.json").write_text(json.dumps(scene_graph, indent=2))

        panorama_path = world_dir / "panorama.txt"
        panorama_path.write_text(
            f"Agentic synthetic panorama for '{prompt or 'unspecified world'}' (mode={mode}).\n"
        )

        metadata = {
            "provider": self.name,
            "world_id": world_id,
            "scene_graph": str(panorama_path.with_name("scene_graph.json")),
        }

        return WorldGenerationResult(
            True,
            str(panorama_path),
            str(world_dir),
            None,
            metadata,
            provider=self.name,
        )
