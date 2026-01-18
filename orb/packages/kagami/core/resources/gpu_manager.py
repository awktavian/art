"""GPU memory management with automatic cleanup.

Provides safe GPU operations with guaranteed memory cleanup,
preventing CUDA out-of-memory errors.
"""

import asyncio
import logging
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Literal

from kagami.core.resources.tracker import track_resource

logger = logging.getLogger(__name__)

# Try to import torch, but make it optional
try:
    import torch
    import torch.cuda as cuda

    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None  # type: ignore[assignment]
    cuda = None  # type: ignore[assignment]


@dataclass
class GPUResource:
    """Represents a GPU resource (tensor, model, etc).

    Attributes:
        resource: The actual resource (tensor, model, etc)
        device: GPU device ID
        memory_bytes: Memory usage in bytes
        resource_type: Type of resource (tensor, model, etc)
    """

    resource: Any
    device: int | str
    memory_bytes: int
    resource_type: str


class GPUMemoryManager:
    """Managed GPU memory with automatic cleanup.

    Features:
    - Automatic CUDA memory cleanup
    - Memory leak detection
    - Device management
    - Cache clearing
    - Memory metrics

    Usage:
        async with GPUMemoryManager(device='cuda:0') as gpu:
            tensor = gpu.allocate((1000, 1000))
            result = await model(tensor)
            # Automatic cleanup on exit

        # With explicit resources
        async with GPUMemoryManager() as gpu:
            tensor1 = torch.randn(100, 100, device='cuda')
            gpu.track(tensor1, "tensor")

            tensor2 = torch.randn(200, 200, device='cuda')
            gpu.track(tensor2, "tensor")

            # Both cleaned up automatically
    """

    def __init__(
        self,
        device: str | int | None = None,
        clear_cache: bool = True,
        synchronize: bool = True,
    ) -> None:
        """Initialize GPU memory manager.

        Args:
            device: GPU device ID or 'cuda'/'cuda:N' (None for auto)
            clear_cache: Whether to clear CUDA cache on cleanup
            synchronize: Whether to synchronize before cleanup
        """
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch is not available. Install torch to use GPUMemoryManager.")

        self.device = self._resolve_device(device)
        self.clear_cache = clear_cache
        self.synchronize = synchronize
        self._resources: dict[int, GPUResource] = {}
        self._resource_id: str | None = None
        self._total_allocated = 0
        self._peak_allocated = 0

    def _resolve_device(self, device: str | int | None) -> str:
        """Resolve device string.

        Args:
            device: Device specification

        Returns:
            Device string like 'cuda:0'
        """
        if device is None:
            if cuda.is_available():
                return f"cuda:{cuda.current_device()}"
            return "cpu"

        if isinstance(device, int):
            return f"cuda:{device}"

        return device

    async def __aenter__(self) -> "GPUMemoryManager":
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Literal[False]:
        """Async context manager exit with cleanup."""
        await self.cleanup()
        return False

    async def initialize(self) -> None:
        """Initialize GPU resources."""
        # Track manager
        self._resource_id = track_resource(
            resource_type="gpu",
            resource_id=self.device,
            metadata={
                "device": self.device,
                "available": cuda.is_available() if cuda else False,
                "memory_total": (
                    cuda.get_device_properties(self.device).total_memory
                    if cuda and cuda.is_available()
                    else 0
                ),
            },
        )

        # Record initial memory
        if cuda and cuda.is_available():
            self._total_allocated = cuda.memory_allocated(self.device)
            self._peak_allocated = cuda.max_memory_allocated(self.device)

        logger.debug(f"GPU memory manager initialized on {self.device}")

    async def cleanup(self) -> None:
        """Cleanup GPU resources."""
        cleanup_errors = []

        try:
            # Delete tracked resources
            for resource_id, gpu_resource in list(self._resources.items()):
                try:
                    await self._cleanup_resource(gpu_resource)
                except Exception as e:
                    cleanup_errors.append(e)
                    logger.error(f"Failed to cleanup GPU resource {resource_id}: {e}")

            self._resources.clear()

            # Synchronize if requested
            if self.synchronize and cuda and cuda.is_available():
                try:
                    if self.device.startswith("cuda"):
                        device_num = int(self.device.split(":")[-1]) if ":" in self.device else 0
                        cuda.synchronize(device_num)
                except Exception as e:
                    cleanup_errors.append(e)
                    logger.error(f"Failed to synchronize GPU: {e}")

            # Clear cache if requested
            if self.clear_cache and cuda and cuda.is_available():
                try:
                    cuda.empty_cache()
                except Exception as e:
                    cleanup_errors.append(e)
                    logger.error(f"Failed to clear GPU cache: {e}")

            # Log memory stats
            if cuda and cuda.is_available():
                final_allocated = cuda.memory_allocated(self.device)
                peak = cuda.max_memory_allocated(self.device)
                freed = self._total_allocated - final_allocated

                logger.debug(
                    f"GPU cleanup: freed={freed / 1024 / 1024:.2f}MB, "
                    f"peak={peak / 1024 / 1024:.2f}MB, "
                    f"remaining={final_allocated / 1024 / 1024:.2f}MB"
                )

        finally:
            # Untrack resource
            if self._resource_id:
                from kagami.core.resources.tracker import get_resource_tracker

                tracker = get_resource_tracker()
                tracker.untrack(self._resource_id)
                self._resource_id = None

            # Raise first cleanup error if any
            if cleanup_errors:
                raise cleanup_errors[0]

    async def _cleanup_resource(self, gpu_resource: GPUResource) -> None:
        """Cleanup a single GPU resource.

        Args:
            gpu_resource: Resource to cleanup
        """
        resource = gpu_resource.resource

        # Delete tensor/model
        if hasattr(resource, "cpu"):
            # Move to CPU first to free GPU memory
            try:
                resource.cpu()
            except Exception:
                pass

        # Delete reference
        del resource

    def track(self, resource: Any, resource_type: str = "tensor") -> int:
        """Track a GPU resource for automatic cleanup.

        Args:
            resource: Resource to track (tensor, model, etc)
            resource_type: Type of resource

        Returns:
            Resource ID for untracking
        """
        # Calculate memory usage
        memory_bytes = 0
        if hasattr(resource, "element_size") and hasattr(resource, "nelement"):
            memory_bytes = resource.element_size() * resource.nelement()
        elif hasattr(resource, "numel"):
            memory_bytes = resource.numel() * 4  # Assume float32

        # Get device
        device = str(resource.device) if hasattr(resource, "device") else self.device

        # Track resource
        resource_id = id(resource)
        gpu_resource = GPUResource(
            resource=resource,
            device=device,
            memory_bytes=memory_bytes,
            resource_type=resource_type,
        )
        self._resources[resource_id] = gpu_resource

        logger.debug(
            f"Tracking GPU resource: type={resource_type}, "
            f"memory={memory_bytes / 1024 / 1024:.2f}MB"
        )

        return resource_id

    def untrack(self, resource_id: int) -> None:
        """Stop tracking a resource.

        Args:
            resource_id: Resource ID from track()
        """
        if resource_id in self._resources:
            del self._resources[resource_id]

    def allocate(
        self,
        shape: tuple[int, ...],
        dtype: Any = None,
        requires_grad: bool = False,
    ) -> Any:
        """Allocate a tensor on GPU.

        Args:
            shape: Tensor shape
            dtype: Data type (default: float32)
            requires_grad: Whether to track gradients

        Returns:
            Allocated tensor
        """
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch is not available")

        dtype = dtype or torch.float32
        tensor = torch.empty(shape, dtype=dtype, device=self.device, requires_grad=requires_grad)
        self.track(tensor, "tensor")
        return tensor

    def zeros(
        self,
        shape: tuple[int, ...],
        dtype: Any = None,
        requires_grad: bool = False,
    ) -> Any:
        """Allocate a zero-initialized tensor on GPU.

        Args:
            shape: Tensor shape
            dtype: Data type (default: float32)
            requires_grad: Whether to track gradients

        Returns:
            Zero tensor
        """
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch is not available")

        dtype = dtype or torch.float32
        tensor = torch.zeros(shape, dtype=dtype, device=self.device, requires_grad=requires_grad)
        self.track(tensor, "tensor")
        return tensor

    def ones(
        self,
        shape: tuple[int, ...],
        dtype: Any = None,
        requires_grad: bool = False,
    ) -> Any:
        """Allocate a one-initialized tensor on GPU.

        Args:
            shape: Tensor shape
            dtype: Data type (default: float32)
            requires_grad: Whether to track gradients

        Returns:
            Ones tensor
        """
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch is not available")

        dtype = dtype or torch.float32
        tensor = torch.ones(shape, dtype=dtype, device=self.device, requires_grad=requires_grad)
        self.track(tensor, "tensor")
        return tensor

    def randn(
        self,
        shape: tuple[int, ...],
        dtype: Any = None,
        requires_grad: bool = False,
    ) -> Any:
        """Allocate a random normal tensor on GPU.

        Args:
            shape: Tensor shape
            dtype: Data type (default: float32)
            requires_grad: Whether to track gradients

        Returns:
            Random tensor
        """
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch is not available")

        dtype = dtype or torch.float32
        tensor = torch.randn(shape, dtype=dtype, device=self.device, requires_grad=requires_grad)
        self.track(tensor, "tensor")
        return tensor

    def to_device(self, tensor: Any) -> Any:
        """Move tensor to managed device.

        Args:
            tensor: Tensor to move

        Returns:
            Tensor on device
        """
        result = tensor.to(self.device)
        self.track(result, "tensor")
        return result

    def get_memory_stats(self) -> dict[str, Any]:
        """Get GPU memory statistics.

        Returns:
            Memory stats dict[str, Any]
        """
        if not cuda or not cuda.is_available():
            return {
                "available": False,
                "device": self.device,
            }

        device_num = int(self.device.split(":")[-1]) if ":" in self.device else 0

        return {
            "available": True,
            "device": self.device,
            "allocated": cuda.memory_allocated(device_num),
            "reserved": cuda.memory_reserved(device_num),
            "max_allocated": cuda.max_memory_allocated(device_num),
            "total": cuda.get_device_properties(device_num).total_memory,
            "tracked_resources": len(self._resources),
        }


