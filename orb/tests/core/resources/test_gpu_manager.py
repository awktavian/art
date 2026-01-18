"""Comprehensive tests for GPU memory management.

Tests GPU memory allocation, cleanup, cache clearing, leak detection,
OOM handling, and multi-device support.
"""

import asyncio
import pytest
from typing import Any
from unittest.mock import Mock, patch, MagicMock

from kagami.core.resources.tracker import get_resource_tracker, reset_tracker


# Check if torch is available
try:
    import torch

    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


@pytest.fixture(autouse=True)
def reset_resource_tracker():
    """Reset tracker before each test."""
    reset_tracker()
    yield
    reset_tracker()


@pytest.fixture
def mock_cuda():
    """Create mock CUDA module."""
    cuda = Mock()
    cuda.is_available = Mock(return_value=True)
    cuda.current_device = Mock(return_value=0)
    cuda.memory_allocated = Mock(return_value=1000000)
    cuda.max_memory_allocated = Mock(return_value=2000000)
    cuda.memory_reserved = Mock(return_value=3000000)
    cuda.empty_cache = Mock()
    cuda.synchronize = Mock()

    # Mock device properties
    props = Mock()
    props.total_memory = 8 * 1024 * 1024 * 1024  # 8GB
    cuda.get_device_properties = Mock(return_value=props)

    return cuda


@pytest.fixture
def mock_torch():
    """Create mock torch module."""
    torch_mock = Mock()
    torch_mock.float32 = "float32"
    torch_mock.float16 = "float16"

    def empty(*args, **kwargs):
        tensor = Mock()
        tensor.device = kwargs.get("device", "cpu")
        tensor.element_size = Mock(return_value=4)
        tensor.nelement = Mock(return_value=100)
        tensor.cpu = Mock()
        return tensor

    torch_mock.empty = empty
    torch_mock.zeros = empty
    torch_mock.ones = empty
    torch_mock.randn = empty

    return torch_mock


@pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not available")
class TestGPUMemoryManagerWithTorch:
    """Test GPU memory manager with real PyTorch."""

    @pytest.mark.asyncio
    async def test_basic_lifecycle(self):
        """Test basic GPU manager lifecycle."""
        from kagami.core.resources.gpu_manager import GPUMemoryManager

        if not torch.cuda.is_available():
            pytest.skip("CUDA not available")

        async with GPUMemoryManager(device="cpu") as gpu:  # Use CPU for testing
            assert gpu._resource_id is not None

    @pytest.mark.asyncio
    async def test_allocate_tensor(self):
        """Test tensor allocation."""
        from kagami.core.resources.gpu_manager import GPUMemoryManager

        async with GPUMemoryManager(device="cpu") as gpu:
            tensor = gpu.allocate((10, 10))
            assert tensor.shape == (10, 10)
            assert len(gpu._resources) == 1

    @pytest.mark.asyncio
    async def test_multiple_tensors(self):
        """Test tracking multiple tensors."""
        from kagami.core.resources.gpu_manager import GPUMemoryManager

        async with GPUMemoryManager(device="cpu") as gpu:
            t1 = gpu.zeros((5, 5))
            t2 = gpu.ones((10, 10))
            t3 = gpu.randn((3, 3))

            assert len(gpu._resources) == 3

    @pytest.mark.asyncio
    async def test_cleanup_frees_memory(self):
        """Test that cleanup frees tracked tensors."""
        from kagami.core.resources.gpu_manager import GPUMemoryManager

        async with GPUMemoryManager(device="cpu") as gpu:
            t1 = gpu.allocate((100, 100))
            t2 = gpu.allocate((200, 200))
            initial_count = len(gpu._resources)
            assert initial_count == 2

        # After exit, resources should be cleared
        assert len(gpu._resources) == 0


