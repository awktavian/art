"""Apple Health Integration — Biometric Data from HealthKit.

Provides access to Apple Health data for biometric monitoring (asyncio optimized):
- Heart rate (resting, walking, workout)
- Heart rate variability (HRV)
- Sleep analysis (stages, duration, quality)
- Activity (steps, calories, distance, exercise minutes)
- Blood oxygen (SpO2)
- Respiratory rate
- Body measurements (weight, body fat)
- Mindfulness minutes
- Workouts (type, duration, calories)

Data Access Methods:
1. Health Auto Export (iOS app → webhook): Real-time export to Kagami
2. Terra API (aggregator): Professional health data aggregation
3. Apple Health XML Export: Manual import for historical data

Architecture:
- Webhook endpoint receives real-time data from Health Auto Export
- Terra API provides normalized access across health platforms
- Pattern learners track biometric trends over time
- Alert hierarchy triggers on anomalous readings

Created: December 30, 2025
"""

from __future__ import annotations

import asyncio
import logging
import time
import xml.etree.ElementTree as ET
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import aiohttp

if TYPE_CHECKING:
    from kagami_smarthome.types import SmartHomeConfig

logger = logging.getLogger(__name__)


# =============================================================================
# DATA TYPES
# =============================================================================


class HealthMetricType(str, Enum):
    """Types of health metrics from Apple Health."""

    # Heart
    HEART_RATE = "heart_rate"
    RESTING_HEART_RATE = "resting_heart_rate"
    WALKING_HEART_RATE = "walking_heart_rate"
    HEART_RATE_VARIABILITY = "hrv"

    # Sleep
    SLEEP_ANALYSIS = "sleep_analysis"
    SLEEP_DURATION = "sleep_duration"
    SLEEP_QUALITY = "sleep_quality"
    TIME_IN_BED = "time_in_bed"

    # Activity
    STEPS = "steps"
    DISTANCE = "distance"
    ACTIVE_CALORIES = "active_calories"
    TOTAL_CALORIES = "total_calories"
    EXERCISE_MINUTES = "exercise_minutes"
    STAND_HOURS = "stand_hours"
    FLIGHTS_CLIMBED = "flights_climbed"

    # Respiratory
    BLOOD_OXYGEN = "blood_oxygen"
    RESPIRATORY_RATE = "respiratory_rate"

    # Body
    WEIGHT = "weight"
    BODY_FAT = "body_fat"
    BMI = "bmi"
    LEAN_BODY_MASS = "lean_body_mass"

    # Mindfulness
    MINDFULNESS_MINUTES = "mindfulness_minutes"

    # Workouts
    WORKOUT = "workout"


class SleepStage(str, Enum):
    """Sleep stages from Apple Health."""

    AWAKE = "awake"
    REM = "rem"
    CORE = "core"  # Light sleep
    DEEP = "deep"
    IN_BED = "in_bed"
    ASLEEP = "asleep"  # Generic asleep (older iOS)


class WorkoutType(str, Enum):
    """Common workout types."""

    RUNNING = "running"
    WALKING = "walking"
    CYCLING = "cycling"
    SWIMMING = "swimming"
    STRENGTH = "strength_training"
    HIIT = "hiit"
    YOGA = "yoga"
    ROWING = "rowing"
    ELLIPTICAL = "elliptical"
    STAIR_CLIMBING = "stair_climbing"
    OTHER = "other"


@dataclass
class HeartData:
    """Heart rate and HRV data."""

    heart_rate: float | None = None  # bpm
    resting_heart_rate: float | None = None  # bpm
    walking_heart_rate: float | None = None  # bpm
    hrv: float | None = None  # ms (SDNN)
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def is_elevated(self) -> bool:
        """Check if heart rate is elevated (> 100 bpm at rest)."""
        if self.heart_rate and self.resting_heart_rate:
            return self.heart_rate > self.resting_heart_rate * 1.5
        return self.heart_rate is not None and self.heart_rate > 100

    @property
    def hrv_status(self) -> str:
        """Interpret HRV status."""
        if self.hrv is None:
            return "unknown"
        if self.hrv > 50:
            return "good"
        if self.hrv > 30:
            return "moderate"
        return "low"


