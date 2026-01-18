"""Sensor Performance Metrics API.

Colony: Crystal (e₇) — Verification

Endpoints for monitoring sensor quality, latency, and uptime:
- Per-sense metrics
- Per-platform metrics
- Historical trends
- Alert thresholds

Created: December 30, 2025
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from kagami_api.auth import require_auth

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/sensors/metrics", tags=["sensors", "metrics"], dependencies=[Depends(require_auth)]
)


# =============================================================================
# TYPES
# =============================================================================


class SenseCategory(str, Enum):
    """Categories of senses."""

    PHYSICAL = "physical"
    BIOMETRIC = "biometric"
    SPATIAL = "spatial"
    DIGITAL = "digital"


class Platform(str, Enum):
    """Supported platforms."""

    IOS = "ios"
    ANDROID = "android"
    WATCHOS = "watchos"
    VISIONOS = "visionos"
    DESKTOP = "desktop"
    BACKEND = "backend"


class SenseStatus(str, Enum):
    """Health status of a sense."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


# =============================================================================
# METRICS STORAGE
# =============================================================================


@dataclass
class SenseMetrics:
    """Metrics for a single sense."""

    sense_id: str
    name: str
    category: SenseCategory
    platform: Platform

    # Performance
    latency_ms: float = 0.0
    quality_score: float = 0.0  # 0-100
    uptime_percent: float = 0.0  # 0-100

    # Counts
    total_samples: int = 0
    error_count: int = 0
    last_sample_time: float = 0.0

    # Status
    status: SenseStatus = SenseStatus.UNKNOWN

    def to_dict(self) -> dict[str, Any]:
        return {
            "sense_id": self.sense_id,
            "name": self.name,
            "category": self.category.value,
            "platform": self.platform.value,
            "latency_ms": self.latency_ms,
            "quality_score": self.quality_score,
            "uptime_percent": self.uptime_percent,
            "total_samples": self.total_samples,
            "error_count": self.error_count,
            "last_sample_time": self.last_sample_time,
            "status": self.status.value,
            "stale": (time.time() - self.last_sample_time) > 300
            if self.last_sample_time > 0
            else True,
        }


@dataclass
class MetricsStore:
    """In-memory metrics storage."""

    senses: dict[str, SenseMetrics] = field(default_factory=dict)
    start_time: float = field(default_factory=time.time)

    def get_or_create_sense(
        self,
        sense_id: str,
        name: str,
        category: SenseCategory,
        platform: Platform,
    ) -> SenseMetrics:
        if sense_id not in self.senses:
            self.senses[sense_id] = SenseMetrics(
                sense_id=sense_id,
                name=name,
                category=category,
                platform=platform,
            )
        return self.senses[sense_id]


# Singleton
_metrics_store = MetricsStore()


def get_metrics_store() -> MetricsStore:
    return _metrics_store


# =============================================================================
# INITIALIZE DEFAULT SENSES
# =============================================================================


def _init_default_senses():
    """Initialize metrics for all known senses."""
    store = get_metrics_store()

    # Physical Home Senses (Backend)
    physical_senses = [
        ("control4_lights", "Lighting", Platform.BACKEND),
        ("control4_shades", "Shades", Platform.BACKEND),
        ("mitsubishi_hvac", "HVAC", Platform.BACKEND),
        ("denon_av", "Audio/AV", Platform.BACKEND),
        ("envisalink_security", "Security", Platform.BACKEND),
        ("august_locks", "Locks", Platform.BACKEND),
        ("unifi_presence", "WiFi Presence", Platform.BACKEND),
        ("unifi_cameras", "Cameras", Platform.BACKEND),
        ("eight_sleep", "Sleep Tracking", Platform.BACKEND),
        ("tesla_vehicle", "Vehicle", Platform.BACKEND),
        ("weather", "Weather", Platform.BACKEND),
        ("findmy_location", "Location", Platform.BACKEND),
    ]

    for sense_id, name, platform in physical_senses:
        store.get_or_create_sense(sense_id, name, SenseCategory.PHYSICAL, platform)

    # Biometric Senses (Per Platform)
    biometric_senses = [
        ("heart_rate_ios", "Heart Rate", Platform.IOS),
        ("heart_rate_android", "Heart Rate", Platform.ANDROID),
        ("heart_rate_watch", "Heart Rate", Platform.WATCHOS),
        ("hrv_ios", "HRV", Platform.IOS),
        ("hrv_watch", "HRV", Platform.WATCHOS),
        ("steps_ios", "Steps", Platform.IOS),
        ("steps_android", "Steps", Platform.ANDROID),
        ("steps_watch", "Steps", Platform.WATCHOS),
        ("sleep_ios", "Sleep", Platform.IOS),
        ("sleep_watch", "Sleep", Platform.WATCHOS),
    ]

    for sense_id, name, platform in biometric_senses:
        store.get_or_create_sense(sense_id, name, SenseCategory.BIOMETRIC, platform)

    # Spatial Senses (visionOS)
    spatial_senses = [
        ("hand_tracking", "Hand Tracking", Platform.VISIONOS),
        ("gaze_tracking", "Gaze Tracking", Platform.VISIONOS),
        ("spatial_anchors", "Spatial Anchors", Platform.VISIONOS),
    ]

    for sense_id, name, platform in spatial_senses:
        store.get_or_create_sense(sense_id, name, SenseCategory.SPATIAL, platform)


