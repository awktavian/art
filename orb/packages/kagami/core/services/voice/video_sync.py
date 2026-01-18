"""Video Synchronization — Frame-accurate audio-video alignment.

Provides algorithms for:
- Word timing → Frame synchronization
- Phoneme → Viseme mapping for lip sync
- Subtitle timing export (ASS, SRT, WebVTT)
- OBS text source updates

Usage:
    from kagami.core.services.voice.video_sync import (
        VideoSyncEngine,
        sync_to_frames,
        generate_visemes,
        export_subtitles,
    )

    # From word timings to frame sync
    frames = sync_to_frames(word_timings, fps=30)

    # Generate visemes for lip sync
    visemes = generate_visemes(word_timings)

    # Export subtitles
    ass_content = export_subtitles(word_timings, format="ass")

Created: January 7, 2026
Colony: ⚒️ Forge
鏡
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# FRAME SYNCHRONIZATION
# =============================================================================


@dataclass
class FrameSync:
    """Frame-synchronized word timing."""

    word: str
    start_frame: int
    end_frame: int

    # Sub-frame timing (for interpolation)
    start_offset_ms: float = 0.0  # Offset within start frame
    end_offset_ms: float = 0.0  # Offset within end frame

    # Original timing
    start_ms: int = 0
    end_ms: int = 0


@dataclass
class WordTiming:
    """Word timing from TTS."""

    text: str
    start_ms: int
    end_ms: int

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms


def sync_to_frames(
    word_timings: list[WordTiming],
    fps: float = 30.0,
) -> list[FrameSync]:
    """Convert word timings to frame-synchronized data.

    Snaps word boundaries to nearest video frame while
    preserving sub-frame offset for smooth interpolation.

    Args:
        word_timings: List of word timings
        fps: Video frame rate (24, 30, 60)

    Returns:
        List of FrameSync objects
    """
    if not word_timings:
        return []

    frame_ms = 1000.0 / fps
    synced: list[FrameSync] = []

    for word in word_timings:
        # Calculate frame numbers
        start_frame = int(word.start_ms / frame_ms)
        end_frame = int(word.end_ms / frame_ms)

        # Calculate sub-frame offsets
        start_offset = word.start_ms - (start_frame * frame_ms)
        end_offset = word.end_ms - (end_frame * frame_ms)

        synced.append(
            FrameSync(
                word=word.text,
                start_frame=start_frame,
                end_frame=end_frame,
                start_offset_ms=start_offset,
                end_offset_ms=end_offset,
                start_ms=word.start_ms,
                end_ms=word.end_ms,
            )
        )

    return synced


def interpolate_word_position(
    frame_sync: FrameSync,
    current_frame: int,
    fps: float = 30.0,
) -> float:
    """Calculate interpolated word visibility at a given frame.

    Returns a value 0-1 indicating how "visible" the word should be:
    - 0: Not yet spoken
    - 0-1: Fading in/out
    - 1: Fully spoken

    Args:
        frame_sync: Frame sync data for the word
        current_frame: Current video frame
        fps: Frame rate

    Returns:
        Interpolation factor 0-1
    """
    if current_frame < frame_sync.start_frame:
        return 0.0

    if current_frame > frame_sync.end_frame:
        return 1.0

    # Within the word's duration
    frame_ms = 1000.0 / fps
    current_ms = current_frame * frame_ms

    total_duration = frame_sync.end_ms - frame_sync.start_ms
    if total_duration <= 0:
        return 1.0

    elapsed = current_ms - frame_sync.start_ms
    return min(1.0, max(0.0, elapsed / total_duration))


# =============================================================================
# VISEME GENERATION (Lip Sync)
# =============================================================================


class Viseme(str, Enum):
    """Standard viseme set (Oculus/ARKit compatible).

    15 standard visemes representing mouth shapes for lip sync.
    """

    # Silence / rest position
    SIL = "sil"  # Silent, mouth closed

    # Vowels
    AA = "aa"  # "bot", "father"
    AE = "ae"  # "bat", "cat"  (can merge with AA)
    AH = "ah"  # "but", "cup"
    AO = "ao"  # "bought", "caught" (can merge with O)
    E = "E"  # "bet", "red"
    EH = "eh"  # Same as E
    I = "I"  # "bit", "kid"
    IY = "iy"  # "beat", "see" (can merge with I)
    O = "O"  # "boat", "go"
    U = "U"  # "book", "put"
    UW = "uw"  # "boot", "blue" (can merge with U)

    # Consonants (mouth shapes)
    PP = "PP"  # Bilabial: P, B, M
    FF = "FF"  # Labiodental: F, V
    TH = "TH"  # Dental: TH
    DD = "DD"  # Alveolar: D, T, N, L
    KK = "KK"  # Velar: K, G
    CH = "CH"  # Palatal: CH, J, SH
    SS = "SS"  # Sibilant: S, Z
    NN = "NN"  # Nasal: N, NG
    RR = "RR"  # Rhotic: R
    WW = "WW"  # Labial glide: W


# CMU phoneme to viseme mapping
PHONEME_TO_VISEME: dict[str, Viseme] = {
    # Vowels
    "AA": Viseme.AA,  # bot
    "AE": Viseme.AA,  # bat (merged)
    "AH": Viseme.AH,  # but
    "AO": Viseme.O,  # bought (merged)
    "AW": Viseme.O,  # bout
    "AY": Viseme.AA,  # bite
    "EH": Viseme.E,  # bet
    "ER": Viseme.RR,  # bird
    "EY": Viseme.E,  # bait
    "IH": Viseme.I,  # bit
    "IY": Viseme.I,  # beat (merged)
    "OW": Viseme.O,  # boat
    "OY": Viseme.O,  # boy
    "UH": Viseme.U,  # book
    "UW": Viseme.U,  # boot (merged)
    # Consonants - Bilabial
    "B": Viseme.PP,
    "M": Viseme.PP,
    "P": Viseme.PP,
    # Labiodental
    "F": Viseme.FF,
    "V": Viseme.FF,
    # Dental
    "DH": Viseme.TH,
    "TH": Viseme.TH,
    # Alveolar
    "D": Viseme.DD,
    "L": Viseme.DD,
    "N": Viseme.DD,
    "T": Viseme.DD,
    # Velar
    "G": Viseme.KK,
    "K": Viseme.KK,
    "NG": Viseme.NN,
    # Palatal
    "CH": Viseme.CH,
    "JH": Viseme.CH,
    "SH": Viseme.CH,
    "ZH": Viseme.CH,
    # Sibilants
    "S": Viseme.SS,
    "Z": Viseme.SS,
    # Glides
    "W": Viseme.WW,
    "Y": Viseme.I,
    "HH": Viseme.AH,
    "R": Viseme.RR,
}


@dataclass
class VisemeFrame:
    """Viseme data for a single frame."""

    viseme: Viseme
    start_ms: int
    end_ms: int

    # Blend weight (0-1) for smooth transitions
    weight: float = 1.0

    # Source word
    word: str = ""


def generate_visemes_from_words(
    word_timings: list[WordTiming],
    phoneme_dict: dict[str, list[str]] | None = None,
) -> list[VisemeFrame]:
    """Generate viseme sequence from word timings.

    Uses a simple heuristic when phoneme dictionary is not available:
    maps word characters to approximate visemes.

    For production lip sync, consider using:
    - CMU Pronouncing Dictionary
    - G2P (Grapheme-to-Phoneme) models
    - ElevenLabs' native alignment data

    Args:
        word_timings: Word timing data
        phoneme_dict: Optional pronunciation dictionary

    Returns:
        List of VisemeFrame objects
    """
    visemes: list[VisemeFrame] = []

    for word in word_timings:
        # Get phonemes (or use heuristic)
        if phoneme_dict and word.text.upper() in phoneme_dict:
            phonemes = phoneme_dict[word.text.upper()]
        else:
            phonemes = _heuristic_phonemes(word.text)

        if not phonemes:
            continue

        # Distribute phonemes across word duration
        phoneme_duration = word.duration_ms / len(phonemes)

        for i, phoneme in enumerate(phonemes):
            # Strip stress markers (e.g., "AA1" -> "AA")
            base_phoneme = "".join(c for c in phoneme if not c.isdigit())

            viseme = PHONEME_TO_VISEME.get(base_phoneme, Viseme.SIL)

            start_ms = word.start_ms + int(i * phoneme_duration)
            end_ms = word.start_ms + int((i + 1) * phoneme_duration)

            visemes.append(
                VisemeFrame(
                    viseme=viseme,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    word=word.text,
                )
            )

    return _smooth_visemes(visemes)


def _heuristic_phonemes(word: str) -> list[str]:
    """Generate approximate phonemes from spelling.

    This is a simple heuristic - for production use CMU dict or G2P.
    """
    phonemes = []
    word = word.upper()

    # Simple letter-to-phoneme mapping
    letter_phonemes = {
        "A": "AE",
        "E": "EH",
        "I": "IH",
        "O": "OW",
        "U": "AH",
        "B": "B",
        "C": "K",
        "D": "D",
        "F": "F",
        "G": "G",
        "H": "HH",
        "J": "JH",
        "K": "K",
        "L": "L",
        "M": "M",
        "N": "N",
        "P": "P",
        "Q": "K",
        "R": "R",
        "S": "S",
        "T": "T",
        "V": "V",
        "W": "W",
        "X": "K",
        "Y": "Y",
        "Z": "Z",
    }

    for char in word:
        if char in letter_phonemes:
            phonemes.append(letter_phonemes[char])

    return phonemes


def _smooth_visemes(visemes: list[VisemeFrame]) -> list[VisemeFrame]:
    """Smooth viseme transitions by merging consecutive same visemes."""
    if not visemes:
        return []

    smoothed = [visemes[0]]

    for v in visemes[1:]:
        if v.viseme == smoothed[-1].viseme:
            # Extend previous viseme
            smoothed[-1] = VisemeFrame(
                viseme=v.viseme,
                start_ms=smoothed[-1].start_ms,
                end_ms=v.end_ms,
                weight=1.0,
                word=smoothed[-1].word,
            )
        else:
            smoothed.append(v)

    return smoothed


# =============================================================================
# SUBTITLE EXPORT
# =============================================================================


def export_subtitles(
    word_timings: list[WordTiming],
    format: str = "ass",
    style: str = "kinetic",
    language: str = "en",
) -> str:
    """Export word timings as subtitles.

    Formats:
    - ass: Advanced SubStation Alpha (best for kinetic effects)
    - srt: SubRip (universal)
    - vtt: WebVTT (web)

    Args:
        word_timings: Word timing data
        format: Output format (ass, srt, vtt)
        style: Subtitle style (kinetic, simple)
        language: Language code for emotion keywords

    Returns:
        Subtitle file content as string
    """
    format = format.lower()

    if format == "ass":
        return _export_ass(word_timings, style, language)
    elif format == "srt":
        return _export_srt(word_timings)
    elif format == "vtt":
        return _export_vtt(word_timings)
    else:
        raise ValueError(f"Unsupported format: {format}")


def _format_ass_time(ms: int) -> str:
    """Format milliseconds as ASS timestamp (H:MM:SS.cc)."""
    hours = ms // 3600000
    ms = ms % 3600000
    minutes = ms // 60000
    ms = ms % 60000
    seconds = ms // 1000
    centiseconds = (ms % 1000) // 10
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"


def _format_srt_time(ms: int) -> str:
    """Format milliseconds as SRT timestamp (HH:MM:SS,mmm)."""
    hours = ms // 3600000
    ms = ms % 3600000
    minutes = ms // 60000
    ms = ms % 60000
    seconds = ms // 1000
    milliseconds = ms % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def _export_ass(
    word_timings: list[WordTiming],
    style: str,
    language: str,
) -> str:
    """Export as ASS subtitles with kinetic word reveal."""

    # ASS header
    header = """[Script Info]
