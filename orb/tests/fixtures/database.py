"""Database fixtures for Kagami test suite.

Provides standardized database fixtures for testing:
- In-memory SQLite for fast unit tests
- PostgreSQL for integration tests
- Transaction management and cleanup
- Schema setup and teardown

Usage:
    @pytest.mark.requires_db
    def test_something(db_session):
        # Use db_session for database operations
        pass
"""

from __future__ import annotations

import asyncio
from typing import Any
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from kagami.core.database.base import Base


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async database session for testing.

    Uses SQLite in-memory by default for speed.
    Set KAGAMI_USE_REAL_DB=1 to use PostgreSQL.
    """
    import os

    if os.getenv("KAGAMI_USE_REAL_DB") == "1":
        db_url = "postgresql+asyncpg://test:test@localhost:5432/kagami_test"
    else:
        db_url = "sqlite+aiosqlite:///:memory:"

    engine = create_async_engine(db_url, echo=False)

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            yield session
        finally:
            await session.rollback()

    await engine.dispose()


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Provide a mocked database session for testing.

    Useful for testing without actual database operations.
    """
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_session.close = AsyncMock()
    return mock_session


@pytest_asyncio.fixture
async def db_with_test_data(db_session: AsyncSession) -> AsyncSession:
    """Provide a database session with pre-populated test data.

    Add common test data that many tests can use.
    """
    # Add any common test data here
    # Example:
    # test_user = User(name="test", email="test@example.com")
    # db_session.add(test_user)
    # await db_session.commit()

    return db_session


__all__ = [
    "db_session",
    "mock_db_session",
    "db_with_test_data",
]