@dataclass
class SleepData:
    """Sleep analysis data."""

    total_duration_hours: float = 0.0
    time_in_bed_hours: float = 0.0
    sleep_efficiency: float = 0.0  # 0-1

    # Stage breakdown (hours)
    awake_hours: float = 0.0
    rem_hours: float = 0.0
    core_hours: float = 0.0
    deep_hours: float = 0.0

    # Timing
    bed_time: datetime | None = None
    wake_time: datetime | None = None

    # Quality score (0-100)
    quality_score: int = 0

    @property
    def sleep_quality(self) -> str:
        """Get sleep quality assessment."""
        if self.quality_score >= 80:
            return "excellent"
        if self.quality_score >= 60:
            return "good"
        if self.quality_score >= 40:
            return "fair"
        return "poor"

    @property
    def deep_sleep_percentage(self) -> float:
        """Percentage of sleep that was deep."""
        if self.total_duration_hours > 0:
            return (self.deep_hours / self.total_duration_hours) * 100
        return 0.0


@dataclass
class ActivityData:
    """Daily activity data."""

    steps: int = 0
    distance_miles: float = 0.0
    active_calories: int = 0
    total_calories: int = 0
    exercise_minutes: int = 0
    stand_hours: int = 0
    flights_climbed: int = 0

    # Goals (for ring completion)
    move_goal: int = 500  # calories
    exercise_goal: int = 30  # minutes
    stand_goal: int = 12  # hours

    @property
    def move_ring_progress(self) -> float:
        """Progress toward move goal (0-1+)."""
        return self.active_calories / self.move_goal if self.move_goal else 0

    @property
    def exercise_ring_progress(self) -> float:
        """Progress toward exercise goal (0-1+)."""
        return self.exercise_minutes / self.exercise_goal if self.exercise_goal else 0

    @property
    def stand_ring_progress(self) -> float:
        """Progress toward stand goal (0-1+)."""
        return self.stand_hours / self.stand_goal if self.stand_goal else 0

    @property
    def all_rings_closed(self) -> bool:
        """Check if all activity rings are closed."""
        return (
            self.move_ring_progress >= 1.0
            and self.exercise_ring_progress >= 1.0
            and self.stand_ring_progress >= 1.0
        )


@dataclass
class RespiratoryData:
    """Respiratory metrics."""

    blood_oxygen: float | None = None  # percentage (0-100)
    respiratory_rate: float | None = None  # breaths per minute
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def oxygen_status(self) -> str:
        """Interpret blood oxygen status."""
        if self.blood_oxygen is None:
            return "unknown"
        if self.blood_oxygen >= 95:
            return "normal"
        if self.blood_oxygen >= 90:
            return "low"
        return "critical"


@dataclass
class BodyData:
    """Body measurements."""

    weight_lbs: float | None = None
    body_fat_percentage: float | None = None
    bmi: float | None = None
    lean_body_mass_lbs: float | None = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class WorkoutData:
    """Workout session data."""

    workout_type: WorkoutType
    duration_minutes: float
    calories_burned: int
    distance_miles: float | None = None
    avg_heart_rate: float | None = None
    max_heart_rate: float | None = None
    start_time: datetime = field(default_factory=datetime.now)
    end_time: datetime | None = None


