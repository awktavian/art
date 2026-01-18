"""Comprehensive Intent Service Tests

Tests for kagami_api/services/intent_service.py with full coverage.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_unit

import asyncio
import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("KAGAMI_TEST_ECHO_LLM", "1")


class TestSmokeImports:
    """Smoke test for all module exports."""

    def test_all_exports_importable(self) -> None:
        """Test all module exports can be imported."""
        from kagami_api.services.intent_service import (
            IntentParseError,
            IntentResult,
            IntentServiceError,
            ParsedResult,
            assess_risk,
            derive_v2_suggestions,
            infer_v2_suggestions_with_llm,
            parse_lang_command,
            parse_lang_command_fast,
            sanitize_intent_metadata,
        )

        # Verify all exports are not None
        assert IntentServiceError is not None
        assert IntentParseError is not None
        assert IntentResult is not None
        assert ParsedResult is not None
        assert assess_risk is not None
        assert sanitize_intent_metadata is not None
        assert derive_v2_suggestions is not None
        assert parse_lang_command is not None
        assert parse_lang_command_fast is not None
        assert infer_v2_suggestions_with_llm is not None


class TestAssessRisk:
    """Tests for assess_risk function."""

    def test_assess_risk_low_preview(self) -> None:
        """Test low risk assessment for preview action."""
        from kagami_api.services.intent_service import assess_risk
        from kagami.core.schemas.schemas.intents import Intent, IntentVerb

        intent = Intent(action=IntentVerb.PREVIEW, target="test.file")
        risk = assess_risk(intent)

        assert risk == "low"

    def test_assess_risk_low_read(self) -> None:
        """Test low risk assessment for read operations."""
        from kagami_api.services.intent_service import assess_risk
        from kagami.core.schemas.schemas.intents import Intent, IntentVerb

        intent = Intent(action=IntentVerb.EXECUTE, target="read.data")
        risk = assess_risk(intent)

        assert risk == "low"

    def test_assess_risk_high_delete_target(self) -> None:
        """Test high risk assessment for delete in target."""
        from kagami_api.services.intent_service import assess_risk
        from kagami.core.schemas.schemas.intents import Intent, IntentVerb

        intent = Intent(action=IntentVerb.EXECUTE, target="delete.file")
        risk = assess_risk(intent)

        assert risk == "high"

    def test_assess_risk_high_remove_target(self) -> None:
        """Test high risk assessment for remove in target."""
        from kagami_api.services.intent_service import assess_risk
        from kagami.core.schemas.schemas.intents import Intent, IntentVerb

        intent = Intent(action=IntentVerb.EXECUTE, target="remove.user")
        risk = assess_risk(intent)

        assert risk == "high"

    def test_assess_risk_high_destroy_target(self) -> None:
        """Test high risk assessment for destroy in target."""
        from kagami_api.services.intent_service import assess_risk
        from kagami.core.schemas.schemas.intents import Intent, IntentVerb

        intent = Intent(action=IntentVerb.EXECUTE, target="destroy.resource")
        risk = assess_risk(intent)

        assert risk == "high"

    def test_assess_risk_medium_end_action(self) -> None:
        """Test medium risk assessment for END action."""
        from kagami_api.services.intent_service import assess_risk
        from kagami.core.schemas.schemas.intents import Intent, IntentVerb

        intent = Intent(action=IntentVerb.END, target="session")
        risk = assess_risk(intent)

        assert risk == "medium"

    def test_assess_risk_medium_catch_action(self) -> None:
        """Test medium risk assessment for CATCH action."""
        from kagami_api.services.intent_service import assess_risk
        from kagami.core.schemas.schemas.intents import Intent, IntentVerb

        intent = Intent(action=IntentVerb.CATCH, target="error")
        risk = assess_risk(intent)

        assert risk == "medium"

    def test_assess_risk_medium_end_target(self) -> None:
        """Test medium risk assessment for target starting with 'end.'."""
        from kagami_api.services.intent_service import assess_risk
        from kagami.core.schemas.schemas.intents import Intent, IntentVerb

        intent = Intent(action=IntentVerb.EXECUTE, target="end.workflow")
        risk = assess_risk(intent)

        assert risk == "medium"

    def test_assess_risk_medium_catch_target(self) -> None:
        """Test medium risk assessment for target starting with 'catch.'."""
        from kagami_api.services.intent_service import assess_risk
        from kagami.core.schemas.schemas.intents import Intent, IntentVerb

        intent = Intent(action=IntentVerb.EXECUTE, target="catch.exception")
        risk = assess_risk(intent)

        assert risk == "medium"

    def test_assess_risk_none_target(self) -> None:
        """Test risk assessment with None target."""
        from kagami_api.services.intent_service import assess_risk
        from kagami.core.schemas.schemas.intents import Intent, IntentVerb

        intent = Intent(action=IntentVerb.PREVIEW, target=None)

        risk = assess_risk(intent)

        assert risk == "low"

    def test_assess_risk_case_insensitive(self) -> None:
        """Test risk assessment is case insensitive."""
        from kagami_api.services.intent_service import assess_risk
        from kagami.core.schemas.schemas.intents import Intent, IntentVerb

        intent = Intent(action=IntentVerb.EXECUTE, target="DELETE.FILE")
        risk = assess_risk(intent)

        assert risk == "high"


class TestSanitizeIntentMetadata:
    """Tests for sanitize_intent_metadata function."""

    def test_sanitize_clamps_max_tokens_upper_bound(self) -> None:
        """Test max_tokens is clamped to upper bound of 1000."""
        from kagami_api.services.intent_service import sanitize_intent_metadata
        from kagami.core.schemas.schemas.intents import Intent, IntentVerb

        intent = Intent(action=IntentVerb.EXECUTE, target="test", metadata={"max_tokens": 99999})
        sanitize_intent_metadata(intent)

        assert intent.metadata["max_tokens"] == 1000

    def test_sanitize_clamps_max_tokens_lower_bound(self) -> None:
        """Test max_tokens is clamped to lower bound of 16."""
        from kagami_api.services.intent_service import sanitize_intent_metadata
        from kagami.core.schemas.schemas.intents import Intent, IntentVerb

        intent = Intent(action=IntentVerb.EXECUTE, target="test", metadata={"max_tokens": 5})
        sanitize_intent_metadata(intent)

        assert intent.metadata["max_tokens"] == 16

    def test_sanitize_max_tokens_within_range(self) -> None:
        """Test max_tokens within valid range is preserved."""
        from kagami_api.services.intent_service import sanitize_intent_metadata
        from kagami.core.schemas.schemas.intents import Intent, IntentVerb

        intent = Intent(action=IntentVerb.EXECUTE, target="test", metadata={"max_tokens": 500})
        sanitize_intent_metadata(intent)

        assert intent.metadata["max_tokens"] == 500

    def test_sanitize_max_tokens_default(self) -> None:
        """Test max_tokens defaults to 300 when not provided."""
        from kagami_api.services.intent_service import sanitize_intent_metadata
        from kagami.core.schemas.schemas.intents import Intent, IntentVerb

        intent = Intent(action=IntentVerb.EXECUTE, target="test", metadata={})
        sanitize_intent_metadata(intent)

        assert intent.metadata["max_tokens"] == 300

    def test_sanitize_max_tokens_invalid_string(self) -> None:
        """Test max_tokens defaults to 300 for invalid string values."""
        from kagami_api.services.intent_service import sanitize_intent_metadata
        from kagami.core.schemas.schemas.intents import Intent, IntentVerb

        intent = Intent(
            action=IntentVerb.EXECUTE, target="test", metadata={"max_tokens": "invalid"}
        )
        sanitize_intent_metadata(intent)

        assert intent.metadata["max_tokens"] == 300

    def test_sanitize_clamps_budget_ms_upper_bound(self) -> None:
        """Test budget_ms is clamped to upper bound of 30000."""
        from kagami_api.services.intent_service import sanitize_intent_metadata
        from kagami.core.schemas.schemas.intents import Intent, IntentVerb

        intent = Intent(action=IntentVerb.EXECUTE, target="test", metadata={"budget_ms": 999999})
        sanitize_intent_metadata(intent)

        assert intent.metadata["budget_ms"] == 30000

    def test_sanitize_clamps_budget_ms_lower_bound(self) -> None:
        """Test budget_ms is clamped to lower bound of 50."""
        from kagami_api.services.intent_service import sanitize_intent_metadata
        from kagami.core.schemas.schemas.intents import Intent, IntentVerb

        intent = Intent(action=IntentVerb.EXECUTE, target="test", metadata={"budget_ms": 10})
        sanitize_intent_metadata(intent)

        assert intent.metadata["budget_ms"] == 50

    def test_sanitize_budget_ms_within_range(self) -> None:
        """Test budget_ms within valid range is preserved."""
        from kagami_api.services.intent_service import sanitize_intent_metadata
        from kagami.core.schemas.schemas.intents import Intent, IntentVerb

        intent = Intent(action=IntentVerb.EXECUTE, target="test", metadata={"budget_ms": 5000})
        sanitize_intent_metadata(intent)

        assert intent.metadata["budget_ms"] == 5000

    def test_sanitize_budget_ms_default(self) -> None:
        """Test budget_ms defaults to 2000 when not provided."""
        from kagami_api.services.intent_service import sanitize_intent_metadata
        from kagami.core.schemas.schemas.intents import Intent, IntentVerb

        intent = Intent(action=IntentVerb.EXECUTE, target="test", metadata={})
        sanitize_intent_metadata(intent)

        assert intent.metadata["budget_ms"] == 2000

    def test_sanitize_budget_ms_invalid_value(self) -> None:
        """Test budget_ms defaults to 2000 for invalid values."""
        from kagami_api.services.intent_service import sanitize_intent_metadata
        from kagami.core.schemas.schemas.intents import Intent, IntentVerb

        intent = Intent(action=IntentVerb.EXECUTE, target="test", metadata={"budget_ms": "bad"})
        sanitize_intent_metadata(intent)

        assert intent.metadata["budget_ms"] == 2000

    def test_sanitize_tools_allowlist_filtering(self) -> None:
        """Test tools are filtered against allowlist."""
        from kagami_api.services.intent_service import sanitize_intent_metadata
        from kagami.core.schemas.schemas.intents import Intent, IntentVerb

        # Set allowlist via environment
        os.environ["ALLOWED_TOOLS"] = "files,plans"

        intent = Intent(
            action=IntentVerb.EXECUTE,
            target="test",
            metadata={"tools": ["files", "plans", "forbidden", "crm"]},
        )
        sanitize_intent_metadata(intent)

        # Only files and plans should be allowed
        assert "files" in intent.metadata["tools"]
        assert "plans" in intent.metadata["tools"]
        assert "forbidden" not in intent.metadata["tools"]
        assert "crm" not in intent.metadata["tools"]

    def test_sanitize_tools_max_limit(self) -> None:
        """Test tools list is limited to 8 items."""
        from kagami_api.services.intent_service import sanitize_intent_metadata
        from kagami.core.schemas.schemas.intents import Intent, IntentVerb

        os.environ["ALLOWED_TOOLS"] = "t1,t2,t3,t4,t5,t6,t7,t8,t9,t10"

        intent = Intent(
            action=IntentVerb.EXECUTE,
            target="test",
            metadata={"tools": ["t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8", "t9", "t10"]},
        )
        sanitize_intent_metadata(intent)

        assert len(intent.metadata["tools"]) <= 8

    def test_sanitize_string_field_truncation(self) -> None:
        """Test long string fields are truncated to 2048 characters."""
        from kagami_api.services.intent_service import sanitize_intent_metadata
        from kagami.core.schemas.schemas.intents import Intent, IntentVerb

        long_string = "x" * 5000
        intent = Intent(
            action=IntentVerb.EXECUTE,
            target="test",
            metadata={
                "scope": long_string,
                "regex": long_string,
                "since": long_string,
                "until": long_string,
            },
        )
        sanitize_intent_metadata(intent)

        assert len(intent.metadata["scope"]) == 2048
        assert len(intent.metadata["regex"]) == 2048
        assert len(intent.metadata["since"]) == 2048
        assert len(intent.metadata["until"]) == 2048

    def test_sanitize_none_metadata(self) -> None:
        """Test sanitize handles None metadata gracefully."""
        from kagami_api.services.intent_service import sanitize_intent_metadata
        from kagami.core.schemas.schemas.intents import Intent, IntentVerb

        intent = Intent(action=IntentVerb.EXECUTE, target="test", metadata=None)

        sanitize_intent_metadata(intent)

        assert intent.metadata["max_tokens"] == 300
        assert intent.metadata["budget_ms"] == 2000


class TestDeriveV2Suggestions:
    """Tests for derive_v2_suggestions function."""

    def test_derive_goal_for_settings(self) -> None:
        """Test GOAL suggestion for settings target."""
        from kagami_api.services.intent_service import derive_v2_suggestions
        from kagami.core.schemas.schemas.intents import Intent, IntentVerb

        intent = Intent(action=IntentVerb.EXECUTE, target="settings.update")
        sections = {}

        suggestions = derive_v2_suggestions(intent, sections)

        assert "GOAL" in suggestions
        assert "settings" in suggestions["GOAL"].lower()

    def test_derive_goal_for_plan(self) -> None:
        """Test GOAL suggestion for plan target."""
        from kagami_api.services.intent_service import derive_v2_suggestions
        from kagami.core.schemas.schemas.intents import Intent, IntentVerb

        intent = Intent(action=IntentVerb.EXECUTE, target="plan.create")
        sections = {}

        suggestions = derive_v2_suggestions(intent, sections)

        assert "GOAL" in suggestions
        assert "plan" in suggestions["GOAL"].lower()

    def test_derive_context_with_paths_and_refs(self) -> None:
        """Test CONTEXT suggestion includes paths and refs."""
        from kagami_api.services.intent_service import derive_v2_suggestions
        from kagami.core.schemas.schemas.intents import Intent, IntentVerb

        intent = Intent(action=IntentVerb.EXECUTE, target="settings.update")
        sections = {}

        suggestions = derive_v2_suggestions(intent, sections)

        assert "CONTEXT" in suggestions
        assert "paths" in suggestions["CONTEXT"]
        assert "refs" in suggestions["CONTEXT"]
        assert isinstance(suggestions["CONTEXT"]["paths"], list)
        assert len(suggestions["CONTEXT"]["paths"]) > 0

    def test_derive_constraints_with_perf_and_security(self) -> None:
        """Test CONSTRAINTS suggestion includes perf and security."""
        from kagami_api.services.intent_service import derive_v2_suggestions
        from kagami.core.schemas.schemas.intents import Intent, IntentVerb

        intent = Intent(action=IntentVerb.EXECUTE, target="test")
        sections = {}

        suggestions = derive_v2_suggestions(intent, sections)

        assert "CONSTRAINTS" in suggestions
        assert "perf" in suggestions["CONSTRAINTS"]
        assert "security" in suggestions["CONSTRAINTS"]
        assert "p99_ms" in suggestions["CONSTRAINTS"]["perf"]
        assert "require_rbac" in suggestions["CONSTRAINTS"]["security"]

    def test_derive_acceptance_with_tests_and_behaviors(self) -> None:
        """Test ACCEPTANCE suggestion includes tests and behaviors."""
        from kagami_api.services.intent_service import derive_v2_suggestions
        from kagami.core.schemas.schemas.intents import Intent, IntentVerb

        intent = Intent(action=IntentVerb.EXECUTE, target="plan.create")
        sections = {}

        suggestions = derive_v2_suggestions(intent, sections)

        assert "ACCEPTANCE" in suggestions
        assert "tests" in suggestions["ACCEPTANCE"]
        assert "behaviors" in suggestions["ACCEPTANCE"]
        assert isinstance(suggestions["ACCEPTANCE"]["tests"], list)
        assert isinstance(suggestions["ACCEPTANCE"]["behaviors"], list)

    def test_derive_workflow_default(self) -> None:
        """Test WORKFLOW suggestion defaults to auto."""
        from kagami_api.services.intent_service import derive_v2_suggestions
        from kagami.core.schemas.schemas.intents import Intent, IntentVerb

        intent = Intent(action=IntentVerb.EXECUTE, target="test")
        sections = {}

        suggestions = derive_v2_suggestions(intent, sections)

        assert "WORKFLOW" in suggestions
        assert suggestions["WORKFLOW"]["plan"] == "auto"

    def test_derive_boundaries_with_edit_restrictions(self) -> None:
        """Test BOUNDARIES suggestion includes only_edit."""
        from kagami_api.services.intent_service import derive_v2_suggestions
        from kagami.core.schemas.schemas.intents import Intent, IntentVerb

        intent = Intent(action=IntentVerb.EXECUTE, target="test")
        sections = {}

        suggestions = derive_v2_suggestions(intent, sections)

        assert "BOUNDARIES" in suggestions
        assert "only_edit" in suggestions["BOUNDARIES"]
        assert isinstance(suggestions["BOUNDARIES"]["only_edit"], list)

    def test_derive_respects_existing_sections(self) -> None:
        """Test derive_v2_suggestions does not override existing sections."""
        from kagami_api.services.intent_service import derive_v2_suggestions
        from kagami.core.schemas.schemas.intents import Intent, IntentVerb

        intent = Intent(action=IntentVerb.EXECUTE, target="test")
        sections = {"GOAL": "Custom goal"}

        suggestions = derive_v2_suggestions(intent, sections)

        # Should not suggest GOAL if already present
        assert "GOAL" not in suggestions or suggestions["GOAL"] != "Custom goal"

    def test_derive_empty_dict_on_error(self) -> None:
        """Test derive_v2_suggestions returns default suggestions when intent is None."""
        from kagami_api.services.intent_service import derive_v2_suggestions

        # Pass invalid intent (None) - function uses getattr with defaults
        suggestions = derive_v2_suggestions(None, {})  # type: ignore[arg-type]

        # Function returns default suggestions (not empty dict) because getattr provides defaults
        assert isinstance(suggestions, dict)
        assert "GOAL" in suggestions  # Always generates GOAL
        assert "CONSTRAINTS" in suggestions  # Always generates CONSTRAINTS


class TestParseLangCommand:
    """Tests for parse_lang_command function."""

    @pytest.mark.asyncio
    async def test_parse_lang2_command(self) -> None:
        """Test parsing LANG/2 command returns all expected fields."""
        from kagami_api.services.intent_service import parse_lang_command

        result = await parse_lang_command("LANG/2 EXECUTE test.action")

        assert "intent" in result
        assert "event" in result
        assert "quality" in result
        assert "sections" in result
        assert "suggestions" in result
        assert "compiled_lang" in result

    @pytest.mark.asyncio
    async def test_parse_slang_command(self) -> None:
        """Test parsing SLANG command (compact LANG/2)."""
        from kagami_api.services.intent_service import parse_lang_command

        result = await parse_lang_command('SLANG EXECUTE test.action goal="test"')

        assert "intent" in result
        assert "event" in result
        assert "quality" in result
        assert "suggestions" in result

    @pytest.mark.asyncio
    async def test_parse_v1_command(self) -> None:
        """Test parsing basic LANG v1 command."""
        from kagami_api.services.intent_service import parse_lang_command

        result = await parse_lang_command("EXECUTE test.action")

        assert "intent" in result
        assert "event" in result
        assert result["intent"]["action"] is not None

    @pytest.mark.asyncio
    async def test_parse_empty_string_raises_error(self) -> None:
        """Test parsing empty string raises ValueError."""
        from kagami_api.services.intent_service import parse_lang_command

        with pytest.raises(ValueError, match="non-empty string"):
            await parse_lang_command("")

    @pytest.mark.asyncio
    async def test_parse_whitespace_only_raises_error(self) -> None:
        """Test parsing whitespace-only string raises ValueError."""
        from kagami_api.services.intent_service import parse_lang_command

        with pytest.raises(ValueError, match="non-empty string"):
            await parse_lang_command("   ")

    @pytest.mark.asyncio
    async def test_parse_case_insensitive(self) -> None:
        """Test parsing is case insensitive for LANG/2."""
        from kagami_api.services.intent_service import parse_lang_command

        result = await parse_lang_command("lang/2 execute test.action")

        assert "intent" in result
        assert "quality" in result


class TestParseLangCommandFast:
    """Tests for parse_lang_command_fast function."""

    @pytest.mark.asyncio
    async def test_parse_fast_lang2_command(self) -> None:
        """Test fast parsing of LANG/2 command."""
        from kagami_api.services.intent_service import parse_lang_command_fast

        result = await parse_lang_command_fast("LANG/2 PREVIEW test.resource")

        assert "intent" in result
        assert "event" in result
        assert "quality" in result
        assert "sections" in result
        assert "suggestions" in result
        assert "compiled_lang" in result

    @pytest.mark.asyncio
    async def test_parse_fast_slang_command(self) -> None:
        """Test fast parsing of SLANG command."""
        from kagami_api.services.intent_service import parse_lang_command_fast

        result = await parse_lang_command_fast("SLANG PREVIEW test")

        assert "intent" in result
        assert "quality" in result

    @pytest.mark.asyncio
    async def test_parse_fast_v1_fallback(self) -> None:
        """Test fast parsing falls back to v1 for non-LANG/2 commands."""
        from kagami_api.services.intent_service import parse_lang_command_fast

        result = await parse_lang_command_fast("EXECUTE test.action")

        assert "intent" in result
        assert "event" in result

    @pytest.mark.asyncio
    async def test_parse_fast_empty_raises_error(self) -> None:
        """Test fast parsing empty string raises ValueError."""
        from kagami_api.services.intent_service import parse_lang_command_fast

        with pytest.raises(ValueError, match="non-empty string"):
            await parse_lang_command_fast("")

    @pytest.mark.asyncio
    async def test_parse_fast_caching(self) -> None:
        """Test fast parsing uses caching for repeated calls."""
        from kagami_api.services.intent_service import parse_lang_command_fast

        # First call
        result1 = await parse_lang_command_fast("LANG/2 PREVIEW test")
        # Second call (should be cached)
        result2 = await parse_lang_command_fast("LANG/2 PREVIEW test")

        # Results should be equivalent
        assert result1["intent"] == result2["intent"]
        assert result1["quality"] == result2["quality"]


class TestInferV2SuggestionsWithLLM:
    """Tests for infer_v2_suggestions_with_llm function."""

    @pytest.mark.asyncio
    async def test_infer_suggestions_with_missing_sections(self) -> None:
        """Test LLM-based suggestion inference for missing sections."""
        from kagami_api.services.intent_service import infer_v2_suggestions_with_llm
        from kagami.core.schemas.schemas.intents import Intent, IntentVerb

        intent = Intent(action=IntentVerb.EXECUTE, target="test")
        sections = {"app": "test"}

        result = await infer_v2_suggestions_with_llm(intent, sections)

        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_infer_suggestions_no_missing_sections(self) -> None:
        """Test LLM inference returns empty dict when all sections present."""
        from kagami_api.services.intent_service import infer_v2_suggestions_with_llm
        from kagami.core.schemas.schemas.intents import Intent, IntentVerb

        intent = Intent(action=IntentVerb.EXECUTE, target="test")
        sections = {
            "GOAL": "test",
            "CONTEXT": {},
            "CONSTRAINTS": {},
            "ACCEPTANCE": {},
            "WORKFLOW": {},
            "BOUNDARIES": {},
        }

        result = await infer_v2_suggestions_with_llm(intent, sections)

        # Should return empty dict when all sections are present
        assert result == {}

    @pytest.mark.asyncio
    async def test_infer_suggestions_timeout_handling(self) -> None:
        """Test LLM inference handles timeout gracefully."""
        from kagami_api.services.intent_service import infer_v2_suggestions_with_llm
        from kagami.core.schemas.schemas.intents import Intent, IntentVerb

        intent = Intent(action=IntentVerb.EXECUTE, target="test", metadata={"budget_ms": 100})
        sections = {}

        # Should not raise, just return empty dict on timeout
        result = await infer_v2_suggestions_with_llm(intent, sections)

        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_infer_suggestions_error_handling(self) -> None:
        """Test LLM inference handles errors gracefully."""
        from kagami_api.services.intent_service import infer_v2_suggestions_with_llm
        from kagami.core.schemas.schemas.intents import Intent, IntentVerb

        with patch("kagami_api.services.intent_service.get_llm_service") as mock_llm:
            mock_llm.side_effect = Exception("LLM failure")

            intent = Intent(action=IntentVerb.EXECUTE, target="test")
            sections = {}

            result = await infer_v2_suggestions_with_llm(intent, sections)

            # Should return empty dict on error, not raise
            assert result == {}


class TestParsedResult:
    """Tests for ParsedResult TypedDict."""

    def test_parsed_result_structure(self) -> None:
        """Test ParsedResult has all expected keys."""
        from kagami_api.services.intent_service import ParsedResult

        # TypedDict should have these keys
        expected_keys = [
            "intent",
            "event",
            "quality",
            "sections",
            "suggestions",
            "compiled_lang",
            "prompt_trace",
        ]

        # Check the TypedDict definition
        assert all(key in ParsedResult.__annotations__ for key in expected_keys)


class TestExceptionTypes:
    """Tests for exception types."""

    def test_intent_service_error_attributes(self) -> None:
        """Test IntentServiceError has correct error_code."""
        from kagami_api.services.intent_service import IntentServiceError

        error = IntentServiceError("test error")

        assert error.error_code == "INTENT_SERVICE_ERROR"
        assert str(error) == "test error"

    def test_intent_parse_error_attributes(self) -> None:
        """Test IntentParseError has correct error_code."""
        from kagami_api.services.intent_service import IntentParseError

        error = IntentParseError("parse error")

        assert error.error_code == "INTENT_PARSE_ERROR"
        assert str(error) == "parse error"

    def test_intent_parse_error_inheritance(self) -> None:
        """Test IntentParseError inherits from IntentServiceError."""
        from kagami_api.services.intent_service import IntentParseError, IntentServiceError

        assert issubclass(IntentParseError, IntentServiceError)


class TestIntentResult:
    """Tests for IntentResult dataclass."""

    def test_intent_result_success(self) -> None:
        """Test IntentResult success case."""
        from kagami_api.services.intent_service import IntentResult

        result = IntentResult(success=True, data={"key": "value"})

        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.error is None
        assert result.error_code is None

    def test_intent_result_failure(self) -> None:
        """Test IntentResult failure case."""
        from kagami_api.services.intent_service import IntentResult

        result = IntentResult(success=False, error="Something went wrong", error_code="TEST_ERROR")

        assert result.success is False
        assert result.error == "Something went wrong"
        assert result.error_code == "TEST_ERROR"
        assert result.data == {}

    def test_intent_result_default_data(self) -> None:
        """Test IntentResult defaults data to empty dict."""
        from kagami_api.services.intent_service import IntentResult

        result = IntentResult(success=True)

        assert result.data == {}
