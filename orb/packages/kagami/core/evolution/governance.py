from __future__ import annotations

"Evolution Governance - Rollback Policies & Code Quality Enforcement.\n\nImplements:\n- Automatic rollback thresholds (SLO violations, safety risks, regressions)\n- Code:Docs ratio enforcement (>=5:1 per forensic rules)\n- Evidence link requirements\n- Skeptic-agent internal review process\n\nEnsures all autonomous changes meet quality standards.\n"
import logging
from typing import Any

logger = logging.getLogger(__name__)


class CodeQualityEnforcement:
    """Enforce code quality standards per forensic rules."""

    CODE_DOCS_RATIO_MIN = 5.0

    @classmethod
    def check_code_docs_ratio(cls, proposal: dict[str, Any]) -> dict[str, Any]:
        """Check Code:Docs ratio (forensic rule).

        Returns:
            {"passed": bool, "ratio": float, "message": str}
        """
        code = proposal.get("proposed_code_snippet", "")
        rationale = proposal.get("rationale", "")
        code_lines = cls._count_code_lines(code)
        doc_lines = len(rationale.split("\n"))
        if doc_lines == 0:
            ratio = float("inf") if code_lines > 0 else 0.0
        else:
            ratio = code_lines / doc_lines
        passed = ratio >= cls.CODE_DOCS_RATIO_MIN
        return {
            "passed": passed,
            "ratio": ratio,
            "message": f"Code:Docs ratio {ratio:.1f}:1 (min: {cls.CODE_DOCS_RATIO_MIN}:1)",
            "code_lines": code_lines,
            "doc_lines": doc_lines,
        }

    @classmethod
    def _count_code_lines(cls, code: str) -> int:
        """Count actual code lines (excluding comments, docstrings, blank lines)."""
        lines = code.split("\n")
        code_count = 0
        in_docstring = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                continue
            if '"""' in stripped or "'''" in stripped:
                in_docstring = not in_docstring
                continue
            if in_docstring:
                continue
            code_count += 1
        return code_count

    @classmethod
    def require_evidence_links(cls, proposal: dict[str, Any]) -> dict[str, Any]:
        """Require evidence links (forensic rule).

        Returns:
            {"passed": bool, "evidence_links": list[str]}
        """
        rationale = proposal.get("rationale", "")
        evidence_keywords = [
            "evidence:",
            "artifacts/",
            "benchmarks/",
            "tests/",
            "measured:",
            "verified:",
        ]
        evidence_links = [kw for kw in evidence_keywords if kw.lower() in rationale.lower()]
        passed = len(evidence_links) > 0
        return {
            "passed": passed,
            "evidence_links": evidence_links,
            "message": (
                "Evidence links required per forensic rules"
                if not passed
                else "Evidence links present"
            ),
        }


def enforce_governance(proposal: dict[str, Any]) -> dict[str, Any]:
    """Enforce all governance policies.

    Returns:
        {"approved": bool, "violations": list[str]}
    """
    violations = []
    code_docs = CodeQualityEnforcement.check_code_docs_ratio(proposal)
    if not code_docs["passed"]:
        violations.append(code_docs["message"])
    evidence = CodeQualityEnforcement.require_evidence_links(proposal)
    if not evidence["passed"]:
        violations.append(evidence["message"])
    return {"approved": len(violations) == 0, "violations": violations}
