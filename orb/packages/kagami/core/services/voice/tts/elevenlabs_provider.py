"""ElevenLabs TTS provider for Kagami.

High-quality, low-latency TTS using ElevenLabs Flash v2.5 with
Kagami's cloned voice.

Features:
- 75ms latency with Flash v2.5
- Voice cloning with Kagami identity
- Streaming support for real-time playback
- WebSocket streaming for lowest latency

Created: January 1, 2026
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from kagami.core.services.voice.tts.base import TTSConfig, TTSProvider, TTSResult

logger = logging.getLogger(__name__)


class ElevenLabsTTS(TTSProvider):
    """ElevenLabs TTS provider.

    Uses the ElevenLabs API with Kagami's cloned voice for
    high-quality, low-latency speech synthesis.

    Usage:
        tts = ElevenLabsTTS()
        await tts.initialize()
        result = await tts.synthesize("Hello Tim")
    """

    def __init__(self, config: TTSConfig | None = None):
        """Initialize ElevenLabs TTS.

        Args:
            config: TTS configuration
        """
        super().__init__(config)
        self._client: Any = None
        self._voice_id: str | None = None
        self._api_key: str | None = None

    async def initialize(self) -> bool:
        """Initialize ElevenLabs client.

        Returns:
            True if successful
        """
        if self._initialized:
            return True

        try:
            from kagami.core.security import get_secret

            # Get API key and voice ID from keychain
            self._api_key = get_secret("elevenlabs_api_key")
            self._voice_id = get_secret("elevenlabs_kagami_voice_id")

            if not self._api_key:
                logger.error("ElevenLabs API key not found in keychain")
                return False

            if not self._voice_id:
                logger.warning("Kagami voice ID not found, will use default voice")

            # Initialize client
            from elevenlabs import ElevenLabs

            self._client = ElevenLabs(api_key=self._api_key)

            # Verify connection
            voices = self._client.voices.get_all()
            logger.info(f"✓ ElevenLabs initialized ({len(voices.voices)} voices available)")

            # Verify Kagami voice exists
            if self._voice_id:
                kagami_voice = None
                for v in voices.voices:
                    if v.voice_id == self._voice_id:
                        kagami_voice = v
                        break

                if kagami_voice:
                    logger.info(f"✓ Kagami voice ready: {kagami_voice.name}")
                else:
                    logger.warning(f"Kagami voice ID {self._voice_id} not found in account")

            self._initialized = True
            return True

        except Exception as e:
            logger.error(f"ElevenLabs initialization failed: {e}")
            return False

    async def synthesize(
        self,
        text: str,
        voice_id: str | None = None,
        **kwargs: Any,
    ) -> TTSResult:
        """Synthesize text to speech.

        Args:
            text: Text to synthesize
            voice_id: Optional voice override (uses Kagami by default)
            **kwargs: Additional options

        Returns:
            TTSResult with audio path
        """
        if not self._initialized:
            await self.initialize()

        if not self._client:
            return TTSResult(success=False, error="Client not initialized")

        start = time.perf_counter()
        voice = voice_id or self._voice_id or "mVI4sVQ8lmFpGDyfy6sQ"  # Tim's cloned voice

        try:
            # Generate audio with Kagami voice settings
            audio = self._client.text_to_speech.convert(
                voice_id=voice,
                text=text,
                model_id=self.config.model_id,
                output_format=self.config.output_format,
                voice_settings={
                    "stability": self.config.stability,
                    "similarity_boost": self.config.similarity_boost,
                    "style": self.config.style,
                    "use_speaker_boost": self.config.use_speaker_boost,
                    "speed": self.config.speed,  # Slower, measured pace
                },
            )

            # Collect audio chunks
            audio_data = b"".join(chunk for chunk in audio)
            synthesis_ms = (time.perf_counter() - start) * 1000

            # Apply volume reduction for ambient use
            audio_data = self._apply_volume(audio_data)

            # Save to temp file
            temp_dir = Path(tempfile.gettempdir()) / "kagami_tts"
            temp_dir.mkdir(exist_ok=True)
            audio_path = temp_dir / f"elevenlabs_{int(time.time() * 1000)}.mp3"

            with open(audio_path, "wb") as f:
                f.write(audio_data)

            # Estimate duration (rough: ~150 words/min, ~5 chars/word)
            word_count = len(text.split())
            duration_ms = (word_count / 150) * 60 * 1000

            return TTSResult(
                success=True,
                audio_path=audio_path,
                audio_data=audio_data,
                sample_rate=self.config.sample_rate,
                duration_ms=duration_ms,
                synthesis_ms=synthesis_ms,
                metadata={
                    "voice_id": voice,
                    "model_id": self.config.model_id,
                    "text_length": len(text),
                },
            )

        except Exception as e:
            logger.error(f"ElevenLabs synthesis failed: {e}")
            return TTSResult(success=False, error=str(e))

    async def stream_synthesize(
        self,
        text: str,
        voice_id: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[bytes]:
        """Stream synthesize text to speech.

        Uses ElevenLabs streaming API for lowest latency.

        Args:
            text: Text to synthesize
            voice_id: Optional voice override
            **kwargs: Additional options

        Yields:
            Audio chunks as bytes
        """
        if not self._initialized:
            await self.initialize()

        if not self._client:
            return

        voice = voice_id or self._voice_id or "EXAVITQu4vr4xnSDxMaL"

        try:
            # Use streaming endpoint with voice settings
            audio_stream = self._client.text_to_speech.stream(
                voice_id=voice,
                text=text,
                model_id=self.config.model_id,
                output_format=self.config.output_format,
                voice_settings={
                    "stability": self.config.stability,
                    "similarity_boost": self.config.similarity_boost,
                    "style": self.config.style,
                    "use_speaker_boost": self.config.use_speaker_boost,
                    "speed": self.config.speed,
                },
            )

            for chunk in audio_stream:
                yield chunk
                # Small yield to allow other tasks
                await asyncio.sleep(0)

        except Exception as e:
            logger.error(f"ElevenLabs stream failed: {e}")

    async def stream_to_file(
        self,
        text: str,
        output_path: Path | str,
        voice_id: str | None = None,
    ) -> TTSResult:
        """Stream synthesize directly to file.

        Args:
            text: Text to synthesize
            output_path: Output file path
            voice_id: Optional voice override

        Returns:
            TTSResult with audio path
        """
        start = time.perf_counter()
        ttfa = 0.0
        first_chunk = True
        output_path = Path(output_path)

        try:
            with open(output_path, "wb") as f:
                async for chunk in self.stream_synthesize(text, voice_id):
                    if first_chunk:
                        ttfa = (time.perf_counter() - start) * 1000
                        first_chunk = False
                    f.write(chunk)

            synthesis_ms = (time.perf_counter() - start) * 1000

            return TTSResult(
                success=True,
                audio_path=output_path,
                sample_rate=self.config.sample_rate,
                ttfa_ms=ttfa,
                synthesis_ms=synthesis_ms,
                metadata={"voice_id": voice_id or self._voice_id},
            )

        except Exception as e:
            logger.error(f"Stream to file failed: {e}")
            return TTSResult(success=False, error=str(e))

    async def list_voices(self) -> list[dict[str, Any]]:
        """List available voices.

        Returns:
            List of voice info dicts
        """
        if not self._initialized:
            await self.initialize()

        if not self._client:
            return []

        try:
            voices = self._client.voices.get_all()
            return [
                {
                    "voice_id": v.voice_id,
                    "name": v.name,
                    "description": v.description,
                    "labels": v.labels,
                    "is_kagami": v.voice_id == self._voice_id,
                }
                for v in voices.voices
            ]
        except Exception as e:
            logger.error(f"Failed to list voices: {e}")
            return []

    def _apply_volume(self, audio_data: bytes) -> bytes:
        """Apply volume adjustment to MP3 audio.

        Uses ffmpeg for reliable MP3 processing.
        Default: -6dB for softer ambient presence.
        """
        if self.config.volume_db >= 0:
            return audio_data  # No reduction needed

        try:
            import subprocess
            import tempfile

            # Write input
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f_in:
                f_in.write(audio_data)
                in_path = f_in.name

            out_path = in_path.replace(".mp3", "_soft.mp3")

            # Apply volume with ffmpeg
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    in_path,
                    "-filter:a",
                    f"volume={self.config.volume_db}dB",
                    "-q:a",
                    "2",
                    out_path,
                ],
                capture_output=True,
                check=True,
            )

            # Read output
            with open(out_path, "rb") as f:
                result = f.read()

            # Cleanup
            Path(in_path).unlink(missing_ok=True)
            Path(out_path).unlink(missing_ok=True)

            return result

        except Exception as e:
            logger.warning(f"Volume adjustment failed: {e}, using original")
            return audio_data

    @property
    def kagami_voice_id(self) -> str | None:
        """Get Kagami's voice ID."""
        return self._voice_id


# Module-level singleton
_elevenlabs_tts: ElevenLabsTTS | None = None


async def get_elevenlabs_tts(config: TTSConfig | None = None) -> ElevenLabsTTS:
    """Get the singleton ElevenLabs TTS instance.

    Args:
        config: Optional configuration (only used on first call)

    Returns:
        ElevenLabsTTS instance
    """
    global _elevenlabs_tts
    if _elevenlabs_tts is None:
        _elevenlabs_tts = ElevenLabsTTS(config)
        await _elevenlabs_tts.initialize()
    return _elevenlabs_tts
