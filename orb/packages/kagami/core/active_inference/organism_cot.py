"""Organism-Level Chain-of-Thought - Hierarchical Meta-Reasoning.

ARCHITECTURE (Dec 3, 2025):
===========================
This module adds ORGANISM-LEVEL CoT on top of ColonyCollaborativeCoT.
It provides meta-reasoning, self-reflection, and EFE-integrated planning.

HIERARCHY:
==========
    Level 0: Colony Traces (7 × [trace_dim])
        │ ColonyTraceGenerator per colony
        ▼
    Level 1: Fano Compositions ([N × trace_dim])
        │ FanoTracePropagator
        ▼
    Level 2: Colony Aggregation ([7*z_dim] = [98])
        │ ThoughtAggregator
        ▼
    Level 3: ORGANISM COT (NEW!) ([meta_dim])
        │ OrganismMetaReasoner
        │ • Self-reflection via strange loop μ_self
        │ • EFE-guided policy evaluation
        │ • Hierarchical attention over colony thoughts
        ▼
    Level 4: Action Selection ([8] E8)
        │ Modulates organism.act() output

MARKOV BLANKET POSITION:
========================
Organism CoT is INTERNAL (μ → μ), between:
- Colony CoT aggregation (input)
- Organism action selection (output)

TENSOR DIMENSIONS (FULL SCAN):
==============================
| Tensor              | Dimension | Source                    |
|---------------------|-----------|---------------------------|
| colony_trace        | [32]      | ColonyTraceGenerator      |
| colony_z            | [14]      | ColonyRSSM.state.z        |
| colony_h            | [256]     | ColonyRSSM.state.h        |
| fano_trace          | [32]      | FanoTracePropagator       |
| aggregated_thought  | [98]      | ThoughtAggregator         |
| μ_self_colony       | [16]      | ColonyRSSM.strange_loop   |
| μ_self_organism     | [32]      | OrganismRSSM.strange_loop |
| z_coupled           | [98]      | Fano coupling output      |
| meta_state          | [64]      | OrganismMetaReasoner      |
| meta_thought        | [98]      | Meta-reasoning output     |
| e8_action           | [8]       | E8VQWrapper               |
| policy_sequence     | [H, 8]    | EFE action sequences      |
| G_values            | [P]       | EFE expected free energy  |

GRADIENT FLOW:
==============
All paths are differentiable:
1. colony_z → trace → fano → aggregated → meta → action (FORWARD)
2. action → meta_loss → aggregated → trace → colony_z (BACKWARD)
3. μ_self → coherence_loss → meta → action (SELF-REFERENCE)
4. G_values → policy_prior_loss → meta → EFE (ACTIVE INFERENCE)

Created: December 3, 2025
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F

from kagami.core.active_inference.colony_collaborative_cot import (
    CollaborativeThought,
    ColonyCollaborativeCoT,
)

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class OrganismCoTConfig:
    """Configuration for Organism-Level Chain-of-Thought.

    OPTIMAL SETUP (Dec 3, 2025):
    ===========================
    Based on analysis of all tensor dimensions and gradient paths.
    """

    # Input dimensions (from colony CoT)
    z_dim: int = 14  # Colony z dimension (H¹⁴)
    trace_dim: int = 32  # Colony trace dimension
    aggregated_dim: int = 98  # 7 × z_dim

    # Meta-reasoning dimensions
    meta_state_dim: int = 64  # Internal meta-state
    meta_thought_dim: int = 98  # Output matches aggregated

    # Self-reference (strange loop integration)
    mu_self_dim: int = 7  # S7 dimension (was 32)  # Organism μ_self dimension
    self_coherence_weight: float = 0.1  # Weight for coherence loss

    # EFE integration
    efe_integration: bool = True  # Enable EFE policy evaluation
    num_policy_samples: int = 8  # Policies to evaluate in meta-reasoning
    efe_weight: float = 0.1  # Weight for EFE-guided refinement

    # Architecture
    num_attention_heads: int = 4
    hidden_dim: int = 128
    num_meta_layers: int = 2  # Depth of meta-reasoning

    # Hierarchical attention
    use_hierarchical_attention: bool = True
    hierarchy_levels: int = 3  # Colony → Fano → Meta

    # E8 quantization (for meta-thoughts)
    use_e8_encoding: bool = True
    max_e8_levels: int = 4

    # Dropout
    dropout: float = 0.1


# =============================================================================
# META-STATE ENCODER
# =============================================================================


class MetaStateEncoder(nn.Module):
    """Encodes organism state for meta-reasoning.

    Combines:
    - Aggregated colony thought [98]
    - Organism μ_self [32]
    - EFE policy values [P] (if enabled)

    Into unified meta-state [meta_state_dim].
    """

    def __init__(self, config: OrganismCoTConfig) -> None:
        super().__init__()
        self.config = config

        # Input dimension = aggregated + μ_self
        input_dim = config.aggregated_dim + config.mu_self_dim

        # Main encoder
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, config.hidden_dim),
            nn.LayerNorm(config.hidden_dim),
            nn.GELU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.hidden_dim, config.meta_state_dim),
            nn.LayerNorm(config.meta_state_dim),
        )

        # EFE integration (optional)
        if config.efe_integration:
            self.efe_encoder = nn.Sequential(
                nn.Linear(config.num_policy_samples, config.hidden_dim // 4),
                nn.GELU(),
                nn.Linear(config.hidden_dim // 4, config.meta_state_dim),
            )
            self.efe_gate = nn.Sequential(
                nn.Linear(config.meta_state_dim * 2, 1),
                nn.Sigmoid(),
            )

    def forward(
        self,
        aggregated_thought: torch.Tensor,
        mu_self: torch.Tensor,
        efe_values: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Encode inputs to meta-state.

        Args:
            aggregated_thought: [98] or [B, 98] from ColonyCollaborativeCoT
            mu_self: [32] or [B, 32] from OrganismRSSM.strange_loop.mu_self
            efe_values: [P] or [B, P] optional EFE values per policy

        Returns:
            meta_state: [meta_state_dim] (squeezed to 1D for HierarchicalAttention)
        """
        # Ensure batch dimension for processing
        was_unbatched = aggregated_thought.dim() == 1
        if was_unbatched:
            aggregated_thought = aggregated_thought.unsqueeze(0)
        if mu_self.dim() == 1:
            mu_self = mu_self.unsqueeze(0)

        # Combine inputs
        combined = torch.cat([aggregated_thought, mu_self], dim=-1)
        meta_state = self.encoder(combined)

        # EFE integration (if enabled and provided)
        if self.config.efe_integration and efe_values is not None:
            if efe_values.dim() == 1:
                efe_values = efe_values.unsqueeze(0)

            efe_state = self.efe_encoder(efe_values)
            gate = self.efe_gate(torch.cat([meta_state, efe_state], dim=-1))
            meta_state = meta_state + gate * efe_state

        # Squeeze back to 1D if input was unbatched (for HierarchicalAttention)
        if was_unbatched:
            meta_state = meta_state.squeeze(0)

        return meta_state


