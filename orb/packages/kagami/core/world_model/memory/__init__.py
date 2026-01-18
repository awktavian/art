"""Split E₈ Memory Architecture for K OS World Model.

ARCHITECTURE (Dec 5, 2025 - CLEANED):
=====================================
Memory and programs are SEPARATE concerns with optimal dimensions:

1. EpisodicMemory (256D values)  → "What happened?" (stores RSSM h)
2. ProgramLibrary (52D + control params) → "What to do?" (action selection)
3. E8VQ (8D native)               → Discrete quantization

CATASTROPHE-AWARE PROGRAMS:
===========================
Programs store catastrophe control parameters (a, b, c, d) alongside embeddings.
This enables:
- Learned colony affinity (not round-robin)
- Catastrophe state alignment in selection
- Integration with CatastropheKAN activation functions

RESEARCH FOUNDATIONS:
====================
- Ramsauer et al. (2021): Hopfield Networks exponential capacity
- DreamerV3 (Hafner): RSSM h must not be bottlenecked
- Viazovska (2016): E₈ optimal sphere packing in 8D
- Thom (1972): 7 elementary catastrophes
- Exceptional Lie algebras: G₂(14) ⊂ F₄(52) ⊂ E₆(78) ⊂ E₇(133) ⊂ E₈(248)

DIMENSION CHOICES:
=================
| Component      | Dimension | Rationale                          |
|----------------|-----------|-------------------------------------|
| Memory values  | 256D      | Match RSSM h (no truncation)       |
| Program embeds | 52D + 4D  | F₄ + catastrophe control params    |
| VQ codebook    | 8D        | E₈ roots (native dimension)        |

Created: November 30, 2025 (Memory)
Refactored: December 5, 2025 (Deprecated code removed)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

# === NEW SPLIT ARCHITECTURE (PREFERRED) ===
from kagami.core.world_model.memory.episodic_memory import (
    RSSM_H_DIM,
    EpisodicMemory,
    EpisodicMemoryConfig,
    G2Projection,
)

# NEW: Residual Program Library with E8 multi-level addressing (Dec 3, 2025)
from kagami.core.world_model.memory.residual_program_library import (
    ResidualCatastropheProgramLibrary,
    ResidualProgramConfig,
)

# Constants from canonical catastrophe module

# === PRIMARY EXPORTS (USE THESE!) ===
ProgramLibrary = ResidualCatastropheProgramLibrary  # 240^L residual E8 states
ProgramLibraryConfig = ResidualProgramConfig
PROGRAM_DIM = 52  # F₄ dimension

# === HOPFIELD MEMORY (CANONICAL) ===
# All Hopfield functionality consolidated in ModernHopfieldScaled
from kagami.core.optimality.improvements import ModernHopfieldScaled

# Backward-compatible aliases
HierarchicalHopfieldMemory = ModernHopfieldScaled
ModernHopfieldMemory = ModernHopfieldScaled

# =============================================================================
# ALIASES (Canonical names point to current implementations)
# =============================================================================

# NOTE (Dec 8, 2025): Solomonoff aliases REMOVED — the name was misleading.
# True Solomonoff induction requires computing Kolmogorov complexity, which is
# provably incomputable. Use ResidualCatastropheProgramLibrary directly.


# =============================================================================
# COLONY GENOME
# =============================================================================


@dataclass
class ColonyGenome:
    """First 16 bytes of DNA determine colony identity."""

    colony_type: int = 0
    catastrophe_codim: int = 1
    curiosity: float = 0.5
    competence: float = 0.5
    autonomy: float = 0.5
    relatedness: float = 0.5
    purpose: float = 0.5
    temperature: float = 0.5
    fano_partner_1: int = 0
    fano_partner_2: int = 0
    fano_partner_3: int = 0
    growth_rate: float = 0.1
    program_bias: int = 0
    mutation_rate: float = 0.01
    reserved_1: int = 0
    reserved_2: int = 0

    def to_bytes(self) -> bytes:
        return bytes(
            [
                self.colony_type % 7,
                self.catastrophe_codim % 5,
                int(self.curiosity * 255),
                int(self.competence * 255),
                int(self.autonomy * 255),
                int(self.relatedness * 255),
                int(self.purpose * 255),
                int(self.temperature * 255),
                self.fano_partner_1 % 7,
                self.fano_partner_2 % 7,
                self.fano_partner_3 % 7,
                int(self.growth_rate * 255),
                self.program_bias % 240,
                int(self.mutation_rate * 255),
                self.reserved_1 % 256,
                self.reserved_2 % 256,
            ]
        )

    @classmethod
    def from_bytes(cls, data: bytes) -> ColonyGenome:
        if len(data) < 16:
            data = data + bytes(16 - len(data))
        return cls(
            colony_type=data[0] % 7,
            catastrophe_codim=max(1, data[1] % 5),
            curiosity=data[2] / 255.0,
            competence=data[3] / 255.0,
            autonomy=data[4] / 255.0,
            relatedness=data[5] / 255.0,
            purpose=data[6] / 255.0,
            temperature=data[7] / 255.0,
            fano_partner_1=data[8] % 7,
            fano_partner_2=data[9] % 7,
            fano_partner_3=data[10] % 7,
            growth_rate=data[11] / 255.0,
            program_bias=data[12] % 240,
            mutation_rate=data[13] / 255.0,
            reserved_1=data[14],
            reserved_2=data[15],
        )

    @classmethod
    def for_colony(cls, colony_idx: int) -> ColonyGenome:
        # Catastrophe codimensions: Fold(1), Cusp(2), Swallowtail(3), Butterfly(4),
        # Hyperbolic(3), Elliptic(3), Parabolic(4)
        COLONY_CODIM = [1, 2, 3, 4, 3, 3, 4]

        # Fano partners derived from canonical FANO_LINES (quantum/fano_plane.py)
        # FANO_LINES = [(1,2,3), (1,4,5), (1,6,7), (2,4,6), (5,2,7), (4,3,7), (5,3,6)]
        # For each colony (0-6), list[Any] the colonies it shares Fano lines with (0-indexed)
        # Colony 0 (e₁): lines 0,1,2 → partners {1,2,3,4,5,6}
        # Colony 1 (e₂): lines 0,3,4 → partners {0,2,3,4,5,6}
        # Colony 2 (e₃): lines 0,5,6 → partners {0,1,3,4,5,6}
        # Colony 3 (e₄): lines 1,3,5 → partners {0,1,2,5,6}
        # Colony 4 (e₅): lines 1,4,6 → partners {0,1,2,3,6}
        # Colony 5 (e₆): lines 2,3,6 → partners {0,1,2,3,4}
        # Colony 6 (e₇): lines 2,4,5 → partners {0,1,2,3,4,5}
        # Pick first 3 partners for simplicity (from shared Fano lines)
        FANO_PARTNERS = [
            (1, 2, 3),  # e₁: shares lines with e₂(line 0), e₃(line 0), e₄(line 1)
            (0, 3, 4),  # e₂: shares lines with e₁(line 0), e₄(line 3), e₅(line 4)
            (0, 4, 5),  # e₃: shares lines with e₁(line 0), e₅(line 6), e₆(line 6)
            (0, 2, 6),  # e₄: shares lines with e₁(line 1), e₃(line 5), e₇(line 5)
            (0, 1, 6),  # e₅: shares lines with e₁(line 1), e₂(line 4), e₇(line 4)
            (0, 1, 2),  # e₆: shares lines with e₁(line 2), e₂(line 3), e₃(line 6)
            (0, 2, 3),  # e₇: shares lines with e₁(line 2), e₃(line 5), e₄(line 5)
        ]
        partners = FANO_PARTNERS[colony_idx % 7]
        return cls(
            colony_type=colony_idx % 7,
            catastrophe_codim=COLONY_CODIM[colony_idx % 7],
            curiosity=0.5 + 0.1 * (colony_idx % 3),
            fano_partner_1=partners[0],
            fano_partner_2=partners[1],
            fano_partner_3=partners[2],
            program_bias=colony_idx * 34,
        )


__all__ = [
    "PROGRAM_DIM",
    "RSSM_H_DIM",
    # === COLONY GENOME ===
    "ColonyGenome",
    # === EPISODIC MEMORY ===
    "EpisodicMemory",
    "EpisodicMemoryConfig",
    "G2Projection",
    "HierarchicalHopfieldMemory",
    "ModernHopfieldMemory",
    # === HOPFIELD MEMORY ===
    "ModernHopfieldScaled",
    "ProgramLibrary",
    "ProgramLibraryConfig",
    # === PROGRAM LIBRARY (PRIMARY) ===
    "ResidualCatastropheProgramLibrary",
    "ResidualProgramConfig",
]
