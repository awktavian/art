"""Glowforge Pro Laser Cutter Integration.

Integration for Glowforge Pro laser cutter.

⚠️  LIMITATIONS:
Glowforge does NOT provide a public API. All device control happens
through their cloud service at app.glowforge.com. This integration
provides LIMITED monitoring capabilities only.

Provides:
- Device connectivity status (via mDNS discovery)
- Basic online/offline detection
- SVG file preparation helpers
- Job file generation (manual upload required)

Equipment:
- Glowforge Pro 45W CO₂ Laser
- Bed: 20" × 18", up to 2" height
- Pro Passthrough: unlimited length ¼" material
- Materials: wood, acrylic, leather, fabric

⚠️  NO REMOTE CONTROL:
- Cannot start/stop/pause jobs remotely
- Cannot upload files programmatically
- Physical button press required to start cuts

Created: December 30, 2025
"""

from __future__ import annotations

import asyncio
import logging
import socket
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from kagami_smarthome.types import SmartHomeConfig

logger = logging.getLogger(__name__)

# Glowforge mDNS service name
MDNS_SERVICE = "_glowforge._tcp.local."
DEFAULT_PORT = 80


class GlowforgeState(Enum):
    """Glowforge device state (limited detection)."""

    ONLINE = "online"  # Responding to network
    OFFLINE = "offline"  # Not found on network
    UNKNOWN = "unknown"


class LaserPower(Enum):
    """Laser power presets."""

    ENGRAVE_LIGHT = 10
    ENGRAVE_MEDIUM = 30
    ENGRAVE_DEEP = 60
    CUT_THIN = 80
    CUT_THICK = 100


@dataclass
class GlowforgeMachine:
    """Glowforge machine info from network discovery."""

    name: str
    ip_address: str
    serial: str | None
    model: str
    firmware: str | None
    state: GlowforgeState
    last_seen: datetime


@dataclass
class MaterialSettings:
    """Laser settings for a material."""

    name: str
    thickness_mm: float
    cut_power: int  # 0-100
    cut_speed: int  # 0-500
    engrave_power: int
    engrave_speed: int
    engrave_lpi: int  # lines per inch
    score_power: int
    score_speed: int


# Common material presets
MATERIAL_PRESETS: dict[str, MaterialSettings] = {
    "plywood_3mm": MaterialSettings(
        name="3mm Plywood",
        thickness_mm=3.0,
        cut_power=100,
        cut_speed=150,
        engrave_power=30,
        engrave_speed=1000,
        engrave_lpi=270,
        score_power=15,
        score_speed=300,
    ),
    "plywood_6mm": MaterialSettings(
        name="6mm Plywood",
        thickness_mm=6.0,
        cut_power=100,
        cut_speed=120,
        engrave_power=35,
        engrave_speed=1000,
        engrave_lpi=270,
        score_power=20,
        score_speed=300,
    ),
    "acrylic_3mm": MaterialSettings(
        name="3mm Acrylic",
        thickness_mm=3.0,
        cut_power=100,
        cut_speed=168,
        engrave_power=40,
        engrave_speed=1000,
        engrave_lpi=270,
        score_power=20,
        score_speed=300,
    ),
    "leather_2mm": MaterialSettings(
        name="2mm Leather",
        thickness_mm=2.0,
        cut_power=80,
        cut_speed=200,
        engrave_power=25,
        engrave_speed=1000,
        engrave_lpi=195,
        score_power=15,
        score_speed=400,
    ),
    "cardstock": MaterialSettings(
        name="Cardstock",
        thickness_mm=0.3,
        cut_power=40,
        cut_speed=400,
        engrave_power=15,
        engrave_speed=1000,
        engrave_lpi=270,
        score_power=10,
        score_speed=500,
    ),
}


@dataclass
class GlowforgeStatus:
    """Current Glowforge status."""

    machine: GlowforgeMachine | None
    state: GlowforgeState
    network_reachable: bool
    last_check: datetime = field(default_factory=datetime.now)

    # Note: Cannot get actual job status without API
    # These are placeholders for future integration
    job_in_progress: bool = False
    estimated_job_time: int = 0


