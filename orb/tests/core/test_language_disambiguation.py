"""Tests for Language Disambiguation

Validates that ambiguous commands trigger clarification requests.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration


from kagami.core.language_model.disambiguation import (
    LanguageDisambiguator,
    check_disambiguation,
)


class TestDisambiguationDetection:
    """Test detection of ambiguous commands."""

    def test_delete_all_is_ambiguous(self) -> None:
        """Verify 'delete all' triggers clarification."""
        disamb = LanguageDisambiguator(confidence_threshold=0.7)

        intent = {
            "action": "delete all deprecated",
            "params": {},  # No specific parameters
        }

        result = disamb.analyze_intent(intent)

        assert result.is_ambiguous, "'delete all' should be ambiguous"
        assert result.confidence < 0.7, "Confidence should be low"
        assert result.clarification_prompt is not None, "Should provide clarification"

        print(f"✅ Detected ambiguity: {result.ambiguity_type}")
        print(f"   - Confidence: {result.confidence}")
        print(f"   - Prompt: {result.clarification_prompt}")

    def test_specific_delete_is_clear(self) -> None:
        """Verify specific delete with ID/path is not ambiguous."""
        disamb = LanguageDisambiguator(confidence_threshold=0.7)

        intent = {
            "action": "delete",
            "params": {"id": "file_12345"},  # Explicit ID
        }

        result = disamb.analyze_intent(intent)

        assert not result.is_ambiguous, "Specific delete should be clear"
        assert result.confidence >= 0.7, "Confidence should be high"
        assert result.clarification_prompt is None, "Should not need clarification"

        print(f"✅ Clear intent recognized: confidence={result.confidence}")

    def test_vague_update_triggers_clarification(self) -> None:
        """Verify 'update the config' without specifics is ambiguous."""
        disamb = LanguageDisambiguator(confidence_threshold=0.7)

        intent = {
            "action": "update config",
            "params": {},
        }

        result = disamb.analyze_intent(intent)

        assert result.is_ambiguous, "'update config' should be ambiguous"
        assert result.confidence < 0.7, "Confidence should be low"

        print("✅ Vague update detected as ambiguous")

    def test_fix_bug_provides_suggestions(self) -> None:
        """Verify 'fix bug' provides interpretation suggestions."""
        disamb = LanguageDisambiguator(confidence_threshold=0.7)

        intent = {
            "action": "fix bug",
            "params": {},
        }

        result = disamb.analyze_intent(intent)

        assert result.is_ambiguous, "'fix bug' should be ambiguous"
        assert result.suggested_interpretations is not None, "Should suggest interpretations"
        assert len(result.suggested_interpretations) > 0, "Should have suggestions"

        print(f"✅ Suggestions provided: {len(result.suggested_interpretations)} options")
        for suggestion in result.suggested_interpretations:
            print(f"   - {suggestion['interpretation']}: needs {suggestion['needs']}")


class TestDisambiguationThreshold:
    """Test confidence threshold behavior."""

    def test_threshold_controls_clarification(self) -> None:
        """Verify threshold=0.5 allows more ambiguity than threshold=0.8."""
        intent = {
            "action": "remove",  # Somewhat ambiguous
            "params": {},
        }

        # Strict threshold
        strict_disamb = LanguageDisambiguator(confidence_threshold=0.8)
        strict_result = strict_disamb.analyze_intent(intent)

        # Lenient threshold
        lenient_disamb = LanguageDisambiguator(confidence_threshold=0.5)
        lenient_result = lenient_disamb.analyze_intent(intent)

        # Same confidence score
        assert strict_result.confidence == lenient_result.confidence

        # But different clarification requirements based on threshold
        if strict_result.confidence < 0.8:
            assert strict_result.is_ambiguous, "Should be ambiguous with strict threshold"

        if lenient_result.confidence >= 0.5:
            assert not lenient_result.is_ambiguous, "Should be clear with lenient threshold"

        print("✅ Threshold controls clarification")
        print(f"   - Confidence: {strict_result.confidence}")
        print(f"   - Strict (0.8): ambiguous={strict_result.is_ambiguous}")
        print(f"   - Lenient (0.5): ambiguous={lenient_result.is_ambiguous}")


@pytest.mark.asyncio
async def test_check_disambiguation_helper() -> None:
    """Test async helper function."""
    # Ambiguous intent
    ambiguous_intent = {
        "action": "delete all",
        "params": {},
    }

    clarification = await check_disambiguation(ambiguous_intent)

    assert clarification is not None, "Should request clarification"
    assert clarification["status"] == "needs_clarification"
    assert "clarification_prompt" in clarification

    # Clear intent
    clear_intent = {
        "action": "delete",
        "params": {"id": "specific-item-123"},
    }

    clarification = await check_disambiguation(clear_intent)

    assert clarification is None, "Clear intent should not need clarification"

    print("✅ Async helper function works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
