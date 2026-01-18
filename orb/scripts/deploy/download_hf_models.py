#!/usr/bin/env python3
"""Download and cache HuggingFace models used by K os llm_service.

K os uses Qwen3 model family (2025 flagship series) exclusively.
See kagami/core/services/llm/model_resolver.py for model selection logic.

Usage:
    python scripts/setup/download_hf_models.py --set minimal
    python scripts/setup/download_hf_models.py --set recommended
    python scripts/setup/download_hf_models.py --set all
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

from huggingface_hub import snapshot_download

# Qwen3 model sets - ACTUAL AVAILABLE MODELS (verified Jan 2025)
# Based on https://huggingface.co/collections/Qwen/qwen3-coder
# and HuggingFace API search results
MODEL_SETS = {
    "minimal": {
        "models": [
            "Qwen/Qwen3-0.6B",  # Tiny tier (~1.2GB)
            "Qwen/Qwen3-Embedding-0.6B",  # Embedding model (~1.2GB)
        ],
        "total_size_gb": 2.4,
    },
    "recommended": {
        "models": [
            "Qwen/Qwen3-1.7B",  # Fast tier (~3.4GB)
            "Qwen/Qwen3-14B",  # Standard tier (~28GB)
            "Qwen/Qwen3-Coder-30B-A3B-Instruct",  # Code MoE (~18GB, 3B active)
            "Qwen/Qwen2.5-VL-7B-Instruct",  # Vision (~14GB)
            "Qwen/Qwen3-Embedding-4B",  # Embedding model (~8GB)
        ],
        "total_size_gb": 71,
    },
    "all": {
        "models": [
            # General + coding + embeddings (<= ~110GB total)
            "Qwen/Qwen3-0.6B",
            "Qwen/Qwen3-1.7B",
            "Qwen/Qwen3-14B",
            "Qwen/Qwen3-Coder-30B-A3B-Instruct",
            "Qwen/Qwen2.5-VL-7B-Instruct",
            "Qwen/Qwen3-Embedding-0.6B",
            "Qwen/Qwen3-Embedding-4B",
            "Qwen/Qwen3-Embedding-8B",
        ],
        "total_size_gb": 110,
    },
    "extreme": {
        "models": [
            # Optional ultra-heavy research models (multi-hundred GB)
            "deepseek-ai/DeepSeek-V3.2-Exp",  # ~685B MoE (requires multi-GPU vLLM/SGLang)
            "Qwen/Qwen3-32B",  # ~64GB
            "Qwen/Qwen3-235B-A22B",  # ~140GB
            "Qwen/Qwen3-Coder-480B-A35B-Instruct",  # ~280GB
        ],
        "total_size_gb": 484 + 700,  # ballpark (DeepSeek-V3.2-Exp is extremely large)
    },
}

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "huggingface"
ENV_CACHE_VAR = "KAGAMI_HF_CACHE_DIR"
DISK_BUFFER_RATIO = 0.15
DISK_BUFFER_ABSOLUTE_GB = 25.0


def _bytes_to_gb(value: int) -> float:
    return value / (1024**3)


def resolve_cache_dir(cli_value: Path | None) -> Path:
    """Resolve the on-disk cache directory for HuggingFace snapshots."""

    if cli_value is not None:
        return cli_value.expanduser()

    env_override = os.environ.get(ENV_CACHE_VAR)
    if env_override:
        return Path(env_override).expanduser()

    hf_home = os.environ.get("HF_HOME")
    if hf_home:
        return Path(hf_home).expanduser()

    hf_hub_cache = os.environ.get("HF_HUB_CACHE")
    if hf_hub_cache:
        return Path(hf_hub_cache).expanduser()

    return DEFAULT_CACHE_DIR


def ensure_disk_headroom(cache_dir: Path, estimated_gb: float) -> tuple[float, float]:
    """Verify that the destination filesystem has enough free space."""

    cache_dir.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(cache_dir)
    free_gb = _bytes_to_gb(usage.free)
    required_gb = estimated_gb * (1 + DISK_BUFFER_RATIO) + DISK_BUFFER_ABSOLUTE_GB

    if free_gb < required_gb:
        print(f"❌ Not enough free space at {cache_dir}")
        print(f"   Required (estimate + buffer): ~{required_gb:.1f}GB, available: {free_gb:.1f}GB")
        print("   Tip: set KAGAMI_HF_CACHE_DIR or HF_HOME to an external drive,")
        print("        or run a smaller set (make hf-reco / make hf-minimal).")
        sys.exit(1)

    return required_gb, free_gb


def download_models(model_set: str, cache_dir: Path) -> None:
    """Download specified model set to HuggingFace cache.

    Args:
        model_set: One of 'minimal', 'recommended', 'all'
        cache_dir: Target cache directory (will be created if missing)
    """
    if model_set not in MODEL_SETS:
        print(f"❌ Invalid model set: {model_set}")
        print(f"   Valid options: {', '.join(MODEL_SETS.keys())}")
        sys.exit(1)

    config = MODEL_SETS[model_set]
    models = config["models"]
    total_size = config["total_size_gb"]

    print(f"📦 Downloading {model_set} model set ({len(models)} models, ~{total_size}GB)")  # type: ignore[arg-type]
    print(f"   Cache dir: {cache_dir}")
    print()

    required_gb, free_gb = ensure_disk_headroom(cache_dir, total_size)  # type: ignore[arg-type]
    print(f"   Required free space (with buffer): ~{required_gb:.1f}GB")
    print(f"   Free space detected: ~{free_gb:.1f}GB")
    print()

    for i, model_id in enumerate(models, 1):  # type: ignore[arg-type]
        print(f"[{i}/{len(models)}] Downloading {model_id}...")  # type: ignore[arg-type]
        try:
            snapshot_download(
                model_id,
                cache_dir=str(cache_dir),
                local_dir_use_symlinks=False,
            )
            print(f"✅ {model_id}")
        except Exception as e:
            print(f"❌ Failed to download {model_id}: {e}")
            sys.exit(1)
        print()

    print(f"✅ All {len(models)} models downloaded successfully!")  # type: ignore[arg-type]
    print(f"   Total size: ~{total_size}GB")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download HuggingFace models for K os llm_service")
    parser.add_argument(
        "--set",
        choices=["minimal", "recommended", "all", "extreme"],
        required=True,
        help="Model set to download",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        help=(
            "Custom cache directory. Defaults to KAGAMI_HF_CACHE_DIR, "
            "then HF_HOME/HF_HUB_CACHE, then ~/.cache/huggingface."
        ),
    )

    args = parser.parse_args()

    # Show what will be downloaded
    config = MODEL_SETS[args.set]
    print(f"Model Set: {args.set}")
    print(f"Models ({len(config['models'])}):")  # type: ignore[arg-type]
    for model in config["models"]:
        print(f"  - {model}")
    print(f"Estimated total: ~{config['total_size_gb']}GB")
    print()

    response = input("Continue? [y/N] ")
    if response.lower() != "y":
        print("Cancelled.")
        sys.exit(0)

    cache_dir = resolve_cache_dir(args.cache_dir)
    download_models(args.set, cache_dir)


if __name__ == "__main__":
    main()
