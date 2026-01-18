"""Causal Inference Intent Handler.

Created: November 2, 2025
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


async def handle_causal_intent(intent: dict[str, Any]) -> dict[str, Any]:
    """Handle causal inference intents.

    Args:
        intent: Intent dict[str, Any]

    Returns:
        Causal analysis result
    """
    params = intent.get("args", {}) or intent.get("params", {})

    try:
        from kagami.core.reasoning.counterfactual import (
            CausalGraph,
            DoCalculus,
            estimate_ate_simple,
        )

        query_type = params.get("type", "ate")

        if query_type == "ate":
            # Average Treatment Effect
            treatment = params.get("treatment")
            outcome = params.get("outcome")
            data = params.get("data", {})

            if not treatment or not outcome or not data:
                return {
                    "status": "error",
                    "error": "Missing required params: treatment, outcome, data",
                }

            # Convert to numpy
            data_arrays = {k: np.array(v) if isinstance(v, list) else v for k, v in data.items()}

            ate = estimate_ate_simple(treatment, outcome, data_arrays)

            return {
                "status": "success",
                "ate": float(ate),
                "treatment": treatment,
                "outcome": outcome,
                "interpretation": f"{treatment} causes {ate:+.3f} change in {outcome}",
            }

        elif query_type == "counterfactual":
            # Counterfactual query
            nodes = params.get("nodes", [])
            edges = params.get("edges", [])
            factual = params.get("factual", {})
            intervention = params.get("intervention", {})
            query_var = params.get("query_variable")

            graph = CausalGraph(nodes=nodes, edges=edges)
            do_calc = DoCalculus(graph)

            result = do_calc.compute_counterfactual(factual, intervention, query_var)

            return {"status": "success", "counterfactual": result}

        else:
            return {"status": "error", "error": f"Unknown causal query type: {query_type}"}

    except Exception as e:
        logger.error(f"Causal inference failed: {e}")
        return {"status": "error", "error": str(e)}


__all__ = ["handle_causal_intent"]
