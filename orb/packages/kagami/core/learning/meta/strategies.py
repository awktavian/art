"""Reasoning Strategies for Agent Operations.

Defines the reasoning strategies used by the meta-learning system
to track and optimize agent decision-making approaches.

These strategies correspond to different reasoning frameworks:
- ReAct: Reason + Act interleaved pattern
- Self-Consistency: Multiple reasoning paths with voting
- Tree of Thought: Structured exploration of thought branches
- Reflexion: Learn from mistakes with reflection
- Chain of Verification: Verify claims through questioning

Migrated from kagami.core.agent_operations_lib.strategies
"""

from enum import Enum


class ReasoningStrategy(Enum):
    """Reasoning strategies for agent meta-learning.

    These are meta-level strategies that determine HOW the agent
    reasons, not WHAT it reasons about. The StrategyOptimizer
    learns which strategies work best for different problem types.

    K-values indicate reasoning depth (higher = more thorough):
    - K=1: Single pass (fast)
    - K=3-5: Standard depth (balanced)
    - K=7-11: Deep reasoning (thorough)
    """

    # ReAct: Reason + Act interleaved (Yao et al., 2022)
    REACT_K1 = "react_k1"  # Single ReAct loop
    REACT_K3 = "react_k3"  # 3-step ReAct
    REACT_K5 = "react_k5"  # 5-step ReAct

    # Self-Consistency: Multiple paths + voting (Wang et al., 2022)
    SELF_CONSISTENCY_K3 = "self_consistency_k3"  # 3 reasoning paths
    SELF_CONSISTENCY_K5 = "self_consistency_k5"  # 5 reasoning paths
    SELF_CONSISTENCY_K7 = "self_consistency_k7"  # 7 reasoning paths

    # Tree of Thought: Structured exploration (Yao et al., 2023)
    TOT_BREADTH_2 = "tot_breadth_2"  # 2 branches per node
    TOT_BREADTH_3 = "tot_breadth_3"  # 3 branches per node
    TOT_DEPTH_3 = "tot_depth_3"  # 3 levels deep

    # Reflexion: Learn from mistakes (Shinn et al., 2023)
    REFLEXION_K1 = "reflexion_k1"  # Single reflection
    REFLEXION_K3 = "reflexion_k3"  # Up to 3 reflections

    # Chain of Verification: Verify claims (Dhuliawala et al., 2023)
    COVE_BASIC = "cove_basic"  # Basic verification
    COVE_FACTORED = "cove_factored"  # Factored verification

    # Hybrid strategies
    REACT_COT = "react_cot"  # ReAct + Chain of Thought
    TOT_SELF_CONSISTENCY = "tot_self_consistency"  # ToT with voting

    # Simple/baseline strategies
    DIRECT = "direct"  # No special reasoning
    COT = "cot"  # Chain of Thought only


__all__ = ["ReasoningStrategy"]
