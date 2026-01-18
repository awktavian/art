"""Composition Audio — Unified audio rendering for shot/scene/project.

This is THE audio pipeline for video production:
1. Voice (TTS from CharacterVoice)
2. SFX (sound effects)
3. Music (background track)
4. Ambient (environmental sounds)

Flow:
    Shot → voice audio + sfx/music/ambient
      → AudioRenderer.render_shot_audio()
      → Mixed audio file

    Scene → shot audios + scene music_bed
      → AudioRenderer.render_scene_audio()
      → Mixed audio with ducking

The AudioMixer handles multi-track mixing.
The AudioDucker handles voice-over-music ducking.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(tempfile.gettempdir()) / "kagami_audio"


@dataclass
class AudioTrack:
    """An audio track for mixing."""

    name: str
    path: Path | None = None
    data: np.ndarray | None = None
    volume: float = 1.0
    pan: float = 0.0  # -1.0 (left) to 1.0 (right)
    start_time: float = 0.0  # seconds offset
    duck_on_voice: bool = False  # Auto-duck when voice is present


@dataclass
class AudioRenderResult:
    """Result of audio rendering."""

    success: bool
    audio_path: Path | None = None
    duration_s: float = 0.0
    render_time_ms: float = 0.0
    tracks_mixed: int = 0
    error: str | None = None


class AudioRenderer:
    """Unified audio renderer for composition.

    Handles all audio mixing for shots, scenes, and projects:
    - Voice track (TTS output)
    - SFX tracks (sound effects)
    - Music track (background)
    - Ambient track (environment)

    Features:
    - Automatic ducking (music ducks under voice)
    - Volume normalization
    - Multi-track mixing
    - Format conversion
    """

    def __init__(
        self,
        sample_rate: int = 48000,
        channels: int = 2,
        duck_amount_db: float = -12.0,
    ):
        """Initialize renderer.

        Args:
            sample_rate: Output sample rate
            channels: Output channels (1=mono, 2=stereo)
            duck_amount_db: How much to duck music under voice
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.duck_amount_db = duck_amount_db
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the renderer."""
        if self._initialized:
            return

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self._initialized = True
        logger.info("✓ AudioRenderer initialized")

    async def render_shot_audio(
        self,
        voice_path: Path | None,
        sfx_paths: list[Path] | None = None,
        music_path: Path | None = None,
        ambient_path: Path | None = None,
        output_path: Path | None = None,
        voice_volume: float = 1.0,
        music_volume: float = 0.3,
        sfx_volume: float = 0.8,
        ambient_volume: float = 0.2,
    ) -> AudioRenderResult:
        """Render audio for a single shot.

        Args:
            voice_path: Voice/dialogue audio
            sfx_paths: Sound effect audio files
            music_path: Background music
            ambient_path: Ambient/environmental audio
            output_path: Output file path
            voice_volume: Voice track volume (0.0-2.0)
            music_volume: Music volume (0.0-2.0)
            sfx_volume: SFX volume (0.0-2.0)
            ambient_volume: Ambient volume (0.0-2.0)

        Returns:
            AudioRenderResult with mixed audio path
        """
        if not self._initialized:
            await self.initialize()

        start = time.perf_counter()

        # If only voice, return it directly
        if voice_path and not sfx_paths and not music_path and not ambient_path:
            return AudioRenderResult(
                success=True,
                audio_path=voice_path,
                duration_s=self._get_audio_duration(voice_path),
                render_time_ms=(time.perf_counter() - start) * 1000,
                tracks_mixed=1,
            )

        try:
            # Build ffmpeg filter for mixing
            inputs = []
            filters = []
            track_count = 0

            # Voice track (primary)
            if voice_path and voice_path.exists():
                inputs.extend(["-i", str(voice_path)])
                filters.append(f"[{track_count}:a]volume={voice_volume}[voice]")
                track_count += 1

            # Music track (ducked under voice)
            if music_path and music_path.exists():
                inputs.extend(["-i", str(music_path)])
                if voice_path:
                    # Duck music under voice using sidechain
                    filters.append(
                        f"[{track_count}:a]volume={music_volume},"
                        f"sidechaincompress=threshold=0.02:ratio=4:attack=50:release=300[music]"
                    )
                else:
                    filters.append(f"[{track_count}:a]volume={music_volume}[music]")
                track_count += 1

            # Ambient track
            if ambient_path and ambient_path.exists():
                inputs.extend(["-i", str(ambient_path)])
                filters.append(f"[{track_count}:a]volume={ambient_volume}[ambient]")
                track_count += 1

            # SFX tracks
            sfx_labels = []
            if sfx_paths:
                for i, sfx_path in enumerate(sfx_paths):
                    if sfx_path.exists():
                        inputs.extend(["-i", str(sfx_path)])
                        label = f"sfx{i}"
                        filters.append(f"[{track_count}:a]volume={sfx_volume}[{label}]")
                        sfx_labels.append(f"[{label}]")
                        track_count += 1

            if track_count == 0:
                return AudioRenderResult(success=False, error="No audio inputs")

            # Build mix filter
            mix_inputs = []
            if voice_path and voice_path.exists():
                mix_inputs.append("[voice]")
            if music_path and music_path.exists():
                mix_inputs.append("[music]")
            if ambient_path and ambient_path.exists():
                mix_inputs.append("[ambient]")
            mix_inputs.extend(sfx_labels)

            if len(mix_inputs) > 1:
                filters.append(
                    f"{''.join(mix_inputs)}amix=inputs={len(mix_inputs)}:"
                    f"duration=longest:normalize=0[out]"
                )
                filter_out = "[out]"
            else:
                filter_out = mix_inputs[0] if mix_inputs else "[0:a]"

            # Output path
            if output_path is None:
                output_path = OUTPUT_DIR / f"shot_audio_{int(time.time() * 1000)}.mp3"

            # Build ffmpeg command
            cmd = ["ffmpeg", "-y"]
            cmd.extend(inputs)

            if filters:
                cmd.extend(["-filter_complex", ";".join(filters)])
                if len(mix_inputs) > 1:
                    cmd.extend(["-map", filter_out])

            cmd.extend(
                [
                    "-ar",
                    str(self.sample_rate),
                    "-ac",
                    str(self.channels),
                    "-b:a",
                    "192k",
                    str(output_path),
                ]
            )

            # Run ffmpeg
            result = subprocess.run(cmd, capture_output=True)

            if result.returncode != 0:
                error = result.stderr.decode()[:500]
                logger.error(f"Audio mix failed: {error}")
                # Fallback: just use voice
                if voice_path and voice_path.exists():
                    return AudioRenderResult(
                        success=True,
                        audio_path=voice_path,
                        duration_s=self._get_audio_duration(voice_path),
                        render_time_ms=(time.perf_counter() - start) * 1000,
                        tracks_mixed=1,
                    )
                return AudioRenderResult(success=False, error=error)

            duration = self._get_audio_duration(output_path)
            render_ms = (time.perf_counter() - start) * 1000

            logger.info(f"🎵 Mixed {track_count} tracks → {duration:.1f}s ({render_ms:.0f}ms)")

            return AudioRenderResult(
                success=True,
                audio_path=output_path,
                duration_s=duration,
                render_time_ms=render_ms,
                tracks_mixed=track_count,
            )

        except Exception as e:
            logger.error(f"Audio render failed: {e}")
            return AudioRenderResult(
                success=False,
                error=str(e),
                render_time_ms=(time.perf_counter() - start) * 1000,
            )

    async def render_scene_audio(
        self,
        shot_audios: list[Path],
        music_bed: Path | None = None,
        output_path: Path | None = None,
        music_volume: float = 0.25,
        crossfade_s: float = 0.0,
    ) -> AudioRenderResult:
        """Render audio for a scene (concatenate shot audios with music bed).

        Args:
            shot_audios: List of shot audio files
            music_bed: Background music for entire scene
            output_path: Output file path
            music_volume: Music volume (ducked under dialogue)
            crossfade_s: Crossfade duration between shots

        Returns:
            AudioRenderResult with scene audio
        """
        if not self._initialized:
            await self.initialize()

        start = time.perf_counter()

        if not shot_audios:
            return AudioRenderResult(success=False, error="No shot audios")

        try:
            # Concatenate shot audios
            concat_path = OUTPUT_DIR / f"concat_{int(time.time() * 1000)}.mp3"

            if len(shot_audios) == 1:
                # Single shot
                concat_path = shot_audios[0]
            else:
                # Multiple shots - concatenate
                concat_file = OUTPUT_DIR / "audio_concat.txt"
                concat_file.write_text("\n".join(f"file '{p}'" for p in shot_audios if p.exists()))

                cmd = [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(concat_file),
                    "-c:a",
                    "libmp3lame",
                    "-b:a",
                    "192k",
                    str(concat_path),
                ]
                subprocess.run(cmd, capture_output=True, check=True)

            # Add music bed if specified
            if music_bed and music_bed.exists():
                if output_path is None:
                    output_path = OUTPUT_DIR / f"scene_audio_{int(time.time() * 1000)}.mp3"

                # Get concat duration
                duration = self._get_audio_duration(concat_path)

                # Mix with music (ducked under dialogue)
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(concat_path),
                    "-stream_loop",
                    "-1",  # Loop music
                    "-i",
                    str(music_bed),
                    "-filter_complex",
                    f"[1:a]volume={music_volume}[music];"
                    f"[0:a][music]amix=inputs=2:duration=first:normalize=0",
                    "-t",
                    str(duration),
                    "-ar",
                    str(self.sample_rate),
                    "-b:a",
                    "192k",
                    str(output_path),
                ]
                subprocess.run(cmd, capture_output=True, check=True)

                final_path = output_path
            else:
                final_path = concat_path
                if output_path:
                    final_path.rename(output_path)
                    final_path = output_path

            duration = self._get_audio_duration(final_path)
            render_ms = (time.perf_counter() - start) * 1000

            logger.info(f"🎵 Scene audio: {len(shot_audios)} shots → {duration:.1f}s")

            return AudioRenderResult(
                success=True,
                audio_path=final_path,
                duration_s=duration,
                render_time_ms=render_ms,
                tracks_mixed=len(shot_audios) + (1 if music_bed else 0),
            )

        except Exception as e:
            logger.error(f"Scene audio render failed: {e}")
            return AudioRenderResult(
                success=False,
                error=str(e),
                render_time_ms=(time.perf_counter() - start) * 1000,
            )

    async def combine_video_audio(
        self,
        video_path: Path,
        audio_path: Path,
        output_path: Path | None = None,
    ) -> Path | None:
        """Combine video with rendered audio.

        Args:
            video_path: Video file
            audio_path: Audio file
            output_path: Output path (default: replace video audio)

        Returns:
            Output path or None if failed
        """
        if not video_path.exists() or not audio_path.exists():
            return None

        if output_path is None:
            output_path = video_path.with_suffix(".final.mp4")

        try:
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                str(video_path),
                "-i",
                str(audio_path),
                "-c:v",
                "copy",
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-shortest",
                str(output_path),
            ]
            subprocess.run(cmd, capture_output=True, check=True)
            return output_path

        except Exception as e:
            logger.error(f"Video+audio combine failed: {e}")
            return None

    @staticmethod
    def _get_audio_duration(path: Path) -> float:
        """Get audio duration in seconds."""
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "csv=p=0",
                str(path),
            ],
            capture_output=True,
            text=True,
        )
        return float(result.stdout.strip()) if result.stdout.strip() else 0.0


# Singleton
_audio_renderer: AudioRenderer | None = None


async def get_audio_renderer() -> AudioRenderer:
    """Get the singleton AudioRenderer."""
    global _audio_renderer

    if _audio_renderer is None:
        _audio_renderer = AudioRenderer()
        await _audio_renderer.initialize()

    return _audio_renderer


__all__ = [
    "AudioRenderResult",
    "AudioRenderer",
    "AudioTrack",
    "get_audio_renderer",
]
