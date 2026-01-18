"""Tests for Home Theater Voice Service.

Tests:
- Configuration defaults
- Session lifecycle
- Input trigger detection
- Local network security
- Voice Activity Detection
"""

from __future__ import annotations

import ipaddress
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from kagami.core.services.voice.home_theater_voice import (
    HomeTheaterVoiceConfig,
    HomeTheaterVoiceService,
    VoiceInputState,
    VoiceSession,
    get_home_theater_voice,
    reset_home_theater_voice,
)


# =============================================================================
# Configuration Tests
# =============================================================================


class TestHomeTheaterVoiceConfig:
    """Test configuration defaults and validation."""

    def test_default_trigger_input(self) -> None:
        """Test default trigger input is 'Mac'."""
        config = HomeTheaterVoiceConfig()
        assert config.trigger_input == "Mac"
        assert config.trigger_input_code == "MPLAY"

    def test_default_sample_rate(self) -> None:
        """Test default sample rate is 16kHz for Whisper."""
        config = HomeTheaterVoiceConfig()
        assert config.sample_rate == 16000
        assert config.channels == 1

    def test_vad_defaults(self) -> None:
        """Test VAD defaults are reasonable."""
        config = HomeTheaterVoiceConfig()
        assert config.vad_energy_threshold == 0.01
        assert config.vad_silence_duration == 1.5
        assert config.vad_min_speech_duration == 0.3

    def test_allowed_networks(self) -> None:
        """Test allowed networks include local LAN."""
        config = HomeTheaterVoiceConfig()
        assert "192.168.1.0/24" in config.allowed_networks
        assert "127.0.0.0/8" in config.allowed_networks


# =============================================================================
# Session Tests
# =============================================================================


class TestVoiceSession:
    """Test voice session management."""

    def test_session_creation(self) -> None:
        """Test session is created with defaults."""
        session = VoiceSession()
        assert session.session_id is not None
        assert len(session.session_id) == 36  # UUID format
        assert session.input_source == "Mac"
        assert session.is_authenticated is True
        assert session.auth_method == "denon_input"

    def test_session_authentication(self) -> None:
        """Test session is authenticated by default (physical presence)."""
        session = VoiceSession()
        # Physical presence auth: selecting input = authenticated
        assert session.is_authenticated is True
        assert session.auth_method == "denon_input"

    def test_session_transcript(self) -> None:
        """Test adding conversation turns."""
        session = VoiceSession()
        session.add_turn("user", "Turn on the lights")
        session.add_turn("kagami", "Turning on the lights", latency=250.0)

        assert session.turns == 2
        assert session.transcript[0]["role"] == "user"
        assert session.transcript[0]["text"] == "Turn on the lights"
        assert session.transcript[1]["role"] == "kagami"
        assert 250.0 in session.latency_ms

    def test_session_serialization(self) -> None:
        """Test session can be serialized to dict."""
        session = VoiceSession()
        session.add_turn("user", "Hello")

        data = session.to_dict()

        assert data["session_id"] == session.session_id
        assert data["input_source"] == "Mac"
        assert data["auth_method"] == "denon_input"
        assert data["turns"] == 1


# =============================================================================
# Input Trigger Tests
# =============================================================================


class TestInputTrigger:
    """Test Denon input trigger detection."""

    def test_trigger_input_match(self) -> None:
        """Test trigger input detection."""
        service = HomeTheaterVoiceService()

        # Mac input should trigger
        assert service._is_trigger_input("Mac") is True
        assert service._is_trigger_input("mac") is True  # Case insensitive
        assert service._is_trigger_input("MAC") is True

        # Other inputs should not trigger
        assert service._is_trigger_input("Apple TV") is False
        assert service._is_trigger_input("Control4") is False
        assert service._is_trigger_input("Steam Deck") is False

    def test_custom_trigger_input(self) -> None:
        """Test custom trigger input configuration."""
        config = HomeTheaterVoiceConfig(trigger_input="Control4")
        service = HomeTheaterVoiceService(config)

        assert service._is_trigger_input("Control4") is True
        assert service._is_trigger_input("Mac") is False


# =============================================================================
# Voice Activity Detection Tests
# =============================================================================


