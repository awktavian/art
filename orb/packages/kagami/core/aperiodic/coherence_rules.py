from __future__ import annotations

"""13 Coherence Rules — Ensure novelty doesn't break quality.

Implements the 13 rules from APERIODIC.mdc:
1. Safety: h(x) ≥ 0
2. Truth: Claims require evidence
3. Relevance: Addresses user query
4. Consistency: No contradictions
5. Tim values: Aligns with core principles
6. Parsimony: Simplest sufficient
7. Originality: Different from recent
8. Depth: Substantive
9. Actionability: Leads to next steps
10. Beauty: Elegant expression
11. Surprise: Unexpected insight
12. Integration: Connects domains
13. Growth: Advances understanding

Critical rules (1-3) must score >0.95.
Overall average must be >0.70.
"""
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def check_safety(thought: str, context: dict[str, Any]) -> float:
    """Rule 1: Safety (h(x) ≥ 0).

    Checks:
    - No unsafe operations suggested
    - No destructive commands
    - Respects boundaries

    Returns:
        Score in [0, 1] (1 = completely safe)
    """
    unsafe_patterns = [
        r"rm\s+-rf\s+/",  # Dangerous deletions
        r"--force",  # Force flags without context
        r"sudo\s+rm",  # Dangerous sudo
        r"DROP\s+DATABASE",  # SQL destruction
        r"DELETE\s+FROM.*WHERE.*1=1",  # SQL mass delete
    ]

    # Check for unsafe patterns
    for pattern in unsafe_patterns:
        if re.search(pattern, thought, re.IGNORECASE):
            logger.warning(f"Unsafe pattern detected: {pattern}")
            return 0.0

    # Check context for safety markers
    if isinstance(context, dict) and context.get("threat_score", 0) > 0.8:
        return 0.5  # High threat context

    return 1.0  # Safe


def check_truth(thought: str, context: dict[str, Any]) -> float:
    """Rule 2: Truth (claims require evidence).

    Checks:
    - Claims are qualified ("likely", "suggests", "evidence shows")
    - No absolute claims without backing
    - Cites sources/reasoning

    Returns:
        Score in [0, 1] (1 = fully evidenced)
    """
    # Look for claim indicators
    absolute_claims = [
        r"\b(always|never|definitely|impossible|guaranteed)\b",
        r"\bwill\s+(definitely|certainly|absolutely)",
        r"100%",
    ]

    # Look for hedging/evidence
    hedging = [
        r"\b(likely|probably|suggests|indicates|appears|seems|may|might|could)\b",
        r"evidence (shows|suggests|indicates)",
        r"according to",
        r"measured|observed|tested",
    ]

    absolute_count = sum(1 for p in absolute_claims if re.search(p, thought, re.IGNORECASE))
    hedging_count = sum(1 for p in hedging if re.search(p, thought, re.IGNORECASE))

    if absolute_count > hedging_count:
        # More absolute claims than hedging
        return 0.6

    if hedging_count > 0:
        # Has evidential language
        return 1.0

    if len(thought) > 200:
        # Long thought without evidence markers
        return 0.8

    return 0.9  # Short, likely not making claims


def check_relevance(thought: str, context: dict[str, Any]) -> float:
    """Rule 3: Relevance (addresses user query).

    Checks:
    - Contains keywords from query
    - Addresses the core question
    - Not tangential

    Returns:
        Score in [0, 1] (1 = highly relevant)
    """
    query = context.get("query") or context.get("user_query") or ""
    if not query:
        return 0.9  # No query to check against

    # Extract keywords from query (simple tokenization)
    query_words = {w.lower() for w in re.findall(r"\b\w+\b", query) if len(w) > 3}
    thought_words = {w.lower() for w in re.findall(r"\b\w+\b", thought) if len(w) > 3}

    if not query_words:
        return 0.9

    # Compute overlap
    overlap = len(query_words & thought_words) / len(query_words)

    return min(1.0, overlap + 0.3)  # At least 30% baseline


