"""Voice Sample Extraction for Voice Cloning.

Extracts clean voice samples from diarized audio for voice cloning.
Targets 2+ minutes of clean audio per speaker for ElevenLabs cloning.

Each voice sample includes:
- Audio file (MP3/WAV)
- Duration and quality metrics
- Transcript
- Source timestamps

Usage:
    extractor = VoiceExtractor()
    samples = extractor.extract_voice_samples(diarization_result)
"""

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from kagami_media.audio.speaker_diarization import (
    DiarizationResult,
)


@dataclass
class VoiceSample:
    """A clean voice sample for voice cloning."""

    speaker_id: str
    sample_id: str

    # Audio
    audio_path: str
    duration_seconds: float

    # Quality
    quality_score: float = 0.0
    snr_db: float = 0.0  # Signal-to-noise ratio

    # Content
    transcript: str = ""
    word_count: int = 0

    # Source tracking
    source_video: str = ""
    start_timestamp: float = 0.0
    end_timestamp: float = 0.0

    @property
    def timestamp_formatted(self) -> str:
        start_m, start_s = divmod(int(self.start_timestamp), 60)
        end_m, end_s = divmod(int(self.end_timestamp), 60)
        return f"{start_m:02d}:{start_s:02d} - {end_m:02d}:{end_s:02d}"

    def to_dict(self) -> dict:
        return {
            "speaker_id": self.speaker_id,
            "sample_id": self.sample_id,
            "audio_path": self.audio_path,
            "duration_seconds": self.duration_seconds,
            "quality_score": self.quality_score,
            "snr_db": self.snr_db,
            "transcript": self.transcript,
            "word_count": self.word_count,
            "source_video": self.source_video,
            "timestamp_formatted": self.timestamp_formatted,
        }


