#!/usr/bin/env python3
"""Colony Coordination Script

Helps colonies coordinate work by:
1. Detecting active branches per colony
2. Identifying potential file conflicts
3. Suggesting available work based on colony specialty
4. Checking issue status and assignments

Colony System (7 Octonion Imaginary Basis):
    Spark (e₁):  Creativity, divergence
    Forge (e₂):  Features, implementation
    Flow (e₃):   Recovery, maintenance
    Nexus (e₄):  Integration, memory
    Beacon (e₅): Architecture, planning
    Grove (e₆):  Research, documentation
    Crystal (e₇): Testing, verification

Usage:
    python scripts/ops/agent_coordinator.py --colony crystal
    python scripts/ops/agent_coordinator.py --check-conflicts path/to/file.py
    python scripts/ops/agent_coordinator.py --suggest-work
"""

import argparse
import subprocess
import sys
from collections import defaultdict
from typing import Any

try:
    import requests
except ImportError:
    print("Error: requests library required. Install with: pip install requests")
    sys.exit(1)


# Colony specialties (mapped to octonion imaginary basis e₁-e₇)
COLONY_SPECIALTIES = {
    "spark": {  # e₁ - Fold (A₂) - Creativity
        "primary_paths": ["kagami/core/fractal_agents/", "kagami/core/creative/"],
        "keywords": ["creative", "novel", "brainstorm", "diverge", "generate"],
        "file_patterns": ["*.py"],
    },
    "forge": {  # e₂ - Cusp (A₃) - Implementation
        "primary_paths": [
            "kagami_api/routes/",
            "kagami/core/services/",
            "kagami/core/unified_agents/",
        ],
        "keywords": ["feature", "api", "endpoint", "integration", "implement"],
        "file_patterns": ["routes/*.py", "services/*.py"],
    },
    "flow": {  # e₃ - Swallowtail (A₄) - Recovery
        "primary_paths": ["kagami/", "tests/"],  # Can work anywhere for fixes
        "keywords": ["bug", "fix", "error", "crash", "hotfix", "emergency", "maintenance"],
        "file_patterns": ["*.py"],
    },
    "nexus": {  # e₄ - Butterfly (A₅) - Integration
        "primary_paths": ["kagami/core/receipts/", "kagami/memory/", "kagami_integrations/"],
        "keywords": ["memory", "integrate", "connect", "receipt", "coherence"],
        "file_patterns": ["*.py"],
    },
    "beacon": {  # e₅ - Hyperbolic (D₄⁺) - Architecture
        "primary_paths": ["kagami/__init__.py", "kagami/**/__init__.py", "docs/architecture/"],
        "keywords": ["architecture", "refactor", "circular", "dependency", "design", "plan"],
        "file_patterns": ["*.py"],
    },
    "grove": {  # e₆ - Elliptic (D₄⁻) - Research/Documentation
        "primary_paths": ["docs/", "README.md", "CHANGELOG.md", "examples/"],
        "keywords": ["docs", "documentation", "guide", "tutorial", "example", "research"],
        "file_patterns": ["*.md", "*.rst"],
    },
    "crystal": {  # e₇ - Parabolic (D₅) - Verification
        "primary_paths": ["tests/", "pytest.ini", "conftest.py", ".github/workflows/ci.yml"],
        "keywords": ["test", "coverage", "flaky", "ci", "quality", "verify", "safety"],
        "file_patterns": ["test_*.py", "*_test.py"],
    },
}


def run_command(cmd: list[str]) -> tuple[int, str, str]:
    """Run shell command and return (returncode, stdout, stderr)."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def get_active_branches() -> dict[str, list[str]]:
    """Get all active colony branches grouped by colony."""
    returncode, stdout, stderr = run_command(["git", "branch", "-r"])

    if returncode != 0:
        print(f"Error getting branches: {stderr}")
        return {}

    colony_branches = defaultdict(list)
    for line in stdout.split("\n"):
        line = line.strip()
        if not line or "->" in line:  # Skip HEAD pointer
            continue

        # Extract branch name
        branch = line.split("/")[-1] if "/" in line else line

        # Check if it's a colony branch
        for name in COLONY_SPECIALTIES:
            if branch.startswith(f"{name}/"):
                colony_branches[name].append(branch)
                break

    return dict(colony_branches)


def get_files_in_branch(branch: str) -> list[str]:
    """Get list of files modified in a branch."""
    # Get common ancestor with main
    returncode, stdout, _stderr = run_command(["git", "merge-base", branch, "main"])

    if returncode != 0:
        return []

    base_commit = stdout.strip()

    # Get files changed since base
    returncode, stdout, _stderr = run_command(["git", "diff", "--name-only", base_commit, branch])

    if returncode != 0:
        return []

    return [f.strip() for f in stdout.split("\n") if f.strip()]


def check_file_conflicts(target_file: str, colony: str | None = None) -> dict[str, Any]:
    """Check if file has conflicts with other colonies' work."""
    active_branches = get_active_branches()
    conflicts = []

    for other_colony, branches in active_branches.items():
        if colony and other_colony == colony.lower():
            continue  # Skip own branches

        for branch in branches:
            files = get_files_in_branch(branch)
            if target_file in files:
                conflicts.append({"colony": other_colony, "branch": branch, "file": target_file})

    return {"file": target_file, "has_conflicts": len(conflicts) > 0, "conflicts": conflicts}


