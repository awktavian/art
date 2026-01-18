from __future__ import annotations

#!/usr/bin/env python3
"""Text-to-motion generation for 3D character animation.

This module provides motion synthesis capabilities using AI models to generate
realistic character animations from text descriptions. It integrates with the
rigging system to produce animation-ready motion sequences.

Key Features:
    - Generate character motion from natural language descriptions
    - Support for common actions (walking, running, dancing, etc.)
    - Compatible with standard skeleton formats
    - Performance tracking and optimization
    - Export-ready motion data

Example:
    >>> animation = AnimationModule("animation")
    >>> await animation.initialize()
    >>> result = await animation.process({
    ...     'text_prompt': 'a person walking forward',
    ...     'motion_length': 3.0
    ... })
    >>> motion_data = result.data['motion_sequence']
"""
import logging
import time
from typing import TYPE_CHECKING, Any

try:  # pragma: no cover - optional heavy dependency
    import numpy as _np

    _NUMPY_IMPORT_ERROR: Exception | None = None
except Exception as _numpy_err:  # pragma: no cover
    _np: Any = None  # type: ignore[no-redef]
    _NUMPY_IMPORT_ERROR = _numpy_err

try:  # pragma: no cover - optional heavy dependency
    import torch as _torch

    _TORCH_IMPORT_ERROR: Exception | None = None
except Exception as _torch_err:  # pragma: no cover
    _torch: Any = None  # type: ignore[no-redef]
    _TORCH_IMPORT_ERROR = _torch_err

if TYPE_CHECKING:  # pragma: no cover - type checking only
    import numpy as np
    import torch
else:  # pragma: no cover - runtime branch
    np = _np  # type: ignore[assignment]
    torch = _torch  # type: ignore[assignment]

from kagami.forge.core_integration import (
    CharacterAspect,
    CharacterResult,
    ForgeComponent,
    ProcessingStatus,
)
from kagami.forge.inference.motion_agent import MotionAgent
from kagami.forge.utils.style_rewriters import (
    build_prompts_for_content_type,
)

try:
    from kagami_observability.metrics import (
        MOTION_GENERATION_LATENCY_MS,
        MOTION_GENERATIONS,
    )
except Exception:
    MOTION_GENERATIONS: Any = None  # type: ignore[no-redef]
    MOTION_GENERATION_LATENCY_MS: Any = None  # type: ignore[no-redef]

logger = logging.getLogger(__name__)


class MotionSequence:
    """Container for motion capture data sequences.

    Stores motion data in a format compatible with export modules and
    rendering systems. Provides convenient access to motion properties.

    Attributes:
        motion: Motion data as numpy array (frames x joints x 3)
        fps: Frames per second of the motion
        joint_names: Optional list[Any] of joint/bone names
        duration: Total duration in seconds
    """

    def __init__(
        self,
        motion_data: np.ndarray[Any, Any],
        fps: float = 20.0,
        joint_names: list[str] | None = None,
    ) -> None:
        self.motion = motion_data
        self.fps = fps
        self.joint_names = joint_names or []
        self.duration = len(motion_data) / fps

    @property
    def n_frames(self) -> int:
        return len(self.motion)

    @property
    def n_joints(self) -> int:
        return self.motion.shape[1] if len(self.motion.shape) > 1 else 0

    def get_duration(self) -> float:
        return self.duration


class AnimationData:
    """Structured container for animation data with metadata.

    Encapsulates motion data along with the generation parameters and
    metadata for tracking and reproducibility.

    Args:
        motion: Motion capture data array
        text_prompt: Text description used to generate the motion
        fps: Playback frames per second
    """

    def __init__(self, motion: np.ndarray[Any, Any], text_prompt: str, fps: float = 20.0) -> None:
        self.motion = motion
        self.text_prompt = text_prompt
        self.fps = fps
        self.duration = len(motion) / fps

    def to_dict(self) -> dict[str, Any]:
        """Convert animation data to dictionary for serialization.

        Returns:
            Dictionary containing motion data and metadata
        """
        return {
            "motion": self.motion.tolist(),
            "text_prompt": self.text_prompt,
            "fps": self.fps,
            "duration": self.duration,
            "n_frames": self.motion.shape[0],
            "n_joints": self.motion.shape[1],
        }


