"""Common Sense Instinct - A+ Plan Phase 1.3

Production instinct for common sense reasoning and plausibility checking.

Integrates ConceptNet for everyday knowledge:
- Physical properties (ice melts when warm)
- Social scripts (crying indicates sadness)
- Causal relationships (dropping cup → falls)

Blocks implausible operations before execution.
"""

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Feature flag
COMMON_SENSE_ENABLED = os.getenv("KAGAMI_COMMON_SENSE_ENABLED", "1") == "1"
BLOCK_THRESHOLD = float(os.getenv("KAGAMI_COMMON_SENSE_BLOCK_THRESHOLD", "0.3"))

# Global instance
_common_sense_instinct: Optional["CommonSenseInstinct"] = None


class CommonSenseInstinct:
    """Production instinct for common sense reasoning.

    Uses ConceptNet API for everyday knowledge and plausibility checking.
    Blocks implausible high-risk operations.
    """

    def __init__(self) -> None:
        """Initialize common sense instinct."""
        self._enabled = COMMON_SENSE_ENABLED
        self._knowledge = None  # Lazy-load ConceptNet
        self._cache = {}  # type: ignore[var-annotated]
        self._block_threshold = BLOCK_THRESHOLD

        logger.info(
            f"✅ Common Sense Instinct initialized "
            f"(enabled={self._enabled}, block_threshold={self._block_threshold})"
        )

    def _get_knowledge(self) -> Any:
        """Lazy-load ConceptNet knowledge base."""
        if self._knowledge is None and self._enabled:
            try:
                from kagami_knowledge.common_sense import get_common_sense

                self._knowledge = get_common_sense()
                logger.info("✅ ConceptNet knowledge base loaded")
            except Exception as e:
                raise RuntimeError(
                    f"ConceptNet unavailable: {e}. Cannot operate without common sense."
                ) from e
        return self._knowledge

    async def check_plausibility(self, operation: str, context: dict[str, Any]) -> dict[str, Any]:
        """Check if an operation is plausible according to common sense.

        Args:
            operation: Operation description
            context: Additional context

        Returns:
            {
                "plausible": bool,
                "confidence": float (0.0-1.0),
                "reason": str,
                "should_block": bool
            }
        """
        if not self._enabled:
            return {
                "plausible": True,
                "confidence": 0.5,
                "reason": "common_sense_disabled",
                "should_block": False,
            }

        # Check cache
        cache_key = f"{operation}:{context.get('risk_level', 'unknown')}"
        if cache_key in self._cache:
            return self._cache[cache_key]  # type: ignore[no-any-return]

        knowledge = self._get_knowledge()
        if knowledge is None:
            # Fail-fast: block if we can't verify plausibility
            raise RuntimeError(
                f"Cannot check plausibility of '{operation}': knowledge base unavailable. "
                "Operation blocked for safety."
            )

        # Query ConceptNet
        try:
            result = await knowledge.check_plausibility(operation)

            plausible = result["plausible"]
            confidence = result["confidence"]

            # Determine if we should block
            risk_level = context.get("risk_level", "low")
            should_block = (
                not plausible
                and confidence > self._block_threshold
                and risk_level in ["high", "critical"]
            )

            check_result = {
                "plausible": plausible,
                "confidence": confidence,
                "reason": (
                    result.get("supporting_knowledge", [])[0]
                    if result.get("supporting_knowledge")
                    else "no_evidence"
                ),
                "should_block": should_block,
            }

            # Cache result
            self._cache[cache_key] = check_result

            # Log warnings for implausible operations
            if not plausible:
                logger.warning(
                    f"⚠️  Common sense check: '{operation}' seems implausible "
                    f"(confidence={confidence:.2f}, risk={risk_level})"
                )

            # Emit metric
            try:
                from kagami_observability.metrics import Counter

                COMMON_SENSE_CHECKS = Counter(
                    "kagami_common_sense_checks_total",
                    "Total common sense plausibility checks",
                    ["plausible"],
                )
                COMMON_SENSE_CHECKS.labels(plausible=str(plausible)).inc()

                if should_block:
                    BLOCKS = Counter(
                        "kagami_common_sense_blocks_total", "Operations blocked by common sense"
                    )
                    BLOCKS.inc()
            except Exception:
                pass

            return check_result

        except Exception as e:
            logger.error(f"Common sense check failed: {e}")
            # Fail open (allow operation)
            return {
                "plausible": True,
                "confidence": 0.0,
                "reason": f"error: {e}",
                "should_block": False,
            }

    async def get_related_knowledge(self, concept: str, limit: int = 5) -> list[dict[str, Any]]:
        """Get related common sense knowledge about a concept.

        Args:
            concept: Concept to query
            limit: Max results

        Returns:
            List of related knowledge edges
        """
        knowledge = self._get_knowledge()
        if knowledge is None:
            return []

        try:
            edges = await knowledge.query(concept, limit=limit)
            return edges  # type: ignore[no-any-return]
        except Exception as e:
            logger.debug(f"Knowledge query failed: {e}")
            return []

    async def infer_properties(self, entity: str) -> list[str]:
        """Infer common properties of an entity.

        Example: infer_properties("ice") → ["cold", "solid", "melts"]
        """
        knowledge = self._get_knowledge()
        if knowledge is None:
            return []

        try:
            properties = await knowledge.get_properties(entity)
            return properties  # type: ignore[no-any-return]
        except Exception as e:
            logger.debug(f"Property inference failed: {e}")
            return []

    async def infer_causes(self, effect: str) -> list[str]:
        """Infer what typically causes an effect.

        Example: infer_causes("crying") → ["sadness", "pain", "joy"]
        """
        knowledge = self._get_knowledge()
        if knowledge is None:
            return []

        try:
            causes = await knowledge.get_causes(effect)
            return causes  # type: ignore[no-any-return]
        except Exception as e:
            logger.debug(f"Cause inference failed: {e}")
            return []


def get_common_sense_instinct() -> CommonSenseInstinct:
    """Get singleton common sense instinct."""
    global _common_sense_instinct

    if _common_sense_instinct is None:
        _common_sense_instinct = CommonSenseInstinct()

    return _common_sense_instinct


__all__ = ["COMMON_SENSE_ENABLED", "CommonSenseInstinct", "get_common_sense_instinct"]