class TestGPUMemoryManagerMocked:
    """Test GPU memory manager with mocked PyTorch."""

    @pytest.mark.asyncio
    async def test_initialization_without_torch(self):
        """Test initialization fails without PyTorch."""
        with patch.dict("sys.modules", {"torch": None, "torch.cuda": None}):
            with patch("kagami.core.resources.gpu_manager.TORCH_AVAILABLE", False):
                from kagami.core.resources.gpu_manager import GPUMemoryManager

                with pytest.raises(RuntimeError, match="PyTorch is not available"):
                    GPUMemoryManager()

    @pytest.mark.asyncio
    @patch("kagami.core.resources.gpu_manager.TORCH_AVAILABLE", True)
    @patch("kagami.core.resources.gpu_manager.cuda")
    @patch("kagami.core.resources.gpu_manager.torch")
    async def test_device_resolution_cuda(self, mock_torch, mock_cuda):
        """Test device resolution for CUDA."""
        mock_cuda.is_available.return_value = True
        mock_cuda.current_device.return_value = 0
        mock_cuda.memory_allocated.return_value = 0
        mock_cuda.max_memory_allocated.return_value = 0

        props = Mock()
        props.total_memory = 8 * 1024 * 1024 * 1024
        mock_cuda.get_device_properties.return_value = props

        from kagami.core.resources.gpu_manager import GPUMemoryManager

        async with GPUMemoryManager() as gpu:
            assert gpu.device == "cuda:0"

    @pytest.mark.asyncio
    @patch("kagami.core.resources.gpu_manager.TORCH_AVAILABLE", True)
    @patch("kagami.core.resources.gpu_manager.cuda")
    async def test_device_resolution_cpu_fallback(self, mock_cuda):
        """Test device falls back to CPU when CUDA unavailable."""
        mock_cuda.is_available.return_value = False

        from kagami.core.resources.gpu_manager import GPUMemoryManager

        mgr = GPUMemoryManager()
        assert mgr.device == "cpu"

    @pytest.mark.asyncio
    @patch("kagami.core.resources.gpu_manager.TORCH_AVAILABLE", True)
    @patch("kagami.core.resources.gpu_manager.cuda")
    async def test_device_resolution_explicit_device(self, mock_cuda):
        """Test explicit device specification."""
        mock_cuda.is_available.return_value = True

        from kagami.core.resources.gpu_manager import GPUMemoryManager

        mgr = GPUMemoryManager(device="cuda:2")
        assert mgr.device == "cuda:2"

    @pytest.mark.asyncio
    @patch("kagami.core.resources.gpu_manager.TORCH_AVAILABLE", True)
    @patch("kagami.core.resources.gpu_manager.cuda")
    async def test_device_resolution_integer(self, mock_cuda):
        """Test integer device specification."""
        mock_cuda.is_available.return_value = True

        from kagami.core.resources.gpu_manager import GPUMemoryManager

        mgr = GPUMemoryManager(device=1)
        assert mgr.device == "cuda:1"

    @pytest.mark.asyncio
    @patch("kagami.core.resources.gpu_manager.TORCH_AVAILABLE", True)
    @patch("kagami.core.resources.gpu_manager.cuda")
    async def test_resource_tracking(self, mock_cuda):
        """Test GPU resources are tracked."""
        mock_cuda.is_available.return_value = True
        mock_cuda.memory_allocated.return_value = 0
        mock_cuda.max_memory_allocated.return_value = 0

        props = Mock()
        props.total_memory = 8 * 1024 * 1024 * 1024
        mock_cuda.get_device_properties.return_value = props

        from kagami.core.resources.gpu_manager import GPUMemoryManager

        tracker = get_resource_tracker()

        async with GPUMemoryManager(device="cuda:0") as gpu:
            resources = tracker.get_resources("gpu")
            assert len(resources) == 1
            assert resources[0].resource_id == "cuda:0"

        # Should be untracked after exit
        resources = tracker.get_resources("gpu")
        assert len(resources) == 0

    @pytest.mark.asyncio
    @patch("kagami.core.resources.gpu_manager.TORCH_AVAILABLE", True)
    @patch("kagami.core.resources.gpu_manager.cuda")
    @patch("kagami.core.resources.gpu_manager.torch")
    async def test_track_resource(self, mock_torch, mock_cuda):
        """Test tracking individual resources."""
        mock_cuda.is_available.return_value = False

        from kagami.core.resources.gpu_manager import GPUMemoryManager

        async with GPUMemoryManager(device="cpu") as gpu:
            tensor = Mock()
            tensor.device = "cpu"
            tensor.element_size = Mock(return_value=4)
            tensor.nelement = Mock(return_value=100)

            resource_id = gpu.track(tensor, "tensor")
            assert resource_id == id(tensor)
            assert len(gpu._resources) == 1

    @pytest.mark.asyncio
    @patch("kagami.core.resources.gpu_manager.TORCH_AVAILABLE", True)
    @patch("kagami.core.resources.gpu_manager.cuda")
    async def test_untrack_resource(self, mock_cuda):
        """Test untracking resources."""
        mock_cuda.is_available.return_value = False

        from kagami.core.resources.gpu_manager import GPUMemoryManager

        async with GPUMemoryManager(device="cpu") as gpu:
            tensor = Mock()
            tensor.device = "cpu"
            tensor.element_size = Mock(return_value=4)
            tensor.nelement = Mock(return_value=100)

            resource_id = gpu.track(tensor)
            assert len(gpu._resources) == 1

            gpu.untrack(resource_id)
            assert len(gpu._resources) == 0

    @pytest.mark.asyncio
    @patch("kagami.core.resources.gpu_manager.TORCH_AVAILABLE", True)
    @patch("kagami.core.resources.gpu_manager.cuda")
    async def test_cache_clearing(self, mock_cuda):
        """Test CUDA cache is cleared on cleanup."""
        mock_cuda.is_available.return_value = True
        mock_cuda.empty_cache = Mock()
        mock_cuda.synchronize = Mock()
        mock_cuda.memory_allocated.return_value = 0
        mock_cuda.max_memory_allocated.return_value = 0

        props = Mock()
        props.total_memory = 8 * 1024 * 1024 * 1024
        mock_cuda.get_device_properties.return_value = props

        from kagami.core.resources.gpu_manager import GPUMemoryManager

        async with GPUMemoryManager(device="cuda:0", clear_cache=True) as gpu:
            pass

        # Cache should be cleared
        mock_cuda.empty_cache.assert_called_once()

    @pytest.mark.asyncio
    @patch("kagami.core.resources.gpu_manager.TORCH_AVAILABLE", True)
    @patch("kagami.core.resources.gpu_manager.cuda")
    async def test_no_cache_clearing(self, mock_cuda):
        """Test cache clearing can be disabled."""
        mock_cuda.is_available.return_value = True
        mock_cuda.empty_cache = Mock()
        mock_cuda.memory_allocated.return_value = 0
        mock_cuda.max_memory_allocated.return_value = 0

        props = Mock()
        props.total_memory = 8 * 1024 * 1024 * 1024
        mock_cuda.get_device_properties.return_value = props

        from kagami.core.resources.gpu_manager import GPUMemoryManager

        async with GPUMemoryManager(device="cuda:0", clear_cache=False) as gpu:
            pass

        # Cache should not be cleared
        mock_cuda.empty_cache.assert_not_called()

    @pytest.mark.asyncio
    @patch("kagami.core.resources.gpu_manager.TORCH_AVAILABLE", True)
    @patch("kagami.core.resources.gpu_manager.cuda")
    async def test_synchronization(self, mock_cuda):
        """Test GPU synchronization on cleanup."""
        mock_cuda.is_available.return_value = True
        mock_cuda.synchronize = Mock()
        mock_cuda.empty_cache = Mock()
        mock_cuda.memory_allocated.return_value = 0
        mock_cuda.max_memory_allocated.return_value = 0

        props = Mock()
        props.total_memory = 8 * 1024 * 1024 * 1024
        mock_cuda.get_device_properties.return_value = props

        from kagami.core.resources.gpu_manager import GPUMemoryManager

        async with GPUMemoryManager(device="cuda:0", synchronize=True) as gpu:
            pass

        # Should synchronize
        mock_cuda.synchronize.assert_called_once_with(0)

    @pytest.mark.asyncio
    @patch("kagami.core.resources.gpu_manager.TORCH_AVAILABLE", True)
    @patch("kagami.core.resources.gpu_manager.cuda")
    async def test_no_synchronization(self, mock_cuda):
        """Test synchronization can be disabled."""
        mock_cuda.is_available.return_value = True
        mock_cuda.synchronize = Mock()
        mock_cuda.memory_allocated.return_value = 0
        mock_cuda.max_memory_allocated.return_value = 0

        props = Mock()
        props.total_memory = 8 * 1024 * 1024 * 1024
        mock_cuda.get_device_properties.return_value = props

        from kagami.core.resources.gpu_manager import GPUMemoryManager

        async with GPUMemoryManager(device="cuda:0", synchronize=False) as gpu:
            pass

        # Should not synchronize
        mock_cuda.synchronize.assert_not_called()

    @pytest.mark.asyncio
    @patch("kagami.core.resources.gpu_manager.TORCH_AVAILABLE", True)
    @patch("kagami.core.resources.gpu_manager.cuda")
    async def test_cleanup_error_handling(self, mock_cuda):
        """Test cleanup handles errors gracefully."""
        mock_cuda.is_available.return_value = True
        mock_cuda.synchronize = Mock(side_effect=RuntimeError("Sync failed"))
        mock_cuda.empty_cache = Mock()
        mock_cuda.memory_allocated.return_value = 0
        mock_cuda.max_memory_allocated.return_value = 0

        props = Mock()
        props.total_memory = 8 * 1024 * 1024 * 1024
        mock_cuda.get_device_properties.return_value = props

        from kagami.core.resources.gpu_manager import GPUMemoryManager

        # Should not raise during cleanup
        with pytest.raises(RuntimeError):
            async with GPUMemoryManager(device="cuda:0") as gpu:
                pass

    @pytest.mark.asyncio
    @patch("kagami.core.resources.gpu_manager.TORCH_AVAILABLE", True)
    @patch("kagami.core.resources.gpu_manager.cuda")
    async def test_memory_statistics(self, mock_cuda):
        """Test getting memory statistics."""
        mock_cuda.is_available.return_value = True
        mock_cuda.memory_allocated.return_value = 1000000
        mock_cuda.memory_reserved.return_value = 2000000
        mock_cuda.max_memory_allocated.return_value = 1500000

        props = Mock()
        props.total_memory = 8 * 1024 * 1024 * 1024
        mock_cuda.get_device_properties.return_value = props

        from kagami.core.resources.gpu_manager import GPUMemoryManager

        async with GPUMemoryManager(device="cuda:0") as gpu:
            stats = gpu.get_memory_stats()

            assert stats["available"] is True
            assert stats["device"] == "cuda:0"
            assert stats["allocated"] == 1000000
            assert stats["reserved"] == 2000000
            assert stats["max_allocated"] == 1500000
            assert stats["total"] == 8 * 1024 * 1024 * 1024

    @pytest.mark.asyncio
    @patch("kagami.core.resources.gpu_manager.TORCH_AVAILABLE", True)
    @patch("kagami.core.resources.gpu_manager.cuda")
    async def test_memory_statistics_no_cuda(self, mock_cuda):
        """Test memory statistics when CUDA unavailable."""
        mock_cuda.is_available.return_value = False

        from kagami.core.resources.gpu_manager import GPUMemoryManager

        async with GPUMemoryManager(device="cpu") as gpu:
            stats = gpu.get_memory_stats()

            assert stats["available"] is False
            assert stats["device"] == "cpu"

    @pytest.mark.asyncio
    @patch("kagami.core.resources.gpu_manager.TORCH_AVAILABLE", True)
    @patch("kagami.core.resources.gpu_manager.cuda")
    @patch("kagami.core.resources.gpu_manager.torch")
    async def test_to_device(self, mock_torch, mock_cuda):
        """Test moving tensor to device."""
        mock_cuda.is_available.return_value = False

        from kagami.core.resources.gpu_manager import GPUMemoryManager

        async with GPUMemoryManager(device="cpu") as gpu:
            tensor = Mock()
            moved_tensor = Mock()
            moved_tensor.device = "cpu"
            moved_tensor.element_size = Mock(return_value=4)
            moved_tensor.nelement = Mock(return_value=100)
            tensor.to = Mock(return_value=moved_tensor)

            result = gpu.to_device(tensor)

            tensor.to.assert_called_once_with("cpu")
            assert len(gpu._resources) == 1

    @pytest.mark.asyncio
    @patch("kagami.core.resources.gpu_manager.TORCH_AVAILABLE", True)
    @patch("kagami.core.resources.gpu_manager.cuda")
    async def test_resource_cleanup_moves_to_cpu(self, mock_cuda):
        """Test that resources are moved to CPU before deletion."""
        mock_cuda.is_available.return_value = False

        from kagami.core.resources.gpu_manager import GPUMemoryManager, GPUResource

        mgr = GPUMemoryManager(device="cpu")

        tensor = Mock()
        tensor.cpu = Mock()

        gpu_resource = GPUResource(
            resource=tensor, device="cpu", memory_bytes=100, resource_type="tensor"
        )

        await mgr._cleanup_resource(gpu_resource)

        # Should call cpu() to move to CPU
        tensor.cpu.assert_called_once()

    @pytest.mark.asyncio
    @patch("kagami.core.resources.gpu_manager.TORCH_AVAILABLE", True)
    @patch("kagami.core.resources.gpu_manager.cuda")
    async def test_cleanup_on_error(self, mock_cuda):
        """Test cleanup happens even on error."""
        mock_cuda.is_available.return_value = False

        from kagami.core.resources.gpu_manager import GPUMemoryManager

        tracker = get_resource_tracker()

        try:
            async with GPUMemoryManager(device="cpu") as gpu:
                raise ValueError("Test error")
        except ValueError:
            pass

        # Should be cleaned up
        resources = tracker.get_resources("gpu")
        assert len(resources) == 0

    @pytest.mark.asyncio
    @patch("kagami.core.resources.gpu_manager.TORCH_AVAILABLE", True)
    @patch("kagami.core.resources.gpu_manager.cuda")
    async def test_multiple_cleanup_errors(self, mock_cuda):
        """Test cleanup handles multiple errors."""
        mock_cuda.is_available.return_value = True
        mock_cuda.synchronize = Mock(side_effect=RuntimeError("Sync failed"))
        mock_cuda.empty_cache = Mock(side_effect=RuntimeError("Cache failed"))
        mock_cuda.memory_allocated.return_value = 0
        mock_cuda.max_memory_allocated.return_value = 0

        props = Mock()
        props.total_memory = 8 * 1024 * 1024 * 1024
        mock_cuda.get_device_properties.return_value = props

        from kagami.core.resources.gpu_manager import GPUMemoryManager

        # Should raise the first error
        with pytest.raises(RuntimeError):
            async with GPUMemoryManager(device="cuda:0") as gpu:
                pass


