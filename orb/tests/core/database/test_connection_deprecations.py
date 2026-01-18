"""Tests for database connection patterns.

TIER: Unit (tests session factory and get_db patterns)
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration


@pytest.mark.tier_unit
def test_get_session_factory_returns_sessionmaker() -> None:
    """Test get_session_factory() returns a sessionmaker."""

    from kagami.core.database.connection import get_session_factory

    factory = get_session_factory()
    assert factory is not None
    assert callable(factory)

    # Should be able to create sessions
    db = factory()
    assert db is not None
    assert hasattr(db, "query")
    assert hasattr(db, "commit")
    assert hasattr(db, "close")

    db.close()


@pytest.mark.tier_unit
def test_get_session_factory_singleton() -> None:
    """Test get_session_factory() returns the same factory instance."""
    from kagami.core.database.connection import get_session_factory

    factory1 = get_session_factory()
    factory2 = get_session_factory()

    # Should be same instance (cached)
    assert factory1 is factory2


@pytest.mark.tier_unit
def test_get_db_preferred_pattern() -> None:
    """Test preferred get_db() pattern (generator)."""
    from kagami.core.database.connection import get_db

    # get_db() returns a generator for dependency injection
    gen = get_db()
    assert hasattr(gen, "__next__")

    # Should work with next()
    db = next(gen)
    assert db is not None
    assert hasattr(db, "query")

    # Cleanup
    try:
        next(gen)
    except StopIteration:
        pass  # Expected


@pytest.mark.tier_unit
def test_session_factory_creates_independent_sessions() -> None:
    """Test that each call to factory() creates a new session."""
    from kagami.core.database.connection import get_session_factory

    factory = get_session_factory()
    db1 = factory()
    db2 = factory()

    try:
        # Should be different session objects
        assert db1 is not db2
    finally:
        db1.close()
        db2.close()
