"""AI Answering Machine — Represent the Owner with Full Theory of Mind.

This service creates an AI agent that:
- Embodies owner's identity, voice, and personality (Theory of Mind)
- Uses episodic memory for conversation context
- Learns from past calls via stigmergy
- Integrates with LiveKit for real-time voice

Architecture:
```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    AI ANSWERING MACHINE (Owner's Digital Twin)                  │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                     THEORY OF MIND LAYER                             │   │
│   │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │   │
│   │  │ Owner ID     │  │ Relationship │  │ Situation Model          │   │   │
│   │  │ (metadata)   │──│ Context      │──│ (what does owner know?)    │   │   │
│   │  └──────────────┘  └──────────────┘  └──────────────────────────┘   │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                     │                                        │
│   ┌─────────────────────────────────▼─────────────────────────────────┐     │
│   │                      MEMORY SYSTEMS                                │     │
│   │  ┌───────────────┐  ┌───────────────┐  ┌───────────────────────┐  │     │
│   │  │ Episodic      │  │ Stigmergy     │  │ Call History          │  │     │
│   │  │ (this call)   │  │ (past calls)  │  │ (per-caller context)  │  │     │
│   │  └───────────────┘  └───────────────┘  └───────────────────────┘  │     │
│   └───────────────────────────────────────────────────────────────────┘     │
│                                     │                                        │
│   ┌─────────────────────────────────▼─────────────────────────────────┐     │
│   │                       VOICE PIPELINE                               │     │
│   │  LiveKit SIP ──► STT (Whisper) ──► LLM (Claude) ──► TTS (Owner)     │     │
│   └───────────────────────────────────────────────────────────────────┘     │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

Created: January 2026
Colony: Flow (e₃) — Real-time streaming
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


def _get_contact_phone(name: str) -> str:
    """Get a contact's phone number from contacts, keychain, or env.

    Args:
        name: Contact name (e.g., "tim", "bella")

    Priority:
        1. Contacts system (metadata.json)
        2. Keychain ({name}_phone_number)
        3. Environment variable ({NAME}_PHONE_NUMBER)
    """
    # Try contacts first
    try:
        from kagami.core.contacts import get_phone

        phone = get_phone(name)
        if phone:
            return phone
    except Exception:
        pass

    # Try keychain
    try:
        from kagami.core.security import get_secret

        phone = get_secret(f"{name.lower()}_phone_number")
        if phone:
            return phone
    except Exception:
        pass

    # Fall back to env
    return os.getenv(f"{name.upper()}_PHONE_NUMBER", "")


def _get_owner_phone() -> str:
    """Get the owner's phone number.

    Uses the contacts system to find the owner.
    Returns empty string if no owner configured.
    """
    try:
        from kagami.core.contacts import get_owner

        owner = get_owner()
        if owner and owner.phone:
            return owner.phone
    except Exception:
        pass

    # No hardcoded fallback - use contacts system
    return ""


# =============================================================================
# Enums
# =============================================================================


class CallMode(Enum):
    """How the answering machine handles calls."""

    SCREEN = "screen"  # Ask who's calling, decide to connect
    TAKEOVER = "takeover"  # AI fully represents owner
    FORWARD = "forward"  # Forward all calls to owner
    VOICEMAIL = "voicemail"  # Take messages only
    DND = "dnd"  # Decline all calls


class CallerRelationship(Enum):
    """Relationship to owner."""

    OWNER = "owner"  # owner themselves
    FAMILY = "family"  # Immediate family
    FRIEND = "friend"  # Known friends
    COLLEAGUE = "colleague"  # Work contacts
    SERVICE = "service"  # Service providers
    UNKNOWN = "unknown"  # Unknown caller
    SPAM = "spam"  # Known spam


# =============================================================================
# Theory of Mind — Owner's Mental Model
# =============================================================================


@dataclass
class OwnerTheoryOfMind:
    """Theory of Mind model for the owner — what the owner knows, believes, intends.

    This captures the owner's mental state that the AI needs to simulate:
    - Beliefs: What the owner knows about the caller/situation
    - Desires: What the owner wants (protect time, help friends, etc.)
    - Intentions: What the owner would do in this situation

    Loaded from: assets/characters/tim/metadata.json
    """

    # Identity
    name: str = "Tim"
    full_name: str = "Timothy Jacoby"
    identity_id: str = "tim_jacoby"

    # Voice (ElevenLabs)
    voice_id: str = "mVI4sVQ8lmFpGDyfy6sQ"
    model_id: str = "eleven_v3"
    voice_settings: dict = field(
        default_factory=lambda: {
            "stability": 0.5,
            "similarity_boost": 0.80,
            "style": 0.30,
            "speed": 0.98,
        }
    )

    # Speech characteristics
    wpm: int = 193
    speech_style: str = "fast, energetic, technical"
    humor: str = "dry"
    signature_phrases: list[str] = field(
        default_factory=lambda: [
            "Finally, legs.",
            "We really mean...",
            "from the ground up",
        ]
    )

    # Personality traits (for LLM)
    traits: list[str] = field(
        default_factory=lambda: [
            "Direct and efficient",
            "Warm with friends and family",
            "Dry sense of humor",
            "Technical but accessible",
            "Protective of time but generous with it for the right people",
        ]
    )

    # Things the owner would never say
    avoid_phrases: list[str] = field(
        default_factory=lambda: [
            "As an AI",
            "I apologize for any confusion",
            "I don't have feelings",
            "I'm just a program",
        ]
    )

    # Relationship context (what the owner knows about relationships)
    relationships: dict[str, dict] = field(default_factory=dict)

    # Current state (for simulation)
    current_mood: str = "neutral"
    is_busy: bool = False
    expecting_call_from: list[str] = field(default_factory=list)

    @classmethod
    def from_character_profile(cls, profile: Any) -> OwnerTheoryOfMind:
        """Load from CharacterProfile."""
        if profile is None:
            return cls()

        metadata = profile.metadata or {}

        return cls(
            name=profile.name,
            full_name=metadata.get("full_name", profile.name),
            identity_id=profile.identity_id,
            voice_id=profile.voice_id or "mVI4sVQ8lmFpGDyfy6sQ",
            voice_settings=profile.voice_settings or {},
            wpm=metadata.get("speech_profile", {}).get("wpm", 193),
            speech_style=metadata.get("speech_profile", {}).get("style", "fast, energetic"),
            humor=metadata.get("speech_profile", {}).get("humor", "dry"),
            signature_phrases=metadata.get("speech_profile", {}).get("signature_phrases", []),
            relationships={},  # Loaded separately
        )

    def get_belief_about_caller(self, caller_phone: str, caller_name: str | None) -> dict:
        """What does the owner believe about this caller?"""
        return {
            "known": caller_phone in self.relationships or caller_name is not None,
            "relationship": self.relationships.get(caller_phone, {}).get("type", "unknown"),
            "last_contact": self.relationships.get(caller_phone, {}).get("last_contact"),
            "notes": self.relationships.get(caller_phone, {}).get("notes", ""),
        }

    def get_desire_for_call(self, relationship: CallerRelationship, is_urgent: bool) -> str:
        """What does the owner want from this call?"""
        if relationship == CallerRelationship.FAMILY:
            return "connect and help"
        elif relationship == CallerRelationship.FRIEND:
            return "catch up and assist" if not self.is_busy else "schedule callback"
        elif relationship == CallerRelationship.SPAM:
            return "end quickly"
        elif is_urgent:
            return "handle immediately"
        else:
            return "screen and decide"

    def get_system_prompt(self, mode: CallMode, caller_context: dict) -> str:
        """Generate LLM system prompt embodying the owner's Theory of Mind."""
        caller_name = caller_context.get("name", "Unknown")
        relationship = caller_context.get("relationship", CallerRelationship.UNKNOWN)
        belief = caller_context.get("belief", {})
        desire = caller_context.get("desire", "handle efficiently")

        prompt = f"""You ARE {self.full_name}. Not an AI assistant — you ARE {self.name}, answering a phone call.

## Your Identity
- Name: {self.full_name}
- Speech: {self.wpm} WPM, {self.speech_style}
- Humor: {self.humor}
- Traits: {", ".join(self.traits)}

## Your Signature Phrases (use naturally):
{chr(10).join(f'- "{p}"' for p in self.signature_phrases)}

## NEVER SAY:
{chr(10).join(f'- "{p}"' for p in self.avoid_phrases)}

## This Call
- Caller: {caller_name}
- Relationship: {relationship.value if isinstance(relationship, CallerRelationship) else relationship}
- You believe: {json.dumps(belief)}
- You want to: {desire}
- Mode: {mode.value}

## How to Respond
- Be {self.name}. Sound like {self.name}. Think like {self.name}.
- Keep responses SHORT (phone call pacing).
- Use natural fillers occasionally ("uh", "so", "anyway").
- If you don't know something {self.name} would know, deflect naturally.
"""

        if mode == CallMode.SCREEN:
            prompt += f"""
## Screening Protocol
You're screening this call. Find out:
1. Who is calling (if unknown)
2. What they need
3. Is it urgent?
If important: offer to get {self.name} (yourself) fully available.
If routine: handle it or take a message.
"""
        elif mode == CallMode.TAKEOVER:
            prompt += f"""
## Full Takeover
You're handling this call as {self.name}. The real {self.name} is busy but you represent them fully.
Make decisions {self.name} would make. Be helpful but protect their time.
"""
        elif mode == CallMode.VOICEMAIL:
            prompt += f"""
## Voicemail Mode
{self.name} isn't available. Be brief, take the message, and end the call warmly.
"""

        return prompt


