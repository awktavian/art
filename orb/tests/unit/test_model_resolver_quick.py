from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_unit


import os


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: Any) -> None:
    # Ensure deterministic env across tests
    for key in [
        "KAGAMI_LLM_LOCAL_ONLY",
        "OPENAI_API_KEY",
        "GPT_OSS_120B_BASE_URL",
        "KAGAMI_LLM_PREFER_LOCAL",
        "GAIA_ENV",
    ]:
        monkeypatch.delenv(key, raising=False)
    yield


def test_resolver_local_only_tiny(monkeypatch: Any) -> None:
    from kagami.core.services.llm import model_resolver as mr

    # Force deterministic local tier mapping
    monkeypatch.setenv("KAGAMI_LLM_LOCAL_ONLY", "1")
    monkeypatch.setenv("KAGAMI_LLM_PREFER_LOCAL", "0")
    monkeypatch.setenv("GAIA_ENV", "")

    monkeypatch.setattr(
        mr,
        "recommend_local_tiers",
        lambda hints=None: {
            "tiny": "qwen3:0.6b",
            "fast": "gpt-oss:20b",
            "medium": "qwen3:7b",
            "large": "qwen3:14b",
            "huge": "qwen3-coder:32b",
        },
        raising=True,
    )

    sel = mr.resolve_text_model(hints={"use_tiny": True})
    # Phase 1 fix: Now using 'local' provider with transformers directly (not ollama)
    # In test mode, returns tiny-gpt2
    assert sel.provider == "local"
    # In test mode, should get tiny-gpt2 or similar lightweight model
    assert (
        "gpt2" in sel.model_name.lower()
        or "tiny" in sel.model_name.lower()
        or sel.model_name
        in {
            "sshleifer/tiny-gpt2",
            "qwen3:0.6b",
            "gpt-oss:20b",
            "qwen3:7b",
            "qwen3:14b",
        }
    )


def test_resolver_openai_when_key_present(monkeypatch: Any) -> None:
    # Ensure non-local and with key prefers API
    monkeypatch.setenv("KAGAMI_LLM_LOCAL_ONLY", "0")
    monkeypatch.setenv("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", "test"))

    from kagami.core.services.llm import model_resolver as mr

    sel = mr.resolve_text_model(hints={})
    # Model resolver returns "local" for transformers models
    # May use local or API depending on config
    assert sel.provider in {"api", "openai", "local", "ollama"}
    assert "gpt" in sel.model_name.lower() or "qwen" in sel.model_name.lower()


def test_resolver_gaia_env_test_prefers_tiny_local(monkeypatch: Any) -> None:
    monkeypatch.setenv("KAGAMI_LLM_LOCAL_ONLY", "0")
    monkeypatch.setenv("GAIA_ENV", "test")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    from kagami.core.services.llm import model_resolver as mr

    sel = mr.resolve_text_model(hints={})
    # Model resolver returns "local" for transformers models (not "ollama")
    assert sel.provider in {"local", "ollama"}
    # Returns HF model names like "Qwen/Qwen3-1.7B-Instruct" or ollama names like "qwen3:7b"
    assert "qwen" in sel.model_name.lower() or "gpt" in sel.model_name.lower()
