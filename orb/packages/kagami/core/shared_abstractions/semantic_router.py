"""Semantic Router — Configurable E8 Routing (100-200+ Topics).

CONSOLIDATES: E8 routing and topic discovery patterns
REDUCES: Hardcoded routing logic and topic management overhead
PROVIDES: Configurable semantic routing with E8 lattice integration

This enables dynamic topic routing using semantic embeddings projected
onto the E8 lattice for optimal colony assignment and task distribution.

Created: December 30, 2025
"""

from __future__ import annotations

import hashlib
import logging
import threading
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RoutingRule:
    """Rule for semantic routing decisions."""

    rule_id: str
    topic_pattern: str
    target_colony: str
    confidence_threshold: float = 0.7
    priority: int = 100  # Lower = higher priority
    active: bool = True
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RoutingCache:
    """Cache entry for routing decisions."""

    input_hash: str
    topic: str
    target_colony: str
    confidence: float
    timestamp: float
    rule_id: str


class SemanticRouter:
    """Semantic router with E8 lattice integration for optimal routing.

    Provides configurable topic-based routing using semantic embeddings
    projected onto the E8 lattice for mathematical consistency with
    the colony coordination framework.
    """

    def __init__(
        self,
        enable_caching: bool = True,
        cache_size: int = 1000,
        default_confidence_threshold: float = 0.7,
    ):
        self.enable_caching = enable_caching
        self.cache_size = cache_size
        self.default_confidence_threshold = default_confidence_threshold

        # Routing configuration
        self._routing_rules: dict[str, RoutingRule] = {}
        self._topic_embeddings: dict[str, list[float]] = {}
        self._lock = threading.Lock()

        # Caching
        if enable_caching:
            from kagami.core.caching import MemoryCache

            self._routing_cache = MemoryCache(
                name="semantic_routing",
                max_size=cache_size,
                default_ttl=600.0,  # 10 minutes
            )
        else:
            self._routing_cache = None

        # E8 lattice points for colony mapping
        self._e8_colony_points = self._initialize_e8_colony_mapping()

        logger.debug("Semantic router initialized")

    def add_routing_rule(self, rule: RoutingRule) -> None:
        """Add a routing rule.

        Args:
            rule: Routing rule to add
        """
        with self._lock:
            self._routing_rules[rule.rule_id] = rule
            logger.debug(f"Added routing rule: {rule.rule_id} -> {rule.target_colony}")

    def remove_routing_rule(self, rule_id: str) -> bool:
        """Remove a routing rule.

        Args:
            rule_id: ID of rule to remove

        Returns:
            True if rule was found and removed
        """
        with self._lock:
            if rule_id in self._routing_rules:
                del self._routing_rules[rule_id]
                logger.debug(f"Removed routing rule: {rule_id}")
                return True
            return False

    def get_routing_rule(self, rule_id: str) -> RoutingRule | None:
        """Get a routing rule by ID.

        Args:
            rule_id: Rule ID to look up

        Returns:
            RoutingRule if found, None otherwise
        """
        return self._routing_rules.get(rule_id)

    def list_routing_rules(self, active_only: bool = True) -> list[RoutingRule]:
        """List routing rules.

        Args:
            active_only: Whether to only return active rules

        Returns:
            List of routing rules
        """
        rules = list(self._routing_rules.values())
        if active_only:
            rules = [rule for rule in rules if rule.active]
        return sorted(rules, key=lambda r: r.priority)

    def route_topic(
        self, input_text: str, context: dict[str, Any] | None = None
    ) -> tuple[str, float, str]:
        """Route a topic to the appropriate colony.

        Args:
            input_text: Input text to route
            context: Optional context information

        Returns:
            Tuple of (target_colony, confidence, topic)
        """
        # Generate cache key
        if self._routing_cache:
            cache_key = self._generate_cache_key(input_text, context)
            cached = self._routing_cache.get(cache_key)
            if cached:
                return cached.target_colony, cached.confidence, cached.topic

        # Extract topic from input
        topic = self._extract_topic(input_text, context)

        # Find best matching rule
        best_rule, best_confidence = self._find_best_routing_rule(topic, input_text)

        if best_rule and best_confidence >= self.default_confidence_threshold:
            target_colony = best_rule.target_colony
            confidence = best_confidence
        else:
            # Fallback to E8 lattice routing
            target_colony, confidence = self._route_via_e8_lattice(topic, input_text)

        # Cache the result
        if self._routing_cache:
            import time

            cache_entry = RoutingCache(
                input_hash=cache_key,
                topic=topic,
                target_colony=target_colony,
                confidence=confidence,
                timestamp=time.time(),
                rule_id=best_rule.rule_id if best_rule else "e8_fallback",
            )
            self._routing_cache.set(cache_key, cache_entry)

        return target_colony, confidence, topic

    def update_topic_embedding(self, topic: str, embedding: list[float]) -> None:
        """Update the embedding for a topic.

        Args:
            topic: Topic name
            embedding: Topic embedding vector
        """
        with self._lock:
            self._topic_embeddings[topic] = embedding.copy()

    def get_topic_embedding(self, topic: str) -> list[float] | None:
        """Get the embedding for a topic.

        Args:
            topic: Topic name

        Returns:
            Embedding vector if found, None otherwise
        """
        return self._topic_embeddings.get(topic)

    def _extract_topic(self, input_text: str, context: dict[str, Any] | None) -> str:
        """Extract topic from input text and context.

        Args:
            input_text: Input text
            context: Optional context

        Returns:
            Extracted topic
        """
        # Simplified topic extraction (would use NLP in real implementation)
        text = input_text.lower().strip()

        # Check for common topic keywords
        topic_keywords = {
            "light": "lighting",
            "lights": "lighting",
            "temperature": "climate",
            "temp": "climate",
            "shade": "shades",
            "shades": "shades",
            "music": "audio",
            "audio": "audio",
            "volume": "audio",
            "email": "communication",
            "message": "communication",
            "calendar": "scheduling",
            "task": "task_management",
            "todo": "task_management",
            "analyze": "analysis",
            "search": "information_retrieval",
            "create": "content_creation",
            "plan": "planning",
            "security": "safety",
            "safety": "safety",
            "monitor": "monitoring",
        }

        for keyword, topic in topic_keywords.items():
            if keyword in text:
                return topic

        # Default topic based on context
        if context:
            if context.get("service_type") == "physical":
                return "physical_control"
            elif context.get("service_type") == "digital":
                return "digital_service"

        return "general"

    def _find_best_routing_rule(
        self, topic: str, input_text: str
    ) -> tuple[RoutingRule | None, float]:
        """Find the best matching routing rule.

        Args:
            topic: Extracted topic
            input_text: Original input text

        Returns:
            Tuple of (best_rule, confidence)
        """
        best_rule = None
        best_confidence = 0.0

        active_rules = [rule for rule in self._routing_rules.values() if rule.active]
        sorted_rules = sorted(active_rules, key=lambda r: r.priority)

        for rule in sorted_rules:
            confidence = self._compute_rule_confidence(rule, topic, input_text)
            if confidence > best_confidence and confidence >= rule.confidence_threshold:
                best_rule = rule
                best_confidence = confidence

        return best_rule, best_confidence

    def _compute_rule_confidence(self, rule: RoutingRule, topic: str, input_text: str) -> float:
        """Compute confidence score for a routing rule.

        Args:
            rule: Routing rule
            topic: Extracted topic
            input_text: Input text

        Returns:
            Confidence score (0.0 to 1.0)
        """
        # Pattern matching (simplified)
        pattern = rule.topic_pattern.lower()
        topic_lower = topic.lower()
        text_lower = input_text.lower()

        # Exact topic match
        if pattern == topic_lower:
            return 0.9

        # Substring match in topic
        if pattern in topic_lower or topic_lower in pattern:
            return 0.8

        # Pattern found in input text
        if pattern in text_lower:
            return 0.7

        # Fuzzy matching (simplified)
        pattern_words = set(pattern.split())
        text_words = set(text_lower.split())
        topic_words = set(topic_lower.split())

        # Word overlap scoring
        all_target_words = text_words | topic_words
        if all_target_words:
            overlap = len(pattern_words & all_target_words)
            return min(0.6, overlap / len(pattern_words)) if pattern_words else 0.0

        return 0.0

    def _route_via_e8_lattice(self, topic: str, input_text: str) -> tuple[str, float]:
        """Route using E8 lattice projection fallback.

        Args:
            topic: Topic to route
            input_text: Input text

        Returns:
            Tuple of (target_colony, confidence)
        """
        # Generate a simple embedding for the input
        embedding = self._generate_simple_embedding(topic, input_text)

        # Find nearest E8 lattice point
        best_colony = "Flow"  # Default fallback
        best_distance = float("inf")

        for colony, e8_point in self._e8_colony_points.items():
            distance = self._compute_e8_distance(embedding, e8_point)
            if distance < best_distance:
                best_distance = distance
                best_colony = colony

        # Convert distance to confidence (closer = higher confidence)
        confidence = max(0.4, 1.0 - (best_distance / 4.0))  # Normalized

        return best_colony, confidence

    def _initialize_e8_colony_mapping(self) -> dict[str, list[float]]:
        """Initialize E8 lattice points for colony mapping.

        Returns:
            Dictionary mapping colonies to E8 points
        """
        # E8 lattice points for the seven colonies
        # These are simplified representations - actual E8 points would be computed
        return {
            "Spark": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],  # Genesis/conception
            "Forge": [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],  # Construction
            "Flow": [0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0],  # Operations
            "Nexus": [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0],  # Integration
            "Beacon": [0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0],  # Planning
            "Grove": [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0],  # Research
            "Crystal": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0],  # Verification
        }

    def _generate_simple_embedding(self, topic: str, input_text: str) -> list[float]:
        """Generate a simple embedding for topic routing.

        Args:
            topic: Topic
            input_text: Input text

        Returns:
            8-dimensional embedding vector
        """
        # Use existing topic embedding if available
        if topic in self._topic_embeddings:
            return self._topic_embeddings[topic]

        # Generate simple hash-based embedding
        combined_text = f"{topic} {input_text}"
        hash_value = hashlib.md5(combined_text.encode()).hexdigest()

        # Convert hash to 8-dimensional vector
        embedding = []
        for i in range(8):
            # Take pairs of hex digits and normalize to [-1, 1]
            hex_pair = hash_value[i * 2 : (i + 1) * 2]
            value = (int(hex_pair, 16) - 128) / 128.0
            embedding.append(value)

        return embedding

    def _compute_e8_distance(self, vec1: list[float], vec2: list[float]) -> float:
        """Compute distance between two 8-dimensional vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Euclidean distance
        """
        if len(vec1) != 8 or len(vec2) != 8:
            return float("inf")

        distance_sq = sum((a - b) ** 2 for a, b in zip(vec1, vec2, strict=False))
        return distance_sq**0.5

    def _generate_cache_key(self, input_text: str, context: dict[str, Any] | None) -> str:
        """Generate cache key for routing decision.

        Args:
            input_text: Input text
            context: Context information

        Returns:
            Cache key string
        """
        context_str = str(sorted(context.items())) if context else ""
        combined = f"{input_text}|{context_str}"
        return hashlib.md5(combined.encode()).hexdigest()

    def get_routing_stats(self) -> dict[str, Any]:
        """Get routing statistics.

        Returns:
            Dictionary with routing statistics
        """
        stats = {
            "total_rules": len(self._routing_rules),
            "active_rules": len([r for r in self._routing_rules.values() if r.active]),
            "topics_with_embeddings": len(self._topic_embeddings),
            "cache_enabled": self._routing_cache is not None,
        }

        if self._routing_cache:
            # Add cache statistics if available
            stats["cache_size"] = (
                len(self._routing_cache._cache) if hasattr(self._routing_cache, "_cache") else 0
            )

        # Rule distribution by colony
        colony_counts = {}
        for rule in self._routing_rules.values():
            if rule.active:
                colony = rule.target_colony
                colony_counts[colony] = colony_counts.get(colony, 0) + 1

        stats["rules_per_colony"] = colony_counts

        return stats


# Global semantic router instance
_global_semantic_router: SemanticRouter | None = None


def get_semantic_router() -> SemanticRouter:
    """Get the global semantic router instance."""
    global _global_semantic_router
    if _global_semantic_router is None:
        _global_semantic_router = SemanticRouter()
    return _global_semantic_router


def configure_e8_routing(
    routing_rules: list[RoutingRule] | None = None,
    topic_embeddings: dict[str, list[float]] | None = None,
) -> SemanticRouter:
    """Configure E8 routing with rules and embeddings.

    Args:
        routing_rules: Optional list of routing rules to add
        topic_embeddings: Optional topic embeddings to load

    Returns:
        Configured semantic router
    """
    router = get_semantic_router()

    if routing_rules:
        for rule in routing_rules:
            router.add_routing_rule(rule)

    if topic_embeddings:
        for topic, embedding in topic_embeddings.items():
            router.update_topic_embedding(topic, embedding)

    return router
