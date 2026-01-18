"""Centralized ID Generation - Single Source of Truth.

Consolidates duplicate ID generation functions from:
- kagami/core/correlation.py (merged December 21, 2025)
- kagami_api/correlation.py (imports from here)
- kagami/core/receipts/__init__.py
- kagami_api/routes/intents_lang.py
- kagami/core/orchestrator.py
- 15+ other files

Full Operation Mode: All ID generation goes through this module.

Format Compatibility:
- Standard format: Uses underscores (_) as separators
- ID length: 12 hex chars (default) for correlation IDs
- Request IDs: 'req_' prefix with 12 hex chars
- UUID format: Standard UUID4 with hyphens for full UUIDs
"""

import time
import uuid


def generate_correlation_id(
    name: str | None = None,
    prefix: str | None = None,
    length: int = 12,
) -> str:
    """Generate unique correlation ID for tracking operations.

    Consolidates patterns from kagami/core/correlation.py and maintains
    compatibility with existing receipt system expectations.

    Args:
        name: Optional name to include in ID (e.g., "intent", "forge")
        prefix: Optional prefix for ID (e.g., "req", "c", "autosave")
        length: Length of hex portion (default: 12, compatible with receipts)

    Returns:
        Unique correlation ID string

    Format:
        - With prefix and name: "{prefix}_{name}_{hex12}"
        - With prefix only: "{prefix}_{hex12}"
        - With name only: "{name}_{hex12}"
        - No prefix/name: "{hex12}"

    Examples:
        >>> generate_correlation_id()  # doctest: +SKIP
        'a3f5b7c9d2e1'

        >>> generate_correlation_id(name="intent")  # doctest: +SKIP
        'intent_a3f5b7c9d2e1'

        >>> generate_correlation_id(prefix="req")  # doctest: +SKIP
        'req_a3f5b7c9d2e1'

        >>> generate_correlation_id(prefix="c", length=16)  # doctest: +SKIP
        'c_a3f5b7c9d2e1f4a6'

    Note:
        The length parameter allows compatibility with legacy code that used
        different ID lengths (e.g., 8 for autosave, 16 for API requests).
    """
    base_id = uuid.uuid4().hex[:length]

    if prefix and name:
        return f"{prefix}_{name}_{base_id}"
    elif prefix:
        return f"{prefix}_{base_id}"
    elif name:
        return f"{name}_{base_id}"
    else:
        return base_id


def generate_uuid() -> str:
    """Generate standard UUID4.

    Returns:
        UUID4 string with hyphens

    Examples:
        >>> generate_uuid()
        'a3f5b7c9-d2e1-4f6a-8b9c-1d2e3f4a5b6c'
    """
    return str(uuid.uuid4())


def generate_short_id(length: int = 8) -> str:
    """Generate short random ID.

    Args:
        length: Length of ID (default 8)

    Returns:
        Short hex string

    Examples:
        >>> generate_short_id()
        'a3f5b7c9'

        >>> generate_short_id(16)
        'a3f5b7c9d2e1f4a6'
    """
    return uuid.uuid4().hex[:length]


def generate_timestamped_id(prefix: str | None = None) -> str:
    """Generate ID with timestamp component.

    Args:
        prefix: Optional prefix

    Returns:
        Timestamped ID

    Examples:
        >>> generate_timestamped_id()
        '1699000000_a3f5b7c9'

        >>> generate_timestamped_id("task")
        'task_1699000000_a3f5b7c9'
    """
    timestamp = int(time.time())
    short_id = uuid.uuid4().hex[:8]

    if prefix:
        return f"{prefix}_{timestamp}_{short_id}"
    else:
        return f"{timestamp}_{short_id}"


def generate_session_id() -> str:
    """Generate session ID.

    Returns:
        Session ID with 'session_' prefix

    Examples:
        >>> generate_session_id()
        'session_a3f5b7c9d2e1'
    """
    return f"session_{uuid.uuid4().hex[:12]}"


def generate_request_id() -> str:
    """Generate request ID for HTTP requests.

    Used by API middleware (kagami_api/correlation.py) for request tracking
    and distributed tracing with W3C Trace Context.

    Returns:
        Request ID with 'req_' prefix and 16 hex chars

    Format:
        'req_{hex16}' - Compatible with X-Request-ID header standards

    Examples:
        >>> generate_request_id()  # doctest: +SKIP
        'req_a3f5b7c9d2e1f4a6'

    Note:
        Uses 16 hex chars (vs 12 for correlation_id) to match
        W3C Trace Context span ID length expectations.
    """
    return f"req_{uuid.uuid4().hex[:16]}"


def generate_agent_id(agent_type: str | None = None) -> str:
    """Generate agent ID.

    Args:
        agent_type: Optional agent type

    Returns:
        Agent ID

    Examples:
        >>> generate_agent_id()  # doctest: +SKIP
        'agent_a3f5b7c9'

        >>> generate_agent_id("research")  # doctest: +SKIP
        'agent_research_a3f5b7c9'
    """
    short_id = uuid.uuid4().hex[:8]

    if agent_type:
        return f"agent_{agent_type}_{short_id}"
    else:
        return f"agent_{short_id}"


def generate_autosave_correlation_id() -> str:
    """Generate correlation ID for autosave operations.

    Used by the autosave service for checkpoint creation tracking.

    Returns:
        Correlation ID with 'autosave' prefix and 8 hex chars

    Format:
        'autosave_{hex8}' - Short ID for high-frequency autosave operations

    Examples:
        >>> generate_autosave_correlation_id()  # doctest: +SKIP
        'autosave_a3f5b7c9'

    Note:
        Uses shorter 8-char ID (vs 12-char default) for autosave operations
        which occur frequently and need compact IDs.
    """
    return generate_correlation_id(prefix="autosave", length=8)


__all__ = [
    "generate_agent_id",
    "generate_autosave_correlation_id",
    "generate_correlation_id",
    "generate_request_id",
    "generate_session_id",
    "generate_short_id",
    "generate_timestamped_id",
    "generate_uuid",
]
