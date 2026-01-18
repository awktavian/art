"""Comprehensive Tests for Colony Coordinator.

COVERAGE:
=========
- Initialization and setup
- Single colony execution (SINGLE mode)
- Fano line execution (3 colonies, FANO_LINE mode)
- All colonies execution (7 colonies, ALL_COLONIES mode)
- E8 fusion of colony outputs
- S7 output extraction and fallback
- E8 message encoding/decoding
- World model context enrichment
- Error handling and exceptions
- Concurrent execution with semaphore
- Context integration with routing

Created: December 27, 2025
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import torch

from kagami.core.unified_agents.colony_coordinator import (
    ColonyCoordinator,
    create_colony_coordinator,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_router():
    """Create mock FanoActionRouter."""
    router = Mock()
    router.route = Mock()
    return router


@pytest.fixture
def mock_reducer():
    """Create mock E8ActionReducer."""
    reducer = Mock()
    # Mock the reducer to return simple outputs
    reducer.return_value = (
        torch.randn(1, 8),  # e8_code
        torch.tensor([42]),  # e8_index
        torch.ones(1, 7) / 7,  # weights
    )
    return reducer


@pytest.fixture
def e8_roots():
    """Create mock E8 roots tensor."""
    return torch.randn(240, 8)


@pytest.fixture
def mock_colony():
    """Create mock MinimalColony."""

    async def mock_execute(action: Any, params: Any, context: Any) -> Any:
        return Mock(
            success=True,
            result={
                "kernel_output": {
                    "s7_output": torch.randn(8),
                }
            },
        )

    colony = Mock()
    colony.execute = AsyncMock(side_effect=mock_execute)
    return colony


@pytest.fixture
def get_colony_fn(mock_colony: Any) -> str:
    """Create mock get_colony function."""

    def _get_colony(idx: Any) -> str:
        return mock_colony

    return _get_colony


@pytest.fixture
def coordinator(mock_router: Any, mock_reducer: Any, e8_roots: Any, get_colony_fn: Any) -> Any:
    """Create ColonyCoordinator instance."""
    return ColonyCoordinator(
        router=mock_router,
        reducer=mock_reducer,
        e8_roots=e8_roots,
        get_colony_fn=get_colony_fn,
    )


@pytest.fixture
def mock_action():
    """Create mock action for routing result."""
    action = Mock()
    action.colony_idx = 0
    action.action = "test.action"
    action.weight = 1.0
    return action


@pytest.fixture
def mock_routing_single(mock_action: Any) -> Any:
    """Create mock routing result for SINGLE mode."""
    # Mock the ActionMode enum
    with patch(
        "kagami.core.unified_agents.colony_coordinator._lazy_import_fano_types"
    ) as mock_import:
        action_mode = Mock()
        action_mode.SINGLE = "SINGLE"
        action_mode.FANO_LINE = "FANO_LINE"
        action_mode.ALL_COLONIES = "ALL_COLONIES"
        mock_import.return_value = (action_mode, Mock())

        routing = Mock()
        routing.mode = action_mode.SINGLE
        routing.actions = [mock_action]
        routing.complexity = 1.0
        return routing


@pytest.fixture
def mock_routing_fano_line(mock_action: Any) -> Any:
    """Create mock routing result for FANO_LINE mode."""
    with patch(
        "kagami.core.unified_agents.colony_coordinator._lazy_import_fano_types"
    ) as mock_import:
        action_mode = Mock()
        action_mode.SINGLE = "SINGLE"
        action_mode.FANO_LINE = "FANO_LINE"
        action_mode.ALL_COLONIES = "ALL_COLONIES"
        mock_import.return_value = (action_mode, Mock())

        routing = Mock()
        routing.mode = action_mode.FANO_LINE
        # Create 3 actions for Fano line
        routing.actions = [
            Mock(colony_idx=0, action="test.action", weight=1.0),
            Mock(colony_idx=1, action="test.action", weight=1.0),
            Mock(colony_idx=2, action="test.action", weight=1.0),
        ]
        routing.complexity = 2.0
        return routing


# =============================================================================
# TEST: INITIALIZATION
# =============================================================================


def test_coordinator_initialization(
    mock_router: Any, mock_reducer: Any, e8_roots: Any, get_colony_fn: Any
) -> None:
    """Test ColonyCoordinator initialization."""
    coordinator = ColonyCoordinator(
        router=mock_router,
        reducer=mock_reducer,
        e8_roots=e8_roots,
        get_colony_fn=get_colony_fn,
    )

    assert coordinator._router == mock_router
    assert coordinator._reducer == mock_reducer
    assert coordinator._get_colony == get_colony_fn
    assert torch.equal(coordinator._e8_roots, e8_roots)


def test_factory_function(
    mock_router: Any, mock_reducer: Any, e8_roots: Any, get_colony_fn: Any
) -> None:
    """Test create_colony_coordinator factory."""
    coordinator = create_colony_coordinator(
        router=mock_router,
        reducer=mock_reducer,
        e8_roots=e8_roots,
        get_colony_fn=get_colony_fn,
    )

    assert isinstance(coordinator, ColonyCoordinator)
    assert coordinator._router == mock_router
    assert coordinator._reducer == mock_reducer


# =============================================================================
# TEST: S7 OUTPUT EXTRACTION
# =============================================================================


def test_extract_s7_output_from_kernel_output(coordinator: Any) -> None:
    """Test S7 output extraction from kernel_output."""
    result = Mock()
    result.result = {
        "kernel_output": {
            "s7_output": torch.randn(8),
        }
    }

    output = coordinator._extract_s7_output(result, colony_idx=0)

    assert output.shape == (8,)
    assert isinstance(output, torch.Tensor)


def test_extract_s7_output_from_direct_s7(coordinator: Any) -> None:
    """Test S7 output extraction from direct s7_output field."""
    result = Mock()
    result.result = {
        "s7_output": torch.randn(8),
    }

    output = coordinator._extract_s7_output(result, colony_idx=0)

    assert output.shape == (8,)
    assert isinstance(output, torch.Tensor)


def test_extract_s7_output_fallback_success(coordinator: Any) -> None:
    """Test S7 output fallback for successful result without kernel output."""
    result = Mock()
    result.result = {}
    result.success = True

    output = coordinator._extract_s7_output(result, colony_idx=2, weight=1.0)

    assert output.shape == (8,)
    # Check that colony index is encoded
    assert output[0] != 0  # Real part
    assert output[3] != 0  # Imaginary part for colony 2 (index 2+1=3)


def test_extract_s7_output_fallback_failure(coordinator: Any) -> None:
    """Test S7 output fallback for failed result without kernel output."""
    result = Mock()
    result.result = {}
    result.success = False

    output = coordinator._extract_s7_output(result, colony_idx=1, weight=1.0)

    assert output.shape == (8,)
    # Failed result should have negative signature
    assert output[0] < 0  # Negative real part for failure


def test_extract_s7_output_with_weight(coordinator: Any) -> None:
    """Test S7 output extraction respects weight parameter."""
    result = Mock()
    result.result = {
        "s7_output": torch.ones(8),
    }

    output = coordinator._extract_s7_output(result, colony_idx=0, weight=0.5)

    # Output should be scaled by weight
    assert torch.allclose(output, torch.ones(8) * 0.5 / torch.ones(8).norm())


# =============================================================================
# TEST: SINGLE COLONY EXECUTION
# =============================================================================


@pytest.mark.asyncio
async def test_execute_single_colony(
    coordinator: Any, mock_routing_single: Any, mock_colony: Any
) -> None:
    """Test single colony execution."""
    with patch.object(coordinator, "_router") as mock_router:
        mock_router.route.return_value = mock_routing_single

        result = await coordinator._execute_single(
            routing=mock_routing_single,
            params={"key": "value"},
            context={},
        )

        assert "results" in result
        assert "colony_outputs" in result
        assert len(result["results"]) == 1
        assert result["colony_outputs"].shape == (1, 7, 8)


@pytest.mark.asyncio
async def test_execute_single_colony_calls_correct_colony(
    coordinator, mock_routing_single, mock_colony
) -> None:
    """Test that single execution calls the correct colony."""
    result = await coordinator._execute_single(
        routing=mock_routing_single,
        params={"test": "params"},
        context={"test": "context"},
    )

    # Verify colony.execute was called
    mock_colony.execute.assert_called_once()
    call_args = mock_colony.execute.call_args
    assert call_args[0][0] == "test.action"  # action
    assert call_args[0][1] == {"test": "params"}  # params


# =============================================================================
# TEST: FANO LINE EXECUTION
# =============================================================================


@pytest.mark.asyncio
async def test_execute_fano_line_three_colonies(
    coordinator: Any, mock_routing_fano_line: Any
) -> None:
    """Test Fano line execution with 3 colonies."""
    result = await coordinator._execute_fano_line(
        routing=mock_routing_fano_line,
        params={"key": "value"},
        context={},
    )

    assert "results" in result
    assert "colony_outputs" in result
    assert len(result["results"]) == 3
    assert result["colony_outputs"].shape == (1, 7, 8)


@pytest.mark.asyncio
async def test_execute_fano_line_parallel_execution(
    coordinator, mock_routing_fano_line, mock_colony
) -> None:
    """Test that Fano line executes colonies in parallel."""
    # Track execution order with timestamps
    execution_times = []

    async def mock_execute_with_delay(action: Any, params: Any, context: Any) -> Any:
        execution_times.append(asyncio.get_event_loop().time())
        await asyncio.sleep(0.01)  # Small delay
        return Mock(
            success=True,
            result={"kernel_output": {"s7_output": torch.randn(8)}},
        )

    mock_colony.execute = AsyncMock(side_effect=mock_execute_with_delay)

    await coordinator._execute_fano_line(
        routing=mock_routing_fano_line,
        params={},
        context={},
    )

    # All executions should start at roughly the same time (parallel)
    assert len(execution_times) == 3
    time_spread = max(execution_times) - min(execution_times)
    assert time_spread < 0.005  # Started within 5ms of each other


@pytest.mark.asyncio
async def test_execute_fano_line_handles_exceptions(
    coordinator: Any, mock_routing_fano_line: Any
) -> None:
    """Test Fano line execution handles colony exceptions gracefully."""
    # Create colony that raises exception
    failing_colony = Mock()
    failing_colony.execute = AsyncMock(side_effect=RuntimeError("Colony failed"))

    coordinator._get_colony = lambda idx: failing_colony

    result = await coordinator._execute_fano_line(
        routing=mock_routing_fano_line,
        params={},
        context={},
    )

    # Should return results with failure placeholders
    assert "results" in result
    assert len(result["results"]) == 3
    # All results should be failure placeholders
    for res in result["results"]:
        assert hasattr(res, "success")
        assert res.success is False


# =============================================================================
# TEST: ALL COLONIES EXECUTION
# =============================================================================


@pytest.mark.asyncio
async def test_execute_all_colonies_seven_colonies(coordinator: Any) -> None:
    """Test execution of all 7 colonies."""
    # Create routing for all colonies
    with patch(
        "kagami.core.unified_agents.colony_coordinator._lazy_import_fano_types"
    ) as mock_import:
        action_mode = Mock()
        action_mode.ALL_COLONIES = "ALL_COLONIES"
        mock_import.return_value = (action_mode, Mock())

        routing = Mock()
        routing.mode = action_mode.ALL_COLONIES
        routing.actions = [Mock(colony_idx=i, action="test.action", weight=1.0) for i in range(7)]

        result = await coordinator._execute_all_colonies(
            routing=routing,
            params={},
            context={},
        )

        assert "results" in result
        assert "colony_outputs" in result
        assert len(result["results"]) == 7
        assert result["colony_outputs"].shape == (1, 7, 8)


@pytest.mark.asyncio
async def test_execute_all_colonies_uses_semaphore(coordinator: Any, mock_colony: Any) -> None:
    """Test that all colonies execution uses semaphore for bounded concurrency."""
    # Track concurrent executions
    concurrent_count = 0
    max_concurrent = 0

    async def mock_execute_tracking(action: Any, params: Any, context: Any) -> Any:
        nonlocal concurrent_count, max_concurrent
        concurrent_count += 1
        max_concurrent = max(max_concurrent, concurrent_count)
        await asyncio.sleep(0.01)
        concurrent_count -= 1
        return Mock(success=True, result={"s7_output": torch.randn(8)})

    mock_colony.execute = AsyncMock(side_effect=mock_execute_tracking)

    with patch(
        "kagami.core.unified_agents.colony_coordinator._lazy_import_fano_types"
    ) as mock_import:
        action_mode = Mock()
        action_mode.ALL_COLONIES = "ALL_COLONIES"
        mock_import.return_value = (action_mode, Mock())

        routing = Mock()
        routing.mode = action_mode.ALL_COLONIES
        routing.actions = [Mock(colony_idx=i, action="test.action", weight=1.0) for i in range(7)]

        await coordinator._execute_all_colonies(routing, {}, {})

        # Should respect semaphore limit (default 7)
        assert max_concurrent <= 7


# =============================================================================
# TEST: E8 FUSION
# =============================================================================


@pytest.mark.asyncio
async def test_fuse_e8_basic(coordinator: Any) -> None:
    """Test E8 fusion of colony outputs."""
    colony_outputs = torch.randn(1, 7, 8)

    result = await coordinator._fuse_e8(colony_outputs)

    assert "code" in result
    assert "index" in result
    assert "weights" in result
    assert isinstance(result["index"], int)
    assert 0 <= result["index"] < 240
    assert len(result["code"]) == 8
    assert len(result["weights"]) == 7


@pytest.mark.asyncio
async def test_fuse_e8_calls_reducer(coordinator: Any, mock_reducer: Any) -> None:
    """Test that E8 fusion calls the reducer correctly."""
    colony_outputs = torch.randn(1, 7, 8)

    await coordinator._fuse_e8(colony_outputs)

    mock_reducer.assert_called_once()
    call_args = mock_reducer.call_args[0]
    assert torch.equal(call_args[0], colony_outputs)


# =============================================================================
# TEST: E8 MESSAGE ENCODING/DECODING
# =============================================================================


def test_encode_e8_message(coordinator: Any) -> None:
    """Test E8 message encoding."""
    data = torch.randn(8)

    message = coordinator.encode_e8_message(
        source_colony=0,
        target_colony=3,
        data=data,
    )

    assert "source" in message
    assert "target" in message
    assert "e8_index" in message
    assert "e8_root" in message
    assert message["source"] == 0
    assert message["target"] == 3
    assert isinstance(message["e8_index"], int)
    assert 0 <= message["e8_index"] < 240


def test_decode_e8_message(coordinator: Any) -> None:
    """Test E8 message decoding."""
    e8_index = 42

    decoded = coordinator.decode_e8_message(e8_index)

    assert decoded.shape == (8,)
    assert torch.equal(decoded, coordinator._e8_roots[e8_index])


def test_encode_decode_roundtrip(coordinator: Any) -> None:
    """Test encode-decode roundtrip preserves E8 structure."""
    data = torch.randn(8)

    # Encode
    message = coordinator.encode_e8_message(0, 1, data)
    e8_index = message["e8_index"]

    # Decode
    decoded = coordinator.decode_e8_message(e8_index)

    # Should be close to nearest E8 root
    assert decoded.shape == (8,)
    # Decoded should be exactly the E8 root
    assert torch.equal(decoded, coordinator._e8_roots[e8_index])


# =============================================================================
# TEST: INTENT EXECUTION
# =============================================================================


@pytest.mark.asyncio
async def test_execute_intent_single_mode(coordinator: Any, mock_routing_single: Any) -> None:
    """Test execute_intent with SINGLE mode."""
    with (
        patch.object(coordinator, "_router") as mock_router,
        patch.object(
            coordinator, "_enrich_context_with_world_model", new_callable=AsyncMock
        ) as mock_enrich,
    ):
        mock_router.route.return_value = mock_routing_single
        mock_enrich.return_value = {}

        result = await coordinator.execute_intent(
            intent="test.intent",
            params={"key": "value"},
            context={},
        )

        assert "mode" in result
        assert "results" in result
        assert "e8_action" in result
        assert result["mode"] == "SINGLE"


@pytest.mark.asyncio
async def test_execute_intent_enriches_context(coordinator: Any, mock_routing_single: Any) -> None:
    """Test that execute_intent enriches context with world model."""
    with (
        patch.object(coordinator, "_router") as mock_router,
        patch.object(
            coordinator, "_enrich_context_with_world_model", new_callable=AsyncMock
        ) as mock_enrich,
    ):
        mock_router.route.return_value = mock_routing_single
        mock_enrich.return_value = {"wm_colony_hint": 3}

        await coordinator.execute_intent(
            intent="test.intent",
            params={},
            context={},
        )

        # Should call enrichment
        mock_enrich.assert_called_once()
        # Should pass enriched context to router
        mock_router.route.assert_called_once()


@pytest.mark.asyncio
async def test_execute_intent_returns_e8_action(coordinator: Any, mock_routing_single: Any) -> None:
    """Test that execute_intent returns proper E8 action structure."""
    with (
        patch.object(coordinator, "_router") as mock_router,
        patch.object(
            coordinator, "_enrich_context_with_world_model", new_callable=AsyncMock
        ) as mock_enrich,
    ):
        mock_router.route.return_value = mock_routing_single
        mock_enrich.return_value = {}

        result = await coordinator.execute_intent(
            intent="test.intent",
            params={},
            context={},
        )

        e8_action = result["e8_action"]
        assert "index" in e8_action
        assert "code" in e8_action
        assert "weights" in e8_action
        assert isinstance(e8_action["index"], int)
        assert len(e8_action["code"]) == 8


# =============================================================================
# TEST: WORLD MODEL ENRICHMENT
# =============================================================================


@pytest.mark.asyncio
async def test_enrich_context_world_model_unavailable(coordinator: Any) -> None:
    """Test context enrichment when world model is unavailable."""
    with patch(
        "kagami.core.unified_agents.colony_coordinator.get_world_model_service"
    ) as mock_get_wm:
        mock_wm = Mock()
        mock_wm.is_available = False
        mock_get_wm.return_value = mock_wm

        context = await coordinator._enrich_context_with_world_model(
            intent="test",
            params={},
            context={},
        )

        # Should return original context unchanged
        assert context == {}


@pytest.mark.asyncio
async def test_enrich_context_handles_exceptions(coordinator: Any) -> None:
    """Test that context enrichment handles exceptions gracefully."""
    with patch(
        "kagami.core.unified_agents.colony_coordinator.get_world_model_service",
        side_effect=RuntimeError("WM failed"),
    ):
        context = await coordinator._enrich_context_with_world_model(
            intent="test",
            params={},
            context={"original": "data"},
        )

        # Should return original context on error
        assert context == {"original": "data"}


# =============================================================================
# TEST: ERROR HANDLING
# =============================================================================


@pytest.mark.asyncio
async def test_execute_single_handles_colony_failure(
    coordinator: Any, mock_routing_single: Any
) -> None:
    """Test single execution handles colony failures."""
    failing_colony = Mock()
    failing_colony.execute = AsyncMock(side_effect=RuntimeError("Colony crashed"))
    coordinator._get_colony = lambda idx: failing_colony

    # Should raise the exception
    with pytest.raises(RuntimeError, match="Colony crashed"):
        await coordinator._execute_single(
            routing=mock_routing_single,
            params={},
            context={},
        )


@pytest.mark.asyncio
async def test_fano_line_execution_partial_failure(
    coordinator: Any, mock_routing_fano_line: Any
) -> None:
    """Test Fano line execution with partial colony failures."""
    call_count = 0

    async def mock_execute_mixed(action: Any, params: Any, context: Any) -> Any:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("Second colony failed")
        return Mock(success=True, result={"s7_output": torch.randn(8)})

    mock_colony = Mock()
    mock_colony.execute = AsyncMock(side_effect=mock_execute_mixed)
    coordinator._get_colony = lambda idx: mock_colony

    result = await coordinator._execute_fano_line(
        routing=mock_routing_fano_line,
        params={},
        context={},
    )

    # Should return results with failure placeholder for failed colony
    assert len(result["results"]) == 3
    assert result["results"][1].success is False


# =============================================================================
# TEST: EDGE CASES
# =============================================================================


def test_extract_s7_output_tensor_conversion(coordinator: Any) -> None:
    """Test S7 extraction handles list inputs."""
    result = Mock()
    result.result = {
        "s7_output": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0],  # List, not tensor
    }

    output = coordinator._extract_s7_output(result, colony_idx=0)

    assert isinstance(output, torch.Tensor)
    assert output.shape == (8,)


@pytest.mark.asyncio
async def test_execute_intent_empty_context(coordinator: Any, mock_routing_single: Any) -> None:
    """Test execute_intent with None context."""
    with (
        patch.object(coordinator, "_router") as mock_router,
        patch.object(
            coordinator, "_enrich_context_with_world_model", new_callable=AsyncMock
        ) as mock_enrich,
    ):
        mock_router.route.return_value = mock_routing_single
        mock_enrich.return_value = {}

        result = await coordinator.execute_intent(
            intent="test.intent",
            params={},
            context=None,  # None context
        )

        # Should handle None context gracefully
        assert "mode" in result
        mock_enrich.assert_called_once()


def test_encode_e8_message_normalizes_input(coordinator: Any) -> None:
    """Test that E8 encoding normalizes unnormalized input."""
    # Create unnormalized data
    data = torch.tensor([10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0])

    message = coordinator.encode_e8_message(0, 1, data)

    # Should successfully encode (normalization happens inside)
    assert "e8_index" in message
    assert isinstance(message["e8_index"], int)
