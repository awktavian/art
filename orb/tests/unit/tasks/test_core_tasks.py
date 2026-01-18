"""Unit tests for `kagami.core.tasks`.

These tests are designed to run in lightweight environments where Celery may not
be installed (CI/minimal dev). They validate:
- Task helper functions (pure logic)
- Task behavior using mocked Redis/DB backends
- Optional Celery import does not break imports
"""

from __future__ import annotations
from typing import Any

import json
import sys
import types
from datetime import datetime, timedelta

import pytest


def test_month_window_from_period_valid():
    from kagami.core.tasks import tasks

    start, end = tasks._month_window_from_period("2025-12")
    assert start.year == 2025 and start.month == 12 and start.day == 1
    assert end.year == 2026 and end.month == 1 and end.day == 1


@pytest.mark.parametrize("period", ["", "202512", "2025/12", "20-12", "2025-13"])
def test_month_window_from_period_invalid(period: str) -> None:
    from kagami.core.tasks import tasks

    with pytest.raises(ValueError):
        tasks._month_window_from_period(period)


def test_extract_tokens_from_receipt_blobs():
    from kagami.core.tasks import tasks

    metrics = {"tokens_used": 10}
    event = {"data": {"usage": {"total_tokens": 5}}}
    assert tasks._extract_tokens_from_receipt_blobs(metrics, event) == 15

    # Negative values ignored
    metrics2 = {"tokens_used": -1}
    event2 = {"data": {"usage": {"total_tokens": -3, "prompt_tokens": 2}}}
    assert tasks._extract_tokens_from_receipt_blobs(metrics2, event2) == 2


def test_extract_bytes_from_receipt_blobs():
    from kagami.core.tasks import tasks

    metrics = {"storage_bytes": 100, "bytes_written": 50}
    event = {"data": {"bytes_sent": 20, "bytes_received": 10}}
    storage, bandwidth = tasks._extract_bytes_from_receipt_blobs(metrics, event)
    assert storage == 150
    assert bandwidth == 30


def test_sync_embeddings_task_counts_vectors(monkeypatch: Any) -> None:
    from kagami.core.tasks import tasks

    class FakeRedis:
        def __init__(self) -> None:
            self._values = {
                "kagami:embedding:1": json.dumps({"vector": [1, 2, 3], "metadata": {"a": 1}}),
                "kagami:embedding:2": "not-json",
            }

        def scan(self, cursor: int, *, match: str, count: int):
            assert match == "kagami:embedding:*"
            return 0, list(self._values.keys())

        def get(self, key: str):
            return self._values.get(key)

    # Patch RedisClientFactory.get_client used inside the task
    import kagami.core.caching.redis as redis_mod

    monkeypatch.setattr(redis_mod.RedisClientFactory, "get_client", lambda *a, **k: FakeRedis())

    result = tasks.sync_embeddings_task()
    assert result["status"] == "success"
    assert result["total_keys"] == 2
    assert result["synced"] == 1
    assert result["errors"] == 1


def test_generate_analytics_task_aggregates_receipts(monkeypatch: Any) -> None:
    from kagami.core.tasks import tasks

    now = datetime.utcnow().timestamp()
    old = (datetime.utcnow() - timedelta(days=365)).timestamp()

    receipts = {
        "kagami:receipt:1": json.dumps({"timestamp": now, "status": "success", "app": "app1"}),
        "kagami:receipt:2": json.dumps({"timestamp": now, "status": "error", "app": "app2"}),
        "kagami:receipt:3": json.dumps({"timestamp": old, "status": "success", "app": "app1"}),
    }

    class FakeRedis:
        def __init__(self) -> None:
            self.setex_calls: list[tuple[str, int, str]] = []

        def scan(self, cursor: int, *, match: str, count: int):
            assert match == "kagami:receipt:*"
            return 0, list(receipts.keys())

        def get(self, key: str):
            return receipts.get(key)

        def setex(self, key: str, ttl: int, value: str) -> None:
            self.setex_calls.append((key, ttl, value))

    import kagami.core.caching.redis as redis_mod

    fake = FakeRedis()
    monkeypatch.setattr(redis_mod.RedisClientFactory, "get_client", lambda *a, **k: fake)

    out = tasks.generate_analytics_task("daily")
    assert out["status"] == "success"
    report = out["report"]
    assert report["total_operations"] == 2
    assert report["success_count"] == 1
    assert report["error_count"] == 1
    assert report["success_rate"] == 50.0
    assert report["top_apps"] == {"app1": 1, "app2": 1}

    # Report is persisted with TTL (7 days)
    assert fake.setex_calls
    key, ttl, value = fake.setex_calls[-1]
    assert key.startswith("kagami:analytics:daily:")
    assert ttl == 86400 * 7
    assert json.loads(value)["report_type"] == "daily"


