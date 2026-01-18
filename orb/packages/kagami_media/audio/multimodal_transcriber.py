"""Multimodal Video Transcription using Gemini 3 Flash.

State-of-the-art transcription that uses BOTH audio AND visual (lip reading)
for maximum accuracy on degraded home video footage.

Gemini 3 Flash (Dec 2025) provides:
- Native multimodal understanding (audio + video together)
- 1M+ token context (handles 2+ hours of video)
- Speaker diarization from visual + audio cues
- Emotion detection
- Timestamp alignment

This is superior to audio-only transcription for:
- Noisy VHS recordings
- Multiple overlapping speakers
- Degraded audio quality
- Identifying WHO is speaking via face matching

Usage:
    transcriber = MultimodalTranscriber()
    result = transcriber.transcribe_video("video.mp4")

    for segment in result.segments:
        print(f"[{segment.timestamp}] {segment.speaker}: {segment.text}")
"""

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

# Try to import Google GenAI
try:
    import google.generativeai as genai

    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

# Fallback imports
try:
    from faster_whisper import WhisperModel

    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False


@dataclass
class TranscriptSegment:
    """A single segment of transcribed speech."""

    start_seconds: float
    end_seconds: float
    speaker: str  # Speaker label or description
    text: str
    confidence: float = 0.0

    # Visual context
    speaker_description: str = ""  # e.g., "child in red shirt"
    emotion: str = ""  # e.g., "excited", "calm"

    # Word-level timing (if available)
    words: list[dict] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        return self.end_seconds - self.start_seconds

    @property
    def timestamp(self) -> str:
        """Format as MM:SS."""
        m, s = divmod(int(self.start_seconds), 60)
        return f"{m:02d}:{s:02d}"

    @property
    def timestamp_range(self) -> str:
        """Format as MM:SS - MM:SS."""
        start_m, start_s = divmod(int(self.start_seconds), 60)
        end_m, end_s = divmod(int(self.end_seconds), 60)
        return f"{start_m:02d}:{start_s:02d} - {end_m:02d}:{end_s:02d}"

    def to_dict(self) -> dict:
        return {
            "start_seconds": self.start_seconds,
            "end_seconds": self.end_seconds,
            "duration_seconds": self.duration_seconds,
            "timestamp": self.timestamp,
            "speaker": self.speaker,
            "speaker_description": self.speaker_description,
            "text": self.text,
            "emotion": self.emotion,
            "confidence": self.confidence,
            "word_count": len(self.words),
        }

    def to_srt(self, index: int) -> str:
        """Format as SRT subtitle entry."""
        start_h, start_rem = divmod(self.start_seconds, 3600)
        start_m, start_s = divmod(start_rem, 60)
        start_ms = int((start_s % 1) * 1000)

        end_h, end_rem = divmod(self.end_seconds, 3600)
        end_m, end_s = divmod(end_rem, 60)
        end_ms = int((end_s % 1) * 1000)

        return (
            f"{index}\n"
            f"{int(start_h):02d}:{int(start_m):02d}:{int(start_s):02d},{start_ms:03d} --> "
            f"{int(end_h):02d}:{int(end_m):02d}:{int(end_s):02d},{end_ms:03d}\n"
            f"[{self.speaker}] {self.text}\n\n"
        )


