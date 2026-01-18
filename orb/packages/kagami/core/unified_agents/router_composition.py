# pyright: reportGeneralTypeIssues=false
"""Fano Action Router - Action Composition and Multi-Colony Coordination.

This module contains action composition logic, Fano line generation,
multi-colony coordination, consensus-aware routing, and inhibition mechanisms.

Split from fano_action_router.py (December 28, 2025)
"""

from __future__ import annotations

import logging
import time
from typing import Any

from .router_core import (
    COLONY_NAMES,
    FANO_LINES_0IDX,
    ActionMode,
    ColonyAction,
    RoutingResult,
    _lazy_import_torch,
)

logger = logging.getLogger(__name__)


# =============================================================================
# COMPOSITION METHODS (Extension of FanoActionRouter)
# =============================================================================


class RouterCompositionMixin:
    """Mixin class providing composition and multi-colony coordination for FanoActionRouter.

    This mixin contains all the methods related to:
    - Main route() orchestration with OOD detection and safety enforcement
    - Fano line selection and neighbor scoring
    - Single/Fano/All-colonies routing modes
    - Brain-inspired inhibitory competition
    - Consensus-aware routing
    """

    def route(
        self,
        action: str,
        params: dict[str, Any],
        complexity: float | None = None,
        context: dict[str, Any] | None = None,
    ) -> RoutingResult:
        """Route action to appropriate colony(ies).

        Args:
            action: Action name (e.g., "research.web", "build.feature")
            params: Action parameters
            complexity: Explicit complexity (0-1), or None to infer
            context: Additional routing context

        Returns:
            RoutingResult with actions for colonies
        """
        context = context or {}

        # MEMORY INTEGRATION (Dec 27, 2025 - FIXED): Use sync stigmergy patterns
        # Previous implementation had async issues - now uses StigmergyLearner directly
        if "memory_patterns" not in context:
            try:
                # Use stigmergy patterns (sync-safe) instead of MemoryHub (async)
                task_type = self._extract_task_type_sync(action)
                patterns = self._stigmergy_learner.get_patterns(intent_type=task_type, limit=5)

                if patterns:
                    context["memory_patterns"] = patterns
                    # Extract colony hints and complexity from past patterns
                    for pattern in patterns:
                        # Stigmergy patterns have workspace_hash as colony domain
                        domain = pattern.get("workspace_hash") or pattern.get("actor", "")
                        if domain:
                            context.setdefault("memory_colony_hints", []).append(domain)

                        # Extract Bayesian confidence for OOD detection
                        bayesian_conf = pattern.get("bayesian_confidence", 0.5)
                        context.setdefault("memory_confidence_hints", []).append(bayesian_conf)

                        # Use success rate as complexity hint (inverse)
                        success_rate = pattern.get("bayesian_success_rate", 0.5)
                        # Low success = high complexity
                        complexity_hint = 1.0 - success_rate
                        context.setdefault("memory_complexity_hints", []).append(complexity_hint)

                    logger.debug(f"📚 Stigmergy recall: {len(patterns)} patterns for '{action}'")
            except Exception as e:
                logger.debug(f"Stigmergy recall skipped: {e}")

        # OOD DETECTION (Dec 27, 2025): Assess out-of-distribution risk
        ood_risk = self._assess_ood_risk(action, context)

        inferred = False
        # Infer complexity if not provided
        if complexity is None:
            complexity = self._infer_complexity(action, params, context)
            inferred = True
        else:
            # Clamp explicit complexity to valid range [0, 1]
            complexity = max(0.0, min(1.0, complexity))

        # LLM-DRIVEN MODE DETERMINATION (Jan 5, 2026)
        # Check if LLM routing decision is available in context (pre-computed)
        llm_decision = context.get("llm_routing_decision")
        if llm_decision:
            mode = llm_decision.get("mode", ActionMode.SINGLE)
            complexity = llm_decision.get("complexity", complexity)
            logger.info(
                f"🧠 Using LLM routing decision: {action} → {mode.value} "
                f"(complexity={complexity:.2f})"
            )
        else:
            # COMPLEXITY-BASED MODE (emergency fallback when LLM unavailable)
            # This is NOT a heuristic - it's a safe default when LLM can't be reached
            # The LLM should be called BEFORE route() to populate context["llm_routing_decision"]
            if complexity < 0.3:
                mode = ActionMode.SINGLE
            elif complexity < 0.7:
                mode = ActionMode.FANO_LINE
            else:
                mode = ActionMode.ALL_COLONIES

            logger.debug(
                f"⚙️ Using complexity-based mode (LLM unavailable): {action} → {mode.value} "
                f"(complexity={complexity:.2f})"
            )

        # OOD ESCALATION (Dec 27, 2025): Override routing for high OOD risk
        # From CLAUDE.md: "No signal matches → Route to Grove"
        # UPDATED (Jan 4, 2026): Trust world model hints with high confidence
        # to override OOD escalation - learned priors beat heuristics

        try:
            from kagami.core.safety.safety_zones import OODRisk

            if ood_risk == OODRisk.HIGH:
                # Check for high-confidence world model hint that overrides OOD
                wm_hint = context.get("wm_colony_hint")
                hint_confidence = 0.0
                if wm_hint and isinstance(wm_hint, dict):
                    hint_confidence = wm_hint.get("confidence", 0.0)

                # Trust world model hint if confidence >= 0.8 (learned prior)
                if hint_confidence >= 0.8:
                    logger.info(
                        f"🧠 World model hint accepted for '{action}' "
                        f"(confidence={hint_confidence:.2f} overrides OOD escalation)"
                    )
                    # Don't escalate to Grove - let hint-based routing handle it
                else:
                    # High OOD risk without confident hint: Force escalation to Grove
                    logger.warning(
                        f"🔬 OOD ESCALATION: High uncertainty for '{action}', routing to Grove"
                    )
                    mode = ActionMode.SINGLE
                    context["ood_escalation"] = "grove"
                    context["original_mode"] = mode.value
        except Exception:
            pass  # OOD module not available

        # Generate actions based on mode
        if mode == ActionMode.SINGLE:
            actions = self._route_single(action, params, context)
            fano_line = None
        elif mode == ActionMode.FANO_LINE:
            actions, fano_line = self._route_fano_line(action, params, context)
        else:
            actions = self._route_all_colonies(action, params, context)
            fano_line = None

        # SAFETY ENFORCEMENT: Ensure Crystal verification for safety-critical operations
        crystal_idx = 6  # Crystal is colony index 6
        is_safety_critical = self._is_safety_critical(action, params)
        crystal_included = any(a.colony_idx == crystal_idx for a in actions)

        # OOD VERIFICATION (Dec 27, 2025): Add Crystal for medium OOD risk
        # From CLAUDE.md: Medium OOD risk should be verified before proceeding
        ood_requires_crystal = False
        try:
            from kagami.core.safety.safety_zones import OODRisk

            if ood_risk == OODRisk.MEDIUM and not crystal_included:
                ood_requires_crystal = True
                logger.info(f"🔍 OOD VERIFICATION: Adding Crystal for medium-risk action: {action}")
        except Exception:
            pass

        if (is_safety_critical or ood_requires_crystal) and not crystal_included:
            # Force Crystal inclusion for safety-critical operations
            logger.warning(
                f"🔒 SAFETY: Enforcing Crystal verification for safety-critical action: {action}"
            )

            # Add Crystal to actions WITHOUT changing mode
            # Safety enforcement adds verification but doesn't change routing complexity
            if mode == ActionMode.SINGLE:
                # Append Crystal directly to single-colony action
                actions.append(
                    ColonyAction(
                        colony_idx=crystal_idx,
                        colony_name="crystal",
                        action=action,
                        params=params,
                        weight=0.3,
                        is_primary=False,
                        fano_role="safety_enforced",
                    )
                )
            elif mode == ActionMode.FANO_LINE:
                # Append Crystal to existing Fano line
                actions.append(
                    ColonyAction(
                        colony_idx=crystal_idx,
                        colony_name="crystal",
                        action=action,
                        params=params,
                        weight=0.2,
                        is_primary=False,
                        fano_role="safety_enforced",
                    )
                )
            # If mode is ALL_COLONIES, Crystal is already included

            inferred = True  # Mark as modified

        # Re-check Crystal inclusion after enforcement
        crystal_included_final = any(a.colony_idx == crystal_idx for a in actions)

        metadata = {
            "action": action,
            "inferred_complexity": inferred,
            "is_safety_critical": is_safety_critical,
        }
        if is_safety_critical:
            if crystal_included_final:
                metadata["crystal_enforced"] = True
            else:
                # This should not happen after enforcement, but log for debugging
                logger.error(f"❌ SAFETY VIOLATION: Failed to enforce Crystal for action: {action}")

        routing_result = RoutingResult(
            mode=mode,
            actions=actions,
            complexity=complexity,
            fano_line=fano_line,
            # FIXED Dec 24, 2025: Confidence should be HIGH at edges (clear simple/synthesis)
            # and LOW in middle (uncertain). Old formula was inverted.
            # Edge (0 or 1): confidence = 1.0, Middle (0.5): confidence = 0.5
            confidence=0.5 + abs(complexity - 0.5),
            metadata=metadata,
        )

        try:
            from kagami.core.safety.fano_cbf_composition import check_fano_routing_safety

            # Get colony states from context if available
            colony_states = context.get("colony_states")
            shared_resources = context.get("shared_resources")

            if colony_states is not None:
                is_safe, safety_info = check_fano_routing_safety(
                    routing_result=routing_result,
                    colony_states=colony_states,
                    shared_resources=shared_resources,
                )

                # Add safety info to metadata
                routing_result.metadata["cbf_safe"] = is_safe
                routing_result.metadata["cbf_info"] = safety_info

                if not is_safe:
                    logger.warning(
                        f"⚠️  Fano routing safety violation for {action}: "
                        f"mode={mode}, safety_info={safety_info}. "
                        f"Falling back to SINGLE mode (fail-safe)."
                    )
                    # SAFETY INVARIANT: Fall back to single colony mode
                    # Multi-colony coordination with safety violations is not allowed
                    # Use first colony from original routing, or Forge (1) as default
                    primary_colony = (
                        routing_result.actions[0].colony_idx if routing_result.actions else 1
                    )
                    routing_result = RoutingResult(
                        mode=ActionMode.SINGLE,
                        actions=[
                            ColonyAction(
                                colony_idx=primary_colony,
                                colony_name=COLONY_NAMES[primary_colony],
                                action=action,
                                params=params,
                                weight=1.0,
                                is_primary=True,
                                fano_role=None,
                            )
                        ],
                        complexity=routing_result.complexity,
                        fano_line=None,
                        confidence=0.5,
                        metadata={
                            "fallback_reason": "fano_safety_violation",
                            "original_mode": mode.name,
                            "cbf_info": safety_info,
                        },
                    )
        except Exception as e:
            logger.debug(f"CBF routing safety check skipped: {e}")

        # BRAIN-INSPIRED INHIBITION (Dec 26, 2025)
        # Apply inhibitory competition to modulate colony weights (MANDATORY)
        routing_result = self._apply_inhibition(routing_result, context)

        return routing_result

    def _apply_inhibition(
        self,
        routing_result: RoutingResult,
        context: dict[str, Any],
    ) -> RoutingResult:
        """Apply brain-inspired inhibitory competition to colony weights.

        BRAIN SCIENCE (Dec 26, 2025):
        - Fast (PV) inhibition: Winner-take-all for ambiguous tasks
        - Slow (SST) inhibition: Context-dependent suppression
        - Disinhibition (VIP): Meta-control from higher levels

        Args:
            routing_result: Original routing result
            context: Routing context

        Returns:
            Modified routing result with inhibition-adjusted weights
        """
        if not routing_result.actions:
            return routing_result

        torch = _lazy_import_torch()

        # Build activation tensor from action weights
        activations = torch.zeros(7)
        for action in routing_result.actions:
            activations[action.colony_idx] = action.weight

        # Get meta signal from context (if available from neuromodulation)
        meta_signal = None
        if "neuromodulator_state" in context:
            neuromod = context["neuromodulator_state"]
            if hasattr(neuromod, "norepinephrine"):
                meta_signal = neuromod.norepinephrine.expand(7)

        # Apply inhibitory gate (ALWAYS runs - no bypass)
        # Gate is either full PV/SST/VIP or identity gate with strength=0
        inhibited, inhibition_state = self._inhibitory_gate(
            activations.unsqueeze(0),
            meta_signal=meta_signal.unsqueeze(0) if meta_signal is not None else None,
        )
        inhibited = inhibited.squeeze(0)

        # Update action weights based on inhibition
        modified_actions = []
        for action in routing_result.actions:
            new_weight = inhibited[action.colony_idx].item()
            if new_weight > 0.01:  # Keep if not fully suppressed
                modified_actions.append(
                    ColonyAction(
                        colony_idx=action.colony_idx,
                        colony_name=action.colony_name,
                        action=action.action,
                        params=action.params,
                        weight=new_weight,
                        is_primary=action.is_primary,
                        fano_role=action.fano_role,
                    )
                )

        # Ensure at least one action survives (use winner from inhibition)
        if not modified_actions:
            winner_idx = (
                inhibition_state.winner_idx if inhibition_state.winner_idx is not None else 0
            )
            modified_actions = [
                ColonyAction(
                    colony_idx=winner_idx,
                    colony_name=COLONY_NAMES[winner_idx],
                    action=routing_result.actions[0].action
                    if routing_result.actions
                    else "unknown",
                    params=routing_result.actions[0].params if routing_result.actions else {},
                    weight=1.0,
                    is_primary=True,
                    fano_role="inhibition_winner",
                )
            ]

        # Renormalize weights to sum to 1.0 after inhibition
        total_weight = sum(a.weight for a in modified_actions)
        if total_weight > 0:
            for action in modified_actions:
                action.weight /= total_weight

        # Add inhibition info to metadata
        metadata = routing_result.metadata.copy()
        metadata["inhibition_applied"] = True
        metadata["inhibition_mean"] = inhibition_state.mean_inhibition
        if inhibition_state.winner_idx is not None:
            metadata["inhibition_winner"] = COLONY_NAMES[inhibition_state.winner_idx]

        return RoutingResult(
            mode=routing_result.mode,
            actions=modified_actions,
            complexity=routing_result.complexity,
            fano_line=routing_result.fano_line,
            confidence=routing_result.confidence,
            metadata=metadata,
        )

    def _select_best_fano_neighbor(
        self,
        primary_idx: int,
        neighbors: list[tuple[int, int]],
        action: str,
        context: dict[str, Any],
    ) -> tuple[int, int]:
        """Select best Fano neighbor pair based on action affinity.

        Uses domain affinity scoring to pick the neighbor composition
        that best complements the primary colony for the given action.

        Colony composition affinities:
        - Creative tasks benefit from: Spark × Forge = Flow (iteration)
        - Research tasks benefit from: Grove × Crystal = Beacon (verified plans)
        - Integration tasks benefit from: Nexus × Flow = Crystal (verified integration)

        Returns:
            (partner_idx, result_idx) tuple[Any, ...]
        """
        if not neighbors:
            # FIX (Dec 27, 2025): Score ALL Fano lines, not just first match
            # Use Fano plane structure: find BEST neighbor pair for primary colony
            # Each colony has exactly 3 Fano lines it participates in
            candidate_neighbors = []
            for line in FANO_LINES_0IDX:
                if primary_idx in line:
                    # Get the other two colonies as (partner, result)
                    other_colonies = [c for c in line if c != primary_idx]
                    if len(other_colonies) >= 2:
                        candidate_neighbors.append((other_colonies[0], other_colonies[1]))

            if not candidate_neighbors:
                # If no Fano line found, use default: Forge (1) × Flow (2)
                logger.warning(f"No Fano lines found for colony {primary_idx}, using default")
                return (1, 2)

            # Score all candidates and pick best (recursive call with candidates)
            neighbors = candidate_neighbors

        action_lower = action.lower()
        best_score = -1.0
        best_neighbor = neighbors[0]

        # Score each neighbor pair based on action affinity
        for partner_idx, result_idx in neighbors:
            score = 0.0
            partner_name = COLONY_NAMES[partner_idx]
            result_name = COLONY_NAMES[result_idx]

            # Affinity scoring using semantic similarity (NO keywords)
            try:
                import asyncio

                from kagami.core.routing.semantic_matcher import get_semantic_matcher

                matcher = asyncio.run(get_semantic_matcher())

                # Get semantic embeddings
                action_embedding = matcher.encode(action)
                partner_desc = f"{partner_name} colony"
                partner_embedding = matcher.encode(partner_desc)

                # Compute semantic affinity
                affinity = matcher.compute_similarity(action_embedding, partner_embedding)

                # Weight affinity into score
                score += affinity * 1.0  # Full weight for semantic match

                logger.debug(f"🔗 Semantic affinity: {action} × {partner_name} = {affinity:.2f}")

            except Exception as e:
                logger.debug(f"Semantic affinity scoring skipped: {e}")

            # Integration actions benefit from all - use result colony quality
            if any(k in action_lower for k in ["integrate", "connect", "merge"]):
                if result_name == "crystal":
                    score += 0.8  # Integration verified
                elif result_name == "beacon":
                    score += 0.7  # Integration planned

            # Bonus if context hints at specific domains
            if "domain" in context:
                domain = context["domain"].lower()
                if partner_name in domain or result_name in domain:
                    score += 0.5

            # GÖDEL AGENT: Boost from Nash equilibrium if available
            task_type = self._extract_task_type_sync(action_lower)
            nash_ranking = self._stigmergy_learner.select_colony_nash(task_type)
            if nash_ranking:
                ranking_names = [r[0] for r in nash_ranking]
                if partner_name in ranking_names[:3]:
                    score += 0.3 * (3 - ranking_names.index(partner_name)) / 3

            if score > best_score:
                best_score = score
                best_neighbor = (partner_idx, result_idx)

        logger.debug(
            f"🔀 Fano selection: primary={COLONY_NAMES[primary_idx]}, "
            f"partner={COLONY_NAMES[best_neighbor[0]]}, "
            f"result={COLONY_NAMES[best_neighbor[1]]}, score={best_score:.2f}"
        )

        return best_neighbor

    def _route_single(
        self,
        action: str,
        params: dict[str, Any],
        context: dict[str, Any],
    ) -> list[ColonyAction]:
        """Route to single best colony.

        OOD ESCALATION (Dec 27, 2025): If OOD escalation is set[Any], route to Grove.
        """
        # Check for OOD escalation override
        if context.get("ood_escalation") == "grove":
            colony_idx = 5  # Grove
            logger.debug("🔬 OOD override: routing to Grove instead of best colony")
        else:
            colony_idx = self._get_best_colony(action, context)

        return [
            ColonyAction(
                colony_idx=colony_idx,
                colony_name=COLONY_NAMES[colony_idx],
                action=action,
                params=params,
                weight=1.0,
                is_primary=True,
            )
        ]

    def _route_fano_line(
        self,
        action: str,
        params: dict[str, Any],
        context: dict[str, Any],
    ) -> tuple[list[ColonyAction], tuple[int, int, int]]:
        """Route using Fano line composition (3 colonies)."""
        # Get primary colony
        primary_idx = self._get_best_colony(action, context)

        # Get Fano neighbors
        neighbors = self._fano_neighbors[primary_idx]
        if not neighbors:
            # Fallback to single
            return self._route_single(action, params, context), None  # type: ignore[return-value]

        # Pick best neighbor pair based on action affinity
        partner_idx, result_idx = self._select_best_fano_neighbor(
            primary_idx, neighbors, action, context
        )

        fano_line = (primary_idx, partner_idx, result_idx)

        # Validate the constructed Fano line
        if not self._validate_fano_line(fano_line):
            logger.warning(
                f"⚠️  Invalid Fano line composition: {fano_line}. "
                f"Colonies {[COLONY_NAMES[i] for i in fano_line]} do not form a valid Fano line. "
                f"Falling back to single colony."
            )
            return self._route_single(action, params, context), None  # type: ignore[return-value]

        actions = [
            ColonyAction(
                colony_idx=primary_idx,
                colony_name=COLONY_NAMES[primary_idx],
                action=action,
                params=params,
                weight=0.5,
                is_primary=True,
                fano_role="source",
            ),
            ColonyAction(
                colony_idx=partner_idx,
                colony_name=COLONY_NAMES[partner_idx],
                action=action,
                params=params,
                weight=0.3,
                is_primary=False,
                fano_role="partner",
            ),
            ColonyAction(
                colony_idx=result_idx,
                colony_name=COLONY_NAMES[result_idx],
                action=action,
                params=params,
                weight=0.2,
                is_primary=False,
                fano_role="result",
            ),
        ]

        return actions, fano_line

    def _route_all_colonies(
        self,
        action: str,
        params: dict[str, Any],
        context: dict[str, Any],
    ) -> list[ColonyAction]:
        """Route to all 7 colonies for synthesis.

        Returns actions with PRIMARY colony FIRST, then others in index order.
        Dec 21, 2025 FIX: Previously returned in index order (0-6) regardless of primary.
        """
        # Primary colony gets higher weight
        primary_idx = self._get_best_colony(action, context)

        actions = []
        for i, name in enumerate(COLONY_NAMES):
            is_primary = i == primary_idx
            weight = 0.3 if is_primary else 0.1  # Primary: 30%, others: 10% each

            actions.append(
                ColonyAction(
                    colony_idx=i,
                    colony_name=name,
                    action=action,
                    params=params,
                    weight=weight,
                    is_primary=is_primary,
                )
            )

        # Normalize weights
        total_weight = sum(a.weight for a in actions)
        for a in actions:
            a.weight /= total_weight

        # Sort so primary colony comes first (Dec 21, 2025 FIX)
        actions.sort(key=lambda a: (not a.is_primary, a.colony_idx))

        return actions


