"""鏡 Production — THE Unified Video Production Pipeline.

This is THE ONLY video production system. All other systems have been deleted.

Architecture:
    script.py      → Script dataclasses and export (MD/PDF)
    slides.py      → Slide-to-video renderer (FFmpeg/Playwright)
    avatar.py      → HeyGen Avatar IV for lip-synced talking heads
    spatial.py     → Spatial audio via UnifiedVoiceEffector
    compositor.py  → FFmpeg compositor with chromakey

Pipeline Flow:
    Script → Audio (TTS) → Slides Video → Avatar Video → Spatial Audio →
    → Subtitles (ASS) → Compositor → Final MP4

Features:
    - Full script generation with slide + spoken text + timing
    - Multi-shot support: dialogue, reverse (back of head), audience views
    - Spatial audio via UnifiedVoiceEffector
    - HeyGen Avatar IV for lip-synced talking heads
    - Runway for action/audience shots (future)
    - FFmpeg compositor with chromakey
    - Kinetic subtitles (DCC-style word reveal)

Usage:
    from kagami_studio.production import produce_video, ShotType

    result = await produce_video(
        script=[
            {"title": "Welcome", "spoken": "Hello everyone...", "shot": "dialogue"},
            {"title": "", "spoken": "", "shot": "audience", "duration": 2.0},
            {"title": "The Problem", "spoken": "Here's the issue...", "shot": "reverse"},
        ],
        speaker="tim",
        spatial_audio=True,
    )

    print(f"Final video: {result.video_path}")

Created: January 2026
Replaces: talk/, presentation/, scattered production code
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Re-export from submodules
from kagami_studio.composition.shot import CameraAngle, ShotType
from kagami_studio.production.script import (
    ProductionScript,
    ScriptSlide,
    WordTiming,
    export_script_markdown,
    export_script_pdf,
)

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("/tmp/kagami_production")


@dataclass
class ProductionResult:
    """Result of video production."""

    success: bool
    video_path: Path | None = None
    script_path: Path | None = None
    audio_path: Path | None = None
    subtitle_path: Path | None = None
    timeline_path: Path | None = None
    duration_s: float = 0.0
    error: str | None = None
    shots: list[Path] = field(default_factory=list)


async def produce_video(
    script: list[dict[str, Any]],
    speaker: str = "tim",
    output_dir: Path | str | None = None,  # Auto-generate if None
    spatial_audio: bool = False,  # Skip by default (fast)
    include_avatar: bool = True,  # HeyGen avatar enabled by default
    layout: str = "corner",  # corner, side_by_side, pip
    resolution: tuple[int, int] = (1920, 1080),
    slide_method: str = "playwright",  # Rich slides by default
    # Design options (Gamma-style)
    generate_images: bool = True,  # AI hero images enabled by default
    theme: str = "dark_blue",  # Gradient theme
    accent_color: str = "4a9eff",  # Accent color (hex without #)
    use_llm: bool = True,  # Use LLM for slide design by default
    reuse_images: bool = True,  # Reuse existing images (faster iteration)
    # Subtitle options (ASS subtitles are DEFAULT for perfect audio sync)
    generate_ass_subtitles: bool = True,  # Generate ASS file (default: True for sync)
    burn_ass_subtitles: bool = True,  # Burn ASS into video (default: True for perfect sync)
    # Shot planning (optional, auto-generated if None)
    shot_plan: ProductionPlan | None = None,
    coverage: str = "ted_talk",  # Coverage strategy if auto-planning
) -> ProductionResult:
    """THE unified video production pipeline.

    WORKS WITH ZERO CONFIGURATION — just pass a script!

    Optimized defaults:
    - Rich slides with craft design system (playwright)
    - LLM-powered slide design with fallback to heuristics
    - Fast rendering (~10x faster than frame-by-frame)
    - Auto-generated output directory

    Args:
        script: List of slide dictionaries with keys:
            - title: Slide title (optional)
            - spoken: Text to speak (required for dialogue)
            - points: Bullet points (optional)
            - shot: Shot type (dialogue, reverse, audience, etc.) (optional)
            - duration: Duration in seconds (optional, auto from TTS)
            - mood: Emotional tone (optional)
        speaker: Character identity_id for TTS/avatar (default: "tim")
                 Examples: "tim", "andy_mcrorie", "kelli_finglass"
        output_dir: Output directory (auto-generated if None)
        spatial_audio: Spatialize audio (default: False - fast mode)
        include_avatar: Generate HeyGen avatar (default: False - fast mode)
        layout: Avatar position (corner, side_by_side, pip)
        resolution: Video resolution
        slide_method: Slide rendering ("playwright" for rich, "drawtext" for fast)
        generate_images: Generate AI hero images (default: True)
        theme: Gradient theme (dark_blue, midnight, ocean, sunset, forest, warm)
        accent_color: Accent color hex without # (default: "4a9eff")
        use_llm: Use LLM for slide design (default: True)
        reuse_images: Reuse existing hero images instead of regenerating (default: True)
        generate_ass_subtitles: Generate ASS subtitle file (default: True for perfect sync)
        burn_ass_subtitles: Burn ASS subtitles into video via FFmpeg (default: True)
            NOTE: ASS subtitles are burned using audio timeline, guaranteeing perfect sync.
            HTML kinetic subtitles are automatically disabled when burn_ass_subtitles=True.
        shot_plan: Pre-planned shots (from plan_production). If None, auto-generated.
        coverage: Coverage strategy if auto-planning ("ted_talk", "interview", etc.)

    Returns:
        ProductionResult with paths to all generated files

    Example:
        # Minimal usage - just works!
        result = await produce_video([
            {"title": "Welcome", "spoken": "Hello everyone!"},
            {"title": "Key Point", "spoken": "Here's what matters..."},
        ])

        # With speaker
        result = await produce_video(script, speaker="tim")

        # Full featured (slow but comprehensive)
        result = await produce_video(
            script,
            speaker="tim",
            spatial_audio=True,
            include_avatar=True,
            generate_images=True,
        )

        # List available speakers
        print(list_available_speakers())
    """
    # Auto-generate output directory if not provided
    if output_dir is None:
        from datetime import datetime

        output_dir = Path(f"/tmp/kagami_video_{datetime.now():%Y%m%d_%H%M%S}")
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load speaker context for logging
    speaker_ctx = load_speaker_context(speaker)
    logger.info(
        f"Starting production: {len(script)} slides, "
        f"speaker={speaker_ctx.name} ({speaker_ctx.identity_id})"
    )

    # Auto-generate shot plan if not provided
    if shot_plan is None and include_avatar:
        try:
            from kagami_studio.production.shot_planner import (
                CoverageStrategy,
                plan_production as _plan_production,
            )

            logger.info(f"  Auto-generating shot plan (coverage={coverage})...")
            shot_plan = await _plan_production(
                script=script,
                speaker=speaker,
                coverage=CoverageStrategy(coverage),
                include_broll=True,
            )
            logger.info(f"  ✓ Planned {shot_plan.shot_count} shots")
        except Exception as e:
            logger.warning(f"  Shot planning failed, using defaults: {e}")

    try:
        # 1. Parse script into structured format
        production_script = ProductionScript.from_dict_list(script, speaker)

        # 2. Export script document
        script_path = output_dir / "script.md"
        production_script.export_markdown(script_path)
        logger.info(f"Exported script: {script_path}")

        # 3. Generate audio with word timings
        audio_path, word_timings, slide_timings = await _generate_audio(
            production_script, output_dir, speaker
        )

        # Update script with actual durations
        for slide, timing in zip(production_script.slides, slide_timings, strict=False):
            slide.duration_s = timing["duration_s"]
        production_script.total_duration_s = sum(
            s.duration_s or 0 for s in production_script.slides
        )

        # Re-export script with timing
        production_script.export_markdown(script_path)

        # 4. Spatialize audio (if enabled)
        if spatial_audio:
            from kagami_studio.production.spatial import spatialize_audio

            audio_path = await spatialize_audio(audio_path, format="stereo")

        # 5. Generate slides video (Gamma-style rich design)
        from kagami_studio.production.slides import render_slides_to_video

        # If burning ASS subtitles, disable HTML kinetic subtitles to avoid duplication
        # ASS subtitles burned via FFmpeg have perfect audio sync
        render_html_subtitles = not burn_ass_subtitles

        slides_video = await render_slides_to_video(
            script=production_script,
            slide_timings=slide_timings,
            output_path=output_dir / "slides.mp4",
            word_timings=word_timings,
            audio_path=audio_path,  # For duration calculation
            resolution=resolution,
            generate_images=generate_images,
            theme=theme,
            accent_color=accent_color,
            use_llm=use_llm,
            speaker=speaker,
            reuse_images=reuse_images,
            render_html_subtitles=render_html_subtitles,  # Disable if using ASS
        )

        # 6. Generate avatar/shot videos (using shot_plan if available)
        shot_videos = []
        if include_avatar:
            shot_videos = await _generate_shots(
                production_script,
                audio_path,
                slide_timings,
                output_dir,
                shot_plan=shot_plan,
            )

        # 7. Generate ASS subtitles (optional)
        subtitle_path = None
        if generate_ass_subtitles and word_timings:
            from kagami_studio.subtitles.kinetic import KineticSubtitleGenerator

            subtitle_path = output_dir / "subtitles.ass"
            words = [
                {"text": w.text, "start_ms": w.start_ms, "end_ms": w.end_ms} for w in word_timings
            ]
            generator = KineticSubtitleGenerator()
            generator.generate(words, output_path=subtitle_path)
            logger.info(f"Generated ASS subtitles: {subtitle_path}")

        # 8. Composite final video
        from kagami_studio.production.compositor import composite_video

        composite_result = await composite_video(
            slides_video=slides_video,
            avatar_video=shot_videos[0] if shot_videos else None,
            audio_path=audio_path,
            subtitle_path=subtitle_path if burn_ass_subtitles else None,
            output_path=output_dir / "final.mp4",
            layout=layout,
        )

        if not composite_result.success:
            return ProductionResult(
                success=False,
                error=f"Compositing failed: {composite_result.error}",
            )

        # 9. Save timeline
        timeline_path = output_dir / "timeline.json"
        timeline_path.write_text(
            json.dumps(
                {
                    "words": [
                        {
                            "text": w.text,
                            "start_ms": w.start_ms,
                            "end_ms": w.end_ms,
                            "slide": w.slide_index,
                        }
                        for w in word_timings
                    ],
                    "slides": slide_timings,
                },
                indent=2,
            )
        )

        logger.info(f"✓ Production complete: {composite_result.output_path}")

        return ProductionResult(
            success=True,
            video_path=composite_result.output_path,
            script_path=script_path,
            audio_path=audio_path,
            subtitle_path=subtitle_path,
            timeline_path=timeline_path,
            duration_s=production_script.total_duration_s,
            shots=shot_videos,
        )

    except Exception as e:
        logger.error(f"Production failed: {e}", exc_info=True)
        return ProductionResult(success=False, error=str(e))


async def _generate_audio(
    script: ProductionScript,
    output_dir: Path,
    speaker: str,
) -> tuple[Path, list[WordTiming], list[dict]]:
    """Generate unified TTS audio with word timings.

    Uses ElevenLabs v3 with [pause] tags for non-dialogue sections.
    """
    from kagami_studio.characters.voice import CharacterVoice

    voice = CharacterVoice(speaker)
    await voice.initialize()

    # Build unified text with pause tags
    unified_text_parts = []
    slide_markers = []

    for i, slide in enumerate(script.slides):
        if slide.spoken_text:
            slide_markers.append(
                {
                    "index": i,
                    "text": slide.spoken_text,
                    "word_count": len(slide.spoken_text.split()),
                }
            )
            unified_text_parts.append(slide.spoken_text)
        else:
            pause_duration = slide.duration_s or 2.0
            if pause_duration <= 1.0:
                unified_text_parts.append("[pause]")
            elif pause_duration <= 2.0:
                unified_text_parts.append("[long pause]")
            else:
                num_pauses = int(pause_duration / 1.5)
                unified_text_parts.append(" ".join(["[long pause]"] * max(1, num_pauses)))

            slide_markers.append(
                {
                    "index": i,
                    "text": "",
                    "word_count": 0,
                    "is_pause": True,
                    "duration_s": pause_duration,
                }
            )

    unified_text = " [pause] ".join(unified_text_parts)
    logger.info(f"Generating audio: {len(unified_text)} chars, {len(slide_markers)} slides")

    # Generate ONE audio with timestamps
    result = await voice.speak(
        unified_text,
        mood="neutral",
        with_timestamps=True,
    )

    if not result.success or not result.audio_path:
        raise RuntimeError(f"TTS generation failed: {result.error}")

    audio_path = output_dir / "narration.mp3"
    shutil.copy(result.audio_path, audio_path)

    # Parse word timings into slide timings
    all_word_timings = []
    slide_timings = []

    if result.word_timings:
        word_idx = 0

        for marker in slide_markers:
            slide_start_ms = None
            slide_end_ms = 0

            if marker.get("is_pause"):
                if word_idx > 0 and word_idx < len(result.word_timings):
                    prev_end = result.word_timings[word_idx - 1].end_ms if word_idx > 0 else 0
                    slide_start_ms = prev_end
                    slide_end_ms = prev_end + int(marker["duration_s"] * 1000)
                else:
                    slide_start_ms = slide_timings[-1]["end_ms"] if slide_timings else 0
                    slide_end_ms = slide_start_ms + int(marker["duration_s"] * 1000)
            else:
                words_for_slide = marker["word_count"]
                words_collected = 0

                while word_idx < len(result.word_timings) and words_collected < words_for_slide:
                    wt = result.word_timings[word_idx]

                    if wt.text.lower() in ["[pause]", "[short", "pause]", "[long", "long]"]:
                        word_idx += 1
                        continue

                    if slide_start_ms is None:
                        slide_start_ms = wt.start_ms

                    slide_end_ms = wt.end_ms

                    all_word_timings.append(
                        WordTiming(
                            text=wt.text,
                            start_ms=wt.start_ms,
                            end_ms=wt.end_ms,
                            slide_index=marker["index"],
                        )
                    )

                    words_collected += 1
                    word_idx += 1

            if slide_start_ms is None:
                slide_start_ms = slide_timings[-1]["end_ms"] if slide_timings else 0

            slide_timings.append(
                {
                    "index": marker["index"],
                    "start_ms": slide_start_ms,
                    "end_ms": slide_end_ms,
                    "duration_s": (slide_end_ms - slide_start_ms) / 1000,
                }
            )
    else:
        logger.warning("No word timings returned, estimating durations")
        current_ms = 0
        for marker in slide_markers:
            if marker.get("is_pause"):
                duration_ms = int(marker["duration_s"] * 1000)
            else:
                duration_ms = marker["word_count"] * 150

            slide_timings.append(
                {
                    "index": marker["index"],
                    "start_ms": current_ms,
                    "end_ms": current_ms + duration_ms,
                    "duration_s": duration_ms / 1000,
                }
            )
            current_ms += duration_ms

    logger.info(f"Generated audio: {len(all_word_timings)} words, {len(slide_timings)} slides")
    return audio_path, all_word_timings, slide_timings


async def _generate_shots(
    script: ProductionScript,
    audio_path: Path,
    slide_timings: list[dict],
    output_dir: Path,
    shot_plan: ProductionPlan | None = None,
) -> list[Path]:
    """Generate avatar/action shots via HeyGen.

    Uses shot_plan for visual consistency if provided.
    """
    from kagami_studio.production.avatar import AvatarGenerator

    shots_dir = output_dir / "shots"
    shots_dir.mkdir(exist_ok=True)

    shot_paths = []

    # Use planned shots if available
    if shot_plan is not None:
        dialogue_shots = shot_plan.get_dialogue_shots()
        visual_seed = shot_plan.visual_seed
        logger.info(
            f"Using shot plan: {len(dialogue_shots)} dialogue shots, "
            f"speaker={visual_seed.character_name}"
        )
    else:
        # Fallback: collect dialogue shots from script
        dialogue_shots = []
        visual_seed = None
        for i, (slide, timing) in enumerate(zip(script.slides, slide_timings, strict=False)):
            if slide.shot_type in (ShotType.DIALOGUE, ShotType.MONOLOGUE):
                dialogue_shots.append(
                    {
                        "index": i,
                        "slide": slide,
                        "timing": timing,
                        "type": slide.shot_type.value,
                        "mood": slide.mood,
                    }
                )

    if not dialogue_shots:
        return []

    # Generate avatar for all dialogue shots
    generator = AvatarGenerator()
    await generator.initialize()

    try:
        # Determine motion from shot plan or first shot
        if shot_plan is not None and dialogue_shots:
            # Use the first planned shot's motion
            first_planned = dialogue_shots[0]
            motion = first_planned.motion if hasattr(first_planned, "motion") else "neutral"
        elif dialogue_shots:
            first_shot = dialogue_shots[0]
            motion = (
                first_shot.get("mood", "neutral") if isinstance(first_shot, dict) else "neutral"
            )
        else:
            motion = "neutral"

        # Generate avatar video
        result = await generator.generate(
            audio_path=audio_path,
            character=script.speaker,
            shot_type="dialogue",
            motion=motion,
        )

        if result.success and result.video_path:
            shot_path = shots_dir / "shot_000_dialogue.mp4"
            shutil.copy(result.video_path, shot_path)
            shot_paths.append(shot_path)
            logger.info(f"Generated avatar shot: {shot_path}")

            # Log visual consistency info
            if visual_seed:
                logger.info(f"  Visual seed: {visual_seed.appearance_prompt[:50]}...")

    except Exception as e:
        logger.warning(f"Avatar generation failed: {e}")
        # Create placeholder
        shot_path = await _create_placeholder_shot(
            shots_dir, 0, "dialogue", slide_timings[0]["duration_s"] if slide_timings else 5.0
        )
        shot_paths.append(shot_path)

    return shot_paths


async def _create_placeholder_shot(
    output_dir: Path,
    index: int,
    shot_type: str,
    duration: float,
) -> Path:
    """Create placeholder video for failed shots."""
    import subprocess

    shot_path = output_dir / f"shot_{index:03d}_{shot_type}.mp4"

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=0x1a1a2e:s=1920x1080:d={duration}:r=30",
            "-vf",
            f"drawtext=text='[{shot_type.upper()}]':fontsize=48:fontcolor=white:"
            f"x=(w-text_w)/2:y=(h-text_h)/2",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            str(shot_path),
        ],
        capture_output=True,
        check=True,
    )

    return shot_path


# Re-export design system
from kagami_studio.production.slide_design import (
    GradientPreset,
    SlideDesign,
    SlideLayout,
    generate_slide_html,
    generate_slide_deck_html,
)

# Re-export LLM generator
from kagami_studio.production.llm_slide_generator import (
    LLMSlideGenerator,
    PresentationPlan,
    SlideContentDesign,
    SpeakerContext,
    generate_presentation,
    list_available_speakers,
    load_speaker_context,
)

# Re-export shot planner
from kagami_studio.production.shot_planner import (
    CoverageStrategy,
    PlannedShot,
    ProductionPlan,
    ShotPlanner,
    VisualSeed,
    list_coverage_strategies,
    load_visual_seed,
    plan_production,
)

# Re-export topic generator (THE entry point)
from kagami_studio.production.topic_generator import (
    PresentationTone,
    generate_presentation as generate_presentation_from_topic,
    generate_script_from_topic,
    quick_video,
)

# Re-export new unified models
from kagami_studio.production.models import (
    Presentation,
    SlideContent,
    SlideTiming,
    COLOR_PALETTES,
)

# Re-export unified layouts
from kagami_studio.production.layouts import (
    LayoutCategory,
    LayoutConfig,
    SlideLayoutType,
    LAYOUT_METADATA,
    get_layout_config,
    get_ted_style_layouts,
    get_image_layouts,
)

# Re-export HTML renderer
from kagami_studio.production.html_renderer import (
    render_presentation_html,
    render_slide_html,
    generate_css,
    FIBONACCI_MS,
)

# Re-export TED-style video renderer
from kagami_studio.production.slides import render_ted_style_video


# === COMPOSABLE PRIMITIVES ===
# Standalone functions for modular usage


async def synthesize_speech(
    text: str,
    speaker: str = "tim",
    mood: str = "neutral",
    with_timestamps: bool = True,
) -> tuple[Path, list[WordTiming]]:
    """Standalone TTS synthesis with word timings.

    Low-level primitive for generating speech audio.

    Args:
        text: Text to synthesize
        speaker: Character identity_id
        mood: Emotional tone (neutral, excited, calm, etc.)
        with_timestamps: Return word-level timings

    Returns:
        Tuple of (audio_path, word_timings)

    Example:
        audio, timings = await synthesize_speech("Hello world", speaker="tim")
    """
    from kagami_studio.characters.voice import CharacterVoice

    voice = CharacterVoice(speaker)
    await voice.initialize()

    result = await voice.speak(text, mood=mood, with_timestamps=with_timestamps)

    if not result.success or not result.audio_path:
        raise RuntimeError(f"TTS failed: {result.error}")

    word_timings = []
    if result.word_timings:
        word_timings = [
            WordTiming(text=w.text, start_ms=w.start_ms, end_ms=w.end_ms, slide_index=0)
            for w in result.word_timings
        ]

    return Path(result.audio_path), word_timings


async def render_slide_image(
    slide: dict[str, Any],
    output_path: Path | str,
    resolution: tuple[int, int] = (1920, 1080),
    theme: str = "dark_blue",
    use_llm: bool = True,
    speaker: str = "tim",
) -> Path:
    """Render a single slide to a static image.

    Low-level primitive for single-slide rendering.

    Args:
        slide: Slide dictionary with title, spoken, points, etc.
        output_path: Output PNG path
        resolution: Image resolution
        theme: Gradient theme
        use_llm: Use LLM for design
        speaker: Speaker identity

    Returns:
        Path to rendered PNG image

    Example:
        img = await render_slide_image(
            {"title": "Hello", "spoken": "World"},
            "/tmp/slide.png",
        )
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError as e:
        raise ImportError(
            "Playwright required: pip install playwright && playwright install chromium"
        ) from e

    from kagami_studio.production.slide_content import enhance_script_to_designs
    from kagami_studio.production.slide_design import (
        GradientPreset,
        generate_slide_deck_html,
    )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Generate design
    try:
        theme_preset = GradientPreset(theme)
    except (ValueError, KeyError):
        theme_preset = GradientPreset.DARK_BLUE

    designs = await enhance_script_to_designs(
        slides=[slide],
        theme=theme_preset,
        use_llm=use_llm,
        speaker=speaker,
    )

    # Generate HTML
    html_content = generate_slide_deck_html(designs, resolution)
    html_path = Path("/tmp/kagami_slide_render.html")
    html_path.write_text(html_content)

    # Screenshot
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": resolution[0], "height": resolution[1]})
        await page.goto(f"file://{html_path}")
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(0.2)
        await page.screenshot(path=str(output_path))
        await browser.close()

    return output_path