Title: Kagami Subtitles
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
Timer: 100.0000

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Inter,56,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,1,2,40,40,60,1
Style: Emotion,Inter,56,&H00D4AF37,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,1,2,40,40,60,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events = []

    if style == "kinetic":
        # Word-by-word reveal
        for word in word_timings:
            start = _format_ass_time(word.start_ms)
            end = _format_ass_time(word.end_ms)

            # Simple kinetic: each word appears at its time
            events.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{word.text}")
    else:
        # Simple: group into lines
        lines = _group_into_lines(word_timings, max_words=8)
        for line_start, line_end, line_text in lines:
            start = _format_ass_time(line_start)
            end = _format_ass_time(line_end)
            events.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{line_text}")

    return header + "\n".join(events)


def _export_srt(word_timings: list[WordTiming]) -> str:
    """Export as SRT subtitles."""
    lines = _group_into_lines(word_timings, max_words=8)

    srt_lines = []
    for i, (start, end, text) in enumerate(lines, 1):
        srt_lines.append(str(i))
        srt_lines.append(f"{_format_srt_time(start)} --> {_format_srt_time(end)}")
        srt_lines.append(text)
        srt_lines.append("")

    return "\n".join(srt_lines)


def _export_vtt(word_timings: list[WordTiming]) -> str:
    """Export as WebVTT subtitles."""
    lines = _group_into_lines(word_timings, max_words=8)

    vtt_lines = ["WEBVTT", ""]
    for start, end, text in lines:
        start_str = _format_srt_time(start).replace(",", ".")
        end_str = _format_srt_time(end).replace(",", ".")
        vtt_lines.append(f"{start_str} --> {end_str}")
        vtt_lines.append(text)
        vtt_lines.append("")

    return "\n".join(vtt_lines)