@dataclass
class TranscriptionResult:
    """Complete transcription result for a video."""

    source_file: str
    duration_seconds: float
    segments: list[TranscriptSegment] = field(default_factory=list)

    # Metadata
    model_used: str = ""
    processing_time_seconds: float = 0.0

    # Detected speakers
    speakers: list[dict] = field(default_factory=list)  # [{id, description, total_time}]

    @property
    def speaker_count(self) -> int:
        return len({s.speaker for s in self.segments})

    @property
    def full_transcript(self) -> str:
        """Get full transcript as plain text."""
        return "\n".join(f"[{s.timestamp}] {s.speaker}: {s.text}" for s in self.segments)

    @property
    def full_text(self) -> str:
        """Get just the text without timestamps."""
        return " ".join(s.text for s in self.segments)

    def get_speaker_segments(self, speaker: str) -> list[TranscriptSegment]:
        return [s for s in self.segments if s.speaker == speaker]

    def get_speaker_text(self, speaker: str) -> str:
        return " ".join(s.text for s in self.get_speaker_segments(speaker))

    def to_dict(self) -> dict:
        return {
            "source_file": self.source_file,
            "duration_seconds": self.duration_seconds,
            "model_used": self.model_used,
            "processing_time_seconds": self.processing_time_seconds,
            "speaker_count": self.speaker_count,
            "speakers": self.speakers,
            "segment_count": len(self.segments),
            "segments": [s.to_dict() for s in self.segments],
            "full_transcript": self.full_transcript,
        }

    def to_srt(self) -> str:
        """Export as SRT subtitle file content."""
        return "".join(s.to_srt(i + 1) for i, s in enumerate(self.segments))

    def save_srt(self, output_path: str):
        """Save transcript as SRT subtitle file."""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(self.to_srt())

    def save_json(self, output_path: str):
        """Save transcript as JSON."""
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)


