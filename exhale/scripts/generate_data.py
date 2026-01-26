#!/usr/bin/env python3
"""
Generate data files for Weekend Metamorphosis V2.
Extracts git commits since Friday 5 PM and categorizes them into 6 narrative arcs.
"""

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from collections import defaultdict

# Configuration
REPO_PATH = Path.home() / "projects" / "kagami"
OUTPUT_DIR = Path(__file__).parent.parent / "data"
CUTOFF_DATE = "2026-01-23 17:00:00"  # Friday 5 PM

# Arc classification patterns
ARC_PATTERNS = {
    "ci-cd": [
        r"\bci[:\(]", r"fix\(ci\)", r"workflow", r"github.actions", 
        r"cache.*v\d", r"\.github", r"uv.*setup", r"virtualenv"
    ],
    "tpu-training": [
        r"\btrain", r"\bjax\b", r"\btpu\b", r"hjepa", r"gradient",
        r"checkpoint", r"shard", r"xla", r"compile", r"phase.*\d+"
    ],
    "architecture": [
        r"refactor", r"consolidat", r"cleanup", r"\bsdk\b", r"singleton",
        r"split.*model", r"module", r"reorganiz", r"restructur"
    ],
    "security": [
        r"security", r"rce", r"pickle", r"crypto", r"byzantine",
        r"injection", r"cve", r"oauth", r"secret", r"audit"
    ],
    "verification": [
        r"medverify", r"verify", r"state.?board", r"license",
        r"finverify", r"insverify", r"legalverify", r"transverify"
    ],
    "quality": [
        r"\btest", r"\blint", r"dead.?code", r"vulture", r"clone.?detect",
        r"format", r"stub", r"placeholder", r"assertion"
    ]
}

# Arc metadata
ARC_META = {
    "ci-cd": {
        "name": "CI/CD Stabilization",
        "icon": "⚡",
        "color": "#00d4ff",
        "gradient": ["#0066ff", "#00d4ff"]
    },
    "tpu-training": {
        "name": "TPU Training",
        "icon": "🧠",
        "color": "#ff006e",
        "gradient": ["#ff006e", "#ff5c8d"]
    },
    "architecture": {
        "name": "Architecture",
        "icon": "🏗️",
        "color": "#8b5cf6",
        "gradient": ["#8b5cf6", "#4f46e5"]
    },
    "security": {
        "name": "Security",
        "icon": "🔐",
        "color": "#f59e0b",
        "gradient": ["#f59e0b", "#f97316"]
    },
    "verification": {
        "name": "Verification",
        "icon": "✅",
        "color": "#10b981",
        "gradient": ["#10b981", "#14b8a6"]
    },
    "quality": {
        "name": "Quality",
        "icon": "✨",
        "color": "#94a3b8",
        "gradient": ["#94a3b8", "#f8fafc"]
    }
}


def run_git_command(cmd: list[str]) -> str:
    """Run a git command in the repo directory."""
    result = subprocess.run(
        ["git"] + cmd,
        cwd=REPO_PATH,
        capture_output=True,
        text=True
    )
    return result.stdout


def classify_commit(subject: str, body: str = "") -> str:
    """Classify a commit into one of the 6 arcs based on its message."""
    text = f"{subject} {body}".lower()
    
    scores = defaultdict(int)
    for arc, patterns in ARC_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                scores[arc] += 1
    
    if scores:
        return max(scores, key=scores.get)
    return "quality"  # Default to quality for misc commits


def get_commit_type(subject: str) -> str:
    """Extract conventional commit type."""
    match = re.match(r'^(\w+)[\(:]', subject)
    if match:
        type_map = {
            "feat": "feature",
            "fix": "fix",
            "refactor": "refactor",
            "chore": "chore",
            "docs": "docs",
            "test": "test",
            "perf": "perf",
            "style": "style",
            "ci": "chore"
        }
        return type_map.get(match.group(1).lower(), "other")
    return "other"


