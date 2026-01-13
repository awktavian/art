#!/usr/bin/env python3
"""
Kagami Architecture Analyzer
Static analysis tool that extracts real dependencies and generates pre-computed layouts.

Usage:
    python analyze.py [--output arch-data.json]
"""

import ast
import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Configuration
KAGAMI_ROOT = Path(__file__).parent.parent.parent.parent / ".claude-squad/worktrees/analysis_188a2ff8efc63c10"
if not KAGAMI_ROOT.exists():
    KAGAMI_ROOT = Path.home() / ".claude-squad/worktrees/analysis_188a2ff8efc63c10"
if not KAGAMI_ROOT.exists():
    KAGAMI_ROOT = Path(__file__).parent.parent.parent  # Fallback

PACKAGES_DIR = KAGAMI_ROOT / "packages"
APPS_DIR = KAGAMI_ROOT / "apps"

# Language detection
LANG_EXTENSIONS = {
    ".py": "python",
    ".rs": "rust",
    ".swift": "swift",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
}

# Color palette (carefully chosen for distinction)
LANG_COLORS = {
    "python": "#4B8BBE",    # Python blue (official)
    "rust": "#FF6B35",      # Rust orange (vibrant)
    "swift": "#F05138",     # Swift red (official)
    "kotlin": "#B125EA",    # Kotlin purple (vibrant)
    "typescript": "#007ACC", # TypeScript blue (official)
    "javascript": "#F7DF1E", # JavaScript yellow
    "mixed": "#10B981",     # Green for mixed
}


@dataclass
class Package:
    """Represents a package or app."""
    id: str
    name: str
    lang: str
    path: Path
    loc: int = 0
    files: int = 0
    modules: list = field(default_factory=list)
    description: str = ""
    type: str = "package"  # package, app, core_module


@dataclass
class Dependency:
    """Represents a dependency between packages."""
    source: str
    target: str
    count: int = 0
    type: str = "import"  # import, ffi, websocket


def count_lines(file_path: Path) -> int:
    """Count non-empty, non-comment lines in a file."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        count = 0
        in_multiline = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            # Skip comments
            if stripped.startswith("#") or stripped.startswith("//"):
                continue
            if stripped.startswith('"""') or stripped.startswith("'''"):
                in_multiline = not in_multiline
                continue
            if in_multiline:
                continue
            count += 1
        return count
    except Exception:
        return 0


def detect_language(path: Path) -> tuple[str, int, int]:
    """Detect primary language and count LOC/files."""
    lang_counts: dict[str, int] = defaultdict(int)
    file_counts: dict[str, int] = defaultdict(int)
    total_loc = 0
    total_files = 0

    for ext, lang in LANG_EXTENSIONS.items():
        for file_path in path.rglob(f"*{ext}"):
            # Skip test files, vendored code, etc.
            if any(skip in str(file_path) for skip in [
                "__pycache__", "node_modules", ".git", "target",
                "build", "dist", ".pytest_cache", "venv"
            ]):
                continue
            loc = count_lines(file_path)
            lang_counts[lang] += loc
            file_counts[lang] += 1
            total_loc += loc
            total_files += 1

    if not lang_counts:
        return "mixed", 0, 0

    primary_lang = max(lang_counts, key=lang_counts.get)
    return primary_lang, total_loc, total_files


def extract_python_imports(file_path: Path) -> list[str]:
    """Extract import statements from a Python file."""
    imports = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # Parse AST for accurate imports
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name.split(".")[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module.split(".")[0])
        except SyntaxError:
            # Fallback to regex
            for match in re.finditer(r"^(?:from|import)\s+([\w.]+)", content, re.MULTILINE):
                imports.append(match.group(1).split(".")[0])
    except Exception:
        pass
    return imports


def extract_rust_imports(file_path: Path) -> list[str]:
    """Extract use/extern crate statements from Rust."""
    imports = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        # use kagami_xxx::...
        for match in re.finditer(r"use\s+(kagami[\w_]*)", content):
            imports.append(match.group(1))
        # extern crate
        for match in re.finditer(r"extern\s+crate\s+(kagami[\w_]*)", content):
            imports.append(match.group(1))
    except Exception:
        pass
    return imports


def extract_swift_imports(file_path: Path) -> list[str]:
    """Extract import statements from Swift."""
    imports = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        for match in re.finditer(r"import\s+(Kagami\w*)", content):
            imports.append(match.group(1).lower().replace("kagami", "kagami_"))
    except Exception:
        pass
    return imports


