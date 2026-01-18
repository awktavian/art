"""Cloud Training Infrastructure — Von Neumann Probe.

CREATED: January 4, 2026

The hub is the SEED. It spawns probes (TPU VMs) in the cloud,
controls them, and retrieves results — all encrypted end-to-end.

This module provides:
- VonNeumannProbe: Controller for spawning/managing TPU VMs
- ProbeConfig: Configuration for cloud training
- TrainingJob: Represents a spawned training job
- TrainingProgress: Progress updates from training

Usage:
    from kagami.core.training.cloud import VonNeumannProbe

    probe = VonNeumannProbe()
    await probe.initialize()

    # Spawn training on 16 TPU chips
    job = await probe.spawn_training(topology="4x4")

    # Monitor
    async for progress in probe.stream_progress(job.id):
        print(f"Step {progress.step}: loss={progress.loss:.4f}")

    # Retrieve and terminate
    await probe.retrieve_checkpoints(job.id, "/data/ckpt")
    await probe.terminate(job.id)

Security Model:
- All data encrypted at rest (GCS + Cloud KMS CMEK)
- All data encrypted in transit (WireGuard VPN from house)
- TPU VMs have NO public IP
- Secrets stored in macOS Keychain, delivered via Secret Manager

Architecture:
```
House (SEED)                         Google Cloud (PROBES)
┌─────────────┐                     ┌─────────────────────┐
│ Kagami Hub  │◄════encrypted═════►│  TPU v6e-256 Pod    │
│ (Pi/Mac)    │   WireGuard VPN    │                     │
│             │                     │  Training → GCS     │
│  Keychain   │───credentials──────►│  (encrypted)       │
└─────────────┘                     └─────────────────────┘
```
"""

from kagami.core.training.cloud.probe import (
    ProbeConfig,
    ProbeState,
    TrainingJob,
    TrainingProgress,
    VonNeumannProbe,
    get_probe_controller,
)

__all__ = [
    "ProbeConfig",
    "ProbeState",
    "TrainingJob",
    "TrainingProgress",
    "VonNeumannProbe",
    "get_probe_controller",
]
