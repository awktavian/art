"""Unified Character System — Single source of truth for all characters.

Loads characters from assets/characters/*/metadata.json and provides:
- Voice settings (ElevenLabs)
- Avatar settings (HeyGen)
- Personality/behavior
- Smart home integration

Usage:
    from kagami_studio.characters import Character, load_character, list_characters

    # Load any character
    bella = load_character("bella")
    tim = load_character("tim")

    # Access voice
    await bella.speak("SNOW!")

    # Access avatar
    video = await bella.generate_video("I'm so happy!")

    # List all
    for name in list_characters():
        char = load_character(name)
        print(f"{char.name}: {char.role}")
"""

from kagami_studio.characters.protocol import (
    AvatarConfig,
    Character,
    PersonalityConfig,
    VoiceConfig,
    get_character,
    list_characters,
    list_characters_by_role,
    load_character,
)
from kagami_studio.characters.voice import (
    CharacterVoice,
    Mood,
    RemixVariant,
    SpeakResult,
    get_voice,
    speak,
    speak_with_emotion,
)

__all__ = [
    "AvatarConfig",
    "Character",
    "CharacterVoice",
    "Mood",
    "PersonalityConfig",
    "RemixVariant",
    "SpeakResult",
    "VoiceConfig",
    "get_character",
    "get_voice",
    "list_characters",
    "list_characters_by_role",
    "load_character",
    "speak",
    "speak_with_emotion",
]
