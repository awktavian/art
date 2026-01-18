from __future__ import annotations

"""Optimized image generator - Emu3.5 PRIMARY.

Emu3.5 is the default and primary provider:
- Superior text rendering (EN + ZH + formulas)
- Any-to-Image (X2I) editing
- Up to 2K resolution
- 20× faster with DiDA

OpenAI gpt-image-1 is supported, but only when explicitly requested.

This module is **fail-fast** by default: we do not silently fall back to a
different provider on errors, because that masks wiring/config problems.
"""

import asyncio
import base64
import logging
import os
from dataclasses import dataclass

import torch
from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class ImageGenConfig:
    model_id: str = "black-forest-labs/FLUX.1-dev"
    guidance_scale: float = 0.5
    num_inference_steps: int = int(os.getenv("FORGE_IMAGE_MAX_STEPS", "12"))
    width: int = int(os.getenv("FORGE_IMAGE_WIDTH", "1024"))
    height: int = int(os.getenv("FORGE_IMAGE_HEIGHT", "1024"))
    provider: str = "emu"  # Emu3.5 is PRIMARY


class OptimizedImageGenerator:
    """Image generator with Emu3.5 as primary provider."""

    def __init__(self, device: torch.device, config: ImageGenConfig | None = None) -> None:
        self.device = device
        self.config = config or ImageGenConfig()
        self._pipeline = None
        self.openai_client = None
        self.initialized = False

        # Optional OpenAI client (explicit provider selection only).
        try:
            from openai import OpenAI

            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                self.openai_client = OpenAI(api_key=api_key)
        except Exception:
            pass

    async def initialize(self) -> None:
        """Initialize generator (Emu3.5 loads on-demand)."""
        self.initialized = True
        logger.info("✅ OptimizedImageGenerator initialized (Emu3.5 PRIMARY)")

    async def generate_image(
        self,
        prompt: str,
        *,
        width: int | None = None,
        height: int | None = None,
        use_local: bool = True,
        request_timeout_seconds: float | None = None,
        reference_images: list[str | Image.Image] | None = None,
    ) -> Image.Image:
        """Generate an image.

        Provider selection is explicit:
        - ``use_local=True``  -> Emu3.5 only (fail-fast)
        - ``use_local=False`` -> OpenAI gpt-image-1 only (fail-fast)
        """
        gen_width = int(width if width is not None else self.config.width)
        gen_height = int(height if height is not None else self.config.height)

        if use_local:
            from kagami.forge.emu_image_generator import get_emu_image_generator

            emu_gen = get_emu_image_generator()
            if not emu_gen._initialized:
                await emu_gen.initialize()

            mode = "x2i" if reference_images else "t2i"
            return await emu_gen.generate_image(
                prompt,
                width=gen_width,
                height=gen_height,
                reference_images=reference_images,
                mode=mode,
            )

        # OpenAI gpt-image-1 (explicit)
        if self.openai_client is not None:
            if not isinstance(prompt, str) or not prompt.strip():
                prompt = "K os mascot, Neo-Kawaii Futurism, pure white background"

            # Coerce to OpenAI sizes
            if gen_width >= gen_height:
                size = "1024x1024" if gen_width == gen_height else "1536x1024"
            else:
                size = "1024x1536"

            try:
                logger.info(f"Using OpenAI gpt-image-1.5 (size={size})")
                loop = asyncio.get_running_loop()
                fut = loop.run_in_executor(
                    None,
                    lambda: self.openai_client.images.generate(  # type: ignore[union-attr, call-overload]
                        model="gpt-image-1.5",
                        prompt=prompt,
                        size=size,
                        quality="high",
                    ),
                )

                if request_timeout_seconds and request_timeout_seconds > 0:
                    resp = await asyncio.wait_for(fut, timeout=float(request_timeout_seconds))
                else:
                    resp = await fut

                b64 = getattr(resp.data[0], "b64_json", None)
                if not isinstance(b64, str):
                    raise RuntimeError("Invalid response from OpenAI")

                raw = base64.b64decode(b64)
                from io import BytesIO

                return Image.open(BytesIO(raw)).convert("RGBA")

            except Exception as e:
                logger.error(f"OpenAI image generation failed: {e}")
                raise

        # No providers available
        raise RuntimeError(
            "No image generation providers available. "
            "Requested OpenAI provider but OPENAI_API_KEY is not configured."
        )

    async def generate_for_3d(
        self,
        prompt: str,
        *,
        view: str = "front",
        style: str = "photorealistic",
        width: int | None = None,
        height: int | None = None,
        reference_images: list[str | Image.Image] | None = None,
        request_timeout_seconds: float | None = None,
        use_local: bool = True,
    ) -> Image.Image:
        """Generate an image optimized for downstream 3D reconstruction.

        The Forge 3D pipeline expects this API (`generate_for_3d`); earlier
        code referenced it but it did not exist, which broke wiring.
        """
        view_hint = (view or "front").strip().lower()
        view_phrase = {
            "front": "front view",
            "side": "side profile view",
            "left": "left side view",
            "right": "right side view",
            "back": "back view",
            "rear": "back view",
            "three_quarter": "three-quarter view",
            "3/4": "three-quarter view",
            "quarter": "three-quarter view",
            "top": "top-down view",
            "bottom": "bottom-up view",
        }.get(view_hint, f"{view_hint} view")

        style_phrase = (style or "photorealistic").strip()

        shaped = (
            f"{prompt}, {style_phrase}, {view_phrase}, "
            "single centered subject, full object in frame, "
            "plain white background, even studio lighting, sharp focus, "
            "no text, no watermark, no logo, no clutter"
        )

        return await self.generate_image(
            shaped,
            width=width,
            height=height,
            use_local=use_local,
            request_timeout_seconds=request_timeout_seconds,
            reference_images=reference_images,
        )
