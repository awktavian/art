"""OBS Source Types — Input source definitions and factories.

Provides typed source creation for common OBS source types:
- Browser sources (web pages, overlays)
- Video sources (files, streams)
- Image sources (static images)
- Media sources (audio/video files)
- Camera sources (webcams, capture cards)
- Screen capture sources
- NDI sources

Usage:
    from kagami_studio.obs import OBSController
    from kagami_studio.obs.sources import create_browser_source

    async with connect_obs() as obs:
        # Create browser source with HTML overlay
        settings = create_browser_source(
            url="http://localhost:8080/overlay.html",
            width=1920,
            height=1080,
        )
        await obs.add_source("MyOverlay", "browser_source", settings)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class OBSSourceType(str, Enum):
    """OBS source type identifiers."""

    # Video inputs
    BROWSER = "browser_source"
    MEDIA = "ffmpeg_source"
    VLC = "vlc_source"
    IMAGE = "image_source"
    SLIDESHOW = "slideshow"

    # Capture
    SCREEN = "screen_capture"
    WINDOW = "window_capture"
    GAME = "game_capture"
    CAMERA = "av_capture_input"  # macOS
    V4L2 = "v4l2_input"  # Linux

    # Audio
    AUDIO_INPUT = "coreaudio_input_capture"  # macOS
    AUDIO_OUTPUT = "coreaudio_output_capture"  # macOS
    WASAPI_INPUT = "wasapi_input_capture"  # Windows
    WASAPI_OUTPUT = "wasapi_output_capture"  # Windows

    # Network
    NDI = "obs_ndi_source"
    SRT = "ffmpeg_source"

    # Virtual
    COLOR = "color_source"
    TEXT = "text_ft2_source"
    TEXT_GDI = "text_gdiplus"


@dataclass
class OBSSourceSettings:
    """Base settings for OBS sources."""

    settings: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to OBS settings dict."""
        return self.settings


@dataclass
class OBSSource:
    """OBS source definition."""

    name: str
    kind: OBSSourceType
    settings: dict = field(default_factory=dict)
    scene_item_id: int | None = None
    visible: bool = True

    # Transform
    position: tuple[float, float] = (0, 0)
    scale: tuple[float, float] = (1.0, 1.0)
    rotation: float = 0.0
    crop: dict = field(default_factory=dict)


# =============================================================================
# SOURCE FACTORIES
# =============================================================================


def create_browser_source(
    url: str,
    width: int = 1920,
    height: int = 1080,
    css: str = "",
    shutdown_when_hidden: bool = True,
    restart_when_active: bool = True,
    fps: int = 30,
    reroute_audio: bool = True,
) -> dict:
    """Create browser source settings.

    Browser sources render web pages in OBS. Perfect for:
    - Overlays (alerts, chat, etc.)
    - Dynamic graphics
    - Local HTML files
    - Web-based tools

    Args:
        url: Web URL or file:// URL
        width: Render width
        height: Render height
        css: Custom CSS to inject
        shutdown_when_hidden: Shutdown browser when not visible
        restart_when_active: Restart when becoming visible
        fps: Target frame rate
        reroute_audio: Capture audio from browser

    Returns:
        Settings dict for browser_source
    """
    return {
        "url": url,
        "width": width,
        "height": height,
        "css": css,
        "shutdown": shutdown_when_hidden,
        "restart_when_active": restart_when_active,
        "fps": fps,
        "reroute_audio": reroute_audio,
    }


def create_video_source(
    path: str | Path,
    loop: bool = True,
    restart_on_activate: bool = True,
    hw_decode: bool = True,
    close_when_inactive: bool = True,
) -> dict:
    """Create video/media source settings.

    Args:
        path: Path to video file
        loop: Whether to loop
        restart_on_activate: Restart when scene activates
        hw_decode: Use hardware decoding
        close_when_inactive: Close file when not visible

    Returns:
        Settings dict for ffmpeg_source
    """
    return {
        "local_file": str(path),
        "looping": loop,
        "restart_on_activate": restart_on_activate,
        "hw_decode": hw_decode,
        "close_when_inactive": close_when_inactive,
    }


def create_image_source(
    path: str | Path,
    unload_when_hidden: bool = True,
) -> dict:
    """Create image source settings.

    Args:
        path: Path to image file
        unload_when_hidden: Unload image when not visible

    Returns:
        Settings dict for image_source
    """
    return {
        "file": str(path),
        "unload": unload_when_hidden,
    }


def create_media_source(
    path: str | Path,
    loop: bool = False,
    restart_on_activate: bool = True,
    hw_decode: bool = True,
    buffering_mb: int = 2,
    speed_percent: int = 100,
) -> dict:
    """Create media source settings (for playback control).

    Similar to video source but with more playback options.

    Args:
        path: Path to media file
        loop: Whether to loop
        restart_on_activate: Restart when scene activates
        hw_decode: Use hardware decoding
        buffering_mb: Buffering size in MB
        speed_percent: Playback speed (100 = normal)

    Returns:
        Settings dict for ffmpeg_source
    """
    return {
        "local_file": str(path),
        "looping": loop,
        "restart_on_activate": restart_on_activate,
        "hw_decode": hw_decode,
        "buffering_mb": buffering_mb,
        "speed_percent": speed_percent,
    }


