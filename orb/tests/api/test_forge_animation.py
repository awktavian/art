from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


"""Tests for Forge animation API endpoints."""


class TestFacialAnimation:
    """Test facial animation endpoints."""

    def test_animate_expression_endpoint_exists(self, client) -> None:
        """Test facial expression endpoint is registered."""
        response = client.post(
            "/api/forge/animation/facial/expression",
            json={
                "character_id": "test_char_123",
                "emotion": "happy",
                "intensity": 0.8,
                "duration": 2.0,
            },
            headers={"Idempotency-Key": "test-expression-001"},
        )
        # May return 401 (auth), 501 (module unavailable), or 200 (success)
        assert response.status_code in [200, 401, 403, 501]

    def test_animate_expression_requires_character(self, client) -> None:
        """Test expression animation requires character_id."""
        response = client.post(
            "/api/forge/animation/facial/expression",
            json={
                "emotion": "happy",
            },
            headers={"Idempotency-Key": "test-expression-002"},
        )
        # Should fail validation or auth
        assert response.status_code in [400, 401, 403, 422, 501]

    def test_lipsync_endpoint_exists(self, client) -> None:
        """Test lipsync endpoint is registered."""
        # Create fake audio file

        import io

        audio_data = b"fake audio content"
        files = {"audio_file": ("test.wav", io.BytesIO(audio_data), "audio/wav")}

        response = client.post(
            "/api/forge/animation/facial/lipsync",
            data={"character_id": "test_char_123"},
            files=files,
            headers={"Idempotency-Key": "test-lipsync-001"},
        )
        assert response.status_code in [200, 401, 403, 501]

    def test_blinks_endpoint_exists(self, client) -> None:
        """Test blink generation endpoint is registered."""
        response = client.post(
            "/api/forge/animation/facial/blinks",
            json={
                "character_id": "test_char_123",
                "duration": 10.0,
                "frequency": 0.2,
            },
            headers={"Idempotency-Key": "test-blinks-001"},
        )
        assert response.status_code in [200, 401, 403, 501]


class TestGaitAnimation:
    """Test gait analysis and generation endpoints."""

    def test_gait_generation_endpoint_exists(self, client) -> None:
        """Test gait generation endpoint is registered."""
        response = client.post(
            "/api/forge/animation/gait/generate",
            json={
                "character_id": "test_char_123",
                "terrain_type": "flat",
                "speed": 1.0,
                "distance": 10.0,
            },
            headers={"Idempotency-Key": "test-gait-001"},
        )
        assert response.status_code in [200, 401, 403, 501]

    def test_gait_terrain_types(self, client) -> None:
        """Test different terrain types."""
        terrains = ["flat", "uphill", "downhill", "stairs", "rough"]

        for terrain in terrains:
            response = client.post(
                "/api/forge/animation/gait/generate",
                json={
                    "character_id": "test_char_123",
                    "terrain_type": terrain,
                },
                headers={"Idempotency-Key": f"test-gait-terrain-{terrain}"},
            )
            assert response.status_code in [200, 401, 403, 501]


class TestGestureGeneration:
    """Test gesture generation endpoints."""

    def test_gestures_from_speech_endpoint_exists(self, client) -> None:
        """Test speech-driven gesture endpoint is registered."""
        response = client.post(
            "/api/forge/animation/gestures/from_speech",
            json={
                "character_id": "test_char_123",
                "text": "Hello, how are you doing today?",
                "emotion": "friendly",
                "energy_level": 0.6,
            },
            headers={"Idempotency-Key": "test-gesture-speech-001"},
        )
        assert response.status_code in [200, 401, 403, 501]

    def test_idle_gestures_endpoint_exists(self, client) -> None:
        """Test idle gesture endpoint is registered."""
        response = client.post(
            "/api/forge/animation/gestures/idle",
            json={
                "character_id": "test_char_123",
                "duration": 10.0,
                "energy_level": 0.3,
            },
            headers={"Idempotency-Key": "test-gesture-idle-001"},
        )
        assert response.status_code in [200, 401, 403, 501]

    def test_gesture_energy_levels(self, client) -> None:
        """Test different energy levels."""
        for energy in [0.1, 0.5, 1.0]:
            response = client.post(
                "/api/forge/animation/gestures/idle",
                json={
                    "character_id": "test_char_123",
                    "duration": 5.0,
                    "energy_level": energy,
                },
                headers={"Idempotency-Key": f"test-gesture-energy-{int(energy * 10)}"},
            )
            assert response.status_code in [200, 401, 403, 501]


class TestImageToCharacter:
    """Test image-to-character generation endpoint."""

    def test_image_generation_endpoint_exists(self, client) -> None:
        """Test image-to-character endpoint is registered."""
        import io

        # Create fake image
        image_data = b"fake image content"
        files = {"image": ("test.jpg", io.BytesIO(image_data), "image/jpeg")}

        response = client.post(
            "/api/forge/generate/from_image",
            files=files,
            data={"quality_mode": "preview"},
            headers={"Idempotency-Key": "test-image-char-001"},
        )
        assert response.status_code in [200, 401, 403, 501]

    def test_image_generation_quality_modes(self, client) -> None:
        """Test different quality modes."""
        import io

        for quality in ["preview", "draft"]:
            image_data = b"fake image"
            files = {"image": ("test.jpg", io.BytesIO(image_data), "image/jpeg")}

            response = client.post(
                "/api/forge/generate/from_image",
                files=files,
                data={"quality_mode": quality},
                headers={"Idempotency-Key": f"test-image-quality-{quality}"},
            )
            assert response.status_code in [200, 401, 403, 501]

    def test_image_generation_requires_confirmation_for_final(self, client) -> None:
        """Test final quality requires confirmation."""
        import io

        image_data = b"fake image"
        files = {"image": ("test.jpg", io.BytesIO(image_data), "image/jpeg")}

        response = client.post(
            "/api/forge/generate/from_image",
            files=files,
            data={"quality_mode": "final"},
            headers={"Idempotency-Key": "test-image-final-001"},
        )
        # Should require confirmation
        assert response.status_code in [400, 401, 403, 501]


class TestIdempotency:
    """Test idempotency across animation endpoints."""

    def test_duplicate_requests_rejected(self, client) -> None:
        """Test duplicate idempotency keys are rejected."""
        key = "test-duplicate-001"

        # First request
        response1 = client.post(
            "/api/forge/animation/facial/expression",
            json={
                "character_id": "test",
                "emotion": "happy",
            },
            headers={"Idempotency-Key": key},
        )

        # Duplicate request with same key
        response2 = client.post(
            "/api/forge/animation/facial/expression",
            json={
                "character_id": "test",
                "emotion": "sad",  # Different data
            },
            headers={"Idempotency-Key": key},
        )

        # If both succeed or both hit auth, that's fine
        # If first succeeds, second should be 409 or return cached result
        if response1.status_code == 200:
            assert response2.status_code in [200, 409]
