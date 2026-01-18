"""Tests for video compositing — FFmpeg and OBS engines.

Tests the FFmpeg offline compositor and OBS real-time compositor,
including layer management and output format validation.
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from kagami_studio.obs.compositing import (
    CompositeLayer,
    LayerBlendMode,
    OBSCompositor,
    create_corner_cam_layout,
    create_pip_layout,
    create_side_by_side_layout,
)
from kagami_studio.production.compositor import (
    CHROMAKEY_PRESETS,
    LAYOUTS,
    CompositeResult,
    composite_multi_shot,
    composite_video,
    concatenate_videos,
)

# =============================================================================
# COMPOSITE RESULT TESTS
# =============================================================================


class TestCompositeResult:
    """Tests for CompositeResult dataclass."""

    def test_success_result(self, tmp_path: Path) -> None:
        """Test creating successful composite result."""
        output_path = tmp_path / "final.mp4"
        result = CompositeResult(success=True, output_path=output_path, duration_s=30.5)

        assert result.success is True
        assert result.output_path == output_path
        assert result.duration_s == 30.5
        assert result.error is None

    def test_failure_result(self) -> None:
        """Test creating failed composite result."""
        result = CompositeResult(success=False, error="FFmpeg encoding error")

        assert result.success is False
        assert result.output_path is None
        assert result.error == "FFmpeg encoding error"

    def test_default_values(self) -> None:
        """Test default values."""
        result = CompositeResult(success=True)

        assert result.output_path is None
        assert result.duration_s == 0.0
        assert result.error is None


# =============================================================================
# LAYOUT CONFIGURATION TESTS
# =============================================================================


class TestLayouts:
    """Tests for layout configurations."""

    def test_corner_layout(self) -> None:
        """Test corner layout configuration."""
        layout = LAYOUTS["corner"]

        assert layout["scale"] == "0.25"
        assert "W-w" in layout["x"]  # Right-aligned
        assert "H-h" in layout["y"]  # Bottom-aligned

    def test_corner_left_layout(self) -> None:
        """Test corner_left layout."""
        layout = LAYOUTS["corner_left"]

        assert layout["scale"] == "0.25"
        assert layout["x"] == "50"  # Left side

    def test_side_by_side_layout(self) -> None:
        """Test side_by_side layout."""
        layout = LAYOUTS["side_by_side"]

        assert layout["scale"] == "0.5"
        assert "W-w" in layout["x"]  # Right half

    def test_pip_layout(self) -> None:
        """Test picture-in-picture layout."""
        layout = LAYOUTS["pip"]

        assert layout["scale"] == "0.30"
        assert "description" in layout

    def test_pip_top_layout(self) -> None:
        """Test pip_top layout."""
        layout = LAYOUTS["pip_top"]

        assert layout["y"] == "50"  # Top position

    def test_fullscreen_layout(self) -> None:
        """Test fullscreen layout."""
        layout = LAYOUTS["fullscreen"]

        assert layout["scale"] == "1.0"
        assert layout["x"] == "0"
        assert layout["y"] == "0"


# =============================================================================
# CHROMAKEY PRESET TESTS
# =============================================================================


class TestChromakeyPresets:
    """Tests for chromakey configurations."""

    def test_green_preset(self) -> None:
        """Test green chromakey preset."""
        preset = CHROMAKEY_PRESETS["green"]

        assert preset["color"] == "0x00ff00"
        assert float(preset["similarity"]) == 0.3
        assert float(preset["smoothness"]) == 0.1

    def test_green_loose_preset(self) -> None:
        """Test green_loose chromakey preset."""
        preset = CHROMAKEY_PRESETS["green_loose"]

        assert float(preset["similarity"]) == 0.4  # More tolerant

    def test_blue_preset(self) -> None:
        """Test blue chromakey preset."""
        preset = CHROMAKEY_PRESETS["blue"]

        assert preset["color"] == "0x0000ff"

    def test_blue_loose_preset(self) -> None:
        """Test blue_loose chromakey preset."""
        preset = CHROMAKEY_PRESETS["blue_loose"]

        assert float(preset["similarity"]) == 0.4


# =============================================================================
# COMPOSITE_VIDEO TESTS
# =============================================================================


class TestCompositeVideo:
    """Tests for composite_video() function."""

    @pytest.fixture
    def video_files(self, tmp_path: Path) -> dict[str, Path]:
        """Create mock video files for testing."""
        slides = tmp_path / "slides.mp4"
        slides.write_bytes(b"fake slides video")

        avatar = tmp_path / "avatar.mp4"
        avatar.write_bytes(b"fake avatar video")

        audio = tmp_path / "audio.mp3"
        audio.write_bytes(b"fake audio")

        subtitles = tmp_path / "subtitles.ass"
        subtitles.write_text("[Script Info]\n")

        return {
            "slides": slides,
            "avatar": avatar,
            "audio": audio,
            "subtitles": subtitles,
            "output": tmp_path / "final.mp4",
        }

    @pytest.mark.asyncio
    async def test_composite_simple_success(self, video_files: dict[str, Path]) -> None:
        """Test simple compositing (no avatar)."""
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = ""
        mock_process.stderr = ""

        with (
            patch(
                "kagami_studio.production.compositor._run_ffmpeg",
                new_callable=AsyncMock,
                return_value=mock_process,
            ),
            patch(
                "kagami_studio.production.compositor._get_video_duration",
                return_value=30.0,
            ),
        ):
            result = await composite_video(
                slides_video=video_files["slides"],
                avatar_video=None,  # No avatar
                audio_path=video_files["audio"],
                output_path=video_files["output"],
            )

        assert result.success is True
        assert result.duration_s == 30.0

    @pytest.mark.asyncio
    async def test_composite_with_avatar(self, video_files: dict[str, Path]) -> None:
        """Test compositing with avatar overlay."""
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = ""
        mock_process.stderr = ""

        with (
            patch(
                "kagami_studio.production.compositor._run_ffmpeg",
                new_callable=AsyncMock,
                return_value=mock_process,
            ),
            patch(
                "kagami_studio.production.compositor._get_video_duration",
                return_value=30.0,
            ),
        ):
            result = await composite_video(
                slides_video=video_files["slides"],
                avatar_video=video_files["avatar"],
                audio_path=video_files["audio"],
                output_path=video_files["output"],
                layout="corner",
                chromakey="green",
            )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_composite_with_subtitles(self, video_files: dict[str, Path]) -> None:
        """Test compositing with subtitles."""
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = ""
        mock_process.stderr = ""

        with (
            patch(
                "kagami_studio.production.compositor._run_ffmpeg",
                new_callable=AsyncMock,
                return_value=mock_process,
            ),
            patch(
                "kagami_studio.production.compositor._get_video_duration",
                return_value=30.0,
            ),
        ):
            result = await composite_video(
                slides_video=video_files["slides"],
                avatar_video=None,
                audio_path=video_files["audio"],
                subtitle_path=video_files["subtitles"],
                output_path=video_files["output"],
            )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_composite_ffmpeg_failure(self, video_files: dict[str, Path]) -> None:
        """Test handling of FFmpeg failure."""
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.stdout = ""
        mock_process.stderr = "Error: codec not found"

        with patch(
            "kagami_studio.production.compositor._run_ffmpeg",
            new_callable=AsyncMock,
            return_value=mock_process,
        ):
            result = await composite_video(
                slides_video=video_files["slides"],
                avatar_video=None,
                audio_path=video_files["audio"],
                output_path=video_files["output"],
            )

        assert result.success is False
        assert "FFmpeg failed" in result.error

    @pytest.mark.asyncio
    async def test_composite_different_layouts(self, video_files: dict[str, Path]) -> None:
        """Test compositing with different layout options."""
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stderr = ""

        layouts_to_test = ["corner", "side_by_side", "pip", "pip_top"]

        for layout in layouts_to_test:
            with (
                patch(
                    "kagami_studio.production.compositor._run_ffmpeg",
                    new_callable=AsyncMock,
                    return_value=mock_process,
                ),
                patch(
                    "kagami_studio.production.compositor._get_video_duration",
                    return_value=30.0,
                ),
            ):
                result = await composite_video(
                    slides_video=video_files["slides"],
                    avatar_video=video_files["avatar"],
                    audio_path=video_files["audio"],
                    output_path=video_files["output"],
                    layout=layout,
                )

            assert result.success is True, f"Failed for layout: {layout}"

    @pytest.mark.asyncio
    async def test_composite_nonexistent_avatar(self, video_files: dict[str, Path]) -> None:
        """Test compositing with nonexistent avatar (falls back to simple)."""
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stderr = ""

        nonexistent_avatar = video_files["output"].parent / "nonexistent.mp4"

        with (
            patch(
                "kagami_studio.production.compositor._run_ffmpeg",
                new_callable=AsyncMock,
                return_value=mock_process,
            ),
            patch(
                "kagami_studio.production.compositor._get_video_duration",
                return_value=30.0,
            ),
        ):
            result = await composite_video(
                slides_video=video_files["slides"],
                avatar_video=nonexistent_avatar,  # Doesn't exist
                audio_path=video_files["audio"],
                output_path=video_files["output"],
            )

        # Should fall back to simple composite
        assert result.success is True


# =============================================================================
# COMPOSITE_MULTI_SHOT TESTS
# =============================================================================


class TestCompositeMultiShot:
    """Tests for composite_multi_shot() function."""

    @pytest.fixture
    def shot_videos(self, tmp_path: Path) -> dict:
        """Create mock shot video files."""
        slides = tmp_path / "slides.mp4"
        slides.write_bytes(b"fake slides")

        shot1 = tmp_path / "shot_dialogue.mp4"
        shot1.write_bytes(b"fake dialogue")

        shot2 = tmp_path / "shot_reverse.mp4"
        shot2.write_bytes(b"fake reverse")

        audio = tmp_path / "audio.mp3"
        audio.write_bytes(b"fake audio")

        return {
            "slides": slides,
            "shots": [
                {"video": shot1, "type": "dialogue", "start_ms": 0, "end_ms": 5000},
                {"video": shot2, "type": "reverse", "start_ms": 5000, "end_ms": 8000},
            ],
            "audio": audio,
            "output": tmp_path / "final.mp4",
        }

    @pytest.mark.asyncio
    async def test_multi_shot_with_dialogue(self, shot_videos: dict) -> None:
        """Test multi-shot with dialogue as primary."""
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stderr = ""

        with (
            patch(
                "kagami_studio.production.compositor._run_ffmpeg",
                new_callable=AsyncMock,
                return_value=mock_process,
            ),
            patch(
                "kagami_studio.production.compositor._get_video_duration",
                return_value=8.0,
            ),
        ):
            result = await composite_multi_shot(
                slides_video=shot_videos["slides"],
                shot_videos=shot_videos["shots"],
                audio_path=shot_videos["audio"],
                subtitle_path=None,
                output_path=shot_videos["output"],
            )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_multi_shot_empty_shots(self, tmp_path: Path) -> None:
        """Test multi-shot with no shots (falls back to simple)."""
        slides = tmp_path / "slides.mp4"
        slides.write_bytes(b"fake")
        audio = tmp_path / "audio.mp3"
        audio.write_bytes(b"fake")

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stderr = ""

        with (
            patch(
                "kagami_studio.production.compositor._run_ffmpeg",
                new_callable=AsyncMock,
                return_value=mock_process,
            ),
            patch(
                "kagami_studio.production.compositor._get_video_duration",
                return_value=5.0,
            ),
        ):
            result = await composite_multi_shot(
                slides_video=slides,
                shot_videos=[],  # No shots
                audio_path=audio,
                subtitle_path=None,
                output_path=tmp_path / "output.mp4",
            )

        # Should fall back to simple composite
        assert result.success is True


# =============================================================================
# CONCATENATE_VIDEOS TESTS
# =============================================================================


class TestConcatenateVideos:
    """Tests for concatenate_videos() function."""

    @pytest.fixture
    def video_list(self, tmp_path: Path) -> list[Path]:
        """Create mock video files for concatenation."""
        videos = []
        for i in range(3):
            video = tmp_path / f"segment_{i}.mp4"
            video.write_bytes(f"fake video {i}".encode())
            videos.append(video)
        return videos

    @pytest.mark.asyncio
    async def test_concatenate_multiple(self, video_list: list[Path], tmp_path: Path) -> None:
        """Test concatenating multiple videos."""
        output = tmp_path / "concat.mp4"

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stderr = ""

        with (
            patch(
                "kagami_studio.production.compositor._run_ffmpeg",
                new_callable=AsyncMock,
                return_value=mock_process,
            ),
            patch(
                "kagami_studio.production.compositor._get_video_duration",
                return_value=15.0,
            ),
        ):
            result = await concatenate_videos(video_list, output)

        assert result.success is True
        assert result.duration_s == 15.0

    @pytest.mark.asyncio
    async def test_concatenate_single(self, video_list: list[Path], tmp_path: Path) -> None:
        """Test concatenating single video (copy)."""
        output = tmp_path / "single.mp4"

        mock_process = MagicMock()
        mock_process.returncode = 0

        with patch(
            "kagami_studio.production.compositor._run_ffmpeg",
            new_callable=AsyncMock,
            return_value=mock_process,
        ):
            result = await concatenate_videos([video_list[0]], output)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_concatenate_with_audio(self, video_list: list[Path], tmp_path: Path) -> None:
        """Test concatenating with replacement audio."""
        output = tmp_path / "concat_audio.mp4"
        audio = tmp_path / "new_audio.mp3"
        audio.write_bytes(b"fake audio")

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stderr = ""

        with (
            patch(
                "kagami_studio.production.compositor._run_ffmpeg",
                new_callable=AsyncMock,
                return_value=mock_process,
            ),
            patch(
                "kagami_studio.production.compositor._get_video_duration",
                return_value=15.0,
            ),
        ):
            result = await concatenate_videos(video_list, output, audio_path=audio)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_concatenate_empty_list(self, tmp_path: Path) -> None:
        """Test concatenating empty list."""
        result = await concatenate_videos([], tmp_path / "empty.mp4")

        assert result.success is False
        assert "No videos" in result.error

    @pytest.mark.asyncio
    async def test_concatenate_failure(self, video_list: list[Path], tmp_path: Path) -> None:
        """Test concatenation failure handling."""
        output = tmp_path / "fail.mp4"

        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.stderr = "Concat error"

        with patch(
            "kagami_studio.production.compositor._run_ffmpeg",
            new_callable=AsyncMock,
            return_value=mock_process,
        ):
            result = await concatenate_videos(video_list, output)

        assert result.success is False
        assert "Concatenation failed" in result.error


# =============================================================================
# OBS COMPOSITOR TESTS
# =============================================================================


class TestOBSCompositor:
    """Tests for OBSCompositor class."""

    @pytest.fixture
    def mock_obs(self) -> MagicMock:
        """Create mock OBS controller."""
        obs = MagicMock()
        obs.set_source_transform = AsyncMock()
        obs.set_source_visible = AsyncMock()
        obs.add_filter = AsyncMock()
        obs.set_filter_settings = AsyncMock()
        obs.remove_source = AsyncMock()
        return obs

    @pytest.fixture
    def compositor(self, mock_obs: MagicMock) -> OBSCompositor:
        """Create OBS compositor."""
        return OBSCompositor(mock_obs, canvas_width=1920, canvas_height=1080)

    @pytest.mark.asyncio
    async def test_add_layer(self, compositor: OBSCompositor, mock_obs: MagicMock) -> None:
        """Test adding a layer."""
        layer = CompositeLayer(
            source_name="Webcam",
            position=(100, 100),
            scale=(0.5, 0.5),
        )

        await compositor.add_layer(layer)

        mock_obs.set_source_transform.assert_called_once()
        mock_obs.set_source_visible.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_layer_with_opacity(
        self, compositor: OBSCompositor, mock_obs: MagicMock
    ) -> None:
        """Test adding layer with opacity."""
        layer = CompositeLayer(
            source_name="Overlay",
            opacity=0.7,
        )

        await compositor.add_layer(layer)

        # Should add opacity filter
        mock_obs.add_filter.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_layer(self, compositor: OBSCompositor, mock_obs: MagicMock) -> None:
        """Test updating layer properties."""
        # First add a layer
        layer = CompositeLayer(source_name="Source1")
        await compositor.add_layer(layer)

        # Then update it
        await compositor.update_layer(
            "Source1",
            position=(200, 200),
            scale=(0.8, 0.8),
        )

        # Should call transform again
        assert mock_obs.set_source_transform.call_count >= 2

    @pytest.mark.asyncio
    async def test_update_layer_visibility(
        self, compositor: OBSCompositor, mock_obs: MagicMock
    ) -> None:
        """Test updating layer visibility."""
        layer = CompositeLayer(source_name="Source1")
        await compositor.add_layer(layer)

        await compositor.update_layer("Source1", visible=False)

        # Should have been called at least twice (add + update)
        assert mock_obs.set_source_visible.call_count >= 2

    @pytest.mark.asyncio
    async def test_remove_layer(self, compositor: OBSCompositor, mock_obs: MagicMock) -> None:
        """Test removing a layer."""
        layer = CompositeLayer(source_name="ToRemove")
        await compositor.add_layer(layer)

        await compositor.remove_layer("ToRemove")

        mock_obs.remove_source.assert_called_once_with("ToRemove", None)

    @pytest.mark.asyncio
    async def test_create_pip(self, compositor: OBSCompositor, mock_obs: MagicMock) -> None:
        """Test creating PIP layout."""
        await compositor.create_pip(
            main_source="GameCapture",
            pip_source="Webcam",
            pip_corner="bottom-right",
            pip_size=0.25,
        )

        # Should add two layers
        assert mock_obs.set_source_transform.call_count == 2

    @pytest.mark.asyncio
    async def test_create_pip_different_corners(
        self, compositor: OBSCompositor, mock_obs: MagicMock
    ) -> None:
        """Test PIP in different corners."""
        corners = ["top-left", "top-right", "bottom-left", "bottom-right"]

        for corner in corners:
            mock_obs.reset_mock()
            compositor._layers.clear()

            await compositor.create_pip(
                main_source="Main",
                pip_source="PIP",
                pip_corner=corner,
            )

            assert mock_obs.set_source_transform.call_count == 2

    @pytest.mark.asyncio
    async def test_create_split_screen(
        self, compositor: OBSCompositor, mock_obs: MagicMock
    ) -> None:
        """Test creating split screen layout."""
        await compositor.create_split_screen(
            left_source="Camera1",
            right_source="Camera2",
            split_ratio=0.5,
        )

        # Should add two layers
        assert mock_obs.set_source_transform.call_count == 2

    @pytest.mark.asyncio
    async def test_create_corner_camera(
        self, compositor: OBSCompositor, mock_obs: MagicMock
    ) -> None:
        """Test creating corner camera layout."""
        await compositor.create_corner_camera(
            main_source="ScreenCapture",
            camera_source="Webcam",
            corner="bottom-right",
            camera_size=0.2,
            circular=True,
        )

        # Should add filter for circular mask
        mock_obs.add_filter.assert_called()

    @pytest.mark.asyncio
    async def test_create_documentary_layout(
        self, compositor: OBSCompositor, mock_obs: MagicMock
    ) -> None:
        """Test creating documentary layout."""
        await compositor.create_documentary_layout(
            video_source="Video",
            text_source="TextOverlay",
            video_width_ratio=0.65,
        )

        assert mock_obs.set_source_transform.call_count == 2

    @pytest.mark.asyncio
    async def test_create_interview_layout(
        self, compositor: OBSCompositor, mock_obs: MagicMock
    ) -> None:
        """Test creating interview layout."""
        await compositor.create_interview_layout(
            host_source="HostCam",
            guest_source="GuestCam",
            background_source="Background",
        )

        # Should add three layers (bg + host + guest)
        assert mock_obs.set_source_transform.call_count == 3


# =============================================================================
# COMPOSITE LAYER TESTS
# =============================================================================


class TestCompositeLayer:
    """Tests for CompositeLayer dataclass."""

    def test_default_values(self) -> None:
        """Test default layer values."""
        layer = CompositeLayer(source_name="Test")

        assert layer.source_name == "Test"
        assert layer.position == (0, 0)
        assert layer.scale == (1.0, 1.0)
        assert layer.rotation == 0
        assert layer.opacity == 1.0
        assert layer.blend_mode == LayerBlendMode.NORMAL
        assert layer.visible is True
        assert layer.z_index == 0

    def test_crop_values(self) -> None:
        """Test layer crop values."""
        layer = CompositeLayer(
            source_name="Test",
            crop_left=100,
            crop_right=100,
            crop_top=50,
            crop_bottom=50,
        )

        assert layer.crop_left == 100
        assert layer.crop_right == 100
        assert layer.crop_top == 50
        assert layer.crop_bottom == 50

    def test_blend_modes(self) -> None:
        """Test different blend modes."""
        for mode in LayerBlendMode:
            layer = CompositeLayer(source_name="Test", blend_mode=mode)
            assert layer.blend_mode == mode


# =============================================================================
# LAYER BLEND MODE TESTS
# =============================================================================


class TestLayerBlendMode:
    """Tests for LayerBlendMode enum."""

    def test_blend_mode_values(self) -> None:
        """Test all blend mode values exist."""
        assert LayerBlendMode.NORMAL.value == "normal"
        assert LayerBlendMode.ADDITIVE.value == "additive"
        assert LayerBlendMode.SUBTRACT.value == "subtract"
        assert LayerBlendMode.MULTIPLY.value == "multiply"
        assert LayerBlendMode.SCREEN.value == "screen"
        assert LayerBlendMode.OVERLAY.value == "overlay"


# =============================================================================
# LAYOUT FACTORY FUNCTION TESTS
# =============================================================================


class TestLayoutFactoryFunctions:
    """Tests for layout factory functions."""

    def test_create_pip_layout(self) -> None:
        """Test create_pip_layout factory."""
        layers = create_pip_layout(
            main_source="Main",
            pip_source="PIP",
            pip_corner="bottom-right",
            pip_size=0.25,
        )

        assert len(layers) == 2
        assert layers[0].source_name == "Main"
        assert layers[1].source_name == "PIP"
        assert layers[1].scale == (0.25, 0.25)

    def test_create_pip_layout_corners(self) -> None:
        """Test PIP layout positions for each corner."""
        corners_and_expected = {
            "top-left": (40, 40),  # Margin
            "top-right": (1920 - 480 - 40, 40),  # Width - pip_w - margin
            "bottom-left": (40, 1080 - 270 - 40),  # margin, height - pip_h - margin
            "bottom-right": (1920 - 480 - 40, 1080 - 270 - 40),
        }

        for corner, expected_pos in corners_and_expected.items():
            layers = create_pip_layout(
                main_source="Main",
                pip_source="PIP",
                pip_corner=corner,
                pip_size=0.25,
                pip_margin=40,
            )
            # PIP layer is second
            assert layers[1].position == expected_pos, f"Failed for {corner}"

    def test_create_side_by_side_layout(self) -> None:
        """Test create_side_by_side_layout factory."""
        layers = create_side_by_side_layout(
            left_source="Left",
            right_source="Right",
            split_ratio=0.5,
        )

        assert len(layers) == 2
        assert layers[0].source_name == "Left"
        assert layers[1].source_name == "Right"

    def test_create_corner_cam_layout(self) -> None:
        """Test create_corner_cam_layout factory."""
        layers = create_corner_cam_layout(
            main_source="Main",
            camera_source="Camera",
            corner="bottom-right",
            camera_size=0.2,
        )

        assert len(layers) == 2
        assert layers[1].source_name == "Camera"
        assert layers[1].scale == (0.2, 0.2)


# =============================================================================
# OUTPUT FORMAT VALIDATION TESTS
# =============================================================================


class TestOutputFormatValidation:
    """Tests for output format handling."""

    @pytest.mark.asyncio
    async def test_output_directory_creation(self, tmp_path: Path) -> None:
        """Test that output directory is created if it doesn't exist."""
        nested_output = tmp_path / "deep" / "nested" / "path" / "output.mp4"

        slides = tmp_path / "slides.mp4"
        slides.write_bytes(b"fake")
        audio = tmp_path / "audio.mp3"
        audio.write_bytes(b"fake")

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stderr = ""

        with (
            patch(
                "kagami_studio.production.compositor._run_ffmpeg",
                new_callable=AsyncMock,
                return_value=mock_process,
            ),
            patch(
                "kagami_studio.production.compositor._get_video_duration",
                return_value=5.0,
            ),
        ):
            result = await composite_video(
                slides_video=slides,
                avatar_video=None,
                audio_path=audio,
                output_path=nested_output,
            )

        # Output directory should be created
        assert nested_output.parent.exists()

    @pytest.mark.asyncio
    async def test_string_output_path_conversion(self, tmp_path: Path) -> None:
        """Test that string output path is converted to Path."""
        slides = tmp_path / "slides.mp4"
        slides.write_bytes(b"fake")
        audio = tmp_path / "audio.mp3"
        audio.write_bytes(b"fake")

        output_str = str(tmp_path / "output.mp4")

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stderr = ""

        with (
            patch(
                "kagami_studio.production.compositor._run_ffmpeg",
                new_callable=AsyncMock,
                return_value=mock_process,
            ),
            patch(
                "kagami_studio.production.compositor._get_video_duration",
                return_value=5.0,
            ),
        ):
            result = await composite_video(
                slides_video=slides,
                avatar_video=None,
                audio_path=audio,
                output_path=output_str,  # String path
            )

        assert result.success is True


