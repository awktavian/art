"""Custom Forge Module Plugin Example.

This example demonstrates how to create a custom Forge module that extends
Kagami's content generation capabilities.

The custom module:
- Integrates with Forge matrix orchestrator
- Implements custom generation logic
- Registers via module registration hooks
- Provides new content types

Created: December 28, 2025
"""

from kagami.plugins.examples.custom_forge.plugin import DocumentGeneratorPlugin

__all__ = ["DocumentGeneratorPlugin"]
