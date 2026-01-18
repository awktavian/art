"""Gemini 3 VLM — Video Understanding Engine.

Primary video understanding using Google's Gemini 3 Pro model.
Provides accurate transcription, scene analysis, and video comprehension.

ARCHITECTURE:
    Video → Gemini 3 Upload → VLM Analysis → Structured Output
                                    ↓
                         TranscriptResult (compatible)

MODELS:
- gemini-3-pro-preview: Best quality, slowest
- gemini-3-flash-preview: Good quality, faster
- gemini-2.5-pro: Fallback if 3 unavailable
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import google.generativeai as genai

logger = logging.getLogger(__name__)


class VLMModel(str, Enum):
    """Available VLM models in priority order."""

    GEMINI_3_PRO = "gemini-3-pro-preview"
    GEMINI_3_FLASH = "gemini-3-flash-preview"
    GEMINI_25_PRO = "gemini-2.5-pro"
    GEMINI_25_FLASH = "gemini-2.5-flash"


# Model priority for automatic selection
MODEL_PRIORITY = [
    VLMModel.GEMINI_3_PRO,
    VLMModel.GEMINI_3_FLASH,
    VLMModel.GEMINI_25_PRO,
    VLMModel.GEMINI_25_FLASH,
]


@dataclass
class VLMConfig:
    """VLM configuration.

    Attributes:
        model: Model to use (default: auto-select best available)
        api_key: Gemini API key (default: from keychain)
        include_word_timing: Estimate word-level timestamps
        include_speaker_id: Identify different speakers
        include_emotions: Detect emotional content
        include_sound_effects: Transcribe non-speech sounds
        language_hint: Expected language (helps accuracy)
    """

    model: VLMModel | None = None
    api_key: str | None = None
    include_word_timing: bool = True
    include_speaker_id: bool = True
    include_emotions: bool = True
    include_sound_effects: bool = True
    language_hint: str = "en"


@dataclass
class VLMWord:
    """Word with timing information."""

    text: str
    start: float
    end: float
    confidence: float = 0.95


@dataclass
class VLMSegment:
    """Transcript segment."""

    text: str
    start: float
    end: float
    words: list[VLMWord] = field(default_factory=list)
    speaker: str | None = None
    emotion: str | None = None


@dataclass
class VLMTranscript:
    """Complete video transcript."""

    segments: list[VLMSegment]
    language: str
    duration: float
    model_used: str

    @property
    def full_text(self) -> str:
        """Get full transcript text."""
        return " ".join(seg.text for seg in self.segments)

    @property
    def word_count(self) -> int:
        """Total word count."""
        return sum(len(seg.words) for seg in self.segments)


@dataclass
class VLMScene:
    """Scene description."""

    start: float
    end: float
    description: str
    objects: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    mood: str | None = None


@dataclass
class VLMAnalysis:
    """Full video analysis."""

    transcript: VLMTranscript
    scenes: list[VLMScene] = field(default_factory=list)
    summary: str = ""
    topics: list[str] = field(default_factory=list)
    people_count: int = 0
    duration: float = 0.0


def _get_api_key() -> str:
    """Get Gemini API key from keychain."""
    try:
        return (
            subprocess.check_output(
                ["security", "find-generic-password", "-s", "kagami", "-a", "gemini_api_key", "-w"]
            )
            .decode()
            .strip()
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            "Gemini API key not found in keychain. "
            "Add with: security add-generic-password -s kagami -a gemini_api_key -w YOUR_KEY"
        ) from e


class GeminiVLM:
    """Gemini Vision Language Model interface.

    Handles video upload, processing, and structured output extraction.

    Usage:
        vlm = GeminiVLM()
        await vlm.initialize()

        transcript = await vlm.transcribe("video.mp4")
        analysis = await vlm.analyze("video.mp4")
    """

    def __init__(self, config: VLMConfig | None = None):
        """Initialize VLM.

        Args:
            config: VLM configuration (optional)
        """
        self.config = config or VLMConfig()
        self._client = None
        self._model = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize Gemini client and select best model."""
        if self._initialized:
            return

        from google import genai

        api_key = self.config.api_key or _get_api_key()
        self._client = genai.Client(api_key=api_key)

        # Select model
        if self.config.model:
            self._model = self.config.model.value
        else:
            # Auto-select best available
            available = {m.name for m in self._client.models.list()}
            for model in MODEL_PRIORITY:
                if f"models/{model.value}" in available:
                    self._model = model.value
                    break

            if not self._model:
                raise RuntimeError("No Gemini model available")

        logger.info(f"VLM initialized with model: {self._model}")
        self._initialized = True

    async def _upload_video(self, video_path: Path) -> genai.File:
        """Upload video to Gemini."""

        video_file = self._client.files.upload(file=str(video_path))

        # Wait for processing
        while video_file.state.name == "PROCESSING":
            await asyncio.sleep(2)
            video_file = self._client.files.get(name=video_file.name)

        if video_file.state.name != "ACTIVE":
            raise RuntimeError(f"Video upload failed: {video_file.state.name}")

        return video_file

    async def transcribe(
        self,
        video_path: Path | str,
        progress_callback: Callable[[str, float], None] | None = None,
    ) -> VLMTranscript:
        """Transcribe video using Gemini VLM.

        Args:
            video_path: Path to video file
            progress_callback: Optional progress callback(status, percent)

        Returns:
            VLMTranscript with word-level timing
        """
        await self.initialize()
        video_path = Path(video_path)

        if progress_callback:
            progress_callback("Uploading video...", 10)

        video_file = await self._upload_video(video_path)

        if progress_callback:
            progress_callback("Transcribing with Gemini 3...", 40)

        # Build prompt based on config
        prompt = self._build_transcription_prompt()

        response = self._client.models.generate_content(
            model=self._model, contents=[video_file, prompt]
        )

        if progress_callback:
            progress_callback("Parsing transcript...", 80)

        # Parse response
        transcript = self._parse_transcript_response(response.text)
        transcript.model_used = self._model

        if progress_callback:
            progress_callback("Complete", 100)

        return transcript

    def _build_transcription_prompt(self) -> str:
        """Build transcription prompt based on config."""
        parts = [
            "Transcribe this video with precise timing.",
            "",
            "OUTPUT FORMAT - Return ONLY valid JSON:",
            "{",
            '  "language": "detected language code",',
            '  "duration": total_seconds,',
            '  "segments": [',
            "    {",
            '      "start": 0.0,',
            '      "end": 2.5,',
            '      "text": "exact words spoken",',
        ]

        if self.config.include_speaker_id:
            parts.append('      "speaker": "speaker identifier or description",')

        if self.config.include_emotions:
            parts.append('      "emotion": "neutral/happy/sad/excited/etc",')

        parts.extend(
            [
                "    }",
                "  ]",
                "}",
                "",
                "RULES:",
                "- Transcribe EXACTLY what is spoken, including mistakes",
                "- Include accurate start/end timestamps",
            ]
        )

        if self.config.include_sound_effects:
            parts.append(
                "- Include non-speech sounds in [brackets] like [coughing], [laughter], [door slam]"
            )

        if self.config.language_hint:
            parts.append(f"- Expected language: {self.config.language_hint}")

        return "\n".join(parts)

    def _parse_transcript_response(self, text: str) -> VLMTranscript:
        """Parse Gemini response into VLMTranscript."""
        # Extract JSON
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        data = json.loads(text)

        segments = []
        for seg in data.get("segments", []):
            # Generate word timing
            words = self._estimate_word_timing(seg["text"], seg["start"], seg["end"])

            segments.append(
                VLMSegment(
                    text=seg["text"],
                    start=seg["start"],
                    end=seg["end"],
                    words=words,
                    speaker=seg.get("speaker"),
                    emotion=seg.get("emotion"),
                )
            )

        return VLMTranscript(
            segments=segments,
            language=data.get("language", "en"),
            duration=data.get("duration", segments[-1].end if segments else 0),
            model_used=self._model or "unknown",
        )

    def _estimate_word_timing(
        self,
        text: str,
        start: float,
        end: float,
    ) -> list[VLMWord]:
        """Estimate word-level timing from segment timing."""
        words = text.split()
        if not words:
            return []

        duration = end - start
        # Weight by word length for more accurate timing
        total_chars = sum(len(w) for w in words)

        result = []
        current_time = start

        for word in words:
            word_duration = (
                (len(word) / total_chars) * duration if total_chars > 0 else duration / len(words)
            )
            word_end = current_time + word_duration

            result.append(
                VLMWord(
                    text=word,
                    start=round(current_time, 3),
                    end=round(word_end, 3),
                    confidence=0.9,
                )
            )

            current_time = word_end

        return result

    async def analyze(
        self,
        video_path: Path | str,
        include_scenes: bool = True,
        include_summary: bool = True,
    ) -> VLMAnalysis:
        """Full video analysis including transcript, scenes, and summary.

        Args:
            video_path: Path to video file
            include_scenes: Include scene-by-scene breakdown
            include_summary: Include overall summary

        Returns:
            VLMAnalysis with full video understanding
        """
        await self.initialize()
        video_path = Path(video_path)

        # Get transcript first
        transcript = await self.transcribe(video_path)

        # Upload for analysis
        video_file = await self._upload_video(video_path)

        # Build analysis prompt
        prompt_parts = ["Analyze this video comprehensively.", ""]

        if include_scenes:
            prompt_parts.append(
                "SCENES: Describe each distinct scene with timestamps, objects, and actions."
            )

        if include_summary:
            prompt_parts.append("SUMMARY: Provide a brief summary of the video content.")

        prompt_parts.extend(
            [
                "",
                "OUTPUT FORMAT - JSON:",
                "{",
                '  "scenes": [{"start": 0.0, "end": 5.0, "description": "...", "objects": [...], "actions": [...], "mood": "..."}],',
                '  "summary": "overall summary",',
                '  "topics": ["topic1", "topic2"],',
                '  "people_count": number_of_people',
                "}",
            ]
        )

        response = self._client.models.generate_content(
            model=self._model, contents=[video_file, "\n".join(prompt_parts)]
        )

        # Parse response
        text = response.text
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        data = json.loads(text)

        scenes = [
            VLMScene(
                start=s["start"],
                end=s["end"],
                description=s.get("description", ""),
                objects=s.get("objects", []),
                actions=s.get("actions", []),
                mood=s.get("mood"),
            )
            for s in data.get("scenes", [])
        ]

        return VLMAnalysis(
            transcript=transcript,
            scenes=scenes,
            summary=data.get("summary", ""),
            topics=data.get("topics", []),
            people_count=data.get("people_count", 0),
            duration=transcript.duration,
        )


