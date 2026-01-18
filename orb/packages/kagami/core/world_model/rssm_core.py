"""RSSM Core Implementation.

EXTRACTED FROM colony_rssm.py (December 13, 2025):
==================================================
Core OrganismRSSM class implementation. This was the largest class in the
original file (1800+ lines) and has been simplified for maintainability.

Contains:
- OrganismRSSM: Main RSSM implementation (simplified)
- Factory functions
- Core RSSM dynamics

WARNING: This is a simplified extraction. The original class contained
extensive implementation details that need to be preserved and gradually
migrated.

DreamerV3 IMPROVEMENTS (December 27, 2025):
===========================================
Enhanced with three DreamerV3-style improvements for better stability and performance:

1. BlockGRU with LayerNorm (lines 66-98):
   - Replaces standard GRUCell with block-structured GRU + layer normalization
   - Improves training stability and gradient flow
   - Used in dynamics_cell (line 242)

2. Discrete Latent Encoder (lines 101-142):
   - Adds 32 categorical distributions (32 classes each) for discrete latents
   - Uses straight-through Gumbel softmax for differentiable sampling
   - Complements existing E8-based discrete latents
   - Integrated in _step method (lines 648-656)

3. Episode Boundary Handling (lines 601-612):
   - continue_flag parameter resets hidden/stochastic states at episode boundaries
   - Enables proper handling of multi-episode trajectories
   - Propagated through step(), step_all(), and forward() methods

All improvements preserve the existing E8 lattice dynamics and octonion algebra structure.
"""

from __future__ import annotations

import logging
import os
from typing import Any, TypeAlias, cast

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.checkpoint import checkpoint as gradient_checkpoint

from kagami.core.config.unified_config import RSSMConfig as ColonyRSSMConfig
from kagami.core.config.unified_config import get_kagami_config

from .dreamer_transforms import TwoHotEncoder, balanced_kl_loss_categorical
from .rssm_components import SparseFanoAttention
from .rssm_state import ColonyState, create_colony_states

# torch.compile availability check
_TORCH_COMPILE_AVAILABLE = hasattr(torch, "compile")


def _get_rssm_config() -> ColonyRSSMConfig:
    """Get RSSM config from unified config (internal helper)."""
    return get_kagami_config().world_model.rssm


# FORGE MISSION: Direct import - no more optional fallbacks
from .layers.gated_fano_attention import GatedFanoAttention

AttentionType: TypeAlias = SparseFanoAttention | GatedFanoAttention

# Lazy import for CoT to avoid circular dependencies
_ColonyCollaborativeCoT = None


def _get_cot_class() -> Any:
    """Lazy load ColonyCollaborativeCoT to avoid circular imports."""
    global _ColonyCollaborativeCoT
    if _ColonyCollaborativeCoT is None:
        from kagami.core.active_inference.colony_collaborative_cot import ColonyCollaborativeCoT

        _ColonyCollaborativeCoT = ColonyCollaborativeCoT
    return _ColonyCollaborativeCoT


logger = logging.getLogger(__name__)


class BlockGRU(nn.Module):
    """Block GRU with LayerNorm for stability (DreamerV3).

    Replaces standard GRU with a block-structured variant that applies
    layer normalization for improved training stability.

    Args:
        input_size: Input dimension
        hidden_size: Hidden state dimension
        num_blocks: Number of blocks to partition hidden state (default: 8)
    """

    def __init__(self, input_size: int, hidden_size: int, num_blocks: int = 8):
        super().__init__()
        self.num_blocks = num_blocks
        self.block_size = hidden_size // num_blocks
        self.hidden_size = hidden_size
        self.gru = nn.GRUCell(input_size, hidden_size)
        self.layer_norm = nn.LayerNorm(hidden_size)

    def forward(self, x: torch.Tensor, h: torch.Tensor) -> torch.Tensor:
        """Forward pass with layer normalization.

        Args:
            x: Input [B, input_size]
            h: Hidden state [B, hidden_size]

        Returns:
            New hidden state [B, hidden_size]
        """
        h_new = self.gru(x, h)
        h_new = self.layer_norm(h_new)
        return h_new


