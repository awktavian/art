"""ElevenLabs Video Dubbing — Automatic Translation + Voice Cloning.

Translates video into multiple languages while preserving the original
speaker's voice characteristics through automatic voice cloning.

Features:
- Automatic voice cloning from source video
- 32+ language support
- Automatic lip-sync (when dubbing_studio=False)
- Speaker detection and separation
- Background audio preservation

Usage:
    from kagami_studio.generation.dubbing import (
        ElevenLabsDubbing,
        dub_video,
    )

    # Quick single language
    result = await dub_video(
        "/path/to/video.mp4",
        target_lang="es",
    )

    # Multiple languages
    dubber = ElevenLabsDubbing()
    await dubber.initialize()
    results = await dubber.dub_multiple(
        "/path/to/video.mp4",
        target_langs=["es", "ja"],
    )

API Reference:
    POST https://api.elevenlabs.io/v1/dubbing
    - Accepts video/audio file or URL
    - Returns dubbing_id for status polling
    - Download via GET /v1/dubbing/{id}/audio/{lang}

Created: January 4, 2026
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("/tmp/kagami_dubbing")


def _get_secret(name: str) -> str | None:
    """Get secret from keychain."""
    try:
        from kagami.core.security import get_secret

        return get_secret(name)
    except Exception:
        try:
            result = subprocess.run(
                ["security", "find-generic-password", "-s", "kagami", "-a", name, "-w"],
                capture_output=True,
                text=True,
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except Exception:
            return None


class DubbingStatus(str, Enum):
    """Status of a dubbing job."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class DubbingResult:
    """Result of a dubbing operation."""

    success: bool
    dubbing_id: str | None = None
    video_path: Path | None = None
    audio_path: Path | None = None
    source_lang: str = ""
    target_lang: str = ""
    duration_s: float = 0.0
    processing_time_s: float = 0.0
    error: str | None = None


