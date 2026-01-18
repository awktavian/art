#!/usr/bin/env python3
"""Sync canonical prompts to Claude Code and Cursor.

CANONICAL SOURCE: kagami/core/prompts/colonies.py

This script OVERWRITES:
- .claude/agents/*.md
- .cursor/rules/{colony}.mdc

Usage:
    python scripts/hooks/sync-prompts.py [--check] [--fix]
"""

import argparse
import sys
from pathlib import Path


def get_repo_root() -> Path:
    """Get repository root directory."""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / ".git").exists():
            return parent
    return Path.cwd()


def sync_claude_code_agents(repo_root: Path, check_only: bool = False) -> list[str]:
    """Sync .claude/agents/*.md files."""
    # Add repo root to path so 'kagami' package is importable
    sys.path.insert(0, str(repo_root))
    from kagami.core.prompts.agent_system_prompts import generate_all_claude_code_agents

    agents_dir = repo_root / ".claude" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)

    changes = []
    agents = generate_all_claude_code_agents()

    for filename, content in agents.items():
        filepath = agents_dir / filename
        existing = filepath.read_text() if filepath.exists() else ""

        if existing != content:
            changes.append(str(filepath))
            if not check_only:
                filepath.write_text(content)
                print(f"  ✅ {filepath.name}")
            else:
                print(f"  ❌ {filepath.name}")

    return changes


def sync_cursor_rules(repo_root: Path, check_only: bool = False) -> list[str]:
    """Sync .cursor/rules/{colony}.mdc files — FORCE OVERWRITE."""
    # Add repo root to path so 'kagami' package is importable
    sys.path.insert(0, str(repo_root))
    from kagami.core.prompts.colonies import COLONY_PROMPTS

    rules_dir = repo_root / ".cursor" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)

    changes = []

    for name, colony in COLONY_PROMPTS.items():
        filepath = rules_dir / f"{name}.mdc"
        existing = filepath.read_text() if filepath.exists() else ""

        if existing != colony.cursor_rule:
            changes.append(str(filepath))
            if not check_only:
                filepath.write_text(colony.cursor_rule)
                print(f"  ✅ {filepath.name}")
            else:
                print(f"  ❌ {filepath.name}")

    return changes


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync canonical prompts")
    parser.add_argument("--check", action="store_true", help="Check only")
    parser.add_argument("--fix", action="store_true", help="Fix (default)")
    args = parser.parse_args()

    check_only = args.check and not args.fix
    repo_root = get_repo_root()

    print(f"🔄 Sync from kagami/core/prompts/ ({'check' if check_only else 'fix'})")
    print()

    all_changes = []

    print("Claude Code agents:")
    changes = sync_claude_code_agents(repo_root, check_only)
    all_changes.extend(changes)
    if not changes:
        print("  ✓ in sync")

    print()
    print("Cursor rules:")
    changes = sync_cursor_rules(repo_root, check_only)
    all_changes.extend(changes)
    if not changes:
        print("  ✓ in sync")

    print()
    if all_changes:
        if check_only:
            print(f"❌ {len(all_changes)} file(s) out of sync")
            return 1
        print(f"✅ {len(all_changes)} file(s) updated")
    else:
        print("✅ All in sync")

    return 0


if __name__ == "__main__":
    sys.exit(main())
