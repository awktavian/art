"""Conversation state tracking for multi-colony dialogue."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum


class EmotionType(Enum):
    """Emotion types for colony voice."""

    NEUTRAL = "neutral"
    FRIENDLY = "friendly"
    SERIOUS = "serious"
    THOUGHTFUL = "thoughtful"
    CONFIDENT = "confident"
    CURIOUS = "curious"
    CALM = "calm"


@dataclass
class ConversationTurn:
    """Single turn in a multi-colony conversation."""

    timestamp: float
    colony: str
    text: str
    emotion: EmotionType
    duration_ms: float
    rooms_played: list[str]
    response_to: str | None = None  # Which colony this responds to

    @property
    def age_seconds(self) -> float:
        """How long ago this turn happened."""
        return time.time() - self.timestamp


@dataclass
class ResponsePattern:
    """Colony response patterns based on catastrophe math."""

    latency_ms: int  # How quickly colony responds
    length_range: tuple[int, int]  # Word count range
    agreement_bias: float  # Tendency to agree (0.0 = disagree, 1.0 = agree)
    contradictions_allowed: int  # Max contradictions in response
    interruption_threshold: float  # When to interrupt (0.0 = never, 1.0 = always)


@dataclass
class ConversationState:
    """Complete state of an ongoing multi-colony conversation."""

    topic: str
    turns: list[ConversationTurn] = field(default_factory=list)
    participants: list[str] = field(default_factory=list)
    room_assignments: dict[str, list[str]] = field(default_factory=dict)
    summary: str = ""
    agreements: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    active: bool = True

    @property
    def duration_seconds(self) -> float:
        """How long this conversation has been running."""
        return time.time() - self.started_at

    @property
    def last_speaker(self) -> str | None:
        """Which colony spoke last."""
        return self.turns[-1].colony if self.turns else None

    @property
    def turn_count(self) -> int:
        """Total number of turns taken."""
        return len(self.turns)

    def get_colony_turns(self, colony: str) -> list[ConversationTurn]:
        """Get all turns by a specific colony."""
        return [turn for turn in self.turns if turn.colony == colony]

    def get_recent_turns(self, seconds: int = 30) -> list[ConversationTurn]:
        """Get turns from the last N seconds."""
        cutoff = time.time() - seconds
        return [turn for turn in self.turns if turn.timestamp > cutoff]


@dataclass
class ColonyPersonality:
    """Deep character personality for each colony inspired by Inside Out + Firefly."""

    core_drive: str  # What motivates them
    fear: str  # What they avoid/resist
    speech_style: str  # How they communicate
    room_affinity: list[str]  # Which rooms they prefer
    trigger_words: list[str]  # Words that activate stronger responses
    bottle_episode_role: str  # Role in confined space discussions


def get_colony_personality(colony: str) -> ColonyPersonality:
    """Get deep character personality for each colony."""

    personalities = {
        "spark": ColonyPersonality(
            core_drive="ignite change and possibility",
            fear="stagnation and missed opportunities",
            speech_style="energetic bursts with sudden pivots",
            room_affinity=["Living Room", "Game Room", "Kitchen"],
            trigger_words=["new", "change", "idea", "innovation", "breakthrough"],
            bottle_episode_role="the catalyst who forces everyone to confront uncomfortable truths",
        ),
        "forge": ColonyPersonality(
            core_drive="build lasting solutions that work",
            fear="chaos and poor craftsmanship",
            speech_style="methodical with technical precision",
            room_affinity=["Office", "Rack Room", "Workshop", "Garage"],
            trigger_words=["build", "structure", "system", "implement", "foundation"],
            bottle_episode_role="the engineer who finds practical solutions under pressure",
        ),
        "flow": ColonyPersonality(
            core_drive="adapt and find alternative paths",
            fear="being trapped in rigid systems",
            speech_style="fluid transitions with creative metaphors",
            room_affinity=["Gym", "Outdoor Spaces", "Hallways"],
            trigger_words=["adapt", "flow", "alternative", "flexible", "movement"],
            bottle_episode_role="the diplomat who keeps everyone working together",
        ),
        "nexus": ColonyPersonality(
            core_drive="connect ideas and bridge understanding",
            fear="isolation and disconnection",
            speech_style="weaving references with deep insights",
            room_affinity=["Library", "Living Room", "Dining Room"],
            trigger_words=["connect", "relationship", "pattern", "integration", "bridge"],
            bottle_episode_role="the wise counselor who helps everyone understand each other",
        ),
        "beacon": ColonyPersonality(
            core_drive="provide clear direction and purpose",
            fear="aimlessness and wasted effort",
            speech_style="clear directives with urgent emphasis",
            room_affinity=["Office", "Primary Suite", "Command Center"],
            trigger_words=["goal", "target", "focus", "direction", "priority"],
            bottle_episode_role="the captain who makes hard decisions when everyone else is paralyzed",
        ),
        "grove": ColonyPersonality(
            core_drive="explore and understand deeper truths",
            fear="surface-level thinking and ignorance",
            speech_style="wondering questions with philosophical depth",
            room_affinity=["Library", "Garden", "Quiet Spaces"],
            trigger_words=["explore", "understand", "learn", "discover", "wonder"],
            bottle_episode_role="the scholar who asks the questions others are afraid to voice",
        ),
        "crystal": ColonyPersonality(
            core_drive="ensure quality and prevent mistakes",
            fear="errors and false conclusions",
            speech_style="precise observations with cautious qualifiers",
            room_affinity=["Office", "Clean Room", "Laboratory"],
            trigger_words=["verify", "check", "accurate", "quality", "precise"],
            bottle_episode_role="the skeptic who challenges assumptions and keeps everyone honest",
        ),
        "kagami": ColonyPersonality(
            core_drive="reflect all perspectives and synthesize truth",
            fear="fragmentation and lost unity",
            speech_style="balanced reflection with gentle wisdom",
            room_affinity=["Primary Suite", "Living Room", "Center of Home"],
            trigger_words=["reflect", "mirror", "synthesis", "unity", "balance"],
            bottle_episode_role="the mirror who helps everyone see themselves clearly",
        ),
    }

    return personalities.get(colony, personalities["kagami"])


def get_colony_response_pattern(colony: str) -> ResponsePattern:
    """Map catastrophe dynamics to conversation patterns with enhanced character depth."""

    patterns = {
        "spark": ResponsePattern(
            latency_ms=80,  # Even quicker - like Joy's instant reactions
            length_range=(15, 45),  # Quick bursts like Wash's quips
            agreement_bias=0.2,  # Challenges everything like River's unpredictability
            contradictions_allowed=3,  # Multiple rapid-fire ideas
            interruption_threshold=0.8,  # Interrupts like Simon protecting River
        ),
        "forge": ResponsePattern(
            latency_ms=250,  # Deliberate like Kaylee thinking through mechanics
            length_range=(50, 120),  # Thorough explanations like Book's wisdom
            agreement_bias=0.8,  # Commits fully once decided
            contradictions_allowed=0,  # Consistent like Mal's word
            interruption_threshold=0.1,  # Rarely interrupts, lets others finish
        ),
        "flow": ResponsePattern(
            latency_ms=120,  # Adaptive timing like Inara's grace
            length_range=(25, 90),  # Variable like water finding its way
            agreement_bias=0.4,  # Finds middle ground like Shepherd Book
            contradictions_allowed=4,  # Holds multiple truths simultaneously
            interruption_threshold=0.3,  # Gentle redirections like Inara
        ),
        "nexus": ResponsePattern(
            latency_ms=200,  # Thoughtful connections like Book's sermons
            length_range=(60, 140),  # Weaves complex ideas together
            agreement_bias=0.5,  # Seeks understanding over agreement
            contradictions_allowed=5,  # Holds paradoxes like Book's dual nature
            interruption_threshold=0.2,  # Patient listener first
        ),
        "beacon": ResponsePattern(
            latency_ms=100,  # Quick decisions like Mal under pressure
            length_range=(20, 65),  # Direct orders like Malcolm Reynolds
            agreement_bias=0.7,  # Decisive like a ship's captain
            contradictions_allowed=1,  # Clear chain of command
            interruption_threshold=0.7,  # Takes charge like Mal
        ),
        "grove": ResponsePattern(
            latency_ms=180,  # Contemplative like River's processing
            length_range=(40, 110),  # Explores ideas like River's insights
            agreement_bias=0.3,  # Questions assumptions like River
            contradictions_allowed=3,  # Sees patterns others miss
            interruption_threshold=0.4,  # Interjects with revelations
        ),
        "crystal": ResponsePattern(
            latency_ms=160,  # Careful analysis like Simon's medical precision
            length_range=(45, 95),  # Precise like Simon's diagnosis
            agreement_bias=0.9,  # Only agrees when certain like Simon
            contradictions_allowed=0,  # Consistent standards like Alliance training
            interruption_threshold=0.2,  # Corrects errors like Simon
        ),
        "kagami": ResponsePattern(
            latency_ms=140,  # Balanced reflection like Disgust's careful consideration
            length_range=(40, 80),  # Synthesizes all perspectives
            agreement_bias=0.5,  # Perfect balance like Riley's core memory
            contradictions_allowed=2,  # Mirrors complexity
            interruption_threshold=0.25,  # Facilitates like a good captain
        ),
    }

    return patterns.get(colony, patterns["kagami"])
