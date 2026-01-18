"""Common Math Utilities and Patterns.

EXTRACTED FOR CONSOLIDATION (December 13, 2025):
================================================
Common mathematical patterns found across 145 files with numpy imports.
This module consolidates repeated mathematical operations, linear algebra,
and numerical utilities to reduce duplication.

Contains:
- Common numpy imports and aliases
- Linear algebra utilities
- Numerical operations
- Statistical functions
- Geometric operations
- Mathematical constants
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from typing import Any

# Consolidated numpy imports (most common pattern: import numpy as np)
import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)

# Common mathematical constants
PI = math.pi
TAU = 2 * math.pi  # Full circle in radians
E = math.e
GOLDEN_RATIO = (1 + math.sqrt(5)) / 2
SQRT_2 = math.sqrt(2)
SQRT_PI = math.sqrt(math.pi)

# Numerical tolerances
DEFAULT_TOLERANCE = 1e-6
FLOAT_TOLERANCE = 1e-8
MATRIX_CONDITION_THRESHOLD = 1e12

# Type aliases for mathematical objects
Vector = NDArray[np.floating]
Matrix = NDArray[np.floating]
ComplexArray = NDArray[np.complexfloating]
NumberLike = int | float | np.number


class LinearAlgebra:
    """Linear algebra utilities and common operations."""

    @staticmethod
    def safe_inverse(matrix: Matrix, regularization: float = 1e-6) -> Matrix:
        """Safely compute matrix inverse with regularization."""
        try:
            # Check condition number
            cond = np.linalg.cond(matrix)
            if cond > MATRIX_CONDITION_THRESHOLD:
                logger.warning(
                    f"Matrix poorly conditioned (cond={cond:.2e}), adding regularization"
                )

                # Add regularization to diagonal
                regularized = matrix + regularization * np.eye(matrix.shape[0])
                return np.linalg.inv(regularized)
            else:
                return np.linalg.inv(matrix)

        except np.linalg.LinAlgError as e:
            logger.warning(f"Matrix inversion failed: {e}, using pseudo-inverse")
            return np.linalg.pinv(matrix)

    @staticmethod
    def safe_solve(A: Matrix, b: Vector, regularization: float = 1e-6) -> Vector:
        """Safely solve linear system Ax = b with regularization."""
        try:
            return np.linalg.solve(A, b)
        except np.linalg.LinAlgError:
            logger.warning("Direct solve failed, using least squares")
            try:
                return np.linalg.lstsq(A, b, rcond=None)[0]
            except np.linalg.LinAlgError:
                logger.warning("Least squares failed, using regularized solve")
                regularized = A + regularization * np.eye(A.shape[0])
                return np.linalg.solve(regularized, b)

    @staticmethod
    def orthogonalize(vectors: Matrix) -> Matrix:
        """Orthogonalize vectors using Gram-Schmidt process."""
        # QR decomposition is more numerically stable than manual Gram-Schmidt
        Q, _ = np.linalg.qr(vectors)
        return Q

    @staticmethod
    def project_onto_sphere(x: Vector, radius: float = 1.0) -> Vector:
        """Project vector onto sphere of given radius."""
        norm = np.linalg.norm(x)
        if norm < DEFAULT_TOLERANCE:
            # Handle zero vector case
            result = np.zeros_like(x)
            result[0] = radius
            return result
        return (radius / norm) * x

    @staticmethod
    def rotation_matrix_2d(angle: float) -> Matrix:
        """Create 2D rotation matrix."""
        cos_a = np.cos(angle)
        sin_a = np.sin(angle)
        return np.array([[cos_a, -sin_a], [sin_a, cos_a]])

    @staticmethod
    def rotation_matrix_3d(axis: Vector, angle: float) -> Matrix:
        """Create 3D rotation matrix using Rodrigues' formula."""
        axis = LinearAlgebra.project_onto_sphere(axis)  # Normalize
        cos_a = np.cos(angle)
        sin_a = np.sin(angle)

        # Cross product matrix for axis
        K = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])

        # Rodrigues' formula
        R = np.eye(3) + sin_a * K + (1 - cos_a) * np.dot(K, K)
        return R  # type: ignore[no-any-return]