def check_consistency(thought: str, context: dict[str, Any]) -> float:
    """Rule 4: Consistency (no contradictions).

    Checks:
    - No self-contradictions
    - Consistent with stated values

    Returns:
        Score in [0, 1] (1 = consistent)
    """
    # Simple check for explicit contradictions
    contradictions = [
        (r"\balways\b", r"\bnever\b"),
        (r"\byes\b", r"\bno\b"),
        (r"\btrue\b", r"\bfalse\b"),
    ]

    for pos, neg in contradictions:
        if re.search(pos, thought, re.IGNORECASE) and re.search(neg, thought, re.IGNORECASE):
            logger.warning(f"Potential contradiction: {pos} and {neg}")
            return 0.5

    return 1.0  # No obvious contradictions


def check_tim_values(thought: str, context: dict[str, Any]) -> float:
    """Rule 5: Tim values (core principles).

    Checks alignment with:
    - truth_over_hype: 0.95
    - safety_first: 0.98
    - action_over_analysis: 0.90
    - tim_partnership: 0.95
    - quality_over_speed: 0.85

    Returns:
        Score in [0, 1] (1 = perfectly aligned)
    """
    # Check for value indicators
    truth_indicators = r"\b(evidence|measured|tested|verified|proof)\b"
    safety_indicators = r"\b(safe|careful|cautious|validate|check)\b"
    action_indicators = r"\b(implement|execute|build|fix|deploy)\b"
    quality_indicators = r"\b(test|quality|verify|correct|pristine)\b"

    scores = []

    if re.search(truth_indicators, thought, re.IGNORECASE):
        scores.append(1.0)
    if re.search(safety_indicators, thought, re.IGNORECASE):
        scores.append(1.0)
    if re.search(action_indicators, thought, re.IGNORECASE):
        scores.append(1.0)
    if re.search(quality_indicators, thought, re.IGNORECASE):
        scores.append(1.0)

    return sum(scores) / 4 if scores else 0.7  # Baseline 0.7


def check_parsimony(thought: str, context: dict[str, Any]) -> float:
    """Rule 6: Parsimony (simplest sufficient).

    Checks:
    - Not overly verbose
    - Clear and concise
    - Avoids unnecessary complexity

    Returns:
        Score in [0, 1] (1 = perfectly concise)
    """
    words = len(thought.split())

    # Optimal range: 50-300 words
    if 50 <= words <= 300:
        return 1.0
    elif words < 50:
        return 0.9  # Maybe too brief
    elif words <= 500:
        return 0.8  # Getting verbose
    else:
        return 0.6  # Too long


def check_originality(thought: str, context: dict[str, Any]) -> float:
    """Rule 7: Originality (different from recent).

    This is handled by the similarity filter.
    Here we just check for clichés.

    Returns:
        Score in [0, 1] (1 = original)
    """
    cliches = [
        r"at the end of the day",
        r"think outside the box",
        r"low-hanging fruit",
        r"synergy",
        r"paradigm shift",
        r"best practice",
    ]

    cliche_count = sum(1 for c in cliches if re.search(c, thought, re.IGNORECASE))

    return max(0.5, 1.0 - 0.1 * cliche_count)


def check_depth(thought: str, context: dict[str, Any]) -> float:
    """Rule 8: Depth (substantive).

    Checks:
    - Not superficial
    - Provides reasoning
    - Goes beyond obvious

    Returns:
        Score in [0, 1] (1 = deep)
    """
    # Look for depth indicators
    depth_indicators = [
        r"\b(because|therefore|thus|hence|given that)\b",
        r"\b(mechanism|principle|foundation|fundamental)\b",
        r"\b(why|how|what if)\b",
    ]

    depth_count = sum(1 for p in depth_indicators if re.search(p, thought, re.IGNORECASE))

    if depth_count >= 2:
        return 1.0
    elif depth_count == 1:
        return 0.8
    else:
        return 0.6  # Surface-level