class MultimodalTranscriber:
    """State-of-the-art multimodal video transcription.

    Uses Gemini 3 Flash for combined audio + visual transcription.
    Falls back to Whisper for audio-only if Gemini unavailable.

    Gemini 3 Flash advantages:
    - Processes video natively (not just extracted audio)
    - Uses lip reading + audio together
    - Better speaker identification via visual cues
    - Handles noisy/degraded audio better
    - Context-aware transcription
    """

    # Model hierarchy (best to fallback)
    GEMINI_MODELS = [
        "gemini-3-flash",  # Latest (Dec 2025)
        "gemini-2.5-flash",  # Strong fallback
        "gemini-2.0-flash",  # Older but capable
    ]

    def __init__(
        self,
        google_api_key: str | None = None,
        model: str = "auto",  # "auto" selects best available
        thinking_level: str = "medium",  # minimal, low, medium, high
        media_resolution: str = "medium",  # low, medium, high, ultra_high
        enable_diarization: bool = True,
        enable_emotion: bool = True,
        whisper_model: str = "large-v3",  # Fallback
    ):
        """Initialize multimodal transcriber.

        Args:
            google_api_key: Google API key (or set GOOGLE_API_KEY env var)
            model: Gemini model to use, or "auto" for best available
            thinking_level: Amount of reasoning (affects quality vs speed)
            media_resolution: Video processing quality
            enable_diarization: Identify different speakers
            enable_emotion: Detect emotions in speech
            whisper_model: Fallback Whisper model if Gemini unavailable
        """
        self.api_key = google_api_key or os.environ.get("GOOGLE_API_KEY")
        self.model_name = model
        self.thinking_level = thinking_level
        self.media_resolution = media_resolution
        self.enable_diarization = enable_diarization
        self.enable_emotion = enable_emotion
        self.whisper_model = whisper_model

        self._gemini_model = None
        self._whisper = None
        self._init_models()

    def _init_models(self):
        """Initialize transcription models."""
        # Try Gemini first
        if GENAI_AVAILABLE and self.api_key:
            try:
                genai.configure(api_key=self.api_key)

                # Select model
                if self.model_name == "auto":
                    # Try models in order of preference
                    for model_name in self.GEMINI_MODELS:
                        try:
                            self._gemini_model = genai.GenerativeModel(model_name)
                            self.model_name = model_name
                            print(f"Using Gemini model: {model_name}")
                            break
                        except Exception:
                            continue
                else:
                    self._gemini_model = genai.GenerativeModel(self.model_name)

            except Exception as e:
                print(f"Gemini init failed: {e}")

        # Fallback to Whisper
        if self._gemini_model is None and WHISPER_AVAILABLE:
            try:
                self._whisper = WhisperModel(
                    self.whisper_model,
                    device="cpu",
                    compute_type="int8",
                )
                print(f"Using Whisper fallback: {self.whisper_model}")
            except Exception as e:
                print(f"Whisper init failed: {e}")

    def transcribe_video(
        self,
        video_path: str,
        output_dir: str | None = None,
        context: str = "",
        progress_callback: callable | None = None,
    ) -> TranscriptionResult:
        """Transcribe a video using multimodal AI.

        Args:
            video_path: Path to video file
            output_dir: Directory to save transcript files
            context: Additional context about the video
            progress_callback: Callback(stage, progress)

        Returns:
            TranscriptionResult with all transcribed segments
        """
        import time

        start_time = time.time()

        video_path = Path(video_path)
        duration = self._get_video_duration(video_path)

        if self._gemini_model is not None:
            # Use Gemini multimodal (BEST)
            result = self._transcribe_with_gemini(video_path, duration, context, progress_callback)
        elif self._whisper is not None:
            # Fallback to Whisper audio-only
            result = self._transcribe_with_whisper(video_path, duration, progress_callback)
        else:
            raise RuntimeError(
                "No transcription model available. Install google-generativeai or faster-whisper."
            )

        result.processing_time_seconds = time.time() - start_time

        # Save outputs if directory specified
        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)

            # Save transcript files
            result.save_json(str(output_path / "transcript.json"))
            result.save_srt(str(output_path / "transcript.srt"))

            # Save plain text
            with open(output_path / "transcript.txt", "w") as f:
                f.write(result.full_transcript)

        return result

    def _transcribe_with_gemini(
        self,
        video_path: Path,
        duration: float,
        context: str,
        progress_callback: callable | None,
    ) -> TranscriptionResult:
        """Transcribe using Gemini 3 multimodal model."""
        if progress_callback:
            progress_callback("uploading", 0.1)

        # Upload video to Gemini
        video_file = genai.upload_file(str(video_path))

        # Wait for processing
        import time

        while video_file.state.name == "PROCESSING":
            time.sleep(2)
            video_file = genai.get_file(video_file.name)

        if video_file.state.name != "ACTIVE":
            raise RuntimeError(f"Video processing failed: {video_file.state.name}")

        if progress_callback:
            progress_callback("transcribing", 0.3)

        # Build transcription prompt
        prompt = self._build_transcription_prompt(context)

        # Configure generation
        generation_config = {
            "response_mime_type": "application/json",
        }

        # Add thinking level if supported
        if hasattr(genai, "ThinkingConfig"):
            generation_config["thinking_config"] = {"thinking_level": self.thinking_level}

        # Generate transcription
        response = self._gemini_model.generate_content(
            [video_file, prompt],
            generation_config=generation_config,
        )

        if progress_callback:
            progress_callback("parsing", 0.9)

        # Parse response
        result = self._parse_gemini_response(response.text, video_path, duration)
        result.model_used = self.model_name

        # Clean up uploaded file
        try:
            genai.delete_file(video_file.name)
        except Exception:
            pass

        return result

    def _build_transcription_prompt(self, context: str) -> str:
        """Build the transcription prompt for Gemini."""
        base_prompt = """Transcribe all spoken dialogue in this video with precise timestamps.

OUTPUT FORMAT (JSON):
{
    "segments": [
        {
            "start_seconds": 0.0,
            "end_seconds": 5.2,
            "speaker": "Speaker 1",
            "speaker_description": "adult woman with brown hair",
            "text": "The transcribed text here",
            "emotion": "happy"
        }
    ],
    "speakers": [
        {
            "id": "Speaker 1",
            "description": "adult woman with brown hair, wearing blue shirt",
            "estimated_age": "30-40",
            "gender": "female"
        }
    ]
}

REQUIREMENTS:
1. Use timestamps in seconds (e.g., 12.5 for 12.5 seconds)
2. Identify different speakers by their visual appearance
3. Use consistent speaker labels throughout (Speaker 1, Speaker 2, etc.)
4. Include speaker descriptions based on what you see (clothing, appearance)
5. Detect emotions when clearly expressed
6. Transcribe ALL audible speech, including overlapping conversations
7. Handle background noise and unclear audio gracefully
8. Use visual cues (lip movements) to help with unclear audio

"""

        if self.enable_diarization:
            base_prompt += """
SPEAKER DIARIZATION:
- Identify each unique speaker by their visual appearance
- Match audio to the person whose lips are moving
- Note when multiple people speak simultaneously
"""

        if self.enable_emotion:
            base_prompt += """
EMOTION DETECTION:
- Detect emotions from both voice tone and facial expressions
- Use: happy, sad, excited, angry, surprised, neutral, confused, scared
"""

        if context:
            base_prompt += f"""
ADDITIONAL CONTEXT:
{context}
"""

        base_prompt += """
VIDEO CONTEXT:
This is a VHS home video from the late 1980s/early 1990s. The audio may be
degraded or noisy. Use visual cues (lip reading) to help transcribe unclear
audio. Focus on capturing the voices of family members, especially children.

Now transcribe the video:"""

        return base_prompt

    def _parse_gemini_response(
        self,
        response_text: str,
        video_path: Path,
        duration: float,
    ) -> TranscriptionResult:
        """Parse Gemini's JSON response into TranscriptionResult."""
        try:
            # Parse JSON response
            data = json.loads(response_text)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            import re

            json_match = re.search(r"\{[\s\S]*\}", response_text)
            if json_match:
                data = json.loads(json_match.group())
            else:
                # Create minimal result from raw text
                return TranscriptionResult(
                    source_file=str(video_path),
                    duration_seconds=duration,
                    segments=[
                        TranscriptSegment(
                            start_seconds=0,
                            end_seconds=duration,
                            speaker="Unknown",
                            text=response_text,
                        )
                    ],
                )

        # Build segments
        segments = []
        for seg_data in data.get("segments", []):
            segment = TranscriptSegment(
                start_seconds=float(seg_data.get("start_seconds", 0)),
                end_seconds=float(seg_data.get("end_seconds", 0)),
                speaker=seg_data.get("speaker", "Unknown"),
                speaker_description=seg_data.get("speaker_description", ""),
                text=seg_data.get("text", ""),
                emotion=seg_data.get("emotion", ""),
                confidence=float(seg_data.get("confidence", 0.8)),
            )
            segments.append(segment)

        # Build result
        result = TranscriptionResult(
            source_file=str(video_path),
            duration_seconds=duration,
            segments=segments,
            speakers=data.get("speakers", []),
        )

        return result

    def _transcribe_with_whisper(
        self,
        video_path: Path,
        duration: float,
        progress_callback: callable | None,
    ) -> TranscriptionResult:
        """Fallback transcription using Whisper (audio-only)."""
        if progress_callback:
            progress_callback("extracting_audio", 0.1)

        # Extract audio
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            audio_path = f.name

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            audio_path,
        ]
        subprocess.run(cmd, capture_output=True, check=True)

        if progress_callback:
            progress_callback("transcribing", 0.3)

        # Transcribe with Whisper
        segments_gen, _info = self._whisper.transcribe(
            audio_path,
            word_timestamps=True,
            language="en",
        )

        segments = []
        for seg in segments_gen:
            # Build word list
            words = []
            if hasattr(seg, "words") and seg.words:
                for word in seg.words:
                    words.append(
                        {
                            "word": word.word,
                            "start": word.start,
                            "end": word.end,
                            "confidence": word.probability,
                        }
                    )

            segment = TranscriptSegment(
                start_seconds=seg.start,
                end_seconds=seg.end,
                speaker="Speaker",  # Whisper doesn't do diarization
                text=seg.text.strip(),
                confidence=seg.avg_logprob if hasattr(seg, "avg_logprob") else 0.8,
                words=words,
            )
            segments.append(segment)

        # Clean up
        os.remove(audio_path)

        return TranscriptionResult(
            source_file=str(video_path),
            duration_seconds=duration,
            segments=segments,
            model_used=f"whisper-{self.whisper_model}",
        )

    def _get_video_duration(self, video_path: Path) -> float:
        """Get video duration in seconds."""
        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(result.stdout.strip())
        except Exception:
            return 0.0


def transcribe_video(
    video_path: str,
    output_dir: str | None = None,
    context: str = "",
) -> TranscriptionResult:
    """Convenience function for video transcription.

    Args:
        video_path: Path to video file
        output_dir: Optional output directory for transcript files
        context: Additional context about the video

    Returns:
        TranscriptionResult
    """
    transcriber = MultimodalTranscriber()
    return transcriber.transcribe_video(video_path, output_dir, context)