@contextmanager
def gpu_memory_scope(
    device: str | int | None = None,
    clear_cache: bool = True,
    synchronize: bool = True,
):
    """Synchronous context manager for GPU memory.

    Args:
        device: GPU device
        clear_cache: Whether to clear cache on exit
        synchronize: Whether to synchronize on exit

    Yields:
        GPUMemoryManager instance
    """
    manager = GPUMemoryManager(device=device, clear_cache=clear_cache, synchronize=synchronize)

    try:
        # Initialize synchronously
        loop = asyncio.get_event_loop()
        loop.run_until_complete(manager.initialize())

        yield manager
    finally:
        # Cleanup synchronously
        loop = asyncio.get_event_loop()
        loop.run_until_complete(manager.cleanup())


def clear_gpu_cache(device: str | int | None = None) -> None:
    """Clear GPU cache immediately.

    Args:
        device: GPU device (None for current)
    """
    if not cuda or not cuda.is_available():
        return

    if device is None:
        cuda.empty_cache()
    else:
        # Set device and clear
        if isinstance(device, str):
            device = int(device.split(":")[-1]) if ":" in device else 0
        with cuda.device(device):
            cuda.empty_cache()

    logger.debug(f"GPU cache cleared for device {device}")


def synchronize_gpu(device: str | int | None = None) -> None:
    """Synchronize GPU operations.

    Args:
        device: GPU device (None for current)
    """
    if not cuda or not cuda.is_available():
        return

    if device is None:
        cuda.synchronize()
    else:
        if isinstance(device, str):
            device = int(device.split(":")[-1]) if ":" in device else 0
        cuda.synchronize(device)

    logger.debug(f"GPU synchronized for device {device}")
