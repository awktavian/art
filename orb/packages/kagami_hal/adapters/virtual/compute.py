"""Virtual Compute Capabilities.

Detects available compute resources for headless/cloud environments.
Typically CPU-only without GPU acceleration.

CBF Safety: All compute resource allocation operations are protected
by Control Barrier Functions to prevent resource exhaustion.

Created: December 15, 2025
Updated: December 18, 2025 - Added CBF safety enforcement
"""

from __future__ import annotations

import logging
import os
import platform
from dataclasses import dataclass
from typing import Literal

from kagami.core.safety.cbf_decorators import CBFViolation
from kagami.core.safety.cbf_integration import check_cbf_for_operation

logger = logging.getLogger(__name__)


@dataclass
class ComputeCapabilities:
    """Compute hardware capabilities.

    Attributes:
        platform: CPU architecture (x86_64, arm64, etc.)
        cpu_count: Number of CPU cores
        has_gpu: GPU available
        gpu_vendor: GPU vendor if available (nvidia, amd, apple, intel)
        gpu_memory_mb: GPU memory in MB (0 if no GPU)
        has_npu: Neural Processing Unit available
        recommended_batch_size: Recommended inference batch size
        recommended_precision: Recommended model precision
    """

    platform: str
    cpu_count: int
    has_gpu: bool
    gpu_vendor: str | None
    gpu_memory_mb: int
    has_npu: bool
    recommended_batch_size: int
    recommended_precision: Literal["fp32", "fp16", "int8"]


def detect_compute_capabilities() -> ComputeCapabilities:
    """Detect compute capabilities for virtual platform.

    In cloud/headless environments, typically:
    - CPU only (no GPU)
    - Conservative batch sizes
    - FP32 precision (safest)

    Returns:
        Detected compute capabilities
    """
    # Detect CPU architecture
    machine = platform.machine().lower()
    cpu_arch = machine

    # Count CPU cores
    try:
        import multiprocessing

        cpu_count = multiprocessing.cpu_count()
    except Exception:
        cpu_count = 1

    # Check for GPU (conservative - assume none in virtual mode)
    has_gpu = False
    gpu_vendor = None
    gpu_memory_mb = 0

    # Allow environment override for testing
    if os.getenv("KAGAMI_VIRTUAL_FORCE_GPU", "0") == "1":
        has_gpu = True
        gpu_vendor = os.getenv("KAGAMI_VIRTUAL_GPU_VENDOR", "nvidia")
        gpu_memory_mb = int(os.getenv("KAGAMI_VIRTUAL_GPU_MEMORY_MB", "8192"))
    else:
        # Try to detect GPU anyway (might be running on a cloud GPU instance)
        try:
            import torch

            if torch.cuda.is_available():
                has_gpu = True
                gpu_vendor = "nvidia"
                gpu_memory_mb = torch.cuda.get_device_properties(0).total_memory // (1024 * 1024)
        except (ImportError, Exception):
            pass

        # Check for Apple Silicon
        if not has_gpu and machine.startswith("arm"):
            try:
                import torch

                if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                    has_gpu = True
                    gpu_vendor = "apple"
                    # Apple Silicon unified memory - conservative estimate
                    gpu_memory_mb = 8192
            except (ImportError, Exception):
                pass

    # NPU detection (rare in virtual environments)
    has_npu = False

    # Recommendations based on available hardware
    if has_gpu and gpu_memory_mb >= 8192:
        recommended_batch_size = 32
        recommended_precision = "fp16"
    elif has_gpu and gpu_memory_mb >= 4096:
        recommended_batch_size = 16
        recommended_precision = "fp16"
    elif cpu_count >= 8:
        recommended_batch_size = 8
        recommended_precision = "fp32"
    else:
        recommended_batch_size = 4
        recommended_precision = "fp32"

    capabilities = ComputeCapabilities(
        platform=cpu_arch,
        cpu_count=cpu_count,
        has_gpu=has_gpu,
        gpu_vendor=gpu_vendor,
        gpu_memory_mb=gpu_memory_mb,
        has_npu=has_npu,
        recommended_batch_size=recommended_batch_size,
        recommended_precision=recommended_precision,  # type: ignore[arg-type]
    )

    logger.info(
        f"Virtual compute: {cpu_arch} ({cpu_count} cores), "
        f"GPU: {has_gpu} ({gpu_vendor if has_gpu else 'none'}), "
        f"batch={recommended_batch_size}, precision={recommended_precision}"
    )

    return capabilities


