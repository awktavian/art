"""Video Generation — Kling AI (primary) with Runway Gen-4 fallback.

Implements video_generate and video_extend for AI video generation.

Primary: Kling AI 1.5
- Faster: 30s-2min generation
- Cheaper: ~$0.01/video
- Higher quality: Native 1080p

Fallback: Runway Gen-4
- Industry standard
- More control options
- 1-5 minute generation

Created: 2026-01-05
Updated: 2026-01-11 - Added Kling AI as primary
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class VideoProvider(Enum):
    """Available video generation providers."""

    KLING = "kling"
    RUNWAY = "runway"
    AUTO = "auto"  # Try Kling first, fallback to Runway


@dataclass
class VideoResult:
    """Result of video generation."""

    success: bool
    video_url: str | None = None
    video_path: Path | None = None
    provider: str = ""
    duration_seconds: float = 0.0
    generation_time_seconds: float = 0.0
    error: str | None = None
    job_id: str | None = None


class KlingVideoGenerator:
    """Kling AI video generation client.

    Kling 1.5 produces high-quality videos at low cost:
    - Text-to-video: 5-10 second clips
    - Image-to-video: Animate images
    - 1080p output
    - ~30s-2min generation time
    """

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("KLING_API_KEY")
        self._keychain_checked = False
        self.base_url = "https://api.klingai.com/v1"
        self._session: aiohttp.ClientSession | None = None

    async def _ensure_api_key(self) -> bool:
        """Ensure API key is available, checking keychain if needed."""
        if self.api_key:
            return True

        if not self._keychain_checked:
            self._keychain_checked = True
            try:
                from kagami.core.security import get_secret

                self.api_key = await asyncio.to_thread(get_secret, "kling_api_key")
                if self.api_key:
                    logger.info("✅ Kling API key loaded from keychain")
                    return True
            except Exception as e:
                logger.debug(f"Could not load Kling key from keychain: {e}")

        return False

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if not await self._ensure_api_key():
            raise RuntimeError("KLING_API_KEY not configured")

        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }
            )
        return self._session

    async def generate(
        self,
        prompt: str,
        *,
        duration: int = 5,
        image_url: str | None = None,
        mode: str = "std",  # "std" or "pro"
        cfg_scale: float = 7.5,
    ) -> str:
        """Generate video from prompt (and optional image).

        Args:
            prompt: Text description of desired video
            duration: Duration in seconds (5 or 10)
            image_url: Optional image URL to animate
            mode: Quality mode ("std" for fast, "pro" for best)
            cfg_scale: Creativity scale (0-15, higher = more creative)

        Returns:
            Task ID for polling
        """
        session = await self._get_session()

        endpoint = "videos/image2video" if image_url else "videos/text2video"

        payload: dict[str, Any] = {
            "prompt": prompt,
            "duration": str(duration),
            "mode": mode,
            "cfg_scale": cfg_scale,
        }

        if image_url:
            payload["image_url"] = image_url

        async with session.post(f"{self.base_url}/{endpoint}", json=payload) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"Kling API error {resp.status}: {text}")
            data = await resp.json()
            task_id = data.get("data", {}).get("task_id") or data.get("task_id")
            if not task_id:
                raise RuntimeError(f"No task_id in response: {data}")
            logger.info(f"✅ Kling video generation started: {task_id}")
            return task_id

    async def get_status(self, task_id: str) -> dict[str, Any]:
        """Get generation status.

        Returns:
            Dict with 'status' key: "processing", "succeed", "failed"
        """
        session = await self._get_session()

        async with session.get(f"{self.base_url}/videos/text2video/{task_id}") as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"Kling status error {resp.status}: {text}")
            data = await resp.json()
            return data.get("data", data)

    async def get_result(self, task_id: str) -> str:
        """Get video URL when complete."""
        status = await self.get_status(task_id)
        output = status.get("output", {})
        videos = output.get("videos", [])
        if videos:
            return videos[0].get("url", "")
        raise RuntimeError(f"No video URL in result: {status}")

    async def wait_for_completion(
        self,
        task_id: str,
        timeout: float = 300.0,
        poll_interval: float = 5.0,
    ) -> str:
        """Wait for video generation (30s-2min typical).

        Args:
            task_id: Task ID from generate()
            timeout: Max wait time in seconds
            poll_interval: Time between status checks

        Returns:
            Video URL
        """
        start = time.monotonic()

        while True:
            status = await self.get_status(task_id)
            state = status.get("status", "").lower()

            if state == "succeed":
                return await self.get_result(task_id)
            elif state == "failed":
                error = status.get("error", "Unknown error")
                raise RuntimeError(f"Kling generation failed: {error}")

            elapsed = time.monotonic() - start
            if elapsed > timeout:
                raise TimeoutError(f"Kling video generation timeout after {elapsed:.0f}s")

            logger.debug(f"Kling status: {state} ({elapsed:.0f}s elapsed)")
            await asyncio.sleep(poll_interval)

    async def close(self) -> None:
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()


class RunwayVideoGenerator:
    """Runway Gen-4 API client for video generation (fallback)."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("RUNWAY_API_KEY")
        self._keychain_checked = False
        self.base_url = "https://api.runwayml.com/v1"
        self._session: aiohttp.ClientSession | None = None

    async def _ensure_api_key(self) -> bool:
        """Ensure API key is available."""
        if self.api_key:
            return True

        if not self._keychain_checked:
            self._keychain_checked = True
            try:
                from kagami.core.security import get_secret

                self.api_key = await asyncio.to_thread(get_secret, "runway_api_key")
                if self.api_key:
                    logger.info("✅ Runway API key loaded from keychain")
                    return True
            except Exception as e:
                logger.debug(f"Could not load Runway key from keychain: {e}")

        return False

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if not await self._ensure_api_key():
            raise RuntimeError("RUNWAY_API_KEY not configured")

        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
        return self._session

    async def generate(
        self,
        prompt: str,
        *,
        duration: int = 5,
        image_url: str | None = None,
    ) -> str:
        """Generate video from prompt.

        Returns:
            Job ID for polling
        """
        session = await self._get_session()

        payload: dict[str, Any] = {
            "prompt": prompt,
            "duration": duration,
        }

        if image_url:
            payload["image_url"] = image_url

        async with session.post(f"{self.base_url}/generate", json=payload) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"Runway error {resp.status}: {text}")
            data = await resp.json()
            return data.get("id")

    async def extend(self, video_url: str, prompt: str, duration: int = 4) -> str:
        """Extend existing video."""
        session = await self._get_session()

        payload = {
            "video_url": video_url,
            "prompt": prompt,
            "duration": duration,
        }

        async with session.post(f"{self.base_url}/extend", json=payload) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"Runway extend error {resp.status}: {text}")
            data = await resp.json()
            return data.get("id")

    async def get_status(self, job_id: str) -> dict[str, Any]:
        """Get generation status."""
        session = await self._get_session()

        async with session.get(f"{self.base_url}/status/{job_id}") as resp:
            return await resp.json()

    async def get_result(self, job_id: str) -> str:
        """Get video URL when complete."""
        session = await self._get_session()

        async with session.get(f"{self.base_url}/result/{job_id}") as resp:
            data = await resp.json()
            return data.get("video_url")

    async def wait_for_completion(
        self, job_id: str, timeout: float = 600.0, poll_interval: float = 10.0
    ) -> str:
        """Wait for video generation (1-5 minutes typical)."""
        start = time.monotonic()

        while True:
            status = await self.get_status(job_id)
            state = status.get("state", "")

            if state == "completed":
                return await self.get_result(job_id)
            elif state == "failed":
                raise RuntimeError(f"Runway generation failed: {status.get('error')}")

            elapsed = time.monotonic() - start
            if elapsed > timeout:
                raise TimeoutError("Runway video generation timeout")

            logger.debug(f"Runway status: {state} ({elapsed:.0f}s elapsed)")
            await asyncio.sleep(poll_interval)

    async def close(self) -> None:
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()


