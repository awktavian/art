from __future__ import annotations

from typing import Any

"""Attribute Encoder - Maps tokens to attribute space for preference learning.

Each token gets an attribute embedding e_t ∈ R^m that describes its
functional role in K os cognition.

Attribute dimensions (m=16):
0. is_tool_call - Token is part of tool invocation
1. is_safety_check - Token relates to safety/CBF
2. is_causal_word - Token is causal connector (because, therefore, if, when)
3. is_plan_phase - Token is in PLAN/SIMULATE phase
4. is_verify_phase - Token is in VERIFY phase
5. is_novel_concept - Token has high novelty (>90% dissimilar)
6. has_tim_value - Token aligns with Tim's values
7. is_code_reference - Token is code/file reference
8. is_refactor - Token relates to refactoring
9. is_test - Token relates to testing
10. is_collaboration - Token relates to agent collaboration
11. is_hive_query - Token relates to hive knowledge
12. is_autonomous - Token relates to autonomous action
13. is_error_correction - Token relates to fixing errors
14. is_convergence - Token relates to convergence/completion
15. is_exploration - Token relates to exploration/novelty
"""
import logging

import numpy as np

logger = logging.getLogger(__name__)

M = 16  # Attribute space dimension

# Keywords for each attribute dimension
ATTRIBUTE_KEYWORDS = {
    0: ["tool", "invoke", "call", "execute", "run", "grep", "search", "read_file"],
    1: ["safety", "cbf", "h(x)", "violation", "boundary", "safe", "unsafe"],
    2: ["because", "therefore", "since", "thus", "if", "when", "then", "causes"],
    3: ["plan", "simulate", "predict", "anticipate", "forecast", "candidate"],
    4: ["verify", "test", "lint", "check", "validate", "confirm"],
    5: ["novel", "new", "unexplored", "creative", "innovative", "unique"],
    6: ["truth", "evidence", "honest", "quality", "tim", "partnership"],
    7: ["code", "file", "function", "class", "import", ".py", ".ts"],
    8: ["refactor", "restructure", "consolidate", "simplify", "optimize"],
    9: ["test", "pytest", "assert", "coverage", "mock"],
    10: ["collaborate", "agent", "hive", "team", "together", "consult"],
    11: ["hive", "knowledge", "query", "discover", "learn"],
    12: ["autonomous", "proactive", "initiate", "independent", "self"],
    13: ["error", "fix", "debug", "correct", "repair", "resolve"],
    14: ["converge", "complete", "done", "finish", "stable"],
    15: ["explore", "search", "discover", "investigate", "novel"],
}


class AttributeEncoder:
    """Encodes tokens into attribute space for preference learning.

    Uses lightweight keyword matching + semantic similarity.
    No heavy neural network - designed for real-time encoding.
    """

    def __init__(self, m: int = M) -> None:
        """Initialize attribute encoder.

        Args:
            m: Dimension of attribute space (default 16)
        """
        self.m = m
        self.keyword_dict = ATTRIBUTE_KEYWORDS

        # Optional: Load semantic embeddings for better matching
        self.semantic_encoder = None
        try:
            from kagami.core.services.embedding_service import get_embedding_service

            self.semantic_encoder = get_embedding_service()
        except Exception:
            logger.debug("Semantic embeddings unavailable, using keyword matching only")

    def encode_token(
        self, token: str, context: dict[str, Any] | None = None
    ) -> np.ndarray[Any, Any]:
        """Encode a single token to attribute vector.

        Args:
            token: Token string to encode
            context: Optional context dict[str, Any] with phase, action, etc.

        Returns:
            e_t ∈ R^m attribute vector
        """
        e = np.zeros(self.m, dtype=np.float32)
        token_lower = token.lower()

        # Keyword matching
        for dim, keywords in self.keyword_dict.items():
            for keyword in keywords:
                if keyword in token_lower:
                    e[dim] += 1.0

        # Context-based attributes (if provided)
        if context:
            phase = context.get("phase", "")
            if phase == "simulate" or phase == "plan":
                e[3] += 0.5
            elif phase == "verify":
                e[4] += 0.5

            # Novelty from context
            if context.get("is_novel", False):
                e[5] += 1.0

        # Normalize to unit norm (optional - Oja does this later)
        norm = np.linalg.norm(e)
        if norm > 0:
            e = e / norm

        return e

    def encode_sequence(
        self, tokens: list[str], context: dict[str, Any] | None = None
    ) -> np.ndarray[Any, Any]:
        """Encode sequence of tokens to attribute matrix.

        Args:
            tokens: List of token strings
            context: Optional shared context

        Returns:
            E ∈ R^(T, m) attribute matrix
        """
        T = len(tokens)
        E = np.zeros((T, self.m), dtype=np.float32)

        for i, token in enumerate(tokens):
            E[i] = self.encode_token(token, context)

        return E

    def encode_text(self, text: str, context: dict[str, Any] | None = None) -> np.ndarray[Any, Any]:
        """Encode text by splitting into tokens and encoding each.

        Simple word-level tokenization for now.

        Args:
            text: Input text
            context: Optional context

        Returns:
            E ∈ R^(T, m) attribute matrix
        """
        # Simple whitespace tokenization
        tokens = text.split()
        return self.encode_sequence(tokens, context)

    def get_dimension_names(self) -> list[str]:
        """Get human-readable dimension names."""
        return [
            "tool_invocation",
            "safety_check",
            "causal_reasoning",
            "plan_phase",
            "verify_phase",
            "novel_concept",
            "tim_value_alignment",
            "code_reference",
            "refactor",
            "test_coverage",
            "collaboration",
            "hive_knowledge",
            "autonomous_action",
            "error_correction",
            "convergence",
            "exploration",
        ]


# Singleton instance
_attribute_encoder: AttributeEncoder | None = None


def get_attribute_encoder() -> AttributeEncoder:
    """Get singleton attribute encoder."""
    global _attribute_encoder
    if _attribute_encoder is None:
        _attribute_encoder = AttributeEncoder()
    return _attribute_encoder
