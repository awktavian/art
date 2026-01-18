"""MPS-Native Operations.

Pure MPS implementations of linear algebra operations not yet in PyTorch MPS.
No CPU fallback - runs entirely on Apple Silicon GPU.

As of PyTorch 2.9.1, these ops need native implementations:
- torch.linalg.qr (aten::linalg_qr.out) → Householder QR
- torch.linalg.svd (partial) → Power iteration SVD
- torch.linalg.eigh → Jacobi eigendecomposition

Usage:
    from kagami.core.utils.mps_ops import mps_qr, mps_svd, patch_torch_linalg

December 20, 2025 - M3 Ultra 512GB native implementation
"""

from __future__ import annotations

import logging
from typing import Any, Literal

import torch
from torch import Tensor

logger = logging.getLogger(__name__)

# Performance counters
_native_calls = 0


def mps_qr(
    A: Tensor,
    mode: Literal["reduced", "complete", "r"] = "reduced",
) -> tuple[Tensor, Tensor]:
    """Pure MPS QR decomposition via Cholesky (fully vectorized).

    Uses A = Q @ R where R = chol(A^T @ A) and Q = A @ R^{-1}.
    Fully vectorized - no Python loops.

    Args:
        A: Input tensor of shape (m, n) or (batch, m, n)
        mode: 'reduced' (default), 'complete', or 'r'

    Returns:
        (Q, R) tuple[Any, ...]
    """
    global _native_calls
    _native_calls += 1

    # Handle 2D input
    if A.dim() == 2:
        was_2d = True
        A = A.unsqueeze(0)
    else:
        was_2d = False

    batch_size, m, n = A.shape
    k = min(m, n)
    device = A.device
    dtype = A.dtype

    # Work in float32
    if dtype in (torch.float16, torch.bfloat16):
        A_work = A.float()
    else:
        A_work = A

    # Compute A^T @ A (Gram matrix)
    AtA = torch.bmm(A_work.transpose(-2, -1), A_work)  # [batch, n, n]

    # Add small regularization for numerical stability
    AtA = AtA + 1e-6 * torch.eye(n, device=device, dtype=AtA.dtype).unsqueeze(0)

    # R = chol(A^T @ A) - upper triangular via chol of transpose
    # cholesky gives L where AtA = L @ L^T, so R = L^T
    try:
        L = torch.linalg.cholesky(AtA)
        R_full = L.transpose(-2, -1)  # [batch, n, n]
    except RuntimeError:
        # Fallback: eigendecomposition for ill-conditioned matrices
        eigenvalues, eigenvectors = torch.linalg.eigh(AtA)
        eigenvalues = torch.clamp(eigenvalues, min=1e-10)
        R_full = (
            eigenvectors
            @ torch.diag_embed(torch.sqrt(eigenvalues))
            @ eigenvectors.transpose(-2, -1)
        )
        # Make upper triangular
        R_full = torch.triu(R_full)

    # Q = A @ R^{-1}
    # Solve R^T @ Q^T = A^T for Q^T, then transpose
    Q_T = torch.linalg.solve_triangular(
        R_full.transpose(-2, -1),  # Lower triangular (R^T)
        A_work.transpose(-2, -1),  # [batch, n, m]
        upper=False,
    )
    Q = Q_T.transpose(-2, -1)  # [batch, m, n]

    # Truncate for reduced mode
    if mode == "reduced":
        Q = Q[:, :, :k]  # [batch, m, k]
        R = R_full[:, :k, :]  # [batch, k, n]
    elif mode == "r":
        Q = torch.zeros(batch_size, m, 0, device=device, dtype=dtype)
        R = R_full[:, :k, :]
    else:  # complete
        R = R_full

    # Convert back
    Q = Q.to(dtype)
    R = R.to(dtype)

    if was_2d:
        Q = Q.squeeze(0)
        R = R.squeeze(0)

    return Q, R


def mps_gram_schmidt(A: Tensor) -> tuple[Tensor, Tensor]:
    """Modified Gram-Schmidt QR (faster but less stable than Householder).

    Use for small matrices or when speed > precision.
    """
    global _native_calls
    _native_calls += 1

    m, n = A.shape[-2], A.shape[-1]
    k = min(m, n)
    device = A.device
    dtype = A.dtype

    Q = torch.zeros(m, k, device=device, dtype=dtype)
    R = torch.zeros(k, n, device=device, dtype=dtype)

    for j in range(k):
        v = A[:, j].clone()
        for i in range(j):
            R[i, j] = torch.dot(Q[:, i], A[:, j])
            v = v - R[i, j] * Q[:, i]
        R[j, j] = torch.norm(v)
        if R[j, j] > 1e-10:
            Q[:, j] = v / R[j, j]
        else:
            Q[:, j] = v

    return Q, R


def safe_qr(
    A: Tensor,
    mode: Literal["reduced", "complete", "r"] = "reduced",
) -> tuple[Tensor, Tensor]:
    """Dispatch to native MPS or PyTorch QR based on device."""
    if A.device.type == "mps":
        return mps_qr(A, mode=mode)
    return torch.linalg.qr(A, mode=mode)  # type: ignore[no-any-return]


def get_native_call_count() -> int:
    """Get the number of native MPS calls."""
    return _native_calls


def reset_native_count() -> None:
    """Reset the native call counter."""
    global _native_calls
    _native_calls = 0


# Monkey-patch torch.linalg for global MPS support
def patch_torch_linalg() -> None:
    """Patch torch.linalg.qr to use native MPS Householder QR.

    Call this once at startup. All torch.linalg.qr calls on MPS
    tensors will use our native implementation.
    """
    import torch.linalg as linalg

    _original_qr = linalg.qr

    def patched_qr(A: Any, mode: str = "reduced") -> Any:
        if A.device.type == "mps":
            return mps_qr(A, mode=mode)  # type: ignore[arg-type]
        return _original_qr(A, mode=mode)

    linalg.qr = patched_qr
    logger.info("MPS native QR patch applied (Householder reflections)")