class VideoGenerator:
    """Unified video generator with automatic provider selection.

    Uses Kling AI as primary (faster, cheaper) with Runway as fallback.
    """

    def __init__(
        self,
        provider: VideoProvider = VideoProvider.AUTO,
        kling_api_key: str | None = None,
        runway_api_key: str | None = None,
    ):
        self.provider = provider
        self._kling = KlingVideoGenerator(kling_api_key)
        self._runway = RunwayVideoGenerator(runway_api_key)

    async def generate(
        self,
        prompt: str,
        *,
        duration: int = 5,
        image_url: str | None = None,
        provider: VideoProvider | None = None,
    ) -> VideoResult:
        """Generate video from prompt.

        Args:
            prompt: Text description of desired video
            duration: Duration in seconds (5-10)
            image_url: Optional image URL to animate
            provider: Override default provider

        Returns:
            VideoResult with video URL or error
        """
        use_provider = provider or self.provider
        start_time = time.monotonic()

        # AUTO mode: try Kling first, fallback to Runway
        if use_provider == VideoProvider.AUTO:
            try:
                return await self._generate_with_kling(prompt, duration, image_url)
            except Exception as kling_error:
                logger.warning(f"Kling failed, trying Runway: {kling_error}")
                try:
                    return await self._generate_with_runway(prompt, duration, image_url)
                except Exception as runway_error:
                    return VideoResult(
                        success=False,
                        error=f"Both providers failed. Kling: {kling_error}, Runway: {runway_error}",
                        generation_time_seconds=time.monotonic() - start_time,
                    )

        elif use_provider == VideoProvider.KLING:
            return await self._generate_with_kling(prompt, duration, image_url)

        elif use_provider == VideoProvider.RUNWAY:
            return await self._generate_with_runway(prompt, duration, image_url)

        return VideoResult(success=False, error=f"Unknown provider: {use_provider}")

    async def _generate_with_kling(
        self, prompt: str, duration: int, image_url: str | None
    ) -> VideoResult:
        """Generate video using Kling AI."""
        start_time = time.monotonic()

        try:
            task_id = await self._kling.generate(prompt, duration=duration, image_url=image_url)
            video_url = await self._kling.wait_for_completion(task_id)

            return VideoResult(
                success=True,
                video_url=video_url,
                provider="kling",
                duration_seconds=float(duration),
                generation_time_seconds=time.monotonic() - start_time,
                job_id=task_id,
            )

        except Exception as e:
            return VideoResult(
                success=False,
                provider="kling",
                error=str(e),
                generation_time_seconds=time.monotonic() - start_time,
            )

    async def _generate_with_runway(
        self, prompt: str, duration: int, image_url: str | None
    ) -> VideoResult:
        """Generate video using Runway."""
        start_time = time.monotonic()

        try:
            job_id = await self._runway.generate(prompt, duration=duration, image_url=image_url)
            video_url = await self._runway.wait_for_completion(job_id)

            return VideoResult(
                success=True,
                video_url=video_url,
                provider="runway",
                duration_seconds=float(duration),
                generation_time_seconds=time.monotonic() - start_time,
                job_id=job_id,
            )

        except Exception as e:
            return VideoResult(
                success=False,
                provider="runway",
                error=str(e),
                generation_time_seconds=time.monotonic() - start_time,
            )

    async def extend(self, video_url: str, prompt: str, duration: int = 4) -> VideoResult:
        """Extend an existing video (Runway only)."""
        start_time = time.monotonic()

        try:
            job_id = await self._runway.extend(video_url, prompt, duration)
            result_url = await self._runway.wait_for_completion(job_id)

            return VideoResult(
                success=True,
                video_url=result_url,
                provider="runway",
                duration_seconds=float(duration),
                generation_time_seconds=time.monotonic() - start_time,
                job_id=job_id,
            )

        except Exception as e:
            return VideoResult(
                success=False,
                provider="runway",
                error=str(e),
                generation_time_seconds=time.monotonic() - start_time,
            )

    async def close(self) -> None:
        """Close all provider sessions."""
        await self._kling.close()
        await self._runway.close()


# Singleton instance
_video_generator: VideoGenerator | None = None


def get_video_generator(
    provider: VideoProvider = VideoProvider.AUTO,
) -> VideoGenerator:
    """Get or create video generator singleton."""
    global _video_generator
    if _video_generator is None:
        _video_generator = VideoGenerator(provider=provider)
    return _video_generator


async def generate_video(
    prompt: str,
    *,
    duration: int = 5,
    image_url: str | None = None,
    provider: VideoProvider = VideoProvider.AUTO,
) -> VideoResult:
    """Convenience function to generate video.

    Args:
        prompt: Text description of desired video
        duration: Duration in seconds (5-10)
        image_url: Optional image URL to animate
        provider: Which provider to use (AUTO = Kling with Runway fallback)

    Returns:
        VideoResult with video URL or error

    Example:
        result = await generate_video(
            "A cat playing piano in a jazz club",
            duration=5,
        )
        if result.success:
            print(f"Video: {result.video_url}")
    """
    generator = get_video_generator(provider)
    return await generator.generate(
        prompt, duration=duration, image_url=image_url, provider=provider
    )
