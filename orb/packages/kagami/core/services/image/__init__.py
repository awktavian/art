"""Image Generation Service.

Provides unified access to image generation with:
- OpenAI gpt-image-1.5 (default, fast, high quality, best instruction adherence)
- FLUX.1 local fallback (free, requires GPU)

Usage:
    from kagami.core.services.image import get_image_service

    service = get_image_service()
    await service.initialize()

    # Generate image (uses OpenAI by default)
    result = await service.generate(
        prompt="A serene Japanese garden at sunset",
        quality="medium",
    )

    # Force local FLUX
    result = await service.generate(
        prompt="...",
        provider="flux",
    )

Models:
    - gpt-image-1.5: OpenAI's latest, ~12s, $0.02-0.19/image, enhanced editing
    - FLUX.1-schnell: Fast local, ~5-10s on M3 Ultra
    - FLUX.1-dev: Quality local, ~30-60s on M3 Ultra
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from io import BytesIO
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================


class ImageProvider(str, Enum):
    """Available image generation providers."""

    OPENAI = "openai"  # gpt-image-1.5 (default)
    FLUX_SCHNELL = "flux_schnell"  # Fast local
    FLUX_DEV = "flux_dev"  # Quality local
    AUTO = "auto"  # OpenAI if available, else FLUX


class ImageQuality(str, Enum):
    """Image quality levels (for OpenAI)."""

    LOW = "low"  # $0.02 - fastest
    MEDIUM = "medium"  # $0.07 - balanced
    HIGH = "high"  # $0.19 - best quality


class ImageSize(str, Enum):
    """Image size presets."""

    SQUARE = "1024x1024"
    PORTRAIT = "1024x1536"
    LANDSCAPE = "1536x1024"


@dataclass
class ImageConfig:
    """Image service configuration."""

    # Provider settings
    default_provider: ImageProvider = ImageProvider.AUTO
    openai_api_key: str | None = None

    # OpenAI settings
    openai_model: str = "gpt-image-1.5"
    default_quality: ImageQuality = ImageQuality.MEDIUM
    default_size: ImageSize = ImageSize.SQUARE

    # FLUX settings
    flux_model: str = "black-forest-labs/FLUX.1-schnell"
    flux_device: str = "mps"  # mps for M3 Ultra, cuda for NVIDIA
    flux_dtype: str = "float16"
    flux_steps: int = 4  # schnell uses fewer steps
    flux_guidance: float = 0.0  # schnell doesn't need guidance

    # Performance
    enable_cpu_offload: bool = True
    cache_dir: str | None = None


@dataclass
class ImageResult:
    """Result from image generation."""

    success: bool
    image_data: bytes | None = None
    image_url: str | None = None
    image_path: str | None = None
    provider: str = ""
    model: str = ""
    generation_time: float = 0.0
    cost_usd: float = 0.0
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# OPENAI CLIENT
# =============================================================================


class OpenAIImageClient:
    """OpenAI gpt-image-1.5 client."""

    def __init__(self, config: ImageConfig) -> None:
        self.config = config
        self._client: Any = None
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize OpenAI client."""
        api_key = self.config.openai_api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.info("OPENAI_API_KEY not found. OpenAI image generation disabled.")
            return False

        try:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(api_key=api_key)
            self._initialized = True
            logger.info("✅ OpenAI image client initialized (model=%s)", self.config.openai_model)
            return True
        except ImportError:
            logger.warning("openai package not installed. Run: pip install openai")
            return False
        except Exception as e:
            logger.warning(f"OpenAI initialization failed: {e}")
            return False

    async def generate(
        self,
        prompt: str,
        quality: ImageQuality | None = None,
        size: ImageSize | None = None,
    ) -> ImageResult:
        """Generate image using gpt-image-1.5."""
        if not self._initialized or self._client is None:
            return ImageResult(
                success=False,
                error="OpenAI client not initialized",
                provider="openai",
            )

        quality = quality or self.config.default_quality
        size = size or self.config.default_size

        start = time.time()
        try:
            # gpt-image-1.5 params
            response = await self._client.images.generate(
                model=self.config.openai_model,
                prompt=prompt,
                n=1,
                size=size.value,
                quality=quality.value,
            )

            # Extract image data from response
            image_b64 = response.data[0].b64_json
            if image_b64:
                image_data = base64.b64decode(image_b64)
            else:
                # Fallback: might return URL instead
                image_url = response.data[0].url
                if image_url:
                    import httpx

                    async with httpx.AsyncClient() as client:
                        img_resp = await client.get(image_url)
                        image_data = img_resp.content
                else:
                    raise ValueError("No image data in response")

            gen_time = time.time() - start

            # Calculate cost
            cost = self._calculate_cost(quality, size)

            return ImageResult(
                success=True,
                image_data=image_data,
                provider="openai",
                model=self.config.openai_model,
                generation_time=gen_time,
                cost_usd=cost,
                metadata={
                    "quality": quality.value,
                    "size": size.value,
                    "revised_prompt": getattr(response.data[0], "revised_prompt", None),
                },
            )
        except Exception as e:
            return ImageResult(
                success=False,
                error=str(e),
                provider="openai",
                model=self.config.openai_model,
                generation_time=time.time() - start,
            )

    def _calculate_cost(self, quality: ImageQuality, size: ImageSize) -> float:
        """Calculate cost based on quality and size."""
        # Base costs for 1024x1024
        base_costs = {
            ImageQuality.LOW: 0.02,
            ImageQuality.MEDIUM: 0.07,
            ImageQuality.HIGH: 0.19,
        }
        cost = base_costs.get(quality, 0.07)

        # Adjust for size (larger = more tokens)
        if size == ImageSize.PORTRAIT or size == ImageSize.LANDSCAPE:
            cost *= 1.5

        return cost


