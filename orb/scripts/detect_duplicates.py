#!/usr/bin/env python3
"""
Code Duplication Detection Tool

A comprehensive tool for detecting code duplication in Python codebases:
1. Duplicate class names across modules
2. Duplicate function names (business logic, excluding dunder methods)
3. Schema duplication (Pydantic models, dataclasses with overlapping fields)
4. Similar code blocks using AST structural comparison

Usage:
    # Basic usage - scan packages/ directory
    python scripts/detect_duplicates.py

    # Custom paths
    python scripts/detect_duplicates.py --path packages/kagami

    # JSON output for CI
    python scripts/detect_duplicates.py --format json

    # Markdown report
    python scripts/detect_duplicates.py --format markdown --output report.md

    # Fail if duplicates exceed threshold (for CI)
    python scripts/detect_duplicates.py --max-duplicates 10 --fail-on-threshold

    # Only check specific categories
    python scripts/detect_duplicates.py --check classes functions

    # Adjust similarity threshold for code blocks
    python scripts/detect_duplicates.py --similarity-threshold 0.85

Example CI integration:
    python scripts/detect_duplicates.py --format json --max-duplicates 5 --fail-on-threshold
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeAlias

# Type aliases
ASTNode: TypeAlias = ast.AST
FileLocation: TypeAlias = tuple[str, int]  # (filepath, line_number)


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class DuplicateClass:
    """Represents a duplicate class definition."""

    name: str
    locations: list[FileLocation] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "locations": [{"file": loc[0], "line": loc[1]} for loc in self.locations],
            "count": len(self.locations),
        }


@dataclass
class DuplicateFunction:
    """Represents a duplicate function definition."""

    name: str
    locations: list[FileLocation] = field(default_factory=list)
    signatures: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "locations": [{"file": loc[0], "line": loc[1]} for loc in self.locations],
            "signatures": self.signatures,
            "count": len(self.locations),
        }


@dataclass
class SchemaOverlap:
    """Represents overlapping schema definitions."""

    schema1_name: str
    schema1_file: str
    schema2_name: str
    schema2_file: str
    common_fields: list[str]
    overlap_percentage: float
    schema1_fields: list[str] = field(default_factory=list)
    schema2_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "schema1": {"name": self.schema1_name, "file": self.schema1_file},
            "schema2": {"name": self.schema2_name, "file": self.schema2_file},
            "common_fields": self.common_fields,
            "overlap_percentage": round(self.overlap_percentage, 2),
            "schema1_fields": self.schema1_fields,
            "schema2_fields": self.schema2_fields,
        }


@dataclass
class SimilarCodeBlock:
    """Represents similar code blocks."""

    function1_name: str
    function1_file: str
    function1_line: int
    function2_name: str
    function2_file: str
    function2_line: int
    similarity_score: float
    ast_hash: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "function1": {
                "name": self.function1_name,
                "file": self.function1_file,
                "line": self.function1_line,
            },
            "function2": {
                "name": self.function2_name,
                "file": self.function2_file,
                "line": self.function2_line,
            },
            "similarity_score": round(self.similarity_score, 3),
            "ast_hash": self.ast_hash,
        }


@dataclass
class DuplicationReport:
    """Complete duplication analysis report."""

    duplicate_classes: list[DuplicateClass] = field(default_factory=list)
    duplicate_functions: list[DuplicateFunction] = field(default_factory=list)
    schema_overlaps: list[SchemaOverlap] = field(default_factory=list)
    similar_code_blocks: list[SimilarCodeBlock] = field(default_factory=list)
    files_scanned: int = 0
    total_classes: int = 0
    total_functions: int = 0
    total_schemas: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "summary": {
                "files_scanned": self.files_scanned,
                "total_classes": self.total_classes,
                "total_functions": self.total_functions,
                "total_schemas": self.total_schemas,
                "duplicate_class_names": len(self.duplicate_classes),
                "duplicate_function_names": len(self.duplicate_functions),
                "schema_overlaps": len(self.schema_overlaps),
                "similar_code_blocks": len(self.similar_code_blocks),
                "total_issues": (
                    len(self.duplicate_classes)
                    + len(self.duplicate_functions)
                    + len(self.schema_overlaps)
                    + len(self.similar_code_blocks)
                ),
            },
            "duplicate_classes": [dc.to_dict() for dc in self.duplicate_classes],
            "duplicate_functions": [df.to_dict() for df in self.duplicate_functions],
            "schema_overlaps": [so.to_dict() for so in self.schema_overlaps],
            "similar_code_blocks": [scb.to_dict() for scb in self.similar_code_blocks],
        }

    @property
    def total_issues(self) -> int:
        """Total number of duplication issues found."""
        return (
            len(self.duplicate_classes)
            + len(self.duplicate_functions)
            + len(self.schema_overlaps)
            + len(self.similar_code_blocks)
        )


# =============================================================================
# AST UTILITIES
# =============================================================================


class ASTNormalizer(ast.NodeTransformer):
    """
    Normalizes AST for structural comparison.

    Replaces variable names, string literals, and numbers with placeholders
    to focus on structural similarity rather than literal matching.
    """

    def __init__(self) -> None:
        """Initialize the normalizer."""
        self.var_counter = 0
        self.var_map: dict[str, str] = {}

    def visit_Name(self, node: ast.Name) -> ast.Name:
        """Normalize variable names."""
        if node.id not in self.var_map:
            self.var_map[node.id] = f"VAR_{self.var_counter}"
            self.var_counter += 1
        node.id = self.var_map[node.id]
        return node

    def visit_Constant(self, node: ast.Constant) -> ast.Constant:
        """Normalize constants."""
        if isinstance(node.value, str):
            node.value = "STR_CONST"
        elif isinstance(node.value, (int, float)):
            node.value = 0
        return node

    def visit_arg(self, node: ast.arg) -> ast.arg:
        """Normalize argument names."""
        if node.arg not in self.var_map:
            self.var_map[node.arg] = f"ARG_{self.var_counter}"
            self.var_counter += 1
        node.arg = self.var_map[node.arg]
        return node


def normalize_ast(node: ASTNode) -> ASTNode:
    """
    Normalize an AST node for structural comparison.

    Args:
        node: AST node to normalize

    Returns:
        Normalized AST node
    """
    import copy

    normalized = copy.deepcopy(node)
    normalizer = ASTNormalizer()
    return normalizer.visit(normalized)


def ast_to_hash(node: ASTNode) -> str:
    """
    Generate a hash of an AST node for quick comparison.

    Args:
        node: AST node to hash

    Returns:
        MD5 hash of the normalized AST dump
    """
    normalized = normalize_ast(node)
    dump = ast.dump(normalized, annotate_fields=False, include_attributes=False)
    return hashlib.md5(dump.encode()).hexdigest()


def calculate_ast_similarity(node1: ASTNode, node2: ASTNode) -> float:
    """
    Calculate structural similarity between two AST nodes.

    Uses a simplified Jaccard similarity over node types and structure.

    Args:
        node1: First AST node
        node2: Second AST node

    Returns:
        Similarity score between 0.0 and 1.0
    """

    def get_node_features(node: ASTNode) -> list[str]:
        """Extract structural features from an AST node."""
        features = []
        for child in ast.walk(node):
            feature = type(child).__name__
            # Add some structural context
            if isinstance(child, ast.BinOp):
                feature += f"_{type(child.op).__name__}"
            elif isinstance(child, ast.Compare):
                feature += f"_{len(child.ops)}"
            elif isinstance(child, ast.Call):
                feature += f"_{len(child.args)}_{len(child.keywords)}"
            elif isinstance(child, (ast.For, ast.While)):
                feature += "_loop"
            elif isinstance(child, (ast.If,)):
                feature += "_conditional"
            features.append(feature)
        return features

    features1 = get_node_features(node1)
    features2 = get_node_features(node2)

    # Calculate Jaccard similarity
    set1 = set(features1)
    set2 = set(features2)

    intersection = len(set1 & set2)
    union = len(set1 | set2)

    if union == 0:
        return 0.0

    jaccard = intersection / union

    # Also consider sequence similarity
    len_diff = abs(len(features1) - len(features2))
    max_len = max(len(features1), len(features2))
    length_penalty = 1.0 - (len_diff / max_len if max_len > 0 else 0)

    return (jaccard + length_penalty) / 2


def get_function_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """
    Extract function signature for reporting.

    Args:
        node: Function definition node

    Returns:
        Function signature string
    """
    args = []
    for arg in node.args.args:
        arg_str = arg.arg
        if arg.annotation:
            try:
                arg_str += f": {ast.unparse(arg.annotation)}"
            except Exception:
                pass
        args.append(arg_str)

    return_annotation = ""
    if node.returns:
        try:
            return_annotation = f" -> {ast.unparse(node.returns)}"
        except Exception:
            pass

    prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
    return f"{prefix}def {node.name}({', '.join(args)}){return_annotation}"


# =============================================================================
# DETECTION FUNCTIONS
# =============================================================================


def find_python_files(path: Path) -> list[Path]:
    """
    Find all Python files in a directory.

    Args:
        path: Directory to search

    Returns:
        List of Python file paths
    """
    if path.is_file() and path.suffix == ".py":
        return [path]

    return sorted(path.rglob("*.py"))


def parse_file(filepath: Path) -> ast.Module | None:
    """
    Parse a Python file into an AST.

    Args:
        filepath: Path to Python file

    Returns:
        AST module or None if parsing fails
    """
    try:
        content = filepath.read_text(encoding="utf-8")
        return ast.parse(content, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError) as e:
        print(f"  Warning: Could not parse {filepath}: {e}", file=sys.stderr)
        return None


def detect_duplicate_classes(
    files: list[Path],
    base_path: Path,
) -> tuple[list[DuplicateClass], int]:
    """
    Detect duplicate class names across files.

    Args:
        files: List of Python files to scan
        base_path: Base path for relative file paths

    Returns:
        Tuple of (duplicate classes list, total classes count)
    """
    class_locations: dict[str, list[FileLocation]] = defaultdict(list)
    total_classes = 0

    for filepath in files:
        tree = parse_file(filepath)
        if tree is None:
            continue

        rel_path = str(filepath.relative_to(base_path))

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                total_classes += 1
                class_locations[node.name].append((rel_path, node.lineno))

    # Filter to only duplicates
    duplicates = [
        DuplicateClass(name=name, locations=locations)
        for name, locations in class_locations.items()
        if len(locations) > 1
    ]

    return sorted(duplicates, key=lambda x: -len(x.locations)), total_classes


# Dunder methods and common overrides to exclude
EXCLUDED_FUNCTIONS = {
    "__init__",
    "__new__",
    "__del__",
    "__repr__",
    "__str__",
    "__bytes__",
    "__format__",
    "__lt__",
    "__le__",
    "__eq__",
    "__ne__",
    "__gt__",
    "__ge__",
    "__hash__",
    "__bool__",
    "__getattr__",
    "__getattribute__",
    "__setattr__",
    "__delattr__",
    "__dir__",
    "__get__",
    "__set__",
    "__delete__",
    "__init_subclass__",
    "__set_name__",
    "__call__",
    "__len__",
    "__length_hint__",
    "__getitem__",
    "__setitem__",
    "__delitem__",
    "__iter__",
    "__next__",
    "__reversed__",
    "__contains__",
    "__add__",
    "__sub__",
    "__mul__",
    "__matmul__",
    "__truediv__",
    "__floordiv__",
    "__mod__",
    "__divmod__",
    "__pow__",
    "__lshift__",
    "__rshift__",
    "__and__",
    "__xor__",
    "__or__",
    "__neg__",
    "__pos__",
    "__abs__",
    "__invert__",
    "__complex__",
    "__int__",
    "__float__",
    "__round__",
    "__index__",
    "__enter__",
    "__exit__",
    "__await__",
    "__aiter__",
    "__anext__",
    "__aenter__",
    "__aexit__",
    # Common framework methods
    "setUp",
    "tearDown",
    "setUpClass",
    "tearDownClass",
    "setup_method",
    "teardown_method",
    "to_dict",
    "from_dict",
    "validate",
    "model_validate",
    "model_dump",
}


def detect_duplicate_functions(
    files: list[Path],
    base_path: Path,
    min_occurrences: int = 3,
) -> tuple[list[DuplicateFunction], int]:
    """
    Detect duplicate function names across files.

    Args:
        files: List of Python files to scan
        base_path: Base path for relative file paths
        min_occurrences: Minimum occurrences to report as duplicate

    Returns:
        Tuple of (duplicate functions list, total functions count)
    """
    function_data: dict[str, dict[str, list]] = defaultdict(
        lambda: {"locations": [], "signatures": []}
    )
    total_functions = 0

    for filepath in files:
        tree = parse_file(filepath)
        if tree is None:
            continue

        rel_path = str(filepath.relative_to(base_path))

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Skip excluded functions
                if node.name in EXCLUDED_FUNCTIONS:
                    continue
                # Skip private/protected methods (single underscore)
                if node.name.startswith("_") and not node.name.startswith("__"):
                    continue

                total_functions += 1
                function_data[node.name]["locations"].append((rel_path, node.lineno))
                function_data[node.name]["signatures"].append(get_function_signature(node))

    # Filter to duplicates with sufficient occurrences
    duplicates = [
        DuplicateFunction(
            name=name,
            locations=data["locations"],
            signatures=list(set(data["signatures"])),
        )
        for name, data in function_data.items()
        if len(data["locations"]) >= min_occurrences
    ]

    return sorted(duplicates, key=lambda x: -len(x.locations)), total_functions


def extract_schema_fields(
    node: ast.ClassDef,
) -> tuple[list[str], str | None]:
    """
    Extract field names from a Pydantic model or dataclass.

    Args:
        node: Class definition node

    Returns:
        Tuple of (field names list, schema type)
    """
    fields = []
    schema_type = None

    # Check for dataclass decorator
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Name) and decorator.id == "dataclass":
            schema_type = "dataclass"
        elif isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Name) and decorator.func.id == "dataclass":
                schema_type = "dataclass"

    # Check for Pydantic base class
    for base in node.bases:
        base_name = ""
        if isinstance(base, ast.Name):
            base_name = base.id
        elif isinstance(base, ast.Attribute):
            base_name = base.attr

        if base_name in ("BaseModel", "BaseSettings", "BaseSchema"):
            schema_type = "pydantic"

    if schema_type is None:
        return [], None

    # Extract field names
    for child in node.body:
        if isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
            fields.append(child.target.id)
        elif isinstance(child, ast.Assign):
            for target in child.targets:
                if isinstance(target, ast.Name):
                    fields.append(target.id)

    return fields, schema_type


def detect_schema_duplicates(
    files: list[Path],
    base_path: Path,
    min_overlap: float = 0.7,
) -> tuple[list[SchemaOverlap], int]:
    """
    Detect overlapping schema definitions.

    Args:
        files: List of Python files to scan
        base_path: Base path for relative file paths
        min_overlap: Minimum field overlap percentage (0.0-1.0)

    Returns:
        Tuple of (schema overlaps list, total schemas count)
    """
    schemas: list[tuple[str, str, list[str]]] = []  # (name, file, fields)

    for filepath in files:
        tree = parse_file(filepath)
        if tree is None:
            continue

        rel_path = str(filepath.relative_to(base_path))

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                fields, schema_type = extract_schema_fields(node)
                if schema_type and len(fields) >= 2:  # At least 2 fields
                    schemas.append((node.name, rel_path, fields))

    total_schemas = len(schemas)
    overlaps = []

    # Compare all pairs
    for i, (name1, file1, fields1) in enumerate(schemas):
        for name2, file2, fields2 in schemas[i + 1 :]:
            # Skip if same file
            if file1 == file2:
                continue

            common = set(fields1) & set(fields2)
            if len(common) < 2:  # At least 2 common fields
                continue

            # Calculate overlap as percentage of smaller schema
            min_fields = min(len(fields1), len(fields2))
            overlap_pct = len(common) / min_fields

            if overlap_pct >= min_overlap:
                overlaps.append(
                    SchemaOverlap(
                        schema1_name=name1,
                        schema1_file=file1,
                        schema2_name=name2,
                        schema2_file=file2,
                        common_fields=sorted(common),
                        overlap_percentage=overlap_pct * 100,
                        schema1_fields=fields1,
                        schema2_fields=fields2,
                    )
                )

    return sorted(overlaps, key=lambda x: -x.overlap_percentage), total_schemas


def detect_similar_code_blocks(
    files: list[Path],
    base_path: Path,
    similarity_threshold: float = 0.80,
    min_statements: int = 5,
) -> list[SimilarCodeBlock]:
    """
    Detect similar code blocks using AST comparison.

    Args:
        files: List of Python files to scan
        base_path: Base path for relative file paths
        similarity_threshold: Minimum similarity score (0.0-1.0)
        min_statements: Minimum statements in function to consider

    Returns:
        List of similar code blocks
    """
    functions: list[tuple[str, str, int, ast.FunctionDef | ast.AsyncFunctionDef]] = []

    for filepath in files:
        tree = parse_file(filepath)
        if tree is None:
            continue

        rel_path = str(filepath.relative_to(base_path))

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Skip small functions
                stmt_count = sum(1 for _ in ast.walk(node) if isinstance(_, ast.stmt))
                if stmt_count < min_statements:
                    continue
                # Skip test functions
                if node.name.startswith("test_"):
                    continue
                functions.append((node.name, rel_path, node.lineno, node))

    similar_blocks = []

    # Group by AST hash first for efficiency
    hash_groups: dict[str, list[tuple[str, str, int, ASTNode]]] = defaultdict(list)
    for name, file, line, node in functions:
        h = ast_to_hash(node)
        hash_groups[h].append((name, file, line, node))

    # Report exact matches (same hash)
    for h, group in hash_groups.items():
        if len(group) > 1:
            for i, (name1, file1, line1, _node1) in enumerate(group):
                for name2, file2, line2, _node2 in group[i + 1 :]:
                    # Skip same file
                    if file1 == file2:
                        continue
                    similar_blocks.append(
                        SimilarCodeBlock(
                            function1_name=name1,
                            function1_file=file1,
                            function1_line=line1,
                            function2_name=name2,
                            function2_file=file2,
                            function2_line=line2,
                            similarity_score=1.0,
                            ast_hash=h,
                        )
                    )

    # For functions with different hashes, do pairwise comparison
    # This is O(n^2) but we limit to larger functions
    large_functions = [
        (name, file, line, node)
        for name, file, line, node in functions
        if sum(1 for _ in ast.walk(node) if isinstance(_, ast.stmt)) >= min_statements * 2
    ]

    # Limit comparisons to avoid excessive runtime
    if len(large_functions) <= 200:
        for i, (name1, file1, line1, node1) in enumerate(large_functions):
            for name2, file2, line2, node2 in large_functions[i + 1 :]:
                # Skip same file
                if file1 == file2:
                    continue
                # Skip if already found as exact match
                if ast_to_hash(node1) == ast_to_hash(node2):
                    continue

                similarity = calculate_ast_similarity(node1, node2)
                if similarity >= similarity_threshold:
                    similar_blocks.append(
                        SimilarCodeBlock(
                            function1_name=name1,
                            function1_file=file1,
                            function1_line=line1,
                            function2_name=name2,
                            function2_file=file2,
                            function2_line=line2,
                            similarity_score=similarity,
                            ast_hash="partial_match",
                        )
                    )

    return sorted(similar_blocks, key=lambda x: -x.similarity_score)


# =============================================================================
# REPORT FORMATTING
# =============================================================================


def format_markdown_report(report: DuplicationReport) -> str:
    """
    Format report as Markdown.

    Args:
        report: DuplicationReport to format

    Returns:
        Markdown formatted string
    """
    lines = [
        "# Code Duplication Analysis Report",
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "|--------|-------|",
        f"| Files Scanned | {report.files_scanned} |",
        f"| Total Classes | {report.total_classes} |",
        f"| Total Functions | {report.total_functions} |",
        f"| Total Schemas | {report.total_schemas} |",
        f"| **Duplicate Class Names** | {len(report.duplicate_classes)} |",
        f"| **Duplicate Function Names** | {len(report.duplicate_functions)} |",
        f"| **Schema Overlaps** | {len(report.schema_overlaps)} |",
        f"| **Similar Code Blocks** | {len(report.similar_code_blocks)} |",
        f"| **Total Issues** | {report.total_issues} |",
        "",
    ]

    # Duplicate Classes
    if report.duplicate_classes:
        lines.extend(
            [
                "## Duplicate Class Names",
                "",
                "Classes defined multiple times across the codebase:",
                "",
            ]
        )
        for dc in report.duplicate_classes[:20]:  # Limit output
            lines.append(f"### `{dc.name}` ({len(dc.locations)} occurrences)")
            lines.append("")
            for file, line in dc.locations:
                lines.append(f"- `{file}:{line}`")
            lines.append("")

    # Duplicate Functions
    if report.duplicate_functions:
        lines.extend(
            [
                "## Duplicate Function Names",
                "",
                "Functions with the same name in different modules:",
                "",
            ]
        )
        for df in report.duplicate_functions[:20]:
            lines.append(f"### `{df.name}` ({len(df.locations)} occurrences)")
            lines.append("")
            lines.append("**Signatures:**")
            for sig in df.signatures[:3]:
                lines.append(f"- `{sig}`")
            lines.append("")
            lines.append("**Locations:**")
            for file, line in df.locations[:10]:
                lines.append(f"- `{file}:{line}`")
            if len(df.locations) > 10:
                lines.append(f"- ... and {len(df.locations) - 10} more")
            lines.append("")

    # Schema Overlaps
    if report.schema_overlaps:
        lines.extend(
            [
                "## Schema Overlaps",
                "",
                "Pydantic models and dataclasses with overlapping field definitions:",
                "",
            ]
        )
        for so in report.schema_overlaps[:20]:
            lines.append(
                f"### `{so.schema1_name}` <-> `{so.schema2_name}` "
                f"({so.overlap_percentage:.0f}% overlap)"
            )
            lines.append("")
            lines.append(f"- **Schema 1:** `{so.schema1_file}` ({len(so.schema1_fields)} fields)")
            lines.append(f"- **Schema 2:** `{so.schema2_file}` ({len(so.schema2_fields)} fields)")
            lines.append(f"- **Common fields:** `{', '.join(so.common_fields)}`")
            lines.append("")

    # Similar Code Blocks
    if report.similar_code_blocks:
        lines.extend(
            [
                "## Similar Code Blocks",
                "",
                "Functions with >80% structural similarity (potential refactoring targets):",
                "",
            ]
        )
        for scb in report.similar_code_blocks[:20]:
            match_type = "EXACT" if scb.similarity_score == 1.0 else "SIMILAR"
            lines.append(
                f"### [{match_type}] `{scb.function1_name}` <-> `{scb.function2_name}` "
                f"({scb.similarity_score:.0%})"
            )
            lines.append("")
            lines.append(f"- `{scb.function1_file}:{scb.function1_line}`")
            lines.append(f"- `{scb.function2_file}:{scb.function2_line}`")
            lines.append("")

    # Recommendations
    lines.extend(
        [
            "## Recommendations",
            "",
        ]
    )

    if report.duplicate_classes:
        lines.append(
            "1. **Duplicate Classes:** Consider renaming classes to be more specific, "
            "or consolidate duplicate implementations."
        )
    if report.duplicate_functions:
        lines.append(
            "2. **Duplicate Functions:** Review function names for clarity. "
            "Consider extracting common functionality to shared utilities."
        )
    if report.schema_overlaps:
        lines.append(
            "3. **Schema Overlaps:** Consider creating base schemas for common fields, "
            "or use schema composition/inheritance."
        )
    if report.similar_code_blocks:
        lines.append(
            "4. **Similar Code:** Refactor duplicate code into shared functions "
            "to reduce maintenance burden."
        )

    if report.total_issues == 0:
        lines.append("No significant duplication issues detected.")

    lines.append("")
    lines.append("---")
    lines.append("*Generated by detect_duplicates.py*")

    return "\n".join(lines)


def format_text_report(report: DuplicationReport) -> str:
    """
    Format report as plain text summary.

    Args:
        report: DuplicationReport to format

    Returns:
        Plain text formatted string
    """
    lines = [
        "",
        "=" * 60,
        "         CODE DUPLICATION ANALYSIS REPORT",
        "=" * 60,
        "",
        f"  Files scanned:          {report.files_scanned}",
        f"  Total classes:          {report.total_classes}",
        f"  Total functions:        {report.total_functions}",
        f"  Total schemas:          {report.total_schemas}",
        "",
        "-" * 60,
        "  ISSUES FOUND",
        "-" * 60,
        f"  Duplicate class names:  {len(report.duplicate_classes)}",
        f"  Duplicate functions:    {len(report.duplicate_functions)}",
        f"  Schema overlaps:        {len(report.schema_overlaps)}",
        f"  Similar code blocks:    {len(report.similar_code_blocks)}",
        "-" * 60,
        f"  TOTAL ISSUES:           {report.total_issues}",
        "=" * 60,
        "",
    ]

    if report.duplicate_classes:
        lines.append("TOP DUPLICATE CLASSES:")
        for dc in report.duplicate_classes[:5]:
            lines.append(f"  - {dc.name} ({len(dc.locations)} occurrences)")
        lines.append("")

    if report.duplicate_functions:
        lines.append("TOP DUPLICATE FUNCTIONS:")
        for df in report.duplicate_functions[:5]:
            lines.append(f"  - {df.name} ({len(df.locations)} occurrences)")
        lines.append("")

    if report.schema_overlaps:
        lines.append("TOP SCHEMA OVERLAPS:")
        for so in report.schema_overlaps[:5]:
            lines.append(
                f"  - {so.schema1_name} <-> {so.schema2_name} ({so.overlap_percentage:.0f}%)"
            )
        lines.append("")

    if report.similar_code_blocks:
        lines.append("TOP SIMILAR CODE BLOCKS:")
        for scb in report.similar_code_blocks[:5]:
            lines.append(
                f"  - {scb.function1_name} <-> {scb.function2_name} ({scb.similarity_score:.0%})"
            )
        lines.append("")

    return "\n".join(lines)


# =============================================================================
# MAIN
# =============================================================================


def analyze_codebase(
    path: Path,
    checks: list[str] | None = None,
    similarity_threshold: float = 0.80,
    min_function_occurrences: int = 3,
    min_schema_overlap: float = 0.70,
) -> DuplicationReport:
    """
    Analyze a codebase for code duplication.

    Args:
        path: Path to analyze
        checks: List of checks to run (classes, functions, schemas, similar)
        similarity_threshold: Threshold for similar code detection
        min_function_occurrences: Minimum occurrences for function duplicates
        min_schema_overlap: Minimum overlap for schema detection

    Returns:
        DuplicationReport with analysis results
    """
    if checks is None:
        checks = ["classes", "functions", "schemas", "similar"]

    report = DuplicationReport()

    print(f"Scanning {path}...")
    files = find_python_files(path)
    report.files_scanned = len(files)
    print(f"  Found {len(files)} Python files")

    if "classes" in checks:
        print("  Detecting duplicate class names...")
        report.duplicate_classes, report.total_classes = detect_duplicate_classes(files, path)
        print(f"    Found {len(report.duplicate_classes)} duplicates")

    if "functions" in checks:
        print("  Detecting duplicate function names...")
        report.duplicate_functions, report.total_functions = detect_duplicate_functions(
            files, path, min_occurrences=min_function_occurrences
        )
        print(f"    Found {len(report.duplicate_functions)} duplicates")

    if "schemas" in checks:
        print("  Detecting schema overlaps...")
        report.schema_overlaps, report.total_schemas = detect_schema_duplicates(
            files, path, min_overlap=min_schema_overlap
        )
        print(f"    Found {len(report.schema_overlaps)} overlaps")

    if "similar" in checks:
        print("  Detecting similar code blocks...")
        report.similar_code_blocks = detect_similar_code_blocks(
            files, path, similarity_threshold=similarity_threshold
        )
        print(f"    Found {len(report.similar_code_blocks)} similar blocks")

    return report


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Detect code duplication in Python codebases",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic scan of packages/
  %(prog)s

  # Custom path
  %(prog)s --path packages/kagami

  # JSON output for CI
  %(prog)s --format json

  # Markdown report to file
  %(prog)s --format markdown --output report.md

  # CI mode with threshold
  %(prog)s --max-duplicates 10 --fail-on-threshold

  # Only check specific categories
  %(prog)s --check classes functions

  # Adjust similarity threshold
  %(prog)s --similarity-threshold 0.85
        """,
    )

    parser.add_argument(
        "--path",
        type=Path,
        default=Path("packages"),
        help="Path to analyze (default: packages/)",
    )

    parser.add_argument(
        "--format",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output file (default: stdout)",
    )

    parser.add_argument(
        "--check",
        nargs="+",
        choices=["classes", "functions", "schemas", "similar"],
        default=["classes", "functions", "schemas", "similar"],
        help="Categories to check (default: all)",
    )

    parser.add_argument(
        "--similarity-threshold",
        type=float,
        default=0.80,
        help="Similarity threshold for code blocks (0.0-1.0, default: 0.80)",
    )

    parser.add_argument(
        "--min-function-occurrences",
        type=int,
        default=3,
        help="Minimum occurrences to report function as duplicate (default: 3)",
    )

    parser.add_argument(
        "--min-schema-overlap",
        type=float,
        default=0.70,
        help="Minimum field overlap for schema detection (0.0-1.0, default: 0.70)",
    )

    parser.add_argument(
        "--max-duplicates",
        type=int,
        default=0,
        help="Maximum allowed duplicates (0 = no limit)",
    )

    parser.add_argument(
        "--fail-on-threshold",
        action="store_true",
        help="Exit with code 1 if duplicates exceed --max-duplicates",
    )

    args = parser.parse_args()

    # Validate path
    if not args.path.exists():
        print(f"Error: Path does not exist: {args.path}", file=sys.stderr)
        return 1

    # Run analysis
    report = analyze_codebase(
        path=args.path,
        checks=args.check,
        similarity_threshold=args.similarity_threshold,
        min_function_occurrences=args.min_function_occurrences,
        min_schema_overlap=args.min_schema_overlap,
    )

    # Format output
    if args.format == "json":
        output = json.dumps(report.to_dict(), indent=2)
    elif args.format == "markdown":
        output = format_markdown_report(report)
    else:
        output = format_text_report(report)

    # Write output
    if args.output:
        args.output.write_text(output)
        print(f"Report written to {args.output}")
    else:
        print(output)

    # Check threshold
    if args.fail_on_threshold and args.max_duplicates > 0:
        if report.total_issues > args.max_duplicates:
            print(
                f"\nFailed: {report.total_issues} issues exceed threshold of {args.max_duplicates}",
                file=sys.stderr,
            )
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
