"""Tests for the RTE (Real-Time Executor) subsystem.

Tests cover:
- Protocol encoding/decoding
- VirtualRTE for testing
- Command recording
- Event injection

Created: January 2, 2026
"""

import pytest
from kagami_hal.rte import (
    LEDPattern,
    NativeRTE,
    RTECommand,
    RTEError,
    RTEEvent,
    RTEEventType,
    RTEResponse,
    RTEStatus,
    VirtualRTE,
    encode_command,
    get_rte_backend,
    parse_response,
)


class TestProtocol:
    """Test RTE protocol encoding/decoding."""

    def test_encode_command_no_args(self):
        """Test encoding command without arguments."""
        data = encode_command(RTECommand.PING)
        assert data == b"PNG\n"

    def test_encode_command_single_arg(self):
        """Test encoding command with single argument."""
        data = encode_command(RTECommand.LED_PATTERN, 1)
        assert data == b"PAT:1\n"

    def test_encode_command_multiple_args(self):
        """Test encoding command with multiple arguments."""
        data = encode_command(RTECommand.LED_COLOR, 255, 128, 0)
        assert data == b"COL:255,128,0\n"

    def test_parse_response_simple(self):
        """Test parsing simple response."""
        resp, args = parse_response(b"PON\n")
        assert resp == RTEResponse.PONG
        assert args == []

    def test_parse_response_with_args(self):
        """Test parsing response with arguments."""
        resp, args = parse_response(b"STS:1,128,1000\n")
        assert resp == RTEResponse.STATUS
        assert args == ["1", "128", "1000"]

    def test_parse_response_error(self):
        """Test parsing error response raises exception."""
        with pytest.raises(RTEError) as exc_info:
            parse_response(b"ERR:3\n")
        assert exc_info.value.code == 3


class TestRTEError:
    """Test RTE error handling."""

    def test_error_code(self):
        """Test error code storage."""
        err = RTEError(RTEError.TIMEOUT)
        assert err.code == RTEError.TIMEOUT

    def test_error_message(self):
        """Test error message generation."""
        err = RTEError(RTEError.HARDWARE_FAILURE)
        assert "Hardware failure" in err.message

    def test_error_custom_message(self):
        """Test custom error message."""
        err = RTEError(1, "Custom error")
        assert err.message == "Custom error"


class TestLEDPattern:
    """Test LED pattern enum."""

    def test_pattern_values(self):
        """Test pattern integer values."""
        assert LEDPattern.IDLE == 0
        assert LEDPattern.BREATHING == 1
        assert LEDPattern.SAFETY_VIOLATION == 15

    def test_pattern_from_int(self):
        """Test creating pattern from int."""
        pattern = LEDPattern(5)
        assert pattern == LEDPattern.FLASH


class TestRTEStatus:
    """Test RTE status dataclass."""

    def test_default_status(self):
        """Test default status values."""
        status = RTEStatus()
        assert status.pattern == 0
        assert status.brightness == 128
        assert not status.connected

    def test_pattern_name(self):
        """Test pattern name property."""
        status = RTEStatus(pattern=1)
        assert status.pattern_name == "BREATHING"

    def test_unknown_pattern_name(self):
        """Test unknown pattern name."""
        status = RTEStatus(pattern=99)
        assert "UNKNOWN" in status.pattern_name


class TestRTEEvent:
    """Test RTE event dataclass."""

    def test_button_pressed_event(self):
        """Test creating button pressed event."""
        event = RTEEvent.button_pressed()
        assert event.event_type == RTEEventType.BUTTON_PRESSED

    def test_error_event(self):
        """Test creating error event."""
        event = RTEEvent.error(3, "Hardware failure")
        assert event.event_type == RTEEventType.ERROR
        assert event.data["code"] == 3
        assert event.data["message"] == "Hardware failure"


