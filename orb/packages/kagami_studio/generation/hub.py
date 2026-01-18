"""Generation Hub — Central AI generation orchestrator.

Self-contained generator implementations.
No dependencies on deprecated kagami_media.production.
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

from kagami_studio.generation.image import IMAGE_MODEL, IMAGE_QUALITY

if TYPE_CHECKING:
    from PIL import Image

    from kagami_studio.generation.dubbing import DubbingResult

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("/tmp/kagami_generation")


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
class ImageResult:
    """Result of image generation."""

    success: bool
    path: Path | None = None
    error: str | None = None


@dataclass
class AvatarResult:
    """Result of avatar video generation."""

    success: bool
    video_path: Path | None = None
    audio_path: Path | None = None
    duration_s: float = 0.0
    error: str | None = None


@dataclass
class VideoResult:
    """Result of video generation."""

    success: bool
    path: Path | None = None
    duration_s: float = 0.0
    error: str | None = None


@dataclass
class AudioResult:
    """Result of audio generation."""

    success: bool
    path: Path | None = None
    duration_s: float = 0.0
    error: str | None = None


@dataclass
class FaviconResult:
    """Result of favicon generation.

    Contains paths to all generated sizes for a colony favicon.
    """

    success: bool
    colony: str = ""
    paths: dict[int, Path] | None = None  # size -> path mapping
    master_path: Path | None = None  # 512px master
    error: str | None = None


# Colony-specific favicon prompts with chromakey backgrounds
COLONY_FAVICON_PROMPTS: dict[str, dict[str, str]] = {
    "spark": {
        "concept": "flame sprite",
        "prompt": "tiny cute flame mascot character, kawaii style, adorable fire spirit with big sparkly eyes, simple clean design, chibi proportions, warm orange and red colors, solid bright green #00FF00 background for chromakey removal, centered composition, no shadows on background",
    },
    "forge": {
        "concept": "anvil/hammer buddy",
        "prompt": "adorable little hammer mascot character, kawaii chibi style, friendly blacksmith tool with cute face, metallic silver and warm brown colors, simple clean design, solid bright green #00FF00 background for chromakey removal, centered composition, no shadows on background",
    },
    "flow": {
        "concept": "water droplet",
        "prompt": "cute water droplet character mascot, kawaii style, friendly blue water spirit with sparkly eyes, simple clean translucent design, cool blue colors, solid bright green #00FF00 background for chromakey removal, centered composition, no shadows on background",
    },
    "nexus": {
        "concept": "connected nodes",
        "prompt": "friendly network node mascot, kawaii style, cute connected dots character, adorable hub spirit with glowing connections, purple and cyan colors, solid bright green #00FF00 background for chromakey removal, centered composition, no shadows on background",
    },
    "beacon": {
        "concept": "lighthouse",
        "prompt": "tiny cute lighthouse character mascot, kawaii chibi style, adorable beacon with warm glowing light and friendly face, white and gold colors, solid bright green #00FF00 background for chromakey removal, centered composition, no shadows on background",
    },
    "grove": {
        "concept": "leaf sprite",
        "prompt": "adorable leaf sprite mascot character, kawaii forest spirit, cute little tree creature with sparkly eyes, fresh green and brown colors, simple clean design, solid bright green #00FF00 background for chromakey removal, centered composition, no shadows on background",
    },
    "crystal": {
        "concept": "gem buddy",
        "prompt": "cute crystal gem mascot character, kawaii style, sparkling diamond spirit with friendly face, prismatic rainbow reflections, translucent faceted design, solid bright green #00FF00 background for chromakey removal, centered composition, no shadows on background",
    },
}


class GenerationHub:
    """Central hub for all AI generation.

    Provides unified interface for:
    - Image generation (OpenAI gpt-image-1)
    - Avatar video generation (HeyGen Avatar IV)
    - Video generation (placeholder for Runway)
    - Audio generation (ElevenLabs)
    """

    def __init__(self, config: Any = None):
        self.config = config
        self._client: httpx.AsyncClient | None = None
        self._openai_key: str | None = None
        self._heygen_key: str | None = None
        self._elevenlabs_key: str | None = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize API clients."""
        if self._initialized:
            return

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        self._openai_key = _get_secret("openai_api_key")
        self._heygen_key = _get_secret("heygen_api_key")
        self._elevenlabs_key = _get_secret("elevenlabs_api_key")

        self._client = httpx.AsyncClient(timeout=120.0)
        self._initialized = True

        logger.info("GenerationHub initialized")

    async def generate_image(
        self,
        prompt: str,
        aspect: str = "16:9",
        style: str | None = None,
    ) -> ImageResult:
        """Generate an image using OpenAI gpt-image-1.

        Args:
            prompt: Image description
            aspect: Aspect ratio (16:9, 9:16, 1:1)
            style: Style hint

        Returns:
            ImageResult with path to generated image
        """
        if not self._initialized:
            await self.initialize()

        if not self._openai_key:
            return ImageResult(success=False, error="OpenAI API key not found")

        try:
            # Map aspect to size
            size_map = {
                "16:9": "1792x1024",
                "9:16": "1024x1792",
                "1:1": "1024x1024",
            }
            size = size_map.get(aspect, "1792x1024")

            # Build prompt
            full_prompt = prompt
            if style:
                full_prompt = f"{prompt}, {style} style"

            resp = await self._client.post(
                "https://api.openai.com/v1/images/generations",
                headers={
                    "Authorization": f"Bearer {self._openai_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": IMAGE_MODEL,  # Global preference: gpt-image-1.5
                    "prompt": full_prompt,
                    "n": 1,
                    "size": size,
                    "quality": IMAGE_QUALITY,
                },
            )

            if resp.status_code != 200:
                return ImageResult(success=False, error=f"OpenAI error: {resp.text[:200]}")

            data = resp.json()

            # gpt-image-1.5 returns base64 encoded images
            image_data = data.get("data", [{}])[0]
            b64_image = image_data.get("b64_json")

            if not b64_image:
                # Fallback to URL if available
                image_url = image_data.get("url")
                if image_url:
                    img_resp = await self._client.get(image_url)
                    output_path = OUTPUT_DIR / f"image_{int(time.time() * 1000)}.png"
                    output_path.write_bytes(img_resp.content)
                    return ImageResult(success=True, path=output_path)
                return ImageResult(success=False, error="No image data in response")

            # Decode base64 image
            import base64

            image_bytes = base64.b64decode(b64_image)
            output_path = OUTPUT_DIR / f"image_{int(time.time() * 1000)}.png"
            output_path.write_bytes(image_bytes)

            return ImageResult(success=True, path=output_path)

        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            return ImageResult(success=False, error=str(e))

    async def generate_avatar(
        self,
        text: str,
        image_path: Path | None = None,
        voice_id: str | None = None,
    ) -> AvatarResult:
        """Generate avatar video with lip sync.

        Args:
            text: Text to speak
            image_path: Character image (uses default Kagami if None)
            voice_id: ElevenLabs voice ID

        Returns:
            AvatarResult with video path
        """
        if not self._initialized:
            await self.initialize()

        if not self._heygen_key:
            return AvatarResult(success=False, error="HeyGen API key not found")

        # Use default identity if no image provided
        if image_path is None:
            image_path = Path("assets/identities/kagami/halfbody_professional.png")

        if not image_path.exists():
            return AvatarResult(success=False, error=f"Image not found: {image_path}")

        try:
            # Generate TTS first
            audio_result = await self.generate_audio(text, voice_id)
            if not audio_result.success:
                return AvatarResult(success=False, error=f"TTS failed: {audio_result.error}")

            # Upload image
            resp = await self._client.post(
                "https://upload.heygen.com/v1/asset",
                headers={"X-API-KEY": self._heygen_key, "Content-Type": "image/png"},
                content=image_path.read_bytes(),
            )
            if resp.status_code != 200:
                return AvatarResult(success=False, error=f"Image upload failed: {resp.text[:200]}")

            image_key = resp.json().get("data", {}).get("image_key")

            # Upload audio
            resp = await self._client.post(
                "https://upload.heygen.com/v1/asset",
                headers={"X-API-KEY": self._heygen_key, "Content-Type": "audio/mpeg"},
                content=audio_result.path.read_bytes(),
            )
            if resp.status_code != 200:
                return AvatarResult(success=False, error=f"Audio upload failed: {resp.text[:200]}")

            audio_url = resp.json().get("data", {}).get("url")

            # Submit Avatar IV job
            payload = {
                "image_key": image_key,
                "video_title": f"avatar_{int(time.time())}",
                "video_orientation": "landscape",
                "fit": "contain",
                "audio_url": audio_url,
                "custom_motion_prompt": "Warm, friendly expression",
                "enhance_custom_motion_prompt": True,
            }

            resp = await self._client.post(
                "https://api.heygen.com/v2/video/av4/generate",
                headers={"X-Api-Key": self._heygen_key, "Content-Type": "application/json"},
                json=payload,
            )

            if resp.status_code != 200:
                return AvatarResult(success=False, error=f"HeyGen submit failed: {resp.text[:200]}")

            video_id = resp.json().get("data", {}).get("video_id")

            # Poll for completion
            video_url = None
            for _ in range(120):
                resp = await self._client.get(
                    f"https://api.heygen.com/v1/video_status.get?video_id={video_id}",
                    headers={"X-Api-Key": self._heygen_key},
                )
                data = resp.json().get("data", {})
                status = data.get("status")

                if status == "completed":
                    video_url = data.get("video_url")
                    break
                elif status == "failed":
                    return AvatarResult(success=False, error=f"HeyGen failed: {data.get('error')}")

                await asyncio.sleep(5)

            if not video_url:
                return AvatarResult(success=False, error="HeyGen timeout")

            # Download video
            resp = await self._client.get(video_url)
            video_path = OUTPUT_DIR / f"avatar_{video_id}.mp4"
            video_path.write_bytes(resp.content)

            # Get duration
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "csv=p=0",
                    str(video_path),
                ],
                capture_output=True,
                text=True,
            )
            duration = float(result.stdout.strip()) if result.stdout.strip() else 0.0

            return AvatarResult(
                success=True,
                video_path=video_path,
                audio_path=audio_result.path,
                duration_s=duration,
            )

        except Exception as e:
            logger.error(f"Avatar generation failed: {e}")
            return AvatarResult(success=False, error=str(e))

    async def generate_video(
        self,
        prompt: str,
        duration: float = 5.0,
    ) -> VideoResult:
        """Generate video from prompt.

        Note: Runway API not yet available, returns placeholder.

        Args:
            prompt: Video description
            duration: Duration in seconds

        Returns:
            VideoResult with video path
        """
        logger.warning("Video generation (Runway) not yet implemented")
        return VideoResult(
            success=False,
            error="Runway video generation not yet implemented",
        )

    async def generate_audio(
        self,
        text: str,
        voice_id: str | None = None,
    ) -> AudioResult:
        """Generate TTS audio.

        Args:
            text: Text to speak
            voice_id: ElevenLabs voice ID (uses default if None)

        Returns:
            AudioResult with audio path
        """
        if not self._initialized:
            await self.initialize()

        if not self._elevenlabs_key:
            return AudioResult(success=False, error="ElevenLabs API key not found")

        # Default to Kagami voice
        if voice_id is None:
            voice_id = _get_secret("elevenlabs_kagami_voice_id") or "21m00Tcm4TlvDq8ikWAM"

        try:
            resp = await self._client.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                headers={
                    "xi-api-key": self._elevenlabs_key,
                    "Content-Type": "application/json",
                },
                json={
                    "text": text,
                    "model_id": "eleven_v3",  # ALWAYS V3 for audio tags
                },
            )

            if resp.status_code != 200:
                return AudioResult(success=False, error=f"ElevenLabs error: {resp.text[:200]}")

            output_path = OUTPUT_DIR / f"audio_{int(time.time() * 1000)}.mp3"
            output_path.write_bytes(resp.content)

            # Get duration
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "csv=p=0",
                    str(output_path),
                ],
                capture_output=True,
                text=True,
            )
            duration = float(result.stdout.strip()) if result.stdout.strip() else 0.0

            return AudioResult(success=True, path=output_path, duration_s=duration)

        except Exception as e:
            logger.error(f"Audio generation failed: {e}")
            return AudioResult(success=False, error=str(e))

    async def generate_favicon(
        self,
        colony: str,
        style: str = "kawaii mascot",
        sizes: list[int] | None = None,
    ) -> FaviconResult:
        """Generate colony favicon using OpenAI gpt-image-1.

        Creates cute mascot icons for each colony with transparent backgrounds.
        Uses chromakey prompts to generate on solid green, then removes background.

        Args:
            colony: Colony name (spark, forge, flow, nexus, beacon, grove, crystal)
            style: Style modifier for the prompt
            sizes: List of output sizes (default: [16, 32, 48, 180, 512])

        Returns:
            FaviconResult with paths to all generated sizes

        Example:
            >>> hub = GenerationHub()
            >>> await hub.initialize()
            >>> result = await hub.generate_favicon("spark")
            >>> print(result.paths[32])  # Path to 32px icon
        """
        if not self._initialized:
            await self.initialize()

        if not self._openai_key:
            return FaviconResult(success=False, colony=colony, error="OpenAI API key not found")

        if colony not in COLONY_FAVICON_PROMPTS:
            return FaviconResult(
                success=False,
                colony=colony,
                error=f"Unknown colony: {colony}. Valid: {list(COLONY_FAVICON_PROMPTS.keys())}",
            )

        if sizes is None:
            sizes = [16, 32, 48, 180, 512]

        colony_info = COLONY_FAVICON_PROMPTS[colony]
        prompt = f"{colony_info['prompt']}, {style}"

        try:
            # Generate master image at 1024x1024 (will downscale)
            logger.info(f"Generating favicon for {colony} colony...")

            resp = await self._client.post(
                "https://api.openai.com/v1/images/generations",
                headers={
                    "Authorization": f"Bearer {self._openai_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": IMAGE_MODEL,  # Global preference
                    "prompt": prompt,
                    "n": 1,
                    "size": "1024x1024",
                    "quality": IMAGE_QUALITY,
                },
            )

            if resp.status_code != 200:
                return FaviconResult(
                    success=False,
                    colony=colony,
                    error=f"OpenAI error: {resp.text[:200]}",
                )

            data = resp.json()
            image_data = data.get("data", [{}])[0]
            b64_image = image_data.get("b64_json")

            master_path = OUTPUT_DIR / f"favicon_{colony}_master.png"

            if b64_image:
                # gpt-image-1.5 returns base64
                import base64

                image_bytes = base64.b64decode(b64_image)
                master_path.write_bytes(image_bytes)
            else:
                # Fallback to URL if available
                image_url = image_data.get("url")
                if not image_url:
                    return FaviconResult(
                        success=False,
                        colony=colony,
                        error="No image data in response",
                    )
                img_resp = await self._client.get(image_url)
                master_path.write_bytes(img_resp.content)

            logger.info(f"Downloaded master favicon for {colony}: {master_path}")

            # Remove background and create sized versions
            paths = await self._process_favicon(master_path, colony, sizes)

            if not paths:
                return FaviconResult(
                    success=False,
                    colony=colony,
                    master_path=master_path,
                    error="Failed to process favicon sizes",
                )

            return FaviconResult(
                success=True,
                colony=colony,
                paths=paths,
                master_path=master_path,
            )

        except Exception as e:
            logger.error(f"Favicon generation failed for {colony}: {e}")
            return FaviconResult(success=False, colony=colony, error=str(e))

    async def _process_favicon(
        self,
        master_path: Path,
        colony: str,
        sizes: list[int],
    ) -> dict[int, Path] | None:
        """Process master favicon: remove background and create sized versions.

        Args:
            master_path: Path to master 1024px image
            colony: Colony name for output naming
            sizes: List of target sizes

        Returns:
            Dict mapping size to output path, or None on failure
        """
        try:
            from PIL import Image

            # Try to use rembg for background removal
            try:
                from rembg import remove as remove_bg

                with Image.open(master_path) as img:
                    # Remove green chromakey background
                    img_no_bg = remove_bg(img)
                    logger.info(f"Background removed using rembg for {colony}")
            except ImportError:
                logger.warning("rembg not available, using chromakey removal fallback")
                img_no_bg = self._chromakey_remove(master_path)

            if img_no_bg is None:
                return None

            # Ensure RGBA mode for transparency
            if img_no_bg.mode != "RGBA":
                img_no_bg = img_no_bg.convert("RGBA")

            # Create sized versions
            paths: dict[int, Path] = {}
            for size in sizes:
                output_path = OUTPUT_DIR / f"favicon_{colony}_{size}.png"

                # Use high-quality LANCZOS resampling
                resized = img_no_bg.resize((size, size), Image.Resampling.LANCZOS)
                resized.save(output_path, "PNG", optimize=True)

                paths[size] = output_path
                logger.info(f"Created {colony} favicon at {size}px: {output_path}")

            return paths

        except Exception as e:
            logger.error(f"Favicon processing failed: {e}")
            return None

    def _chromakey_remove(self, image_path: Path) -> Image.Image | None:
        """Remove green chromakey background using PIL.

        Fallback when rembg is not available.

        Args:
            image_path: Path to image with green background

        Returns:
            PIL Image with transparent background, or None on failure
        """
        try:
            from PIL import Image

            img = Image.open(image_path).convert("RGBA")
            data = img.getdata()

            new_data = []
            for item in data:
                r, g, b, _a = item
                # Detect bright green chromakey (#00FF00 and similar)
                if g > 200 and r < 100 and b < 100:
                    # Make transparent
                    new_data.append((r, g, b, 0))
                else:
                    new_data.append(item)

            img.putdata(new_data)
            return img

        except Exception as e:
            logger.error(f"Chromakey removal failed: {e}")
            return None

    async def dub_video(
        self,
        video_path: Path | str,
        target_languages: list[str],
        source_lang: str = "auto",
        voice_clone: bool = True,
    ) -> dict[str, DubbingResult]:
        """Dub a video into multiple languages.

        Uses ElevenLabs Dubbing API for automatic voice cloning
        and translation with lip-sync.

        Args:
            video_path: Path to video file
            target_languages: List of target language codes (e.g., ["es", "ja"])
            source_lang: Source language code or "auto" for detection
            voice_clone: Clone original voice (vs library voice)

        Returns:
            Dict mapping language code to DubbingResult
        """
        from kagami_studio.generation.dubbing import ElevenLabsDubbing

        dubber = ElevenLabsDubbing()
        await dubber.initialize()

        return await dubber.dub_multiple(
            video_path=video_path,
            target_langs=target_languages,
            source_lang=source_lang,
            voice_clone=voice_clone,
        )

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_hub: GenerationHub | None = None


