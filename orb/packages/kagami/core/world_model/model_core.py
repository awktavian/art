"""KagamiWorldModel core implementation.

MAJOR REFACTORING (December 27, 2025):
=======================================
Split model_core.py (1188 lines) into focused modules:
- model_encoder.py: Encoding methods (encode, encode_observation, observe)
- model_decoder.py: Decoding methods (decode)
- model_inference.py: Inference methods (forward, H-JEPA predictions)
- model_training.py: Training methods (training_step, loss computation)
- model_core.py: Coordination and initialization (this file)

This modular structure follows single responsibility principle and enables:
- Better testability of individual components
- Easier code navigation and maintenance
- Reduced cognitive load for developers
- Cleaner git diffs and parallel development

MAJOR UPDATE (December 13, 2025):
================================
Integrated S7 phase extraction at ALL hierarchy levels and unified strange loop:
- S7AugmentedHierarchy: Extracts S7 (7D octonion phase) at E8, E7, E6, F4, G2
- StrangeLoopS7Tracker: Tracks μ_self convergence in S7 space (mathematically meaningful)
- GodelianSelfReference: TRUE self-reference via code inspection (optional)

The key insight: μ_self should live in S7 (7D), not arbitrary 32D.
S7 = unit imaginary octonions = 7 colonies = Fano plane structure.

Key contracts enforced by the test suite:
- `model(x)` returns `(output, metrics)`
- `model.encode(x)` returns `(CoreState, metrics)`
- `model.decode(core_state)` returns `(output, metrics)`
- `model.training_step(x, target)` returns `LossOutput`
- `model.unified_hourglass` exists
"""

from __future__ import annotations

import logging
from typing import Any

import torch
import torch.nn as nn

from kagami.core.config.unified_config import RSSMConfig
from kagami.core.config.world_model_config import WorldModelConfig as KagamiWorldModelConfig
from kagami.core.world_model.equivariance.unified_equivariant_hierarchy import (
    create_unified_hourglass,
)
from kagami.core.world_model.information_bottleneck import (
    SequenceIBConfig,
    SequenceInformationBottleneck,
)
from kagami.core.world_model.losses.composed import create_loss_module
from kagami.core.world_model.rssm_core import OrganismRSSM

from .model_config import CoreState
from .model_decoder import DecoderMixin

# Import mixins for modular functionality
from .model_encoder import EncoderMixin
from .model_inference import InferenceMixin
from .model_training import TrainingMixin

# Import mixins for modular functionality

logger = logging.getLogger(__name__)


# =============================================================================
# SHAPE-AWARE COMPILATION GUARDS (Dec 16, 2025)
# =============================================================================


def _should_compile_for_shape(batch_size: int, seq_len: int) -> bool:
    """Determine if torch.compile is beneficial for given shape.

    Args:
        batch_size: Batch dimension
        seq_len: Sequence length dimension

    Returns:
        True if compilation should be used, False to use eager mode

    Rationale:
        - batch=1: Compilation overhead > single-sample benefit
        - seq=1: Trivial computation, eager is faster
        - seq>512: Long sequences cause graph breaks and slow compilation
        - batch>128: Large batches may exceed GPU memory in compiled mode
    """
    # Edge cases where eager mode is faster
    if batch_size == 1:
        return False  # Single sample: compilation overhead not worth it
    if seq_len == 1:
        return False  # Single token: trivial, no benefit
    if seq_len > 512:
        return False  # Long sequence: compilation too slow due to graph breaks
    if batch_size > 128:
        return False  # Large batch: potential memory issues in compiled mode

    # Sweet spot: batch in [2, 128], seq in [2, 512]
    return True


