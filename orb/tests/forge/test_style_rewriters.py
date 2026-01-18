from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration


from pathlib import Path


@pytest.mark.asyncio
async def test_build_prompts_uses_machine_readable_directives(tmp_path: Path):
    # Create a minimal style guide with machine-readable block
    guide = tmp_path / "STYLE_GUIDE.md"
    guide.write_text(
        """
## Machine‑Readable Directives
```json
{
  "version": 1,
  "content_types": {
    "ui_component": {
      "core": ["UI component: flat 2D", "AA contrast"],
      "background": "pure white",
      "notes": "strict"
    }
  }
}
```
""".strip(),
        encoding="utf-8",
    )

    from kagami.forge.utils.style_rewriters import (
        build_prompts_for_content_type,
    )

    built = await build_prompts_for_content_type(
        content_type="ui_component",
        mascot_data={},
        style_engine=None,
        guide_path=guide,
    )
    assert any("UI component" in ln for ln in built.core_lines)
    assert "pure white" in built.style_prompt or built.style_prompt == ""


def test_sanitize_final_prompt_for_non_character_removes_anatomy_terms() -> None:
    from kagami.forge.utils.style_rewriters import (
        sanitize_final_prompt_for_content_type,
    )

    prompt = "Use anatomy and eyes; AA contrast; background white"
    out = sanitize_final_prompt_for_content_type(prompt, content_type="ui_component")
    assert "anatomy" not in out.lower()
    assert "eyes" not in out.lower()
    assert "aa contrast" in out.lower()


@pytest.mark.asyncio
async def test_ar_overlay_and_world_types(tmp_path: Path):
    guide = tmp_path / "STYLE_GUIDE.md"
    guide.write_text(
        """
## Machine‑Readable Directives
```json
{
  "version": 1,
  "content_types": {
    "ar_overlay": {"core": ["Overlay: labels/icons/panels only; anatomy‑free"]},
    "world": {"core": ["Scene: panoramic/room/environment; anatomy‑free"]},
    "motion": {"core": ["Motion: natural, stable, readable"]},
    "facial": {"core": ["Expressions: joy, curiosity, empathy; subtle asymmetry"]}
  }
}
```
""".strip(),
        encoding="utf-8",
    )

    from kagami.forge.utils.style_rewriters import (
        build_prompts_for_content_type,
        sanitize_final_prompt_for_content_type,
    )

    for ct in ("ar_overlay", "world", "motion", "facial"):
        built = await build_prompts_for_content_type(
            content_type=ct, mascot_data={}, style_engine=None, guide_path=guide
        )
        assert len(built.core_lines) >= 1
        out = sanitize_final_prompt_for_content_type("anatomy and eyes", content_type=ct)
        assert "anatomy" not in out.lower()
        assert "eyes" not in out.lower()