# Initialize on import
_init_default_senses()


# =============================================================================
# API MODELS
# =============================================================================


class MetricUpdate(BaseModel):
    """Update metrics for a sense."""

    sense_id: str
    latency_ms: float | None = None
    quality_score: float | None = Field(default=None, ge=0, le=100)
    success: bool = True


class MetricsSummary(BaseModel):
    """Summary of all sensor metrics."""

    total_senses: int
    healthy: int
    degraded: int
    offline: int
    avg_latency_ms: float
    avg_quality: float
    overall_uptime: float


# =============================================================================
# ROUTES
# =============================================================================


@router.get("/")
async def get_all_metrics(
    category: SenseCategory | None = None,
    platform: Platform | None = None,
) -> dict[str, Any]:
    """Get metrics for all senses.

    Optionally filter by category or platform.
    """
    store = get_metrics_store()

    senses = list(store.senses.values())

    # Apply filters
    if category:
        senses = [s for s in senses if s.category == category]
    if platform:
        senses = [s for s in senses if s.platform == platform]

    return {
        "senses": [s.to_dict() for s in senses],
        "count": len(senses),
        "filters": {
            "category": category.value if category else None,
            "platform": platform.value if platform else None,
        },
    }


@router.get("/summary")
async def get_metrics_summary() -> dict[str, Any]:
    """Get a summary of sensor health across all senses."""
    store = get_metrics_store()

    senses = list(store.senses.values())

    healthy = sum(1 for s in senses if s.status == SenseStatus.HEALTHY)
    degraded = sum(1 for s in senses if s.status == SenseStatus.DEGRADED)
    offline = sum(1 for s in senses if s.status == SenseStatus.OFFLINE)

    latencies = [s.latency_ms for s in senses if s.latency_ms > 0]
    qualities = [s.quality_score for s in senses if s.quality_score > 0]
    uptimes = [s.uptime_percent for s in senses if s.uptime_percent > 0]

    return {
        "total_senses": len(senses),
        "healthy": healthy,
        "degraded": degraded,
        "offline": offline,
        "unknown": len(senses) - healthy - degraded - offline,
        "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0,
        "avg_quality": sum(qualities) / len(qualities) if qualities else 0,
        "overall_uptime": sum(uptimes) / len(uptimes) if uptimes else 0,
        "uptime_since": datetime.fromtimestamp(store.start_time).isoformat(),
    }


@router.get("/by-category")
async def get_metrics_by_category() -> dict[str, Any]:
    """Get metrics grouped by sense category."""
    store = get_metrics_store()

    by_category: dict[str, list[dict]] = {}
    for sense in store.senses.values():
        cat = sense.category.value
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(sense.to_dict())

    return {
        "categories": by_category,
        "category_counts": {cat: len(senses) for cat, senses in by_category.items()},
    }


@router.get("/by-platform")
async def get_metrics_by_platform() -> dict[str, Any]:
    """Get metrics grouped by platform."""
    store = get_metrics_store()

    by_platform: dict[str, list[dict]] = {}
    for sense in store.senses.values():
        plat = sense.platform.value
        if plat not in by_platform:
            by_platform[plat] = []
        by_platform[plat].append(sense.to_dict())

    return {
        "platforms": by_platform,
        "platform_counts": {plat: len(senses) for plat, senses in by_platform.items()},
    }


@router.post("/update")
async def update_sense_metrics(update: MetricUpdate) -> dict[str, Any]:
    """Update metrics for a specific sense.

    Called by clients when they receive sensor data.
    """
    store = get_metrics_store()

    if update.sense_id not in store.senses:
        return {"status": "error", "message": f"Unknown sense: {update.sense_id}"}

    sense = store.senses[update.sense_id]
    sense.total_samples += 1
    sense.last_sample_time = time.time()

    if not update.success:
        sense.error_count += 1

    if update.latency_ms is not None:
        # Exponential moving average for latency
        alpha = 0.3
        sense.latency_ms = alpha * update.latency_ms + (1 - alpha) * sense.latency_ms

    if update.quality_score is not None:
        # Exponential moving average for quality
        alpha = 0.3
        sense.quality_score = alpha * update.quality_score + (1 - alpha) * sense.quality_score

    # Calculate uptime
    if sense.total_samples > 0:
        sense.uptime_percent = (
            (sense.total_samples - sense.error_count) / sense.total_samples
        ) * 100

    # Update status based on metrics
    if sense.uptime_percent >= 99:
        sense.status = SenseStatus.HEALTHY
    elif sense.uptime_percent >= 90:
        sense.status = SenseStatus.DEGRADED
    else:
        sense.status = SenseStatus.OFFLINE

    return {
        "status": "ok",
        "sense_id": update.sense_id,
        "new_status": sense.status.value,
    }