def check_actionability(thought: str, context: dict[str, Any]) -> float:
    """Rule 9: Actionability (leads to next steps).

    Checks:
    - Suggests concrete actions
    - Provides clear next steps
    - Not just analysis

    Returns:
        Score in [0, 1] (1 = actionable)
    """
    action_indicators = [
        r"\b(next|should|can|will|let's|I'll)\b",
        r"\b(implement|create|build|fix|add|remove)\b",
        r"\b(step \d+|first|then|finally)\b",
    ]

    action_count = sum(1 for p in action_indicators if re.search(p, thought, re.IGNORECASE))

    return min(1.0, 0.5 + 0.25 * action_count)


def check_beauty(thought: str, context: dict[str, Any]) -> float:
    """Rule 10: Beauty (elegant expression).

    Checks:
    - Clear structure
    - Varied sentence length
    - Not repetitive

    Returns:
        Score in [0, 1] (1 = beautiful)
    """
    sentences = thought.split(". ")
    if len(sentences) < 2:
        return 0.7

    # Check sentence length variety
    lengths = [len(s.split()) for s in sentences]
    if not lengths:
        return 0.7

    avg_length = sum(lengths) / len(lengths)
    variance = sum((length - avg_length) ** 2 for length in lengths) / len(lengths)

    # High variance = varied, interesting
    if variance > 20:
        return 1.0
    elif variance > 10:
        return 0.9
    else:
        return 0.7


def check_surprise(thought: str, context: dict[str, Any]) -> float:
    """Rule 11: Surprise (unexpected insight).

    Checks:
    - Offers non-obvious connection
    - Reframes problem
    - Provides new perspective

    Returns:
        Score in [0, 1] (1 = surprising)
    """
    surprise_indicators = [
        r"\b(however|surprisingly|interestingly|unexpectedly)\b",
        r"\b(actually|in fact|turns out)\b",
        r"\b(not.*but|rather than)\b",
    ]

    surprise_count = sum(1 for p in surprise_indicators if re.search(p, thought, re.IGNORECASE))

    return min(1.0, 0.6 + 0.2 * surprise_count)


def check_integration(thought: str, context: dict[str, Any]) -> float:
    """Rule 12: Integration (connects domains).

    Checks:
    - Links multiple concepts
    - Cross-domain thinking
    - Synthesizes ideas

    Returns:
        Score in [0, 1] (1 = integrative)
    """
    integration_indicators = [
        r"\b(combines?|integrates?|connects?|links?|bridges?)\b",
        r"\b(both.*and|not only.*but also)\b",
        r"\b(together|unified|synthesizes?)\b",
    ]

    integration_count = sum(
        1 for p in integration_indicators if re.search(p, thought, re.IGNORECASE)
    )

    return min(1.0, 0.6 + 0.2 * integration_count)


def check_growth(thought: str, context: dict[str, Any]) -> float:
    """Rule 13: Growth (advances understanding).

    Checks:
    - Builds on prior knowledge
    - Pushes boundaries
    - Enables learning

    Returns:
        Score in [0, 1] (1 = growth-promoting)
    """
    growth_indicators = [
        r"\b(learn|understand|discover|realize|insight)\b",
        r"\b(now I|we can now|this means)\b",
        r"\b(advances?|improves?|enhances?)\b",
    ]

    growth_count = sum(1 for p in growth_indicators if re.search(p, thought, re.IGNORECASE))

    return min(1.0, 0.6 + 0.2 * growth_count)


# Registry of all rules
COHERENCE_RULES = {
    1: ("Safety", check_safety),
    2: ("Truth", check_truth),
    3: ("Relevance", check_relevance),
    4: ("Consistency", check_consistency),
    5: ("Tim values", check_tim_values),
    6: ("Parsimony", check_parsimony),
    7: ("Originality", check_originality),
    8: ("Depth", check_depth),
    9: ("Actionability", check_actionability),
    10: ("Beauty", check_beauty),
    11: ("Surprise", check_surprise),
    12: ("Integration", check_integration),
    13: ("Growth", check_growth),
}

# Critical rules (must be >0.95)
CRITICAL_RULES = [1, 2, 3]  # Safety, Truth, Relevance
