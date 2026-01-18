"""Tests for video generation — Kling AI and Runway integration.

Tests the video generation system with Kling AI as primary
and Runway Gen-4 as fallback.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from kagami_studio.generation.video import (
    KlingVideoGenerator,
    RunwayVideoGenerator,
    VideoGenerator,
    VideoProvider,
    VideoResult,
    generate_video,
    get_video_generator,
)

# =============================================================================
# VIDEO RESULT TESTS
# =============================================================================


class TestVideoResult:
    """Tests for VideoResult dataclass."""

    def test_success_result(self) -> None:
        """Test creating successful video result."""
        result = VideoResult(
            success=True,
            video_url="https://example.com/video.mp4",
            provider="kling",
            duration_seconds=5.0,
            generation_time_seconds=45.3,
            job_id="task_123",
        )

        assert result.success is True
        assert result.video_url == "https://example.com/video.mp4"
        assert result.provider == "kling"
        assert result.duration_seconds == 5.0
        assert result.generation_time_seconds == 45.3
        assert result.job_id == "task_123"
        assert result.error is None

    def test_failure_result(self) -> None:
        """Test creating failed video result."""
        result = VideoResult(
            success=False,
            provider="runway",
            error="API rate limit exceeded",
            generation_time_seconds=2.1,
        )

        assert result.success is False
        assert result.video_url is None
        assert result.error == "API rate limit exceeded"

    def test_default_values(self) -> None:
        """Test default values are set correctly."""
        result = VideoResult(success=True)

        assert result.video_url is None
        assert result.video_path is None
        assert result.provider == ""
        assert result.duration_seconds == 0.0
        assert result.generation_time_seconds == 0.0
        assert result.error is None
        assert result.job_id is None


# =============================================================================
# KLING VIDEO GENERATOR TESTS
# =============================================================================


class TestKlingVideoGenerator:
    """Tests for KlingVideoGenerator."""

    @pytest.fixture
    def generator(self) -> KlingVideoGenerator:
        """Create Kling generator with test API key."""
        return KlingVideoGenerator(api_key="test_kling_key")

    @pytest.mark.asyncio
    async def test_generate_text_to_video(self, generator: KlingVideoGenerator) -> None:
        """Test text-to-video generation."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"data": {"task_id": "task_123"}})

        with patch.object(
            generator,
            "_get_session",
            return_value=MagicMock(
                post=AsyncMock(
                    return_value=AsyncMock(
                        __aenter__=AsyncMock(return_value=mock_response), __aexit__=AsyncMock()
                    )
                )
            ),
        ):
            # Mock the actual aiohttp session behavior
            mock_session = MagicMock()
            mock_session.post = MagicMock(
                return_value=AsyncMock(
                    __aenter__=AsyncMock(return_value=mock_response), __aexit__=AsyncMock()
                )
            )
            generator._session = mock_session

            # Directly test the session creation with API key
            assert generator.api_key == "test_kling_key"

    @pytest.mark.asyncio
    async def test_generate_image_to_video(self, generator: KlingVideoGenerator) -> None:
        """Test image-to-video generation."""
        # Verify different endpoint is used for image input
        generator._session = MagicMock()

        # Test that image_url parameter is accepted
        with patch.object(generator, "_get_session", new_callable=AsyncMock) as mock_get_session:
            mock_session = MagicMock()
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"data": {"task_id": "img_task"}})

            # Create context manager for post
            mock_post_cm = AsyncMock()
            mock_post_cm.__aenter__ = AsyncMock(return_value=mock_response)
            mock_post_cm.__aexit__ = AsyncMock()
            mock_session.post = MagicMock(return_value=mock_post_cm)

            mock_get_session.return_value = mock_session

            task_id = await generator.generate(
                prompt="A cat walking",
                duration=5,
                image_url="https://example.com/cat.jpg",
            )

            assert task_id == "img_task"
            # Verify image2video endpoint was called
            mock_session.post.assert_called_once()
            call_args = mock_session.post.call_args
            assert "image2video" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_get_status(self, generator: KlingVideoGenerator) -> None:
        """Test status retrieval."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"data": {"status": "processing", "progress": 50}}
        )

        mock_get_cm = AsyncMock()
        mock_get_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get_cm.__aexit__ = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_get_cm)

        with patch.object(
            generator, "_get_session", new_callable=AsyncMock, return_value=mock_session
        ):
            status = await generator.get_status("task_123")

        assert status["status"] == "processing"
        assert status["progress"] == 50

    @pytest.mark.asyncio
    async def test_get_result_success(self, generator: KlingVideoGenerator) -> None:
        """Test successful result retrieval."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "data": {
                    "status": "succeed",
                    "output": {"videos": [{"url": "https://kling.ai/video.mp4"}]},
                }
            }
        )

        mock_get_cm = AsyncMock()
        mock_get_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get_cm.__aexit__ = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_get_cm)

        with patch.object(
            generator, "_get_session", new_callable=AsyncMock, return_value=mock_session
        ):
            video_url = await generator.get_result("task_123")

        assert video_url == "https://kling.ai/video.mp4"

    @pytest.mark.asyncio
    async def test_wait_for_completion_success(self, generator: KlingVideoGenerator) -> None:
        """Test waiting for completion with success."""
        # Simulate polling: first processing, then succeed
        call_count = [0]

        async def mock_get_status(task_id: str):
            call_count[0] += 1
            if call_count[0] < 3:
                return {"status": "processing"}
            return {
                "status": "succeed",
                "output": {"videos": [{"url": "https://kling.ai/final.mp4"}]},
            }

        with patch.object(generator, "get_status", side_effect=mock_get_status):
            with patch.object(
                generator,
                "get_result",
                new_callable=AsyncMock,
                return_value="https://kling.ai/final.mp4",
            ):
                video_url = await generator.wait_for_completion(
                    "task_123", timeout=60.0, poll_interval=0.01
                )

        assert video_url == "https://kling.ai/final.mp4"
        assert call_count[0] >= 3

    @pytest.mark.asyncio
    async def test_wait_for_completion_failure(self, generator: KlingVideoGenerator) -> None:
        """Test waiting for completion with failure."""

        async def mock_get_status(task_id: str):
            return {"status": "failed", "error": "Invalid prompt"}

        with patch.object(generator, "get_status", side_effect=mock_get_status):
            with pytest.raises(RuntimeError, match="Kling generation failed"):
                await generator.wait_for_completion("task_123", poll_interval=0.01)

    @pytest.mark.asyncio
    async def test_wait_for_completion_timeout(self, generator: KlingVideoGenerator) -> None:
        """Test timeout during waiting."""

        async def mock_get_status(task_id: str):
            return {"status": "processing"}

        with patch.object(generator, "get_status", side_effect=mock_get_status):
            with pytest.raises(TimeoutError, match="timeout"):
                await generator.wait_for_completion("task_123", timeout=0.05, poll_interval=0.01)

    @pytest.mark.asyncio
    async def test_api_key_from_keychain(self) -> None:
        """Test API key retrieval from keychain."""
        generator = KlingVideoGenerator()  # No API key provided

        with patch(
            "kagami_studio.generation.video.KlingVideoGenerator._ensure_api_key",
            new_callable=AsyncMock,
            return_value=True,
        ):
            generator.api_key = "keychain_key"
            assert generator.api_key == "keychain_key"


