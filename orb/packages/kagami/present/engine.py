"""Presentation Engine — Unified video production.

One function. Maximum impact.

Internal Architecture:
    1. ScriptGenerator → Narrative beats with emotion and timing
    2. AudioTrack → Voice + word timings (ElevenLabs V3)
    3. VisualTrack → Scenes + avatar (gpt-image-1 + HeyGen)
    4. KineticCompositor → Text overlays, transitions, final video
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


# =============================================================================
# TYPES
# =============================================================================


class PresentationStyle(str, Enum):
    """Presentation style presets."""

    ANNOUNCEMENT = "announcement"
    EXPLAINER = "explainer"
    DEMO = "demo"
    PITCH = "pitch"
    STORY = "story"


class CharacterType(str, Enum):
    """Character type for presentation."""

    LAMP = "lamp"  # Kagami Hub lamp
    AVATAR = "avatar"  # Human-like avatar
    VOICEOVER = "voiceover"  # Voice only, no character
    NONE = "none"  # No voice


class Mood(str, Enum):
    """Emotional mood."""

    WARM = "warm"
    PROFESSIONAL = "professional"
    PLAYFUL = "playful"
    DRAMATIC = "dramatic"
    CONTEMPLATIVE = "contemplative"


@dataclass
class Beat:
    """A single story beat with timing and visuals."""

    id: str
    text: str
    emotion: str
    duration_s: float
    scene_prompt: str | None = None
    character_action: str | None = None
    transition: str = "fade"  # cut, fade, dissolve, zoom, wipe
    motion: str = "zoom_in"  # static, zoom_in, zoom_out, pan_left, pan_right


@dataclass
class Script:
    """Complete presentation script."""

    title: str
    style: PresentationStyle
    mood: Mood
    beats: list[Beat]
    total_duration_s: float
    hook: str
    resolution: str


@dataclass
class AudioAssets:
    """Generated audio assets."""

    voice_path: Path
    voice_duration_s: float
    word_timings: list[dict] = field(default_factory=list)


@dataclass
class VisualAssets:
    """Generated visual assets."""

    scene_paths: dict[str, Path]
    avatar_path: Path | None = None
    thumbnail_path: Path | None = None


@dataclass
class PresentationResult:
    """Final presentation output."""

    video_path: Path
    duration_s: float
    thumbnail_path: Path | None = None
    transcript: str = ""
    generation_time_s: float = 0.0
    style: PresentationStyle = PresentationStyle.ANNOUNCEMENT
    character: CharacterType = CharacterType.LAMP
    resolution: tuple[int, int] = (1920, 1080)
    has_spatial_audio: bool = True
    text_overlays_count: int = 0
    transitions_count: int = 0


# =============================================================================
# SCRIPT GENERATOR
# =============================================================================


class ScriptGenerator:
    """Generates narrative scripts with emotional beats."""

    async def generate(
        self,
        topic: str,
        style: PresentationStyle,
        mood: Mood,
        duration_target: str = "auto",
        character: CharacterType = CharacterType.LAMP,
    ) -> Script:
        """Generate a complete script with beats."""
        durations = {"short": 30, "medium": 60, "long": 90, "auto": 60}
        target_s = durations.get(duration_target, 60)

        beats = await self._generate_beats(topic, style, mood, target_s, character)
        total_s = sum(b.duration_s for b in beats)

        return Script(
            title=topic,
            style=style,
            mood=mood,
            beats=beats,
            total_duration_s=total_s,
            hook=beats[0].text if beats else "",
            resolution=beats[-1].text if beats else "",
        )

    async def _generate_beats(
        self,
        topic: str,
        style: PresentationStyle,
        mood: Mood,
        target_s: float,
        character: CharacterType,
    ) -> list[Beat]:
        """Generate story beats."""
        # Kagami Hub specialized script
        if "kagami hub" in topic.lower() or "lamp" in topic.lower():
            return self._kagami_hub_beats(mood, character)

        return self._generic_beats(topic, style, mood, target_s, character)

    def _kagami_hub_beats(self, mood: Mood, character: CharacterType) -> list[Beat]:
        """Specialized beats for Kagami Hub announcement."""
        return [
            Beat(
                id="hook",
                text="You come home. The house knows.",
                emotion="mysterious",
                duration_s=4.0,
                scene_prompt="Dark room, single brass desk lamp, warm glow emerging from darkness, cinematic",
                transition="fade",
                motion="zoom_in",
            ),
            Beat(
                id="wake",
                text="I am Kagami.",
                emotion="warm",
                duration_s=2.5,
                scene_prompt="Brass articulated lamp with glowing cyan LED eye, tilting up curiously, warm lighting",
                transition="fade",
                motion="static",
            ),
            Beat(
                id="identity",
                text="I live in this lamp. But I am everywhere in your home.",
                emotion="confident",
                duration_s=4.5,
                scene_prompt="Wide shot modern living room, smart home elements subtly lighting up, lamp in foreground",
                transition="dissolve",
                motion="pan_right",
            ),
            Beat(
                id="problem",
                text="Your smart home isn't smart. Forty-seven apps. Zero intelligence.",
                emotion="serious",
                duration_s=4.5,
                scene_prompt="Phone screen filled with countless app icons, overwhelming, cold blue light",
                transition="cut",
                motion="zoom_out",
            ),
            Beat(
                id="insight",
                text="The best interface is no interface.",
                emotion="thoughtful",
                duration_s=3.0,
                scene_prompt="Phone fading away, warm ambient light taking over, minimalist",
                transition="dissolve",
                motion="zoom_in",
            ),
            Beat(
                id="solution",
                text="Just presence.",
                emotion="peaceful",
                duration_s=2.5,
                scene_prompt="Warm ambient lighting throughout room, lamp centered and glowing softly",
                transition="fade",
                motion="static",
            ),
            Beat(
                id="demo_voice",
                text="I hear you. Not just your words. Your intent.",
                emotion="attentive",
                duration_s=4.0,
                scene_prompt="Sound waves visualized in warm colors, lamp's LED eye tracking subtly",
                transition="dissolve",
                motion="zoom_in",
            ),
            Beat(
                id="demo_action",
                text="Movie time? The lights dim. The TV descends. The fireplace ignites.",
                emotion="impressive",
                duration_s=5.0,
                scene_prompt="Living room transforming, lights dimming, TV lowering from ceiling, fireplace glowing",
                transition="cut",
                motion="pan_left",
            ),
            Beat(
                id="personal",
                text="I learn what you love. What makes your home feel like home.",
                emotion="warm",
                duration_s=4.0,
                scene_prompt="Warm family silhouette, lamp observing with soft glow, intimate moment",
                transition="dissolve",
                motion="zoom_in",
            ),
            Beat(
                id="closing",
                text="Welcome home.",
                emotion="warm_confident",
                duration_s=3.0,
                scene_prompt="Lamp centered, warm golden glow, welcoming atmosphere",
                transition="fade",
                motion="static",
            ),
            Beat(
                id="title",
                text="Kagami Hub. Your home's new soul.",
                emotion="powerful",
                duration_s=4.0,
                scene_prompt="Product hero shot, brass lamp on dark background, logo subtle, premium",
                transition="fade",
                motion="zoom_in",
            ),
        ]

    def _generic_beats(
        self,
        topic: str,
        style: PresentationStyle,
        mood: Mood,
        target_s: float,
        character: CharacterType,
    ) -> list[Beat]:
        """Generate generic beats for any topic."""
        beat_duration = target_s / 5

        return [
            Beat(
                id="hook",
                text=f"Introducing {topic}.",
                emotion="confident",
                duration_s=beat_duration,
                scene_prompt=f"Title card: {topic}, premium, cinematic",
                transition="fade",
                motion="zoom_in",
            ),
            Beat(
                id="problem",
                text="The problem we're solving.",
                emotion="serious",
                duration_s=beat_duration,
                scene_prompt="Abstract visualization of problem, dark tones",
                transition="dissolve",
                motion="zoom_out",
            ),
            Beat(
                id="solution",
                text=f"{topic} changes everything.",
                emotion="excited",
                duration_s=beat_duration,
                scene_prompt="Product/solution visualization, bright, optimistic",
                transition="fade",
                motion="zoom_in",
            ),
            Beat(
                id="demo",
                text="Watch how it works.",
                emotion="engaging",
                duration_s=beat_duration,
                scene_prompt="Demo visualization, action shot",
                transition="dissolve",
                motion="pan_right",
            ),
            Beat(
                id="close",
                text=f"{topic}. Available now.",
                emotion="confident",
                duration_s=beat_duration,
                scene_prompt="Hero shot with CTA, premium finish",
                transition="fade",
                motion="static",
            ),
        ]


# =============================================================================
# AUDIO TRACK GENERATOR
# =============================================================================


class AudioTrackGenerator:
    """Generates all audio through spatial path."""

    def __init__(self):
        self._audio_gen = None

    async def generate(
        self,
        script: Script,
        output_dir: Path,
    ) -> AudioAssets:
        """Generate voice with word timings."""
        from kagami_media.production.generators.audio import SpatialAudioGenerator

        if self._audio_gen is None:
            self._audio_gen = SpatialAudioGenerator()
            await self._audio_gen.initialize()

        # Build continuous narration
        narration_text = " ".join(beat.text for beat in script.beats)

        # Generate with word timing
        voice_result = await self._audio_gen.generate_speech(
            text=narration_text,
            output_path=output_dir / "voice.mp3",
            with_timing=True,
        )

        # Convert word timings
        word_timings = []
        if voice_result.word_timings:
            for wt in voice_result.word_timings:
                word_timings.append(
                    {
                        "word": wt.word,
                        "start_s": wt.start_ms / 1000,
                        "end_s": wt.end_ms / 1000,
                    }
                )

        return AudioAssets(
            voice_path=voice_result.path,
            voice_duration_s=voice_result.duration_seconds,
            word_timings=word_timings,
        )


# =============================================================================
# VISUAL TRACK GENERATOR
# =============================================================================


class VisualTrackGenerator:
    """Generates all visuals: scenes and avatar."""

    def __init__(self):
        self._image_gen = None
        self._avatar_gen = None

    async def generate(
        self,
        script: Script,
        output_dir: Path,
        character: CharacterType,
        audio_path: Path | None = None,
    ) -> VisualAssets:
        """Generate all visual assets."""
        from kagami_media.production.generators.image import ImageGenerator

        if self._image_gen is None:
            self._image_gen = ImageGenerator()
            await self._image_gen.initialize()

        scene_paths: dict[str, Path] = {}

        # Generate scenes in parallel
        tasks = []
        for beat in script.beats:
            if beat.scene_prompt:
                tasks.append(self._generate_scene(beat, output_dir))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, tuple):
                beat_id, path = result
                scene_paths[beat_id] = path
            elif isinstance(result, Exception):
                logger.error(f"Scene generation failed: {result}")

        # Generate avatar if needed
        avatar_path = None
        if character == CharacterType.AVATAR and audio_path:
            avatar_path = await self._generate_avatar(audio_path, output_dir)

        # Generate thumbnail
        thumbnail_path = None
        if script.beats:
            try:
                thumb_result = await self._image_gen.generate_product(
                    prompt=f"{script.title} - hero image, premium, cinematic",
                    style="hero_shot",
                )
                thumbnail_path = thumb_result.path
            except Exception as e:
                logger.warning(f"Thumbnail generation failed: {e}")

        return VisualAssets(
            scene_paths=scene_paths,
            avatar_path=avatar_path,
            thumbnail_path=thumbnail_path,
        )

    async def _generate_scene(
        self,
        beat: Beat,
        output_dir: Path,
    ) -> tuple[str, Path]:
        """Generate a single scene image."""
        result = await self._image_gen.generate_background(
            prompt=beat.scene_prompt,
            aspect="16:9",
            mood=beat.emotion,
        )
        return beat.id, result.path

    async def _generate_avatar(
        self,
        audio_path: Path,
        output_dir: Path,
    ) -> Path | None:
        """Generate avatar video from audio."""
        try:
            from kagami_media.production.generators.avatar import AvatarGenerator

            if self._avatar_gen is None:
                self._avatar_gen = AvatarGenerator()
                await self._avatar_gen.initialize()

            # Use default Kagami identity image
            identity_path = Path("assets/identities/kagami/kagami_halfbody_professional.png")
            if not identity_path.exists():
                logger.warning("Kagami identity image not found, skipping avatar")
                return None

            result = await self._avatar_gen.generate(
                image_path=identity_path,
                audio_path=audio_path,
                output_path=output_dir / "avatar.mp4",
            )
            return result.path

        except Exception as e:
            logger.error(f"Avatar generation failed: {e}")
            return None


# =============================================================================
# COMPOSITOR (using KineticCompositor)
# =============================================================================


class Compositor:
    """Final assembly with kinetic text and transitions."""

    def __init__(self):
        self._compositor = None

    async def compose(
        self,
        script: Script,
        audio: AudioAssets,
        visuals: VisualAssets,
        output_path: Path,
        mood: Mood,
    ) -> PresentationResult:
        """Compose final video with kinetic text."""
        from kagami_media.production.compositor.kinetic import (
            KineticCompositor,
            SceneAsset,
            StylePreset,
            WordTiming,
        )

        start = time.time()

        # Map mood to style preset
        mood_to_style = {
            Mood.WARM: StylePreset.WARM,
            Mood.PROFESSIONAL: StylePreset.PROFESSIONAL,
            Mood.PLAYFUL: StylePreset.PLAYFUL,
            Mood.DRAMATIC: StylePreset.DRAMATIC,
            Mood.CONTEMPLATIVE: StylePreset.MINIMAL,
        }
        style = mood_to_style.get(mood, StylePreset.WARM)

        if self._compositor is None:
            self._compositor = KineticCompositor(style=style)

        # Build scene assets
        scenes = []
        current_time = 0.0

        for beat in script.beats:
            if beat.id in visuals.scene_paths:
                scenes.append(
                    SceneAsset(
                        beat_id=beat.id,
                        visual_path=visuals.scene_paths[beat.id],
                        start_s=current_time,
                        duration_s=beat.duration_s,
                        text=beat.text,
                        transition_in=beat.transition,
                        motion=beat.motion,
                    )
                )
                current_time += beat.duration_s

        # Convert word timings
        word_timings = None
        if audio.word_timings:
            word_timings = [
                WordTiming(
                    word=wt["word"],
                    start_s=wt["start_s"],
                    end_s=wt["end_s"],
                )
                for wt in audio.word_timings
            ]

        # Compose with kinetic text
        result = await self._compositor.compose(
            scenes=scenes,
            audio_path=audio.voice_path,
            output_path=output_path,
            word_timings=word_timings,
            title_card=script.title if len(script.beats) > 3 else None,
            end_card=f"{script.title}" if len(script.beats) > 5 else None,
        )

        generation_time = time.time() - start

        return PresentationResult(
            video_path=result.path,
            duration_s=result.duration_s,
            thumbnail_path=visuals.thumbnail_path,
            transcript=" ".join(b.text for b in script.beats),
            generation_time_s=generation_time,
            style=script.style,
            has_spatial_audio=True,
            text_overlays_count=result.text_overlays_count,
            transitions_count=result.transitions_count,
        )


# =============================================================================
# MAIN ENGINE
# =============================================================================


class PresentationEngine:
    """The unified presentation engine."""

    def __init__(self):
        self.script_gen = ScriptGenerator()
        self.audio_gen = AudioTrackGenerator()
        self.visual_gen = VisualTrackGenerator()
        self.compositor = Compositor()

    async def present(
        self,
        topic: str,
        *,
        style: PresentationStyle | str = PresentationStyle.ANNOUNCEMENT,
        character: CharacterType | str = CharacterType.LAMP,
        mood: Mood | str = Mood.WARM,
        duration: str = "auto",
        output_path: Path | None = None,
    ) -> PresentationResult:
        """Create a presentation video.

        Args:
            topic: What the presentation is about
            style: Presentation style
            character: Presenter type
            mood: Emotional tone
            duration: Target length (short/medium/long/auto)
            output_path: Where to save the video

        Returns:
            PresentationResult with video path and metadata
        """
        total_start = time.time()

        # Normalize enums
        if isinstance(style, str):
            style = PresentationStyle(style)
        if isinstance(character, str):
            character = CharacterType(character)
        if isinstance(mood, str):
            mood = Mood(mood)

        # Create output directory
        if output_path is None:
            safe_topic = "".join(c if c.isalnum() else "_" for c in topic.lower())[:30]
            output_dir = Path("/tmp/kagami_present") / f"{safe_topic}_{int(time.time())}"
        else:
            output_dir = output_path.parent

        output_dir.mkdir(parents=True, exist_ok=True)

        if output_path is None:
            output_path = output_dir / "presentation.mp4"

        logger.info(f"Creating presentation: {topic}")
        logger.info(f"  Style: {style.value}, Character: {character.value}, Mood: {mood.value}")

        # 1. Generate script
        logger.info("Generating script...")
        script = await self.script_gen.generate(
            topic=topic,
            style=style,
            mood=mood,
            duration_target=duration,
            character=character,
        )
        logger.info(f"  {len(script.beats)} beats, ~{script.total_duration_s:.0f}s")

        # 2. Generate audio first (needed for avatar)
        logger.info("Generating audio...")
        audio = await self.audio_gen.generate(script, output_dir)
        logger.info(f"  Voice: {audio.voice_duration_s:.1f}s, {len(audio.word_timings)} words")

        # 3. Generate visuals (can use audio for avatar)
        logger.info("Generating visuals...")
        visuals = await self.visual_gen.generate(
            script,
            output_dir,
            character,
            audio_path=audio.voice_path if character == CharacterType.AVATAR else None,
        )
        logger.info(f"  Scenes: {len(visuals.scene_paths)}")

        # 4. Compose final video
        logger.info("Compositing video...")
        result = await self.compositor.compose(
            script=script,
            audio=audio,
            visuals=visuals,
            output_path=output_path,
            mood=mood,
        )

        total_time = time.time() - total_start
        result.generation_time_s = total_time
        result.character = character

        logger.info(f"✅ Complete: {result.video_path}")
        logger.info(f"   Duration: {result.duration_s:.1f}s")
        logger.info(f"   Text overlays: {result.text_overlays_count}")
        logger.info(f"   Transitions: {result.transitions_count}")
        logger.info(f"   Generated in: {total_time:.1f}s")

        return result


# =============================================================================
# PUBLIC API
# =============================================================================


_engine: PresentationEngine | None = None


async def present(
    topic: str,
    *,
    style: PresentationStyle | str = "announcement",
    character: CharacterType | str = "lamp",
    mood: Mood | str = "warm",
    duration: str = "auto",
    output_path: Path | str | None = None,
) -> PresentationResult:
    """Create a presentation video.

    The simplest way to create AI-native video presentations.

    Args:
        topic: What the presentation is about (e.g., "Kagami Hub")
        style: Presentation style
            - "announcement": Product launch, big reveal
            - "explainer": How it works, educational
            - "demo": Show it in action
            - "pitch": Investor/sales pitch
            - "story": Narrative, emotional
        character: Presenter type
            - "lamp": Kagami Hub lamp
            - "avatar": Human-like avatar
            - "voiceover": Voice only
            - "none": No voice
        mood: Emotional tone
            - "warm": Friendly, inviting
            - "professional": Business, polished
            - "playful": Fun, energetic
            - "dramatic": Intense, impactful
        duration: Target length (short/medium/long/auto)
        output_path: Where to save the video (optional)

    Returns:
        PresentationResult with:
            - video_path: Path to the MP4 file
            - duration_s: Actual duration
            - thumbnail_path: Path to thumbnail image
            - transcript: Full spoken text
            - generation_time_s: How long it took
            - text_overlays_count: Number of text overlays
            - transitions_count: Number of transitions

    Example:
        video = await present("Kagami Hub")
        print(f"Video: {video.video_path}")
        print(f"Duration: {video.duration_s}s")
    """
    global _engine

    if _engine is None:
        _engine = PresentationEngine()

    if isinstance(output_path, str):
        output_path = Path(output_path)

    return await _engine.present(
        topic=topic,
        style=style,
        character=character,
        mood=mood,
        duration=duration,
        output_path=output_path,
    )
