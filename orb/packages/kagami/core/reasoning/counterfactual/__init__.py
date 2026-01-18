"""Counterfactual Reasoning using Pearl's Do-Calculus.

Enables "what if" questions:
- P(Y|do(X=x)) - causal effect
- Counterfactuals - "what if X had been different?"
- Adjustment sets - blocking confounders

Created: November 2, 2025
"""

from kagami.core.reasoning.counterfactual.do_calculus import (
    CausalGraph,
    DoCalculus,
    estimate_ate_simple,
)

__all__ = [
    "CausalGraph",
    "DoCalculus",
    "estimate_ate_simple",
]