# =============================================================================
# INTEGRATION-STYLE TESTS
# =============================================================================


class TestCompositingIntegration:
    """Integration-style tests for compositing pipeline."""

    @pytest.mark.asyncio
    async def test_full_composite_pipeline(self, tmp_path: Path) -> None:
        """Test full compositing pipeline with all options."""
        # Create all input files
        slides = tmp_path / "slides.mp4"
        slides.write_bytes(b"slides")

        avatar = tmp_path / "avatar.mp4"
        avatar.write_bytes(b"avatar")

        audio = tmp_path / "audio.mp3"
        audio.write_bytes(b"audio")

        subs = tmp_path / "subs.ass"
        subs.write_text("[Script Info]\n")

        output = tmp_path / "final.mp4"

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stderr = ""

        with (
            patch(
                "kagami_studio.production.compositor._run_ffmpeg",
                new_callable=AsyncMock,
                return_value=mock_process,
            ),
            patch(
                "kagami_studio.production.compositor._get_video_duration",
                return_value=60.0,
            ),
        ):
            result = await composite_video(
                slides_video=slides,
                avatar_video=avatar,
                audio_path=audio,
                subtitle_path=subs,
                output_path=output,
                layout="corner",
                chromakey="green",
                resolution=(1920, 1080),
            )

        assert result.success is True
        assert result.duration_s == 60.0
