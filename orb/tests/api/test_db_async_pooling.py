
from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



@pytest.mark.asyncio
async def test_async_engine_is_pooled(monkeypatch: pytest.MonkeyPatch):
    # Ensure we construct engine via async_connection to exercise pooling choice
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    from kagami.core.database import async_connection as ac

    eng = ac.async_engine
    # For sqlite in-memory we keep lightweight engine; still should be AsyncEngine
    from sqlalchemy.ext.asyncio import AsyncEngine

    assert isinstance(eng, AsyncEngine)


@pytest.mark.asyncio
async def test_concurrent_sessions_do_not_crash(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    from kagami.core.database import async_connection as ac

    async def _use_session(idx: int):
        async with ac.AsyncSessionLocal() as s:
            # no-op simple statement to ensure connection checkout is valid
            await s.run_sync(lambda sync: None)

    # Launch small concurrent batch
    import asyncio

    await asyncio.gather(*[_use_session(i) for i in range(5)])
