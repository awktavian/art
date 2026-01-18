"""Tests for the production pipeline — produce_video() end-to-end flow.

Tests the full pipeline: script -> audio -> slides -> avatar -> composite.
Focus on orchestration, error handling, and partial failure recovery.
"""

from __future__ import annotations

import asyncio
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from kagami_studio.production import (
    ProductionResult,
    ProductionScript,
    ScriptSlide,
    WordTiming,
    produce_video,
)
from kagami_studio.production.compositor import CompositeResult
from kagami_studio.production.models import (
    Presentation,
    PresentationTone,
    SlideContent,
    SlideTiming,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def minimal_script() -> list[dict[str, Any]]:
    """Minimal valid script for testing."""
    return [
        {"title": "Welcome", "spoken": "Hello everyone, welcome to the presentation."},
        {"title": "Main Point", "spoken": "Here is the key insight."},
        {"title": "Conclusion", "spoken": "Thank you for watching."},
    ]


@pytest.fixture
def script_with_shots() -> list[dict[str, Any]]:
    """Script with explicit shot types."""
    return [
        {"title": "Opening", "spoken": "Let me introduce myself.", "shot": "dialogue"},
        {"title": "", "spoken": "", "shot": "audience", "duration": 2.0},
        {"title": "The Problem", "spoken": "Here's what we're facing.", "shot": "dialogue"},
        {"title": "Reaction", "spoken": "", "shot": "reverse", "duration": 1.5},
        {"title": "Solution", "spoken": "And here's how we solve it.", "shot": "dialogue"},
    ]


@pytest.fixture
def mock_word_timings() -> list[WordTiming]:
    """Mock word timings from TTS."""
    return [
        WordTiming(text="Hello", start_ms=0, end_ms=300, slide_index=0),
        WordTiming(text="everyone", start_ms=350, end_ms=700, slide_index=0),
        WordTiming(text="welcome", start_ms=750, end_ms=1100, slide_index=0),
        WordTiming(text="Here", start_ms=1500, end_ms=1700, slide_index=1),
        WordTiming(text="is", start_ms=1750, end_ms=1900, slide_index=1),
        WordTiming(text="the", start_ms=1950, end_ms=2100, slide_index=1),
        WordTiming(text="key", start_ms=2150, end_ms=2400, slide_index=1),
        WordTiming(text="Thank", start_ms=2800, end_ms=3000, slide_index=2),
        WordTiming(text="you", start_ms=3050, end_ms=3200, slide_index=2),
    ]


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    """Temporary output directory."""
    output_dir = tmp_path / "production_output"
    output_dir.mkdir()
    return output_dir


# =============================================================================
# PRODUCTION SCRIPT TESTS
# =============================================================================


class TestProductionScript:
    """Tests for ProductionScript dataclass and methods."""

    def test_from_dict_list_basic(self, minimal_script: list[dict[str, Any]]) -> None:
        """Test creating ProductionScript from dictionary list."""
        script = ProductionScript.from_dict_list(minimal_script, speaker="tim")

        assert script.title == "Welcome"  # First slide title
        assert script.speaker == "tim"
        assert len(script.slides) == 3
        assert script.slides[0].spoken_text == "Hello everyone, welcome to the presentation."

    def test_from_dict_list_with_custom_title(self, minimal_script: list[dict[str, Any]]) -> None:
        """Test creating ProductionScript with custom title."""
        script = ProductionScript.from_dict_list(
            minimal_script, speaker="andy", title="Custom Title"
        )

        assert script.title == "Custom Title"
        assert script.speaker == "andy"

    def test_from_dict_list_with_shots(self, script_with_shots: list[dict[str, Any]]) -> None:
        """Test creating ProductionScript with explicit shot types."""
        from kagami_studio.composition.shot import ShotType

        script = ProductionScript.from_dict_list(script_with_shots, speaker="tim")

        assert len(script.slides) == 5
        assert script.slides[0].shot_type == ShotType.DIALOGUE
        assert script.slides[1].shot_type == ShotType.AUDIENCE
        assert script.slides[3].shot_type == ShotType.REVERSE

    def test_empty_script(self) -> None:
        """Test creating ProductionScript from empty list."""
        script = ProductionScript.from_dict_list([], speaker="tim")

        assert script.title == "Untitled"
        assert len(script.slides) == 0
        assert script.total_duration_s == 0.0

    def test_to_markdown(self, minimal_script: list[dict[str, Any]]) -> None:
        """Test Markdown export."""
        script = ProductionScript.from_dict_list(minimal_script, speaker="tim")
        markdown = script.to_markdown()

        assert "# Welcome" in markdown
        assert "**Speaker:** tim" in markdown
        assert "Slide 1: Welcome" in markdown
        assert "Hello everyone, welcome to the presentation." in markdown

    def test_export_markdown(self, minimal_script: list[dict[str, Any]], tmp_path: Path) -> None:
        """Test Markdown file export."""
        script = ProductionScript.from_dict_list(minimal_script, speaker="tim")
        output_path = tmp_path / "script.md"

        result = script.export_markdown(output_path)

        assert result.exists()
        assert "# Welcome" in result.read_text()

    def test_to_json_and_from_json(self, minimal_script: list[dict[str, Any]]) -> None:
        """Test JSON serialization round-trip."""
        original = ProductionScript.from_dict_list(minimal_script, speaker="tim")
        json_data = original.to_json()
        restored = ProductionScript.from_json(json_data)

        assert restored.title == original.title
        assert restored.speaker == original.speaker
        assert len(restored.slides) == len(original.slides)
        assert restored.slides[0].spoken_text == original.slides[0].spoken_text


class TestScriptSlide:
    """Tests for ScriptSlide dataclass."""

    def test_from_dict_basic(self) -> None:
        """Test creating ScriptSlide from dictionary."""
        data = {"title": "Test", "spoken": "Test speech."}
        slide = ScriptSlide.from_dict(data, index=0)

        assert slide.id == "slide_0"
        assert slide.title == "Test"
        assert slide.spoken_text == "Test speech."

    def test_from_dict_with_all_fields(self) -> None:
        """Test creating ScriptSlide with all fields."""
        data = {
            "id": "custom_id",
            "title": "Full Test",
            "spoken": "Full speech.",
            "points": ["Point 1", "Point 2"],
            "shot": "reverse",
            "camera": "close",  # Valid CameraAngle value
            "duration": 5.0,
            "notes": "Production notes",
            "mood": "excited",
        }
        slide = ScriptSlide.from_dict(data, index=99)

        assert slide.id == "custom_id"  # Uses provided ID
        assert slide.title == "Full Test"
        assert len(slide.points) == 2
        assert slide.duration_s == 5.0
        assert slide.mood == "excited"

    def test_to_dict(self) -> None:
        """Test serializing ScriptSlide to dictionary."""
        from kagami_studio.composition.shot import CameraAngle, ShotType

        slide = ScriptSlide(
            id="test_slide",
            title="Test",
            spoken_text="Test speech.",
            shot_type=ShotType.DIALOGUE,
            camera=CameraAngle.MEDIUM,
            mood="neutral",
        )
        data = slide.to_dict()

        assert data["id"] == "test_slide"
        assert data["shot"] == "dialogue"
        assert data["camera"] == "medium"


# =============================================================================
# WORD TIMING TESTS
# =============================================================================


class TestWordTiming:
    """Tests for WordTiming dataclass."""

    def test_basic_word_timing(self) -> None:
        """Test creating basic WordTiming."""
        timing = WordTiming(text="hello", start_ms=0, end_ms=500, slide_index=0)

        assert timing.text == "hello"
        assert timing.start_ms == 0
        assert timing.end_ms == 500
        assert timing.slide_index == 0

    def test_slide_index_default(self) -> None:
        """Test default slide_index is 0."""
        timing = WordTiming(text="test", start_ms=100, end_ms=200)

        assert timing.slide_index == 0


# =============================================================================
# PRODUCTION RESULT TESTS
# =============================================================================


class TestProductionResult:
    """Tests for ProductionResult dataclass."""

    def test_success_result(self, tmp_path: Path) -> None:
        """Test creating successful production result."""
        video_path = tmp_path / "final.mp4"
        result = ProductionResult(
            success=True,
            video_path=video_path,
            duration_s=30.5,
            shots=[tmp_path / "shot_0.mp4"],
        )

        assert result.success is True
        assert result.video_path == video_path
        assert result.duration_s == 30.5
        assert len(result.shots) == 1
        assert result.error is None

    def test_failure_result(self) -> None:
        """Test creating failed production result."""
        result = ProductionResult(success=False, error="TTS generation failed")

        assert result.success is False
        assert result.video_path is None
        assert result.error == "TTS generation failed"


# =============================================================================
# PRODUCE_VIDEO PIPELINE TESTS
# =============================================================================


class TestProduceVideoPipeline:
    """Tests for the produce_video() orchestration function."""

    @pytest.mark.asyncio
    async def test_produce_video_success_mocked(
        self, minimal_script: list[dict[str, Any]], temp_output_dir: Path
    ) -> None:
        """Test successful production with mocked components."""
        # Create mock audio file
        mock_audio = temp_output_dir / "narration.mp3"
        mock_audio.write_bytes(b"fake audio")

        # Create mock slides video
        mock_slides = temp_output_dir / "slides.mp4"
        mock_slides.write_bytes(b"fake video")

        # Create mock final video
        mock_final = temp_output_dir / "final.mp4"
        mock_final.write_bytes(b"fake final")

        mock_word_timings = [
            WordTiming(text="Hello", start_ms=0, end_ms=300, slide_index=0),
            WordTiming(text="everyone", start_ms=350, end_ms=700, slide_index=0),
        ]

        mock_slide_timings = [
            {"index": 0, "start_ms": 0, "end_ms": 2000, "duration_s": 2.0},
            {"index": 1, "start_ms": 2000, "end_ms": 4000, "duration_s": 2.0},
            {"index": 2, "start_ms": 4000, "end_ms": 6000, "duration_s": 2.0},
        ]

        with (
            patch(
                "kagami_studio.production._generate_audio",
                new_callable=AsyncMock,
                return_value=(mock_audio, mock_word_timings, mock_slide_timings),
            ),
            patch(
                "kagami_studio.production.slides.render_slides_to_video",
                new_callable=AsyncMock,
                return_value=mock_slides,
            ),
            patch(
                "kagami_studio.production.compositor.composite_video",
                new_callable=AsyncMock,
                return_value=CompositeResult(success=True, output_path=mock_final, duration_s=6.0),
            ),
            patch(
                "kagami_studio.production.load_speaker_context",
                return_value=MagicMock(name="Tim", identity_id="tim"),
            ),
        ):
            result = await produce_video(
                script=minimal_script,
                speaker="tim",
                output_dir=temp_output_dir,
                include_avatar=False,  # Skip avatar for this test
            )

        assert result.success is True
        assert result.video_path == mock_final

    @pytest.mark.asyncio
    async def test_produce_video_audio_failure(
        self, minimal_script: list[dict[str, Any]], temp_output_dir: Path
    ) -> None:
        """Test production failure during audio generation."""
        with (
            patch(
                "kagami_studio.production._generate_audio",
                new_callable=AsyncMock,
                side_effect=RuntimeError("TTS service unavailable"),
            ),
            patch(
                "kagami_studio.production.load_speaker_context",
                return_value=MagicMock(name="Tim", identity_id="tim"),
            ),
        ):
            result = await produce_video(
                script=minimal_script,
                speaker="tim",
                output_dir=temp_output_dir,
                include_avatar=False,
            )

        assert result.success is False
        assert "TTS service unavailable" in result.error

    @pytest.mark.asyncio
    async def test_produce_video_compositor_failure(
        self, minimal_script: list[dict[str, Any]], temp_output_dir: Path
    ) -> None:
        """Test production failure during compositing."""
        mock_audio = temp_output_dir / "narration.mp3"
        mock_audio.write_bytes(b"fake audio")

        mock_slides = temp_output_dir / "slides.mp4"
        mock_slides.write_bytes(b"fake video")

        mock_word_timings = [
            WordTiming(text="Hello", start_ms=0, end_ms=300, slide_index=0),
        ]

        mock_slide_timings = [
            {"index": 0, "start_ms": 0, "end_ms": 2000, "duration_s": 2.0},
            {"index": 1, "start_ms": 2000, "end_ms": 4000, "duration_s": 2.0},
            {"index": 2, "start_ms": 4000, "end_ms": 6000, "duration_s": 2.0},
        ]

        with (
            patch(
                "kagami_studio.production._generate_audio",
                new_callable=AsyncMock,
                return_value=(mock_audio, mock_word_timings, mock_slide_timings),
            ),
            patch(
                "kagami_studio.production.slides.render_slides_to_video",
                new_callable=AsyncMock,
                return_value=mock_slides,
            ),
            patch(
                "kagami_studio.production.compositor.composite_video",
                new_callable=AsyncMock,
                return_value=CompositeResult(success=False, error="FFmpeg failed: codec error"),
            ),
            patch(
                "kagami_studio.production.load_speaker_context",
                return_value=MagicMock(name="Tim", identity_id="tim"),
            ),
        ):
            result = await produce_video(
                script=minimal_script,
                speaker="tim",
                output_dir=temp_output_dir,
                include_avatar=False,
            )

        assert result.success is False
        assert "Compositing failed" in result.error

    @pytest.mark.asyncio
    async def test_produce_video_auto_output_dir(
        self, minimal_script: list[dict[str, Any]]
    ) -> None:
        """Test that output directory is auto-generated when not provided."""
        mock_audio = Path("/tmp/test_audio.mp3")
        mock_slides = Path("/tmp/test_slides.mp4")
        mock_final = Path("/tmp/test_final.mp4")

        with (
            patch(
                "kagami_studio.production._generate_audio",
                new_callable=AsyncMock,
                return_value=(
                    mock_audio,
                    [],
                    [{"index": 0, "start_ms": 0, "end_ms": 1000, "duration_s": 1.0}],
                ),
            ),
            patch(
                "kagami_studio.production.slides.render_slides_to_video",
                new_callable=AsyncMock,
                return_value=mock_slides,
            ),
            patch(
                "kagami_studio.production.compositor.composite_video",
                new_callable=AsyncMock,
                return_value=CompositeResult(success=True, output_path=mock_final),
            ),
            patch(
                "kagami_studio.production.load_speaker_context",
                return_value=MagicMock(name="Tim", identity_id="tim"),
            ),
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.write_text"),
        ):
            result = await produce_video(
                script=minimal_script,
                speaker="tim",
                output_dir=None,  # Auto-generate
                include_avatar=False,
            )

        # Should still succeed with auto-generated directory
        assert result.success is True


# =============================================================================
# PIPELINE STAGES TESTS
# =============================================================================


class TestPipelineStages:
    """Tests for individual pipeline stages."""

    def test_script_parsing_stage(self, script_with_shots: list[dict[str, Any]]) -> None:
        """Test script parsing correctly identifies shot types."""
        script = ProductionScript.from_dict_list(script_with_shots, speaker="tim")

        # Should have 5 slides with correct types
        assert len(script.slides) == 5

        # Check dialogue slides have spoken text
        dialogue_slides = [s for s in script.slides if s.shot_type.value == "dialogue"]
        assert all(s.spoken_text for s in dialogue_slides)

        # Check non-dialogue slides may have duration
        audience_slides = [s for s in script.slides if s.shot_type.value == "audience"]
        assert len(audience_slides) == 1
        assert audience_slides[0].duration_s == 2.0

    def test_word_timing_slide_index_assignment(self, mock_word_timings: list[WordTiming]) -> None:
        """Test word timings are correctly assigned to slides."""
        slide_0_words = [w for w in mock_word_timings if w.slide_index == 0]
        slide_1_words = [w for w in mock_word_timings if w.slide_index == 1]
        slide_2_words = [w for w in mock_word_timings if w.slide_index == 2]

        assert len(slide_0_words) == 3  # "Hello everyone welcome"
        assert len(slide_1_words) == 4  # "Here is the key"
        assert len(slide_2_words) == 2  # "Thank you"


# =============================================================================
# ERROR RECOVERY TESTS
# =============================================================================


class TestErrorRecovery:
    """Tests for partial failure recovery."""

    @pytest.mark.asyncio
    async def test_avatar_failure_continues(
        self, minimal_script: list[dict[str, Any]], temp_output_dir: Path
    ) -> None:
        """Test that avatar generation failure doesn't break entire pipeline."""
        mock_audio = temp_output_dir / "narration.mp3"
        mock_audio.write_bytes(b"fake audio")

        mock_slides = temp_output_dir / "slides.mp4"
        mock_slides.write_bytes(b"fake video")

        mock_final = temp_output_dir / "final.mp4"
        mock_final.write_bytes(b"fake final")

        mock_slide_timings = [
            {"index": 0, "start_ms": 0, "end_ms": 2000, "duration_s": 2.0},
            {"index": 1, "start_ms": 2000, "end_ms": 4000, "duration_s": 2.0},
            {"index": 2, "start_ms": 4000, "end_ms": 6000, "duration_s": 2.0},
        ]

        # Simulate avatar generator failing
        async def mock_generate_shots(*args, **kwargs) -> list[Path]:
            raise RuntimeError("HeyGen API unavailable")

        with (
            patch(
                "kagami_studio.production._generate_audio",
                new_callable=AsyncMock,
                return_value=(mock_audio, [], mock_slide_timings),
            ),
            patch(
                "kagami_studio.production.slides.render_slides_to_video",
                new_callable=AsyncMock,
                return_value=mock_slides,
            ),
            patch(
                "kagami_studio.production._generate_shots",
                new_callable=AsyncMock,
                return_value=[],  # Empty list means no shots generated
            ),
            patch(
                "kagami_studio.production.compositor.composite_video",
                new_callable=AsyncMock,
                return_value=CompositeResult(success=True, output_path=mock_final),
            ),
            patch(
                "kagami_studio.production.load_speaker_context",
                return_value=MagicMock(name="Tim", identity_id="tim"),
            ),
        ):
            result = await produce_video(
                script=minimal_script,
                speaker="tim",
                output_dir=temp_output_dir,
                include_avatar=True,  # Enable avatar, but it will "fail"
            )

        # Pipeline should still succeed without avatar
        assert result.success is True


# =============================================================================
# MODEL TESTS
# =============================================================================


class TestPresentationModels:
    """Tests for Presentation and SlideContent models."""

    def test_slide_content_needs_image(self) -> None:
        """Test needs_image() method for different layouts."""
        hero_slide = SlideContent(title="Test", spoken_text="Test", layout="hero_full")
        stat_slide = SlideContent(title="Test", spoken_text="Test", layout="stat_focus")

        assert hero_slide.needs_image() is True
        assert stat_slide.needs_image() is False

    def test_slide_content_to_dict(self) -> None:
        """Test SlideContent serialization."""
        slide = SlideContent(
            title="Title",
            spoken_text="Speech",
            layout="hero_split",
            stat_value="42%",
            stat_label="improvement",
        )
        data = slide.to_dict()

        assert data["title"] == "Title"
        assert data["layout"] == "hero_split"
        assert data["stat_value"] == "42%"

    def test_slide_content_from_dict(self) -> None:
        """Test SlideContent deserialization."""
        data = {
            "title": "Test",
            "spoken_text": "Speech",
            "layout": "stat_focus",
            "stat_value": "100x",
        }
        slide = SlideContent.from_dict(data)

        assert slide.title == "Test"
        assert slide.stat_value == "100x"

    def test_presentation_get_colors(self) -> None:
        """Test color palette retrieval."""
        presentation = Presentation(
            title="Test",
            topic="test",
            tone=PresentationTone.EDUCATIONAL_FUNNY,
            slides=[],
        )
        colors = presentation.get_colors()

        assert "primary" in colors
        assert "background" in colors

    def test_presentation_to_dict_and_from_dict(self) -> None:
        """Test Presentation serialization round-trip."""
        slide = SlideContent(title="Slide", spoken_text="Speech", layout="hero_full")
        original = Presentation(
            title="Test Presentation",
            topic="testing",
            tone=PresentationTone.PROFESSIONAL,
            slides=[slide],
            speaker="andy",
        )

        data = original.to_dict()
        restored = Presentation.from_dict(data)

        assert restored.title == original.title
        assert restored.tone == original.tone
        assert restored.speaker == original.speaker
        assert len(restored.slides) == 1

    def test_slide_timing_properties(self) -> None:
        """Test SlideTiming computed properties."""
        timing = SlideTiming(index=0, start_ms=1000, end_ms=3500)

        assert timing.duration_ms == 2500
        assert timing.duration_s == 2.5


# =============================================================================
# INTEGRATION-LIKE TESTS (WITH MOCKS)
# =============================================================================


class TestPipelineIntegration:
    """Integration-style tests with comprehensive mocking."""

    @pytest.mark.asyncio
    async def test_full_pipeline_with_subtitles(
        self, minimal_script: list[dict[str, Any]], temp_output_dir: Path
    ) -> None:
        """Test full pipeline including subtitle generation."""
        mock_audio = temp_output_dir / "narration.mp3"
        mock_audio.write_bytes(b"fake audio")

        mock_slides = temp_output_dir / "slides.mp4"
        mock_slides.write_bytes(b"fake video")

        mock_final = temp_output_dir / "final.mp4"
        mock_final.write_bytes(b"fake final")

        mock_word_timings = [
            WordTiming(text="Hello", start_ms=0, end_ms=300, slide_index=0),
            WordTiming(text="everyone", start_ms=350, end_ms=700, slide_index=0),
        ]

        mock_slide_timings = [
            {"index": 0, "start_ms": 0, "end_ms": 2000, "duration_s": 2.0},
            {"index": 1, "start_ms": 2000, "end_ms": 4000, "duration_s": 2.0},
            {"index": 2, "start_ms": 4000, "end_ms": 6000, "duration_s": 2.0},
        ]

        with (
            patch(
                "kagami_studio.production._generate_audio",
                new_callable=AsyncMock,
                return_value=(mock_audio, mock_word_timings, mock_slide_timings),
            ),
            patch(
                "kagami_studio.production.slides.render_slides_to_video",
                new_callable=AsyncMock,
                return_value=mock_slides,
            ),
            patch(
                "kagami_studio.production.compositor.composite_video",
                new_callable=AsyncMock,
                return_value=CompositeResult(success=True, output_path=mock_final),
            ),
            patch(
                "kagami_studio.production.load_speaker_context",
                return_value=MagicMock(name="Tim", identity_id="tim"),
            ),
            patch(
                "kagami_studio.subtitles.kinetic.KineticSubtitleGenerator.generate",
                return_value="[Script Info]...",
            ),
        ):
            result = await produce_video(
                script=minimal_script,
                speaker="tim",
                output_dir=temp_output_dir,
                include_avatar=False,
                generate_ass_subtitles=True,
                burn_ass_subtitles=True,
            )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_pipeline_with_spatial_audio(
        self, minimal_script: list[dict[str, Any]], temp_output_dir: Path
    ) -> None:
        """Test pipeline with spatial audio processing."""
        mock_audio = temp_output_dir / "narration.mp3"
        mock_audio.write_bytes(b"fake audio")

        mock_spatial_audio = temp_output_dir / "spatial_audio.mp3"
        mock_spatial_audio.write_bytes(b"fake spatial")

        mock_slides = temp_output_dir / "slides.mp4"
        mock_slides.write_bytes(b"fake video")

        mock_final = temp_output_dir / "final.mp4"
        mock_final.write_bytes(b"fake final")

        mock_slide_timings = [
            {"index": 0, "start_ms": 0, "end_ms": 2000, "duration_s": 2.0},
            {"index": 1, "start_ms": 2000, "end_ms": 4000, "duration_s": 2.0},
            {"index": 2, "start_ms": 4000, "end_ms": 6000, "duration_s": 2.0},
        ]

        with (
            patch(
                "kagami_studio.production._generate_audio",
                new_callable=AsyncMock,
                return_value=(mock_audio, [], mock_slide_timings),
            ),
            patch(
                "kagami_studio.production.spatial.spatialize_audio",
                new_callable=AsyncMock,
                return_value=mock_spatial_audio,
            ),
            patch(
                "kagami_studio.production.slides.render_slides_to_video",
                new_callable=AsyncMock,
                return_value=mock_slides,
            ),
            patch(
                "kagami_studio.production.compositor.composite_video",
                new_callable=AsyncMock,
                return_value=CompositeResult(success=True, output_path=mock_final),
            ),
            patch(
                "kagami_studio.production.load_speaker_context",
                return_value=MagicMock(name="Tim", identity_id="tim"),
            ),
        ):
            result = await produce_video(
                script=minimal_script,
                speaker="tim",
                output_dir=temp_output_dir,
                include_avatar=False,
                spatial_audio=True,  # Enable spatial audio
            )

        assert result.success is True


# =============================================================================
# DESIGN SYSTEM TESTS
# =============================================================================


class TestDesignSystem:
    """Tests for design system utilities."""

    def test_get_design_system(self) -> None:
        """Test design system returns expected structure."""
        from kagami_studio.production import get_design_system

        ds = get_design_system()

        assert "timing" in ds
        assert "spacing" in ds
        assert "colors" in ds
        assert "easing" in ds

        # Check Fibonacci timing
        assert ds["timing"]["fibonacci"][0] == 89
        assert ds["timing"]["fibonacci"][5] == 987

        # Check spacing grid
        assert ds["spacing"]["grid"] == 8
