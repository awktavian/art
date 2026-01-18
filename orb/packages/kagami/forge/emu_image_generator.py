from __future__ import annotations

"""Emu3.5 image generation backend for Forge.

Provides T2I and X2I (Any-to-Image) generation using Emu3.5:
- Text-to-Image with superior text rendering (English + Chinese)
- Any-to-Image editing with high consistency
- Fast inference via DiDA (20× faster than AR baseline)
- Up to 2K resolution support

This can be used as a drop-in replacement for FLUX/OpenAI backends.
"""

import asyncio
import logging
import os
from pathlib import Path

from PIL import Image

from kagami.core.config import get_config

logger = logging.getLogger(__name__)


class EmuImageGenerator:
    """Emu3.5 image generation backend.

    Modes:
    - T2I: Text-to-image generation
    - X2I: Any-to-image editing (with reference images)

    Features:
    - 1024×1024 default resolution
    - DiDA acceleration (20× faster)
    - Text rendering (English + Chinese)
    - Multiple reference images supported
    """

    def __init__(self) -> None:
        from pathlib import Path as PathLib

        self.enabled = os.getenv("EMU_IMAGE_GEN_ENABLED", "1") == "1"

        # Emu3.5 repo path
        default_emu_repo = PathLib.home() / "dev" / "Emu3.5"
        emu_repo_env = get_config("EMU_REPO_PATH", "")
        self.emu_repo_path = PathLib(emu_repo_env or default_emu_repo)

        # Model cache (use same location as EmuWorldService)
        self.model_cache = PathLib.home() / ".cache" / "kagami" / "emu3.5"
        self.model_cache.mkdir(parents=True, exist_ok=True)

        # Inference engine (lazy-loaded)
        self._engine = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize Emu3.5 for image generation - PRODUCTION ONLY."""
        if self._initialized:
            return

        if not self.enabled:
            raise RuntimeError("EmuImageGenerator disabled - set[Any] EMU_IMAGE_GEN_ENABLED=1")

        # Check repo exists
        if not self.emu_repo_path.exists():
            raise RuntimeError(
                f"Emu3.5 repo not found at {self.emu_repo_path}\n"
                "Setup: make forge-emu (or set[Any] EMU_REPO_PATH to an existing checkout)"
            )

        # Initialize real inference (NO TEST MODE)
        from kagami.core.services.world.emu_inference import Emu3InferenceEngine

        # Download models if needed
        await self._ensure_models_downloaded()

        # Create engine
        self._engine = Emu3InferenceEngine(self.emu_repo_path, self.model_cache)  # type: ignore[assignment]
        await self._engine.initialize()  # type: ignore[attr-defined]

        logger.info("✅ EmuImageGenerator initialized with real Emu3.5 inference on MPS")
        self._initialized = True

    async def _ensure_models_downloaded(self) -> None:
        """Download Emu3.5 models if not cached."""
        from huggingface_hub import snapshot_download

        model_id = "BAAI/Emu3.5"
        cache_dir = str(self.model_cache / "models")

        if (Path(cache_dir) / "model_index.json").exists():
            logger.debug("Emu3.5 models already cached")
            return

        logger.info(f"Downloading Emu3.5 models to {cache_dir}...")
        await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: snapshot_download(model_id, cache_dir=cache_dir, local_dir_use_symlinks=False),
        )
        logger.info("✅ Emu3.5 models downloaded")

    async def generate_image(
        self,
        prompt: str,
        *,
        width: int = 1024,
        height: int = 1024,
        reference_images: list[str | Image.Image] | None = None,
        mode: str = "t2i",  # t2i or x2i
        guidance_scale: float = 7.5,
        num_inference_steps: int = 50,
    ) -> Image.Image:
        """Generate image using Emu3.5.

        Args:
            prompt: Text description
            width: Output width (unused - Emu determines size)
            height: Output height (unused - Emu determines size)
            reference_images: Optional reference images for X2I
            mode: Generation mode (t2i or x2i)
            guidance_scale: Guidance strength (T2I: 2.0, X2I: 5.0)
            num_inference_steps: Number of denoising steps (unused - Emu uses DiDA)

        Returns:
            Generated PIL Image
        """
        # Emu3.5 determines size internally; these params maintained for API compatibility
        del width, height, num_inference_steps

        if not self._initialized:
            await self.initialize()

        # Ensure engine is initialized
        if self._engine is None:
            raise RuntimeError("Emu3.5 inference engine not initialized")

        # Prepare reference image
        reference_image = None  # type: ignore[unreachable]
        if reference_images:
            ref = reference_images[0]
            if isinstance(ref, str):
                reference_image = Image.open(ref).convert("RGB")
            else:
                reference_image = ref

        # Generate using real Emu3.5
        results = await self._engine.generate(
            prompt=prompt,
            mode=mode,
            reference_image=reference_image,
            guidance_scale=guidance_scale if mode == "x2i" else 2.0,
        )

        # Extract first image from results
        for item in results:
            if item["type"] == "image":
                return item["content"]

        raise RuntimeError("No image generated")


# Singleton
_emu_image_generator: EmuImageGenerator | None = None


def get_emu_image_generator() -> EmuImageGenerator:
    """Get global EmuImageGenerator instance."""
    global _emu_image_generator
    if _emu_image_generator is None:
        _emu_image_generator = EmuImageGenerator()
    return _emu_image_generator
