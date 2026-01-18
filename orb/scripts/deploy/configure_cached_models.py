#!/usr/bin/env python3
"""Configure K OS to use locally cached HuggingFace models.

This script scans your HuggingFace cache and generates optimal environment
configuration to use only cached models, preventing failed download attempts.

Usage:
    python scripts/setup/configure_cached_models.py

    # To apply configuration to .env:
    python scripts/setup/configure_cached_models.py --apply
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Configure K OS to use locally cached HuggingFace models"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply configuration by printing export commands",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output configuration as JSON",
    )
    args = parser.parse_args()

    try:
        from kagami.core.services.llm.cached_model_resolver import (  # noqa: F401
            get_cached_models,
            get_optimal_model_chain,
            get_recommended_env_config,
            log_available_models,
        )
    except ImportError as e:
        print(f"Error importing cached_model_resolver: {e}")
        print("Make sure you're running from the project root with venv activated")
        sys.exit(1)

    print("=" * 60)
    print("K OS Cached Model Configuration")
    print("=" * 60)
    print()

    # Show available models
    log_available_models()
    print()

    # Show optimal chain
    chain = get_optimal_model_chain()
    print("📊 Optimal Model Chain:")
    for role, model in chain.items():
        print(f"   {role:12} → {model}")
    print()

    # Get recommended config
    config = get_recommended_env_config()

    if args.json:
        import json

        print(json.dumps(config, indent=2))
        return

    print("🔧 Recommended Environment Configuration:")
    print()
    for key, value in config.items():
        print(f'export {key}="{value}"')

    if args.apply:
        print()
        print("=" * 60)
        print("To apply this configuration, run:")
        print()
        for key, value in config.items():
            print(f'export {key}="{value}"')
        print()
        print("Or add these lines to your .env file.")
    else:
        print()
        print("💡 Run with --apply to see how to apply this configuration")


if __name__ == "__main__":
    main()
