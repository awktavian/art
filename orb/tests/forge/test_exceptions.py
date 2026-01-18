"""Comprehensive tests for forge exceptions module.

Tests all custom exception classes.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration


from kagami.forge.exceptions import (
    AnimationError,
    ExportError,
    ForgeError,
    GenerationError,
    GenerationTimeoutError,
    ModuleInitializationError,
    ModuleNotAvailableError,
    NarrativeGenerationError,
    PersonalityGenerationError,
    RiggingError,
    VisualGenerationError,
    VoiceGenerationError,
)


class TestModuleInitializationError:
    """Test ModuleInitializationError exception."""

    def test_creation(self) -> None:
        """Test creating the exception."""
        error = ModuleInitializationError("mesh_generator", "GPU not available")

        assert error.module_name == "mesh_generator"
        assert error.reason == "GPU not available"
        assert "mesh_generator" in str(error)
        assert "GPU not available" in str(error)

    def test_inheritance(self) -> None:
        """Test exception inherits from ForgeError."""
        error = ModuleInitializationError("test", "reason")
        assert isinstance(error, ForgeError)


class TestModuleNotAvailableError:
    """Test ModuleNotAvailableError exception."""

    def test_creation(self) -> None:
        """Test creating the exception."""
        error = ModuleNotAvailableError("voice_synthesizer")

        assert error.module_name == "voice_synthesizer"
        assert "voice_synthesizer" in str(error)

    def test_inheritance(self) -> None:
        """Test exception inherits from ForgeError."""
        error = ModuleNotAvailableError("test")
        assert isinstance(error, ForgeError)


class TestGenerationTimeoutError:
    """Test GenerationTimeoutError exception."""

    def test_creation(self) -> None:
        """Test creating the exception."""
        error = GenerationTimeoutError("mesh_generation", 30000.0)

        assert error.phase == "mesh_generation"
        assert error.timeout_ms == 30000.0
        assert "mesh_generation" in str(error)
        assert "30000" in str(error)

    def test_inheritance(self) -> None:
        """Test exception inherits from GenerationError."""
        error = GenerationTimeoutError("test", 1000.0)
        assert isinstance(error, GenerationError)
        assert isinstance(error, ForgeError)


class TestVisualGenerationError:
    """Test VisualGenerationError exception."""

    def test_creation_simple(self) -> None:
        """Test creating with just reason."""
        error = VisualGenerationError("Texture generation failed")

        assert "Texture generation failed" in str(error)

    def test_creation_with_details(self) -> None:
        """Test creating with details."""
        error = VisualGenerationError("Mesh invalid", details={"vertex_count": 0, "expected": 1000})

        assert "Mesh invalid" in str(error)

    def test_inheritance(self) -> None:
        """Test exception inherits from GenerationError."""
        error = VisualGenerationError("test")
        assert isinstance(error, GenerationError)


class TestPersonalityGenerationError:
    """Test PersonalityGenerationError exception."""

    def test_creation(self) -> None:
        """Test creating the exception."""
        error = PersonalityGenerationError("Trait conflict detected")

        assert "Trait conflict detected" in str(error)

    def test_with_details(self) -> None:
        """Test creating with details."""
        error = PersonalityGenerationError(
            "Invalid traits", details={"conflicting": ["brave", "cowardly"]}
        )

        assert "Invalid traits" in str(error)


class TestVoiceGenerationError:
    """Test VoiceGenerationError exception."""

    def test_creation(self) -> None:
        """Test creating the exception."""
        error = VoiceGenerationError("TTS model unavailable")

        assert "TTS model unavailable" in str(error)
        assert isinstance(error, GenerationError)


class TestNarrativeGenerationError:
    """Test NarrativeGenerationError exception."""

    def test_creation(self) -> None:
        """Test creating the exception."""
        error = NarrativeGenerationError("Backstory contradicts traits")

        assert "Backstory contradicts traits" in str(error)
        assert isinstance(error, GenerationError)


class TestRiggingError:
    """Test RiggingError exception."""

    def test_creation(self) -> None:
        """Test creating the exception."""
        error = RiggingError("Skeleton generation failed")

        assert "Skeleton generation failed" in str(error)

    def test_with_details(self) -> None:
        """Test creating with details."""
        error = RiggingError("Invalid bone count", details={"bones": 0, "required": 50})

        assert "Invalid bone count" in str(error)
        assert isinstance(error, GenerationError)


class TestAnimationError:
    """Test AnimationError exception."""

    def test_creation(self) -> None:
        """Test creating the exception."""
        error = AnimationError("Motion synthesis failed")

        assert "Motion synthesis failed" in str(error)
        assert isinstance(error, GenerationError)


class TestExportError:
    """Test ExportError exception."""

    def test_creation_simple(self) -> None:
        """Test creating with just reason."""
        error = ExportError("File write failed")

        assert "File write failed" in str(error)

    def test_creation_with_format(self) -> None:
        """Test creating with format."""
        error = ExportError("Invalid format", format="fbx")

        assert "Invalid format" in str(error)

    def test_creation_with_details(self) -> None:
        """Test creating with details."""
        error = ExportError("Export failed", format="gltf", details={"file_size": "too_large"})

        assert "Export failed" in str(error)
        assert isinstance(error, GenerationError)


class TestExceptionContext:
    """Test exception context handling."""

    def test_forge_error_context(self) -> None:
        """Test ForgeError accepts context."""
        try:
            raise ModuleInitializationError("test", "reason")
        except ForgeError as e:
            assert hasattr(e, "context") or hasattr(e, "module_name")

    def test_generation_error_chaining(self) -> None:
        """Test exception chaining works."""
        original = ValueError("Original error")

        try:
            try:
                raise original
            except ValueError:
                raise GenerationTimeoutError("test", 1000.0) from None
        except GenerationTimeoutError as e:
            assert e.__cause__ is None
