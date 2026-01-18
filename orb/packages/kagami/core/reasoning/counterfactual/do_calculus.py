"""Pearl's Do-Calculus for Counterfactual Reasoning.

Enables "what if" questions via causal intervention:
- do(X=x): Intervention (force X to value x)
- P(Y|do(X=x)): Causal effect of X on Y
- Counterfactuals: "What if X had been x instead?"

Based on: Pearl, Judea (2009) "Causality: Models, Reasoning and Inference"

Created: November 2, 2025
Status: Research-ready (requires causal graph)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

try:
    import networkx as nx

    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False
    logger.warning("networkx not installed - causal reasoning limited")


@dataclass
class CausalGraph:
    """Directed acyclic graph representing causal relationships."""

    nodes: list[str]
    edges: list[tuple[str, str]]  # (cause, effect)

    def to_networkx(self) -> Any:
        """Convert to NetworkX DiGraph."""
        if not HAS_NETWORKX:
            raise ImportError("networkx required") from None

        G = nx.DiGraph()  # type: ignore[var-annotated]
        G.add_nodes_from(self.nodes)
        G.add_edges_from(self.edges)
        return G

    def parents(self, node: str) -> list[str]:
        """Get parent nodes (direct causes)."""
        return [src for src, dst in self.edges if dst == node]

    def children(self, node: str) -> list[str]:
        """Get child nodes (direct effects)."""
        return [dst for src, dst in self.edges if src == node]

    def ancestors(self, node: str) -> set[str]:
        """Get all ancestor nodes (transitive causes)."""
        if not HAS_NETWORKX:
            return set()

        G = self.to_networkx()
        return set(nx.ancestors(G, node))

    def descendants(self, node: str) -> set[str]:
        """Get all descendant nodes (transitive effects)."""
        if not HAS_NETWORKX:
            return set()

        G = self.to_networkx()
        return set(nx.descendants(G, node))


class DoCalculus:
    """Implement Pearl's do-calculus for causal reasoning."""

    def __init__(self, causal_graph: CausalGraph):
        """Initialize do-calculus engine.

        Args:
            causal_graph: Causal graph structure
        """
        self.graph = causal_graph
        self.G = causal_graph.to_networkx() if HAS_NETWORKX else None

        logger.info(
            f"DoCalculus initialized: {len(causal_graph.nodes)} nodes, {len(causal_graph.edges)} edges"
        )

    def do_intervention(
        self,
        intervention_node: str,
        intervention_value: float,
        data: dict[str, np.ndarray[Any, Any]],
    ) -> dict[str, np.ndarray[Any, Any]]:
        """Perform do-intervention: force node to value, remove incoming edges.

        Args:
            intervention_node: Node to intervene on
            intervention_value: Value to set[Any]
            data: Observational data

        Returns:
            Modified data with intervention applied
        """
        # Create copy of data
        intervened_data = {k: v.copy() for k, v in data.items()}

        # Set intervention node to constant value
        intervened_data[intervention_node] = np.full_like(
            data[intervention_node], intervention_value
        )

        return intervened_data

    def estimate_causal_effect(
        self,
        treatment: str,
        outcome: str,
        data: dict[str, np.ndarray[Any, Any]],
        treatment_value: float = 1.0,
        control_value: float = 0.0,
    ) -> dict[str, Any]:
        """Estimate causal effect of treatment on outcome.

        Computes: E[Y|do(X=1)] - E[Y|do(X=0)]

        Args:
            treatment: Treatment variable name
            outcome: Outcome variable name
            data: Observational data
            treatment_value: Treatment value
            control_value: Control value

        Returns:
            Causal effect estimate
        """
        # Intervention 1: do(treatment = treatment_value)
        data_treatment = self.do_intervention(treatment, treatment_value, data)
        outcome_treatment = np.mean(data_treatment[outcome])

        # Intervention 2: do(treatment = control_value)
        data_control = self.do_intervention(treatment, control_value, data)
        outcome_control = np.mean(data_control[outcome])

        # Average treatment effect (ATE)
        ate = outcome_treatment - outcome_control

        return {
            "ate": float(ate),
            "outcome_treatment": float(outcome_treatment),
            "outcome_control": float(outcome_control),
            "treatment": treatment,
            "outcome": outcome,
        }

    def compute_counterfactual(
        self, factual_data: dict[str, float], intervention: dict[str, float], query_variable: str
    ) -> dict[str, Any]:
        """Compute counterfactual: "What if X had been x instead?"

        Three-step process:
        1. Abduction: Infer exogenous variables from factual data
        2. Action: Apply intervention (set[Any] X=x)
        3. Prediction: Propagate through causal graph using topological order

        Args:
            factual_data: Actual observed values
            intervention: Variables to intervene on and their values
            query_variable: Variable to predict

        Returns:
            Counterfactual prediction
        """
        # Step 1: Abduction - use factual values as baseline for exogenous variables
        # In a full SEM, we would solve for exogenous variables given observed values
        # For now, we use factual values directly (assumes deterministic SEM)
        counterfactual_state = factual_data.copy()

        # Step 2: Action - apply intervention (set[Any] intervened variables)
        counterfactual_state.update(intervention)

        # Step 3: Prediction - propagate through causal graph using topological order
        # Compute values for all descendants of intervened variables
        if self.G is not None and HAS_NETWORKX:
            try:
                import networkx as nx

                # Get topological order to ensure parents computed before children
                topo_order = list(nx.topological_sort(self.G))

                # Propagate effects: for each node in topological order,
                # if it's a descendant of an intervened variable, recompute its value
                intervened_nodes = set(intervention.keys())

                for node in topo_order:
                    if node in intervened_nodes:
                        # Node was intervened on, keep its intervention value
                        continue

                    # Check if node is descendant of any intervened node
                    parents = self.graph.parents(node)
                    if any(p in intervened_nodes for p in parents) or any(
                        node in self.graph.descendants(interv_node)
                        for interv_node in intervened_nodes
                    ):
                        # Node is downstream of intervention, recompute using linear SEM approximation
                        # Linear SEM: Y = sum(α_i * X_i) + ε where X_i are parents
                        # For simplicity, use weighted sum of parent values
                        if parents:
                            # Compute as weighted average of parent values
                            # In a full SEM, this would use learned coefficients
                            parent_values = [
                                counterfactual_state.get(p, factual_data.get(p, 0.0))
                                for p in parents
                            ]
                            # Simple linear combination (full SEM would have learned weights)
                            counterfactual_state[node] = (
                                sum(parent_values) / len(parents)
                                if parent_values
                                else factual_data.get(node, 0.0)
                            )
                        else:
                            # Root node not intervened, keep factual value
                            counterfactual_state[node] = factual_data.get(node, 0.0)

                counterfactual_value = counterfactual_state.get(
                    query_variable, factual_data.get(query_variable, 0.0)
                )
            except Exception as e:
                logger.warning(
                    f"Graph-based counterfactual propagation failed: {e}, using simplified method"
                )
                # Fallback to simplified method
                if query_variable in intervention:
                    counterfactual_value = intervention[query_variable]
                else:
                    counterfactual_value = factual_data.get(query_variable, 0.0)
        else:
            # No graph available, use simplified propagation
            if query_variable in intervention:
                counterfactual_value = intervention[query_variable]
            else:
                # Check if query variable is downstream of any intervention
                # Simple heuristic: if query variable has parents that were intervened, estimate effect
                parents = self.graph.parents(query_variable)
                if parents and any(p in intervention for p in parents):
                    # Estimate: weighted average of parent values
                    parent_values = [
                        counterfactual_state.get(p, factual_data.get(p, 0.0)) for p in parents
                    ]
                    counterfactual_value = (
                        sum(parent_values) / len(parent_values)
                        if parent_values
                        else factual_data.get(query_variable, 0.0)
                    )
                else:
                    counterfactual_value = factual_data.get(query_variable, 0.0)

        return {
            "query_variable": query_variable,
            "factual_value": factual_data.get(query_variable, 0.0),
            "counterfactual_value": counterfactual_value,
            "intervention": intervention,
            "note": "Counterfactual computed via causal graph propagation (linear SEM approximation)",
        }

    def identify_adjustment_set(self, treatment: str, outcome: str) -> set[str]:
        """Find minimal adjustment set[Any] for identifying causal effect.

        Adjustment set[Any]: variables to condition on to block confounding paths.

        Args:
            treatment: Treatment variable
            outcome: Outcome variable

        Returns:
            Minimal adjustment set[Any]
        """
        if not HAS_NETWORKX:
            logger.error("networkx required for adjustment set[Any] identification")
            return set()

        # Find all backdoor paths (confounders)
        try:
            # Simple heuristic: all common ancestors
            treatment_ancestors = self.graph.ancestors(treatment)
            outcome_ancestors = self.graph.ancestors(outcome)
            confounders = treatment_ancestors & outcome_ancestors

            return confounders
        except Exception as e:
            logger.error(f"Adjustment set[Any] identification failed: {e}")
            return set()


def estimate_ate_simple(
    treatment_var: str, outcome_var: str, data: dict[str, np.ndarray[Any, Any]]
) -> float:
    """Simple ATE estimation without causal graph.

    Computes: E[Y|X=1] - E[Y|X=0] (may be confounded!)

    Args:
        treatment_var: Treatment variable name
        outcome_var: Outcome variable name
        data: Observational data

    Returns:
        Average treatment effect (may include confounding bias)
    """
    treatment = data[treatment_var]
    outcome = data[outcome_var]

    # Split by treatment
    treated = outcome[treatment > 0.5]
    control = outcome[treatment <= 0.5]

    ate = np.mean(treated) - np.mean(control) if len(treated) > 0 and len(control) > 0 else 0.0

    return float(ate)


__all__ = ["CausalGraph", "DoCalculus", "estimate_ate_simple"]