class GlowforgeIntegration:
    """Glowforge Pro integration (limited - no official API).

    ⚠️  This integration provides MONITORING ONLY.
    Glowforge requires cloud authentication and physical
    button press to start jobs.

    Features:
    - Network discovery via IP/hostname
    - Online/offline detection
    - SVG file generation helpers
    - Material presets

    NOT Supported (no API):
    - Remote job start/stop
    - File upload
    - Camera preview
    - Lid detection
    """

    def __init__(self, config: SmartHomeConfig):
        self.config = config
        self._host = getattr(config, "glowforge_ip", None)
        self._initialized = False

        # Current state
        self._status: GlowforgeStatus | None = None
        self._machine: GlowforgeMachine | None = None

        # Callbacks
        self._on_state_change: Callable[[GlowforgeStatus], None] | None = None

        # Polling with resilience
        self._poll_task: asyncio.Task[None] | None = None
        self._poll_interval = 60.0  # Check every minute
        self._consecutive_failures = 0
        self._max_backoff_minutes = 10

        # Load from Keychain if not set (after instance vars initialized)
        self._load_from_keychain()

    def _load_from_keychain(self) -> None:
        """Load Glowforge config from Keychain."""
        try:
            from kagami_smarthome.secrets import secrets

            # Load IP if not already set
            if not self._host:
                ip = secrets.get("glowforge_ip")
                if ip:
                    self._host = ip
                    logger.debug("Glowforge: Loaded IP from Keychain")

        except Exception as e:
            logger.debug(f"Glowforge: Could not load from Keychain: {e}")

    @property
    def is_connected(self) -> bool:
        """Check if Glowforge is reachable on network."""
        return self._initialized and self._status is not None and self._status.network_reachable

    @property
    def state(self) -> GlowforgeState:
        if self._status:
            return self._status.state
        return GlowforgeState.UNKNOWN

    async def connect(self) -> bool:
        """Attempt to discover/connect to Glowforge on network."""
        try:
            # Try to find Glowforge on network
            if self._host:
                reachable = await self._check_host(self._host)
                if reachable:
                    self._machine = GlowforgeMachine(
                        name="Glowforge Pro",
                        ip_address=self._host,
                        serial=None,
                        model="Pro",
                        firmware=None,
                        state=GlowforgeState.ONLINE,
                        last_seen=datetime.now(),
                    )
                    self._status = GlowforgeStatus(
                        machine=self._machine,
                        state=GlowforgeState.ONLINE,
                        network_reachable=True,
                    )
                    self._initialized = True
                    logger.info("Glowforge: Found on network")

                    # Start polling
                    self._start_polling()
                    return True

            # Try mDNS discovery
            discovered = await self._mdns_discover()
            if discovered:
                self._machine = discovered
                self._status = GlowforgeStatus(
                    machine=discovered,
                    state=GlowforgeState.ONLINE,
                    network_reachable=True,
                )
                self._initialized = True
                logger.info(f"Glowforge: Discovered {discovered.name}")
                self._start_polling()
                return True

            logger.debug("Glowforge: Not found on network")
            self._status = GlowforgeStatus(
                machine=None,
                state=GlowforgeState.OFFLINE,
                network_reachable=False,
            )
            return False

        except Exception as e:
            logger.error(f"Glowforge: Connection failed - {e}")
            return False

    async def disconnect(self) -> None:
        """Stop monitoring."""
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None
        self._initialized = False

    async def _check_host(self, host: str, port: int = DEFAULT_PORT) -> bool:
        """Check if host is reachable."""
        try:
            # Simple TCP connect check
            loop = asyncio.get_event_loop()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setblocking(False)
            sock.settimeout(5)

            try:
                await asyncio.wait_for(loop.sock_connect(sock, (host, port)), timeout=5.0)
                return True
            except (TimeoutError, OSError):
                return False
            finally:
                sock.close()
        except Exception:
            return False

    async def _mdns_discover(self) -> GlowforgeMachine | None:
        """Try to discover Glowforge via mDNS."""
        try:
            # Try common hostnames
            hostnames = [
                "glowforge.local",
                "glowforge-pro.local",
            ]

            for hostname in hostnames:
                try:
                    ip = socket.gethostbyname(hostname)
                    if ip and await self._check_host(ip):
                        return GlowforgeMachine(
                            name=hostname.replace(".local", ""),
                            ip_address=ip,
                            serial=None,
                            model="Pro",
                            firmware=None,
                            state=GlowforgeState.ONLINE,
                            last_seen=datetime.now(),
                        )
                except socket.gaierror:
                    continue

            return None
        except Exception:
            return None

    def _start_polling(self) -> None:
        """Start background polling."""
        if self._poll_task is None:
            self._poll_task = asyncio.create_task(self._poll_loop())

    async def _poll_loop(self) -> None:
        """Background polling loop with resilience."""
        while True:
            try:
                # Adaptive interval - back off if device seems offline
                if self._status and not self._status.network_reachable:
                    self._consecutive_failures += 1
                    # Exponential backoff up to max
                    backoff_factor = min(self._consecutive_failures, self._max_backoff_minutes)
                    interval = self._poll_interval * backoff_factor
                else:
                    self._consecutive_failures = 0
                    interval = self._poll_interval

                await asyncio.sleep(interval)
                await self._update_status()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._consecutive_failures += 1
                logger.debug(f"Glowforge poll error (attempt {self._consecutive_failures}): {e}")

    async def _update_status(self) -> None:
        """Update connectivity status."""
        if not self._machine:
            return

        reachable = await self._check_host(self._machine.ip_address)

        new_state = GlowforgeState.ONLINE if reachable else GlowforgeState.OFFLINE

        if self._status and new_state != self._status.state:
            logger.info(f"Glowforge: State changed to {new_state.value}")

        self._status = GlowforgeStatus(
            machine=self._machine,
            state=new_state,
            network_reachable=reachable,
            last_check=datetime.now(),
        )

        if self._on_state_change:
            self._on_state_change(self._status)

    # === Callbacks ===

    def on_state_change(self, callback: Callable[[GlowforgeStatus], None]) -> None:
        """Register state change callback."""
        self._on_state_change = callback

    # === SVG Generation Helpers ===

    def create_cut_svg(
        self,
        width_mm: float,
        height_mm: float,
        shapes: list[dict[str, Any]],
        output_path: Path | str,
    ) -> Path:
        """Create an SVG file optimized for Glowforge cutting.

        Args:
            width_mm: Document width in mm
            height_mm: Document height in mm
            shapes: List of shape definitions:
                - type: "rect", "circle", "path", "text"
                - operation: "cut" (stroke) or "engrave" (fill)
                - ... shape-specific params
            output_path: Where to save the SVG

        Returns:
            Path to created SVG file

        Note: Upload the SVG to app.glowforge.com manually.
        """
        output_path = Path(output_path)

        # SVG with mm units (Glowforge uses 96 DPI)
        svg = ET.Element("svg")
        svg.set("xmlns", "http://www.w3.org/2000/svg")
        svg.set("width", f"{width_mm}mm")
        svg.set("height", f"{height_mm}mm")
        svg.set("viewBox", f"0 0 {width_mm} {height_mm}")

        for shape in shapes:
            shape_type = shape.get("type", "rect")
            operation = shape.get("operation", "cut")

            # Cut = stroke only, no fill
            # Engrave = fill, no stroke
            if operation == "cut":
                style = "stroke:#000000;stroke-width:0.1;fill:none"
            else:
                style = "fill:#000000;stroke:none"

            if shape_type == "rect":
                elem = ET.SubElement(svg, "rect")
                elem.set("x", str(shape.get("x", 0)))
                elem.set("y", str(shape.get("y", 0)))
                elem.set("width", str(shape.get("width", 10)))
                elem.set("height", str(shape.get("height", 10)))
                if shape.get("rx"):
                    elem.set("rx", str(shape["rx"]))
                elem.set("style", style)

            elif shape_type == "circle":
                elem = ET.SubElement(svg, "circle")
                elem.set("cx", str(shape.get("cx", 0)))
                elem.set("cy", str(shape.get("cy", 0)))
                elem.set("r", str(shape.get("r", 5)))
                elem.set("style", style)

            elif shape_type == "path":
                elem = ET.SubElement(svg, "path")
                elem.set("d", shape.get("d", ""))
                elem.set("style", style)

            elif shape_type == "text":
                elem = ET.SubElement(svg, "text")
                elem.set("x", str(shape.get("x", 0)))
                elem.set("y", str(shape.get("y", 0)))
                elem.set("font-size", str(shape.get("font_size", 10)))
                elem.set("font-family", shape.get("font", "Arial"))
                elem.set("style", style)
                elem.text = shape.get("text", "")

        # Write with proper XML declaration
        tree = ET.ElementTree(svg)
        tree.write(output_path, encoding="utf-8", xml_declaration=True)

        logger.info(f"Glowforge: Created SVG at {output_path}")
        return output_path

    def get_material_settings(self, material: str) -> MaterialSettings | None:
        """Get preset settings for a material."""
        return MATERIAL_PRESETS.get(material)

    def list_materials(self) -> list[str]:
        """List available material presets."""
        return list(MATERIAL_PRESETS.keys())

    # === Status ===

    def to_dict(self) -> dict[str, Any]:
        """Export status as dictionary for unified sensory."""
        if not self._status:
            return {"connected": False, "state": "unknown"}

        result: dict[str, Any] = {
            "connected": self._status.network_reachable,
            "state": self._status.state.value,
            "last_check": self._status.last_check.isoformat(),
        }

        if self._status.machine:
            result["machine"] = {
                "name": self._status.machine.name,
                "ip": self._status.machine.ip_address,
                "model": self._status.machine.model,
            }

        # Note about limitations
        result["note"] = "Limited monitoring only - no official API"

        return result


# Factory functions
_instance: GlowforgeIntegration | None = None


def get_glowforge() -> GlowforgeIntegration | None:
    """Get the global Glowforge integration instance."""
    return _instance


async def start_glowforge(config: SmartHomeConfig) -> GlowforgeIntegration | None:
    """Start Glowforge integration."""
    global _instance

    _instance = GlowforgeIntegration(config)
    if await _instance.connect():
        return _instance

    # Return instance even if offline (for monitoring)
    return _instance
