from __future__ import annotations

"""Similarity Filter — Ensure thoughts differ from recent history.

Core aperiodic mechanism: reject candidates too similar to recent thoughts.
Threshold configurable (default 0.90 = 90% similarity).
"""
import logging
import os
import random
from typing import Any

from kagami.core.aperiodic.embeddings import cosine_similarity, embed_text
from kagami.core.aperiodic.history import get_thought_history

logger = logging.getLogger(__name__)


def filter_by_novelty(
    candidates: list[str],
    threshold: float = 0.90,
    history_window: int = 100,
    force_novelty: bool = True,
) -> tuple[str, dict[str, Any]]:
    """Filter candidates by novelty (dissimilarity to history).

    Args:
        candidates: List of candidate thoughts to choose from
        threshold: Maximum allowed similarity (0.90 = reject if >90% similar)
        history_window: Number of recent thoughts to check against
        force_novelty: If all filtered, perturb least similar instead of failing

    Returns:
        Tuple of (selected_thought, metadata)
        metadata contains: {
            "similarity": float,  # Max similarity to history
            "filtered_count": int,  # How many candidates filtered
            "forced": bool,  # Whether novelty was forced
        }
    """
    if not candidates:
        raise ValueError("No candidates provided")

    # Get recent history
    history = get_thought_history(window_size=history_window)
    recent = history.get_recent(n=history_window)

    if not recent:
        # No history yet - any candidate is novel
        selected = candidates[0]
        return selected, {
            "similarity": 0.0,
            "filtered_count": 0,
            "forced": False,
            "reason": "no_history",
        }

    # Extract historical content
    historical_texts = [r.content for r in recent]

    # Compute similarity for each candidate
    similarities: list[tuple[int, float, str]] = []
    for i, cand in enumerate(candidates):
        cand_emb = embed_text(cand)

        # Get cached historical embeddings if available
        hist_embs = history.get_embeddings(n=history_window)

        if hist_embs and len(hist_embs) == len(historical_texts):
            # Use cached embeddings
            max_sim = max(cosine_similarity(cand_emb, h_emb) for h_emb in hist_embs)  # type: ignore[arg-type]
        else:
            # Compute from text
            from kagami.core.aperiodic.embeddings import max_similarity as _max_sim

            max_sim = _max_sim(cand, historical_texts)

        similarities.append((i, max_sim, cand))

    # Filter: keep only novel candidates (similarity < threshold)
    novel = [(i, sim, c) for (i, sim, c) in similarities if sim < threshold]

    # Emit metrics
    try:
        from kagami_observability.metrics import (
            APERIODIC_FILTERED_TOTAL,
            APERIODIC_SIMILARITY_MAX,
        )

        filtered_count = len(candidates) - len(novel)
        APERIODIC_FILTERED_TOTAL.inc(filtered_count)

        if similarities:
            max_overall = max(s[1] for s in similarities)
            APERIODIC_SIMILARITY_MAX.observe(max_overall)

    except Exception:
        pass

    if novel:
        # Select least similar among novel candidates
        selected_idx, selected_sim, selected = min(novel, key=lambda x: x[1])

        logger.info(
            f"Aperiodic: Selected candidate {selected_idx} "
            f"(similarity={selected_sim:.3f}, {len(novel)}/{len(candidates)} novel)"
        )

        return selected, {
            "similarity": selected_sim,
            "filtered_count": len(candidates) - len(novel),
            "forced": False,
            "candidate_index": selected_idx,
        }

    # All candidates too similar!
    if not force_novelty:
        # Fail hard
        raise ValueError(
            f"All {len(candidates)} candidates exceed similarity threshold {threshold}"
        )

    # Force novelty: perturb the least similar candidate
    least_sim_idx, least_sim, least_sim_cand = min(similarities, key=lambda x: x[1])

    logger.warning(
        f"Aperiodic: All candidates too similar (min={least_sim:.3f}); forcing novelty perturbation"
    )

    # Add novelty perturbation
    perturbed = _add_novelty_perturbation(least_sim_cand)

    # Emit metric

    return perturbed, {
        "similarity": least_sim,
        "filtered_count": len(candidates),
        "forced": True,
        "candidate_index": least_sim_idx,
        "perturbation": "applied",
    }


def _add_novelty_perturbation(text: str) -> str:
    """Add small perturbation to force novelty.

    Strategies:
    - Add clarifying phrase
    - Reorder sentences
    - Substitute synonyms
    - Change perspective

    Args:
        text: Original text

    Returns:
        Perturbed text (semantically similar but not identical)
    """
    # Get perturbation strategy from env (for testing)
    strategy = os.getenv("APERIODIC_PERTURBATION", "clarify")

    if strategy == "clarify":
        # Add clarifying phrase
        clarifications = [
            "In other words: ",
            "To put it differently: ",
            "Another way to see this: ",
            "From a different angle: ",
            "More precisely: ",
        ]
        prefix = random.choice(clarifications)
        return prefix + text

    elif strategy == "reorder":
        # Reorder sentences (if multiple)
        sentences = text.split(". ")
        if len(sentences) > 1:
            random.shuffle(sentences)
            return ". ".join(sentences)
        return text

    elif strategy == "perspective":
        # Change perspective
        perspectives = [
            "Considering this from first principles: ",
            "Looking at this pragmatically: ",
            "Through the lens of active inference: ",
            "From the fractal kernel perspective: ",
        ]
        prefix = random.choice(perspectives)
        return prefix + text

    else:
        # Default: clarify
        return "To elaborate: " + text


def is_novel(text: str, threshold: float = 0.90, history_window: int = 100) -> bool:
    """Check if text is novel (below similarity threshold).

    Args:
        text: Text to check
        threshold: Maximum allowed similarity
        history_window: Number of recent thoughts to check

    Returns:
        True if novel, False if too similar to history
    """
    history = get_thought_history(window_size=history_window)
    recent = history.get_recent(n=history_window)

    if not recent:
        return True  # No history = novel

    historical_texts = [r.content for r in recent]

    from kagami.core.aperiodic.embeddings import max_similarity as _max_sim

    max_sim = _max_sim(text, historical_texts)

    return max_sim < threshold