def parse_commits():
    """Parse all commits since the cutoff date."""
    # Get commit list with stats
    log_format = "%H|%h|%s|%ai|%an"
    log_output = run_git_command([
        "log",
        f"--since={CUTOFF_DATE}",
        f"--pretty=format:{log_format}",
        "--numstat"
    ])
    
    commits = []
    current_commit = None
    file_changes = []
    
    for line in log_output.split("\n"):
        if "|" in line and line.count("|") >= 4:
            # This is a commit line
            if current_commit:
                current_commit["files"] = file_changes
                commits.append(current_commit)
            
            parts = line.split("|")
            hash_full, hash_short, subject, date_str, author = parts[:5]
            
            # Parse date - git format: "2026-01-25 23:30:33 -0800"
            dt = datetime.strptime(date_str.split(" -")[0].split(" +")[0], "%Y-%m-%d %H:%M:%S")
            
            current_commit = {
                "hash": hash_full,
                "shortHash": hash_short,
                "subject": subject,
                "date": date_str,
                "timestamp": dt.isoformat(),
                "author": author,
                "type": get_commit_type(subject),
                "arc": classify_commit(subject),
                "additions": 0,
                "deletions": 0
            }
            file_changes = []
        
        elif line.strip() and current_commit:
            # This is a file stat line
            parts = line.split("\t")
            if len(parts) >= 3:
                add, delete, filepath = parts[0], parts[1], parts[2]
                try:
                    additions = int(add) if add != "-" else 0
                    deletions = int(delete) if delete != "-" else 0
                    current_commit["additions"] += additions
                    current_commit["deletions"] += deletions
                    file_changes.append({
                        "path": filepath,
                        "additions": additions,
                        "deletions": deletions
                    })
                except ValueError:
                    pass
    
    # Don't forget the last commit
    if current_commit:
        current_commit["files"] = file_changes
        commits.append(current_commit)
    
    return commits


def compute_metrics(commits: list) -> dict:
    """Compute aggregate metrics from commits."""
    total_additions = sum(c["additions"] for c in commits)
    total_deletions = sum(c["deletions"] for c in commits)
    
    # By day
    by_day = defaultdict(lambda: {"commits": 0, "additions": 0, "deletions": 0})
    for c in commits:
        dt = datetime.fromisoformat(c["timestamp"])
        day_name = dt.strftime("%A")
        by_day[day_name]["commits"] += 1
        by_day[day_name]["additions"] += c["additions"]
        by_day[day_name]["deletions"] += c["deletions"]
    
    # By arc
    by_arc = defaultdict(lambda: {"commits": 0, "additions": 0, "deletions": 0})
    for c in commits:
        arc = c["arc"]
        by_arc[arc]["commits"] += 1
        by_arc[arc]["additions"] += c["additions"]
        by_arc[arc]["deletions"] += c["deletions"]
    
    # By type
    by_type = defaultdict(int)
    for c in commits:
        by_type[c["type"]] += 1
    
    return {
        "totalCommits": len(commits),
        "totalAdditions": total_additions,
        "totalDeletions": total_deletions,
        "netChange": total_additions - total_deletions,
        "startDate": min(c["timestamp"] for c in commits) if commits else None,
        "endDate": max(c["timestamp"] for c in commits) if commits else None,
        "byDay": dict(by_day),
        "byArc": dict(by_arc),
        "byType": dict(by_type)
    }


def build_arcs(commits: list) -> dict:
    """Build arc data structures with metadata and commits."""
    arcs = {}
    
    for arc_id, meta in ARC_META.items():
        arc_commits = [c for c in commits if c["arc"] == arc_id]
        
        # Key moments for this arc
        key_moments = []
        for c in sorted(arc_commits, key=lambda x: x["additions"] + x["deletions"], reverse=True)[:5]:
            key_moments.append({
                "hash": c["shortHash"],
                "subject": c["subject"],
                "impact": c["additions"] + c["deletions"]
            })
        
        arcs[arc_id] = {
            **meta,
            "id": arc_id,
            "commitCount": len(arc_commits),
            "additions": sum(c["additions"] for c in arc_commits),
            "deletions": sum(c["deletions"] for c in arc_commits),
            "keyMoments": key_moments
        }
    
    return arcs


