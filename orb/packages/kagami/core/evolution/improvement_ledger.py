from __future__ import annotations

"""Improvement Ledger - Complete Audit Trail of Evolution.

Links proposals → code diffs → test results → rollout → outcomes.

Provides full transparency and traceability for all autonomous changes.
"""
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class LedgerEntry:
    """One complete improvement record."""

    entry_id: str
    proposal_id: str
    created_at: float

    # Proposal details
    file_path: str
    rationale: str
    expected_improvement: float
    risk_level: str

    # Code diff
    code_before: str
    code_after: str
    diff_lines: int

    # Evaluation results
    dry_run_result: dict[str, Any]
    fitness_score: float
    passed_guardrails: bool
    violations: list[str] = field(default_factory=list[Any])

    # Application
    applied: bool = False
    applied_at: float | None = None
    checkpoint_id: str | None = None

    # Rollout
    rollout_status: str = "not_started"  # not_started, canary, full, rolled_back
    rollout_percentage: float = 0.0

    # Outcome
    verified: bool = False
    actual_improvement: float | None = None
    rolled_back: bool = False
    rollback_reason: str | None = None

    # Evidence
    test_results_path: str | None = None
    benchmark_results_path: str | None = None
    metrics_path: str | None = None


class ImprovementLedger:
    """Comprehensive ledger of all autonomous improvements."""

    def __init__(self, ledger_dir: Path | None = None) -> None:
        self._ledger_dir = ledger_dir or Path.cwd() / "var" / "evolution_ledger"
        self._ledger_dir.mkdir(parents=True, exist_ok=True)

        self._entries: dict[str, LedgerEntry] = {}
        self._load_existing_entries()

    def _load_existing_entries(self) -> None:
        """Load existing ledger entries from disk."""
        if not self._ledger_dir.exists():
            return

        for entry_file in self._ledger_dir.glob("entry_*.json"):
            try:
                data = json.loads(entry_file.read_text(encoding="utf-8"))
                entry_id = data.get("entry_id")
                if entry_id:
                    # Reconstruct LedgerEntry (simplified)
                    self._entries[entry_id] = data
            except Exception as e:
                logger.warning(f"Could not load ledger entry {entry_file}: {e}")

    def create_entry(self, proposal: dict[str, Any], dry_run_result: dict[str, Any]) -> LedgerEntry:
        """Create new ledger entry for proposal.

        Args:
            proposal: ImprovementProposal dict[str, Any]
            dry_run_result: DryRunResult dict[str, Any]

        Returns:
            LedgerEntry
        """
        import hashlib

        entry_id = hashlib.sha256(
            f"{proposal.get('proposal_id')}:{time.time()}".encode()
        ).hexdigest()[:16]

        entry = LedgerEntry(
            entry_id=entry_id,
            proposal_id=proposal.get("proposal_id", "unknown"),
            created_at=time.time(),
            file_path=proposal.get("file_path", ""),
            rationale=proposal.get("rationale", ""),
            expected_improvement=proposal.get("expected_improvement", 0.0),
            risk_level=proposal.get("risk_level", "unknown"),
            code_before=proposal.get("current_code_snippet", ""),
            code_after=proposal.get("proposed_code_snippet", ""),
            diff_lines=abs(
                proposal.get("proposed_code_snippet", "").count("\n")
                - proposal.get("current_code_snippet", "").count("\n")
            ),
            dry_run_result=dry_run_result,
            fitness_score=dry_run_result.get("fitness_score", 0.0),
            passed_guardrails=dry_run_result.get("passed_guardrails", False),
            violations=dry_run_result.get("violations", []),
        )

        # Save to disk
        self._save_entry(entry)

        # Store in memory
        self._entries[entry_id] = entry

        logger.info(f"📝 Created ledger entry {entry_id} for {entry.proposal_id}")

        return entry

    def record_application(self, entry_id: str, checkpoint_id: str, success: bool = True) -> None:
        """Record that improvement was applied."""
        entry = self._entries.get(entry_id)
        if not entry:
            logger.warning(f"Entry {entry_id} not found")
            return

        entry.applied = success
        entry.applied_at = time.time()
        entry.checkpoint_id = checkpoint_id

        self._save_entry(entry)

        logger.info(f"Applied: {entry_id} (checkpoint: {checkpoint_id})")

    def record_rollout_status(self, entry_id: str, status: str, percentage: float) -> None:
        """Record rollout status update."""
        entry = self._entries.get(entry_id)
        if not entry:
            return

        entry.rollout_status = status
        entry.rollout_percentage = percentage

        self._save_entry(entry)

    def record_verification(
        self, entry_id: str, actual_improvement: float, verified: bool = True
    ) -> None:
        """Record verification outcome."""
        entry = self._entries.get(entry_id)
        if not entry:
            return

        entry.verified = verified
        entry.actual_improvement = actual_improvement

        self._save_entry(entry)

        logger.info(
            f"✅ Verified: {entry_id} (improvement: {actual_improvement:.1%}, expected: {entry.expected_improvement:.1%})"
        )

    def record_rollback(self, entry_id: str, reason: str) -> None:
        """Record that improvement was rolled back."""
        entry = self._entries.get(entry_id)
        if not entry:
            return

        entry.rolled_back = True
        entry.rollback_reason = reason

        self._save_entry(entry)

        logger.warning(f"🔄 Rolled back: {entry_id} ({reason})")

    def _save_entry(self, entry: LedgerEntry) -> None:
        """Save entry to disk."""
        entry_file = self._ledger_dir / f"entry_{entry.entry_id}.json"

        # Convert to dict[str, Any] for serialization
        entry_dict = {
            "entry_id": entry.entry_id,
            "proposal_id": entry.proposal_id,
            "created_at": entry.created_at,
            "file_path": entry.file_path,
            "rationale": entry.rationale,
            "expected_improvement": entry.expected_improvement,
            "risk_level": entry.risk_level,
            "diff_lines": entry.diff_lines,
            "fitness_score": entry.fitness_score,
            "passed_guardrails": entry.passed_guardrails,
            "violations": entry.violations,
            "applied": entry.applied,
            "applied_at": entry.applied_at,
            "checkpoint_id": entry.checkpoint_id,
            "rollout_status": entry.rollout_status,
            "rollout_percentage": entry.rollout_percentage,
            "verified": entry.verified,
            "actual_improvement": entry.actual_improvement,
            "rolled_back": entry.rolled_back,
            "rollback_reason": entry.rollback_reason,
        }

        entry_file.write_text(json.dumps(entry_dict, indent=2), encoding="utf-8")

    def get_stats(self) -> dict[str, Any]:
        """Get ledger statistics."""
        total = len(self._entries)
        applied = sum(1 for e in self._entries.values() if e.applied)
        verified = sum(1 for e in self._entries.values() if e.verified)
        rolled_back = sum(1 for e in self._entries.values() if e.rolled_back)

        success_rate = verified / applied if applied > 0 else 0.0

        return {
            "total_entries": total,
            "applied": applied,
            "verified": verified,
            "rolled_back": rolled_back,
            "success_rate": success_rate,
            "in_progress": applied - verified - rolled_back,
        }

    def get_recent_entries(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent ledger entries."""
        entries = sorted(self._entries.values(), key=lambda e: e.created_at, reverse=True)

        return [
            {
                "entry_id": e.entry_id,
                "proposal_id": e.proposal_id,
                "file_path": e.file_path,
                "rationale": e.rationale[:100],
                "applied": e.applied,
                "verified": e.verified,
                "rolled_back": e.rolled_back,
                "fitness_score": e.fitness_score,
            }
            for e in entries[:limit]
        ]


# Singleton
_ledger: ImprovementLedger | None = None


def get_improvement_ledger() -> ImprovementLedger:
    """Get global improvement ledger."""
    global _ledger
    if _ledger is None:
        _ledger = ImprovementLedger()
    return _ledger
