"""Composite Engine — Core video composition system.

Handles all offline video compositing operations:
- Template-based layouts (PIP, split, documentary)
- Adaptive masking with SAM2
- Chromakey processing
- Audio mixing
- Web artifact generation

This is the central orchestrator for compositing operations.
For real-time OBS compositing, see kagami_studio.obs.compositing.
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path

logger = logging.getLogger(__name__)


class CompositeTemplate(Enum):
    """Available composition templates."""

    # Picture-in-picture variants
    PIP = auto()
    PIP_LARGE = auto()
    PIP_FLOATING = auto()

    # Split screen
    SPLIT = auto()
    SPLIT_DIAGONAL = auto()

    # Documentary styles
    DOCUMENTARY = auto()
    DOCUMENTARY_MINIMAL = auto()

    # Chromakey
    CHROMAKEY = auto()
    CHROMAKEY_DEPTH = auto()

    # Interview/podcast
    INTERVIEW = auto()
    PODCAST = auto()

    # Full frame
    FULL_FRAME = auto()
    DEPTH_COMPOSITE = auto()


class DepthLayer(Enum):
    """Depth layers for compositing."""

    BACKGROUND = 0
    MID_GROUND = 1
    FOREGROUND = 2
    OVERLAY = 3


@dataclass
class CompositeConfig:
    """Configuration for compositing operations."""

    # Output settings
    width: int = 1920
    height: int = 1080
    fps: int = 30
    video_codec: str = "libx264"
    video_preset: str = "medium"
    crf: int = 18
    audio_codec: str = "aac"
    audio_bitrate: str = "192k"

    # Processing
    use_gpu: bool = True
    threads: int = 0  # 0 = auto

    # Quality
    quality: str = "high"  # low, medium, high, ultra

    # Effects
    glassmorphism: bool = True
    glassmorphism_blur: int = 20
    border_width: int = 3
    border_color: str = "white"

    # Audio mixing
    background_volume: float = 0.7
    overlay_volume: float = 1.0
    ducking: bool = True


@dataclass
class CompositeResult:
    """Result of compositing operation."""

    success: bool
    output_path: Path | None = None
    web_artifact_path: Path | None = None
    duration: float = 0.0
    error: str | None = None
    metadata: dict = field(default_factory=dict)


class CompositeEngine:
    """Central video composition engine.

    Handles all offline compositing through FFmpeg,
    with support for templates, masking, and effects.

    Usage:
        engine = CompositeEngine()

        # Simple PIP
        result = await engine.composite(
            background="game.mp4",
            overlay="cam.mp4",
            output="output.mp4",
            template=CompositeTemplate.PIP,
        )

        # Documentary with transcript
        result = await engine.composite(
            background="interview.mp4",
            output="doc.mp4",
            template=CompositeTemplate.DOCUMENTARY,
            template_config={"transcript": transcript_data},
        )
    """

    def __init__(self, config: CompositeConfig | None = None):
        """Initialize engine.

        Args:
            config: Compositing configuration
        """
        self.config = config or CompositeConfig()

    async def composite(
        self,
        background: str | Path,
        output: str | Path,
        overlay: str | Path | None = None,
        template: CompositeTemplate = CompositeTemplate.PIP,
        template_config: dict | None = None,
    ) -> CompositeResult:
        """Create composite video.

        Args:
            background: Background video path
            output: Output path
            overlay: Overlay video (if applicable)
            template: Composition template
            template_config: Template-specific settings

        Returns:
            CompositeResult with output info
        """
        background = Path(background)
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)

        template_config = template_config or {}

        # Get video info
        bg_info = self._get_video_info(background)
        if not bg_info:
            return CompositeResult(success=False, error=f"Cannot read: {background}")

        ov_info = None
        if overlay:
            overlay = Path(overlay)
            ov_info = self._get_video_info(overlay)
            if not ov_info:
                return CompositeResult(success=False, error=f"Cannot read: {overlay}")

        # Build filter based on template
        try:
            filter_complex, audio_filter = self._build_filter(
                template=template,
                template_config=template_config,
                bg_info=bg_info,
                ov_info=ov_info,
            )
        except Exception as e:
            return CompositeResult(success=False, error=f"Filter build failed: {e}")

        # Build FFmpeg command
        cmd = self._build_ffmpeg_command(
            background=background,
            output=output,
            overlay=overlay,
            filter_complex=filter_complex,
            audio_filter=audio_filter,
            duration=min(
                bg_info.get("duration", 60),
                ov_info.get("duration", 60) if ov_info else 60,
            ),
        )

        # Execute
        try:
            result = await asyncio.to_thread(subprocess.run, cmd, capture_output=True, text=True)

            if result.returncode != 0:
                return CompositeResult(
                    success=False,
                    error=f"FFmpeg error: {result.stderr[-500:] if result.stderr else 'Unknown'}",
                )

            # Generate web artifact if documentary template
            web_artifact = None
            if template in (CompositeTemplate.DOCUMENTARY, CompositeTemplate.DOCUMENTARY_MINIMAL):
                web_artifact = await self._generate_web_artifact(
                    output=output,
                    template_config=template_config,
                )

            return CompositeResult(
                success=True,
                output_path=output,
                web_artifact_path=web_artifact,
                duration=bg_info.get("duration", 0),
                metadata={
                    "template": template.name,
                    "resolution": (self.config.width, self.config.height),
                },
            )

        except Exception as e:
            return CompositeResult(success=False, error=str(e))

    def _get_video_info(self, path: Path) -> dict | None:
        """Get video metadata."""
        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,duration,r_frame_rate",
            "-of",
            "json",
            str(path),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                return None

            data = json.loads(result.stdout)
            stream = data.get("streams", [{}])[0]
            return {
                "width": stream.get("width", 1920),
                "height": stream.get("height", 1080),
                "duration": float(stream.get("duration", 10)),
                "fps": eval(stream.get("r_frame_rate", "30/1")),
            }
        except Exception:
            return None

    def _build_filter(
        self,
        template: CompositeTemplate,
        template_config: dict,
        bg_info: dict,
        ov_info: dict | None,
    ) -> tuple[str, str]:
        """Build FFmpeg filter complex for template.

        Returns:
            (video_filter, audio_filter)
        """
        w, h = self.config.width, self.config.height

        if template == CompositeTemplate.PIP:
            return self._build_pip_filter(template_config, w, h)
        elif template == CompositeTemplate.SPLIT:
            return self._build_split_filter(template_config, w, h)
        elif template == CompositeTemplate.CHROMAKEY:
            return self._build_chromakey_filter(template_config, w, h)
        elif template in (CompositeTemplate.DOCUMENTARY, CompositeTemplate.DOCUMENTARY_MINIMAL):
            return self._build_documentary_filter(template_config, w, h)
        else:
            # Default: simple overlay
            return self._build_simple_overlay(template_config, w, h)

    def _build_pip_filter(self, config: dict, w: int, h: int) -> tuple[str, str]:
        """Build PIP (picture-in-picture) filter."""
        corner = config.get("corner", "bottom-right")
        scale = config.get("scale", 0.3)
        glassmorphism = config.get("glassmorphism", self.config.glassmorphism)
        margin = config.get("margin", 40)

        ov_w = int(w * scale)
        ov_h = int(h * scale)

        positions = {
            "top-left": (margin, margin),
            "top-right": (w - ov_w - margin, margin),
            "bottom-left": (margin, h - ov_h - margin),
            "bottom-right": (w - ov_w - margin, h - ov_h - margin),
        }
        ov_x, ov_y = positions.get(corner, positions["bottom-right"])

        if glassmorphism:
            glow = 20
            crop_x = max(0, ov_x - glow)
            crop_y = max(0, ov_y - glow)

            video = f"""
            [0:v]scale={w}:{h}[bg];
            [1:v]scale={ov_w}:{ov_h}[ov];
            [bg]crop={ov_w + glow * 2}:{ov_h + glow * 2}:{crop_x}:{crop_y},
               boxblur={self.config.glassmorphism_blur}:5,
               colorchannelmixer=rr=1.1:gg=1.1:bb=1.1:aa=0.85[blur];
            [bg][blur]overlay={crop_x}:{crop_y}[with_blur];
            [with_blur]drawbox=x={ov_x - self.config.border_width}:y={ov_y - self.config.border_width}:w={ov_w + self.config.border_width * 2}:h={ov_h + self.config.border_width * 2}:color={self.config.border_color}@0.6:t={self.config.border_width}[with_border];
            [with_border][ov]overlay={ov_x}:{ov_y}:shortest=1[vout]
            """
        else:
            video = f"""
            [0:v]scale={w}:{h}[bg];
            [1:v]scale={ov_w}:{ov_h}[ov];
            [bg][ov]overlay={ov_x}:{ov_y}:shortest=1[vout]
            """

        audio = self._build_audio_mix_filter()
        return video.strip().replace("\n", " "), audio

    def _build_split_filter(self, config: dict, w: int, h: int) -> tuple[str, str]:
        """Build split-screen filter."""
        ratio = config.get("ratio", 0.5)
        direction = config.get("direction", "vertical")
        gap = config.get("gap", 10)

        if direction == "vertical":
            left_w = int(w * ratio) - gap // 2
            video = f"""
            [0:v]scale={left_w}:{h}[left];
            [1:v]scale={w - left_w - gap}:{h}[right];
            color=black:{w}x{h}[base];
            [base][left]overlay=0:0[with_left];
            [with_left][right]overlay={left_w + gap}:0:shortest=1[vout]
            """
        else:
            top_h = int(h * ratio) - gap // 2
            video = f"""
            [0:v]scale={w}:{top_h}[top];
            [1:v]scale={w}:{h - top_h - gap}[bottom];
            color=black:{w}x{h}[base];
            [base][top]overlay=0:0[with_top];
            [with_top][bottom]overlay=0:{top_h + gap}:shortest=1[vout]
            """

        audio = self._build_audio_mix_filter()
        return video.strip().replace("\n", " "), audio

    def _build_chromakey_filter(self, config: dict, w: int, h: int) -> tuple[str, str]:
        """Build chromakey filter."""
        key_color = config.get("key_color", "green")
        position = config.get("position")
        scale = config.get("scale", 1.0)
        similarity = config.get("similarity", 0.3)
        blend = config.get("blend", 0.2)

        # Convert color name to hex
        colors = {
            "green": "0x00FF00",
            "blue": "0x0000FF",
            "magenta": "0xFF00FF",
        }
        color_hex = colors.get(key_color, key_color)

        ov_w = int(w * scale)
        ov_h = int(h * scale)

        if position:
            ov_x, ov_y = position
        else:
            ov_x = (w - ov_w) // 2
            ov_y = (h - ov_h) // 2

        video = f"""
        [0:v]scale={w}:{h}[bg];
        [1:v]colorkey={color_hex}:{similarity}:{blend},scale={ov_w}:{ov_h}[fg];
        [bg][fg]overlay={ov_x}:{ov_y}:shortest=1[vout]
        """

        audio = "[0:a]volume=1[aout]"  # Background only
        return video.strip().replace("\n", " "), audio

    def _build_documentary_filter(self, config: dict, w: int, h: int) -> tuple[str, str]:
        """Build documentary-style filter (DCC pattern).

        Video on left, space for text overlay on right.
        """
        video_ratio = config.get("video_ratio", 0.65)
        config.get("style", "dcc")

        video_w = int(w * video_ratio)

        # DCC style: gradient overlay, space for text
        video = f"""
        [0:v]scale={video_w}:{h}[video];
        color=0x0a0908:{w}x{h}[base];
        [base][video]overlay=0:0[with_video];
        [with_video]drawbox=x={video_w}:y=0:w={w - video_w}:h={h}:color=0x0a0908:t=fill[vout]
        """

        audio = "[0:a]volume=1[aout]"
        return video.strip().replace("\n", " "), audio

    def _build_simple_overlay(self, config: dict, w: int, h: int) -> tuple[str, str]:
        """Build simple overlay filter."""
        video = f"""
        [0:v]scale={w}:{h}[bg];
        [1:v]scale={w}:{h}[ov];
        [bg][ov]overlay=0:0:shortest=1[vout]
        """
        audio = self._build_audio_mix_filter()
        return video.strip().replace("\n", " "), audio

    def _build_audio_mix_filter(self) -> str:
        """Build audio mixing filter."""
        bg_vol = self.config.background_volume
        ov_vol = self.config.overlay_volume

        if self.config.ducking:
            bg_vol *= 0.6

        return f"""
        [0:a]volume={bg_vol}[bg_audio];
        [1:a]volume={ov_vol}[ov_audio];
        [bg_audio][ov_audio]amix=inputs=2:duration=shortest:normalize=0[aout]
        """

    def _build_ffmpeg_command(
        self,
        background: Path,
        output: Path,
        overlay: Path | None,
        filter_complex: str,
        audio_filter: str,
        duration: float,
    ) -> list[str]:
        """Build complete FFmpeg command."""
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(background),
        ]

        if overlay:
            cmd.extend(["-i", str(overlay)])

        # Combined filter
        full_filter = filter_complex
        if audio_filter and overlay:
            full_filter += ";" + audio_filter

        cmd.extend(
            [
                "-filter_complex",
                full_filter,
                "-map",
                "[vout]",
            ]
        )

        if overlay and "[aout]" in audio_filter:
            cmd.extend(["-map", "[aout]"])
        else:
            cmd.extend(["-map", "0:a?"])

        cmd.extend(
            [
                "-c:v",
                self.config.video_codec,
                "-preset",
                self.config.video_preset,
                "-crf",
                str(self.config.crf),
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                self.config.audio_codec,
                "-b:a",
                self.config.audio_bitrate,
                "-t",
                str(min(duration, 60)),
                str(output),
            ]
        )

        return cmd

    async def _generate_web_artifact(
        self,
        output: Path,
        template_config: dict,
    ) -> Path | None:
        """Generate DCC-style web artifact."""
        try:
            from kagami_studio.compositing.web_artifacts import create_dcc_artifact

            transcript = template_config.get("transcript", [])
            style = template_config.get("style", "dcc")

            artifact_dir = output.parent / f"{output.stem}_web"
            return await create_dcc_artifact(
                video_path=output,
                transcript=transcript,
                output_dir=artifact_dir,
                style=style,
            )
        except Exception as e:
            logger.warning(f"Web artifact generation failed: {e}")
            return None
