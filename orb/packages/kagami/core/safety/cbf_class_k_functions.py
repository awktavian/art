"""Parametric Class-K Functions for Control Barrier Functions.

CONSOLIDATED: December 14, 2025 into kagami.core.safety.cbf_utils

For new code, import from cbf_utils:
    from kagami.core.safety.cbf_utils import (
        LinearClassK,
        ExponentialClassK,
        create_class_k_function,
    )

Direct imports from this module still work for backward compatibility.

Provides various class-K function implementations beyond linear α(h) = α·h.

Class-K function properties:
- α(0) = 0
- α strictly increasing
- α continuous

References:
- Ames et al. 2017 - "Control Barrier Functions: Theory and Applications"
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import Any


class ClassKFunction(ABC):
    """Abstract base class for class-K functions."""

    @abstractmethod
    def evaluate(self, h: float) -> float:
        """Evaluate class-K function.

        Args:
            h: Barrier value

        Returns:
            α(h) value
        """

    @abstractmethod
    def derivative(self, h: float) -> float:
        """Compute derivative dα/dh.

        Args:
            h: Barrier value

        Returns:
            Derivative value
        """


class LinearClassK(ClassKFunction):
    """Linear class-K function: α(h) = k·h

    Simplest class-K function, currently used in CBF.
    """

    def __init__(self, k: float = 1.0) -> None:
        """Initialize linear class-K.

        Args:
            k: Proportionality constant (k > 0)

        Raises:
            ValueError: If k <= 0
        """
        if k <= 0:
            raise ValueError(f"k must be positive, got {k}")
        self.k = k

    def evaluate(self, h: float) -> float:
        """Evaluate α(h) = k·h.

        Args:
            h: Barrier value

        Returns:
            k·h
        """
        return self.k * h

    def derivative(self, h: float) -> float:
        """Derivative: dα/dh = k.

        Args:
            h: Barrier value (unused for linear)

        Returns:
            Constant k
        """
        return self.k


class ExponentialClassK(ClassKFunction):
    """Exponential class-K function: α(h) = k·(e^(λh) - 1)

    Provides faster convergence to safe set[Any] than linear.
    """

    def __init__(self, k: float = 1.0, lambda_param: float = 1.0) -> None:
        """Initialize exponential class-K.

        Args:
            k: Scaling constant (k > 0)
            lambda_param: Exponential rate (λ > 0)

        Raises:
            ValueError: If k <= 0 or lambda_param <= 0
        """
        if k <= 0:
            raise ValueError(f"k must be positive, got {k}")
        if lambda_param <= 0:
            raise ValueError(f"lambda_param must be positive, got {lambda_param}")
        self.k = k
        self.lambda_param = lambda_param

    def evaluate(self, h: float) -> float:
        """Evaluate α(h) = k·(e^(λh) - 1).

        Args:
            h: Barrier value

        Returns:
            k·(e^(λh) - 1)
        """
        return self.k * (math.exp(self.lambda_param * h) - 1.0)

    def derivative(self, h: float) -> float:
        """Derivative: dα/dh = k·λ·e^(λh).

        Args:
            h: Barrier value

        Returns:
            k·λ·e^(λh)
        """
        return self.k * self.lambda_param * math.exp(self.lambda_param * h)


class PolynomialClassK(ClassKFunction):
    """Polynomial class-K function: α(h) = k·h^p

    Provides tunable aggressiveness via exponent p.
    - p > 1: More aggressive near boundary
    - p < 1: Less aggressive near boundary
    - p = 1: Linear (default)
    """

    def __init__(self, k: float = 1.0, p: float = 2.0) -> None:
        """Initialize polynomial class-K.

        Args:
            k: Scaling constant (k > 0)
            p: Polynomial degree (p > 0, typically p >= 1)

        Raises:
            ValueError: If k <= 0 or p <= 0
        """
        if k <= 0:
            raise ValueError(f"k must be positive, got {k}")
        if p <= 0:
            raise ValueError(f"p must be positive, got {p}")
        self.k = k
        self.p = p

    def evaluate(self, h: float) -> float:
        """Evaluate α(h) = k·h^p.

        Args:
            h: Barrier value

        Returns:
            k·h^p (0 if h < 0 to maintain class-K properties)
        """
        if h < 0:
            return 0.0
        return float(self.k * (h**self.p))

    def derivative(self, h: float) -> float:
        """Derivative: dα/dh = k·p·h^(p-1).

        Args:
            h: Barrier value

        Returns:
            k·p·h^(p-1)
        """
        if h <= 0:
            return 0.0
        return float(self.k * self.p * (h ** (self.p - 1.0)))


class SigmoidClassK(ClassKFunction):
    """Sigmoid-based class-K function: α(h) = k·h·σ(λh)

    Where σ(x) = 1/(1+e^(-x)) is the sigmoid function.
    Provides smooth saturation behavior.
    """

    def __init__(self, k: float = 1.0, lambda_param: float = 2.0) -> None:
        """Initialize sigmoid class-K.

        Args:
            k: Scaling constant (k > 0)
            lambda_param: Sigmoid steepness (λ > 0)

        Raises:
            ValueError: If k <= 0 or lambda_param <= 0
        """
        if k <= 0:
            raise ValueError(f"k must be positive, got {k}")
        if lambda_param <= 0:
            raise ValueError(f"lambda_param must be positive, got {lambda_param}")
        self.k = k
        self.lambda_param = lambda_param

    def evaluate(self, h: float) -> float:
        """Evaluate α(h) = k·h·σ(λh).

        Args:
            h: Barrier value

        Returns:
            k·h·σ(λh)
        """
        sigmoid = 1.0 / (1.0 + math.exp(-self.lambda_param * h))
        return self.k * h * sigmoid

    def derivative(self, h: float) -> float:
        """Derivative: dα/dh = k·σ(λh)·(1 + λh·σ'(λh)).

        Args:
            h: Barrier value

        Returns:
            Derivative value
        """
        sigmoid = 1.0 / (1.0 + math.exp(-self.lambda_param * h))
        sigmoid_deriv = self.lambda_param * sigmoid * (1.0 - sigmoid)
        return self.k * sigmoid * (1.0 + h * sigmoid_deriv)


def create_class_k_function(function_type: str = "linear", **params: Any) -> ClassKFunction:
    """Factory for creating class-K functions.

    Args:
        function_type: Type of function ("linear", "exponential", "polynomial", "sigmoid")
        **params: Parameters for the function

    Returns:
        ClassKFunction instance

    Examples:
        >>> linear = create_class_k_function("linear", k=1.0)
        >>> exponential = create_class_k_function("exponential", k=1.0, lambda_param=1.0)
        >>> polynomial = create_class_k_function("polynomial", k=1.0, p=2.0)
    """
    # Filter params based on function type to avoid unexpected keyword arguments
    k = params.get("k", 1.0)

    if function_type == "linear":
        return LinearClassK(k=k)
    elif function_type == "exponential":
        lambda_param = params.get("lambda_param", 1.0)
        return ExponentialClassK(k=k, lambda_param=lambda_param)
    elif function_type == "polynomial":
        p = params.get("p", 2.0)
        return PolynomialClassK(k=k, p=p)
    elif function_type == "sigmoid":
        lambda_param = params.get("lambda_param", 2.0)
        return SigmoidClassK(k=k, lambda_param=lambda_param)
    else:
        raise ValueError(f"Unknown class-K function type: {function_type}")


__all__ = [
    "ClassKFunction",
    "ExponentialClassK",
    "LinearClassK",
    "PolynomialClassK",
    "SigmoidClassK",
    "create_class_k_function",
]