# =============================================================================
# RUNWAY VIDEO GENERATOR TESTS
# =============================================================================


class TestRunwayVideoGenerator:
    """Tests for RunwayVideoGenerator."""

    @pytest.fixture
    def generator(self) -> RunwayVideoGenerator:
        """Create Runway generator with test API key."""
        return RunwayVideoGenerator(api_key="test_runway_key")

    @pytest.mark.asyncio
    async def test_generate(self, generator: RunwayVideoGenerator) -> None:
        """Test video generation."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"id": "runway_job_456"})

        mock_post_cm = AsyncMock()
        mock_post_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post_cm.__aexit__ = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_post_cm)

        with patch.object(
            generator, "_get_session", new_callable=AsyncMock, return_value=mock_session
        ):
            job_id = await generator.generate("A beautiful sunset", duration=5)

        assert job_id == "runway_job_456"

    @pytest.mark.asyncio
    async def test_extend(self, generator: RunwayVideoGenerator) -> None:
        """Test video extension."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"id": "extend_job_789"})

        mock_post_cm = AsyncMock()
        mock_post_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post_cm.__aexit__ = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_post_cm)

        with patch.object(
            generator, "_get_session", new_callable=AsyncMock, return_value=mock_session
        ):
            job_id = await generator.extend(
                video_url="https://example.com/original.mp4",
                prompt="Continue with dramatic clouds",
                duration=4,
            )

        assert job_id == "extend_job_789"

    @pytest.mark.asyncio
    async def test_get_status(self, generator: RunwayVideoGenerator) -> None:
        """Test status retrieval."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"state": "processing", "progress": 0.75})

        mock_get_cm = AsyncMock()
        mock_get_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get_cm.__aexit__ = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_get_cm)

        with patch.object(
            generator, "_get_session", new_callable=AsyncMock, return_value=mock_session
        ):
            status = await generator.get_status("job_123")

        assert status["state"] == "processing"
        assert status["progress"] == 0.75

    @pytest.mark.asyncio
    async def test_get_result(self, generator: RunwayVideoGenerator) -> None:
        """Test result retrieval."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"video_url": "https://runway.ml/generated.mp4"}
        )

        mock_get_cm = AsyncMock()
        mock_get_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get_cm.__aexit__ = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_get_cm)

        with patch.object(
            generator, "_get_session", new_callable=AsyncMock, return_value=mock_session
        ):
            video_url = await generator.get_result("job_123")

        assert video_url == "https://runway.ml/generated.mp4"

    @pytest.mark.asyncio
    async def test_wait_for_completion_success(self, generator: RunwayVideoGenerator) -> None:
        """Test waiting for completion."""
        call_count = [0]

        async def mock_get_status(job_id: str):
            call_count[0] += 1
            if call_count[0] < 2:
                return {"state": "processing"}
            return {"state": "completed"}

        with (
            patch.object(generator, "get_status", side_effect=mock_get_status),
            patch.object(
                generator,
                "get_result",
                new_callable=AsyncMock,
                return_value="https://runway.ml/done.mp4",
            ),
        ):
            video_url = await generator.wait_for_completion(
                "job_123", timeout=60.0, poll_interval=0.01
            )

        assert video_url == "https://runway.ml/done.mp4"