def extract_kotlin_imports(file_path: Path) -> list[str]:
    """Extract import statements from Kotlin."""
    imports = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        for match in re.finditer(r"import\s+(?:com\.kagami|io\.kagami)\.([\w.]+)", content):
            pkg = match.group(1).split(".")[0]
            imports.append(f"kagami_{pkg}")
    except Exception:
        pass
    return imports


def analyze_packages() -> list[Package]:
    """Analyze all packages in the packages directory."""
    packages = []

    if not PACKAGES_DIR.exists():
        print(f"Warning: Packages directory not found at {PACKAGES_DIR}", file=sys.stderr)
        return packages

    for pkg_path in sorted(PACKAGES_DIR.iterdir()):
        if not pkg_path.is_dir():
            continue
        if pkg_path.name.startswith("."):
            continue

        lang, loc, files = detect_language(pkg_path)

        # Get description from pyproject.toml or Cargo.toml
        description = ""
        pyproject = pkg_path / "pyproject.toml"
        cargo = pkg_path / "Cargo.toml"

        if pyproject.exists():
            try:
                content = pyproject.read_text()
                match = re.search(r'description\s*=\s*"([^"]+)"', content)
                if match:
                    description = match.group(1)
            except Exception:
                pass
        elif cargo.exists():
            try:
                content = cargo.read_text()
                match = re.search(r'description\s*=\s*"([^"]+)"', content)
                if match:
                    description = match.group(1)
            except Exception:
                pass

        # Count modules for Python packages
        modules = []
        if lang == "python":
            src_dir = pkg_path / pkg_path.name.replace("-", "_")
            if not src_dir.exists():
                src_dir = pkg_path / "src" / pkg_path.name.replace("-", "_")
            if src_dir.exists():
                for mod in src_dir.iterdir():
                    if mod.is_dir() and not mod.name.startswith("_"):
                        modules.append(mod.name)

        pkg = Package(
            id=pkg_path.name.replace("-", "_"),
            name=pkg_path.name,
            lang=lang,
            path=pkg_path,
            loc=loc,
            files=files,
            modules=modules,
            description=description,
            type="package"
        )
        packages.append(pkg)

    return packages


def analyze_apps() -> list[Package]:
    """Analyze all apps in the apps directory."""
    apps = []

    if not APPS_DIR.exists():
        print(f"Warning: Apps directory not found at {APPS_DIR}", file=sys.stderr)
        return apps

    for app_path in sorted(APPS_DIR.iterdir()):
        if not app_path.is_dir():
            continue
        if app_path.name.startswith("."):
            continue

        lang, loc, files = detect_language(app_path)

        app = Package(
            id=f"app_{app_path.name}",
            name=app_path.name,
            lang=lang,
            path=app_path,
            loc=loc,
            files=files,
            type="app"
        )
        apps.append(app)

    return apps


def analyze_core_modules() -> list[Package]:
    """Analyze core modules within the main kagami package."""
    modules = []

    core_path = PACKAGES_DIR / "kagami" / "core"
    if not core_path.exists():
        core_path = PACKAGES_DIR / "kagami" / "kagami" / "core"
    if not core_path.exists():
        core_path = PACKAGES_DIR / "kagami" / "src" / "kagami" / "core"
    if not core_path.exists():
        print(f"Warning: Core modules not found", file=sys.stderr)
        return modules

    for mod_path in sorted(core_path.iterdir()):
        if not mod_path.is_dir():
            continue
        if mod_path.name.startswith("_"):
            continue

        lang, loc, files = detect_language(mod_path)

        # Get description from __init__.py docstring
        description = ""
        init_file = mod_path / "__init__.py"
        if init_file.exists():
            try:
                content = init_file.read_text()
                match = re.search(r'^"""([^"]+)"""', content, re.DOTALL)
                if match:
                    description = match.group(1).strip().split("\n")[0]
            except Exception:
                pass

        mod = Package(
            id=mod_path.name,
            name=mod_path.name,
            lang="python",
            path=mod_path,
            loc=loc,
            files=files,
            description=description,
            type="core_module"
        )
        modules.append(mod)

    return modules