def get_github_issues(colony: str | None = None, status: str = "open") -> list[dict]:
    """Get GitHub issues (requires GITHUB_TOKEN env var)."""
    import os

    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return []

    # Determine repo from git remote
    returncode, stdout, _stderr = run_command(["git", "remote", "get-url", "origin"])
    if returncode != 0:
        return []

    remote_url = stdout.strip()
    # Extract owner/repo from URL
    if "github.com" in remote_url:
        parts = remote_url.split("github.com")[-1].strip("/:").replace(".git", "").split("/")
        if len(parts) >= 2:
            owner, repo = parts[0], parts[1]
        else:
            return []
    else:
        return []

    # Build query
    query = f"repo:{owner}/{repo} is:issue is:{status}"
    if colony:
        query += f" label:colony:{colony.lower()}"

    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}

    url = "https://api.github.com/search/issues"
    params = {"q": query, "per_page": 100}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)  # type: ignore[arg-type]
        if response.status_code == 200:
            return response.json().get("items", [])
    except Exception as e:
        print(f"Error fetching issues: {e}")

    return []


def suggest_work_for_colony(colony: str) -> dict[str, Any]:
    """Suggest work items for a colony based on their specialty."""
    colony_lower = colony.lower()
    specialty = COLONY_SPECIALTIES.get(colony_lower, {})

    # Get open issues for this colony
    issues = get_github_issues(colony=colony_lower, status="open")

    # Filter by status:ready if possible
    ready_issues = [
        i for i in issues if any(label["name"] == "status:ready" for label in i.get("labels", []))
    ]

    if not ready_issues:
        ready_issues = [
            i
            for i in issues
            if not any(label["name"] == "status:in-progress" for label in i.get("labels", []))
        ]

    return {
        "colony": colony_lower,
        "total_issues": len(issues),
        "ready_issues": len(ready_issues),
        "suggested_issues": ready_issues[:5],  # Top 5
        "specialty": specialty,
    }


def main():
    colony_names = list(COLONY_SPECIALTIES.keys())

    parser = argparse.ArgumentParser(description="Colony coordination helper (K OS)")
    parser.add_argument("--colony", choices=colony_names, help="Colony name")
    parser.add_argument(
        "--check-conflicts", metavar="FILE", help="Check if file has conflicts with other colonies"
    )
    parser.add_argument("--suggest-work", action="store_true", help="Suggest work for colony")
    parser.add_argument(
        "--list-branches", action="store_true", help="List all active colony branches"
    )
    parser.add_argument("--status", action="store_true", help="Show overall coordination status")

    args = parser.parse_args()

    colony = args.colony

    # List branches
    if args.list_branches:
        print("Active Colony Branches:")
        print("=" * 50)
        active_branches = get_active_branches()
        if not active_branches:
            print("No active colony branches found.")
        else:
            for col, branches in active_branches.items():
                print(f"\n{col.upper()} (e{list(COLONY_SPECIALTIES.keys()).index(col) + 1}):")
                for branch in branches:
                    print(f"  - {branch}")
        return

    # Check file conflicts
    if args.check_conflicts:
        result = check_file_conflicts(args.check_conflicts, colony)
        print(f"File Conflict Check: {result['file']}")
        print("=" * 50)
        if result["has_conflicts"]:
            print(
                f"⚠️  CONFLICTS DETECTED ({len(result['conflicts'])} colonies working on this file)"
            )
            for conflict in result["conflicts"]:
                print(f"\n  Colony: {conflict['colony']}")
                print(f"  Branch: {conflict['branch']}")
                print(f"  File: {conflict['file']}")
            print("\n⚡ ACTION REQUIRED: Coordinate with other colonies before proceeding")
            print("   Tag them in your issue or create coordination issue.")
        else:
            print("✅ No conflicts detected. Safe to proceed.")
        return

    # Suggest work
    if args.suggest_work:
        if not colony:
            print("Error: --colony required with --suggest-work")
            sys.exit(1)

        result = suggest_work_for_colony(colony)
        print(f"Work Suggestions for {result['colony'].upper()}")
        print("=" * 50)
        print(f"Total open issues: {result['total_issues']}")
        print(f"Ready to work: {result['ready_issues']}")

        if result["suggested_issues"]:
            print("\nSuggested Issues:")
            for i, issue in enumerate(result["suggested_issues"], 1):
                labels = ", ".join(l["name"] for l in issue.get("labels", []))
                print(f"\n{i}. #{issue['number']}: {issue['title']}")
                print(f"   Labels: {labels}")
                print(f"   URL: {issue['html_url']}")
        else:
            print("\n✅ No ready issues found. Check with team for new work.")
        return

    # Overall status
    if args.status:
        print("Colony Coordination Status (Kagami OS)")
        print("=" * 50)
        print("\nThe 7 Colonies (Im(𝕆) on S⁷):")
        for i, (col, spec) in enumerate(COLONY_SPECIALTIES.items(), 1):
            primary = spec["primary_paths"][:2]
            print(f"  e{i} {col.upper():8} → {', '.join(primary)}")

        print("\nKagami (鏡, e₀=1): The emergent observer (NOT a colony)")

        active_branches = get_active_branches()
        print(f"\nActive colonies: {len(active_branches)}")
        for col, branches in active_branches.items():
            print(f"  - {col}: {len(branches)} branch(es)")

        print("\nCoordination Tips:")
        print("  1. Before starting work:")
        print("     python scripts/ops/agent_coordinator.py --check-conflicts path/to/file.py")
        print("  2. Find work:")
        print("     python scripts/ops/agent_coordinator.py --colony crystal --suggest-work")
        print("  3. Check active work:")
        print("     python scripts/ops/agent_coordinator.py --list-branches")
        return

    # Default: show help
    parser.print_help()


if __name__ == "__main__":
    main()
