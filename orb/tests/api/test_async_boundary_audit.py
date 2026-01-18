from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import ast
from pathlib import Path


@pytest.mark.performance
def test_no_sync_sleep_in_async_paths():
    """Audit for time.sleep() usage inside async defs on hot paths.

    Flags occurrences under `kagami/api` modules, excluding tests and explicit allowlist spots.
    """
    root = Path(__file__).resolve().parents[2] / "kagami" / "api"
    violations: list[str] = []
    allowlist = {
        "routes/auth.py:time.sleep",  # backoff acceptable for SMTP fallback (rare path)
    }

    def check_file(filepath):
        """Check a single file for async time.sleep - closure captures filepath properly."""
        code = filepath.read_text(encoding="utf-8")
        tree = ast.parse(code, filename=str(filepath))
        cur_async: list[bool] = []

        class V(ast.NodeVisitor):
            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
                cur_async.append(True)
                self.generic_visit(node)
                cur_async.pop()

            def visit_Call(self, node: ast.Call):
                # detect time.sleep(...) within async context
                if cur_async and isinstance(node.func, ast.Attribute):
                    if (
                        getattr(node.func, "attr", "") == "sleep"
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "time"
                    ):
                        sig = f"{filepath.relative_to(root).as_posix()}:time.sleep"
                        if sig not in allowlist:
                            violations.append(sig)
                self.generic_visit(node)

        V().visit(tree)

    for py in root.rglob("*.py"):
        check_file(py)

    assert not violations, f"Blocking time.sleep detected in async paths: {violations}"
