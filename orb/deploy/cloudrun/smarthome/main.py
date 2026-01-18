"""Kagami SmartHome Cloud Run Service.

Always-on smart home controller with persistent integrations.
Designed for Cloud Run with min-instances=1.

Created: January 5, 2026
"""

from __future__ import annotations

# =============================================================================
# SETUP PATH AND MOCK HEAVY DEPENDENCIES - MUST BE FIRST
# =============================================================================

import os
import sys
import types
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime

# Add packages to path FIRST
sys.path.insert(0, "/app/packages")


# =============================================================================
# MOCK SECURITY (avoids Keychain dependency)
# =============================================================================


def _get_secret(key: str, default: str | None = None) -> str | None:
    """Get a secret from environment variables."""
    mapping = {
        "control4_host": "CONTROL4_HOST",
        "control4_bearer_token": "CONTROL4_BEARER_TOKEN",
        "unifi_host": "UNIFI_HOST",
        "unifi_local_username": "UNIFI_LOCAL_USERNAME",
        "unifi_local_password": "UNIFI_LOCAL_PASSWORD",  # pragma: allowlist secret
        "denon_host": "DENON_HOST",
    }
    env_name = mapping.get(key, key.upper())
    return os.getenv(env_name, default)


def _set_secret(key: str, value: str) -> bool:
    return False


class _MockHalKeychain:
    def __init__(self, *args, **kwargs):
        pass

    def get(self, key: str) -> str | None:
        return _get_secret(key)

    def set(self, key: str, value: str) -> bool:
        return False

    def list(self):
        return []


_security = types.ModuleType("kagami.core.security")
_security.get_secret = _get_secret
_security.set_secret = _set_secret

_backends = types.ModuleType("kagami.core.security.backends")
_keychain = types.ModuleType("kagami.core.security.backends.keychain_backend")
_keychain.HalKeychain = _MockHalKeychain
_backends.keychain_backend = _keychain
_security.backends = _backends

sys.modules["kagami.core.security"] = _security
sys.modules["kagami.core.security.backends"] = _backends
sys.modules["kagami.core.security.backends.keychain_backend"] = _keychain


# =============================================================================
# MOCK KAGAMI.CORE.INTEGRATIONS (avoids heavy deps like pyicloud)
# =============================================================================


class MockPresenceState(str, Enum):
    HOME = "home"
    AWAY = "away"
    ARRIVING = "arriving"
    LEAVING = "leaving"
    UNKNOWN = "unknown"


class MockTravelMode(str, Enum):
    HOME = "home"
    DRIVING = "driving"
    UNKNOWN = "unknown"


@dataclass
class MockPresenceSnapshot:
    state: MockPresenceState = MockPresenceState.UNKNOWN
    is_home: bool = True
    travel_mode: MockTravelMode = MockTravelMode.HOME
    current_room: str | None = None
    previous_room: str | None = None
    room_confidence: float = 0.0
    phone_at_home: bool = True
    laptop_at_home: bool = True
    car_at_home: bool = True
    timestamp: datetime = field(default_factory=datetime.now)


class MockPresenceService:
    """Minimal presence service for Cloud Run."""

    def __init__(self):
        self._state = MockPresenceSnapshot()

    def is_home(self) -> bool:
        return True

    def current_room(self) -> str | None:
        return None

    def travel_mode(self) -> MockTravelMode:
        return MockTravelMode.HOME

    def get_snapshot(self) -> MockPresenceSnapshot:
        return self._state


# Create mock presence_service module
_presence_service = types.ModuleType("kagami.core.integrations.presence_service")
_presence_service.PresenceState = MockPresenceState
_presence_service.TravelMode = MockTravelMode
_presence_service.PresenceSnapshot = MockPresenceSnapshot
_presence_service.PresenceService = MockPresenceService


def _get_presence_service():
    return MockPresenceService()


_presence_service.get_presence_service = _get_presence_service

