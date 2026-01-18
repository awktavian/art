"""Speaker Diarization - Who Spoke When.

Uses PyAnnote for speaker diarization and Faster-Whisper for transcription.
Identifies speaker segments and matches them to tracked people.

Each speaker segment includes:
- Start/end timestamps
- Speaker ID
- Transcribed text
- Confidence score
- Speaker embedding

Usage:
    diarizer = SpeakerDiarizer()
    result = diarizer.diarize("video.mp4")

    for segment in result.segments:
        print(f"Speaker {segment.speaker_id}: {segment.text}")
"""

import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

# Try to import audio processing libraries
try:
    from pyannote.audio import Pipeline
    from pyannote.audio.pipelines.utils.hook import ProgressHook

    PYANNOTE_AVAILABLE = True
except ImportError:
    PYANNOTE_AVAILABLE = False

try:
    from faster_whisper import WhisperModel

    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

try:
    import torch
    import torchaudio

    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


@dataclass
class SpeakerSegment:
    """A segment of speech from a single speaker."""

    speaker_id: str
    start_seconds: float
    end_seconds: float

    # Transcription
    text: str = ""
    words: list[dict] = field(default_factory=list)  # [{word, start, end, confidence}]

    # Quality
    confidence: float = 0.0

    # Source tracking
    source_video: str = ""
    source_audio: str = ""

    @property
    def duration_seconds(self) -> float:
        return self.end_seconds - self.start_seconds

    @property
    def timestamp_formatted(self) -> str:
        """Format as MM:SS - MM:SS."""
        start_m, start_s = divmod(int(self.start_seconds), 60)
        end_m, end_s = divmod(int(self.end_seconds), 60)
        return f"{start_m:02d}:{start_s:02d} - {end_m:02d}:{end_s:02d}"

    def to_dict(self) -> dict:
        return {
            "speaker_id": self.speaker_id,
            "start_seconds": self.start_seconds,
            "end_seconds": self.end_seconds,
            "duration_seconds": self.duration_seconds,
            "timestamp_formatted": self.timestamp_formatted,
            "text": self.text,
            "word_count": len(self.words),
            "confidence": self.confidence,
            "source_video": self.source_video,
        }


@dataclass
class DiarizationResult:
    """Complete diarization result for an audio/video file."""

    source_file: str
    duration_seconds: float

    segments: list[SpeakerSegment] = field(default_factory=list)
    speaker_embeddings: dict[str, np.ndarray] = field(default_factory=dict)

    @property
    def speaker_count(self) -> int:
        return len({s.speaker_id for s in self.segments})

    @property
    def speakers(self) -> list[str]:
        return list({s.speaker_id for s in self.segments})

    def get_speaker_segments(self, speaker_id: str) -> list[SpeakerSegment]:
        return [s for s in self.segments if s.speaker_id == speaker_id]

    def get_speaker_total_duration(self, speaker_id: str) -> float:
        return sum(s.duration_seconds for s in self.get_speaker_segments(speaker_id))

    def get_speaker_text(self, speaker_id: str) -> str:
        return " ".join(s.text for s in self.get_speaker_segments(speaker_id))

    def to_dict(self) -> dict:
        return {
            "source_file": self.source_file,
            "duration_seconds": self.duration_seconds,
            "speaker_count": self.speaker_count,
            "speakers": self.speakers,
            "segments": [s.to_dict() for s in self.segments],
            "speaker_durations": {sp: self.get_speaker_total_duration(sp) for sp in self.speakers},
        }