class ElevenLabsDubbing:
    """ElevenLabs video dubbing service.

    Translates videos into multiple languages while preserving
    the original speaker's voice through automatic voice cloning.

    Usage:
        dubber = ElevenLabsDubbing()
        await dubber.initialize()

        # Single language
        result = await dubber.dub_video(
            "video.mp4",
            target_lang="es",
        )

        # Multiple languages
        results = await dubber.dub_multiple(
            "video.mp4",
            target_langs=["es", "ja"],
        )
    """

    # Language code mapping (ElevenLabs uses ISO 639-1/3)
    LANGUAGE_CODES = {
        "en": "en",
        "es": "es",
        "ja": "ja",
        "fr": "fr",
        "de": "de",
        "it": "it",
        "pt": "pt",
        "zh": "zh",
        "ko": "ko",
        "ru": "ru",
        "ar": "ar",
        "hi": "hi",
        "nl": "nl",
        "pl": "pl",
        "tr": "tr",
        "sv": "sv",
        "da": "da",
        "fi": "fi",
        "no": "nb",
        "el": "el",
        "cs": "cs",
        "ro": "ro",
        "hu": "hu",
        "th": "th",
        "vi": "vi",
        "id": "id",
        "ms": "ms",
        "tl": "fil",
        "uk": "uk",
        "bg": "bg",
        "hr": "hr",
        "sk": "sk",
    }

    def __init__(self, config: Any = None):
        """Initialize dubbing service.

        Args:
            config: Optional configuration
        """
        self.config = config
        self._client: httpx.AsyncClient | None = None
        self._api_key: str | None = None
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize the ElevenLabs client.

        Returns:
            True if initialization successful
        """
        if self._initialized:
            return True

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        self._api_key = _get_secret("elevenlabs_api_key")
        if not self._api_key:
            logger.error("ElevenLabs API key not found in keychain")
            return False

        self._client = httpx.AsyncClient(timeout=300.0)  # 5 min timeout for uploads
        self._initialized = True

        logger.info("✓ ElevenLabs Dubbing service initialized")
        return True

    async def dub_video(
        self,
        video_path: Path | str,
        target_lang: str,
        source_lang: str = "auto",
        name: str | None = None,
        num_speakers: int = 0,
        voice_clone: bool = True,
        highest_resolution: bool = True,
        drop_background_audio: bool = False,
        dubbing_studio: bool = False,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> DubbingResult:
        """Dub a video into a target language.

        Args:
            video_path: Path to video file
            target_lang: Target language code (e.g., "es", "ja")
            source_lang: Source language code or "auto" for detection
            name: Project name
            num_speakers: Number of speakers (0 for auto-detect)
            voice_clone: Clone original voice (vs library voice)
            highest_resolution: Use highest resolution output
            drop_background_audio: Remove background audio
            dubbing_studio: Prepare for manual edits (slower)
            start_time: Start time in seconds
            end_time: End time in seconds

        Returns:
            DubbingResult with dubbed video/audio path
        """
        if not self._initialized:
            await self.initialize()

        if not self._client or not self._api_key:
            return DubbingResult(success=False, error="Service not initialized")

        video_path = Path(video_path)
        if not video_path.exists():
            return DubbingResult(success=False, error=f"Video not found: {video_path}")

        # Normalize language code
        target_lang_code = self.LANGUAGE_CODES.get(target_lang, target_lang)

        start = time.perf_counter()
        project_name = name or f"dub_{video_path.stem}_{target_lang}"

        try:
            logger.info(f"🎬 Starting dubbing: {video_path.name} → {target_lang}")

            # Prepare multipart form data
            files = {
                "file": (video_path.name, open(video_path, "rb"), "video/mp4"),
            }

            data = {
                "name": project_name,
                "target_lang": target_lang_code,
                "mode": "automatic",
                "num_speakers": str(num_speakers),
                "watermark": "false",
                "highest_resolution": str(highest_resolution).lower(),
                "drop_background_audio": str(drop_background_audio).lower(),
                "dubbing_studio": str(dubbing_studio).lower(),
                "disable_voice_cloning": str(not voice_clone).lower(),
            }

            if source_lang != "auto":
                data["source_lang"] = self.LANGUAGE_CODES.get(source_lang, source_lang)

            if start_time is not None:
                data["start_time"] = str(start_time)
            if end_time is not None:
                data["end_time"] = str(end_time)

            # Submit dubbing job
            resp = await self._client.post(
                "https://api.elevenlabs.io/v1/dubbing",
                headers={"xi-api-key": self._api_key},
                files=files,
                data=data,
            )

            files["file"][1].close()  # Close file handle

            if resp.status_code != 200:
                error_msg = resp.text[:500]
                logger.error(f"Dubbing submit failed: {error_msg}")
                return DubbingResult(
                    success=False,
                    error=f"API error {resp.status_code}: {error_msg}",
                )

            result_data = resp.json()
            dubbing_id = result_data.get("dubbing_id")
            expected_duration = result_data.get("expected_duration_sec", 0)

            logger.info(f"✓ Dubbing job submitted: {dubbing_id}")
            logger.info(f"  Expected duration: {expected_duration:.1f}s")

            # Poll for completion
            dubbed_path = await self._wait_and_download(
                dubbing_id=dubbing_id,
                target_lang=target_lang_code,
                output_name=f"{video_path.stem}_{target_lang}",
            )

            if dubbed_path is None:
                return DubbingResult(
                    success=False,
                    dubbing_id=dubbing_id,
                    error="Failed to download dubbed video",
                )

            processing_time = time.perf_counter() - start

            # Get duration
            duration = self._get_duration(dubbed_path)

            logger.info(f"✓ Dubbing complete: {dubbed_path.name} ({duration:.1f}s)")

            return DubbingResult(
                success=True,
                dubbing_id=dubbing_id,
                video_path=dubbed_path,
                source_lang=source_lang,
                target_lang=target_lang,
                duration_s=duration,
                processing_time_s=processing_time,
            )

        except Exception as e:
            logger.error(f"Dubbing failed: {e}")
            return DubbingResult(success=False, error=str(e))

    async def dub_multiple(
        self,
        video_path: Path | str,
        target_langs: list[str],
        source_lang: str = "auto",
        **kwargs,
    ) -> dict[str, DubbingResult]:
        """Dub a video into multiple languages.

        Args:
            video_path: Path to video file
            target_langs: List of target language codes
            source_lang: Source language code
            **kwargs: Additional arguments passed to dub_video

        Returns:
            Dict mapping language code to DubbingResult
        """
        results = {}

        # Run sequentially to avoid rate limits
        for lang in target_langs:
            result = await self.dub_video(
                video_path=video_path,
                target_lang=lang,
                source_lang=source_lang,
                **kwargs,
            )
            results[lang] = result

            # Brief pause between jobs
            if lang != target_langs[-1]:
                await asyncio.sleep(2)

        return results

    async def _wait_and_download(
        self,
        dubbing_id: str,
        target_lang: str,
        output_name: str,
        timeout_s: int = 600,
    ) -> Path | None:
        """Wait for dubbing to complete and download result.

        Args:
            dubbing_id: Dubbing job ID
            target_lang: Target language for download
            output_name: Output filename (without extension)
            timeout_s: Maximum wait time

        Returns:
            Path to downloaded video or None
        """
        start = time.perf_counter()

        while time.perf_counter() - start < timeout_s:
            # Check status
            resp = await self._client.get(
                f"https://api.elevenlabs.io/v1/dubbing/{dubbing_id}",
                headers={"xi-api-key": self._api_key},
            )

            if resp.status_code != 200:
                logger.warning(f"Status check failed: {resp.status_code}")
                await asyncio.sleep(10)
                continue

            data = resp.json()
            status = data.get("status", "unknown")

            if status == "dubbed":
                # Download the dubbed video
                return await self._download_dubbed(
                    dubbing_id=dubbing_id,
                    target_lang=target_lang,
                    output_name=output_name,
                )
            elif status == "failed":
                error = data.get("error", "Unknown error")
                logger.error(f"Dubbing failed: {error}")
                return None

            # Still processing
            elapsed = time.perf_counter() - start
            logger.info(f"  Dubbing in progress... ({elapsed:.0f}s)")
            await asyncio.sleep(15)

        logger.error(f"Dubbing timeout after {timeout_s}s")
        return None

    async def _download_dubbed(
        self,
        dubbing_id: str,
        target_lang: str,
        output_name: str,
    ) -> Path | None:
        """Download the dubbed video.

        Args:
            dubbing_id: Dubbing job ID
            target_lang: Target language code
            output_name: Output filename

        Returns:
            Path to downloaded file or None
        """
        try:
            # Download video with audio
            resp = await self._client.get(
                f"https://api.elevenlabs.io/v1/dubbing/{dubbing_id}/audio/{target_lang}",
                headers={"xi-api-key": self._api_key},
            )

            if resp.status_code != 200:
                logger.error(f"Download failed: {resp.status_code}")
                return None

            # Determine extension from content-type
            content_type = resp.headers.get("content-type", "")
            ext = ".mp4" if "video" in content_type else ".mp3"

            output_path = OUTPUT_DIR / f"{output_name}{ext}"
            output_path.write_bytes(resp.content)

            logger.info(f"✓ Downloaded: {output_path.name}")
            return output_path

        except Exception as e:
            logger.error(f"Download failed: {e}")
            return None

    async def get_status(self, dubbing_id: str) -> dict[str, Any]:
        """Get status of a dubbing job.

        Args:
            dubbing_id: Dubbing job ID

        Returns:
            Status dict from API
        """
        if not self._initialized:
            await self.initialize()

        resp = await self._client.get(
            f"https://api.elevenlabs.io/v1/dubbing/{dubbing_id}",
            headers={"xi-api-key": self._api_key},
        )

        if resp.status_code != 200:
            return {"status": "error", "error": resp.text}

        return resp.json()

    async def delete_dubbing(self, dubbing_id: str) -> bool:
        """Delete a dubbing project.

        Args:
            dubbing_id: Dubbing job ID

        Returns:
            True if deleted successfully
        """
        if not self._initialized:
            await self.initialize()

        resp = await self._client.delete(
            f"https://api.elevenlabs.io/v1/dubbing/{dubbing_id}",
            headers={"xi-api-key": self._api_key},
        )

        return resp.status_code == 200

    @staticmethod
    def _get_duration(path: Path) -> float:
        """Get video/audio duration."""
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "csv=p=0",
                str(path),
            ],
            capture_output=True,
            text=True,
        )
        return float(result.stdout.strip()) if result.stdout.strip() else 0.0

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_dubber: ElevenLabsDubbing | None = None


async def _get_dubber() -> ElevenLabsDubbing:
    """Get or create singleton dubber."""
    global _dubber
    if _dubber is None:
        _dubber = ElevenLabsDubbing()
        await _dubber.initialize()
    return _dubber


async def dub_video(
    video_path: Path | str,
    target_lang: str,
    source_lang: str = "auto",
    **kwargs,
) -> DubbingResult:
    """Dub a video into a target language (convenience function).

    Args:
        video_path: Path to video file
        target_lang: Target language code (e.g., "es", "ja")
        source_lang: Source language code or "auto"
        **kwargs: Additional arguments

    Returns:
        DubbingResult with dubbed video path
    """
    dubber = await _get_dubber()
    return await dubber.dub_video(
        video_path=video_path,
        target_lang=target_lang,
        source_lang=source_lang,
        **kwargs,
    )


async def dub_multiple(
    video_path: Path | str,
    target_langs: list[str],
    **kwargs,
) -> dict[str, DubbingResult]:
    """Dub a video into multiple languages (convenience function).

    Args:
        video_path: Path to video file
        target_langs: List of target language codes
        **kwargs: Additional arguments

    Returns:
        Dict mapping language code to DubbingResult
    """
    dubber = await _get_dubber()
    return await dubber.dub_multiple(
        video_path=video_path,
        target_langs=target_langs,
        **kwargs,
    )


__all__ = [
    "DubbingResult",
    "DubbingStatus",
    "ElevenLabsDubbing",
    "dub_multiple",
    "dub_video",
]