async def render_slide_deck(
    slides: list[dict[str, Any]],
    timings: list[dict],
    output_path: Path | str,
    resolution: tuple[int, int] = (1920, 1080),
    theme: str = "dark_blue",
    use_llm: bool = True,
    speaker: str = "tim",
) -> Path:
    """Render slides to video with transitions.

    Low-level primitive for slide deck rendering.

    Args:
        slides: List of slide dictionaries
        timings: List of {"start_ms", "end_ms", "duration_s"} per slide
        output_path: Output MP4 path
        resolution: Video resolution
        theme: Gradient theme
        use_llm: Use LLM for design
        speaker: Speaker identity

    Returns:
        Path to rendered video

    Example:
        video = await render_slide_deck(
            slides=[{"title": "A", "spoken": "..."}, {"title": "B", "spoken": "..."}],
            timings=[{"start_ms": 0, "end_ms": 3000}, {"start_ms": 3000, "end_ms": 6000}],
            output_path="/tmp/slides.mp4",
        )
    """
    from kagami_studio.production.slides import render_slides_to_video
    from kagami_studio.production.script import ProductionScript

    # Convert to ProductionScript
    script = ProductionScript.from_dict_list(slides, speaker)

    # Update timings
    for i, timing in enumerate(timings):
        if i < len(script.slides):
            script.slides[i].duration_s = timing.get("duration_s", 3.0)

    return await render_slides_to_video(
        script=script,
        slide_timings=timings,
        output_path=Path(output_path),
        resolution=resolution,
        theme=theme,
        use_llm=use_llm,
        speaker=speaker,
        reuse_images=True,
    )


