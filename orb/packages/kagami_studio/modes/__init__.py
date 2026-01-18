"""Production Modes — Specialized production workflows.

Each mode provides a streamlined API for specific production types:
- Holodeck: Multi-party dialogue simulation
- Podcast: Audio-first production with optional video
- Documentary: Interview/B-roll structure
- Announcement: Quick single-shot announcements

Usage:
    from kagami_studio.modes import Holodeck, Podcast

    # Multi-party dialogue
    holodeck = Holodeck()
    await holodeck.initialize()
    holodeck.dialogue("bella", "I am built for the cold.")
    holodeck.dialogue("kagami", "Would you like me to lower the thermostat?")
    result = await holodeck.render()

    # Podcast
    podcast = Podcast(hosts=["tim", "jill"])
    await podcast.discuss("Smart home automation trends")
    result = await podcast.render()
"""

from kagami_studio.modes.holodeck import (
    DialogueLine,
    Holodeck,
    HolodeckResult,
    simulate_dialogue,
)

__all__ = [
    "DialogueLine",
    "Holodeck",
    "HolodeckResult",
    "simulate_dialogue",
]
