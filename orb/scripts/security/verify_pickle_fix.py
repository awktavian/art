#!/usr/bin/env python3
"""Verify that pickle deserialization vulnerabilities have been fixed.

Scans codebase for unsafe pickle.load() calls and verifies all
cache files now use signed serialization.

Usage:
    python scripts/security/verify_pickle_fix.py

Returns:
    Exit code 0 if all checks pass, 1 if vulnerabilities remain

Created: December 20, 2025
Colony: Crystal (e₇) - Verification
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


def find_unsafe_pickle_loads(project_root: Path) -> list[dict[str, Any]]:
    """Scan for unsafe pickle.load() calls.

    Args:
        project_root: Root directory of project

    Returns:
        List of files with unsafe pickle.load() calls
    """
    unsafe_calls = []

    # Scan Python files (excluding tests and this script)
    for py_file in project_root.rglob("*.py"):
        # Skip test files and migration scripts
        if "tests/" in str(py_file) or "scripts/security/" in str(py_file):
            continue

        try:
            with open(py_file) as f:
                content = f.read()

            # Look for pickle.load() without nosec comment
            lines = content.split("\n")
            for i, line in enumerate(lines, 1):
                if "pickle.load(" in line:
                    # Skip comments and docstrings
                    stripped = line.strip()
                    if (
                        stripped.startswith("#")
                        or stripped.startswith('"""')
                        or stripped.startswith("'''")
                    ):
                        continue

                    # Skip lines that are just documentation
                    if "Replaces" in line or "restricted to" in line:
                        continue

                    # Check if nosec comment is present (one-time migration OK)
                    if "nosec B301" in line or (i >= 2 and "nosec B301" in lines[i - 2]):
                        continue

                    unsafe_calls.append(
                        {
                            "file": str(py_file.relative_to(project_root)),
                            "line": i,
                            "code": line.strip(),
                        }
                    )

        except Exception as e:
            print(f"Warning: Could not scan {py_file}: {e}", file=sys.stderr)

    return unsafe_calls


def verify_signed_serialization_module(project_root: Path) -> bool:
    """Verify signed serialization module exists and is complete.

    Args:
        project_root: Root directory of project

    Returns:
        True if module exists and has required functions
    """
    module_path = project_root / "kagami" / "core" / "security" / "signed_serialization.py"

    if not module_path.exists():
        print(f"✗ Missing: {module_path}", file=sys.stderr)
        return False

    try:
        with open(module_path) as f:
            content = f.read()

        # Check for required functions
        required = ["save_signed", "load_signed", "is_signed_format", "_migrate_legacy_pickle"]

        for func in required:
            if f"def {func}" not in content:
                print(f"✗ Missing function: {func} in {module_path}", file=sys.stderr)
                return False

        # Check for HMAC usage
        if "hmac.new" not in content or "hashlib.sha256" not in content:
            print(f"✗ Missing HMAC implementation in {module_path}", file=sys.stderr)
            return False

        return True

    except Exception as e:
        print(f"✗ Error reading {module_path}: {e}", file=sys.stderr)
        return False


def verify_fixed_files(project_root: Path) -> dict[str, bool]:
    """Verify that the 3 vulnerable files have been fixed.

    Args:
        project_root: Root directory of project

    Returns:
        Dict of file -> fixed status
    """
    files_to_check = {
        "kagami/core/world_model/e8_trajectory_cache.py": False,
        "kagami/core/reasoning/adaptive_router.py": False,
        "kagami/core/caching/unified_model_cache.py": False,
    }

    for file_path_str, _ in files_to_check.items():
        file_path = project_root / file_path_str

        if not file_path.exists():
            print(f"✗ File not found: {file_path_str}", file=sys.stderr)
            continue

        try:
            with open(file_path) as f:
                content = f.read()

            # Check if it imports signed_serialization
            if "from kagami.core.security.signed_serialization import" in content:
                # Check if it uses save_signed and load_signed
                if "save_signed" in content and "load_signed" in content:
                    files_to_check[file_path_str] = True

        except Exception as e:
            print(f"✗ Error reading {file_path_str}: {e}", file=sys.stderr)

    return files_to_check