async def composite_final_video(
    slides_video: Path | str,
    audio_path: Path | str,
    output_path: Path | str,
    subtitle_path: Path | str | None = None,
    avatar_video: Path | str | None = None,
    layout: str = "corner",
) -> Path:
    """Composite final video from components.

    Low-level primitive for video compositing.

    Args:
        slides_video: Path to slides video
        audio_path: Path to audio
        output_path: Output MP4 path
        subtitle_path: Optional subtitles (ASS)
        avatar_video: Optional avatar video for PIP
        layout: Avatar layout (corner, side_by_side, pip)

    Returns:
        Path to final video

    Example:
        final = await composite_final_video(
            slides_video="/tmp/slides.mp4",
            audio_path="/tmp/audio.mp3",
            output_path="/tmp/final.mp4",
        )
    """
    from kagami_studio.production.compositor import composite_video

    result = await composite_video(
        slides_video=Path(slides_video),
        avatar_video=Path(avatar_video) if avatar_video else None,
        audio_path=Path(audio_path),
        subtitle_path=Path(subtitle_path) if subtitle_path else None,
        output_path=Path(output_path),
        layout=layout,
    )

    if not result.success:
        raise RuntimeError(f"Compositing failed: {result.error}")

    return result.output_path


# === DESIGN SYSTEM ACCESS ===
# For programmatic access to CSS variables and patterns