# =============================================================================
# CONSENSUS-AWARE FANO ROUTER
# =============================================================================


class ConsensusAwareFanoRouter:
    """Fano router that respects consensus state.

    ARCHITECTURE:
    =============
    1. Initial routing proposal from FanoActionRouter (fast heuristic)
    2. Collect colony proposals via KagamiConsensus (if enabled)
    3. Run Byzantine quorum (5/7 threshold)
    4. Return consensus routing (overrides initial if different)

    FALLBACK MODE:
    ==============
    - If consensus fails or times out → use initial FanoActionRouter routing
    - If enable_consensus=False → bypass consensus (testing/fallback mode)

    METRICS:
    ========
    - consensus_routing_overrides_total: Consensus differs from initial
    - consensus_routing_fallbacks_total: Consensus fails
    - consensus_routing_latency_seconds: Added latency from consensus

    Created: December 15, 2025
    """

    def __init__(
        self,
        fano_router: Any,  # FanoActionRouter with mixins
        consensus: Any | None = None,  # KagamiConsensus
        enable_consensus: bool = True,
        consensus_timeout: float = 2.0,  # seconds
    ):
        """Initialize consensus-aware router.

        Args:
            fano_router: Base FanoActionRouter for initial proposals
            consensus: KagamiConsensus instance (or None to create default)
            enable_consensus: Enable consensus validation (False = testing mode)
            consensus_timeout: Timeout for consensus (seconds)
        """
        self.fano_router = fano_router
        self.enable_consensus = enable_consensus
        self.consensus_timeout = consensus_timeout

        # Lazy import to avoid circular dependency
        if consensus is None and enable_consensus:
            from kagami.core.coordination.kagami_consensus import create_consensus_protocol

            self.consensus = create_consensus_protocol()
        else:
            self.consensus = consensus  # type: ignore[assignment]

        # Initialize metrics
        self._init_metrics()

        logger.info(
            f"✅ ConsensusAwareFanoRouter initialized: "
            f"consensus={'ENABLED' if enable_consensus else 'DISABLED'}, "
            f"timeout={consensus_timeout}s"
        )

    def _init_metrics(self) -> None:
        """Initialize Prometheus metrics."""
        try:
            from kagami_observability.metrics.core import Counter, Histogram

            self.metrics_overrides = Counter(
                "kagami_consensus_routing_overrides_total",
                "Consensus routing differs from initial FanoActionRouter proposal",
                ["mode"],  # single/fano/all
            )

            self.metrics_fallbacks = Counter(
                "kagami_consensus_routing_fallbacks_total",
                "Consensus routing failed, fell back to initial proposal",
                ["reason"],  # timeout/convergence_failure/error
            )

            self.metrics_latency = Histogram(
                "kagami_consensus_routing_latency_seconds",
                "Added latency from consensus computation",
                buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0),
            )

            logger.info("Consensus routing metrics initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize consensus routing metrics: {e}")
            # Metrics unavailable - set[Any] to None (graceful degradation)
            self.metrics_overrides = None
            self.metrics_fallbacks = None
            self.metrics_latency = None

    async def route_with_consensus(
        self,
        action: str,
        params: dict[str, Any],
        complexity: float | None = None,
        context: dict[str, Any] | None = None,
    ) -> RoutingResult:
        """Route action with consensus validation.

        WORKFLOW:
        1. Initial routing from FanoActionRouter (fast)
        2. If consensus enabled: collect colony proposals
        3. Run Byzantine consensus (5/7 quorum)
        4. Compare consensus vs initial
        5. Return consensus if different, else initial

        Args:
            action: Action name
            params: Action parameters
            complexity: Explicit complexity (or None to infer)
            context: Additional routing context

        Returns:
            RoutingResult with consensus-validated routing
        """
        import asyncio

        context = context or {}
        start_time = time.time()

        # PART 1: Initial routing (fast heuristic)
        initial_routing = self.fano_router.route(
            action=action,
            params=params,
            complexity=complexity,
            context=context,
        )

        # If consensus disabled, return initial routing immediately
        if not self.enable_consensus or self.consensus is None:
            return initial_routing

        # PART 2: Consensus validation
        try:
            # Collect proposals from all colonies (parallel)
            consensus_task = asyncio.create_task(
                self.consensus.collect_proposals(
                    task_description=action,
                    context=context,
                )
            )

            # Wait for proposals with timeout
            proposals = await asyncio.wait_for(
                consensus_task,
                timeout=self.consensus_timeout,
            )

            # Run Byzantine consensus
            consensus_state = await self.consensus.byzantine_consensus(proposals)

            # Record latency
            latency = time.time() - start_time
            if self.metrics_latency:
                self.metrics_latency.observe(latency)

            # PART 3: Validate and compare
            if not consensus_state.converged:
                # Consensus failed to converge
                logger.warning(
                    f"Consensus failed to converge for action={action}, "
                    f"falling back to initial routing"
                )
                if self.metrics_fallbacks:
                    self.metrics_fallbacks.labels(reason="convergence_failure").inc()
                return initial_routing

            if consensus_state.consensus_routing is None:
                # No valid routing from consensus
                logger.warning(
                    f"Consensus produced no valid routing for action={action}, "
                    f"falling back to initial routing"
                )
                if self.metrics_fallbacks:
                    self.metrics_fallbacks.labels(reason="no_valid_routing").inc()
                return initial_routing

            # PART 4: Check if consensus differs from initial
            consensus_routing = self._consensus_to_routing_result(
                consensus_state=consensus_state,
                initial_routing=initial_routing,
                action=action,
                params=params,
            )

            if self._routing_differs(initial_routing, consensus_routing):
                logger.info(
                    f"Consensus override: initial={initial_routing.mode.value}, "
                    f"consensus={consensus_routing.mode.value}, "
                    f"colonies_initial={[a.colony_name for a in initial_routing.actions]}, "
                    f"colonies_consensus={[a.colony_name for a in consensus_routing.actions]}"
                )
                if self.metrics_overrides:
                    self.metrics_overrides.labels(mode=initial_routing.mode.value).inc()
                return consensus_routing
            else:
                # Consensus agrees with initial
                logger.debug(f"Consensus agrees with initial routing for action={action}")
                return initial_routing

        except TimeoutError:
            logger.warning(f"Consensus timeout ({self.consensus_timeout}s) for action={action}")
            if self.metrics_fallbacks:
                self.metrics_fallbacks.labels(reason="timeout").inc()
            return initial_routing

        except Exception as e:
            logger.error(f"Consensus error for action={action}: {e}", exc_info=True)
            if self.metrics_fallbacks:
                self.metrics_fallbacks.labels(reason="error").inc()
            return initial_routing

    def _consensus_to_routing_result(
        self,
        consensus_state: Any,  # ConsensusState
        initial_routing: RoutingResult,
        action: str,
        params: dict[str, Any],
    ) -> RoutingResult:
        """Convert consensus state to RoutingResult.

        Args:
            consensus_state: ConsensusState from Byzantine consensus
            initial_routing: Initial routing for reference
            action: Action name
            params: Action parameters

        Returns:
            RoutingResult from consensus
        """

        # Extract activated colonies from consensus
        activated_colonies = [
            colony_id
            for colony_id, task in consensus_state.consensus_routing.items()
            if task == "activate"
        ]

        if not activated_colonies:
            # Fallback to initial if no colonies activated
            return initial_routing

        # Determine mode based on colony count
        n_colonies = len(activated_colonies)
        if n_colonies == 1:
            mode = ActionMode.SINGLE
            fano_line = None
        elif n_colonies == 3:
            mode = ActionMode.FANO_LINE
            # Extract Fano line (if valid)
            colony_indices = [c.value for c in activated_colonies]
            if self._validate_fano_line(tuple(colony_indices)):
                fano_line = tuple(colony_indices)
            else:
                fano_line = None
        else:
            mode = ActionMode.ALL_COLONIES
            fano_line = None

        # Build ColonyAction list[Any]
        actions = []
        for colony_id in activated_colonies:
            colony_idx = colony_id.value
            actions.append(
                ColonyAction(
                    colony_idx=colony_idx,
                    colony_name=COLONY_NAMES[colony_idx],
                    action=action,
                    params=params,
                    weight=1.0 / n_colonies,  # Equal weight
                    is_primary=(colony_idx == activated_colonies[0].value),
                    fano_role="consensus",
                )
            )

        return RoutingResult(
            mode=mode,
            actions=actions,
            complexity=initial_routing.complexity,  # Preserve inferred complexity
            fano_line=fano_line,
            confidence=float(consensus_state.agreement_matrix.mean()),
            metadata={
                "action": action,
                "consensus_iterations": consensus_state.iterations,
                "cbf_constraint": consensus_state.cbf_constraint,
                "source": "consensus",
            },
        )

    def _routing_differs(
        self,
        r1: RoutingResult,
        r2: RoutingResult,
    ) -> bool:
        """Check if two routing results differ significantly.

        Args:
            r1: First routing result
            r2: Second routing result

        Returns:
            True if routings differ (different colonies or mode)
        """
        # Check mode
        if r1.mode != r2.mode:
            return True

        # Check activated colonies
        colonies1 = {a.colony_idx for a in r1.actions}
        colonies2 = {a.colony_idx for a in r2.actions}

        return colonies1 != colonies2

    def _validate_fano_line(self, line: tuple[int, int, int]) -> bool:
        """Validate that a line is in the canonical Fano set[Any]."""
        return self.fano_router._validate_fano_line(line)

    def complete_fano_line(self, active_colonies: set[int]) -> set[int]:
        """If two colonies on a Fano line are active, add the third.

        FANO LINE COMPLETION (January 5, 2026):
        ======================================
        This implements compositional enforcement: if two colonies from
        a Fano line are already engaged, the third should join automatically.

        The 7 Fano lines encode valid catastrophe compositions:
            Line 1: (0, 1, 2) → Spark × Forge = Flow
            Line 2: (0, 3, 4) → Spark × Nexus = Beacon
            Line 3: (0, 5, 6) → Spark × Grove = Crystal
            Line 4: (1, 3, 5) → Forge × Nexus = Grove
            Line 5: (1, 4, 6) → Forge × Beacon = Crystal
            Line 6: (2, 3, 6) → Flow × Nexus = Crystal
            Line 7: (2, 4, 5) → Flow × Beacon = Grove

        Args:
            active_colonies: Set of currently active colony indices (0-6)

        Returns:
            Completed set with third colony added if two from a line exist
        """
        completed = set(active_colonies)

        for line in FANO_LINES_0IDX:
            # Check if exactly 2 colonies from this line are active
            active_in_line = completed.intersection(line)
            if len(active_in_line) == 2:
                # Add the third colony from this line
                third = next(c for c in line if c not in active_in_line)
                completed.add(third)
                logger.debug(
                    f"Fano completion: {[COLONY_NAMES[i] for i in active_in_line]} "
                    f"→ added {COLONY_NAMES[third]}"
                )

        return completed


