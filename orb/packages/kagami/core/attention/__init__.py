"""Valued-Attention System - Attention that learns preferences via TD-learning.

This module implements attention with preference memory that creates stable
micro-habits over time through Hebbian+TD learning.

Core components:
- ValuedAttentionHead: Main attention module with bias terms
- PreferenceMemory: P_long (trait) and P_sess (session) preference vectors
- StateVector: Proprioceptive state from manifold + metrics
- AttributeEncoder: Maps tokens to attribute space
- ValueFunction: Critic network for TD-learning

Theory:
    L' = L + B_long + B_state + B_homeo
    where:
    - L = QK^T / √d_k (standard attention logits)
    - B_long = β·⟨P, e_t⟩ (preference memory)
    - B_state = γ·s^T W_v e_t (state coupling)
    - B_homeo = -λ·||s - s*||² (homeostasis)

Learning:
    P ← (1-η_d)P + η_p·δ_t·(Σ_t a_t e_t)
    where δ_t = r_t + γ_TD·V(s_{t+1}) - V(s_t)
"""

from kagami.core.attention.attribute_encoder import (
    AttributeEncoder,
    get_attribute_encoder,
)
from kagami.core.attention.preference_memory import (
    PreferenceMemory,
    get_preference_memory,
)
from kagami.core.attention.state_vector import (
    StateVector,
    manifold_to_state_vector,
)
from kagami.core.attention.value_function import (
    CriticNetwork,
    get_value_function,
)
from kagami.core.attention.valued_attention import (
    ValuedAttentionHead,
    get_valued_attention_head,
)

__all__ = [
    "AttributeEncoder",
    "CriticNetwork",
    "PreferenceMemory",
    "StateVector",
    "ValuedAttentionHead",
    "get_attribute_encoder",
    "get_preference_memory",
    "get_value_function",
    "get_valued_attention_head",
    "manifold_to_state_vector",
]
