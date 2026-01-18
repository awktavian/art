"""Slide Video Renderer — Audio-Synced Real-time Recording.

ARCHITECTURE:
1. Generate HTML with slides, Ken Burns animation, and kinetic subtitles
2. Play AUDIO through the browser while recording
3. JavaScript syncs to audio.currentTime (not performance.now())
4. Record everything together = PERFECT sync

This captures ALL animations AND maintains perfect AV sync:
- Slide transitions sync to audio
- Kinetic subtitles sync to audio
- Ken Burns image animation
- Shimmer/particle effects

This is the CANONICAL slide renderer.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import aiohttp

if TYPE_CHECKING:
    from kagami_studio.production.models import Presentation
    from kagami_studio.production.script import ProductionScript, WordTiming

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("/tmp/kagami_slides")


async def render_slides_to_video(
    script: ProductionScript,
    slide_timings: list[dict],
    output_path: Path | str,
    word_timings: list[WordTiming] | None = None,
    audio_path: Path | str | None = None,  # Audio for duration calculation
    resolution: tuple[int, int] = (1920, 1080),
    generate_images: bool = False,
    theme: str = "dark_blue",
    accent_color: str = "4a9eff",
    use_llm: bool = True,
    speaker: str = "tim",
    reuse_images: bool = True,
    render_html_subtitles: bool = True,  # NEW: Enable/disable HTML kinetic subtitles
) -> Path:
    """Render slides to video using Playwright recording.

    TIMING ARCHITECTURE:
    1. HTML playback runs at 1:1 real-time using performance.now()
    2. Playwright records video (may have variable frame rate)
    3. FFmpeg stretches/compresses video to match audio duration EXACTLY
    4. This guarantees slide transitions align with audio

    SUBTITLE SYNC:
    - render_html_subtitles=True: Kinetic subtitles baked into video (may drift)
    - render_html_subtitles=False: Use ASS subtitles burned via FFmpeg (PERFECT sync)

    RECOMMENDED: Set render_html_subtitles=False and use burn_ass_subtitles=True
    in produce_video() for guaranteed perfect subtitle sync.

    Args:
        script: Production script with slide content
        slide_timings: List of {start_ms, end_ms, duration_s} for each slide
        output_path: Output video file path
        word_timings: Word-level timings for kinetic subtitles
        audio_path: Audio file for duration calculation and sync
        resolution: Video resolution (width, height)
        generate_images: Generate AI images for slides
        theme: Color theme preset
        accent_color: Accent color hex
        use_llm: Use LLM for slide design
        speaker: Speaker ID for voice/style
        reuse_images: Reuse cached images
        render_html_subtitles: Enable HTML kinetic subtitles (False for ASS-only)

    Returns:
        Path to rendered video file
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    from kagami_studio.production.slide_content import enhance_script_to_designs
    from kagami_studio.production.slide_design import (
        GradientPreset,
        generate_slide_deck_html,
    )

    # Convert script to slide dicts
    slide_dicts = [
        {
            "title": slide.title,
            "spoken": slide.spoken_text,
            "points": slide.points,
            "mood": slide.mood,
            "shot": slide.shot_type.value
            if hasattr(slide.shot_type, "value")
            else str(slide.shot_type),
        }
        for slide in script.slides
    ]

    # Get designs (generates hero images if needed)
    logger.info(f"🎨 Enhancing {len(slide_dicts)} slides...")
    try:
        theme_preset = (
            GradientPreset(theme)
            if theme in [g.value for g in GradientPreset]
            else GradientPreset.DARK_BLUE
        )
    except (ValueError, KeyError):
        theme_preset = GradientPreset.DARK_BLUE

    designs = await enhance_script_to_designs(
        slides=slide_dicts,
        theme=theme_preset,
        reuse_images=reuse_images,
        accent_color=accent_color,
        generate_images=generate_images,
        use_llm=use_llm,
        speaker=speaker,
    )

    # Generate HTML
    logger.info("📄 Generating audio-synced HTML deck...")
    html_content = generate_slide_deck_html(designs, resolution)

    # Inject timing data (skip word timings if HTML subtitles disabled)
    html_content = _inject_audio_sync(
        html_content,
        slide_timings,
        word_timings
        if render_html_subtitles
        else None,  # Skip word timings to disable HTML subtitles
        audio_path,
    )

    html_path = OUTPUT_DIR / "slides.html"
    html_path.write_text(html_content)

    # Calculate total duration from LAST SLIDE END TIME (includes gaps)
    # This is more accurate than summing durations which misses inter-slide pauses
    if slide_timings:
        last_slide_end_ms = max(t.get("end_ms", 0) for t in slide_timings)
        total_duration_ms = last_slide_end_ms + 1000  # Add 1s buffer for final slide
    else:
        total_duration_ms = 150000  # Fallback

    # If we have audio, use the LONGER of audio vs slide timings
    if audio_path and Path(audio_path).exists():
        probe_cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ]
        result = subprocess.run(probe_cmd, capture_output=True, text=True)
        if result.stdout.strip():
            audio_duration_ms = float(result.stdout.strip()) * 1000
            total_duration_ms = max(total_duration_ms, audio_duration_ms + 500)
            logger.info(f"  Audio duration: {audio_duration_ms / 1000:.1f}s")

    total_duration_s = total_duration_ms / 1000
    last_slide_end_s = last_slide_end_ms / 1000 if slide_timings else 0

    logger.info(
        f"🎬 Recording {total_duration_s:.1f}s (last slide ends at {last_slide_end_s:.1f}s)"
    )

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError(
            "Playwright required: pip install playwright && playwright install chromium"
        )

    # Store recording metadata for timing fix
    recording_info = {"start_time": 0, "end_time": 0}

    def _record_with_audio():
        import time as time_module

        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
            context = browser.new_context(
                viewport={"width": resolution[0], "height": resolution[1]},
                record_video_dir=str(OUTPUT_DIR),
                record_video_size={"width": resolution[0], "height": resolution[1]},
            )
            page = context.new_page()

            # Load HTML
            page.goto(f"file://{html_path}")
            page.wait_for_load_state("networkidle")

            # === CRITICAL SYNC APPROACH ===
            # Recording starts NOW (Playwright starts recording on page creation)
            # We track wallclock time to know actual recording duration

            page.wait_for_timeout(50)  # Let recording stabilize

            # Start playback and track wallclock time
            recording_info["start_time"] = time_module.time()
            page.evaluate("window.startPlayback()")

            # Wait for content duration + buffer (extra 10% for safety)
            wait_ms = int(total_duration_ms * 1.1 + 500)
            logger.info(f"  Recording {wait_ms / 1000:.1f}s...")
            page.wait_for_timeout(wait_ms)

            recording_info["end_time"] = time_module.time()
            actual_duration = recording_info["end_time"] - recording_info["start_time"]
            logger.debug(f"  Actual wallclock: {actual_duration:.1f}s")

            # Stop
            page.evaluate("window.stopPlayback()")
            page.wait_for_timeout(50)

            page.close()
            context.close()
            browser.close()

    await asyncio.to_thread(_record_with_audio)

    # Find recorded video
    recorded_videos = list(OUTPUT_DIR.glob("*.webm"))
    if not recorded_videos:
        raise RuntimeError("No video recorded by Playwright")

    recorded_video = max(recorded_videos, key=lambda p: p.stat().st_mtime)
    logger.info(f"  Recorded: {recorded_video}")

    # Re-encode to H.264 with ULTIMATE QUALITY
    # CRITICAL: Stretch/compress video to match audio duration for perfect sync
    logger.info("🔄 Re-encoding to H.264 with timing correction...")

    # Get recorded video duration
    probe_cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(recorded_video),
    ]
    result = subprocess.run(probe_cmd, capture_output=True, text=True)
    recorded_duration = float(result.stdout.strip()) if result.stdout.strip() else total_duration_s

    # Get target audio duration
    if audio_path and Path(audio_path).exists():
        probe_cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ]
        result = subprocess.run(probe_cmd, capture_output=True, text=True)
        target_duration = (
            float(result.stdout.strip()) if result.stdout.strip() else total_duration_s
        )
    else:
        target_duration = total_duration_s

    # Calculate time stretch factor
    # If video is shorter than audio, we need to STRETCH it (setpts > 1)
    # If video is longer than audio, we need to COMPRESS it (setpts < 1)
    stretch_factor = target_duration / recorded_duration

    logger.info(
        f"  Recorded: {recorded_duration:.1f}s, Target: {target_duration:.1f}s, Stretch: {stretch_factor:.3f}x"
    )

    # Build FFmpeg command with timing correction
    if abs(stretch_factor - 1.0) > 0.01:  # More than 1% difference
        # Use setpts filter to stretch/compress video
        setpts = f"setpts={stretch_factor}*PTS"
        filter_complex = f"[0:v]{setpts}[v]"

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(recorded_video),
            "-filter_complex",
            filter_complex,
            "-map",
            "[v]",
            "-t",
            str(target_duration),  # Ensure exact duration
            "-c:v",
            "libx264",
            "-preset",
            "medium",  # Faster for re-render
            "-crf",
            "12",
            "-tune",
            "animation",
            "-profile:v",
            "high",
            "-pix_fmt",
            "yuv420p",
            "-color_primaries",
            "bt709",
            "-color_trc",
            "bt709",
            "-colorspace",
            "bt709",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    else:
        # No stretching needed, just re-encode
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(recorded_video),
            "-t",
            str(target_duration),
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryslow",
            "-crf",
            "6",
            "-tune",
            "animation",
            "-profile:v",
            "high444",
            "-level",
            "5.2",
            "-pix_fmt",
            "yuv444p",
            "-color_primaries",
            "bt709",
            "-color_trc",
            "bt709",
            "-colorspace",
            "bt709",
            "-movflags",
            "+faststart",
            "-x264-params",
            "ref=16:bframes=8:b-adapt=2:direct=auto:me=umh:subme=10:trellis=2:deblock=-1,-1",
            str(output_path),
        ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        logger.error(f"FFmpeg failed: {result.stderr}")
        raise RuntimeError(f"FFmpeg failed: {result.stderr[:500]}")

    # Clean up temp WebM
    recorded_video.unlink(missing_ok=True)

    if output_path.exists():
        size = output_path.stat().st_size / (1024 * 1024)
        logger.info(f"✓ Video: {output_path} ({size:.1f}MB, {total_duration_s:.1f}s)")

    return output_path


