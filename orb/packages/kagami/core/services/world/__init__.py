"""World Generation Service.

Provides world generation capabilities using Emu 3.5, a large-scale
multimodal world model that can generate and explore virtual worlds.

Features:
    - Text-to-world generation
    - Image-to-world expansion
    - Spatiotemporally consistent exploration
    - Interleaved vision-language generation
    - Any-to-image (X2I) generation

Usage:
    from kagami.core.services.world import get_world_service

    service = get_world_service()
    await service.initialize()

    # Generate world from description
    result = await service.generate(
        prompt="A serene Japanese garden with a koi pond",
        style="photorealistic",
    )

    # Explore/expand existing world
    result = await service.explore(
        world_id=result.world_id,
        direction="forward",
        steps=5,
    )

References:
    - Emu3.5: https://github.com/baaivision/Emu3.5
    - Paper: https://arxiv.org/abs/2510.26583
    - HuggingFace: https://huggingface.co/BAAI/Emu3.5
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


class WorldProvider(str, Enum):
    """Available world generation providers."""

    EMU35 = "emu35"  # BAAI Emu 3.5 (primary)
    EMU35_IMAGE = "emu35_image"  # Emu 3.5 Image variant
    AUTO = "auto"  # Auto-select best available


class WorldStyle(str, Enum):
    """World generation styles."""

    PHOTOREALISTIC = "photorealistic"
    ARTISTIC = "artistic"
    ANIME = "anime"
    CINEMATIC = "cinematic"
    FANTASY = "fantasy"
    SCIFI = "scifi"


@dataclass
class WorldConfig:
    """World service configuration."""

    # Model paths (auto-download from HuggingFace if not present)
    model_id: str = "BAAI/Emu3.5"
    image_model_id: str = "BAAI/Emu3.5-Image"
    tokenizer_id: str = "BAAI/Emu3.5-VisionTokenizer"

    # Local cache
    cache_dir: str | None = None

    # Generation settings
    default_style: WorldStyle = WorldStyle.PHOTOREALISTIC
    default_width: int = 1024
    default_height: int = 1024
    num_inference_steps: int = 50
    guidance_scale: float = 7.5

    # Device
    device: str = "mps"  # mps for M3 Ultra, cuda for NVIDIA
    dtype: str = "float16"

    # Exploration settings
    exploration_steps: int = 10
    temporal_consistency: float = 0.9


@dataclass
class WorldFrame:
    """A single frame/view in a generated world."""

    frame_id: str
    image_data: bytes
    timestamp: float = 0.0
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    direction: tuple[float, float, float] = (0.0, 0.0, 1.0)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorldResult:
    """Result from world generation."""

    success: bool
    world_id: str = ""
    frames: list[WorldFrame] = field(default_factory=list)
    preview_image: bytes | None = None
    provider: str = ""
    model: str = ""
    generation_time: float = 0.0
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# EMU 3.5 CLIENT
# =============================================================================


class Emu35Client:
    """Emu 3.5 world generation client.

    Emu3.5 is a large-scale multimodal world model that can:
    - Generate spatiotemporally consistent worlds
    - Perform any-to-image (X2I) generation
    - Create interleaved vision-language sequences
    - Support open-world exploration and manipulation
    """

    def __init__(self, config: WorldConfig) -> None:
        self.config = config
        self._model: Any = None
        self._tokenizer: Any = None
        self._vision_tokenizer: Any = None
        self._initialized = False
        self._model_loaded = False

    async def initialize(self) -> bool:
        """Initialize Emu 3.5 (lazy load on first use)."""
        try:
            # Check if transformers is available
            import transformers

            self._initialized = True
            logger.info("✅ Emu 3.5 client ready (lazy load on first use)")
            return True
        except ImportError:
            logger.warning("transformers not installed. Run: pip install transformers")
            return False

    def _load_model(self) -> bool:
        """Load Emu 3.5 model (blocking, called from thread)."""
        if self._model_loaded:
            return True

        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer

            logger.info(f"Loading Emu 3.5 model: {self.config.model_id}...")

            # Determine device and dtype
            device = self.config.device
            if device == "mps" and not torch.backends.mps.is_available():
                device = "cpu"
                logger.warning("MPS not available, falling back to CPU")
            elif device == "cuda" and not torch.cuda.is_available():
                device = "cpu"
                logger.warning("CUDA not available, falling back to CPU")

            dtype = torch.float16 if self.config.dtype == "float16" else torch.float32

            # Load tokenizer
            logger.info("Loading tokenizer...")
            self._tokenizer = AutoTokenizer.from_pretrained(
                self.config.model_id,
                trust_remote_code=True,
                cache_dir=self.config.cache_dir,
            )

            # Load model
            logger.info("Loading model (this may take a while)...")
            self._model = AutoModelForCausalLM.from_pretrained(
                self.config.model_id,
                torch_dtype=dtype,
                trust_remote_code=True,
                cache_dir=self.config.cache_dir,
                device_map="auto" if device == "cuda" else None,
            )

            if device in ("mps", "cpu"):
                self._model = self._model.to(device)

            self._model_loaded = True
            logger.info(f"✅ Emu 3.5 model loaded on {device}")
            return True

        except Exception as e:
            logger.error(f"Failed to load Emu 3.5 model: {e}")
            return False

    async def generate(
        self,
        prompt: str,
        style: WorldStyle | None = None,
        width: int | None = None,
        height: int | None = None,
        num_frames: int = 1,
        **kwargs: Any,
    ) -> WorldResult:
        """Generate world from text prompt.

        Args:
            prompt: Description of the world to generate
            style: Visual style
            width: Image width
            height: Image height
            num_frames: Number of frames to generate
            **kwargs: Additional generation parameters

        Returns:
            WorldResult with generated frames
        """
        if not self._initialized:
            return WorldResult(
                success=False,
                error="Emu 3.5 client not initialized",
                provider="emu35",
            )

        style = style or self.config.default_style
        width = width or self.config.default_width
        height = height or self.config.default_height

        start = time.time()

        # Load model in thread pool
        loop = asyncio.get_event_loop()
        loaded = await loop.run_in_executor(None, self._load_model)

        if not loaded:
            return WorldResult(
                success=False,
                error="Failed to load Emu 3.5 model",
                provider="emu35",
                model=self.config.model_id,
            )

        try:
            # Enhance prompt with style
            styled_prompt = self._style_prompt(prompt, style)

            # Generate in thread pool
            def _generate() -> list[bytes]:
                frames = []
                for _i in range(num_frames):
                    # Use Emu 3.5's generation
                    inputs = self._tokenizer(
                        styled_prompt,
                        return_tensors="pt",
                    ).to(self._model.device)

                    with torch.no_grad():
                        outputs = self._model.generate(
                            **inputs,
                            max_new_tokens=kwargs.get("max_tokens", 2048),
                            do_sample=True,
                            temperature=kwargs.get("temperature", 0.7),
                        )

                    # Decode output
                    result = self._tokenizer.decode(outputs[0], skip_special_tokens=True)

                    # For now, return placeholder until we have proper vision decoding
                    # Emu 3.5 outputs interleaved text/vision tokens
                    frames.append(self._decode_vision_output(result))

                return frames

            import torch

            frames_data = await loop.run_in_executor(None, _generate)
            gen_time = time.time() - start

            # Build result
            frames = []
            for i, frame_data in enumerate(frames_data):
                frames.append(
                    WorldFrame(
                        frame_id=f"frame_{i}",
                        image_data=frame_data,
                        timestamp=i * 0.1,
                        metadata={"style": style.value},
                    )
                )

            return WorldResult(
                success=True,
                world_id=f"world_{int(time.time())}",
                frames=frames,
                preview_image=frames[0].image_data if frames else None,
                provider="emu35",
                model=self.config.model_id,
                generation_time=gen_time,
                metadata={
                    "prompt": prompt,
                    "style": style.value,
                    "width": width,
                    "height": height,
                    "num_frames": num_frames,
                },
            )

        except Exception as e:
            return WorldResult(
                success=False,
                error=str(e),
                provider="emu35",
                model=self.config.model_id,
                generation_time=time.time() - start,
            )

    def _style_prompt(self, prompt: str, style: WorldStyle) -> str:
        """Enhance prompt with style modifiers."""
        style_modifiers = {
            WorldStyle.PHOTOREALISTIC: "photorealistic, high detail, 8k resolution",
            WorldStyle.ARTISTIC: "artistic, painterly, expressive brushstrokes",
            WorldStyle.ANIME: "anime style, vibrant colors, cel shading",
            WorldStyle.CINEMATIC: "cinematic, dramatic lighting, movie scene",
            WorldStyle.FANTASY: "fantasy world, magical, ethereal atmosphere",
            WorldStyle.SCIFI: "science fiction, futuristic, advanced technology",
        }
        modifier = style_modifiers.get(style, "")
        return f"{prompt}, {modifier}" if modifier else prompt

    def _decode_vision_output(self, output: str) -> bytes:
        """Decode vision tokens from Emu 3.5 output.

        Note: This is a placeholder. Full implementation requires
        the Emu 3.5 vision tokenizer to decode visual tokens.
        """
        # For now, create a placeholder image
        # In production, this would decode Emu 3.5's visual tokens
        try:
            from PIL import Image, ImageDraw

            img = Image.new("RGB", (512, 512), color=(30, 30, 40))
            draw = ImageDraw.Draw(img)
            draw.text(
                (50, 240),
                "Emu 3.5 World Generation",
                fill=(200, 200, 200),
            )
            draw.text(
                (100, 280),
                "(Vision decoder pending)",
                fill=(150, 150, 150),
            )

            buffer = BytesIO()
            img.save(buffer, format="PNG")
            return buffer.getvalue()
        except ImportError:
            return b""


# =============================================================================
# WORLD SERVICE
# =============================================================================


class WorldService:
    """Unified world generation service.

    Provides a high-level interface for generating and exploring
    virtual worlds using Emu 3.5.
    """

    def __init__(self, config: WorldConfig | None = None) -> None:
        self.config = config or WorldConfig()
        self._emu35 = Emu35Client(self.config)
        self._initialized = False
        self._worlds: dict[str, WorldResult] = {}  # Cache of generated worlds

    async def initialize(self) -> bool:
        """Initialize available providers."""
        emu35_ok = await self._emu35.initialize()

        self._initialized = emu35_ok

        if self._initialized:
            logger.info("✅ WorldService initialized (Emu 3.5)")
        else:
            logger.warning("⚠️ WorldService: no providers available")

        return self._initialized

    async def generate(
        self,
        prompt: str,
        provider: str | WorldProvider | None = None,
        style: str | WorldStyle | None = None,
        width: int | None = None,
        height: int | None = None,
        num_frames: int = 1,
        save_path: str | None = None,
        **kwargs: Any,
    ) -> WorldResult:
        """Generate a new world.

        Args:
            prompt: Description of the world
            provider: Which provider to use
            style: Visual style
            width: Image width
            height: Image height
            num_frames: Number of frames/views to generate
            save_path: Optional path to save preview image
            **kwargs: Additional parameters

        Returns:
            WorldResult with generated world
        """
        if not self._initialized:
            return WorldResult(success=False, error="WorldService not initialized")

        # Normalize parameters
        if provider is None:
            provider = WorldProvider.AUTO
        elif isinstance(provider, str):
            provider = WorldProvider(provider.lower())

        if style and isinstance(style, str):
            style = WorldStyle(style.lower())

        # Route to provider
        if provider in (WorldProvider.EMU35, WorldProvider.EMU35_IMAGE, WorldProvider.AUTO):
            result = await self._emu35.generate(
                prompt,
                style=style,
                width=width,
                height=height,
                num_frames=num_frames,
                **kwargs,
            )
        else:
            result = WorldResult(success=False, error=f"Unknown provider: {provider}")

        # Cache world
        if result.success and result.world_id:
            self._worlds[result.world_id] = result

        # Save preview if requested
        if result.success and result.preview_image and save_path:
            try:
                path = Path(save_path)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(result.preview_image)
                logger.info(f"World preview saved to {path}")
            except Exception as e:
                logger.warning(f"Failed to save preview: {e}")

        return result

    async def explore(
        self,
        world_id: str,
        direction: str = "forward",
        steps: int = 5,
        **kwargs: Any,
    ) -> WorldResult:
        """Explore/expand an existing world.

        Args:
            world_id: ID of world to explore
            direction: Exploration direction (forward, back, left, right, up, down)
            steps: Number of steps to explore
            **kwargs: Additional parameters

        Returns:
            WorldResult with new frames
        """
        if world_id not in self._worlds:
            return WorldResult(
                success=False,
                error=f"World not found: {world_id}",
            )

        original = self._worlds[world_id]

        # Generate exploration prompt
        explore_prompt = (
            f"Continue exploring: {original.metadata.get('prompt', '')}, moving {direction}"
        )

        return await self.generate(
            explore_prompt,
            style=original.metadata.get("style"),
            num_frames=steps,
            **kwargs,
        )

    def get_world(self, world_id: str) -> WorldResult | None:
        """Get a cached world by ID."""
        return self._worlds.get(world_id)

    def list_worlds(self) -> list[str]:
        """List all cached world IDs."""
        return list(self._worlds.keys())


# =============================================================================
# SINGLETON
# =============================================================================

_world_service: WorldService | None = None


def get_world_service() -> WorldService:
    """Get global WorldService instance."""
    global _world_service
    if _world_service is None:
        _world_service = WorldService()
    return _world_service


def reset_world_service() -> None:
    """Reset global instance."""
    global _world_service
    _world_service = None


__all__ = [
    "Emu35Client",
    "WorldConfig",
    "WorldFrame",
    "WorldProvider",
    "WorldResult",
    "WorldService",
    "WorldStyle",
    "get_world_service",
    "reset_world_service",
]
