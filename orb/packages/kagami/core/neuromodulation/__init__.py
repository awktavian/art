"""Neuromodulation System - Brain-Inspired State Modulation.

This package implements analogs of the four primary neuromodulator systems:
- Dopamine (DA): Reward prediction, gating, motivation
- Norepinephrine (NE): Arousal, exploration-exploitation
- Acetylcholine (ACh): Attention, learning rate
- Serotonin (5-HT): Temporal discounting, risk aversion

References:
- Dayan & Yu (2006): Phasic norepinephrine
- Schultz (1998): Dopamine reward prediction error
- Hasselmo (2006): Acetylcholine and memory
"""

from .modulator_system import (
    AcetylcholineChannel,
    DopamineChannel,
    NeuromodulatorState,
    NeuromodulatorSystem,
    NorepinephrineChannel,
    SerotoninChannel,
    create_neuromodulator_system,
)

__all__ = [
    "AcetylcholineChannel",
    "DopamineChannel",
    "NeuromodulatorState",
    "NeuromodulatorSystem",
    "NorepinephrineChannel",
    "SerotoninChannel",
    "create_neuromodulator_system",
]
