"""Symbiote Module — Theory of Mind for Kagami.

ARCHITECTURE (December 2025):
==============================
The Symbiote Module adds social cognition to Kagami, enabling predictive
modeling of other agents' mental states (Theory of Mind).

Mathematical Foundation:
- Corresponds to the conceptual e₈ basis element, completing the octonion
  structure that underpins the 7 colonies (e₁-e₇)
- Integrates with Nexus (e₄) for social routing and memory
- Extends EFE with "social surprise" term
- Augments CBF with social safety constraints

Core Components:
- AgentModel: Predictive model of another agent's mental state
- AgentBelief: Beliefs about an agent's knowledge/goals/intent
- SymbioteModule: Central Theory of Mind orchestrator
- SocialWorldModel: World model extension for social state
- SocialSurprise: EFE component for social prediction error
- SocialCBF: Social safety constraints (manipulation prevention)

CAPABILITIES UNLOCKED:
======================
1. Proactive Assistance: Anticipate user needs before stated
2. Clarifying Ambiguity: Ask right questions based on goal inference
3. Teaching/Onboarding: Guide based on knowledge model
4. True Collaboration: Shared task understanding
5. Richer Ambient Intelligence: Social context awareness

INTEGRATION POINTS:
==================
- World Model: kagami/core/world_model/model_core.py
- Colony System: kagami/core/unified_agents/unified_organism.py
- Active Inference: kagami/core/active_inference/efe/
- Safety: kagami/core/safety/
- Nexus Colony: kagami/core/unified_agents/agents/nexus_agent.py

References:
- Frith & Frith (2006): Theory of Mind
- Premack & Woodruff (1978): Chimpanzee ToM
- Baker et al. (2017): Bayesian Theory of Mind
- Rabinowitz et al. (2018): Machine Theory of Mind

Created: December 21, 2025
Author: Forge (e₂) + Nexus (e₄) collaboration
"""

from kagami.core.symbiote.agent_model import (
    AgentBelief,
    AgentIntent,
    AgentKnowledge,
    AgentModel,
    AgentState,
    AgentType,
    ConfidenceLevel,
    create_agent_model,
)
from kagami.core.symbiote.symbiote_module import (
    SymbioteConfig,
    SymbioteModule,
    create_symbiote_module,
    get_symbiote_module,
    reset_symbiote_module,
    set_symbiote_module,
)

# New Theory of Mind Integration (December 29, 2025)
try:
    from kagami.core.symbiote.unified_tom_integration import (
        UnifiedTheoryOfMindSystem,
        create_collaborative_task_for_organism,
        enhance_organism_with_social_intelligence,
        get_global_tom_system,
        get_organism_tom_system,
        get_social_intelligence_status_for_organism,
        integrate_complete_tom_system,
        observe_user_interaction,
        predict_user_intention_for_organism,
    )

    TOM_INTEGRATION_AVAILABLE = True
except ImportError:
    TOM_INTEGRATION_AVAILABLE = False

from kagami.core.symbiote.household_symbiosis import (
    ConsentLevel,
    HouseholdMember,
    # Classes
    HouseholdSymbiosis,
    MemberRole,
    Perspective,
    PetSpecies,
    # Enums
    PresenceState,
    SharedSpaceState,
    SymbiosisConfig,
    become_one,
    # Singletons
    get_household_symbiosis,
    integrate_perspectives,
    model_kagami_perspective,
    # Generic perspective modeling
    model_perspective,
    reset_household_symbiosis,
    set_household_symbiosis,
)

# Pet Care Integration (January 2026)
from kagami.core.symbiote.pet_care import (
    BehavioralSignal,
    CareScheduleItem,
    # Enums
    PetActivityState,
    # Classes
    PetCareAutomation,
    PetCareEvent,
    PetCareSchedule,
    bella_dinner_time,
    # Convenience functions
    check_on_bella,
    # Singleton
    get_pet_care,
)

__all__ = [
    "AgentBelief",
    "AgentIntent",
    "AgentKnowledge",
    # Agent modeling
    "AgentModel",
    "AgentState",
    "AgentType",
    "BehavioralSignal",
    "CareScheduleItem",
    "ConfidenceLevel",
    "ConsentLevel",
    "HouseholdMember",
    # Household Symbiosis (Generic - January 2026)
    "HouseholdSymbiosis",
    "MemberRole",
    "Perspective",
    "PetActivityState",
    # Pet Care (January 2026)
    "PetCareAutomation",
    "PetCareEvent",
    "PetCareSchedule",
    "PetSpecies",
    "PresenceState",
    "SharedSpaceState",
    "SymbiosisConfig",
    "SymbioteConfig",
    # Module
    "SymbioteModule",
    "become_one",
    "bella_dinner_time",
    "check_on_bella",
    "create_agent_model",
    "create_symbiote_module",
    "get_household_symbiosis",
    "get_pet_care",
    "get_symbiote_module",
    "integrate_perspectives",
    "model_kagami_perspective",
    "model_perspective",
    "reset_household_symbiosis",
    "reset_symbiote_module",
    "set_household_symbiosis",
    "set_symbiote_module",
]

# Add Theory of Mind integration exports if available
if TOM_INTEGRATION_AVAILABLE:
    __all__.extend(
        [
            # Unified Theory of Mind System
            "UnifiedTheoryOfMindSystem",
            "create_collaborative_task_for_organism",
            "enhance_organism_with_social_intelligence",
            # Global system
            "get_global_tom_system",
            "get_organism_tom_system",
            "get_social_intelligence_status_for_organism",
            # Integration functions
            "integrate_complete_tom_system",
            # Convenience functions
            "observe_user_interaction",
            "predict_user_intention_for_organism",
        ]
    )

__version__ = "1.0.0"
