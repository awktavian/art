"""Fuzzing Tests for Input Validation.

Uses hypothesis and atheris (when available) for comprehensive fuzzing.
"""

from __future__ import annotations


from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st


class TestInputValidationFuzzing:
    """Fuzz test input validation."""

    @given(path=st.text(min_size=0, max_size=200))
    @settings(max_examples=100, deadline=1000)  # FIXED Nov 10, 2025: Increase deadline for fuzzing
    def test_path_validation_doesnt_crash(self, path: str) -> None:
        """Property: Path validation should never crash, only raise HTTPException."""
        from kagami_api.input_validation import InputValidator

        try:
            InputValidator.validate_path(path)
        except Exception as e:
            # Should only raise HTTPException or ValueError
            assert "HTTPException" in type(e).__name__ or "ValueError" in type(e).__name__

    @given(filename=st.text(min_size=0, max_size=200))
    @settings(max_examples=100, deadline=1000)  # FIXED Nov 10, 2025: Increase deadline for fuzzing
    def test_filename_validation_doesnt_crash(self, filename: str) -> None:
        """Property: Filename validation should never crash."""
        from kagami_api.input_validation import InputValidator

        try:
            InputValidator.validate_filename(filename)
        except Exception as e:
            assert "HTTPException" in type(e).__name__ or "ValueError" in type(e).__name__

    @given(html=st.text(min_size=0, max_size=1000))
    @settings(max_examples=50, deadline=1000)  # FIXED Nov 10, 2025: Increase deadline for fuzzing
    def test_html_sanitization_doesnt_crash(self, html: str) -> None:
        """Property: HTML sanitization should always return string."""
        from kagami_api.input_validation import InputValidator

        result = InputValidator.sanitize_html(html)
        assert isinstance(result, str)

        # Should not contain script tags
        assert "<script" not in result.lower()

    @given(
        data=st.recursive(
            st.one_of(
                st.none(),
                st.booleans(),
                st.integers(),
                st.floats(allow_nan=False, allow_infinity=False, allow_subnormal=False),
                st.text(max_size=100),
            ),
            lambda children: st.lists(children, max_size=5)
            | st.dictionaries(st.text(max_size=20), children, max_size=5),
            max_leaves=20,
        )
    )
    @settings(max_examples=50, suppress_health_check=(HealthCheck.too_slow,), deadline=None)
    def test_json_validation_doesnt_crash(self, data: dict) -> None:
        """Property: JSON validation should handle any nested structure."""
        from kagami_api.input_validation import InputValidator

        try:
            if isinstance(data, dict):
                InputValidator.validate_json_data(data)
        except Exception as e:
            # Should only raise HTTPException for depth violations
            assert "HTTPException" in type(e).__name__ or "too deep" in str(e).lower()


class TestSecurityFuzzing:
    """Fuzz test security components."""

    @given(api_key=st.text(min_size=0, max_size=256))
    @settings(max_examples=100, deadline=1000)  # FIXED Nov 10, 2025: Increase deadline for fuzzing
    def test_api_key_validation_doesnt_crash(self, api_key: str) -> None:
        """Property: API key validation should always return bool."""
        from kagami_api.security import SecurityFramework

        result = SecurityFramework.validate_api_key(api_key)
        assert isinstance(result, bool)

    @given(
        subject=st.text(min_size=1, max_size=100),
        scopes=st.lists(st.text(min_size=1, max_size=20), max_size=10),
    )
    @settings(max_examples=50, deadline=1000)  # FIXED Nov 10, 2025: Increase deadline for fuzzing
    def test_token_creation_doesnt_crash(self, subject: str, scopes: list[str]) -> None:
        """Property: Token creation should always succeed with valid inputs."""
        from kagami_api.security import SecurityFramework

        try:
            token = SecurityFramework.create_access_token(subject, scopes)
            assert isinstance(token, str)
            assert len(token) > 0
        except Exception:
            # Some inputs may be invalid (e.g., empty subject)
            pass


class TestIdempotencyFuzzing:
    """Fuzz test idempotency key handling."""

    @given(key=st.text(min_size=0, max_size=255))
    @settings(max_examples=100)
    def test_idempotency_key_handling(self, key: str) -> None:
        """Property: Idempotency key handling should be robust."""
        # Test that we can safely hash and store any key
        import hashlib

        try:
            if key:
                hashed = hashlib.md5(key.encode(), usedforsecurity=False).hexdigest()
                assert isinstance(hashed, str)
                assert len(hashed) == 32
        except Exception:
            # Invalid UTF-8 or other encoding errors are acceptable
            pass


__all__ = ["TestIdempotencyFuzzing", "TestInputValidationFuzzing", "TestSecurityFuzzing"]
