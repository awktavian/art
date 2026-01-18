"""Tests for emergency control endpoints.

Tests the safety-critical emergency stop, system halt, and resume endpoints.

Created: December 15, 2025
Author: Forge (e₂)
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException

from kagami_api.routes.control import (
    EmergencyStopRequest,
    SystemHaltRequest,
    ResumeSystemRequest,
    emergency_stop,
    system_halt,
    resume_system,
    get_safety_status,
    is_emergency_stop_active,
    _get_current_h_value,
    _get_safety_zone,
)
from kagami_api.security import Principal


@pytest.fixture
def admin_principal():
    """Create an admin principal for testing."""
    return Principal(
        sub="test_admin",
        roles=["admin"],
        scopes=["system:admin"],
    )


@pytest.fixture
def user_principal():
    """Create a regular user principal for testing."""
    return Principal(
        sub="test_user",
        roles=["user"],
        scopes=["user:read"],
    )


# ===== SAFETY ZONE TESTS =====


def test_get_safety_zone_green():
    """Test GREEN zone detection (h > 0.5)."""
    assert _get_safety_zone(0.6) == "GREEN"
    assert _get_safety_zone(1.0) == "GREEN"
    assert _get_safety_zone(10.0) == "GREEN"


def test_get_safety_zone_yellow():
    """Test YELLOW zone detection (0 <= h <= 0.5)."""
    assert _get_safety_zone(0.0) == "YELLOW"
    assert _get_safety_zone(0.25) == "YELLOW"
    assert _get_safety_zone(0.5) == "YELLOW"


def test_get_safety_zone_red():
    """Test RED zone detection (h < 0)."""
    assert _get_safety_zone(-0.1) == "RED"
    assert _get_safety_zone(-1.0) == "RED"
    assert _get_safety_zone(-10.0) == "RED"


def test_get_safety_zone_unknown():
    """Test UNKNOWN zone for None value."""
    assert _get_safety_zone(None) == "UNKNOWN"


# ===== EMERGENCY STOP TESTS =====


@pytest.mark.asyncio
async def test_emergency_stop_invalid_token(admin_principal: Any) -> None:
    """Test emergency stop rejects invalid confirmation token."""
    request = EmergencyStopRequest(
        reason="Test emergency stop",
        confirmation_token="INVALID_TOKEN",
    )

    with pytest.raises(HTTPException) as exc_info:
        await emergency_stop(request, admin_principal)

    assert exc_info.value.status_code == 400
    assert "Invalid confirmation token" in exc_info.value.detail


@pytest.mark.asyncio
async def test_emergency_stop_valid_token(admin_principal: Any) -> None:
    """Test emergency stop with valid confirmation token."""
    request = EmergencyStopRequest(
        reason="Test emergency stop for safety reasons",
        confirmation_token="EMERGENCY_STOP_CONFIRMED",
    )

    # Mock dependencies (patch at import location, not module level)
    with (
        patch("kagami.core.safety.cbf_runtime_monitor.get_cbf_monitor") as mock_cbf,
        patch("kagami.orchestration.colony_manager.get_colony_manager") as mock_manager,
        patch("kagami.core.unified_agents.unified_organism.get_organism") as mock_organism,
        patch("kagami_api.routes.control._emit_emergency_audit_event") as mock_audit,
        patch("kagami_api.routes.control._emit_emergency_receipt") as mock_receipt,
    ):
        # Setup mocks
        mock_cbf.return_value = MagicMock()
        mock_manager.return_value = AsyncMock()
        mock_organism.return_value = MagicMock(_colonies={})

        # Execute emergency stop
        response = await emergency_stop(request, admin_principal)

        # Verify response
        assert response.success is True
        assert response.user == "test_admin"
        assert response.reason == "Test emergency stop for safety reasons"
        assert len(response.actions_taken) > 0

        # Verify emergency stop is active
        assert is_emergency_stop_active() is True

        # Verify audit logging
        mock_audit.assert_called_once()
        mock_receipt.assert_called_once()


@pytest.mark.asyncio
async def test_emergency_stop_forces_h_value(admin_principal: Any) -> None:
    """Test emergency stop forces h(x) = -1.0."""
    request = EmergencyStopRequest(
        reason="Test emergency stop forcing RED zone",
        confirmation_token="EMERGENCY_STOP_CONFIRMED",
    )

    with (
        patch("kagami.core.safety.cbf_runtime_monitor.get_cbf_monitor") as mock_cbf,
        patch("kagami.orchestration.colony_manager.get_colony_manager") as mock_manager,
        patch("kagami.core.unified_agents.unified_organism.get_organism") as mock_organism,
        patch("kagami_api.routes.control._emit_emergency_audit_event"),
        patch("kagami_api.routes.control._emit_emergency_receipt"),
    ):
        mock_monitor = MagicMock()
        mock_cbf.return_value = mock_monitor
        mock_manager.return_value = AsyncMock()
        mock_organism.return_value = MagicMock(_colonies={})

        # Execute emergency stop
        response = await emergency_stop(request, admin_principal)

        # Verify h(x) = -1.0 was logged
        mock_monitor.log_check.assert_called_once()
        call_args = mock_monitor.log_check.call_args
        assert call_args[1]["h_value"] == -1.0
        assert call_args[1]["safe"] is False
        assert call_args[1]["barrier_name"] == "emergency_override"


# ===== SYSTEM HALT TESTS =====


@pytest.mark.asyncio
async def test_system_halt_invalid_token(admin_principal: Any) -> None:
    """Test system halt rejects invalid confirmation token."""
    request = SystemHaltRequest(
        reason="Test system halt",
        confirmation_token="INVALID_TOKEN",
    )

    with pytest.raises(HTTPException) as exc_info:
        await system_halt(request, admin_principal)

    assert exc_info.value.status_code == 400
    assert "Invalid confirmation token" in exc_info.value.detail


@pytest.mark.asyncio
async def test_system_halt_valid_token(admin_principal: Any) -> None:
    """Test system halt with valid confirmation token."""
    request = SystemHaltRequest(
        reason="Test system halt for maintenance",
        confirmation_token="SYSTEM_HALT_CONFIRMED",
    )

    with (
        patch("kagami.orchestration.colony_manager.get_colony_manager") as mock_manager,
        patch("kagami.core.unified_agents.unified_organism.get_organism") as mock_organism,
        patch("kagami_api.routes.control._emit_emergency_audit_event") as mock_audit,
        patch("kagami_api.routes.control._emit_emergency_receipt") as mock_receipt,
    ):
        mock_manager.return_value = AsyncMock()
        mock_organism.return_value = MagicMock(_running=True)

        # Execute system halt
        response = await system_halt(request, admin_principal)

        # Verify response
        assert response.success is True
        assert response.user == "test_admin"
        assert response.reason == "Test system halt for maintenance"
        assert response.colonies_stopped == 7

        # Verify audit logging
        mock_audit.assert_called_once()
        mock_receipt.assert_called_once()


@pytest.mark.asyncio
async def test_system_halt_handles_errors(admin_principal: Any) -> None:
    """Test system halt handles colony manager errors gracefully."""
    request = SystemHaltRequest(
        reason="Test system halt with errors",
        confirmation_token="SYSTEM_HALT_CONFIRMED",
        force=True,
    )

    with (
        patch("kagami.orchestration.colony_manager.get_colony_manager") as mock_manager,
        patch("kagami.core.unified_agents.unified_organism.get_organism") as mock_organism,
        patch("kagami_api.routes.control._emit_emergency_audit_event"),
        patch("kagami_api.routes.control._emit_emergency_receipt"),
    ):
        # Simulate colony manager error
        mock_manager.return_value.stop_all = AsyncMock(side_effect=Exception("Colony error"))
        mock_organism.return_value = MagicMock(_running=True)

        # Execute system halt
        response = await system_halt(request, admin_principal)

        # Verify warnings are present
        assert len(response.warnings) > 0
        assert "Failed to stop some colonies" in response.warnings[0]


# ===== SAFETY STATUS TESTS =====


@pytest.mark.asyncio
async def test_get_safety_status_no_emergency(admin_principal: Any) -> None:
    """Test safety status when no emergency is active."""
    with (
        patch("kagami_api.routes.control._get_current_h_value") as mock_h,
        patch("kagami.orchestration.colony_manager.get_colony_manager") as mock_manager,
    ):
        mock_h.return_value = 0.8
        mock_manager.return_value = MagicMock(
            _colonies={"0": {"healthy": True}, "1": {"healthy": True}},
            all_healthy=MagicMock(return_value=True),
        )

        # Reset emergency stop state
        import kagami_api.routes.control as control_module

        control_module._emergency_stop_active = False

        response = await get_safety_status(admin_principal)

        assert response.emergency_stop_active is False
        assert response.h_value == 0.8
        assert response.safety_zone == "GREEN"
        assert response.colonies_running == 2
        assert response.system_healthy is True


@pytest.mark.asyncio
async def test_get_safety_status_with_emergency(admin_principal: Any) -> None:
    """Test safety status when emergency stop is active."""
    with (
        patch("kagami_api.routes.control._get_current_h_value") as mock_h,
        patch("kagami.orchestration.colony_manager.get_colony_manager") as mock_manager,
    ):
        mock_h.return_value = -1.0
        mock_manager.return_value = MagicMock(
            _colonies={},
            all_healthy=MagicMock(return_value=False),
        )

        # Simulate emergency stop
        import kagami_api.routes.control as control_module

        control_module._emergency_stop_active = True
        control_module._emergency_stop_reason = "Test emergency"
        control_module._emergency_stop_user = "admin"
        control_module._emergency_stop_timestamp = 123456.0

        response = await get_safety_status(admin_principal)

        assert response.emergency_stop_active is True
        assert response.h_value == -1.0
        assert response.safety_zone == "RED"
        assert response.emergency_stop_reason == "Test emergency"
        assert response.emergency_stop_user == "admin"


# ===== RESUME SYSTEM TESTS =====


@pytest.mark.asyncio
async def test_resume_system_no_emergency_active(admin_principal: Any) -> None:
    """Test resume system fails when no emergency is active."""
    request = ResumeSystemRequest(
        reason="Test resume without emergency",
        confirmation_token="RESUME_CONFIRMED",
    )

    # Reset emergency stop state
    import kagami_api.routes.control as control_module

    control_module._emergency_stop_active = False

    with pytest.raises(HTTPException) as exc_info:
        await resume_system(request, admin_principal)

    assert exc_info.value.status_code == 400
    assert "No emergency stop is currently active" in exc_info.value.detail


@pytest.mark.asyncio
async def test_resume_system_valid(admin_principal: Any) -> None:
    """Test resume system with valid confirmation token."""
    request = ResumeSystemRequest(
        reason="Test resume after emergency resolved",
        confirmation_token="RESUME_CONFIRMED",
    )

    with (
        patch("kagami_api.routes.control._emit_emergency_audit_event") as mock_audit,
        patch("kagami_api.routes.control._emit_emergency_receipt") as mock_receipt,
    ):
        # Simulate emergency stop
        import kagami_api.routes.control as control_module

        control_module._emergency_stop_active = True
        control_module._emergency_stop_reason = "Test emergency"

        # Execute resume
        response = await resume_system(request, admin_principal)

        # Verify response
        assert response.success is True
        assert response.user == "test_admin"
        assert response.previous_stop_reason == "Test emergency"

        # Verify emergency stop is cleared
        assert is_emergency_stop_active() is False

        # Verify audit logging
        mock_audit.assert_called_once()
        mock_receipt.assert_called_once()


@pytest.mark.asyncio
async def test_resume_system_invalid_token(admin_principal: Any) -> None:
    """Test resume system rejects invalid confirmation token."""
    request = ResumeSystemRequest(
        reason="Test resume with invalid token",
        confirmation_token="INVALID_TOKEN",
    )

    # Simulate emergency stop
    import kagami_api.routes.control as control_module

    control_module._emergency_stop_active = True

    with pytest.raises(HTTPException) as exc_info:
        await resume_system(request, admin_principal)

    assert exc_info.value.status_code == 400
    assert "Invalid confirmation token" in exc_info.value.detail


# ===== INTEGRATION TESTS =====


@pytest.mark.asyncio
async def test_emergency_stop_then_resume_workflow(admin_principal: Any) -> None:
    """Test full emergency stop → resume workflow."""
    # 1. Emergency stop
    stop_request = EmergencyStopRequest(
        reason="Test full workflow emergency",
        confirmation_token="EMERGENCY_STOP_CONFIRMED",
    )

    with (
        patch("kagami.core.safety.cbf_runtime_monitor.get_cbf_monitor") as mock_cbf,
        patch("kagami.orchestration.colony_manager.get_colony_manager") as mock_manager,
        patch("kagami.core.unified_agents.unified_organism.get_organism") as mock_organism,
        patch("kagami_api.routes.control._emit_emergency_audit_event"),
        patch("kagami_api.routes.control._emit_emergency_receipt"),
    ):
        mock_cbf.return_value = MagicMock()
        mock_manager.return_value = AsyncMock()
        mock_organism.return_value = MagicMock(_colonies={})

        stop_response = await emergency_stop(stop_request, admin_principal)
        assert stop_response.success is True
        assert is_emergency_stop_active() is True

    # 2. Resume
    resume_request = ResumeSystemRequest(
        reason="Test full workflow resume",
        confirmation_token="RESUME_CONFIRMED",
    )

    with (
        patch("kagami_api.routes.control._emit_emergency_audit_event"),
        patch("kagami_api.routes.control._emit_emergency_receipt"),
    ):
        resume_response = await resume_system(resume_request, admin_principal)
        assert resume_response.success is True
        assert is_emergency_stop_active() is False
