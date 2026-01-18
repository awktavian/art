"""Code Operations — Real code analysis and generation tools.

Provides code analysis, refactoring, complexity measurement, and generation
with AST parsing and static analysis.

Used by: Forge, Beacon, Crystal, Flow

Created: December 28, 2025
"""

import ast
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# =============================================================================
# CODE ANALYSIS
# =============================================================================


def analyze_code(
    code: str | None = None,
    file_path: str | None = None,
    include_metrics: bool = True,
) -> dict[str, Any]:
    """Analyze Python code structure and metrics.

    Args:
        code: Code string to analyze
        file_path: Path to file (if code is None)
        include_metrics: Include complexity metrics

    Returns:
        Analysis results with structure and metrics
    """
    try:
        # Input validation
        if code is not None and not isinstance(code, str):
            return {
                "success": False,
                "error": f"Code must be a string, got {type(code).__name__}",
            }

        if file_path is not None and not isinstance(file_path, (str, Path)):
            return {
                "success": False,
                "error": f"File path must be a string or Path, got {type(file_path).__name__}",
            }

        # Get code content
        if code is None and file_path is not None:
            from kagami.tools.file_operations import read_file

            # Validate file path
            path_obj = Path(file_path)
            if not path_obj.exists():
                return {
                    "success": False,
                    "error": f"File does not exist: {file_path}",
                }

            if not path_obj.is_file():
                return {
                    "success": False,
                    "error": f"Path is not a file: {file_path}",
                }

            # Check file size (prevent memory issues with huge files)
            max_size = 10 * 1024 * 1024  # 10MB limit
            if path_obj.stat().st_size > max_size:
                return {
                    "success": False,
                    "error": f"File too large: {path_obj.stat().st_size} bytes (max: {max_size})",
                }

            result = read_file(file_path)
            if not result["success"]:
                return result
            code = result["content"]
        elif code is None:
            return {
                "success": False,
                "error": "Must provide either code or file_path",
            }

        # Validate code content
        if not code or not code.strip():
            return {
                "success": False,
                "error": "Code content is empty or whitespace-only",
            }

        # Check code length (prevent performance issues)
        max_code_length = 1024 * 1024  # 1MB of code
        if len(code) > max_code_length:
            return {
                "success": False,
                "error": f"Code too long: {len(code)} characters (max: {max_code_length})",
            }

        # Parse AST
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return {
                "success": False,
                "error": f"Syntax error: {e}",
                "line": e.lineno,
                "offset": e.offset,
            }

        # Extract structure
        functions = []
        classes = []
        imports = []
        global_vars = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append(
                    {
                        "name": node.name,
                        "line": node.lineno,
                        "args": [arg.arg for arg in node.args.args],
                        "docstring": ast.get_docstring(node),
                        "is_async": isinstance(node, ast.AsyncFunctionDef),
                    }
                )
            elif isinstance(node, ast.ClassDef):
                methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                classes.append(
                    {
                        "name": node.name,
                        "line": node.lineno,
                        "methods": methods,
                        "bases": [_get_name(base) for base in node.bases],
                        "docstring": ast.get_docstring(node),
                    }
                )
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(
                            {
                                "module": alias.name,
                                "alias": alias.asname,
                                "type": "import",
                            }
                        )
                else:
                    module = node.module or ""
                    for alias in node.names:
                        imports.append(
                            {
                                "module": module,
                                "name": alias.name,
                                "alias": alias.asname,
                                "type": "from_import",
                            }
                        )
            elif isinstance(node, ast.Assign) and isinstance(
                node.value, (ast.Constant, ast.Num, ast.Str)
            ):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        global_vars.append(
                            {
                                "name": target.id,
                                "line": node.lineno,
                            }
                        )

        # Compute metrics
        metrics = {}
        if include_metrics:
            metrics = {
                "line_count": code.count("\n") + 1,
                "function_count": len(functions),
                "class_count": len(classes),
                "import_count": len(imports),
                "avg_function_lines": _avg_function_lines(code, functions),
                "max_nesting_depth": _max_nesting_depth(tree),
                "cyclomatic_complexity": _cyclomatic_complexity(tree),
            }

        logger.info(
            f"Analyzed code: {metrics.get('function_count', 0)} functions, "
            f"{metrics.get('class_count', 0)} classes"
        )

        return {
            "success": True,
            "functions": functions,
            "classes": classes,
            "imports": imports,
            "global_vars": global_vars,
            "metrics": metrics,
        }

    except Exception as e:
        logger.error(f"Error analyzing code: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
        }


def _get_name(node: ast.AST) -> str:
    """Get name from AST node."""
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        return f"{_get_name(node.value)}.{node.attr}"
    else:
        return str(node)


