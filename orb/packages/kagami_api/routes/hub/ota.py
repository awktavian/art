"""OTA (Over-The-Air) Update Endpoints.

Provides firmware distribution and update management for Kagami Hubs.

Flow:
1. Hub checks for updates → GET /hub/ota/check
2. If update available, download firmware → GET /hub/ota/download/{version}
3. Hub applies update and reports status → POST /hub/ota/report

Colony: Nexus (e₄) → Firmware distribution

η → s → μ → a → η′
h(x) ≥ 0. Always.
"""

from datetime import datetime
from pathlib import Path

import structlog
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/ota", tags=["ota"])


# ============================================================================
# Models
# ============================================================================


class FirmwareInfo(BaseModel):
    """Information about a firmware version."""

    version: str = Field(..., description="Semantic version (e.g., '1.2.3')")
    channel: str = Field(default="stable", description="Release channel")
    release_date: datetime = Field(..., description="When this version was released")
    size_bytes: int = Field(..., description="Firmware file size")
    sha256: str = Field(..., description="SHA256 hash of firmware file")
    min_version: str | None = Field(None, description="Minimum version that can upgrade to this")
    changelog: str = Field(default="", description="Release notes")
    is_critical: bool = Field(default=False, description="Critical security update")
    rollback_version: str | None = Field(None, description="Safe version to rollback to")


class UpdateCheckRequest(BaseModel):
    """Request to check for updates."""

    current_version: str = Field(..., description="Current firmware version")
    hub_id: str = Field(..., description="Unique hub identifier")
    channel: str = Field(default="stable", description="Release channel preference")
    hardware_revision: str | None = Field(None, description="Hardware revision")


class UpdateCheckResponse(BaseModel):
    """Response to update check."""

    update_available: bool = Field(..., description="Whether an update is available")
    current_version: str = Field(..., description="Hub's current version")
    latest_version: str | None = Field(None, description="Latest available version")
    firmware_info: FirmwareInfo | None = Field(None, description="Info about available update")
    download_url: str | None = Field(None, description="URL to download firmware")


class UpdateReport(BaseModel):
    """Report from hub after update attempt."""

    hub_id: str = Field(..., description="Unique hub identifier")
    old_version: str = Field(..., description="Version before update")
    new_version: str = Field(..., description="Version after update (or attempted)")
    success: bool = Field(..., description="Whether update succeeded")
    error_message: str | None = Field(None, description="Error if failed")
    update_duration_seconds: int | None = Field(None, description="How long update took")
    rollback_performed: bool = Field(default=False, description="Whether rollback occurred")


class UpdateReportResponse(BaseModel):
    """Response to update report."""

    acknowledged: bool = Field(default=True)
    message: str = Field(default="Update report received")
    recommended_action: str | None = Field(None, description="Suggested next step")


# ============================================================================
# In-Memory Storage (Replace with DB in production)
# ============================================================================

# Simulated firmware registry
FIRMWARE_REGISTRY: dict[str, dict[str, FirmwareInfo]] = {
    "stable": {
        "1.0.0": FirmwareInfo(
            version="1.0.0",
            channel="stable",
            release_date=datetime(2025, 1, 1),
            size_bytes=15_000_000,
            sha256="a" * 64,
            changelog="Initial release",
            rollback_version=None,
        ),
        "1.1.0": FirmwareInfo(
            version="1.1.0",
            channel="stable",
            release_date=datetime(2025, 12, 15),
            size_bytes=15_500_000,
            sha256="b" * 64,
            min_version="1.0.0",
            changelog="- Added CRDT state sync\n- Improved wake word detection",
            rollback_version="1.0.0",
        ),
        "1.2.0": FirmwareInfo(
            version="1.2.0",
            channel="stable",
            release_date=datetime(2025, 12, 30),
            size_bytes=16_000_000,
            sha256="c" * 64,
            min_version="1.0.0",
            changelog="- Cross-hub command routing\n- LLM integration\n- Speaker identification",
            rollback_version="1.1.0",
        ),
    },
    "beta": {
        "1.3.0-beta.1": FirmwareInfo(
            version="1.3.0-beta.1",
            channel="beta",
            release_date=datetime(2026, 1, 1),
            size_bytes=16_500_000,
            sha256="d" * 64,
            min_version="1.1.0",
            changelog="- Face identification\n- Fleet dashboard\n- OTA improvements",
            rollback_version="1.2.0",
        ),
    },
}