@dataclass
class HealthState:
    """Aggregated health state from all metrics."""

    heart: HeartData = field(default_factory=HeartData)
    sleep: SleepData = field(default_factory=SleepData)
    activity: ActivityData = field(default_factory=ActivityData)
    respiratory: RespiratoryData = field(default_factory=RespiratoryData)
    body: BodyData = field(default_factory=BodyData)
    recent_workouts: list[WorkoutData] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "heart": {
                "heart_rate": self.heart.heart_rate,
                "resting_heart_rate": self.heart.resting_heart_rate,
                "hrv": self.heart.hrv,
                "hrv_status": self.heart.hrv_status,
                "is_elevated": self.heart.is_elevated,
            },
            "sleep": {
                "duration_hours": self.sleep.total_duration_hours,
                "quality": self.sleep.sleep_quality,
                "quality_score": self.sleep.quality_score,
                "deep_percentage": self.sleep.deep_sleep_percentage,
                "bed_time": self.sleep.bed_time.isoformat() if self.sleep.bed_time else None,
                "wake_time": self.sleep.wake_time.isoformat() if self.sleep.wake_time else None,
            },
            "activity": {
                "steps": self.activity.steps,
                "distance_miles": self.activity.distance_miles,
                "active_calories": self.activity.active_calories,
                "exercise_minutes": self.activity.exercise_minutes,
                "rings_closed": self.activity.all_rings_closed,
                "move_progress": round(self.activity.move_ring_progress, 2),
                "exercise_progress": round(self.activity.exercise_ring_progress, 2),
                "stand_progress": round(self.activity.stand_ring_progress, 2),
            },
            "respiratory": {
                "blood_oxygen": self.respiratory.blood_oxygen,
                "oxygen_status": self.respiratory.oxygen_status,
                "respiratory_rate": self.respiratory.respiratory_rate,
            },
            "body": {
                "weight_lbs": self.body.weight_lbs,
                "body_fat_percentage": self.body.body_fat_percentage,
                "bmi": self.body.bmi,
            },
            "recent_workouts": len(self.recent_workouts),
            "last_updated": self.last_updated.isoformat(),
        }


# =============================================================================
# EVENT CALLBACKS
# =============================================================================

# Callback type: (metric_type, value, timestamp) -> None
HealthEventCallback = Callable[[HealthMetricType, Any, datetime], Awaitable[None]]


# =============================================================================
# APPLE HEALTH INTEGRATION
# =============================================================================


