from __future__ import annotations

"""Causal Inference Engine - Unified Interface to Full Algorithms.

This module provides a unified interface to FULL scientific causal inference:
1. PC Algorithm (Spirtes et al., 2000) - Rigorous causal discovery
2. Do-Calculus (Pearl, 2009) - Intervention prediction
3. Counterfactual reasoning - "What if X?" questions

Uses the complete implementations from:
- kagami/core/reasoning/pc_algorithm.py (full PC with CI tests)
- kagami/core/reasoning/do_calculus.py (full do-calculus rules)

Based on Pearl 2009: "Causality: Models, Reasoning, and Inference"
"""
import logging
from dataclasses import dataclass
from typing import Any

import networkx as nx
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class CausalEdge:
    """A causal relationship between variables."""

    cause: str
    effect: str
    strength: float  # -1.0 to 1.0 (negative = inhibitory, positive = excitatory)
    confidence: float  # 0.0-1.0 (how certain of this causal link)


class CausalInferenceEngine:
    """Unified interface to FULL scientific causal inference algorithms.

    Delegates to:
    1. PC Algorithm (Spirtes et al., 2000) - Causal discovery with CI tests
    2. Do-Calculus (Pearl, 2009) - Rigorous intervention prediction
    3. Counterfactual engine - "What if" reasoning

    This is a HIGH-LEVEL interface. For direct access to algorithms:
    - kagami.core.reasoning.pc_algorithm.get_pc_algorithm()
    - kagami.core.reasoning.do_calculus.get_do_calculus()
    """

    def __init__(self) -> None:
        self.causal_graph = nx.DiGraph()  # type: ignore[var-annotated]

        self._observations: list[dict[str, Any]] = []
        self._learned_edges: list[CausalEdge] = []

        # Delegate to full implementations
        self._pc: Any = None  # Lazy loaded
        self._do_calculus: Any = None  # Lazy loaded

    def add_observation(self, observation: dict[str, Any]) -> None:
        """Add observational data for causal discovery.

        Args:
            observation: {variable_name: value, ...}
        """
        self._observations.append(observation)

    async def discover_causal_structure(
        self, variables: list[str], min_samples: int = 50
    ) -> list[CausalEdge]:
        """Discover causal relationships using FULL PC algorithm.

        Uses Spirtes et al. (2000) PC algorithm with:
        - Conditional independence tests (Fisher's Z)
        - V-structure orientation
        - Meek rules for edge propagation

        Args:
            variables: List of variable names to analyze
            min_samples: Minimum samples needed for reliable discovery

        Returns:
            List of discovered causal edges (partially oriented CPDAG)
        """
        if len(self._observations) < min_samples:
            logger.warning(
                f"Insufficient data for causal discovery: {len(self._observations)} < {min_samples}"
            )
            return []

        # Convert observations to numpy array
        data_matrix = self._observations_to_matrix(variables)

        if data_matrix is None:
            return []

        # USE FULL PC ALGORITHM (not correlation-based)
        from kagami.core.reasoning.pc_algorithm import get_pc_algorithm

        if self._pc is None:
            self._pc = get_pc_algorithm(alpha=0.05, max_cond_set=3)

        edges = await self._pc.discover_causal_structure(data_matrix, variables)

        # Update our graph from PC results
        self.causal_graph = self._pc.graph.copy()
        self._learned_edges = edges

        logger.info(
            f"🔗 Discovered {len(edges)} causal edges via PC algorithm "
            f"(directed={self._pc.graph.number_of_edges()}, "
            f"undirected={self._pc.skeleton.number_of_edges()})"
        )

        # PC algorithm returns its own CausalEdge type - convert to ours (same structure)
        from kagami.core.reasoning.pc_algorithm import CausalEdge as PCCausalEdge

        # Both CausalEdge types have same structure (cause, effect, strength, confidence)
        # Convert PC CausalEdge to our CausalEdge
        converted_edges = [
            (
                CausalEdge(
                    cause=e.cause,
                    effect=e.effect,
                    strength=e.strength,
                    confidence=getattr(e, "confidence", 0.5),  # PC has confidence field
                )
                if isinstance(e, PCCausalEdge)
                else CausalEdge(
                    cause=str(e[0]) if isinstance(e, tuple) else getattr(e, "cause", ""),
                    effect=str(e[1]) if isinstance(e, tuple) else getattr(e, "effect", ""),
                    strength=getattr(e, "strength", 0.5),
                    confidence=getattr(e, "confidence", 0.5),
                )
            )
            for e in edges
        ]
        return converted_edges

    def _observations_to_matrix(self, variables: list[str]) -> np.ndarray[Any, Any] | None:
        """Convert observations to numpy matrix."""
        try:
            matrix: list[Any] = []
            for obs in self._observations:
                row = [obs.get(var, 0.0) for var in variables]
                matrix.append(row)

            return np.array(matrix)
        except Exception as e:
            logger.error(f"Failed to convert observations to matrix: {e}")
            return None

    # REMOVED: Old _correlation_based_discovery() method
    # Now uses FULL PC algorithm from kagami/core/reasoning/pc_algorithm.py
    # which includes conditional independence tests, v-structures, and Meek rules

    async def predict_intervention(
        self, intervention: dict[str, Any], target_variable: str
    ) -> dict[str, Any]:
        """Predict effect of intervention using FULL do-calculus.

        Uses Pearl's (2009) do-calculus with:
        - Back-door criterion checking
        - Front-door criterion checking
        - Proper marginalization over adjustment sets

        Args:
            intervention: {variable: new_value} to set[Any]
            target_variable: Variable to predict outcome for

        Returns:
            {
                "predicted_value": float,
                "confidence": float,
                "identifiable": bool,
                "formula": str  # Do-calculus derivation
            }
        """
        if not self.causal_graph.has_node(target_variable):
            return {
                "predicted_value": None,
                "confidence": 0.0,
                "causal_path": [],
                "identifiable": False,
                "error": f"Target variable {target_variable} not in causal graph",
            }

        # USE FULL DO-CALCULUS (not simple path propagation)
        from kagami.core.reasoning.do_calculus import get_do_calculus

        if self._do_calculus is None:
            self._do_calculus = get_do_calculus(self.causal_graph)

            # Pass observational data to do-calculus engine
            if self._observations:
                data_matrix = self._observations_to_matrix(list(self.causal_graph.nodes()))
                if data_matrix is not None:
                    self._do_calculus.set_observational_data(
                        data_matrix, list(self.causal_graph.nodes())
                    )

        result = await self._do_calculus.predict_intervention(intervention, target_variable)

        # Convert to legacy format for backward compatibility
        return {
            "predicted_value": result.expected_value,
            "confidence": result.confidence,
            "identifiable": result.identifiable,
            "formula": result.formula,
            "distribution": result.predicted_distribution,
            "intervention": result.intervention,
        }

    async def answer_counterfactual(
        self, factual: dict[str, Any], counterfactual: dict[str, Any], target: str
    ) -> dict[str, Any]:
        """
        Answer counterfactual questions: "What if X had been Y?"

        Args:
            factual: What actually happened {var: value}
            counterfactual: What we imagine {var: different_value}
            target: Variable to predict under counterfactual

        Returns:
            {
                "factual_outcome": float,
                "counterfactual_outcome": float,
                "difference": float,
                "confidence": float
            }
        """
        # This requires causal model + Pearl's 3-step procedure:
        # 1. Abduction: Infer hidden factors from factual
        # 2. Action: Apply counterfactual intervention
        # 3. Prediction: Predict new outcome

        # Simplified implementation
        counterfactual_prediction = await self.predict_intervention(
            intervention=counterfactual, target_variable=target
        )

        return {
            "factual_outcome": factual.get(target),
            "counterfactual_outcome": counterfactual_prediction.get("predicted_value"),
            "difference": (
                counterfactual_prediction.get("predicted_value", 0) - factual.get(target, 0)
            ),
            "confidence": counterfactual_prediction.get("confidence", 0.5),
        }

    def get_causal_graph_info(self) -> dict[str, Any]:
        """Get information about learned causal graph."""
        return {
            "nodes": list(self.causal_graph.nodes()),
            "edges": len(self.causal_graph.edges()),
            "learned_edges": len(self._learned_edges),
            "observations_collected": len(self._observations),
        }


# Singleton
_causal_engine: CausalInferenceEngine | None = None


def get_causal_inference_engine() -> CausalInferenceEngine:
    """Get or create global causal inference engine."""
    global _causal_engine
    if _causal_engine is None:
        _causal_engine = CausalInferenceEngine()
    return _causal_engine
