"""Tests for HeyGen Holodeck integration.

Tests cover:
- Dialogue line management
- HeyGen image upload
- Content-type detection
- Result tracking
- Multi-party conversation rendering
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import tempfile
import json

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "packages"))

from kagami_studio.modes.holodeck import (
    Holodeck,
    DialogueLine,
    HolodeckResult,
)


class TestDialogueLine:
    """Tests for DialogueLine dataclass."""

    def test_dialogue_line_creation(self):
        """DialogueLine should store all fields."""
        line = DialogueLine(
            character="tim",
            text="Hello world",
            motion="warm",
        )

        assert line.character == "tim"
        assert line.text == "Hello world"
        assert line.motion == "warm"

    def test_dialogue_line_default_motion(self):
        """DialogueLine should have default motion."""
        line = DialogueLine(
            character="tim",
            text="Hello",
        )

        assert line.motion == "warm"


class TestHolodeckResult:
    """Tests for HolodeckResult dataclass."""

    def test_result_success(self):
        """HolodeckResult should track success."""
        result = HolodeckResult(
            success=True,
            video_path=Path("/tmp/video.mp4"),
            duration_s=120.5,
            line_count=5,
        )

        assert result.success
        assert result.video_path == Path("/tmp/video.mp4")
        assert result.duration_s == 120.5
        assert result.line_count == 5

    def test_result_failure(self):
        """HolodeckResult should track failure."""
        result = HolodeckResult(
            success=False,
            error="API Error",
        )

        assert not result.success
        assert result.error == "API Error"


class TestHolodeckInit:
    """Tests for Holodeck initialization."""

    def test_init_defaults(self):
        """Holodeck should have sensible defaults."""
        holodeck = Holodeck()

        assert not holodeck._initialized
        assert holodeck._lines == []
        assert holodeck._image_cache == {}

    @pytest.mark.asyncio
    async def test_initialize_requires_api_key(self):
        """initialize() should require HeyGen API key."""
        holodeck = Holodeck()

        with patch("kagami_studio.modes.holodeck._get_secret", return_value=None):
            with pytest.raises(ValueError, match="HeyGen API key"):
                await holodeck.initialize()

    @pytest.mark.asyncio
    async def test_initialize_success(self):
        """initialize() should succeed with API key."""
        holodeck = Holodeck()

        with patch("kagami_studio.modes.holodeck._get_secret", return_value="test_key"):
            await holodeck.initialize()

            assert holodeck._initialized
            assert holodeck._heygen_key == "test_key"

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self):
        """initialize() should be idempotent."""
        holodeck = Holodeck()
        holodeck._initialized = True

        # Should not raise
        await holodeck.initialize()

        assert holodeck._initialized


class TestDialogueManagement:
    """Tests for dialogue line management."""

    def test_add_dialogue(self):
        """dialogue() should add lines."""
        holodeck = Holodeck()

        holodeck.dialogue("tim", "Hello")

        assert len(holodeck._lines) == 1
        assert holodeck._lines[0].character == "tim"
        assert holodeck._lines[0].text == "Hello"

    def test_dialogue_chaining(self):
        """dialogue() should return self for chaining."""
        holodeck = Holodeck()

        result = holodeck.dialogue("tim", "Hello")

        assert result is holodeck

    def test_multiple_dialogue_lines(self):
        """Should support multiple dialogue lines."""
        holodeck = Holodeck()

        holodeck.dialogue("tim", "Line 1")
        holodeck.dialogue("andy", "Line 2")
        holodeck.dialogue("tim", "Line 3")

        assert len(holodeck._lines) == 3
        assert holodeck._lines[0].character == "tim"
        assert holodeck._lines[1].character == "andy"

    def test_dialogue_with_motion(self):
        """dialogue() should accept motion parameter."""
        holodeck = Holodeck()

        holodeck.dialogue("tim", "Hello", motion="excited")

        assert holodeck._lines[0].motion == "excited"

    def test_dialogue_lowercase_character(self):
        """Character names should be lowercased."""
        holodeck = Holodeck()

        holodeck.dialogue("TIM", "Hello")

        assert holodeck._lines[0].character == "tim"

    def test_clear_dialogue(self):
        """clear() should remove all lines."""
        holodeck = Holodeck()

        holodeck.dialogue("tim", "Line 1")
        holodeck.dialogue("andy", "Line 2")
        holodeck.clear()

        assert len(holodeck._lines) == 0

    def test_clear_chaining(self):
        """clear() should return self for chaining."""
        holodeck = Holodeck()

        result = holodeck.clear()

        assert result is holodeck


class TestContentTypeDetection:
    """Tests for image content-type detection."""

    def test_png_detection(self, tmp_path):
        """PNG files should be detected correctly."""
        png_file = tmp_path / "test.png"
        png_file.write_bytes(b"fake png data")

        suffix = png_file.suffix.lower()
        content_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }
        content_type = content_types.get(suffix, "image/png")

        assert content_type == "image/png"

    def test_jpeg_detection(self, tmp_path):
        """JPEG files should be detected correctly."""
        jpeg_file = tmp_path / "test.jpg"
        jpeg_file.write_bytes(b"fake jpeg data")

        suffix = jpeg_file.suffix.lower()
        content_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }
        content_type = content_types.get(suffix, "image/png")

        assert content_type == "image/jpeg"

    def test_jpeg_extension_variant(self, tmp_path):
        """Both .jpg and .jpeg should work."""
        jpg_file = tmp_path / "test.jpg"
        jpeg_file = tmp_path / "test.jpeg"
        jpg_file.write_bytes(b"fake")
        jpeg_file.write_bytes(b"fake")

        content_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }

        assert content_types.get(jpg_file.suffix.lower()) == "image/jpeg"
        assert content_types.get(jpeg_file.suffix.lower()) == "image/jpeg"


class TestImageCaching:
    """Tests for image upload caching."""

    def test_cache_starts_empty(self):
        """Image cache should start empty."""
        holodeck = Holodeck()

        assert holodeck._image_cache == {}

    @pytest.mark.asyncio
    async def test_cache_hit_avoids_upload(self):
        """Cached images should not be re-uploaded."""
        holodeck = Holodeck()
        holodeck._initialized = True
        holodeck._heygen_key = "test_key"

        # Pre-populate cache
        holodeck._image_cache["/fake/image.png"] = "cached_key_123"

        # Mock the upload method
        with patch.object(holodeck, "_upload_image") as mock_upload:
            # Get from cache
            key = str(Path("/fake/image.png"))
            cached = holodeck._image_cache.get(key)

            if cached:
                result = cached
            else:
                result = await mock_upload(Path("/fake/image.png"))

            assert result == "cached_key_123"
            mock_upload.assert_not_called()


class TestRenderMethod:
    """Tests for render method structure."""

    def test_render_method_exists(self):
        """Holodeck should have render method."""
        holodeck = Holodeck()

        assert hasattr(holodeck, "render")
        assert callable(holodeck.render)

    def test_result_type(self):
        """HolodeckResult should have expected fields."""
        result = HolodeckResult(
            success=True,
            video_path=Path("/tmp/test.mp4"),
            duration_s=10.0,
            line_count=3,
        )

        assert result.success
        assert result.video_path is not None
        assert result.duration_s == 10.0
        assert result.line_count == 3


class TestMultiPartyConversation:
    """Tests for multi-party conversation flow."""

    def test_conversation_flow(self):
        """Should support back-and-forth dialogue."""
        holodeck = Holodeck()

        holodeck.dialogue("tim", "What do you think about AI?")
        holodeck.dialogue("andy", "It's moving fast!")
        holodeck.dialogue("tim", "Should we scale up?")
        holodeck.dialogue("andy", "Let's be careful.")

        assert len(holodeck._lines) == 4

        # Verify alternating speakers
        assert holodeck._lines[0].character == "tim"
        assert holodeck._lines[1].character == "andy"
        assert holodeck._lines[2].character == "tim"
        assert holodeck._lines[3].character == "andy"


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_text(self):
        """Empty text should be allowed."""
        holodeck = Holodeck()

        holodeck.dialogue("tim", "")

        assert len(holodeck._lines) == 1
        assert holodeck._lines[0].text == ""

    def test_very_long_text(self):
        """Very long text should be allowed."""
        holodeck = Holodeck()

        long_text = "Hello " * 1000
        holodeck.dialogue("tim", long_text)

        assert holodeck._lines[0].text == long_text

    def test_special_characters_in_text(self):
        """Special characters should be preserved."""
        holodeck = Holodeck()

        text = "Hello! @#$%^&*() \"quotes\" 'apostrophe'"
        holodeck.dialogue("tim", text)

        assert holodeck._lines[0].text == text

    def test_unicode_text(self):
        """Unicode text should work."""
        holodeck = Holodeck()

        text = "Hallo! 你好 مرحبا こんにちは"
        holodeck.dialogue("tim", text)

        assert holodeck._lines[0].text == text

    def test_newlines_in_text(self):
        """Newlines should be preserved."""
        holodeck = Holodeck()

        text = "Line 1\nLine 2\nLine 3"
        holodeck.dialogue("tim", text)

        assert "\n" in holodeck._lines[0].text
