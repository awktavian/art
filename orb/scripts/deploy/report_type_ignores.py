#!/usr/bin/env python3
"""
Report type-ignore / noqa usage across the codebase.

Goal: make ignore usage visible and trackable without breaking CI.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path


PATTERNS = {
    "type_ignore": re.compile(r"#\s*type:\s*ignore\b"),
    "type_ignore_bracketed": re.compile(r"#\s*type:\s*ignore\[[^\]]+\]"),
    "noqa": re.compile(r"#\s*noqa\b"),
    "pylint_disable": re.compile(r"#\s*pylint:\s*disable\b"),
}


def iter_python_files(root: Path, changed_files_only: bool) -> list[Path]:
    if not changed_files_only:
        return sorted(root.glob("**/*.py"))

    # PR-friendly diff range if available; fallback to HEAD~1...HEAD.
    base = None
    github_base_ref = subprocess.run(
        ["bash", "-lc", "printf '%s' \"${GITHUB_BASE_REF:-}\""],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()

    if github_base_ref:
        base = f"origin/{github_base_ref}"
        subprocess.run(
            ["git", "fetch", "--no-tags", "--depth", "2", "origin", github_base_ref],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        diff_range = f"{base}...HEAD"
    else:
        diff_range = "HEAD~1...HEAD"

    out = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACMRTUXB", diff_range],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    paths = []
    for line in out.splitlines():
        p = line.strip()
        if p.endswith(".py"):
            paths.append(root / p)
    return [p for p in paths if p.exists()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--changed-files-only", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    files = iter_python_files(root, changed_files_only=args.changed_files_only)

    totals = Counter()
    by_file: dict[str, Counter] = defaultdict(Counter)

    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        for key, rx in PATTERNS.items():
            n = len(rx.findall(text))
            if n:
                totals[key] += n
                by_file[str(path.relative_to(root))][key] += n

    print("Ignore directive report")
    print("======================")
    print(f"files_scanned: {len(files)}")
    for k in sorted(totals):
        print(f"{k}: {totals[k]}")

    # Most ignore-heavy files
    score = []
    for fp, c in by_file.items():
        score.append((c["type_ignore"] + c["noqa"] + c["pylint_disable"], fp, c))
    score.sort(reverse=True)

    print("\nTop files by ignore count")
    print("-------------------------")
    for total, fp, c in score[:25]:
        print(
            f"{total:4d}  {fp}  "
            f"type:ignore={c['type_ignore']} "
            f"type:ignore[]={c['type_ignore_bracketed']} "
            f"noqa={c['noqa']} "
            f"pylint:disable={c['pylint_disable']}"
        )

    # Small, actionable signal: encourage bracketed ignores
    unbracketed = totals["type_ignore"] - totals["type_ignore_bracketed"]
    if totals["type_ignore"]:
        pct = 100.0 * (totals["type_ignore_bracketed"] / totals["type_ignore"])
        print(f"\nBracketed type:ignore ratio: {pct:.1f}% (unbracketed={unbracketed})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
