"""Unified Voice API — STT, Speaker ID, and TTS endpoints.

Exposes the UnifiedVoicePipeline to client apps:
- STT: Transcribe audio to text
- Speaker ID: Identify speaker from audio
- TTS: Speak text (routes through voice effector)

All apps should use these endpoints for voice operations.

Created: January 1, 2026
"""

from __future__ import annotations

import base64
import logging
import tempfile
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


def get_router() -> APIRouter:
    """Get voice API router."""
    router = APIRouter(prefix="/api/voice", tags=["voice"])

    # =========================================================================
    # SCHEMAS
    # =========================================================================

    class TranscribeRequest(BaseModel):
        """Request to transcribe audio."""

        audio_base64: str = Field(..., description="Base64-encoded audio data")
        language: str = Field(default="en", description="Language code")
        identify_speaker: bool = Field(default=True, description="Whether to identify speaker")

    class TranscribeResponse(BaseModel):
        """Response from transcription."""

        success: bool
        transcript: str = ""
        confidence: float = 0.0
        speaker_id: str | None = None
        speaker_name: str | None = None
        speaker_confidence: float = 0.0
        processing_time_ms: float = 0.0
        error: str | None = None

    class SpeakRequest(BaseModel):
        """Request to speak text."""

        text: str = Field(..., description="Text to speak")
        target: str = Field(default="auto", description="Target: auto, home_room, car, etc.")
        rooms: list[str] | None = Field(default=None, description="Specific rooms")
        colony: str = Field(default="kagami", description="Voice personality")
        personalize: bool = Field(default=False, description="Personalize with speaker name")
        priority: str = Field(default="normal", description="Priority level")

    class SpeakResponse(BaseModel):
        """Response from speech."""

        success: bool
        target: str
        target_detail: str = ""
        latency_ms: float = 0.0
        error: str | None = None

    class IdentifyRequest(BaseModel):
        """Request to identify speaker."""

        audio_base64: str = Field(..., description="Base64-encoded audio data")

    class IdentifyResponse(BaseModel):
        """Response from speaker identification."""

        is_identified: bool
        user_id: str | None = None
        name: str | None = None
        confidence: float = 0.0
        all_scores: dict[str, float] = Field(default_factory=dict)

    class PipelineStatusResponse(BaseModel):
        """Voice pipeline status."""

        initialized: bool
        stt_available: bool
        speaker_id_available: bool
        tts_available: bool
        stats: dict[str, Any] = Field(default_factory=dict)

    # =========================================================================
    # ROUTES
    # =========================================================================

    @router.post("/transcribe", response_model=TranscribeResponse, summary="Transcribe audio")
    async def transcribe_audio(request: TranscribeRequest) -> TranscribeResponse:
        """Transcribe audio to text with optional speaker identification.

        This is THE endpoint for voice input. All apps should use this.

        Args:
            request: TranscribeRequest with audio and options

        Returns:
            TranscribeResponse with transcript and speaker info
        """
        start = time.perf_counter()

        try:
            # Decode audio
            audio_bytes = base64.b64decode(request.audio_base64)

            # Write to temp file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(audio_bytes)
                audio_path = Path(f.name)

            # Get unified pipeline
            from kagami.core.voice import get_voice_pipeline

            pipeline = await get_voice_pipeline()

            # Process input
            result = await pipeline.process_input(
                audio_data=audio_path,
                language=request.language,
                identify_speaker=request.identify_speaker,
            )

            # Clean up temp file
            audio_path.unlink(missing_ok=True)

            return TranscribeResponse(
                success=result.success,
                transcript=result.transcript,
                confidence=0.8,  # From STT
                speaker_id=result.speaker.speaker.user_id if result.speaker.speaker else None,
                speaker_name=result.speaker.speaker.name if result.speaker.speaker else None,
                speaker_confidence=result.speaker.confidence,
                processing_time_ms=(time.perf_counter() - start) * 1000,
                error=result.error,
            )

        except ImportError as e:
            raise HTTPException(
                status_code=503,
                detail="Voice pipeline not available",
            ) from e
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return TranscribeResponse(
                success=False,
                error=str(e),
                processing_time_ms=(time.perf_counter() - start) * 1000,
            )

    @router.post("/transcribe/upload", response_model=TranscribeResponse)
    async def transcribe_upload(
        file: UploadFile = File(...),
        language: str = Form(default="en"),
        identify_speaker: bool = Form(default=True),
    ) -> TranscribeResponse:
        """Transcribe uploaded audio file.

        Alternative to base64 for larger audio files.
        """
        start = time.perf_counter()

        try:
            # Save uploaded file
            with tempfile.NamedTemporaryFile(
                suffix=Path(file.filename or "audio.wav").suffix,
                delete=False,
            ) as f:
                content = await file.read()
                f.write(content)
                audio_path = Path(f.name)

            # Get unified pipeline
            from kagami.core.voice import get_voice_pipeline

            pipeline = await get_voice_pipeline()

            # Process input
            result = await pipeline.process_input(
                audio_data=audio_path,
                language=language,
                identify_speaker=identify_speaker,
            )

            # Clean up
            audio_path.unlink(missing_ok=True)

            return TranscribeResponse(
                success=result.success,
                transcript=result.transcript,
                speaker_id=result.speaker.speaker.user_id if result.speaker.speaker else None,
                speaker_name=result.speaker.speaker.name if result.speaker.speaker else None,
                speaker_confidence=result.speaker.confidence,
                processing_time_ms=(time.perf_counter() - start) * 1000,
                error=result.error,
            )

        except ImportError as e:
            raise HTTPException(status_code=503, detail="Voice pipeline not available") from e
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return TranscribeResponse(
                success=False,
                error=str(e),
                processing_time_ms=(time.perf_counter() - start) * 1000,
            )

    @router.post("/speak", response_model=SpeakResponse, summary="Speak text")
    async def speak_text(request: SpeakRequest) -> SpeakResponse:
        """Speak text through the voice effector.

        Routes to appropriate output based on presence context.

        Args:
            request: SpeakRequest with text and options

        Returns:
            SpeakResponse with success and target info
        """
        start = time.perf_counter()

        try:
            # Get voice effector
            from kagami.core.effectors.voice import VoicePriority, VoiceTarget, get_voice_effector

            effector = await get_voice_effector()

            # Map target string to enum
            target_map = {
                "auto": VoiceTarget.AUTO,
                "home_room": VoiceTarget.HOME_ROOM,
                "home_all": VoiceTarget.HOME_ALL,
                "car": VoiceTarget.CAR,
                "glasses": VoiceTarget.GLASSES,
                "desktop": VoiceTarget.DESKTOP,
            }
            target = target_map.get(request.target.lower(), VoiceTarget.AUTO)

            # Map priority
            priority_map = {
                "critical": VoicePriority.CRITICAL,
                "high": VoicePriority.HIGH,
                "normal": VoicePriority.NORMAL,
                "low": VoicePriority.LOW,
                "ambient": VoicePriority.AMBIENT,
            }
            priority = priority_map.get(request.priority.lower(), VoicePriority.NORMAL)

            # Speak
            result = await effector.speak(
                text=request.text,
                target=target,
                rooms=request.rooms,
                colony=request.colony,
                priority=priority,
                personalize=request.personalize,
            )

            return SpeakResponse(
                success=result.success,
                target=result.target.value,
                target_detail=result.target_detail,
                latency_ms=(time.perf_counter() - start) * 1000,
                error=result.error,
            )

        except ImportError as e:
            raise HTTPException(status_code=503, detail="Voice effector not available") from e
        except Exception as e:
            logger.error(f"Speech error: {e}")
            return SpeakResponse(
                success=False,
                target="error",
                error=str(e),
                latency_ms=(time.perf_counter() - start) * 1000,
            )

    @router.post("/identify", response_model=IdentifyResponse, summary="Identify speaker")
    async def identify_speaker(request: IdentifyRequest) -> IdentifyResponse:
        """Identify speaker from audio.

        Uses voice embeddings to match against registered profiles.
        """
        try:
            # Decode audio
            audio_bytes = base64.b64decode(request.audio_base64)

            # Write to temp file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(audio_bytes)
                audio_path = Path(f.name)

            # Get unified pipeline
            from kagami.core.voice import get_voice_pipeline

            pipeline = await get_voice_pipeline()

            # Just do speaker ID
            if pipeline._speaker_id:
                embedding = await pipeline._speaker_id.extract_embedding(audio_path)
                match = await pipeline._speaker_id.identify(embedding)

                # Clean up
                audio_path.unlink(missing_ok=True)

                return IdentifyResponse(
                    is_identified=match.is_identified,
                    user_id=match.speaker.user_id if match.speaker else None,
                    name=match.speaker.name if match.speaker else None,
                    confidence=match.confidence,
                    all_scores=match.all_scores,
                )

            audio_path.unlink(missing_ok=True)
            return IdentifyResponse(is_identified=False)

        except ImportError as e:
            raise HTTPException(status_code=503, detail="Voice pipeline not available") from e
        except Exception as e:
            logger.error(f"Speaker ID error: {e}")
            return IdentifyResponse(is_identified=False)

    @router.get("/status", response_model=PipelineStatusResponse, summary="Pipeline status")
    async def get_pipeline_status() -> PipelineStatusResponse:
        """Get voice pipeline status."""
        try:
            from kagami.core.voice import get_voice_pipeline

            pipeline = await get_voice_pipeline()

            return PipelineStatusResponse(
                initialized=pipeline._initialized,
                stt_available=pipeline._stt is not None,
                speaker_id_available=pipeline._speaker_id is not None,
                tts_available=pipeline._voice_effector is not None,
                stats=pipeline.get_stats(),
            )

        except ImportError:
            return PipelineStatusResponse(
                initialized=False,
                stt_available=False,
                speaker_id_available=False,
                tts_available=False,
            )
        except Exception as e:
            logger.error(f"Status error: {e}")
            return PipelineStatusResponse(
                initialized=False,
                stt_available=False,
                speaker_id_available=False,
                tts_available=False,
            )

    return router


__all__ = ["get_router"]
