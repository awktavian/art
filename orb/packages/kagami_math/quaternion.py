"""Quaternion Mathematics for K OS.

Provides standard Hamilton quaternion operations used throughout the codebase.
Consolidates duplicate implementations from:
- kagami/core/fractal_agents/organism/fano_sequence.py
- kagami/core/world_model/fano_integration.py

Quaternions are 4D hypercomplex numbers: q = w + xi + yj + zk
where i² = j² = k² = ijk = -1

References:
- Hamilton, W.R. (1843) "On Quaternions"
- K OS Architecture: Quaternions as rotations on S³ embedded in octonion structure
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray


def quat_mul(q1: NDArray[np.floating], q2: NDArray[np.floating]) -> NDArray[np.floating]:
    """Hamilton quaternion multiplication.

    Computes q1 * q2 using the Hamilton product:
        (a + bi + cj + dk)(e + fi + gj + hk)

    Args:
        q1: First quaternion [w, x, y, z]
        q2: Second quaternion [w, x, y, z]

    Returns:
        Product quaternion [w, x, y, z]

    Note:
        Quaternion multiplication is associative but NOT commutative:
        q1 * q2 ≠ q2 * q1 in general.
    """
    w1, x1, y1, z1 = q1
    w2, x2, y2, z2 = q2
    return np.array(
        [
            w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
        ]
    )


def quat_conj(q: NDArray[np.floating]) -> NDArray[np.floating]:
    """Quaternion conjugate.

    For q = w + xi + yj + zk, conjugate is q* = w - xi - yj - zk

    Args:
        q: Quaternion [w, x, y, z]

    Returns:
        Conjugate quaternion [w, -x, -y, -z]

    Note:
        |q|² = q * q* = w² + x² + y² + z²
    """
    return np.array([q[0], -q[1], -q[2], -q[3]])


def quat_norm(q: NDArray[np.floating]) -> float:
    """Quaternion norm (magnitude).

    Args:
        q: Quaternion [w, x, y, z]

    Returns:
        Euclidean norm sqrt(w² + x² + y² + z²)
    """
    return float(np.linalg.norm(q))


def quat_normalize(q: NDArray[np.floating]) -> NDArray[np.floating]:
    """Normalize quaternion to unit length.

    Args:
        q: Quaternion [w, x, y, z]

    Returns:
        Unit quaternion q / |q|
    """
    norm = quat_norm(q)
    if norm < 1e-10:
        return np.array([1.0, 0.0, 0.0, 0.0])  # Identity quaternion
    return q / norm


def quat_inverse(q: NDArray[np.floating]) -> NDArray[np.floating]:
    """Quaternion inverse.

    For unit quaternions: q⁻¹ = q*
    For general quaternions: q⁻¹ = q* / |q|²

    Args:
        q: Quaternion [w, x, y, z]

    Returns:
        Inverse quaternion
    """
    norm_sq = float(np.sum(q * q))
    if norm_sq < 1e-10:
        return np.array([1.0, 0.0, 0.0, 0.0])  # Fallback to identity
    return quat_conj(q) / norm_sq


def quat_from_axis_angle(axis: NDArray[np.floating], angle: float) -> NDArray[np.floating]:
    """Create quaternion from axis-angle representation.

    Args:
        axis: Unit rotation axis [x, y, z]
        angle: Rotation angle in radians

    Returns:
        Quaternion representing the rotation
    """
    half_angle = angle / 2
    s = np.sin(half_angle)
    return np.array([np.cos(half_angle), axis[0] * s, axis[1] * s, axis[2] * s])


def quat_to_rotation_matrix(q: NDArray[np.floating]) -> NDArray[np.floating]:
    """Convert unit quaternion to 3x3 rotation matrix.

    Args:
        q: Unit quaternion [w, x, y, z]

    Returns:
        3x3 rotation matrix
    """
    q = quat_normalize(q)
    w, x, y, z = q

    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )


def quat_slerp(
    q1: NDArray[np.floating], q2: NDArray[np.floating], t: float
) -> NDArray[np.floating]:
    """Spherical linear interpolation between quaternions.

    Args:
        q1: Start quaternion
        q2: End quaternion
        t: Interpolation parameter [0, 1]

    Returns:
        Interpolated quaternion
    """
    # Normalize inputs
    q1 = quat_normalize(q1)
    q2 = quat_normalize(q2)

    # Compute dot product
    dot = float(np.dot(q1, q2))

    # If dot is negative, negate one quaternion to take shorter path
    if dot < 0:
        q2 = -q2
        dot = -dot

    # If quaternions are very close, use linear interpolation
    if dot > 0.9995:
        result = q1 + t * (q2 - q1)
        return quat_normalize(result)

    # Compute the angle between quaternions
    theta_0 = np.arccos(np.clip(dot, -1.0, 1.0))
    theta = theta_0 * t

    # Compute orthogonal quaternion
    q_perp = q2 - q1 * dot
    q_perp = quat_normalize(q_perp)

    # Compute interpolated quaternion
    result: NDArray[np.floating[Any]] = q1 * np.cos(theta) + q_perp * np.sin(theta)  # type: ignore[no-redef]
    return result


__all__ = [
    "quat_conj",
    "quat_from_axis_angle",
    "quat_inverse",
    "quat_mul",
    "quat_norm",
    "quat_normalize",
    "quat_slerp",
    "quat_to_rotation_matrix",
]