# =============================================================================
# FLUX LOCAL CLIENT
# =============================================================================


class FLUXLocalClient:
    """FLUX.1 local image generation client.

    Supports:
    - FLUX.1-schnell: Fast, 4 steps, no guidance (best for M3 Ultra)
    - FLUX.1-dev: Quality, 50 steps, guidance=3.5
    """

    def __init__(self, config: ImageConfig) -> None:
        self.config = config
        self._pipe: Any = None
        self._initialized = False
        self._model_loaded: str | None = None

    async def initialize(self) -> bool:
        """Initialize FLUX pipeline (lazy load on first use)."""
        # Just check if diffusers is available
        try:
            import diffusers

            self._initialized = True
            logger.info("✅ FLUX client ready (lazy load on first use)")
            return True
        except ImportError:
            logger.warning("diffusers not installed. Run: pip install diffusers transformers")
            return False

    def _load_model(self, model_name: str) -> bool:
        """Load FLUX model (blocking, called from thread)."""
        if self._model_loaded == model_name:
            return True

        try:
            import torch
            from diffusers import FluxPipeline

            logger.info(f"Loading FLUX model: {model_name}...")

            # Determine device and dtype
            device = self.config.flux_device
            if device == "mps" and not torch.backends.mps.is_available():
                device = "cpu"
                logger.warning("MPS not available, falling back to CPU")
            elif device == "cuda" and not torch.cuda.is_available():
                device = "cpu"
                logger.warning("CUDA not available, falling back to CPU")

            dtype = torch.float16 if self.config.flux_dtype == "float16" else torch.float32

            # Load pipeline
            self._pipe = FluxPipeline.from_pretrained(
                model_name,
                torch_dtype=dtype,
                cache_dir=self.config.cache_dir,
            )

            # Optimize for device
            if device == "mps":
                self._pipe = self._pipe.to("mps")
                # MPS-specific optimizations
                self._pipe.enable_attention_slicing()
            elif device == "cuda":
                self._pipe = self._pipe.to("cuda")
                if self.config.enable_cpu_offload:
                    self._pipe.enable_model_cpu_offload()
            else:
                self._pipe = self._pipe.to("cpu")

            self._model_loaded = model_name
            logger.info(f"✅ FLUX model loaded on {device}")
            return True

        except Exception as e:
            logger.error(f"Failed to load FLUX model: {e}")
            return False

    async def generate(
        self,
        prompt: str,
        model: str | None = None,
        width: int = 1024,
        height: int = 1024,
        steps: int | None = None,
        guidance: float | None = None,
    ) -> ImageResult:
        """Generate image using FLUX locally."""
        if not self._initialized:
            return ImageResult(
                success=False,
                error="FLUX client not initialized",
                provider="flux",
            )

        model_name = model or self.config.flux_model
        is_schnell = "schnell" in model_name.lower()

        # Use appropriate defaults for model type
        if steps is None:
            steps = 4 if is_schnell else 50
        if guidance is None:
            guidance = 0.0 if is_schnell else 3.5

        start = time.time()

        # Load model in thread pool (blocking operation)
        loop = asyncio.get_event_loop()
        loaded = await loop.run_in_executor(None, self._load_model, model_name)

        if not loaded:
            return ImageResult(
                success=False,
                error="Failed to load FLUX model",
                provider="flux",
                model=model_name,
            )

        try:
            # Generate in thread pool
            def _generate() -> Any:
                return self._pipe(
                    prompt,
                    height=height,
                    width=width,
                    guidance_scale=guidance,
                    num_inference_steps=steps,
                ).images[0]

            image = await loop.run_in_executor(None, _generate)
            gen_time = time.time() - start

            # Convert PIL to bytes
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            image_data = buffer.getvalue()

            return ImageResult(
                success=True,
                image_data=image_data,
                provider="flux",
                model=model_name,
                generation_time=gen_time,
                cost_usd=0.0,  # Free local generation
                metadata={
                    "width": width,
                    "height": height,
                    "steps": steps,
                    "guidance": guidance,
                    "device": self.config.flux_device,
                },
            )

        except Exception as e:
            return ImageResult(
                success=False,
                error=str(e),
                provider="flux",
                model=model_name,
                generation_time=time.time() - start,
            )