# Update history per hub
UPDATE_HISTORY: dict[str, list[UpdateReport]] = {}

# Firmware files directory (configure in production)
FIRMWARE_DIR = Path("/var/kagami/firmware")


# ============================================================================
# Helper Functions
# ============================================================================


def parse_version(version: str) -> tuple[int, ...]:
    """Parse semantic version to tuple for comparison."""
    # Handle beta/rc versions
    clean_version = version.split("-")[0]
    return tuple(int(x) for x in clean_version.split("."))


def is_newer_version(current: str, candidate: str) -> bool:
    """Check if candidate is newer than current."""
    return parse_version(candidate) > parse_version(current)


def get_latest_version(channel: str) -> FirmwareInfo | None:
    """Get the latest firmware for a channel."""
    channel_firmware = FIRMWARE_REGISTRY.get(channel, {})
    if not channel_firmware:
        return None

    # Sort by version and get latest
    versions = sorted(channel_firmware.keys(), key=parse_version, reverse=True)
    return channel_firmware.get(versions[0]) if versions else None


def can_upgrade(current: str, target: FirmwareInfo) -> bool:
    """Check if upgrade path is valid."""
    if target.min_version is None:
        return True
    return parse_version(current) >= parse_version(target.min_version)


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/check", response_model=UpdateCheckResponse)
async def check_for_updates(request: UpdateCheckRequest):
    """Check if firmware updates are available.

    The hub calls this endpoint periodically to check for updates.
    Returns update info if a newer compatible version exists.
    """
    logger.info(
        "ota_check",
        hub_id=request.hub_id,
        current_version=request.current_version,
        channel=request.channel,
    )

    latest = get_latest_version(request.channel)

    if latest is None:
        return UpdateCheckResponse(
            update_available=False,
            current_version=request.current_version,
            latest_version=None,
            firmware_info=None,
            download_url=None,
        )

    # Check if newer and compatible
    update_available = is_newer_version(request.current_version, latest.version) and can_upgrade(
        request.current_version, latest
    )

    if update_available:
        download_url = f"/api/v1/hub/ota/download/{latest.version}?channel={request.channel}"

        logger.info(
            "ota_update_available",
            hub_id=request.hub_id,
            current=request.current_version,
            latest=latest.version,
        )

        return UpdateCheckResponse(
            update_available=True,
            current_version=request.current_version,
            latest_version=latest.version,
            firmware_info=latest,
            download_url=download_url,
        )

    return UpdateCheckResponse(
        update_available=False,
        current_version=request.current_version,
        latest_version=latest.version,
        firmware_info=None,
        download_url=None,
    )


@router.get("/download/{version}")
async def download_firmware(
    version: str,
    channel: str = Query(default="stable"),
    hub_id: str = Header(..., alias="X-Hub-ID"),
):
    """Download firmware binary.

    Streams the firmware file to the hub for installation.
    Requires hub authentication via X-Hub-ID header.
    """
    logger.info(
        "ota_download_start",
        hub_id=hub_id,
        version=version,
        channel=channel,
    )

    # Validate version exists
    channel_firmware = FIRMWARE_REGISTRY.get(channel, {})
    firmware_info = channel_firmware.get(version)

    if firmware_info is None:
        raise HTTPException(
            status_code=404,
            detail=f"Firmware version {version} not found in {channel} channel",
        )

    # In production, serve actual firmware file
    # For now, return a placeholder response
    firmware_path = FIRMWARE_DIR / channel / f"kagami-hub-{version}.bin"

    if firmware_path.exists():
        return FileResponse(
            path=firmware_path,
            media_type="application/octet-stream",
            filename=f"kagami-hub-{version}.bin",
            headers={
                "X-Firmware-Version": version,
                "X-Firmware-SHA256": firmware_info.sha256,
                "X-Firmware-Size": str(firmware_info.size_bytes),
            },
        )

    # Development mode: return mock response
    logger.warning("ota_mock_download", version=version, reason="File not found")

    raise HTTPException(
        status_code=503,
        detail="Firmware file not available (development mode)",
    )


