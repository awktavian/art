"""LARGE TPU Model Configuration — Teacher for Distillation.

This is the CANONICAL large model configuration for TPU v6e training.
Use this as the teacher model for knowledge distillation to smaller models.

Model Sizes (Parameter Count):
- Small:  ~12M params   (deter=256, stoch=16, heads=4)
- Base:   ~50M params   (deter=384, stoch=32, heads=8)   [default]
- Large:  ~200M params  (deter=768, stoch=64, heads=16)  [THIS FILE]
- XL:     ~500M params  (deter=1024, stoch=96, heads=16)

TPU v6e-4 (4 chips, 192GB HBM2e total):
- Large model fits comfortably with batch_size=256
- Use FSDP for XL model

Created: January 9, 2026
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config import (
    CurriculumConfig,
    CurriculumPhase,
    LossConfig,
    OrganismRSSMConfig,
    PhaseConfig,
    TrainingConfig,
)
from ..multimodal.config import (
    AudioEncoderConfig,
    CrossModalConfig,
    ModalityType,
    MultimodalConfig,
    TextEncoderConfig,
    VisionEncoderConfig,
)

# =============================================================================
# LARGE MODEL CONFIG (~200M parameters)
# =============================================================================


def get_large_rssm_config() -> OrganismRSSMConfig:
    """Large OrganismRSSM configuration.

    ~200M parameters:
    - 768-dim hidden state (2x base)
    - 64-dim stochastic (2x base)
    - 16 attention heads (2x base)
    - 1024 discrete classes (same as base)

    Memory footprint per batch:
    - Hidden: B×T×7×768 = 344KB per batch at B=64,T=16
    - Total activations: ~500MB at B=256
    """
    return OrganismRSSMConfig(
        # === Dimensions (2x base) ===
        obs_dim=128,  # 2x (richer observations)
        action_dim=8,  # E8 lattice (unchanged)
        num_colonies=7,  # Octonion basis (unchanged)
        deter_dim=768,  # 2x base (384)
        stoch_dim=64,  # 2x base (32)
        # === Discrete Latents ===
        discrete_categories=32,  # 32×32=1024 (unchanged)
        discrete_classes=32,
        latent_classes=240,  # E8 roots (unchanged)
        # === KL Settings ===
        unimix=0.01,
        free_bits=3.0,
        kl_dyn_weight=0.8,
        kl_rep_weight=0.2,
        # === TwoHot ===
        num_reward_bins=255,
        reward_low=-20.0,
        reward_high=20.0,
        # === Architecture (scaled) ===
        gru_num_blocks=16,  # 2x base (8)
        attention_dim=768,  # Match deter_dim
        attention_heads=16,  # 2x base (8)
        head_dim=48,  # 768/16
        attention_dropout=0.1,
        # === SimNorm ===
        simnorm_anchors=8,  # 2x base (4)
        # === H-JEPA Horizons ===
        hjepa_horizons=(1, 4, 16, 64),  # Add 64-step horizon
    )


def get_large_loss_config() -> LossConfig:
    """Loss configuration for large model.

    Higher regularization for larger model:
    - Increased stability loss
    - Balanced multi-horizon HJEPA
    """
    return LossConfig(
        # === TIER 1: Core Prediction ===
        prediction_weight=1.0,
        # === TIER 2: Essential Losses ===
        e8_commitment_weight=0.05,
        e8_commitment_warmup_steps=4000,  # Longer warmup
        ib_kl_weight=0.01,
        ib_free_bits=1.5,  # Slightly higher for larger latent
        rssm_kl_weight=0.1,
        seq_ib_recon_weight=0.1,
        seq_ib_kl_weight=0.01,
        fano_synergy_weight=0.01,
        h_jepa_pred_weight=0.1,  # 2x for multi-horizon
        loop_closure_weight=0.01,
        stability_weight=0.02,  # 2x for larger model
        # === TIER 3: Auxiliary ===
        manifold_curvature_weight=0.01,
        catastrophe_weight=0.0,
        chaos_entropy_weight=0.0,
        recognition_weight=0.0,
        reward_weight=0.5,
        value_weight=0.5,
        continue_weight=0.1,
        # === Gradient Control ===
        max_gradient_norm=50.0,  # Tighter clip for stability
        # === Uncertainty Weighting ===
        enable_uncertainty_weighting=True,  # Enable for large model
    )


def get_large_multimodal_config() -> MultimodalConfig:
    """Large multimodal configuration.

    Uses SOTA encoders:
    - Text: E5-large-v2 (1024D)
    - Vision: SigLIP 2 large (1024D, 384px)
    - Audio: Whisper large (1024D)
    """
    return MultimodalConfig(
        # Text: E5-large-v2 (SOTA retrieval)
        text=TextEncoderConfig(
            model_name="intfloat/e5-large-v2",
            embed_dim=1024,
            max_length=512,
            pooling="mean",
            normalize=True,
            freeze=True,
            project_dim=768,  # Match RSSM
            num_project_layers=3,
        ),
        # Vision: SigLIP 2 large (SOTA vision-language)
        vision=VisionEncoderConfig(
            model_name="google/siglip2-large-patch16-384",
            embed_dim=1024,
            image_size=384,
            patch_size=16,
            freeze=True,
            use_jax_native=True,
            project_dim=768,
            num_project_layers=3,
        ),
        # Audio: Whisper large (SOTA speech)
        audio=AudioEncoderConfig(
            model_name="openai/whisper-large-v3",
            embed_dim=1280,
            sample_rate=16000,
            max_duration=30.0,
            freeze=True,
            project_dim=768,
            num_project_layers=3,
        ),
        # Cross-modal fusion (enhanced)
        cross_modal=CrossModalConfig(
            num_heads=16,
            head_dim=48,
            dropout=0.1,
            num_fusion_layers=4,  # Deeper fusion
            use_hierarchical=True,
            use_lora=True,
            lora_rank=32,  # Higher rank
            lora_alpha=64.0,
            use_modality_gating=True,
            gate_activation="sigmoid",
            use_entity_attention=True,
            num_entities=7,
            residual_scale=0.1,
        ),
        # All modalities enabled
        enabled_modalities=(
            ModalityType.TEXT,
            ModalityType.VISION,
            ModalityType.AUDIO,
        ),
        # RSSM integration
        rssm_latent_dim=768,
        num_colonies=7,
        # Contrastive learning
        contrastive_temperature=0.07,
        contrastive_weight=0.1,
        # Grounding
        grounding_weight=0.5,
        # Training
        freeze_encoders_steps=10000,  # Longer warmup
        encoder_lr_multiplier=0.05,  # Lower LR for large encoders
    )


def get_large_curriculum_config() -> CurriculumConfig:
    """Large model curriculum configuration.

    Longer training with more gradual phase transitions.
    """
    return CurriculumConfig(
        # === Scale Parameters ===
        num_chips=4,  # TPU v6e-4
        baseline_batch_size=256,  # 4x base
        baseline_lr=1e-4,  # Lower for large model
        # === Batch Scaling ===
        max_per_device_batch=64,  # 256/4 chips
        sqrt_scaling_threshold=4096,
        gradient_accumulation_steps=4,  # Effective batch 1024
        # === Learning Rate ===
        base_warmup_steps=5000,  # Longer warmup
        min_warmup_steps=1000,
        lr_scaling_mode="sqrt",
        # === Curriculum ===
        enable_curriculum=True,
        phase_patience=10000,  # 2x patience
        auto_advance=True,
        # === E8 ===
        e8_warmup_start=2000,
        e8_warmup_end=10000,
        # === Total Training ===
        total_steps=500_000,  # 5x longer
        checkpoint_every=5000,
        log_every=100,
    )


def get_large_training_config() -> TrainingConfig:
    """Large model training hyperparameters."""
    return TrainingConfig(
        batch_size=256,
        seq_len=32,  # Longer sequences
        total_steps=500_000,
        learning_rate=1e-4,
        weight_decay=0.05,  # Higher regularization
        warmup_steps=5000,
        grad_clip=50.0,
        seed=42,
    )


# =============================================================================
# LARGE CURRICULUM PHASES (7-phase progression)
# =============================================================================


def get_large_curriculum_phases() -> list[PhaseConfig]:
    """Large model 7-phase curriculum.

    Extended duration per phase for larger model capacity.
    """
    return [
        # === Phase 0: WARMUP (β≈0) ===
        PhaseConfig(
            name=CurriculumPhase.WARMUP,
            min_steps=2000,
            max_steps=10000,
            loss_threshold=0.05,
            gradient_threshold=0.005,
            velocity_threshold=0.005,
            lr_multiplier=1.0,
            e8_weight=0.0,
            kl_weight=0.0,
            kl_beta=1e-6,  # Near-zero for warmup
            recon_weight=1.0,
            reward_weight=0.0,
            fano_weight=0.0,
            hjepa_weight=0.0,
            plateau_patience=500,
            efe_enabled=False,
            alignment_enabled=False,
            language_enabled=False,
            data_weights={"jepa": 1.0},
        ),
        # === Phase 1: GEOMETRY (Fold A₂) ===
        PhaseConfig(
            name=CurriculumPhase.GEOMETRY,
            min_steps=10000,
            max_steps=50000,
            loss_threshold=0.3,
            gradient_threshold=0.01,
            velocity_threshold=0.01,
            lr_multiplier=1.0,
            e8_weight=0.1,
            kl_weight=0.1,
            kl_beta=0.1,
            recon_weight=1.0,
            reward_weight=0.1,
            fano_weight=0.0,
            hjepa_weight=0.05,
            plateau_patience=800,
            efe_enabled=False,
            alignment_enabled=False,
            language_enabled=False,
            data_weights={"jepa": 0.6, "qm9": 0.2, "tree_of_life": 0.2},
        ),
        # === Phase 2: ROTATION (Cusp A₃) ===
        PhaseConfig(
            name=CurriculumPhase.ROTATION,
            min_steps=20000,
            max_steps=80000,
            loss_threshold=0.25,
            gradient_threshold=0.01,
            velocity_threshold=0.01,
            lr_multiplier=0.8,
            e8_weight=0.15,
            kl_weight=0.3,
            kl_beta=0.5,
            recon_weight=1.0,
            reward_weight=0.2,
            fano_weight=0.01,
            hjepa_weight=0.1,
            plateau_patience=1000,
            efe_enabled=False,
            alignment_enabled=True,
            language_enabled=False,
            data_weights={"jepa": 0.5, "qm9": 0.2, "tree_of_life": 0.2, "generation": 0.1},
        ),
        # === Phase 3: DYNAMICS (Swallowtail A₄) ===
        PhaseConfig(
            name=CurriculumPhase.DYNAMICS,
            min_steps=30000,
            max_steps=100000,
            loss_threshold=0.2,
            gradient_threshold=0.005,
            velocity_threshold=0.005,
            lr_multiplier=0.6,
            e8_weight=0.2,
            kl_weight=0.5,
            kl_beta=0.8,
            recon_weight=1.0,
            reward_weight=0.3,
            fano_weight=0.02,
            hjepa_weight=0.15,
            plateau_patience=1200,
            efe_enabled=True,
            alignment_enabled=True,
            language_enabled=False,
            data_weights={"jepa": 0.45, "qm9": 0.2, "tree_of_life": 0.2, "generation": 0.15},
        ),
        # === Phase 4: JOINT (Butterfly A₅) ===
        PhaseConfig(
            name=CurriculumPhase.JOINT,
            min_steps=50000,
            max_steps=150000,
            loss_threshold=0.15,
            gradient_threshold=0.003,
            velocity_threshold=0.003,
            lr_multiplier=0.4,
            e8_weight=0.25,
            kl_weight=0.5,
            kl_beta=1.0,
            recon_weight=1.0,
            reward_weight=0.5,
            fano_weight=0.05,
            hjepa_weight=0.2,
            plateau_patience=1500,
            efe_enabled=True,
            alignment_enabled=True,
            language_enabled=False,
            data_weights={"jepa": 0.35, "qm9": 0.15, "tree_of_life": 0.15, "generation": 0.35},
        ),
        # === Phase 5: GENERATION (Hyperbolic D₄⁺) ===
        PhaseConfig(
            name=CurriculumPhase.GENERATION,
            min_steps=50000,
            max_steps=100000,
            loss_threshold=0.1,
            gradient_threshold=0.002,
            velocity_threshold=0.002,
            lr_multiplier=0.2,
            e8_weight=0.3,
            kl_weight=0.5,
            kl_beta=1.0,
            recon_weight=1.0,
            reward_weight=0.5,
            fano_weight=0.1,
            hjepa_weight=0.2,
            plateau_patience=2000,
            efe_enabled=True,
            alignment_enabled=True,
            language_enabled=False,
            data_weights={"generation": 0.5, "jepa": 0.25, "qm9": 0.15, "tree_of_life": 0.1},
        ),
        # === Phase 6: LANGUAGE (Elliptic D₄⁻) ===
        PhaseConfig(
            name=CurriculumPhase.LANGUAGE,
            min_steps=50000,
            max_steps=100000,
            loss_threshold=0.08,
            gradient_threshold=0.001,
            velocity_threshold=0.001,
            lr_multiplier=0.1,
            e8_weight=0.3,
            kl_weight=0.5,
            kl_beta=1.0,
            recon_weight=1.0,
            reward_weight=0.5,
            fano_weight=0.1,
            hjepa_weight=0.2,
            plateau_patience=2500,
            efe_enabled=True,
            alignment_enabled=True,
            language_enabled=True,  # Enable language grounding
            data_weights={
                "jepa": 0.3,
                "language": 0.3,
                "instruction": 0.2,
                "qm9": 0.1,
                "tree_of_life": 0.1,
            },
        ),
    ]


# =============================================================================
# COMPLETE LARGE CONFIG
# =============================================================================


@dataclass
class LargeModelConfig:
    """Complete large model configuration bundle.

    Usage:
        config = get_large_model_config()
        model = OrganismRSSM(config.rssm)
        trainer = Trainer(config.training, config.curriculum)
    """

    rssm: OrganismRSSMConfig
    loss: LossConfig
    multimodal: MultimodalConfig
    curriculum: CurriculumConfig
    training: TrainingConfig
    phases: list[PhaseConfig]


def get_large_model_config() -> LargeModelConfig:
    """Get complete large model configuration."""
    return LargeModelConfig(
        rssm=get_large_rssm_config(),
        loss=get_large_loss_config(),
        multimodal=get_large_multimodal_config(),
        curriculum=get_large_curriculum_config(),
        training=get_large_training_config(),
        phases=get_large_curriculum_phases(),
    )


# =============================================================================
# EXPORTS
# =============================================================================


__all__ = [
    "LargeModelConfig",
    "get_large_curriculum_config",
    "get_large_curriculum_phases",
    "get_large_loss_config",
    "get_large_model_config",
    "get_large_multimodal_config",
    "get_large_rssm_config",
    "get_large_training_config",
]