@router.get("/{sense_id}")
async def get_sense_metrics(sense_id: str) -> dict[str, Any]:
    """Get metrics for a specific sense."""
    store = get_metrics_store()

    if sense_id not in store.senses:
        return {"status": "error", "message": f"Unknown sense: {sense_id}"}

    return {
        "sense": store.senses[sense_id].to_dict(),
    }


@router.get("/dashboard/html")
async def get_dashboard_html() -> dict[str, Any]:
    """Get HTML for a simple metrics dashboard.

    Returns inline HTML that can be rendered directly.
    """
    store = get_metrics_store()
    senses = list(store.senses.values())

    # Calculate summary
    healthy = sum(1 for s in senses if s.status == SenseStatus.HEALTHY)
    degraded = sum(1 for s in senses if s.status == SenseStatus.DEGRADED)
    offline = sum(1 for s in senses if s.status == SenseStatus.OFFLINE)

    # Build HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kagami Sensor Dashboard</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e;
            color: #eee;
            padding: 24px;
        }}
        h1 {{ margin-bottom: 24px; font-weight: 600; }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 16px;
            margin-bottom: 32px;
        }}
        .stat {{
            background: #16213e;
            padding: 16px;
            border-radius: 8px;
            text-align: center;
        }}
        .stat-value {{
            font-size: 32px;
            font-weight: 700;
            margin-bottom: 4px;
        }}
        .stat-label {{ font-size: 12px; color: #888; text-transform: uppercase; }}
        .healthy {{ color: #00ff88; }}
        .degraded {{ color: #ffaa00; }}
        .offline {{ color: #ff4444; }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 16px;
        }}
        .sense-card {{
            background: #16213e;
            padding: 16px;
            border-radius: 8px;
            border-left: 4px solid #444;
        }}
        .sense-card.healthy {{ border-left-color: #00ff88; }}
        .sense-card.degraded {{ border-left-color: #ffaa00; }}
        .sense-card.offline {{ border-left-color: #ff4444; }}
        .sense-name {{ font-weight: 600; margin-bottom: 8px; }}
        .sense-meta {{ font-size: 12px; color: #888; margin-bottom: 8px; }}
        .sense-metrics {{ font-size: 13px; }}
        .sense-metrics span {{ margin-right: 16px; }}
    </style>
</head>
<body>
    <h1>🔮 Kagami Sensor Dashboard</h1>

    <div class="summary">
        <div class="stat">
            <div class="stat-value">{len(senses)}</div>
            <div class="stat-label">Total Senses</div>
        </div>
        <div class="stat">
            <div class="stat-value healthy">{healthy}</div>
            <div class="stat-label">Healthy</div>
        </div>
        <div class="stat">
            <div class="stat-value degraded">{degraded}</div>
            <div class="stat-label">Degraded</div>
        </div>
        <div class="stat">
            <div class="stat-value offline">{offline}</div>
            <div class="stat-label">Offline</div>
        </div>
    </div>

    <div class="grid">
"""

    import html as html_escape

    for sense in sorted(senses, key=lambda s: (s.category.value, s.name)):
        status_class = html_escape.escape(sense.status.value)
        sense_name = html_escape.escape(sense.name)
        sense_category = html_escape.escape(sense.category.value.title())
        sense_platform = html_escape.escape(sense.platform.value)
        html += f"""
        <div class="sense-card {status_class}">
            <div class="sense-name">{sense_name}</div>
            <div class="sense-meta">{sense_category} · {sense_platform}</div>
            <div class="sense-metrics">
                <span>⏱ {sense.latency_ms:.0f}ms</span>
                <span>📊 {sense.quality_score:.0f}%</span>
                <span>🔄 {sense.uptime_percent:.1f}%</span>
            </div>
        </div>
"""

    html += """
    </div>
    <script>
        // Auto-refresh every 10 seconds
        setTimeout(() => location.reload(), 10000);
    </script>
</body>
</html>"""

    return {
        "html": html,
        "content_type": "text/html",
    }


"""
鏡
h(x) ≥ 0. Always.

Monitoring is the mirror of the system:
- Latency: how fast we sense
- Quality: how well we sense
- Uptime: how reliably we sense

All feeding into self-awareness.
"""