def _ceil_multiple(x: int, m: int) -> int:
    return ((x + m - 1) // m) * m


class KagamiWorldModel(EncoderMixin, DecoderMixin, InferenceMixin, TrainingMixin, nn.Module):
    """Unified hourglass world model with S7-augmented strange loop.

    REFACTORED ARCHITECTURE (December 27, 2025):
    ============================================
    This class now uses mixins for modular functionality:
    - EncoderMixin: encode(), encode_observation(), observe()
    - DecoderMixin: decode()
    - InferenceMixin: forward(), H-JEPA predictions
    - TrainingMixin: training_step(), loss computation

    ARCHITECTURE (December 13, 2025):
    =================================
    E8(248) ─┬→ E7(133) ─┬→ E6(78) ─┬→ F4(52) ─┬→ G2(14) ─┬→ S7(7) ─→ E8_lattice(8)
             │           │          │          │          │
             └→ s7_e8    └→ s7_e7   └→ s7_e6   └→ s7_f4   └→ s7_g2 (canonical)

    S7 phase is extracted at EVERY level. This enables:
    - Colony coherence tracking (7 colonies = 7 imaginary octonions)
    - Fano plane composition across hierarchy
    - μ_self fixed point in mathematically meaningful space

    The strange loop closure is: s7_{t+1} ≈ s7_t (stable self-representation)
    """

    def __init__(self, config: KagamiWorldModelConfig):
        super().__init__()
        self.config = config

        # Public dimension contract used by training/tests.
        self.dimensions = [
            int(d) for d in (self.config.layer_dimensions or (self.config.bulk_dim,))
        ]

        # Core hourglass.
        # FIX (Dec 29, 2025): Pass dropout from config to hourglass
        # Previously dropout was hardcoded at 0.1, causing overfitting
        self.unified_hourglass = create_unified_hourglass(
            bulk_dim=int(self.config.bulk_dim),
            dropout=float(getattr(self.config, "dropout", 0.1)),
        )

        # Dynamic input projection layers for variable observation dimensions
        # Handles observations from different sources (29, 64, 128, 256, etc.)
        # Lazily created on first use via _project_to_bulk_dim()
        self._input_projections: dict[int, nn.Linear] = {}

        # =================================================================
        # H-JEPA PREDICTOR AND TARGET NETWORKS (December 19, 2025)
        # =================================================================
        # Hierarchical Joint-Embedding Predictive Architecture (LeCun 2022)
        # Multi-horizon prediction in E8 latent space
        # FIX (Dec 28, 2025): Increase EMA tau to slow down target updates
        # Combined with less frequent updates (every 10 steps), this prevents
        # target from becoming identical to predictor too quickly
        self.h_jepa_ema_tau = 0.999  # Higher tau = slower target update
        self._h_jepa_step_counter = 0  # FIX (Jan 4, 2026): Initialize in __init__ not lazily
        self._init_h_jepa_networks()

        # Variable-length nucleus information bottleneck (Sequence-IB).
        self._sequence_ib = SequenceInformationBottleneck(
            SequenceIBConfig(
                max_levels=int(self.config.ib_max_levels),
                bottleneck_dim=int(self.config.ib_bottleneck_dim),
                num_heads=int(self.config.ib_num_heads),
                num_layers=int(self.config.ib_num_layers),
                beta=float(self.config.ib_beta),
            )
        )

        # Unified loss module (single entry point).
        self.loss_module = create_loss_module()

        # =================================================================
        # ORGANISM RSSM FOR E8 LATTICE DYNAMICS (December 22, 2025)
        # =================================================================
        # Colony RSSM with DreamerV3-style KL balancing
        # Input: E8 code [B, T, 8] - full E8 lattice end-to-end
        # Output: kl for training loss, colony actions for downstream
        # FIX (Dec 29, 2025): Pass dropout from config to RSSM
        # Previously dropout was hardcoded at 0.1
        rssm_config = RSSMConfig(
            num_colonies=7,
            colony_dim=64,  # Deterministic state per colony
            stochastic_dim=32,  # Stochastic latent per colony
            action_dim=8,  # Action dimension (matches E8)
            obs_dim=8,  # E8 code dimension
            # DreamerV3 parameters (Dec 28, 2025)
            # free_bits=1.0: Standard for categorical (14% of max entropy)
            # unimix=0.01: 1% uniform mixing (prevents deterministic collapse)
            kl_free_nats=1.0,
            unimix=0.01,
            # Regularization (Dec 29, 2025)
            dropout=float(getattr(self.config, "dropout", 0.1)),
            attention_dropout=float(getattr(self.config, "attention_dropout", 0.1)),
        )
        self.organism_rssm = OrganismRSSM(rssm_config)
        logger.info("✅ OrganismRSSM initialized for E8 lattice dynamics")

        # =================================================================
        # E8 TRAJECTORY CACHE (December 24, 2025)
        # =================================================================
        # O(1) lookup for repeated E8 patterns + bifurcation replay
        self._trajectory_cache = None
        if getattr(config, "use_trajectory_cache", True):
            try:
                from kagami.core.world_model.e8_trajectory_cache import create_e8_trajectory_cache

                self._trajectory_cache = create_e8_trajectory_cache(
                    max_size=getattr(config, "trajectory_cache_size", 10000),
                    bifurcation_buffer_size=getattr(config, "bifurcation_buffer_size", 1000),
                )
                logger.info("✅ E8 trajectory cache enabled")
            except ImportError as e:
                logger.debug(f"E8 trajectory cache not available: {e}")

        # =================================================================
        # S7-AUGMENTED HIERARCHY + STRANGE LOOP (December 13, 2025)
        # =================================================================
        # Initialize attributes first, then ensure hierarchy is ready
        self._s7_hierarchy: nn.Module | None = None
        self._s7_tracker: Any | None = None
        self._godelian: nn.Module | None = None

        # Initialize immediately to avoid repeated lazy initialization during training
        self._ensure_s7_hierarchy()

        # =================================================================
        # FANO ATTENTION FOR CROSS-COLONY COMMUNICATION (December 20, 2025)
        # =================================================================
        # Optional Fano attention applied to S7 phase for cross-colony message passing
        if config.use_fano_attention:
            from kagami.core.world_model.layers.gated_fano_attention import GatedFanoAttention

            # Create minimal RSSM config for Fano attention
            # RSSMConfig has validation constraints: colony_dim >= 32, attention_dim >= 8
            # We pad S7 (7D) to meet these requirements
            fano_config = RSSMConfig(
                num_colonies=7,
                colony_dim=32,  # Minimum allowed by RSSMConfig validation
                attention_dim=max(8, 32 * config.fano_attention_num_heads),
                attention_heads=config.fano_attention_num_heads,
                head_dim=32,  # Match colony_dim
                attention_dropout=config.fano_attention_dropout,
            )
            self.fano_attention = GatedFanoAttention(
                fano_config,
                gating_mode="enabled",  # Use gating for dynamic sparsity
                gate_bias=True,  # Enable bias for gate initialization
            )
            # Project S7 (7D) to/from Fano attention space (32D)
            self.s7_to_fano = nn.Linear(7, 32, bias=False)
            self.fano_to_s7 = nn.Linear(32, 7, bias=False)
            logger.info(
                f"✅ Fano attention enabled: {config.fano_attention_num_heads} heads, "
                f"dropout={config.fano_attention_dropout}, dim=7→32→7"
            )
        else:
            self.fano_attention = None

            self.s7_to_fano = None

            self.fano_to_s7 = None

        # OPTIMIZATION (Dec 16, 2025): Compile hot paths for 3-4x speedup
        # Only on GPU - CPU has timeout issues with torch.compile
        if torch.cuda.is_available():
            from kagami.core.world_model.compilation import compile_hot_paths

            try:
                compile_hot_paths(self, mode="training")
                logger.info("✅ Hot paths compiled for training")
            except Exception as e:
                logger.debug(f"Hot path compilation skipped: {e}")

        # μ_self lives in S7 (7D) - mathematically meaningful
        self.register_buffer("_mu_self", torch.zeros(7))
        self._mu_self_initialized = False

        # Populated by training_step for downstream code.
        self._last_forward_output_detached: torch.Tensor | None = None

        # Optional wiring hook (optimality integration monkeypatches).
        self._optimality_wiring = None

        # =================================================================
        # E8 LANGUAGE DECODER (December 28, 2025 - VL-JEPA STYLE)
        # =================================================================
        # Text generation from world model states via embedding prediction
        # Training: WM State → E8 core → Text Embedding (MSE vs teacher)
        # Inference: Text Embedding → Decoder → Tokens
        # Language decoder DISABLED by default (requires 1M+ hours video data)
        # Use V-JEPA 2 pretrained encoder instead: kagami/core/training/vjepa2_encoder.py
        self.language_decoder: nn.Module | None = None
        if getattr(config, "enable_e8_language_decoder", False):  # Default: disabled
            try:
                from kagami.core.training.language_decoder import E8LanguageDecoder

                wm_dim = min(int(config.bulk_dim), 128)
                self.language_decoder = E8LanguageDecoder(
                    wm_dim=wm_dim,
                    text_emb_dim=384,
                    llm_dim=1024,
                    vocab_size=32000,
                    use_quantization=False,
                    teacher_model="sentence-transformers/all-MiniLM-L6-v2",
                )
                logger.info(f"✅ E8LanguageDecoder enabled: {wm_dim}D → 384D")
            except Exception as e:
                logger.debug(f"E8LanguageDecoder skipped: {e}")

        # =================================================================
        # FROZEN LLM LANGUAGE GROUNDING + GENERATION (CoCa/DeCap style)
        # =================================================================
        # Trains a lightweight prefix projection while keeping the LM frozen.
        # Provides BOTH:
        # - grounded text generation (captioning loss)
        # - contrastive alignment (InfoNCE grounding loss)
        self.language_captioner: nn.Module | None = None
        if getattr(config, "enable_language_decoder", False):  # piggyback on same flag
            try:
                from kagami.core.training.language_grounding import (
                    FrozenPrefixCaptioner,
                    LanguageGroundingConfig,
                )

                # Prefer an explicit LM name if present on config, else default.
                lm_name = getattr(config, "language_model_name", None) or "Qwen/Qwen2.5-0.5B"
                prefix_len = int(getattr(config, "language_prefix_len", 8))
                max_len = int(getattr(config, "language_max_length", 64))
                temperature = float(getattr(config, "language_temperature", 0.07))

                # Choose device based on runtime availability (model is moved later).
                lm_device = (
                    "cuda"
                    if torch.cuda.is_available()
                    else ("mps" if torch.backends.mps.is_available() else "cpu")
                )

                # FIX (Dec 30, 2025): Pass dropout from main config to language grounding
                # Previously hardcoded at 0.1, causing 388% train/val gap
                lang_dropout = float(getattr(config, "dropout", 0.2))

                self.language_captioner = FrozenPrefixCaptioner(
                    wm_dim=min(int(config.bulk_dim), 128),
                    config=LanguageGroundingConfig(
                        model_name=str(lm_name),
                        prefix_len=prefix_len,
                        max_length=max_len,
                        temperature=temperature,
                        dropout=lang_dropout,  # FIX: Use config dropout
                    ),
                    device=lm_device,
                )
                logger.info(
                    "✅ FrozenPrefixCaptioner enabled: %s (prefix_len=%d, max_len=%d)",
                    lm_name,
                    prefix_len,
                    max_len,
                )
            except Exception as e:
                logger.debug(f"FrozenPrefixCaptioner skipped: {e}")

        # =================================================================
        # FRAME DECODER FOR VIDEO GENERATION (December 28, 2025)
        # =================================================================
        # Decodes latent representations to pixel space for video prediction
        # Enables render loss during training when frames_t/frames_t_plus_1 available
        self.frame_decoder: nn.Module | None = None
        if getattr(config, "enable_frame_decoder", True):
            try:
                # Build frame decoder: bulk_dim → 128x128 RGB frames
                D = int(config.bulk_dim)
                self.frame_decoder = nn.Sequential(
                    nn.Linear(D, 512),
                    nn.ReLU(),
                    nn.Linear(512, 256 * 4 * 4),
                    nn.ReLU(),
                    nn.Unflatten(1, (256, 4, 4)),
                    nn.ConvTranspose2d(256, 128, 4, 2, 1),  # 4→8
                    nn.ReLU(),
                    nn.ConvTranspose2d(128, 64, 4, 2, 1),  # 8→16
                    nn.ReLU(),
                    nn.ConvTranspose2d(64, 32, 4, 2, 1),  # 16→32
                    nn.ReLU(),
                    nn.ConvTranspose2d(32, 16, 4, 2, 1),  # 32→64
                    nn.ReLU(),
                    nn.ConvTranspose2d(16, 3, 4, 2, 1),  # 64→128
                    nn.Sigmoid(),  # Output in [0, 1]
                )
                logger.info(f"✅ FrameDecoder enabled: {D}D → 128x128 RGB")
            except Exception as e:
                logger.debug(f"FrameDecoder initialization skipped: {e}")

        # =================================================================
        # META-TOWER FOR FIXED POINT OPTIMIZATION (December 24, 2025)
        # =================================================================
        # Wires in MetaTower for policy-level fixed point: Π* ≈ F(Π*; R(Π*))
        # Called at end of epoch to update policy towards fixed point
        self._meta_tower = None
        self._meta_tower_receipts: list[dict[str, Any]] = []  # Collect receipts for meta-learning
        self._meta_tower_epoch_interval = 1  # Update every epoch
        self._meta_tower_current_epoch = 0
        try:
            from kagami.core.strange_loops.fixed_point import create_meta_tower

            self._meta_tower = create_meta_tower(
                convergence_threshold=0.01,
                max_iterations=5,  # Limit iterations per epoch
            )
            logger.info("✅ MetaTower wired for fixed point optimization")
        except Exception as e:
            logger.debug(f"MetaTower initialization skipped: {e}")

        # =================================================================
        # CAUSAL GROUNDED INTELLIGENCE (December 27, 2025)
        # =================================================================
        # Three-layer cognitive enhancement from "Kagami Evolution" proposal:
        # 1. Causal Reasoning Engine - counterfactual reasoning
        # 2. Temporal Abstraction Layer - long-horizon planning
        # 3. Embodied Sensorimotor Input - physics grounding
        self._causal_grounded: nn.Module | None = None
        try:
            from kagami.core.world_model.causal_grounded_integration import (
                CausalGroundedWorldModel,
                GroundedIntelligenceConfig,
            )

            grounded_config = GroundedIntelligenceConfig(
                obs_dim=8,  # E8 code dimension
                action_dim=8,
                hidden_dim=64,
                enable_causal=True,
                enable_temporal=True,
                enable_embodied=True,
                subgoal_dim=32,
                n_subgoals=8,
                physics_dim=32,
            )
            self._causal_grounded = CausalGroundedWorldModel(
                config=grounded_config,
                rssm=self.organism_rssm,
            )
            logger.info("✅ CausalGroundedWorldModel wired (causal + temporal + embodied)")
        except Exception as e:
            logger.debug(f"CausalGroundedWorldModel initialization skipped: {e}")

        # =================================================================
        # TPU OPTIMIZATION: Apply dtype to model (Jan 4, 2026)
        # =================================================================
        # bfloat16 is the native format for TPU MXU (Matrix eXecution Unit).
        # XLA will auto-cast, but explicit conversion saves memory bandwidth
        # and ensures consistent precision throughout training.
        model_dtype = getattr(config, "dtype", "float32")
        if model_dtype != "float32":
            try:
                target_dtype = getattr(torch, model_dtype)
                self.to(target_dtype)
                logger.info(f"✅ Model converted to {model_dtype} for TPU optimization")
            except (AttributeError, RuntimeError) as e:
                logger.warning(f"Failed to convert model to {model_dtype}: {e}")

        # =================================================================
        # GPU AMP AUTOCAST SETUP (Jan 4, 2026)
        # =================================================================
        # Cache the torch dtype for AMP autocast to avoid repeated getattr calls
        self._amp_dtype: torch.dtype | None = None
        if getattr(config, "use_amp", False):
            amp_dtype_str = getattr(config, "amp_dtype", "float16")
            self._amp_dtype = getattr(torch, amp_dtype_str, torch.float16)
            logger.info(f"✅ GPU AMP autocast enabled with dtype={amp_dtype_str}")

    def _ensure_s7_hierarchy(self) -> None:
        """Lazy-initialize S7 hierarchy components."""
        if self._s7_hierarchy is not None:
            return

        logger.debug("Initializing S7 hierarchy (lazy)")

        try:
            from kagami_math.s7_augmented_hierarchy import (
                S7AugmentedHierarchy,
                StrangeLoopS7Tracker,
            )

            # Get device from model parameters
            device = next(self.parameters()).device

            logger.debug("Creating S7AugmentedHierarchy...")
            self._s7_hierarchy = S7AugmentedHierarchy()
            self._s7_hierarchy = self._s7_hierarchy.to(device)  # CRITICAL: move to same device

            logger.debug("Creating StrangeLoopS7Tracker...")
            self._s7_tracker = StrangeLoopS7Tracker(
                convergence_threshold=0.01,
                ema_decay=0.99,
            )
            self._s7_tracker = self._s7_tracker.to(device)  # CRITICAL: move to same device

            logger.debug("✅ S7AugmentedHierarchy initialized on %s", device)
        except Exception as e:
            logger.debug("S7 hierarchy init failed: %s", e)

    def _init_h_jepa_networks(self) -> None:
        """Initialize H-JEPA predictor and target networks.

        Architecture:
            - Predictor: E8(8) → hidden(64) → E8(8) multi-horizon predictions
            - Target: EMA copy of predictor (no gradients)
            - Horizons: [1, 2, 4, 8] steps ahead

        Reference: LeCun (2022), Assran et al. (2023)
        """
        e8_dim = 8  # E8 lattice dimension
        hidden_dim = 64  # Compact predictor for efficiency

        # Predictor network (online, trainable)
        # Input: E8 latent [B, 8] → Output: 4 horizon predictions [B, 4, 8]
        self.h_jepa_predictor = nn.Sequential(
            nn.Linear(e8_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, 4 * e8_dim),  # 4 horizons * 8D each
        )

        # Target network (EMA, frozen)
        # FIX (Dec 28, 2025): Initialize with DIFFERENT random weights
        # This ensures predictor and target produce different outputs from the start
        # allowing meaningful H-JEPA loss from step 1
        self.h_jepa_target = nn.Sequential(
            nn.Linear(e8_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, 4 * e8_dim),
        )

        # DON'T copy predictor to target - let them start with different random weights
        # This creates initial divergence for meaningful H-JEPA loss
        # The EMA updates will gradually align them over time
        for p_target in self.h_jepa_target.parameters():
            p_target.requires_grad = False  # Freeze target network

        logger.debug("✅ H-JEPA networks initialized (predictor + target, horizons=[1,2,4,8])")

    def _extract_s7_at_all_levels(
        self,
        encoder_states: dict[str, Any],
        core_state: CoreState,
    ) -> dict[str, Any]:
        """Extract S7 phase at all hierarchy levels.

        Returns metrics dict[str, Any] with s7_phases and strange_loop info.
        """
        metrics: dict[str, Any] = {}

        self._ensure_s7_hierarchy()
        if self._s7_hierarchy is None:
            return metrics

        # Get E8 representation from encoder (248D adjoint representation)
        # The key is "e8_248" for the full 248D E8 representation
        e8 = encoder_states.get("e8_248")
        if e8 is None:
            e8 = encoder_states.get("e8")
        if e8 is None:
            return metrics

        # Ensure we have the 248D representation (not the 8D quantized version)
        if e8.shape[-1] != 248:
            logger.debug(f"S7 extraction skipped: e8 shape {e8.shape} is not 248D")
            return metrics

        try:
            # Project through S7-augmented hierarchy
            result = self._s7_hierarchy.project_all(e8, return_intermediates=False)  # type: ignore[operator]
            s7_phases = result.get("s7_phases") if isinstance(result, dict) else None

            if s7_phases is not None:
                # Populate CoreState with S7 at all levels
                core_state.s7_e8 = s7_phases.s7_e8
                core_state.s7_e7 = s7_phases.s7_e7
                core_state.s7_e6 = s7_phases.s7_e6
                core_state.s7_f4 = s7_phases.s7_f4

                # Canonical s7_phase is from G2→S7
                if s7_phases.s7_g2 is not None:
                    core_state.s7_phase = s7_phases.s7_g2

                # Coherence across levels (keep as float for core_state, but avoid .item() in graph)
                if s7_phases.coherence is not None:
                    # Use detach() to avoid graph break, then convert
                    core_state.s7_coherence = float(s7_phases.coherence.mean().detach().cpu())

                metrics["s7_phases"] = {
                    "e8": s7_phases.s7_e8,
                    "e7": s7_phases.s7_e7,
                    "e6": s7_phases.s7_e6,
                    "f4": s7_phases.s7_f4,
                    "g2": s7_phases.s7_g2,
                    "coherence": s7_phases.coherence,
                }

            # Update μ_self tracker (strange loop convergence)
            if self._s7_tracker is not None and core_state.s7_phase is not None:
                tracker_result = self._s7_tracker.update(core_state.s7_phase)

                core_state.mu_self = self._s7_tracker.mu_self
                core_state.fixed_point_distance = tracker_result["distance"]

                # Update internal buffer
                mu_self_tensor = self._s7_tracker.mu_self
                if isinstance(mu_self_tensor, torch.Tensor):
                    self._mu_self.copy_(mu_self_tensor)

                self._mu_self_initialized = True

                metrics["strange_loop"] = {
                    "convergence_h": tracker_result["convergence_h"],
                    "distance_to_fixed_point": tracker_result["distance"],
                    "converged": tracker_result["converged"],
                    "mu_self": self._s7_tracker.mu_self,
                }

                # Loop closure loss (differentiable)
                if s7_phases is not None and s7_phases.s7_g2 is not None:
                    mu_expanded = self._mu_self.unsqueeze(0).unsqueeze(0).expand_as(s7_phases.s7_g2)

                    metrics["loop_closure_loss"] = (s7_phases.s7_g2 - mu_expanded).pow(2).mean()

        except Exception as e:
            logger.debug("S7 extraction failed: %s", e)

        return metrics

    # -------------------------------------------------------------------------
    # All encoding/decoding/inference/training methods moved to mixins!
    # See: model_encoder.py, model_decoder.py, model_inference.py, model_training.py
    # -------------------------------------------------------------------------
    # Methods provided by mixins:
    # - EncoderMixin: encode(), encode_observation(), observe(), _project_to_bulk_dim()
    # - DecoderMixin: decode()
    # - InferenceMixin: forward(), _compute_h_jepa_predictions(), update_h_jepa_target()
    # - TrainingMixin: training_step(), _compute_h_jepa_loss(), on_epoch_end()
    # -------------------------------------------------------------------------

    # ---------------------------------------------------------------------
    # Strange Loop Access (public API)
    # ---------------------------------------------------------------------

    @property
    def mu_self(self) -> torch.Tensor:
        """Current fixed point estimate in S7 space (7D)."""
        return self._mu_self.clone()

    @property
    def s7_tracker(self) -> Any:
        """Access to StrangeLoopS7Tracker (lazy-init)."""
        self._ensure_s7_hierarchy()
        return self._s7_tracker

    @property
    def s7_hierarchy(self) -> nn.Module | None:
        """Access to S7AugmentedHierarchy (lazy-init)."""
        self._ensure_s7_hierarchy()
        return self._s7_hierarchy

    # ---------------------------------------------------------------------
    # Causal Grounded Intelligence (December 27, 2025)
    # ---------------------------------------------------------------------

    @property
    def causal_grounded(self) -> nn.Module | None:
        """Access to CausalGroundedWorldModel (causal + temporal + embodied)."""
        return self._causal_grounded

    @property
    def causal_reasoning_engine(self) -> nn.Module | None:
        """Access to CausalReasoningEngine for counterfactual queries."""
        if self._causal_grounded is None:
            return None
        return getattr(self._causal_grounded, "causal_engine", None)

    @property
    def temporal_abstraction(self) -> nn.Module | None:
        """Access to TemporalAbstractionLayer for long-horizon planning."""
        if self._causal_grounded is None:
            return None
        return getattr(self._causal_grounded, "temporal_abstraction", None)

    @property
    def sensorimotor_encoder(self) -> nn.Module | None:
        """Access to SensorimotorEncoder for Genesis physics grounding."""
        if self._causal_grounded is None:
            return None
        return getattr(self._causal_grounded, "sensorimotor_encoder", None)

    def counterfactual(
        self,
        observation: Any,
        factual_action: Any,
        counterfactual_action: Any,
        next_observation: Any | None = None,
    ) -> Any:
        """Perform counterfactual reasoning.

        "What would have happened if action A' was taken instead of A?"

        Args:
            observation: Current observation (tensor)
            factual_action: Action that was taken
            counterfactual_action: Alternative action to evaluate
            next_observation: Actual next state (for abduction)

        Returns:
            CounterfactualResult with factual and counterfactual outcomes
        """
        if self._causal_grounded is None:
            raise RuntimeError("CausalGroundedWorldModel not initialized")

        from kagami.core.world_model.causal_grounded_integration import CounterfactualQuery

        query = CounterfactualQuery(
            observation=observation,
            factual_action=factual_action,
            counterfactual_action=counterfactual_action,
        )
        return self._causal_grounded.counterfactual(query, next_observation)  # type: ignore

    def imagine_macro_action(
        self,
        initial_state: Any,
        horizon: int = 50,
    ) -> Any:
        """Plan using temporal abstraction (macro-actions).

        Plans at the level of "refactor module" instead of "type character".

        Args:
            initial_state: Starting state [B, state_dim]
            horizon: Planning horizon

        Returns:
            HierarchicalPlanResult with macro and primitive actions
        """
        if self._causal_grounded is None:
            raise RuntimeError("CausalGroundedWorldModel not initialized")

        return self._causal_grounded.imagine_macro_action(initial_state, horizon)  # type: ignore

    def encode_sensorimotor(
        self,
        physics_state: Any,
    ) -> Any:
        """Encode Genesis physics state to E8.

        Grounds abstract knowledge in embodied experience.

        Args:
            physics_state: Genesis physics state [B, T, physics_dim]

        Returns:
            E8 code [B, T, 8]
        """
        if self._causal_grounded is None:
            raise RuntimeError("CausalGroundedWorldModel not initialized")

        return self._causal_grounded.encode_sensorimotor(physics_state)  # type: ignore

    def grounded_forward(
        self,
        physics_state: Any,
        s7_phase: Any | None = None,
        action: Any | None = None,
    ) -> dict[str, Any]:
        """Forward pass with embodied grounding.

        Full pipeline:
        1. Encode Genesis physics → E8
        2. Run through RSSM
        3. Return predictions + grounding info

        Args:
            physics_state: Genesis physics state [B, T, physics_dim]
            s7_phase: Optional S7 phase [B, T, 7]
            action: Optional action [B, T, action_dim]

        Returns:
            Dict with predictions and grounding metrics
        """
        if self._causal_grounded is None:
            raise RuntimeError("CausalGroundedWorldModel not initialized")

        return self._causal_grounded.grounded_forward(physics_state, s7_phase, action)  # type: ignore

    # ---------------------------------------------------------------------
    # Optional wiring hooks
    # ---------------------------------------------------------------------

    def _wire_optimality_improvements(self) -> None:
        """Best-effort wiring for optional optimality patches."""
        try:
            from kagami.core.optimality.integration import integrate_all_improvements

            self._optimality_wiring = integrate_all_improvements(self)  # type: ignore[assignment]
        except Exception as e:
            logger.debug("Optimality wiring skipped: %s", e)
            self._optimality_wiring = None

    # ---------------------------------------------------------------------
    # DEPRECATION GUARD (December 14, 2025)
    # ---------------------------------------------------------------------

    def __getattr__(self, name: str) -> Any:
        """Intercept attribute access to provide helpful migration errors.

        RSSM RE-INTEGRATION (Dec 22, 2025):
        ===================================
        OrganismRSSM is now properly wired into KagamiWorldModel.forward()!
        Access it via model.organism_rssm.

        The old 'rssm' attribute is deprecated - use 'organism_rssm' instead.
        """
        # Provide helpful migration errors for specific deprecated attributes
        if name == "rssm":
            raise AttributeError(
                f"\n{'=' * 70}\n"
                f"KagamiWorldModel.rssm is deprecated.\n\n"
                f"Use model.organism_rssm instead (re-integrated Dec 22, 2025).\n"
                f"{'=' * 70}\n"
            )

        # NOTE (Dec 22, 2025): organism_rssm is now wired into KagamiWorldModel!
        # The guard has been removed since RSSM is now properly integrated.

        # CRITICAL: Call super().__getattr__() to allow normal nn.Module attribute resolution
        # nn.Module stores submodules in _modules dict[str, Any], not __dict__, so we must delegate
        # to the parent class to check _modules, _parameters, and _buffers.
        try:
            return super().__getattr__(name)
        except AttributeError as e:
            # If parent class also doesn't have it, raise our custom error
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'") from e