def analyze_dependencies(packages: list[Package]) -> list[Dependency]:
    """Analyze dependencies between packages."""
    deps: dict[tuple[str, str], int] = defaultdict(int)
    pkg_names = {p.id for p in packages}

    for pkg in packages:
        if pkg.type == "core_module":
            continue  # Handle core modules separately

        # Collect all imports from this package
        imports: list[str] = []

        for file_path in pkg.path.rglob("*.py"):
            imports.extend(extract_python_imports(file_path))
        for file_path in pkg.path.rglob("*.rs"):
            imports.extend(extract_rust_imports(file_path))
        for file_path in pkg.path.rglob("*.swift"):
            imports.extend(extract_swift_imports(file_path))
        for file_path in pkg.path.rglob("*.kt"):
            imports.extend(extract_kotlin_imports(file_path))

        # Count imports to other kagami packages
        for imp in imports:
            # Normalize import name
            normalized = imp.replace("-", "_")
            if normalized.startswith("kagami"):
                if normalized in pkg_names and normalized != pkg.id:
                    deps[(pkg.id, normalized)] += 1

    return [
        Dependency(source=src, target=tgt, count=cnt)
        for (src, tgt), cnt in deps.items()
        if cnt > 0
    ]


def analyze_core_dependencies(modules: list[Package]) -> list[Dependency]:
    """Analyze dependencies between core modules."""
    deps: dict[tuple[str, str], int] = defaultdict(int)
    mod_names = {m.id for m in modules}

    for mod in modules:
        for file_path in mod.path.rglob("*.py"):
            imports = extract_python_imports(file_path)
            for imp in imports:
                # Look for imports from kagami.core.xxx
                if imp in mod_names and imp != mod.id:
                    deps[(mod.id, imp)] += 1

    return [
        Dependency(source=src, target=tgt, count=cnt)
        for (src, tgt), cnt in deps.items()
        if cnt > 0
    ]


def compute_hierarchical_layout(
    nodes: list[dict],
    edges: list[dict],
    width: int = 1200,
    height: int = 800
) -> dict[str, dict]:
    """
    Compute a force-directed layout with hierarchical hints.
    Pre-computes stable positions with good spread.
    """
    import math
    import random

    random.seed(42)  # Deterministic

    # Build adjacency
    adj: dict[str, set[str]] = defaultdict(set)
    node_ids = {n["id"] for n in nodes}

    for edge in edges:
        if edge["source"] in node_ids and edge["target"] in node_ids:
            adj[edge["source"]].add(edge["target"])
            adj[edge["target"]].add(edge["source"])

    # Initialize positions in a grid-like pattern with some randomness
    n_nodes = len(nodes)
    cols = max(1, int(math.ceil(math.sqrt(n_nodes * width / height))))
    rows = max(1, int(math.ceil(n_nodes / cols)))

    cell_width = width / (cols + 1)
    cell_height = height / (rows + 1)

    # Sort nodes by LOC for visual hierarchy (largest first, in center)
    sorted_nodes = sorted(nodes, key=lambda x: -x.get("loc", 0))

    positions: dict[str, dict] = {}

    # Place nodes in a spiral pattern from center
    cx, cy = width / 2, height / 2
    for i, node in enumerate(sorted_nodes):
        if i == 0:
            # Largest node in center
            x, y = cx, cy
        else:
            # Spiral outward
            angle = i * 2.4  # Golden angle
            radius = 50 + i * 25
            x = cx + math.cos(angle) * radius
            y = cy + math.sin(angle) * radius

        # Add small randomness
        x += random.uniform(-20, 20)
        y += random.uniform(-20, 20)

        positions[node["id"]] = {"x": x, "y": y}

    # Run force simulation to spread out
    for iteration in range(150):
        alpha = 1.0 - (iteration / 150)

        # Repulsion between all nodes
        for i, n1 in enumerate(sorted_nodes):
            for j, n2 in enumerate(sorted_nodes):
                if i >= j:
                    continue

                p1 = positions[n1["id"]]
                p2 = positions[n2["id"]]

                dx = p2["x"] - p1["x"]
                dy = p2["y"] - p1["y"]
                dist = math.sqrt(dx * dx + dy * dy) or 1

                # Strong repulsion, especially for nearby nodes
                min_dist = 100
                if dist < min_dist * 2:
                    force = (min_dist * 2 - dist) * 0.3 * alpha
                    if dist > 0:
                        fx = (dx / dist) * force
                        fy = (dy / dist) * force
                        p1["x"] -= fx
                        p1["y"] -= fy
                        p2["x"] += fx
                        p2["y"] += fy

        # Attraction along edges
        for edge in edges:
            if edge["source"] not in positions or edge["target"] not in positions:
                continue

            p1 = positions[edge["source"]]
            p2 = positions[edge["target"]]

            dx = p2["x"] - p1["x"]
            dy = p2["y"] - p1["y"]
            dist = math.sqrt(dx * dx + dy * dy) or 1

            # Pull connected nodes together, but not too close
            target_dist = 180
            force = (dist - target_dist) * 0.02 * alpha
            if dist > 0:
                fx = (dx / dist) * force
                fy = (dy / dist) * force
                p1["x"] += fx
                p1["y"] += fy
                p2["x"] -= fx
                p2["y"] -= fy

        # Soft boundary constraint
        margin = 80
        for node in sorted_nodes:
            p = positions[node["id"]]
            if p["x"] < margin:
                p["x"] += (margin - p["x"]) * 0.1
            if p["x"] > width - margin:
                p["x"] -= (p["x"] - (width - margin)) * 0.1
            if p["y"] < margin:
                p["y"] += (margin - p["y"]) * 0.1
            if p["y"] > height - margin:
                p["y"] -= (p["y"] - (height - margin)) * 0.1

    return positions