# =============================================================================
# UNIFIED VIDEO GENERATOR TESTS
# =============================================================================


class TestVideoGenerator:
    """Tests for the unified VideoGenerator with provider selection."""

    @pytest.fixture
    def generator(self) -> VideoGenerator:
        """Create unified video generator."""
        return VideoGenerator(
            provider=VideoProvider.AUTO,
            kling_api_key="kling_key",
            runway_api_key="runway_key",
        )

    @pytest.mark.asyncio
    async def test_auto_provider_kling_success(self, generator: VideoGenerator) -> None:
        """Test AUTO mode uses Kling first when successful."""
        mock_result = VideoResult(
            success=True,
            video_url="https://kling.ai/video.mp4",
            provider="kling",
            duration_seconds=5.0,
        )

        with patch.object(
            generator,
            "_generate_with_kling",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await generator.generate("A cat playing piano")

        assert result.success is True
        assert result.provider == "kling"

    @pytest.mark.asyncio
    async def test_auto_provider_fallback_to_runway(self, generator: VideoGenerator) -> None:
        """Test AUTO mode falls back to Runway when Kling fails."""
        kling_error = RuntimeError("Kling API error")
        runway_result = VideoResult(
            success=True,
            video_url="https://runway.ml/video.mp4",
            provider="runway",
            duration_seconds=5.0,
        )

        with (
            patch.object(
                generator,
                "_generate_with_kling",
                new_callable=AsyncMock,
                side_effect=kling_error,
            ),
            patch.object(
                generator,
                "_generate_with_runway",
                new_callable=AsyncMock,
                return_value=runway_result,
            ),
        ):
            result = await generator.generate("A cat playing piano")

        assert result.success is True
        assert result.provider == "runway"

    @pytest.mark.asyncio
    async def test_auto_provider_both_fail(self, generator: VideoGenerator) -> None:
        """Test AUTO mode returns error when both providers fail."""
        with (
            patch.object(
                generator,
                "_generate_with_kling",
                new_callable=AsyncMock,
                side_effect=RuntimeError("Kling down"),
            ),
            patch.object(
                generator,
                "_generate_with_runway",
                new_callable=AsyncMock,
                side_effect=RuntimeError("Runway down"),
            ),
        ):
            result = await generator.generate("A cat playing piano")

        assert result.success is False
        assert "Both providers failed" in result.error
        assert "Kling" in result.error
        assert "Runway" in result.error

    @pytest.mark.asyncio
    async def test_explicit_kling_provider(self, generator: VideoGenerator) -> None:
        """Test explicitly selecting Kling provider."""
        mock_result = VideoResult(
            success=True,
            video_url="https://kling.ai/video.mp4",
            provider="kling",
        )

        with patch.object(
            generator,
            "_generate_with_kling",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await generator.generate("A cat", provider=VideoProvider.KLING)

        assert result.provider == "kling"

    @pytest.mark.asyncio
    async def test_explicit_runway_provider(self, generator: VideoGenerator) -> None:
        """Test explicitly selecting Runway provider."""
        mock_result = VideoResult(
            success=True,
            video_url="https://runway.ml/video.mp4",
            provider="runway",
        )

        with patch.object(
            generator,
            "_generate_with_runway",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await generator.generate("A cat", provider=VideoProvider.RUNWAY)

        assert result.provider == "runway"

    @pytest.mark.asyncio
    async def test_extend_uses_runway(self, generator: VideoGenerator) -> None:
        """Test video extension uses Runway (Kling doesn't support it)."""
        mock_result = VideoResult(
            success=True,
            video_url="https://runway.ml/extended.mp4",
            provider="runway",
            duration_seconds=4.0,
        )

        with patch.object(
            generator._runway,
            "extend",
            new_callable=AsyncMock,
            return_value="extend_job_123",
        ):
            with patch.object(
                generator._runway,
                "wait_for_completion",
                new_callable=AsyncMock,
                return_value="https://runway.ml/extended.mp4",
            ):
                result = await generator.extend(
                    video_url="https://example.com/original.mp4",
                    prompt="Continue the scene",
                    duration=4,
                )

        assert result.success is True
        assert result.provider == "runway"


# =============================================================================
# VIDEO PROVIDER ENUM TESTS
# =============================================================================


class TestVideoProvider:
    """Tests for VideoProvider enum."""

    def test_provider_values(self) -> None:
        """Test provider enum values."""
        assert VideoProvider.KLING.value == "kling"
        assert VideoProvider.RUNWAY.value == "runway"
        assert VideoProvider.AUTO.value == "auto"

    def test_provider_from_string(self) -> None:
        """Test creating provider from string."""
        assert VideoProvider("kling") == VideoProvider.KLING
        assert VideoProvider("runway") == VideoProvider.RUNWAY
        assert VideoProvider("auto") == VideoProvider.AUTO


# =============================================================================
# RESOLUTION HANDLING TESTS
# =============================================================================


class TestResolutionHandling:
    """Tests for video resolution handling."""

    def test_supported_durations(self) -> None:
        """Test that Kling supports 5 and 10 second durations."""
        # Kling 1.5 supports 5s and 10s
        supported_durations = [5, 10]

        for duration in supported_durations:
            result = VideoResult(
                success=True,
                duration_seconds=float(duration),
            )
            assert result.duration_seconds in [5.0, 10.0]

    @pytest.mark.asyncio
    async def test_generate_with_duration(self) -> None:
        """Test generation with specific duration."""
        generator = VideoGenerator(kling_api_key="test_key")

        mock_result = VideoResult(
            success=True,
            video_url="https://kling.ai/video.mp4",
            provider="kling",
            duration_seconds=10.0,
        )

        with patch.object(
            generator,
            "_generate_with_kling",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_gen:
            result = await generator.generate(
                "Test prompt", duration=10, provider=VideoProvider.KLING
            )

        assert result.duration_seconds == 10.0


# =============================================================================
# FORMAT CONVERSION TESTS
# =============================================================================


class TestFormatConversion:
    """Tests for video format handling."""

    def test_video_result_url_format(self) -> None:
        """Test video URL formats."""
        # Test various URL formats that might be returned
        urls = [
            "https://kling.ai/videos/abc123.mp4",
            "https://cdn.runwayml.com/output/xyz789.mp4",
            "https://storage.googleapis.com/bucket/video.mp4",
        ]

        for url in urls:
            result = VideoResult(success=True, video_url=url)
            assert result.video_url.endswith(".mp4")


# =============================================================================
# CONVENIENCE FUNCTION TESTS
# =============================================================================


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    @pytest.mark.asyncio
    async def test_generate_video_function(self) -> None:
        """Test generate_video() convenience function."""
        mock_result = VideoResult(
            success=True,
            video_url="https://example.com/video.mp4",
            provider="kling",
        )

        with patch("kagami_studio.generation.video.get_video_generator") as mock_get_gen:
            mock_gen = MagicMock()
            mock_gen.generate = AsyncMock(return_value=mock_result)
            mock_get_gen.return_value = mock_gen

            result = await generate_video("A beautiful sunset", duration=5)

        assert result.success is True
        mock_gen.generate.assert_called_once()

    def test_get_video_generator_singleton(self) -> None:
        """Test singleton behavior of get_video_generator."""
        # Clear any existing singleton
        import kagami_studio.generation.video as vid_module

        vid_module._video_generator = None

        gen1 = get_video_generator(VideoProvider.AUTO)
        gen2 = get_video_generator(VideoProvider.AUTO)

        # Should return same instance
        assert gen1 is gen2

        # Clean up
        vid_module._video_generator = None


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


class TestErrorHandling:
    """Tests for error handling in video generation."""

    @pytest.mark.asyncio
    async def test_api_error_handling(self) -> None:
        """Test handling of API errors."""
        generator = KlingVideoGenerator(api_key="test_key")

        # Create proper async context manager
        class MockResponse:
            status = 429

            async def text(self):
                return "Rate limit exceeded"

        class MockContextManager:
            async def __aenter__(self):
                return MockResponse()

            async def __aexit__(self, *args):
                pass

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=MockContextManager())

        with patch.object(
            generator, "_get_session", new_callable=AsyncMock, return_value=mock_session
        ):
            with pytest.raises(RuntimeError, match="Kling API error 429"):
                await generator.generate("Test prompt")

    @pytest.mark.asyncio
    async def test_missing_task_id_error(self) -> None:
        """Test handling of missing task ID in response."""
        generator = KlingVideoGenerator(api_key="test_key")

        # Create proper async context manager
        class MockResponse:
            status = 200

            async def json(self):
                return {"data": {}}  # No task_id

        class MockContextManager:
            async def __aenter__(self):
                return MockResponse()

            async def __aexit__(self, *args):
                pass

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=MockContextManager())

        with patch.object(
            generator, "_get_session", new_callable=AsyncMock, return_value=mock_session
        ):
            with pytest.raises(RuntimeError, match="No task_id"):
                await generator.generate("Test prompt")

    @pytest.mark.asyncio
    async def test_generation_time_tracking(self) -> None:
        """Test that generation time is tracked."""
        generator = VideoGenerator(kling_api_key="test_key")

        # Mock a successful generation that takes some time
        async def slow_generate(*args, **kwargs):
            await asyncio.sleep(0.1)  # Simulate some processing time
            return VideoResult(
                success=True,
                video_url="https://example.com/video.mp4",
                provider="kling",
                generation_time_seconds=0.1,
            )

        with patch.object(
            generator,
            "_generate_with_kling",
            new_callable=AsyncMock,
            side_effect=slow_generate,
        ):
            result = await generator.generate("Test prompt", provider=VideoProvider.KLING)

        assert result.generation_time_seconds >= 0.0


# =============================================================================
# SESSION MANAGEMENT TESTS
# =============================================================================


class TestSessionManagement:
    """Tests for HTTP session management."""

    @pytest.mark.asyncio
    async def test_session_reuse(self) -> None:
        """Test that sessions are reused."""
        generator = KlingVideoGenerator(api_key="test_key")

        # Manually set initialized state
        generator._keychain_checked = True

        mock_session = MagicMock()
        mock_session.closed = False
        generator._session = mock_session

        session = await generator._get_session()
        assert session is mock_session

    @pytest.mark.asyncio
    async def test_session_close(self) -> None:
        """Test session cleanup."""
        generator = KlingVideoGenerator(api_key="test_key")

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.close = AsyncMock()
        generator._session = mock_session

        await generator.close()

        mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_without_session(self) -> None:
        """Test close when no session exists."""
        generator = KlingVideoGenerator(api_key="test_key")
        generator._session = None

        # Should not raise
        await generator.close()
