"""Unified World Model Service Layer.

UPDATED: December 6, 2025 - CANONICAL ENTRY POINT

This module provides THE SINGLE entry point for all world model functionality.
All other access patterns (registry, direct imports) are deprecated.

BREAKING CHANGES (Dec 6, 2025):
==============================
- Strange Loop wiring moved here from UnifiedOrchestrator
- Service now owns lifecycle and wiring
- get_world_model_service() is the canonical entry point
- All other patterns deprecated (but still functional for compatibility)

Previously, world model access was scattered across:
- kagami/core/kernel/syscalls.py (SYS_WORLD_QUERY)
- kagami/core/fractal_agents/world_model_integration.py (simulate_with_world_model)
- kagami/core/fractal_agents/organism/e8_message_bus.py (_ensure_world_model)
- Various other modules

Now all access goes through WorldModelService, which:
- Manages singleton lifecycle
- Provides typed access to sub-components
- Handles initialization and device placement
- Wires Strange Loop to EgoModel and Planner
- Tracks usage metrics
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from kagami.core.world_model.initializer import WorldModelInitializer

if TYPE_CHECKING:
    from kagami.core.world_model.intrinsic.multi_step_empowerment import MultiStepEmpowerment
    from kagami.core.world_model.kagami_world_model import (
        KagamiWorldModel,
    )

logger = logging.getLogger(__name__)


def _lazy_import_torch() -> Any:
    """Lazy import torch to avoid blocking module import.

    OPTIMIZATION (Dec 16, 2025): torch import adds 200-1000ms delay.
    Only import when actually needed for world model operations.
    """
    import torch

    return torch


class CUDAGraphWrapper:
    """Wrapper for CUDA Graphs-based low-latency inference.

    CUDA Graphs capture a sequence of GPU operations as a graph that can be
    replayed with minimal CPU overhead. This is ideal for inference workloads
    with static tensor shapes.

    ADDED: December 31, 2025

    Key constraints:
    - Requires CUDA device (no-op on CPU/MPS)
    - Requires static tensor shapes (input shape must match captured shape)
    - Graph must be re-captured if model changes (weights update, etc.)

    Usage pattern:
        wrapper = CUDAGraphWrapper(model.encode, warmup_iterations=3)
        # First call captures the graph
        output = wrapper(input_tensor)
        # Subsequent calls replay the captured graph (low latency)
        output = wrapper(input_tensor)

    Performance:
    - Reduces inference latency by 2-10x for small batch sizes
    - Most beneficial for latency-sensitive applications
    - Overhead reduction comes from eliminating kernel launch costs

    References:
    - PyTorch CUDA Graphs: https://pytorch.org/docs/stable/notes/cuda.html#cuda-graphs
    - NVIDIA CUDA Graphs: https://developer.nvidia.com/blog/cuda-graphs/
    """

    def __init__(
        self,
        forward_fn: Any,
        warmup_iterations: int = 3,
        stream: Any = None,
    ) -> None:
        """Initialize CUDA Graph wrapper.

        Args:
            forward_fn: The forward function to capture (e.g., model.encode)
            warmup_iterations: Number of warmup iterations before capture
            stream: CUDA stream to use (default: creates new stream)
        """
        self._forward_fn = forward_fn
        self._warmup_iterations = warmup_iterations
        self._graph: Any = None  # torch.cuda.CUDAGraph
        self._stream = stream
        self._captured = False
        self._static_input: Any = None  # torch.Tensor
        self._static_output: Any = None  # torch.Tensor or tuple
        self._input_shape: tuple[int, ...] | None = None
        self._warmup_count = 0
        self._enabled = False  # Set during first call if CUDA available

    def _check_cuda_available(self) -> bool:
        """Check if CUDA Graphs are supported on this device."""
        torch = _lazy_import_torch()
        if not torch.cuda.is_available():
            logger.debug("CUDA Graphs disabled: CUDA not available")
            return False
        # Check CUDA compute capability (graphs need 7.0+)
        device = torch.cuda.current_device()
        capability = torch.cuda.get_device_capability(device)
        if capability[0] < 7:
            logger.debug(f"CUDA Graphs disabled: compute capability {capability} < 7.0")
            return False
        return True

    def _warmup(self, x: Any) -> Any:
        """Run warmup iterations to stabilize CUDA state.

        Warmup ensures:
        - CUDA caches are populated
        - Memory allocations are stable
        - Kernel JIT compilation is complete

        Args:
            x: Input tensor

        Returns:
            Output from forward function
        """
        torch = _lazy_import_torch()
        output = None

        # Run warmup iterations
        for i in range(self._warmup_iterations):
            # Synchronize to ensure stable state
            torch.cuda.synchronize()
            with torch.inference_mode():
                output = self._forward_fn(x)
            torch.cuda.synchronize()
            logger.debug(f"CUDA Graph warmup iteration {i + 1}/{self._warmup_iterations}")

        return output

    def _capture_graph(self, x: Any) -> None:
        """Capture the forward pass as a CUDA Graph.

        This creates static input/output tensors and records the graph.
        After capture, calling replay() executes the graph with minimal overhead.

        Args:
            x: Input tensor (shape will be fixed for this graph)
        """
        torch = _lazy_import_torch()

        # Store input shape for validation
        self._input_shape = tuple(x.shape)

        # Create static input tensor (copy of input)
        self._static_input = torch.empty_like(x)
        self._static_input.copy_(x)

        # Create CUDA stream for graph operations if not provided
        if self._stream is None:
            self._stream = torch.cuda.Stream()

        # Synchronize before capture
        torch.cuda.synchronize()

        # Create graph
        self._graph = torch.cuda.CUDAGraph()

        # Capture graph
        with torch.cuda.stream(self._stream):
            # Warmup the stream
            torch.cuda.synchronize()

            # Begin capture
            with torch.cuda.graph(self._graph, stream=self._stream):
                # Run forward pass with static input
                with torch.inference_mode():
                    self._static_output = self._forward_fn(self._static_input)

        # Synchronize after capture
        torch.cuda.synchronize()

        self._captured = True
        logger.info(
            f"CUDA Graph captured for input shape {self._input_shape}, "
            f"output type: {type(self._static_output).__name__}"
        )

    def _replay(self, x: Any) -> Any:
        """Replay the captured graph with new input.

        Args:
            x: Input tensor (must match captured shape)

        Returns:
            Output from the replayed graph (clone of static output)
        """
        torch = _lazy_import_torch()

        # Validate input shape
        if tuple(x.shape) != self._input_shape:
            raise ValueError(
                f"Input shape {tuple(x.shape)} does not match captured shape "
                f"{self._input_shape}. CUDA Graphs require static shapes."
            )

        # Copy new input to static tensor
        self._static_input.copy_(x)

        # Replay graph
        self._graph.replay()

        # Return clone of static output (to avoid aliasing issues)
        if isinstance(self._static_output, tuple):
            return tuple(
                out.clone() if isinstance(out, torch.Tensor) else out for out in self._static_output
            )
        elif isinstance(self._static_output, torch.Tensor):
            return self._static_output.clone()
        else:
            return self._static_output

    def __call__(self, x: Any) -> Any:
        """Execute the forward function, using CUDA Graph if possible.

        First call checks CUDA availability and runs warmup.
        Subsequent calls capture the graph (if not captured) or replay it.

        Args:
            x: Input tensor

        Returns:
            Output from forward function (or replayed graph)
        """
        torch = _lazy_import_torch()

        # First call: check if CUDA Graphs are usable
        if self._warmup_count == 0:
            self._enabled = self._check_cuda_available()
            if not self._enabled:
                logger.info("CUDA Graphs disabled, using standard forward pass")

        # If CUDA Graphs not available, fall back to direct call
        if not self._enabled:
            with torch.inference_mode():
                return self._forward_fn(x)

        # Warmup phase
        if self._warmup_count < self._warmup_iterations:
            self._warmup_count += 1
            output = self._warmup(x)
            # After warmup complete, capture graph
            if self._warmup_count >= self._warmup_iterations:
                self._capture_graph(x)
            return output

        # Graph captured: replay
        if self._captured:
            # Check if shape changed (requires re-capture)
            if tuple(x.shape) != self._input_shape:
                logger.warning(
                    f"Input shape changed from {self._input_shape} to {tuple(x.shape)}, "
                    "re-capturing graph"
                )
                self._captured = False
                self._capture_graph(x)

            return self._replay(x)

        # Fallback: direct execution
        with torch.inference_mode():
            return self._forward_fn(x)

    def reset(self) -> None:
        """Reset the wrapper, forcing re-capture on next call."""
        self._graph = None
        self._captured = False
        self._static_input = None
        self._static_output = None
        self._input_shape = None
        self._warmup_count = 0
        logger.debug("CUDA Graph wrapper reset")


@dataclass
class WorldModelMetrics:
    """Metrics for world model usage."""

    encode_calls: int = 0
    decode_calls: int = 0
    predict_calls: int = 0
    inference_calls: int = 0
    total_encode_ms: float = 0.0
    total_decode_ms: float = 0.0
    total_predict_ms: float = 0.0
    last_access: float = field(default_factory=time.time)

    @property
    def avg_encode_ms(self) -> float:
        return self.total_encode_ms / max(1, self.encode_calls)

    @property
    def avg_decode_ms(self) -> float:
        return self.total_decode_ms / max(1, self.decode_calls)

    @property
    def avg_predict_ms(self) -> float:
        return self.total_predict_ms / max(1, self.predict_calls)


class WorldModelService:
    """Unified service layer for world model access.

    THE CANONICAL ENTRY POINT for world model operations.

    Provides:
    - Single access point for KagamiWorldModel
    - Typed access to Active Inference engine
    - Typed access to Empowerment estimator
    - Typed access to RSSM dynamics
    - Strange Loop wiring (Dec 6, 2025)
    - Usage metrics and diagnostics

    Usage:
        from kagami.core.world_model import get_world_model_service

        service = get_world_model_service()
        model = service.model  # KagamiWorldModel
        ai = service.active_inference  # ActiveInferenceEngine
        emp = service.empowerment  # MultiStepEmpowerment

        # Direct operations
        state = service.encode(observation)
        pred = service.predict(observation, horizon=5)
    """

    def __init__(self) -> None:
        """Initialize service (lazy-loads world model)."""
        self._model: KagamiWorldModel | None = None
        self._initialized = False
        self._initializing = False  # Guard against concurrent initialization
        self._strange_loop_wired = False
        self._device: Any = None  # torch.device, but avoid import at init
        self.metrics = WorldModelMetrics()
        self.initializer = WorldModelInitializer()
        self._init_lock: Any = None  # Will be set[Any] to asyncio.Lock on first use

        # CUDA Graph wrappers (Dec 31, 2025)
        # These are initialized lazily when CUDA graphs are enabled
        self._cuda_graph_encode: CUDAGraphWrapper | None = None
        self._cuda_graph_decode: CUDAGraphWrapper | None = None
        self._use_cuda_graphs: bool = False
        self._cuda_graph_warmup_iterations: int = 3

        logger.debug("🌍 WorldModelService created (lazy, singleton)")

    def _should_load_world_model(self) -> bool:
        """Return True if world model loading is allowed (delegates to initializer)."""
        return self.initializer.should_load_world_model()

    def _select_device(self) -> Any:  # torch.device
        """Pick a reasonable default device for the world model (delegates to initializer)."""
        return self.initializer.select_device()

    async def _ensure_initialized_async(self) -> None:
        """Ensure world model is initialized and Strange Loop is wired (ASYNC VERSION).

        Uses a lock to prevent concurrent initialization from creating multiple models.
        """
        # Fast path: already initialized
        if self._initialized and self._model is not None:
            return

        # Initialize lock lazily (avoids issues with module-level asyncio)
        if self._init_lock is None:
            import asyncio

            self._init_lock = asyncio.Lock()

        # Use lock to prevent concurrent initialization
        async with self._init_lock:
            # Double-check after acquiring lock (another task may have finished init)
            if self._initialized and self._model is not None:
                return

            # Guard against re-entry during initialization
            if self._initializing:
                logger.debug("WorldModelService: initialization already in progress, waiting...")
                return

            self._initializing = True
            try:
                # Delegate initialization to WorldModelInitializer
                model, device = await self.initializer.ensure_initialized_async()

                self._model = model
                self._device = device
                self._initialized = True

                # Wire Strange Loop if model loaded
                if self._model is not None:
                    self._wire_strange_loop()

                    # Initialize CUDA Graphs if enabled in config (Dec 31, 2025)
                    self._init_cuda_graphs()

                logger.info(
                    f"🌍 WorldModelService initialized: device={self._device}, "
                    f"model={'ready' if self._model else 'unavailable'}, "
                    f"cuda_graphs={'enabled' if self._use_cuda_graphs else 'disabled'}"
                )
            finally:
                self._initializing = False

    def _ensure_initialized(self) -> None:
        """Ensure world model is initialized (SYNC wrapper for async).

        FIXED (Dec 29, 2025): Previous implementation deadlocked by blocking
        on a future scheduled on the same event loop.

        Strategy:
        - If already initialized: return immediately (fast path)
        - If in async context: use nest_asyncio or thread pool to avoid deadlock
        - If no event loop: run synchronously with asyncio.run()
        """
        # Fast path: already initialized
        if self._initialized and self._model is not None:
            return

        import asyncio
        import concurrent.futures

        try:
            asyncio.get_running_loop()
            # We're in async context - CANNOT block on same loop
            # Use a thread pool to run the async init without deadlock
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:

                def _run_init() -> None:
                    """Run async init in a new event loop in this thread."""
                    asyncio.run(self._ensure_initialized_async())

                future = executor.submit(_run_init)
                # Wait with timeout - this blocks the calling coroutine but not the event loop
                # because we're running in a separate thread
                future.result(timeout=60.0)

        except RuntimeError:
            # No event loop running - safe to use asyncio.run()
            asyncio.run(self._ensure_initialized_async())

    def _wire_strange_loop(self) -> None:
        """Wire Strange Loop to EgoModel and LatentMultimodalPlanner.

        Delegates to WorldModelInitializer.wire_strange_loop().
        """
        if self._strange_loop_wired or self._model is None:
            return

        success = self.initializer.wire_strange_loop(self._model)
        if success:
            self._strange_loop_wired = True

    def _init_cuda_graphs(self) -> None:
        """Initialize CUDA Graph wrappers if enabled in config.

        ADDED: December 31, 2025

        Reads config and creates CUDAGraphWrapper instances for encode/decode
        operations. Graph capture happens lazily on first inference call.

        Prerequisites:
        - Model must be initialized
        - CUDA must be available
        - use_cuda_graphs must be True in config
        """
        if self._model is None:
            return

        # Check config for CUDA graphs setting
        try:
            config = getattr(self._model, "config", None)
            if config is None:
                logger.debug("CUDA Graphs: No config found, disabled")
                return

            self._use_cuda_graphs = getattr(config, "use_cuda_graphs", False)
            self._cuda_graph_warmup_iterations = getattr(config, "cuda_graph_warmup_iterations", 3)
        except Exception as e:
            logger.debug(f"CUDA Graphs: Config access failed: {e}")
            return

        if not self._use_cuda_graphs:
            logger.debug("CUDA Graphs disabled in config")
            return

        # Check CUDA availability
        torch = _lazy_import_torch()
        if not torch.cuda.is_available():
            logger.info("CUDA Graphs requested but CUDA not available, disabling")
            self._use_cuda_graphs = False
            return

        # Create wrappers for encode and decode
        # Note: Graph capture happens lazily on first call to each wrapper
        logger.info(f"CUDA Graphs enabled: warmup_iterations={self._cuda_graph_warmup_iterations}")

        # We create the wrappers here but they don't capture until first call
        # This allows the model to be fully set up before capture

    def _get_cuda_graph_encode(self) -> CUDAGraphWrapper:
        """Get or create CUDA Graph wrapper for encode operation.

        Creates wrapper lazily on first request. The wrapper itself handles
        warmup and graph capture on first inference call.
        """
        if self._cuda_graph_encode is None and self._model is not None:
            self._cuda_graph_encode = CUDAGraphWrapper(
                forward_fn=self._encode_for_graph,
                warmup_iterations=self._cuda_graph_warmup_iterations,
            )
        assert self._cuda_graph_encode is not None
        return self._cuda_graph_encode

    def _get_cuda_graph_decode(self) -> CUDAGraphWrapper:
        """Get or create CUDA Graph wrapper for decode operation.

        Creates wrapper lazily on first request. The wrapper itself handles
        warmup and graph capture on first inference call.
        """
        if self._cuda_graph_decode is None and self._model is not None:
            self._cuda_graph_decode = CUDAGraphWrapper(
                forward_fn=self._decode_for_graph,
                warmup_iterations=self._cuda_graph_warmup_iterations,
            )
        assert self._cuda_graph_decode is not None
        return self._cuda_graph_decode

    def _encode_for_graph(self, x: Any) -> Any:
        """Encode function suitable for CUDA Graph capture.

        This is a thin wrapper around model.encode() that ensures
        the operation is suitable for graph capture (no dynamic control flow).
        """
        if self._model is None:
            raise RuntimeError("Model not initialized")
        return self._model.encode(x)

    def _decode_for_graph(self, e8_code: Any) -> Any:
        """Decode function suitable for CUDA Graph capture.

        This is a thin wrapper around unified_hourglass.decode() that ensures
        the operation is suitable for graph capture (no dynamic control flow).
        """
        if self._model is None:
            raise RuntimeError("Model not initialized")
        return self._model.unified_hourglass.decode(e8_code, return_all=True)

    @property
    def model(self) -> KagamiWorldModel | None:
        """Get KagamiWorldModel (HARDENED - all features enabled)."""
        self._ensure_initialized()
        return self._model

    async def get_model_async(self) -> KagamiWorldModel | None:
        """Get KagamiWorldModel asynchronously (preferred in async contexts).

        ADDED (Dec 29, 2025): Use this instead of .model property in async code
        to avoid blocking the event loop during initialization.
        """
        await self._ensure_initialized_async()
        return self._model

    @property
    def is_available(self) -> bool:
        """Check if world model is available."""
        self._ensure_initialized()
        return self._model is not None

    @property
    def device(self) -> Any:  # torch.device
        """Get model device."""
        self._ensure_initialized()
        if self._device is not None:
            return self._device
        torch = _lazy_import_torch()
        return torch.device("cpu")

    @property
    def active_inference(self) -> Any:
        """Get Active Inference engine."""
        if self.model is None:
            return None
        return getattr(self.model, "_active_inference_engine", None)

    @property
    def empowerment(self) -> MultiStepEmpowerment | None:
        """Get empowerment estimator."""
        if self.model is None:
            return None
        return getattr(self.model, "_empowerment_estimator", None)

    @property
    def rssm(self) -> Any:
        """Get RSSM dynamics model (OrganismRSSM)."""
        if self.model is None:
            return None
        return getattr(self.model, "organism_rssm", None)

    @property
    def chaos_dynamics(self) -> Any:
        """Get chaos/catastrophe dynamics."""
        if self.model is None:
            return None
        return getattr(self.model, "_chaos_catastrophe_dynamics", None)

    @property
    def strange_loop(self) -> Any:
        """Get HofstadterStrangeLoop from OrganismRSSM.

        Returns the self-reference module containing mu_self.

        NOTE (December 13, 2025): Prefer using `mu_self` or `s7_tracker`
        directly from the model for the new S7-based strange loop.
        """
        if self.model is None:
            return None
        rssm = getattr(self.model, "rssm", None)
        if rssm is None:
            return None
        return getattr(rssm, "strange_loop", None)

    @property
    def mu_self(self) -> Any:  # torch.Tensor | None
        """Get μ_self fixed point in S7 space (7D).

        ADDED: December 13, 2025

        μ_self lives in S7 (7D) - mathematically meaningful:
        - S7 = unit imaginary octonions = 7 colonies
        - Each dimension corresponds to one Fano plane axis
        - The strange loop closure is: s7_{t+1} ≈ s7_t

        Returns:
            7D tensor representing the current self-representation,
            or None if model unavailable.
        """
        if self.model is None:
            return None
        return getattr(self.model, "mu_self", None)

    @property
    def s7_tracker(self) -> Any:
        """Get StrangeLoopS7Tracker for fixed point convergence.

        ADDED: December 13, 2025

        Returns the tracker that monitors s7_{t+1} ≈ s7_t convergence.
        """
        if self.model is None:
            return None
        return getattr(self.model, "s7_tracker", None)

    @property
    def s7_hierarchy(self) -> Any:
        """Get S7AugmentedHierarchy for S7 extraction at all levels.

        ADDED: December 13, 2025

        Returns the hierarchy that extracts S7 phase at E8, E7, E6, F4, G2.
        """
        if self.model is None:
            return None
        return getattr(self.model, "s7_hierarchy", None)

    @property
    def godelian_wrapper(self) -> Any:
        """Get GodelianSelfReference wrapper for TRUE self-reference.

        Returns the Gödelian wrapper that provides:
        - Self-inspection via inspect.getsource()
        - Self-referential weight encoding (SRWM-style)
        - LLM-based self-modification capability

        Added: December 7, 2025
        """
        try:
            # Dynamic import to avoid world_model.service ↔ strange_loops.integration cycles.
            import importlib

            sl_mod = importlib.import_module("kagami.core.strange_loops.integration")
            get_godelian_wrapper = getattr(sl_mod, "get_godelian_wrapper", None)
            if get_godelian_wrapper is None:
                return None
            return get_godelian_wrapper(self.strange_loop)
        except Exception:
            return None

    def encode(
        self,
        observation: Any,  # torch.Tensor | dict[str, Any] | str
    ) -> Any:  # CoreState | None
        """Encode observation to CoreState.

        Args:
            observation: Tensor, dict[str, Any], or string to encode

        Returns:
            CoreState if successful, None otherwise

        OPTIMIZED (Dec 31, 2025):
        - Uses inference_mode for faster inference
        - Supports CUDA Graphs for low-latency inference with static shapes
        """
        if self.model is None:
            return None

        start = time.perf_counter()
        self.metrics.encode_calls += 1
        self.metrics.last_access = time.time()

        try:
            torch = _lazy_import_torch()
            # OPTIMIZED (Dec 31, 2025): Use inference_mode for faster inference
            # inference_mode is faster than no_grad because it also disables version tracking
            self.model.eval()  # Ensure dropout/batchnorm are in eval mode

            if isinstance(observation, torch.Tensor):
                if observation.dim() == 2:
                    observation = observation.unsqueeze(1)
                obs_tensor = observation.to(self.device)

                # Use CUDA Graphs for tensor inputs if enabled (Dec 31, 2025)
                if self._use_cuda_graphs and obs_tensor.is_cuda:
                    try:
                        graph_wrapper = self._get_cuda_graph_encode()
                        core_state, _ = graph_wrapper(obs_tensor)
                        self.metrics.total_encode_ms += (time.perf_counter() - start) * 1000
                        return core_state
                    except ValueError as e:
                        # Shape mismatch - fall back to standard encode
                        logger.warning(f"CUDA Graph encode fallback: {e}")

                # Standard encode path (or fallback)
                with torch.inference_mode():
                    core_state, _ = self.model.encode(obs_tensor)
                    self.metrics.total_encode_ms += (time.perf_counter() - start) * 1000
                    return core_state
            else:
                # Use encode_observation for non-tensor inputs
                # CUDA Graphs not applicable for text/dict inputs (variable shapes)
                with torch.inference_mode():
                    semantic_state = self.model.encode_observation(observation)
                    self.metrics.total_encode_ms += (time.perf_counter() - start) * 1000
                    # Convert SemanticState to CoreState
                    return self._semantic_to_core_state(semantic_state)

        except Exception as e:
            logger.error(f"Encode failed: {e}")
            return None

    def decode(
        self,
        core_state: Any,  # CoreState
    ) -> Any:  # torch.Tensor | None
        """Decode CoreState to output tensor.

        Args:
            core_state: CoreState to decode

        Returns:
            Output tensor if successful, None otherwise

        OPTIMIZED (Dec 31, 2025):
        - Uses inference_mode for faster inference
        - Supports CUDA Graphs for low-latency inference with static shapes
        """
        if self.model is None:
            return None

        start = time.perf_counter()
        self.metrics.decode_calls += 1
        self.metrics.last_access = time.time()

        try:
            torch = _lazy_import_torch()
            # OPTIMIZED (Dec 31, 2025): Use inference_mode for faster inference
            self.model.eval()

            # Extract e8_code for CUDA Graph path
            e8_code = getattr(core_state, "e8_code", None)

            # Use CUDA Graphs if enabled and e8_code is on CUDA (Dec 31, 2025)
            if (
                self._use_cuda_graphs
                and e8_code is not None
                and isinstance(e8_code, torch.Tensor)
                and e8_code.is_cuda
            ):
                try:
                    graph_wrapper = self._get_cuda_graph_decode()
                    dec_result = graph_wrapper(e8_code)
                    if isinstance(dec_result, dict):
                        output = dec_result.get("bulk", torch.tensor([]))
                    else:
                        output = (
                            dec_result if isinstance(dec_result, torch.Tensor) else torch.tensor([])
                        )
                    self.metrics.total_decode_ms += (time.perf_counter() - start) * 1000
                    return output
                except ValueError as e:
                    # Shape mismatch - fall back to standard decode
                    logger.warning(f"CUDA Graph decode fallback: {e}")

            # Standard decode path (or fallback)
            with torch.inference_mode():
                output, _ = self.model.decode(core_state)
                self.metrics.total_decode_ms += (time.perf_counter() - start) * 1000
                return output

        except Exception as e:
            logger.error(f"Decode failed: {e}")
            return None

    def predict(
        self,
        observation: Any,
        action: dict[str, Any] | None = None,
        horizon: int = 1,
    ) -> Any:
        """Predict next state.

        Args:
            observation: Current observation
            action: Action to take (optional)
            horizon: Prediction horizon

        Returns:
            Prediction object
        """
        if self.model is None:
            return None

        start = time.perf_counter()
        self.metrics.predict_calls += 1
        self.metrics.last_access = time.time()

        try:
            torch = _lazy_import_torch()
            # OPTIMIZED (Dec 31, 2025): Use inference_mode for faster inference
            self.model.eval()
            with torch.inference_mode():
                current_state = self.model.encode_observation(observation)
                prediction = self.model.predict_next_state(
                    current_state,
                    action=action or {},
                    horizon=horizon,
                )
                self.metrics.total_predict_ms += (time.perf_counter() - start) * 1000
                return prediction

        except Exception as e:
            logger.error(f"Predict failed: {e}")
            return None

    async def select_action_ai(
        self,
        observation: dict[str, Any],
        candidates: list[dict[str, Any]] | None = None,
        goals: Any = None,  # torch.Tensor | None
    ) -> dict[str, Any]:
        """Select action using Active Inference.

        Args:
            observation: Current observation
            candidates: Candidate actions
            goals: Goal tensor

        Returns:
            Selected action dict[str, Any]
        """
        if self.model is None:
            return {}

        self.metrics.inference_calls += 1
        self.metrics.last_access = time.time()

        return await self.model.select_action_active_inference(observation, candidates, goals)

    def compute_empowerment(
        self,
        state: Any,  # torch.Tensor
        horizon: int = 5,
    ) -> Any:  # torch.Tensor | None
        """Compute empowerment for state.

        Args:
            state: State tensor
            horizon: Planning horizon

        Returns:
            Empowerment value
        """
        if self.model is None:
            return None

        return self.model.compute_empowerment(state.to(self.device), horizon)

    async def validate_predicted_state(
        self,
        predicted_state: Any,  # torch.Tensor | SemanticState | LatentState
        action: dict[str, Any] | Any,  # dict[str, Any] or torch.Tensor
        uncertainty: float | None = None,
    ) -> bool:
        """Validate predicted state satisfies safety constraints.

        CRITICAL: H-JEPA prediction validation gate (December 21, 2025).
        Ensures predicted states are safe before executing actions.

        Uses higher safety margin for predictions due to model uncertainty:
        - Base margin: 15% (predictions are less certain than observations)
        - Uncertainty margin: 3-sigma rule (3 * uncertainty)
        - Total margin: base + uncertainty (conservative safety)

        Args:
            predicted_state: Predicted state tensor [*, D] or SemanticState/LatentState
            action: Action that led to this prediction (dict[str, Any] or tensor)
            uncertainty: Prediction uncertainty if available (0.0-1.0)

        Returns:
            True if predicted state is safe to execute, False otherwise

        Raises:
            None - Always returns bool (fail-closed on errors)
        """
        try:
            # Import here to avoid circular dependency
            from kagami.core.safety.cbf_integration import check_cbf_for_operation

            torch = _lazy_import_torch()

            # Extract state representation for safety check
            if hasattr(predicted_state, "embedding"):
                # SemanticState or LatentState
                state_embedding = predicted_state.embedding
                if hasattr(state_embedding, "numpy"):
                    state_embedding = state_embedding.detach().cpu().numpy()
                # threat, uncertainty, complexity, risk
                state_vector = state_embedding.flatten()[:4]
            elif isinstance(predicted_state, torch.Tensor):
                # Raw tensor
                state_vector = predicted_state.detach().cpu().numpy().flatten()[:4]
            else:
                logger.warning(
                    f"Unknown predicted_state type: {type(predicted_state)}, "
                    "using conservative safety estimate"
                )
                state_vector = [0.2, 0.3, 0.2, 0.3]  # Medium risk estimate

            # Ensure we have 4 dimensions (threat, uncertainty, complexity, risk)
            if len(state_vector) < 4:
                # Pad with medium-risk estimates if not enough dimensions
                state_vector = list(state_vector) + [0.25] * (4 - len(state_vector))

            # Calculate required safety margin based on uncertainty
            base_margin = 0.15  # 15% margin for predictions (vs 0% for observations)
            uncertainty_value = uncertainty if uncertainty is not None else 0.1  # Default 10%
            uncertainty_margin = 3.0 * uncertainty_value  # 3-sigma rule (99.7% confidence)
            required_margin = base_margin + uncertainty_margin

            # Extract action description for logging
            action_desc = "unknown"
            if isinstance(action, dict):
                action_desc = str(action.get("action", action.get("type", "unknown")))
            elif isinstance(action, torch.Tensor):
                action_desc = f"tensor[{tuple(action.shape)}]"

            logger.debug(
                f"H-JEPA prediction validation: action={action_desc}, "
                f"uncertainty={uncertainty_value:.3f}, required_margin={required_margin:.3f}"
            )

            # Run CBF safety check on predicted state
            # Use metadata to indicate this is a prediction (not actual state)
            state_list = (
                state_vector.tolist() if hasattr(state_vector, "tolist") else list(state_vector)
            )
            result = await check_cbf_for_operation(
                operation="prediction_validation",
                action="h_jepa_predicted_action",
                target="predicted_state",
                metadata={
                    "predicted": True,
                    "uncertainty": uncertainty_value,
                    "required_margin": required_margin,
                    "action": action_desc,
                    "state_vector": state_list,
                },
            )

            # Enforce higher margin for predictions (conservative safety)
            if result.h_x is None:
                logger.warning(
                    f"Prediction validation failed: h(x') is None, rejecting action={action_desc}"
                )
                return False

            if result.h_x < required_margin:
                logger.warning(
                    f"Prediction rejected: h(x')={result.h_x:.3f} < "
                    f"required_margin={required_margin:.3f} for action={action_desc}"
                )
                return False

            logger.debug(
                f"Prediction validated: h(x')={result.h_x:.3f} >= "
                f"required_margin={required_margin:.3f} for action={action_desc}"
            )
            return True

        except Exception as e:
            # FAIL CLOSED: If validation fails to execute, reject action (safe default)
            logger.error(
                f"Prediction validation execution error: {e}, "
                f"failing closed (rejecting action={action})",
                exc_info=True,
            )
            return False

    def get_catastrophe_risk(
        self,
        embedding: Any,  # torch.Tensor
    ) -> float:
        """Get catastrophe risk for embedding.

        Args:
            embedding: State embedding

        Returns:
            Risk score [0, 1]
        """
        if self.model is None:
            return 0.0

        return self.model.get_catastrophe_risk(embedding.to(self.device))

    def quantize(
        self,
        mode: str = "dynamic",
        calibration_data: Any = None,
        keep_original: bool = False,
        compile_mode: str | None = None,
    ) -> Any:
        """Apply INT8 quantization to world model for inference speedup.

        ADDED: December 31, 2025

        Quantization reduces model size and speeds up inference on CPU:
        - Dynamic: 2-4x speedup, no calibration needed
        - Static: 3-5x speedup, requires calibration data
        - Combined with torch.compile: up to 6x speedup

        Args:
            mode: Quantization mode ("dynamic" or "static")
            calibration_data: DataLoader for static quantization calibration
            keep_original: Keep original FP32 model for verification
            compile_mode: Optional torch.compile mode ("inference", "training", None)

        Returns:
            QuantizedWorldModel wrapper with quantized model

        Raises:
            RuntimeError: If model not initialized
            ValueError: If static mode without calibration_data

        Example:
            >>> service = get_world_model_service()
            >>> quantized = service.quantize(mode="dynamic")
            >>> # Use quantized model for fast inference
            >>> state = quantized.quantized_model.encode(observation)

            >>> # With static quantization (better performance)
            >>> quantized = service.quantize(
            ...     mode="static",
            ...     calibration_data=calibration_loader,
            ... )

            >>> # With torch.compile for maximum speedup
            >>> quantized = service.quantize(
            ...     mode="dynamic",
            ...     compile_mode="inference",
            ... )
        """
        if self.model is None:
            raise RuntimeError("World model not initialized. Call ensure_initialized() first.")

        # Lazy import quantization module
        from kagami.core.world_model.quantization import (
            QuantizationConfig,
            QuantizedWorldModel,
            quantize_with_compile,
        )

        # Validate mode
        if mode not in ("dynamic", "static"):
            raise ValueError(f"Invalid quantization mode: {mode}. Use 'dynamic' or 'static'.")

        # Validate static mode has calibration data
        if mode == "static" and calibration_data is None:
            raise ValueError(
                "Static quantization requires calibration_data. "
                "Use mode='dynamic' for calibration-free quantization."
            )

        logger.info(
            f"Applying INT8 quantization: mode={mode}, "
            f"compile={compile_mode}, keep_original={keep_original}"
        )

        # Create quantization config
        config = QuantizationConfig(
            mode=mode,  # type: ignore[arg-type]
        )

        # Apply quantization (with optional compilation)
        if compile_mode is not None:
            # Use combined quantization + compilation
            quantized_model = quantize_with_compile(
                self.model,
                compile_mode=compile_mode,  # type: ignore[arg-type]
                quantization_config=config,
            )
            # Wrap in QuantizedWorldModel for consistent API
            return QuantizedWorldModel(
                quantized_model=quantized_model,
                original_model=self.model if keep_original else None,
                config=config,
            )
        else:
            # Use QuantizedWorldModel factory
            return QuantizedWorldModel.from_model(
                self.model,
                config=config,
                calibration_data=calibration_data,
                keep_original=keep_original,
            )

    def _semantic_to_core_state(self, semantic_state: Any) -> Any:  # CoreState | None
        """Convert SemanticState to CoreState (delegates to initializer)."""
        if self._model is None:
            return None
        return self.initializer.semantic_to_core_state(semantic_state, self._model)

    def get_metrics(self) -> dict[str, Any]:
        """Get service metrics."""
        return {
            "available": self.is_available,
            "device": str(self.device),
            "encode_calls": self.metrics.encode_calls,
            "decode_calls": self.metrics.decode_calls,
            "predict_calls": self.metrics.predict_calls,
            "inference_calls": self.metrics.inference_calls,
            "avg_encode_ms": self.metrics.avg_encode_ms,
            "avg_decode_ms": self.metrics.avg_decode_ms,
            "avg_predict_ms": self.metrics.avg_predict_ms,
            "last_access": self.metrics.last_access,
            "features": self._get_feature_status(),
            "cuda_graphs": self._get_cuda_graph_status(),
        }

    def _get_cuda_graph_status(self) -> dict[str, Any]:
        """Get CUDA Graph status and statistics.

        ADDED: December 31, 2025
        """
        status: dict[str, Any] = {
            "enabled": self._use_cuda_graphs,
            "warmup_iterations": self._cuda_graph_warmup_iterations,
        }

        if self._cuda_graph_encode is not None:
            status["encode_graph"] = {
                "captured": self._cuda_graph_encode._captured,
                "input_shape": self._cuda_graph_encode._input_shape,
            }

        if self._cuda_graph_decode is not None:
            status["decode_graph"] = {
                "captured": self._cuda_graph_decode._captured,
                "input_shape": self._cuda_graph_decode._input_shape,
            }

        return status

    def _get_feature_status(self) -> dict[str, bool]:
        """Get status of world model features."""
        if self.model is None:
            return {}

        return {
            "active_inference": self.active_inference is not None,
            "empowerment": self.empowerment is not None,
            "rssm": self.rssm is not None,
            "chaos_dynamics": self.chaos_dynamics is not None,
            "strange_loop": self.strange_loop is not None,
            "strange_loop_wired": self._strange_loop_wired,
            "godelian_wrapper": self.godelian_wrapper is not None,  # TRUE self-reference
            "hardened": True,  # All features always enabled
        }

    def reset(self) -> None:
        """Reset service state (for testing)."""
        self._model = None
        self._initialized = False
        self._strange_loop_wired = False
        self._device = None
        self.metrics = WorldModelMetrics()

        # Reset CUDA Graph wrappers (Dec 31, 2025)
        if self._cuda_graph_encode is not None:
            self._cuda_graph_encode.reset()
        if self._cuda_graph_decode is not None:
            self._cuda_graph_decode.reset()
        self._cuda_graph_encode = None
        self._cuda_graph_decode = None
        self._use_cuda_graphs = False

    def save_state(self, path: str | Path) -> None:
        """Save service state to checkpoint.

        Serializes WorldModelMetrics to a checkpoint file using torch.save().
        This allows metrics to persist across restarts.

        Args:
            path: Path to save checkpoint file (.pt or .pth recommended)

        Example:
            >>> service = get_world_model_service()
            >>> service.save_state("/tmp/world_model_checkpoint.pt")
        """
        torch = _lazy_import_torch()

        state = {
            "metrics": asdict(self.metrics),
            "timestamp": datetime.now().isoformat(),
            "version": "1.0",
        }
        torch.save(state, path)
        logger.info(f"WorldModelService state saved to {path}")

    def load_state(self, path: str | Path) -> None:
        """Load service state from checkpoint.

        Restores WorldModelMetrics from a checkpoint file.
        If the file doesn't exist, the operation is a no-op.

        Args:
            path: Path to checkpoint file

        Example:
            >>> service = get_world_model_service()
            >>> service.load_state("/tmp/world_model_checkpoint.pt")
        """
        path = Path(path)
        if not path.exists():
            logger.debug(f"No checkpoint found at {path}, skipping load")
            return

        torch = _lazy_import_torch()

        try:
            state = torch.load(path, weights_only=False)

            # Validate version
            version = state.get("version", "unknown")
            if version != "1.0":
                logger.warning(f"Checkpoint version mismatch: expected 1.0, got {version}")

            # Restore metrics
            metrics_dict = state.get("metrics", {})
            self.metrics = WorldModelMetrics(
                encode_calls=metrics_dict.get("encode_calls", 0),
                decode_calls=metrics_dict.get("decode_calls", 0),
                predict_calls=metrics_dict.get("predict_calls", 0),
                inference_calls=metrics_dict.get("inference_calls", 0),
                total_encode_ms=metrics_dict.get("total_encode_ms", 0.0),
                total_decode_ms=metrics_dict.get("total_decode_ms", 0.0),
                total_predict_ms=metrics_dict.get("total_predict_ms", 0.0),
                last_access=metrics_dict.get("last_access", time.time()),
            )

            timestamp = state.get("timestamp", "unknown")
            logger.info(f"WorldModelService state loaded from {path} (saved at {timestamp})")

        except Exception as e:
            logger.error(f"Failed to load state from {path}: {e}")
            # Keep current metrics on failure (don't corrupt state)


# Singleton
_world_model_service: WorldModelService | None = None


def get_world_model_service() -> WorldModelService:
    """Get singleton world model service.

    THE CANONICAL ENTRY POINT for world model access.

    All modules should use this instead of:
    - get_kagami_world_model() (deprecated)
    - get_world_model_registry().get_primary() (deprecated)
    - Direct KagamiWorldModel imports (deprecated)

    Returns:
        WorldModelService singleton instance
    """
    global _world_model_service
    if _world_model_service is None:
        _world_model_service = WorldModelService()
    return _world_model_service


def reset_world_model_service() -> None:
    """Reset service (for testing)."""
    global _world_model_service
    if _world_model_service is not None:
        _world_model_service.reset()
    _world_model_service = None


__all__ = [
    "CUDAGraphWrapper",
    "WorldModelMetrics",
    "WorldModelService",
    "get_world_model_service",
    "reset_world_model_service",
]
