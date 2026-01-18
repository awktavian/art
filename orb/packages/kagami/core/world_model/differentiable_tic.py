"""Differentiable Typed Intent Calculus (TIC) — Neural Receipt Dynamics.

CREATED: December 1, 2025

This module makes PLAN/EXECUTE/VERIFY differentiable by encoding TIC tuples
as tensors and learning receipt dynamics through the world model.

THEORETICAL FOUNDATION:
======================
Traditional TIC: τ = {E, P, Q, I, T} (symbolic)
    E = Effects (discrete: file_write, db_commit, ...)
    P = Preconditions (predicates)
    Q = Postconditions (predicates)
    I = Invariants (h(x) ≥ 0)
    T = Termination (fuel, ranking function)

Differentiable TIC: τ̃ = {ẽ, p̃, q̃, ĩ, t̃} (continuous)
    ẽ ∈ ℝ^D_effect     (effect embedding)
    p̃ ∈ [0,1]^N_pre    (precondition satisfaction scores)
    q̃ ∈ [0,1]^N_post   (postcondition satisfaction scores)
    ĩ ∈ ℝ^+            (invariant margin h(x) ≥ 0)
    t̃ ∈ [0,1]          (termination probability / fuel ratio)

RECEIPT DYNAMICS MODEL:
======================
The world model learns the transition:

    PLAN state:    s_plan = encode(TIC_plan)
    EXECUTE state: s_exec = RSSM(s_plan, action)
    VERIFY state:  s_verify = predict(s_exec)

    P(success | plan, action) = σ(decoder(s_verify))

This enables:
1. **Predictive Planning**: Simulate receipts before acting
2. **Counterfactual Learning**: Learn from receipt outcomes
3. **Gradient-Based Optimization**: Optimize actions for receipt success

INTEGRATION WITH CBF:
====================
Invariants I are directly connected to Control Barrier Functions:
    h(x) ≥ 0 (safety constraint)

The differentiable invariant margin ĩ = h(x) flows gradients for:
    - Learning what states are safe
    - Projecting actions onto safe set[Any] via QP

ARCHITECTURE:
=============
```
         TIC Tuple                   TIC Encoder                World Model
    ┌─────────────────┐          ┌─────────────────┐        ┌─────────────────┐
    │ E: effects      │──encode──│ ẽ: effect_emb   │        │                 │
    │ P: preconditions│──score───│ p̃: pre_scores  │───────►│ RSSM Dynamics   │
    │ Q: postconditions│─────────│ q̃: post_scores │        │ (h_t, z_t)      │
    │ I: invariants   │──CBF────►│ ĩ: h(x) margin  │        │                 │
    │ T: termination  │──fuel────│ t̃: fuel_ratio  │        └────────┬────────┘
    └─────────────────┘          └─────────────────┘                 │
                                                                     ▼
                                                              ┌─────────────────┐
                                                              │ Receipt Decoder │
                                                              │ P(success|state)│
                                                              └─────────────────┘
```
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, cast

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class DifferentiableTICConfig:
    """Configuration for Differentiable TIC."""

    # Dimensions
    effect_vocab_size: int = 64  # Number of known effects
    effect_embedding_dim: int = 32  # Effect embedding dimension
    max_preconditions: int = 8  # Max preconditions per TIC
    max_postconditions: int = 8  # Max postconditions per TIC
    max_invariants: int = 4  # Max invariants per TIC

    # RSSM integration (aligns to compressed nucleus sequence CLS embedding)
    state_dim: int = 64  # Matches SequenceIB bottleneck_dim
    hidden_dim: int = 128

    # Phase encoding
    num_phases: int = 3  # PLAN, EXECUTE, VERIFY
    phase_embedding_dim: int = 8

    # Learning
    temperature: float = 1.0  # Softmax temperature for predictions
    success_threshold: float = 0.5  # Threshold for success prediction


# =============================================================================
# EFFECT ENCODER
# =============================================================================


class EffectEncoder(nn.Module):
    """Encode discrete effects as continuous embeddings.

    Effects like "file_write", "db_commit" → learned embeddings.
    """

    # Known effects vocabulary
    KNOWN_EFFECTS = [
        "file_write",
        "file_read",
        "file_delete",
        "db_commit",
        "db_rollback",
        "db_query",
        "api_call",
        "api_response",
        "state_mutation",
        "config_change",
        "receipt_emission",
        "task_completion",
        "agent_spawn",
        "agent_terminate",
        "memory_write",
        "memory_read",
        "skill_execution",
        "goal_update",
        # Add more as needed
    ]

    def __init__(self, config: DifferentiableTICConfig):
        super().__init__()
        self.config = config

        # Build effect vocabulary
        self.effect_to_idx = {e: i for i, e in enumerate(self.KNOWN_EFFECTS)}
        self.effect_to_idx["<unk>"] = len(self.KNOWN_EFFECTS)
        self.effect_to_idx["<pad>"] = len(self.KNOWN_EFFECTS) + 1

        vocab_size = max(config.effect_vocab_size, len(self.effect_to_idx))

        # Learned embeddings
        self.embedding = nn.Embedding(vocab_size, config.effect_embedding_dim)

        # Aggregation (sum pooling over effects)
        self.aggregate = nn.Linear(config.effect_embedding_dim, config.effect_embedding_dim)

    def forward(self, effects: list[str]) -> torch.Tensor:
        """Encode list[Any] of effects to embedding.

        Args:
            effects: List of effect names

        Returns:
            [effect_embedding_dim] aggregated effect embedding
        """
        # Get device from embedding weights (FIXED: Dec 3, 2025)
        device = self.embedding.weight.device

        if not effects:
            # No effects → zero embedding (on correct device)
            return torch.zeros(self.config.effect_embedding_dim, device=device)

        # Convert to indices
        indices = []
        for e in effects:
            idx = self.effect_to_idx.get(e.lower(), self.effect_to_idx["<unk>"])
            indices.append(idx)

        idx_tensor = torch.tensor(indices, dtype=torch.long, device=device)

        # Get embeddings
        embeddings = self.embedding(idx_tensor)  # [num_effects, effect_dim]

        # Aggregate via mean + learned projection
        pooled = embeddings.mean(dim=0)  # [effect_dim]
        aggregated = self.aggregate(pooled)  # [effect_dim]

        return aggregated


# =============================================================================
# CONDITION ENCODER
# =============================================================================


class ConditionEncoder(nn.Module):
    """Encode preconditions/postconditions as satisfaction scores.

    Conditions like "energy > 0", "task_valid" → soft satisfaction in [0, 1].
    """

    def __init__(self, config: DifferentiableTICConfig, is_post: bool = False):
        super().__init__()
        self.config = config
        self.is_post = is_post
        self.max_conditions = config.max_postconditions if is_post else config.max_preconditions

        # Condition names are hashed to indices for embedding
        self.condition_embedding = nn.Embedding(256, config.hidden_dim // 4)

        # Satisfaction scorer (outputs logit)
        self.scorer = nn.Sequential(
            nn.Linear(config.hidden_dim // 4, config.hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(config.hidden_dim // 2, 1),
        )

    def forward(
        self,
        conditions: dict[str, Any],
        context: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Encode conditions to satisfaction scores.

        Args:
            conditions: Dict of condition_name → status (e.g., {"energy_check": "verified"})
            context: Optional context tensor [hidden_dim] for conditioning

        Returns:
            [max_conditions] satisfaction scores in [0, 1]
        """
        # Get device from embedding weights (FIXED: Dec 3, 2025)
        device = self.condition_embedding.weight.device

        scores = torch.zeros(self.max_conditions, device=device)

        for i, (name, status) in enumerate(conditions.items()):
            if i >= self.max_conditions:
                break

            # Hash condition name to index
            name_hash = hash(name) % 256
            name_idx = torch.tensor([name_hash], dtype=torch.long, device=device)

            # Get embedding
            emb = self.condition_embedding(name_idx).squeeze(0)  # [hidden_dim // 4]

            # Get satisfaction logit
            logit = self.scorer(emb).squeeze()

            # Apply sigmoid for [0, 1] score
            base_score = torch.sigmoid(logit)

            # Adjust based on actual status (supervision signal)
            if isinstance(status, str):
                if status in ("verified", "passed", "true", "success"):
                    scores[i] = base_score * 0.5 + 0.5  # Bias toward 1
                elif status in ("failed", "false", "error"):
                    scores[i] = base_score * 0.5  # Bias toward 0
                else:
                    scores[i] = base_score  # Neutral
            elif isinstance(status, bool):
                scores[i] = 1.0 if status else 0.0
            elif isinstance(status, (int, float)):
                scores[i] = float(torch.sigmoid(torch.tensor(float(status), device=device)))
            else:
                scores[i] = base_score

        return scores


