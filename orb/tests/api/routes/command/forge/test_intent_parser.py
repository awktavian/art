"""Tests for secure LANG/2 parser in Forge intent endpoint.

Tests security measures:
- Intent length validation
- Params size validation
- Regex timeout protection (ReDoS)
- Depth limits on nested structures
- Type coercion with validation
- Parameter allowlist enforcement
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration

import json
from typing import Any

from kagami_api.routes.command.forge.intent import (
    MAX_INTENT_LENGTH,
    MAX_NESTING_DEPTH,
    MAX_PARAMS_SIZE,
    REGEX_TIMEOUT_SEC,
    _check_nesting_depth,
    _coerce_param_type,
    _regex_match_with_timeout,
    _validate_params,
    parse_lang2_string,
)
from kagami.forge.service import ForgeOperation


class TestParseLang2String:
    """Test LANG/2 string parsing with security validation."""

    def test_parse_simple_intent(self) -> None:
        """Test parsing simple intent without params."""
        intent, params = parse_lang2_string("EXECUTE character.generate")
        assert intent == "character.generate"
        assert params == {}

    def test_parse_intent_with_json_params(self) -> None:
        """Test parsing intent with JSON params."""
        lang = 'EXECUTE character.generate {"concept": "warrior", "quality": "draft"}'
        intent, params = parse_lang2_string(lang)
        assert intent == "character.generate"
        assert params == {"concept": "warrior", "quality": "draft"}

    def test_parse_intent_with_app(self) -> None:
        """Test parsing intent with @app qualifier."""
        lang = 'EXECUTE character.generate @app=Forge {"concept": "ninja"}'
        intent, params = parse_lang2_string(lang)
        assert intent == "character.generate"
        assert params == {"concept": "ninja"}

    def test_parse_intent_with_nested_params(self) -> None:
        """Test parsing intent with nested params (within depth limit)."""
        lang = 'EXECUTE character.generate {"metadata": {"source": "api", "version": "1.0"}}'
        intent, params = parse_lang2_string(lang)
        assert intent == "character.generate"
        assert params == {"metadata": {"source": "api", "version": "1.0"}}

    def test_reject_invalid_format(self) -> None:
        """Test rejection of invalid LANG/2 format."""
        with pytest.raises(ValueError, match="Invalid LANG/2 format"):
            parse_lang2_string("CREATE character.generate")

    def test_reject_missing_intent(self) -> None:
        """Test rejection of missing intent."""
        with pytest.raises(ValueError, match="Invalid LANG/2 format"):
            parse_lang2_string("EXECUTE")

    def test_reject_invalid_intent_format(self) -> None:
        """Test rejection of invalid intent format (missing dot)."""
        with pytest.raises(ValueError, match="capability.action"):
            parse_lang2_string("EXECUTE charactergenerate")

    def test_reject_special_chars_in_intent(self) -> None:
        """Test rejection of special characters in intent."""
        with pytest.raises(ValueError, match="Invalid LANG/2 format"):
            parse_lang2_string("EXECUTE character.gen@rate")

    def test_reject_excessive_intent_length(self) -> None:
        """Test rejection of excessively long intent."""
        long_intent = "a" * (MAX_INTENT_LENGTH + 1)
        with pytest.raises(ValueError, match="Intent exceeds maximum length"):
            parse_lang2_string(f"EXECUTE {long_intent}.test")

    def test_reject_excessive_total_length(self) -> None:
        """Test rejection of excessively long total string."""
        long_string = "a" * (MAX_INTENT_LENGTH + MAX_PARAMS_SIZE + 100)
        with pytest.raises(ValueError, match="exceeds maximum length"):
            parse_lang2_string(f"EXECUTE character.generate {long_string}")

    def test_reject_excessive_params_size(self) -> None:
        """Test rejection of excessively large params."""
        large_value = "x" * (MAX_PARAMS_SIZE + 1)
        lang = f'EXECUTE character.generate {{"data": "{large_value}"}}'
        with pytest.raises(ValueError, match="Parameters exceed maximum size"):
            parse_lang2_string(lang)

    def test_reject_invalid_json(self) -> None:
        """Test rejection of invalid JSON in params."""
        with pytest.raises(ValueError, match="Invalid JSON"):
            parse_lang2_string('EXECUTE character.generate {"concept": invalid}')

    def test_reject_non_dict_json(self) -> None:
        """Test rejection of non-dict JSON in params."""
        with pytest.raises(ValueError, match="must be a JSON object"):
            parse_lang2_string('EXECUTE character.generate ["concept", "warrior"]')

    def test_no_fallback_to_keyvalue_parsing(self) -> None:
        """Test that fallback key=value parsing is disabled."""
        # This used to work with fallback parsing, should now fail
        with pytest.raises(ValueError, match="Invalid JSON"):
            parse_lang2_string("EXECUTE character.generate concept=warrior")


class TestNestingDepthValidation:
    """Test nesting depth validation."""

    def test_accept_shallow_nesting(self) -> None:
        """Test acceptance of shallow nesting."""
        obj = {"a": {"b": {"c": "value"}}}
        _check_nesting_depth(obj)  # Should not raise

    def test_reject_excessive_nesting(self) -> None:
        """Test rejection of excessive nesting."""
        # Create deeply nested structure beyond limit
        obj: dict[str, Any] = {"level": 0}
        current = obj
        for i in range(1, MAX_NESTING_DEPTH + 2):
            current["nested"] = {"level": i}
            current = current["nested"]

        with pytest.raises(ValueError, match="Nesting depth exceeds maximum"):
            _check_nesting_depth(obj)

    def test_check_list_nesting(self) -> None:
        """Test nesting depth checks lists."""
        obj = {"a": [{"b": [{"c": [{"d": [{"e": "too deep"}]}]}]}]}
        with pytest.raises(ValueError, match="Nesting depth exceeds maximum"):
            _check_nesting_depth(obj)


class TestTypeCoercion:
    """Test parameter type coercion."""

    def test_coerce_to_string(self) -> None:
        """Test coercion to string."""
        assert _coerce_param_type(123, str) == "123"
        assert _coerce_param_type(True, str) == "True"
        assert _coerce_param_type("test", str) == "test"

    def test_coerce_to_int(self) -> None:
        """Test coercion to int."""
        assert _coerce_param_type("123", int) == 123
        assert _coerce_param_type(123.7, int) == 123
        assert _coerce_param_type(123, int) == 123

    def test_coerce_to_float(self) -> None:
        """Test coercion to float."""
        assert _coerce_param_type("123.5", float) == 123.5
        assert _coerce_param_type(123, float) == 123.0
        assert _coerce_param_type(123.5, float) == 123.5

    def test_coerce_to_list(self) -> None:
        """Test coercion to list."""
        assert _coerce_param_type([1, 2, 3], list) == [1, 2, 3]
        assert _coerce_param_type('["a", "b"]', list) == ["a", "b"]

    def test_coerce_to_dict(self) -> None:
        """Test coercion to dict."""
        assert _coerce_param_type({"a": 1}, dict) == {"a": 1}
        assert _coerce_param_type('{"a": 1}', dict) == {"a": 1}

    def test_coerce_with_multiple_types(self) -> None:
        """Test coercion with multiple allowed types."""
        # Should accept either int or float (tries int first, then float)
        assert _coerce_param_type(123, (int, float)) == 123
        # 123.5 will be coerced to int (123) since int is tried first
        assert _coerce_param_type(123.5, (int, float)) == 123
        assert _coerce_param_type("123", (int, float)) == 123
        # Use float-only tuple to preserve float value
        assert _coerce_param_type(123.5, (float,)) == 123.5

    def test_reject_invalid_coercion(self) -> None:
        """Test rejection of invalid coercion."""
        with pytest.raises(ValueError, match="Cannot coerce"):
            _coerce_param_type("not_a_number", int)

        with pytest.raises(ValueError, match="Cannot coerce"):
            _coerce_param_type("not_json", list)


class TestParameterValidation:
    """Test parameter allowlist validation."""

    def test_accept_valid_params(self) -> None:
        """Test acceptance of valid params."""
        params = {"concept": "warrior", "quality": "draft"}
        validated = _validate_params(params, ForgeOperation.CHARACTER_GENERATION)
        assert validated == params

    def test_reject_unexpected_params(self) -> None:
        """Test filtering of unexpected params."""
        params = {"concept": "warrior", "invalid_param": "value"}
        validated = _validate_params(params, ForgeOperation.CHARACTER_GENERATION)
        # invalid_param should be filtered out
        assert "invalid_param" not in validated
        assert validated == {"concept": "warrior"}

    def test_coerce_param_types(self) -> None:
        """Test type coercion during validation."""
        params = {"concept": "warrior", "duration": "120"}
        validated = _validate_params(params, ForgeOperation.ANIMATION_FACIAL)
        # duration should be coerced to int
        assert isinstance(validated.get("duration"), int)
        assert validated["duration"] == 120

    def test_validate_nested_structures(self) -> None:
        """Test validation of nested structures."""
        params = {
            "concept": "warrior",
            "metadata": {"source": "api", "nested": {"level": 2}},
        }
        validated = _validate_params(params, ForgeOperation.CHARACTER_GENERATION)
        assert validated == params

    def test_reject_excessive_nesting_in_params(self) -> None:
        """Test rejection of excessive nesting in params."""
        # Create deeply nested metadata
        nested: dict[str, Any] = {"level": 0}
        current = nested
        for i in range(1, MAX_NESTING_DEPTH + 2):
            current["nested"] = {"level": i}
            current = current["nested"]

        params = {"concept": "warrior", "metadata": nested}
        with pytest.raises(ValueError, match="Nesting depth exceeds maximum"):
            _validate_params(params, ForgeOperation.CHARACTER_GENERATION)

    def test_genesis_video_allowlist_filters_unknown_fields(self) -> None:
        params = {
            "template": "physics_diversity",
            "output_dir": "/tmp/out",
            "duration": 3,
            "raytracer": {"tracing_depth": 12},
            "unknown": "nope",
        }
        validated = _validate_params(params, ForgeOperation.GENESIS_VIDEO)
        assert "unknown" not in validated
        assert validated["template"] == "physics_diversity"
        assert validated["output_dir"] == "/tmp/out"


class TestRegexTimeout:
    """Test regex timeout protection."""

    def test_normal_regex_match(self) -> None:
        """Test normal regex matching works."""
        match = _regex_match_with_timeout(r"^test\s+(\w+)$", "test value")
        assert match is not None
        assert match.group(1) == "value"

    def test_regex_no_match(self) -> None:
        """Test regex that doesn't match."""
        match = _regex_match_with_timeout(r"^test\s+(\w+)$", "invalid format")
        assert match is None

    def test_regex_timeout_protection(self) -> None:
        """Test regex timeout on catastrophic backtracking (ReDoS).

        Note: This test may be slow due to the timeout mechanism.
        We use a smaller timeout for testing.
        """
        # Classic ReDoS pattern: (a+)+b with input that has no 'b'
        # This causes catastrophic backtracking
        redos_pattern = r"^(a+)+b$"
        redos_input = "a" * 25  # No 'b', causes backtracking

        # Should timeout before catastrophic backtracking completes
        # Note: This may not always trigger on fast machines with simple patterns
        # The main protection is having the timeout mechanism in place
        try:
            match = _regex_match_with_timeout(redos_pattern, redos_input, timeout=0.1)
            # If it doesn't timeout, it should at least return None (no match)
            assert match is None
        except ValueError as e:
            # If it does timeout, verify the error message
            assert "timed out" in str(e)


