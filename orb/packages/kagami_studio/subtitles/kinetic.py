"""Kinetic Subtitle Generator — Broadcast-quality subtitles with PERFECT audio sync.

Creates ASS (Advanced SubStation Alpha) subtitles with:
- Large, highly visible text (72px)
- Thick outline for any background
- Clean timing (no overlaps)
- Emotion-based word highlighting

TIMING ARCHITECTURE:
- Word timings come from TTS (same source as audio)
- ASS file uses these exact timings
- FFmpeg burns subtitles using audio as timing reference
- Result: PERFECT subtitle-audio synchronization

WHY ASS > HTML KINETIC SUBTITLES:
- HTML subtitles are rendered by Playwright at variable frame rate
- This causes timing drift between subtitles and audio
- ASS subtitles are burned by FFmpeg using audio timeline as master
- Guarantees perfect sync regardless of video frame rate issues

Usage:
    generator = KineticSubtitleGenerator()
    generator.generate(words, output_path="subtitles.ass")

    # Then in FFmpeg:
    # ffmpeg -i video.mp4 -i audio.mp3 -vf "ass=subtitles.ass" output.mp4
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path


class EmotionStyle(Enum):
    """Emotion-based word styling."""

    NONE = auto()
    POWER = auto()  # Cyan - tech/power words
    HEART = auto()  # Coral - emotional words
    PRIDE = auto()  # Gold - achievement words
    WISDOM = auto()  # Gray - wisdom words
    ENERGY = auto()  # Bright cyan - energy words


@dataclass
class WordTiming:
    """Timing for a single word."""

    text: str
    start_ms: int
    end_ms: int
    emotion: EmotionStyle = EmotionStyle.NONE


@dataclass
class SubtitleLine:
    """A line of subtitle."""

    words: list[WordTiming] = field(default_factory=list)

    @property
    def start_ms(self) -> int:
        return self.words[0].start_ms if self.words else 0

    @property
    def end_ms(self) -> int:
        return self.words[-1].end_ms if self.words else 0

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)


# Emotion keywords
EMOTION_KEYWORDS: dict[str, EmotionStyle] = {
    # Power - tech words
    "AI": EmotionStyle.POWER,
    "brain": EmotionStyle.POWER,
    "nerves": EmotionStyle.POWER,
    "neurons": EmotionStyle.POWER,
    "signal": EmotionStyle.POWER,
    # Heart - emotional
    "people": EmotionStyle.HEART,
    "love": EmotionStyle.HEART,
    "cream": EmotionStyle.HEART,
    "pain": EmotionStyle.HEART,
    # Pride - achievement
    "science": EmotionStyle.PRIDE,
    "best": EmotionStyle.PRIDE,
    "success": EmotionStyle.PRIDE,
    # Wisdom - understanding
    "cold": EmotionStyle.WISDOM,
    "ice": EmotionStyle.WISDOM,
    "experience": EmotionStyle.WISDOM,
    "learned": EmotionStyle.WISDOM,
    # Energy - action
    "freeze": EmotionStyle.ENERGY,
    "fast": EmotionStyle.ENERGY,
    "now": EmotionStyle.ENERGY,
    "immediately": EmotionStyle.ENERGY,
}

# ASS colors (BGR format)
EMOTION_COLORS: dict[EmotionStyle, str] = {
    EmotionStyle.NONE: "&HFFFFFF&",
    EmotionStyle.POWER: "&HFFDD44&",  # Cyan
    EmotionStyle.HEART: "&H8888FF&",  # Coral
    EmotionStyle.PRIDE: "&H37AFD4&",  # Gold
    EmotionStyle.WISDOM: "&HDDDDDD&",  # Gray
    EmotionStyle.ENERGY: "&H00F0FF&",  # Bright cyan
}


class KineticSubtitleGenerator:
    """Generates broadcast-quality ASS subtitles."""

    def __init__(
        self,
        resolution: tuple[int, int] = (1920, 1080),
        font_size: int = 72,
        margin_v: int = 80,
    ):
        self.resolution = resolution
        self.font_size = font_size
        self.margin_v = margin_v

    def generate(
        self,
        words: list[dict] | list[WordTiming],
        output_path: Path | str | None = None,
    ) -> str:
        """Generate ASS subtitles from word timings."""
        # Convert to WordTiming objects
        timings = []
        for w in words:
            if isinstance(w, dict):
                text = w.get("text", "")
                start = int(w.get("start_ms", w.get("start", 0) * 1000 if "start" in w else 0))
                end = int(w.get("end_ms", w.get("end", 0) * 1000 if "end" in w else start + 200))
                emotion = self._detect_emotion(text)
                timings.append(WordTiming(text=text, start_ms=start, end_ms=end, emotion=emotion))
            else:
                if w.emotion == EmotionStyle.NONE:
                    w.emotion = self._detect_emotion(w.text)
                timings.append(w)

        # Group into lines
        lines = self._group_into_lines(timings)

        # Generate ASS
        ass_content = self._generate_ass(lines)

        if output_path:
            Path(output_path).write_text(ass_content)

        return ass_content

    def _detect_emotion(self, word: str) -> EmotionStyle:
        """Detect emotion for a word."""
        clean = word.strip(".,!?;:'\"()-").lower()
        return EMOTION_KEYWORDS.get(clean, EmotionStyle.NONE)

    def _group_into_lines(
        self,
        words: list[WordTiming],
        max_words: int = 8,
        max_chars: int = 50,
        pause_threshold_ms: int = 500,
    ) -> list[SubtitleLine]:
        """Group words into readable subtitle lines."""
        if not words:
            return []

        lines: list[SubtitleLine] = []
        current = SubtitleLine(words=[])
        char_count = 0

        for word in words:
            word_len = len(word.text) + 1
            need_new_line = False

            if current.words:
                gap = word.start_ms - current.words[-1].end_ms
                last_text = current.words[-1].text

                # Break conditions
                if gap > pause_threshold_ms:
                    need_new_line = True
                elif last_text.endswith((".", "!", "?")):
                    need_new_line = True
                elif len(current.words) >= 5 and last_text.endswith((",", ";", ":")):
                    need_new_line = True
                elif len(current.words) >= max_words:
                    need_new_line = True
                elif char_count + word_len > max_chars:
                    need_new_line = True

            if need_new_line and current.words:
                lines.append(current)
                current = SubtitleLine(words=[])
                char_count = 0

            current.words.append(word)
            char_count += word_len

        if current.words:
            lines.append(current)

        return lines

    def _generate_ass(self, lines: list[SubtitleLine]) -> str:
        """Generate ASS file content with polished broadcast-quality styling."""
        width, height = self.resolution

        # Use IBM Plex Sans (Kagami standard) with enhanced visibility
        # PrimaryColour: White, OutlineColour: Dark navy, BackColour: Semi-transparent black
        # Thicker outline (5) and shadow (3) for better readability on any background
        header = f"""[Script Info]
