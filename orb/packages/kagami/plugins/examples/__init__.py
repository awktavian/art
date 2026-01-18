"""Kagami Plugin Examples.

This package contains complete examples of different plugin types:

1. Custom Colony (`custom_colony/`):
   - Architect colony for system design
   - Demonstrates colony agent integration
   - Shows catastrophe dynamics implementation

2. Custom Safety Filter (`custom_safety/`):
   - Code security filter
   - Demonstrates CBF integration
   - Shows safety hook implementation

3. Custom Forge Module (`custom_forge/`):
   - Document generator module
   - Demonstrates Forge integration
   - Shows generation hook implementation

Usage:
    ```python
    from kagami.plugins import get_plugin_manager
    from kagami.plugins.examples.custom_colony import ArchitectColonyPlugin

    # Load example plugin
    manager = get_plugin_manager()
    plugin = ArchitectColonyPlugin()
    manager.register(plugin)
    manager.load("kagami.architect_colony")
    manager.start("kagami.architect_colony")
    ```

Created: December 28, 2025
"""

__all__ = []
