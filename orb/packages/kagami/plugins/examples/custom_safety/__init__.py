"""Custom Safety Filter Plugin Example.

This example demonstrates how to create a custom safety filter that integrates
with Kagami's Control Barrier Function (CBF) system.

The custom safety filter:
- Implements domain-specific safety checks
- Integrates with the CBF pipeline
- Provides custom threat detection
- Contributes to h(x) >= 0 invariant

Created: December 28, 2025
"""

from kagami.plugins.examples.custom_safety.plugin import CodeSecurityFilterPlugin

__all__ = ["CodeSecurityFilterPlugin"]
