"""Oelo Outdoor Lighting Integration.

Direct HTTP REST API for Oelo Evolution controllers.
Full pattern control with musical and design-driven presets.

API: GET /getController, GET /setPattern?...
No authentication required.

Created: December 29, 2025
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

import aiohttp

from kagami_smarthome.types import SmartHomeConfig

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Types
# =============================================================================


class OeloPattern(str, Enum):
    """Available Oelo patterns."""

    OFF = "off"
    STATIONARY = "stationary"
    MARCH = "march"
    BREATHE = "breathe"
    SPARKLE = "sparkle"
    TWINKLE = "twinkle"
    STROBE = "strobe"
    WAVE = "wave"
    RAINBOW = "rainbow"
    GRADIENT = "gradient"


class OeloHoliday(str, Enum):
    """Holiday preset modes."""

    CHRISTMAS = "christmas"
    HALLOWEEN = "halloween"
    VALENTINES = "valentines"
    PATRIOTIC = "patriotic"
    ST_PATRICKS = "st_patricks"
    EASTER = "easter"


class OeloState(str, Enum):
    """Oelo zone state."""

    OFF = "off"
    ON = "on"
    PATTERN = "pattern"


# =============================================================================
# Data Types
# =============================================================================


@dataclass
class OeloZone:
    """Zone state."""

    num: int
    name: str
    enabled: bool
    led_count: int
    is_on: bool
    pattern: str
    colors: str
    speed: int
    direction: str


@dataclass
class Color:
    """RGB color with helpers."""

    r: int
    g: int
    b: int

    @classmethod
    def from_hex(cls, hex_str: str) -> Color:
        """Create from hex string like '#ff0000' or 'ff0000'."""
        h = hex_str.lstrip("#")
        return cls(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

    @classmethod
    def from_hsv(cls, h: float, s: float, v: float) -> Color:
        """Create from HSV (h: 0-360, s: 0-1, v: 0-1)."""
        import colorsys

        r, g, b = colorsys.hsv_to_rgb(h / 360, s, v)
        return cls(int(r * 255), int(g * 255), int(b * 255))

    def __str__(self) -> str:
        return f"{self.r},{self.g},{self.b}"

    def dim(self, factor: float) -> Color:
        """Return dimmed color."""
        return Color(int(self.r * factor), int(self.g * factor), int(self.b * factor))


# Common colors
WHITE = Color(255, 255, 255)
WARM_WHITE = Color(255, 200, 150)
COOL_WHITE = Color(200, 220, 255)
RED = Color(255, 0, 0)
GREEN = Color(0, 255, 0)
BLUE = Color(0, 0, 255)
YELLOW = Color(255, 255, 0)
CYAN = Color(0, 255, 255)
MAGENTA = Color(255, 0, 255)
ORANGE = Color(255, 100, 0)
PURPLE = Color(128, 0, 255)
PINK = Color(255, 50, 200)


# =============================================================================
# Pattern Presets - Musical & Design Driven
# =============================================================================

PATTERNS = {
    # === Solid States ===
    "off": {"type": "off", "colors": [Color(0, 0, 0)], "speed": 0},
    "white": {"type": "stationary", "colors": [WHITE], "speed": 0},
    "warm": {"type": "stationary", "colors": [WARM_WHITE], "speed": 0},
    "cool": {"type": "stationary", "colors": [COOL_WHITE], "speed": 0},
    # === Seasonal ===
    "christmas": {
        "type": "march",
        "colors": [RED, GREEN, RED, GREEN, WHITE],
        "speed": 3,
    },
    "halloween": {
        "type": "twinkle",
        "colors": [ORANGE, PURPLE, ORANGE, Color(0, 0, 0)],
        "speed": 5,
    },
    "july4th": {
        "type": "chase",
        "colors": [RED, WHITE, BLUE, WHITE],
        "speed": 8,
    },
    "valentines": {
        "type": "fade",
        "colors": [RED, PINK, WHITE],
        "speed": 2,
    },
    "stpatricks": {
        "type": "river",
        "colors": [GREEN, Color(0, 200, 100), WHITE],
        "speed": 4,
    },
    "thanksgiving": {
        "type": "stationary",
        "colors": [ORANGE, Color(180, 80, 0), YELLOW],
        "speed": 0,
    },
    # === Musical Moods (tempo-inspired speeds) ===
    "adagio": {  # Slow, peaceful ~60 BPM
        "type": "fade",
        "colors": [BLUE, PURPLE, Color(50, 50, 100)],
        "speed": 1,
    },
    "andante": {  # Walking pace ~80 BPM
        "type": "river",
        "colors": [CYAN, BLUE, Color(100, 150, 255)],
        "speed": 3,
    },
    "allegro": {  # Fast, bright ~140 BPM
        "type": "chase",
        "colors": [YELLOW, ORANGE, WHITE],
        "speed": 10,
    },
    "presto": {  # Very fast ~180 BPM
        "type": "bolt",
        "colors": [WHITE, CYAN, WHITE],
        "speed": 18,
    },
    "crescendo": {  # Building intensity
        "type": "takeover",
        "colors": [Color(50, 0, 100), PURPLE, MAGENTA, WHITE],
        "speed": 6,
    },
    # === Ambient Moods ===
    "calm": {
        "type": "fade",
        "colors": [Color(100, 150, 200), Color(150, 180, 220)],
        "speed": 1,
    },
    "energy": {
        "type": "streak",
        "colors": [RED, ORANGE, YELLOW],
        "speed": 12,
    },
    "focus": {
        "type": "stationary",
        "colors": [COOL_WHITE],
        "speed": 0,
    },
    "romance": {
        "type": "twinkle",
        "colors": [RED.dim(0.7), PINK.dim(0.7), WARM_WHITE.dim(0.5)],
        "speed": 2,
    },
    "party": {
        "type": "chase",
        "colors": [RED, YELLOW, GREEN, CYAN, BLUE, MAGENTA],
        "speed": 15,
    },
    "rave": {
        "type": "bolt",
        "colors": [MAGENTA, CYAN, YELLOW, WHITE],
        "speed": 20,
    },
    # === Nature Inspired ===
    "ocean": {
        "type": "river",
        "colors": [Color(0, 50, 150), Color(0, 100, 200), CYAN],
        "speed": 4,
    },
    "forest": {
        "type": "twinkle",
        "colors": [Color(0, 100, 0), Color(50, 150, 50), Color(100, 200, 100)],
        "speed": 2,
    },
    "sunset": {
        "type": "fade",
        "colors": [Color(255, 100, 50), Color(255, 50, 100), PURPLE],
        "speed": 1,
    },
    "aurora": {
        "type": "river",
        "colors": [GREEN, CYAN, PURPLE, MAGENTA],
        "speed": 3,
    },
    "fire": {
        "type": "twinkle",
        "colors": [RED, ORANGE, YELLOW, Color(255, 50, 0)],
        "speed": 8,
    },
    "ice": {
        "type": "sprinkle",
        "colors": [WHITE, CYAN, Color(200, 230, 255)],
        "speed": 3,
    },
    # === Welcome/Alert ===
    "welcome": {
        "type": "stationary",
        "colors": [WARM_WHITE],
        "speed": 0,
    },
    "arriving": {
        "type": "march",
        "colors": [WARM_WHITE, Color(255, 220, 180)],
        "speed": 5,
    },
    "alert": {
        "type": "bolt",
        "colors": [RED, Color(0, 0, 0), RED],
        "speed": 15,
    },
    "security": {
        "type": "chase",
        "colors": [RED, BLUE],
        "speed": 12,
    },
}


# =============================================================================
# Integration
# =============================================================================


class OeloIntegration:
    """Oelo outdoor lighting control.

    Full API support for patterns, colors, zones, and creative presets.
    """

    def __init__(self, config: SmartHomeConfig):
        self.config = config

        # Load from keychain if not configured
        self._load_credentials_from_keychain()

        self._session: aiohttp.ClientSession | None = None
        self._base_url = f"http://{config.oelo_host or '192.168.1.254'}"
        self._zones: list[OeloZone] = []
        self._initialized = False

    def _load_credentials_from_keychain(self) -> None:
        """Load Oelo host from macOS Keychain."""
        if self.config.oelo_host:
            return

        try:
            from kagami_smarthome.secrets import secrets

            host = secrets.get("oelo_host")
            if host:
                self.config.oelo_host = host
                logger.debug(f"Oelo: Loaded host from Keychain: {host}")
        except Exception as e:
            logger.debug(f"Oelo: Could not load from Keychain: {e}")

    @property
    def is_connected(self) -> bool:
        return self._initialized

    @property
    def zones(self) -> list[OeloZone]:
        return self._zones

    @property
    def enabled_zones(self) -> list[int]:
        return [z.num for z in self._zones if z.enabled]

    # =========================================================================
    # Connection
    # =========================================================================

    async def connect(self) -> bool:
        """Connect and discover zones."""
        try:
            self._session = aiohttp.ClientSession()
            await self.refresh()

            if self._zones:
                self._initialized = True
                enabled = [z for z in self._zones if z.enabled]
                total_leds = sum(z.led_count for z in enabled)
                logger.info(f"Oelo: {len(enabled)} zones, {total_leds} LEDs")
                return True
            return False
        except Exception as e:
            logger.error(f"Oelo connection failed: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect."""
        self._initialized = False
        if self._session:
            await self._session.close()
            self._session = None

    async def refresh(self) -> None:
        """Refresh zone state from controller."""
        if not self._session:
            return

        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with self._session.get(f"{self._base_url}/getController", timeout=timeout) as r:
                if r.status == 200:
                    data = await r.json(content_type=None)
                    self._zones = [
                        OeloZone(
                            num=z["num"],
                            name=z.get("name", f"Zone {z['num']}"),
                            enabled=z.get("enabled", False),
                            led_count=z.get("ledCnt", 0),
                            is_on=z.get("isOn", False),
                            pattern=z.get("pattern", "off"),
                            colors=z.get("colorStr", ""),
                            speed=z.get("speed", 0),
                            direction=z.get("direction", "R"),
                        )
                        for z in data
                    ]
        except Exception as e:
            logger.debug(f"Oelo refresh error: {e}")

    # =========================================================================
    # Core API
    # =========================================================================

    async def _send(
        self,
        zone: int,
        pattern_type: str,
        colors: list[Color],
        speed: int = 5,
        direction: str = "R",
        gap: int = 0,
        retries: int = 2,
    ) -> bool:
        """Send pattern command to zone with retry logic.

        The Oelo controller is ESP8266-based and can be slow/fragile.
        Use longer timeouts and retry on failure.
        """
        if not self._session:
            return False

        color_str = ",".join(str(c) for c in colors)
        params = (
            f"patternType={pattern_type}"
            f"&zones={zone}&num_zones=1"
            f"&num_colors={len(colors)}&colors={color_str}"
            f"&direction={direction}&speed={speed}"
            f"&gap={gap}&other=0&pause=0"
        )

        url = f"{self._base_url}/setPattern?{params}"

        for attempt in range(retries + 1):
            try:
                # Long timeout - controller can be slow
                timeout = aiohttp.ClientTimeout(total=15)
                async with self._session.get(url, timeout=timeout) as r:
                    if r.status == 200:
                        logger.debug(f"Oelo zone {zone}: {pattern_type} OK")
                        return True
            except TimeoutError:
                logger.warning(f"Oelo zone {zone}: timeout (attempt {attempt + 1})")
                if attempt < retries:
                    await asyncio.sleep(3)  # Wait before retry
            except Exception as e:
                logger.debug(f"Oelo zone {zone} error: {e}")
                if attempt < retries:
                    await asyncio.sleep(2)

        logger.error(f"Oelo zone {zone}: failed after {retries + 1} attempts")
        return False

    async def _send_all(
        self,
        pattern_type: str,
        colors: list[Color],
        speed: int = 5,
        direction: str = "R",
    ) -> bool:
        """Send to all enabled zones SEQUENTIALLY to avoid crashing controller.

        The Oelo ESP8266 controller has very limited resources and will crash
        if multiple HTTP requests are sent simultaneously. We must send one
        at a time with delays between each.
        """
        success = True
        for z in self._zones:
            if z.enabled:
                result = await self._send(z.num, pattern_type, colors, speed, direction)
                if not result:
                    success = False
                # Critical: Wait between commands to avoid overwhelming the controller
                await asyncio.sleep(2.0)
        return success

    # =========================================================================
    # Simple Controls
    # =========================================================================

    async def on(self, zone: int | None = None) -> bool:
        """Turn on (warm white)."""
        if zone:
            return await self._send(zone, "stationary", [WARM_WHITE], 0)
        return await self._send_all("stationary", [WARM_WHITE], 0)

    async def off(self, zone: int | None = None) -> bool:
        """Turn off."""
        if zone:
            return await self._send(zone, "off", [Color(0, 0, 0)], 0)
        return await self._send_all("off", [Color(0, 0, 0)], 0)

    async def set_color(self, color: Color | str | tuple, zone: int | None = None) -> bool:
        """Set solid color."""
        if isinstance(color, str):
            color = Color.from_hex(color)
        elif isinstance(color, tuple):
            color = Color(*color)

        if zone:
            return await self._send(zone, "stationary", [color], 0)
        return await self._send_all("stationary", [color], 0)

    async def set_brightness(self, brightness: float, zone: int | None = None) -> bool:
        """Set brightness (0.0 - 1.0) as white."""
        color = WHITE.dim(max(0, min(1, brightness)))
        return await self.set_color(color, zone)

    # =========================================================================
    # Pattern Controls
    # =========================================================================

    async def set_pattern(
        self,
        name: str,
        zone: int | None = None,
        speed_override: int | None = None,
    ) -> bool:
        """Apply named pattern preset."""
        preset = PATTERNS.get(name.lower())
        if not preset:
            logger.warning(f"Unknown pattern: {name}")
            return False

        speed = speed_override if speed_override is not None else preset["speed"]

        if zone:
            return await self._send(zone, preset["type"], preset["colors"], speed)
        return await self._send_all(preset["type"], preset["colors"], speed)

    async def set_custom(
        self,
        pattern_type: str,
        colors: list[Color | str | tuple],
        speed: int = 5,
        zone: int | None = None,
    ) -> bool:
        """Set custom pattern with colors."""
        parsed = []
        for c in colors:
            if isinstance(c, str):
                parsed.append(Color.from_hex(c))
            elif isinstance(c, tuple):
                parsed.append(Color(*c))
            else:
                parsed.append(c)

        if zone:
            return await self._send(zone, pattern_type, parsed, speed)
        return await self._send_all(pattern_type, parsed, speed)

    # =========================================================================
    # Creative Helpers
    # =========================================================================

    async def rainbow(self, speed: int = 8, zone: int | None = None) -> bool:
        """Full rainbow chase."""
        colors = [Color.from_hsv(h, 1, 1) for h in range(0, 360, 60)]
        if zone:
            return await self._send(zone, "chase", colors, speed)
        return await self._send_all("chase", colors, speed)

    async def gradient(
        self,
        start: Color | str,
        end: Color | str,
        steps: int = 5,
        zone: int | None = None,
    ) -> bool:
        """Smooth gradient between two colors."""
        if isinstance(start, str):
            start = Color.from_hex(start)
        if isinstance(end, str):
            end = Color.from_hex(end)

        colors = []
        for i in range(steps):
            t = i / (steps - 1)
            colors.append(
                Color(
                    int(start.r + (end.r - start.r) * t),
                    int(start.g + (end.g - start.g) * t),
                    int(start.b + (end.b - start.b) * t),
                )
            )

        if zone:
            return await self._send(zone, "march", colors, 2)
        return await self._send_all("march", colors, 2)

    async def pulse(self, color: Color | str, speed: int = 5, zone: int | None = None) -> bool:
        """Pulsing single color."""
        if isinstance(color, str):
            color = Color.from_hex(color)

        colors = [color, color.dim(0.3)]
        if zone:
            return await self._send(zone, "fade", colors, speed)
        return await self._send_all("fade", colors, speed)

    async def sparkle(self, color: Color | str, speed: int = 8, zone: int | None = None) -> bool:
        """Sparkling effect."""
        if isinstance(color, str):
            color = Color.from_hex(color)

        colors = [color, WHITE, color.dim(0.5), Color(0, 0, 0)]
        if zone:
            return await self._send(zone, "twinkle", colors, speed)
        return await self._send_all("twinkle", colors, speed)

    async def wave(self, color: Color | str, speed: int = 6, zone: int | None = None) -> bool:
        """Smooth wave motion."""
        if isinstance(color, str):
            color = Color.from_hex(color)

        colors = [color.dim(0.2), color.dim(0.5), color, color.dim(0.5), color.dim(0.2)]
        if zone:
            return await self._send(zone, "river", colors, speed)
        return await self._send_all("river", colors, speed)

    # =========================================================================
    # Scene Shortcuts
    # =========================================================================

    async def welcome_home(self) -> bool:
        """Warm, inviting welcome."""
        return await self.set_pattern("welcome")

    async def movie_night(self) -> bool:
        """Dim, ambient lighting."""
        return await self.set_color(WARM_WHITE.dim(0.2))

    async def party_mode(self) -> bool:
        """High-energy party."""
        return await self.set_pattern("party")

    async def bedtime(self) -> bool:
        """Gentle fade to off."""
        await self.set_pattern("calm")
        await asyncio.sleep(5)
        return await self.off()

    async def alert_mode(self) -> bool:
        """Security/alert flashing."""
        return await self.set_pattern("alert")

    # =========================================================================
    # State
    # =========================================================================

    def get_state(self) -> dict[str, Any]:
        """Get current state."""
        return {
            "connected": self._initialized,
            "zones": [
                {
                    "num": z.num,
                    "name": z.name,
                    "enabled": z.enabled,
                    "leds": z.led_count,
                    "on": z.is_on,
                    "pattern": z.pattern,
                }
                for z in self._zones
            ],
        }

    @staticmethod
    def list_patterns() -> list[str]:
        """List available pattern presets."""
        return list(PATTERNS.keys())