class Statistics:
    """Statistical utilities and common operations."""

    @staticmethod
    def safe_mean(x: NDArray[Any], axis: int | None = None, keepdims: bool = False) -> NDArray[Any]:
        """Compute mean with NaN handling."""
        return np.nanmean(x, axis=axis, keepdims=keepdims)  # type: ignore[no-any-return]

    @staticmethod
    def safe_std(
        x: NDArray[Any], axis: int | None = None, keepdims: bool = False, ddof: int = 1
    ) -> NDArray[Any]:
        """Compute standard deviation with NaN handling."""
        return np.nanstd(x, axis=axis, keepdims=keepdims, ddof=ddof)  # type: ignore[no-any-return]

    @staticmethod
    def normalize_distribution(x: NDArray[Any], eps: float = 1e-8) -> NDArray[Any]:
        """Normalize array to sum to 1 (probability distribution)."""
        x = np.maximum(x, 0)  # Ensure non-negative
        total = np.sum(x)
        if total < eps:
            # Return uniform distribution if sum is too small
            return np.ones_like(x) / len(x)
        return x / total  # type: ignore[no-any-return]

    @staticmethod
    def entropy(p: NDArray[Any], base: float = np.e) -> float:
        """Compute entropy of probability distribution."""
        p = Statistics.normalize_distribution(p)
        # Remove zeros to avoid log(0)
        p_clean = p[p > 0]
        if len(p_clean) == 0:
            return 0.0

        if base == np.e:
            return float(np.sum(p_clean * np.log(p_clean)) * -1)
        else:
            return float(np.sum(p_clean * np.log(p_clean)) * -1 / np.log(base))

    @staticmethod
    def kl_divergence(p: NDArray[Any], q: NDArray[Any], eps: float = 1e-8) -> float:
        """Compute KL divergence D(P||Q)."""
        p = Statistics.normalize_distribution(p)
        q = Statistics.normalize_distribution(q)

        # Add small epsilon to avoid log(0)
        q = np.maximum(q, eps)

        # Only compute KL where p > 0
        mask = p > 0
        if not np.any(mask):
            return 0.0

        return float(np.sum(p[mask] * np.log(p[mask] / q[mask])))

    @staticmethod
    def wasserstein_1d(x: NDArray[Any], y: NDArray[Any]) -> float:
        """Compute 1D Wasserstein distance."""
        x_sorted = np.sort(x.flatten())
        y_sorted = np.sort(y.flatten())

        # Handle different lengths by padding
        if len(x_sorted) != len(y_sorted):
            min_len = min(len(x_sorted), len(y_sorted))
            x_sorted = x_sorted[:min_len]
            y_sorted = y_sorted[:min_len]

        return float(np.mean(np.abs(x_sorted - y_sorted)))


class Geometry:
    """Geometric utilities and transformations."""

    @staticmethod
    def distance_euclidean(x: Vector, y: Vector) -> float:
        """Compute Euclidean distance between vectors."""
        return float(np.linalg.norm(x - y))

    @staticmethod
    def distance_cosine(x: Vector, y: Vector) -> float:
        """Compute cosine distance between vectors."""
        dot_product = np.dot(x, y)
        norm_x = np.linalg.norm(x)
        norm_y = np.linalg.norm(y)

        if norm_x < DEFAULT_TOLERANCE or norm_y < DEFAULT_TOLERANCE:
            return 1.0  # Maximum distance

        cosine_sim = dot_product / (norm_x * norm_y)
        return float(1.0 - cosine_sim)

    @staticmethod
    def distance_manhattan(x: Vector, y: Vector) -> float:
        """Compute Manhattan (L1) distance."""
        return float(np.sum(np.abs(x - y)))

    @staticmethod
    def spherical_to_cartesian(r: float, theta: float, phi: float) -> Vector:
        """Convert spherical coordinates to Cartesian (3D)."""
        x = r * np.sin(phi) * np.cos(theta)
        y = r * np.sin(phi) * np.sin(theta)
        z = r * np.cos(phi)
        return np.array([x, y, z])

    @staticmethod
    def cartesian_to_spherical(x: float, y: float, z: float) -> tuple[float, float, float]:
        """Convert Cartesian to spherical coordinates."""
        r = np.sqrt(x**2 + y**2 + z**2)
        theta = np.arctan2(y, x)
        phi = np.arccos(z / r) if r > 0 else 0
        return float(r), float(theta), float(phi)

    @staticmethod
    def angle_between_vectors(v1: Vector, v2: Vector) -> float:
        """Compute angle between two vectors in radians."""
        v1_norm = LinearAlgebra.project_onto_sphere(v1)
        v2_norm = LinearAlgebra.project_onto_sphere(v2)

        dot_product = np.clip(np.dot(v1_norm, v2_norm), -1.0, 1.0)
        return float(np.arccos(dot_product))


