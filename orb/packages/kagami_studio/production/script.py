"""Production Script — Script dataclasses and export functions.

This module contains the script representation for video productions:
- ScriptSlide: Individual slide with title, points, spoken text, shot type
- ProductionScript: Full script with metadata and export methods
- WordTiming: Word-level timing from TTS for subtitle sync

Export formats:
- Markdown (.md) — Human-readable production script
- PDF (.pdf) — Print-ready version via weasyprint

Usage:
    from kagami_studio.production.script import ProductionScript, ScriptSlide

    script = ProductionScript(
        title="Welcome Home",
        slides=[
            ScriptSlide(
                id="intro",
                title="Welcome",
                spoken_text="You walk through the door...",
                shot_type=ShotType.DIALOGUE,
            ),
        ],
        speaker="tim",
    )

    # Export
    script.export_markdown(Path("/tmp/script.md"))
    script.export_pdf(Path("/tmp/script.pdf"))
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kagami_studio.composition.shot import CameraAngle, ShotType

logger = logging.getLogger(__name__)


@dataclass
class WordTiming:
    """Word timing from TTS for subtitle synchronization.

    Attributes:
        text: The word text
        start_ms: Start time in milliseconds
        end_ms: End time in milliseconds
        slide_index: Which slide this word belongs to
    """

    text: str
    start_ms: int
    end_ms: int
    slide_index: int = 0


@dataclass
class ScriptSlide:
    """A single slide in the production script.

    Represents one unit of content with visual, audio, and timing info.

    Attributes:
        id: Unique identifier for the slide
        title: On-screen title (may be empty)
        points: Bullet points to display
        spoken_text: Text to be spoken (TTS)
        shot_type: Type of shot (dialogue, reverse, audience, etc.)
        camera: Camera angle/framing
        duration_s: Duration in seconds (auto-calculated from TTS if None)
        notes: Production notes (not shown on screen)
        mood: Emotional tone for TTS and avatar
    """

    id: str
    title: str = ""
    points: list[str] = field(default_factory=list)
    spoken_text: str = ""
    shot_type: ShotType = ShotType.DIALOGUE
    camera: CameraAngle = CameraAngle.MEDIUM
    duration_s: float | None = None  # Auto-calculated from TTS if None
    notes: str = ""
    mood: str = "neutral"

    @classmethod
    def from_dict(cls, data: dict[str, Any], index: int = 0) -> ScriptSlide:
        """Create ScriptSlide from dictionary.

        Args:
            data: Dictionary with slide data
            index: Slide index (used for auto-generated ID)

        Returns:
            ScriptSlide instance
        """
        shot_type = data.get("shot", "dialogue")
        if isinstance(shot_type, str):
            shot_type = ShotType(shot_type)

        camera = data.get("camera", "medium")
        if isinstance(camera, str):
            camera = CameraAngle(camera)

        return cls(
            id=data.get("id", f"slide_{index}"),
            title=data.get("title", ""),
            points=data.get("points", []),
            spoken_text=data.get("spoken", ""),
            shot_type=shot_type,
            camera=camera,
            duration_s=data.get("duration"),
            notes=data.get("notes", ""),
            mood=data.get("mood", "neutral"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "points": self.points,
            "spoken": self.spoken_text,
            "shot": self.shot_type.value,
            "camera": self.camera.value,
            "duration": self.duration_s,
            "notes": self.notes,
            "mood": self.mood,
        }


@dataclass
class ProductionScript:
    """Full production script with slides, timing, and metadata.

    This is the central data structure for video production.
    It holds all slides and can be exported to various formats.

    Attributes:
        title: Script title
        slides: List of ScriptSlide objects
        speaker: Default speaker character ID
        total_duration_s: Total duration in seconds (calculated)
        description: Optional script description
        created_at: ISO timestamp when created
    """

    title: str
    slides: list[ScriptSlide]
    speaker: str = "tim"
    total_duration_s: float = 0.0
    description: str = ""
    created_at: str = ""

    def __post_init__(self):
        """Calculate total duration after initialization."""
        if not self.total_duration_s:
            self.total_duration_s = sum(s.duration_s or 0.0 for s in self.slides)

    @classmethod
    def from_dict_list(
        cls,
        script: list[dict[str, Any]],
        speaker: str = "tim",
        title: str | None = None,
    ) -> ProductionScript:
        """Create ProductionScript from list of slide dictionaries.

        Args:
            script: List of slide dictionaries
            speaker: Default speaker character ID
            title: Optional title (defaults to first slide title)

        Returns:
            ProductionScript instance
        """
        slides = [ScriptSlide.from_dict(s, i) for i, s in enumerate(script)]

        return cls(
            title=title or (script[0].get("title", "Untitled") if script else "Untitled"),
            slides=slides,
            speaker=speaker,
        )

    def to_markdown(self) -> str:
        """Export script as Markdown.

        Returns:
            Markdown-formatted production script
        """
        lines = [
            f"# {self.title}",
            "",
            f"**Speaker:** {self.speaker}",
            f"**Total Duration:** {self.total_duration_s:.1f}s",
            f"**Slides:** {len(self.slides)}",
        ]

        if self.description:
            lines.extend(["", f"*{self.description}*"])

        lines.extend(["", "---", ""])

        for i, slide in enumerate(self.slides, 1):
            lines.append(f"## Slide {i}: {slide.title or '(No title)'}")
            lines.append("")
            lines.append(
                f"**Shot:** `{slide.shot_type.value}` | "
                f"**Camera:** `{slide.camera.value}` | "
                f"**Mood:** `{slide.mood}`"
            )
            lines.append(f"**Duration:** {slide.duration_s or 'auto'}s")

            if slide.points:
                lines.extend(["", "### Key Points:"])
                for point in slide.points:
                    lines.append(f"- {point}")

            if slide.spoken_text:
                lines.extend(["", "### Script:", "", f"> {slide.spoken_text}"])

            if slide.notes:
                lines.extend(["", f"*Notes: {slide.notes}*"])

            lines.extend(["", "---", ""])

        return "\n".join(lines)

    def export_markdown(self, path: Path) -> Path:
        """Export script to Markdown file.

        Args:
            path: Output file path

        Returns:
            Path to written file
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_markdown())
        logger.info(f"Exported Markdown: {path}")
        return path

    def export_pdf(self, path: Path) -> Path:
        """Export script to PDF file.

        Requires weasyprint. Falls back to Markdown if not available.

        Args:
            path: Output file path

        Returns:
            Path to written file
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            from weasyprint import HTML

            # Convert markdown to HTML
            html_content = self._to_html()
            HTML(string=html_content).write_pdf(str(path))
            logger.info(f"Exported PDF: {path}")
            return path

        except ImportError:
            logger.warning("weasyprint not installed, exporting Markdown instead")
            md_path = path.with_suffix(".md")
            return self.export_markdown(md_path)

    def _to_html(self) -> str:
        """Convert script to HTML for PDF export."""
        lines = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "<meta charset='utf-8'>",
            "<style>",
            "body { font-family: 'Helvetica Neue', Arial, sans-serif; "
            "max-width: 800px; margin: 40px auto; padding: 20px; }",
            "h1 { color: #1a1a2e; border-bottom: 2px solid #4a4a6a; padding-bottom: 10px; }",
            "h2 { color: #4a4a6a; margin-top: 30px; }",
            ".meta { color: #666; margin-bottom: 20px; }",
            ".slide { border-left: 3px solid #4a4a6a; padding-left: 20px; margin: 20px 0; }",
            ".slide-header { font-size: 0.9em; color: #888; }",
            "blockquote { background: #f5f5f5; padding: 15px; border-radius: 5px; "
            "font-style: italic; }",
            "ul { margin: 10px 0; }",
            ".notes { color: #888; font-style: italic; font-size: 0.9em; }",
            "hr { border: none; border-top: 1px solid #ddd; margin: 30px 0; }",
            "</style>",
            "</head>",
            "<body>",
            f"<h1>{self.title}</h1>",
            "<div class='meta'>",
            f"<p><strong>Speaker:</strong> {self.speaker}</p>",
            f"<p><strong>Duration:</strong> {self.total_duration_s:.1f}s</p>",
            f"<p><strong>Slides:</strong> {len(self.slides)}</p>",
            "</div>",
        ]

        if self.description:
            lines.append(f"<p><em>{self.description}</em></p>")

        lines.append("<hr>")

        for i, slide in enumerate(self.slides, 1):
            title = slide.title or "(No title)"
            lines.extend(
                [
                    "<div class='slide'>",
                    f"<h2>Slide {i}: {title}</h2>",
                    "<p class='slide-header'>",
                    f"<strong>Shot:</strong> {slide.shot_type.value} | ",
                    f"<strong>Camera:</strong> {slide.camera.value} | ",
                    f"<strong>Mood:</strong> {slide.mood} | ",
                    f"<strong>Duration:</strong> {slide.duration_s or 'auto'}s",
                    "</p>",
                ]
            )

            if slide.points:
                lines.append("<h3>Key Points:</h3>")
                lines.append("<ul>")
                for point in slide.points:
                    lines.append(f"<li>{point}</li>")
                lines.append("</ul>")

            if slide.spoken_text:
                lines.extend(
                    [
                        "<h3>Script:</h3>",
                        f"<blockquote>{slide.spoken_text}</blockquote>",
                    ]
                )

            if slide.notes:
                lines.append(f"<p class='notes'>Notes: {slide.notes}</p>")

            lines.append("</div>")

        lines.extend(["</body>", "</html>"])

        return "\n".join(lines)

    def to_json(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dictionary."""
        return {
            "title": self.title,
            "speaker": self.speaker,
            "total_duration_s": self.total_duration_s,
            "description": self.description,
            "created_at": self.created_at,
            "slides": [s.to_dict() for s in self.slides],
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> ProductionScript:
        """Deserialize from JSON dictionary."""
        slides = [ScriptSlide.from_dict(s, i) for i, s in enumerate(data.get("slides", []))]
        return cls(
            title=data.get("title", "Untitled"),
            slides=slides,
            speaker=data.get("speaker", "tim"),
            total_duration_s=data.get("total_duration_s", 0.0),
            description=data.get("description", ""),
            created_at=data.get("created_at", ""),
        )


def export_script_markdown(script: ProductionScript, path: Path) -> Path:
    """Export script to Markdown (convenience function)."""
    return script.export_markdown(path)


def export_script_pdf(script: ProductionScript, path: Path) -> Path:
    """Export script to PDF (convenience function)."""
    return script.export_pdf(path)


__all__ = [
    "ProductionScript",
    "ScriptSlide",
    "WordTiming",
    "export_script_markdown",
    "export_script_pdf",
]
