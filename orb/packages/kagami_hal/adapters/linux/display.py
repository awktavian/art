"""Linux Display Adapter.

Implements display output for Linux via:
- Framebuffer (/dev/fb0) for direct hardware access
- X11 for desktop environments
- Wayland detection

Created: December 15, 2025
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Any

from kagami.core.boot_mode import is_test_mode

from kagami_hal.data_types import DisplayInfo, DisplayMode

logger = logging.getLogger(__name__)

# Lazy display availability checks (cached after first call)
_framebuffer_available_cache: bool | None = None
_x11_available_cache: bool | None = None
_wayland_available_cache: bool | None = None


def _check_framebuffer_available() -> bool:
    """Check framebuffer availability (lazy, cached)."""
    global _framebuffer_available_cache
    if _framebuffer_available_cache is None:
        _framebuffer_available_cache = Path("/dev/fb0").exists()
    return _framebuffer_available_cache


def _check_x11_available() -> bool:
    """Check X11 availability (lazy, cached)."""
    global _x11_available_cache
    if _x11_available_cache is None:
        _x11_available_cache = "DISPLAY" in os.environ
    return _x11_available_cache


def _check_wayland_available() -> bool:
    """Check Wayland availability (lazy, cached)."""
    global _wayland_available_cache
    if _wayland_available_cache is None:
        _wayland_available_cache = "WAYLAND_DISPLAY" in os.environ
    return _wayland_available_cache


class LinuxDisplay:
    """Linux display implementation.

    Supports:
    - Framebuffer (/dev/fb0) for embedded/direct access
    - X11 for desktop environments
    - Wayland detection (limited support)
    """

    def __init__(self) -> None:
        """Initialize display adapter."""
        self._initialized = False
        self._display_info: DisplayInfo | None = None
        self._mode = DisplayMode.FULL
        self._fb_device: Any = None
        self._display_backend: str | None = None

    async def initialize(self) -> bool:
        """Initialize display adapter."""
        # Determine available backend (lazy checks)
        if _check_x11_available():
            self._display_backend = "x11"
            return await self._initialize_x11()
        elif _check_wayland_available():
            self._display_backend = "wayland"
            return await self._initialize_wayland()
        elif _check_framebuffer_available():
            self._display_backend = "framebuffer"
            return await self._initialize_framebuffer()
        else:
            if is_test_mode():
                logger.info("No display backend available")
                return False
            raise RuntimeError(
                "No display backend available. Need X11, Wayland, or framebuffer (/dev/fb0)"
            )

    async def _initialize_x11(self) -> bool:
        """Initialize X11 display."""
        try:
            # Query display info using xrandr
            result = subprocess.run(
                ["xrandr", "--current"],
                capture_output=True,
                text=True,
                timeout=2,
            )

            if result.returncode != 0:
                logger.warning("xrandr failed, X11 may not be available")
                return False

            # Parse xrandr output for primary display
            lines = result.stdout.split("\n")
            for line in lines:
                if " connected" in line and "*" in line:
                    # Parse resolution like "1920x1080+0+0"
                    parts = line.split()
                    for part in parts:
                        if "x" in part and "+" in part:
                            resolution = part.split("+")[0]
                            width, height = map(int, resolution.split("x"))

                            # Extract refresh rate
                            refresh_rate = 60  # Default
                            for p in parts:
                                if "*" in p:
                                    try:
                                        refresh_rate = int(float(p.replace("*", "")))
                                    except ValueError:
                                        pass

                            self._display_info = DisplayInfo(
                                width=width,
                                height=height,
                                bpp=24,  # Assume 24-bit
                                refresh_rate=refresh_rate,
                                supports_aod=False,
                                supports_touch=False,
                            )
                            break

            if not self._display_info:
                # Fallback: use default resolution
                self._display_info = DisplayInfo(
                    width=1920,
                    height=1080,
                    bpp=24,
                    refresh_rate=60,
                    supports_aod=False,
                    supports_touch=False,
                )

            self._initialized = True
            logger.info(
                f"✅ X11 display initialized: "
                f"{self._display_info.width}x{self._display_info.height} "
                f"@ {self._display_info.refresh_rate}Hz"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to initialize X11 display: {e}", exc_info=True)
            return False

    async def _initialize_wayland(self) -> bool:
        """Initialize Wayland display.

        Note: Wayland support is limited. Most operations require compositor-specific APIs.
        """
        try:
            # Wayland doesn't have a standard query tool like xrandr
            # We'll use reasonable defaults
            self._display_info = DisplayInfo(
                width=1920,
                height=1080,
                bpp=24,
                refresh_rate=60,
                supports_aod=False,
                supports_touch=False,
            )

            self._initialized = True
            logger.info("✅ Wayland display initialized (limited support, using defaults)")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Wayland display: {e}", exc_info=True)
            return False

    async def _initialize_framebuffer(self) -> bool:
        """Initialize framebuffer display."""
        try:
            # Read framebuffer info from /sys
            fb_path = Path("/sys/class/graphics/fb0")

            if not fb_path.exists():
                raise RuntimeError("/sys/class/graphics/fb0 not found")

            # Read virtual resolution
            virtual_size_file = fb_path / "virtual_size"
            if virtual_size_file.exists():
                with open(virtual_size_file) as f:
                    width, height = map(int, f.read().strip().split(","))
            else:
                # Fallback to default
                width, height = 1920, 1080

            # Read bits per pixel
            bits_per_pixel_file = fb_path / "bits_per_pixel"
            if bits_per_pixel_file.exists():
                with open(bits_per_pixel_file) as f:
                    bpp = int(f.read().strip())
            else:
                bpp = 24

            self._display_info = DisplayInfo(
                width=width,
                height=height,
                bpp=bpp,
                refresh_rate=60,  # Default, hard to query for FB
                supports_aod=False,
                supports_touch=False,
            )

            self._initialized = True
            logger.info(
                f"✅ Framebuffer display initialized: "
                f"{self._display_info.width}x{self._display_info.height} "
                f"{self._display_info.bpp}bpp"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to initialize framebuffer: {e}", exc_info=True)
            return False

    async def get_info(self) -> DisplayInfo:
        """Get display capabilities."""
        if not self._initialized or not self._display_info:
            raise RuntimeError("Display not initialized")
        return self._display_info

    async def write_frame(self, buffer: bytes) -> None:
        """Write frame buffer to display.

        Args:
            buffer: Raw pixel data (format depends on display bpp)

        Note: Only supported for framebuffer backend.
        """
        if not self._initialized:
            raise RuntimeError("Display not initialized")

        if self._display_backend == "framebuffer":
            await self._write_framebuffer(buffer)
        else:
            logger.warning(f"write_frame not supported for {self._display_backend} backend")

    async def _write_framebuffer(self, buffer: bytes) -> None:
        """Write directly to framebuffer device."""
        try:
            with open("/dev/fb0", "wb") as fb:
                fb.write(buffer)
        except Exception as e:
            logger.error(f"Failed to write framebuffer: {e}")
            raise

    async def capture_screen(self) -> bytes | None:
        """Capture current screen content.

        Returns:
            Screenshot as PNG bytes, or None if not supported
        """
        if not self._initialized:
            raise RuntimeError("Display not initialized")

        if self._display_backend == "x11":
            return await self._capture_x11()
        else:
            logger.warning(f"capture_screen not supported for {self._display_backend} backend")
            return None

    async def _capture_x11(self) -> bytes | None:
        """Capture X11 screen using scrot or import."""
        try:
            import tempfile

            # Try scrot first
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = tmp.name

            try:
                subprocess.run(
                    ["scrot", tmp_path],
                    check=True,
                    timeout=2,
                    capture_output=True,
                )

                with open(tmp_path, "rb") as f:
                    return f.read()

            except (FileNotFoundError, subprocess.CalledProcessError):
                # Try imagemagick import
                subprocess.run(
                    ["import", "-window", "root", tmp_path],
                    check=True,
                    timeout=2,
                    capture_output=True,
                )

                with open(tmp_path, "rb") as f:
                    return f.read()

            finally:
                Path(tmp_path).unlink(missing_ok=True)

        except Exception as e:
            logger.error(f"Failed to capture screen: {e}")
            return None

    async def clear(self, color: int = 0x000000) -> None:
        """Clear display to color.

        Args:
            color: RGB color as 0xRRGGBB
        """
        if not self._initialized or not self._display_info:
            raise RuntimeError("Display not initialized")

        if self._display_backend == "framebuffer":
            # Create blank buffer
            width = self._display_info.width
            height = self._display_info.height
            bpp = self._display_info.bpp

            bytes_per_pixel = bpp // 8

            # Extract RGB
            r = (color >> 16) & 0xFF
            g = (color >> 8) & 0xFF
            b = color & 0xFF

            # Create buffer
            if bytes_per_pixel == 4:
                pixel = bytes([b, g, r, 0xFF])  # BGRA
            elif bytes_per_pixel == 3:
                pixel = bytes([b, g, r])  # BGR
            else:
                pixel = bytes([0] * bytes_per_pixel)

            buffer = pixel * (width * height)
            await self.write_frame(buffer)

    async def set_brightness(self, level: float) -> None:
        """Set display brightness.

        Args:
            level: Brightness 0.0-1.0
        """
        if not self._initialized:
            raise RuntimeError("Display not initialized")

        # Try to set brightness via sysfs
        brightness_paths = [
            Path("/sys/class/backlight/intel_backlight/brightness"),
            Path("/sys/class/backlight/acpi_video0/brightness"),
        ]

        for brightness_path in brightness_paths:
            if brightness_path.exists():
                try:
                    # Read max brightness
                    max_brightness_path = brightness_path.parent / "max_brightness"
                    with open(max_brightness_path) as f:
                        max_brightness = int(f.read().strip())

                    # Calculate and set brightness
                    target_brightness = int(max_brightness * level)

                    with open(brightness_path, "w") as f:
                        f.write(str(target_brightness))

                    logger.debug(f"Brightness set to {level:.1%}")
                    return

                except OSError as e:
                    logger.warning(f"Cannot set brightness: {e}")
                    continue

        logger.warning("No accessible brightness control found")

    async def set_mode(self, mode: DisplayMode) -> None:
        """Set display power mode.

        Args:
            mode: Display mode (FULL, LOW_POWER, OFF)
        """
        self._mode = mode
        logger.debug(f"Display mode set to {mode.value}")

        # For X11, we can use xset to control DPMS
        if self._display_backend == "x11":
            try:
                if mode == DisplayMode.OFF:
                    subprocess.run(
                        ["xset", "dpms", "force", "off"],
                        timeout=1,
                        capture_output=True,
                    )
                else:
                    subprocess.run(
                        ["xset", "dpms", "force", "on"],
                        timeout=1,
                        capture_output=True,
                    )
            except Exception as e:
                logger.warning(f"Failed to set display mode: {e}")

    async def shutdown(self) -> None:
        """Shutdown display adapter."""
        self._initialized = False

        if self._fb_device:
            try:
                self._fb_device.close()
            except Exception:
                pass
            self._fb_device = None

        logger.info("✅ Linux display shutdown complete")


__all__ = ["LinuxDisplay"]