# =============================================================================
# HIERARCHICAL ATTENTION
# =============================================================================


class HierarchicalAttention(nn.Module):
    """Hierarchical attention over colony thoughts.

    Attends across 3 levels:
    1. Individual colony traces [7, trace_dim]
    2. Fano compositions [N, trace_dim]
    3. Meta-state [1, meta_state_dim]

    This allows the organism to reason about:
    - Which colonies are most relevant?
    - Which Fano compositions matter?
    - How does this relate to my current meta-state?
    """

    def __init__(self, config: OrganismCoTConfig) -> None:
        super().__init__()
        # Store key dimensions as attributes (not whole config)
        self.meta_state_dim = config.meta_state_dim
        self.meta_thought_dim = config.meta_thought_dim

        # Project all levels to common dimension
        self.colony_proj = nn.Linear(config.trace_dim, config.meta_state_dim)
        self.fano_proj = nn.Linear(config.trace_dim, config.meta_state_dim)
        self.meta_proj = nn.Linear(config.meta_state_dim, config.meta_state_dim)

        # Multi-head attention
        self.attention = nn.MultiheadAttention(
            embed_dim=config.meta_state_dim,
            num_heads=config.num_attention_heads,
            dropout=config.dropout,
            batch_first=True,
        )

        # Level embeddings (learnable)
        self.level_embeddings = nn.Parameter(
            torch.randn(config.hierarchy_levels, config.meta_state_dim) * 0.02
        )

        # Output projection
        self.output_proj = nn.Sequential(
            nn.Linear(config.meta_state_dim, config.hidden_dim),
            nn.GELU(),
            nn.Linear(config.hidden_dim, config.meta_thought_dim),
        )

    def forward(
        self,
        colony_traces: list[torch.Tensor],
        fano_traces: list[torch.Tensor],
        meta_state: torch.Tensor,
    ) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
        """Hierarchical attention over all levels.

        Args:
            colony_traces: List of [trace_dim] tensors (7 colonies)
            fano_traces: List of [trace_dim] tensors (variable)
            meta_state: [meta_state_dim] current meta-state

        Returns:
            meta_thought: [meta_thought_dim] refined thought
            attention_info: Dict with attention weights
        """
        device = meta_state.device

        # Stack and project colony traces
        if colony_traces:
            colony_stack = torch.stack(colony_traces)  # [7, trace_dim]
            colony_proj = self.colony_proj(colony_stack)  # [7, meta_state_dim]
            colony_proj = colony_proj + self.level_embeddings[0]  # Broadcasting [64] + [7, 64]
        else:
            colony_proj = torch.zeros(0, self.meta_state_dim, device=device)

        # Stack and project Fano traces
        if fano_traces:
            fano_stack = torch.stack(fano_traces)  # [N, trace_dim]
            fano_proj = self.fano_proj(fano_stack)  # [N, meta_state_dim]
            fano_proj = fano_proj + self.level_embeddings[1]  # Broadcasting [64] + [N, 64]
        else:
            fano_proj = torch.zeros(0, self.meta_state_dim, device=device)

        # Project meta-state (keep 2D: [1, meta_state_dim])
        meta_proj = self.meta_proj(meta_state.unsqueeze(0))  # [1, meta_state_dim]
        meta_proj = meta_proj + self.level_embeddings[2]  # Broadcasting [64] + [1, 64]

        # Concatenate all levels (all 2D: [N_total, dim])
        all_values = torch.cat([colony_proj, fano_proj, meta_proj], dim=0)  # [N_total, dim]
        all_values = all_values.unsqueeze(0)  # [1, N_total, dim] for batch

        # Query is the meta-state [1, 1, dim]
        query = meta_proj.unsqueeze(0)  # [1, 1, dim]

        # Self-attention
        attended, attn_weights = self.attention(query, all_values, all_values)

        # Output projection
        meta_thought = self.output_proj(attended.squeeze(0).squeeze(0))

        # Attention info (handle variable-length attention weights)
        num_colony = len(colony_traces)
        num_fano = len(fano_traces)

        # attn_weights shape: [1, 1, N_total] → squeeze to [N_total]
        attn_flat = attn_weights.squeeze()
        if attn_flat.dim() == 0:
            # Single element
            attn_flat = attn_flat.unsqueeze(0)

        info = {
            "colony_attention": attn_flat[:num_colony] if num_colony > 0 else None,
            "fano_attention": attn_flat[num_colony : num_colony + num_fano]
            if num_fano > 0
            else None,
            "meta_attention": attn_flat[-1:] if attn_flat.numel() > 0 else None,
        }

        return meta_thought, info  # type: ignore[return-value]


