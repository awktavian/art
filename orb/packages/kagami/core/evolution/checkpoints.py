from __future__ import annotations

from kagami.core.async_utils import safe_create_task

"""Evolution Checkpoints & Rollback System.

Save state before every change, verify for 1hr, auto-rollback on degradation.

Ensures every improvement can be undone if problems emerge.
"""
import asyncio
import json
import logging
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class MetricsCollector(Protocol):
    """Protocol for metric collectors."""

    async def collect(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        """Collect metrics and update snapshot."""
        ...


class ModelMetricsCollector:
    """Collects raw metrics from Prometheus registry."""

    async def collect(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        """Collect Prometheus metrics."""
        try:
            from prometheus_client import REGISTRY

            for metric in REGISTRY.collect():
                self._process_metric(metric, snapshot)

        except ImportError:
            logger.debug("Prometheus client not available")
        except Exception as e:
            logger.warning(f"Error collecting Prometheus metrics: {e}")

        return snapshot

    def _process_metric(self, metric: Any, snapshot: dict[str, Any]) -> None:
        """Process individual metric and update snapshot."""
        metric_name = metric.name

        for sample in metric.samples:
            self._process_request_metrics(metric_name, sample, snapshot)
            self._process_latency_metrics(metric_name, sample, snapshot)
            self._process_throughput_metrics(metric_name, sample, snapshot)
            self._process_uptime_metrics(metric_name, sample, snapshot)

    def _process_request_metrics(
        self, metric_name: str, sample: Any, snapshot: dict[str, Any]
    ) -> None:
        """Process HTTP request metrics for error rate."""
        if "http_requests_total" in metric_name or "kagami_requests_total" in metric_name:
            labels = sample.labels
            if labels.get("status", "").startswith("5"):
                snapshot["_error_count"] = snapshot.get("_error_count", 0) + sample.value
            snapshot["_total_requests"] = snapshot.get("_total_requests", 0) + sample.value

    def _process_latency_metrics(
        self, metric_name: str, sample: Any, snapshot: dict[str, Any]
    ) -> None:
        """Process latency histogram for p95 calculation."""
        is_duration_metric = (
            "http_request_duration" in metric_name or "kagami_request_duration" in metric_name
        )
        if is_duration_metric and "_bucket" in sample.name:
            if "le" in sample.labels and sample.labels["le"] != "+Inf":
                try:
                    bucket_le = float(sample.labels["le"])
                    bucket_count = sample.value
                    if "_latency_buckets" not in snapshot:
                        snapshot["_latency_buckets"] = []
                    snapshot["_latency_buckets"].append((bucket_le, bucket_count))
                except (ValueError, TypeError):
                    pass

    def _process_throughput_metrics(
        self, metric_name: str, sample: Any, snapshot: dict[str, Any]
    ) -> None:
        """Process throughput counters."""
        if "operations_total" in metric_name or "requests_total" in metric_name:
            snapshot["_ops_count"] = snapshot.get("_ops_count", 0) + sample.value

    def _process_uptime_metrics(
        self, metric_name: str, sample: Any, snapshot: dict[str, Any]
    ) -> None:
        """Process uptime metrics."""
        if "uptime" in metric_name or "start_time" in metric_name:
            if sample.value > 0:
                if "start_time" in metric_name:
                    snapshot["uptime"] = time.time() - sample.value
                else:
                    snapshot["uptime"] = sample.value


class PerformanceMetricsCollector:
    """Calculates derived performance metrics from raw data."""

    async def collect(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        """Calculate derived metrics."""
        self._calculate_error_rate(snapshot)
        self._calculate_p95_latency(snapshot)
        self._calculate_throughput(snapshot)
        return snapshot

    def _calculate_error_rate(self, snapshot: dict[str, Any]) -> None:
        """Calculate error rate from request counts."""
        total_requests = snapshot.pop("_total_requests", 0)
        error_count = snapshot.pop("_error_count", 0)
        if total_requests > 0:
            snapshot["error_rate"] = error_count / total_requests

    def _calculate_p95_latency(self, snapshot: dict[str, Any]) -> None:
        """Calculate p95 latency from histogram buckets."""
        latency_buckets = snapshot.pop("_latency_buckets", [])
        if not latency_buckets:
            return

        latency_buckets.sort(key=lambda x: x[0])
        total_count = latency_buckets[-1][1] if latency_buckets else 0

        if total_count > 0:
            p95_target = total_count * 0.95
            for bucket_le, bucket_count in latency_buckets:
                if bucket_count >= p95_target:
                    # Convert to milliseconds if in seconds
                    snapshot["p95_latency_ms"] = bucket_le * 1000 if bucket_le < 10 else bucket_le
                    break

    def _calculate_throughput(self, snapshot: dict[str, Any]) -> None:
        """Calculate throughput from operation counts."""
        ops_count = snapshot.pop("_ops_count", 0)
        uptime = snapshot.get("uptime", 0)

        if ops_count > 0 and uptime > 0:
            snapshot["throughput_ops_s"] = ops_count / min(uptime, 60)


class ResourceMetricsCollector:
    """Fallback collector using health endpoint."""

    async def collect(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        """Collect metrics from health endpoint if Prometheus unavailable."""
        # Only fallback if throughput still zero
        if snapshot.get("throughput_ops_s", 0) == 0:
            await self._fetch_health_metrics(snapshot)
        return snapshot

    async def _fetch_health_metrics(self, snapshot: dict[str, Any]) -> None:
        """Fetch metrics from health endpoint."""
        try:
            import aiohttp

            async with (
                aiohttp.ClientSession() as session,
                session.get(
                    "http://localhost:8000/health",
                    timeout=aiohttp.ClientTimeout(total=2),
                ) as resp,
            ):
                if resp.status == 200:
                    health = await resp.json()
                    self._update_from_health(health, snapshot)
        except Exception:
            pass  # Health endpoint unavailable

    def _update_from_health(self, health: dict[str, Any], snapshot: dict[str, Any]) -> None:
        """Update snapshot with health endpoint metrics."""
        if "metrics" in health:
            metrics = health["metrics"]
            snapshot.update(
                {
                    "error_rate": metrics.get("error_rate", snapshot["error_rate"]),
                    "p95_latency_ms": metrics.get("p95_latency_ms", snapshot["p95_latency_ms"]),
                    "throughput_ops_s": metrics.get(
                        "throughput_ops_s", snapshot["throughput_ops_s"]
                    ),
                }
            )


@dataclass
class Checkpoint:
    """A saved system state checkpoint."""

    checkpoint_id: str
    created_at: float
    proposal_id: str
    files_changed: list[str]
    backup_path: Path
    metrics_snapshot: dict[str, Any]
    verification_window_s: float = 3600  # 1 hour default
    status: str = "verifying"  # "verifying", "verified", "rolled_back"


class EvolutionCheckpoints:
    """Manage checkpoints and rollback for evolution."""

    def __init__(self, checkpoint_dir: Path | None = None) -> None:
        self._checkpoint_dir = checkpoint_dir or Path.cwd() / "var" / "evolution_checkpoints"
        self._checkpoint_dir.mkdir(parents=True, exist_ok=True)

        self._active_checkpoints: dict[str, Checkpoint] = {}
        self._checkpoint_history: list[Checkpoint] = []

    async def create_checkpoint(self, proposal_id: str, files_to_change: list[str]) -> Checkpoint:
        """Create checkpoint before applying improvement.

        Args:
            proposal_id: ID of proposal about to be applied
            files_to_change: List of files that will be modified

        Returns:
            Checkpoint object
        """
        import hashlib

        checkpoint_id = hashlib.sha256(f"{proposal_id}:{time.time()}".encode()).hexdigest()[:16]

        logger.info(f"💾 Creating checkpoint {checkpoint_id} for {proposal_id}")

        # Create backup directory
        backup_path = self._checkpoint_dir / checkpoint_id
        backup_path.mkdir(parents=True, exist_ok=True)

        # Backup files
        for file_path in files_to_change:
            src = Path(file_path)
            if src.exists():
                dst = backup_path / file_path
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

        # Capture current metrics
        metrics_snapshot = await self._capture_metrics_snapshot()

        # Create checkpoint
        checkpoint = Checkpoint(
            checkpoint_id=checkpoint_id,
            created_at=time.time(),
            proposal_id=proposal_id,
            files_changed=files_to_change,
            backup_path=backup_path,
            metrics_snapshot=metrics_snapshot,
            status="verifying",
        )

        # Save checkpoint metadata
        metadata_file = backup_path / "checkpoint.json"
        metadata_file.write_text(
            json.dumps(
                {
                    "checkpoint_id": checkpoint_id,
                    "created_at": checkpoint.created_at,
                    "proposal_id": proposal_id,
                    "files_changed": files_to_change,
                    "metrics_snapshot": metrics_snapshot,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        self._active_checkpoints[checkpoint_id] = checkpoint

        # Start verification monitoring
        safe_create_task(self._monitor_verification(checkpoint, name="_monitor_verification"))  # type: ignore  # Call sig

        return checkpoint

    async def _monitor_verification(self, checkpoint: Checkpoint) -> None:
        """Monitor metrics during verification window."""
        logger.info(
            f"👁️ Monitoring checkpoint {checkpoint.checkpoint_id} for {checkpoint.verification_window_s}s"
        )

        # Wait for verification window
        await asyncio.sleep(checkpoint.verification_window_s)

        # Collect post-change metrics
        metrics_after = await self._capture_metrics_snapshot()

        # Compare to baseline
        degraded = self._detect_degradation(checkpoint.metrics_snapshot, metrics_after)

        if degraded:
            # AUTO-ROLLBACK!
            logger.warning(
                f"⚠️ Degradation detected in checkpoint {checkpoint.checkpoint_id} - ROLLING BACK"
            )
            await self.rollback_checkpoint(checkpoint.checkpoint_id, reason="degradation_detected")
        else:
            # Mark as verified
            checkpoint.status = "verified"
            logger.info(f"✅ Checkpoint {checkpoint.checkpoint_id} VERIFIED - no degradation")

            # Clean up old checkpoints (keep last 10)
            await self._cleanup_old_checkpoints(keep_recent=10)

    async def _capture_metrics_snapshot(self) -> dict[str, Any]:
        """Capture current system metrics from observability layer.

        Queries real Prometheus metrics to get actual system performance data.
        Falls back to health endpoint if metrics unavailable.

        Returns:
            Dictionary with error_rate, p95_latency_ms, throughput_ops_s, uptime
        """
        snapshot: dict[str, Any] = {
            "timestamp": time.time(),
            "error_rate": 0.0,
            "p95_latency_ms": 0.0,
            "throughput_ops_s": 0.0,
            "uptime": 1.0,
        }

        # Create collector pipeline
        collectors: list[MetricsCollector] = [
            ModelMetricsCollector(),
            PerformanceMetricsCollector(),
            ResourceMetricsCollector(),
        ]

        # Run collectors in sequence
        for collector in collectors:
            snapshot = await collector.collect(snapshot)

        return snapshot

    def _detect_degradation(self, before: dict[str, Any], after: dict[str, Any]) -> bool:
        """Detect if metrics degraded.

        Returns:
            True if degradation detected, False otherwise
        """
        # Error rate increased >50%
        error_before = before.get("error_rate", 0)
        error_after = after.get("error_rate", 0)
        if error_after > error_before * 1.5:
            logger.warning(f"Error rate degradation: {error_before:.3f} → {error_after:.3f}")
            return True

        # Latency increased >20%
        latency_before = before.get("p95_latency_ms", 0)
        latency_after = after.get("p95_latency_ms", 0)
        if latency_after > latency_before * 1.2:
            logger.warning(f"Latency degradation: {latency_before:.1f}ms → {latency_after:.1f}ms")
            return True

        # Throughput decreased >20%
        throughput_before = before.get("throughput_ops_s", 0)
        throughput_after = after.get("throughput_ops_s", 0)
        if throughput_before > 0 and throughput_after < throughput_before * 0.8:
            logger.warning(
                f"Throughput degradation: {throughput_before:.1f} → {throughput_after:.1f} ops/s"
            )
            return True

        # No degradation detected
        return False

    async def rollback_checkpoint(
        self, checkpoint_id: str, reason: str = "Manual rollback"
    ) -> dict[str, Any]:
        """Rollback to a checkpoint.

        Args:
            checkpoint_id: ID of checkpoint to restore
            reason: Why rolling back

        Returns:
            Status dict[str, Any]
        """
        checkpoint = self._active_checkpoints.get(checkpoint_id)
        if not checkpoint:
            return {"status": "error", "message": "Checkpoint not found"}

        logger.warning(f"🔄 Rolling back checkpoint {checkpoint_id}: {reason}")

        # Restore files from backup
        for file_path in checkpoint.files_changed:
            backup_file = checkpoint.backup_path / file_path
            if backup_file.exists():
                target_file = Path(file_path)
                target_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup_file, target_file)
                logger.info(f"Restored: {file_path}")

        # Update checkpoint status
        checkpoint.status = "rolled_back"

        # Move to history
        self._checkpoint_history.append(checkpoint)
        del self._active_checkpoints[checkpoint_id]

        # Emit metric
        try:
            from kagami_observability.metrics import (
                emit_counter,
            )

            emit_counter("kagami_evolution_rollback_total", labels={"reason": reason})
        except Exception:
            pass

        return {
            "status": "rolled_back",
            "checkpoint_id": checkpoint_id,
            "files_restored": len(checkpoint.files_changed),
            "reason": reason,
        }

    async def _cleanup_old_checkpoints(self, keep_recent: int = 10) -> None:
        """Clean up old verified checkpoints."""
        verified = [cp for cp in self._checkpoint_history if cp.status == "verified"]

        if len(verified) > keep_recent:
            to_remove = verified[:-keep_recent]

            for checkpoint in to_remove:
                if checkpoint.backup_path.exists():
                    shutil.rmtree(checkpoint.backup_path, ignore_errors=True)

                self._checkpoint_history.remove(checkpoint)

            logger.info(f"Cleaned up {len(to_remove)} old checkpoints")

    def get_active_checkpoints(self) -> list[Checkpoint]:
        """Get all active (verifying) checkpoints."""
        return list(self._active_checkpoints.values())

    def get_checkpoint_history(self) -> list[dict[str, Any]]:
        """Get checkpoint history."""
        return [
            {
                "checkpoint_id": cp.checkpoint_id,
                "proposal_id": cp.proposal_id,
                "created_at": cp.created_at,
                "status": cp.status,
                "files_changed": len(cp.files_changed),
            }
            for cp in self._checkpoint_history
        ]


# Singleton
_checkpoints: EvolutionCheckpoints | None = None


def get_evolution_checkpoints() -> EvolutionCheckpoints:
    """Get global checkpoints manager."""
    global _checkpoints
    if _checkpoints is None:
        _checkpoints = EvolutionCheckpoints()
    return _checkpoints
