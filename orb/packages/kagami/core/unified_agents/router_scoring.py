# pyright: reportGeneralTypeIssues=false
"""Fano Action Router - Scoring and Utility Calculations.

This module contains colony scoring algorithms, utility calculations,
confidence metrics, complexity inference, and cost evaluation.

Split from fano_action_router.py (December 28, 2025)
Enhanced with service context injection (January 2026)
"""

from __future__ import annotations

import logging
import time
from typing import Any

from .router_core import (
    COLONY_NAMES,
    RoutingResult,
)

logger = logging.getLogger(__name__)


# =============================================================================
# SERVICE CONTEXT MAPPING (January 2026)
# =============================================================================

# Map colonies to their primary services and capabilities
# Updated January 5, 2026: Added Figma direct integration
COLONY_SERVICE_MAP: dict[str, dict[str, Any]] = {
    "spark": {
        "primary_services": ["twitter", "slack", "figma"],
        "context_hint": "Twitter trends for ideation. Figma design inspiration. Slack brainstorm channels.",
        "key_actions": [
            "TWITTER_SEARCH",
            "SLACK_CREATE_CHANNEL",
            "figma.get_file",
            "figma.add_comment",
        ],
    },
    "forge": {
        "primary_services": ["github", "linear"],
        "context_hint": "GitHub branches available. Linear issues trackable. Auto-merge enabled.",
        "key_actions": ["GITHUB_CREATE_A_REFERENCE", "LINEAR_CREATE_LINEAR_ISSUE"],
    },
    "flow": {
        "primary_services": ["github", "slack"],
        "context_hint": "CI monitoring active. Slack alerts configured. Auto-debug available.",
        "key_actions": ["GITHUB_LIST_WORKFLOW_RUNS_FOR_A_REPOSITORY", "SLACK_SEND_MESSAGE"],
    },
    "nexus": {
        "primary_services": ["all"],
        "context_hint": "All 12 services available. Cross-domain triggers configured. Event bus active.",
        "key_actions": ["Ecosystem orchestration", "Cross-service routing", "Event publishing"],
    },
    "beacon": {
        "primary_services": ["linear", "notion", "calendar"],
        "context_hint": "Linear milestones available. Notion KB for decisions. Calendar for scheduling.",
        "key_actions": [
            "LINEAR_GET_CYCLES_BY_TEAM_ID",
            "NOTION_CREATE_NOTION_PAGE",
            "GOOGLECALENDAR_LIST_EVENTS",
        ],
    },
    "grove": {
        "primary_services": ["notion", "googledrive"],
        "context_hint": "Notion KB for research persistence. Drive for organization.",
        "key_actions": ["NOTION_SEARCH_NOTION_PAGE", "GOOGLEDRIVE_LIST_FILES"],
    },
    "crystal": {
        "primary_services": ["github", "linear", "figma"],
        "context_hint": "CI checks available. Figma VLM design QA. PR verification. Quality gates.",
        "key_actions": [
            "GITHUB_GET_A_PULL_REQUEST",
            "figma.get_file_images",
            "VLM design analysis",
        ],
    },
}


# =============================================================================
# SCORING METHODS (Extension of FanoActionRouter)
# =============================================================================