def _inject_audio_sync(
    html: str,
    slide_timings: list[dict],
    word_timings: list | None,
    audio_path: Path | str | None,
) -> str:
    """Inject audio element and sync logic into HTML.

    KEY: JavaScript syncs to audio.currentTime, NOT performance.now().
    This guarantees perfect sync because everything references the same clock.
    """

    # Embed audio as base64 data URI (avoids file:// issues)
    audio_data_uri = ""
    if audio_path and Path(audio_path).exists():
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
        # Detect format
        ext = Path(audio_path).suffix.lower()
        mime = "audio/mpeg" if ext == ".mp3" else "audio/wav" if ext == ".wav" else "audio/mp4"
        audio_data_uri = f"data:{mime};base64,{audio_b64}"

    # Convert timings to JSON
    slide_json = json.dumps(
        [
            {
                "start_ms": t.get("start_ms", 0),
                "end_ms": t.get("end_ms", t.get("start_ms", 0) + t.get("duration_s", 3) * 1000),
            }
            for t in slide_timings
        ]
    )

    word_json = "[]"
    if word_timings:
        word_json = json.dumps(
            [{"text": w.text, "start_ms": w.start_ms, "end_ms": w.end_ms} for w in word_timings]
        )

    # Create audio element HTML
    audio_html = ""
    if audio_data_uri:
        audio_html = f'''
    <!-- EMBEDDED AUDIO FOR SYNC -->
    <audio id="sync-audio" preload="auto" style="display:none;">
        <source src="{audio_data_uri}" type="audio/mpeg">
    </audio>
'''

    # Inject timing data and audio sync JavaScript
    # Replace the variable declarations in the script

    # First, inject the slide timings
    html = html.replace(
        "window.slideTimings = []; // Set from Python",
        f"window.slideTimings = {slide_json}; // Injected from Python",
    )

    # Then inject word timings
    html = html.replace(
        "window.wordTimings = []; // Set from Python - word-by-word timing",
        f"window.wordTimings = {word_json}; // Injected from Python",
    )

    # Now inject the audio sync functions BEFORE the closing </script> tag
    audio_sync_js = """
        // === AUDIO-SYNCED PLAYBACK (Injected) ===
        const syncAudio = document.getElementById('sync-audio');
        let isAudioPlaying = false;

        // Get current time from AUDIO (the source of truth)
        function getAudioTimeMs() {
            if (syncAudio && !syncAudio.paused) {
                return syncAudio.currentTime * 1000;
            }
            return window.currentTimeMs || 0;
        }

        // Audio-synced playback loop
        function audioSyncLoop() {
            if (!isAudioPlaying) return;

            window.currentTimeMs = getAudioTimeMs();
            window.updateSlide();
            window.updateSubtitles();

            requestAnimationFrame(audioSyncLoop);
        }

        // Start with audio playback
        window.startAudioPlayback = function() {
            isAudioPlaying = true;
            if (syncAudio) {
                syncAudio.currentTime = 0;
                syncAudio.play().then(() => {
                    console.log('Audio playback started');
                    audioSyncLoop();
                }).catch(e => {
                    console.warn('Audio autoplay blocked:', e);
                    // Fallback to timer-based
                    window.startPlayback();
                });
            } else {
                console.log('No audio element, using timer');
                window.startPlayback();
            }
        };

        // Override stopPlayback to also stop audio
        const originalStopPlayback = window.stopPlayback;
        window.stopPlayback = function() {
            isAudioPlaying = false;
            if (syncAudio) {
                syncAudio.pause();
            }
            if (originalStopPlayback) {
                originalStopPlayback();
            }
        };
    """

    # Insert before </script>
    html = html.replace("</script>\n</body>", f"{audio_sync_js}\n    </script>\n</body>")

    # Insert audio element before slides container
    if audio_html:
        html = html.replace(
            '<div id="slides-container">', f'{audio_html}\n    <div id="slides-container">'
        )

    return html


