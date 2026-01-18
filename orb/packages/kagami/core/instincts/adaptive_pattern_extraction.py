"""Adaptive Pattern Extraction for Prediction Instinct.

Makes LLM pattern extraction frequency adaptive instead of fixed 1-hour cooldown.
Based on:
- Prediction error magnitude (high error = extract sooner)
- Sample count growth rate
- Pattern staleness detection
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ExtractionSchedule:
    """Schedule for next pattern extraction."""

    should_extract: bool
    next_extract_time: float
    reason: str
    confidence: float


class AdaptivePatternExtractor:
    """Adaptive scheduling for LLM pattern extraction."""

    def __init__(
        self,
        min_interval: float = 300.0,  # 5 minutes minimum
        max_interval: float = 7200.0,  # 2 hours maximum
        base_interval: float = 3600.0,  # 1 hour baseline
    ) -> None:
        """Initialize adaptive extractor.

        Args:
            min_interval: Minimum seconds between extractions
            max_interval: Maximum seconds between extractions
            base_interval: Baseline interval
        """
        self.min_interval = min_interval
        self.max_interval = max_interval
        self.base_interval = base_interval

        # Track last extraction per signature
        self._last_extraction: dict[str, float] = {}
        self._last_error_rate: dict[str, float] = {}
        self._last_sample_count: dict[str, int] = {}

    def should_extract_now(
        self,
        signature: str,
        current_experiences: list[Any],
        recent_error_rate: float,
    ) -> ExtractionSchedule:
        """Determine if should extract patterns now.

        Args:
            signature: Task signature
            current_experiences: List of current experiences
            recent_error_rate: Recent prediction error rate (0-1)

        Returns:
            ExtractionSchedule with decision and reason
        """
        current_time = time.time()
        last_extract = self._last_extraction.get(signature, 0)
        time_since_extract = current_time - last_extract

        sample_count = len(current_experiences)

        # Reason tracking
        reasons = []

        # TRIGGER 1: Minimum sample count not met
        if sample_count < 10:
            return ExtractionSchedule(
                should_extract=False,
                next_extract_time=last_extract + self.base_interval,
                reason="insufficient_samples",
                confidence=0.0,
            )

        # TRIGGER 2: High error rate (extract sooner)
        if recent_error_rate > 0.3:
            # High error = patterns may have changed
            adaptive_interval = self.min_interval * (1.0 / (recent_error_rate + 0.1))
            adaptive_interval = max(self.min_interval, min(adaptive_interval, self.base_interval))

            if time_since_extract >= adaptive_interval:
                reasons.append(f"high_error_rate={recent_error_rate:.2f}")
                return ExtractionSchedule(
                    should_extract=True,
                    next_extract_time=current_time,
                    reason="; ".join(reasons),
                    confidence=0.8,
                )

        # TRIGGER 3: Rapid sample growth (extract sooner)
        last_count = self._last_sample_count.get(signature, 0)
        growth_rate = (sample_count - last_count) / max(1, time_since_extract)

        if growth_rate > 1.0:  # More than 1 new sample per second
            adaptive_interval = self.base_interval / (1.0 + growth_rate)
            adaptive_interval = max(self.min_interval, min(adaptive_interval, self.base_interval))

            if time_since_extract >= adaptive_interval:
                reasons.append(f"rapid_growth={growth_rate:.2f}/s")
                return ExtractionSchedule(
                    should_extract=True,
                    next_extract_time=current_time,
                    reason="; ".join(reasons),
                    confidence=0.7,
                )

        # TRIGGER 4: Error rate decreased significantly (patterns stabilized, extract later)
        last_error = self._last_error_rate.get(signature, recent_error_rate)
        error_delta = abs(recent_error_rate - last_error)

        if error_delta < 0.05 and recent_error_rate < 0.1:
            # Stable low error = extend interval
            adaptive_interval = min(self.max_interval, self.base_interval * 1.5)
        else:
            # Normal case
            adaptive_interval = self.base_interval

        # Check if time for scheduled extraction
        if time_since_extract >= adaptive_interval:
            reasons.append("scheduled")
            return ExtractionSchedule(
                should_extract=True,
                next_extract_time=current_time,
                reason="; ".join(reasons) or "scheduled",
                confidence=0.6,
            )

        # Not time yet
        return ExtractionSchedule(
            should_extract=False,
            next_extract_time=last_extract + adaptive_interval,
            reason="cooldown",
            confidence=0.0,
        )

    def mark_extracted(self, signature: str, sample_count: int, error_rate: float) -> None:
        """Mark that extraction occurred.

        Args:
            signature: Task signature
            sample_count: Number of samples at extraction
            error_rate: Error rate at extraction
        """
        current_time = time.time()
        self._last_extraction[signature] = current_time
        self._last_sample_count[signature] = sample_count
        self._last_error_rate[signature] = error_rate


def get_adaptive_pattern_extractor() -> AdaptivePatternExtractor:
    """Get singleton adaptive pattern extractor.

    Returns:
        AdaptivePatternExtractor instance
    """
    global _extractor
    if _extractor is None:
        _extractor = AdaptivePatternExtractor()
    return _extractor


_extractor: AdaptivePatternExtractor | None = None

__all__ = ["AdaptivePatternExtractor", "ExtractionSchedule", "get_adaptive_pattern_extractor"]