async def _get_hub() -> GenerationHub:
    """Get or create singleton hub."""
    global _hub
    if _hub is None:
        _hub = GenerationHub()
        await _hub.initialize()
    return _hub


async def generate_image(prompt: str, aspect: str = "16:9") -> ImageResult:
    """Generate an image (convenience function)."""
    hub = await _get_hub()
    return await hub.generate_image(prompt, aspect)


async def generate_avatar(text: str, image_path: Path | None = None) -> AvatarResult:
    """Generate avatar video (convenience function)."""
    hub = await _get_hub()
    return await hub.generate_avatar(text, image_path)


async def generate_video(prompt: str, duration: float = 5.0) -> VideoResult:
    """Generate video (convenience function)."""
    hub = await _get_hub()
    return await hub.generate_video(prompt, duration)


async def generate_audio(text: str, voice_id: str | None = None) -> AudioResult:
    """Generate audio (convenience function)."""
    hub = await _get_hub()
    return await hub.generate_audio(text, voice_id)


async def generate_favicon(colony: str, style: str = "kawaii mascot") -> FaviconResult:
    """Generate colony favicon (convenience function)."""
    hub = await _get_hub()
    return await hub.generate_favicon(colony, style)


__all__ = [
    "COLONY_FAVICON_PROMPTS",
    "AudioResult",
    "AvatarResult",
    "FaviconResult",
    "GenerationHub",
    "ImageResult",
    "VideoResult",
    "generate_audio",
    "generate_avatar",
    "generate_favicon",
    "generate_image",
    "generate_video",
]
