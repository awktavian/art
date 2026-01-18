"""Image Generation — OpenAI gpt-image-1.5.

Global image model: gpt-image-1.5 (highest quality, best results)

Usage:
    from kagami_studio.generation.image import generate_image

    path = await generate_image(
        prompt="A sunset over mountains",
        output_path="/tmp/image.png",
    )

Created: 2026-01-05
Updated: 2026-01-10 - Switched to gpt-image-1.5 as global default
"""

from __future__ import annotations

import base64
import logging
import os
import time
from pathlib import Path
from typing import Literal

import aiohttp

logger = logging.getLogger(__name__)


# === GLOBAL IMAGE MODEL PREFERENCES ===
# These settings are respected across all image generation

IMAGE_MODEL = "gpt-image-1.5"  # ALWAYS use gpt-image-1.5
IMAGE_QUALITY = "high"  # high quality by default
IMAGE_STYLE = "vivid"  # vivid style by default

# === GLOBAL SAFETY PROMPTS ===
# These are appended to ALL image prompts to prevent creepy imagery

SAFETY_SUFFIX = (
    " Style: warm, friendly, modern illustration. "
    "Avoid: skulls, exposed bones, teeth, x-rays, anatomical cross-sections, "
    "medical imagery, body horror, creepy faces, uncanny valley."
)


def sanitize_prompt(prompt: str) -> str:
    """Add safety suffix to prevent creepy/medical imagery.

    This ensures all generated images are warm and approachable,
    not clinical or unsettling.
    """
    # Don't double-add if already sanitized
    if "Avoid:" in prompt or "avoid:" in prompt:
        return prompt
    return prompt.strip() + SAFETY_SUFFIX


class ImageGenerator:
    """OpenAI gpt-image-1.5 image generator.

    ALWAYS uses gpt-image-1.5 model for best quality.
    """

    def __init__(self, openai_key: str | None = None):
        """Initialize with OpenAI API key."""
        self.openai_key = openai_key or os.getenv("OPENAI_API_KEY")
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def generate(
        self,
        prompt: str,
        *,
        size: Literal["1024x1024", "1024x1536", "1536x1024", "auto"] = "1536x1024",
        quality: Literal["standard", "high"] = IMAGE_QUALITY,
    ) -> bytes:
        """Generate image using gpt-image-1.5.

        gpt-image-1.5 supported sizes: 1024x1024, 1024x1536, 1536x1024, auto

        Args:
            prompt: Image description
            size: Output dimensions (landscape: 1536x1024, portrait: 1024x1536, square: 1024x1024)
            quality: Image quality (high recommended)

        Returns:
            Image bytes (PNG)
        """
        if not self.openai_key:
            raise RuntimeError("OPENAI_API_KEY not set")

        session = await self._get_session()

        payload = {
            "model": IMAGE_MODEL,  # GLOBAL: Always gpt-image-1.5
            "prompt": prompt,
            "n": 1,
            "size": size,
            "quality": quality,
        }

        headers = {
            "Authorization": f"Bearer {self.openai_key}",
            "Content-Type": "application/json",
        }

        # Apply safety sanitization to prevent creepy imagery
        safe_prompt = sanitize_prompt(prompt)
        payload["prompt"] = safe_prompt

        logger.info(f"Generating with {IMAGE_MODEL}: {prompt[:60]}...")

        async with session.post(
            "https://api.openai.com/v1/images/generations",
            json=payload,
            headers=headers,
        ) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                raise RuntimeError(f"{IMAGE_MODEL} error: {resp.status} - {error_text[:200]}")

            data = await resp.json()
            image_data = data.get("data", [{}])[0]

            # gpt-image-1.5 returns base64
            b64_image = image_data.get("b64_json")
            if b64_image:
                logger.info(f"✓ {IMAGE_MODEL} generated (base64)")
                return base64.b64decode(b64_image)

            # Fallback to URL if available
            image_url = image_data.get("url")
            if image_url:
                logger.info(f"✓ {IMAGE_MODEL} generated (URL)")
                async with session.get(image_url) as img_resp:
                    if img_resp.status == 200:
                        return await img_resp.read()

            raise RuntimeError("No image data in response")

    async def close(self) -> None:
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()


# === SINGLETON INSTANCE ===

_generator: ImageGenerator | None = None


def get_image_generator() -> ImageGenerator:
    """Get singleton image generator."""
    global _generator
    if _generator is None:
        _generator = ImageGenerator()
    return _generator


async def generate_image(
    prompt: str,
    width: int = 1920,
    height: int = 1080,
    output_path: str | Path | None = None,
    quality: Literal["standard", "high"] = IMAGE_QUALITY,
) -> Path | None:
    """Generate image and save to file.

    ALWAYS uses gpt-image-1.5 model.

    Args:
        prompt: Image description (be detailed for best results)
        width: Desired width (maps to closest supported size)
        height: Desired height (maps to closest supported size)
        output_path: Where to save image
        quality: Image quality

    Returns:
        Path to saved image, or None if failed
    """
    generator = get_image_generator()

    # Map dimensions to gpt-image-1.5 supported sizes
    # Supported: 1024x1024, 1024x1536, 1536x1024, auto
    aspect = width / height
    if aspect > 1.2:
        size: Literal["1024x1024", "1024x1536", "1536x1024", "auto"] = "1536x1024"  # Landscape
    elif aspect < 0.8:
        size = "1024x1536"  # Portrait
    else:
        size = "1024x1024"  # Square

    # Determine output path
    if output_path:
        save_path = Path(output_path)
    else:
        save_path = Path(f"/tmp/kagami_slides/images/gen_{int(time.time() * 1000)}.png")

    save_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Generate image
        image_bytes = await generator.generate(
            prompt=prompt,
            size=size,
            quality=quality,
        )

        # Save to file
        save_path.write_bytes(image_bytes)
        logger.info(f"✓ Saved: {save_path.name} ({len(image_bytes) / 1024:.0f}KB)")
        return save_path

    except Exception as e:
        logger.error(f"Image generation failed: {e}")
        return None


__all__ = [
    "IMAGE_MODEL",
    "IMAGE_QUALITY",
    "ImageGenerator",
    "generate_image",
    "get_image_generator",
]
