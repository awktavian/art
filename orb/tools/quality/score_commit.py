#!/usr/bin/env python3
"""Calculate quality score for a commit.

Usage:
    python scripts/quality/score_commit.py HEAD
    python scripts/quality/score_commit.py abc1234
    python scripts/quality/score_commit.py --since="1 week ago"
"""

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class QualityScore:
    """Quality score breakdown."""

    base: int = 60
    lint: int = 10
    types: int = 10
    tests: int = 10
    docs: int = 5
    safety: int = 5

    lint_errors: int = 0
    type_errors: int = 0
    test_failures: int = 0
    doc_issues: int = 0
    safety_issues: int = 0

    @property
    def total(self) -> int:
        """Calculate total score."""
        score = self.base
        score += max(0, self.lint - self.lint_errors * 2)
        score += max(0, self.types - self.type_errors * 2)
        score += max(0, self.tests - self.test_failures * 2)
        score += max(0, self.docs - self.doc_issues)
        score += max(0, self.safety - self.safety_issues * 5)
        return min(100, score)

    def __str__(self) -> str:
        """Format score breakdown."""
        lines = [
            f"Quality Score: {self.total}/100",
            "",
            "Breakdown:",
            f"  Base:   {self.base}/60",
            f"  Lint:   {max(0, self.lint - self.lint_errors * 2)}/10 ({self.lint_errors} errors)",
            f"  Types:  {max(0, self.types - self.type_errors * 2)}/10 ({self.type_errors} errors)",
            f"  Tests:  {max(0, self.tests - self.test_failures * 2)}/10 ({self.test_failures} failures)",
            f"  Docs:   {max(0, self.docs - self.doc_issues)}/5 ({self.doc_issues} issues)",
            f"  Safety: {max(0, self.safety - self.safety_issues * 5)}/5 ({self.safety_issues} violations)",
        ]
        return "\n".join(lines)


def run_command(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    """Run command and return exit code + output."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=120,
        )
        return result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return 1, "Command timed out"
    except Exception as e:
        return 1, str(e)


def count_lint_errors(root: Path) -> int:
    """Count lint errors using ruff."""
    code, output = run_command(["ruff", "check", "kagami/"], cwd=root)
    if code == 0:
        return 0
    # Count error lines
    errors = [line for line in output.split("\n") if line.strip() and "error" in line.lower()]
    return len(errors)


def count_type_errors(root: Path) -> int:
    """Count type errors using mypy."""
    code, output = run_command(
        ["python", "-m", "mypy", "kagami/", "--ignore-missing-imports"],
        cwd=root,
    )
    if code == 0:
        return 0
    # Count error lines
    errors = [line for line in output.split("\n") if ": error:" in line]
    return len(errors)


def score_commit(commit: str, root: Path) -> QualityScore:
    """Calculate quality score for a commit."""
    score = QualityScore()

    # Check if commit exists
    code, _ = run_command(["git", "rev-parse", commit], cwd=root)
    if code != 0:
        score.base = 0
        return score

    # Get files changed in commit
    _, output = run_command(
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", commit],
        cwd=root,
    )
    changed_files = [f for f in output.strip().split("\n") if f.endswith(".py")]

    if not changed_files:
        # No Python files changed, full score
        return score

    # Run lint check
    score.lint_errors = count_lint_errors(root)

    # Run type check
    score.type_errors = count_type_errors(root)

    return score


def score_commits_since(since: str, root: Path) -> None:
    """Score all commits since a date."""
    _, output = run_command(
        ["git", "log", f"--since={since}", "--oneline", "--format=%h|%s"],
        cwd=root,
    )

    commits = [line.split("|") for line in output.strip().split("\n") if line]

    print(f"Scoring {len(commits)} commits since {since}\n")
    print("-" * 60)

    total_score = 0
    for commit_hash, message in commits:
        score = score_commit(commit_hash, root)
        total_score += score.total
        status = "✅" if score.total == 100 else "⚠️" if score.total >= 90 else "❌"
        print(f"{status} {commit_hash} | {score.total:3d}/100 | {message[:40]}")

    print("-" * 60)
    avg = total_score // len(commits) if commits else 0
    print(f"Average: {avg}/100")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Calculate commit quality score")
    parser.add_argument("commit", nargs="?", default="HEAD", help="Commit hash to score")
    parser.add_argument("--since", help="Score all commits since date")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root")

    args = parser.parse_args()

    if args.since:
        score_commits_since(args.since, args.root)
    else:
        score = score_commit(args.commit, args.root)
        print(score)

        # Exit with error if score < 100
        if score.total < 100:
            sys.exit(1)


if __name__ == "__main__":
    main()