class AppleHealthIntegration:
    """Apple Health integration via multiple data sources.

    Data Sources (in order of preference):
    1. Health Auto Export webhook (real-time iOS app export)
    2. Terra API (professional health aggregator)
    3. Apple Health XML export (manual import)

    Features:
    - Real-time biometric monitoring
    - Sleep tracking and quality analysis
    - Activity ring progress
    - Workout detection and logging
    - Anomaly detection (elevated heart rate, low SpO2)
    - Pattern learning for circadian rhythm

    Usage:
        health = AppleHealthIntegration(config)
        await health.connect()

        # Get current state
        state = health.get_state()
        print(f"Heart rate: {state.heart.heart_rate} bpm")
        print(f"Steps today: {state.activity.steps}")

        # Subscribe to events
        health.on_event(my_callback)

    Created: December 30, 2025
    """

    # HealthKit type identifiers → our types
    HEALTHKIT_TYPE_MAP = {
        "HKQuantityTypeIdentifierHeartRate": HealthMetricType.HEART_RATE,
        "HKQuantityTypeIdentifierRestingHeartRate": HealthMetricType.RESTING_HEART_RATE,
        "HKQuantityTypeIdentifierWalkingHeartRateAverage": HealthMetricType.WALKING_HEART_RATE,
        "HKQuantityTypeIdentifierHeartRateVariabilitySDNN": HealthMetricType.HEART_RATE_VARIABILITY,
        "HKCategoryTypeIdentifierSleepAnalysis": HealthMetricType.SLEEP_ANALYSIS,
        "HKQuantityTypeIdentifierStepCount": HealthMetricType.STEPS,
        "HKQuantityTypeIdentifierDistanceWalkingRunning": HealthMetricType.DISTANCE,
        "HKQuantityTypeIdentifierActiveEnergyBurned": HealthMetricType.ACTIVE_CALORIES,
        "HKQuantityTypeIdentifierBasalEnergyBurned": HealthMetricType.TOTAL_CALORIES,
        "HKQuantityTypeIdentifierAppleExerciseTime": HealthMetricType.EXERCISE_MINUTES,
        "HKQuantityTypeIdentifierAppleStandHour": HealthMetricType.STAND_HOURS,
        "HKQuantityTypeIdentifierFlightsClimbed": HealthMetricType.FLIGHTS_CLIMBED,
        "HKQuantityTypeIdentifierOxygenSaturation": HealthMetricType.BLOOD_OXYGEN,
        "HKQuantityTypeIdentifierRespiratoryRate": HealthMetricType.RESPIRATORY_RATE,
        "HKQuantityTypeIdentifierBodyMass": HealthMetricType.WEIGHT,
        "HKQuantityTypeIdentifierBodyFatPercentage": HealthMetricType.BODY_FAT,
        "HKQuantityTypeIdentifierBodyMassIndex": HealthMetricType.BMI,
        "HKQuantityTypeIdentifierLeanBodyMass": HealthMetricType.LEAN_BODY_MASS,
        "HKCategoryTypeIdentifierMindfulSession": HealthMetricType.MINDFULNESS_MINUTES,
        "HKWorkoutTypeIdentifier": HealthMetricType.WORKOUT,
    }

    def __init__(self, config: SmartHomeConfig | None = None):
        self.config = config

        # State
        self._state = HealthState()
        self._initialized = False
        self._last_sync = 0.0

        # Sessions
        self._session: aiohttp.ClientSession | None = None

        # Terra API credentials (optional)
        self._terra_api_key: str | None = None
        self._terra_dev_id: str | None = None
        self._terra_user_id: str | None = None

        # Event callbacks
        self._callbacks: list[HealthEventCallback] = []

        # Statistics
        self._stats = {
            "samples_received": 0,
            "webhook_calls": 0,
            "terra_syncs": 0,
            "xml_imports": 0,
            "anomalies_detected": 0,
        }

        # Load credentials
        self._load_credentials()

    def _load_credentials(self) -> None:
        """Load Apple Health/Terra credentials from Keychain."""
        try:
            from kagami_smarthome.secrets import get_secret

            self._terra_api_key = get_secret("terra_api_key")
            self._terra_dev_id = get_secret("terra_dev_id")
            self._terra_user_id = get_secret("terra_user_id")
        except Exception as e:
            logger.debug(f"Apple Health: Could not load Terra credentials: {e}")

    @property
    def is_connected(self) -> bool:
        """Check if integration is connected."""
        return self._initialized

    @property
    def has_terra(self) -> bool:
        """Check if Terra API is configured."""
        return bool(self._terra_api_key and self._terra_dev_id)

    async def connect(self) -> bool:
        """Initialize Apple Health integration.

        Returns:
            True if connected successfully
        """
        try:
            self._session = aiohttp.ClientSession()

            # Try Terra API if configured
            if self.has_terra:
                if await self._init_terra():
                    logger.info("✅ Apple Health: Connected via Terra API")
                    self._initialized = True
                    return True

            # Fall back to webhook-only mode
            logger.info("✅ Apple Health: Ready for webhook data (Health Auto Export)")
            self._initialized = True
            return True

        except Exception as e:
            logger.error(f"Apple Health: Connection failed - {e}")
            if self._session:
                await self._session.close()
            return False

    async def disconnect(self) -> None:
        """Disconnect and cleanup."""
        if self._session:
            await self._session.close()
            self._session = None
        self._initialized = False

    # =========================================================================
    # TERRA API
    # =========================================================================

    async def _init_terra(self) -> bool:
        """Initialize Terra API connection."""
        if not self._session or not self._terra_api_key:
            return False

        try:
            # Verify connection with Terra
            headers = {
                "x-api-key": self._terra_api_key,
                "dev-id": self._terra_dev_id or "",
            }

            async with self._session.get(
                "https://api.tryterra.co/v2/auth/providers",
                headers=headers,
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    logger.debug(f"Terra providers: {data}")
                    return True
                else:
                    logger.warning(f"Terra API error: {resp.status}")
                    return False

        except Exception as e:
            logger.debug(f"Terra API init failed: {e}")
            return False

    async def sync_from_terra(self) -> bool:
        """Sync latest data from Terra API.

        Returns:
            True if sync successful
        """
        if not self._session or not self.has_terra or not self._terra_user_id:
            return False

        try:
            headers = {
                "x-api-key": self._terra_api_key or "",
                "dev-id": self._terra_dev_id or "",
            }

            # Get daily data
            today = datetime.now().strftime("%Y-%m-%d")

            async with self._session.get(
                f"https://api.tryterra.co/v2/daily?user_id={self._terra_user_id}&start_date={today}&end_date={today}",
                headers=headers,
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    await self._process_terra_daily(data)
                    self._stats["terra_syncs"] += 1
                    return True

            # Get sleep data
            async with self._session.get(
                f"https://api.tryterra.co/v2/sleep?user_id={self._terra_user_id}&start_date={today}&end_date={today}",
                headers=headers,
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    await self._process_terra_sleep(data)

            self._last_sync = time.time()
            return True

        except Exception as e:
            logger.error(f"Terra sync failed: {e}")
            return False

    async def _process_terra_daily(self, data: dict) -> None:
        """Process daily data from Terra."""
        if "data" not in data:
            return

        for day in data["data"]:
            # Heart data
            if "heart_rate_data" in day:
                hr_data = day["heart_rate_data"]
                if "summary" in hr_data:
                    summary = hr_data["summary"]
                    self._state.heart.resting_heart_rate = summary.get("resting_hr_bpm")
                    self._state.heart.heart_rate = summary.get("avg_hr_bpm")

            # HRV data
            if "heart_rate_variability_data" in day:
                hrv_data = day["heart_rate_variability_data"]
                if "summary" in hrv_data:
                    self._state.heart.hrv = hrv_data["summary"].get("avg_hrv_sdnn")

            # Activity data
            if "distance_data" in day:
                dist = day["distance_data"]
                self._state.activity.steps = dist.get("steps", 0)
                # Convert meters to miles
                self._state.activity.distance_miles = dist.get("distance_meters", 0) / 1609.34

            if "calories_data" in day:
                cal = day["calories_data"]
                self._state.activity.active_calories = int(cal.get("net_activity_calories", 0))
                self._state.activity.total_calories = int(cal.get("total_burned_calories", 0))

            if "active_durations_data" in day:
                act = day["active_durations_data"]
                # Convert seconds to minutes
                self._state.activity.exercise_minutes = int(act.get("activity_seconds", 0) / 60)

            # Oxygen data
            if "oxygen_data" in day:
                ox = day["oxygen_data"]
                if "saturation_samples" in ox and ox["saturation_samples"]:
                    # Use latest sample
                    latest = ox["saturation_samples"][-1]
                    self._state.respiratory.blood_oxygen = latest.get("percentage")

        self._state.last_updated = datetime.now()

    async def _process_terra_sleep(self, data: dict) -> None:
        """Process sleep data from Terra."""
        if "data" not in data:
            return

        for sleep in data["data"]:
            if "sleep_durations_data" in sleep:
                dur = sleep["sleep_durations_data"]

                # Convert seconds to hours
                self._state.sleep.total_duration_hours = (
                    dur.get("asleep", {}).get("duration_asleep_state_seconds", 0) / 3600
                )

                self._state.sleep.deep_hours = (
                    dur.get("asleep", {}).get("duration_deep_sleep_state_seconds", 0) / 3600
                )

                self._state.sleep.rem_hours = (
                    dur.get("asleep", {}).get("duration_REM_sleep_state_seconds", 0) / 3600
                )

                self._state.sleep.core_hours = (
                    dur.get("asleep", {}).get("duration_light_sleep_state_seconds", 0) / 3600
                )

                self._state.sleep.awake_hours = (
                    dur.get("awake", {}).get("duration_awake_state_seconds", 0) / 3600
                )

            # Calculate sleep efficiency
            if self._state.sleep.time_in_bed_hours > 0:
                self._state.sleep.sleep_efficiency = (
                    self._state.sleep.total_duration_hours / self._state.sleep.time_in_bed_hours
                )

            # Calculate quality score
            self._state.sleep.quality_score = self._calculate_sleep_quality()

    def _calculate_sleep_quality(self) -> int:
        """Calculate sleep quality score (0-100)."""
        score = 0

        # Duration score (7-9 hours optimal)
        duration = self._state.sleep.total_duration_hours
        if 7 <= duration <= 9:
            score += 40
        elif 6 <= duration < 7 or 9 < duration <= 10:
            score += 30
        elif duration >= 5:
            score += 20
        else:
            score += 10

        # Deep sleep score (15-25% optimal)
        deep_pct = self._state.sleep.deep_sleep_percentage
        if 15 <= deep_pct <= 25:
            score += 30
        elif 10 <= deep_pct < 15 or 25 < deep_pct <= 30:
            score += 20
        else:
            score += 10

        # Efficiency score (> 85% good)
        efficiency = self._state.sleep.sleep_efficiency * 100
        if efficiency >= 90:
            score += 30
        elif efficiency >= 85:
            score += 25
        elif efficiency >= 80:
            score += 20
        else:
            score += 10

        return min(100, score)

    # =========================================================================
    # HEALTH AUTO EXPORT WEBHOOK
    # =========================================================================

    async def process_webhook(self, payload: dict) -> None:
        """Process webhook data from Health Auto Export app.

        Expected payload format:
        {
            "data": {
                "metrics": [
                    {
                        "name": "heart_rate",
                        "units": "bpm",
                        "data": [{"qty": 72, "date": "2025-12-30T10:00:00"}]
                    },
                    ...
                ]
            }
        }
        """
        self._stats["webhook_calls"] += 1

        try:
            metrics = payload.get("data", {}).get("metrics", [])

            for metric in metrics:
                name = metric.get("name", "")
                data_points = metric.get("data", [])

                # Process all health samples in parallel
                if data_points:
                    await asyncio.gather(
                        *[self._process_health_sample(name, point) for point in data_points],
                        return_exceptions=True,
                    )

            self._state.last_updated = datetime.now()
            logger.debug(f"Apple Health: Processed {len(metrics)} metrics from webhook")

        except Exception as e:
            logger.error(f"Apple Health: Webhook processing error - {e}")

    async def _process_health_sample(self, metric_name: str, sample: dict) -> None:
        """Process a single health sample."""
        value = sample.get("qty") or sample.get("value")
        date_str = sample.get("date")
        timestamp = datetime.fromisoformat(date_str) if date_str else datetime.now()

        self._stats["samples_received"] += 1

        # Map to our metric type
        metric_type = self._map_metric_name(metric_name)

        # Update state based on metric type
        if metric_type == HealthMetricType.HEART_RATE:
            self._state.heart.heart_rate = float(value)
            self._state.heart.timestamp = timestamp
            await self._check_heart_anomaly()

        elif metric_type == HealthMetricType.RESTING_HEART_RATE:
            self._state.heart.resting_heart_rate = float(value)

        elif metric_type == HealthMetricType.HEART_RATE_VARIABILITY:
            self._state.heart.hrv = float(value)

        elif metric_type == HealthMetricType.STEPS:
            self._state.activity.steps = int(value)

        elif metric_type == HealthMetricType.ACTIVE_CALORIES:
            self._state.activity.active_calories = int(value)

        elif metric_type == HealthMetricType.EXERCISE_MINUTES:
            self._state.activity.exercise_minutes = int(value)

        elif metric_type == HealthMetricType.BLOOD_OXYGEN:
            # Convert from 0-1 to percentage if needed
            if value <= 1:
                value = value * 100
            self._state.respiratory.blood_oxygen = float(value)
            self._state.respiratory.timestamp = timestamp
            await self._check_oxygen_anomaly()

        elif metric_type == HealthMetricType.RESPIRATORY_RATE:
            self._state.respiratory.respiratory_rate = float(value)

        elif metric_type == HealthMetricType.WEIGHT:
            # Convert kg to lbs if needed
            if value < 100:  # Likely kg
                value = value * 2.20462
            self._state.body.weight_lbs = float(value)

        elif metric_type == HealthMetricType.BODY_FAT:
            self._state.body.body_fat_percentage = float(value)

        # Emit event
        await self._emit_event(metric_type, value, timestamp)

    def _map_metric_name(self, name: str) -> HealthMetricType | None:
        """Map metric name to HealthMetricType."""
        # Check HealthKit identifiers
        if name in self.HEALTHKIT_TYPE_MAP:
            return self.HEALTHKIT_TYPE_MAP[name]

        # Check common names
        name_lower = name.lower().replace("_", "").replace(" ", "")

        mappings = {
            "heartrate": HealthMetricType.HEART_RATE,
            "restingheartrate": HealthMetricType.RESTING_HEART_RATE,
            "hrv": HealthMetricType.HEART_RATE_VARIABILITY,
            "heartratevariability": HealthMetricType.HEART_RATE_VARIABILITY,
            "steps": HealthMetricType.STEPS,
            "stepcount": HealthMetricType.STEPS,
            "activecalories": HealthMetricType.ACTIVE_CALORIES,
            "activeenergyburned": HealthMetricType.ACTIVE_CALORIES,
            "exerciseminutes": HealthMetricType.EXERCISE_MINUTES,
            "appleexercisetime": HealthMetricType.EXERCISE_MINUTES,
            "bloodoxygen": HealthMetricType.BLOOD_OXYGEN,
            "oxygensaturation": HealthMetricType.BLOOD_OXYGEN,
            "spo2": HealthMetricType.BLOOD_OXYGEN,
            "respiratoryrate": HealthMetricType.RESPIRATORY_RATE,
            "weight": HealthMetricType.WEIGHT,
            "bodymass": HealthMetricType.WEIGHT,
            "bodyfat": HealthMetricType.BODY_FAT,
            "bodyfatpercentage": HealthMetricType.BODY_FAT,
        }

        return mappings.get(name_lower)

    # =========================================================================
    # APPLE HEALTH XML IMPORT
    # =========================================================================

    async def import_from_xml(self, xml_path: Path | str) -> int:
        """Import data from Apple Health XML export.

        Args:
            xml_path: Path to export.xml from Apple Health

        Returns:
            Number of samples imported
        """
        xml_path = Path(xml_path)
        if not xml_path.exists():
            logger.error(f"Apple Health: XML file not found: {xml_path}")
            return 0

        samples_imported = 0

        try:
            # Parse XML (can be very large, use iterparse)
            for event, elem in ET.iterparse(xml_path, events=("end",)):
                if elem.tag == "Record":
                    await self._process_xml_record(elem)
                    samples_imported += 1

                    # Clear element to save memory
                    elem.clear()

                    # Progress logging
                    if samples_imported % 10000 == 0:
                        logger.info(f"Apple Health: Imported {samples_imported} samples...")

            self._stats["xml_imports"] += 1
            logger.info(f"✅ Apple Health: Imported {samples_imported} samples from XML")
            return samples_imported

        except Exception as e:
            logger.error(f"Apple Health: XML import failed - {e}")
            return samples_imported

    async def _process_xml_record(self, elem: ET.Element) -> None:
        """Process a single Record element from XML."""
        record_type = elem.get("type", "")
        value = elem.get("value")
        date_str = elem.get("startDate")

        if not value or not record_type:
            return

        # Parse timestamp
        timestamp = datetime.now()
        if date_str:
            try:
                timestamp = datetime.fromisoformat(date_str.replace(" ", "T"))
            except ValueError:
                pass

        # Create sample and process
        sample = {"qty": float(value), "date": timestamp.isoformat()}
        await self._process_health_sample(record_type, sample)

    # =========================================================================
    # ANOMALY DETECTION
    # =========================================================================

    async def _check_heart_anomaly(self) -> None:
        """Check for heart rate anomalies."""
        hr = self._state.heart.heart_rate
        rhr = self._state.heart.resting_heart_rate

        if hr is None:
            return

        # Check for significantly elevated heart rate
        threshold = (rhr or 70) * 1.8  # 80% above resting
        if hr > threshold and hr > 120:
            self._stats["anomalies_detected"] += 1
            logger.warning(f"⚠️ Apple Health: Elevated heart rate detected: {hr} bpm")
            await self._emit_event(
                HealthMetricType.HEART_RATE,
                {"value": hr, "anomaly": "elevated", "threshold": threshold},
                datetime.now(),
            )

    async def _check_oxygen_anomaly(self) -> None:
        """Check for blood oxygen anomalies."""
        spo2 = self._state.respiratory.blood_oxygen

        if spo2 is None:
            return

        if spo2 < 90:
            self._stats["anomalies_detected"] += 1
            logger.warning(f"⚠️ Apple Health: Low blood oxygen detected: {spo2}%")
            await self._emit_event(
                HealthMetricType.BLOOD_OXYGEN,
                {"value": spo2, "anomaly": "low", "status": "critical"},
                datetime.now(),
            )

    # =========================================================================
    # EVENT SYSTEM
    # =========================================================================

    def on_event(self, callback: HealthEventCallback) -> None:
        """Register callback for health events."""
        self._callbacks.append(callback)

    def remove_callback(self, callback: HealthEventCallback) -> None:
        """Remove a callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    async def _emit_event(
        self, metric_type: HealthMetricType, value: Any, timestamp: datetime
    ) -> None:
        """Emit health event to all callbacks."""
        for callback in self._callbacks:
            try:
                await callback(metric_type, value, timestamp)
            except Exception as e:
                logger.error(f"Apple Health: Callback error - {e}")

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def get_state(self) -> HealthState:
        """Get current health state."""
        return self._state

    def get_heart_data(self) -> HeartData:
        """Get current heart data."""
        return self._state.heart

    def get_sleep_data(self) -> SleepData:
        """Get current sleep data."""
        return self._state.sleep

    def get_activity_data(self) -> ActivityData:
        """Get current activity data."""
        return self._state.activity

    def get_stats(self) -> dict[str, Any]:
        """Get integration statistics."""
        return {
            **self._stats,
            "connected": self._initialized,
            "has_terra": self.has_terra,
            "last_sync": datetime.fromtimestamp(self._last_sync).isoformat()
            if self._last_sync
            else None,
            "last_updated": self._state.last_updated.isoformat(),
        }

    async def refresh(self) -> bool:
        """Refresh data from available sources.

        Returns:
            True if refresh successful
        """
        if self.has_terra:
            return await self.sync_from_terra()
        return False


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

_apple_health: AppleHealthIntegration | None = None


def get_apple_health(config: SmartHomeConfig | None = None) -> AppleHealthIntegration:
    """Get or create Apple Health integration instance."""
    global _apple_health
    if _apple_health is None:
        _apple_health = AppleHealthIntegration(config)
    return _apple_health


async def start_apple_health(config: SmartHomeConfig | None = None) -> AppleHealthIntegration:
    """Initialize and start Apple Health integration."""
    health = get_apple_health(config)
    if not health.is_connected:
        await health.connect()
    return health