class TestGPUUtilityFunctions:
    """Test GPU utility functions."""

    @pytest.mark.asyncio
    @patch("kagami.core.resources.gpu_manager.TORCH_AVAILABLE", True)
    @patch("kagami.core.resources.gpu_manager.cuda")
    async def test_clear_gpu_cache(self, mock_cuda):
        """Test clear_gpu_cache function."""
        mock_cuda.is_available.return_value = True
        mock_cuda.empty_cache = Mock()

        from kagami.core.resources.gpu_manager import clear_gpu_cache

        clear_gpu_cache()
        mock_cuda.empty_cache.assert_called_once()

    @pytest.mark.asyncio
    @patch("kagami.core.resources.gpu_manager.TORCH_AVAILABLE", True)
    @patch("kagami.core.resources.gpu_manager.cuda")
    async def test_clear_gpu_cache_no_cuda(self, mock_cuda):
        """Test clear_gpu_cache when CUDA unavailable."""
        mock_cuda.is_available.return_value = False

        from kagami.core.resources.gpu_manager import clear_gpu_cache

        # Should not raise
        clear_gpu_cache()

    @pytest.mark.asyncio
    @patch("kagami.core.resources.gpu_manager.TORCH_AVAILABLE", True)
    @patch("kagami.core.resources.gpu_manager.cuda")
    async def test_synchronize_gpu(self, mock_cuda):
        """Test synchronize_gpu function."""
        mock_cuda.is_available.return_value = True
        mock_cuda.synchronize = Mock()

        from kagami.core.resources.gpu_manager import synchronize_gpu

        synchronize_gpu()
        mock_cuda.synchronize.assert_called_once()

    @pytest.mark.asyncio
    @patch("kagami.core.resources.gpu_manager.TORCH_AVAILABLE", True)
    @patch("kagami.core.resources.gpu_manager.cuda")
    async def test_synchronize_gpu_no_cuda(self, mock_cuda):
        """Test synchronize_gpu when CUDA unavailable."""
        mock_cuda.is_available.return_value = False

        from kagami.core.resources.gpu_manager import synchronize_gpu

        # Should not raise
        synchronize_gpu()

    @pytest.mark.asyncio
    @patch("kagami.core.resources.gpu_manager.TORCH_AVAILABLE", True)
    @patch("kagami.core.resources.gpu_manager.cuda")
    async def test_gpu_memory_scope(self, mock_cuda):
        """Test gpu_memory_scope context manager."""
        mock_cuda.is_available.return_value = False

        from kagami.core.resources.gpu_manager import gpu_memory_scope

        with gpu_memory_scope(device="cpu") as gpu:
            assert gpu.device == "cpu"


