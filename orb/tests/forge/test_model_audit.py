from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import json
from pathlib import Path


def _parse_ollama_list_models() -> list[str]:
    import subprocess

    try:
        res = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        lines = [ln.strip() for ln in (res.stdout or "").splitlines() if ln.strip()]
        models: list[str] = []
        for ln in lines:
            if ln.lower().startswith("name ") or ln.lower().startswith("name\t"):
                continue
            parts = ln.split()
            if parts:
                name = parts[0].strip()
                if name and name not in models:
                    models.append(name)
        return models
    except Exception:
        return []


def test_audit_creates_json(tmp_path: Any, monkeypatch: Any) -> None:
    out_dir = tmp_path / "style_enforced_output"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Redirect output path by chdir
    monkeypatch.chdir(tmp_path)

    # Mock inventory helpers to avoid relying on local ollama
    import kagami.forge.modules.visual_design.model_audit as audit

    available = _parse_ollama_list_models()
    if not available:
        available = ["qwen3:1.7b", "qwen3:7b", "gpt-oss:20b"]

    monkeypatch.setattr(audit, "_inventory_cli_table", lambda: available)
    monkeypatch.setattr(audit, "_inventory_cli_json", lambda: [])
    monkeypatch.setattr(audit, "_inventory_http_tags", lambda: available)
    monkeypatch.setattr(
        audit,
        "_fs_probe",
        lambda: {
            "/home/user/.ollama/models/tags": {
                "tags_count": 1,
                "manifests_count": 1,
                "blobs_count": 1,
            }
        },
    )

    # Mock measurement to be fast and deterministic
    def _fake_measure(model: Any, prompt: Any, timeout_s: Any = 90.0) -> None:
        class R:
            def __init__(self, d: Any) -> Any:
                self.duration_ms = d
                self.exit_code = 0
                self.stdout = f"- {model} OK\n- words present\n- more"
                self.stderr = ""
                self.timed_out = False

        base = 100 if model == "qwen3:1.7b" else 150
        return R(base)

    monkeypatch.setattr(audit, "_measure_model", _fake_measure)

    result = audit.run_local_model_audit()
    assert "selected" in result
    assert Path("style_enforced_output/model_audit.json").exists()

    data = json.loads(Path("style_enforced_output/model_audit.json").read_text())
    assert data["selected"]
    assert sorted(data["reconciled_models"]) == sorted(set(available))


def test_dashboard_renders_with_minimal_json(tmp_path: Any, monkeypatch: Any) -> None:
    # Prepare minimal JSON
    out_dir = tmp_path / "style_enforced_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(tmp_path)

    data = {
        "env": {"OLLAMA_HOST": "http://localhost:11434", "ollama_version": "0.1"},
        "reconciled_models": ["qwen3:1.7b"],
        "telemetry": {
            "qwen3:1.7b": {
                "p50": 120,
                "p95": 180,
                "avg_words": 30,
                "quality": "good",
                "excerpt": "- ok",
            }
        },
        "selected": ["qwen3:1.7b"],
        "rejected": [],
        "errors": [],
    }
    (out_dir / "model_audit.json").write_text(json.dumps(data))

    from kagami.forge.modules.visual_design.model_audit_dashboard import (
        render_model_audit_dashboard_png,
    )

    out = render_model_audit_dashboard_png()
    assert Path(out).exists()
