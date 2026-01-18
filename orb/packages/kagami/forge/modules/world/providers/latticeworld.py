from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from typing import Any

from kagami.forge.modules.world.provider_types import WorldGenerationResult

from .base import WorldGenerationProvider

logger = logging.getLogger(__name__)


class LatticeWorldProvider(WorldGenerationProvider):
    """Provider that forwards requests to a LatticeWorld UE5 orchestration service."""

    name = "latticeworld"

    def __init__(self) -> None:
        self.api_url = os.getenv("LATTICEWORLD_API_URL")
        self.api_key = os.getenv("LATTICEWORLD_API_KEY")
        self._http_error_logged = False

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
        if not self.api_url:
            return WorldGenerationResult(
                False,
                None,
                None,
                "latticeworld_api_unconfigured",
                {"provider": self.name},
                provider=self.name,
            )

        try:
            import httpx
        except Exception as exc:
            if not self._http_error_logged:
                logger.warning("httpx not available for LatticeWorld provider: %s", exc)
                self._http_error_logged = True
            return WorldGenerationResult(
                False,
                None,
                None,
                "httpx_missing",
                {"provider": self.name},
                provider=self.name,
            )

        payload = {
            "prompt": prompt,
            "image_path": image_path,
            "mode": mode,
            "wait": wait,
            "metadata": dict(extra or {}),
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            async with httpx.AsyncClient(timeout=timeout or 60) as client:
                response = await client.post(self.api_url, json=payload, headers=headers)
        except Exception as exc:
            logger.debug("LatticeWorld request failed: %s", exc)
            return WorldGenerationResult(
                False,
                None,
                None,
                "latticeworld_unreachable",
                {"provider": self.name, "error": str(exc)},
                provider=self.name,
            )

        if response.status_code >= 400:
            error_msg = f"LatticeWorld error {response.status_code}"
            try:
                detail = response.json()
                error_msg = detail.get("detail", error_msg)
            except Exception:
                pass
            return WorldGenerationResult(
                False,
                None,
                None,
                error_msg,
                {"provider": self.name, "status_code": response.status_code},
                provider=self.name,
            )

        try:
            data = response.json()
        except Exception as exc:
            return WorldGenerationResult(
                False,
                None,
                None,
                f"invalid_response: {exc}",
                {"provider": self.name},
                provider=self.name,
            )

        metadata = data.get("metadata") or {}
        metadata["provider"] = self.name

        return WorldGenerationResult(
            bool(data.get("success", True)),
            data.get("panorama_path"),
            data.get("world_dir"),
            data.get("error"),
            metadata,
            provider=self.name,
        )