def create_color_source(
    color: int = 0xFF000000,
    width: int = 1920,
    height: int = 1080,
) -> dict:
    """Create solid color source.

    Args:
        color: Color in ABGR format (0xAABBGGRR)
        width: Width
        height: Height

    Returns:
        Settings dict for color_source
    """
    return {
        "color": color,
        "width": width,
        "height": height,
    }


def create_text_source(
    text: str,
    font: dict | None = None,
    color: int = 0xFFFFFFFF,
    outline: bool = False,
    outline_color: int = 0xFF000000,
    outline_size: int = 2,
    vertical: bool = False,
    custom_width: int = 0,
    word_wrap: bool = False,
) -> dict:
    """Create text source.

    Args:
        text: Text content
        font: Font dict with 'face', 'size', 'style', etc.
        color: Text color (ABGR)
        outline: Enable outline
        outline_color: Outline color
        outline_size: Outline thickness
        vertical: Vertical text
        custom_width: Custom width (0 = auto)
        word_wrap: Enable word wrap

    Returns:
        Settings dict for text source
    """
    settings = {
        "text": text,
        "color": color,
        "outline": outline,
        "outline_color": outline_color,
        "outline_size": outline_size,
        "vertical": vertical,
        "custom_width": custom_width,
        "word_wrap": word_wrap,
    }

    if font:
        settings["font"] = {
            "face": font.get("face", "Arial"),
            "size": font.get("size", 64),
            "style": font.get("style", "Regular"),
            "flags": font.get("flags", 0),
        }

    return settings


def create_ndi_source(
    ndi_source_name: str,
    bandwidth: str = "highest",
    color_range: str = "partial",
    latency: str = "normal",
    audio: bool = True,
) -> dict:
    """Create NDI source settings.

    NDI (Network Device Interface) allows high-quality,
    low-latency video over network.

    Args:
        ndi_source_name: NDI source name on network
        bandwidth: 'highest', 'lowest', or 'audio_only'
        color_range: 'full' or 'partial'
        latency: 'normal' or 'low'
        audio: Include audio

    Returns:
        Settings dict for obs_ndi_source
    """
    return {
        "ndi_source_name": ndi_source_name,
        "bandwidth": bandwidth,
        "color_range": color_range,
        "latency": latency,
        "audio": audio,
    }


def create_screen_capture_source(
    display: int = 0,
    show_cursor: bool = True,
    crop_mode: str = "none",
) -> dict:
    """Create screen capture source.

    Args:
        display: Display index
        show_cursor: Show cursor
        crop_mode: 'none', 'manual', 'to_window'

    Returns:
        Settings dict for screen_capture
    """
    return {
        "display": display,
        "show_cursor": show_cursor,
        "crop_mode": crop_mode,
    }


def create_camera_source_macos(
    device: str = "",
    preset: str = "AVCaptureSessionPresetHigh",
    use_buffering: bool = True,
    buffered_frames: int = 3,
) -> dict:
    """Create camera source for macOS.

    Args:
        device: Device UUID (empty = default)
        preset: Quality preset
        use_buffering: Enable buffering
        buffered_frames: Number of buffered frames

    Returns:
        Settings dict for av_capture_input
    """
    return {
        "device": device,
        "preset": preset,
        "use_buffering": use_buffering,
        "buffered_frames": buffered_frames,
    }


def create_srt_source(
    url: str,
    latency: int = 120,
    passphrase: str = "",
) -> dict:
    """Create SRT (Secure Reliable Transport) source.

    Args:
        url: SRT URL (srt://host:port)
        latency: Target latency in ms
        passphrase: Encryption passphrase

    Returns:
        Settings dict for SRT via ffmpeg_source
    """
    srt_url = url
    if latency:
        srt_url += f"?latency={latency * 1000}"  # Convert to microseconds
    if passphrase:
        srt_url += f"&passphrase={passphrase}"

    return {
        "input": srt_url,
        "is_local_file": False,
        "hw_decode": True,
    }


def create_rtmp_source(
    url: str,
    hw_decode: bool = True,
    buffering_mb: int = 2,
) -> dict:
    """Create RTMP source.

    Args:
        url: RTMP URL
        hw_decode: Use hardware decoding
        buffering_mb: Buffering size

    Returns:
        Settings dict for ffmpeg_source
    """
    return {
        "input": url,
        "is_local_file": False,
        "hw_decode": hw_decode,
        "buffering_mb": buffering_mb,
    }


def create_slideshow_source(
    files: list[str | Path],
    slide_time: int = 5000,
    transition: str = "fade",
    transition_speed: int = 700,
    loop: bool = True,
    randomize: bool = False,
) -> dict:
    """Create slideshow source.

    Args:
        files: List of image paths
        slide_time: Time per slide in ms
        transition: Transition type ('cut', 'fade', 'swipe')
        transition_speed: Transition duration in ms
        loop: Loop slideshow
        randomize: Randomize order

    Returns:
        Settings dict for slideshow
    """
    return {
        "files": [{"value": str(f), "selected": True, "hidden": False} for f in files],
        "slide_time": slide_time,
        "transition": transition,
        "transition_speed": transition_speed,
        "loop": loop,
        "randomize": randomize,
    }