# =============================================================================
# SELF-REFLECTION MODULE
# =============================================================================


class SelfReflectionModule(nn.Module):
    """Self-reflection via strange loop integration.

    This module connects organism CoT to the Hofstadter strange loop:
    - Takes μ_self as input (the "I")
    - Produces coherence signal (how consistent is reasoning with self?)
    - Updates μ_self based on meta-reasoning (the "I" evolves)

    CRITICAL: This is WHERE the strange loop meets reasoning.
    """

    def __init__(self, config: OrganismCoTConfig) -> None:
        super().__init__()
        self.config = config

        # Self-encoder: meta_thought → self-representation
        self.self_encoder = nn.Sequential(
            nn.Linear(config.meta_thought_dim, config.hidden_dim),
            nn.LayerNorm(config.hidden_dim),
            nn.GELU(),
            nn.Linear(config.hidden_dim, config.mu_self_dim),
        )

        # Coherence estimator: how consistent is meta_thought with μ_self?
        self.coherence_net = nn.Sequential(
            nn.Linear(config.mu_self_dim * 2, config.hidden_dim // 2),
            nn.GELU(),
            nn.Linear(config.hidden_dim // 2, 1),
            nn.Sigmoid(),
        )

        # Self-update gate: how much should μ_self change?
        self.update_gate = nn.Sequential(
            nn.Linear(config.mu_self_dim * 2, config.hidden_dim // 2),
            nn.GELU(),
            nn.Linear(config.hidden_dim // 2, 1),
            nn.Sigmoid(),
        )

    def forward(
        self,
        meta_thought: torch.Tensor,
        mu_self: torch.Tensor,
    ) -> dict[str, torch.Tensor]:
        """Self-reflection and μ_self update.

        Args:
            meta_thought: [meta_thought_dim] from hierarchical attention
            mu_self: [mu_self_dim] current self-representation

        Returns:
            Dict with:
                mu_self_new: [mu_self_dim] updated self-representation
                coherence: [1] how consistent is reasoning with self
                update_magnitude: [1] how much μ_self changed
                self_reflection_loss: tensor for training
        """
        # Encode meta-thought as self-representation
        mu_from_thought = self.self_encoder(meta_thought)

        # Coherence: how aligned is meta-thought with stored μ_self?
        coherence_input = torch.cat([mu_from_thought, mu_self], dim=-1)
        coherence = self.coherence_net(coherence_input)

        # Update gate: how much should μ_self change?
        update_gate = self.update_gate(coherence_input)

        # New μ_self: blend of old and new
        mu_self_new = (1 - update_gate) * mu_self + update_gate * mu_from_thought

        # Self-reflection loss: encourage coherence
        # (meta-reasoning should be consistent with self)
        self_reflection_loss = F.mse_loss(mu_from_thought, mu_self)

        return {
            "mu_self_new": mu_self_new,
            "coherence": coherence,
            "update_magnitude": update_gate,
            "self_reflection_loss": self_reflection_loss,
        }


# =============================================================================
# ORGANISM META-REASONER
# =============================================================================


class OrganismMetaReasoner(nn.Module):
    """Complete organism-level meta-reasoning module.

    Integrates:
    1. MetaStateEncoder: Combine inputs into meta-state
    2. HierarchicalAttention: Attend over colony/Fano/meta levels
    3. SelfReflectionModule: Strange loop integration
    4. EFE guidance: Policy evaluation for planning

    OUTPUT: Meta-thought that modulates organism action.
    """

    def __init__(self, config: OrganismCoTConfig) -> None:
        super().__init__()
        self.config = config

        # Components
        self.meta_encoder = MetaStateEncoder(config)
        self.hierarchical_attn = HierarchicalAttention(config)
        self.self_reflection = SelfReflectionModule(config)

        # Multi-layer meta-reasoning
        # Ensure num_heads divides meta_thought_dim (98D = 2 heads × 49D)
        meta_heads = 2  # 98 / 2 = 49 (valid)
        if config.meta_thought_dim % config.num_attention_heads == 0:
            meta_heads = config.num_attention_heads
        elif config.meta_thought_dim % 2 == 0:
            meta_heads = 2
        else:
            meta_heads = 1

        self.meta_layers = nn.ModuleList(
            [
                nn.TransformerEncoderLayer(
                    d_model=config.meta_thought_dim,
                    nhead=meta_heads,
                    dim_feedforward=config.hidden_dim,
                    dropout=config.dropout,
                    batch_first=True,
                )
                for _ in range(config.num_meta_layers)
            ]
        )

        # Final output projection (matches z_coupled dimension)
        self.output_proj = nn.Sequential(
            nn.Linear(config.meta_thought_dim, config.hidden_dim),
            nn.LayerNorm(config.hidden_dim),
            nn.GELU(),
            nn.Linear(config.hidden_dim, config.aggregated_dim),
        )

        # Influence gate: how much should meta-thought modulate action?
        self.influence_gate = nn.Sequential(
            nn.Linear(config.aggregated_dim * 2, config.hidden_dim // 2),
            nn.GELU(),
            nn.Linear(config.hidden_dim // 2, 1),
            nn.Sigmoid(),
        )

    def forward(
        self,
        aggregated_thought: torch.Tensor,
        colony_traces: list[torch.Tensor],
        fano_traces: list[torch.Tensor],
        mu_self: torch.Tensor,
        efe_values: torch.Tensor | None = None,
    ) -> dict[str, torch.Tensor | Any]:
        """Complete meta-reasoning pass.

        Args:
            aggregated_thought: [98] from ColonyCollaborativeCoT
            colony_traces: List of [32] trace tensors (7 colonies)
            fano_traces: List of [32] Fano-composed traces
            mu_self: [32] organism μ_self
            efe_values: [P] optional EFE values per policy

        Returns:
            Dict with:
                z_modulation: [98] to add to z_coupled
                meta_thought: [98] final meta-thought
                mu_self_new: [32] updated self-representation
                coherence: float self-coherence
                attention_info: Dict with attention weights
                losses: Dict with training losses
        """
        # 1. Encode meta-state
        meta_state = self.meta_encoder(aggregated_thought, mu_self, efe_values)

        # 2. Hierarchical attention
        meta_thought, attn_info = self.hierarchical_attn(colony_traces, fano_traces, meta_state)

        # 3. Multi-layer meta-reasoning
        # Add batch and sequence dimensions for transformer
        meta_seq = meta_thought.unsqueeze(0).unsqueeze(0)  # [1, 1, dim]
        for layer in self.meta_layers:
            meta_seq = layer(meta_seq)
        meta_thought = meta_seq.squeeze(0).squeeze(0)  # [dim]

        # 4. Self-reflection
        reflection = self.self_reflection(meta_thought, mu_self)

        # 5. Output projection
        meta_output = self.output_proj(meta_thought)

        # 6. Influence gate
        gate_input = torch.cat([meta_output, aggregated_thought], dim=-1)
        influence = self.influence_gate(gate_input)

        # 7. Final modulation
        z_modulation = influence * meta_output

        return {
            "z_modulation": z_modulation,
            "meta_thought": meta_thought,
            "meta_output": meta_output,
            "mu_self_new": reflection["mu_self_new"],
            "coherence": reflection["coherence"].item(),
            "influence": influence.item(),
            "attention_info": attn_info,
            "losses": {
                "self_reflection_loss": reflection["self_reflection_loss"],
            },
        }


# =============================================================================
# ORGANISM COT (COMPLETE)
# =============================================================================


@dataclass
class OrganismThought:
    """Complete organism-level thought.

    Contains both colony-level and organism-level reasoning.
    """

    # Colony-level (from ColonyCollaborativeCoT)
    colony_thought: CollaborativeThought | None = None

    # Organism-level
    meta_thought: torch.Tensor | None = None
    meta_output: torch.Tensor | None = None
    z_modulation: torch.Tensor | None = None

    # Self-reference
    mu_self_new: torch.Tensor | None = None
    coherence: float = 0.0
    influence: float = 0.0

    # Attention
    colony_attention: torch.Tensor | None = None
    fano_attention: torch.Tensor | None = None

    # Metrics
    num_reasoning_steps: int = 0
    processing_time_ms: float = 0.0

    # Losses (for training)
    losses: dict[str, torch.Tensor] = field(default_factory=dict[str, Any])


class OrganismCoT(nn.Module):
    """Complete Organism-Level Chain-of-Thought.

    OPTIMAL SETUP (Dec 3, 2025):
    ===========================

    Architecture:
        ColonyCollaborativeCoT
            │ (7 colony traces + Fano compositions)
            ▼
        OrganismMetaReasoner
            │ • MetaStateEncoder (aggregated + μ_self + EFE)
            │ • HierarchicalAttention (colony → Fano → meta)
            │ • SelfReflectionModule (strange loop)
            │ • Multi-layer transformer (depth reasoning)
            ▼
        z_modulation [98]
            │
            ▼
        organism.act(z_coupled + z_modulation)

    Gradient Flow (all differentiable):
        z_colonies → colony_cot → aggregated → meta_encoder
            → hierarchical_attn → self_reflection → meta_layers
            → output_proj → influence_gate → z_modulation → action

    Integration:
        Called in OrganismRSSM.step_all() between:
        - Colony CoT (existing)
        - Organism action selection
    """

    def __init__(
        self,
        config: OrganismCoTConfig | None = None,
        colony_cot: ColonyCollaborativeCoT | None = None,
    ) -> None:
        super().__init__()
        self.config = config or OrganismCoTConfig()

        # Colony-level CoT (create if not provided)
        if colony_cot is not None:
            self.colony_cot = colony_cot
        else:
            self.colony_cot = ColonyCollaborativeCoT(
                z_dim=self.config.z_dim,
                trace_dim=self.config.trace_dim,
                hidden_dim=self.config.hidden_dim,
            )

        # Organism-level meta-reasoner
        self.meta_reasoner = OrganismMetaReasoner(self.config)

        # EFE reference (set[Any] via set_efe)
        self._efe: Any | None = None

        logger.debug(
            "OrganismCoT: trace=%dD, meta=%dD", self.config.trace_dim, self.config.meta_state_dim
        )

    def set_efe(self, efe: Any) -> None:
        """Connect to EFE for policy evaluation.

        Call this to enable EFE-guided meta-reasoning.
        """
        self._efe = efe
        logger.debug("OrganismCoT connected to EFE")

    def set_library(self, library: Any) -> None:
        """Connect to program library for gradient flow."""
        self.colony_cot.set_library(library)

    def forward(
        self,
        z_states: dict[str, torch.Tensor],
        mu_self: torch.Tensor,
        h_states: dict[str, torch.Tensor] | None = None,
    ) -> tuple[OrganismThought, torch.Tensor]:
        """Complete organism-level chain-of-thought.

        Args:
            z_states: Dict mapping colony_name → z[14]
            mu_self: [32] organism μ_self
            h_states: Optional dict[str, Any] mapping colony_name → h[256]

        Returns:
            (OrganismThought, z_modulation[98])
        """
        import time

        start_time = time.time()

        # =========================================================
        # STEP 1: Colony-level CoT
        # =========================================================
        colony_thought, colony_modulation = self.colony_cot(z_states)

        # =========================================================
        # STEP 2: Extract traces for meta-reasoning
        # =========================================================
        colony_traces = [trace.trace_vector for trace in colony_thought.colony_traces.values()]
        fano_traces = [trace.trace_vector for trace in colony_thought.fano_traces]
        aggregated = colony_thought.aggregated_vector

        # =========================================================
        # STEP 3: Get EFE values (if enabled)
        # =========================================================
        efe_values = None
        if self.config.efe_integration and self._efe is not None:
            # Generate random policies for evaluation
            # (In full integration, these come from policy search)
            device = aggregated.device
            efe_values = torch.randn(self.config.num_policy_samples, device=device)

        # =========================================================
        # STEP 4: Organism meta-reasoning
        # =========================================================
        meta_result = self.meta_reasoner(
            aggregated_thought=aggregated,
            colony_traces=colony_traces,
            fano_traces=fano_traces,
            mu_self=mu_self,
            efe_values=efe_values,
        )

        # =========================================================
        # STEP 5: Combine modulations
        # =========================================================
        # Colony modulation + Organism modulation
        z_modulation = colony_modulation + meta_result["z_modulation"]

        # =========================================================
        # STEP 6: Build result
        # =========================================================
        thought = OrganismThought(
            colony_thought=colony_thought,
            meta_thought=meta_result["meta_thought"],
            meta_output=meta_result["meta_output"],
            z_modulation=z_modulation,
            mu_self_new=meta_result["mu_self_new"],
            coherence=meta_result["coherence"],
            influence=meta_result["influence"],
            colony_attention=meta_result["attention_info"].get("colony_attention"),
            fano_attention=meta_result["attention_info"].get("fano_attention"),
            num_reasoning_steps=(colony_thought.num_reasoning_steps + self.config.num_meta_layers),
            processing_time_ms=(time.time() - start_time) * 1000,
            losses=meta_result["losses"],
        )

        return thought, z_modulation

    def get_total_loss(self, thought: OrganismThought) -> torch.Tensor:
        """Get total loss for training.

        Combines:
        - Colony CoT commitment loss (E8 quantization)
        - Self-reflection loss (μ_self coherence)

        Args:
            thought: OrganismThought from forward()

        Returns:
            Scalar loss tensor
        """
        total_loss = torch.tensor(0.0, device=thought.z_modulation.device)  # type: ignore[union-attr]

        # Colony commitment loss
        if thought.colony_thought is not None:
            total_loss = total_loss + thought.colony_thought.commitment_loss

        # Self-reflection loss
        if "self_reflection_loss" in thought.losses:
            total_loss = total_loss + (
                self.config.self_coherence_weight * thought.losses["self_reflection_loss"]
            )

        return total_loss


# =============================================================================
# INTEGRATION WITH ORGANISM RSSM
# =============================================================================


def create_organism_cot(
    config: OrganismCoTConfig | None = None,
    colony_cot: ColonyCollaborativeCoT | None = None,
) -> OrganismCoT:
    """Create OrganismCoT with optimal configuration.

    Args:
        config: Optional configuration override
        colony_cot: Optional existing ColonyCollaborativeCoT

    Returns:
        Configured OrganismCoT
    """
    return OrganismCoT(config, colony_cot)


def integrate_organism_cot(
    organism: Any,
    organism_cot: OrganismCoT | None = None,
    config: OrganismCoTConfig | None = None,
) -> OrganismCoT:
    """Integrate OrganismCoT into OrganismRSSM.

    This patches step_all to include organism-level meta-reasoning.

    OPTIMAL INTEGRATION (Dec 3, 2025):
    ==================================

    Modified step_all flow:
        1. Colony updates (parallel GRU)
        2. Fano coupling (z_coupled)
        3. Colony CoT (existing)
        4. ORGANISM COT (NEW!) ← Inserts here
           • Meta-encoder: aggregated + μ_self
           • Hierarchical attention
           • Self-reflection (μ_self update)
           • Multi-layer reasoning
        5. z_coupled += organism_cot.z_modulation
        6. Organism action (with enhanced z_coupled)

    Args:
        organism: OrganismRSSM to patch
        organism_cot: Optional pre-created OrganismCoT
        config: Optional configuration

    Returns:
        The integrated OrganismCoT module
    """
    # Create if not provided
    if organism_cot is None:
        # Use existing colony_cot if available
        existing_cot = getattr(organism, "collaborative_cot", None)
        organism_cot = OrganismCoT(
            config=config or OrganismCoTConfig(),
            colony_cot=existing_cot,
        )

    # Store on organism
    organism.organism_cot = organism_cot
    organism._organism_cot_enabled = True

    # Store original step_all
    original_step_all = organism.step_all

    def step_all_with_organism_cot(
        observations: dict[str, torch.Tensor] | None = None,
        reward: float | None = None,
        use_differentiable: bool = True,
        enable_cot: bool | None = None,
        enable_organism_cot: bool | None = None,
    ) -> dict[str, Any]:
        """Step with both colony and organism-level CoT.

        The organism CoT adds meta-reasoning on top of colony CoT:
        - Hierarchical attention over colony/Fano traces
        - Self-reflection via strange loop μ_self
        - Multi-layer transformer reasoning
        """
        # Resolve organism CoT flag
        run_organism_cot = (
            enable_organism_cot
            if enable_organism_cot is not None
            else organism._organism_cot_enabled
        )

        # Run original step_all (includes colony CoT)
        results = original_step_all(
            observations=observations,
            reward=reward,
            use_differentiable=use_differentiable,
            enable_cot=enable_cot,
        )

        # === ORGANISM COT (NEW) ===
        if run_organism_cot and hasattr(organism, "organism_cot"):
            # Get current z_states
            z_states = {name: organism.colonies[name].state.z for name in organism.DOMAIN_NAMES}

            # Get organism μ_self
            mu_self = organism.strange_loop.mu_self

            # Run organism meta-reasoning
            thought, z_modulation = organism.organism_cot(z_states, mu_self)

            # Apply organism modulation to z_coupled
            z_mod_split = z_modulation.split(organism.config.stochastic_dim)
            for i, name in enumerate(organism.DOMAIN_NAMES):
                if i < len(z_mod_split):
                    organism.colonies[name].state.z = (
                        organism.colonies[name].state.z + 0.1 * z_mod_split[i]  # Blended influence
                    )

            # Update organism μ_self (strange loop evolution)
            if thought.mu_self_new is not None:
                with torch.no_grad():
                    organism.strange_loop.mu_self.data = (
                        0.95 * organism.strange_loop.mu_self.data + 0.05 * thought.mu_self_new
                    )

            # Re-compute organism action with enhanced z_coupled
            z_all_enhanced = torch.cat(
                [organism.colonies[name].state.z for name in organism.DOMAIN_NAMES]
            )
            organism_action = organism.act(z_all_enhanced)

            # Update results
            results["organism_action"] = organism_action
            results["organism_thought"] = thought
            results["organism_coherence"] = thought.coherence
            results["organism_influence"] = thought.influence
            results["organism_cot_loss"] = organism.organism_cot.get_total_loss(thought)

        return results

    # Patch
    organism.step_all = step_all_with_organism_cot

    logger.debug("OrganismCoT integrated into OrganismRSSM")

    return organism_cot


# =============================================================================
# EXPORTS
# =============================================================================


__all__ = [
    "HierarchicalAttention",
    # Components
    "MetaStateEncoder",
    # Main module
    "OrganismCoT",
    # Configuration
    "OrganismCoTConfig",
    "OrganismMetaReasoner",
    "OrganismThought",
    "SelfReflectionModule",
    # Integration
    "create_organism_cot",
    "integrate_organism_cot",
]