class Numerical:
    """Numerical utilities and common operations."""

    @staticmethod
    def safe_log(x: NDArray[Any], eps: float = 1e-8) -> NDArray[Any]:
        """Numerically safe logarithm."""
        return np.log(np.maximum(x, eps))  # type: ignore[no-any-return]

    @staticmethod
    def safe_sqrt(x: NDArray[Any], eps: float = 1e-8) -> NDArray[Any]:
        """Numerically safe square root."""
        return np.sqrt(np.maximum(x, eps))  # type: ignore[no-any-return]

    @staticmethod
    def safe_divide(
        numerator: NDArray[Any], denominator: NDArray[Any], eps: float = 1e-8
    ) -> NDArray[Any]:
        """Safe division with small epsilon to avoid division by zero."""
        return numerator / (denominator + eps)

    @staticmethod
    def logaddexp_stable(x: NDArray[Any], y: NDArray[Any]) -> NDArray[Any]:
        """Numerically stable log(exp(x) + exp(y))."""
        return np.logaddexp(x, y)  # type: ignore[no-any-return]

    @staticmethod
    def softmax_stable(x: NDArray[Any], axis: int = -1, temperature: float = 1.0) -> NDArray[Any]:
        """Numerically stable softmax."""
        x = x / temperature
        x_max = np.max(x, axis=axis, keepdims=True)
        exp_x = np.exp(x - x_max)
        return exp_x / np.sum(exp_x, axis=axis, keepdims=True)  # type: ignore[no-any-return]

    @staticmethod
    def log_softmax_stable(
        x: NDArray[Any], axis: int = -1, temperature: float = 1.0
    ) -> NDArray[Any]:
        """Numerically stable log softmax."""
        x = x / temperature
        x_max = np.max(x, axis=axis, keepdims=True)
        log_sum_exp = x_max + np.log(np.sum(np.exp(x - x_max), axis=axis, keepdims=True))
        return x - log_sum_exp  # type: ignore[no-any-return]

    @staticmethod
    def is_close(
        a: NDArray[Any], b: NDArray[Any], rtol: float = 1e-05, atol: float = 1e-08
    ) -> NDArray[Any]:
        """Element-wise comparison with tolerance."""
        return np.isclose(a, b, rtol=rtol, atol=atol)

    @staticmethod
    def clamp(x: NDArray[Any], min_val: float = 0.0, max_val: float = 1.0) -> NDArray[Any]:
        """Clamp values to range [min_val, max_val]."""
        return np.clip(x, min_val, max_val)


class Signal:
    """Signal processing utilities."""

    @staticmethod
    def moving_average(x: NDArray[Any], window: int) -> NDArray[Any]:
        """Compute moving average."""
        if window <= 0:
            return x

        return np.convolve(x, np.ones(window) / window, mode="valid")

    @staticmethod
    def gaussian_filter_1d(x: NDArray[Any], sigma: float) -> NDArray[Any]:
        """Apply Gaussian filter (simplified)."""
        # Simple Gaussian kernel
        kernel_size = int(6 * sigma + 1)
        if kernel_size % 2 == 0:
            kernel_size += 1

        # Create Gaussian kernel
        kernel = np.exp(-0.5 * np.linspace(-3 * sigma, 3 * sigma, kernel_size) ** 2)
        kernel = kernel / np.sum(kernel)

        # Apply convolution
        return np.convolve(x, kernel, mode="same")

    @staticmethod
    def normalize_signal(x: NDArray[Any], method: str = "zscore") -> NDArray[Any]:
        """Normalize signal using various methods."""
        if method == "zscore":
            return (x - np.mean(x)) / (np.std(x) + 1e-8)  # type: ignore[no-any-return]
        elif method == "minmax":
            x_min, x_max = np.min(x), np.max(x)
            if x_max - x_min < 1e-8:
                return np.zeros_like(x)
            return (x - x_min) / (x_max - x_min)  # type: ignore[no-any-return]
        elif method == "unit":
            norm = np.linalg.norm(x)
            return x / (norm + 1e-8)
        else:
            raise ValueError(f"Unknown normalization method: {method}")


