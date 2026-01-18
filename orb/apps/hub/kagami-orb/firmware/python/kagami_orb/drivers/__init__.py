"""
Hardware Drivers for Kagami Orb V3

All drivers support simulation mode for testing without hardware.
"""

from .led import HD108Driver, OrbState, RGBW
from .power import (
    PowerMonitor,
    BQ25895Driver,
    BQ40Z50Driver,
    BQ25895Status,
    BQ40Z50Status,
    BQ25895ChargeStatus,
    BQ25895VBUSStatus,
    BQ25895Fault,
)
from .sensors import (
    OrbSensors,
    ICM45686Driver,
    VL53L8CXDriver,
    SHT45Driver,
    IMUData,
    ToFFrame,
    ToFZone,
    TempHumidity,
    OrbSensorState,
)
from .npu import (
    HailoNPUDriver,
    ModelType,
    ModelConfig,
    OrbVisionPipeline,
    InferenceResult,
    Detection,
    PoseResult,
    PoseKeypoint,
    FaceEmbedding,
)
from .cellular import (
    CellularModem,
    ModemManager,
    ModemInfo,
    SignalQuality,
    CellInfo,
    NetworkType,
    RegistrationStatus,
    SIMStatus,
    ConnectionState,
)
from .gnss import (
    GNSSDriver,
    GNSSPosition,
    NMEAParser,
    SatelliteInfo,
    GNSSSystem,
    FixType,
    FixMode,
    LocationService,
    LocationUpdate,
)

__all__ = [
    # LED
    "HD108Driver",
    "OrbState",
    "RGBW",
    # Power
    "PowerMonitor",
    "BQ25895Driver",
    "BQ40Z50Driver",
    "BQ25895Status",
    "BQ40Z50Status",
    "BQ25895ChargeStatus",
    "BQ25895VBUSStatus",
    "BQ25895Fault",
    # Sensors
    "OrbSensors",
    "ICM45686Driver",
    "VL53L8CXDriver",
    "SHT45Driver",
    "IMUData",
    "ToFFrame",
    "ToFZone",
    "TempHumidity",
    "OrbSensorState",
    # NPU
    "HailoNPUDriver",
    "ModelType",
    "ModelConfig",
    "OrbVisionPipeline",
    "InferenceResult",
    "Detection",
    "PoseResult",
    "PoseKeypoint",
    "FaceEmbedding",
    # Cellular
    "CellularModem",
    "ModemManager",
    "ModemInfo",
    "SignalQuality",
    "CellInfo",
    "NetworkType",
    "RegistrationStatus",
    "SIMStatus",
    "ConnectionState",
    # GNSS
    "GNSSDriver",
    "GNSSPosition",
    "NMEAParser",
    "SatelliteInfo",
    "GNSSSystem",
    "FixType",
    "FixMode",
    "LocationService",
    "LocationUpdate",
]
