"""Tests for Meta Glasses HAL Adapter.

Tests the Meta glasses protocol, camera, and audio adapters.

Created: December 30, 2025
"""

from __future__ import annotations

import asyncio
import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch

from kagami_hal.adapters.meta_glasses import (
    MetaGlassesProtocol,
    MetaGlassesCamera,
    MetaGlassesAudio,
    GlassesConnectionState,
    GlassesCommand,
    GlassesEvent,
    CameraFrame,
    CameraStreamConfig,
    CameraResolution,
    PhotoCaptureResult,
    VisualContext,
    AudioBuffer,
    OpenEarAudioConfig,
    MicrophoneConfig,
    AudioQuality,
)


class TestGlassesProtocol:
    """Tests for MetaGlassesProtocol."""

    @pytest.fixture
    def protocol(self) -> MetaGlassesProtocol:
        """Create protocol instance."""
        return MetaGlassesProtocol()

    @pytest.mark.asyncio
    async def test_initialize(self, protocol: MetaGlassesProtocol):
        """Test protocol initialization."""
        result = await protocol.initialize("http://test.local:8001")
        assert result is True
        assert protocol._api_base_url == "http://test.local:8001"

    @pytest.mark.asyncio
    async def test_status_defaults(self, protocol: MetaGlassesProtocol):
        """Test default status values."""
        status = protocol.status
        assert status.connection_state == GlassesConnectionState.DISCONNECTED
        assert status.battery_level == 0
        assert status.is_wearing is False
        assert status.camera_active is False
        assert status.audio_active is False

    def test_is_connected(self, protocol: MetaGlassesProtocol):
        """Test is_connected property."""
        assert protocol.is_connected is False

        protocol._status.connection_state = GlassesConnectionState.CONNECTED
        assert protocol.is_connected is True

    def test_event_callbacks(self, protocol: MetaGlassesProtocol):
        """Test event callback registration."""
        async def callback(event: GlassesEvent) -> None:
            pass

        protocol.on_event(callback)
        assert callback in protocol._event_callbacks

        protocol.off_event(callback)
        assert callback not in protocol._event_callbacks

    @pytest.mark.asyncio
    async def test_shutdown(self, protocol: MetaGlassesProtocol):
        """Test protocol shutdown."""
        await protocol.shutdown()
        assert protocol._status.connection_state == GlassesConnectionState.DISCONNECTED


class TestGlassesCamera:
    """Tests for MetaGlassesCamera."""

    @pytest.fixture
    def mock_protocol(self) -> MagicMock:
        """Create mock protocol."""
        protocol = MagicMock()
        protocol.is_connected = True
        protocol.send_command = AsyncMock(return_value={"success": True})
        protocol.on_event = MagicMock()
        protocol.off_event = MagicMock()
        return protocol

    @pytest.fixture
    def camera(self, mock_protocol: MagicMock) -> MetaGlassesCamera:
        """Create camera instance with mock protocol."""
        camera = MetaGlassesCamera(mock_protocol)
        return camera

    @pytest.mark.asyncio
    async def test_initialize(self, camera: MetaGlassesCamera):
        """Test camera initialization."""
        result = await camera.initialize()
        assert result is True
        camera._protocol.on_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_stream(self, camera: MetaGlassesCamera):
        """Test starting camera stream."""
        await camera.initialize()

        config = CameraStreamConfig(
            resolution=CameraResolution.MEDIUM,
            fps=15,
            extract_features=True,
        )

        result = await camera.start_stream(config)
        assert result is True
        assert camera.is_streaming is True

        camera._protocol.send_command.assert_called()

    @pytest.mark.asyncio
    async def test_stop_stream(self, camera: MetaGlassesCamera):
        """Test stopping camera stream."""
        await camera.initialize()
        await camera.start_stream()

        await camera.stop_stream()
        assert camera.is_streaming is False

    @pytest.mark.asyncio
    async def test_capture_photo(self, camera: MetaGlassesCamera):
        """Test photo capture."""
        await camera.initialize()

        # Mock response with image data
        import base64
        fake_image = b"fake_jpeg_data"
        camera._protocol.send_command = AsyncMock(return_value={
            "success": True,
            "image_data": base64.b64encode(fake_image).decode(),
            "width": 1920,
            "height": 1080,
            "timestamp": time.time(),
            "features": {"scene_type": "office"},
        })

        result = await camera.capture_photo()
        assert result is not None
        assert result.success is True
        assert result.width == 1920
        assert result.height == 1080
        assert result.data == fake_image
        assert result.features.get("scene_type") == "office"

    @pytest.mark.asyncio
    async def test_capture_photo_not_connected(self, camera: MetaGlassesCamera):
        """Test photo capture when not connected."""
        camera._protocol.is_connected = False

        result = await camera.capture_photo()
        assert result.success is False
        assert "not connected" in result.error.lower()

    @pytest.mark.asyncio
    async def test_get_visual_context(self, camera: MetaGlassesCamera):
        """Test visual context extraction."""
        await camera.initialize()

        import base64
        camera._protocol.send_command = AsyncMock(return_value={
            "success": True,
            "image_data": base64.b64encode(b"data").decode(),
            "width": 1280,
            "height": 720,
            "timestamp": time.time(),
            "features": {
                "is_indoor": True,
                "lighting": "bright",
                "scene_type": "kitchen",
                "objects": ["refrigerator", "counter"],
                "text": ["recipe"],
                "face_count": 0,
                "activity": "cooking",
                "confidence": 0.85,
            },
        })

        context = await camera.get_visual_context()
        assert context.is_indoor is True
        assert context.lighting == "bright"
        assert context.scene_type == "kitchen"
        assert "refrigerator" in context.detected_objects
        assert context.activity_hint == "cooking"
        assert context.confidence == 0.85

    def test_frame_callbacks(self, camera: MetaGlassesCamera):
        """Test frame callback registration."""
        async def callback(frame: CameraFrame) -> None:
            pass

        camera.on_frame(callback)
        assert callback in camera._frame_callbacks

        camera.off_frame(callback)
        assert callback not in camera._frame_callbacks