def build_file_tree(commits: list) -> dict:
    """Build file tree data for treemap visualization."""
    file_stats = defaultdict(lambda: {"additions": 0, "deletions": 0, "commits": 0})
    
    for c in commits:
        for f in c.get("files", []):
            path = f["path"]
            file_stats[path]["additions"] += f["additions"]
            file_stats[path]["deletions"] += f["deletions"]
            file_stats[path]["commits"] += 1
    
    # Build hierarchical structure
    def build_tree(paths_data):
        root = {"name": "root", "children": {}}
        
        for path, stats in paths_data.items():
            parts = path.split("/")
            current = root
            
            for i, part in enumerate(parts):
                if part not in current["children"]:
                    current["children"][part] = {
                        "name": part,
                        "children": {},
                        "additions": 0,
                        "deletions": 0,
                        "commits": 0
                    }
                current = current["children"][part]
                current["additions"] += stats["additions"]
                current["deletions"] += stats["deletions"]
                current["commits"] += stats["commits"]
        
        # Convert to list format for D3
        def to_list(node):
            if node["children"]:
                return {
                    "name": node["name"],
                    "children": [to_list(c) for c in node["children"].values()],
                    "additions": node.get("additions", 0),
                    "deletions": node.get("deletions", 0)
                }
            return {
                "name": node["name"],
                "value": node.get("additions", 0) + node.get("deletions", 0),
                "additions": node.get("additions", 0),
                "deletions": node.get("deletions", 0)
            }
        
        return to_list(root)
    
    return build_tree(file_stats)


def main():
    print("🔍 Extracting commits from kagami repo...")
    commits = parse_commits()
    print(f"   Found {len(commits)} commits since {CUTOFF_DATE}")
    
    print("📊 Computing metrics...")
    metrics = compute_metrics(commits)
    
    print("🏛️ Building narrative arcs...")
    arcs = build_arcs(commits)
    
    print("🌳 Building file tree...")
    file_tree = build_file_tree(commits)
    
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Write commits.json
    commits_output = {
        "meta": {
            "version": "2.0",
            "generated": datetime.now().isoformat(),
            "source": "kagami"
        },
        "commits": commits
    }
    with open(OUTPUT_DIR / "commits.json", "w") as f:
        json.dump(commits_output, f, indent=2)
    print(f"   ✅ Written {OUTPUT_DIR / 'commits.json'}")
    
    # Write metrics.json
    with open(OUTPUT_DIR / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"   ✅ Written {OUTPUT_DIR / 'metrics.json'}")
    
    # Write arcs.json
    with open(OUTPUT_DIR / "arcs.json", "w") as f:
        json.dump(arcs, f, indent=2)
    print(f"   ✅ Written {OUTPUT_DIR / 'arcs.json'}")
    
    # Write files.json (for treemap)
    with open(OUTPUT_DIR / "files.json", "w") as f:
        json.dump(file_tree, f, indent=2)
    print(f"   ✅ Written {OUTPUT_DIR / 'files.json'}")
    
    # Summary
    print("\n📈 Summary:")
    print(f"   Commits: {metrics['totalCommits']}")
    print(f"   Additions: +{metrics['totalAdditions']:,}")
    print(f"   Deletions: -{metrics['totalDeletions']:,}")
    print(f"   Net: {metrics['netChange']:+,}")
    print("\n   By Arc:")
    for arc_id, arc in arcs.items():
        print(f"     {arc['icon']} {arc['name']}: {arc['commitCount']} commits")


if __name__ == "__main__":
    main()
