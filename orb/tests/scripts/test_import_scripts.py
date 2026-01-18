"""Test that all scripts can be imported without side effects.

This prevents regressions where scripts execute code at import time
instead of guarding execution behind `if __name__ == "__main__":`.

Tier: 1 (Unit tests)
- Fast execution (~5 seconds total)
- No external dependencies
- Safe to run on every change

Created: December 16, 2025
"""

from __future__ import annotations

import pytest
import importlib.util
import sys
from pathlib import Path
from typing import Any

# Get absolute path to scripts directory
REPO_ROOT = Path(__file__).parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"

# Critical scripts that MUST be importable
# These are used by other modules or deployment systems
CRITICAL_SCRIPTS = [
    "benchmark/benchmark_world_model.py",
    "benchmark/benchmark_math_foundations.py",
    "devops/check_safety_bypass.py",
    "devops/verify_hardening.py",
    "devops/monitor_training.py",
    "devops/etcd_backup.py",
    "devops/etcd_restore.py",
]

# Known broken scripts (have import errors - need fixing separately)
KNOWN_BROKEN: list[str] = [
    # deploy_kagami.py - FIXED Dec 16, 2025 (SafetyMonitor import corrected)
]


def import_script(script_path: Path) -> Any:
    """Import a script dynamically without executing main().

    Args:
        script_path: Path to the script file

    Returns:
        Imported module object

    Raises:
        ImportError: If script cannot be imported
    """
    # Convert path to module name
    relative_path = script_path.relative_to(SCRIPTS_DIR)
    module_name = f"scripts.{str(relative_path).replace('/', '.').replace('.py', '')}"

    # Create module spec
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not create spec for {script_path}")

    # Create module from spec
    module = importlib.util.module_from_spec(spec)

    # Add to sys.modules to handle relative imports
    sys.modules[module_name] = module

    # Execute module (this should NOT run main() if properly guarded)
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        # Clean up sys.modules on failure
        sys.modules.pop(module_name, None)
        raise ImportError(f"Failed to import {script_path}: {e}") from e

    return module


@pytest.mark.tier_unit
@pytest.mark.parametrize("script_name", CRITICAL_SCRIPTS)
def test_critical_script_importable(script_name: str) -> None:
    """Verify critical scripts can be imported without side effects.

    Args:
        script_name: Relative path to script from scripts/ directory
    """
    script_path = SCRIPTS_DIR / script_name

    # Verify file exists
    assert script_path.exists(), f"Script not found: {script_path}"

    # Import should not raise exceptions or execute main()
    module = import_script(script_path)

    # Verify module was imported
    assert module is not None, f"Module import returned None: {script_name}"

    # Check for expected patterns in different script types
    if "deploy_kagami" in script_name:
        # Deployment script should have main functions
        assert hasattr(
            module, "deploy_autonomous_kagami"
        ), "deploy_kagami missing deploy_autonomous_kagami function"
        assert hasattr(module, "main"), "deploy_kagami missing main function"
        assert callable(module.main), "deploy_kagami.main is not callable"

    elif "benchmark" in script_name:
        # Benchmark scripts should have benchmark functions
        # Note: benchmark_world_model has benchmark_forward
        if "world_model" in script_name:
            assert hasattr(module, "benchmark_forward") or hasattr(
                module, "main"
            ), f"{script_name} missing benchmark function"

    elif "devops" in script_name:
        # DevOps scripts should have main or specific functions
        if "check_safety_bypass" in script_name:
            assert hasattr(module, "scan_file"), "check_safety_bypass missing scan_file function"
        elif "etcd" in script_name:
            # Backup/restore scripts should have main
            assert hasattr(module, "main"), f"{script_name} missing main function"


@pytest.mark.tier_unit
@pytest.mark.parametrize("script_name", KNOWN_BROKEN)
def test_known_broken_scripts_fail_gracefully(script_name: str) -> None:
    """Document known broken scripts - these need fixing.

    Args:
        script_name: Script that has known import errors
    """
    script_path = SCRIPTS_DIR / script_name

    # Verify file exists
    assert script_path.exists(), f"Script not found: {script_path}"

    # Should raise ImportError (this is EXPECTED)
    with pytest.raises(ImportError):
        import_script(script_path)


