"""Metrics Label Linter - Enforce Bounded Label Sets.

Scans metrics.py and ensures all labels are bounded (no user_id, timestamp, etc).
Allowed: method, route, outcome, app, operation, phase, gate, reason, pattern
"""

import re
import sys
from pathlib import Path


ALLOWED_LABELS = {
    "method",
    "route",
    "outcome",
    "app",
    "operation",
    "phase",
    "gate",
    "reason",
    "pattern",
    "loop_type",
    "converged",
    "trigger",
    "feature",
    "agents_count",
    "from_model",
    "to_model",
    "code",
    "violation_type",
    "level",
    "from_level",
    "to_level",
    "target_variable",
    "concept_type",
}

HIGH_CARDINALITY_PATTERNS = [
    r"user_id",
    r"request_id",
    r"correlation_id",
    r"timestamp",
    r"ip_address",
    r"session_id",
]


def scan_metrics_file(file_path: Path) -> list[dict]:
    """Scan metrics.py for unbounded labels."""
    violations = []

    content = file_path.read_text()
    lines = content.split("\n")

    for line_num, line in enumerate(lines, 1):
        # Find labelnames declarations
        if "labelnames=" in line or "labelnames =" in line:
            # Extract label list
            match = re.search(r"labelnames\s*=\s*[\(\[](.*?)[\)\]]", line)
            if match:
                labels_str = match.group(1)
                # Parse labels
                labels = [
                    l.strip().strip('"').strip("'") for l in labels_str.split(",") if l.strip()
                ]

                # Check each label
                for label in labels:
                    if label and label not in ALLOWED_LABELS:
                        # Check if high-cardinality pattern
                        is_high_card = any(
                            re.search(pattern, label, re.I) for pattern in HIGH_CARDINALITY_PATTERNS
                        )

                        violations.append(
                            {
                                "line": line_num,
                                "label": label,
                                "reason": (
                                    "high_cardinality" if is_high_card else "not_in_allowed_list"
                                ),
                                "text": line.strip(),
                            }
                        )

    return violations


def main():
    """Lint metrics file."""
    metrics_file = Path("kagami_observability/metrics.py")

    if not metrics_file.exists():
        print("❌ metrics.py not found")
        return 1

    violations = scan_metrics_file(metrics_file)

    if not violations:
        print("✅ All metric labels are bounded")
        return 0

    print(f"❌ Found {len(violations)} label violations:\n")

    for v in violations:
        print(f"Line {v['line']}: {v['label']}")
        print(f"  Reason: {v['reason']}")
        print(f"  Text: {v['text']}")
        print()

    print("Allowed labels:", ", ".join(sorted(ALLOWED_LABELS)))
    print("\nForbidden patterns:", ", ".join(HIGH_CARDINALITY_PATTERNS))

    return 1


if __name__ == "__main__":
    sys.exit(main())
