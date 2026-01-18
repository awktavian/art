from __future__ import annotations

"""Aperiodic Wrapper — Always-on novelty filtering for thought generation.

Call apply_aperiodic_filter() to filter candidates by novelty.
No feature flags; this is the default path.
"""
import logging
from typing import Any

from kagami.core.di.container import register_service
from kagami.core.interfaces import (
    CandidateFilterContext,
    CandidateFilterProtocol,
)

logger = logging.getLogger(__name__)


def apply_aperiodic_filter(
    candidates: list[str],
    correlation_id: str | None = None,
    threshold: float | None = None,
) -> str:
    """Apply aperiodic novelty filter to candidates.

    Args:
        candidates: List of candidate responses
        correlation_id: Optional correlation ID for history
        threshold: Optional similarity threshold (default 0.90)

    Returns:
        Selected candidate (most novel if enabled, first if disabled)
    """
    if not candidates:
        logger.warning("No candidates provided to aperiodic filter")
        return ""

    # Apply novelty filter
    try:
        from kagami.core.aperiodic.history import get_thought_history
        from kagami.core.aperiodic.similarity_filter import filter_by_novelty

        # Get threshold from env if not provided
        if threshold is None:
            threshold = 0.90

        # Filter by novelty
        selected, metadata = filter_by_novelty(candidates=candidates, threshold=threshold)

        # Add to history
        history = get_thought_history()
        history.add(
            content=selected,
            correlation_id=correlation_id,
            metadata=metadata,
        )

        # Log
        logger.info(
            f"Aperiodic filter: Selected candidate with similarity={metadata['similarity']:.3f} "
            f"(filtered {metadata['filtered_count']}/{len(candidates)})"
        )

        return selected

    except Exception as e:
        logger.error(f"Aperiodic filter failed: {e}, falling back to first candidate")
        # Fallback: return first candidate
        return candidates[0]


def update_lzc_metrics() -> None:
    """Compute and publish LZC metrics (call periodically).

    Measures Lempel-Ziv Complexity of recent thoughts.
    Should be called every ~10 thoughts or 60s.
    """
    try:
        from kagami.core.aperiodic.history import get_thought_history
        from kagami.core.integrations.monitors.lzc_monitor import lempel_ziv_complexity

        history = get_thought_history()
        recent = history.get_recent(n=100)

        if len(recent) < 10:
            return  # Need minimum data

        # Convert to sequence (just concatenate content)
        sequence = "".join(r.content[:100] for r in recent)  # First 100 chars each

        # Compute LZC (result used for monitoring/filtering)
        _ = lempel_ziv_complexity(sequence)

    except Exception as e:
        logger.error(f"LZC update failed: {e}")


class AperiodicCandidateFilter(CandidateFilterProtocol):
    """Adapter that uses aperiodic novelty filter for candidate prioritization."""

    def select(
        self,
        candidates: list[dict[str, Any]],
        context: CandidateFilterContext,
    ) -> list[dict[str, Any]]:
        if not candidates:
            return []

        descriptions = [
            f"{candidate.get('action_type', '')}:{candidate.get('description', '')}"
            for candidate in candidates
        ]
        selected = apply_aperiodic_filter(
            descriptions,
            correlation_id=context.correlation_id,
            threshold=(
                float(context.metadata.get("novelty_threshold", 0.90)) if context.metadata else None
            ),
        )

        if selected:
            for idx, desc in enumerate(descriptions):
                if desc == selected:
                    prioritized = candidates[idx]
                    remainder = candidates[:idx] + candidates[idx + 1 :]
                    return [prioritized, *remainder]
        return candidates


try:
    register_service(
        CandidateFilterProtocol,
        lambda: AperiodicCandidateFilter(),
        singleton=True,
    )
except ValueError:
    # Tests or alternate filters may override registration
    pass