# =============================================================================
# INVARIANT ENCODER (CBF INTEGRATION)
# =============================================================================


class InvariantEncoder(nn.Module):
    """Encode invariants as continuous safety margins h(x).

    Invariants like "h(x) >= 0" become differentiable CBF constraints.
    """

    def __init__(self, config: DifferentiableTICConfig):
        super().__init__()
        self.config = config

        # State encoder for computing h(x)
        self.state_to_barrier = nn.Sequential(
            nn.Linear(config.state_dim, config.hidden_dim),
            nn.ReLU(),
            nn.Linear(config.hidden_dim, config.max_invariants),
        )

        # Known invariant importance weights
        self.invariant_weights = nn.Parameter(torch.ones(config.max_invariants))

    def forward(
        self,
        state: torch.Tensor,
        invariant_names: list[str] | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Compute barrier function values for invariants.

        Args:
            state: Current state [batch, state_dim] or [state_dim]
            invariant_names: Optional list[Any] of invariant names

        Returns:
            (h_values, margin): Barrier values and minimum margin
                h_values: [max_invariants] raw CBF values
                margin: scalar, min(h_values) - safety margin
        """
        if state.dim() == 1:
            state = state.unsqueeze(0)

        # Compute barrier values
        h_values = self.state_to_barrier(state)  # [batch, max_invariants]

        # Weight by learned importance
        weighted_h = h_values * F.softplus(self.invariant_weights)

        # Safety margin is minimum value (all must be ≥ 0)
        margin = weighted_h.min(dim=-1).values  # [batch]

        return h_values.squeeze(0), margin.squeeze()

    def is_safe(self, state: torch.Tensor) -> bool:
        """Check if state satisfies all invariants.

        Args:
            state: Current state tensor

        Returns:
            True if h(x) ≥ 0 for all invariants
        """
        _, margin = self.forward(state)
        return margin.item() >= 0


# =============================================================================
# TERMINATION ENCODER
# =============================================================================


class TerminationEncoder(nn.Module):
    """Encode termination conditions as fuel ratio in [0, 1].

    Termination types:
    - bounded_fuel: fuel_remaining / fuel_limit
    - timeout: time_remaining / time_limit
    - ranking_function: learned termination predictor
    """

    def __init__(self, config: DifferentiableTICConfig):
        super().__init__()
        self.config = config

        # For ranking function prediction
        self.rank_predictor = nn.Sequential(
            nn.Linear(config.state_dim, config.hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(config.hidden_dim // 2, 1),
            nn.Sigmoid(),  # Output in [0, 1]
        )

    def forward(
        self,
        termination: dict[str, Any] | None,
        state: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Compute termination fuel ratio.

        Args:
            termination: Termination dict[str, Any] with type, fuel_limit, etc.
            state: Optional state for ranking function

        Returns:
            fuel_ratio in [0, 1] (1 = full fuel, 0 = terminated)
        """
        # Get device from model weights (FIXED: Dec 14, 2025 - proper type)
        device: torch.device = next(self.rank_predictor.parameters()).device

        if termination is None:
            return torch.tensor(1.0, device=device)  # No termination constraint

        term_type = termination.get("type", "bounded_fuel")

        if term_type == "bounded_fuel":
            fuel_limit = termination.get("fuel_limit", 1)
            fuel_used = termination.get("fuel_used", 0)
            if fuel_limit > 0:
                return torch.tensor(max(0.0, 1.0 - fuel_used / fuel_limit), device=device)
            return torch.tensor(1.0, device=device)

        elif term_type == "timeout":
            time_limit_ms = termination.get("time_limit_ms", 30000)
            time_elapsed_ms = termination.get("time_elapsed_ms", 0)
            if time_limit_ms > 0:
                return torch.tensor(max(0.0, 1.0 - time_elapsed_ms / time_limit_ms), device=device)
            return torch.tensor(1.0, device=device)

        elif term_type == "ranking_function":
            # Use learned predictor
            if state is not None:
                if state.dim() == 1:
                    state = state.unsqueeze(0)
                return self.rank_predictor(state).squeeze()
            return torch.tensor(0.5, device=device)  # Uncertain without state

        return torch.tensor(1.0, device=device)


# =============================================================================
# DIFFERENTIABLE TIC ENCODER
# =============================================================================


class DifferentiableTICEncoder(nn.Module):
    """Full encoder for Typed Intent Calculus → differentiable representation.

    Encodes TIC tuple[Any, ...] τ = {E, P, Q, I, T} into continuous tensor τ̃.
    """

    def __init__(self, config: DifferentiableTICConfig | None = None):
        super().__init__()
        self.config = config or DifferentiableTICConfig()

        # Component encoders
        self.effect_encoder = EffectEncoder(self.config)
        self.precondition_encoder = ConditionEncoder(self.config, is_post=False)
        self.postcondition_encoder = ConditionEncoder(self.config, is_post=True)
        self.invariant_encoder = InvariantEncoder(self.config)
        self.termination_encoder = TerminationEncoder(self.config)

        # Phase encoding
        self.phase_embedding = nn.Embedding(self.config.num_phases, self.config.phase_embedding_dim)

        # Combine all components into unified TIC embedding
        total_dim = (
            self.config.effect_embedding_dim
            + self.config.max_preconditions
            + self.config.max_postconditions
            + self.config.max_invariants
            + 1  # termination fuel
            + self.config.phase_embedding_dim
        )

        self.fusion = nn.Sequential(
            nn.Linear(total_dim, self.config.hidden_dim),
            nn.LayerNorm(self.config.hidden_dim),
            nn.ReLU(),
            nn.Linear(self.config.hidden_dim, self.config.state_dim),
        )

        logger.debug("DifferentiableTICEncoder initialized: output_dim=%d", self.config.state_dim)

    def forward(
        self,
        tic_data: dict[str, Any],
        phase: int = 0,  # 0=PLAN, 1=EXECUTE, 2=VERIFY
        state: torch.Tensor | None = None,
    ) -> dict[str, torch.Tensor]:
        """Encode TIC tuple[Any, ...] to differentiable representation.

        Args:
            tic_data: TIC dictionary with E, P, Q, I, T
            phase: Phase index (0=PLAN, 1=EXECUTE, 2=VERIFY)
            state: Optional current state for invariant computation

        Returns:
            Dict with:
                embedding: [state_dim] fused TIC embedding
                effect_emb: [effect_dim] effect embedding
                pre_scores: [max_pre] precondition scores
                post_scores: [max_post] postcondition scores
                h_values: [max_inv] invariant barrier values
                safety_margin: scalar CBF margin
                fuel_ratio: scalar termination fuel
        """
        # Get device from model weights (FIXED: Dec 14, 2025 - proper type)
        device: torch.device = next(self.fusion.parameters()).device

        # 1. Encode effects
        effects = tic_data.get("effects", [])
        effect_emb = self.effect_encoder(effects)

        # 2. Encode preconditions
        pre = tic_data.get("pre", {})
        pre_scores = self.precondition_encoder(pre)

        # 3. Encode postconditions
        post = tic_data.get("post", {})
        post_scores = self.postcondition_encoder(post)

        # 4. Encode invariants (using state if available)
        if state is None:
            state = torch.zeros(self.config.state_dim, device=device, dtype=torch.float32)
        invariant_names = tic_data.get("invariants", [])
        h_values, safety_margin = self.invariant_encoder(state, invariant_names)

        # 5. Encode termination
        termination = tic_data.get("termination")
        fuel_ratio = self.termination_encoder(termination, state)

        # 6. Phase embedding
        phase_idx = torch.tensor([phase], dtype=torch.long, device=device)
        phase_emb = self.phase_embedding(phase_idx).squeeze(0)

        # 7. Fuse all components
        combined = torch.cat(
            [
                effect_emb,
                pre_scores,
                post_scores,
                h_values,
                fuel_ratio.unsqueeze(0),
                phase_emb,
            ]
        )

        embedding = self.fusion(combined)

        return {
            "embedding": embedding,
            "effect_emb": effect_emb,
            "pre_scores": pre_scores,
            "post_scores": post_scores,
            "h_values": h_values,
            "safety_margin": safety_margin,
            "fuel_ratio": fuel_ratio,
            "phase": phase,
        }


# =============================================================================
# RECEIPT DYNAMICS MODEL
# =============================================================================


class ReceiptDynamicsModel(nn.Module):
    """RSSM-style dynamics for PLAN → EXECUTE → VERIFY.

    RSSM INTEGRATION (Dec 1, 2025):
    ==============================
    This module now shares latent space with the main RSSM dynamics:
    - Uses RSSMCore for state transitions when available
    - Falls back to internal GRU when RSSM not initialized
    - Receipt states live in H¹⁴ (same as RSSM z_t)

    Learns the transition:
        s_exec = f(s_plan, action)  # via shared RSSM
        s_verify = g(s_exec)
        P(success) = σ(h(s_verify))
    """

    def __init__(self, config: DifferentiableTICConfig | None = None):
        super().__init__()
        self.config = config or DifferentiableTICConfig()

        # TIC encoder
        self.tic_encoder = DifferentiableTICEncoder(self.config)

        # RSSM integration: ALWAYS use shared RSSM (Dec 7, 2025)
        # DELETED: plan_to_execute fallback GRU (26K params, 0% gradient)
        # RSSM provides PLAN→EXECUTE dynamics via shared latent space
        self._rssm_core: Any | None = None
        self._use_shared_rssm = False

        # EXECUTE → VERIFY dynamics (no RSSM equivalent)
        # This GRU handles the VERIFY phase which is TIC-specific
        self.execute_to_verify = nn.GRUCell(
            input_size=self.config.state_dim,
            hidden_size=self.config.state_dim,
        )

        # Projection from RSSM (h_t, z_t) to TIC state
        # RSSM has h_t (256D) + z_t (14D) = 270D → TIC state (14D)
        self.rssm_to_tic = nn.Linear(256 + 14, self.config.state_dim)

        # Projection from TIC state back to RSSM z_t
        self.tic_to_rssm = nn.Linear(self.config.state_dim, 14)

        # Success predictor (from VERIFY state)
        self.success_head = nn.Sequential(
            nn.Linear(self.config.state_dim, self.config.hidden_dim),
            nn.ReLU(),
            nn.Linear(self.config.hidden_dim, 1),
        )

        # Postcondition predictor (predict Q from VERIFY state)
        self.postcondition_head = nn.Sequential(
            nn.Linear(self.config.state_dim, self.config.hidden_dim),
            nn.ReLU(),
            nn.Linear(self.config.hidden_dim, self.config.max_postconditions),
            nn.Sigmoid(),
        )

        # Hopfield-E₈ Memory integration for receipt pattern storage
        self._hopfield_memory: Any | None = None
        self._use_hopfield = False

        logger.debug("ReceiptDynamicsModel initialized")

    def connect_rssm(self, rssm_core: Any) -> None:
        """Connect to shared RSSM core for unified latent space.

        Args:
            rssm_core: RSSMCore instance from world model
        """
        self._rssm_core = rssm_core
        self._use_shared_rssm = True
        logger.debug("ReceiptDynamicsModel connected to RSSM")

    def connect_hopfield_memory(self, hopfield_memory: Any) -> None:
        """Connect to Hopfield-E₈ Memory for geometric pattern storage.

        This enables:
        - Storing receipt embeddings as geometric patterns in E₈ lattice
        - Retrieving similar past receipts for transfer learning
        - Unified memory across TIC and world model

        Args:
            hopfield_memory: EpisodicMemory instance (256D values)
        """
        self._hopfield_memory = hopfield_memory
        self._use_hopfield = True
        logger.debug("ReceiptDynamicsModel connected to Hopfield memory")

    def store_receipt_pattern(
        self,
        receipt_embedding: torch.Tensor,
        success: bool,
    ) -> dict[str, Any]:
        """Store receipt embedding in Hopfield-E₈ Memory.

        The receipt pattern is stored at the E₈ root nearest to the
        embedding, enabling geometric retrieval of similar patterns.

        Args:
            receipt_embedding: TIC state embedding [state_dim]
            success: Whether the receipt was successful

        Returns:
            Dict with storage info (slot_idx, attention)
        """
        if not self._use_hopfield or self._hopfield_memory is None:
            return {"status": "no_hopfield"}

        # Ensure correct shape [1, query_dim]
        if receipt_embedding.dim() == 1:
            receipt_embedding = receipt_embedding.unsqueeze(0)

        # Create value to store: embedding + success flag
        value = torch.cat(
            [
                receipt_embedding.flatten(),
                torch.tensor([1.0 if success else 0.0]),
            ]
        )

        # Pad to value_dim if needed
        value_dim = self._hopfield_memory.config.value_dim
        if value.shape[-1] > value_dim:
            value = value[:value_dim]
        else:
            value = F.pad(value, (0, value_dim - value.shape[-1]))

        # Write to memory (key_state, content)
        result = self._hopfield_memory.write(
            key_state=receipt_embedding,
            content=value.unsqueeze(0),
        )

        return {
            "status": "stored",
            "slot_idx": result.get("slot_idx", -1),
            "attention_entropy": result.get("attention_entropy", 0.0),
        }

    def retrieve_similar_receipts(
        self,
        query_embedding: torch.Tensor,
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        """Retrieve similar past receipts from Hopfield-E₈ Memory.

        Uses the query embedding to find geometrically similar patterns
        in the E₈ lattice, enabling transfer learning from past experience.

        Args:
            query_embedding: Current TIC state [state_dim]
            top_k: Number of similar receipts to retrieve

        Returns:
            List of dicts with retrieved patterns
        """
        if not self._use_hopfield or self._hopfield_memory is None:
            return []

        # Ensure correct shape [1, query_dim]
        if query_embedding.dim() == 1:
            query_embedding = query_embedding.unsqueeze(0)

        # Retrieve from memory using read() method
        # Returns (content, attention) or (content, attention, energy)
        result = self._hopfield_memory.read(query=query_embedding)

        content = result[0]  # [B, value_dim]
        attention = result[1]  # [B, 240]

        # Get top-k attended slots
        top_k = min(top_k, attention.shape[-1])
        top_attention, top_indices = attention.topk(top_k, dim=-1)

        retrieved = []
        for k in range(top_k):
            slot_idx = top_indices[0, k].item()
            similarity = top_attention[0, k].item()

            # Content from this specific slot
            slot_content = content[0]  # Use blended content for now

            # Last element is success flag (if stored)
            success = slot_content[-1].item() > 0.5 if slot_content.numel() > 1 else True
            embedding = slot_content[:-1] if slot_content.numel() > 1 else slot_content

            retrieved.append(
                {
                    "embedding": embedding,
                    "success": success,
                    "similarity": similarity,
                    "slot_idx": slot_idx,
                }
            )

        return retrieved

    def rssm_state_to_tic(
        self,
        h: torch.Tensor,
        z: torch.Tensor,
    ) -> torch.Tensor:
        """Convert RSSM state (h_t, z_t) to TIC state.

        Args:
            h: Deterministic state [B, 256]
            z: Stochastic state [B, 14] (H¹⁴)

        Returns:
            TIC state [B, state_dim]
        """
        combined = torch.cat([h, z], dim=-1)
        return self.rssm_to_tic(combined)

    def tic_state_to_rssm_z(self, tic_state: torch.Tensor) -> torch.Tensor:
        """Convert TIC state back to RSSM z_t for imagination.

        Args:
            tic_state: TIC state [B, state_dim]

        Returns:
            z_t for RSSM [B, 14]
        """
        return self.tic_to_rssm(tic_state)

    def forward(
        self,
        plan_tic: dict[str, Any],
        action: torch.Tensor,
        initial_state: torch.Tensor | None = None,
        rssm_h: torch.Tensor | None = None,
        rssm_z: torch.Tensor | None = None,
    ) -> dict[str, torch.Tensor]:
        """Simulate PLAN → EXECUTE → VERIFY dynamics.

        RSSM INTEGRATION:
        =================
        If rssm_h and rssm_z are provided (or shared RSSM is connected),
        the TIC dynamics are grounded in the world model's latent space.
        This enables:
        - Consistent state representation across agents
        - Imagination using world model predictions
        - Unified training with world model losses

        Args:
            plan_tic: TIC data for PLAN phase
            action: Action tensor [8] (octonion)
            initial_state: Optional initial state for invariant computation
            rssm_h: Optional RSSM deterministic state [B, 256]
            rssm_z: Optional RSSM stochastic state [B, 14]

        Returns:
            Dict with:
                plan_state: Encoded PLAN state
                execute_state: Predicted EXECUTE state
                verify_state: Predicted VERIFY state
                success_prob: P(success | plan, action)
                predicted_post: Predicted postcondition scores
                rssm_z_out: Predicted z_t for RSSM (if using shared RSSM)
        """
        # Encode PLAN
        plan_encoded = self.tic_encoder(plan_tic, phase=0, state=initial_state)
        plan_state = plan_encoded["embedding"]

        if plan_state.dim() == 1:
            plan_state = plan_state.unsqueeze(0)

        # RSSM integration: blend TIC encoding with RSSM state
        if rssm_h is not None and rssm_z is not None:
            # Project RSSM state to TIC space
            rssm_contribution = self.rssm_state_to_tic(rssm_h, rssm_z)
            # Blend with TIC encoding (learned gate)
            plan_state = 0.5 * plan_state + 0.5 * rssm_contribution

        # Ensure action is right shape
        if action.dim() == 1:
            action = action.unsqueeze(0)
        if action.shape[-1] != 8:
            action = F.pad(action, (0, 8 - action.shape[-1]))

        # PLAN → EXECUTE transition
        # PERF FIX (Dec 4, 2025): Check for pre-computed execute states
        # If rssm_h and rssm_z are already POST-step (from forward pass),
        # we can skip the redundant rssm.step() call
        rssm_h_is_post_step = getattr(self, "_rssm_states_are_post_step", False)

        if rssm_h_is_post_step and rssm_h is not None and rssm_z is not None:
            # FAST PATH: Use pre-computed states (no extra rssm.step!)
            execute_state = self.rssm_state_to_tic(rssm_h, rssm_z)
        elif self._use_shared_rssm and self._rssm_core is not None:
            # Use shared RSSM for PLAN→EXECUTE dynamics
            # Convert TIC state to RSSM z
            z_plan = self.tic_state_to_rssm_z(plan_state)
            h_plan = (
                rssm_h
                if rssm_h is not None
                else torch.zeros(plan_state.shape[0], 256, device=plan_state.device)
            )

            # Ensure proper batch dimensions for OrganismRSSM.step
            if h_plan.dim() == 1:
                h_plan = h_plan.unsqueeze(0)
            if z_plan.dim() == 1:
                z_plan = z_plan.unsqueeze(0)

            # RSSM step (no fallback - RSSM must work)
            h_exec, z_exec, _ = self._rssm_core.step(h_plan, z_plan, action, obs=None, sample=False)

            # Convert back to TIC space
            execute_state = self.rssm_state_to_tic(h_exec, z_exec)
        else:
            # No RSSM connected - use simple linear projection as minimal dynamics
            # DELETED: plan_to_execute fallback GRU (was 26K params with 0% gradients)
            execute_state = plan_state + 0.1 * torch.tanh(action.mean()) * plan_state

        # EXECUTE → VERIFY transition
        verify_state = self.execute_to_verify(execute_state, execute_state)

        # Predict success probability
        success_logit = self.success_head(verify_state)
        success_prob = torch.sigmoid(success_logit / self.config.temperature)

        # Predict postconditions
        predicted_post = self.postcondition_head(verify_state)

        # Compute output z_t for RSSM integration
        rssm_z_out = self.tic_state_to_rssm_z(verify_state)

        return {
            "plan_state": plan_state.squeeze(0),
            "execute_state": execute_state.squeeze(0),
            "verify_state": verify_state.squeeze(0),
            "success_prob": success_prob.squeeze(),
            "predicted_post": predicted_post.squeeze(0),
            "plan_encoded": plan_encoded,
            "rssm_z_out": rssm_z_out.squeeze(0),
        }

    def compute_loss(
        self,
        plan_tic: dict[str, Any],
        action: torch.Tensor,
        actual_success: bool,
        actual_postconditions: dict[str, Any] | None = None,
    ) -> dict[str, torch.Tensor]:
        """Compute training loss for receipt dynamics.

        Args:
            plan_tic: TIC data for PLAN phase
            action: Action taken
            actual_success: Whether execution actually succeeded
            actual_postconditions: Actual postcondition outcomes

        Returns:
            Dict with loss components
        """
        # Forward pass
        result = self.forward(plan_tic, action)

        # Success prediction loss (BCE)
        target_success = torch.tensor(1.0 if actual_success else 0.0)
        success_loss = F.binary_cross_entropy(
            result["success_prob"],
            target_success,
        )

        # Postcondition prediction loss (if provided)
        post_loss = torch.tensor(0.0)
        if actual_postconditions:
            actual_post = self.tic_encoder.postcondition_encoder(actual_postconditions)
            post_loss = F.mse_loss(result["predicted_post"], actual_post)

        # CBF safety loss (penalize unsafe states)
        plan_encoded = cast(dict[str, torch.Tensor], result["plan_encoded"])
        safety_margin = plan_encoded["safety_margin"]
        safety_loss = F.relu(-safety_margin)  # Penalize h(x) < 0

        # Total loss
        total_loss = success_loss + 0.5 * post_loss + 0.1 * safety_loss

        return {
            "total": total_loss,
            "success": success_loss,
            "postcondition": post_loss,
            "safety": safety_loss,
        }


# =============================================================================
# SINGLETON ACCESS
# =============================================================================


_receipt_dynamics_model: ReceiptDynamicsModel | None = None


def get_receipt_dynamics_model() -> ReceiptDynamicsModel:
    """Get singleton ReceiptDynamicsModel instance."""
    global _receipt_dynamics_model
    if _receipt_dynamics_model is None:
        _receipt_dynamics_model = ReceiptDynamicsModel()
    return _receipt_dynamics_model


def reset_receipt_dynamics_model() -> None:
    """Reset the singleton."""
    global _receipt_dynamics_model
    _receipt_dynamics_model = None


__all__ = [
    "ConditionEncoder",
    "DifferentiableTICConfig",
    "DifferentiableTICEncoder",
    "EffectEncoder",
    "InvariantEncoder",
    "ReceiptDynamicsModel",
    "TerminationEncoder",
    "get_receipt_dynamics_model",
    "reset_receipt_dynamics_model",
]
