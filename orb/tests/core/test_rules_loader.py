from __future__ import annotations


from pathlib import Path

from kagami.core.rules_loader import _split_frontmatter, get_rules_digest


def test_split_frontmatter_parses_yaml(tmp_path: Path) -> None:
    text = """---
description: X
version: 1.0.0
priority: 1
tags: [a, b]
globs: ["**/*.py"]
alwaysApply: true
---
Body
"""
    meta, body = _split_frontmatter(text)

    assert meta.get("description") == "X"
    assert meta.get("alwaysApply") in (True, "true", "1")
    assert body.strip() == "Body"


def test_rules_digest_contains_content() -> None:
    d = get_rules_digest(max_chars=2000)
    assert isinstance(d, str)
    assert len(d) > 0
