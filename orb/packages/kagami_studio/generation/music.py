"""Music Generation — Suno API Integration.

Implements music_generate and music_extend actions from action_space.py.

API: Suno v4 (https://suno.com/api)
Latency: 2-3 minutes per generation
Output: MP3 audio files

Usage:
    >>> generator = MusicGenerator(api_key="...")
    >>> job_id = await generator.generate(prompt="upbeat electronic")
    >>> status = await generator.get_status(job_id)
    >>> audio_url = await generator.get_result(job_id)

Created: 2026-01-05
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class MusicGenerator:
    """Suno API client for music generation.

    Implements:
        - music_generate: Generate music from prompt or custom lyrics
        - music_extend: Extend existing song
    """

    def __init__(self, api_key: str | None = None):
        """Initialize music generator.

        Args:
            api_key: Suno API key (or from SUNO_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("SUNO_API_KEY")
        if not self.api_key:
            logger.warning("SUNO_API_KEY not set - music generation will fail")

        self.base_url = "https://api.suno.com/v1"
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
        return self._session

    async def generate(
        self,
        prompt: str,
        *,
        style: str | None = None,
        lyrics: str | None = None,
        duration: int = 120,
        instrumental: bool = False,
    ) -> str:
        """Generate music from prompt.

        Args:
            prompt: Description of desired music
            style: Musical style/genre
            lyrics: Custom lyrics (optional)
            duration: Target duration in seconds
            instrumental: Generate instrumental only

        Returns:
            Job ID for polling status
        """
        session = await self._get_session()

        payload: dict[str, Any] = {
            "prompt": prompt,
            "duration": duration,
            "instrumental": instrumental,
        }

        if style:
            payload["style"] = style
        if lyrics:
            payload["lyrics"] = lyrics

        async with session.post(f"{self.base_url}/generate", json=payload) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Suno API error: {resp.status} - {await resp.text()}")

            data = await resp.json()
            job_id = data.get("id")

            logger.info(f"Music generation started: {job_id}")
            return job_id

    async def extend(self, audio_url: str, prompt: str, duration: int = 60) -> str:
        """Extend existing song.

        Args:
            audio_url: URL of existing audio to extend
            prompt: Description of how to extend
            duration: Additional duration in seconds

        Returns:
            Job ID for polling
        """
        session = await self._get_session()

        payload = {
            "audio_url": audio_url,
            "prompt": prompt,
            "duration": duration,
        }

        async with session.post(f"{self.base_url}/extend", json=payload) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Suno API error: {resp.status}")

            data = await resp.json()
            return data.get("id")

    async def get_status(self, job_id: str) -> dict[str, Any]:
        """Get generation status.

        Args:
            job_id: Job ID from generate() or extend()

        Returns:
            Status dict with state, progress, error
        """
        session = await self._get_session()

        async with session.get(f"{self.base_url}/status/{job_id}") as resp:
            if resp.status != 200:
                raise RuntimeError(f"Suno API error: {resp.status}")

            return await resp.json()

    async def get_result(self, job_id: str) -> str:
        """Get generated audio URL (when complete).

        Args:
            job_id: Job ID

        Returns:
            URL to download generated MP3
        """
        session = await self._get_session()

        async with session.get(f"{self.base_url}/result/{job_id}") as resp:
            if resp.status != 200:
                raise RuntimeError(f"Suno API error: {resp.status}")

            data = await resp.json()
            return data.get("audio_url")

    async def wait_for_completion(
        self, job_id: str, timeout: float = 300.0, poll_interval: float = 5.0
    ) -> str:
        """Wait for generation to complete and return result.

        Args:
            job_id: Job ID
            timeout: Maximum wait time in seconds
            poll_interval: Seconds between status checks

        Returns:
            Audio URL
        """
        start = asyncio.get_event_loop().time()

        while True:
            status = await self.get_status(job_id)
            state = status.get("state")

            if state == "completed":
                return await self.get_result(job_id)
            elif state == "failed":
                error = status.get("error", "Unknown error")
                raise RuntimeError(f"Generation failed: {error}")

            # Check timeout
            elapsed = asyncio.get_event_loop().time() - start
            if elapsed > timeout:
                raise TimeoutError(f"Generation timed out after {timeout}s")

            # Wait before next poll
            await asyncio.sleep(poll_interval)

    async def close(self) -> None:
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()


# Factory function
def get_music_generator() -> MusicGenerator:
    """Get music generator instance."""
    return MusicGenerator()