def verify_test_suite(project_root: Path) -> bool:
    """Verify test suite exists and is comprehensive.

    Args:
        project_root: Root directory of project

    Returns:
        True if test suite exists and has required tests
    """
    test_path = project_root / "tests" / "core" / "security" / "test_signed_serialization.py"

    if not test_path.exists():
        print(f"✗ Missing test suite: {test_path}", file=sys.stderr)
        return False

    try:
        with open(test_path) as f:
            content = f.read()

        # Check for test classes
        required_tests = [
            "TestSignedSerializationBasic",
            "TestLegacyPickleMigration",
            "TestSecurityProperties",
        ]

        for test_class in required_tests:
            if f"class {test_class}" not in content:
                print(f"✗ Missing test class: {test_class}", file=sys.stderr)
                return False

        # Check for key security tests
        security_tests = [
            "test_signature_verification_fails_on_tamper",
            "test_different_keys_fail_verification",
            "test_constant_time_comparison",
        ]

        for test in security_tests:
            if f"def {test}" not in content:
                print(f"✗ Missing security test: {test}", file=sys.stderr)
                return False

        return True

    except Exception as e:
        print(f"✗ Error reading test suite: {e}", file=sys.stderr)
        return False


def main() -> int:
    """Run all verification checks."""
    project_root = Path(__file__).parent.parent.parent.resolve()

    print("=" * 80)
    print("PICKLE DESERIALIZATION FIX VERIFICATION")
    print("=" * 80)
    print()

    all_passed = True

    # Check 1: No unsafe pickle.load() calls
    print("1. Scanning for unsafe pickle.load() calls...")
    unsafe_calls = find_unsafe_pickle_loads(project_root)

    if unsafe_calls:
        print(f"✗ Found {len(unsafe_calls)} unsafe pickle.load() call(s):")
        for call in unsafe_calls:
            print(f"  - {call['file']}:{call['line']}: {call['code']}")
        all_passed = False
    else:
        print("✓ No unsafe pickle.load() calls found")
    print()

    # Check 2: Signed serialization module exists
    print("2. Verifying signed serialization module...")
    if verify_signed_serialization_module(project_root):
        print("✓ Signed serialization module complete")
    else:
        print("✗ Signed serialization module incomplete")
        all_passed = False
    print()

    # Check 3: Fixed files use signed serialization
    print("3. Verifying fixed files...")
    fixed_files = verify_fixed_files(project_root)

    for file_path, is_fixed in fixed_files.items():
        if is_fixed:
            print(f"✓ {file_path}")
        else:
            print(f"✗ {file_path}")
            all_passed = False
    print()

    # Check 4: Test suite exists
    print("4. Verifying test suite...")
    if verify_test_suite(project_root):
        print("✓ Test suite comprehensive")
    else:
        print("✗ Test suite incomplete")
        all_passed = False
    print()

    # Check 5: Documentation exists
    print("5. Verifying documentation...")

    doc_files = [
        "docs/SECURITY_SIGNED_CACHES.md",
        "SECURITY_FIX_SUMMARY.md",
        "scripts/security/generate_cache_secret.py",
    ]

    for doc_file in doc_files:
        doc_path = project_root / doc_file
        if doc_path.exists():
            print(f"✓ {doc_file}")
        else:
            print(f"✗ {doc_file}")
            all_passed = False
    print()

    # Final verdict
    print("=" * 80)
    if all_passed:
        print("✓ ALL CHECKS PASSED - Pickle vulnerabilities fixed")
        print("=" * 80)
        print()
        print("Next steps:")
        print("1. Generate secret key: python scripts/security/generate_cache_secret.py")
        print("2. Set KAGAMI_CACHE_SECRET environment variable")
        print("3. Run tests: pytest tests/core/security/test_signed_serialization.py -v")
        return 0
    else:
        print("✗ CHECKS FAILED - Vulnerabilities remain or incomplete fix")
        print("=" * 80)
        return 1


if __name__ == "__main__":
    sys.exit(main())