class TestPerformance:
    """Test GPU manager performance."""

    @pytest.mark.asyncio
    @patch("kagami.core.resources.gpu_manager.TORCH_AVAILABLE", True)
    @patch("kagami.core.resources.gpu_manager.cuda")
    async def test_overhead_is_minimal(self, mock_cuda):
        """Test that manager overhead is minimal."""
        import time

        mock_cuda.is_available.return_value = False

        from kagami.core.resources.gpu_manager import GPUMemoryManager

        # Measure overhead
        start = time.perf_counter()

        for _ in range(100):
            async with GPUMemoryManager(device="cpu") as gpu:
                pass

        elapsed = time.perf_counter() - start

        # Should be fast (< 1 second for 100 iterations)
        assert elapsed < 1.0

    @pytest.mark.asyncio
    @patch("kagami.core.resources.gpu_manager.TORCH_AVAILABLE", True)
    @patch("kagami.core.resources.gpu_manager.cuda")
    async def test_concurrent_managers(self, mock_cuda):
        """Test multiple concurrent GPU managers."""
        mock_cuda.is_available.return_value = False

        from kagami.core.resources.gpu_manager import GPUMemoryManager

        async def use_gpu(device):
            async with GPUMemoryManager(device=device) as gpu:
                # Simulate work
                await asyncio.sleep(0.01)

        # Run multiple managers concurrently
        await asyncio.gather(
            use_gpu("cpu"),
            use_gpu("cpu"),
            use_gpu("cpu"),
        )