def get_design_system() -> dict[str, Any]:
    """Get design system CSS variables and patterns.

    Returns a dictionary with all design tokens from design_system.css.

    Returns:
        Dictionary with keys:
            - timing: Fibonacci durations
            - spacing: 8px grid values
            - colors: Text opacity tiers and accents
            - easing: Spring/expo curves
            - shadows: Depth system

    Example:
        ds = get_design_system()
        print(ds["timing"]["fibonacci"])  # [89, 144, 233, 377, 610, 987]
    """
    return {
        "timing": {
            "fibonacci": [89, 144, 233, 377, 610, 987, 1597, 2584],
            "instant": 0,
            "fast": 144,
            "normal": 233,
            "slow": 377,
            "slower": 610,
            "slowest": 987,
        },
        "spacing": {
            "grid": 8,  # Base unit in px
            "scale": [0, 8, 16, 24, 32, 40, 48, 64, 80, 96, 128],
        },
        "colors": {
            "text": {
                "primary": "rgba(244, 241, 234, 1.0)",  # 100%
                "secondary": "rgba(244, 241, 234, 0.65)",  # 65%
                "tertiary": "rgba(244, 241, 234, 0.35)",  # 35%
            },
            "accent": "#00f0ff",
            "gold": "#D4AF37",
        },
        "easing": {
            "spring": "cubic-bezier(0.34, 1.56, 0.64, 1)",
            "smooth": "cubic-bezier(0.16, 1, 0.3, 1)",
            "fold": "cubic-bezier(0.7, 0, 0.3, 1)",
            "cusp": "cubic-bezier(0.4, 0, 0.2, 1)",
        },
        "shadows": {
            "glow_accent": "0 0 30px rgba(0, 240, 255, 0.3)",
            "glow_gold": "0 0 30px rgba(212, 175, 55, 0.15)",
        },
    }


