"""Unit tests for DeferredModelLoader."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.tier_unit


class TestDeferredModelLoader:
    """Test DeferredModelLoader."""

    @pytest.mark.asyncio
    async def test_register_model(self) -> None:
        """Test model registration."""
        from kagami.boot.deferred_loader import DeferredModelLoader

        loader = DeferredModelLoader()
        await loader.register_model("test_model")

        assert "test_model" in loader._slots
        assert "test_model" in loader._queues
        await loader.shutdown()

    @pytest.mark.asyncio
    async def test_load_model_success(self) -> None:
        """Test successful model loading."""
        from kagami.boot.deferred_loader import DeferredModelLoader

        loader = DeferredModelLoader()

        async def mock_loader():
            return MagicMock()

        result = await loader.load_model("test", mock_loader)

        assert result is True
        assert loader.is_ready("test")
        assert loader.get_model("test") is not None
        await loader.shutdown()

    @pytest.mark.asyncio
    async def test_load_model_failure(self) -> None:
        """Test failed model loading."""
        from kagami.boot.deferred_loader import DeferredModelLoader

        loader = DeferredModelLoader()

        async def failing_loader():
            raise RuntimeError("Load failed")

        result = await loader.load_model("test", failing_loader)

        assert result is False
        assert not loader.is_ready("test")
        assert loader._slots["test"].error == "Load failed"
        await loader.shutdown()

    @pytest.mark.asyncio
    async def test_call_when_ready_immediate(self) -> None:
        """Test immediate call when model ready."""
        from kagami.boot.deferred_loader import DeferredModelLoader

        loader = DeferredModelLoader()
        model = MagicMock()

        async def mock_loader():
            return model

        await loader.load_model("test", mock_loader)

        async def handler(m, x):
            return m.process(x)

        model.process.return_value = "result"
        result = await loader.call_when_ready("test", handler, 42)

        assert result == "result"
        model.process.assert_called_once_with(42)
        await loader.shutdown()

    @pytest.mark.asyncio
    async def test_call_when_ready_queued(self) -> None:
        """Test queued call when model loading."""
        from kagami.boot.deferred_loader import DeferredModelLoader

        loader = DeferredModelLoader()
        model = MagicMock()
        model.process.return_value = "result"

        async def slow_loader():
            await asyncio.sleep(0.2)
            return model

        async def handler(m, x):
            return m.process(x)

        # Start loading in background
        load_task = asyncio.create_task(loader.load_model("test", slow_loader))

        # Call should queue and wait
        result = await loader.call_when_ready("test", handler, 42, timeout=5.0)

        await load_task
        assert result == "result"
        await loader.shutdown()

    @pytest.mark.asyncio
    async def test_hot_swap(self) -> None:
        """Test hot-swap model replacement."""
        from kagami.boot.deferred_loader import DeferredModelLoader

        loader = DeferredModelLoader()

        old_model = MagicMock(name="old")
        new_model = MagicMock(name="new")

        async def old_loader():
            return old_model

        async def new_loader():
            return new_model

        await loader.load_model("test", old_loader)
        assert loader.get_model("test") is old_model

        result = await loader.hot_swap("test", new_loader)

        assert result is True
        assert loader.get_model("test") is new_model
        await loader.shutdown()

    @pytest.mark.asyncio
    async def test_get_status(self) -> None:
        """Test status reporting."""
        from kagami.boot.deferred_loader import DeferredModelLoader

        loader = DeferredModelLoader()

        async def mock_loader():
            return MagicMock()

        await loader.load_model("test", mock_loader)

        status = loader.get_status()

        assert "models" in status
        assert "queues" in status
        assert status["models"]["test"]["ready"] is True
        await loader.shutdown()

    @pytest.mark.asyncio
    async def test_singleton(self) -> None:
        """Test singleton pattern."""
        from kagami.boot.deferred_loader import (
            get_deferred_loader,
            reset_deferred_loader,
        )

        reset_deferred_loader()
        loader1 = get_deferred_loader()
        loader2 = get_deferred_loader()

        assert loader1 is loader2
        reset_deferred_loader()

    @pytest.mark.asyncio
    async def test_timeout_in_queue(self) -> None:
        """Test request timeout while queued."""
        from kagami.boot.deferred_loader import DeferredModelLoader

        loader = DeferredModelLoader()
        await loader.register_model("test")

        async def handler(m, x):
            return x

        with pytest.raises(asyncio.TimeoutError):
            await loader.call_when_ready("test", handler, 42, timeout=0.1)

        await loader.shutdown()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
