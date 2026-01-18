"""Holodeck — Multi-party dialogue simulation.

Create conversations between any characters using the unified Character system.
Supports humans, pets, AI, and external characters.

Migrated from: core/media/production/holodeck.py

Usage:
    from kagami_studio.modes import Holodeck

    holodeck = Holodeck()
    await holodeck.initialize()

    # Add dialogue (any character from assets/characters/)
    holodeck.dialogue("bella", "The cold? I am built for the cold.")
    holodeck.dialogue("tim", "I know, girl. Let's go outside.")
    holodeck.dialogue("bella", "SNOW! SNOW SNOW SNOW!")

    # Render
    result = await holodeck.render(play=True)
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from kagami_studio.characters import Character, load_character
from kagami_studio.characters.voice import SpeakResult, speak

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("/tmp/kagami_holodeck")


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
class DialogueLine:
    """A single line of dialogue."""

    character: str  # Character identity_id
    text: str
    motion: str = "warm"


@dataclass
class HolodeckResult:
    """Result from holodeck rendering."""

    success: bool
    video_path: Path | None = None
    duration_s: float = 0.0
    line_count: int = 0
    error: str | None = None


class Holodeck:
    """Multi-party dialogue simulation engine.

    Uses unified Character system for any character type:
    - Household members (Tim, Jill)
    - Pets (Bella the Malamute)
    - AI (Kagami)
    - External (DCC characters)
    """

    def __init__(self):
        self._client: httpx.AsyncClient | None = None
        self._heygen_key: str | None = None
        self._initialized = False
        self._lines: list[DialogueLine] = []
        self._image_cache: dict[str, str] = {}

    async def initialize(self) -> None:
        """Initialize API clients."""
        if self._initialized:
            return

        self._heygen_key = _get_secret("heygen_api_key")

        if not self._heygen_key:
            raise ValueError("HeyGen API key not found in keychain")

        self._client = httpx.AsyncClient(timeout=120.0)
        self._initialized = True
        logger.info("Holodeck initialized")

    def dialogue(self, character: str, text: str, motion: str = "warm") -> Holodeck:
        """Add a dialogue line.

        Args:
            character: Character identity_id (bella, tim, kagami, etc.)
            text: What the character says
            motion: Emotional direction

        Returns:
            Self for chaining
        """
        self._lines.append(
            DialogueLine(
                character=character.lower(),
                text=text,
                motion=motion,
            )
        )
        return self

    def clear(self) -> Holodeck:
        """Clear all dialogue lines."""
        self._lines = []
        return self

    async def _upload_image(self, path: Path) -> str:
        """Upload image to HeyGen. Returns image_key."""
        key = str(path)
        if key in self._image_cache:
            return self._image_cache[key]

        # Detect content type from extension
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
            headers={"X-API-KEY": self._heygen_key, "Content-Type": content_type},
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
            headers={"X-API-KEY": self._heygen_key, "Content-Type": "audio/mpeg"},
            content=path.read_bytes(),
        )

        if resp.status_code != 200:
            raise RuntimeError(f"Audio upload failed: {resp.text[:200]}")

        return resp.json().get("data", {}).get("url")

    async def _submit_avatar(self, image_key: str, audio_url: str, motion: str) -> str:
        """Submit HeyGen Avatar IV job."""
        motion_prompts = {
            "warm": "Warm, friendly expression with natural gestures",
            "excited": "Enthusiastic, animated with bright eyes",
            "dramatic": "Theatrical, expressive, commanding presence",
            "regal": "Dignified, composed, measured movements",
            "sleepy": "Relaxed, slow movements, soft expression",
        }

        payload = {
            "image_key": image_key,
            "video_title": f"holodeck_{int(time.time())}",
            "video_orientation": "landscape",
            "fit": "contain",
            "audio_url": audio_url,
            "custom_motion_prompt": motion_prompts.get(motion, motion_prompts["warm"]),
            "enhance_custom_motion_prompt": True,
        }

        resp = await self._client.post(
            "https://api.heygen.com/v2/video/av4/generate",
            headers={"X-Api-Key": self._heygen_key, "Content-Type": "application/json"},
            json=payload,
        )

        if resp.status_code != 200:
            raise RuntimeError(f"HeyGen submit failed: {resp.text[:300]}")

        return resp.json().get("data", {}).get("video_id")

    async def _poll_avatar(self, video_id: str) -> str:
        """Poll HeyGen for completion."""
        start = time.time()

        while time.time() - start < 600:
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

            await asyncio.sleep(5)

        raise RuntimeError("HeyGen timeout")

    @staticmethod
    def _get_audio_duration(path: Path) -> float:
        """Get audio duration in seconds."""
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

    async def render(
        self,
        output_path: Path | None = None,
        play: bool = False,
    ) -> HolodeckResult:
        """Render the dialogue scene.

        OPTIMIZED: Groups lines by character and generates ONE HeyGen
        video per character instead of one per line.

        Args:
            output_path: Output video path
            play: Open video after rendering

        Returns:
            HolodeckResult with video path
        """
        if not self._initialized:
            await self.initialize()

        if not self._lines:
            return HolodeckResult(success=False, error="No dialogue lines")

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        start_time = time.time()

        try:
            # Load all characters
            characters: dict[str, Character] = {}
            for line in self._lines:
                if line.character not in characters:
                    char = load_character(line.character)
                    if not char:
                        return HolodeckResult(
                            success=False,
                            error=f"Character not found: {line.character}",
                        )
                    if not char.has_avatar:
                        return HolodeckResult(
                            success=False,
                            error=f"Character has no avatar: {line.character}",
                        )
                    characters[line.character] = char

            num_chars = len(characters)
            logger.info(f"=== HOLODECK: {len(self._lines)} lines, {num_chars} characters ===")

            # Phase 1: Upload images (one per character)
            logger.info("Phase 1: Upload images")
            image_keys = {}
            for name, char in characters.items():
                if char.avatar.primary_image:
                    image_keys[name] = await self._upload_image(char.avatar.primary_image)

            # Phase 2: Generate audio for ALL lines
            logger.info("Phase 2: Generate audio (all lines)")
            audio_results: list[SpeakResult] = []
            audio_durations: list[float] = []
            for line in self._lines:
                result = await speak(line.character, line.text, mood=line.motion)
                if not result.success:
                    return HolodeckResult(success=False, error=f"TTS failed: {result.error}")
                audio_results.append(result)
                # Get audio duration
                dur = self._get_audio_duration(result.audio_path)
                audio_durations.append(dur)

            # Phase 3: Group lines by character and concatenate audio
            logger.info("Phase 3: Group by character and concatenate audio")
            char_audio_map: dict[str, list[tuple[int, Path, float]]] = {
                name: [] for name in characters
            }

            for i, (line, result, dur) in enumerate(
                zip(self._lines, audio_results, audio_durations, strict=True)
            ):
                char_audio_map[line.character].append((i, result.audio_path, dur))

            # Concatenate audio for each character and get cumulative offsets
            char_concat_audio: dict[str, Path] = {}
            char_line_offsets: dict[str, list[tuple[int, float, float]]] = {}

            for char_name, segments in char_audio_map.items():
                if not segments:
                    continue

                # Track line index, start offset, duration for later slicing
                offsets = []
                cumulative = 0.0
                audio_paths = []

                for line_idx, audio_path, dur in segments:
                    offsets.append((line_idx, cumulative, dur))
                    audio_paths.append(audio_path)
                    cumulative += dur

                char_line_offsets[char_name] = offsets

                if len(audio_paths) == 1:
                    char_concat_audio[char_name] = audio_paths[0]
                else:
                    # Concatenate audio files
                    concat_path = OUTPUT_DIR / f"concat_{char_name}_{int(time.time())}.mp3"
                    list_path = OUTPUT_DIR / f"list_{char_name}.txt"
                    list_path.write_text("\n".join(f"file '{p}'" for p in audio_paths))

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
                    list_path.unlink()
                    char_concat_audio[char_name] = concat_path
                    logger.info(
                        f"  {char_name}: concatenated {len(audio_paths)} clips "
                        f"({cumulative:.1f}s total)"
                    )

            # Phase 4: Upload concatenated audio and submit ONE job per character
            logger.info(f"Phase 4: Submit HeyGen jobs ({num_chars} jobs, was {len(self._lines)})")
            char_video_ids: dict[str, str] = {}

            for char_name, concat_audio in char_concat_audio.items():
                audio_url = await self._upload_audio(concat_audio)
                img_key = image_keys[char_name]
                # Use first line's motion for this character
                motion = next(
                    (line.motion for line in self._lines if line.character == char_name),
                    "neutral",
                )
                video_id = await self._submit_avatar(img_key, audio_url, motion)
                char_video_ids[char_name] = video_id
                logger.info(f"  {char_name}: submitted job {video_id}")

            # Phase 5: Poll all jobs in parallel
            logger.info("Phase 5: Poll HeyGen jobs")
            poll_tasks = {name: self._poll_avatar(vid) for name, vid in char_video_ids.items()}
            poll_results = await asyncio.gather(*poll_tasks.values(), return_exceptions=True)
            char_video_urls = dict(zip(poll_tasks.keys(), poll_results, strict=True))

            # Check for errors
            for char_name, result in char_video_urls.items():
                if isinstance(result, Exception):
                    return HolodeckResult(
                        success=False,
                        error=f"HeyGen failed for {char_name}: {result}",
                    )

            # Phase 6: Download character videos
            logger.info("Phase 6: Download videos")
            char_video_paths: dict[str, Path] = {}
            for char_name, video_url in char_video_urls.items():
                video_path = OUTPUT_DIR / f"char_{char_name}_{int(time.time())}.mp4"
                resp = await self._client.get(video_url)
                video_path.write_bytes(resp.content)
                char_video_paths[char_name] = video_path
                logger.info(f"  {char_name}: downloaded video")

            # Phase 7: Slice and interleave videos by original line order
            logger.info("Phase 7: Slice and compose")
            shot_paths = []

            for i, line in enumerate(self._lines):
                char_name = line.character
                video_path = char_video_paths[char_name]

                # Find this line's offset in the character's video
                offset_info = next((o for o in char_line_offsets[char_name] if o[0] == i), None)
                if not offset_info:
                    continue

                _, start_s, duration_s = offset_info
                shot_path = OUTPUT_DIR / f"shot_{i:03d}.mp4"

                # Extract segment from character video
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-ss",
                        str(start_s),
                        "-i",
                        str(video_path),
                        "-t",
                        str(duration_s),
                        "-c:v",
                        "libx264",
                        "-preset",
                        "fast",
                        "-crf",
                        "18",
                        "-c:a",
                        "aac",
                        "-b:a",
                        "192k",
                        str(shot_path),
                    ],
                    capture_output=True,
                    check=True,
                )
                shot_paths.append(shot_path)

            # Phase 8: Final composition
            logger.info("Phase 8: Final composition")
            if output_path is None:
                output_path = OUTPUT_DIR / f"holodeck_{int(time.time())}.mp4"

            if len(shot_paths) == 1:
                import shutil

                shutil.copy(shot_paths[0], output_path)
            else:
                concat_file = OUTPUT_DIR / "concat_final.txt"
                concat_file.write_text("\n".join(f"file '{p}'" for p in shot_paths))

                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-f",
                        "concat",
                        "-safe",
                        "0",
                        "-i",
                        str(concat_file),
                        "-c:v",
                        "libx264",
                        "-preset",
                        "medium",
                        "-crf",
                        "20",
                        "-c:a",
                        "aac",
                        "-b:a",
                        "192k",
                        str(output_path),
                    ],
                    capture_output=True,
                    check=True,
                )

            # Get duration
            duration = self._get_video_duration(output_path)

            elapsed = time.time() - start_time
            logger.info(
                f"✓ {output_path.name} ({duration:.1f}s video, {elapsed:.1f}s elapsed)\n"
                f"  OPTIMIZATION: {num_chars} HeyGen jobs instead of {len(self._lines)}"
            )

            if play:
                subprocess.run(["open", str(output_path)])

            return HolodeckResult(
                success=True,
                video_path=output_path,
                duration_s=duration,
                line_count=len(self._lines),
            )

        except Exception as e:
            logger.error(f"Holodeck failed: {e}", exc_info=True)
            return HolodeckResult(success=False, error=str(e))

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()


async def simulate_dialogue(
    lines: list[tuple[str, str]],
    play: bool = True,
) -> HolodeckResult:
    """Convenience function for multi-party dialogue.

    Args:
        lines: List of (character, text) tuples
        play: Open video after rendering

    Example:
        result = await simulate_dialogue([
            ("bella", "I am built for the cold."),
            ("tim", "Let's go for a walk!"),
            ("bella", "SNOW!"),
        ])
    """
    holodeck = Holodeck()
    await holodeck.initialize()

    for char, text in lines:
        holodeck.dialogue(char, text)

    return await holodeck.render(play=play)


__all__ = [
    "DialogueLine",
    "Holodeck",
    "HolodeckResult",
    "simulate_dialogue",
]
