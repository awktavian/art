"""3D Model Generation — Meshy API.

Implements model_3d_generate and model_3d_texture from action_space.py.

API: Meshy (https://meshy.ai)
Latency: 30-60 seconds
Output: GLB, OBJ, FBX formats

Created: 2026-01-05
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Literal

import aiohttp

logger = logging.getLogger(__name__)


class Model3DGenerator:
    """Meshy API client for 3D model generation."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("MESHY_API_KEY")
        self.base_url = "https://api.meshy.ai/v1"
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
        return self._session

    async def generate(
        self,
        prompt: str,
        *,
        style: str = "realistic",
        topology: Literal["quad", "triangle"] = "quad",
    ) -> str:
        """Generate 3D model from text prompt."""
        session = await self._get_session()

        payload = {
            "prompt": prompt,
            "style": style,
            "topology": topology,
        }

        async with session.post(f"{self.base_url}/text-to-3d", json=payload) as resp:
            data = await resp.json()
            return data.get("id")

    async def texture(
        self,
        model_url: str,
        prompt: str,
        resolution: int = 2048,
    ) -> str:
        """Generate/apply textures to 3D model."""
        session = await self._get_session()

        payload = {
            "model_url": model_url,
            "prompt": prompt,
            "resolution": resolution,
        }

        async with session.post(f"{self.base_url}/texture", json=payload) as resp:
            data = await resp.json()
            return data.get("id")

    async def get_status(self, job_id: str) -> dict[str, Any]:
        session = await self._get_session()
        async with session.get(f"{self.base_url}/status/{job_id}") as resp:
            return await resp.json()

    async def get_result(self, job_id: str, format: str = "glb") -> str:
        """Get 3D model URL in specified format."""
        session = await self._get_session()
        async with session.get(f"{self.base_url}/result/{job_id}?format={format}") as resp:
            data = await resp.json()
            return data.get("model_url")

    async def wait_for_completion(self, job_id: str, timeout: float = 120.0) -> str:
        start = asyncio.get_event_loop().time()
        while True:
            status = await self.get_status(job_id)
            if status.get("state") == "completed":
                return await self.get_result(job_id)
            elif status.get("state") == "failed":
                raise RuntimeError(f"3D generation failed: {status.get('error')}")
            if asyncio.get_event_loop().time() - start > timeout:
                raise TimeoutError("3D generation timeout")
            await asyncio.sleep(5.0)

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()


def get_model_3d_generator() -> Model3DGenerator:
    return Model3DGenerator()