class TestVirtualRTE:
    """Test VirtualRTE backend."""

    @pytest.mark.asyncio
    async def test_initialize(self):
        """Test initialization."""
        rte = VirtualRTE()
        await rte.initialize()
        assert rte.is_connected()
        await rte.shutdown()

    @pytest.mark.asyncio
    async def test_ping(self):
        """Test ping command."""
        rte = VirtualRTE()
        await rte.initialize()
        result = await rte.ping()
        assert result is True
        await rte.shutdown()

    @pytest.mark.asyncio
    async def test_set_pattern(self):
        """Test setting pattern."""
        rte = VirtualRTE()
        await rte.initialize()
        await rte.set_pattern(1)
        status = await rte.get_status()
        assert status.pattern == 1
        await rte.shutdown()

    @pytest.mark.asyncio
    async def test_set_brightness(self):
        """Test setting brightness."""
        rte = VirtualRTE()
        await rte.initialize()
        await rte.set_brightness(200)
        status = await rte.get_status()
        assert status.brightness == 200
        await rte.shutdown()

    @pytest.mark.asyncio
    async def test_set_color(self):
        """Test setting color."""
        rte = VirtualRTE()
        await rte.initialize()
        await rte.set_color(255, 128, 0)
        assert rte.state["override_color"] == (255, 128, 0)
        await rte.shutdown()

    @pytest.mark.asyncio
    async def test_command_logging(self):
        """Test command logging."""
        rte = VirtualRTE()
        await rte.initialize()
        await rte.send_command(RTECommand.LED_PATTERN, 1)
        await rte.send_command(RTECommand.LED_BRIGHTNESS, 200)

        assert len(rte.command_log) == 2
        assert rte.command_log[0].command == RTECommand.LED_PATTERN
        assert rte.command_log[1].command == RTECommand.LED_BRIGHTNESS
        await rte.shutdown()

    @pytest.mark.asyncio
    async def test_event_injection(self):
        """Test event injection."""
        rte = VirtualRTE()
        await rte.initialize()
        rte.inject_event(RTEEvent.button_pressed())
        events = await rte.poll_events()

        assert len(events) == 1
        assert events[0].event_type == RTEEventType.BUTTON_PRESSED
        await rte.shutdown()

    @pytest.mark.asyncio
    async def test_fail_next(self):
        """Test forced failure."""
        rte = VirtualRTE()
        await rte.initialize()
        rte.set_fail_next(RTEError.HARDWARE_FAILURE)

        with pytest.raises(RTEError) as exc_info:
            await rte.send_command(RTECommand.PING)

        assert exc_info.value.code == RTEError.HARDWARE_FAILURE
        await rte.shutdown()

    @pytest.mark.asyncio
    async def test_assert_command_sent(self):
        """Test command assertion."""
        rte = VirtualRTE()
        await rte.initialize()
        await rte.send_command(RTECommand.LED_PATTERN, 5)

        # Should not raise
        rte.assert_command_sent(RTECommand.LED_PATTERN, (5,))

        # Should raise
        with pytest.raises(AssertionError):
            rte.assert_command_sent(RTECommand.LED_BRIGHTNESS)
        await rte.shutdown()

    @pytest.mark.asyncio
    async def test_reset_state(self):
        """Test state reset."""
        rte = VirtualRTE()
        await rte.initialize()
        await rte.set_pattern(5)
        await rte.set_brightness(200)
        rte.reset_state()

        status = await rte.get_status()
        assert status.pattern == LEDPattern.IDLE
        assert status.brightness == 128
        assert len(rte.command_log) == 0
        await rte.shutdown()

    @pytest.mark.asyncio
    async def test_convenience_methods(self):
        """Test convenience methods."""
        rte = VirtualRTE()
        await rte.initialize()
        await rte.show_listening()
        assert rte.state["pattern"] == LEDPattern.PULSE

        await rte.show_success()
        assert rte.state["pattern"] == LEDPattern.FLASH

        await rte.show_error()
        assert rte.state["pattern"] == LEDPattern.ERROR_FLASH
        await rte.shutdown()

    @pytest.mark.asyncio
    async def test_show_safety(self):
        """Test safety visualization."""
        rte = VirtualRTE()
        await rte.initialize()
        await rte.show_safety(0.8)
        assert rte.state["pattern"] == LEDPattern.SAFETY_SAFE

        await rte.show_safety(0.2)
        assert rte.state["pattern"] == LEDPattern.SAFETY_CAUTION

        await rte.show_safety(-0.1)
        assert rte.state["pattern"] == LEDPattern.SAFETY_VIOLATION
        await rte.shutdown()


class TestGetRTEBackend:
    """Test RTE backend factory."""

    @pytest.mark.asyncio
    async def test_fallback_to_virtual(self):
        """Test fallback to VirtualRTE when no hardware."""
        # When no hardware is available, should fall back to Virtual
        rte = await get_rte_backend(prefer_pico=False)

        # Should get either Native or Virtual
        assert isinstance(rte, (NativeRTE, VirtualRTE))

        await rte.shutdown()


class TestNativeRTE:
    """Test NativeRTE backend (virtual mode on non-Pi systems)."""

    @pytest.mark.asyncio
    async def test_initialize(self):
        """Test initialization (should work even without hardware)."""
        rte = NativeRTE()
        result = await rte.initialize()

        # Should succeed (virtual mode if no hardware)
        assert result is True

        await rte.shutdown()

    @pytest.mark.asyncio
    async def test_commands(self):
        """Test commands work in virtual mode."""
        rte = NativeRTE()
        await rte.initialize()

        response = await rte.send_command(RTECommand.PING)
        assert response == "PON"

        response = await rte.send_command(RTECommand.LED_PATTERN, 1)
        assert response == "OK"

        await rte.shutdown()
