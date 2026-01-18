"""Forge Colony Generation Integration.

Provides unified access to all AI generation capabilities through the Forge colony.
Forge is the Builder colony — responsible for creating artifacts.

Generation Modalities:
    - Music (future: MusicGen, Udio)
    - Image (future: DALL-E, Stable Diffusion, Midjourney)
    - Video (Genesis physics engine)
    - 3D Models (future: Point-E, Shap-E)
    - Audio (TTS, sound effects, voice cloning)

Architecture:
    ┌─────────────────────────────────────────────────────────────────┐
    │                     FORGE GENERATION HUB                        │
    │                                                                 │
    │  World Model ──→ Action Selection ──→ Forge Generator          │
    │       ↓              ↓                     ↓                    │
    │   E8 Code      Generation Action      Execute Generation       │
    │       ↓              ↓                     ↓                    │
    │   Motor Decoder ←── Result ←───────── Artifact                 │
    └─────────────────────────────────────────────────────────────────┘

Usage:
    from kagami.core.embodiment.forge_generation import (
        ForgeGenerator,
        get_forge_generator,
    )

    forge = get_forge_generator()
    await forge.initialize()

    # Generate music through Forge
    result = await forge.generate(
        modality="music",
        prompt="Ambient soundscape for focus",
        style="lo-fi, peaceful",
    )

    # Integrate with world model
    action_embedding = forge.get_action_embedding("music_generate")
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import torch

logger = logging.getLogger(__name__)


# =============================================================================
# GENERATION MODALITIES
# =============================================================================


class GenerationModality(str, Enum):
    """Available generation modalities."""

    MUSIC = "music"
    IMAGE = "image"
    VIDEO = "video"
    MODEL_3D = "model_3d"
    AUDIO = "audio"
    WORLD = "world"  # Emu 3.5 world generation


@dataclass
class GenerationResult:
    """Result from a generation request."""

    modality: GenerationModality
    success: bool
    artifact_url: str | None = None
    artifact_data: bytes | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    action_used: str = ""
    generation_time: float = 0.0


@dataclass
class GenerationRequest:
    """Request for generation."""

    modality: GenerationModality
    prompt: str
    style: str | None = None
    params: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# FORGE GENERATOR
# =============================================================================


class ForgeGenerator:
    """Unified generation interface for Forge colony.

    Connects all AI generation capabilities to the world model and action space.

    Features:
        - Multi-modal generation (music, image, video, 3D, audio)
        - Action space integration (automatic registration)
        - World model embedding support
        - Async execution with proper error handling
    """

    def __init__(self) -> None:
        self._initialized = False
        self._services: dict[GenerationModality, Any] = {}
        self._action_embeddings: dict[str, torch.Tensor] = {}
        self._generation_handlers: dict[
            GenerationModality, Callable[..., Awaitable[GenerationResult]]
        ] = {}

    async def initialize(self) -> bool:
        """Initialize all generation services."""
        logger.info("Initializing Forge Generator...")

        # Initialize Music generation (Symphony Generator via BBC Symphony Orchestra)
        try:
            from kagami.forge.modules.audio.symphony_generator import get_symphony_generator

            symphony_gen = await get_symphony_generator()
            self._services[GenerationModality.MUSIC] = symphony_gen
            self._generation_handlers[GenerationModality.MUSIC] = self._generate_music
            logger.info("✅ Music service initialized (BBC Symphony Orchestra)")
        except Exception as e:
            logger.warning(f"⚠️ Music service not available: {e}")
            self._generation_handlers[GenerationModality.MUSIC] = self._generate_music_placeholder

        # Initialize Image generation (OpenAI gpt-image-1 + FLUX fallback)
        try:
            from kagami.core.services.image import get_image_service

            image_service = get_image_service()
            if await image_service.initialize():
                self._services[GenerationModality.IMAGE] = image_service
                self._generation_handlers[GenerationModality.IMAGE] = self._generate_image
                logger.info("✅ Image service initialized (OpenAI + FLUX)")
            else:
                logger.warning("⚠️ Image service not available")
                self._generation_handlers[GenerationModality.IMAGE] = (
                    self._generate_image_placeholder
                )
        except ImportError as e:
            logger.warning(f"⚠️ Image service not available: {e}")
            self._generation_handlers[GenerationModality.IMAGE] = self._generate_image_placeholder

        # Initialize Video generation (Genesis)
        self._generation_handlers[GenerationModality.VIDEO] = self._generate_video_placeholder

        # Initialize 3D generation (placeholder)
        self._generation_handlers[GenerationModality.MODEL_3D] = self._generate_3d_placeholder

        # Initialize Audio generation (TTS/SFX)
        self._generation_handlers[GenerationModality.AUDIO] = self._generate_audio_placeholder

        # Initialize World generation (Emu 3.5)
        try:
            from kagami.core.services.world import get_world_service

            world_service = get_world_service()
            if await world_service.initialize():
                self._services[GenerationModality.WORLD] = world_service
                self._generation_handlers[GenerationModality.WORLD] = self._generate_world
                logger.info("✅ World service initialized (Emu 3.5)")
            else:
                logger.warning("⚠️ World service not available")
                self._generation_handlers[GenerationModality.WORLD] = (
                    self._generate_world_placeholder
                )
        except ImportError as e:
            logger.warning(f"⚠️ World service not available: {e}")
            self._generation_handlers[GenerationModality.WORLD] = self._generate_world_placeholder

        # Register with action space
        self._register_actions()

        # Build action embeddings
        self._build_action_embeddings()

        self._initialized = True
        logger.info(
            f"✅ ForgeGenerator initialized: {len(self._services)} services, "
            f"{len(self._generation_handlers)} handlers"
        )
        return True

    def _register_actions(self) -> None:
        """Register generation actions with the action space registry.

        Static actions are defined in GENERATION_EFFECTORS.
        This method is for registering dynamic custom generators at runtime.
        """
        try:
            from kagami.core.embodiment.action_space import get_action_registry

            # Registry available for dynamic registration if needed
            _ = get_action_registry()
        except ImportError:
            logger.debug("Action space registry not available")

    def _build_action_embeddings(self) -> None:
        """Build embeddings for generation actions.

        These embeddings can be used by the world model for action selection.
        """
        from kagami.core.embodiment.action_space import (
            GENERATION_EFFECTORS,
            GENERATION_SENSORS,
            get_action_registry,
        )

        registry = get_action_registry()
        embed_dim = registry.get_action_embedding_dim()

        # Create random embeddings for each action (will be learned during training)
        for action in GENERATION_EFFECTORS + GENERATION_SENSORS:
            idx = registry.get_action_index(action)
            if idx >= 0:
                # Use action index to seed for reproducibility
                torch.manual_seed(idx)
                self._action_embeddings[action] = torch.randn(embed_dim)

        logger.debug(f"Built {len(self._action_embeddings)} action embeddings (dim={embed_dim})")

    async def generate(
        self,
        modality: str | GenerationModality,
        prompt: str,
        style: str | None = None,
        **kwargs: Any,
    ) -> GenerationResult:
        """Generate artifact using specified modality.

        Args:
            modality: Generation type (music, image, video, model_3d, audio)
            prompt: Description of what to generate
            style: Optional style/genre tags
            **kwargs: Additional modality-specific parameters

        Returns:
            GenerationResult with artifact URL/data or error
        """
        if not self._initialized:
            raise RuntimeError("ForgeGenerator not initialized. Call initialize() first.")

        # Convert string to enum
        if isinstance(modality, str):
            modality = GenerationModality(modality.lower())

        # Get handler
        handler = self._generation_handlers.get(modality)
        if handler is None:
            return GenerationResult(
                modality=modality,
                success=False,
                error=f"No handler for modality: {modality}",
            )

        # Execute generation
        import time

        start = time.time()

        try:
            result = await handler(prompt=prompt, style=style, **kwargs)
            result.generation_time = time.time() - start
            return result
        except Exception as e:
            logger.error(f"Generation failed ({modality}): {e}")
            return GenerationResult(
                modality=modality,
                success=False,
                error=str(e),
                generation_time=time.time() - start,
            )

    # =========================================================================
    # GENERATION HANDLERS
    # =========================================================================

    async def _generate_music(
        self,
        prompt: str,
        style: str | None = None,
        duration: float = 30.0,
        **kwargs: Any,
    ) -> GenerationResult:
        """Generate orchestral music using BBC Symphony Orchestra.

        Pipeline:
            1. MusicGen generates melody from prompt
            2. basic-pitch converts audio to MIDI
            3. Expression engine adds CC1/CC11 dynamics
            4. BBC Symphony Orchestra renders through REAPER
            5. VBAP spatializes to 5.1.4 Atmos

        Args:
            prompt: Description of desired music
            style: Style preset (romantic, baroque, film_score, epic, etc.)
            duration: Target duration in seconds
            **kwargs: Additional parameters

        Latency: SLOW (2-5 minutes depending on duration)
        """
        symphony_gen = self._services.get(GenerationModality.MUSIC)
        if symphony_gen is None:
            return GenerationResult(
                modality=GenerationModality.MUSIC,
                success=False,
                error="Symphony generator not initialized",
                action_used="music_generate",
            )

        try:
            from kagami.forge.modules.audio.symphony_generator import generate_symphony

            result = await generate_symphony(
                prompt=prompt,
                style=style or "film_score",
                duration=duration,
                **kwargs,
            )

            if result.success:
                return GenerationResult(
                    modality=GenerationModality.MUSIC,
                    success=True,
                    artifact_url=str(result.audio_path) if result.audio_path else None,
                    metadata={
                        "audio_path": str(result.audio_path) if result.audio_path else None,
                        "midi_path": str(result.midi_path) if result.midi_path else None,
                        "duration_sec": result.duration_sec,
                        "generation_time": result.generation_time_sec,
                        "render_time": result.render_time_sec,
                        "style": result.style.value,
                        "prompt_used": result.prompt_used,
                        "latency_tier": "SLOW",
                        **result.metadata,
                    },
                    action_used="music_generate",
                )
            else:
                return GenerationResult(
                    modality=GenerationModality.MUSIC,
                    success=False,
                    error=result.error,
                    action_used="music_generate",
                )
        except Exception as e:
            logger.error(f"Music generation failed: {e}")
            return GenerationResult(
                modality=GenerationModality.MUSIC,
                success=False,
                error=str(e),
                action_used="music_generate",
            )

    async def _generate_music_placeholder(
        self,
        prompt: str,
        style: str | None = None,
        **kwargs: Any,
    ) -> GenerationResult:
        """Fallback when music generation is not available.

        Requires:
        - audiocraft (MusicGen)
        - basic-pitch (audio-to-MIDI)
        - REAPER + BBC Symphony Orchestra
        """
        return GenerationResult(
            modality=GenerationModality.MUSIC,
            success=False,
            error="Music generation requires: audiocraft, basic-pitch, REAPER, BBC Symphony Orchestra. "
            "Install: pip install audiocraft basic-pitch",
            action_used="music_generate",
            metadata={"latency_tier": "SLOW", "expected_time": "2-5min"},
        )

    async def _generate_image(
        self,
        prompt: str,
        style: str | None = None,
        quality: str = "medium",
        size: str = "1024x1024",
        provider: str | None = None,
        **kwargs: Any,
    ) -> GenerationResult:
        """Generate image using OpenAI gpt-image-1 or FLUX local.

        Latency:
            - OpenAI gpt-image-1: ~10s
            - FLUX.1-schnell (local): ~5-15s on M3 Ultra

        Cost:
            - OpenAI: $0.02 (low) / $0.07 (med) / $0.19 (high)
            - FLUX: Free (local)
        """
        image_service = self._services.get(GenerationModality.IMAGE)
        if image_service is None:
            return GenerationResult(
                modality=GenerationModality.IMAGE,
                success=False,
                error="Image service not initialized",
                action_used="image_generate",
            )

        try:
            # Combine prompt with style if provided
            full_prompt = f"{prompt}, {style}" if style else prompt

            result = await image_service.generate(
                prompt=full_prompt,
                quality=quality,
                size=size,
                provider=provider,
                **kwargs,
            )

            if result.success:
                return GenerationResult(
                    modality=GenerationModality.IMAGE,
                    success=True,
                    artifact_data=result.image_data,
                    artifact_url=result.image_url,
                    metadata={
                        "provider": result.provider,
                        "model": result.model,
                        "generation_time": result.generation_time,
                        "cost_usd": result.cost_usd,
                        "latency_tier": "FAST",
                        **result.metadata,
                    },
                    action_used="image_generate",
                )
            else:
                return GenerationResult(
                    modality=GenerationModality.IMAGE,
                    success=False,
                    error=result.error,
                    action_used="image_generate",
                )
        except Exception as e:
            return GenerationResult(
                modality=GenerationModality.IMAGE,
                success=False,
                error=str(e),
                action_used="image_generate",
            )

    async def _generate_image_placeholder(
        self,
        prompt: str,
        style: str | None = None,
        **kwargs: Any,
    ) -> GenerationResult:
        """Fallback placeholder when image service unavailable."""
        return GenerationResult(
            modality=GenerationModality.IMAGE,
            success=False,
            error="Image service not available. Need OPENAI_API_KEY or diffusers installed.",
            action_used="image_generate",
            metadata={"latency_tier": "FAST", "expected_time": "<10s"},
        )

    async def _generate_video_placeholder(
        self,
        prompt: str,
        style: str | None = None,
        **kwargs: Any,
    ) -> GenerationResult:
        """Placeholder for video generation.

        Latency: SLOW (1.75-4.5 min depending on service)
        Cost: ~$0.15-0.50/video depending on length/quality

        Planned integrations:
        - Runway Gen-3 (1.75 min avg, $12-76/mo)
        - Pika Labs (2.2 min avg, $10-35/mo)
        - Luma Dream Machine (3 min avg)
        - Genesis (local physics render)
        """
        return GenerationResult(
            modality=GenerationModality.VIDEO,
            success=False,
            error="Video generation not yet implemented. Future: Runway Gen-3, Pika, Luma",
            action_used="video_generate",
            metadata={"latency_tier": "SLOW", "expected_time": "1-5min"},
        )

    async def _generate_3d_placeholder(
        self,
        prompt: str,
        style: str | None = None,
        **kwargs: Any,
    ) -> GenerationResult:
        """Placeholder for 3D model generation.

        Latency: MEDIUM (30-60s for Meshy, 17-30s for Shap-E)
        Cost: ~$0.10-0.50/model depending on complexity

        Planned integrations:
        - Meshy (30-60s, fast production quality)
        - Shap-E (17s load + generation, OpenAI)
        - Point-E (13s load + generation, lower quality)
        - Luma AI (variable, NeRF-based)
        """
        return GenerationResult(
            modality=GenerationModality.MODEL_3D,
            success=False,
            error="3D generation not yet implemented. Future: Meshy, Shap-E",
            action_used="model_3d_generate",
            metadata={"latency_tier": "MEDIUM", "expected_time": "30-60s"},
        )

    async def _generate_audio_placeholder(
        self,
        prompt: str,
        style: str | None = None,
        voice: str | None = None,
        **kwargs: Any,
    ) -> GenerationResult:
        """Placeholder for audio generation (TTS, SFX).

        Latency: FAST (<5s for ElevenLabs TTS)
        Cost: ~$0.015/1000 chars (OpenAI TTS), ~$0.096/min (ElevenLabs)

        Planned integrations:
        - ElevenLabs (75ms latency, best voice cloning)
        - OpenAI TTS ($0.015/1k chars, good quality)
        - Google Cloud TTS (200-400ms, $4-16/1M chars)
        - AudioCraft (Meta, SFX generation)
        """
        return GenerationResult(
            modality=GenerationModality.AUDIO,
            success=False,
            error="Audio generation not yet implemented. Future: ElevenLabs, OpenAI TTS",
            action_used="audio_tts",
            metadata={"latency_tier": "FAST", "expected_time": "<5s"},
        )

    async def _generate_world(
        self,
        prompt: str,
        style: str | None = None,
        width: int = 1024,
        height: int = 1024,
        num_frames: int = 1,
        **kwargs: Any,
    ) -> GenerationResult:
        """Generate virtual world using Emu 3.5.

        Latency: MEDIUM-SLOW (30s-2min depending on frames)
        Cost: Free (local model)

        Features:
        - Spatiotemporally consistent world exploration
        - Any-to-image (X2I) generation
        - Interleaved vision-language sequences
        """
        world_service = self._services.get(GenerationModality.WORLD)
        if world_service is None:
            return GenerationResult(
                modality=GenerationModality.WORLD,
                success=False,
                error="World service not initialized",
                action_used="world_generate",
            )

        try:
            result = await world_service.generate(
                prompt=prompt,
                style=style,
                width=width,
                height=height,
                num_frames=num_frames,
                **kwargs,
            )

            if result.success:
                return GenerationResult(
                    modality=GenerationModality.WORLD,
                    success=True,
                    artifact_data=result.preview_image,
                    metadata={
                        "world_id": result.world_id,
                        "provider": result.provider,
                        "model": result.model,
                        "generation_time": result.generation_time,
                        "num_frames": len(result.frames),
                        "latency_tier": "MEDIUM",
                        **result.metadata,
                    },
                    action_used="world_generate",
                )
            else:
                return GenerationResult(
                    modality=GenerationModality.WORLD,
                    success=False,
                    error=result.error,
                    action_used="world_generate",
                )
        except Exception as e:
            return GenerationResult(
                modality=GenerationModality.WORLD,
                success=False,
                error=str(e),
                action_used="world_generate",
            )

    async def _generate_world_placeholder(
        self,
        prompt: str,
        style: str | None = None,
        **kwargs: Any,
    ) -> GenerationResult:
        """Placeholder when Emu 3.5 is not available."""
        return GenerationResult(
            modality=GenerationModality.WORLD,
            success=False,
            error="World generation requires Emu 3.5. Run: pip install transformers",
            action_used="world_generate",
            metadata={"latency_tier": "MEDIUM", "expected_time": "30s-2min"},
        )

    # =========================================================================
    # WORLD MODEL INTEGRATION
    # =========================================================================

    def get_action_embedding(self, action: str) -> torch.Tensor | None:
        """Get embedding for a generation action.

        Used by world model for action selection.

        Args:
            action: Action name (e.g., "music_generate")

        Returns:
            Embedding tensor or None if not found
        """
        return self._action_embeddings.get(action)

    def get_all_action_embeddings(self) -> dict[str, torch.Tensor]:
        """Get all generation action embeddings."""
        return self._action_embeddings.copy()

    def action_to_generation_request(
        self,
        action: str,
        params: dict[str, Any],
    ) -> GenerationRequest | None:
        """Convert motor decoder action to generation request.

        Args:
            action: Action name from motor decoder
            params: Action parameters

        Returns:
            GenerationRequest or None if not a generation action
        """
        # Map actions to modalities (optimized names)
        modality_map = {
            # Music - SLOW (2-3min)
            "music_generate": GenerationModality.MUSIC,
            "music_extend": GenerationModality.MUSIC,
            # Image (DALL-E/SD) - FAST (<10s)
            "image_generate": GenerationModality.IMAGE,
            "image_edit": GenerationModality.IMAGE,
            "image_variation": GenerationModality.IMAGE,
            # Video (Runway) - SLOW (1-5min)
            "video_generate": GenerationModality.VIDEO,
            "video_extend": GenerationModality.VIDEO,
            # 3D (Meshy) - MEDIUM (30-60s)
            "model_3d_generate": GenerationModality.MODEL_3D,
            "model_3d_texture": GenerationModality.MODEL_3D,
            # Audio (ElevenLabs) - FAST (<5s)
            "audio_tts": GenerationModality.AUDIO,
            "audio_sfx": GenerationModality.AUDIO,
            "audio_clone": GenerationModality.AUDIO,
            # World (Emu 3.5) - MEDIUM (30s-2min)
            "world_generate": GenerationModality.WORLD,
            "world_explore": GenerationModality.WORLD,
            "world_expand": GenerationModality.WORLD,
            "audio_clone_voice": GenerationModality.AUDIO,
        }

        modality = modality_map.get(action)
        if modality is None:
            return None

        return GenerationRequest(
            modality=modality,
            prompt=params.get("prompt", ""),
            style=params.get("style"),
            params=params,
        )

    async def execute_from_motor_decoder(
        self,
        action: str,
        params: dict[str, Any],
    ) -> GenerationResult | None:
        """Execute generation from motor decoder output.

        This bridges the world model → action selection → generation pipeline.

        Args:
            action: Action name from motor decoder
            params: Action parameters

        Returns:
            GenerationResult or None if not a generation action
        """
        request = self.action_to_generation_request(action, params)
        if request is None:
            return None

        return await self.generate(
            modality=request.modality,
            prompt=request.prompt,
            style=request.style,
            **request.params,
        )

    def sync_to_world_model(self, world_model: Any) -> dict[str, Any]:
        """Synchronize generation capabilities with world model.

        Ensures the world model's action space includes all generation actions.

        Args:
            world_model: KagamiWorldModel instance

        Returns:
            Sync report
        """
        from kagami.core.embodiment.action_space import get_action_registry

        registry = get_action_registry()
        return registry.sync_to_world_model(world_model)


# =============================================================================
# SINGLETON
# =============================================================================

_forge_generator: ForgeGenerator | None = None


def get_forge_generator() -> ForgeGenerator:
    """Get global ForgeGenerator instance."""
    global _forge_generator
    if _forge_generator is None:
        _forge_generator = ForgeGenerator()
    return _forge_generator


def reset_forge_generator() -> None:
    """Reset global instance (for testing)."""
    global _forge_generator
    _forge_generator = None


__all__ = [
    "ForgeGenerator",
    "GenerationModality",
    "GenerationRequest",
    "GenerationResult",
    "get_forge_generator",
    "reset_forge_generator",
]