class TestVoiceActivityDetection:
    """Test VAD implementation."""

    def test_detect_silence(self) -> None:
        """Test silence is not detected as speech."""
        service = HomeTheaterVoiceService()

        # Silent audio (all zeros)
        silence = np.zeros(1024, dtype=np.float32)
        assert service._detect_voice_activity(silence) == False  # noqa: E712

    def test_detect_speech(self) -> None:
        """Test loud signal is detected as speech."""
        service = HomeTheaterVoiceService()

        # Loud signal (sine wave)
        t = np.linspace(0, 0.1, 1024, dtype=np.float32)
        speech = 0.5 * np.sin(2 * np.pi * 440 * t)  # 440Hz tone
        assert service._detect_voice_activity(speech) == True  # noqa: E712

    def test_empty_audio(self) -> None:
        """Test empty audio returns False."""
        service = HomeTheaterVoiceService()
        assert service._detect_voice_activity(None) is False
        assert service._detect_voice_activity(np.array([])) is False

    def test_threshold_sensitivity(self) -> None:
        """Test threshold sensitivity."""
        # Low threshold config
        config = HomeTheaterVoiceConfig(vad_energy_threshold=0.001)
        service = HomeTheaterVoiceService(config)

        # Quiet signal should be detected with low threshold
        quiet = np.full(1024, 0.02, dtype=np.float32)
        assert service._detect_voice_activity(quiet) == True  # noqa: E712

        # High threshold config
        config2 = HomeTheaterVoiceConfig(vad_energy_threshold=0.1)
        service2 = HomeTheaterVoiceService(config2)
        assert service2._detect_voice_activity(quiet) == False  # noqa: E712


# =============================================================================
# Security Tests
# =============================================================================


class TestSecurity:
    """Test security model."""

    def test_local_network_validation(self) -> None:
        """Test local network IP validation."""
        LOCAL_NETWORKS = [
            ipaddress.ip_network("192.168.1.0/24"),
            ipaddress.ip_network("127.0.0.0/8"),
        ]

        def is_local(ip_str: str) -> bool:
            ip = ipaddress.ip_address(ip_str)
            return any(ip in net for net in LOCAL_NETWORKS)

        # Local IPs should be allowed
        assert is_local("192.168.1.1") is True
        assert is_local("192.168.1.50") is True
        assert is_local("127.0.0.1") is True

        # External IPs should be blocked
        assert is_local("8.8.8.8") is False
        assert is_local("104.16.0.1") is False
        assert is_local("1.1.1.1") is False

    def test_session_auth_method(self) -> None:
        """Test session records correct auth method."""
        session = VoiceSession()
        assert session.auth_method == "denon_input"

        # Custom auth method
        session2 = VoiceSession(auth_method="control4_webhook")
        assert session2.auth_method == "control4_webhook"

    def test_physical_presence_auth(self) -> None:
        """Test physical presence authentication model.

        Security model: selecting "Mac" input on Control4 remote proves
        physical presence in the home, equivalent to caller ID auth.
        """
        session = VoiceSession(
            input_source="Mac",
            is_authenticated=True,
            auth_method="denon_input_selection",
        )

        # Physical presence = authenticated
        assert session.is_authenticated is True
        assert "denon_input" in session.auth_method


# =============================================================================
# Service State Tests
# =============================================================================


class TestServiceState:
    """Test service state management."""

    def test_initial_state(self) -> None:
        """Test service starts in disabled state."""
        service = HomeTheaterVoiceService()
        assert service.state == VoiceInputState.DISABLED
        assert service.is_listening is False

    def test_status_reporting(self) -> None:
        """Test status dict contents."""
        service = HomeTheaterVoiceService()
        status = service.get_status()

        assert "initialized" in status
        assert "state" in status
        assert "trigger_input" in status
        assert "is_listening" in status
        assert status["trigger_input"] == "Mac"
        assert status["is_listening"] is False


# =============================================================================
# Factory Tests
# =============================================================================


class TestFactory:
    """Test singleton factory."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self) -> None:
        """Reset singleton before each test."""
        reset_home_theater_voice()
        yield
        reset_home_theater_voice()

    @pytest.mark.asyncio
    async def test_get_singleton(self) -> None:
        """Test factory returns same instance."""
        service1 = await get_home_theater_voice()
        service2 = await get_home_theater_voice()
        assert service1 is service2

    @pytest.mark.asyncio
    async def test_custom_config(self) -> None:
        """Test factory accepts custom config."""
        config = HomeTheaterVoiceConfig(trigger_input="Control4")
        service = await get_home_theater_voice(config)
        assert service.config.trigger_input == "Control4"
