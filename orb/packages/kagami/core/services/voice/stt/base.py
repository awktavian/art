from __future__ import annotations

"""Speech-to-Text provider interfaces for K os.

Defines a minimal pluggable interface for streaming/batch ASR that can be
implemented by local open-weights backends or cloud providers.
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class STTSession:
    """Holds per-session buffers and configuration for an STT stream."""

    session_id: str
    sample_rate: int = 16000
    channels: int = 1
    format: str = "pcm16"
    language: str | None = None
    buffer: bytearray = field(default_factory=bytearray)
    # Arbitrary per-session metadata (e.g., target_lang) for downstream use
    context: dict[str, Any] = field(default_factory=dict[str, Any])


class BaseSTTProvider:
    """Abstract base class for STT providers."""

    name: str = "base"

    async def initialize(self) -> None:  # pragma: no cover - default no-op
        return None

    async def start_session(
        self,
        session_id: str,
        sample_rate: int = 16000,
        channels: int = 1,
        fmt: str = "pcm16",
        language: str | None = None,
        **kwargs: Any,
    ) -> STTSession:
        # Accept a provided context dict[str, Any], and also promote common keys
        context: dict[str, Any] = {}
        try:
            provided = kwargs.get("context")
            if isinstance(provided, dict):
                context.update(provided)
        except Exception:
            pass
        # Common convenience fields (safe to include redundantly)
        if language is not None:
            context.setdefault("language", language)
        target_lang = kwargs.get("target_lang")
        if target_lang is not None:
            context.setdefault("target_lang", target_lang)

        return STTSession(
            session_id=session_id,
            sample_rate=sample_rate,
            channels=channels,
            format=fmt,
            language=language,
            context=context,
        )

    async def accept_chunk(self, session: STTSession, audio_bytes: bytes) -> None:
        session.buffer.extend(audio_bytes)

    async def get_partial(self, session: STTSession) -> str | None:  # pragma: no cover
        return None

    async def finalize(self, session: STTSession) -> str:
        """Finalize the session and return the full transcript as a string."""
        # Base provider returns an empty transcript by default. Concrete providers
        # should override this with real transcription logic. Returning a string
        # keeps upstream flows robust without placeholder exceptions.
        return ""

    async def cancel(self, session: STTSession) -> None:  # pragma: no cover
        session.buffer.clear()
