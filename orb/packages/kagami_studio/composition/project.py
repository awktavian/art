"""Project — Multi-scene production.

A Project is a complete production containing multiple scenes.
For example: a documentary, a course module, a podcast episode.
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from kagami_studio.composition.scene import Scene, SceneResult, render_scene

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("/tmp/kagami_projects")


@dataclass
class Project:
    """A complete multi-scene production.

    Attributes:
        name: Project name
        scenes: Ordered list of scenes
        intro: Optional intro scene
        outro: Optional outro scene
        music_track: Main music track
        resolution: Output resolution
        fps: Output frame rate
    """

    name: str
    scenes: list[Scene] = field(default_factory=list)
    intro: Scene | None = None
    outro: Scene | None = None
    music_track: str | None = None
    resolution: tuple[int, int] = (1920, 1080)
    fps: int = 30

    def add_scene(self, scene: Scene) -> Project:
        """Add a scene to the project (fluent API)."""
        self.scenes.append(scene)
        return self

    @property
    def all_scenes(self) -> list[Scene]:
        """Get all scenes in order (intro, main, outro)."""
        result = []
        if self.intro:
            result.append(self.intro)
        result.extend(self.scenes)
        if self.outro:
            result.append(self.outro)
        return result

    @property
    def total_duration_s(self) -> float:
        """Estimated total duration in seconds."""
        return sum(s.total_duration_s for s in self.all_scenes)

    def save(self, path: Path) -> None:
        """Save project to JSON file."""
        data = {
            "name": self.name,
            "scenes": [s.to_dict() for s in self.scenes],
            "intro": self.intro.to_dict() if self.intro else None,
            "outro": self.outro.to_dict() if self.outro else None,
            "music_track": self.music_track,
            "resolution": self.resolution,
            "fps": self.fps,
        }
        path.write_text(json.dumps(data, indent=2))

    @classmethod
    def load(cls, path: Path) -> Project:
        """Load project from JSON file."""
        data = json.loads(path.read_text())
        return cls(
            name=data.get("name", "Untitled"),
            scenes=[Scene.from_dict(s) for s in data.get("scenes", [])],
            intro=Scene.from_dict(data["intro"]) if data.get("intro") else None,
            outro=Scene.from_dict(data["outro"]) if data.get("outro") else None,
            music_track=data.get("music_track"),
            resolution=tuple(data.get("resolution", [1920, 1080])),
            fps=data.get("fps", 30),
        )


@dataclass
class ProjectResult:
    """Result of rendering a project."""

    success: bool
    video_path: Path | None = None
    duration_s: float = 0.0
    render_time_s: float = 0.0
    scene_results: list[SceneResult] = field(default_factory=list)
    project: Project | None = None
    error: str | None = None


async def render_project(
    project: Project,
    output_path: Path | None = None,
    parallel: bool = True,
) -> ProjectResult:
    """Render a complete project.

    Args:
        project: Project to render
        output_path: Output video path
        parallel: Render scenes in parallel

    Returns:
        ProjectResult with video path
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not project.all_scenes:
        return ProjectResult(success=False, error="Project has no scenes", project=project)

    start = time.perf_counter()

    try:
        # Render all scenes
        if parallel:
            scene_results = await asyncio.gather(
                *[render_scene(scene) for scene in project.all_scenes]
            )
        else:
            scene_results = []
            for scene in project.all_scenes:
                result = await render_scene(scene)
                scene_results.append(result)

        # Check for failures
        failed = [r for r in scene_results if not r.success]
        if failed:
            errors = ", ".join(r.error or "Unknown" for r in failed)
            return ProjectResult(
                success=False,
                error=f"Scene failures: {errors}",
                scene_results=scene_results,
                project=project,
                render_time_s=time.perf_counter() - start,
            )

        # Compose scenes
        video_paths = [r.video_path for r in scene_results if r.video_path]

        if output_path is None:
            output_path = OUTPUT_DIR / f"{project.name}_{int(time.time())}.mp4"

        if len(video_paths) == 1:
            video_paths[0].rename(output_path)
        else:
            # Concatenate all scene videos
            concat_file = OUTPUT_DIR / "project_concat.txt"
            concat_file.write_text("\n".join(f"file '{p}'" for p in video_paths))

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
                    str(output_path),
                ],
                capture_output=True,
                check=True,
            )

        # Add master music track if specified
        if project.music_track:
            # Would mix in music here
            pass

        # Get final duration
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "csv=p=0",
                str(output_path),
            ],
            capture_output=True,
            text=True,
        )
        duration = float(result.stdout.strip()) if result.stdout.strip() else 0.0

        logger.info(
            f"✓ Project '{project.name}': {duration:.1f}s, "
            f"{len(project.all_scenes)} scenes, "
            f"{sum(len(s.shots) for s in project.all_scenes)} shots"
        )

        return ProjectResult(
            success=True,
            video_path=output_path,
            duration_s=duration,
            render_time_s=time.perf_counter() - start,
            scene_results=scene_results,
            project=project,
        )

    except Exception as e:
        logger.error(f"Project render failed: {e}")
        return ProjectResult(
            success=False,
            error=str(e),
            project=project,
            render_time_s=time.perf_counter() - start,
        )


__all__ = [
    "Project",
    "ProjectResult",
    "render_project",
]
