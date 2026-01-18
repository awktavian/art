#!/usr/bin/env python3
"""
Architecture Layering Enforcement for K os
Analyzes imports to ensure modules only depend on lower layers.
Exit non-zero if violations detected.
"""

import ast
import sys
from collections import defaultdict
from pathlib import Path

# Layer definitions (see docs/CODEBASE_MODULE_TRAILS.md)
LAYER_RULES = {
    1: {
        "name": "Foundation",
        "modules": [
            "kagami/core/types",
            "kagami/core/schemas",
            "kagami/core/config",
            "kagami/core/utils",
            "kagami/_version.py",
        ],
        "can_import_layers": [],  # Layer 1 imports nothing from kagami
    },
    2: {
        "name": "Infrastructure",
        "modules": [
            "kagami/core/database",
            "kagami/core/kernel",
            "kagami/core/hal",
            "kagami/core/consensus",
            "kagami/core/caching",
            "kagami/core/http",
            "kagami/core/redis_client.py",
            "kagami/core/redis_filesystem.py",
        ],
        "can_import_layers": [1],
    },
    3: {
        "name": "Safety & Security",
        "modules": [
            "kagami/core/safety",
            "kagami_api/security.py",
            "kagami_api/idempotency.py",
            "kagami_api/rate_limiter.py",
            "kagami_api/security_middleware.py",
        ],
        "can_import_layers": [1, 2],
    },
    4: {
        "name": "Services & Middleware",
        "modules": [
            "kagami/core/services",
            "kagami/core/receipts",
            "kagami/core/events",
            "kagami_api/middleware",
        ],
        "can_import_layers": [1, 2, 3],
    },
    5: {
        "name": "Business Logic",
        "modules": [
            "kagami/core/fractal_agents",
            "kagami/core/orchestrator",
            "kagami/core/world_model",
            "kagami/core/learning",
            "kagami/core/embodied",
            "kagami/core/automation",
            "kagami/core/swarm",
            "kagami/core/training",
            "kagami/core/rl",
        ],
        "can_import_layers": [1, 2, 3, 4],
    },
    6: {
        "name": "API Gateway",
        "modules": [
            "kagami_api/routes",
            "kagami_api/socketio_server.py",
            "kagami_api/create_app_v2.py",
            "kagami_api/lifespan_v2.py",
        ],
        "can_import_layers": [1, 2, 3, 4, 5],
    },
    7: {
        "name": "Applications",
        "modules": [
            "kagami/integrations",
            "kagami/viz",
            "kagami/ar",
        ],
        "can_import_layers": [1, 2, 3, 4, 5, 6],
    },
}


class ImportExtractor(ast.NodeVisitor):
    """Extract imports from a Python file."""

    def __init__(self):
        self.imports: set[str] = set()

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.add(alias.name.split(".")[0])
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            self.imports.add(node.module.split(".")[0])
        self.generic_visit(node)


def get_module_layer(file_path: Path) -> int | None:
    """Determine which layer a file belongs to."""
    file_str = str(file_path)

    for layer_num, layer_info in LAYER_RULES.items():
        for module_pattern in layer_info["modules"]:  # type: ignore[index]
            if module_pattern in file_str:
                return layer_num

    return None


def get_imported_module_layer(import_name: str) -> int | None:
    """Determine which layer an import belongs to."""
    if not import_name.startswith("kagami"):
        return None  # External import, allowed

    for layer_num, layer_info in LAYER_RULES.items():
        for module_pattern in layer_info["modules"]:  # type: ignore[index]
            # Normalize paths
            import_path = import_name.replace(".", "/")
            pattern_path = module_pattern.replace("kagami/", "")

            if pattern_path in import_path or import_path.startswith(
                pattern_path.replace("/", ".")
            ):
                return layer_num

    return None


def analyze_file(file_path: Path) -> list[tuple[str, int, int]]:
    """
    Analyze a file for layering violations.
    Returns: [(import_name, import_layer, file_layer), ...]
    """
    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError) as e:
        print(f"Warning: Could not parse {file_path}: {e}", file=sys.stderr)
        return []

    extractor = ImportExtractor()
    extractor.visit(tree)

    file_layer = get_module_layer(file_path)
    if file_layer is None:
        return []  # File not in any defined layer

    violations = []
    allowed_layers = set(LAYER_RULES[file_layer]["can_import_layers"])  # type: ignore[index]

    for import_name in extractor.imports:
        import_layer = get_imported_module_layer(import_name)

        if import_layer is None:
            continue  # External import or not in defined layers

        # Check if import violates layering
        if import_layer not in allowed_layers and import_layer != file_layer:
            violations.append((import_name, import_layer, file_layer))

    return violations


