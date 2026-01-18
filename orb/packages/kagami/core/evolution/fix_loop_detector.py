"""CI auto-fix loop detection.

P1 Mitigation: Auto-fix creates new error → Infinite fix loop → Repo pollution
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


class FixAttempt:
    """Record of a fix attempt."""

    def __init__(
        self,
        test_name: str,
        error_signature: str,
        pr_number: int | None,
        timestamp: datetime,
        success: bool,
    ):
        self.test_name = test_name
        self.error_signature = error_signature
        self.pr_number = pr_number
        self.timestamp = timestamp
        self.success = success


class FixLoopDetector:
    """Detects infinite auto-fix loops.

    P1 Mitigation: Prevents CI from creating infinite fix PRs

    Strategy:
    - Track fix attempts per test
    - Limit attempts within time window
    - Escalate to human after threshold
    - Detect repeating error signatures

    Usage:
        detector = FixLoopDetector(max_attempts=3, window_hours=24)

        if detector.should_attempt_fix("test_auth"):
            # Generate and submit fix
            await detector.record_attempt("test_auth", pr_number=123)
        else:
            # Escalate to human
            await detector.escalate_to_human("test_auth")
    """

    def __init__(
        self,
        max_attempts: int = 3,
        window_hours: int = 24,
    ):
        """Initialize loop detector.

        Args:
            max_attempts: Max fix attempts per test in window
            window_hours: Time window for counting attempts
        """
        self.max_attempts = max_attempts
        self.window_hours = window_hours

        # In-memory storage (persists for process lifetime only)
        self._attempts: dict[str, list[FixAttempt]] = {}

    def should_attempt_fix(self, test_name: str, error_signature: str) -> bool:
        """Check if fix attempt should be made.

        Args:
            test_name: Name of failing test
            error_signature: Hash of error message

        Returns:
            True if attempt allowed
        """
        recent_attempts = self._get_recent_attempts(test_name)

        if len(recent_attempts) >= self.max_attempts:
            logger.warning(
                f"❌ Fix loop detected for {test_name}: "
                f"{len(recent_attempts)} attempts in {self.window_hours}h "
                f"(max: {self.max_attempts})"
            )
            return False

        # Check for repeating error signature
        recent_signatures = [attempt.error_signature for attempt in recent_attempts]

        if recent_signatures.count(error_signature) >= 2:
            logger.warning(
                f"❌ Repeating error detected for {test_name}: "
                f"Same error signature seen {recent_signatures.count(error_signature)} times"
            )
            return False

        logger.info(
            f"✅ Fix attempt allowed for {test_name}: "
            f"{len(recent_attempts)}/{self.max_attempts} in window"
        )
        return True

    async def record_attempt(
        self,
        test_name: str,
        error_signature: str,
        pr_number: int | None = None,
        success: bool = False,
    ) -> None:
        """Record fix attempt.

        Args:
            test_name: Name of failing test
            error_signature: Hash of error message
            pr_number: PR number if created
            success: Whether fix succeeded
        """
        attempt = FixAttempt(
            test_name=test_name,
            error_signature=error_signature,
            pr_number=pr_number,
            timestamp=datetime.utcnow(),
            success=success,
        )

        if test_name not in self._attempts:
            self._attempts[test_name] = []

        self._attempts[test_name].append(attempt)

        logger.info(f"📝 Recorded fix attempt for {test_name}: PR #{pr_number}, success={success}")

    async def escalate_to_human(self, test_name: str) -> None:
        """Escalate to human after too many failed attempts.

        Args:
            test_name: Name of failing test
        """
        recent_attempts = self._get_recent_attempts(test_name)

        # Log escalation for operator visibility
        # Alerting/issue creation handled by log aggregation (e.g., Datadog, PagerDuty)
        logger.error(
            f"🚨 ESCALATING TO HUMAN: {test_name} failed auto-fix "
            f"after {len(recent_attempts)} attempts in {self.window_hours}h"
        )
        logger.critical(
            f"Manual intervention required for {test_name}. "
            "Create Linear issue with label: requires-human"
        )

    def _get_recent_attempts(self, test_name: str) -> list[FixAttempt]:
        """Get fix attempts within time window.

        Args:
            test_name: Name of test

        Returns:
            List of recent attempts
        """
        if test_name not in self._attempts:
            return []

        cutoff = datetime.utcnow() - timedelta(hours=self.window_hours)

        return [attempt for attempt in self._attempts[test_name] if attempt.timestamp > cutoff]

    def get_stats(self) -> dict[str, Any]:
        """Get loop detector statistics."""
        return {
            "tests_tracked": len(self._attempts),
            "tests_with_recent_attempts": sum(
                1 for test in self._attempts if len(self._get_recent_attempts(test)) > 0
            ),
            "tests_at_limit": sum(
                1
                for test in self._attempts
                if len(self._get_recent_attempts(test)) >= self.max_attempts
            ),
            "total_attempts": sum(len(attempts) for attempts in self._attempts.values()),
            "limits": {
                "max_attempts": self.max_attempts,
                "window_hours": self.window_hours,
            },
        }


# Global detector instance
_global_detector: FixLoopDetector | None = None


def get_fix_loop_detector() -> FixLoopDetector:
    """Get global fix loop detector."""
    global _global_detector
    if _global_detector is None:
        _global_detector = FixLoopDetector(
            max_attempts=3,  # Stop after 3 attempts
            window_hours=24,  # Within 24 hour window
        )
    return _global_detector