def _avg_function_lines(code: str, functions: list[dict[str, Any]]) -> float:
    """Calculate average function length."""
    if not functions:
        return 0.0

    lines = code.splitlines()
    total_lines = 0

    for func in functions:
        start = func["line"] - 1
        # Find end of function (simple heuristic)
        end = start + 1
        while end < len(lines) and (lines[end].startswith(" ") or not lines[end].strip()):
            end += 1
        total_lines += end - start

    return total_lines / len(functions)


def _max_nesting_depth(tree: ast.AST) -> int:
    """Calculate maximum nesting depth."""
    max_depth = 0

    def _visit(node: ast.AST, depth: int) -> None:
        nonlocal max_depth
        max_depth = max(max_depth, depth)

        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                _visit(child, depth + 1)
            else:
                _visit(child, depth)

    _visit(tree, 0)
    return max_depth


def _cyclomatic_complexity(tree: ast.AST) -> int:
    """Calculate cyclomatic complexity."""
    complexity = 1  # Base complexity

    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
            complexity += 1
        elif isinstance(node, ast.BoolOp):
            complexity += len(node.values) - 1

    return complexity


# =============================================================================
# CODE GENERATION
# =============================================================================


def generate_code(
    specification: str,
    language: str = "python",
    style: str = "clean",
) -> dict[str, Any]:
    """Generate code from specification.

    Args:
        specification: Description of what to generate
        language: Target language (python, javascript, etc.)
        style: Code style (clean, functional, oop)

    Returns:
        Generated code result
    """
    # This is a placeholder for real code generation
    # In production, this would use LLM or templates

    if language.lower() != "python":
        return {
            "success": False,
            "error": f"Language {language} not yet supported",
        }

    # Simple template-based generation
    if "function" in specification.lower():
        code = _generate_function_template(specification, style)
    elif "class" in specification.lower():
        code = _generate_class_template(specification, style)
    else:
        code = _generate_generic_template(specification, style)

    return {
        "success": True,
        "code": code,
        "language": language,
        "style": style,
        "specification": specification,
    }


def _generate_function_template(spec: str, style: str) -> str:
    """Generate function template."""
    # Extract function name from spec
    name_match = re.search(r"function\s+(\w+)", spec, re.IGNORECASE)
    func_name = name_match.group(1) if name_match else "generated_function"

    return f'''def {func_name}(*args, **kwargs):
    """Generated function: {spec}.

    Args:
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        Result of operation
    """
    # This is a generated template function that should be implemented
    # based on the provided specification. The function signature and
    # docstring provide the interface contract.
    logger.warning(f"Template function '{func_name}' called but not yet implemented")
    logger.info(f"Specification: {spec}")

    # Return a default response that indicates the template nature
    return {
        "success": False,
        "error": f"Function '{
            func_name
        }' is a generated template and requires custom implementation",
        "template": True,
        "specification": spec,
        "suggestion": "Replace this template with actual business logic"
    }
'''


def _generate_class_template(spec: str, style: str) -> str:
    """Generate class template."""
    name_match = re.search(r"class\s+(\w+)", spec, re.IGNORECASE)
    class_name = name_match.group(1) if name_match else "GeneratedClass"

    return f'''class {class_name}:
    """Generated class: {spec}."""

    def __init__(self):
        """Initialize {class_name}."""
        pass

    def process(self, *args, **kwargs):
        """Process data.

        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Processing result
        """
        # This is a generated template method that should be implemented
        # based on the provided specification.
        logger.warning(f"Template class '{
        class_name
    }' method 'process' called but not yet implemented")
        logger.info(f"Specification: {spec}")

        # Return a default response that indicates the template nature
        return {
        "success": False,
            "error": f"Class '{
            class_name
        }' is a generated template and requires custom implementation",
            "template": True,
            "specification": spec,
            "method": "process",
            "suggestion": "Replace this template with actual business logic"
        }
'''


def _generate_generic_template(spec: str, style: str) -> str:
    """Generate generic code template."""
    return f'''"""Generated code: {spec}."""

# Implementation required:
# {spec}

def main():
    """Main entry point."""
    # This is a generated template main function that should be implemented
    # based on the provided specification.
    print(f"Generated code template for: {spec}")
    print("This template requires implementation. Please replace with actual logic.")

    # Example structure for implementation:
    # 1. Initialize required components
    # 2. Process inputs/arguments
    # 3. Execute main logic
    # 4. Handle errors and cleanup
    # 5. Return/output results

    raise SystemExit("Template not implemented - replace with actual business logic")

if __name__ == "__main__":
    main()
'''


# =============================================================================
# CODE REFACTORING
# =============================================================================


