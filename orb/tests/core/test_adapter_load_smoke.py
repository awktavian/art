from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import os
import urllib.request


@pytest.mark.slow
def test_adapter_save_load_and_forward(monkeypatch: Any, tmp_path: Any) -> None:
    # Skip when offline or HF offline mode
    if (os.getenv("TRANSFORMERS_OFFLINE") or "0").lower() in ("1", "true", "yes", "on"):
        pytest.skip("Skipping adapter smoke test: TRANSFORMERS_OFFLINE is set")

    # Minimal connectivity check to avoid OSError during from_pretrained
    try:
        urllib.request.urlopen("https://huggingface.co", timeout=2)
    except Exception as _net_err:  # pragma: no cover - environment dependent
        pytest.skip(f"Skipping adapter smoke test: no internet connectivity: {_net_err}")
    # Skip gracefully if optional transformer/peft vision deps are unavailable in this environment
    try:
        import peft
        import torch
        import transformers

        # Check torch version for CVE-2025-32434
        torch_version = tuple(map(int, torch.__version__.split(".")[:2]))
        if torch_version < (2, 6):
            pytest.skip(
                f"Skipping test: torch>=2.6 required for CVE-2025-32434 fix, got {torch.__version__}"
            )
    except Exception as _e:  # pragma: no cover - environment dependent
        pytest.skip(f"Skipping adapter smoke test: optional deps unavailable: {_e}")
    # Keep model/cache under tmp HOME to avoid polluting user cache
    monkeypatch.setenv("HOME", str(tmp_path))
    cache_dir = tmp_path / ".cache" / "hf"
    cache_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HF_HOME", str(cache_dir))
    monkeypatch.setenv("TRANSFORMERS_CACHE", str(cache_dir))
    # Force use of safetensors to avoid pickle vulnerability
    monkeypatch.setenv("SAFETENSORS_FAST_GPU", "0")

    # Lazy imports to avoid hard deps for unrelated test runs
    import torch
    from peft import LoraConfig, PeftModel, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer

    model_name = "sshleifer/tiny-gpt2"

    # Base model/tokenizer (CPU, eval) - use safetensors if available
    tok = AutoTokenizer.from_pretrained(model_name, cache_dir=str(cache_dir))
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    base = AutoModelForCausalLM.from_pretrained(
        model_name,
        cache_dir=str(cache_dir),
        use_safetensors=True,  # Prefer safetensors over pickle format
    )
    base.eval()

    # Build tiny LoRA adapter and save
    lora_cfg = LoraConfig(
        r=2,
        lora_alpha=4,
        lora_dropout=0.05,
        target_modules=["c_attn"],
        bias="none",
        task_type="CAUSAL_LM",
    )
    peft_model = get_peft_model(base, lora_cfg)
    out_dir = tmp_path / "adapter"
    peft_model.save_pretrained(str(out_dir))

    # Sanity: files exist
    assert (out_dir / "adapter_config.json").exists()
    # safetensors or bin depending on backend
    assert (out_dir / "adapter_model.safetensors").exists() or (
        out_dir / "adapter_model.bin"
    ).exists()

    # Reload base and attach adapter - use safetensors
    base2 = AutoModelForCausalLM.from_pretrained(
        model_name, cache_dir=str(cache_dir), use_safetensors=True
    )
    base2.eval()
    model_with_adapter = PeftModel.from_pretrained(base2, str(out_dir))
    model_with_adapter.eval()

    # Run a tiny forward pass
    with torch.inference_mode():
        inputs = tok("hello", return_tensors="pt")
        outputs = model_with_adapter(**inputs)
        assert hasattr(outputs, "logits")
        assert outputs.logits is not None
        b, t, v = outputs.logits.shape
        assert b == 1 and t >= 1 and v > 0
