"""Action module - Active states of the Markov blanket.

ARCHITECTURE (Dec 2, 2025):
===========================
Actions are the ACTIVE STATES of the system's Markov blanket.
They influence the environment but are not directly influenced by it.

SYMMETRIC E8 BOTTLENECK:
=======================
PERCEPTION:  External → Sensors → E8 Encode → Colony Collaboration → Internal
ACTION:      Internal → Colony Collaboration → E8 Encode → Effectors → External

Both sides use variable-length E8 residual encoding:
- Information Bottleneck optimal: min I(X; Z) - β·I(Z; Y)
- Adaptive capacity: simple = 1 byte, complex = 4+ bytes
- Unified protocol: same E8MessageBus for routing

Colony collaboration (CoT) happens INSIDE the blanket on BOTH sides.

Markov Blanket Structure:
    Environment (η)
        ↓ (sensory)
    Sensory States (s) → Internal States (μ) → Active States (a)
        ↑                                         ↓
    Environment (η) ←─────────────────────────────┘

Components:
- OrganismMarkovBlanket: Unified sensory + active interface
- ActiveDecoder: E8 action → effector commands
- SensoryEncoder: Sensor inputs → bulk observation

Usage:
    from kagami.core.execution import get_markov_blanket

    blanket = get_markov_blanket(organism=organism_rssm)

    # Perception
    sensory = blanket.perceive(hal_input=sensors, agui_input=user_msg)
    observation = sensory.combined  # [512] for world model

    # Action (with colony collaboration INSIDE blanket)
    active = blanket.act(z_all=colony_states)  # Full pipeline
    await blanket.execute_on_hal(hal_manager, active)
    await blanket.send_to_agui(agui_adapter, active)
"""

from .markov_blanket import (
    ActiveDecoder,
    ActiveState,
    OrganismMarkovBlanket,
    SensoryEncoder,
    SensoryState,
    get_markov_blanket,
    reset_markov_blanket,
)

__all__ = [
    "ActiveDecoder",
    "ActiveState",
    # Core blanket
    "OrganismMarkovBlanket",
    # Encoders/Decoders
    "SensoryEncoder",
    "SensoryState",
    # Singleton
    "get_markov_blanket",
    "reset_markov_blanket",
]
