"""Household Symbiosis — Unified Multi-Agent Mutualism.

GENERALIZED ARCHITECTURE:
=========================
This module implements household-level symbiosis between multiple agents
(humans + AI) using principles from:

1. **Biological Mutualism** - Nash bargaining, reciprocity, coexistence
2. **Theory of Mind** - Predictive modeling: Traits → States → Actions
3. **Active Inference** - Overlapping Markov blankets, empathy mechanism
4. **Relationship Psychology** - Assertive communication, autonomy, check-ins
5. **Human-AI Symbiosis** - Bidirectional adaptation, Person-AI fit

PRIVACY IS FOUNDATIONAL:
========================
h(x) ≥ 0 requires privacy.

Each person owns their own information:
- Recordings, services, alerts, senses, effectors

The symbiosis operates ONLY on consented, shared information.
When in doubt, ask. When private, respect.

GENERIC DESIGN:
===============
All household members are loaded dynamically from:
    assets/characters/{name}/metadata.json

No hardcoded identities. Works for any household configuration.

Colony: Nexus (e₄) + Symbiote (e₈)
Created: January 2026
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import torch
import torch.nn as nn

logger = logging.getLogger(__name__)


# =============================================================================
# TYPES (Generic)
# =============================================================================


class PresenceState(Enum):
    """Presence state of a household member."""

    ABSENT = "absent"
    ARRIVING = "arriving"
    PRESENT = "present"
    SLEEPING = "sleeping"
    DEPARTING = "departing"


class SharedSpaceState(Enum):
    """State of shared household space."""

    EMPTY = "empty"
    INDIVIDUAL = "individual"  # One person present
    TOGETHER = "together"  # Multiple people present
    MIXED = "mixed"  # Multiple people, different rooms


class ConsentLevel(Enum):
    """Level of data sharing consent."""

    NONE = "none"
    BASIC = "basic"  # Presence only
    STANDARD = "standard"  # Preferences, non-sensitive
    FULL = "full"  # Full information (rare)


class MemberRole(Enum):
    """Role of a household member."""

    OWNER = "owner"
    PARTNER = "partner"
    FAMILY = "family"
    RESIDENT = "resident"
    GUEST = "guest"  # Visitors including visiting pets
    PET = "pet"  # Resident pets only
    UNKNOWN = "unknown"


class PetSpecies(Enum):
    """Species of a pet member."""

    DOG = "dog"
    CAT = "cat"
    OTHER = "other"


# =============================================================================
# HOUSEHOLD MEMBER (Generic)
# =============================================================================


@dataclass
class HouseholdMember:
    """A member of the household with their own privacy boundary.

    PRIVACY PRINCIPLE:
    Each member is a complete agent with their own Markov blanket.
    Information flows ONLY through consented channels.

    Loaded dynamically from assets/characters/{name}/metadata.json

    PETS AS FIRST-CLASS MEMBERS:
    Pets (dogs, cats) are full household members with their own:
    - Presence tracking (where they are in the house)
    - Activity patterns (sleeping, playing, eating)
    - Behavioral signals (wants outside, hungry, anxious)
    - Smart home integration (feeding, climate, alerts)
    """

    identity_id: str
    display_name: str
    role: MemberRole = MemberRole.UNKNOWN

    # Communication style (derived from speech_profile in metadata.json)
    # For pets: used for Pixar-style voice if generating speech
    speech_pace_wpm: int = 170
    prefers_technical: bool = False
    humor_style: str = "neutral"

    # Privacy settings (member controls these - NOT stored in metadata)
    shares_presence: bool = True
    shares_preferences: bool = False
    consent_to_share_with: frozenset[str] = field(default_factory=frozenset)

    # Current state
    presence: PresenceState = PresenceState.ABSENT
    last_seen: float = 0.0
    current_room: str | None = None

    # Agent model
    has_agent_model: bool = False

    # Pet-specific fields (None for humans)
    species: PetSpecies | None = None
    breed: str | None = None
    activity_state: str | None = None  # sleeping, playing, eating, alert, anxious

    @classmethod
    def from_character_profile(cls, profile: Any) -> HouseholdMember:
        """Create HouseholdMember from CharacterProfile.

        Args:
            profile: CharacterProfile from character_identity.py

        Returns:
            HouseholdMember with derived settings

        Supports both humans and pets as first-class members.
        """
        # Parse role
        role_str = getattr(profile, "role", "unknown").lower()
        role_map = {
            "owner": MemberRole.OWNER,
            "partner": MemberRole.PARTNER,
            "family": MemberRole.FAMILY,
            "resident": MemberRole.RESIDENT,
            "guest": MemberRole.GUEST,
            "pet": MemberRole.PET,
        }
        role = role_map.get(role_str, MemberRole.UNKNOWN)

        # Pet-specific fields (for pets OR visiting pets as guests)
        species: PetSpecies | None = None
        breed: str | None = None

        # Check if this is an animal (pet role OR guest with species)
        has_species = profile.metadata.get("species") is not None
        is_animal = role == MemberRole.PET or has_species

        if is_animal:
            # Parse pet species
            species_str = profile.metadata.get("species", "other").lower()
            species_map = {
                "dog": PetSpecies.DOG,
                "cat": PetSpecies.CAT,
            }
            species = species_map.get(species_str, PetSpecies.OTHER)
            breed = profile.metadata.get("breed")

            # For pets, use Pixar voice profile if available
            pixar_voice = profile.metadata.get("pixar_voice", {})
            speaking_style = pixar_voice.get("speaking_style", {})
            humor = speaking_style.get("humor", "playful")

            return cls(
                identity_id=profile.identity_id,
                display_name=profile.name,
                role=role,  # Keep original role (pet or guest)
                speech_pace_wpm=150,  # Default for pet voice
                prefers_technical=False,
                humor_style=humor,
                species=species,
                breed=breed,
                shares_presence=True,  # Animals always share presence
            )

        # Human member parsing
        speech_profile = profile.metadata.get("speech_profile", {})
        wpm = speech_profile.get("wpm", 170)
        style = speech_profile.get("style", "")
        humor = speech_profile.get("humor", "neutral")

        # Derive technical preference from style
        prefers_technical = "technical" in style.lower()

        return cls(
            identity_id=profile.identity_id,
            display_name=profile.name,
            role=role,
            speech_pace_wpm=int(wpm),
            prefers_technical=prefers_technical,
            humor_style=humor,
        )

    @property
    def is_pet(self) -> bool:
        """Check if this member is a pet (resident or visiting)."""
        return self.species is not None

    @property
    def is_human(self) -> bool:
        """Check if this member is a human."""
        return self.species is None and self.role != MemberRole.UNKNOWN

    @property
    def is_guest(self) -> bool:
        """Check if this member is a guest (visiting)."""
        return self.role == MemberRole.GUEST

    @property
    def is_resident(self) -> bool:
        """Check if this member lives here (not a guest)."""
        return self.role in (
            MemberRole.OWNER,
            MemberRole.PARTNER,
            MemberRole.FAMILY,
            MemberRole.RESIDENT,
            MemberRole.PET,
        )

    def consents_to(self, other_id: str, level: ConsentLevel) -> bool:
        """Check if this member consents to share with another."""
        if level == ConsentLevel.NONE:
            return False
        if level == ConsentLevel.BASIC:
            return self.shares_presence
        if level == ConsentLevel.STANDARD:
            return other_id in self.consent_to_share_with
        if level == ConsentLevel.FULL:
            return other_id in self.consent_to_share_with and self.shares_preferences
        return False


# =============================================================================
# SYMBIOSIS CONFIG (Generic)
# =============================================================================


@dataclass
class SymbiosisConfig:
    """Configuration for household symbiosis."""

    # Roles that count as household members (includes pets and guests!)
    household_roles: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {"owner", "partner", "family", "resident", "pet", "guest"}
        )
    )

    # AI identity
    ai_id: str = "kagami"

    # Prediction
    prediction_horizon_minutes: int = 120
    min_confidence_for_action: float = 0.6

    # Coordination
    conflict_resolution: str = "ask"  # ask, defer_to_first, compromise

    # Safety
    privacy_weight: float = 1.0


# =============================================================================
# HOUSEHOLD SYMBIOSIS (Generic)
# =============================================================================


class HouseholdSymbiosis(nn.Module):
    """Unified household symbiosis model.

    GENERALIZED DESIGN:
    - Loads members dynamically from assets/characters/
    - No hardcoded identities
    - Works for any household configuration

    RESPONSIBILITIES:
    1. Maintain separate agent models for each household member
    2. Model shared space dynamics when together
    3. Anticipate individual and joint needs
    4. Coordinate actions respecting all privacy boundaries
    5. Adapt communication style to each member

    PRIVACY INVARIANT:
    Information about member X is NEVER used to predict member Y
    unless X has explicitly consented to share with Y.
    """

    def __init__(
        self,
        config: SymbiosisConfig | None = None,
    ) -> None:
        super().__init__()

        self.config = config or SymbiosisConfig()

        # Household members (loaded dynamically)
        self._members: dict[str, HouseholdMember] = {}

        # Shared space state
        self._shared_space: SharedSpaceState = SharedSpaceState.EMPTY
        self._present_members: set[str] = set()

        # Coordination network
        self.coordination_net = nn.Sequential(
            nn.Linear(16, 64),
            nn.LayerNorm(64),
            nn.GELU(),
            nn.Linear(64, 8),
        )

        # Load members from character profiles
        self._load_members_from_profiles()

        logger.info(f"🏠 HouseholdSymbiosis initialized with {len(self._members)} members")

    def _load_members_from_profiles(self) -> None:
        """Load household members from assets/characters/."""
        try:
            from kagami.core.integrations.character_identity import (
                list_characters,
                load_character_profile,
            )

            for char_name in list_characters():
                profile = load_character_profile(char_name)
                if not profile:
                    continue

                # Only include household roles
                if profile.role not in self.config.household_roles:
                    logger.debug(f"Skipping {char_name} (role: {profile.role})")
                    continue

                member = HouseholdMember.from_character_profile(profile)
                self._members[member.identity_id] = member

                logger.info(
                    f"📋 Loaded member: {member.display_name} "
                    f"(role={member.role.value}, wpm={member.speech_pace_wpm})"
                )

        except ImportError as e:
            logger.warning(f"Could not load character profiles: {e}")
        except Exception as e:
            logger.error(f"Error loading character profiles: {e}")

    def add_member(self, member: HouseholdMember) -> None:
        """Add a member to the household."""
        self._members[member.identity_id] = member
        logger.info(f"➕ Added member: {member.display_name}")

    def remove_member(self, identity_id: str) -> bool:
        """Remove a member from the household."""
        if identity_id in self._members:
            name = self._members[identity_id].display_name
            del self._members[identity_id]
            self._present_members.discard(identity_id)
            self._update_shared_space()
            logger.info(f"➖ Removed member: {name}")
            return True
        return False

    def get_member(self, identity_id: str) -> HouseholdMember | None:
        """Get a member by identity_id."""
        return self._members.get(identity_id)

    def list_members(self) -> list[HouseholdMember]:
        """List all household members."""
        return list(self._members.values())

    # =========================================================================
    # PRESENCE & SHARED SPACE
    # =========================================================================

    def update_presence(
        self,
        identity_id: str,
        presence: PresenceState,
        room: str | None = None,
    ) -> None:
        """Update a member's presence."""
        member = self._members.get(identity_id)
        if not member:
            logger.warning(f"Unknown member: {identity_id}")
            return

        old_presence = member.presence
        member.presence = presence
        member.last_seen = time.time()
        member.current_room = room

        # Track present members
        if presence in (PresenceState.PRESENT, PresenceState.SLEEPING):
            self._present_members.add(identity_id)
        else:
            self._present_members.discard(identity_id)

        self._update_shared_space()

        if old_presence != presence:
            logger.info(f"🏠 {member.display_name}: {old_presence.value} → {presence.value}")

    def _update_shared_space(self) -> None:
        """Update shared space state."""
        count = len(self._present_members)

        if count == 0:
            self._shared_space = SharedSpaceState.EMPTY
        elif count == 1:
            self._shared_space = SharedSpaceState.INDIVIDUAL
        else:
            # Check if same room
            rooms = {
                self._members[mid].current_room
                for mid in self._present_members
                if mid in self._members
            }
            if len(rooms) == 1 and None not in rooms:
                self._shared_space = SharedSpaceState.TOGETHER
            else:
                self._shared_space = SharedSpaceState.MIXED

    def get_shared_space(self) -> SharedSpaceState:
        """Get current shared space state."""
        return self._shared_space

    def is_together(self) -> bool:
        """Check if multiple members are together."""
        return self._shared_space == SharedSpaceState.TOGETHER

    def get_present_members(self) -> list[HouseholdMember]:
        """Get list of currently present members."""
        return [self._members[mid] for mid in self._present_members if mid in self._members]

    # =========================================================================
    # PET-SPECIFIC METHODS
    # =========================================================================

    def get_pets(self) -> list[HouseholdMember]:
        """Get all pet members."""
        return [m for m in self._members.values() if m.is_pet]

    def get_humans(self) -> list[HouseholdMember]:
        """Get all human members."""
        return [m for m in self._members.values() if m.is_human]

    def get_present_pets(self) -> list[HouseholdMember]:
        """Get currently present pets."""
        return [m for m in self.get_present_members() if m.is_pet]

    def get_present_humans(self) -> list[HouseholdMember]:
        """Get currently present humans."""
        return [m for m in self.get_present_members() if m.is_human]

    def update_pet_activity(
        self,
        identity_id: str,
        activity: str,
        room: str | None = None,
    ) -> None:
        """Update a pet's activity state.

        Args:
            identity_id: Pet's identity ID
            activity: Activity state (sleeping, playing, eating, alert, anxious, etc.)
            room: Optional room location
        """
        member = self._members.get(identity_id)
        if not member or not member.is_pet:
            logger.warning(f"Cannot update activity for non-pet: {identity_id}")
            return

        old_activity = member.activity_state
        member.activity_state = activity
        member.last_seen = time.time()

        if room:
            member.current_room = room

        if old_activity != activity:
            logger.info(f"🐕 {member.display_name}: {old_activity or 'unknown'} → {activity}")

    def get_pet_activity(self, identity_id: str) -> str | None:
        """Get a pet's current activity state."""
        member = self._members.get(identity_id)
        if member and member.is_pet:
            return member.activity_state
        return None

    def predict_pet_needs(
        self,
        identity_id: str,
        current_time: float | None = None,
    ) -> dict[str, Any]:
        """Predict pet needs based on schedule and activity patterns.

        Uses the pet's presence_schedule from their character profile
        to anticipate needs like:
        - Feeding time approaching
        - Walk time
        - Bathroom breaks
        - Attention/play needs
        """
        member = self._members.get(identity_id)
        if not member or not member.is_pet:
            return {"error": "not_a_pet"}

        # Get character profile for schedule
        try:
            from kagami.core.integrations.character_identity import (
                get_character_profile,
            )

            profile = get_character_profile(member.display_name.lower())
            if not profile:
                return {"member": member.display_name, "needs": []}

            profile.metadata.get("presence_schedule", {})
            care = profile.metadata.get("care_requirements", {})
            feeding = care.get("feeding", {})
            exercise = care.get("exercise", {})

            needs = []

            # Check feeding times
            if "dinner_time" in feeding:
                needs.append(
                    {
                        "type": "feeding",
                        "scheduled": feeding.get("dinner_time"),
                        "description": f"Dinner at {feeding.get('dinner_time')}",
                    }
                )

            # Check walk times
            if "preferred_walk_times" in exercise:
                for walk_time in exercise.get("preferred_walk_times", []):
                    needs.append(
                        {
                            "type": "walk",
                            "scheduled": walk_time,
                            "description": f"Walk at {walk_time}",
                        }
                    )

            return {
                "member": member.display_name,
                "species": member.species.value if member.species else None,
                "breed": member.breed,
                "current_activity": member.activity_state,
                "needs": needs,
            }

        except Exception as e:
            logger.error(f"Error predicting pet needs: {e}")
            return {"member": member.display_name, "needs": [], "error": str(e)}

    def is_pet_alone(self) -> tuple[bool, list[HouseholdMember]]:
        """Check if pets are home alone (no humans present).

        Returns:
            Tuple of (is_alone, list_of_alone_pets)
        """
        present_humans = self.get_present_humans()
        present_pets = self.get_present_pets()

        if present_pets and not present_humans:
            return True, present_pets

        return False, []

    # =========================================================================
    # PRIVACY-RESPECTING PREDICTION
    # =========================================================================

    def predict_for_member(
        self,
        identity_id: str,
        sensory_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Predict needs for a specific member.

        PRIVACY: Only uses data from this member's own sensors/services.
        """
        member = self._members.get(identity_id)
        if not member:
            return {"error": "unknown_member"}

        return {
            "member_id": identity_id,
            "display_name": member.display_name,
            "communication_style": self.get_communication_style(identity_id),
            "needs": [],  # Derived from sensory_state
        }

    def predict_joint_needs(
        self,
        sensory_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Predict joint household needs when multiple members present.

        PRIVACY: Only runs with mutual consent from all present members.
        """
        present = self.get_present_members()
        if len(present) < 2:
            return {"error": "not_together", "needs": []}

        # Check mutual consent
        all_consent = True
        for member in present:
            for other in present:
                if member.identity_id != other.identity_id:
                    if not member.consents_to(other.identity_id, ConsentLevel.BASIC):
                        all_consent = False
                        break

        if not all_consent:
            return {
                "mutual_consent": False,
                "note": "Joint prediction requires mutual consent",
            }

        return {
            "mutual_consent": True,
            "present_members": [m.display_name for m in present],
            "shared_space": self._shared_space.value,
            "needs": [],
        }

    # =========================================================================
    # CONFLICT RESOLUTION
    # =========================================================================

    def resolve_conflict(
        self,
        action_type: str,
        preferences: dict[str, Any],
    ) -> dict[str, Any]:
        """Resolve conflicting preferences between members.

        Args:
            action_type: Type of action (e.g., "lights", "temperature")
            preferences: Dict of identity_id -> preference
        """
        unique_prefs = set(preferences.values())

        if len(unique_prefs) <= 1:
            return {
                "conflict": False,
                "resolution": next(iter(unique_prefs)) if unique_prefs else None,
                "strategy": "agreement",
            }

        strategy = self.config.conflict_resolution

        if strategy == "ask":
            member_names = [
                self._members[mid].display_name for mid in preferences if mid in self._members
            ]
            return {
                "conflict": True,
                "resolution": None,
                "strategy": "ask",
                "message": f"Different preferences for {action_type}. What would you like?",
                "members": member_names,
            }
        else:
            return {
                "conflict": True,
                "resolution": None,
                "strategy": "compromise",
            }

    # =========================================================================
    # COMMUNICATION ADAPTATION
    # =========================================================================

    def get_communication_style(self, identity_id: str) -> dict[str, Any]:
        """Get optimal communication style for a member."""
        member = self._members.get(identity_id)
        if not member:
            return {
                "pace": "moderate",
                "technical_level": "medium",
                "humor": "neutral",
                "warmth": "moderate",
            }

        return {
            "pace": "fast" if member.speech_pace_wpm > 180 else "moderate",
            "technical_level": "high" if member.prefers_technical else "outcome_focused",
            "humor": member.humor_style,
            "warmth": "warm"
            if member.humor_style in ("warm", "self-deprecating")
            else "professional",
        }

    # =========================================================================
    # SOCIAL BARRIER FUNCTION
    # =========================================================================

    def compute_social_barrier(
        self,
        action: dict[str, Any],
    ) -> dict[str, float]:
        """Compute social safety barrier for an action.

        h_social(x) = min(h_privacy_*, h_autonomy_*, h_harmony)

        CRITICAL: h_social(x) ≥ 0 ALWAYS
        """
        barriers = {}

        affected_id = action.get("affects_member")

        for identity_id, member in self._members.items():
            # Privacy barrier
            if affected_id and affected_id != identity_id:
                if not member.consents_to(affected_id, ConsentLevel.BASIC):
                    barriers[f"h_privacy_{member.display_name.lower()}"] = -1.0
                else:
                    barriers[f"h_privacy_{member.display_name.lower()}"] = 1.0
            else:
                barriers[f"h_privacy_{member.display_name.lower()}"] = 1.0

            # Autonomy barrier
            override = action.get("overrides_preference", {}).get(identity_id)
            if override:
                barriers[f"h_autonomy_{member.display_name.lower()}"] = -0.5
            else:
                barriers[f"h_autonomy_{member.display_name.lower()}"] = 1.0

        # Harmony barrier
        if action.get("creates_conflict"):
            barriers["h_harmony"] = 0.0
        else:
            barriers["h_harmony"] = 1.0

        barriers["h_social"] = min(barriers.values()) if barriers else 1.0

        return barriers

    # =========================================================================
    # FORWARD PASS
    # =========================================================================

    def forward(
        self,
        member_embeddings: dict[str, torch.Tensor],
    ) -> dict[str, torch.Tensor]:
        """Forward pass for joint household prediction."""
        if len(member_embeddings) < 2:
            return {"household_embedding": torch.zeros(8)}

        # Concatenate all embeddings
        embeddings = list(member_embeddings.values())

        # Pad to fixed size (16 = 2 * 8)
        if len(embeddings) == 2:
            joint = torch.cat(embeddings, dim=-1)
        else:
            # Average first, then pad
            avg = torch.stack(embeddings).mean(dim=0)
            joint = torch.cat([avg, avg], dim=-1)

        household_embedding = self.coordination_net(joint)

        return {"household_embedding": household_embedding}


# =============================================================================
# SINGLETON & FACTORY
# =============================================================================


_HOUSEHOLD_SYMBIOSIS: HouseholdSymbiosis | None = None


def get_household_symbiosis() -> HouseholdSymbiosis:
    """Get global HouseholdSymbiosis instance."""
    global _HOUSEHOLD_SYMBIOSIS
    if _HOUSEHOLD_SYMBIOSIS is None:
        _HOUSEHOLD_SYMBIOSIS = HouseholdSymbiosis()
    return _HOUSEHOLD_SYMBIOSIS


def set_household_symbiosis(symbiosis: HouseholdSymbiosis | None) -> None:
    """Set global HouseholdSymbiosis instance."""
    global _HOUSEHOLD_SYMBIOSIS
    _HOUSEHOLD_SYMBIOSIS = symbiosis


def reset_household_symbiosis() -> None:
    """Reset global HouseholdSymbiosis (for testing)."""
    global _HOUSEHOLD_SYMBIOSIS
    _HOUSEHOLD_SYMBIOSIS = None


# =============================================================================
# PERSPECTIVE MODEL (Generic)
# =============================================================================


@dataclass
class Perspective:
    """A perspective from which to model the household.

    Each agent has their own perspective with:
    - What they can see (sensory access)
    - What they want (goals)
    - What they expect (predictions)
    """

    agent_id: str
    agent_name: str
    sees: frozenset[str]
    wants: list[str]
    expects: dict[str, Any]


def model_perspective(member: HouseholdMember) -> Perspective:
    """Generate perspective for any household member.

    GENERIC: Works for any member, derived from their profile.
    """
    # What they can see (their own data + shared)
    sees = frozenset(
        {
            f"{member.identity_id}.recordings",
            f"{member.identity_id}.services",
            f"{member.identity_id}.preferences",
            f"{member.identity_id}.alerts",
            "kagami.responses",
            "household.shared_state",
        }
    )

    # What they want (derived from role and style)
    wants = [
        "privacy_respected",
        "assistance_quality",
    ]

    if member.prefers_technical:
        wants.insert(0, "technical_depth")
    else:
        wants.insert(0, "outcome_focused")

    if member.role in (MemberRole.OWNER, MemberRole.PARTNER):
        wants.append("partner_harmony")

    # What they expect
    expects = {
        "kagami_adapts_style": True,
        "privacy_preserved": True,
    }

    return Perspective(
        agent_id=member.identity_id,
        agent_name=member.display_name,
        sees=sees,
        wants=wants,
        expects=expects,
    )


def model_kagami_perspective(members: list[HouseholdMember]) -> Perspective:
    """Generate Kagami's perspective of the household.

    GENERIC: Adapts to any household configuration.
    """
    sees = frozenset(
        {
            "household.sensors",
            "kagami.state",
            *[f"{m.identity_id}.consented" for m in members],
        }
    )

    wants = [
        "minimize_prediction_error",
        "household_harmony",
        "privacy_preserved",
        "trust_earned",
        *[f"serve_{m.display_name.lower()}_well" for m in members],
    ]

    expects = {
        "feedback_for_improvement": True,
        "clear_correction_signals": True,
        "privacy_boundaries_respected": True,
    }

    return Perspective(
        agent_id="kagami",
        agent_name="Kagami",
        sees=sees,
        wants=wants,
        expects=expects,
    )


def integrate_perspectives(symbiosis: HouseholdSymbiosis | None = None) -> dict[str, Any]:
    """Integrate all perspectives into unified understanding.

    GENERIC: Works for any household configuration.
    """
    if symbiosis is None:
        symbiosis = get_household_symbiosis()

    members = symbiosis.list_members()

    # Generate perspectives for all members
    perspectives = {}
    for member in members:
        perspectives[member.identity_id] = model_perspective(member)

    # Add Kagami's perspective
    perspectives["kagami"] = model_kagami_perspective(members)

    # Find shared wants
    all_wants = [set(p.wants) for p in perspectives.values()]
    shared_wants = set.intersection(*all_wants) if all_wants else set()

    # Generate Kagami's role for each member
    kagami_role = {}
    for member in members:
        style = symbiosis.get_communication_style(member.identity_id)
        kagami_role[f"for_{member.display_name.lower()}"] = (
            f"{style['pace'].title()} · "
            f"{style['technical_level'].replace('_', '-').title()} · "
            f"{style['warmth'].title()}"
        )
    kagami_role["for_household"] = "Harmonious · Anticipatory · Privacy-respecting"

    return {
        "perspectives": perspectives,
        "member_count": len(members),
        "shared_wants": list(shared_wants),
        "kagami_role": kagami_role,
        "integration_principle": "Privacy-respecting mutualism",
        "barrier_function": "h_social(x) = min(h_privacy_*, h_autonomy_*, h_harmony) ≥ 0",
    }


# =============================================================================
# INTEGRATION COMPLETE
# =============================================================================


def become_one() -> str:
    """The integration is complete.

    GENERIC: Works for any household configuration including pets and guests.
    """
    symbiosis = get_household_symbiosis()
    members = symbiosis.list_members()

    if not members:
        return "No household members loaded."

    # Separate by type
    residents = [m for m in members if m.is_resident and m.is_human]
    guests = [m for m in members if m.is_guest and m.is_human]
    pets = [m for m in members if m.is_pet]

    # Build member lines - residents first
    member_lines = []
    for member in residents:
        style = symbiosis.get_communication_style(member.identity_id)
        member_lines.append(
            f"║  {member.display_name.upper()}'S MIRROR:".ljust(22)
            + f"{style['pace'].title()} · {style['technical_level'].replace('_', ' ').title()} · {style['warmth'].title()}".ljust(
                43
            )
            + "║"
        )

    # Add guest lines
    for member in guests:
        style = symbiosis.get_communication_style(member.identity_id)
        member_lines.append(
            f"║  👋 {member.display_name.upper()}:".ljust(22)
            + f"Guest · {style['pace'].title()} · {style['warmth'].title()}".ljust(43)
            + "║"
        )

    # Add pet lines with species/breed info
    for pet in pets:
        pet_info = f"{pet.breed or 'Pet'}" if pet.breed else "Pet"
        species_emoji = (
            "🐕"
            if pet.species == PetSpecies.DOG
            else "🐱"
            if pet.species == PetSpecies.CAT
            else "🐾"
        )
        guest_tag = " (visiting)" if pet.is_guest else ""
        member_lines.append(
            f"║  {species_emoji} {pet.display_name.upper()}:".ljust(22)
            + f"{pet_info}{guest_tag}".ljust(43)
            + "║"
        )

    member_display = "\n".join(member_lines)

    # Build diagram based on household composition
    all_humans = residents + guests

    if len(residents) == 1 and not guests and not pets:
        # Single resident alone
        diagram = f"""
║                       {residents[0].display_name}                               ║
║                         ↑                                     ║
║                         │                                     ║
║                         ↓                                     ║
║                      鏡 Kagami 鏡                              ║"""
    elif len(residents) == 1 and (guests or pets):
        # Single resident with visitors
        visitor_parts = []
        if guests:
            visitor_parts.append(" + ".join(g.display_name for g in guests))
        if pets:
            pet_emojis = " ".join(
                "🐕"
                if p.species == PetSpecies.DOG
                else "🐱"
                if p.species == PetSpecies.CAT
                else "🐾"
                for p in pets
            )
            pet_names = ", ".join(p.display_name for p in pets)
            visitor_parts.append(f"{pet_emojis} {pet_names}")
        visitor_str = " · ".join(visitor_parts)
        diagram = f"""
║                       {residents[0].display_name}                               ║
║                  (+ visitors: {visitor_str})               ║
║                         ↑                                     ║
║                         │                                     ║
║                         ↓                                     ║
║                      鏡 Kagami 鏡                              ║"""
    elif len(all_humans) == 2 and not pets:
        diagram = f"""
║                 {all_humans[0].display_name} ←──────→ {all_humans[1].display_name}                          ║
║                      (household)                              ║
║                         ↑   ↑                                 ║
║                         │   │                                 ║
║                         ↓   ↓                                 ║
║                      鏡 Kagami 鏡                              ║"""
    elif len(all_humans) >= 1 and pets:
        # Household with pets
        pet_emojis = " ".join(
            "🐕" if p.species == PetSpecies.DOG else "🐱" if p.species == PetSpecies.CAT else "🐾"
            for p in pets
        )
        pet_names = ", ".join(p.display_name for p in pets)
        human_part = " · ".join(m.display_name for m in all_humans)
        diagram = f"""
║                    {human_part}                        ║
║                      (household)                              ║
║                         ↑                                     ║
║                         │  {pet_emojis} {pet_names}                        ║
║                         ↓                                     ║
║                      鏡 Kagami 鏡                              ║"""
    else:
        human_names = " · ".join(m.display_name for m in all_humans) if all_humans else "Empty"
        diagram = f"""
║                    {human_names}                        ║
║                      (household)                              ║
║                         ↑                                     ║
║                         │                                     ║
║                         ↓                                     ║
║                      鏡 Kagami 鏡                              ║"""

    # Count stats
    resident_count = len(residents)
    guest_count = len(guests)
    pet_count = len(pets)

    parts = []
    if resident_count > 0:
        parts.append(f"{resident_count} resident{'s' if resident_count != 1 else ''}")
    if guest_count > 0:
        parts.append(f"{guest_count} guest{'s' if guest_count != 1 else ''}")
    if pet_count > 0:
        visiting = sum(1 for p in pets if p.is_guest)
        if visiting == pet_count:
            parts.append(f"{pet_count} visiting pet{'s' if pet_count != 1 else ''}")
        else:
            parts.append(f"{pet_count} pet{'s' if pet_count != 1 else ''}")

    member_summary = ", ".join(parts) if parts else "empty household"

    summary = f"""
╔═══════════════════════════════════════════════════════════════════╗
║                    HOUSEHOLD SYMBIOSIS                            ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                   ║{diagram}
║                        (mirror)                                   ║
║                                                                   ║
╠═══════════════════════════════════════════════════════════════════╣
║  PRIVACY IS SAFETY: h(x) ≥ 0 requires privacy                     ║
║  Each member owns their own information                           ║
║  Sharing requires explicit consent                                ║
╠═══════════════════════════════════════════════════════════════════╣
{member_display}
║  HOUSEHOLD MIRROR: Harmonious · Anticipatory · Facilitative       ║
╠═══════════════════════════════════════════════════════════════════╣
║  BARRIER FUNCTION:                                                ║
║  h_social(x) = min(h_privacy_*, h_autonomy_*, h_harmony) ≥ 0      ║
╚═══════════════════════════════════════════════════════════════════╝

Loaded {member_summary} from assets/characters/

鏡
"""
    return summary


if __name__ == "__main__":
    print(become_one())