# === EXPORTS ===
__all__ = [
    "COLOR_PALETTES",
    "FIBONACCI_MS",
    "LAYOUT_METADATA",
    # Shot types (re-exported)
    "CameraAngle",
    # Shot planner
    "CoverageStrategy",
    "GradientPreset",
    # LLM slide generator
    "LLMSlideGenerator",
    # === NEW UNIFIED LAYOUTS ===
    "LayoutCategory",
    "LayoutConfig",
    "PlannedShot",
    # === NEW UNIFIED MODELS ===
    "Presentation",
    "PresentationPlan",
    # === TOPIC-BASED GENERATION (THE entry point) ===
    "PresentationTone",
    "ProductionPlan",
    # Result types
    "ProductionResult",
    # Script types (re-exported)
    "ProductionScript",
    "ScriptSlide",
    "ShotPlanner",
    "ShotType",
    "SlideContent",
    "SlideContentDesign",
    "SlideDesign",
    # Design system (Gamma-style)
    "SlideLayout",
    "SlideLayoutType",
    "SlideTiming",
    "SpeakerContext",
    "VisualSeed",
    "WordTiming",
    "composite_final_video",
    # Script export functions
    "export_script_markdown",
    "export_script_pdf",
    "generate_css",
    "generate_presentation",
    "generate_presentation_from_topic",
    "generate_script_from_topic",
    "generate_slide_deck_html",
    "generate_slide_html",
    "get_design_system",
    "get_image_layouts",
    "get_layout_config",
    "get_ted_style_layouts",
    "list_available_speakers",
    "list_coverage_strategies",
    "load_speaker_context",
    "load_visual_seed",
    "plan_production",
    # Main function
    "produce_video",
    "quick_video",
    # === NEW HTML RENDERER ===
    "render_presentation_html",
    "render_slide_deck",
    "render_slide_html",
    "render_slide_image",
    "render_ted_style_video",
    # === COMPOSABLE PRIMITIVES ===
    "synthesize_speech",
]
