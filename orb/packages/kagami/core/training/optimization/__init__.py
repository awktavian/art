"""K OS optimization module.

Includes:
- Meta-optimizer for learning rate adaptation
- Integration optimizer for subsystem coordination
- Vector search tuner for embedding optimization
- Dynamic loader for agent-generated optimizations (consolidated from optimizations/)
"""

from .dynamic_loader import DynamicOptimizationLoader, load_dynamic_optimizations

__all__ = [
    "DynamicOptimizationLoader",
    "load_dynamic_optimizations",
]