class RealMotionGenerator:
    """Motion generation engine using AI models.

    Handles the actual motion synthesis using Motion-Agent integration
    with ModelScope and optional MLD support. Tracks performance metrics
    and ensures compatibility with standard skeleton formats.

    Args:
        device: PyTorch device (cpu, cuda, or mps)

    Attributes:
        device: Computation device
        motion_agent: Initialized Motion-Agent instance
        fps: Standard output frames per second (20)
        n_joints: Number of skeleton joints (22 for humanoid)
    """

    def __init__(self, device: torch.device) -> None:
        self.device = device
        self.model_type = "motion_agent"
        self.motion_agent = None
        self.n_joints = 22  # Standard human skeleton
        self.fps = 20.0
        self.initialized = False

        # Performance tracking
        self.inference_times: list[float] = []
        self.memory_usage: list[float] = []

    async def load_models(self) -> None:
        """Initialize and load the motion generation models.

        Raises:
            RuntimeError: If model loading fails
        """
        try:
            # Initialize Motion-Agent
            self.motion_agent = MotionAgent()  # type: ignore[assignment]
            await self.motion_agent.initialize()  # type: ignore  # Dynamic attr

            self.initialized = True
            logger.info("✅ Motion-Agent loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load Motion-Agent: {e}")
            raise RuntimeError(f"Motion-Agent required: {e}") from None

    async def generate_motion(self, text_prompt: str, motion_length: float) -> np.ndarray[Any, Any]:
        """Generate motion sequence from text description.

        Args:
            text_prompt: Natural language description of the motion
            motion_length: Desired duration in seconds

        Returns:
            Motion data array (frames x joints x 3)

        Raises:
            RuntimeError: If generation fails or models not loaded
        """
        if not self.initialized:
            raise RuntimeError("Motion-Agent not loaded")

        start_time = time.time()

        try:
            logger.info(f"🎭 Generating motion: '{text_prompt[:50]}...'")

            # Generate motion using Motion-Agent
            if not self.motion_agent:
                raise RuntimeError("Motion-Agent not initialized")
            result = await self.motion_agent.generate_motion(text_prompt, motion_length)  # type: ignore  # Defensive/fallback code
            motion_data = result.get("motion_data") if isinstance(result, dict) else result
            # Ensure numpy ndarray[Any, Any]
            if hasattr(motion_data, "numpy"):
                motion_data = motion_data.numpy()

            # Track performance
            inference_time = (time.time() - start_time) * 1000
            self.inference_times.append(inference_time)

            # Memory usage
            if self.device.type == "mps":
                memory_used = torch.mps.current_allocated_memory() / 1024 / 1024
            elif self.device.type == "cuda":
                memory_used = torch.cuda.memory_allocated() / 1024 / 1024
            else:
                memory_used = 0

            self.memory_usage.append(memory_used)

            # Performance validation
            if inference_time > 50:  # GAIA requirement
                logger.warning(f"Motion generation time {inference_time:.2f}ms exceeds 50ms target")

            try:
                shape = getattr(motion_data, "shape", None)
            except Exception:
                shape = None
            logger.info(f"✅ Motion generated: {shape} in {inference_time:.2f}ms")
            try:
                if MOTION_GENERATIONS is not None:
                    MOTION_GENERATIONS.labels("motion_agent", "success").inc()
                if MOTION_GENERATION_LATENCY_MS is not None:
                    MOTION_GENERATION_LATENCY_MS.labels("motion_agent").observe(inference_time)
            except Exception:
                pass
            return motion_data

        except Exception as e:
            logger.error(f"❌ Motion generation failed: {e}")
            try:
                if MOTION_GENERATIONS is not None:
                    MOTION_GENERATIONS.labels("motion_agent", "error").inc()
            except Exception:
                pass
            raise RuntimeError(f"Motion generation failed: {e}") from None

    def get_supported_prompts(self) -> list[str]:
        """Get list[Any] of example motion prompts that work well.

        Returns:
            List of example text prompts for motion generation
        """
        if not self.initialized or not self.motion_agent:
            return []

        # Return common motion prompts that work with Motion-Agent
        return [  # type: ignore  # Defensive/fallback code
            "a person walking forward",
            "a person running",
            "a person jumping",
            "a person dancing",
            "a person waving hello",
            "a person sitting down",
            "a person standing up",
            "a person clapping hands",
            "a person throwing a ball",
            "a person kicking a ball",
        ]

    def get_performance_stats(self) -> dict[str, float]:
        """Get performance metrics for the motion generator.

        Returns:
            Dictionary with average/max inference times and memory usage
        """
        if not self.inference_times:
            return {"avg_inference_time": 0.0, "avg_memory_usage": 0.0}

        return {
            "avg_inference_time": float(np.mean(self.inference_times)),
            "max_inference_time": float(np.max(self.inference_times)),
            "avg_memory_usage": float(np.mean(self.memory_usage)),
            "max_memory_usage": float(np.max(self.memory_usage)),
            "total_generations": len(self.inference_times),
        }


