"""Semantic Intent Parser — Flexible Natural Language Understanding.

Handles any natural language phrasing from either side:
- ElevenLabs agent: "fireplace_off", "turn_off_fireplace"
- User speech: "can you please turn off the fireplace", "shut down the fire"

Architecture:
```
Input → Heavy Normalization → Concept Extraction → Best Match → Action Refinement
```

Created: January 8, 2026
鏡
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# Intent Types
# =============================================================================


class IntentCategory(Enum):
    """High-level intent categories."""

    LIGHTING = auto()
    SHADES = auto()
    CLIMATE = auto()
    ENTERTAINMENT = auto()
    SECURITY = auto()
    SCENE = auto()
    AUDIO = auto()
    EMAIL = auto()
    CALENDAR = auto()
    TASKS = auto()
    COMMUNICATION = auto()
    INFO = auto()
    UNKNOWN = auto()


class IntentAction(Enum):
    """Specific actions within categories."""

    # Lighting
    SET_BRIGHTNESS = auto()
    TURN_ON = auto()
    TURN_OFF = auto()

    # Shades
    OPEN = auto()
    CLOSE = auto()

    # Climate
    FIREPLACE_ON = auto()
    FIREPLACE_OFF = auto()
    SET_TEMPERATURE = auto()

    # Entertainment
    TV_LOWER = auto()
    TV_RAISE = auto()
    MUSIC_PLAY = auto()
    MUSIC_PAUSE = auto()
    MUSIC_SKIP = auto()

    # Security
    LOCK_ALL = auto()
    UNLOCK = auto()

    # Scenes
    MOVIE_MODE = auto()
    GOODNIGHT = auto()
    WELCOME_HOME = auto()
    FOCUS_MODE = auto()

    # Audio
    ANNOUNCE = auto()

    # Digital
    CHECK_EMAIL = auto()
    SEND_EMAIL = auto()
    CHECK_CALENDAR = auto()
    CREATE_EVENT = auto()
    CHECK_TASKS = auto()
    CHECK_SLACK = auto()

    # Info
    GET_TIME = auto()
    GET_STATUS = auto()
    GET_PRESENCE = auto()

    UNKNOWN = auto()


@dataclass
class ParsedIntent:
    """Structured intent from command parsing."""

    category: IntentCategory
    action: IntentAction
    parameters: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    raw_command: str = ""

    def __str__(self) -> str:
        return f"{self.category.name}.{self.action.name}({self.parameters})"


# =============================================================================
# Semantic Concept Maps (Very Flexible)
# =============================================================================

# Each entry: (concept_keywords, category, default_action, priority)
# Keywords are matched flexibly - partial matches, synonyms, etc.
CONCEPT_MAP: list[tuple[set[str], IntentCategory, IntentAction, int]] = [
    # === SCENES (Highest Priority) ===
    (
        {"movie", "film", "cinema", "theater", "theatre", "netflix", "watch", "viewing"},
        IntentCategory.SCENE,
        IntentAction.MOVIE_MODE,
        150,
    ),
    (
        {"goodnight", "night", "sleep", "bed", "bedtime", "retire", "tired", "sleepy", "nighty"},
        IntentCategory.SCENE,
        IntentAction.GOODNIGHT,
        140,
    ),
    (
        {"welcome", "home", "arrive", "arrived", "back", "return", "returned"},
        IntentCategory.SCENE,
        IntentAction.WELCOME_HOME,
        130,
    ),
    (
        {"focus", "concentrate", "work", "productive", "study", "studying"},
        IntentCategory.SCENE,
        IntentAction.FOCUS_MODE,
        120,
    ),
    # === CLIMATE - Fireplace (High Priority) ===
    (
        {"fireplace", "fire", "flame", "hearth", "cozy", "chimney"},
        IntentCategory.CLIMATE,
        IntentAction.FIREPLACE_ON,
        130,
    ),
    # === LIGHTING (High Priority) ===
    (
        {
            "light",
            "lights",
            "lamp",
            "lamps",
            "lighting",
            "illuminate",
            "bright",
            "brightness",
            "brighten",
            "brighter",
            "dim",
            "dimmer",
            "dimming",
            "dark",
            "darker",
            "glow",
            "overhead",
            "pendant",
            "chandelier",
            "spotlight",
            "can",
            "cans",
            "luminance",
        },
        IntentCategory.LIGHTING,
        IntentAction.SET_BRIGHTNESS,
        100,
    ),
    # === SHADES ===
    (
        {
            "shade",
            "shades",
            "blind",
            "blinds",
            "curtain",
            "curtains",
            "drape",
            "drapes",
            "window",
            "windows",
            "privacy",
            "sunlight",
            "daylight",
            "cover",
            "covering",
        },
        IntentCategory.SHADES,
        IntentAction.OPEN,
        100,
    ),
    # === ENTERTAINMENT - TV ===
    (
        {"tv", "television", "screen", "mount", "telly"},
        IntentCategory.ENTERTAINMENT,
        IntentAction.TV_LOWER,
        100,
    ),
    # === ENTERTAINMENT - Music ===
    (
        {
            "music",
            "song",
            "songs",
            "playlist",
            "spotify",
            "tune",
            "tunes",
            "track",
            "album",
            "artist",
            "jazz",
            "classical",
            "chill",
            "workout",
            "beats",
            "radio",
        },
        IntentCategory.ENTERTAINMENT,
        IntentAction.MUSIC_PLAY,
        95,
    ),
    # === SECURITY ===
    (
        {
            "lock",
            "locks",
            "door",
            "doors",
            "secure",
            "security",
            "entry",
            "unlock",
            "deadbolt",
            "latch",
            "bolt",
        },
        IntentCategory.SECURITY,
        IntentAction.LOCK_ALL,
        110,
    ),
    # === AUDIO ===
    (
        {"announce", "announcement", "broadcast", "say", "tell", "notify", "alert"},
        IntentCategory.AUDIO,
        IntentAction.ANNOUNCE,
        100,
    ),
    # === CLIMATE - Temperature ===
    (
        {
            "temperature",
            "temp",
            "thermostat",
            "hvac",
            "heat",
            "heating",
            "cool",
            "cooling",
            "air",
            "conditioning",
            "climate",
            "warm",
            "warmth",
            "warmer",
            "colder",
            "ac",
        },
        IntentCategory.CLIMATE,
        IntentAction.SET_TEMPERATURE,
        90,
    ),
    # === DIGITAL ===
    (
        {"email", "emails", "mail", "inbox", "gmail", "unread", "messages"},
        IntentCategory.EMAIL,
        IntentAction.CHECK_EMAIL,
        80,
    ),
    (
        {
            "calendar",
            "schedule",
            "meeting",
            "meetings",
            "appointment",
            "appointments",
            "event",
            "events",
            "agenda",
        },
        IntentCategory.CALENDAR,
        IntentAction.CHECK_CALENDAR,
        80,
    ),
    (
        {"task", "tasks", "todo", "todos", "todoist", "deadline", "deadlines", "reminder"},
        IntentCategory.TASKS,
        IntentAction.CHECK_TASKS,
        80,
    ),
    (
        {"slack", "chat", "dm", "channel", "discord"},
        IntentCategory.COMMUNICATION,
        IntentAction.CHECK_SLACK,
        80,
    ),
    # === INFO (Lower Priority) ===
    (
        {"time", "clock", "hour", "oclock", "what time"},
        IntentCategory.INFO,
        IntentAction.GET_TIME,
        50,
    ),
    ({"status", "state", "how", "doing"}, IntentCategory.INFO, IntentAction.GET_STATUS, 40),
    (
        {"who", "anyone", "presence", "people", "person", "somebody"},
        IntentCategory.INFO,
        IntentAction.GET_PRESENCE,
        40,
    ),
]


# Action modifiers - these words refine ON/OFF, OPEN/CLOSE, etc.
ON_WORDS = {"on", "enable", "activate", "start", "begin", "engage", "ignite", "light"}
OFF_WORDS = {"off", "disable", "deactivate", "stop", "end", "kill", "shut", "extinguish", "douse"}
OPEN_WORDS = {"open", "up", "raise", "lift", "reveal"}
CLOSE_WORDS = {"close", "down", "lower", "shut", "drop", "hide", "cover"}
PLAY_WORDS = {"play", "start", "resume", "put"}
PAUSE_WORDS = {"pause", "stop", "halt", "quiet"}
SKIP_WORDS = {"skip", "next", "forward", "another"}


# Room normalization
ROOM_MAP = {
    # Living Room
    "living": "Living Room",
    "lounge": "Living Room",
    "main": "Living Room",
    "family": "Living Room",
    "great": "Living Room",
    # Kitchen
    "kitchen": "Kitchen",
    "cook": "Kitchen",
    # Dining
    "dining": "Dining",
    "eat": "Dining",
    # Primary Bedroom
    "bedroom": "Primary Bedroom",
    "primary": "Primary Bedroom",
    "master": "Primary Bedroom",
    "bed": "Primary Bedroom",
    # Office
    "office": "Office",
    "study": "Office",
    "work": "Office",
    "desk": "Office",
    # Entry
    "entry": "Entry",
    "entryway": "Entry",
    "foyer": "Entry",
    "front": "Entry",
    # Game Room
    "game": "Game Room",
    "basement": "Game Room",
    "rec": "Game Room",
    # Gym
    "gym": "Gym",
    "exercise": "Gym",
    "workout": "Gym",
    # Garage
    "garage": "Garage",
    "car": "Garage",
    # Laundry
    "laundry": "Laundry",
    "wash": "Laundry",
    # Bath
    "bath": "Primary Bath",
    "bathroom": "Primary Bath",
    "restroom": "Primary Bath",
    # Special
    "all": None,
    "everywhere": None,
    "whole": None,
    "entire": None,
    "house": None,
}


# =============================================================================
# Flexible Parser
# =============================================================================


class SemanticIntentParser:
    """Ultra-flexible natural language intent parser.

    Handles any phrasing from either ElevenLabs or human speech:
    - "fireplace_off" → CLIMATE.FIREPLACE_OFF
    - "turn off the fireplace" → CLIMATE.FIREPLACE_OFF
    - "can you please shut down the fire" → CLIMATE.FIREPLACE_OFF
    - "extinguish the flames" → CLIMATE.FIREPLACE_OFF
    """

    def parse(self, command: str) -> ParsedIntent:
        """Parse any natural language command into structured intent."""
        # === HEAVY NORMALIZATION ===
        normalized = self._normalize(command)
        logger.info(f"🧠 Parsing: '{command}' → '{normalized}'")

        # === CONCEPT EXTRACTION ===
        tokens = set(normalized.split())

        # Find best matching concept
        best_match = None
        best_score = 0

        for concepts, category, action, priority in CONCEPT_MAP:
            # Count matching concepts
            matches = sum(
                1
                for token in tokens
                if any(
                    token.startswith(concept[:3]) or concept.startswith(token[:3])
                    for concept in concepts
                )
            )

            # Also check if any concept is a substring
            for concept in concepts:
                if concept in normalized:
                    matches += 2  # Bonus for direct substring match

            if matches > 0:
                score = matches * priority
                if score > best_score:
                    best_score = score
                    best_match = (category, action)

        if not best_match:
            logger.warning(f"❓ No intent matched for: {command}")
            return ParsedIntent(
                category=IntentCategory.UNKNOWN,
                action=IntentAction.UNKNOWN,
                confidence=0.0,
                raw_command=command,
            )

        category, default_action = best_match

        # === ACTION REFINEMENT ===
        action = self._refine_action(normalized, category, default_action)

        # === PARAMETER EXTRACTION ===
        params = self._extract_params(normalized, category)

        confidence = min(1.0, best_score / 500)

        result = ParsedIntent(
            category=category,
            action=action,
            parameters=params,
            confidence=confidence,
            raw_command=command,
        )

        logger.info(f"✅ Intent: {result}")
        return result

    def _normalize(self, text: str) -> str:
        """Heavy normalization for maximum flexibility."""
        s = text.lower()

        # Replace separators with spaces
        s = re.sub(r"[_\-/\\|]", " ", s)

        # Remove punctuation except apostrophes
        s = re.sub(r"[^\w\s']", " ", s)

        # Expand contractions
        contractions = {
            "can't": "cannot",
            "won't": "will not",
            "don't": "do not",
            "doesn't": "does not",
            "isn't": "is not",
            "aren't": "are not",
            "i'm": "i am",
            "you're": "you are",
            "it's": "it is",
            "let's": "let us",
            "that's": "that is",
            "what's": "what is",
            "i'd": "i would",
            "i'll": "i will",
            "you'll": "you will",
        }
        for contraction, expansion in contractions.items():
            s = s.replace(contraction, expansion)

        # Remove filler words
        fillers = {
            "please",
            "could",
            "would",
            "can",
            "you",
            "the",
            "a",
            "an",
            "just",
            "maybe",
            "perhaps",
            "actually",
            "really",
            "very",
            "um",
            "uh",
            "like",
            "so",
            "well",
            "hey",
            "hi",
            "okay",
            "ok",
            "sure",
            "yeah",
            "yes",
            "no",
            "not",
            "now",
            "then",
            "there",
            "here",
            "this",
            "that",
            "it",
            "is",
            "are",
            "be",
            "been",
            "being",
            "was",
            "were",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "shall",
            "should",
            "may",
            "might",
            "must",
            "need",
            "to",
            "for",
            "of",
            "in",
            "on",
            "at",
            "by",
            "with",
            "from",
            "into",
            "onto",
            "upon",
            "about",
            "some",
            "any",
            "my",
            "your",
            "his",
            "her",
            "its",
            "our",
            "their",
            "me",
            "him",
            "us",
            "them",
            "go",
            "going",
            "get",
            "getting",
            "got",
            "make",
            "making",
            "made",
            "put",
            "putting",
            "take",
            "taking",
            "i",
        }
        tokens = s.split()
        tokens = [t for t in tokens if t not in fillers or t in ON_WORDS | OFF_WORDS]

        # Collapse multiple spaces
        s = " ".join(tokens)

        return s.strip()

    def _has_word(self, text: str, words: set[str]) -> bool:
        """Check if text contains any word (with word boundaries)."""
        for word in words:
            if re.search(rf"\b{re.escape(word)}\b", text):
                return True
        return False

    def _refine_action(
        self, text: str, category: IntentCategory, default: IntentAction
    ) -> IntentAction:
        """Refine action based on on/off/open/close modifiers."""

        has_on = self._has_word(text, ON_WORDS)
        has_off = self._has_word(text, OFF_WORDS)
        self._has_word(text, OPEN_WORDS)
        has_close = self._has_word(text, CLOSE_WORDS)

        # Lighting
        if category == IntentCategory.LIGHTING:
            if has_off:
                return IntentAction.TURN_OFF
            elif has_on:
                return IntentAction.TURN_ON
            return IntentAction.SET_BRIGHTNESS

        # Shades
        if category == IntentCategory.SHADES:
            if has_close:
                return IntentAction.CLOSE
            return IntentAction.OPEN

        # Fireplace
        if category == IntentCategory.CLIMATE and default in (
            IntentAction.FIREPLACE_ON,
            IntentAction.FIREPLACE_OFF,
        ):
            if has_off:
                return IntentAction.FIREPLACE_OFF
            return IntentAction.FIREPLACE_ON

        # TV
        if category == IntentCategory.ENTERTAINMENT and default in (
            IntentAction.TV_LOWER,
            IntentAction.TV_RAISE,
        ):
            if self._has_word(text, {"raise", "up", "hide", "away", "retract"}):
                return IntentAction.TV_RAISE
            return IntentAction.TV_LOWER

        # Music
        if category == IntentCategory.ENTERTAINMENT and default == IntentAction.MUSIC_PLAY:
            if self._has_word(text, PAUSE_WORDS):
                return IntentAction.MUSIC_PAUSE
            if self._has_word(text, SKIP_WORDS):
                return IntentAction.MUSIC_SKIP
            return IntentAction.MUSIC_PLAY

        # Security
        if category == IntentCategory.SECURITY:
            if self._has_word(text, {"unlock", "open"}):
                return IntentAction.UNLOCK
            return IntentAction.LOCK_ALL

        return default

    def _extract_params(self, text: str, category: IntentCategory) -> dict[str, Any]:
        """Extract parameters like rooms, levels, playlists."""
        params: dict[str, Any] = {}

        # Rooms
        rooms = []
        for keyword, room in ROOM_MAP.items():
            if keyword in text:
                if room is None:
                    rooms = []  # "all" means no specific rooms
                    break
                if room not in rooms:
                    rooms.append(room)
        if rooms:
            params["rooms"] = rooms

        # Brightness level
        if category == IntentCategory.LIGHTING:
            level = self._extract_level(text)
            if level is not None:
                params["level"] = level

        # Playlist
        if category == IntentCategory.ENTERTAINMENT:
            playlist = self._extract_playlist(text)
            if playlist:
                params["playlist"] = playlist

        # Announcement text
        if category == IntentCategory.AUDIO:
            # Try to extract what to announce
            for pattern in [r"announce\s+(.+)", r"say\s+(.+)", r"tell\s+(.+)"]:
                match = re.search(pattern, text)
                if match:
                    params["text"] = match.group(1)
                    break

        return params

    def _extract_level(self, text: str) -> int | None:
        """Extract brightness level."""
        # Explicit percentage
        match = re.search(r"(\d+)\s*%?", text)
        if match:
            return min(100, max(0, int(match.group(1))))

        # Semantic levels (use word boundaries!)
        if self._has_word(text, {"off"}):
            return 0
        if self._has_word(text, {"dim", "low", "soft", "dark", "darker"}):
            return 30
        if self._has_word(text, {"half", "medium", "moderate"}):
            return 50
        if self._has_word(text, {"bright", "brighter", "full", "max", "maximum"}):
            return 100
        if self._has_word(text, ON_WORDS):
            return 100

        return None

    def _extract_playlist(self, text: str) -> str | None:
        """Extract playlist name."""
        playlists = {
            "focus": ["focus", "concentrate", "work", "productive"],
            "chill": ["chill", "relax", "calm", "mellow", "easy"],
            "jazz": ["jazz", "smooth"],
            "classical": ["classical", "orchestra", "symphony"],
            "workout": ["workout", "exercise", "gym", "energy", "pump"],
            "party": ["party", "upbeat", "dance", "edm"],
            "ambient": ["ambient", "background", "atmosphere"],
        }

        for name, keywords in playlists.items():
            if any(k in text for k in keywords):
                return name

        return "focus"


# =============================================================================
# Public API
# =============================================================================

_parser = SemanticIntentParser()


def parse_intent(command: str) -> ParsedIntent:
    """Parse a natural language command into structured intent.

    Handles any phrasing:
    - "fireplace_off"
    - "turn off the fireplace"
    - "can you please extinguish the flames"

    Args:
        command: Any natural language command

    Returns:
        ParsedIntent with category, action, parameters
    """
    return _parser.parse(command)


__all__ = [
    "IntentAction",
    "IntentCategory",
    "ParsedIntent",
    "SemanticIntentParser",
    "parse_intent",
]