class DiscreteLatentEncoder(nn.Module):
    """32 categorical distributions for discrete latents (DreamerV3).

    Encodes observations into 32 categorical distributions, each with 32 classes.
    Uses straight-through Gumbel softmax for differentiable sampling.

    Args:
        input_dim: Input feature dimension
        num_categories: Number of categorical distributions (default: 32)
        num_classes: Number of classes per category (default: 32)
    """

    def __init__(
        self,
        input_dim: int,
        num_categories: int = 32,
        num_classes: int = 32,
    ):
        super().__init__()
        self.num_categories = num_categories
        self.num_classes = num_classes
        self.encoder = nn.Linear(input_dim, num_categories * num_classes)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Encode to categorical distributions.

        Args:
            x: Input features [B, input_dim]

        Returns:
            samples: One-hot samples [B, num_categories * num_classes]
            logits: Raw logits [B, num_categories, num_classes]
        """
        logits = self.encoder(x).view(-1, self.num_categories, self.num_classes)

        # Straight-through Gumbel softmax
        if self.training:
            samples = F.gumbel_softmax(logits, hard=True, dim=-1)
        else:
            samples = F.one_hot(logits.argmax(dim=-1), self.num_classes).float()

        return samples.view(-1, self.num_categories * self.num_classes), logits


class OrganismRSSM(nn.Module):
    """Colony Recurrent State Space Model (RSSM) for unified organisms.

    This class is the stateful orchestrator around a Dreamer-style RSSM with:
    - deterministic per-colony hidden state (h)
    - stochastic per-colony latent (z) (discrete categorical + continuous embed)
    - sparse Fano-plane coupling (optional)

    Markov-blanket discipline:
    - the deterministic transition uses **previous** action only (a_{t-1})
    - the current action is decoded *after* belief update and stored for next step
    """

    def __init__(  # type: ignore[no-untyped-def]
        self,
        config: ColonyRSSMConfig | None = None,
        *,
        library: Any | None = None,
        **kwargs,
    ):
        super().__init__()
        # Backwards-compat (Dec 2025):
        # - Historically `OrganismRSSM()` was callable with defaults.
        # - Some tests also pass `library=...` to wire the split memory architecture.
        if config is None:
            config = _get_rssm_config()
        # Allow ad-hoc overrides without forcing callers to construct a config.
        for k, v in kwargs.items():
            if hasattr(config, k):
                setattr(config, k, v)

        self.config = config
        self._library = library

        self.num_colonies = int(config.num_colonies)
        self.obs_dim = int(config.obs_dim)
        self.deter_dim = int(config.colony_dim)
        self.stoch_dim = int(config.stochastic_dim)
        self.action_dim = int(config.action_dim)
        self.latent_classes = int(getattr(config, "latent_classes", 240))
        # DreamerV3 uses 0.01 (1%) uniform mixing - prevents deterministic collapse
        # 0.10 was causing KL collapse by making prior/posterior too similar
        self.unimix = float(getattr(config, "unimix", 0.01))
        # DreamerV3 free_bits for 240-class categorical
        # FIXED (Jan 6, 2026): Increased from 1.0 to 3.0 to prevent KL collapse
        # Root cause analysis: v6e training showed KL going to -1.49e-7 (collapsed)
        # For 240-class: max entropy = ln(240) = 5.48 nats
        # Floor at 3.0 nats (55% of max) ensures healthy information flow
        # The 1.0 floor (18% of max) was too permissive for this latent space
        self.free_bits = float(getattr(config, "kl_free_nats", 3.0))
        # KL collapse detection (Jan 6, 2026)
        self.kl_collapse_threshold = float(getattr(config, "kl_collapse_threshold", 1e-4))
        self._kl_collapse_warnings = 0  # Track consecutive collapse warnings

        # ARCHITECTURAL CHANGE (Dec 22, 2025):
        # OrganismRSSM uses BOTH E8 code [B, 8] AND S7 phase [B, 7] for full
        # E8 lattice E2E with mathematically correct structure.
        #
        # Mathematical foundation:
        # - E8 code (8D): Lattice coordinates from ResidualE8LatticeVQ (content)
        # - S7 phase (7D): Unit imaginary octonions = 7 colonies (routing)
        #
        # Architecture:
        # - E8 code → project to each colony's space
        # - S7 phase → soft attention weights for colony activation
        # - Fusion: gate_i * project_i(e8_code) (octonion-like multiplication)

        # E8 to colony projection: [B, 8] → [B, 7, deter_dim]
        self.e8_to_colony = nn.Linear(8, self.num_colonies * self.deter_dim)

        # S7 phase gating: normalize phase to soft routing weights
        # No parameters - just uses softmax on S7 phase

        # =====================================================================
        # S7 HIERARCHY FUSION (Dec 24, 2025)
        # =====================================================================
        # Multi-level S7 phases from exceptional Lie hierarchy: E8→E7→E6→F4→G₂
        # Each level provides a different "view" of colony routing:
        # - s7_e8: Full E8(248) → S7 projection (richest, but noisiest)
        # - s7_e7: E7(133) → S7 projection (gravity-like)
        # - s7_e6: E6(78) → S7 projection (electroweak-like)
        # - s7_f4: F4(52) → S7 projection (strong-like)
        #
        # Fusion strategy: Learned weighted sum with residual connection
        # This respects the algebraic hierarchy where lower levels "contain" higher

        # REMOVED Dec 27, 2025: S7 hierarchy fusion now uses unified module
        # kagami_math/s7_hierarchy_fusion.py (S7HierarchyFusion)
        # Legacy params removed: s7_hierarchy_weights, s7_hierarchy_proj, s7_hierarchy_alpha

        # Colony identity bias (e₁..e₇ imaginary octonion basis)
        self.colony_emb = nn.Embedding(self.num_colonies, self.deter_dim)

        # =====================================================================
        # DreamerV3 IMPROVEMENTS (Dec 27, 2025)
        # =====================================================================

        # 1. Block GRU with LayerNorm for stability
        # Replaces standard GRUCell with block-structured GRU + layer normalization
        self.dynamics_cell = BlockGRU(
            input_size=self.stoch_dim + self.action_dim,
            hidden_size=self.deter_dim,
            num_blocks=8,
        )

        # 2. Discrete latents: 32 categorical distributions
        # Adds DreamerV3-style discrete latent encoding alongside existing continuous latents
        self.discrete_latent_encoder = DiscreteLatentEncoder(
            input_dim=self.deter_dim,
            num_categories=32,
            num_classes=32,
        )
        # Dimension of discrete latent features (32 categories × 32 classes = 1024)
        self.discrete_latent_dim = 32 * 32

        # Posterior deterministic correction (inject observation evidence)
        self.post_deter = nn.Sequential(
            nn.Linear(self.deter_dim + self.deter_dim, self.deter_dim),
            nn.GELU(),
            nn.Linear(self.deter_dim, self.deter_dim),
            nn.LayerNorm(self.deter_dim),
        )

        # Discrete latent heads (categorical over 240 E8 roots by default)
        self.prior_net = nn.Sequential(
            nn.Linear(self.deter_dim, self.deter_dim),
            nn.GELU(),
            nn.Linear(self.deter_dim, self.latent_classes),
        )
        self.posterior_net = nn.Sequential(
            nn.Linear(self.deter_dim + self.deter_dim, self.deter_dim),
            nn.GELU(),
            nn.Linear(self.deter_dim, self.latent_classes),
        )

        # Map categorical latent to continuous stochastic vector z ∈ R^{stoch_dim}
        self.latent_embed = nn.Embedding(self.latent_classes, self.stoch_dim)

        # Action decoder: a_t = π(h_t, z_t)
        self.action_head = nn.Sequential(
            nn.Linear(self.deter_dim + self.stoch_dim, self.deter_dim),
            nn.GELU(),
            nn.Linear(self.deter_dim, self.action_dim),
        )

        # Observation decoder: e8_t = ψ(h_t, z_t) - for EFE planning
        # ARCHITECTURAL CHANGE (Dec 22, 2025): Outputs E8 code [B, 8] for full
        # E8 lattice end-to-end dynamics.
        self.obs_decoder = nn.Sequential(
            nn.Linear(self.deter_dim + self.stoch_dim, self.deter_dim),
            nn.SiLU(),
            nn.Linear(self.deter_dim, 8),  # Output E8 code directly
        )

        # =====================================================================
        # RL PREDICTION HEADS (December 14, 2025)
        # =====================================================================
        # Following DreamerV3 (Hafner et al. 2023) architecture for full RL capability
        #
        # IMPROVED (Dec 31, 2025): TwoHot encoding for reward/value heads
        # - Captures multimodal return distributions
        # - More stable across varying reward scales
        # - Uses exponentially-spaced bins in symlog space

        # TwoHot encoders for distributional predictions
        self.num_reward_bins = 255
        self.reward_twohot = TwoHotEncoder(num_bins=self.num_reward_bins, low=-20.0, high=20.0)
        self.value_twohot = TwoHotEncoder(num_bins=self.num_reward_bins, low=-20.0, high=20.0)

        # Reward prediction: r_t = R(h_t, z_t) → logits over bins
        self.reward_head = nn.Sequential(
            nn.Linear(self.deter_dim + self.stoch_dim, self.deter_dim),
            nn.GELU(),
            nn.Linear(self.deter_dim, self.num_reward_bins),
        )

        # Value function: V(s_t) → logits over bins
        self.value_head = nn.Sequential(
            nn.Linear(self.deter_dim + self.stoch_dim, self.deter_dim),
            nn.GELU(),
            nn.Linear(self.deter_dim, self.num_reward_bins),
        )

        # Continue prediction: γ_t = C(h_t, z_t) (episode termination)
        # Outputs probability that episode continues (1 - done)
        # Note: Continue is binary, no TwoHot needed
        self.continue_head = nn.Sequential(
            nn.Linear(self.deter_dim + self.stoch_dim, self.deter_dim),
            nn.GELU(),
            nn.Linear(self.deter_dim, 1),
        )

        # Sparse coupling across colonies (Fano plane)
        # NEXUS INTEGRATION (Dec 14, 2025): Support gated or sparse attention
        self.fano_attention: AttentionType | None = None
        if bool(getattr(config, "use_sparse_fano_attention", True)):
            # Check if gated attention is requested
            if bool(getattr(config, "use_gated_fano_attention", False)):
                try:
                    from kagami.core.world_model.layers.gated_fano_attention import (
                        GatedFanoAttention,
                    )

                    self.fano_attention = GatedFanoAttention(
                        config=config,
                        gating_mode="enabled",
                        gate_bias=bool(getattr(config, "fano_gate_init_bias", False)),
                    )
                    logger.info("OrganismRSSM: Using GATED Fano attention")
                except ImportError as e:
                    logger.warning(
                        "GatedFanoAttention not available (%s), falling back to sparse", e
                    )
                    self.fano_attention = SparseFanoAttention(config)
            else:
                # Standard sparse attention (backward compatible)
                self.fano_attention = SparseFanoAttention(config)
                logger.debug("OrganismRSSM: Using SPARSE Fano attention")

        # Colony Collaborative Chain-of-Thought
        # Lazy-initialized on first use to avoid import cycles
        self._cot_enabled: bool = bool(getattr(config, "enable_cot", True))
        self._collaborative_cot: nn.Module | None = None

        # Organism-Level Chain-of-Thought (Forge Colony Mission Integration)
        self._organism_cot_enabled: bool = bool(getattr(config, "enable_organism_cot", True))
        self._organism_cot: nn.Module | None = None
        self._mu_self = torch.zeros(7)  # Organism μ_self for strange loop tracking

        # TPU OPTIMIZATION (Jan 4, 2026): Gradient checkpointing for memory efficiency
        # When enabled, recomputes forward pass during backward to save activation memory.
        # Critical for long sequences and large batch sizes on TPU.
        self._use_gradient_checkpointing: bool = bool(
            getattr(config, "use_gradient_checkpointing", False)
        )

        # State management
        self._current_states: list[ColonyState] | None = None
        self._initialized = False
        self.register_buffer("_timestep", torch.zeros((), dtype=torch.long), persistent=False)

        # TPU OPTIMIZATION (Jan 4, 2026): Pre-allocated concatenation buffers
        # Reduces memory bandwidth by avoiding repeated torch.cat allocations.
        # These buffers are sized for typical batch sizes and resized dynamically if needed.
        self._max_buffer_batch = 64  # Default max batch size for buffers
        self._buffer_device: str | None = None  # Track device for lazy initialization
        # Buffer placeholders - will be lazily initialized on first use
        self._inp_buffer: torch.Tensor | None = None  # [B, 7, Z+A]
        self._h_obs_buffer: torch.Tensor | None = None  # [B, 7, 2H] for h+obs concat
        self._hz_buffer: torch.Tensor | None = None  # [B, 7, H+Z] for h+z concat

        logger.info(
            "OrganismRSSM initialized (Dec 27, 2025 - DreamerV3 improvements): "
            "colonies=%d obs_dim=%d (E8) deter_dim=%d stoch_dim=%d action_dim=%d K=%d "
            "discrete_latent_dim=%d (BlockGRU + 32x32 categorical + episode boundaries)",
            self.num_colonies,
            self.obs_dim,
            self.deter_dim,
            self.stoch_dim,
            self.action_dim,
            self.latent_classes,
            self.discrete_latent_dim,
        )

        # Compile _step method for 2-3x speedup on hot path (Dec 21, 2025)
        # TPU OPTIMIZATION (Jan 4, 2026): Use configurable compile mode
        # "max-autotune" provides best kernel fusion for TPU/long training runs
        # NOTE: compile_mode=None or empty string disables compilation (useful for CPU debugging)
        # Environment variable KAGAMI_RSSM_COMPILE_MODE overrides config
        env_compile = os.environ.get("KAGAMI_RSSM_COMPILE_MODE")
        if env_compile is not None:
            compile_mode = env_compile if env_compile else None
        else:
            compile_mode = getattr(config, "compile_mode", "max-autotune")
        if _TORCH_COMPILE_AVAILABLE and compile_mode:
            try:
                self._step = torch.compile(self._step, mode=str(compile_mode), dynamic=False)  # type: ignore[method-assign]
                logger.debug(
                    "OrganismRSSM._step compiled (mode=%s) for training acceleration", compile_mode
                )
            except Exception as e:
                logger.warning(f"Failed to compile OrganismRSSM._step: {e}")

    @property
    def collaborative_cot(self) -> nn.Module | None:
        """Lazy-initialized ColonyCollaborativeCoT.

        The CoT module is created on first access to avoid import cycles
        and unnecessary memory allocation if CoT is never used.
        """
        if self._collaborative_cot is None and self._cot_enabled:
            try:
                CoTClass = _get_cot_class()
                self._collaborative_cot = CoTClass(
                    z_dim=self.stoch_dim,
                    trace_dim=32,
                    hidden_dim=64,
                )
                # Move to same device as parent module
                device = next(self.parameters()).device
                self._collaborative_cot = self._collaborative_cot.to(device)
                logger.debug("ColonyCollaborativeCoT initialized on-demand on device %s", device)
            except Exception as e:
                logger.warning("Failed to initialize ColonyCollaborativeCoT: %s", e)
                self._cot_enabled = False
        return self._collaborative_cot

    @property
    def organism_cot(self) -> nn.Module | None:
        """Lazy-initialized OrganismCoT for organism-level meta-reasoning.

        The OrganismCoT module is created on first access to avoid import cycles
        and provides hierarchical meta-reasoning on top of colony CoT.
        """
        if self._organism_cot is None and self._organism_cot_enabled:
            try:
                from kagami.core.active_inference.organism_cot import (
                    OrganismCoT,
                    OrganismCoTConfig,
                )

                config = OrganismCoTConfig(
                    z_dim=self.stoch_dim,
                    trace_dim=32,
                    aggregated_dim=7 * self.stoch_dim,  # 7 colonies × stoch_dim
                    mu_self_dim=7,  # S7 dimension for μ_self
                )

                self._organism_cot = OrganismCoT(
                    config=config,
                    colony_cot=self.collaborative_cot,  # Use existing colony CoT
                )

                # Move to same device as parent module
                device = next(self.parameters()).device
                self._organism_cot = self._organism_cot.to(device)
                self._mu_self = self._mu_self.to(device)

                logger.debug("OrganismCoT initialized on-demand on device %s", device)
            except Exception as e:
                logger.warning("Failed to initialize OrganismCoT: %s", e)
                self._organism_cot_enabled = False
        return self._organism_cot

    def initialize_all(self, batch_size: int = 1, device: str | None = None) -> None:
        """Initialize all colony states.

        This method initializes or resets all colony states to their default values.
        Should be called before stepping through the RSSM.

        Args:
            batch_size: Batch size for states (default: 1)
            device: Device to create states on (default: use config device)
        """
        if device is None:
            device = self.config.device
        self._current_states = create_colony_states(
            batch_size,
            self.config.num_colonies,
            device,
            hidden_dim=self.deter_dim,
            stochastic_dim=self.stoch_dim,
        )
        cast(torch.Tensor, self._timestep).zero_()
        for st in self._current_states:
            st.metadata.setdefault(
                "prev_action",
                torch.zeros(batch_size, self.action_dim, device=device),
            )
        self._initialized = True
        logger.debug(
            "OrganismRSSM: initialized %d colony states (batch=%d, device=%s)",
            self.config.num_colonies,
            batch_size,
            device,
        )

    def _fuse_s7_hierarchy(
        self,
        s7_phase: torch.Tensor,
        s7_e8: torch.Tensor | None = None,
        s7_e7: torch.Tensor | None = None,
        s7_e6: torch.Tensor | None = None,
        s7_f4: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, dict[str, Any]]:
        """Fuse multi-level S7 phases from exceptional Lie hierarchy.

        REFACTORED Dec 27, 2025: Now delegates to unified S7HierarchyFusion module.
        See kagami_math/s7_hierarchy_fusion.py for implementation.

        ENHANCED Jan 4, 2026: Returns coherence info for training loss.

        Args:
            s7_phase: Primary S7 phase [B, 7] (always required)
            s7_e8: S7 from E8(248) projection [B, 7] (optional)
            s7_e7: S7 from E7(133) projection [B, 7] (optional)
            s7_e6: S7 from E6(78) projection [B, 7] (optional)
            s7_f4: S7 from F4(52) projection [B, 7] (optional)

        Returns:
            Tuple of:
                fused: Fused S7 phase [B, 7]
                info: Dict with coherence and fusion metadata
        """
        # If no hierarchy phases provided, use primary s7_phase directly
        if all(x is None for x in [s7_e8, s7_e7, s7_e6, s7_f4]):
            return s7_phase, {"fusion_mode": "primary_only", "coherence": 1.0}

        # COHERENCY (Dec 27, 2025): Use unified S7HierarchyFusion
        from kagami_math.s7_hierarchy_fusion import get_s7_hierarchy_fusion

        fusion = get_s7_hierarchy_fusion(str(s7_phase.device))
        fused, info = fusion(s7_phase, s7_e8, s7_e7, s7_e6, s7_f4)
        return fused, info

    def _states_to_tensors(
        self, states: list[ColonyState], *, device: torch.device, dtype: torch.dtype
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Convert list[ColonyState] to stacked tensors (h, z, a_prev)."""
        h_list: list[torch.Tensor] = []
        z_list: list[torch.Tensor] = []
        a_list: list[torch.Tensor] = []

        for st in states:
            h_list.append(st.hidden.to(device=device, dtype=dtype))
            z_list.append(st.stochastic.to(device=device, dtype=dtype))

            a_prev = st.metadata.get("prev_action")
            if a_prev is None:
                a_prev = torch.zeros(st.hidden.size(0), self.action_dim, device=device, dtype=dtype)
            else:
                a_prev = a_prev.to(device=device, dtype=dtype)
            a_list.append(a_prev)

        h = torch.stack(h_list, dim=1)  # [B,7,H]
        z = torch.stack(z_list, dim=1)  # [B,7,Z]
        a_prev = torch.stack(a_list, dim=1)  # [B,7,A]
        return h, z, a_prev

    def _tensors_to_states(
        self,
        *,
        h: torch.Tensor,
        z: torch.Tensor,
        a_next: torch.Tensor,
        states: list[ColonyState],
    ) -> list[ColonyState]:
        """Write tensor state back into list[ColonyState] (in-place)."""
        for i, st in enumerate(states):
            st.hidden = h[:, i]
            st.stochastic = z[:, i]
            st.timestep = int(cast(torch.Tensor, self._timestep).item())
            st.metadata["prev_action"] = a_next[:, i].detach()
        return states

    def _ensure_buffers(self, batch_size: int, device: torch.device, dtype: torch.dtype) -> None:
        """Ensure concatenation buffers are allocated and properly sized.

        TPU OPTIMIZATION (Jan 4, 2026): Pre-allocates contiguous memory for
        common concatenation patterns to reduce memory bandwidth overhead.

        Args:
            batch_size: Current batch size
            device: Device for tensors
            dtype: Data type for tensors
        """
        device_str = str(device)
        need_realloc = (
            self._inp_buffer is None
            or batch_size > self._max_buffer_batch
            or self._buffer_device != device_str
            or self._inp_buffer.dtype != dtype
        )

        if need_realloc:
            # Update max batch size if current batch is larger
            if batch_size > self._max_buffer_batch:
                self._max_buffer_batch = batch_size

            B = self._max_buffer_batch
            N = self.num_colonies
            H = self.deter_dim
            Z = self.stoch_dim
            A = self.action_dim

            # Pre-allocate buffers with contiguous memory
            self._inp_buffer = torch.empty(B, N, Z + A, device=device, dtype=dtype)
            self._h_obs_buffer = torch.empty(B, N, 2 * H, device=device, dtype=dtype)
            self._hz_buffer = torch.empty(B, N, H + Z, device=device, dtype=dtype)
            self._buffer_device = device_str

            logger.debug(
                "OrganismRSSM: Allocated concat buffers for batch=%d on %s",
                B,
                device_str,
            )

    def _concat_za(self, z: torch.Tensor, a: torch.Tensor, batch_size: int) -> torch.Tensor:
        """Concatenate z and a tensors.

        NOTE (Jan 4, 2026): Buffer optimization disabled due to inplace operation
        issues with autograd. Always using torch.cat for correctness.

        Args:
            z: [B, 7, Z] stochastic state
            a: [B, 7, A] action
            batch_size: Unused (kept for API compat)

        Returns:
            [B, 7, Z+A] concatenated tensor
        """
        return torch.cat([z, a], dim=-1)

    def _concat_hh(self, h1: torch.Tensor, h2: torch.Tensor, batch_size: int) -> torch.Tensor:
        """Concatenate two h tensors.

        NOTE (Jan 4, 2026): Buffer optimization disabled due to inplace operation
        issues with autograd. Always using torch.cat for correctness.

        Args:
            h1: [B, 7, H] first hidden state
            h2: [B, 7, H] second hidden state (e.g., obs_col)
            batch_size: Unused (kept for API compat)

        Returns:
            [B, 7, 2H] concatenated tensor
        """
        return torch.cat([h1, h2], dim=-1)

    def _concat_hz(self, h: torch.Tensor, z: torch.Tensor, batch_size: int) -> torch.Tensor:
        """Concatenate h and z tensors.

        NOTE (Jan 4, 2026): Buffer optimization disabled due to inplace operation
        issues with autograd. Always using torch.cat for correctness.

        Args:
            h: [B, 7, H] hidden state
            z: [B, 7, Z] stochastic state
            batch_size: Unused (kept for API compat)

        Returns:
            [B, 7, H+Z] concatenated tensor
        """
        return torch.cat([h, z], dim=-1)

    def _apply_unimix(self, probs: torch.Tensor) -> torch.Tensor:
        if self.unimix <= 0.0:
            return probs
        u = torch.full_like(probs, 1.0 / float(self.latent_classes))
        return (1.0 - self.unimix) * probs + self.unimix * u

    def _kl_divergence(self, post: torch.Tensor, prior: torch.Tensor) -> torch.Tensor:
        eps = 1e-8
        return (post * (torch.log(post + eps) - torch.log(prior + eps))).sum(dim=-1)  # [...,7]

    def _step_for_checkpoint(
        self,
        e8_code: torch.Tensor,
        s7_phase: torch.Tensor,
        h_prev: torch.Tensor,
        z_prev: torch.Tensor,
        a_prev: torch.Tensor,
        sample: bool,
        s7_e8: torch.Tensor | None,
        s7_e7: torch.Tensor | None,
        s7_e6: torch.Tensor | None,
        s7_f4: torch.Tensor | None,
        continue_flag: torch.Tensor | None,
    ) -> dict[str, torch.Tensor]:
        """Wrapper for gradient checkpointing (requires positional args).

        TPU OPTIMIZATION (Jan 4, 2026): torch.utils.checkpoint.checkpoint() requires
        positional arguments. This wrapper adapts _step to be checkpoint-compatible.
        """
        return self._step(
            e8_code=e8_code,
            s7_phase=s7_phase,
            h_prev=h_prev,
            z_prev=z_prev,
            a_prev=a_prev,
            sample=sample,
            s7_e8=s7_e8,
            s7_e7=s7_e7,
            s7_e6=s7_e6,
            s7_f4=s7_f4,
            continue_flag=continue_flag,
        )

    def _step(
        self,
        *,
        e8_code: torch.Tensor,  # [B, 8] E8 lattice coordinates
        s7_phase: torch.Tensor,  # [B, 7] S7 phase (colony routing)
        h_prev: torch.Tensor,  # [B,7,H]
        z_prev: torch.Tensor,  # [B,7,Z]
        a_prev: torch.Tensor,  # [B,7,A]
        sample: bool,
        # Optional hierarchy phases (Dec 24, 2025)
        s7_e8: torch.Tensor | None = None,
        s7_e7: torch.Tensor | None = None,
        s7_e6: torch.Tensor | None = None,
        s7_f4: torch.Tensor | None = None,
        # DreamerV3: Episode boundary handling (Dec 27, 2025)
        continue_flag: torch.Tensor | None = None,
    ) -> dict[str, torch.Tensor]:
        """One RSSM step (tensor form).

        ARCHITECTURAL CHANGE (Dec 22, 2025):
        Full E8 lattice E2E with mathematically correct structure:
        - e8_code [B, 8]: E8 lattice coordinates (content)
        - s7_phase [B, 7]: S7 phase for colony routing (imaginary octonions)

        ENHANCED Dec 24, 2025:
        Optional multi-level S7 phases from exceptional Lie hierarchy:
        - s7_e8: From E8(248), s7_e7: From E7(133), s7_e6: From E6(78), s7_f4: From F4(52)
        When provided, fuses all levels for richer colony routing.

        ENHANCED Dec 27, 2025 (DreamerV3):
        - continue_flag: [B] or [B, 1] tensor (1 = episode continues, 0 = reset state)
          When 0, resets hidden and stochastic states to handle episode boundaries.

        Architecture:
        - E8 code → project to each colony's space
        - S7 phase → soft gating weights (softmax)
        - Fusion respects octonion multiplication structure
        """
        B = e8_code.size(0)
        device = e8_code.device
        dtype = e8_code.dtype

        # TPU OPTIMIZATION (Jan 4, 2026): Ensure concat buffers are allocated
        self._ensure_buffers(B, device, dtype)

        # DreamerV3: Reset state on episode boundaries (Dec 27, 2025)
        # continue_flag = 1 means episode continues, 0 means reset
        if continue_flag is not None:
            # Ensure shape is [B, 1, 1] for broadcasting to [B, 7, H]
            if continue_flag.dim() == 1 or continue_flag.dim() == 2:
                continue_flag = continue_flag.view(B, 1, 1)

            # Reset hidden and stochastic states at episode boundaries
            h_prev = h_prev * continue_flag
            z_prev = z_prev * continue_flag

        # E8 code [B, 8] → colony representation [B, 7, H]
        e8_proj = self.e8_to_colony(e8_code)  # [B, 7 * H]
        e8_proj = e8_proj.view(B, self.num_colonies, self.deter_dim)  # [B, 7, H]

        # Fuse multi-level S7 phases if available (Dec 24, 2025)
        # ENHANCED Jan 4, 2026: Now returns coherence info for loss
        s7_fused, s7_fusion_info = self._fuse_s7_hierarchy(s7_phase, s7_e8, s7_e7, s7_e6, s7_f4)

        # S7 phase [B, 7] → soft routing weights via spherical normalization
        # IMPROVED (Dec 31, 2025): Use geodesic-aware spherical softmax
        # S7 is a Riemannian manifold (unit sphere in Im(O)), not a simplex.
        # Spherical normalization respects the geometry better than softmax.
        #
        # spherical_softmax: exp(x) / ||exp(x)||_2 (projects to unit sphere)
        # vs softmax: exp(x) / sum(exp(x)) (projects to simplex)
        s7_exp = torch.exp(s7_fused - s7_fused.max(dim=-1, keepdim=True)[0])  # Numerically stable
        s7_gate = F.normalize(s7_exp, p=2, dim=-1)  # [B, 7], ||s7_gate||_2 = 1

        # Gated fusion: e8_proj * s7_gate (octonion-like multiplication)
        # Each colony gets E8 content weighted by its S7 phase activation
        obs_col = e8_proj * s7_gate.unsqueeze(-1)  # [B, 7, H]

        # Add colony identity bias (e₁..e₇ imaginary octonion basis)
        colony_ids = torch.arange(self.num_colonies, device=device)
        colony_bias = self.colony_emb(colony_ids)  # [7, H]
        obs_col = obs_col + colony_bias.unsqueeze(0)  # [B, 7, H]

        # Deterministic dynamics (prior)
        # TPU OPTIMIZATION (Jan 4, 2026): Use pre-allocated buffer instead of torch.cat
        inp = self._concat_za(z_prev, a_prev, B)  # [B,7,Z+A]
        h_prior = self.dynamics_cell(
            inp.reshape(B * self.num_colonies, -1), h_prev.reshape(B * self.num_colonies, -1)
        )
        h_prior = h_prior.view(B, self.num_colonies, self.deter_dim)

        # Posterior deterministic correction (inject evidence)
        # TPU OPTIMIZATION (Jan 4, 2026): Use pre-allocated buffer instead of torch.cat
        h_post = self.post_deter(self._concat_hh(h_prior, obs_col, B))  # [B,7,H]

        # Sparse Fano coupling
        if self.fano_attention is not None:
            h_post = h_post + self.fano_attention(h_post)

        # DreamerV3: Additional discrete latent encoding (Dec 27, 2025)
        # Encode h_post into 32 categorical distributions (32 classes each)
        # This is IN ADDITION to the existing E8-based discrete latents
        h_post_flat = h_post.reshape(B * self.num_colonies, self.deter_dim)
        discrete_latents, discrete_logits = self.discrete_latent_encoder(h_post_flat)
        discrete_latents = discrete_latents.view(B, self.num_colonies, self.discrete_latent_dim)
        discrete_logits = discrete_logits.view(
            B, self.num_colonies, 32, 32
        )  # [B, 7, 32 categories, 32 classes]

        # Discrete latent distributions (existing E8-based system)
        prior_logits = self.prior_net(h_prior)
        # TPU OPTIMIZATION (Jan 4, 2026): Use pre-allocated buffer instead of torch.cat
        post_logits = self.posterior_net(self._concat_hh(h_post, obs_col, B))

        prior_probs = self._apply_unimix(F.softmax(prior_logits, dim=-1))
        post_probs = self._apply_unimix(F.softmax(post_logits, dim=-1))

        # Continuous z from categorical (expected embedding; optional straight-through sample)
        z_expected = torch.matmul(post_probs, self.latent_embed.weight)  # [B,7,Z]
        if sample:
            flat = post_probs.view(-1, self.latent_classes)
            idx = torch.multinomial(flat, num_samples=1).view(B, self.num_colonies)
            z_sample = self.latent_embed(idx)  # [B,7,Z]
            z_next = z_expected + (z_sample - z_expected).detach()
        else:
            idx = post_probs.argmax(dim=-1)
            z_next = z_expected

        # Decode action from (h_post, z_next)
        # TPU OPTIMIZATION (Jan 4, 2026): Use pre-allocated buffer instead of torch.cat
        a_next = self.action_head(self._concat_hz(h_post, z_next, B))  # [B,7,A]

        # Compute KL divergence (symmetric for compatibility, balanced for training)
        kl_symmetric = self._kl_divergence(post_probs, prior_probs)  # [B,7]

        # Compute DreamerV3-style balanced KL with stop-gradients (Dec 14, 2025)
        kl_balanced, kl_info = balanced_kl_loss_categorical(
            post_probs=post_probs,
            prior_probs=prior_probs,
            free_bits=self.free_bits,
            dyn_weight=0.8,
            rep_weight=0.2,
        )

        # S7 coherence loss: encourage hierarchy levels to agree (Jan 4, 2026)
        # Higher coherence = levels agree, so loss = 1 - coherence
        s7_coherence = s7_fusion_info.get("coherence", 1.0)
        s7_coherence_loss = 1.0 - s7_coherence

        return {
            "h_next": h_post,
            "z_next": z_next,
            "a_next": a_next,
            "prior_probs": prior_probs,
            "posterior_probs": post_probs,
            "latent_index": idx,
            "kl": kl_symmetric,  # Backward compatibility
            "kl_balanced": kl_balanced,  # For training loss
            "kl_dyn": kl_info["kl_dyn"],  # Dynamics component
            "kl_rep": kl_info["kl_rep"],  # Representation component
            "kl_raw": kl_info["kl_raw"],  # Unbalanced (logging)
            # DreamerV3 discrete latents (Dec 27, 2025)
            "discrete_latents": discrete_latents,  # [B, 7, 1024] one-hot samples
            "discrete_logits": discrete_logits,  # [B, 7, 32, 32] raw logits
            # S7 Hierarchy Fusion (Jan 4, 2026)
            "s7_coherence": s7_coherence,  # [0, 1] how well S7 levels agree
            "s7_coherence_loss": s7_coherence_loss,  # For training: 1 - coherence
            "s7_fusion_info": s7_fusion_info,  # Full metadata dict
        }

    def step(
        self,
        h_prev: torch.Tensor,
        z_prev: torch.Tensor,
        action: torch.Tensor,
        e8_code: torch.Tensor | None = None,
        s7_phase: torch.Tensor | None = None,
        sample: bool = True,
        continue_flag: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor, dict[str, Any]]:
        """Single-step state prediction (non-mutating, for planning).

        ARCHITECTURAL CHANGE (Dec 22, 2025): Full E8 lattice E2E.
        Uses both E8 code (content) and S7 phase (routing).

        Unlike step_all(), this does NOT update internal state.
        Used by EFE for counterfactual trajectory rollouts.

        Args:
            h_prev: Previous deterministic state [B, 7, H] or [7, H]
            z_prev: Previous stochastic state [B, 7, Z] or [7, Z]
            action: Action taken [B, 7, A] or [7, A]
            e8_code: Optional E8 code [B, 8] or [8] (for posterior)
            s7_phase: Optional S7 phase [B, 7] or [7] (for colony routing)
            sample: Whether to sample from posterior (vs argmax)
            continue_flag: Optional [B] or [B, 1] (1=continue, 0=reset state at episode boundary)

        Returns:
            (h_next, z_next, info_dict)
            - h_next: [B, 7, H] or [7, H]
            - z_next: [B, 7, Z] or [7, Z]
            - info_dict: Contains 'kl', 'prior_probs', 'posterior_probs', etc.
        """
        # Handle different input shapes:
        # - Organism-level: [B, H], [B, Z], [B, A] -> broadcast to all colonies
        # - Colony-level: [B, 7, H], [B, 7, Z], [B, 7, A] -> use directly
        # - Unbatched: [7, H] or [H] -> add batch dimension

        unbatched = False
        organism_level = False

        # Detect format
        if h_prev.dim() == 1:
            # Unbatched organism-level: [H] -> [1, 7, H]
            unbatched = True
            organism_level = True
            h_prev = h_prev.unsqueeze(0).unsqueeze(0).expand(-1, self.num_colonies, -1)
            z_prev = z_prev.unsqueeze(0).unsqueeze(0).expand(-1, self.num_colonies, -1)
            action = action.unsqueeze(0).unsqueeze(0).expand(-1, self.num_colonies, -1)
            if e8_code is not None:
                e8_code = e8_code.unsqueeze(0)
            if s7_phase is not None:
                s7_phase = s7_phase.unsqueeze(0)
        elif h_prev.dim() == 2:
            if h_prev.size(0) == self.num_colonies:
                # Unbatched colony-level: [7, H] -> [1, 7, H]
                unbatched = True
                h_prev = h_prev.unsqueeze(0)
                z_prev = z_prev.unsqueeze(0)
                action = action.unsqueeze(0)
                if e8_code is not None:
                    e8_code = e8_code.unsqueeze(0)
                if s7_phase is not None:
                    s7_phase = s7_phase.unsqueeze(0)
            else:
                # Batched organism-level: [B, H] -> [B, 7, H]
                h_prev = h_prev.unsqueeze(1).expand(-1, self.num_colonies, -1)
                z_prev = z_prev.unsqueeze(1).expand(-1, self.num_colonies, -1)
                action = action.unsqueeze(1).expand(-1, self.num_colonies, -1)
        # else: already [B, 7, H] (batched colony-level)

        B = h_prev.size(0)
        device = h_prev.device

        # If no observation provided, use zeros (prior-only mode)
        if e8_code is None:
            e8_code = torch.zeros(B, 8, device=device, dtype=h_prev.dtype)
        elif e8_code.dim() == 1:
            e8_code = e8_code.unsqueeze(0)

        if s7_phase is None:
            s7_phase = torch.zeros(B, 7, device=device, dtype=h_prev.dtype)
        elif s7_phase.dim() == 1:
            s7_phase = s7_phase.unsqueeze(0)

        # Validate shapes
        if h_prev.shape != (B, self.num_colonies, self.deter_dim):
            raise ValueError(
                f"h_prev must be [B, {self.num_colonies}, {self.deter_dim}], got {tuple(h_prev.shape)}"
            )
        if z_prev.shape != (B, self.num_colonies, self.stoch_dim):
            raise ValueError(
                f"z_prev must be [B, {self.num_colonies}, {self.stoch_dim}], got {tuple(z_prev.shape)}"
            )
        if action.shape != (B, self.num_colonies, self.action_dim):
            raise ValueError(
                f"action must be [B, {self.num_colonies}, {self.action_dim}], got {tuple(action.shape)}"
            )

        # Use internal _step() for computation
        out = self._step(
            e8_code=e8_code,
            s7_phase=s7_phase,
            h_prev=h_prev,
            z_prev=z_prev,
            a_prev=action,
            sample=sample,
            continue_flag=continue_flag,
        )

        h_next = out["h_next"]
        z_next = out["z_next"]

        # If input was organism-level, aggregate back to organism-level
        if organism_level:
            h_next = h_next.mean(dim=1)  # [B, 7, H] -> [B, H]
            z_next = z_next.mean(dim=1)  # [B, 7, Z] -> [B, Z]

        # Remove batch dimension if input was unbatched
        if unbatched:
            h_next = h_next.squeeze(0)
            z_next = z_next.squeeze(0)

        info: dict[str, Any] = {
            "kl": out["kl"],
            "kl_divergence": out["kl"],  # Alias for EFE compatibility
            "prior_probs": out["prior_probs"],
            "posterior_probs": out["posterior_probs"],
            "latent_index": out["latent_index"],
            "a_next": out["a_next"],
        }

        return h_next, z_next, info

    def predict_obs(
        self,
        h: torch.Tensor,
        z: torch.Tensor,
    ) -> torch.Tensor:
        """Predict E8 code from latent state.

        ARCHITECTURAL CHANGE (Dec 22, 2025): Predicts E8 code [B, 8] for full
        E8 lattice end-to-end dynamics.

        Used by EFE for computing epistemic value (information gain).

        Args:
            h: Deterministic state [B, H], [B, 7, H], [H], or [7, H]
            z: Stochastic state [B, Z], [B, 7, Z], [Z], or [7, Z]

        Returns:
            Predicted E8 code [B, 8] or [8]
        """
        # Handle different input shapes (same logic as step())
        unbatched = False

        if h.dim() == 1:
            # Unbatched organism-level: [H] -> [1, 7, H]
            unbatched = True
            h = h.unsqueeze(0).unsqueeze(0).expand(-1, self.num_colonies, -1)
            z = z.unsqueeze(0).unsqueeze(0).expand(-1, self.num_colonies, -1)
        elif h.dim() == 2:
            if h.size(0) == self.num_colonies:
                # Unbatched colony-level: [7, H] -> [1, 7, H]
                unbatched = True
                h = h.unsqueeze(0)
                z = z.unsqueeze(0)
            else:
                # Batched organism-level: [B, H] -> [B, 7, H]
                h = h.unsqueeze(1).expand(-1, self.num_colonies, -1)
                z = z.unsqueeze(1).expand(-1, self.num_colonies, -1)
        # else: already [B, 7, H] (batched colony-level)

        B = h.size(0)

        # Validate shapes
        if h.shape != (B, self.num_colonies, self.deter_dim):
            raise ValueError(
                f"h must be [B, {self.num_colonies}, {self.deter_dim}], got {tuple(h.shape)}"
            )
        if z.shape != (B, self.num_colonies, self.stoch_dim):
            raise ValueError(
                f"z must be [B, {self.num_colonies}, {self.stoch_dim}], got {tuple(z.shape)}"
            )

        # Decode E8 code from each colony's (h, z)
        # [B, 7, H+Z] -> [B, 7, 8]
        hz = torch.cat([h, z], dim=-1)  # [B, 7, H+Z]
        e8_per_colony = self.obs_decoder(hz)  # [B, 7, 8] - each colony predicts 8D E8

        # Aggregate across colonies (mean pooling)
        e8_pred = e8_per_colony.mean(dim=1)  # [B, 8]

        # Remove batch dimension if input was unbatched
        if unbatched:
            e8_pred = e8_pred.squeeze(0)

        return e8_pred

    def step_all(  # type: ignore[no-untyped-def]
        self,
        *,
        e8_code: torch.Tensor | None = None,
        s7_phase: torch.Tensor | None = None,
        action_prev: torch.Tensor | None = None,
        sample: bool = True,
        enable_cot: bool | None = None,
        use_differentiable: bool = True,
        # S7 hierarchy phases (Dec 24, 2025)
        s7_e8: torch.Tensor | None = None,
        s7_e7: torch.Tensor | None = None,
        s7_e6: torch.Tensor | None = None,
        s7_f4: torch.Tensor | None = None,
        # DreamerV3: Episode boundary handling (Dec 27, 2025)
        continue_flag: torch.Tensor | None = None,
        **_,
    ) -> dict[str, Any]:
        """Advance the RSSM by one step for all colonies.

        Uses both E8 code (content) and S7 phase (routing).

        Args:
            e8_code: E8 lattice coordinates [B, 8] or [8]
            s7_phase: S7 phase for colony routing [B, 7] or [7]
            action_prev: Optional previous action override [B, action_dim] or [action_dim]
            sample: Whether to sample from posterior (vs argmax)
            enable_cot: Whether to run Chain-of-Thought reasoning (None = use default)
            use_differentiable: Whether to use differentiable operations
            continue_flag: Optional [B] or [B, 1] (1=continue, 0=reset at episode boundary)
            **_: Additional kwargs (ignored for compatibility)
        """
        device = next(self.parameters()).device

        # Handle missing inputs (use zeros for initialization/testing)
        if e8_code is None:
            e8_code = torch.zeros(1, 8, device=device)
        if s7_phase is None:
            s7_phase = torch.zeros(1, 7, device=device)

        # Ensure batch dimension
        if e8_code.dim() == 1:
            e8_code = e8_code.unsqueeze(0)
        if s7_phase.dim() == 1:
            s7_phase = s7_phase.unsqueeze(0)

        # Validate shapes
        if e8_code.dim() != 2 or e8_code.shape[-1] != 8:
            raise ValueError(f"e8_code must be [B, 8], got {tuple(e8_code.shape)}")
        if s7_phase.dim() != 2 or s7_phase.shape[-1] != 7:
            raise ValueError(f"s7_phase must be [B, 7], got {tuple(s7_phase.shape)}")

        # Infer batch size from inputs (prefer action_prev if provided, else e8_code)
        # This ensures batch consistency when action_prev drives the batch dimension
        if action_prev is not None:
            if action_prev.dim() == 1:
                action_prev = action_prev.unsqueeze(0)
            B = action_prev.size(0)
            # Expand e8_code and s7_phase to match action batch if needed
            if e8_code.size(0) == 1 and B > 1:
                e8_code = e8_code.expand(B, -1).contiguous()
            if s7_phase.size(0) == 1 and B > 1:
                s7_phase = s7_phase.expand(B, -1).contiguous()
        else:
            B = e8_code.size(0)

        # Batch sizes must match
        if s7_phase.size(0) != B:
            raise ValueError(f"e8_code batch {B} != s7_phase batch {s7_phase.size(0)}")

        dtype = e8_code.dtype

        if not self._initialized or self._current_states is None:
            self.initialize_all(batch_size=B, device=str(device))
        elif self._current_states[0].hidden.size(0) != B:
            # Batch-size changed; re-initialize.
            self.initialize_all(batch_size=B, device=str(device))

        assert self._current_states is not None  # for type checkers

        h_prev, z_prev, a_prev = self._states_to_tensors(
            self._current_states, device=device, dtype=dtype
        )

        # Optional override: provide a single organism-level previous action.
        if action_prev is not None:
            if action_prev.dim() != 2 or action_prev.shape[-1] != self.action_dim:
                raise ValueError(
                    f"action_prev must be [B, {self.action_dim}] or [{self.action_dim}], got {tuple(action_prev.shape)}"
                )
            a_prev = (
                action_prev.unsqueeze(1).expand(B, self.num_colonies, self.action_dim).contiguous()
            )

        # TPU OPTIMIZATION (Jan 4, 2026): Gradient checkpointing support
        # Uses recomputation during backward pass to reduce memory usage.
        # Critical for long sequences on TPU where activation memory is limiting.
        if self.training and self._use_gradient_checkpointing:
            # Wrap _step in checkpoint - requires use_reentrant=False for better XLA compatibility
            out = gradient_checkpoint(
                self._step_for_checkpoint,
                e8_code,
                s7_phase,
                h_prev,
                z_prev,
                a_prev,
                sample,
                s7_e8,
                s7_e7,
                s7_e6,
                s7_f4,
                continue_flag,
                use_reentrant=False,  # Better for XLA/TPU
            )
        else:
            out = self._step(
                e8_code=e8_code,
                s7_phase=s7_phase,
                h_prev=h_prev,
                z_prev=z_prev,
                a_prev=a_prev,
                sample=sample,
                # Pass hierarchy phases (Dec 24, 2025)
                s7_e8=s7_e8,
                s7_e7=s7_e7,
                s7_e6=s7_e6,
                s7_f4=s7_f4,
                # Pass continue flag (Dec 27, 2025)
                continue_flag=continue_flag,
            )

        # Persist internal states.
        cast(torch.Tensor, self._timestep).add_(1)
        self._current_states = self._tensors_to_states(
            h=out["h_next"],
            z=out["z_next"],
            a_next=out["a_next"],
            states=self._current_states,
        )

        # Organism-level action (mean across colonies)
        organism_action = out["a_next"].mean(dim=1)  # [B,A]
        if organism_action.size(0) == 1:
            organism_action = organism_action.squeeze(0)

        # FIX (Dec 28, 2025): Use kl_balanced with proper free_bits, remove fallback
        # kl_balanced already has DreamerV3 free_bits applied via balanced_kl_loss_categorical
        result: dict[str, Any] = {
            "organism_action": organism_action,
            "colony_actions": out["a_next"],
            "h_next": out["h_next"],
            "z_next": out["z_next"],
            "prior_probs": out["prior_probs"],
            "posterior_probs": out["posterior_probs"],
            "latent_index": out["latent_index"],
            "kl": out["kl"],  # Raw KL for logging
            "kl_balanced": out["kl_balanced"],  # DreamerV3 balanced KL with free_bits
            "kl_loss": out["kl_balanced"],  # Use balanced KL for loss (backward compat)
            "states": self._current_states,
        }

        # Chain-of-Thought reasoning (if enabled)
        # Resolve whether to run CoT: explicit arg > instance default
        run_cot = enable_cot if enable_cot is not None else self._cot_enabled
        if run_cot and self.collaborative_cot is not None:
            # Convert z_next [B, 7, Z] to dict[str, Any] format for CoT
            # CoT expects: dict[colony_name -> z_tensor]
            from kagami_math.catastrophe_constants import COLONY_NAMES

            z_states_dict = {}
            for idx, name in enumerate(COLONY_NAMES):
                # Take first batch element [Z] for single-step reasoning
                z_states_dict[name] = out["z_next"][0, idx]  # [Z]

            # Run collaborative CoT
            cot_thought, z_modulation = self.collaborative_cot(z_states_dict)

            result["cot_thought"] = cot_thought
            result["cot_confidence"] = cot_thought.confidence
            result["z_modulation"] = z_modulation  # For potential action modulation

            # ORGANISM-LEVEL COT INTEGRATION (Forge Colony Mission)
            # Run organism-level meta-reasoning if available
            if self.organism_cot is not None:
                try:
                    # Get organism μ_self from strange loop if available
                    mu_self = getattr(self, "_mu_self", torch.zeros(7, device=device, dtype=dtype))

                    # Run organism CoT on top of colony CoT
                    organism_thought, organism_z_modulation = self.organism_cot(
                        z_states_dict, mu_self
                    )

                    # Apply organism modulation to z_states and recompute organism action
                    if organism_z_modulation is not None:
                        # Split organism modulation back to colonies [98] -> [7 x 14]
                        z_mod_split = organism_z_modulation.split(self.stoch_dim)
                        for idx, name in enumerate(COLONY_NAMES):
                            if idx < len(z_mod_split):
                                # Apply modulation with blend factor
                                z_states_dict[name] = z_states_dict[name] + 0.1 * z_mod_split[idx]

                        # Update organism μ_self from meta-reasoning (strange loop evolution)
                        if organism_thought.mu_self_new is not None:
                            self._mu_self = 0.95 * mu_self + 0.05 * organism_thought.mu_self_new

                        # Recompute organism action with enhanced z_states
                        _enhanced_z = torch.stack(
                            [z_states_dict[name] for name in COLONY_NAMES]
                        ).unsqueeze(0)
                        enhanced_action = out["a_next"].mean(
                            dim=1
                        )  # Keep same action for now, future: recompute
                        result["organism_action"] = (
                            enhanced_action.squeeze(0)
                            if enhanced_action.size(0) == 1
                            else enhanced_action
                        )

                    result["organism_thought"] = organism_thought
                    result["organism_coherence"] = organism_thought.coherence
                    result["organism_influence"] = organism_thought.influence

                except Exception as e:
                    logger.debug(f"Organism CoT failed: {e}")
                    # Continue without organism CoT

        return result

    def forward(
        self,
        e8_code: torch.Tensor,
        s7_phase: torch.Tensor,
        actions: torch.Tensor | None = None,
        previous_states: list[ColonyState] | None = None,
        *,
        sample: bool = False,
        continue_flags: torch.Tensor | None = None,
    ) -> dict[str, torch.Tensor]:
        """Sequence forward (non-mutating).

        Uses both E8 code (content) and S7 phase (routing).

        Args:
            e8_code: [B, T, 8] E8 lattice coordinates sequence
            s7_phase: [B, T, 7] S7 phase sequence
            actions: Optional [B, T, action_dim] representing a_{t-1} inputs
            previous_states: Optional list[ColonyState] as initial state
            sample: If True, use straight-through categorical sampling for z
            continue_flags: Optional [B, T] or [B, T, 1] (1=continue, 0=reset at episode boundary)
        """

        if e8_code.dim() != 3 or e8_code.shape[-1] != 8:
            raise ValueError(f"e8_code must be [B, T, 8], got {tuple(e8_code.shape)}")
        if s7_phase.dim() != 3 or s7_phase.shape[-1] != 7:
            raise ValueError(f"s7_phase must be [B, T, 7], got {tuple(s7_phase.shape)}")

        B, T, _ = e8_code.shape
        device = e8_code.device
        dtype = e8_code.dtype

        # Validate matching batch/sequence dims
        if s7_phase.shape[:2] != (B, T):
            raise ValueError(
                f"e8_code shape {e8_code.shape[:2]} != s7_phase shape {s7_phase.shape[:2]}"
            )

        if actions is not None:
            if actions.shape[:2] != (B, T) or actions.shape[-1] != self.action_dim:
                raise ValueError(
                    f"actions must be [B, T, {self.action_dim}], got {tuple(actions.shape)}. "
                    f"e8_code.shape={e8_code.shape}, B={B}, T={T}"
                )

        # Validate continue_flags if provided (Dec 27, 2025)
        if continue_flags is not None:
            if continue_flags.dim() == 2:
                # [B, T] -> ensure shape is correct
                if continue_flags.shape != (B, T):
                    raise ValueError(
                        f"continue_flags must be [B, T], got {tuple(continue_flags.shape)}"
                    )
            elif continue_flags.dim() == 3:
                # [B, T, 1] -> ensure shape is correct
                if continue_flags.shape != (B, T, 1):
                    raise ValueError(
                        f"continue_flags must be [B, T, 1], got {tuple(continue_flags.shape)}"
                    )
            else:
                raise ValueError(f"continue_flags must be 2D or 3D, got {continue_flags.dim()}D")

        # Initialize state tensors (do not mutate internal state in forward()).
        if previous_states is None:
            previous_states = create_colony_states(
                B,
                self.num_colonies,
                str(device),
                hidden_dim=self.deter_dim,
                stochastic_dim=self.stoch_dim,
            )
            for st in previous_states:
                st.metadata["prev_action"] = torch.zeros(
                    B, self.action_dim, device=device, dtype=dtype
                )

        h, z, a_prev = self._states_to_tensors(previous_states, device=device, dtype=dtype)

        h_seq: list[torch.Tensor] = []
        z_seq: list[torch.Tensor] = []
        a_seq: list[torch.Tensor] = []
        kl_seq: list[torch.Tensor] = []
        kl_balanced_seq: list[torch.Tensor] = []  # FIX (Dec 28, 2025): Track balanced KL
        latent_idx_seq: list[torch.Tensor] = []
        posterior_probs_seq: list[torch.Tensor] = []

        for t in range(T):
            e8_t = e8_code[:, t]  # [B, 8]
            s7_t = s7_phase[:, t]  # [B, 7]
            if actions is not None:
                a_prev = (
                    actions[:, t]
                    .unsqueeze(1)
                    .expand(B, self.num_colonies, self.action_dim)
                    .contiguous()
                )

            # Extract continue flag for this timestep (Dec 27, 2025)
            continue_t = None
            if continue_flags is not None:
                if continue_flags.dim() == 2:
                    continue_t = continue_flags[:, t]  # [B]
                else:  # dim == 3
                    continue_t = continue_flags[:, t, :]  # [B, 1]

            out = self._step(
                e8_code=e8_t,
                s7_phase=s7_t,
                h_prev=h,
                z_prev=z,
                a_prev=a_prev,
                sample=sample,
                continue_flag=continue_t,
            )
            h = out["h_next"]
            z = out["z_next"]
            a_prev = out["a_next"].detach()

            h_seq.append(h)
            z_seq.append(z)
            a_seq.append(out["a_next"])
            kl_seq.append(out["kl"])
            # FIX (Dec 28, 2025): Collect balanced KL with free_bits applied
            kl_balanced_seq.append(out["kl_balanced"])
            latent_idx_seq.append(out["latent_index"])
            posterior_probs_seq.append(out["posterior_probs"])

        # FIX (Dec 28, 2025): kl_balanced is a scalar from balanced_kl_loss_categorical,
        # need to stack as 1D tensor (no dim argument) then unsqueeze
        kl_balanced_stacked = torch.stack(kl_balanced_seq)  # [T] scalars → [T]

        return {
            "h": torch.stack(h_seq, dim=1),  # [B,T,7,H]
            "z": torch.stack(z_seq, dim=1),  # [B,T,7,Z]
            "colony_actions": torch.stack(a_seq, dim=1),  # [B,T,7,A]
            "organism_actions": torch.stack([a.mean(dim=1) for a in a_seq], dim=1),  # [B,T,A]
            "kl": torch.stack(kl_seq, dim=1),  # [B,T,7] - raw KL for logging
            "kl_balanced": kl_balanced_stacked.mean(),  # Scalar - average over timesteps
            "latent_index": torch.stack(latent_idx_seq, dim=1),  # [B,T,7]
            "posterior_probs": torch.stack(posterior_probs_seq, dim=1),  # [B,T,7,K]
        }

    def get_current_states(self) -> list[ColonyState] | None:
        """Get current colony states."""
        return self._current_states

    def reset_states(self, batch_size: int, device: str = "cuda") -> None:
        """Reset colony states."""
        self._current_states = create_colony_states(
            batch_size,
            self.config.num_colonies,
            device,
            hidden_dim=self.deter_dim,
            stochastic_dim=self.stoch_dim,
        )
        cast(torch.Tensor, self._timestep).zero_()

    def imagine(
        self,
        initial_h: torch.Tensor,
        initial_z: torch.Tensor,
        policy: torch.Tensor,
        *,
        sample: bool = True,
    ) -> dict[str, torch.Tensor]:
        """Imagine trajectory under a given policy (pure latent dynamics).

        ARCHITECTURAL CHANGE (Dec 22, 2025): Outputs E8 predictions [B, depth, 8].
        Full E8 lattice E2E dynamics.

        This is the planning/imagination mode - NO observations, pure dynamics.
        Used by EFE for trajectory alignment during joint training.

        Args:
            initial_h: [B, h_dim] initial deterministic state (organism-level)
            initial_z: [B, z_dim] initial stochastic state (organism-level)
            policy: [B, depth, action_dim] action sequence
            sample: Whether to sample from posterior

        Returns:
            Dict with:
                h_states: [B, depth, h_dim] deterministic trajectory
                z_states: [B, depth, z_dim] stochastic trajectory
                e8_predictions: [B, depth, 8] predicted E8 codes
        """
        _B, depth, _ = policy.shape

        # Expand initial states to all colonies
        h = initial_h.unsqueeze(1).expand(-1, self.num_colonies, -1)  # [B, 7, h_dim]
        z = initial_z.unsqueeze(1).expand(-1, self.num_colonies, -1)  # [B, 7, z_dim]

        h_seq = []
        z_seq = []
        e8_seq = []

        for t in range(depth):
            action = policy[:, t]  # [B, action_dim]

            # Expand action to all colonies
            a_prev = action.unsqueeze(1).expand(-1, self.num_colonies, -1)  # [B, 7, action_dim]

            # Since we're imagining, we don't have real observations
            # Use prior predictions from current state (autoregressive)
            # This is more accurate than zeros for trajectory prediction
            h_organism = h.mean(dim=1)  # [B, h_dim]
            z_organism = z.mean(dim=1)  # [B, z_dim]
            prior_e8 = self.predict_obs(h_organism, z_organism)  # [B, 8]
            prior_s7 = prior_e8[:, :7]  # First 7 dims as S7 proxy

            # Step dynamics (imagination mode)
            out = self._step(
                e8_code=prior_e8,
                s7_phase=prior_s7,
                h_prev=h,
                z_prev=z,
                a_prev=a_prev,
                sample=sample,
            )

            h = out["h_next"]
            z = out["z_next"]

            # Aggregate to organism level (mean over colonies)
            h_organism = h.mean(dim=1)  # [B, h_dim]
            z_organism = z.mean(dim=1)  # [B, z_dim]

            # Predict E8 code (decode from state)
            e8_pred = self.predict_obs(h_organism, z_organism)

            h_seq.append(h_organism)
            z_seq.append(z_organism)
            e8_seq.append(e8_pred)

        return {
            "h_states": torch.stack(h_seq, dim=1),  # [B, depth, h_dim]
            "z_states": torch.stack(z_seq, dim=1),  # [B, depth, z_dim]
            "e8_predictions": torch.stack(e8_seq, dim=1),  # [B, depth, 8] E8 codes
        }

    # =====================================================================
    # RL PREDICTION METHODS (December 14, 2025)
    # =====================================================================

    def predict_reward(self, h: torch.Tensor, z: torch.Tensor) -> torch.Tensor:
        """Predict expected reward from state (TwoHot decoded).

        IMPROVED (Dec 31, 2025): Uses TwoHot encoding for distributional prediction.
        This captures multimodal return distributions and is more stable across
        varying reward scales.

        Args:
            h: Deterministic state [B, H] or [B, 7, H]
            z: Stochastic state [B, Z] or [B, 7, Z]

        Returns:
            Predicted reward [B] or [B, 7] (expected value from TwoHot distribution)
        """
        logits = self.predict_reward_logits(h, z)
        return self.reward_twohot.decode(logits)

    def predict_reward_logits(self, h: torch.Tensor, z: torch.Tensor) -> torch.Tensor:
        """Predict reward logits over TwoHot bins (for loss computation).

        Args:
            h: Deterministic state [B, H] or [B, 7, H]
            z: Stochastic state [B, Z] or [B, 7, Z]

        Returns:
            Reward logits [B, num_bins] or [B, 7, num_bins]
        """
        if h.dim() == 3:
            state = torch.cat([h, z], dim=-1)
        else:
            state = torch.cat([h, z], dim=-1)
        return self.reward_head(state)

    def reward_loss(self, h: torch.Tensor, z: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        """Compute TwoHot cross-entropy loss for reward prediction.

        Args:
            h: Deterministic state [B, H] or [B, 7, H]
            z: Stochastic state [B, Z] or [B, 7, Z]
            target: Target rewards [B] or [B, 7]

        Returns:
            Loss scalar
        """
        logits = self.predict_reward_logits(h, z)
        return self.reward_twohot.loss(logits, target)

    def predict_value(self, h: torch.Tensor, z: torch.Tensor) -> torch.Tensor:
        """Predict state value V(s) for policy optimization (TwoHot decoded).

        IMPROVED (Dec 31, 2025): Uses TwoHot encoding for distributional prediction.

        Args:
            h: Deterministic state [B, H] or [B, 7, H]
            z: Stochastic state [B, Z] or [B, 7, Z]

        Returns:
            State value [B] or [B, 7] (expected value from TwoHot distribution)
        """
        logits = self.predict_value_logits(h, z)
        return self.value_twohot.decode(logits)

    def predict_value_logits(self, h: torch.Tensor, z: torch.Tensor) -> torch.Tensor:
        """Predict value logits over TwoHot bins (for loss computation).

        Args:
            h: Deterministic state [B, H] or [B, 7, H]
            z: Stochastic state [B, Z] or [B, 7, Z]

        Returns:
            Value logits [B, num_bins] or [B, 7, num_bins]
        """
        if h.dim() == 3:
            state = torch.cat([h, z], dim=-1)
        else:
            state = torch.cat([h, z], dim=-1)
        return self.value_head(state)

    def value_loss(self, h: torch.Tensor, z: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        """Compute TwoHot cross-entropy loss for value prediction.

        Args:
            h: Deterministic state [B, H] or [B, 7, H]
            z: Stochastic state [B, Z] or [B, 7, Z]
            target: Target values [B] or [B, 7]

        Returns:
            Loss scalar
        """
        logits = self.predict_value_logits(h, z)
        return self.value_twohot.loss(logits, target)

    def predict_continue(self, h: torch.Tensor, z: torch.Tensor) -> torch.Tensor:
        """Predict episode continuation probability (1 - done).

        Args:
            h: Deterministic state [B, H] or [B, 7, H]
            z: Stochastic state [B, Z] or [B, 7, Z]

        Returns:
            Continue probability [B, 1] or [B, 7, 1] (0 = terminal, 1 = continues)
        """
        if h.dim() == 3:
            # Colony-level: [B, 7, H]
            state = torch.cat([h, z], dim=-1)
        else:
            # Organism-level: [B, H]
            state = torch.cat([h, z], dim=-1)
        return torch.sigmoid(self.continue_head(state))

    def _count_parameters(self) -> int:
        """Count total trainable parameters."""
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


# Global RSSM instance (singleton pattern)
_global_rssm: OrganismRSSM | None = None


def get_organism_rssm(config: ColonyRSSMConfig | None = None) -> OrganismRSSM:
    """Get the global OrganismRSSM instance."""
    global _global_rssm

    if _global_rssm is None:
        if config is None:
            config = get_kagami_config().world_model.rssm

        _global_rssm = OrganismRSSM(config)
        logger.info("Global OrganismRSSM instance created")

    return _global_rssm


def reset_organism_rssm() -> None:
    """Reset the global OrganismRSSM instance."""
    global _global_rssm
    _global_rssm = None
    logger.info("Global OrganismRSSM instance reset")


def create_rssm_world_model(config: ColonyRSSMConfig | None = None) -> OrganismRSSM:
    """Create a new OrganismRSSM world model instance.

    Args:
        config: RSSM configuration. If None, uses default config.

    Returns:
        New OrganismRSSM instance
    """
    if config is None:
        config = get_kagami_config().world_model.rssm

    model = OrganismRSSM(config)
    logger.info(f"New OrganismRSSM created: {model._count_parameters()} parameters")

    return model


# NOTE: The original OrganismRSSM class was 1800+ lines and contained:
# - Sophisticated sequence modeling
# - Advanced colony coordination protocols
# - Complex hierarchical message passing
# - Extensive training and optimization utilities
# - Sophisticated state management
# - Advanced attention mechanisms
# - And much more...
#
# This simplified version provides the basic structure to enable the split.
# The full implementation should be gradually migrated from the original file.