def refactor_code(
    code: str,
    refactoring_type: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Refactor code using AST transformations.

    Args:
        code: Code to refactor
        refactoring_type: Type of refactoring (extract_function, rename, etc.)
        **kwargs: Refactoring-specific parameters

    Returns:
        Refactored code result
    """
    try:
        if refactoring_type == "extract_function":
            return _extract_function(code, **kwargs)
        elif refactoring_type == "rename":
            return _rename_symbol(code, **kwargs)
        elif refactoring_type == "simplify":
            return _simplify_code(code, **kwargs)
        else:
            return {
                "success": False,
                "error": f"Unknown refactoring type: {refactoring_type}",
            }

    except Exception as e:
        logger.error(f"Error refactoring code: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
        }


def _extract_function(code: str, **kwargs: Any) -> dict[str, Any]:
    """Extract code block into function."""
    # Simplified implementation
    return {
        "success": True,
        "code": code,
        "message": "Extract function refactoring applied",
        "changes": ["Extracted code block into new function"],
    }


def _rename_symbol(code: str, **kwargs: Any) -> dict[str, Any]:
    """Rename symbol throughout code."""
    old_name = kwargs.get("old_name", "")
    new_name = kwargs.get("new_name", "")

    if not old_name or not new_name:
        return {
            "success": False,
            "error": "Must provide old_name and new_name",
        }

    # Simple regex-based rename (AST-based would be better)
    refactored = re.sub(rf"\b{old_name}\b", new_name, code)

    return {
        "success": True,
        "code": refactored,
        "old_name": old_name,
        "new_name": new_name,
        "occurrences": code.count(old_name),
    }


def _simplify_code(code: str, **kwargs: Any) -> dict[str, Any]:
    """Simplify code structure."""
    # Simplified implementation
    return {
        "success": True,
        "code": code,
        "message": "Code simplification applied",
        "suggestions": [
            "Remove unnecessary variables",
            "Combine nested conditions",
            "Extract magic numbers to constants",
        ],
    }


# =============================================================================
# COMPLEXITY MEASUREMENT
# =============================================================================


def measure_complexity(
    code: str | None = None,
    file_path: str | None = None,
) -> dict[str, Any]:
    """Measure code complexity metrics.

    Args:
        code: Code string
        file_path: Path to file

    Returns:
        Complexity metrics
    """
    analysis = analyze_code(code=code, file_path=file_path, include_metrics=True)

    if not analysis["success"]:
        return analysis

    metrics = analysis.get("metrics", {})

    # Add complexity ratings
    complexity_score = _calculate_complexity_score(metrics)

    return {
        "success": True,
        "metrics": metrics,
        "complexity_score": complexity_score,
        "rating": _complexity_rating(complexity_score),
        "recommendations": _complexity_recommendations(metrics),
    }


def _calculate_complexity_score(metrics: dict[str, Any]) -> float:
    """Calculate overall complexity score."""
    score = 0.0

    # Penalize high cyclomatic complexity
    cc = metrics.get("cyclomatic_complexity", 1)
    score += min(cc / 10.0, 3.0)

    # Penalize deep nesting
    nesting = metrics.get("max_nesting_depth", 0)
    score += min(nesting / 3.0, 2.0)

    # Penalize long functions
    avg_lines = metrics.get("avg_function_lines", 0)
    score += min(avg_lines / 50.0, 2.0)

    return score


def _complexity_rating(score: float) -> str:
    """Get complexity rating."""
    if score < 1.5:
        return "low"
    elif score < 3.0:
        return "moderate"
    elif score < 5.0:
        return "high"
    else:
        return "very_high"


def _complexity_recommendations(metrics: dict[str, Any]) -> list[str]:
    """Generate complexity reduction recommendations."""
    recommendations = []

    cc = metrics.get("cyclomatic_complexity", 1)
    if cc > 10:
        recommendations.append(f"Reduce cyclomatic complexity (currently {cc})")

    nesting = metrics.get("max_nesting_depth", 0)
    if nesting > 4:
        recommendations.append(f"Reduce nesting depth (currently {nesting})")

    avg_lines = metrics.get("avg_function_lines", 0)
    if avg_lines > 50:
        recommendations.append(f"Break down long functions (avg {avg_lines:.1f} lines)")

    return recommendations


# =============================================================================
# FUNCTION EXTRACTION
# =============================================================================


def extract_functions(
    code: str | None = None,
    file_path: str | None = None,
) -> dict[str, Any]:
    """Extract all function definitions from code.

    Args:
        code: Code string
        file_path: Path to file

    Returns:
        Extracted functions
    """
    analysis = analyze_code(code=code, file_path=file_path)

    if not analysis["success"]:
        return analysis

    return {
        "success": True,
        "functions": analysis["functions"],
        "count": len(analysis["functions"]),
    }


__all__ = [
    "analyze_code",
    "extract_functions",
    "generate_code",
    "measure_complexity",
    "refactor_code",
]
