"""Smart Home Services — Decomposed Controller Components.

This package contains domain-specific services extracted from
the monolithic SmartHomeController to improve modularity,
testability, and maintainability.

Services (14 total):
- DeviceService: Lights, shades, TV mount, fireplace (Control4/Lutron)
- AVService: Audio, TV, home theater (Denon, LG, Samsung, Spotify)
- ClimateService: HVAC, bed temperature (Mitsubishi, Eight Sleep)
- SecurityService: Locks, cameras, alarms (August, UniFi, Envisalink)
- TeslaService: Vehicle presence, battery, charging
- OeloService: Outdoor lighting control
- WorkshopService: Formlabs 3D printer, Glowforge laser
- HealthService: Apple Health biometrics
- FindMyService: Apple Find My device tracking
- PresenceService: Device localization, geofencing
- SceneService: Routines, movie/game mode
- RoomService: Room-centric operations, announcements
- AutomationService: Guest mode, vacation mode, circadian
- VisitorService: WiFi presence monitoring, guest detection

Created: December 30, 2025
"""

from kagami.core.integrations.presence_service import PresenceService

from kagami_smarthome.services.automation_service import AutomationService
from kagami_smarthome.services.av_service import AVService
from kagami_smarthome.services.climate_service import ClimateService
from kagami_smarthome.services.device_service import DeviceService
from kagami_smarthome.services.findmy_service import FindMyService
from kagami_smarthome.services.health_service import HealthService
from kagami_smarthome.services.oelo_service import OeloService
from kagami_smarthome.services.room_service import RoomService
from kagami_smarthome.services.scene_service import SceneService
from kagami_smarthome.services.security_service import SecurityService
from kagami_smarthome.services.tesla_service import TeslaService
from kagami_smarthome.services.visitor_service import VisitorService
from kagami_smarthome.services.workshop_service import WorkshopService

__all__ = [
    "AVService",
    "AutomationService",
    "ClimateService",
    "DeviceService",
    "FindMyService",
    "HealthService",
    "OeloService",
    "PresenceService",
    "RoomService",
    "SceneService",
    "SecurityService",
    "TeslaService",
    "VisitorService",
    "WorkshopService",
]