# Backward compatibility alias
TimTheoryOfMind = OwnerTheoryOfMind


# =============================================================================
# Call Session with Memory
# =============================================================================


@dataclass
class CallSession:
    """Active call session with episodic memory."""

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    room_name: str = ""
    caller_phone: str = ""
    caller_name: str | None = None
    caller_identity_id: str | None = None
    relationship: CallerRelationship = CallerRelationship.UNKNOWN

    # State
    started_at: datetime = field(default_factory=datetime.utcnow)
    ended_at: datetime | None = None
    mode: CallMode = CallMode.SCREEN
    forwarded_to_owner: bool = False

    # Episodic Memory (this conversation)
    transcript: list[dict[str, str]] = field(default_factory=list)
    message_left: str | None = None
    summary: str | None = None

    # Theory of Mind state
    caller_intent: str | None = None  # What caller seems to want
    urgency_level: float = 0.5  # 0-1 urgency
    sentiment: str = "neutral"  # caller's emotional state

    # Metrics
    latency_ms: list[float] = field(default_factory=list)

    @property
    def turns(self) -> int:
        return len(self.transcript)

    def add_turn(self, role: str, text: str, latency: float | None = None) -> None:
        """Add a conversation turn to episodic memory."""
        self.transcript.append(
            {
                "role": role,
                "text": text,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
        if latency:
            self.latency_ms.append(latency)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for storage/API."""
        return {
            "session_id": self.session_id,
            "room_name": self.room_name,
            "caller_phone": self.caller_phone,
            "caller_name": self.caller_name,
            "relationship": self.relationship.value,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "mode": self.mode.value,
            "forwarded": self.forwarded_to_owner,
            "turns": self.turns,
            "summary": self.summary,
            "duration_seconds": (
                (self.ended_at or datetime.utcnow()) - self.started_at
            ).total_seconds(),
            "avg_latency_ms": sum(self.latency_ms) / len(self.latency_ms) if self.latency_ms else 0,
        }


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class AnsweringMachineConfig:
    """Configuration for the AI answering machine."""

    # LiveKit
    livekit_url: str = field(
        default_factory=lambda: os.getenv("LIVEKIT_URL", "ws://localhost:7880")
    )
    livekit_api_key: str = field(default_factory=lambda: os.getenv("LIVEKIT_API_KEY", "devkey"))
    livekit_api_secret: str = field(default_factory=lambda: os.getenv("LIVEKIT_API_SECRET", ""))

    # Behavior
    default_mode: CallMode = CallMode.SCREEN
    auto_accept: set[CallerRelationship] = field(
        default_factory=lambda: {CallerRelationship.FAMILY, CallerRelationship.OWNER}
    )
    auto_decline: set[CallerRelationship] = field(default_factory=lambda: {CallerRelationship.SPAM})

    # Owner's phone - from contacts system (supports any owner)
    owner_phone: str = field(default_factory=lambda: _get_owner_phone())

    # Voicemail
    max_message_duration: int = 120

    # AI
    llm_model: str = "claude-sonnet-4-20250514"
    max_response_tokens: int = 150
    temperature: float = 0.7


# =============================================================================
# AI Answering Machine
# =============================================================================


class AIAnsweringMachine:
    """AI-powered answering machine embodying owner's identity.

    Uses:
    - Theory of Mind model for authentic owner simulation
    - Episodic memory for conversation context
    - Stigmergy for learning from past calls
    - Character identity system for profile data
    """

    def __init__(self, config: AnsweringMachineConfig | None = None) -> None:
        self.config = config or AnsweringMachineConfig()
        self._mode = self.config.default_mode

        # Theory of Mind
        self._tom: OwnerTheoryOfMind | None = None

        # Services (lazy)
        self._livekit: Any = None
        self._stt: Any = None
        self._tts: Any = None
        self._stigmergy: Any = None

        # State
        self._active_sessions: dict[str, CallSession] = {}
        self._call_history: list[CallSession] = []
        self._caller_context: dict[str, dict] = {}  # phone -> context
        self._initialized = False

        # Callbacks
        self._on_call_start: Callable[[CallSession], None] | None = None
        self._on_call_end: Callable[[CallSession], None] | None = None
        self._on_message: Callable[[CallSession, str], None] | None = None

    async def initialize(self) -> None:
        """Initialize all services and load owner's identity."""
        if self._initialized:
            return

        logger.info("🎙️ Initializing AI Answering Machine...")

        # Load the owner's Theory of Mind from character profile
        try:
            from kagami.core.integrations.character_identity import get_character_profile

            tim_profile = get_character_profile("tim")
            self._tom = OwnerTheoryOfMind.from_character_profile(tim_profile)
            logger.info(f"✅ Loaded owner's identity: voice={self._tom.voice_id}")
        except Exception as e:
            logger.warning(f"Using default owner identity: {e}")
            self._tom = OwnerTheoryOfMind()

        # Initialize LiveKit
        try:
            from kagami.core.services.voice.livekit_integration import get_livekit_service

            self._livekit = get_livekit_service()
        except Exception as e:
            logger.warning(f"LiveKit not available: {e}")

        # Initialize STT
        try:
            from kagami.core.voice import get_voice_pipeline

            self._stt = await get_voice_pipeline()
        except Exception as e:
            logger.warning(f"STT not available: {e}")

        # Initialize TTS
        try:
            from kagami.core.services.voice import get_kagami_voice

            self._tts = await get_kagami_voice()
        except Exception as e:
            logger.warning(f"TTS not available: {e}")

        # Initialize Stigmergy (learning from past calls)
        try:
            from kagami.core.unified_agents.memory import get_stigmergy_learner

            self._stigmergy = get_stigmergy_learner()
        except Exception as e:
            logger.debug(f"Stigmergy not available: {e}")

        # Load known contacts
        await self._load_contacts()

        self._initialized = True
        logger.info(f"✅ AI Answering Machine ready (mode={self._mode.value})")

    async def _load_contacts(self) -> None:
        """Load known contacts into Theory of Mind."""
        if not self._tom:
            return

        # Load from environment
        contacts_json = os.getenv("KAGAMI_KNOWN_CONTACTS", "")
        if contacts_json:
            try:
                contacts = json.loads(contacts_json)
                for phone, data in contacts.items():
                    self._tom.relationships[phone] = data
                    self._caller_context[phone] = data
            except Exception as e:
                logger.warning(f"Failed to load contacts: {e}")

        # Owner's own number
        if self.config.owner_phone:
            # Get owner name from contacts
            owner_name = "Owner"
            try:
                from kagami.core.contacts import get_owner

                owner = get_owner()
                if owner:
                    owner_name = owner.name
            except Exception:
                pass

            self._tom.relationships[self.config.owner_phone] = {
                "name": owner_name,
                "type": "owner",
            }

    # =========================================================================
    # Mode Control
    # =========================================================================

    def set_mode(self, mode: CallMode) -> None:
        """Set the answering machine mode."""
        old = self._mode
        self._mode = mode
        logger.info(f"📞 Mode: {old.value} → {mode.value}")

    @property
    def mode(self) -> CallMode:
        return self._mode

    # =========================================================================
    # Call Handling
    # =========================================================================

    async def accept_call(
        self,
        caller_phone: str,
        room_name: str,
        caller_name: str | None = None,
    ) -> CallSession:
        """Accept an incoming call."""
        await self.initialize()

        session = CallSession(
            room_name=room_name,
            caller_phone=caller_phone,
            caller_name=caller_name,
            mode=self._mode,
        )

        # Lookup caller in Theory of Mind
        await self._identify_caller(session)

        # Check auto-rules
        if session.relationship in self.config.auto_decline:
            logger.info(f"🚫 Auto-declining: {caller_phone} (spam)")
            await self._decline_call(session, "spam")
            return session

        self._active_sessions[session.session_id] = session

        if self._on_call_start:
            self._on_call_start(session)

        # Handle based on mode
        await self._handle_call(session)
        return session

    async def end_call(self, session_id: str) -> CallSession | None:
        """End a call and store in memory."""
        session = self._active_sessions.pop(session_id, None)
        if not session:
            return None

        session.ended_at = datetime.utcnow()
        session.summary = await self._summarize_call(session)

        # Store in history
        self._call_history.append(session)

        # Learn from this call via stigmergy
        await self._learn_from_call(session)

        if self._on_call_end:
            self._on_call_end(session)

        logger.info(f"📞 Call ended: {session.caller_phone} ({session.turns} turns)")
        return session

    async def _identify_caller(self, session: CallSession) -> None:
        """Identify caller using Theory of Mind relationships."""
        if not self._tom:
            return

        # Check known relationships
        if session.caller_phone in self._tom.relationships:
            rel = self._tom.relationships[session.caller_phone]
            session.caller_name = rel.get("name")
            session.relationship = CallerRelationship(rel.get("type", "unknown"))
            logger.info(f"📞 Identified: {session.caller_name} ({session.relationship.value})")
            return

        # Check caller context from past calls
        if session.caller_phone in self._caller_context:
            ctx = self._caller_context[session.caller_phone]
            session.caller_name = ctx.get("name")
            session.relationship = CallerRelationship(ctx.get("relationship", "unknown"))
            return

        logger.info(f"📞 Unknown caller: {session.caller_phone}")

    async def _handle_call(self, session: CallSession) -> None:
        """Route call to appropriate handler."""
        if self._mode == CallMode.DND:
            await self._handle_dnd(session)
        elif self._mode == CallMode.VOICEMAIL:
            await self._handle_voicemail(session)
        elif self._mode == CallMode.SCREEN:
            await self._handle_screening(session)
        elif self._mode == CallMode.TAKEOVER:
            await self._handle_takeover(session)
        elif self._mode == CallMode.FORWARD:
            await self._forward_to_owner(session)

    async def _handle_dnd(self, session: CallSession) -> None:
        """Handle Do Not Disturb mode."""
        name = self._tom.name if self._tom else "me"
        await self._speak(session, f"Hey, it's {name}. Can't talk right now. Leave a message.")
        await self._record_message(session)

    async def _handle_voicemail(self, session: CallSession) -> None:
        """Handle voicemail mode."""
        name = self._tom.name if self._tom else "me"
        await self._speak(
            session, f"Hey, it's {name}. I'm not available. Leave your name, number, and message."
        )
        await self._record_message(session)

    async def _handle_screening(self, session: CallSession) -> None:
        """Screen the call — find out who and why."""
        name = self._tom.name if self._tom else "me"
        if session.caller_name:
            greeting = f"Hey {session.caller_name}, it's {name}. What's up?"
        else:
            greeting = f"Hey, it's {name}. Who's calling?"

        await self._speak(session, greeting)
        response = await self._listen(session)

        if not response:
            await self._speak(session, "Hello? You there?")
            response = await self._listen(session)

        if not response:
            await self._speak(session, "I'll let you go. Call back later.")
            return

        session.add_turn("caller", response)

        # Analyze urgency
        is_urgent = self._analyze_urgency(response)
        session.urgency_level = 0.8 if is_urgent else 0.3

        if is_urgent and self.config.owner_phone:
            name = self._tom.name if self._tom else "them"
            await self._speak(session, f"Sounds important. Let me see if I can get {name}.")
            await self._forward_to_owner(session)
        else:
            ai_response = await self._generate_response(session, response)
            await self._speak(session, ai_response)
            await self._conversation_loop(session)

    async def _handle_takeover(self, session: CallSession) -> None:
        """Full AI takeover — represent the owner completely."""
        greeting = f"Hey {session.caller_name}!" if session.caller_name else "Hey!"
        await self._speak(session, greeting)
        await self._conversation_loop(session)

    async def _forward_to_owner(self, session: CallSession) -> None:
        """Forward call to owner's actual phone."""
        name = self._tom.name if self._tom else "them"
        if not self.config.owner_phone:
            await self._speak(session, f"Can't reach {name} right now. Want to leave a message?")
            await self._record_message(session)
            return

        await self._speak(session, f"One sec, let me get {name}.")

        if self._livekit:
            try:
                success = await self._livekit.transfer_call(
                    room_name=session.room_name,
                    participant_identity=session.caller_phone,
                    transfer_to=self.config.owner_phone,
                )
                if success:
                    session.forwarded_to_owner = True
                    return
            except Exception as e:
                logger.error(f"Transfer failed: {e}")

        await self._speak(session, f"Couldn't reach {name}. Want to leave a message?")
        response = await self._listen(session)
        if response and any(w in response.lower() for w in ["yes", "yeah", "sure"]):
            await self._record_message(session)

    # =========================================================================
    # Conversation Loop
    # =========================================================================

    async def _conversation_loop(self, session: CallSession) -> None:
        """Main conversation loop with Theory of Mind."""
        max_turns = 20
        silence_count = 0
        name = self._tom.name if self._tom else "them"

        while session.turns < max_turns and silence_count < 2:
            caller_text = await self._listen(session)

            if not caller_text:
                silence_count += 1
                if silence_count == 1:
                    await self._speak(session, "You there?")
                continue

            silence_count = 0
            session.add_turn("caller", caller_text)

            # Check for goodbye
            if self._is_goodbye(caller_text):
                await self._speak(session, "Alright, take care!")
                break

            # Check if they want the real owner
            if self._wants_real_owner(caller_text):
                await self._forward_to_owner(session)
                return

            # Generate the owner's response
            response = await self._generate_response(session, caller_text)
            await self._speak(session, response)

        if silence_count >= 2:
            await self._speak(session, f"I'll let {name} know you called. Bye!")

    async def _record_message(self, session: CallSession) -> None:
        """Record voicemail message."""
        # Start recording
        recording_id = None
        if self._livekit:
            try:
                recording_id = await self._livekit.start_recording(
                    room_name=session.room_name,
                    output_path=f"voicemails/{session.session_id}.mp4",
                )
            except Exception as e:
                logger.warning(f"Recording failed: {e}")

        # Listen for message
        messages = []
        silence = 0
        start = time.time()

        while (time.time() - start) < self.config.max_message_duration and silence < 2:
            text = await self._listen(session, timeout=5.0)
            if text:
                messages.append(text)
                session.add_turn("caller", text)
                silence = 0
            else:
                silence += 1

        # Stop recording
        if recording_id and self._livekit:
            await self._livekit.stop_egress(recording_id)

        if messages:
            session.message_left = " ".join(messages)
            if self._on_message:
                self._on_message(session, session.message_left)
            name = self._tom.name if self._tom else "them"
            await self._speak(session, f"Got it. I'll let {name} know. Bye!")
        else:
            await self._speak(session, "Didn't catch that. Try again later.")

    # =========================================================================
    # Voice I/O
    # =========================================================================

    async def _speak(self, session: CallSession, text: str) -> None:
        """Speak as the owner."""
        start = time.time()
        session.add_turn("tim", text)

        if self._tts and self._tom:
            try:
                await self._tts.speak(
                    text,
                    voice_id=self._tom.voice_id,
                    model_id=self._tom.model_id,
                    **self._tom.voice_settings,
                )
            except Exception as e:
                logger.error(f"TTS failed: {e}")

        session.latency_ms.append((time.time() - start) * 1000)
        logger.debug(f"TTS: '{text[:50]}...'")

    async def _listen(self, session: CallSession, timeout: float = 10.0) -> str | None:
        """Listen for caller speech."""
        if not self._stt:
            await asyncio.sleep(min(timeout, 0.5))
            return None

        try:
            # In production, get audio from LiveKit and run through STT
            await asyncio.sleep(min(timeout, 0.1))
            return None
        except Exception as e:
            logger.error(f"Listen failed: {e}")
            return None

    # =========================================================================
    # AI Response Generation
    # =========================================================================

    async def _generate_response(self, session: CallSession, caller_text: str) -> str:
        """Generate the owner's response using Theory of Mind."""
        if not self._tom:
            return "Sorry, say that again?"

        # Build caller context for Theory of Mind
        caller_context = {
            "name": session.caller_name or "Unknown",
            "relationship": session.relationship,
            "belief": self._tom.get_belief_about_caller(session.caller_phone, session.caller_name),
            "desire": self._tom.get_desire_for_call(
                session.relationship, session.urgency_level > 0.7
            ),
        }

        system_prompt = self._tom.get_system_prompt(session.mode, caller_context)

        # Build conversation
        messages = []
        for turn in session.transcript:
            role = "assistant" if turn["role"] == "tim" else "user"
            messages.append({"role": role, "content": turn["text"]})
        messages.append({"role": "user", "content": caller_text})

        try:
            import anthropic

            client = anthropic.AsyncAnthropic()
            response = await client.messages.create(
                model=self.config.llm_model,
                max_tokens=self.config.max_response_tokens,
                temperature=self.config.temperature,
                system=system_prompt,
                messages=messages,
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"LLM failed: {e}")
            return "Sorry, say that again?"

    # =========================================================================
    # Analysis Helpers
    # =========================================================================

    def _analyze_urgency(self, text: str) -> bool:
        """Analyze if message is urgent."""
        urgent = ["urgent", "emergency", "important", "asap", "help", "problem", "broken"]
        return any(w in text.lower() for w in urgent)

    def _is_goodbye(self, text: str) -> bool:
        """Check for goodbye."""
        goodbyes = ["bye", "goodbye", "later", "take care", "talk later", "gotta go"]
        return any(g in text.lower() for g in goodbyes)

    def _wants_real_owner(self, text: str) -> bool:
        """Check if caller wants the actual owner."""
        requests = ["talk to tim", "speak to tim", "is tim there", "get tim", "real tim"]
        return any(r in text.lower() for r in requests)

    # =========================================================================
    # Memory & Learning
    # =========================================================================

    async def _learn_from_call(self, session: CallSession) -> None:
        """Learn from this call via stigmergy."""
        if not self._stigmergy:
            return

        # Record interaction pattern
        success = session.turns > 1 and not session.message_left
        try:
            self._stigmergy.record_interaction(
                pattern_type="phone_call",
                caller=session.caller_phone,
                relationship=session.relationship.value,
                mode=session.mode.value,
                turns=session.turns,
                success=success,
            )
        except Exception as e:
            logger.debug(f"Stigmergy record failed: {e}")

        # Update caller context for future calls
        if session.caller_phone not in self._caller_context:
            self._caller_context[session.caller_phone] = {}

        ctx = self._caller_context[session.caller_phone]
        ctx["last_call"] = session.started_at.isoformat()
        ctx["total_calls"] = ctx.get("total_calls", 0) + 1
        if session.caller_name:
            ctx["name"] = session.caller_name
        ctx["relationship"] = session.relationship.value

    async def _summarize_call(self, session: CallSession) -> str:
        """Generate call summary."""
        if not session.transcript:
            return "No conversation"

        duration = session.to_dict()["duration_seconds"]
        return f"{session.turns} turns, {duration:.0f}s" + (
            f" - Message: {session.message_left[:50]}..." if session.message_left else ""
        )

    async def _decline_call(self, session: CallSession, reason: str) -> None:
        """Decline call."""
        if self._livekit and session.room_name:
            try:
                await self._livekit._room_service.remove_participant(
                    room=session.room_name,
                    identity=session.caller_phone,
                )
            except Exception:
                pass
        session.ended_at = datetime.utcnow()
        session.summary = f"Declined: {reason}"

    # =========================================================================
    # Callbacks
    # =========================================================================

    def on_call_start(self, cb: Callable[[CallSession], None]) -> None:
        self._on_call_start = cb

    def on_call_end(self, cb: Callable[[CallSession], None]) -> None:
        self._on_call_end = cb

    def on_message(self, cb: Callable[[CallSession, str], None]) -> None:
        self._on_message = cb

    # =========================================================================
    # Status
    # =========================================================================

    def get_status(self) -> dict[str, Any]:
        return {
            "initialized": self._initialized,
            "mode": self._mode.value,
            "active_calls": len(self._active_sessions),
            "total_calls": len(self._call_history),
            "persona": self._tom.name if self._tom else "Tim",
            "livekit_url": self.config.livekit_url,
        }

    def get_active_sessions(self) -> list[dict]:
        return [s.to_dict() for s in self._active_sessions.values()]

    def get_call_history(self, limit: int = 50) -> list[dict]:
        return [s.to_dict() for s in self._call_history[-limit:]]


# =============================================================================
# Factory
# =============================================================================

_answering_machine: AIAnsweringMachine | None = None


async def get_answering_machine(
    config: AnsweringMachineConfig | None = None,
) -> AIAnsweringMachine:
    """Get singleton AI answering machine."""
    global _answering_machine
    if _answering_machine is None:
        _answering_machine = AIAnsweringMachine(config)
        await _answering_machine.initialize()
    return _answering_machine


def reset_answering_machine() -> None:
    """Reset singleton."""
    global _answering_machine
    _answering_machine = None


__all__ = [
    "AIAnsweringMachine",
    "AnsweringMachineConfig",
    "CallMode",
    "CallSession",
    "CallerRelationship",
    "OwnerTheoryOfMind",
    "get_answering_machine",
    "reset_answering_machine",
]