class RouterScoringMixin:
    """Mixin class providing scoring and utility calculation methods for FanoActionRouter.

    This mixin contains all the methods related to:
    - Task type extraction and complexity inference
    - OOD risk assessment
    - Colony selection and utility lookup
    - Cost evaluation and routing optimization
    - Cache management with TTL
    - Service context injection (January 2026)
    """

    # =========================================================================
    # SERVICE CONTEXT INJECTION (January 2026)
    # =========================================================================

    def get_service_context(self, colony_name: str) -> str:
        """Get service context hint for a colony.

        This method returns a string hint describing available services
        and capabilities for the given colony, enabling context-aware routing.

        Args:
            colony_name: Name of the colony (spark, forge, flow, etc.)

        Returns:
            Service context hint string
        """
        colony_lower = colony_name.lower()
        service_info = COLONY_SERVICE_MAP.get(colony_lower, {})
        return service_info.get("context_hint", "")

    def get_colony_services(self, colony_name: str) -> list[str]:
        """Get primary services for a colony.

        Args:
            colony_name: Name of the colony

        Returns:
            List of primary service names
        """
        colony_lower = colony_name.lower()
        service_info = COLONY_SERVICE_MAP.get(colony_lower, {})
        return service_info.get("primary_services", [])

    def get_colony_actions(self, colony_name: str) -> list[str]:
        """Get key actions available to a colony.

        Args:
            colony_name: Name of the colony

        Returns:
            List of key action names
        """
        colony_lower = colony_name.lower()
        service_info = COLONY_SERVICE_MAP.get(colony_lower, {})
        return service_info.get("key_actions", [])

    def inject_service_context(
        self,
        colony_name: str,
        action: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Inject service context into routing context.

        This method enriches the routing context with service-specific
        information for the target colony, enabling better-informed
        routing decisions.

        Args:
            colony_name: Target colony name
            action: Action being routed
            context: Current routing context

        Returns:
            Enhanced context with service information
        """
        # Create copy to avoid mutation
        enhanced_context = dict(context)

        # Add service context
        enhanced_context["service_context"] = self.get_service_context(colony_name)
        enhanced_context["primary_services"] = self.get_colony_services(colony_name)
        enhanced_context["available_actions"] = self.get_colony_actions(colony_name)

        # Mark that service context was injected
        enhanced_context["_service_context_injected"] = True

        logger.debug(
            f"Injected service context for {colony_name}: "
            f"services={enhanced_context['primary_services']}"
        )

        return enhanced_context

    async def should_prefer_service_colony(
        self,
        action: str,
        context: dict[str, Any],
    ) -> str | None:
        """Determine if a specific colony should be preferred based on semantic service affinity.

        Uses embedding-based semantic matching - NO keyword checks.

        Args:
            action: Action being routed
            context: Routing context

        Returns:
            Colony name if service affinity detected, None otherwise
        """
        try:
            from kagami.core.routing.semantic_matcher import get_semantic_matcher

            # Get semantic matcher
            matcher = await get_semantic_matcher()

            # Try to match service first
            service_match = await matcher.match_service(action)

            if service_match is None:
                return None

            # Map service to colony based on semantic similarity
            # Use semantic colony match with service context
            service_context_text = f"{action} for {service_match.label} service"
            colony_match = await matcher.match_colony(service_context_text, context)

            if colony_match.confidence > 0.6:
                logger.debug(
                    f"🔗 Service-colony mapping: {service_match.label} → {colony_match.label} "
                    f"(confidence={colony_match.confidence:.2f})"
                )
                return colony_match.label

            return None

        except Exception as e:
            logger.debug(f"Service colony preference failed: {e}")
            return None

    def _extract_task_type_sync(self, action: str) -> str:
        """Extract task type synchronously using simple keyword matching.

        This is a sync fallback for when async is not available.

        Args:
            action: Action to classify

        Returns:
            Task type string
        """
        action_lower = action.lower()

        # Simple/trivial actions (ping, health check, status, etc.)
        if any(
            w in action_lower for w in ["ping", "health", "status", "echo", "noop", "heartbeat"]
        ):
            return "simple"
        # Simple keyword-based fallback
        elif any(w in action_lower for w in ["create", "build", "implement", "write"]):
            return "build"
        elif any(w in action_lower for w in ["debug", "fix", "error", "broken"]):
            return "debug"
        elif any(w in action_lower for w in ["plan", "design", "architect"]):
            return "plan"
        elif any(w in action_lower for w in ["test", "verify", "check"]):
            return "verify"
        elif any(w in action_lower for w in ["research", "explore", "investigate"]):
            return "research"
        else:
            return "general"

    async def _extract_task_type(self, action: str) -> str:
        """Extract task type using semantic embedding matching - NO keywords.

        Args:
            action: Action to classify

        Returns:
            Task type string
        """
        try:
            from kagami.core.routing.semantic_matcher import get_semantic_matcher

            matcher = await get_semantic_matcher()
            task_match = await matcher.match_task_type(action)

            logger.debug(
                f"📊 Semantic task type: '{action}' → {task_match.label} "
                f"(confidence={task_match.confidence:.2f})"
            )

            return task_match.label

        except Exception as e:
            logger.warning(f"Semantic task type extraction failed: {e}, defaulting to 'general'")
            return "general"

    def _assess_ood_risk(self, action: str, context: dict[str, Any]) -> Any:
        """Assess out-of-distribution risk for routing decision.

        OOD DETECTION (Dec 27, 2025): Implements CLAUDE.md OOD awareness.
        High OOD risk → escalate to Grove for research.
        Medium OOD risk → add Crystal for verification.

        Args:
            action: Action being routed
            context: Routing context with memory hints

        Returns:
            OODRisk enum value
        """
        try:
            from kagami.core.safety.safety_zones import OODRisk, assess_ood_risk

            # Get pattern for this action
            task_type = self._extract_task_type_sync(action)
            pattern = self._stigmergy_learner.patterns.get((task_type, "general"))

            if pattern is None:
                # No pattern = high uncertainty
                confidence_hints = context.get("memory_confidence_hints", [])
                if confidence_hints:
                    avg_conf = sum(confidence_hints) / len(confidence_hints)
                else:
                    avg_conf = 0.2  # Low confidence for unknown patterns

                return assess_ood_risk(
                    bayesian_confidence=avg_conf,
                    pattern_age_hours=0.0,  # No pattern
                    execution_count=0,
                    semantic_similarity=None,
                )

            # Assess using pattern metadata
            return assess_ood_risk(
                bayesian_confidence=pattern.bayesian_confidence,
                pattern_age_hours=pattern.age_hours(),
                execution_count=pattern.success_count + pattern.failure_count,
                semantic_similarity=None,  # Could add semantic matching later
            )

        except Exception as e:
            logger.debug(f"OOD assessment skipped: {e}")
            # Default to low risk on error
            try:
                from kagami.core.safety.safety_zones import OODRisk

                return OODRisk.LOW
            except ImportError:
                return None

    def _infer_complexity(
        self,
        action: str,
        params: dict[str, Any],
        context: dict[str, Any],
    ) -> float:
        """Infer task complexity from action, params, and context.

        Enhanced complexity inference considers:
        1. Action patterns (simple → synthesis)
        2. Parameter complexity (count, depth, type)
        3. Context signals (query length, domain hints)
        4. Historical receipt patterns (stigmergy learning)
        5. Memory-based complexity hints (Dec 26, 2025)
        """
        # Check for explicit complexity
        if "complexity" in context:
            return float(context["complexity"])

        complexity_signals: list[float] = []

        # MEMORY INTEGRATION (Dec 26, 2025): Use complexity hints from past patterns
        if "memory_complexity_hints" in context:
            hints = context["memory_complexity_hints"]
            if hints:
                avg_hint = sum(hints) / len(hints)
                complexity_signals.append(avg_hint)
                logger.debug(
                    f"📚 Memory complexity hint: {avg_hint:.2f} from {len(hints)} patterns"
                )
        # === SEMANTIC ACTION ANALYSIS (using sync fallback) ===
        # Use keyword-based task type extraction to infer complexity
        try:
            task_type = self._extract_task_type_sync(action)

            # Map task types to complexity hints
            task_complexity_map = {
                "simple": 0.15,  # Simple actions (ping, health, status, echo, noop)
                "verify": 0.8,  # Testing/verification is complex
                "build": 0.7,  # Building requires multiple steps
                "integrate": 0.7,  # Integration is complex
                "plan": 0.75,  # Planning requires synthesis
                "research": 0.6,  # Research is moderately complex
                "debug": 0.5,  # Debugging is moderate
                "general": 0.5,  # Default
            }

            task_complexity = task_complexity_map.get(task_type, 0.5)
            complexity_signals.append(task_complexity)

            logger.debug(f"🧠 Task type complexity: {task_type} → {task_complexity:.2f}")

        except Exception as e:
            logger.debug(f"Task type complexity inference skipped: {e}")

        # === Parameter complexity analysis (structural, not keyword-based) ===
        param_count = len(params)
        if param_count == 0:
            complexity_signals.append(0.3)  # No params = simpler
        elif param_count <= 2:
            complexity_signals.append(0.35)
        elif param_count <= 5:
            complexity_signals.append(0.5)
        elif param_count <= 10:
            complexity_signals.append(0.65)
        else:
            complexity_signals.append(0.8)

        # Deep parameter analysis (nested structures indicate complexity)
        def _param_depth(obj: Any, depth: int = 0) -> int:
            if depth > 5:
                return depth
            if isinstance(obj, dict):
                if not obj:
                    return depth
                return max(_param_depth(v, depth + 1) for v in obj.values())
            if isinstance(obj, list) and obj:
                return max(_param_depth(v, depth + 1) for v in obj[:10])
            return depth

        max_depth = _param_depth(params)
        if max_depth >= 3:
            complexity_signals.append(0.55 + min(max_depth - 3, 3) * 0.1)

        # === Context signals ===
        # Query length (longer queries often indicate more complex needs)
        if "query" in context:
            query = str(context["query"])
            word_count = len(query.split())
            if word_count <= 5:
                complexity_signals.append(0.25)
            elif word_count <= 15:
                complexity_signals.append(0.45)
            elif word_count <= 30:
                complexity_signals.append(0.6)
            else:
                complexity_signals.append(0.75)

            # Multi-part questions use word count as proxy (no keyword checks)
            # Complexity scales with query length naturally above

        # Domain complexity uses embedding distance (no keywords)
        # Removed keyword-based domain checking

        # === Stigmergy learning: historical pattern complexity ===
        try:
            task_type = self._extract_task_type_sync(action)
            pattern = self._stigmergy_learner.get_pattern(task_type)  # type: ignore[attr-defined]
            if pattern and pattern.execution_count > 0:
                # If this task type historically required multiple colonies, increase complexity
                if hasattr(pattern, "metadata") and "avg_colonies_used" in pattern.metadata:
                    avg_colonies = pattern.metadata["avg_colonies_used"]
                    if avg_colonies >= 5:
                        complexity_signals.append(0.75)
                    elif avg_colonies >= 3:
                        complexity_signals.append(0.55)
        except Exception:
            pass  # Stigmergy lookup failed, continue without

        # === Aggregate signals ===
        if not complexity_signals:
            # No signals = unknown complexity, use conservative estimate based on action length
            return min(0.3 + len(action.split()) * 0.05, 0.7)

        # Weighted average with emphasis on higher signals (max-pooling influence)
        avg_complexity = sum(complexity_signals) / len(complexity_signals)
        max_complexity = max(complexity_signals)

        # Blend: 60% average, 40% max (ensures complex signals aren't diluted)
        final_complexity = 0.6 * avg_complexity + 0.4 * max_complexity

        logger.debug(
            f"📊 Complexity inference: action={action}, "
            f"signals={len(complexity_signals)}, avg={avg_complexity:.2f}, "
            f"max={max_complexity:.2f}, final={final_complexity:.2f}"
        )

        return min(1.0, max(0.0, final_complexity))

    def _get_best_colony(self, action: str, context: dict[str, Any]) -> int:
        """Get best colony for action using fast paths + caching.

        PERFORMANCE OPTIMIZATION (Dec 18, 2025):
        - Cache hit: O(1) lookup
        - World model hint: O(1) if confident
        - Keyword affinity: O(K) where K = number of keywords
        - Slow path: O(N) fallback chain (receipt learning, Nash, domain)

        Uses ColonyGameModel for game-theoretic colony selection.
        Falls back to keyword affinity only if Nash provides no clear winner.

        NEXUS BRIDGE (Dec 14, 2025): Dynamic utility lookup from receipt learning.
        WORLD MODEL BRIDGE (Dec 14, 2025): Respects world model predictions.
        """
        action_lower = action.lower()

        # FAST PATH 1: Cache lookup
        # Build cache key from action + relevant context fields
        context_items = frozenset(
            (k, str(v))
            for k, v in context.items()
            if k in {"wm_colony_hint", "domain", "complexity"}
        )
        cache_key = (action_lower, context_items)

        if cache_key in self._affinity_cache:
            cache_entry = self._affinity_cache[cache_key]

            # FIX (Dec 27, 2025): Check TTL validity before returning cached result
            # Handle both legacy (int) and new (tuple[Any, ...]) cache entries
            if isinstance(cache_entry, tuple):
                if self._is_cache_valid(cache_entry):
                    self._cache_hits += 1
                    # Move to end (LRU)
                    self._affinity_cache.pop(cache_key)
                    self._affinity_cache[cache_key] = cache_entry
                    return cache_entry[0]  # colony_idx
                else:
                    # Cache entry expired - remove and continue to slow path
                    self._affinity_cache.pop(cache_key)
                    self._cache_misses += 1
                    logger.debug(f"📦 Cache expired for '{cache_key[0]}'")
            else:
                # Legacy cache entry (just colony_idx) - treat as valid but log
                self._cache_hits += 1
                colony_idx = self._affinity_cache.pop(cache_key)
                self._affinity_cache[cache_key] = colony_idx
                return colony_idx

        self._cache_misses += 1

        # FAST PATH 2: MEMORY COLONY HINTS (Dec 26, 2025)
        # Use past patterns to suggest colony before world model
        memory_hints = context.get("memory_colony_hints", [])
        if memory_hints:
            # Count colony occurrences in past patterns
            from collections import Counter

            hint_counts = Counter(memory_hints)
            most_common = hint_counts.most_common(1)
            if most_common:
                colony_name, count = most_common[0]
                if count >= 2:  # At least 2 patterns agree
                    # Map colony name to index
                    colony_name_lower = (
                        colony_name.lower() if isinstance(colony_name, str) else str(colony_name)
                    )
                    for idx, name in enumerate(COLONY_NAMES):
                        if name.lower() == colony_name_lower:
                            logger.debug(f"📚 Memory colony hint: {name} (from {count} patterns)")
                            # Update cache with memory hint
                            self._affinity_cache[cache_key] = idx
                            if len(self._affinity_cache) > self._cache_size:
                                self._affinity_cache.popitem(last=False)
                            return idx

        # FAST PATH 3: WORLD MODEL HINT (confidence-weighted routing)
        # OPTIMIZED (Dec 27, 2025): Use confidence to modulate exploration
        # COHERENCY (Dec 27, 2025): Use s7_phase directly when available
        # High confidence → trust hint, Low confidence → fall through to exploration
        wm_hint = context.get("wm_colony_hint")
        if wm_hint and isinstance(wm_hint, dict):
            colony_idx_raw = wm_hint.get("colony_idx")
            confidence = wm_hint.get("confidence", 0)

            # COHERENCY (Dec 27, 2025): Check for direct s7_phase routing
            s7_phase = wm_hint.get("s7_phase")
            if s7_phase is not None:
                import torch

                if isinstance(s7_phase, torch.Tensor):
                    # Use argmax of s7_phase for routing (more direct than energy-based)
                    colony_idx_from_s7 = int(s7_phase.argmax().item())
                    s7_confidence = float(s7_phase.max().item())

                    # Override colony_idx if s7 is more confident
                    if s7_confidence > confidence:
                        colony_idx_raw = colony_idx_from_s7
                        confidence = s7_confidence
                        logger.debug(
                            f"🌍 Using s7_phase directly: {COLONY_NAMES[colony_idx_raw]} "
                            f"(s7_confidence={s7_confidence:.2f})"
                        )

            if colony_idx_raw is not None and isinstance(colony_idx_raw, int):
                # Accept world model prediction based on confidence threshold
                # High confidence (>0.7) → use hint directly
                # Medium confidence (0.4-0.7) → log but continue to explore
                # Low confidence (<0.4) → ignore hint
                if confidence > 0.7:
                    logger.debug(
                        f"🌍 World model hint accepted: {COLONY_NAMES[colony_idx_raw]} "
                        f"(confidence={confidence:.2f})"
                    )
                    self._cache_result(cache_key, colony_idx_raw, confidence)
                    return colony_idx_raw  # type: ignore[no-any-return]
                elif confidence > 0.4:
                    # Medium confidence: weight toward hint but allow override
                    logger.debug(
                        f"🌍 World model hint noted (medium confidence): "
                        f"{COLONY_NAMES[colony_idx_raw]} (confidence={confidence:.2f})"
                    )
                    # Store in context for slow path to consider
                    context["_wm_fallback_colony"] = colony_idx_raw
                # Low confidence: ignore and continue exploration

        # FAST PATH 4: Keyword-based colony affinity (sync)
        # Semantic matching requires async context - use sync fallback
        try:
            task_type = self._extract_task_type_sync(action_lower)

            # Map task types to likely colonies
            task_colony_map = {
                "build": 1,  # Forge
                "debug": 2,  # Flow
                "plan": 4,  # Beacon
                "research": 5,  # Grove
                "verify": 6,  # Crystal
                "general": 1,  # Default to Forge
            }

            if task_type in task_colony_map:
                colony_idx = task_colony_map[task_type]
                self._cache_result(cache_key, colony_idx, 0.6)  # Medium confidence
                return colony_idx
        except Exception as e:
            logger.debug(f"Task-based colony selection skipped: {e}")

        # SLOW PATH: Full fallback chain
        result = self._get_best_colony_slow(action_lower, context)
        self._cache_result(cache_key, result)
        return result

    def _cache_result(
        self,
        cache_key: tuple[str, frozenset],
        colony_idx: int,
        confidence: float = 0.5,
    ) -> None:
        """Store result in LRU cache with TTL metadata.

        FIX (Dec 27, 2025): Added confidence-based TTL.
        High confidence = longer TTL, low confidence = shorter TTL.

        Args:
            cache_key: Cache key tuple[Any, ...]
            colony_idx: Colony index to cache
            confidence: Bayesian confidence [0, 1] for TTL calculation
        """
        # Store with timestamp and confidence for TTL calculation
        # Format: (colony_idx, timestamp, confidence)
        self._affinity_cache[cache_key] = (colony_idx, time.time(), confidence)

        # Enforce LRU eviction
        if len(self._affinity_cache) > self._cache_size:
            # Remove oldest entry (first item)
            self._affinity_cache.popitem(last=False)

    def _get_cache_ttl(self, confidence: float) -> float:
        """Calculate cache TTL based on confidence.

        Higher confidence = longer TTL (more stable routing).
        Lower confidence = shorter TTL (more frequent re-evaluation).

        Args:
            confidence: Bayesian confidence [0, 1]

        Returns:
            TTL in seconds
        """
        # Base TTL: 1 hour
        base_ttl = 3600.0

        # Scale by confidence: 0.5-2.0x multiplier
        # confidence 0.0 → 0.5x (30 min)
        # confidence 0.5 → 1.0x (1 hour)
        # confidence 1.0 → 2.0x (2 hours)
        multiplier = 0.5 + 1.5 * confidence

        return base_ttl * multiplier

    def _is_cache_valid(self, cache_entry: tuple[Any, ...]) -> bool:
        """Check if cache entry is still valid based on TTL.

        Args:
            cache_entry: (colony_idx, timestamp, confidence) tuple[Any, ...]

        Returns:
            True if entry is still valid
        """
        if len(cache_entry) < 3:
            # Legacy cache entry without TTL metadata - treat as invalid
            return False

        _, timestamp, confidence = cache_entry
        ttl = self._get_cache_ttl(confidence)
        age = time.time() - timestamp

        return age < ttl  # type: ignore[no-any-return]

    def _get_best_colony_slow(self, action_lower: str, context: dict[str, Any]) -> int:
        """Slow path with full fallback chain.

        This method contains the original complex routing logic.
        Called only on cache miss + no fast path match.

        Args:
            action_lower: Lowercase action string
            context: Routing context

        Returns:
            Colony index (0-6)
        """
        # FRESHNESS DECAY (Dec 27, 2025): Apply periodic decay before using patterns
        # This ensures stale patterns don't dominate routing decisions
        if self._stigmergy_learner is not None:
            self._stigmergy_learner._maybe_apply_periodic_decay()

        # RECEIPT LEARNING dynamic utilities (Nexus integration)
        # Get learned utilities from stigmergy (updated by receipt learning)
        task_type = self._extract_task_type_sync(action_lower)
        if task_type != "general" and self._stigmergy_learner is not None:
            learned_utilities = self._get_learned_utilities(task_type)

            if learned_utilities:
                # Use learned utilities (higher = better)
                best_colony_idx = max(learned_utilities, key=learned_utilities.get)  # type: ignore[arg-type]
                best_colony_name = COLONY_NAMES[best_colony_idx]

                # Get confidence for cache TTL
                pattern = self._stigmergy_learner.patterns.get((task_type, "general"))
                confidence = pattern.bayesian_confidence if pattern else 0.5

                logger.debug(
                    f"📊 Receipt learning: {best_colony_name} "
                    f"(utility={learned_utilities[best_colony_idx]:.3f}, "
                    f"confidence={confidence:.2f}) for {task_type}"
                )
                return best_colony_idx

        # Fallback: Nash equilibrium (game-theoretic routing)
        if task_type == "general":
            # Keep deterministic default for unknown actions (matches unit tests).
            return 1
        nash_ranking = self._stigmergy_learner.select_colony_nash(task_type)
        if nash_ranking and len(nash_ranking) > 0:
            best_colony_name = nash_ranking[0][0]  # (name, utility) tuple[Any, ...]
            colony_name_to_idx = {
                "spark": 0,
                "forge": 1,
                "flow": 2,
                "nexus": 3,
                "beacon": 4,
                "grove": 5,
                "crystal": 6,
            }
            if best_colony_name in colony_name_to_idx:
                logger.debug(f"🎮 Nash equilibrium: {best_colony_name} for {task_type}")
                return colony_name_to_idx[best_colony_name]

        # Check context for domain hint - may produce multiple matches
        domain_matches = []
        if "domain" in context:
            domain = context["domain"].lower()
            for i, name in enumerate(COLONY_NAMES):
                if name in domain:
                    domain_matches.append(i)

        # EXPLICIT CONFLICT RESOLUTION (Dec 27, 2025)
        # Per CLAUDE.md: "Two colonies claim same task | Higher catastrophe index wins"
        if len(domain_matches) > 1:
            from .router_core import FanoActionRouter

            return FanoActionRouter.resolve_conflict_by_catastrophe_index(
                self,
                domain_matches,  # type: ignore[arg-type]
            )
        elif len(domain_matches) == 1:
            return domain_matches[0]

        # Default to Grove (research first for unknown tasks)
        # Per CLAUDE.md fallback routing: "No signal matches → Route to Grove"
        return 5

    def _get_learned_utilities(self, task_type: str) -> dict[int, float]:
        """Get learned utilities from receipt learning.

        NEXUS BRIDGE: Fetches colony utilities from stigmergy game model.

        Args:
            task_type: Task type for utility lookup

        Returns:
            Dict mapping colony_idx (0-6) → utility value
        """
        if self._stigmergy_learner is None or self._stigmergy_learner.game_model is None:
            return {}

        utilities = {}
        for colony_idx, colony_name in enumerate(COLONY_NAMES):
            colony_utility = self._stigmergy_learner.game_model.get_colony_utility(colony_name)
            if colony_utility is not None:
                # Use success_rate as utility (0.0 to 1.0, higher = better)
                utilities[colony_idx] = colony_utility.success_rate

        return utilities

    def evaluate_route_cost(
        self,
        colony_indices: list[int],
        action: str,
        params: dict[str, Any],
    ) -> float:
        """Evaluate cost for a routing decision BEFORE execution.

        COST MODULE INTEGRATION (Dec 27, 2025):
        Evaluates routing cost to guide colony selection. Lower cost = better.
        Uses cost module if available, otherwise estimates from colony load.

        Args:
            colony_indices: List of colony indices in proposed route
            action: Action being routed
            params: Action parameters

        Returns:
            Estimated cost (0-1, lower is better)
        """
        try:
            from kagami.cost.cost_evaluator import get_cost_evaluator

            evaluator = get_cost_evaluator()
            if evaluator is None:
                return 0.5  # Neutral cost if evaluator unavailable

            # Evaluate cost for each colony in route
            total_cost = 0.0
            for colony_idx in colony_indices:
                colony_name = COLONY_NAMES[colony_idx]

                # Get colony-specific cost estimate
                cost = evaluator.estimate_colony_cost(
                    colony_name=colony_name,
                    action=action,
                    params=params,
                )
                total_cost += cost

            # Average across colonies
            avg_cost = total_cost / max(len(colony_indices), 1)

            logger.debug(
                f"💰 Route cost estimate: {avg_cost:.3f} "
                f"(colonies={[COLONY_NAMES[i] for i in colony_indices]})"
            )

            return avg_cost

        except Exception as e:
            logger.debug(f"Cost evaluation skipped: {e}")
            return 0.5  # Neutral fallback

    def select_lowest_cost_route(
        self,
        candidate_colonies: list[int],
        action: str,
        params: dict[str, Any],
        top_k: int = 3,
    ) -> list[int]:
        """Select lowest-cost colonies from candidates.

        Args:
            candidate_colonies: All candidate colony indices
            action: Action being routed
            params: Action parameters
            top_k: Max colonies to select

        Returns:
            Selected colony indices (sorted by cost, lowest first)
        """
        if len(candidate_colonies) <= top_k:
            return candidate_colonies

        # Evaluate cost for each candidate
        costs = []
        for colony_idx in candidate_colonies:
            cost = self.evaluate_route_cost([colony_idx], action, params)
            costs.append((colony_idx, cost))

        # Sort by cost (lowest first)
        costs.sort(key=lambda x: x[1])

        # Return top_k lowest cost colonies
        return [colony_idx for colony_idx, _ in costs[:top_k]]

    def refresh_utilities(self) -> None:
        """Refresh router utilities from stigmergy learning.

        NEXUS BRIDGE: Called by receipt learning to signal utility updates.

        No-op for now (utilities fetched on-demand in _get_best_colony),
        but provides hook for future caching/precomputation.
        """
        if self._stigmergy_learner:
            logger.debug("🔄 Router utilities refreshed from stigmergy learning")

    def record_routing_outcome(
        self,
        routing_result: RoutingResult,
        success: bool,
    ) -> None:
        """Record routing outcome and check health metrics.

        Args:
            routing_result: The routing result that was executed
            success: Whether the routing succeeded

        Records routing to monitor and checks health every 100 routes.
        If unhealthy (Gini > 0.7 or dead colonies), logs warning and
        suggests exploration of underutilized colonies.
        """
        # Extract task type from action
        action = routing_result.metadata.get("action", "unknown")
        task_type = self._extract_task_type_sync(action)

        # Record routing for each colony in the result
        for colony_action in routing_result.actions:
            self.routing_monitor.record_routing(
                colony_idx=colony_action.colony_idx,
                task_type=task_type,
                success=success,
                complexity=routing_result.complexity,
            )

        # Increment route count
        self._route_count += 1

        # Check health every 100 routes
        if self._route_count % 100 == 0:
            metrics = self.routing_monitor.get_metrics()

            if not metrics.is_healthy:
                logger.warning(
                    f"⚠️ ROUTING HEALTH WARNING: "
                    f"Gini={metrics.gini_coefficient:.2f}, "
                    f"dead_colonies={len(metrics.dead_colonies)}, "
                    f"routes={metrics.total_routes}"
                )

                # Suggest exploration
                suggested_colony = self.routing_monitor.suggest_exploration()
                if suggested_colony is not None:
                    from kagami.core.unified_agents.colony_routing_monitor import COLONY_NAMES

                    logger.info(
                        f"💡 SUGGESTION: Explore underutilized colony '{COLONY_NAMES[suggested_colony]}'"
                    )
            else:
                logger.debug(
                    f"✅ ROUTING HEALTH: "
                    f"Gini={metrics.gini_coefficient:.2f}, "
                    f"healthy, routes={metrics.total_routes}"
                )


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "RouterScoringMixin",
]