@router.post("/report", response_model=UpdateReportResponse)
async def report_update_status(
    report: UpdateReport,
    background_tasks: BackgroundTasks,
):
    """Report update status after installation attempt.

    Hubs call this after attempting an update to report success/failure.
    Used for fleet monitoring and update tracking.
    """
    logger.info(
        "ota_report",
        hub_id=report.hub_id,
        old_version=report.old_version,
        new_version=report.new_version,
        success=report.success,
        rollback=report.rollback_performed,
    )

    # Store report
    if report.hub_id not in UPDATE_HISTORY:
        UPDATE_HISTORY[report.hub_id] = []
    UPDATE_HISTORY[report.hub_id].append(report)

    # Determine recommended action
    recommended_action = None

    if not report.success:
        if report.rollback_performed:
            recommended_action = "Rollback successful. Manual intervention may be required."
        else:
            recommended_action = "Consider initiating manual rollback via /hub/ota/rollback"

        logger.error(
            "ota_update_failed",
            hub_id=report.hub_id,
            error=report.error_message,
            rollback=report.rollback_performed,
        )
    else:
        logger.info(
            "ota_update_success",
            hub_id=report.hub_id,
            new_version=report.new_version,
            duration_s=report.update_duration_seconds,
        )

    return UpdateReportResponse(
        acknowledged=True,
        message="Update report recorded",
        recommended_action=recommended_action,
    )


@router.get("/versions")
async def list_versions(
    channel: str = Query(default="stable"),
    limit: int = Query(default=10, le=50),
):
    """List available firmware versions.

    Returns all available versions for a channel, sorted newest first.
    """
    channel_firmware = FIRMWARE_REGISTRY.get(channel, {})

    versions = sorted(
        channel_firmware.values(),
        key=lambda f: parse_version(f.version),
        reverse=True,
    )[:limit]

    return {
        "channel": channel,
        "versions": versions,
        "total": len(channel_firmware),
    }


@router.post("/rollback/{hub_id}")
async def initiate_rollback(
    hub_id: str,
    target_version: str | None = Query(None, description="Version to rollback to"),
):
    """Initiate a rollback for a specific hub.

    This schedules a rollback command to be sent to the hub on next check-in.
    If no target_version specified, uses the firmware's recommended rollback version.
    """
    logger.info(
        "ota_rollback_initiated",
        hub_id=hub_id,
        target_version=target_version,
    )

    # In production, this would queue a rollback command
    return {
        "status": "scheduled",
        "hub_id": hub_id,
        "target_version": target_version or "auto",
        "message": "Rollback scheduled for next hub check-in",
    }


@router.get("/history/{hub_id}")
async def get_update_history(
    hub_id: str,
    limit: int = Query(default=10, le=50),
):
    """Get update history for a specific hub."""
    history = UPDATE_HISTORY.get(hub_id, [])

    return {
        "hub_id": hub_id,
        "updates": history[-limit:],
        "total": len(history),
    }


# ============================================================================
# Admin Endpoints
# ============================================================================


@router.post("/admin/publish")
async def publish_firmware(
    firmware: FirmwareInfo,
    # auth: AdminAuth = Depends(require_admin),  # Add proper auth
):
    """Publish a new firmware version (admin only).

    Adds a new firmware version to the registry.
    """
    logger.info(
        "ota_publish",
        version=firmware.version,
        channel=firmware.channel,
    )

    if firmware.channel not in FIRMWARE_REGISTRY:
        FIRMWARE_REGISTRY[firmware.channel] = {}

    FIRMWARE_REGISTRY[firmware.channel][firmware.version] = firmware

    return {
        "status": "published",
        "version": firmware.version,
        "channel": firmware.channel,
    }


"""
鏡
Firmware flows. Hubs evolve. The mesh grows stronger.
h(x) ≥ 0. Always.
"""