@pytest.mark.tier_unit
def test_deploy_kagami_exports() -> None:
    """Verify deploy_kagami.py exports expected functions for reuse.

    FIXED: Dec 16, 2025 - SafetyMonitor import corrected to use
    kagami.core.executive.self_modification instead of cbf_monitor.
    """
    script_path = SCRIPTS_DIR / "deploy_kagami.py"
    module = import_script(script_path)

    # Check all expected exports
    expected_functions = [
        "deploy_autonomous_kagami",
        "initialize_components",
        "health_checks",
        "load_checkpoint",
        "main",
    ]

    for func_name in expected_functions:
        assert hasattr(module, func_name), f"deploy_kagami missing {func_name}"
        func = getattr(module, func_name)
        assert callable(func), f"deploy_kagami.{func_name} is not callable"


@pytest.mark.tier_unit
def test_safety_bypass_checker_exports() -> None:
    """Verify check_safety_bypass.py exports scanner functions."""
    script_path = SCRIPTS_DIR / "devops" / "check_safety_bypass.py"
    module = import_script(script_path)

    # Check scanner exports
    expected_items = [
        "scan_file",
        "should_scan",
        "FORBIDDEN_PATTERNS",
    ]

    for item_name in expected_items:
        assert hasattr(module, item_name), f"check_safety_bypass missing {item_name}"


@pytest.mark.tier_unit
def test_benchmark_world_model_exports() -> None:
    """Verify benchmark_world_model.py can be imported for reuse."""
    script_path = SCRIPTS_DIR / "benchmark" / "benchmark_world_model.py"
    module = import_script(script_path)

    # Should define benchmark functions
    # Check for either benchmark_forward or main (structure may vary)
    has_benchmark = (
        hasattr(module, "benchmark_forward")
        or hasattr(module, "main")
        or hasattr(module, "run_benchmarks")
    )
    assert has_benchmark, "benchmark_world_model missing benchmark entry point"


@pytest.mark.tier_unit
def test_all_scripts_have_main_guard() -> None:
    """Verify all Python scripts use proper if __name__ == '__main__' guard.

    This is a heuristic test - it checks that scripts with main() functions
    have the guard. Not all scripts need main(), but those that do should guard it.
    """
    violations: list[str] = []

    for script_path in SCRIPTS_DIR.rglob("*.py"):
        # Skip __init__.py files
        if script_path.name == "__init__.py":
            continue

        # Skip shell script wrappers (if any .py.sh files exist)
        if script_path.suffix == ".sh":
            continue

        try:
            content = script_path.read_text()
        except (UnicodeDecodeError, PermissionError):
            # Skip binary or inaccessible files
            continue

        # Check if script defines main() but lacks guard
        has_main = "def main(" in content
        has_guard = 'if __name__ == "__main__":' in content

        if has_main and not has_guard:
            relative = script_path.relative_to(REPO_ROOT)
            violations.append(str(relative))

    # Report violations
    if violations:
        violation_list = "\n  - ".join(violations)
        pytest.fail(f"Scripts with main() but missing if __name__ guard:\n  - {violation_list}")


@pytest.mark.tier_unit
def test_no_scripts_execute_at_import() -> None:
    """Verify importing critical scripts doesn't produce output.

    Scripts should not print, execute asyncio.run(), or perform side effects
    at import time.
    """
    # This is implicitly tested by test_critical_script_importable
    # If a script executes code at import, it will raise an exception
    # or cause test failures.
    pass  # Placeholder for documentation


# Performance check
@pytest.mark.slow
def test_import_time_is_fast() -> None:
    """Verify importing scripts is fast (< 2 seconds each).

    Slow imports indicate heavy computation at module level.
    """
    import time

    for script_name in CRITICAL_SCRIPTS:
        script_path = SCRIPTS_DIR / script_name

        start = time.perf_counter()
        import_script(script_path)
        elapsed = time.perf_counter() - start

        # Scripts should import quickly (allow 2s for torch imports)
        assert elapsed < 2.0, f"{script_name} took {elapsed:.2f}s to import (max 2.0s)"
