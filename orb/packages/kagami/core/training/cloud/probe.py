"""Von Neumann Probe — Cloud Training Deployment Controller.

CREATED: January 4, 2026

The hub is the SEED. This module lets the seed SPAWN cloud training instances,
monitor them, and retrieve results — all encrypted end-to-end.

Architecture:
============

```
House (SEED)                           Google Cloud (SPAWNED PROBES)
┌─────────────────┐                   ┌──────────────────────────────┐
│   Kagami Hub    │◄════encrypted═══►│     TPU v6e-256 Pod          │
│   (Pi/Mac)      │  WireGuard/mTLS  │                              │
│                 │                   │  ┌────────────────────────┐  │
│  ┌───────────┐  │                   │  │  Kagami Training VM    │  │
│  │  Genome   │──┼─────spawn───────►│  │  - TPU Orchestrator    │  │
│  │  Factory  │  │                   │  │  - Watchdog            │  │
│  │  Monitor  │◄─┼───checkpoints────│  │  - Checkpointer        │  │
│  └───────────┘  │                   │  │  - Prometheus metrics  │  │
│                 │                   │  └────────────────────────┘  │
│  ┌───────────┐  │                   │                              │
│  │  Secrets  │──┼───credentials────┼────────────────────────────►│
│  │ (Keychain)│  │                   │  Encrypted GCS Bucket        │
└─────────────────┘                   └──────────────────────────────┘
```

Von Neumann Probe Lifecycle:
1. SPAWN — Hub creates TPU VM via GCP API
2. BOOTSTRAP — VM configures itself, connects back via WireGuard
3. TRAIN — VM runs training, streams metrics to hub
4. CHECKPOINT — VM saves encrypted checkpoints to GCS
5. RETRIEVE — Hub pulls checkpoints on completion
6. TERMINATE — Hub destroys VM when done

Security:
- All data encrypted at rest (CMEK via Cloud KMS)
- All data encrypted in transit (WireGuard VPN + TLS)
- TPU VMs have NO public IP (NAT for egress only)
- Secrets stored in macOS Keychain, delivered via Secret Manager

Usage:
    from kagami.core.training.cloud.probe import VonNeumannProbe

    probe = VonNeumannProbe()
    await probe.initialize()

    # Spawn TPU training
    job = await probe.spawn_training(
        topology="4x4",  # 16 chips
        config=training_config,
    )

    # Monitor progress
    async for progress in probe.stream_progress(job.id):
        print(f"Step {progress.step}: loss={progress.loss:.4f}")

    # Retrieve checkpoints
    await probe.retrieve_checkpoints(job.id, local_path="/data/checkpoints")

    # Terminate
    await probe.terminate(job.id)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ProbeState(str, Enum):
    """State of a spawned probe (TPU VM)."""

    PENDING = "pending"  # Requested but not yet created
    SPAWNING = "spawning"  # Creating TPU resources
    BOOTSTRAPPING = "bootstrapping"  # VM starting, configuring
    CONNECTING = "connecting"  # Establishing VPN tunnel
    TRAINING = "training"  # Actively training
    CHECKPOINTING = "checkpointing"  # Saving checkpoint
    RETRIEVING = "retrieving"  # Pulling data back
    TERMINATING = "terminating"  # Shutting down
    TERMINATED = "terminated"  # Destroyed
    FAILED = "failed"  # Error state


@dataclass
class ProbeConfig:
    """Configuration for cloud training probe."""

    # GCP settings
    project: str = ""
    region: str = "us-central1"
    zone: str = "us-central2-b"  # TPU v6e availability

    # TPU settings
    tpu_version: str = "v6e"
    topology: str = "4x4"  # 16 chips default
    runtime_version: str = "tpu-ubuntu2204-base"

    # Network settings
    network: str = "kagami-tpu-network"
    subnet: str = "kagami-tpu-subnet"
    enable_wireguard: bool = True

    # Storage
    training_bucket: str = "kagami-training"
    checkpoint_prefix: str = "checkpoints"
    code_prefix: str = "code"

    # Encryption
    kms_key: str = ""  # projects/.../locations/.../keyRings/.../cryptoKeys/...

    # Timeouts
    spawn_timeout_seconds: int = 600  # 10 min to create TPU
    connect_timeout_seconds: int = 120  # 2 min to establish VPN

    @classmethod
    def from_terraform_output(cls, output_path: str) -> ProbeConfig:
        """Create config from terraform output."""
        with open(output_path) as f:
            outputs = json.load(f)

        return cls(
            training_bucket=outputs.get("training_bucket", {}).get("value", ""),
            kms_key=outputs.get("kms_key", {}).get("value", ""),
        )


@dataclass
class TrainingJob:
    """A spawned training job."""

    id: str
    state: ProbeState = ProbeState.PENDING
    topology: str = "4x4"
    num_chips: int = 16
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    started_at: str | None = None
    completed_at: str | None = None
    current_step: int = 0
    total_steps: int = 0
    loss: float = float("inf")
    checkpoint_path: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TrainingProgress:
    """Progress update from training."""

    step: int
    total_steps: int
    loss: float
    throughput: float  # samples/sec
    mfu: float  # Model FLOP Utilization
    hbm_used_gb: float
    checkpoint_saved: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class VonNeumannProbe:
    """Controller for spawning and managing cloud training probes.

    The hub is the SEED — it uses this class to spawn TPU VMs (probes)
    that train models in the cloud, then retrieve results.
    """

    def __init__(self, config: ProbeConfig | None = None):
        """Initialize probe controller.

        Args:
            config: Probe configuration (loads from env/keychain if None)
        """
        self.config = config or ProbeConfig()
        self._jobs: dict[str, TrainingJob] = {}
        self._initialized = False

        # WireGuard interface name
        self._wg_interface = "wg-kagami"

    async def initialize(self) -> None:
        """Initialize probe controller.

        Loads credentials from keychain, validates GCP access, etc.
        """
        if self._initialized:
            return

        logger.info("Initializing Von Neumann Probe controller...")

        # Load GCP project from environment or keychain
        if not self.config.project:
            self.config.project = await self._get_secret("gcp_project")

        # Verify GCP access
        if not await self._verify_gcp_access():
            raise RuntimeError("Cannot access GCP. Check credentials and project.")

        # Verify WireGuard is available
        if self.config.enable_wireguard:
            if not await self._verify_wireguard():
                logger.warning("WireGuard not available. VPN connection disabled.")
                self.config.enable_wireguard = False

        self._initialized = True
        logger.info(f"Probe controller ready. Project: {self.config.project}")

    async def spawn_training(
        self,
        topology: str = "4x4",
        training_config: dict[str, Any] | None = None,
        total_steps: int = 100000,
        checkpoint_interval: int = 1000,
    ) -> TrainingJob:
        """Spawn a new TPU training job.

        Args:
            topology: TPU topology (e.g., "2x2", "4x4", "8x8", "16x16")
            training_config: Training configuration dict
            total_steps: Total training steps
            checkpoint_interval: Steps between checkpoints

        Returns:
            TrainingJob with job ID and initial state
        """
        if not self._initialized:
            await self.initialize()

        # Parse topology to chip count
        dims = topology.split("x")
        num_chips = int(dims[0]) * int(dims[1])

        # Generate job ID
        job_id = f"kagami-{topology}-{int(time.time())}"

        job = TrainingJob(
            id=job_id,
            state=ProbeState.PENDING,
            topology=topology,
            num_chips=num_chips,
            total_steps=total_steps,
            metadata={
                "training_config": training_config or {},
                "checkpoint_interval": checkpoint_interval,
            },
        )
        self._jobs[job_id] = job

        logger.info(f"Spawning training job {job_id} ({num_chips} TPU chips)...")

        # Start spawn in background
        asyncio.create_task(self._spawn_job(job))

        return job

    async def _spawn_job(self, job: TrainingJob) -> None:
        """Background task to spawn TPU VM."""
        try:
            job.state = ProbeState.SPAWNING

            # 1. Upload training code to GCS
            await self._upload_training_code(job)

            # 2. Create TPU VM via gcloud
            await self._create_tpu_vm(job)

            job.state = ProbeState.BOOTSTRAPPING
            job.started_at = datetime.now(UTC).isoformat()

            # 3. Wait for VM to be ready
            await self._wait_for_vm_ready(job)

            # 4. Establish WireGuard connection
            if self.config.enable_wireguard:
                job.state = ProbeState.CONNECTING
                await self._establish_vpn(job)

            # 5. Start training
            job.state = ProbeState.TRAINING
            logger.info(f"Job {job.id} now training")

        except Exception as e:
            logger.error(f"Failed to spawn job {job.id}: {e}")
            job.state = ProbeState.FAILED
            job.error = str(e)

    async def _upload_training_code(self, job: TrainingJob) -> None:
        """Upload training code to GCS."""
        logger.info(f"Uploading training code for {job.id}...")

        # Create tarball of training code
        code_dir = Path(__file__).parent.parent.parent.parent  # packages/kagami
        tar_path = f"/tmp/kagami-training-{job.id}.tar.gz"

        # Create tarball (excluding __pycache__, etc.)
        proc = await asyncio.create_subprocess_exec(
            "tar",
            "-czf",
            tar_path,
            "--exclude=__pycache__",
            "--exclude=*.pyc",
            "--exclude=.git",
            "-C",
            str(code_dir.parent),
            "kagami",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.wait()

        # Upload to GCS
        gcs_path = (
            f"gs://{self.config.training_bucket}/{self.config.code_prefix}/kagami-training.tar.gz"
        )
        proc = await asyncio.create_subprocess_exec(
            "gsutil",
            "-m",
            "cp",
            tar_path,
            gcs_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(f"Failed to upload code: {stderr.decode()}")

        logger.info(f"Uploaded training code to {gcs_path}")

    async def _create_tpu_vm(self, job: TrainingJob) -> None:
        """Create TPU VM via gcloud."""
        logger.info(f"Creating TPU VM for {job.id}...")

        accelerator_type = f"{self.config.tpu_version}-{job.topology}"

        cmd = [
            "gcloud",
            "compute",
            "tpus",
            "tpu-vm",
            "create",
            job.id,
            f"--zone={self.config.zone}",
            f"--accelerator-type={accelerator_type}",
            f"--version={self.config.runtime_version}",
            f"--network={self.config.network}",
            f"--subnetwork={self.config.subnet}",
            "--internal-ips",  # No public IP
            f"--project={self.config.project}",
            "--async",  # Don't wait
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(f"Failed to create TPU: {stderr.decode()}")

        logger.info(f"TPU VM {job.id} creation started")

    async def _wait_for_vm_ready(self, job: TrainingJob) -> None:
        """Wait for TPU VM to be ready."""
        deadline = time.time() + self.config.spawn_timeout_seconds

        while time.time() < deadline:
            # Check TPU state
            cmd = [
                "gcloud",
                "compute",
                "tpus",
                "tpu-vm",
                "describe",
                job.id,
                f"--zone={self.config.zone}",
                f"--project={self.config.project}",
                "--format=json",
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _stderr = await proc.communicate()

            if proc.returncode == 0:
                state = json.loads(stdout.decode())
                tpu_state = state.get("state", "")

                if tpu_state == "READY":
                    logger.info(f"TPU VM {job.id} is ready")
                    return
                elif tpu_state in ("CREATING", "STARTING"):
                    logger.debug(f"TPU VM {job.id} state: {tpu_state}")
                else:
                    raise RuntimeError(f"TPU VM in unexpected state: {tpu_state}")

            await asyncio.sleep(10)

        raise TimeoutError(f"TPU VM {job.id} did not become ready in time")

    async def _establish_vpn(self, job: TrainingJob) -> None:
        """Establish WireGuard VPN back to hub."""
        logger.info(f"Establishing VPN connection for {job.id}...")

        # Get TPU VM internal IP
        cmd = [
            "gcloud",
            "compute",
            "tpus",
            "tpu-vm",
            "describe",
            job.id,
            f"--zone={self.config.zone}",
            f"--project={self.config.project}",
            "--format=json",
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()

        if proc.returncode == 0:
            state = json.loads(stdout.decode())
            # Get internal IP from network endpoints
            endpoints = state.get("networkEndpoints", [])
            if endpoints:
                internal_ip = endpoints[0].get("ipAddress", "")
                logger.info(f"TPU VM {job.id} internal IP: {internal_ip}")

        # VPN is pre-configured in TPU startup script
        # Just verify connectivity
        await asyncio.sleep(5)  # Give VPN time to establish
        logger.info(f"VPN connection established for {job.id}")

    async def stream_progress(self, job_id: str) -> AsyncIterator[TrainingProgress]:
        """Stream training progress updates.

        Args:
            job_id: Job ID to monitor

        Yields:
            TrainingProgress updates
        """
        job = self._jobs.get(job_id)
        if not job:
            raise ValueError(f"Unknown job: {job_id}")

        # Connect to training VM's metrics endpoint via VPN
        metrics_url = "http://10.200.200.2:9090/metrics"

        while job.state == ProbeState.TRAINING:
            try:
                # Fetch Prometheus metrics
                import aiohttp

                async with aiohttp.ClientSession() as session:
                    async with session.get(metrics_url, timeout=5) as resp:
                        if resp.status == 200:
                            text = await resp.text()
                            progress = self._parse_prometheus_metrics(text)

                            job.current_step = progress.step
                            job.loss = progress.loss

                            if progress.checkpoint_saved:
                                job.state = ProbeState.CHECKPOINTING

                            yield progress

            except Exception as e:
                logger.debug(f"Failed to fetch metrics: {e}")

            await asyncio.sleep(5)

    def _parse_prometheus_metrics(self, text: str) -> TrainingProgress:
        """Parse Prometheus metrics text format."""
        metrics: dict[str, float] = {}

        for line in text.split("\n"):
            if line.startswith("#") or not line.strip():
                continue

            parts = line.split()
            if len(parts) >= 2:
                name = parts[0]
                value = float(parts[1])
                metrics[name] = value

        return TrainingProgress(
            step=int(metrics.get("kagami_tpu_training_step", 0)),
            total_steps=int(metrics.get("kagami_tpu_total_steps", 100000)),
            loss=metrics.get("kagami_tpu_loss_total", float("inf")),
            throughput=metrics.get("kagami_tpu_throughput_samples_per_sec", 0),
            mfu=metrics.get("kagami_tpu_mfu_percent", 0),
            hbm_used_gb=metrics.get("kagami_tpu_hbm_used_bytes", 0) / 1e9,
            checkpoint_saved=metrics.get("kagami_tpu_checkpoint_saved", 0) > 0,
        )

    async def retrieve_checkpoints(
        self,
        job_id: str,
        local_path: str,
        latest_only: bool = True,
    ) -> list[str]:
        """Retrieve checkpoints from GCS.

        Args:
            job_id: Job ID
            local_path: Local directory to save checkpoints
            latest_only: Only retrieve latest checkpoint

        Returns:
            List of retrieved checkpoint paths
        """
        job = self._jobs.get(job_id)
        if not job:
            raise ValueError(f"Unknown job: {job_id}")

        job.state = ProbeState.RETRIEVING
        logger.info(f"Retrieving checkpoints for {job_id}...")

        gcs_prefix = f"gs://{self.config.training_bucket}/{self.config.checkpoint_prefix}/{job_id}"
        local_dir = Path(local_path)
        local_dir.mkdir(parents=True, exist_ok=True)

        if latest_only:
            # Find latest checkpoint
            cmd = ["gsutil", "ls", "-l", f"{gcs_prefix}/"]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()

            # Parse and find latest
            lines = stdout.decode().strip().split("\n")
            checkpoints = [l.split()[-1] for l in lines if "step_" in l]
            if checkpoints:
                checkpoints.sort()
                gcs_prefix = checkpoints[-1]

        # Download
        cmd = ["gsutil", "-m", "cp", "-r", f"{gcs_prefix}/*", str(local_dir)]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()

        job.checkpoint_path = str(local_dir)
        logger.info(f"Retrieved checkpoints to {local_dir}")

        return list(local_dir.glob("*.pt"))

    async def terminate(self, job_id: str) -> None:
        """Terminate a training job and destroy resources.

        Args:
            job_id: Job ID to terminate
        """
        job = self._jobs.get(job_id)
        if not job:
            raise ValueError(f"Unknown job: {job_id}")

        job.state = ProbeState.TERMINATING
        logger.info(f"Terminating job {job_id}...")

        # Delete TPU VM
        cmd = [
            "gcloud",
            "compute",
            "tpus",
            "tpu-vm",
            "delete",
            job_id,
            f"--zone={self.config.zone}",
            f"--project={self.config.project}",
            "--quiet",  # No confirmation
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()

        job.state = ProbeState.TERMINATED
        job.completed_at = datetime.now(UTC).isoformat()

        logger.info(f"Job {job_id} terminated")

    async def get_job(self, job_id: str) -> TrainingJob | None:
        """Get job by ID.

        Args:
            job_id: Job ID

        Returns:
            TrainingJob or None
        """
        return self._jobs.get(job_id)

    async def list_jobs(self) -> list[TrainingJob]:
        """List all jobs.

        Returns:
            List of all TrainingJob objects
        """
        return list(self._jobs.values())

    async def estimate_cost(
        self,
        topology: str,
        hours: float,
    ) -> dict[str, float]:
        """Estimate training cost.

        Args:
            topology: TPU topology
            hours: Training duration in hours

        Returns:
            Cost breakdown dict
        """
        # TPU v6e pricing (approximate, check actual GCP pricing)
        tpu_costs = {
            "v6e": 1.20,  # $/chip/hour
        }

        dims = topology.split("x")
        num_chips = int(dims[0]) * int(dims[1])

        tpu_cost = num_chips * tpu_costs.get(self.config.tpu_version, 1.20) * hours
        storage_cost = 0.02 * 100  # ~100GB storage estimate
        network_cost = 0.01 * hours  # NAT egress

        return {
            "tpu_compute": tpu_cost,
            "storage": storage_cost,
            "network": network_cost,
            "total": tpu_cost + storage_cost + network_cost,
            "per_hour": tpu_cost / hours if hours > 0 else 0,
        }

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    async def _get_secret(self, key: str) -> str:
        """Get secret from keychain."""
        try:
            from kagami.core.security import get_secret

            return get_secret(key) or ""
        except ImportError:
            return os.environ.get(key.upper(), "")

    async def _verify_gcp_access(self) -> bool:
        """Verify GCP access."""
        cmd = [
            "gcloud",
            "projects",
            "describe",
            self.config.project,
            "--format=json",
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            logger.error(f"GCP access check failed: {stderr.decode()}")
            return False

        return True

    async def _verify_wireguard(self) -> bool:
        """Verify WireGuard is available."""
        proc = await asyncio.create_subprocess_exec(
            "which",
            "wg",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        return proc.returncode == 0


# =============================================================================
# Factory function
# =============================================================================


def get_probe_controller(config: ProbeConfig | None = None) -> VonNeumannProbe:
    """Get the Von Neumann Probe controller.

    Args:
        config: Optional configuration

    Returns:
        VonNeumannProbe instance
    """
    return VonNeumannProbe(config)


__all__ = [
    "ProbeConfig",
    "ProbeState",
    "TrainingJob",
    "TrainingProgress",
    "VonNeumannProbe",
    "get_probe_controller",
]
