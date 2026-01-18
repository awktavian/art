"""JAX Training Configurations.

Model size presets for TPU training:

- Small  (~12M):  Edge deployment (mobile, RPi)
- Base   (~50M):  Default training
- Large  (~200M): Teacher for distillation
- XL     (~500M): Research/LMARENA

Student Configs (for knowledge distillation):
- Small  (12M):  Raspberry Pi / embedded
- Base   (50M):  Desktop / mobile
- Large  (200M): Server API

SOTA Research Configs (sota_research.py):
- DreamerV3: World model best practices
- DeepSeek V3 MLA: Attention efficiency
- Mamba-2: Linear complexity SSM
- Phi-4: Data efficiency
- Modern LLM: GQA, RoPE, SwiGLU

Usage:
    # Large model for training
    from kagami.core.training.jax.configs import get_large_model_config
    config = get_large_model_config()

    # Student config for distillation
    from kagami.core.training.jax.configs import get_student_config
    student = get_student_config("small")

    # SOTA research config
    from kagami.core.training.jax.configs import get_sota_config
    sota = get_sota_config()

Created: January 9, 2026
Updated: January 12, 2026 - Added student configs
"""

from .large_tpu import (
    LargeModelConfig,
    get_large_curriculum_config,
    get_large_curriculum_phases,
    get_large_loss_config,
    get_large_model_config,
    get_large_multimodal_config,
    get_large_rssm_config,
    get_large_training_config,
)
from .sota_research import (
    AttentionType,
    DreamerV3Config,
    Mamba2Config,
    MLAConfig,
    PhiDataConfig,
    SOTALLMConfig,
    SOTAOrganismConfig,
    SOTATrainingConfig,
    SSMType,
    get_sota_config,
    get_sota_config_small,
    get_sota_config_xl,
)
from .student_configs import (
    STUDENT_BASE,
    STUDENT_CONFIGS,
    STUDENT_LARGE,
    STUDENT_SMALL,
    StudentConfig,
    get_student_config,
    list_student_configs,
)

__all__ = [
    # SOTA research configs
    "AttentionType",
    "DreamerV3Config",
    # Large model (teacher for distillation)
    "LargeModelConfig",
    "MLAConfig",
    "Mamba2Config",
    "PhiDataConfig",
    "SOTALLMConfig",
    "SOTAOrganismConfig",
    "SOTATrainingConfig",
    "SSMType",
    "get_large_curriculum_config",
    "get_large_curriculum_phases",
    "get_large_loss_config",
    "get_large_model_config",
    "get_large_multimodal_config",
    "get_large_rssm_config",
    "get_large_training_config",
    "get_sota_config",
    "get_sota_config_small",
    "get_sota_config_xl",
    # Student configs (for distillation)
    "StudentConfig",
    "STUDENT_CONFIGS",
    "STUDENT_SMALL",
    "STUDENT_BASE",
    "STUDENT_LARGE",
    "get_student_config",
    "list_student_configs",
]