async def animate_slide_images(
    image_paths: list[Path],
    prompts: list[str],
    output_dir: Path,
    duration: int = 5,
) -> list[Path]:
    """Animate static images using Runway Gen-3.

    Takes hero images and creates subtle motion videos (Ken Burns, parallax).
    """
    api_key = os.getenv("RUNWAY_API_KEY")
    if not api_key:
        logger.warning("RUNWAY_API_KEY not set - using static images")
        return image_paths

    from kagami_studio.generation.video import VideoGenerator

    generator = VideoGenerator(api_key)
    output_dir.mkdir(parents=True, exist_ok=True)

    animated_paths = []

    for i, (img_path, prompt) in enumerate(zip(image_paths, prompts, strict=False)):
        try:
            logger.info(f"🎬 Animating image {i + 1}/{len(image_paths)}: {img_path.name}")

            motion_prompt = f"{prompt}, subtle camera motion, cinematic, smooth, looping"
            job_id = await generator.generate(
                prompt=motion_prompt,
                duration=duration,
                image_url=str(img_path),
            )

            video_url = await generator.wait_for_completion(job_id, timeout=300)

            output_path = output_dir / f"animated_{i:03d}.mp4"
            async with aiohttp.ClientSession() as session:
                async with session.get(video_url) as resp:
                    with open(output_path, "wb") as f:
                        f.write(await resp.read())

            animated_paths.append(output_path)
            logger.info(f"  ✓ Animated: {output_path}")

        except Exception as e:
            logger.warning(f"  ⚠ Animation failed: {e} - using static image")
            animated_paths.append(img_path)

    await generator.close()
    return animated_paths


