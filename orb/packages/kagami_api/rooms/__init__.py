"""K OS rooms module.

Proxy layer for backward compatibility. Core implementations in kagami.core.rooms.

NOTE: state_service.py is the main file used by API routes.
      Reconnection is imported directly from kagami.core.rooms.reconnection.
"""

# This package exists to proxy kagami.core.rooms to kagami_api.rooms
# for API modules that need room state management.

# The main used file is state_service.py which re-exports from core.

__all__: list[str] = []