def _group_into_lines(
    word_timings: list[WordTiming],
    max_words: int = 8,
) -> list[tuple[int, int, str]]:
    """Group words into subtitle lines."""
    if not word_timings:
        return []

    lines = []
    current_words = []
    line_start = word_timings[0].start_ms

    for word in word_timings:
        current_words.append(word.text)

        if len(current_words) >= max_words:
            line_end = word.end_ms
            lines.append((line_start, line_end, " ".join(current_words)))
            current_words = []
            line_start = line_end

    # Don't forget last line
    if current_words:
        line_end = word_timings[-1].end_ms
        lines.append((line_start, line_end, " ".join(current_words)))

    return lines


# =============================================================================
# VIDEO SYNC ENGINE
# =============================================================================


@dataclass
class SyncState:
    """Current synchronization state."""

    current_frame: int = 0
    current_word_index: int = 0
    current_viseme: Viseme = Viseme.SIL

    # Active words (currently visible)
    active_words: list[str] = field(default_factory=list)

    # Timing
    elapsed_ms: float = 0.0

    # Interpolation factors
    word_progress: float = 0.0  # 0-1 through current word
    viseme_weight: float = 1.0


class VideoSyncEngine:
    """Real-time video synchronization engine.

    Tracks playback position and provides:
    - Current word/viseme state
    - Subtitle updates
    - Lip sync data
    """

    def __init__(
        self,
        fps: float = 30.0,
    ):
        """Initialize sync engine.

        Args:
            fps: Video frame rate
        """
        self.fps = fps
        self.frame_ms = 1000.0 / fps

        self._word_timings: list[WordTiming] = []
        self._frame_sync: list[FrameSync] = []
        self._visemes: list[VisemeFrame] = []

        self._state = SyncState()
        self._callbacks: list[Any] = []

    def load_timings(
        self,
        word_timings: list[WordTiming],
    ) -> None:
        """Load word timings for synchronization.

        Args:
            word_timings: Word timing data from TTS
        """
        self._word_timings = word_timings
        self._frame_sync = sync_to_frames(word_timings, self.fps)
        self._visemes = generate_visemes_from_words(word_timings)

        logger.debug(
            f"Loaded {len(word_timings)} words, "
            f"{len(self._frame_sync)} frames, "
            f"{len(self._visemes)} visemes"
        )

    def update(self, elapsed_ms: float) -> SyncState:
        """Update sync state based on elapsed time.

        Args:
            elapsed_ms: Time elapsed since start

        Returns:
            Current SyncState
        """
        self._state.elapsed_ms = elapsed_ms
        self._state.current_frame = int(elapsed_ms / self.frame_ms)

        # Find current word
        self._state.active_words = []
        for i, word in enumerate(self._word_timings):
            if word.start_ms <= elapsed_ms <= word.end_ms:
                self._state.current_word_index = i
                self._state.active_words.append(word.text)

                # Calculate progress through word
                duration = word.end_ms - word.start_ms
                if duration > 0:
                    self._state.word_progress = (elapsed_ms - word.start_ms) / duration

        # Find current viseme
        for viseme in self._visemes:
            if viseme.start_ms <= elapsed_ms <= viseme.end_ms:
                self._state.current_viseme = viseme.viseme
                self._state.viseme_weight = viseme.weight
                break

        return self._state

    def update_frame(self, frame_number: int) -> SyncState:
        """Update sync state by frame number.

        Args:
            frame_number: Current video frame

        Returns:
            Current SyncState
        """
        elapsed_ms = frame_number * self.frame_ms
        return self.update(elapsed_ms)

    def get_subtitle_at(self, elapsed_ms: float) -> str | None:
        """Get subtitle text at given time.

        Args:
            elapsed_ms: Time position

        Returns:
            Subtitle text or None
        """
        for word in self._word_timings:
            if word.start_ms <= elapsed_ms <= word.end_ms:
                return word.text
        return None

    def export_subtitles(
        self,
        format: str = "ass",
        style: str = "kinetic",
    ) -> str:
        """Export loaded timings as subtitles.

        Args:
            format: Output format
            style: Subtitle style

        Returns:
            Subtitle file content
        """
        return export_subtitles(self._word_timings, format, style)

    def get_viseme_blend(
        self,
        elapsed_ms: float,
        blend_duration_ms: float = 50.0,
    ) -> dict[Viseme, float]:
        """Get viseme blend weights for smooth lip sync.

        Returns weights for blending between visemes
        during transitions.

        Args:
            elapsed_ms: Current time
            blend_duration_ms: Transition duration

        Returns:
            Dict of viseme -> weight (0-1)
        """
        blends: dict[Viseme, float] = {Viseme.SIL: 0.0}

        for viseme in self._visemes:
            if viseme.start_ms <= elapsed_ms <= viseme.end_ms:
                # Fully active
                blends[viseme.viseme] = 1.0
            elif viseme.start_ms - blend_duration_ms <= elapsed_ms < viseme.start_ms:
                # Blending in
                blend_progress = (
                    elapsed_ms - (viseme.start_ms - blend_duration_ms)
                ) / blend_duration_ms
                blends[viseme.viseme] = max(blends.get(viseme.viseme, 0), blend_progress)
            elif viseme.end_ms < elapsed_ms <= viseme.end_ms + blend_duration_ms:
                # Blending out
                blend_progress = 1.0 - ((elapsed_ms - viseme.end_ms) / blend_duration_ms)
                blends[viseme.viseme] = max(blends.get(viseme.viseme, 0), blend_progress)

        # Normalize
        total = sum(blends.values())
        if total > 0:
            blends = {k: v / total for k, v in blends.items()}
        else:
            blends = {Viseme.SIL: 1.0}

        return blends


# =============================================================================
# SINGLETON
# =============================================================================

_sync_engine: VideoSyncEngine | None = None


def get_video_sync_engine(fps: float = 30.0) -> VideoSyncEngine:
    """Get singleton video sync engine.

    Args:
        fps: Frame rate

    Returns:
        VideoSyncEngine instance
    """
    global _sync_engine

    if _sync_engine is None:
        _sync_engine = VideoSyncEngine(fps=fps)

    return _sync_engine


def reset_sync_engine() -> None:
    """Reset singleton engine."""
    global _sync_engine
    _sync_engine = None


__all__ = [
    "PHONEME_TO_VISEME",
    "FrameSync",
    "SyncState",
    "VideoSyncEngine",
    "Viseme",
    "VisemeFrame",
    "WordTiming",
    "export_subtitles",
    "generate_visemes_from_words",
    "get_video_sync_engine",
    "interpolate_word_position",
    "reset_sync_engine",
    "sync_to_frames",
]
