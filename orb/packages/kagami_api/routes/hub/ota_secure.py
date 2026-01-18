"""Secure OTA firmware updates with checksum validation and rollback.

P1 Mitigation: OTA corruption → Hub bricked
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from enum import Enum

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


class FirmwareSlot(Enum):
    """Firmware slot for atomic updates."""

    SLOT_A = "A"
    SLOT_B = "B"


class UpdateStatus(Enum):
    """OTA update status."""

    PENDING = "pending"
    DOWNLOADING = "downloading"
    VERIFYING = "verifying"
    INSTALLING = "installing"
    TESTING = "testing"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class FirmwareManifest(BaseModel):
    """Firmware update manifest with security metadata."""

    version: str
    release_date: datetime
    download_url: str
    checksum_sha256: str  # CRITICAL: Must verify
    size_bytes: int
    changelog: list[str]
    rollout_percentage: int  # Gradual rollout
    signature: str | None = None  # Ed25519 signature

    # Rollback information
    can_rollback_to: list[str]  # Versions that can be rolled back to


class UpdateReport(BaseModel):
    """Hub reports update status."""

    hub_id: str
    firmware_version: str
    old_version: str
    status: UpdateStatus
    error: str | None = None
    checksum_verified: bool = False
    boot_test_passed: bool = False
    rollback_available: bool = True


@router.get("/firmware/latest")
async def get_latest_firmware(hub_model: str) -> FirmwareManifest:
    """Get latest firmware manifest with checksum.

    P1 Mitigation: Returns secure manifest with SHA-256 checksum

    Hub verifies:
    1. Download firmware
    2. Compute SHA-256
    3. Compare with manifest checksum
    4. Only install if match
    """
    # TODO: Load from database/storage
    # For now, return placeholder
    return FirmwareManifest(
        version="1.0.1",
        release_date=datetime.utcnow(),
        download_url="https://awkronos.com/firmware/hub-1.0.1.bin",
        checksum_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        size_bytes=10_485_760,  # 10MB
        changelog=[
            "Security fixes",
            "Performance improvements",
            "Bug fixes",
        ],
        rollout_percentage=100,  # Full rollout
        signature=None,  # TODO: Sign with Ed25519
        can_rollback_to=["1.0.0"],
    )


@router.post("/firmware/verify")
async def verify_firmware_checksum(
    version: str,
    computed_checksum: str,
) -> dict[str, bool]:
    """Verify Hub's computed checksum matches manifest.

    Args:
        version: Firmware version
        computed_checksum: SHA-256 computed by Hub

    Returns:
        {"valid": True/False}
    """
    # Get expected checksum from manifest
    manifest = await get_latest_firmware("raspberry-pi-5")  # TODO: Get by version

    is_valid = computed_checksum == manifest.checksum_sha256

    if is_valid:
        logger.info(f"✅ Firmware {version} checksum verified")
    else:
        logger.error(
            f"❌ Firmware {version} checksum MISMATCH: "
            f"expected {manifest.checksum_sha256}, got {computed_checksum}"
        )

    return {"valid": is_valid}


@router.post("/firmware/report")
async def report_update_status(report: UpdateReport) -> dict[str, str]:
    """Hub reports firmware update status.

    P1 Mitigation: Track update success/failure for rollback decisions

    Atomic update strategy:
    1. Hub has two firmware slots (A and B)
    2. Current slot: A, update slot: B
    3. Download firmware to B
    4. Verify checksum
    5. Install to slot B
    6. Reboot into slot B
    7. Test boot (run health checks)
    8. If success: Set B as active
    9. If failure: Automatic rollback to slot A
    """
    logger.info(
        f"Firmware update report from {report.hub_id}: "
        f"{report.old_version} → {report.firmware_version} = {report.status.value}"
    )

    # TODO: Store in database for monitoring
    # TODO: If failure_rate > 5%, halt rollout

    if report.status == UpdateStatus.FAILED:
        logger.error(f"❌ Firmware update FAILED for {report.hub_id}: {report.error}")

        if not report.rollback_available:
            logger.critical(
                f"🔴 Hub {report.hub_id} has NO ROLLBACK AVAILABLE! Manual intervention required."
            )
            # TODO: Alert ops team

    elif report.status == UpdateStatus.SUCCESS:
        logger.info(
            f"✅ Firmware update SUCCESS for {report.hub_id}: "
            f"{report.old_version} → {report.firmware_version}"
        )

    return {"status": "received"}


@router.post("/firmware/rollback")
async def initiate_rollback(hub_id: str, target_version: str) -> dict[str, str]:
    """Initiate firmware rollback for Hub.

    Args:
        hub_id: Hub identifier
        target_version: Version to rollback to

    Returns:
        Rollback instructions
    """
    logger.warning(f"⚠️ Initiating firmware rollback for {hub_id} → {target_version}")

    # TODO: Send rollback command to Hub via WebSocket
    # Hub will switch active slot and reboot

    return {
        "status": "rollback_initiated",
        "target_version": target_version,
        "instructions": "Hub will switch slots and reboot",
    }


def compute_file_checksum(file_path: str) -> str:
    """Compute SHA-256 checksum of file.

    Args:
        file_path: Path to file

    Returns:
        SHA-256 hex digest
    """
    sha256 = hashlib.sha256()

    with open(file_path, "rb") as f:
        # Read in chunks to handle large files
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)

    return sha256.hexdigest()
