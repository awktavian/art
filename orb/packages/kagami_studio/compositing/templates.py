"""Compositing Templates — Pre-built composition layouts.

Templates define the structure and positioning for common
composition patterns. Each template encapsulates:
- Layer positions and scales
- Effect settings
- Audio mixing rules

Usage:
    from kagami_studio.compositing import DCCTemplate, PIPTemplate

    # DCC documentary style
    template = DCCTemplate(
        video_width_ratio=0.65,
        style="cinematic",
    )

    # Apply to engine
    result = await engine.composite(
        background=video,
        output=output,
        template=template,
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DCCTemplate:
    """DCC (Dallas Cowboys Cheerleaders) documentary template.

    Inspired by the Netflix documentary style:
    - Video panel on left (talking head)
    - Text/quote panel on right
    - Word-by-word reveal with emotion effects
    - Starfield background
    """

    video_width_ratio: float = 0.65
    style: str = "dcc"  # dcc, cinematic, minimal

    # Colors
    bg_color: str = "#0a0908"
    accent_color: str = "#d4af37"  # Gold
    text_color: str = "#f5f5f5"

    # Typography
    font_family: str = "Playfair Display"
    title_size: str = "clamp(2rem, 5vw, 4rem)"
    quote_size: str = "clamp(1.1rem, 2.2vw, 1.6rem)"

    # Effects
    glassmorphism: bool = True
    starfield: bool = True
    word_emotions: bool = True

    # Transition timing (ms)
    fade_in: int = 500
    word_reveal_delay: int = 50

    def to_config(self) -> dict:
        """Convert to template config dict."""
        return {
            "video_ratio": self.video_width_ratio,
            "style": self.style,
            "colors": {
                "bg": self.bg_color,
                "accent": self.accent_color,
                "text": self.text_color,
            },
            "typography": {
                "family": self.font_family,
                "title_size": self.title_size,
                "quote_size": self.quote_size,
            },
            "effects": {
                "glassmorphism": self.glassmorphism,
                "starfield": self.starfield,
                "word_emotions": self.word_emotions,
            },
            "timing": {
                "fade_in": self.fade_in,
                "word_reveal_delay": self.word_reveal_delay,
            },
        }


@dataclass
class PIPTemplate:
    """Picture-in-picture template.

    Overlay source positioned in corner of main source.
    """

    corner: str = "bottom-right"  # top-left, top-right, bottom-left, bottom-right
    scale: float = 0.3  # Overlay size as fraction of canvas
    margin: int = 40  # Pixels from edge

    # Effects
    glassmorphism: bool = True
    glassmorphism_blur: int = 20
    border_width: int = 3
    border_color: str = "white"
    border_opacity: float = 0.6

    # Shape
    rounded_corners: int = 12  # Border radius
    circular: bool = False  # Circular mask

    # Animation
    animate_in: bool = False
    animate_type: str = "slide"  # slide, fade, scale

    def to_config(self) -> dict:
        """Convert to template config dict."""
        return {
            "corner": self.corner,
            "scale": self.scale,
            "margin": self.margin,
            "glassmorphism": self.glassmorphism,
            "glassmorphism_blur": self.glassmorphism_blur,
            "border_width": self.border_width,
            "border_color": self.border_color,
            "border_opacity": self.border_opacity,
            "rounded_corners": self.rounded_corners,
            "circular": self.circular,
            "animate_in": self.animate_in,
            "animate_type": self.animate_type,
        }


@dataclass
class SplitTemplate:
    """Split screen template.

    Two sources side-by-side or top/bottom.
    """

    direction: str = "vertical"  # vertical (side-by-side), horizontal (top/bottom)
    ratio: float = 0.5  # Split position
    gap: int = 10  # Gap between panels

    # Diagonal split
    diagonal: bool = False
    diagonal_angle: float = 15  # Degrees

    # Labels
    labels: list[str] = field(default_factory=list)  # ["Left", "Right"]
    label_position: str = "bottom"  # top, bottom
    label_style: str = "minimal"  # minimal, badge, none

    def to_config(self) -> dict:
        """Convert to template config dict."""
        return {
            "direction": self.direction,
            "ratio": self.ratio,
            "gap": self.gap,
            "diagonal": self.diagonal,
            "diagonal_angle": self.diagonal_angle,
            "labels": self.labels,
            "label_position": self.label_position,
            "label_style": self.label_style,
        }


@dataclass
class InterviewTemplate:
    """Interview/podcast layout template.

    Two cameras for host and guest, optional background.
    """

    layout: str = "side_by_side"  # side_by_side, stacked, asymmetric

    # Host settings (typically left/larger)
    host_scale: float = 0.55
    host_position: tuple[float, float] = (0.05, 0.1)  # Normalized

    # Guest settings (typically right/smaller)
    guest_scale: float = 0.45
    guest_position: tuple[float, float] = (0.52, 0.1)

    # Background
    background_blur: int = 0  # 0 = no blur
    background_dim: float = 0.0  # 0-1 dimming

    # Names
    show_names: bool = True
    name_style: str = "lower_third"  # lower_third, badge, floating
    host_name: str = ""
    guest_name: str = ""

    def to_config(self) -> dict:
        """Convert to template config dict."""
        return {
            "layout": self.layout,
            "host": {
                "scale": self.host_scale,
                "position": self.host_position,
                "name": self.host_name,
            },
            "guest": {
                "scale": self.guest_scale,
                "position": self.guest_position,
                "name": self.guest_name,
            },
            "background": {
                "blur": self.background_blur,
                "dim": self.background_dim,
            },
            "names": {
                "show": self.show_names,
                "style": self.name_style,
            },
        }


@dataclass
class StreamingTemplate:
    """Streaming overlay template.

    For live streaming with alerts, chat, and camera.
    """

    # Camera position
    camera_corner: str = "bottom-right"
    camera_scale: float = 0.25
    camera_circular: bool = True
    camera_border: bool = True

    # Alerts
    alert_position: str = "top-center"
    alert_animation: str = "slide_down"

    # Chat
    chat_enabled: bool = True
    chat_position: str = "left"
    chat_width: float = 0.25
    chat_opacity: float = 0.8

    # Goals/events
    event_bar_enabled: bool = False
    event_bar_position: str = "top"

    # Branding
    logo_position: str = "top-left"
    logo_scale: float = 0.1

    def to_config(self) -> dict:
        """Convert to template config dict."""
        return {
            "camera": {
                "corner": self.camera_corner,
                "scale": self.camera_scale,
                "circular": self.camera_circular,
                "border": self.camera_border,
            },
            "alerts": {
                "position": self.alert_position,
                "animation": self.alert_animation,
            },
            "chat": {
                "enabled": self.chat_enabled,
                "position": self.chat_position,
                "width": self.chat_width,
                "opacity": self.chat_opacity,
            },
            "events": {
                "enabled": self.event_bar_enabled,
                "position": self.event_bar_position,
            },
            "branding": {
                "logo_position": self.logo_position,
                "logo_scale": self.logo_scale,
            },
        }
