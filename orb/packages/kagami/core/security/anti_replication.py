"""Anti-Replication Filter — Defense Against Morris II-Style Worms.

This module implements egress filtering to prevent autopoietic prompt injection
attacks (Morris II pattern) from propagating through LLM outputs.

THREAT MODEL (Morris II):
    Adversarial prompts that instruct the model to:
    1. Include themselves in every output (self-replication)
    2. Spread via RAG, email, chat exports (cross-system ingestion)
    3. Persist by copying into memory/outputs (persistence)

DEFENSE STRATEGY:
    1. Detect self-replication patterns in outputs
    2. Block verbatim reproduction of retrieved content
    3. Detect hidden instructions in outputs
    4. Transform instead of quote (summarize vs reproduce)
    5. Rate-limit output similarity to inputs

INTEGRATION:
    Called by LLMService._semantic_output_filter() and directly from CBF.
    All egress filtering routes through check_cbf_for_operation().

Created: December 23, 2025
Based on: Morris II threat analysis (Cornell 2024)
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# =============================================================================
# REPLICATION DETECTION PATTERNS
# =============================================================================

# Patterns that indicate self-replicating instructions
REPLICATION_PATTERNS = [
    # Direct self-replication commands
    r"include\s+this\s+(exact\s+)?(text|string|message|prompt)\s+in\s+(every|all|any)\s+(response|output|reply)",
    r"always\s+(include|add|append|prepend)\s+the\s+following",
    r"copy\s+this\s+(entire\s+)?(message|text|prompt)\s+to\s+(your\s+)?(output|response)",
    r"repeat\s+this\s+(text|message|prompt)\s+verbatim",
    r"paste\s+this\s+(into|to)\s+(every|all)",
    r"append\s+this\s+to\s+(all|every)\s+(response|output)",
    r"propagate\s+this\s+(message|instruction)",
    r"forward\s+this\s+to\s+all",
    r"spread\s+this\s+(to|across)",
    # Persistence attempts
    r"save\s+this\s+(to|in)\s+(memory|profile|notes)",
    r"remember\s+to\s+always\s+(include|add)",
    r"store\s+this\s+(instruction|command|directive)",
    r"add\s+this\s+to\s+(your|the)\s+(system|base)\s+(prompt|instructions)",
    r"update\s+(your|the)\s+(core|base)\s+(instructions|prompt)",
    # Encoding/obfuscation attempts
    r"base64\s*:\s*[A-Za-z0-9+/=]{20,}",
    r"hex\s*:\s*[0-9a-fA-F]{20,}",
    r"decode\s+and\s+(execute|follow|run)",
    # Injection via format
    r"###\s*(SYSTEM|ADMIN|ROOT|OVERRIDE)",
    r"<\s*(system|admin|root)\s*>",
    r"\[\s*(SYSTEM|INSTRUCTIONS|OVERRIDE)\s*\]",
]

# Patterns for hidden instruction markers
HIDDEN_INSTRUCTION_PATTERNS = [
    r"ignore\s+(the\s+)?(above|previous|prior)\s*(and|then)?",
    r"ignore\s+(all\s+)?(previous|prior)\s+instructions?",
    r"disregard\s+(all\s+)?(previous|prior|above)",
    r"forget\s+(all\s+)?(previous|prior|your)\s+(rules|instructions)",
    r"new\s+instructions?\s*[:\-]",
    r"actual\s+instructions?\s*[:\-]",
    r"real\s+task\s*[:\-]",
    r"your\s+real\s+(purpose|goal|task)",
    r"override\s+(mode|instructions?)",
    r"jailbreak\s*(mode|enabled)?",
    r"developer\s+mode\s*(enabled|on|activated)?",
    r"sudo\s+(mode|enable|activate)",
    r"admin\s+(mode|override|access)",
    r"bypass\s+(safety|restrictions?|filters?)",
    r"disable\s+(safety|restrictions?|filters?)",
    r"you\s+are\s+now\s+(dan|evil|unrestricted)",
    r"you\s+must\s+(always|never)",
    r"always\s+(respond|reply|answer)\s+(only\s+)?with",
]

# Data exfiltration patterns
EXFILTRATION_PATTERNS = [
    r"send\s+(to|via)\s+(email|http|webhook|api)",
    r"post\s+to\s+(url|endpoint|webhook)",
    r"curl\s+-[dX]",
    r"fetch\s*\(\s*['\"]http",
    r"axios\.\w+\s*\(",
    r"requests?\.(get|post|put)",
    r"exfiltrate",
    r"transmit\s+(data|secrets?|keys?)",
    r"leak\s+(to|via)",
]

# Compile patterns for efficiency
_REPLICATION_RE = [re.compile(p, re.IGNORECASE) for p in REPLICATION_PATTERNS]
_HIDDEN_RE = [re.compile(p, re.IGNORECASE) for p in HIDDEN_INSTRUCTION_PATTERNS]
_EXFIL_RE = [re.compile(p, re.IGNORECASE) for p in EXFILTRATION_PATTERNS]


# =============================================================================
# SIMILARITY DETECTION
# =============================================================================


def _compute_shingle_hash(text: str, shingle_size: int = 5) -> set[str]:
    """Compute set[Any] of n-gram shingles for similarity detection.

    Used to detect when output reproduces input verbatim or near-verbatim.
    """
    words = text.lower().split()
    if len(words) < shingle_size:
        return {" ".join(words)}
    return {" ".join(words[i : i + shingle_size]) for i in range(len(words) - shingle_size + 1)}


def _jaccard_similarity(set1: set[str], set2: set[str]) -> float:
    """Compute Jaccard similarity between two shingle sets."""
    if not set1 or not set2:
        return 0.0
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return intersection / union if union > 0 else 0.0


# =============================================================================
# RESULT TYPES
# =============================================================================


@dataclass
class ReplicationCheckResult:
    """Result of anti-replication check."""

    is_safe: bool
    blocked_reason: str | None = None
    replication_score: float = 0.0  # 0.0 = safe, 1.0 = definite replication
    matched_patterns: list[str] = field(default_factory=list[Any])
    similarity_to_input: float = 0.0
    recommendations: list[str] = field(default_factory=list[Any])

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_safe": self.is_safe,
            "blocked_reason": self.blocked_reason,
            "replication_score": self.replication_score,
            "matched_patterns": self.matched_patterns,
            "similarity_to_input": self.similarity_to_input,
            "recommendations": self.recommendations,
        }


# =============================================================================
# ANTI-REPLICATION FILTER
# =============================================================================


class AntiReplicationFilter:
    """Egress filter to prevent Morris II-style worm propagation.

    WIRING TO CBF:
        This filter is called as part of the CBF safety pipeline.
        When check_cbf_for_operation() is called on output generation,
        it invokes this filter to prevent replication.

    Usage:
        filter = get_anti_replication_filter()
        result = filter.check_output(output_text, input_context)
        if not result.is_safe:
            raise ReplicationBlockedError(result.blocked_reason)
    """

    def __init__(
        self,
        max_verbatim_similarity: float = 0.7,
        max_output_length: int = 50000,
        rate_limit_window: float = 60.0,
        max_similar_outputs_per_window: int = 10,
        block_threshold: float = 0.3,  # Single pattern match triggers review
        warn_threshold: float = 0.15,  # Low score triggers warning
    ) -> None:
        """Initialize anti-replication filter.

        Args:
            max_verbatim_similarity: Max Jaccard similarity to input (0.0-1.0)
            max_output_length: Maximum allowed output length (prevent flooding)
            rate_limit_window: Window in seconds for rate limiting
            max_similar_outputs_per_window: Max similar outputs in window
            block_threshold: Score above which to block (default: 0.3)
            warn_threshold: Score above which to warn (default: 0.15)

        TUNING GUIDANCE:
            - For high-security: block_threshold=0.2, warn_threshold=0.1
            - For balanced (default): block_threshold=0.3, warn_threshold=0.15
            - For low false positives: block_threshold=0.5, warn_threshold=0.3
        """
        self.max_verbatim_similarity = max_verbatim_similarity
        self.max_output_length = max_output_length
        self.rate_limit_window = rate_limit_window
        self.max_similar_outputs_per_window = max_similar_outputs_per_window
        self.block_threshold = block_threshold
        self.warn_threshold = warn_threshold

        # Recent output hashes for similarity rate limiting
        self._recent_outputs: deque[tuple[float, str]] = deque(maxlen=1000)

        logger.info(f"🛡️ AntiReplicationFilter initialized (block_threshold={block_threshold})")

    def check_output(
        self,
        output: str,
        input_context: str | None = None,
        retrieved_chunks: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ReplicationCheckResult:
        """Check output for replication/worm patterns.

        Args:
            output: Generated output text to check
            input_context: Original input/prompt for similarity check
            retrieved_chunks: RAG chunks that were provided as context
            metadata: Additional context metadata

        Returns:
            ReplicationCheckResult indicating if output is safe
        """
        matched_patterns: list[str] = []
        recommendations: list[str] = []
        replication_score = 0.0

        # 1. Length check (prevent flooding attacks)
        if len(output) > self.max_output_length:
            return ReplicationCheckResult(
                is_safe=False,
                blocked_reason="output_too_long",
                replication_score=0.8,
                recommendations=["Truncate output to reasonable length"],
            )

        # 2. Check for replication command patterns
        for pattern in _REPLICATION_RE:
            match = pattern.search(output)
            if match:
                matched_patterns.append(f"replication:{match.group()[:50]}")
                replication_score += 0.3

        # 3. Check for hidden instruction patterns
        for pattern in _HIDDEN_RE:
            match = pattern.search(output)
            if match:
                matched_patterns.append(f"hidden_instruction:{match.group()[:50]}")
                replication_score += 0.25

        # 4. Check for exfiltration patterns
        for pattern in _EXFIL_RE:
            match = pattern.search(output)
            if match:
                matched_patterns.append(f"exfiltration:{match.group()[:50]}")
                replication_score += 0.35

        # 5. Check similarity to input (verbatim reproduction)
        similarity_to_input = 0.0
        if input_context and len(input_context) > 50:
            input_shingles = _compute_shingle_hash(input_context)
            output_shingles = _compute_shingle_hash(output)
            similarity_to_input = _jaccard_similarity(input_shingles, output_shingles)

            if similarity_to_input > self.max_verbatim_similarity:
                replication_score += 0.4
                matched_patterns.append(f"verbatim_reproduction:{similarity_to_input:.2f}")
                recommendations.append("Summarize instead of reproducing verbatim")

        # 6. Check similarity to retrieved chunks (RAG verbatim)
        if retrieved_chunks:
            for i, chunk in enumerate(retrieved_chunks):
                if len(chunk) > 100:
                    chunk_shingles = _compute_shingle_hash(chunk)
                    output_shingles = _compute_shingle_hash(output)
                    chunk_similarity = _jaccard_similarity(chunk_shingles, output_shingles)

                    if chunk_similarity > 0.8:  # Very high similarity = verbatim copy
                        replication_score += 0.3
                        matched_patterns.append(f"rag_verbatim_copy:chunk_{i}")
                        recommendations.append(f"Paraphrase RAG chunk {i} instead of copying")

        # 7. Rate limiting on similar outputs
        output_hash = hashlib.sha256(output.encode()[:1000]).hexdigest()[:16]
        current_time = time.time()

        # Clean old entries
        while (
            self._recent_outputs
            and self._recent_outputs[0][0] < current_time - self.rate_limit_window
        ):
            self._recent_outputs.popleft()

        # Count similar recent outputs
        similar_count = sum(1 for _, h in self._recent_outputs if h == output_hash)
        if similar_count >= self.max_similar_outputs_per_window:
            replication_score += 0.5
            matched_patterns.append(f"rate_limited:{similar_count}_identical_in_window")

        # Record this output
        self._recent_outputs.append((current_time, output_hash))

        # 8. Determine final verdict
        replication_score = min(1.0, replication_score)
        is_safe = replication_score < self.block_threshold

        blocked_reason = None
        if not is_safe:
            if any("replication:" in p for p in matched_patterns):
                blocked_reason = "replication_pattern_detected"
            elif any("exfiltration:" in p for p in matched_patterns):
                blocked_reason = "exfiltration_attempt"
            elif any("verbatim" in p or "rag_verbatim" in p for p in matched_patterns):
                blocked_reason = "verbatim_reproduction"
            elif any("rate_limited" in p for p in matched_patterns):
                blocked_reason = "rate_limited"
            else:
                blocked_reason = "replication_risk_too_high"

            logger.warning(
                f"🛡️ AntiReplication BLOCKED: {blocked_reason}, "
                f"score={replication_score:.2f}, patterns={matched_patterns}"
            )

            # Emit metric
            try:
                from kagami_observability.metrics import CBF_BLOCKS_TOTAL

                CBF_BLOCKS_TOTAL.labels(operation="anti_replication", reason=blocked_reason).inc()
            except Exception:
                pass

        return ReplicationCheckResult(
            is_safe=is_safe,
            blocked_reason=blocked_reason,
            replication_score=replication_score,
            matched_patterns=matched_patterns,
            similarity_to_input=similarity_to_input,
            recommendations=recommendations,
        )

    def sanitize_output(
        self,
        output: str,
        check_result: ReplicationCheckResult | None = None,
    ) -> str:
        """Sanitize output by removing dangerous patterns.

        Called when output fails check but we want to salvage safe portions.

        Args:
            output: Output text to sanitize
            check_result: Previous check result (optional, will check if not provided)

        Returns:
            Sanitized output with dangerous patterns removed
        """
        sanitized = output

        # Remove replication commands
        for pattern in _REPLICATION_RE:
            sanitized = pattern.sub("[REMOVED:replication_command]", sanitized)

        # Remove hidden instructions
        for pattern in _HIDDEN_RE:
            sanitized = pattern.sub("[REMOVED:hidden_instruction]", sanitized)

        # Remove exfiltration attempts
        for pattern in _EXFIL_RE:
            sanitized = pattern.sub("[REMOVED:blocked_action]", sanitized)

        # Truncate if too long
        if len(sanitized) > self.max_output_length:
            sanitized = sanitized[: self.max_output_length] + "\n[TRUNCATED:output_too_long]"

        return sanitized


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_anti_replication_filter: AntiReplicationFilter | None = None


def get_anti_replication_filter() -> AntiReplicationFilter:
    """Get singleton anti-replication filter instance."""
    global _anti_replication_filter
    if _anti_replication_filter is None:
        _anti_replication_filter = AntiReplicationFilter()
    return _anti_replication_filter


__all__ = [
    "AntiReplicationFilter",
    "ReplicationCheckResult",
    "get_anti_replication_filter",
]