# =============================================================================
# FANO LINE CONSENSUS
# =============================================================================


def fano_line_consensus(
    line: tuple[int, int, int],
    proposals: list[Any],  # list[ColonyConsensusState]
    quorum_threshold: float = 0.67,  # 2/3 quorum
) -> bool:
    """Check if Fano line colonies agree (2/3 quorum).

    For a Fano line (i, j, k), checks if at least 2 of the 3 colonies
    agree on the routing proposal.

    BYZANTINE TOLERANCE:
    - With 3 colonies on a Fano line, can tolerate 1 faulty colony
    - Requires 2/3 agreement for valid consensus

    Args:
        line: Tuple of 3 colony indices (0-indexed)
        proposals: List of colony consensus states
        quorum_threshold: Minimum agreement for consensus (default 2/3)

    Returns:
        True if Fano line colonies reach quorum
    """

    # Extract proposals from Fano line colonies
    line_proposals = []
    for colony_idx in line:
        if colony_idx < len(proposals):
            line_proposals.append(proposals[colony_idx])

    if len(line_proposals) != 3:
        logger.warning(f"Invalid Fano line proposals: expected 3, got {len(line_proposals)}")
        return False

    # Compute pairwise agreement
    agreements = []
    for i in range(3):
        for j in range(i + 1, 3):
            p1 = line_proposals[i]
            p2 = line_proposals[j]

            # Compute Jaccard similarity on target colonies
            set1 = set(p1.target_colonies) if hasattr(p1, "target_colonies") else set()
            set2 = set(p2.target_colonies) if hasattr(p2, "target_colonies") else set()

            if len(set1 | set2) == 0:
                similarity = 0.0
            else:
                similarity = len(set1 & set2) / len(set1 | set2)

            agreements.append(similarity)

    # Check if mean agreement exceeds threshold
    mean_agreement = sum(agreements) / len(agreements)
    return mean_agreement >= quorum_threshold


# =============================================================================
# FACTORY
# =============================================================================


def create_consensus_aware_router(  # type: ignore[no-untyped-def]
    fano_router: Any | None = None,
    consensus: Any | None = None,
    enable_consensus: bool = True,
    consensus_timeout: float = 2.0,
    **router_kwargs,
) -> ConsensusAwareFanoRouter:
    """Create a consensus-aware Fano router.

    Args:
        fano_router: Base FanoActionRouter (or None to create default)
        consensus: KagamiConsensus instance (or None to create default)
        enable_consensus: Enable consensus validation
        consensus_timeout: Timeout for consensus (seconds)
        **router_kwargs: Additional kwargs for FanoActionRouter creation

    Returns:
        Configured ConsensusAwareFanoRouter
    """
    if fano_router is None:
        from .router_core import create_fano_router

        fano_router = create_fano_router(**router_kwargs)

    return ConsensusAwareFanoRouter(
        fano_router=fano_router,
        consensus=consensus,
        enable_consensus=enable_consensus,
        consensus_timeout=consensus_timeout,
    )


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "ConsensusAwareFanoRouter",
    "RouterCompositionMixin",
    "create_consensus_aware_router",
    "fano_line_consensus",
]
