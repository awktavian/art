"""Debug Operations — Error analysis and diagnostic tools.

Provides error analysis, fix suggestions, tracing, and profiling for Flow agent.

Used by: Flow

Created: December 28, 2025
"""

import logging
import re
import traceback
from typing import Any

logger = logging.getLogger(__name__)


def analyze_error(
    error: str | Exception,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Analyze error and provide diagnostic information.

    Args:
        error: Error message or exception
        context: Additional context

    Returns:
        Error analysis with diagnosis
    """
    try:
        error_str = str(error)
        error_type = type(error).__name__ if isinstance(error, Exception) else "Unknown"

        # Extract stack trace
        stack_trace = None
        if isinstance(error, Exception):
            stack_trace = "".join(
                traceback.format_exception(type(error), error, error.__traceback__)
            )

        # Pattern matching for common errors
        patterns = {
            "AttributeError": r"'(\w+)' object has no attribute '(\w+)'",
            "KeyError": r"'(\w+)'",
            "TypeError": r"(\w+)\(\) (missing|takes|got)",
            "ValueError": r"invalid literal",
            "ImportError": r"No module named '(\w+)'",
        }

        diagnosis = "Unknown error type"
        for error_name, pattern in patterns.items():
            if error_name in error_type or error_name.lower() in error_str.lower():
                match = re.search(pattern, error_str)
                if match:
                    diagnosis = f"{error_name} detected"
                    break

        return {
            "success": True,
            "error_type": error_type,
            "error_message": error_str,
            "diagnosis": diagnosis,
            "stack_trace": stack_trace,
            "severity": _assess_severity(error_type),
            "context": context or {},
        }

    except Exception as e:
        logger.error(f"Error analysis failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
        }


def suggest_fix(
    error: str | Exception,
    code: str | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Suggest fixes for error.

    Args:
        error: Error message or exception
        code: Code where error occurred
        context: Additional context

    Returns:
        Fix suggestions
    """
    try:
        analysis = analyze_error(error, context)
        if not analysis["success"]:
            return analysis

        error_type = analysis["error_type"]
        suggestions = []

        # Common fix patterns
        if "AttributeError" in error_type:
            suggestions.append(
                {
                    "fix": "Check object type and available attributes",
                    "code": "# Use hasattr() to check if attribute exists\nif hasattr(obj, 'attribute'):\n    obj.attribute",
                    "confidence": 0.8,
                }
            )

        elif "KeyError" in error_type:
            suggestions.append(
                {
                    "fix": "Use .get() method or check if key exists",
                    "code": "# Safe dictionary access\nvalue = dict[str, Any].get('key', default_value)",
                    "confidence": 0.9,
                }
            )

        elif "TypeError" in error_type:
            suggestions.append(
                {
                    "fix": "Check function signature and argument types",
                    "code": "# Verify function arguments match signature",
                    "confidence": 0.7,
                }
            )

        elif "ImportError" in error_type:
            suggestions.append(
                {
                    "fix": "Install missing package or check import path",
                    "code": "# pip install <package-name>",
                    "confidence": 0.9,
                }
            )

        else:
            suggestions.append(
                {
                    "fix": "Review error message and stack trace for clues",
                    "confidence": 0.5,
                }
            )

        return {
            "success": True,
            "error_analysis": analysis,
            "suggestions": suggestions,
            "suggestion_count": len(suggestions),
        }

    except Exception as e:
        logger.error(f"Fix suggestion failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
        }


def debug_trace(
    function_name: str,
    args: tuple[Any, ...] | None = None,
    kwargs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Trace function execution.

    Args:
        function_name: Name of function to trace
        args: Function arguments
        kwargs: Function keyword arguments

    Returns:
        Trace information
    """
    try:
        trace_info = {
            "function": function_name,
            "args": args or (),
            "kwargs": kwargs or {},
            "timestamp": __import__("time").time(),
        }

        logger.debug(f"Trace: {function_name}({args}, {kwargs})")

        return {
            "success": True,
            "trace": trace_info,
            "message": f"Traced execution of {function_name}",
        }

    except Exception as e:
        logger.error(f"Debug trace failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
        }


def profile_execution(
    code: str,
    repeat: int = 1,
) -> dict[str, Any]:
    """Profile code execution time.

    Args:
        code: Code to profile
        repeat: Number of repetitions

    Returns:
        Profiling results
    """
    try:
        import time
        import timeit

        # Safety: only allow simple expressions
        if any(keyword in code for keyword in ["import", "exec", "eval", "__"]):
            return {
                "success": False,
                "error": "Unsafe code not allowed in profiling",
            }

        # Time execution
        start = time.time()
        execution_time = timeit.timeit(code, number=repeat)
        end = time.time()

        avg_time = execution_time / repeat

        return {
            "success": True,
            "code": code,
            "total_time": execution_time,
            "avg_time": avg_time,
            "repeat_count": repeat,
            "overhead": end - start - execution_time,
        }

    except Exception as e:
        logger.error(f"Profiling failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "code": code,
        }


def diagnose_issue(
    symptoms: str,
    logs: str | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Diagnose system issue from symptoms.

    Args:
        symptoms: Description of symptoms
        logs: Log output
        context: Additional context

    Returns:
        Diagnostic report
    """
    try:
        diagnosis = {
            "symptoms": symptoms,
            "potential_causes": [],
            "recommended_actions": [],
            "severity": "unknown",
        }

        # Pattern matching for common issues
        symptoms_lower = symptoms.lower()

        if "slow" in symptoms_lower or "performance" in symptoms_lower:
            diagnosis["potential_causes"].append("Performance bottleneck")
            diagnosis["recommended_actions"].append("Profile code execution")
            diagnosis["severity"] = "medium"

        if "crash" in symptoms_lower or "error" in symptoms_lower:
            diagnosis["potential_causes"].append("Unhandled exception")
            diagnosis["recommended_actions"].append("Review stack trace")
            diagnosis["severity"] = "high"

        if "memory" in symptoms_lower or "leak" in symptoms_lower:
            diagnosis["potential_causes"].append("Memory leak")
            diagnosis["recommended_actions"].append("Monitor memory usage")
            diagnosis["severity"] = "high"

        # Analyze logs if provided
        if logs:
            if "error" in logs.lower():
                diagnosis["potential_causes"].append("Error in logs")
            if "warning" in logs.lower():
                diagnosis["potential_causes"].append("Warnings detected")

        return {
            "success": True,
            "diagnosis": diagnosis,
            "confidence": 0.7,
        }

    except Exception as e:
        logger.error(f"Diagnosis failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
        }


def _assess_severity(error_type: str) -> str:
    """Assess error severity."""
    high_severity = ["SystemError", "MemoryError", "RecursionError", "SystemExit"]
    medium_severity = ["ValueError", "TypeError", "AttributeError", "KeyError"]

    if any(severe in error_type for severe in high_severity):
        return "high"
    elif any(medium in error_type for medium in medium_severity):
        return "medium"
    else:
        return "low"


__all__ = [
    "analyze_error",
    "debug_trace",
    "diagnose_issue",
    "profile_execution",
    "suggest_fix",
]
