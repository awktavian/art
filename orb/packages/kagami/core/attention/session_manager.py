from __future__ import annotations

"""Session Memory Manager - Handles session lifecycle for valued-attention.

Responsibilities:
- Clear P_sess on context reset
- Persist P_long to Redis on session end
- Track correlation_id for session continuity
"""
import logging

from kagami.core.attention.preference_memory import (
    get_preference_memory,
    save_preference_memory,
)
from kagami.core.attention.value_function import save_value_function
from kagami.core.attention.valued_attention import (
    get_valued_attention_head,
    save_valued_attention_head,
)

logger = logging.getLogger(__name__)


class SessionMemoryManager:
    """Manages valued-attention memory across sessions."""

    def __init__(self) -> None:
        """Initialize session manager."""
        self.current_session_id: str | None = None
        self.session_count = 0

    def start_session(self, session_id: str) -> None:
        """Start new session - clear ephemeral memory.

        Args:
            session_id: Unique session identifier (correlation_id or session_id)
        """
        logger.info(f"Starting valued-attention session: {session_id}")

        # Get singletons
        pref_memory = get_preference_memory()
        valued_attention = get_valued_attention_head()

        # Clear session-level preferences
        pref_memory.reset_session()
        valued_attention.reset_session()

        self.current_session_id = session_id
        self.session_count += 1

        # Emit metric
        try:
            from kagami_observability.metrics import VALUED_ATTENTION_SESSIONS_TOTAL

            VALUED_ATTENTION_SESSIONS_TOTAL.inc()
        except Exception:
            pass

    def end_session(self) -> None:
        """End session - persist long-term memory."""
        if self.current_session_id is None:
            return

        logger.info(f"Ending valued-attention session: {self.current_session_id}")

        # Persist to Redis
        save_preference_memory()
        save_valued_attention_head()
        save_value_function()

        self.current_session_id = None

    def reset_all(self) -> None:
        """Hard reset - clear ALL memory (emergency only)."""
        logger.warning("HARD RESET: Clearing all valued-attention memory")

        pref_memory = get_preference_memory()
        pref_memory.P_long.fill(0.0)
        pref_memory.P_sess.fill(0.0)
        pref_memory.update_count_long = 0
        pref_memory.update_count_sess = 0

        # Save cleared state
        save_preference_memory()
        save_valued_attention_head()
        save_value_function()


# Singleton
_session_manager: SessionMemoryManager | None = None


def get_session_manager() -> SessionMemoryManager:
    """Get singleton session manager."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionMemoryManager()
    return _session_manager
