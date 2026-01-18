"""Character Protocol — Universal character definition.

All characters (humans, pets, AI, historical) use this unified protocol.
Ground truth is always assets/characters/*/metadata.json.

Architecture:
    assets/characters/
    ├── bella/metadata.json      ← Malamute
    ├── tim/metadata.json        ← Household member
    ├── jill/metadata.json       ← Household member
    ├── kagami/metadata.json     ← AI assistant
    ├── dcc/                     ← Dallas Cowboys Cheerleaders
    │   ├── kelli_finglass/
    │   └── ...
    └── kristi/metadata.json     ← Guest (Tim's sister)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Character assets root
# __file__ is kagami/packages/kagami_studio/characters/protocol.py
# parents[3] = kagami/
CHARACTERS_DIR = Path(__file__).parents[3] / "assets" / "characters"


class CharacterRole(str, Enum):
    """Character role in the household."""

    HOUSEHOLD = "household"  # Tim, Jill - full trust
    GUEST = "guest"  # Visitors
    PET = "pet"  # Bella
    AI = "ai"  # Kagami
    FAMILY_HISTORICAL = "family_historical"  # Childhood characters
    EXTERNAL = "external"  # DCC, etc.


@dataclass(frozen=True)
class VoiceConfig:
    """Voice configuration for TTS."""

    voice_id: str | None
    model: str = "eleven_v3"  # ALWAYS V3 for audio tags
    stability: float = 0.5
    similarity_boost: float = 0.75
    style: float = 0.35
    speed: float = 1.0
    use_speaker_boost: bool = True

    # V3 audio tags that work well for this character
    effective_tags: list[str] = field(default_factory=list)
    avoid_tags: list[str] = field(default_factory=list)

    def to_elevenlabs(self) -> dict[str, Any]:
        """Convert to ElevenLabs voice_settings dict."""
        return {
            "stability": self.stability,
            "similarity_boost": self.similarity_boost,
            "style": self.style,
            "speed": self.speed,
            "use_speaker_boost": self.use_speaker_boost,
        }


@dataclass(frozen=True)
class AvatarConfig:
    """Avatar configuration for video generation."""

    # HeyGen settings
    heygen_avatar_id: str | None = None

    # Image-based avatar (for Avatar IV)
    reference_images: list[Path] = field(default_factory=list)
    primary_image: Path | None = None

    # Motion preferences
    default_motion: str = "warm"
    motion_intensity: float = 0.5

    # Video settings
    video_orientation: str = "landscape"
    fit: str = "contain"


@dataclass(frozen=True)
class PersonalityConfig:
    """Personality and behavior configuration."""

    summary: str = ""
    traits: list[str] = field(default_factory=list)
    speaking_style: str = ""
    wpm: int = 150
    catch_phrases: list[str] = field(default_factory=list)
    quirks: list[str] = field(default_factory=list)


@dataclass
class Character:
    """Universal character definition.

    Unified protocol for ALL characters:
    - Household members (Tim, Jill)
    - Pets (Bella the Malamute)
    - AI (Kagami)
    - Guests (Kristi)
    - External (DCC)
    - Historical (childhood)
    """

    # Identity
    identity_id: str
    name: str
    full_name: str = ""
    role: CharacterRole = CharacterRole.EXTERNAL

    # Relationships
    relationship: str = ""
    owner: str | None = None  # For pets

    # Species (for non-humans)
    species: str = "human"
    breed: str | None = None

    # Configurations
    voice: VoiceConfig = field(default_factory=lambda: VoiceConfig(voice_id=None))
    avatar: AvatarConfig = field(default_factory=AvatarConfig)
    personality: PersonalityConfig = field(default_factory=PersonalityConfig)

    # Raw metadata (for custom fields)
    metadata: dict[str, Any] = field(default_factory=dict)

    # Source
    metadata_path: Path | None = None

    @classmethod
    def from_metadata(cls, path: Path) -> Character:
        """Load character from metadata.json file."""
        with open(path) as f:
            data = json.load(f)

        # Parse role
        role_str = data.get("role", "external")
        try:
            role = CharacterRole(role_str)
        except ValueError:
            role = CharacterRole.EXTERNAL

        # Parse voice config
        voice_settings = data.get("voice_settings", {})
        v3_tags = data.get("v3_audio_tags", {})
        voice = VoiceConfig(
            voice_id=data.get("voice_id") or data.get("elevenlabs_voice_id"),
            stability=voice_settings.get("stability", 0.5),
            similarity_boost=voice_settings.get("similarity_boost", 0.75),
            style=voice_settings.get("style", 0.35),
            speed=voice_settings.get("speed", 1.0),
            use_speaker_boost=voice_settings.get("speaker_boost", True),
            effective_tags=v3_tags.get("effective", []),
            avoid_tags=v3_tags.get("avoid", []),
        )

        # Parse avatar config
        images = data.get("images", [])
        reference_paths = []
        primary_path = None
        for img in images:
            img_path = path.parent / img.get("path", "").replace("assets/characters/", "").lstrip(
                "./"
            )
            if img_path.exists():
                reference_paths.append(img_path)
                if img.get("weight", 1.0) >= 1.0 and not primary_path:
                    primary_path = img_path

        # Also check for direct reference images
        if not reference_paths:
            for pattern in ["reference*.jpg", "reference*.png", "*.jpg", "*.png"]:
                found = list(path.parent.glob(pattern))
                if found:
                    reference_paths.extend(found[:5])  # Max 5
                    if not primary_path:
                        primary_path = found[0]
                    break

        avatar = AvatarConfig(
            heygen_avatar_id=data.get("heygen_avatar_id"),
            reference_images=reference_paths,
            primary_image=primary_path,
        )

        # Parse personality (handles multiple metadata formats)
        personality_data = data.get("personality", {})
        speech_data = data.get("speech_profile", {})
        pixar_data = data.get("pixar_voice", {})
        voice_char = data.get("voice_characteristics", {})

        # Traits: try core_traits, then traits
        traits = personality_data.get("core_traits", []) or personality_data.get("traits", [])

        # Speaking style: try speech_profile.style, then voice_characteristics.style
        speaking_style = speech_data.get("style", "") or voice_char.get("style", "")

        # WPM: try speech_profile.wpm first
        wpm = speech_data.get("wpm", voice_char.get("suggested_speed", 1.0) * 150)

        # Catch phrases: try multiple locations
        catch_phrases = (
            pixar_data.get("speaking_style", {}).get("catch_phrases", [])
            or personality_data.get("catchphrases", [])
            or speech_data.get("signature_phrases", [])
        )

        personality = PersonalityConfig(
            summary=personality_data.get("summary", ""),
            traits=traits,
            speaking_style=speaking_style,
            wpm=int(wpm),
            catch_phrases=catch_phrases,
            quirks=personality_data.get("quirks", []),
        )

        return cls(
            identity_id=data.get("identity_id", path.parent.name),
            name=data.get("character_name", path.parent.name.replace("_", " ").title()),
            full_name=data.get("full_name", ""),
            role=role,
            relationship=data.get("relationship", ""),
            owner=data.get("owner"),
            species=data.get("species", "human"),
            breed=data.get("breed"),
            voice=voice,
            avatar=avatar,
            personality=personality,
            metadata=data,
            metadata_path=path,
        )

    @property
    def has_voice(self) -> bool:
        """Whether this character has TTS capability."""
        return self.voice.voice_id is not None

    @property
    def has_avatar(self) -> bool:
        """Whether this character can generate video."""
        return self.avatar.heygen_avatar_id is not None or self.avatar.primary_image is not None

    @property
    def is_pet(self) -> bool:
        """Whether this is a pet character."""
        return self.species != "human" or self.role == CharacterRole.PET

    @property
    def is_household(self) -> bool:
        """Whether this is a household member (full trust)."""
        return self.role == CharacterRole.HOUSEHOLD


# =============================================================================
# LOADING FUNCTIONS
# =============================================================================


@lru_cache(maxsize=50)
def load_character(name: str) -> Character | None:
    """Load a character by name or identity_id.

    Args:
        name: Character name (bella, tim, kelli_finglass, etc.)

    Returns:
        Character or None if not found
    """
    # Normalize name
    name_key = name.lower().replace(" ", "_")

    # Try direct path
    direct_path = CHARACTERS_DIR / name_key / "metadata.json"
    if direct_path.exists():
        return Character.from_metadata(direct_path)

    # Try DCC subdirectory
    dcc_path = CHARACTERS_DIR / "dcc" / name_key / "metadata.json"
    if dcc_path.exists():
        return Character.from_metadata(dcc_path)

    # Search all subdirectories
    for subdir in CHARACTERS_DIR.iterdir():
        if subdir.is_dir():
            meta = subdir / "metadata.json"
            if meta.exists():
                with open(meta) as f:
                    data = json.load(f)
                if data.get("identity_id", "").lower() == name_key:
                    return Character.from_metadata(meta)
                if data.get("character_name", "").lower() == name_key:
                    return Character.from_metadata(meta)

    logger.warning(f"Character not found: {name}")
    return None


def get_character(name: str) -> Character:
    """Load a character by name, raising if not found."""
    char = load_character(name)
    if char is None:
        raise ValueError(f"Character not found: {name}")
    return char


def list_characters() -> list[str]:
    """List all available character identity_ids."""
    characters = []

    for subdir in CHARACTERS_DIR.iterdir():
        if subdir.is_dir():
            meta = subdir / "metadata.json"
            if meta.exists():
                with open(meta) as f:
                    data = json.load(f)
                characters.append(data.get("identity_id", subdir.name))

            # Check for nested (DCC style)
            for nested in subdir.iterdir():
                if nested.is_dir():
                    nested_meta = nested / "metadata.json"
                    if nested_meta.exists():
                        with open(nested_meta) as f:
                            data = json.load(f)
                        characters.append(data.get("identity_id", nested.name))

    return sorted(set(characters))


def list_characters_by_role(role: CharacterRole | str) -> list[Character]:
    """List all characters with a specific role."""
    if isinstance(role, str):
        role = CharacterRole(role)

    result = []
    for name in list_characters():
        char = load_character(name)
        if char and char.role == role:
            result.append(char)

    return result


__all__ = [
    "CHARACTERS_DIR",
    "AvatarConfig",
    "Character",
    "CharacterRole",
    "PersonalityConfig",
    "VoiceConfig",
    "get_character",
    "list_characters",
    "list_characters_by_role",
    "load_character",
]