class TestGlassesAudio:
    """Tests for MetaGlassesAudio."""

    @pytest.fixture
    def mock_protocol(self) -> MagicMock:
        """Create mock protocol."""
        protocol = MagicMock()
        protocol.is_connected = True
        protocol.send_command = AsyncMock(return_value={"success": True})
        protocol.on_event = MagicMock()
        protocol.off_event = MagicMock()
        return protocol

    @pytest.fixture
    def audio(self, mock_protocol: MagicMock) -> MetaGlassesAudio:
        """Create audio instance with mock protocol."""
        audio = MetaGlassesAudio(mock_protocol)
        return audio

    @pytest.mark.asyncio
    async def test_initialize(self, audio: MetaGlassesAudio):
        """Test audio initialization."""
        result = await audio.initialize()
        assert result is True
        audio._protocol.on_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_listening(self, audio: MetaGlassesAudio):
        """Test starting microphone."""
        await audio.initialize()

        config = MicrophoneConfig(
            quality=AudioQuality.MEDIUM,
            noise_cancellation=True,
        )

        result = await audio.start_listening(config)
        assert result is True
        assert audio.is_listening is True

    @pytest.mark.asyncio
    async def test_stop_listening(self, audio: MetaGlassesAudio):
        """Test stopping microphone."""
        await audio.initialize()
        await audio.start_listening()

        await audio.stop_listening()
        assert audio.is_listening is False

    @pytest.mark.asyncio
    async def test_speak(self, audio: MetaGlassesAudio):
        """Test TTS speak."""
        await audio.initialize()

        result = await audio.speak("Hello Tim", voice="kagami", volume=0.7)
        assert result is True

        audio._protocol.send_command.assert_called()
        call_args = audio._protocol.send_command.call_args
        assert call_args[0][0] == GlassesCommand.PLAY_AUDIO
        assert call_args[1]["params"]["type"] == "tts"
        assert call_args[1]["params"]["text"] == "Hello Tim"

    @pytest.mark.asyncio
    async def test_speak_not_connected(self, audio: MetaGlassesAudio):
        """Test speak when not connected."""
        audio._protocol.is_connected = False

        result = await audio.speak("Hello")
        assert result is False

    @pytest.mark.asyncio
    async def test_play_notification(self, audio: MetaGlassesAudio):
        """Test notification sound playback."""
        await audio.initialize()

        result = await audio.play_notification("alert", volume=0.5)
        assert result is True

    def test_audio_callbacks(self, audio: MetaGlassesAudio):
        """Test audio callback registration."""
        async def callback(buffer: AudioBuffer) -> None:
            pass

        audio.on_audio(callback)
        assert callback in audio._audio_callbacks

        audio.off_audio(callback)
        assert callback not in audio._audio_callbacks


class TestCameraStreamConfig:
    """Tests for CameraStreamConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = CameraStreamConfig()
        assert config.resolution == CameraResolution.MEDIUM
        assert config.fps == 15
        assert config.jpeg_quality == 80
        assert config.extract_features is True
        assert config.send_raw is False

    def test_custom_config(self):
        """Test custom configuration."""
        config = CameraStreamConfig(
            resolution=CameraResolution.HIGH,
            fps=30,
            jpeg_quality=95,
            extract_features=False,
            send_raw=True,
        )
        assert config.resolution == CameraResolution.HIGH
        assert config.fps == 30
        assert config.jpeg_quality == 95


class TestVisualContext:
    """Tests for VisualContext dataclass."""

    def test_default_context(self):
        """Test default context values."""
        context = VisualContext()
        assert context.is_indoor is None
        assert context.scene_type is None
        assert context.detected_objects == []
        assert context.faces_detected == 0
        assert context.confidence == 0.0

    def test_context_with_data(self):
        """Test context with data."""
        context = VisualContext(
            is_indoor=True,
            lighting="bright",
            scene_type="office",
            detected_objects=["desk", "monitor", "keyboard"],
            detected_text=["Work Task"],
            faces_detected=1,
            known_people=["Tim"],
            activity_hint="working",
            confidence=0.9,
        )
        assert context.is_indoor is True
        assert context.scene_type == "office"
        assert len(context.detected_objects) == 3
        assert context.faces_detected == 1
        assert context.activity_hint == "working"


class TestOpenEarAudioConfig:
    """Tests for OpenEarAudioConfig dataclass."""

    def test_default_config(self):
        """Test default audio config."""
        config = OpenEarAudioConfig()
        assert config.volume == 0.7
        assert config.spatial is True
        assert config.priority == 5
        assert config.ducking is True


class TestGlassesEvent:
    """Tests for GlassesEvent dataclass."""

    def test_from_json(self):
        """Test event creation from JSON."""
        json_data = {
            "type": "camera_frame",
            "timestamp": 1234567890.0,
            "data": {"width": 1920, "height": 1080},
        }
        event = GlassesEvent.from_json(json_data)
        assert event.event_type == "camera_frame"
        assert event.timestamp == 1234567890.0
        assert event.data["width"] == 1920

    def test_from_json_defaults(self):
        """Test event creation with missing fields."""
        json_data = {}
        event = GlassesEvent.from_json(json_data)
        assert event.event_type == "unknown"
        assert event.timestamp == 0.0
        assert event.data == {}
