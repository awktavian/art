"""Sensory Integration Package - SENSE layer of the predictive hierarchy.

This package provides modular sensory integration for the Kagami system.
The UnifiedSensoryIntegration class is the main entry point.

Modules:
    - base: Core types (SenseType, SenseConfig, CachedSense, ActivityLevel)
    - environmental: Weather, world state, situation awareness
    - biometric: Sleep, health, Apple Health integration
    - digital: Email, calendar, github, linear, slack, figma
    - home: Presence, locks, climate, security, cameras
    - vehicle: Tesla integration
    - patterns: Pattern learning and prediction
    - aggregator: Main UnifiedSensoryIntegration class
"""

from .aggregator import UnifiedSensoryIntegration
from .base import (
    ADAPTIVE_CONFIGS,
    DEFAULT_SENSE_CONFIGS,
    ActivityLevel,
    AdaptiveConfig,
    CachedSense,
    SenseConfig,
    SenseEventCallback,
    SenseType,
)
from .biometric import BiometricSensors
from .digital import DigitalSensors
from .digital_sensors import DigitalSensorManager
from .environmental import EnvironmentalSensors
from .home import HomeSensors
from .patterns import PatternManager
from .vehicle import VehicleSensors

__all__ = [
    "ADAPTIVE_CONFIGS",
    "DEFAULT_SENSE_CONFIGS",
    "ActivityLevel",
    "AdaptiveConfig",
    "BiometricSensors",
    "CachedSense",
    "DigitalSensorManager",
    "DigitalSensors",
    "EnvironmentalSensors",
    "HomeSensors",
    "PatternManager",
    "SenseConfig",
    "SenseEventCallback",
    "SenseType",
    "UnifiedSensoryIntegration",
    "VehicleSensors",
]
