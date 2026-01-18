"""Scene — A sequence of shots with transitions.

A Scene is a logical grouping of shots that form a coherent segment.
For example: an interview segment, a product demo, an intro sequence.
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kagami_studio.composition.shot import Shot, ShotResult, render_shot

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("/tmp/kagami_scenes")


@dataclass
class Scene:
    """A sequence of shots forming a coherent segment.

    Attributes:
        name: Scene identifier
        shots: Ordered list of shots
        transition: Default transition between shots
        transition_duration: Transition duration in seconds
        audio_bed: Background music/ambient for entire scene
    """

    name: str
    shots: list[Shot] = field(default_factory=list)
    transition: str = "cut"  # cut, fade, dissolve, wipe
    transition_duration: float = 0.5
    audio_bed: str | None = None

    def add_shot(self, shot: Shot) -> Scene:
        """Add a shot to the scene (fluent API)."""
        self.shots.append(shot)
        return self

    def add_dialogue(
        self,
        character: str,
        text: str,
        motion: str = "warm",
    ) -> Scene:
        """Add a dialogue shot (convenience method)."""
        from kagami_studio.composition.shot import ShotType

        self.shots.append(
            Shot(
                type=ShotType.DIALOGUE,
                character=character,
                text=text,
                motion=motion,
            )
        )
        return self

    def add_action(
        self,
        prompt: str,
        duration_s: float = 5.0,
        sfx: list[str] | None = None,
    ) -> Scene:
        """Add an action shot (convenience method)."""
        from kagami_studio.composition.shot import ShotType

        self.shots.append(
            Shot(
                type=ShotType.ACTION,
                action_prompt=prompt,
                duration_s=duration_s,
                sfx=sfx or [],
            )
        )
        return self

    @property
    def total_duration_s(self) -> float:
        """Estimated total duration in seconds."""
        shot_time = sum(s.duration_s for s in self.shots)
        transition_time = max(0, len(self.shots) - 1) * self.transition_duration
        return shot_time + transition_time

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "shots": [s.to_dict() for s in self.shots],
            "transition": self.transition,
            "transition_duration": self.transition_duration,
            "audio_bed": self.audio_bed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Scene:
        """Deserialize from dictionary."""
        return cls(
            name=data.get("name", "Untitled"),
            shots=[Shot.from_dict(s) for s in data.get("shots", [])],
            transition=data.get("transition", "cut"),
            transition_duration=data.get("transition_duration", 0.5),
            audio_bed=data.get("audio_bed"),
        )


@dataclass
class SceneResult:
    """Result of rendering a scene."""

    success: bool
    video_path: Path | None = None
    duration_s: float = 0.0
    render_time_s: float = 0.0
    shot_results: list[ShotResult] = field(default_factory=list)
    scene: Scene | None = None
    error: str | None = None


class SceneRenderer:
    """Renders scenes by composing shot videos.

    Audio pipeline:
    1. Each shot rendered with its own audio mix
    2. Scene concatenates shot videos
    3. Scene audio_bed mixed under concatenated audio
    4. Final video + audio output
    """

    def __init__(self):
        self._audio_renderer = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize renderer."""
        if self._initialized:
            return

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        # Initialize audio renderer
        from kagami_studio.composition.audio import get_audio_renderer

        self._audio_renderer = await get_audio_renderer()

        self._initialized = True

    async def render(
        self,
        scene: Scene,
        parallel: bool = True,
        output_path: Path | None = None,
    ) -> SceneResult:
        """Render a scene.

        Args:
            scene: Scene to render
            parallel: Render shots in parallel (faster)
            output_path: Output video path

        Returns:
            SceneResult with video path
        """
        if not self._initialized:
            await self.initialize()

        if not scene.shots:
            return SceneResult(success=False, error="Scene has no shots", scene=scene)

        start = time.perf_counter()

        try:
            # Render all shots
            if parallel:
                shot_results = await asyncio.gather(*[render_shot(shot) for shot in scene.shots])
            else:
                shot_results = []
                for shot in scene.shots:
                    result = await render_shot(shot)
                    shot_results.append(result)

            # Check for failures
            failed = [r for r in shot_results if not r.success]
            if failed:
                errors = ", ".join(r.error or "Unknown" for r in failed)
                return SceneResult(
                    success=False,
                    error=f"Shot failures: {errors}",
                    shot_results=shot_results,
                    scene=scene,
                    render_time_s=time.perf_counter() - start,
                )

            # Compose videos
            video_paths = [r.video_path for r in shot_results if r.video_path]

            if not video_paths:
                return SceneResult(
                    success=False,
                    error="No video paths from shots",
                    shot_results=shot_results,
                    scene=scene,
                )

            if output_path is None:
                output_path = OUTPUT_DIR / f"scene_{scene.name}_{int(time.time())}.mp4"

            # Compose with transitions
            if len(video_paths) == 1:
                # Single shot - just copy
                video_paths[0].rename(output_path)
            else:
                # Multiple shots - concatenate
                await self._compose_videos(
                    video_paths,
                    output_path,
                    scene.transition,
                    scene.transition_duration,
                )

            # Add audio bed if specified
            if scene.audio_bed:
                await self._add_audio_bed(output_path, scene.audio_bed)

            # Get final duration
            duration = self._get_video_duration(output_path)

            logger.info(f"✓ Scene '{scene.name}': {duration:.1f}s, {len(scene.shots)} shots")

            return SceneResult(
                success=True,
                video_path=output_path,
                duration_s=duration,
                render_time_s=time.perf_counter() - start,
                shot_results=shot_results,
                scene=scene,
            )

        except Exception as e:
            logger.error(f"Scene render failed: {e}")
            return SceneResult(
                success=False,
                error=str(e),
                scene=scene,
                render_time_s=time.perf_counter() - start,
            )

    async def _compose_videos(
        self,
        paths: list[Path],
        output: Path,
        transition: str,
        duration: float,
    ) -> None:
        """Compose multiple videos into one."""
        if transition == "cut":
            # Simple concatenation
            concat_file = OUTPUT_DIR / "concat.txt"
            concat_file.write_text("\n".join(f"file '{p}'" for p in paths))

            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(concat_file),
                    "-c:v",
                    "libx264",
                    "-preset",
                    "medium",
                    "-crf",
                    "20",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                    str(output),
                ],
                capture_output=True,
                check=True,
            )
        elif transition == "fade":
            # Crossfade transitions
            # This is complex - for now, fall back to cut
            await self._compose_videos(paths, output, "cut", duration)
        else:
            # Default to cut
            await self._compose_videos(paths, output, "cut", duration)

    async def _add_audio_bed(self, video_path: Path, audio_name: str) -> None:
        """Add background audio bed to video.

        Mixes the audio bed under the existing video audio with ducking.
        """
        if not self._audio_renderer:
            return

        # Resolve audio bed path
        audio_path = self._resolve_audio_bed(audio_name)
        if not audio_path:
            logger.warning(f"Audio bed not found: {audio_name}")
            return

        try:
            # Extract existing audio from video
            existing_audio = OUTPUT_DIR / f"existing_{int(time.time() * 1000)}.mp3"
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(video_path),
                    "-vn",
                    "-acodec",
                    "libmp3lame",
                    "-b:a",
                    "192k",
                    str(existing_audio),
                ],
                capture_output=True,
                check=True,
            )

            # Mix with audio bed
            audio_result = await self._audio_renderer.render_scene_audio(
                shot_audios=[existing_audio],
                music_bed=audio_path,
                music_volume=0.25,
            )

            if audio_result.success and audio_result.audio_path:
                # Replace audio in video
                await self._audio_renderer.combine_video_audio(
                    video_path,
                    audio_result.audio_path,
                    video_path,  # Overwrite
                )

        except Exception as e:
            logger.warning(f"Audio bed mixing failed: {e}")

    def _resolve_audio_bed(self, audio_name: str) -> Path | None:
        """Resolve audio bed name to file path."""
        audio_dirs = [
            Path("assets/audio/music"),
            Path("assets/audio/beds"),
            Path("assets/music"),
            Path("/tmp/kagami_music"),
        ]

        for audio_dir in audio_dirs:
            for ext in [".mp3", ".wav", ".ogg"]:
                path = audio_dir / f"{audio_name}{ext}"
                if path.exists():
                    return path

        return None

    @staticmethod
    def _get_video_duration(path: Path) -> float:
        """Get video duration in seconds."""
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


# Convenience function
_renderer: SceneRenderer | None = None


async def render_scene(
    scene: Scene,
    output_path: Path | None = None,
) -> SceneResult:
    """Render a scene (convenience function)."""
    global _renderer

    if _renderer is None:
        _renderer = SceneRenderer()
        await _renderer.initialize()

    return await _renderer.render(scene, output_path=output_path)


__all__ = [
    "Scene",
    "SceneRenderer",
    "SceneResult",
    "render_scene",
]