# Singleton instance
_vlm_instance: GeminiVLM | None = None


def get_vlm(config: VLMConfig | None = None) -> GeminiVLM:
    """Get or create VLM instance.

    Args:
        config: Optional configuration (only used on first call)

    Returns:
        GeminiVLM instance
    """
    global _vlm_instance
    if _vlm_instance is None:
        _vlm_instance = GeminiVLM(config)
    return _vlm_instance


async def transcribe_video(
    video_path: Path | str,
    config: VLMConfig | None = None,
) -> VLMTranscript:
    """Transcribe video using Gemini VLM.

    Convenience function for quick transcription.

    Args:
        video_path: Path to video file
        config: Optional VLM configuration

    Returns:
        VLMTranscript with word-level timing

    Example:
        transcript = await transcribe_video("family_video.mp4")
        print(transcript.full_text)
    """
    vlm = GeminiVLM(config) if config else get_vlm()
    return await vlm.transcribe(video_path)


async def analyze_video(
    video_path: Path | str,
    config: VLMConfig | None = None,
    include_scenes: bool = True,
) -> VLMAnalysis:
    """Analyze video using Gemini VLM.

    Args:
        video_path: Path to video file
        config: Optional VLM configuration
        include_scenes: Include scene breakdown

    Returns:
        VLMAnalysis with full video understanding
    """
    vlm = GeminiVLM(config) if config else get_vlm()
    return await vlm.analyze(video_path, include_scenes=include_scenes)
