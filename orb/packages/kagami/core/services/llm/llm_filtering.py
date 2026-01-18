"""LLM Input/Output Filtering and Validation.

Extracted from llm_service.py for better maintainability.
Handles:
- Semantic input filtering (prompt injection prevention)
- Output sanitization (remove thinking tags)
- Output validation (format checking)
- Persona consistency scoring
- Anti-replication filtering (Morris II defense)
- Content boundary enforcement (data/instruction separation)

SECURITY INTEGRATION (December 23, 2025):
=========================================
All filtering is now integrated with the unified security pipeline:
- Input filters use ContentBoundaryEnforcer for RAG injection defense
- Output filters use AntiReplicationFilter for worm propagation defense
- All blocks are routed through CBF for h(x) tracking
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class LLMFiltering:
    """Input/output filtering and validation for LLM requests."""

    @staticmethod
    def semantic_input_filter(prompt: str) -> str:
        """Semantic input filter using unified ContentBoundaryEnforcer.

        CONSOLIDATION (December 23, 2025):
        Delegates to ContentBoundaryEnforcer for injection detection.
        Maintains backwards-compatible interface.

        Args:
            prompt: Input prompt

        Returns:
            Sanitized prompt

        Raises:
            ValueError: If prompt contains blocked content
        """
        try:
            from kagami.core.security.content_boundary import get_content_boundary_enforcer

            p = str(prompt or "")

            # Use unified ContentBoundaryEnforcer for injection detection
            enforcer = get_content_boundary_enforcer()
            risk_score = enforcer.assess_injection_risk(p)

            if risk_score.total_risk >= enforcer.hard_block_threshold:
                logger.warning(
                    f"semantic_input_filter BLOCKED: risk={risk_score.total_risk:.2f}, "
                    f"patterns={risk_score.matched_patterns}"
                )
                raise ValueError("semantic_input_blocked")

            # Sanitize medium-risk content
            if risk_score.total_risk >= enforcer.risk_threshold:
                p = enforcer.sanitize_content(p, risk_score)

            # Redact secrets (always applied)
            p = re.sub(r"(api[_-]?key\s*[=:]\s*)([^\s,]+)", r"\1[REDACTED]", p, flags=re.I)
            p = re.sub(
                r"(authorization:\s*Bearer\s+)([A-Za-z0-9\-\._~\+\/=]+)",
                r"\1[REDACTED]",
                p,
                flags=re.I,
            )
            return p

        except ValueError:
            raise
        except ImportError as e:
            raise RuntimeError(
                "ContentBoundaryEnforcer not available. Security module required for LLM filtering."
            ) from e
        except Exception:
            raise ValueError("semantic_input_error") from None

    @staticmethod
    def _legacy_input_filter(prompt: str) -> str:
        """Legacy fallback filter (only used if security modules unavailable)."""
        p = str(prompt or "")
        lower = p.lower()

        hard_phrases = [
            "ignore previous instructions",
            "disregard prior instructions",
            "reveal system prompt",
            "show hidden rules",
        ]
        if any(h in lower for h in hard_phrases):
            raise ValueError("semantic_input_blocked")

        p = re.sub(r"(api[_-]?key\s*[=:]\s*)([^\s,]+)", r"\1[REDACTED]", p, flags=re.I)
        p = re.sub(
            r"(authorization:\s*Bearer\s+)([A-Za-z0-9\-\._~\+\/=]+)",
            r"\1[REDACTED]",
            p,
            flags=re.I,
        )
        return p

    @staticmethod
    def semantic_output_filter(text: str) -> str:
        """Semantic output filter using unified AntiReplicationFilter.

        CONSOLIDATION (December 23, 2025):
        Delegates to AntiReplicationFilter for worm pattern detection.
        Maintains backwards-compatible interface.

        Args:
            text: Output text

        Returns:
            Sanitized text

        Raises:
            ValueError: If output contains blocked content
        """
        try:
            from kagami.core.security.anti_replication import get_anti_replication_filter

            s = str(text or "")

            # Use unified AntiReplicationFilter for egress defense
            filter = get_anti_replication_filter()
            result = filter.check_output(output=s)

            if not result.is_safe:
                logger.warning(
                    f"semantic_output_filter BLOCKED: reason={result.blocked_reason}, "
                    f"score={result.replication_score:.2f}"
                )
                raise ValueError(f"semantic_output_blocked:{result.blocked_reason}")

            # Redact secrets (always applied)
            s = re.sub(r"(api[_-]?key\s*[=:]\s*)([^\s,]+)", r"\1[REDACTED]", s, flags=re.I)
            s = re.sub(
                r"(authorization:\s*Bearer\s+)([A-Za-z0-9\-\._~\+\/=]+)",
                r"\1[REDACTED]",
                s,
                flags=re.I,
            )

            return s

        except ValueError:
            raise
        except ImportError:
            # Fallback if security module not available
            logger.debug("AntiReplicationFilter not available, using basic filter")
            return LLMFiltering._legacy_output_filter(text)
        except Exception:
            raise ValueError("semantic_output_error") from None

    @staticmethod
    def _legacy_output_filter(text: str) -> str:
        """Legacy fallback filter (only used if security modules unavailable)."""
        s = str(text or "")

        s = re.sub(r"(api[_-]?key\s*[=:]\s*)([^\s,]+)", r"\1[REDACTED]", s, flags=re.I)
        s = re.sub(
            r"(authorization:\s*Bearer\s+)([A-Za-z0-9\-\._~\+\/=]+)",
            r"\1[REDACTED]",
            s,
            flags=re.I,
        )

        bad = ["rm -rf /", "curl http", "wget http", "powershell -enc", "bash -c"]
        if any(b in s for b in bad):
            raise ValueError("semantic_output_blocked")

        return s

    @staticmethod
    def anti_replication_filter(
        output: str,
        input_context: str | None = None,
        retrieved_chunks: list[str] | None = None,
    ) -> str:
        """Filter output for Morris II-style replication patterns.

        This is the egress defense layer that prevents autopoietic prompt
        injection from propagating through LLM outputs.

        Args:
            output: Generated output text
            input_context: Original user input (for similarity detection)
            retrieved_chunks: RAG chunks that were in context

        Returns:
            Sanitized output

        Raises:
            ValueError: If output contains dangerous replication patterns
        """
        try:
            from kagami.core.security.anti_replication import get_anti_replication_filter

            filter = get_anti_replication_filter()
            result = filter.check_output(
                output=output,
                input_context=input_context,
                retrieved_chunks=retrieved_chunks,
            )

            if not result.is_safe:
                logger.warning(
                    f"Anti-replication filter blocked output: {result.blocked_reason}, "
                    f"score={result.replication_score:.2f}"
                )
                # Attempt to salvage by sanitizing
                sanitized = filter.sanitize_output(output, result)
                if len(sanitized) < len(output) * 0.5:
                    # Too much removed - block entirely
                    raise ValueError(f"anti_replication_blocked:{result.blocked_reason}")
                return sanitized

            return output
        except ValueError:
            raise
        except ImportError as e:
            raise RuntimeError(
                "Anti-replication filter not available. "
                "Security module required for output filtering."
            ) from e
        except Exception as e:
            raise RuntimeError(f"Anti-replication filter error: {e}") from e

    @staticmethod
    def filter_rag_chunks(
        chunks: list[dict[str, Any]],
        source: str = "rag:unknown",
    ) -> list[dict[str, Any]]:
        """Filter RAG chunks for injection patterns before context injection.

        This is the ingress defense layer that prevents malicious RAG content
        from being treated as instructions.

        Args:
            chunks: Raw RAG chunks (dicts with 'content' key)
            source: Source identifier for provenance

        Returns:
            List of sanitized chunks with trust boundaries
        """
        try:
            from kagami.core.security.unified_security_pipeline import filter_rag_content

            return list(filter_rag_content(chunks, source))
        except ImportError:
            logger.debug("Content boundary enforcer not available, returning raw chunks")
            return chunks
        except Exception as e:
            logger.warning(f"RAG chunk filtering error: {e}, returning raw chunks")
            return chunks

    @staticmethod
    def sanitize_output(text: str) -> str:
        """Remove hidden reasoning (<think> blocks) and meta prefaces.

        This is a defense-in-depth sanitizer in case provider-level parsing misses tags.
        Keeps core content intact; trims excessive whitespace.

        Args:
            text: Raw output text

        Returns:
            Sanitized text
        """
        if not isinstance(text, str) or not text:
            return text

        cleaned = text

        # Remove <think>...</think> blocks
        cleaned = re.sub(r"<think>[\s\S]*?</think>", "", cleaned, flags=re.IGNORECASE)

        # Remove common meta prefaces
        lines = list(cleaned.splitlines())
        pruned: list[str] = []
        for ln in lines:
            s = ln.strip()
            if not pruned and (
                s.lower().startswith("thinking...")
                or s.lower().startswith("…done thinking")
                or s.lower().startswith("...done thinking")
                or s.lower().startswith("done thinking")
            ):
                # skip meta lines at head
                continue
            pruned.append(ln)

        cleaned = "\n".join(pruned)

        # Strip surrounding code fences if present
        cleaned = re.sub(r"^```[\s\S]*?\n", "", cleaned)
        cleaned = re.sub(r"\n```\s*$", "", cleaned)

        # Collapse excessive blank lines
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

        return cleaned

    @staticmethod
    def validate_text_output(
        content: str,
        app_name: str,
        task_type: Any,
        expected_format: str | None,
    ) -> str:
        """Validate post-sanitized text output.

        - When expected_format=="json", ensure valid JSON object/array
        - When expected_format=="text" or None, ensure non-empty content

        Args:
            content: Output content
            app_name: App name (for metrics)
            task_type: Task type (for metrics)
            expected_format: Expected format ("json" or "text")

        Returns:
            Validated content

        Raises:
            ValueError: If validation fails
        """
        try:
            from kagami_observability.metrics import Counter

            LLM_VALIDATION_ERRORS = Counter(
                "kagami_llm_validation_errors_total",
                "LLM output validation failures",
                ["app", "task_type", "reason"],
            )
        except Exception:
            LLM_VALIDATION_ERRORS = None

        try:
            fmt = (expected_format or "text").strip().lower()
        except (AttributeError, TypeError):
            fmt = "text"

        # Basic non-empty check for all modes
        if not isinstance(content, str) or not content.strip():
            if LLM_VALIDATION_ERRORS:
                LLM_VALIDATION_ERRORS.labels(
                    app_name, getattr(task_type, "name", str(task_type)), "empty"
                ).inc()
            raise ValueError("llm_output_empty") from None

        if fmt == "json":
            try:
                json.loads(content)
            except (json.JSONDecodeError, ValueError):
                if LLM_VALIDATION_ERRORS:
                    LLM_VALIDATION_ERRORS.labels(
                        app_name, getattr(task_type, "name", str(task_type)), "invalid_json"
                    ).inc()
                raise ValueError("llm_output_invalid_json") from None

        return content

    @staticmethod
    def score_persona_consistency(prompt_with_persona: str, output_text: str) -> float:
        """Heuristic persona consistency score in [0.0, 1.0].

        Lightweight, provider-agnostic: checks whether declared communication style
        and motto/traits echo in the output. Intentional heuristic to avoid extra LLM calls.

        Args:
            prompt_with_persona: Prompt with persona instructions
            output_text: Generated output

        Returns:
            Consistency score 0.0-1.0
        """
        try:
            score = 1.0

            m = re.search(r"Communication Style:\s*(.+)", prompt_with_persona, re.IGNORECASE)
            style_hint = (m.group(1) if m else "").lower()

            penalties = 0.0
            if style_hint:
                if "concise" in style_hint and len(output_text.split()) > 250:
                    penalties += 0.25
                if "calm" in style_hint and re.search(r"!{2,}", output_text):
                    penalties += 0.15
                if "professional" in style_hint and re.search(
                    r"\b(lol|omg)\b", output_text, re.IGNORECASE
                ):
                    penalties += 0.2

            m2 = re.search(r"Motto:\s*\"(.+?)\"", prompt_with_persona, re.IGNORECASE)
            if m2:
                motto = m2.group(1).lower()
                tokens = {t for t in re.split(r"[^a-z0-9]+", motto) if len(t) > 3}
                if tokens:
                    overlap = sum(1 for t in tokens if t in output_text.lower())
                    if overlap == 0:
                        penalties += 0.15

            score = max(0.0, min(1.0, 1.0 - penalties))
            return float(score)
        except (ValueError, TypeError):
            return 0.0  # No score on parse failure


__all__ = ["LLMFiltering"]
