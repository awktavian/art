"""Intrinsic Motivation System.

Provides intrinsic rewards for:
1. Empowerment - maximize future control I(A; S'|S)
2. Multi-Step Empowerment - extended horizon influence E_n(s)
3. Curiosity - seek unpredictable outcomes
4. Goal Generation - set and achieve self-motivated goals
5. Skill Empowerment - empowerment over learned skill space

Created: November 2, 2025
Updated: December 2025 - Consolidated into world_model
"""

from kagami.core.world_model.intrinsic.curiosity import (
    CuriosityModule,
    RandomNetworkDistillation,
    compute_curiosity_simple,
)
from kagami.core.world_model.intrinsic.empowerment import (
    EmpowermentEstimator,
    EmpowermentReward,
    compute_empowerment_simple,
)
from kagami.core.world_model.intrinsic.multi_step_empowerment import (
    MultiStepEmpowerment,
    MultiStepEmpowermentConfig,
    SkillEmpowerment,
    get_multi_step_empowerment,
    reset_multi_step_empowerment,
)

# Goal generation is optional (may not exist in all installations)
try:
    from kagami.core.world_model.intrinsic.goal_generation import Goal, GoalGenerator, GoalManager

    _GOAL_GENERATION_AVAILABLE = True
except ImportError:
    Goal = None
    GoalGenerator = None
    GoalManager = None
    _GOAL_GENERATION_AVAILABLE = False

__all__ = [
    # Curiosity
    "CuriosityModule",
    # Empowerment (single-step)
    "EmpowermentEstimator",
    "EmpowermentReward",
    "MultiStepEmpowerment",
    # Multi-Step Empowerment
    "MultiStepEmpowermentConfig",
    "RandomNetworkDistillation",
    "SkillEmpowerment",
    "compute_curiosity_simple",
    "compute_empowerment_simple",
    "get_multi_step_empowerment",
    "reset_multi_step_empowerment",
]

# Add goal generation exports only if available
if _GOAL_GENERATION_AVAILABLE:
    __all__.extend(["Goal", "GoalGenerator", "GoalManager"])