async def create_green_screen_composite(
    foreground_video: Path,
    background_video: Path,
    output_path: Path,
    chroma_color: str = "00FF00",
    similarity: float = 0.3,
    blend: float = 0.1,
) -> Path:
    """Composite foreground over background with chromakey."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(background_video),
        "-i",
        str(foreground_video),
        "-filter_complex",
        f"[1:v]chromakey=0x{chroma_color}:similarity={similarity}:blend={blend}[fg];"
        f"[0:v][fg]overlay=format=auto[out]",
        "-map",
        "[out]",
        "-map",
        "0:a?",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "12",
        "-pix_fmt",
        "yuv420p",
        str(output_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"Chromakey failed: {result.stderr[:500]}")

    logger.info(f"✓ Green screen composite: {output_path}")
    return output_path


async def render_ted_style_video(
    presentation: Presentation,
    image_paths: dict[int, Path],
    slide_timings: list[dict],
    audio_path: Path,
    output_path: Path,
    resolution: tuple[int, int] = (1920, 1080),
) -> Path:
    """Render a TED-style presentation to video.

    Uses the new html_renderer for modern TED-style layouts.

    Args:
        presentation: Presentation model with slides
        image_paths: Dict mapping slide index to hero image path
        slide_timings: List of timing dicts with start_ms/end_ms
        audio_path: Path to audio file
        output_path: Output video path
        resolution: Video resolution

    Returns:
        Path to rendered video
    """
    from kagami_studio.production.html_renderer import render_presentation_html

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Generate HTML
    html = render_presentation_html(
        presentation=presentation,
        image_paths=image_paths,
        slide_timings=slide_timings,
        audio_path=audio_path,
    )

    html_path = OUTPUT_DIR / "ted_slides.html"
    html_path.write_text(html)

    # Get total duration
    if slide_timings:
        last_end = max(t.get("end_ms", 0) for t in slide_timings)
        total_duration_s = (last_end + 1000) / 1000
    else:
        total_duration_s = 120.0

    logger.info(f"🎬 Recording TED-style video: {total_duration_s:.1f}s")

    # Record with Playwright
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError(
            "Playwright required: pip install playwright && playwright install chromium"
        )

    recording_path = None

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
        context = browser.new_context(
            viewport={"width": resolution[0], "height": resolution[1]},
            record_video_dir=str(OUTPUT_DIR),
            record_video_size={"width": resolution[0], "height": resolution[1]},
        )
        page = context.new_page()

        page.goto(f"file://{html_path}")
        page.wait_for_load_state("networkidle")

        # Start playback
        page.evaluate("document.getElementById('sync-audio').play()")

        # Wait for duration
        page.wait_for_timeout(int(total_duration_s * 1000) + 500)

        page.close()
        recording_path = context.pages[0].video.path() if context.pages else None
        context.close()
        browser.close()

    if not recording_path or not Path(recording_path).exists():
        raise RuntimeError("Recording failed")

    # Mux with audio
    temp_video = OUTPUT_DIR / "ted_recorded.webm"
    shutil.move(recording_path, temp_video)

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(temp_video),
        "-i",
        str(audio_path),
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "18",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed: {result.stderr[:500]}")

    logger.info(f"✓ TED-style video: {output_path}")
    return output_path


__all__ = [
    "animate_slide_images",
    "create_green_screen_composite",
    "render_slides_to_video",
    "render_ted_style_video",
]