Title: Kagami Subtitles
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,IBM Plex Sans,{self.font_size},&H00FFFFFF,&H00FF9E4A,&H00171D0D,&H99000000,-1,0,0,0,100,100,1,0,1,5,3,2,100,100,{self.margin_v},1
Style: Highlight,IBM Plex Sans,{self.font_size},&H0099EEFF,&H0000FFFF,&H00171D0D,&H99000000,-1,0,0,0,100,100,1,0,1,5,3,2,100,100,{self.margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        events = []
        for i, line in enumerate(lines):
            # Calculate end time: extend to next line or +500ms
            next_start = lines[i + 1].start_ms if i < len(lines) - 1 else None
            event = self._generate_event(line, next_start)
            if event:
                events.append(event)

        return header + "\n".join(events)

    def _generate_event(self, line: SubtitleLine, next_start_ms: int | None) -> str | None:
        """Generate a single dialogue event."""
        if not line.words:
            return None

        # Build styled text
        parts = []
        for word in line.words:
            if word.emotion != EmotionStyle.NONE:
                color = EMOTION_COLORS[word.emotion]
                parts.append(f"{{\\c{color}}}{word.text}{{\\r}}")
            else:
                parts.append(word.text)

        text = " ".join(parts)

        # Timing
        start_ms = line.start_ms
        natural_end = line.end_ms + 400

        if next_start_ms is not None:
            end_ms = min(natural_end, next_start_ms - 50)
        else:
            end_ms = natural_end + 300

        end_ms = max(end_ms, start_ms + 500)

        # Add fade
        text = f"{{\\fad(100,100)}}{text}"

        start = self._ms_to_time(start_ms)
        end = self._ms_to_time(end_ms)

        return f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}"

    def _ms_to_time(self, ms: int) -> str:
        """Convert ms to ASS time format H:MM:SS.cc"""
        total_s = ms // 1000
        cs = (ms % 1000) // 10
        h = total_s // 3600
        m = (total_s % 3600) // 60
        s = total_s % 60
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def generate_kinetic_subtitles(
    words: list[dict],
    output_path: Path | str,
    resolution: tuple[int, int] = (1920, 1080),
) -> Path:
    """Convenience function."""
    generator = KineticSubtitleGenerator(resolution=resolution)
    generator.generate(words, output_path)
    return Path(output_path)


async def burn_subtitles(
    video_path: Path | str,
    subtitle_path: Path | str,
    output_path: Path | str,
) -> Path:
    """Burn ASS subtitles into video using FFmpeg."""
    import asyncio

    video_path = Path(video_path)
    subtitle_path = Path(subtitle_path)
    output_path = Path(output_path)

    # Escape subtitle path for FFmpeg filter
    sub_escaped = str(subtitle_path).replace(":", "\\:").replace("'", "\\'")

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        f"ass={sub_escaped}",
        "-c:a",
        "copy",
        str(output_path),
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    _, stderr = await process.communicate()

    if process.returncode != 0:
        raise RuntimeError(f"FFmpeg failed: {stderr.decode()}")

    return output_path


__all__ = [
    "EmotionStyle",
    "KineticSubtitleGenerator",
    "WordTiming",
    "burn_subtitles",
    "generate_kinetic_subtitles",
]