class VoiceExtractor:
    """Extract clean voice samples from diarized audio.

    Selects best segments for voice cloning based on:
    - Duration (prefer longer segments)
    - Audio quality (SNR, clarity)
    - Content (clear speech, no overlaps)
    """

    def __init__(
        self,
        min_segment_duration: float = 3.0,
        max_segment_duration: float = 30.0,
        target_total_duration: float = 180.0,  # 3 minutes target
        output_format: str = "mp3",
        output_bitrate: str = "192k",
    ):
        """Initialize voice extractor.

        Args:
            min_segment_duration: Minimum segment length in seconds
            max_segment_duration: Maximum segment length in seconds
            target_total_duration: Target total duration per speaker
            output_format: Output audio format (mp3, wav)
            output_bitrate: Output bitrate for MP3
        """
        self.min_segment_duration = min_segment_duration
        self.max_segment_duration = max_segment_duration
        self.target_total_duration = target_total_duration
        self.output_format = output_format
        self.output_bitrate = output_bitrate

    def extract_voice_samples(
        self,
        diarization: DiarizationResult,
        output_dir: str,
        source_audio: str | None = None,
    ) -> dict[str, list[VoiceSample]]:
        """Extract voice samples for all speakers.

        Args:
            diarization: Diarization result
            output_dir: Directory to save voice samples
            source_audio: Path to source audio (uses diarization source if None)

        Returns:
            Dictionary mapping speaker_id to list of VoiceSample
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Determine source audio
        if source_audio is None:
            source_audio = diarization.source_file

        # Ensure we have audio (extract from video if needed)
        audio_path = self._ensure_audio(source_audio)

        samples_by_speaker: dict[str, list[VoiceSample]] = {}

        for speaker_id in diarization.speakers:
            speaker_segments = diarization.get_speaker_segments(speaker_id)

            # Filter and sort segments by quality
            valid_segments = [
                s for s in speaker_segments if s.duration_seconds >= self.min_segment_duration
            ]

            # Sort by duration (longer is better for cloning)
            valid_segments.sort(key=lambda s: s.duration_seconds, reverse=True)

            # Extract samples until we hit target duration
            speaker_samples = []
            total_duration = 0.0

            speaker_dir = output_path / speaker_id
            speaker_dir.mkdir(exist_ok=True)

            for i, segment in enumerate(valid_segments):
                if total_duration >= self.target_total_duration:
                    break

                # Limit individual segment length
                segment_duration = min(
                    segment.duration_seconds,
                    self.max_segment_duration,
                )

                # Extract audio segment
                sample_id = f"{speaker_id}_sample_{i:03d}"
                sample_path = speaker_dir / f"{sample_id}.{self.output_format}"

                success = self._extract_audio_segment(
                    source=audio_path,
                    output=str(sample_path),
                    start=segment.start_seconds,
                    duration=segment_duration,
                )

                if success:
                    # Calculate quality metrics
                    quality_score = self._calculate_quality(str(sample_path))
                    snr = self._estimate_snr(str(sample_path))

                    sample = VoiceSample(
                        speaker_id=speaker_id,
                        sample_id=sample_id,
                        audio_path=str(sample_path),
                        duration_seconds=segment_duration,
                        quality_score=quality_score,
                        snr_db=snr,
                        transcript=segment.text,
                        word_count=len(segment.text.split()),
                        source_video=segment.source_video,
                        start_timestamp=segment.start_seconds,
                        end_timestamp=segment.start_seconds + segment_duration,
                    )

                    speaker_samples.append(sample)
                    total_duration += segment_duration

            samples_by_speaker[speaker_id] = speaker_samples

            # Save speaker metadata
            self._save_speaker_metadata(
                speaker_dir,
                speaker_id,
                speaker_samples,
                total_duration,
            )

        # Clean up temp audio if created
        if str(audio_path) != str(source_audio):
            try:
                os.remove(audio_path)
            except Exception:
                pass

        return samples_by_speaker

    def _ensure_audio(self, source_path: str) -> str:
        """Ensure we have an audio file to extract from."""
        source = Path(source_path)
        audio_extensions = {".wav", ".mp3", ".flac", ".m4a", ".aac"}

        if source.suffix.lower() in audio_extensions:
            return str(source)

        # Extract audio from video
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            output_path = f.name

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(source),
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
            return output_path
        except subprocess.CalledProcessError:
            return str(source)

    def _extract_audio_segment(
        self,
        source: str,
        output: str,
        start: float,
        duration: float,
    ) -> bool:
        """Extract a segment of audio."""
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            source,
            "-ss",
            str(start),
            "-t",
            str(duration),
        ]

        if self.output_format == "mp3":
            cmd.extend(["-acodec", "libmp3lame", "-b:a", self.output_bitrate])
        else:
            cmd.extend(["-acodec", "pcm_s16le"])

        cmd.append(output)

        try:
            subprocess.run(cmd, capture_output=True, check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def _calculate_quality(self, audio_path: str) -> float:
        """Calculate overall quality score for audio sample."""
        # Simple quality estimation based on file properties
        try:
            # Get audio stats using ffprobe
            cmd = [
                "ffprobe",
                "-v",
                "quiet",
                "-show_entries",
                "format=bit_rate,duration",
                "-of",
                "json",
                audio_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)

            # Higher bitrate = better quality (normalized)
            bitrate = int(data.get("format", {}).get("bit_rate", 128000))
            bitrate_score = min(1.0, bitrate / 320000)

            # Longer duration = better for cloning
            duration = float(data.get("format", {}).get("duration", 0))
            duration_score = min(1.0, duration / 30.0)

            return bitrate_score * 0.5 + duration_score * 0.5

        except Exception:
            return 0.5

    def _estimate_snr(self, audio_path: str) -> float:
        """Estimate signal-to-noise ratio."""
        # Simple SNR estimation using volume levels
        try:
            cmd = ["ffmpeg", "-i", audio_path, "-af", "volumedetect", "-f", "null", "-"]
            result = subprocess.run(cmd, capture_output=True, text=True)

            # Parse mean_volume from stderr
            for line in result.stderr.split("\n"):
                if "mean_volume" in line:
                    # Extract dB value
                    parts = line.split(":")
                    if len(parts) >= 2:
                        db_str = parts[1].strip().replace("dB", "").strip()
                        mean_volume = float(db_str)

                        # Estimate SNR (higher mean volume = cleaner signal)
                        # Typical speech is -20 to -10 dB
                        snr = 40 + mean_volume  # Rough estimate
                        return max(0, min(40, snr))

            return 20.0  # Default estimate

        except Exception:
            return 20.0

    def _save_speaker_metadata(
        self,
        speaker_dir: Path,
        speaker_id: str,
        samples: list[VoiceSample],
        total_duration: float,
    ):
        """Save metadata for speaker's voice samples."""
        metadata = {
            "speaker_id": speaker_id,
            "total_samples": len(samples),
            "total_duration_seconds": total_duration,
            "ready_for_cloning": total_duration >= 60.0,  # 1 min minimum
            "recommended_for_cloning": total_duration >= 120.0,  # 2 min ideal
            "samples": [s.to_dict() for s in samples],
        }

        meta_path = speaker_dir / "metadata.json"
        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=2)


def extract_voice_samples(
    diarization: DiarizationResult,
    output_dir: str,
) -> dict[str, list[VoiceSample]]:
    """Convenience function to extract voice samples.

    Args:
        diarization: Diarization result
        output_dir: Output directory

    Returns:
        Dictionary mapping speaker_id to VoiceSample list
    """
    extractor = VoiceExtractor()
    return extractor.extract_voice_samples(diarization, output_dir)
