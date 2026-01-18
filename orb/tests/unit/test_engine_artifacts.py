from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_unit


from kagami.forge.utils.engine_adapters import generate_engine_artifacts


def test_generate_engine_artifacts_includes_manifest_and_readmes() -> None:
    artifacts = generate_engine_artifacts(["unity", "unreal", "godot", "blender"])
    # Summary exists
    assert "ENGINES/README.md" in artifacts
    # Per-engine artifacts
    for e in ["unity", "unreal", "godot", "blender"]:
        assert f"ENGINES/{e}/README.md" in artifacts
        assert f"ENGINES/{e}/manifest.json" in artifacts


def test_external_template_override(tmp_path, monkeypatch) -> None:
    # Create override dir with a custom unity.md
    override_dir = tmp_path / "templates"
    override_dir.mkdir(parents=True, exist_ok=True)
    (override_dir / "unity.md").write_text("# Custom Unity Template\nLine", encoding="utf-8")
    # Point env to override dir
    monkeypatch.setenv("KAGAMI_ENGINE_TEMPLATES", str(override_dir))
    artifacts = generate_engine_artifacts(["unity"])
    readme = artifacts.get("ENGINES/unity/README.md", b"")
    assert b"Custom Unity Template" in readme
