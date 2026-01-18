"""Kagami Tools — Real tool implementations for colony agents.

This module provides the actual tool implementations that colony agents use
to perform their tasks. Each colony has specialized tools:

- Spark (Ideation): brainstorm, generate_ideas, ideate_variations
- Forge (Building): build_component, compile_project, package_artifact
- Flow (Debugging): analyze_error, suggest_fix, debug_trace
- Nexus (Integration): integrate_components, resolve_conflicts, validate_integration
- Beacon (Planning): create_plan, break_down_task, estimate_effort
- Grove (Research): search_knowledge, summarize_research, extract_insights
- Crystal (Testing): generate_tests, run_test_suite, analyze_coverage

All tools return structured results with error handling and logging.

Created: December 28, 2025
"""

import logging
from typing import Any

from kagami.tools.build_operations import (
    build_component,
    compile_project,
    deploy_service,
    package_artifact,
    validate_build,
)
from kagami.tools.code_operations import (
    analyze_code,
    extract_functions,
    generate_code,
    measure_complexity,
    refactor_code,
)
from kagami.tools.debug_operations import (
    analyze_error,
    debug_trace,
    diagnose_issue,
    profile_execution,
    suggest_fix,
)
from kagami.tools.file_operations import (
    list_directory,
    read_file,
    search_files,
    write_file,
)
from kagami.tools.ideation_operations import (
    brainstorm,
    explore_concepts,
    generate_ideas,
    ideate_variations,
)
from kagami.tools.research_operations import (
    extract_insights,
    search_knowledge,
    summarize_research,
    synthesize_findings,
)
from kagami.tools.test_operations import (
    analyze_coverage,
    generate_tests,
    measure_quality,
    run_test_suite,
)

logger = logging.getLogger(__name__)

# =============================================================================
# TOOL REGISTRY
# =============================================================================

# Maps tool names to their implementations
TOOL_REGISTRY: dict[str, Any] = {
    # File operations
    "read_file": read_file,
    "write_file": write_file,
    "search_files": search_files,
    "list_directory": list_directory,
    # Code operations
    "analyze_code": analyze_code,
    "refactor_code": refactor_code,
    "generate_code": generate_code,
    "extract_functions": extract_functions,
    "measure_complexity": measure_complexity,
    # Research operations
    "search_knowledge": search_knowledge,
    "summarize_research": summarize_research,
    "extract_insights": extract_insights,
    "synthesize_findings": synthesize_findings,
    # Debug operations
    "analyze_error": analyze_error,
    "suggest_fix": suggest_fix,
    "debug_trace": debug_trace,
    "profile_execution": profile_execution,
    "diagnose_issue": diagnose_issue,
    # Test operations
    "generate_tests": generate_tests,
    "run_test_suite": run_test_suite,
    "analyze_coverage": analyze_coverage,
    "measure_quality": measure_quality,
    # Build operations
    "build_component": build_component,
    "compile_project": compile_project,
    "package_artifact": package_artifact,
    "deploy_service": deploy_service,
    "validate_build": validate_build,
    # Ideation operations
    "brainstorm": brainstorm,
    "generate_ideas": generate_ideas,
    "ideate_variations": ideate_variations,
    "explore_concepts": explore_concepts,
}


def get_tool(tool_name: str) -> Any | None:
    """Get tool implementation by name.

    Args:
        tool_name: Name of the tool

    Returns:
        Tool function or None if not found
    """
    return TOOL_REGISTRY.get(tool_name)


def list_tools() -> list[str]:
    """List all available tool names.

    Returns:
        List of tool names
    """
    return list(TOOL_REGISTRY.keys())


def get_tools_for_colony(colony_name: str) -> list[str]:
    """Get recommended tools for a specific colony.

    Args:
        colony_name: Name of the colony (spark, forge, flow, nexus, beacon, grove, crystal)

    Returns:
        List of tool names recommended for that colony
    """
    colony_tools = {
        "spark": [
            "brainstorm",
            "generate_ideas",
            "ideate_variations",
            "explore_concepts",
        ],
        "forge": [
            "build_component",
            "compile_project",
            "package_artifact",
            "deploy_service",
            "validate_build",
            "generate_code",
            "refactor_code",
        ],
        "flow": [
            "analyze_error",
            "suggest_fix",
            "debug_trace",
            "profile_execution",
            "diagnose_issue",
            "analyze_code",
        ],
        "nexus": [
            "integrate_components",
            "resolve_conflicts",
            "validate_integration",
            "search_files",
            "list_directory",
        ],
        "beacon": [
            "create_plan",
            "break_down_task",
            "estimate_effort",
            "analyze_code",
            "measure_complexity",
        ],
        "grove": [
            "search_knowledge",
            "summarize_research",
            "extract_insights",
            "synthesize_findings",
            "read_file",
            "search_files",
        ],
        "crystal": [
            "generate_tests",
            "run_test_suite",
            "analyze_coverage",
            "measure_quality",
            "analyze_code",
            "validate_build",
        ],
    }

    return colony_tools.get(colony_name.lower(), [])


__all__ = [
    # Tool registry
    "TOOL_REGISTRY",
    # Code operations
    "analyze_code",
    "analyze_coverage",
    # Debug operations
    "analyze_error",
    # Ideation operations
    "brainstorm",
    # Build operations
    "build_component",
    "compile_project",
    "debug_trace",
    "deploy_service",
    "diagnose_issue",
    "explore_concepts",
    "extract_functions",
    "extract_insights",
    "generate_code",
    "generate_ideas",
    # Test operations
    "generate_tests",
    "get_tool",
    "get_tools_for_colony",
    "ideate_variations",
    "list_directory",
    "list_tools",
    "measure_complexity",
    "measure_quality",
    "package_artifact",
    "profile_execution",
    # File operations
    "read_file",
    "refactor_code",
    "run_test_suite",
    "search_files",
    # Research operations
    "search_knowledge",
    "suggest_fix",
    "summarize_research",
    "synthesize_findings",
    "validate_build",
    "write_file",
]
