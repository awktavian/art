"""Introspection and self-explanation.

MIGRATION NOTE (December 2025): Prefer importing from kagami.core.mind
for unified cognitive access.

NOTE (December 8, 2025): kagami.core.introspection was merged into debugging.
All imports are now local to this package.
"""

# Import types from correct local sources
from kagami.core.debugging.manager import (
    reflect_post_intent,
    start_periodic_reflection_loop,
    stop_periodic_reflection_loop,
)
from kagami.core.debugging.protocols import IntrospectionManagerProtocol
from kagami.core.debugging.self_explanation import (
    IntrospectionEngine,
    get_introspection_engine,
)
from kagami.core.debugging.unified_debugging_system import (
    ErrorDetection,
    ReasoningTrace,
)
from kagami.core.interfaces import SelfExplanation

__all__ = [
    "ErrorDetection",
    "IntrospectionEngine",
    "IntrospectionManagerProtocol",
    "ReasoningTrace",
    "SelfExplanation",
    "get_introspection_engine",
    # Manager (consolidated from kagami/introspection/)
    "reflect_post_intent",
    "start_periodic_reflection_loop",
    "stop_periodic_reflection_loop",
]
