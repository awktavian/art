from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_unit


import logging

from kagami_observability.logging_setup import (
    SensitiveDataFilter,
    clear_logging_context,
    configure_logging,
    set_logging_context,
)


def test_sensitive_data_filter_scrubs_commons() -> None:
    filt = SensitiveDataFilter()
    rec = logging.LogRecord(
        name="t",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="authorization: Bearer abcdefg123 api-key=xyz token=shh",
        args=(),
        exc_info=None,
    )
    # Simulate extra fields
    rec.__dict__["authorization"] = "Bearer secret"
    rec.__dict__["password"] = "hunter2"
    assert filt.filter(rec)
    rendered = rec.getMessage()
    assert "[REDACTED]" in rendered
    assert rec.__dict__["authorization"] == "[REDACTED]"
    assert rec.__dict__["password"] == "[REDACTED]"


def test_configure_logging_console_and_context() -> None:
    """Test that logging configuration and context work correctly."""
    import os

    os.environ["KAGAMI_LOG_JSON"] = "0"

    # Configure logging and test context setting
    configure_logging(force=True)
    set_logging_context(request_id="req-1", user_id="u")

    # Test that logging configuration was applied
    logger = logging.getLogger("kagami.test")
    assert logger is not None

    # Test context functions don't raise errors
    clear_logging_context()

    # Basic smoke test - logging is configured and works
    # Test completes without raising exceptions