class Interpolation:
    """Interpolation and approximation utilities."""

    @staticmethod
    def linear_interpolate(x0: float, x1: float, t: float) -> float:
        """Linear interpolation between two values."""
        return x0 * (1 - t) + x1 * t

    @staticmethod
    def bilinear_interpolate(
        x: NDArray[Any], y: NDArray[Any], points: NDArray[Any], values: NDArray[Any]
    ) -> NDArray[Any]:
        """Bilinear interpolation (simplified)."""
        # This is a simplified placeholder - real implementation would be more complex
        from scipy.interpolate import griddata

        try:
            return griddata(points, values, (x, y), method="linear")  # type: ignore[no-any-return]
        except ImportError:
            logger.warning("scipy not available, using nearest neighbor")
            # Fallback to nearest neighbor
            distances = np.sqrt((points[:, 0:1] - x) ** 2 + (points[:, 1:2] - y) ** 2)
            nearest_idx = np.argmin(distances, axis=0)
            return values[nearest_idx]  # type: ignore[no-any-return]

    @staticmethod
    def polynomial_fit(x: NDArray[Any], y: NDArray[Any], degree: int = 2) -> NDArray[Any]:
        """Fit polynomial to data."""
        return np.polyfit(x, y, degree)  # type: ignore[no-any-return]

    @staticmethod
    def evaluate_polynomial(coeffs: NDArray[Any], x: NDArray[Any]) -> NDArray[Any]:
        """Evaluate polynomial at given points."""
        return np.polyval(coeffs, x)


class Optimization:
    """Numerical optimization utilities."""

    @staticmethod
    def gradient_descent_1d(
        f: Callable[[float], float],
        df: Callable[[float], float],
        x0: float,
        learning_rate: float = 0.01,
        max_iters: int = 1000,
        tolerance: float = 1e-6,
    ) -> tuple[float, bool]:
        """Simple gradient descent for 1D functions."""
        x = x0

        for _i in range(max_iters):
            grad = df(x)

            if abs(grad) < tolerance:
                return x, True  # Converged

            x = x - learning_rate * grad

        return x, False  # Did not converge

    @staticmethod
    def find_fixed_point(
        f: Callable[[NDArray[Any]], NDArray[Any]],
        x0: NDArray[Any],
        max_iters: int = 100,
        tolerance: float = 1e-6,
    ) -> tuple[NDArray[Any], bool]:
        """Find fixed point x such that f(x) = x."""
        x = x0.copy()

        for _i in range(max_iters):
            x_new = f(x)

            if np.linalg.norm(x_new - x) < tolerance:
                return x_new, True  # Converged

            x = x_new

        return x, False  # Did not converge

    @staticmethod
    def binary_search(
        f: Callable[[float], float],
        target: float,
        left: float,
        right: float,
        tolerance: float = 1e-6,
        max_iters: int = 100,
    ) -> tuple[float, bool]:
        """Binary search for value where f(x) = target."""
        for _i in range(max_iters):
            mid = (left + right) / 2
            value = f(mid)

            if abs(value - target) < tolerance:
                return mid, True  # Found

            if value < target:
                left = mid
            else:
                right = mid

            if right - left < tolerance:
                break

        return (left + right) / 2, False


class SpecialFunctions:
    """Special mathematical functions."""

    @staticmethod
    def sigmoid(x: NDArray[Any], temperature: float = 1.0) -> NDArray[Any]:
        """Sigmoid function with temperature."""
        return 1 / (1 + np.exp(-x / temperature))

    @staticmethod
    def tanh_scaled(x: NDArray[Any], scale: float = 1.0) -> NDArray[Any]:
        """Scaled hyperbolic tangent."""
        return scale * np.tanh(x / scale)

    @staticmethod
    def gaussian(x: NDArray[Any], mean: float = 0.0, std: float = 1.0) -> NDArray[Any]:
        """Gaussian function."""
        return np.exp(-0.5 * ((x - mean) / std) ** 2) / (std * np.sqrt(2 * PI))  # type: ignore[no-any-return]

    @staticmethod
    def rbf_kernel(x: NDArray[Any], y: NDArray[Any], gamma: float = 1.0) -> float:
        """Radial basis function (Gaussian) kernel."""
        return float(np.exp(-gamma * np.linalg.norm(x - y) ** 2))

    @staticmethod
    def sinc(x: NDArray[Any]) -> NDArray[Any]:
        """Sinc function: sin(πx)/(πx)."""
        x_safe = np.where(np.abs(x) < 1e-8, 1e-8, x)  # Avoid division by zero
        return np.sin(PI * x_safe) / (PI * x_safe)