class SpeakerDiarizer:
    """Speaker diarization using PyAnnote and Whisper.

    Identifies who is speaking when in audio/video files.
    """

    def __init__(
        self,
        whisper_model: str = "base",
        device: str = "cpu",
        hf_token: str | None = None,
    ):
        """Initialize speaker diarizer.

        Args:
            whisper_model: Whisper model size (tiny, base, small, medium, large)
            device: 'cpu' or 'cuda'
            hf_token: HuggingFace token for PyAnnote models
        """
        self.whisper_model_name = whisper_model
        self.device = device
        self.hf_token = hf_token

        self._whisper = None
        self._diarization_pipeline = None
        self._init_models()

    def _init_models(self):
        """Initialize Whisper and PyAnnote models."""
        # Initialize Whisper
        if WHISPER_AVAILABLE:
            try:
                compute_type = "int8" if self.device == "cpu" else "float16"
                self._whisper = WhisperModel(
                    self.whisper_model_name,
                    device=self.device,
                    compute_type=compute_type,
                )
            except Exception as e:
                print(f"Whisper init failed: {e}")

        # Initialize PyAnnote (requires HuggingFace token)
        if PYANNOTE_AVAILABLE and self.hf_token:
            try:
                self._diarization_pipeline = Pipeline.from_pretrained(
                    "pyannote/speaker-diarization-3.1",
                    use_auth_token=self.hf_token,
                )
                if self.device == "cuda" and torch.cuda.is_available():
                    self._diarization_pipeline.to(torch.device("cuda"))
            except Exception as e:
                print(f"PyAnnote init failed: {e}")

    def diarize(
        self,
        input_path: str,
        progress_callback: callable | None = None,
    ) -> DiarizationResult:
        """Perform speaker diarization on audio or video file.

        Args:
            input_path: Path to audio or video file
            progress_callback: Optional progress callback

        Returns:
            DiarizationResult with speaker segments
        """
        input_path = Path(input_path)

        # Extract audio if video file
        audio_path = self._ensure_audio(input_path)

        # Get audio duration
        duration = self._get_audio_duration(audio_path)

        # Perform diarization
        if self._diarization_pipeline is not None:
            diarization_segments = self._run_pyannote_diarization(audio_path)
        else:
            # Fallback: treat entire audio as single speaker
            diarization_segments = [("SPEAKER_00", 0.0, duration)]

        # Transcribe with Whisper
        segments = []
        for speaker_id, start, end in diarization_segments:
            # Extract segment audio
            segment_text, words = self._transcribe_segment(audio_path, start, end)

            segment = SpeakerSegment(
                speaker_id=speaker_id,
                start_seconds=start,
                end_seconds=end,
                text=segment_text,
                words=words,
                confidence=0.8,  # Default confidence
                source_video=input_path.name,
                source_audio=str(audio_path),
            )
            segments.append(segment)

        # Clean up temp audio if created
        if str(audio_path) != str(input_path):
            try:
                os.remove(audio_path)
            except Exception:
                pass

        return DiarizationResult(
            source_file=str(input_path),
            duration_seconds=duration,
            segments=segments,
        )

    def _ensure_audio(self, input_path: Path) -> Path:
        """Extract audio from video if needed."""
        audio_extensions = {".wav", ".mp3", ".flac", ".m4a", ".aac"}

        if input_path.suffix.lower() in audio_extensions:
            return input_path

        # Extract audio using ffmpeg
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            output_path = f.name

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            output_path,
        ]

        try:
            subprocess.run(cmd, capture_output=True, check=True)
            return Path(output_path)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Audio extraction failed: {e}") from e

    def _get_audio_duration(self, audio_path: Path) -> float:
        """Get audio duration in seconds."""
        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(result.stdout.strip())
        except Exception:
            return 0.0

    def _run_pyannote_diarization(
        self,
        audio_path: Path,
    ) -> list[tuple[str, float, float]]:
        """Run PyAnnote speaker diarization.

        Returns list of (speaker_id, start, end) tuples.
        """
        if self._diarization_pipeline is None:
            return []

        try:
            diarization = self._diarization_pipeline(str(audio_path))

            segments = []
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                segments.append((speaker, turn.start, turn.end))

            return segments

        except Exception as e:
            print(f"Diarization failed: {e}")
            return []

    def _transcribe_segment(
        self,
        audio_path: Path,
        start: float,
        end: float,
    ) -> tuple[str, list[dict]]:
        """Transcribe a segment of audio.

        Returns (text, words) tuple.
        """
        if self._whisper is None:
            return ("", [])

        try:
            # Extract segment
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                segment_path = f.name

            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                str(audio_path),
                "-ss",
                str(start),
                "-t",
                str(end - start),
                "-acodec",
                "pcm_s16le",
                "-ar",
                "16000",
                "-ac",
                "1",
                segment_path,
            ]
            subprocess.run(cmd, capture_output=True, check=True)

            # Transcribe
            segments, _info = self._whisper.transcribe(
                segment_path,
                word_timestamps=True,
            )

            # Collect results
            text_parts = []
            words = []

            for segment in segments:
                text_parts.append(segment.text)

                if hasattr(segment, "words") and segment.words:
                    for word in segment.words:
                        words.append(
                            {
                                "word": word.word,
                                "start": start + word.start,
                                "end": start + word.end,
                                "confidence": word.probability,
                            }
                        )

            # Clean up
            os.remove(segment_path)

            return (" ".join(text_parts).strip(), words)

        except Exception as e:
            print(f"Transcription failed: {e}")
            return ("", [])


def diarize_audio(
    input_path: str,
    whisper_model: str = "base",
) -> DiarizationResult:
    """Convenience function for speaker diarization.

    Args:
        input_path: Path to audio or video file
        whisper_model: Whisper model size

    Returns:
        DiarizationResult
    """
    diarizer = SpeakerDiarizer(whisper_model=whisper_model)
    return diarizer.diarize(input_path)