def get_optimal_worker_count() -> int:
    """Get optimal number of worker processes for data loading.

    Returns:
        Recommended worker count
    """
    caps = detect_compute_capabilities()
    # Use half of CPU cores, min 1, max 8
    return max(1, min(8, caps.cpu_count // 2))


def supports_mixed_precision() -> bool:
    """Check if mixed precision training is supported.

    Returns:
        True if FP16/BF16 supported
    """
    caps = detect_compute_capabilities()
    return caps.has_gpu and caps.gpu_vendor in ("nvidia", "apple")


async def allocate_compute_resource(
    resource_type: str,
    amount: int,
    metadata: dict[str, str] | None = None,
) -> bool:
    """Allocate compute resources with CBF safety enforcement.

    Args:
        resource_type: Type of resource (cpu, memory, gpu)
        amount: Amount to allocate (cores, MB, etc.)
        metadata: Additional metadata for safety check

    Returns:
        True if allocation is safe and permitted

    Raises:
        CBFViolation: If resource allocation would violate safety constraints
    """
    # CBF Safety Check: Verify resource allocation is safe
    safety_result = await check_cbf_for_operation(
        operation="hal.compute.allocate",
        action="allocate_resource",
        target=resource_type,
        params={
            "resource_type": resource_type,
            "amount": amount,
        },
        metadata=metadata or {},
    )

    if not safety_result.safe:
        raise CBFViolation(
            barrier_name="compute_allocation",
            h_value=safety_result.h_x,  # type: ignore[arg-type]
            tier=3,
            detail=f"Compute resource allocation blocked: {safety_result.reason or safety_result.detail}",
        )

    return True


async def set_batch_size(
    batch_size: int,
    model_size_mb: int = 0,
    metadata: dict[str, str] | None = None,
) -> int:
    """Set inference/training batch size with CBF safety enforcement.

    Args:
        batch_size: Requested batch size
        model_size_mb: Model size in MB (for memory estimation)
        metadata: Additional metadata for safety check

    Returns:
        Approved batch size (may be reduced for safety)

    Raises:
        CBFViolation: If batch size would violate memory constraints
    """
    caps = detect_compute_capabilities()

    # CBF Safety Check: Verify batch size is safe
    safety_result = await check_cbf_for_operation(
        operation="hal.compute.set_batch_size",
        action="configure_batch",
        target="inference_pipeline",
        params={
            "batch_size": batch_size,
            "model_size_mb": model_size_mb,
            "recommended_batch_size": caps.recommended_batch_size,
        },
        metadata=metadata or {},
    )

    if not safety_result.safe:
        # Try to reduce batch size to recommended value
        reduced_batch_size = min(batch_size, caps.recommended_batch_size)

        logger.warning(
            f"Batch size {batch_size} blocked by CBF (h(x)={safety_result.h_x:.3f}), "
            f"reducing to {reduced_batch_size}"
        )

        # Re-check with reduced batch size
        reduced_safety = await check_cbf_for_operation(
            operation="hal.compute.set_batch_size",
            action="configure_batch",
            target="inference_pipeline",
            params={
                "batch_size": reduced_batch_size,
                "model_size_mb": model_size_mb,
                "recommended_batch_size": caps.recommended_batch_size,
            },
            metadata=metadata or {},
        )

        if not reduced_safety.safe:
            raise CBFViolation(
                barrier_name="batch_size",
                h_value=reduced_safety.h_x,  # type: ignore[arg-type]
                tier=3,
                detail=f"Even reduced batch size {reduced_batch_size} blocked: {reduced_safety.reason or reduced_safety.detail}",
            )

        return reduced_batch_size

    return batch_size


async def allocate_worker_pool(
    worker_count: int,
    metadata: dict[str, str] | None = None,
) -> int:
    """Allocate worker pool with CBF safety enforcement.

    Args:
        worker_count: Requested number of workers
        metadata: Additional metadata for safety check

    Returns:
        Approved worker count (may be reduced for safety)

    Raises:
        CBFViolation: If worker allocation would violate resource constraints
    """
    caps = detect_compute_capabilities()
    optimal_workers = get_optimal_worker_count()

    # CBF Safety Check: Verify worker allocation is safe
    safety_result = await check_cbf_for_operation(
        operation="hal.compute.allocate_workers",
        action="spawn_workers",
        target="worker_pool",
        params={
            "worker_count": worker_count,
            "cpu_count": caps.cpu_count,
            "optimal_workers": optimal_workers,
        },
        metadata=metadata or {},
    )

    if not safety_result.safe:
        # Try to reduce worker count to optimal value
        reduced_workers = min(worker_count, optimal_workers)

        logger.warning(
            f"Worker count {worker_count} blocked by CBF (h(x)={safety_result.h_x:.3f}), "
            f"reducing to {reduced_workers}"
        )

        # Re-check with reduced worker count
        reduced_safety = await check_cbf_for_operation(
            operation="hal.compute.allocate_workers",
            action="spawn_workers",
            target="worker_pool",
            params={
                "worker_count": reduced_workers,
                "cpu_count": caps.cpu_count,
                "optimal_workers": optimal_workers,
            },
            metadata=metadata or {},
        )

        if not reduced_safety.safe:
            raise CBFViolation(
                barrier_name="worker_allocation",
                h_value=reduced_safety.h_x,  # type: ignore[arg-type]
                tier=3,
                detail=f"Even reduced worker count {reduced_workers} blocked: {reduced_safety.reason or reduced_safety.detail}",
            )

        return reduced_workers

    return worker_count
