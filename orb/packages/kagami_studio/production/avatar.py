"""Avatar Generator — HeyGen Avatar IV for talking head videos.

Generates lip-synced avatar videos using HeyGen's Avatar IV API.
Supports:
- Multiple shot types (dialogue, front views, reverse angles)
- Green/blue screen backgrounds for chromakey compositing
- Motion prompts for emotional expression
- Sequence generation for multi-segment audio

API Flow:
1. Upload reference image to HeyGen
2. Upload audio (from TTS)
3. Submit Avatar IV generation job
4. Poll for completion
5. Download final video

Usage:
    from kagami_studio.production.avatar import generate_avatar_video, AvatarGenerator

    # Quick path
    video_path = await generate_avatar_video(
        audio_path=Path("/tmp/narration.mp3"),
        character="tim",
        background="green",
    )

    # Sequence generation (multiple audio segments as one video)
    generator = AvatarGenerator()
    await generator.initialize()

    result = await generator.generate_sequence(
        audio_segments=[Path("/tmp/seg1.mp3"), Path("/tmp/seg2.mp3")],
        character="tim",
        motion="neutral",
    )
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("/tmp/kagami_avatar")


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


@dataclass
class AvatarResult:
    """Result from avatar video generation."""

    success: bool
    video_path: Path | None = None
    duration_s: float = 0.0
    shot_type: str = "dialogue"
    error: str | None = None
    video_id: str | None = None
    render_time_s: float = 0.0


# Motion prompts for different shot types and moods
MOTION_PROMPTS: dict[str, dict[str, str]] = {
    "dialogue": {
        "neutral": "Natural, conversational expression with subtle gestures",
        "warm": "Warm, friendly expression with natural gestures, slight smile",
        "excited": "Enthusiastic, animated with bright eyes and energetic gestures",
        "serious": "Thoughtful, focused expression with measured movements",
        "dramatic": "Theatrical, expressive with commanding presence",
        "professional": "Confident, composed demeanor with purposeful gestures",
    },
    "monologue": {
        "neutral": "Engaging storyteller presence, natural eye contact",
        "warm": "Intimate, personal delivery with gentle expressions",
        "excited": "Dynamic energy, varied pace and emphasis",
        "serious": "Gravitas and weight, deliberate pacing",
        "dramatic": "Commanding presence, dramatic pauses and emphasis",
        "professional": "Authoritative delivery, crisp and clear",
    },
    "reverse": {
        # Back of head shots - focus on body language
        "neutral": "Slight head movement, natural breathing",
        "warm": "Relaxed shoulders, gentle sway",
        "excited": "Animated posture, slight bouncing",
        "serious": "Still, composed posture",
        "dramatic": "Tension in shoulders, deliberate movements",
        "professional": "Upright posture, minimal movement",
    },
}


class AvatarGenerator:
    """HeyGen Avatar IV generator for talking head videos.

    Manages the full lifecycle of avatar video generation:
    - Character image loading and upload
    - Audio segment extraction and upload
    - HeyGen job submission and polling
    - Video download and caching
    """

    def __init__(self):
        self._client: httpx.AsyncClient | None = None
        self._heygen_key: str | None = None
        self._initialized = False
        self._image_cache: dict[str, str] = {}  # path -> image_key

    async def initialize(self) -> None:
        """Initialize HeyGen API client."""
        if self._initialized:
            return

        self._heygen_key = _get_secret("heygen_api_key")
        if not self._heygen_key:
            raise ValueError("HeyGen API key not found in keychain")

        self._client = httpx.AsyncClient(timeout=120.0)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self._initialized = True
        logger.info("AvatarGenerator initialized")

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()

    async def generate(
        self,
        audio_path: Path,
        character: str = "tim",
        background: str = "green",  # green, blue, or hex color / image URL
        motion: str = "neutral",
        shot_type: str = "dialogue",
    ) -> AvatarResult:
        """Generate single avatar video.

        Args:
            audio_path: Path to audio file (MP3/WAV)
            character: Character ID from assets/characters/
            background: Background color or URL
            motion: Emotional motion style
            shot_type: Type of shot (dialogue, monologue, reverse)

        Returns:
            AvatarResult with video path
        """
        if not self._initialized:
            await self.initialize()

        start = time.perf_counter()

        try:
            # Load character
            from kagami_studio.characters import load_character

            char = load_character(character)
            if not char:
                return AvatarResult(
                    success=False,
                    error=f"Character not found: {character}",
                    shot_type=shot_type,
                )

            if not char.has_avatar or not char.avatar.primary_image:
                return AvatarResult(
                    success=False,
                    error=f"Character has no avatar image: {character}",
                    shot_type=shot_type,
                )

            image_path = char.avatar.primary_image

            # For reverse shots, use back image if available
            if shot_type == "reverse" and char.avatar.back_image:
                image_path = char.avatar.back_image
                logger.info(f"Using back image for reverse shot: {image_path}")

            # Upload image
            image_key = await self._upload_image(image_path)

            # Upload audio
            audio_url = await self._upload_audio(audio_path)

            # Get motion prompt
            motion_prompt = self._get_motion_prompt(shot_type, motion)

            # Submit job
            video_id = await self._submit_avatar(
                image_key=image_key,
                audio_url=audio_url,
                motion_prompt=motion_prompt,
                background=background,
            )

            # Poll for completion
            video_url = await self._poll_completion(video_id)

            # Download video
            video_path = await self._download_video(video_url, video_id, shot_type)

            # Get duration
            duration = self._get_video_duration(video_path)

            render_time = time.perf_counter() - start
            logger.info(
                f"✓ Avatar generated: {video_path.name} "
                f"({duration:.1f}s video, {render_time:.1f}s render)"
            )

            return AvatarResult(
                success=True,
                video_path=video_path,
                duration_s=duration,
                shot_type=shot_type,
                video_id=video_id,
                render_time_s=render_time,
            )

        except Exception as e:
            logger.error(f"Avatar generation failed: {e}")
            return AvatarResult(
                success=False,
                error=str(e),
                shot_type=shot_type,
                render_time_s=time.perf_counter() - start,
            )

    async def generate_sequence(
        self,
        audio_segments: list[Path],
        character: str,
        motion: str = "neutral",
        background: str = "green",
    ) -> AvatarResult:
        """Generate ONE avatar video from multiple audio segments.

        OPTIMIZED: Concatenates all audio into one file and submits
        a SINGLE HeyGen job. Much faster than generating separate videos.

        Args:
            audio_segments: List of audio file paths (in sequence order)
            character: Character ID from assets/characters/
            motion: Emotional motion style for the entire sequence
            background: Background color or URL

        Returns:
            AvatarResult with single video covering all segments
        """
        if not self._initialized:
            await self.initialize()

        if not audio_segments:
            return AvatarResult(success=False, error="No audio segments provided")

        start = time.perf_counter()

        try:
            # Concatenate all audio into ONE file
            if len(audio_segments) == 1:
                concat_audio = audio_segments[0]
            else:
                concat_audio = await self._concat_audio_files(audio_segments)
                logger.info(
                    f"Concatenated {len(audio_segments)} audio segments "
                    f"for {character} into one file"
                )

            # Generate single avatar video
            result = await self.generate(
                audio_path=concat_audio,
                character=character,
                motion=motion,
                background=background,
                shot_type="dialogue",
            )

            if result.success:
                logger.info(
                    f"✓ Generated ONE avatar video for {character} "
                    f"({len(audio_segments)} segments, {result.duration_s:.1f}s)"
                )

            return result

        except Exception as e:
            logger.error(f"Sequence generation failed: {e}")
            return AvatarResult(
                success=False,
                error=str(e),
                render_time_s=time.perf_counter() - start,
            )

    async def _concat_audio_files(self, audio_files: list[Path]) -> Path:
        """Concatenate multiple audio files into one.

        Uses ffmpeg concat demuxer for lossless concatenation.
        """
        concat_path = OUTPUT_DIR / f"concat_{int(time.time() * 1000)}.mp3"
        list_path = OUTPUT_DIR / f"concat_list_{int(time.time() * 1000)}.txt"

        # Write concat list file
        list_content = "\n".join(f"file '{p}'" for p in audio_files)
        list_path.write_text(list_content)

        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(list_path),
                    "-c:a",
                    "libmp3lame",
                    "-q:a",
                    "2",
                    str(concat_path),
                ],
                capture_output=True,
                check=True,
            )
            return concat_path
        finally:
            # Cleanup list file
            if list_path.exists():
                list_path.unlink()

    async def _extract_audio_segment(
        self,
        audio_path: Path,
        start_ms: int,
        end_ms: int,
        index: int,
    ) -> Path:
        """Extract audio segment for a shot."""
        segment_path = OUTPUT_DIR / f"segment_{index}_{start_ms}_{end_ms}.mp3"

        if segment_path.exists():
            return segment_path

        start_s = start_ms / 1000
        duration_s = (end_ms - start_ms) / 1000

        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(audio_path),
                "-ss",
                str(start_s),
                "-t",
                str(duration_s),
                "-c:a",
                "libmp3lame",
                "-q:a",
                "2",
                str(segment_path),
            ],
            capture_output=True,
            check=True,
        )

        return segment_path

    async def _upload_image(self, path: Path) -> str:
        """Upload image to HeyGen."""
        key = str(path)
        if key in self._image_cache:
            return self._image_cache[key]

        # Detect content type
        suffix = path.suffix.lower()
        content_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }
        content_type = content_types.get(suffix, "image/png")

        resp = await self._client.post(
            "https://upload.heygen.com/v1/asset",
            headers={
                "X-API-KEY": self._heygen_key,
                "Content-Type": content_type,
            },
            content=path.read_bytes(),
        )

        if resp.status_code != 200:
            raise RuntimeError(f"Image upload failed: {resp.text[:200]}")

        image_key = resp.json().get("data", {}).get("image_key")
        if not image_key:
            raise RuntimeError("No image_key in response")

        self._image_cache[key] = image_key
        return image_key

    async def _upload_audio(self, path: Path) -> str:
        """Upload audio to HeyGen."""
        resp = await self._client.post(
            "https://upload.heygen.com/v1/asset",
            headers={
                "X-API-KEY": self._heygen_key,
                "Content-Type": "audio/mpeg",
            },
            content=path.read_bytes(),
        )

        if resp.status_code != 200:
            raise RuntimeError(f"Audio upload failed: {resp.text[:200]}")

        return resp.json().get("data", {}).get("url")

    async def _submit_avatar(
        self,
        image_key: str,
        audio_url: str,
        motion_prompt: str,
        background: str = "green",
    ) -> str:
        """Submit HeyGen Avatar IV job."""
        payload = {
            "image_key": image_key,
            "video_title": f"avatar_{int(time.time())}",
            "video_orientation": "landscape",
            "fit": "contain",
            "audio_url": audio_url,
            "custom_motion_prompt": motion_prompt,
            "enhance_custom_motion_prompt": True,
        }

        # Handle background
        if background in ("green", "blue"):
            # Chroma key background
            payload["background"] = {
                "type": "solid_color",
                "color": "#00FF00" if background == "green" else "#0000FF",
            }
        elif background.startswith("http"):
            # Image URL background
            payload["background"] = {
                "type": "image",
                "url": background,
            }
        elif background.startswith("#"):
            # Hex color
            payload["background"] = {
                "type": "solid_color",
                "color": background,
            }

        resp = await self._client.post(
            "https://api.heygen.com/v2/video/av4/generate",
            headers={
                "X-Api-Key": self._heygen_key,
                "Content-Type": "application/json",
            },
            json=payload,
        )

        if resp.status_code != 200:
            raise RuntimeError(f"HeyGen submit failed: {resp.text[:300]}")

        return resp.json().get("data", {}).get("video_id")

    async def _poll_completion(
        self,
        video_id: str,
        timeout_s: float = 600.0,
        poll_interval_s: float = 5.0,
    ) -> str:
        """Poll HeyGen for job completion."""
        start = time.time()

        while time.time() - start < timeout_s:
            resp = await self._client.get(
                f"https://api.heygen.com/v1/video_status.get?video_id={video_id}",
                headers={"X-Api-Key": self._heygen_key},
            )

            if resp.status_code == 200:
                data = resp.json().get("data", {})
                status = data.get("status")

                if status == "completed":
                    return data.get("video_url")
                elif status == "failed":
                    raise RuntimeError(f"HeyGen render failed: {data.get('error')}")

            await asyncio.sleep(poll_interval_s)

        raise RuntimeError("HeyGen timeout")

    async def _download_video(
        self,
        video_url: str,
        video_id: str,
        shot_type: str,
    ) -> Path:
        """Download completed video from HeyGen."""
        resp = await self._client.get(video_url)
        if resp.status_code != 200:
            raise RuntimeError("Failed to download video")

        video_path = OUTPUT_DIR / f"avatar_{shot_type}_{video_id}.mp4"
        video_path.write_bytes(resp.content)
        return video_path

    def _get_motion_prompt(self, shot_type: str, mood: str) -> str:
        """Get appropriate motion prompt for shot type and mood."""
        shot_prompts = MOTION_PROMPTS.get(shot_type, MOTION_PROMPTS["dialogue"])
        return shot_prompts.get(mood, shot_prompts["neutral"])

    @staticmethod
    def _get_video_duration(path: Path) -> float:
        """Get video duration in seconds."""
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


# Singleton instance
_generator: AvatarGenerator | None = None


async def get_avatar_generator() -> AvatarGenerator:
    """Get or create global AvatarGenerator instance."""
    global _generator
    if _generator is None:
        _generator = AvatarGenerator()
        await _generator.initialize()
    return _generator


async def generate_avatar_video(
    audio_path: Path,
    character: str = "tim",
    background: str = "green",
    motion: str = "neutral",
    shot_type: str = "dialogue",
) -> Path | None:
    """Convenience function to generate avatar video.

    Args:
        audio_path: Path to audio file
        character: Character ID
        background: Background color/URL
        motion: Emotional motion style
        shot_type: Type of shot

    Returns:
        Path to generated video, or None if failed
    """
    generator = await get_avatar_generator()
    result = await generator.generate(
        audio_path=audio_path,
        character=character,
        background=background,
        motion=motion,
        shot_type=shot_type,
    )
    return result.video_path if result.success else None


__all__ = [
    "AvatarGenerator",
    "AvatarResult",
    "generate_avatar_video",
    "get_avatar_generator",
]