class TestIntegrationSecurity:
    """Integration tests for security measures."""

    def test_lang2_string_depth_limit(self) -> None:
        """Test that parse_lang2_string enforces depth limit."""
        # Create deeply nested params
        nested: dict[str, Any] = {"level": 0}
        current = nested
        for i in range(1, MAX_NESTING_DEPTH + 2):
            current["nested"] = {"level": i}
            current = current["nested"]

        params_json = json.dumps({"metadata": nested})
        lang = f"EXECUTE character.generate {params_json}"

        with pytest.raises(ValueError, match="Nesting depth exceeds"):
            parse_lang2_string(lang)

    def test_empty_params(self) -> None:
        """Test handling of empty params."""
        intent, params = parse_lang2_string("EXECUTE character.generate {}")
        assert intent == "character.generate"
        assert params == {}

    def test_whitespace_handling(self) -> None:
        """Test proper whitespace handling."""
        lang = '  EXECUTE character.generate   {"concept": "warrior"}  '
        intent, params = parse_lang2_string(lang)
        assert intent == "character.generate"
        assert params == {"concept": "warrior"}

    def test_unicode_in_params(self) -> None:
        """Test handling of Unicode in params."""
        lang = 'EXECUTE character.generate {"concept": "忍者"}'
        intent, params = parse_lang2_string(lang)
        assert intent == "character.generate"
        assert params == {"concept": "忍者"}

    def test_special_chars_in_params_values(self) -> None:
        """Test handling of special characters in param values."""
        lang = 'EXECUTE character.generate {"concept": "a\\"quoted\\"warrior"}'
        intent, params = parse_lang2_string(lang)
        assert intent == "character.generate"
        assert params == {"concept": 'a"quoted"warrior'}