def analyze_codebase(
    root_dir: Path, changed_files: list[str] | None = None
) -> dict[str, list[tuple[str, int, int]]]:
    """
    Analyze entire codebase or specific files for layering violations.
    Returns: {file_path: [(import, import_layer, file_layer), ...]}
    """
    violations = {}

    if changed_files:
        files_to_check = [root_dir / f for f in changed_files if f.endswith(".py")]
    else:
        files_to_check = list(root_dir.glob("kagami/**/*.py"))

    for file_path in files_to_check:
        if "__pycache__" in str(file_path) or file_path.name.startswith("."):
            continue

        file_violations = analyze_file(file_path)
        if file_violations:
            violations[str(file_path.relative_to(root_dir))] = file_violations

    return violations


def generate_report(violations: dict[str, list[tuple[str, int, int]]]) -> str:
    """Generate human-readable violation report."""
    lines = []
    lines.append("=" * 100)
    lines.append("KAGAMI ARCHITECTURE LAYERING VIOLATIONS")
    lines.append("=" * 100)
    lines.append("")

    if not violations:
        lines.append("✅ No layering violations detected!")
        lines.append("")
        lines.append("All modules respect the 7-layer architecture:")
        for layer_num, layer_info in sorted(LAYER_RULES.items()):
            allowed = ", ".join([f"L{l}" for l in layer_info["can_import_layers"]]) or "nothing"  # type: ignore[index]
            lines.append(f"  Layer {layer_num} ({layer_info['name']}): can import {allowed}")  # type: ignore[index]
        lines.append("")
        return "\n".join(lines)

    lines.append(
        f"❌ Found {sum(len(v) for v in violations.values())} violations across {len(violations)} files"
    )
    lines.append("")

    # Group violations by layer
    by_layer = defaultdict(list)
    for file_path, file_violations in violations.items():
        for import_name, import_layer, file_layer in file_violations:
            by_layer[file_layer].append((file_path, import_name, import_layer))

    for file_layer in sorted(by_layer.keys()):
        layer_name = LAYER_RULES[file_layer]["name"]  # type: ignore[index]
        layer_violations = by_layer[file_layer]

        lines.append("-" * 100)
        lines.append(f"Layer {file_layer} ({layer_name}) - {len(layer_violations)} violations")
        lines.append("-" * 100)

        # Group by file
        by_file = defaultdict(list)
        for file_path, import_name, import_layer in layer_violations:
            by_file[file_path].append((import_name, import_layer))

        for file_path in sorted(by_file.keys()):
            lines.append(f"\n  {file_path}")
            for import_name, import_layer in sorted(by_file[file_path]):
                import_layer_name = LAYER_RULES[import_layer]["name"]  # type: ignore[index]
                lines.append(
                    f"    ❌ imports {import_name} (Layer {import_layer}: {import_layer_name})"
                )

        lines.append("")

    lines.append("=" * 100)
    lines.append("REMEDIATION")
    lines.append("=" * 100)
    lines.append("")
    lines.append("See docs/CODEBASE_MODULE_TRAILS.md for refactoring strategies.")
    lines.append("")
    lines.append("Quick fixes:")
    lines.append("  1. Extract interfaces/protocols to Layer 1 (core/types/)")
    lines.append("  2. Use dependency injection instead of direct imports")
    lines.append("  3. Use event bus (Layer 4) to decouple layers")
    lines.append("  4. Move shared utilities to appropriate lower layer")
    lines.append("")

    return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Enforce K os architecture layering")
    parser.add_argument(
        "--changed-files-only",
        action="store_true",
        help="Only check files in git diff (requires git)",
    )
    parser.add_argument(
        "--report-file", type=str, default="LAYERING_VIOLATIONS.md", help="Output report file path"
    )
    parser.add_argument(
        "--strict", action="store_true", help="Exit non-zero if any violations found"
    )

    args = parser.parse_args()

    root_dir = Path(__file__).parent.parent.parent

    changed_files = None
    if args.changed_files_only:
        import subprocess

        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD"], capture_output=True, text=True, cwd=root_dir
            )
            changed_files = [
                f.strip() for f in result.stdout.split("\n") if f.strip().endswith(".py")
            ]
            print(f"Checking {len(changed_files)} changed Python files...")
        except Exception as e:
            print(f"Warning: Could not get git diff: {e}", file=sys.stderr)

    violations = analyze_codebase(root_dir, changed_files)
    report = generate_report(violations)

    # Print to console
    print(report)

    # Write to file
    report_path = root_dir / args.report_file
    report_path.write_text(report)
    print(f"\n📄 Full report written to: {report_path}")

    # Exit code
    if violations and args.strict:
        print("\n❌ Layering violations detected. Exiting with code 1.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