def test_process_intent_task_not_found(monkeypatch: Any) -> None:
    from kagami.core.tasks import tasks

    class FakeRedis:
        def get(self, _key: str):
            return None

    import kagami.core.caching.redis as redis_mod

    monkeypatch.setattr(redis_mod.RedisClientFactory, "get_client", lambda *a, **k: FakeRedis())

    # process_intent_task is synchronous (uses asyncio.run internally)
    out = tasks.process_intent_task("intent-123")
    assert out["status"] == "error"
    assert out["intent_id"] == "intent-123"


def test_process_intent_task_success(monkeypatch: Any) -> None:
    from kagami.core.tasks import tasks

    intent_payload = {"action": "ping", "metadata": {"x": 1}}

    class FakeRedis:
        def __init__(self) -> None:
            self.store: dict[str, str] = {
                "kagami:intent:intent-abc": json.dumps(intent_payload),
            }
            self.setex_calls: list[tuple[str, int, str]] = []

        def get(self, key: str):
            return self.store.get(key)

        def setex(self, key: str, ttl: int, value: str) -> None:
            self.setex_calls.append((key, ttl, value))
            self.store[key] = value

    import kagami.core.caching.redis as redis_mod

    fake = FakeRedis()
    monkeypatch.setattr(redis_mod.RedisClientFactory, "get_client", lambda *a, **k: fake)

    # Inject a lightweight orchestrator module so tasks.process_intent_task can import it
    orch = types.ModuleType("kagami.core.orchestrator")

    async def process_intent_async(intent: Any) -> Dict[str, Any]:
        assert intent == intent_payload
        return {"ok": True}

    orch.process_intent_async = process_intent_async  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "kagami.core.orchestrator", orch)

    # process_intent_task is synchronous (uses asyncio.run internally)
    out = tasks.process_intent_task("intent-abc")
    assert out["status"] == "success"
    assert out["intent_id"] == "intent-abc"
    assert out["result"] == {"ok": True}

    # Result cached in Redis
    assert any(
        k.startswith("kagami:intent:result:intent-abc") for (k, _ttl, _v) in fake.setex_calls
    )


def test_health_check_task_success(monkeypatch: Any) -> Any:
    from kagami.core.tasks import tasks

    # Inject a lightweight async_connection module
    async_conn = types.ModuleType("kagami.core.database.async_connection")

    class _Conn:
        async def execute(self, _sql: str) -> None:
            return None

    class _Begin:
        async def __aenter__(self) -> Any:
            return _Conn()

        async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
            return False

    class _Engine:
        def begin(self):
            return _Begin()

    async_conn.async_engine = _Engine()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "kagami.core.database.async_connection", async_conn)

    # Patch RedisClientFactory.get_client used inside the task
    cache_mod = types.ModuleType("kagami.core.caching.redis")

    class _AsyncRedis:
        async def ping(self) -> bool:
            return True

    class RedisClientFactory:
        @staticmethod
        def get_client(_purpose: str, async_mode: bool = False, **_kwargs) -> str:
            assert async_mode is True
            return _AsyncRedis()

    cache_mod.RedisClientFactory = RedisClientFactory  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "kagami.core.caching.redis", cache_mod)

    out = tasks.health_check_task()
    assert out["status"] == "success"
    health = out["health"]
    assert health["redis"] is True
    assert health["database"] is True
    assert isinstance(health["timestamp"], str) and health["timestamp"]