class AnimationModule(ForgeComponent):
    """Main animation module for the Forge character generation pipeline.

    Provides high-level interface for text-to-motion generation, integrating
    with the broader character creation workflow. Handles initialization,
    processing requests, and performance monitoring.

    Args:
        module_name: Name identifier for the module

    Example:
        >>> module = AnimationModule("animation")
        >>> await module.initialize()
        >>> result = await module.process({
        ...     'text_prompt': 'a person dancing',
        ...     'motion_length': 5.0
        ... })
    """

    def __init__(self, module_name: str) -> None:
        super().__init__(module_name)
        if torch is None or np is None:
            missing: list[str] = []  # type: ignore  # Defensive/fallback code
            if np is None:
                detail = (
                    f"numpy unavailable ({_NUMPY_IMPORT_ERROR})"
                    if "_NUMPY_IMPORT_ERROR" in globals() and _NUMPY_IMPORT_ERROR
                    else "numpy unavailable"
                )
                missing.append(detail)
            if torch is None:
                detail = (
                    f"torch unavailable ({_TORCH_IMPORT_ERROR})"
                    if "_TORCH_IMPORT_ERROR" in globals() and _TORCH_IMPORT_ERROR
                    else "torch unavailable"
                )
                missing.append(detail)
            raise ImportError("Animation module dependencies missing: " + ", ".join(missing))
        self.device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
        self.motion_generator = RealMotionGenerator(self.device)

    async def initialize(self, config: dict[str, Any] | None = None) -> None:  # type: ignore[override,override]
        """Initialize the animation module and load required models.

        Raises:
            RuntimeError: If initialization fails
        """
        try:
            logger.info("🎬 Initializing Animation Module with Motion-Agent...")

            # Load Motion-Agent
            await self.motion_generator.load_models()

            logger.info(f"✅ Animation module initialized with {self.motion_generator.model_type}")

        except Exception as e:
            logger.error(f"❌ Animation module initialization failed: {e}")
            # Fail fast - no fallbacks
            raise RuntimeError(f"Animation module requires Motion-Agent models: {e}") from e

    async def process(self, input_data: dict[str, Any]) -> CharacterResult:
        """Process a motion generation request.

        Args:
            input_data: Dictionary containing:
                - text_prompt (str): Natural language motion description
                - motion_length (float): Desired duration in seconds

        Returns:
            CharacterResult containing:
                - animation_data: Serialized motion data
                - motion_sequence: MotionSequence object
                - performance_stats: Generation metrics

        Raises:
            ValueError: If input validation fails
            RuntimeError: If motion generation fails
        """
        try:
            # Validate input
            if not isinstance(input_data, dict):
                raise ValueError("Input must be a dictionary")

            text_prompt = input_data.get("text_prompt", "")
            motion_length = input_data.get("motion_length", 3.0)

            if not text_prompt:
                raise ValueError("Text prompt is required for motion generation")

            if not self.motion_generator:
                raise RuntimeError(
                    "Motion generator not available - ModelScope models not installed"
                )

            # Rewrite motion prompt for clarity/consistency using 'motion' content type
            try:
                built = await build_prompts_for_content_type(
                    content_type="motion",
                    mascot_data={},
                    style_engine=None,
                )
                core = "; ".join(built.core_lines)
                prefix = (built.style_prompt + "; ") if built.style_prompt else ""
                rewritten = f"{prefix}{core}; Action: {text_prompt.strip()}".strip()
                logger.info(
                    "Animation: motion prompt rewritten (len=%d -> %d)",
                    len(text_prompt or ""),
                    len(rewritten or ""),
                )
            except Exception:
                rewritten = text_prompt

            # Generate motion using Motion-Agent
            motion_data = await self.motion_generator.generate_motion(rewritten, motion_length)

            # Create animation data
            animation_data = AnimationData(motion_data, rewritten, self.motion_generator.fps)

            # Return result
            return CharacterResult(
                status=ProcessingStatus.COMPLETED,
                aspect=CharacterAspect.MOTION,
                data={
                    "animation_data": animation_data.to_dict(),
                    "motion_sequence": MotionSequence(motion_data, self.motion_generator.fps),
                    "performance_stats": self.motion_generator.get_performance_stats(),
                },
                metadata={
                    "motion_length": float(motion_length),
                    "n_frames": float(motion_data.shape[0]),
                    "n_joints": float(motion_data.shape[1]),
                },
            )

        except Exception as e:
            logger.error(f"❌ Animation processing failed: {e}")
            return CharacterResult(
                status=ProcessingStatus.FAILED,
                aspect=CharacterAspect.MOTION,
                data={},
                error=str(e),
            )

    def get_supported_prompts(self) -> list[str]:
        """Get list[Any] of example motion prompts.

        Returns:
            List of text prompts that work well with the motion generator
        """
        if not self.motion_generator:
            return []
        return self.motion_generator.get_supported_prompts()

    def get_status(self) -> dict[str, Any]:
        """Get current status and statistics of the animation module.

        Returns:
            Dictionary containing initialization status, device info,
            supported prompts count, and performance statistics
        """
        if not self.motion_generator:
            return {
                "initialized": False,
                "model_type": "none",
                "device": str(self.device),
                "supported_prompts": 0,
                "performance_stats": {},
                "error": "ModelScope models not available",
            }

        return {
            "initialized": self.motion_generator.initialized,
            "model_type": self.motion_generator.model_type,
            "device": str(self.device),
            "supported_prompts": len(self.get_supported_prompts()),
            "performance_stats": self.motion_generator.get_performance_stats(),
        }

    def _check_health(self) -> bool:
        """Check component health status."""
        try:
            # Check if motion generator is initialized
            if not self.motion_generator or not self.motion_generator.initialized:
                return False

            # Check if device is available
            if self.device is None:
                return False  # type: ignore  # Defensive/fallback code

            # If we've made it here, the module is healthy
            return True
        except Exception:
            return False

    def _get_status_specific(self) -> dict[str, Any]:
        """Get animation module specific status information."""
        return {
            "motion_generator_initialized": (
                self.motion_generator.initialized if self.motion_generator else False
            ),
            "model_type": (
                self.motion_generator.model_type if self.motion_generator else "unknown"
            ),
            "device": str(self.device) if self.device else "unknown",
            "supported_prompts_count": (
                len(self.get_supported_prompts()) if self.motion_generator else 0
            ),
            "performance_stats": (
                self.motion_generator.get_performance_stats() if self.motion_generator else {}
            ),
        }

    def _do_initialize(self, config: dict[str, Any]) -> None:
        """Initialize the animation module with the given configuration.

        This is the required abstract method implementation from ForgeComponent.
        The actual initialization is done in the async initialize() method.
        """
        # Store config for later use if needed
        self.config = config
        # Note: Actual initialization happens in the async initialize() method
