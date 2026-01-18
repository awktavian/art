
from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration


from fastapi import HTTPException

from kagami_api.input_validation import InputValidator


def test_validate_path_rejects_traversal():
    with pytest.raises(HTTPException) as exc_info:
        InputValidator.validate_path("../secrets.txt")
    assert exc_info.value.status_code == 400


def test_validate_path_absolute_outside_allowed():
    # On CI/Linux this path should be outside allowed dirs
    with pytest.raises(HTTPException) as exc_info:
        InputValidator.validate_path("/etc/passwd")
    assert exc_info.value.status_code == 400


def test_validate_filename_allows_and_blocks_extensions():
    assert InputValidator.validate_filename("notes.txt") == "notes.txt"
    with pytest.raises(HTTPException) as exc_info:
        InputValidator.validate_filename("malware.exe")
    assert exc_info.value.status_code == 400
    with pytest.raises(HTTPException) as exc_info:
        InputValidator.validate_filename("bad\x00name.txt")
    assert exc_info.value.status_code == 400


def test_sanitize_html_strips_script_and_keeps_basic_tags():
    dirty = "<script>alert(1)</script><strong>ok</strong>"
    cleaned = InputValidator.sanitize_html(dirty)
    assert "<script" not in cleaned
    assert "<strong>ok</strong>" in cleaned


def test_validate_query_params_blocks_sql_keywords():
    with pytest.raises(HTTPException) as exc_info:
        InputValidator.validate_query_params({"q": "SELECT * FROM users"})
    assert exc_info.value.status_code == 400


def test_validate_json_depth_limit():
    # Build a nested structure deeper than 10
    deep = {}
    cursor = deep
    for _i in range(12):
        cursor["k"] = {}
        cursor = cursor["k"]
    with pytest.raises(HTTPException) as exc_info:
        InputValidator.validate_json_data(deep)
    assert exc_info.value.status_code == 400