# =============================================================================
# UNIFIED IMAGE SERVICE
# =============================================================================


class ImageService:
    """Unified image generation service.

    Uses OpenAI gpt-image-1.5 by default (fast, high quality).
    Falls back to FLUX.1-schnell for local generation.
    """

    def __init__(self, config: ImageConfig | None = None) -> None:
        self.config = config or ImageConfig()
        self._openai = OpenAIImageClient(self.config)
        self._flux = FLUXLocalClient(self.config)
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize available providers."""
        openai_ok = await self._openai.initialize()
        flux_ok = await self._flux.initialize()

        self._initialized = openai_ok or flux_ok

        if self._initialized:
            providers = []
            if openai_ok:
                providers.append("openai")
            if flux_ok:
                providers.append("flux")
            logger.info(f"✅ ImageService initialized: {providers}")
        else:
            logger.warning("⚠️ No image providers available")

        return self._initialized

    async def generate(
        self,
        prompt: str,
        provider: str | ImageProvider | None = None,
        quality: str | ImageQuality | None = None,
        size: str | ImageSize | None = None,
        save_path: str | None = None,
        **kwargs: Any,
    ) -> ImageResult:
        """Generate an image.

        Args:
            prompt: Text description of the image
            provider: Which provider to use (auto, openai, flux_schnell, flux_dev)
            quality: Quality level for OpenAI (low, medium, high)
            size: Image size (1024x1024, 1024x1536, 1536x1024)
            save_path: Optional path to save the image
            **kwargs: Additional provider-specific arguments

        Returns:
            ImageResult with image data or error
        """
        if not self._initialized:
            return ImageResult(success=False, error="ImageService not initialized")

        # Normalize provider
        if provider is None:
            provider = self.config.default_provider
        elif isinstance(provider, str):
            provider = ImageProvider(provider.lower())

        # Normalize quality/size for OpenAI
        if quality and isinstance(quality, str):
            quality = ImageQuality(quality.lower())
        if size and isinstance(size, str):
            size = ImageSize(size)

        # Route to provider
        result: ImageResult

        if provider == ImageProvider.OPENAI:
            result = await self._openai.generate(prompt, quality, size)
        elif provider == ImageProvider.FLUX_SCHNELL:
            result = await self._flux.generate(
                prompt,
                model="black-forest-labs/FLUX.1-schnell",
                **kwargs,
            )
        elif provider == ImageProvider.FLUX_DEV:
            result = await self._flux.generate(
                prompt,
                model="black-forest-labs/FLUX.1-dev",
                **kwargs,
            )
        elif provider == ImageProvider.AUTO:
            # Try OpenAI first, fall back to FLUX
            if self._openai._initialized:
                result = await self._openai.generate(prompt, quality, size)
            elif self._flux._initialized:
                result = await self._flux.generate(prompt, **kwargs)
            else:
                result = ImageResult(success=False, error="No providers available")
        else:
            result = ImageResult(success=False, error=f"Unknown provider: {provider}")

        # Save if requested
        if result.success and result.image_data and save_path:
            try:
                path = Path(save_path)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(result.image_data)
                result.image_path = str(path)
                logger.info(f"Image saved to {path}")
            except Exception as e:
                logger.warning(f"Failed to save image: {e}")

        return result

    async def generate_with_fallback(
        self,
        prompt: str,
        **kwargs: Any,
    ) -> ImageResult:
        """Generate with automatic fallback.

        Tries OpenAI first, falls back to FLUX if it fails.
        """
        # Try OpenAI
        if self._openai._initialized:
            result = await self._openai.generate(
                prompt,
                kwargs.get("quality"),
                kwargs.get("size"),
            )
            if result.success:
                return result
            logger.warning(f"OpenAI failed: {result.error}, trying FLUX...")

        # Fallback to FLUX
        if self._flux._initialized:
            return await self._flux.generate(prompt, **kwargs)

        return ImageResult(success=False, error="All providers failed")


# =============================================================================
# SINGLETON
# =============================================================================

_image_service: ImageService | None = None


def get_image_service() -> ImageService:
    """Get global ImageService instance."""
    global _image_service
    if _image_service is None:
        _image_service = ImageService()
    return _image_service


def reset_image_service() -> None:
    """Reset global instance."""
    global _image_service
    _image_service = None


__all__ = [
    "ImageConfig",
    "ImageProvider",
    "ImageQuality",
    "ImageResult",
    "ImageService",
    "ImageSize",
    "get_image_service",
    "reset_image_service",
]
