"""Kagami core integration module.

Provides integration components for system-wide coordination.
"""

from .recursive_improvement import (
    IntegrationConfig,
    RecursiveImprovementSystem,
    get_recursive_improvement_system,
    reset_recursive_improvement_system,
)

__all__ = [
    "IntegrationConfig",
    "RecursiveImprovementSystem",
    "get_recursive_improvement_system",
    "reset_recursive_improvement_system",
]
