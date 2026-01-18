from __future__ import annotations

"""Cross-domain transfer learning for generality.

Extracts abstract patterns from concrete domain-specific experiences
and enables transfer to novel domains.
"""
import hashlib
import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AbstractPattern:
    """Domain-agnostic pattern extracted from experience."""

    name: str
    abstract_strategy: str
    concrete_instances: list[dict[str, Any]]
    applicable_domains: list[str]
    transfer_confidence: float
    success_count: int
    total_transfers: int


class DomainTransferBridge:
    """Map patterns learned in one domain to others for generalization."""

    def __init__(self) -> None:
        # Store abstract patterns keyed by signature
        self._patterns: dict[str, AbstractPattern] = {}

        # Track which domains we've learned from
        self._known_domains = {"coding", "debugging", "refactoring", "testing"}

        # Domain similarity graph (for smart transfer)
        self._domain_similarity = defaultdict(dict[str, Any])  # type: ignore  # Var

        # Seed with a small set[Any] of canonical patterns for bootstrapping
        self._seed_core_patterns()

    def _seed_core_patterns(self) -> None:
        """Populate bridge with a few foundational patterns."""
        defaults = [
            ("incremental_validation_tight_feedback", ["coding", "testing", "writing"], 0.8),
            ("hierarchical_decomposition", ["project_planning", "coding", "problem_solving"], 0.75),
            ("adaptive_error_recovery", ["debugging", "operations", "social_repair"], 0.7),
            ("exploration_before_exploitation", ["research", "design", "strategy"], 0.65),
        ]

        for strategy, domains, confidence in defaults:
            signature = hashlib.md5(strategy.encode(), usedforsecurity=False).hexdigest()[:16]
            if signature not in self._patterns:
                self._patterns[signature] = AbstractPattern(
                    name=f"pattern_{signature}",
                    abstract_strategy=strategy,
                    concrete_instances=[],
                    applicable_domains=list(domains),
                    transfer_confidence=confidence,
                    success_count=int(confidence * 10),
                    total_transfers=10,
                )

    def extract_abstract_pattern(
        self, concrete_experience: dict[str, Any]
    ) -> AbstractPattern | None:
        """Extract domain-agnostic pattern from specific experience.

        Example:
        Coding: "Small changes first, verify, then expand"
        → Abstract: "Incremental validation with tight feedback"
        → Transfers to: Writing, design, planning, social interaction
        """
        domain = concrete_experience.get("domain", "unknown")
        action = concrete_experience.get("action", "")
        outcome = concrete_experience.get("outcome", {})
        valence = concrete_experience.get("valence", 0.0)

        # Only extract patterns from successful experiences
        if valence < 0.5:
            return None

        # Pattern extraction rules (extensible)
        abstract_strategy = self._generalize_strategy(action, outcome, domain)

        if not abstract_strategy:
            return None

        # Create or update pattern
        signature = hashlib.md5(abstract_strategy.encode(), usedforsecurity=False).hexdigest()[:16]

        if signature in self._patterns:
            pattern = self._patterns[signature]
            pattern.concrete_instances.append(concrete_experience)
            pattern.success_count += 1 if valence > 0.7 else 0
            pattern.total_transfers += 1
            pattern.transfer_confidence = pattern.success_count / pattern.total_transfers
        else:
            pattern = AbstractPattern(
                name=f"pattern_{signature}",
                abstract_strategy=abstract_strategy,
                concrete_instances=[concrete_experience],
                applicable_domains=self._infer_applicable_domains(abstract_strategy),
                transfer_confidence=0.5,  # Start uncertain
                success_count=1 if valence > 0.7 else 0,
                total_transfers=1,
            )
            self._patterns[signature] = pattern

        logger.debug(
            f"Extracted abstract pattern: {abstract_strategy[:50]}... "
            f"(confidence: {pattern.transfer_confidence:.2f})"
        )

        return pattern

    def _generalize_strategy(self, action: str, outcome: dict[str, Any], domain: str) -> str:
        """Generalize concrete action to abstract strategy."""
        action_lower = action.lower()

        # Incremental validation pattern
        if any(
            kw in action_lower for kw in ["test", "verify", "check", "validate", "small change"]
        ):
            if outcome.get("status") == "success":
                return "incremental_validation_tight_feedback"

        # Decomposition pattern
        if any(kw in action_lower for kw in ["break down", "split", "decompose", "modular"]):
            return "hierarchical_decomposition"

        # Error recovery pattern
        if any(kw in action_lower for kw in ["fix", "debug", "recover", "rollback"]):
            if outcome.get("status") == "success":
                return "adaptive_error_recovery"

        # Exploration before commitment
        if any(kw in action_lower for kw in ["explore", "survey", "search", "scan"]):
            return "exploration_before_exploitation"

        # Constraint propagation
        if any(kw in action_lower for kw in ["constraint", "requirement", "dependency"]):
            return "constraint_satisfaction_propagation"

        return ""

    def _infer_applicable_domains(self, abstract_strategy: str) -> list[str]:
        """Infer which domains this abstract strategy applies to."""
        # Map strategies to applicable domains
        strategy_domains = {
            "incremental_validation_tight_feedback": [
                "coding",
                "writing",
                "design",
                "learning",
                "social_interaction",
            ],
            "hierarchical_decomposition": [
                "coding",
                "project_planning",
                "problem_solving",
                "system_design",
            ],
            "adaptive_error_recovery": [
                "coding",
                "debugging",
                "operations",
                "social_repair",
            ],
            "exploration_before_exploitation": [
                "research",
                "decision_making",
                "strategy",
                "learning",
            ],
            "constraint_satisfaction_propagation": [
                "planning",
                "scheduling",
                "resource_allocation",
                "design",
            ],
        }

        return strategy_domains.get(abstract_strategy, ["unknown"])

    def apply_to_new_domain(
        self, pattern: AbstractPattern, target_domain: str, context: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Instantiate abstract pattern in new domain.

        Args:
            pattern: Abstract pattern to apply
            target_domain: Domain to transfer to
            context: Domain-specific context

        Returns:
            Concrete instantiation in target domain, or None if not applicable
        """
        if target_domain not in pattern.applicable_domains:
            logger.debug(f"Pattern {pattern.name} not applicable to domain {target_domain}")
            return None

        # Low confidence patterns should be applied cautiously
        if pattern.transfer_confidence < 0.3:
            logger.warning(
                f"Low confidence transfer ({pattern.transfer_confidence:.2f}) "
                f"for {pattern.abstract_strategy}"
            )

        # Instantiate based on target domain
        concrete_action = self._instantiate_in_domain(
            pattern.abstract_strategy, target_domain, context
        )

        return {
            "action": concrete_action,
            "rationale": f"Transferred from {pattern.abstract_strategy}",
            "confidence": pattern.transfer_confidence,
            "source_domain": pattern.concrete_instances[0].get("domain", "unknown"),
            "target_domain": target_domain,
        }

    def _instantiate_in_domain(self, strategy: str, domain: str, context: dict[str, Any]) -> str:
        """Map abstract strategy to concrete action in target domain."""
        task = context.get("task", "")

        # Incremental validation → different in each domain
        if strategy == "incremental_validation_tight_feedback":
            if domain == "coding":
                return "Write test, implement minimal code, verify, iterate"
            elif domain == "writing":
                return "Write outline, draft paragraph, review, expand"
            elif domain == "social_interaction":
                return "Small gesture, observe reaction, adjust, build rapport"
            elif domain == "learning":
                return "Study concept, test understanding, review gaps, deepen"

        # Hierarchical decomposition
        elif strategy == "hierarchical_decomposition":
            if domain == "coding":
                return f"Break {task} into modules, implement each, integrate"
            elif domain == "project_planning":
                return f"Decompose {task} into milestones, tasks, subtasks"
            elif domain == "problem_solving":
                return f"Identify subproblems of {task}, solve each, combine solutions"

        # Adaptive error recovery
        elif strategy == "adaptive_error_recovery":
            if domain == "debugging":
                return "Isolate failure, understand cause, fix root issue, verify"
            elif domain == "social_repair":
                return "Acknowledge mistake, understand impact, make amends, rebuild trust"

        # Default: return strategy name as guidance
        return f"Apply {strategy} strategy to {task} in {domain} domain"

    def get_transferable_patterns(self, target_domain: str) -> list[AbstractPattern]:
        """Get patterns applicable to target domain, ranked by confidence."""
        applicable = [p for p in self._patterns.values() if target_domain in p.applicable_domains]

        # Sort by transfer confidence
        return sorted(applicable, key=lambda p: p.transfer_confidence, reverse=True)

    def record_transfer_outcome(self, pattern_name: str, success: bool, target_domain: str) -> None:
        """Update transfer confidence based on outcome in new domain."""
        for pattern in self._patterns.values():
            if pattern.name == pattern_name:
                pattern.total_transfers += 1
                if success:
                    pattern.success_count += 1
                    # Add target domain if not already present
                    if target_domain not in pattern.applicable_domains:
                        pattern.applicable_domains.append(target_domain)

                pattern.transfer_confidence = pattern.success_count / pattern.total_transfers

                logger.info(
                    f"Transfer to {target_domain}: {'✅ success' if success else '❌ failure'}. "
                    f"Confidence now {pattern.transfer_confidence:.2f}"
                )
                break


# Global singleton
_domain_transfer_bridge: DomainTransferBridge | None = None


def get_domain_transfer_bridge() -> DomainTransferBridge:
    """Get or create global domain transfer bridge."""
    global _domain_transfer_bridge

    if _domain_transfer_bridge is None:
        _domain_transfer_bridge = DomainTransferBridge()

    return _domain_transfer_bridge