class ArrayUtils:
    """Array manipulation utilities."""

    @staticmethod
    def pad_to_shape(
        array: NDArray[Any], target_shape: tuple[int, ...], mode: str = "constant", **kwargs: Any
    ) -> NDArray[Any]:
        """Pad array to target shape."""
        current_shape = array.shape

        if len(current_shape) != len(target_shape):
            raise ValueError("Array and target must have same number of dimensions")

        pad_widths = []
        for current, target in zip(current_shape, target_shape, strict=False):
            if current > target:
                raise ValueError(f"Array dimension {current} larger than target {target}")

            total_pad = target - current
            pad_left = total_pad // 2
            pad_right = total_pad - pad_left
            pad_widths.append((pad_left, pad_right))

        return np.pad(array, pad_widths, mode=mode, **kwargs)  # type: ignore[no-any-return,call-overload]

    @staticmethod
    def sliding_window(array: NDArray[Any], window_size: int, step: int = 1) -> NDArray[Any]:
        """Create sliding window view of array."""
        if window_size > len(array):
            return array[np.newaxis, :]

        shape = ((len(array) - window_size) // step + 1, window_size)
        strides = (array.strides[0] * step, array.strides[0])

        return np.lib.stride_tricks.as_strided(array, shape=shape, strides=strides)

    @staticmethod
    def safe_concatenate(arrays: list[NDArray[Any]], axis: int = 0) -> NDArray[Any]:
        """Safely concatenate arrays with shape validation."""
        if not arrays:
            raise ValueError("No arrays to concatenate")

        if len(arrays) == 1:
            return arrays[0]

        # Validate shapes
        ref_shape = list(arrays[0].shape)
        for i, arr in enumerate(arrays[1:], 1):
            arr_shape = list(arr.shape)
            for dim, (ref_size, arr_size) in enumerate(zip(ref_shape, arr_shape, strict=False)):
                if dim != axis and ref_size != arr_size:
                    raise ValueError(
                        f"Shape mismatch in array {i}, dimension {dim}: {ref_size} vs {arr_size}"
                    )

        return np.concatenate(arrays, axis=axis)


# Convenience functions for most common operations
def normalize(x: NDArray[Any], method: str = "l2") -> NDArray[Any]:
    """Normalize array using specified method."""
    if method == "l2":
        norm = np.linalg.norm(x)
        return x / (norm + 1e-8)
    elif method == "l1":
        norm = np.sum(np.abs(x))
        return x / (norm + 1e-8)  # type: ignore[no-any-return]
    elif method == "max":
        max_val = np.max(np.abs(x))
        return x / (max_val + 1e-8)  # type: ignore[no-any-return]
    else:
        return Signal.normalize_signal(x, method)


def create_meshgrid(
    x_range: tuple[float, float], y_range: tuple[float, float], resolution: int = 100
) -> tuple[NDArray[Any], NDArray[Any]]:
    """Create 2D meshgrid for visualization/sampling."""
    x = np.linspace(x_range[0], x_range[1], resolution)
    y = np.linspace(y_range[0], y_range[1], resolution)
    X, Y = np.meshgrid(x, y)
    return (X, Y)


def random_orthogonal_matrix(n: int, random_state: int | None = None) -> Matrix:
    """Generate random orthogonal matrix."""
    if random_state is not None:
        np.random.seed(random_state)

    # QR decomposition of random matrix gives orthogonal Q
    A = np.random.randn(n, n)
    Q, _ = np.linalg.qr(A)
    return Q


def compute_eigenvalues_safe(matrix: Matrix, hermitian: bool = False) -> NDArray[Any]:
    """Safely compute eigenvalues with error handling."""
    try:
        if hermitian:
            return np.linalg.eigvalsh(matrix)
        else:
            eigenvals, _ = np.linalg.eig(matrix)
            return eigenvals
    except np.linalg.LinAlgError as e:
        logger.warning(f"Eigenvalue computation failed: {e}")
        # Return zeros as fallback
        return np.zeros(matrix.shape[0])


def stable_rank(matrix: Matrix, tolerance: float = 1e-12) -> int:
    """Compute stable rank of matrix."""
    try:
        singular_values = np.linalg.svd(matrix, compute_uv=False)
        return int(np.sum(singular_values > tolerance))
    except np.linalg.LinAlgError:
        logger.warning("SVD failed, returning matrix minimum dimension")
        return min(matrix.shape)