def generate_output(
    packages: list[Package],
    apps: list[Package],
    core_modules: list[Package],
    pkg_deps: list[Dependency],
    core_deps: list[Dependency]
) -> dict[str, Any]:
    """Generate the final JSON output."""

    # Convert packages to dicts
    pkg_nodes = [
        {
            "id": p.id,
            "name": p.name,
            "lang": p.lang,
            "loc": p.loc,
            "files": p.files,
            "modules": len(p.modules),
            "description": p.description,
            "type": p.type
        }
        for p in packages
    ]

    app_nodes = [
        {
            "id": a.id,
            "name": a.name,
            "lang": a.lang,
            "loc": a.loc,
            "files": a.files,
            "type": "app"
        }
        for a in apps
    ]

    core_nodes = [
        {
            "id": m.id,
            "name": m.name,
            "lang": m.lang,
            "loc": m.loc,
            "files": m.files,
            "description": m.description,
            "type": "core_module"
        }
        for m in core_modules
    ]

    # Convert dependencies
    pkg_edges = [
        {"source": d.source, "target": d.target, "count": d.count}
        for d in pkg_deps
    ]

    core_edges = [
        {"source": d.source, "target": d.target, "count": d.count}
        for d in core_deps
    ]

    # Compute layouts
    all_pkg_nodes = pkg_nodes + app_nodes
    pkg_positions = compute_hierarchical_layout(all_pkg_nodes, pkg_edges)
    core_positions = compute_hierarchical_layout(core_nodes, core_edges)

    # Compute statistics
    total_loc = sum(p.loc for p in packages) + sum(a.loc for a in apps)
    total_files = sum(p.files for p in packages) + sum(a.files for a in apps)

    return {
        "meta": {
            "generated": True,
            "totalLoc": total_loc,
            "totalFiles": total_files,
            "packageCount": len(packages),
            "appCount": len(apps),
            "coreModuleCount": len(core_modules)
        },
        "packages": pkg_nodes,
        "apps": app_nodes,
        "coreModules": core_nodes,
        "packageDeps": pkg_edges,
        "coreDeps": core_edges,
        "packagePositions": pkg_positions,
        "corePositions": core_positions,
        "colors": LANG_COLORS
    }


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Kagami Architecture Analyzer")
    parser.add_argument("--output", "-o", default="arch-data.json", help="Output file")
    args = parser.parse_args()

    print(f"Analyzing Kagami codebase at {KAGAMI_ROOT}...", file=sys.stderr)

    # Analyze everything
    packages = analyze_packages()
    print(f"  Found {len(packages)} packages", file=sys.stderr)

    apps = analyze_apps()
    print(f"  Found {len(apps)} apps", file=sys.stderr)

    core_modules = analyze_core_modules()
    print(f"  Found {len(core_modules)} core modules", file=sys.stderr)

    pkg_deps = analyze_dependencies(packages + apps)
    print(f"  Found {len(pkg_deps)} package dependencies", file=sys.stderr)

    core_deps = analyze_core_dependencies(core_modules)
    print(f"  Found {len(core_deps)} core module dependencies", file=sys.stderr)

    # Generate output
    output = generate_output(packages, apps, core_modules, pkg_deps, core_deps)

    # Write to file
    output_path = Path(__file__).parent / args.output
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Output written to {output_path}", file=sys.stderr)

    # Also print summary
    print(json.dumps({
        "packages": len(packages),
        "apps": len(apps),
        "coreModules": len(core_modules),
        "totalLoc": output["meta"]["totalLoc"],
        "dependencies": len(pkg_deps) + len(core_deps)
    }, indent=2))


if __name__ == "__main__":
    main()