# Create mock integrations module (minimal - just presence)
_integrations = types.ModuleType("kagami.core.integrations")
_integrations.PresenceState = MockPresenceState
_integrations.TravelMode = MockTravelMode
_integrations.PresenceSnapshot = MockPresenceSnapshot
_integrations.PresenceService = MockPresenceService
_integrations.get_presence_service = _get_presence_service

# Register mocks
sys.modules["kagami.core.integrations"] = _integrations
sys.modules["kagami.core.integrations.presence_service"] = _presence_service

# =============================================================================
# NOW SAFE TO IMPORT OTHER MODULES
# =============================================================================

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("KAGAMI_LOG_LEVEL", "INFO")),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("kagami.smarthome")

# Global controller instance
_controller = None
_background_task = None


async def get_controller():
    """Get or create the SmartHome controller."""
    global _controller

    if _controller is None:
        from kagami_smarthome import get_smart_home

        _controller = await get_smart_home()
        logger.info("SmartHome controller initialized")

    return _controller


async def background_health_monitor():
    """Background task to keep integrations healthy."""
    poll_interval = int(os.getenv("SMARTHOME_POLL_INTERVAL", "30"))

    while True:
        try:
            controller = await get_controller()
            state = controller.get_organism_state()
            lights_count = len(state.get("lights", {})) if state else 0
            logger.debug(f"Health check: {lights_count} lights in cache")
        except Exception as e:
            logger.error(f"Background monitor error: {e}")
        await asyncio.sleep(poll_interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown."""
    global _background_task

    try:
        await get_controller()
        logger.info("✅ SmartHome controller ready")
    except Exception as e:
        logger.error(f"Failed to initialize controller: {e}")

    _background_task = asyncio.create_task(background_health_monitor())
    yield

    if _background_task:
        _background_task.cancel()
        try:
            await _background_task
        except asyncio.CancelledError:
            pass

    if _controller:
        try:
            await _controller.disconnect()
        except Exception:
            pass
    logger.info("SmartHome service shutdown complete")


app = FastAPI(
    title="Kagami SmartHome",
    description="Always-on smart home controller",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    """Basic health check."""
    return {"status": "healthy", "service": "kagami-smarthome"}


@app.get("/health/ready")
async def health_ready():
    """Readiness check - are integrations connected?"""
    try:
        controller = await get_controller()
        state = controller.get_organism_state()
        has_data = bool(state and any(state.values()))
        if has_data:
            return {"status": "ready", "has_data": True}
        return JSONResponse(status_code=503, content={"status": "warming", "has_data": False})
    except Exception as e:
        return JSONResponse(status_code=503, content={"status": "error", "error": str(e)})


@app.get("/state")
async def get_state():
    """Get full organism state."""
    try:
        controller = await get_controller()
        return controller.get_organism_state()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/state/lights")
async def get_lights():
    """Get all light states."""
    try:
        controller = await get_controller()
        state = controller.get_organism_state()
        return state.get("lights", {})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/state/presence")
async def get_presence():
    """Get presence state."""
    try:
        controller = await get_controller()
        return controller.get_presence_state()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


class LightAction(BaseModel):
    """Light control action."""

    level: int
    rooms: list[str] | None = None


@app.post("/action/lights")
async def set_lights(action: LightAction):
    """Set light levels."""
    try:
        controller = await get_controller()
        await controller.set_lights(action.level, rooms=action.rooms)
        return {"success": True, "action": "lights", "level": action.level}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/action/scene/{scene_name}")
async def trigger_scene(scene_name: str):
    """Trigger a scene."""
    try:
        controller = await get_controller()
        scene_methods = {
            "goodnight": controller.goodnight,
            "welcome_home": controller.welcome_home,
            "movie_mode": controller.movie_mode,
        }
        if scene_name not in scene_methods:
            raise HTTPException(status_code=404, detail=f"Unknown scene: {scene_name}")
        await scene_methods[scene_name]()
        return {"success": True, "scene": scene_name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
