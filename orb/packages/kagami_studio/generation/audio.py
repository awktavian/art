"""Audio Generation — ElevenLabs API.

Implements audio_tts, audio_sfx, audio_clone from action_space.py.

API: ElevenLabs (https://elevenlabs.io)
Latency: <5 seconds (FAST)
Output: MP3 audio

Created: 2026-01-05
"""

from __future__ import annotations

import logging
import os
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class AudioGenerator:
    """ElevenLabs API client for audio generation.

    Implements:
        - audio_tts: Text-to-speech with voice selection
        - audio_sfx: Sound effects generation
        - audio_clone: Voice cloning from sample
    """

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        self.base_url = "https://api.elevenlabs.io/v1"
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers={"xi-api-key": self.api_key})
        return self._session

    async def tts(
        self,
        text: str,
        voice_id: str = "21m00Tcm4TlvDq8ikWAM",  # Default voice
        *,
        stability: float = 0.5,
        similarity_boost: float = 0.75,
        style: float = 0.0,
    ) -> bytes:
        """Text-to-speech generation.

        Args:
            text: Text to speak
            voice_id: ElevenLabs voice ID
            stability: Voice stability (0-1)
            similarity_boost: Voice similarity (0-1)
            style: Style exaggeration (0-1)

        Returns:
            MP3 audio bytes
        """
        session = await self._get_session()

        payload = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity_boost,
                "style": style,
            },
        }

        async with session.post(
            f"{self.base_url}/text-to-speech/{voice_id}",
            json=payload,
        ) as resp:
            if resp.status != 200:
                raise RuntimeError(f"ElevenLabs TTS error: {resp.status}")
            return await resp.read()

    async def sfx(
        self,
        prompt: str,
        duration: float = 3.0,
    ) -> bytes:
        """Generate sound effects from text description.

        Args:
            prompt: Description of sound
            duration: Duration in seconds

        Returns:
            MP3 audio bytes
        """
        session = await self._get_session()

        payload = {
            "text": prompt,
            "duration_seconds": duration,
        }

        async with session.post(
            f"{self.base_url}/sound-generation",
            json=payload,
        ) as resp:
            if resp.status != 200:
                raise RuntimeError(f"ElevenLabs SFX error: {resp.status}")
            return await resp.read()

    async def clone_voice(
        self,
        name: str,
        sample_urls: list[str],
        description: str = "",
    ) -> str:
        """Clone voice from audio samples.

        Args:
            name: Name for cloned voice
            sample_urls: URLs of voice samples (25+ seconds total)
            description: Description of voice characteristics

        Returns:
            Voice ID for use with tts()
        """
        session = await self._get_session()

        # Download samples
        samples = []
        for url in sample_urls:
            async with session.get(url) as resp:
                samples.append(await resp.read())

        # Create form data
        form = aiohttp.FormData()
        form.add_field("name", name)
        if description:
            form.add_field("description", description)

        for i, sample in enumerate(samples):
            form.add_field(
                "files",
                sample,
                filename=f"sample_{i}.mp3",
                content_type="audio/mpeg",
            )

        async with session.post(
            f"{self.base_url}/voices/add",
            data=form,
        ) as resp:
            if resp.status != 200:
                raise RuntimeError(f"ElevenLabs clone error: {resp.status}")
            data = await resp.json()
            return data.get("voice_id")

    async def list_voices(self) -> list[dict[str, Any]]:
        """List available voices."""
        session = await self._get_session()
        async with session.get(f"{self.base_url}/voices") as resp:
            data = await resp.json()
            return data.get("voices", [])

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()


def get_audio_generator() -> AudioGenerator:
    return AudioGenerator()
