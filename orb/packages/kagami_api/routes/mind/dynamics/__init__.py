"""Dynamics Management Package - Unified chaos and criticality control.

Consolidates edge-of-chaos management:
- /chaos/* - Chaos safety monitoring (CBF-based)
- /criticality/* - Self-organized criticality (Lyapunov)

Both systems work together to keep the organism at the "edge of chaos"
where computation is most effective.

Consolidated: December 8, 2025
"""

from .core import get_router

__all__ = ["get_router"]
