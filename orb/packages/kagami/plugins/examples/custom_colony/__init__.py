"""Custom Colony Plugin Example.

This example demonstrates how to create a custom colony agent that integrates
with Kagami's unified organism system.

The custom colony:
- Extends BaseColonyAgent with specialized behavior
- Registers with the unified organism
- Implements catastrophe dynamics
- Provides custom tools and capabilities

Created: December 28, 2025
"""

from kagami.plugins.examples.custom_colony.plugin import ArchitectColonyPlugin

__all__ = ["ArchitectColonyPlugin"]
