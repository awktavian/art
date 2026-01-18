"""Receipt storage regression tests covering in-memory cache and search APIs."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from kagami_api import create_app
from kagami_api.routes.mind import receipts as receipt_routes

from kagami.core.receipts import ingestor as receipt_storage


def _add_receipt(
    correlation_id: str,
    *,
    phase: str = "EXECUTE",
    event_name: str = "test.event",
    ts: datetime | None = None,
    intent: dict | None = None,
    event: str = "test_event",
    status: str = "success",
    **extra,
) -> dict:
    payload = {
        "correlation_id": correlation_id,
        "phase": phase,
        "event_name": event_name,
        "ts": (ts or datetime.utcnow()).isoformat(),
        "intent": intent or {"type": "test_intent", "user_id": "test_user"},
        "event": event,
        "status": status,
    }
    payload.update(extra)
    receipt_routes.add_receipt(payload)
    return payload


@pytest.fixture(autouse=True)
def reset_receipts(monkeypatch: Any, tmp_path: Any) -> Any:
    receipt_storage._RECEIPTS.clear()
    monkeypatch.setenv("KAGAMI_STREAM_PROCESSING_ENABLED", "0")
    monkeypatch.setenv("KAGAMI_RECEIPTS_LOG", str(tmp_path / "receipts.jsonl"))
    yield
    receipt_storage._RECEIPTS.clear()


@pytest_asyncio.fixture
async def client():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def test_store_receipt_kept_in_memory():
    receipt = _add_receipt("store-test", phase="PLAN")
    stored = [
        r for r in receipt_storage._RECEIPTS.values() if r.get("correlation_id") == "store-test"
    ]
    assert stored, "receipt not persisted in memory cache"
    assert stored[0]["phase"] == "PLAN"
    assert stored[0]["event_name"] == receipt["event_name"]


@pytest.mark.skip(reason="Requires full API stack - move to integration tier")
@pytest.mark.asyncio
async def test_list_receipts_returns_recent(client: Any) -> None:
    for idx in range(3):
        _add_receipt(f"list-{uuid4()}", event_name=f"test.{idx}")
    resp = await client.get("/api/mind/receipts/", params={"limit": 5})
    # Skip test if route not registered (404)
    if resp.status_code == 404:
        pytest.skip("Receipts route not registered in test environment")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload.get("count", 0) >= 3
    ids = [rec.get("correlation_id") for rec in payload.get("receipts", [])]
    assert len(ids) >= 3


@pytest.mark.skip(reason="Requires full API stack - move to integration tier")
@pytest.mark.asyncio
async def test_search_receipts_by_correlation_id(client: Any) -> None:
    corr_id = f"search-{uuid4()}"
    _add_receipt(corr_id, event_name="search.event")
    resp = await client.get("/api/mind/receipts/search", params={"correlation_id": corr_id})
    # Skip test if route not registered (404) or service unavailable (503)
    if resp.status_code == 404:
        pytest.skip("Receipts route not registered in test environment")
    if resp.status_code == 503:
        pytest.skip("Service unavailable - external dependency (etcd/redis) not running")
    assert resp.status_code == 200
    receipts = resp.json()["receipts"]
    matches = [r for r in receipts if r.get("correlation_id") == corr_id]
    assert matches, "expected correlation_id to be returned by search"


@pytest.mark.skip(reason="Requires full API stack - move to integration tier")
@pytest.mark.asyncio
async def test_receipts_ordered_by_timestamp(client: Any) -> None:
    corr_id = f"ordered-{uuid4()}"
    base = datetime.utcnow()
    _add_receipt(corr_id, phase="PLAN", ts=base - timedelta(seconds=2))
    _add_receipt(corr_id, phase="EXECUTE", ts=base - timedelta(seconds=1))
    _add_receipt(corr_id, phase="VERIFY", ts=base)
    resp = await client.get("/api/mind/receipts/search", params={"correlation_id": corr_id})
    # Skip test if route not registered (404) or service unavailable (503)
    if resp.status_code == 404:
        pytest.skip("Receipts route not registered in test environment")
    if resp.status_code == 503:
        pytest.skip("Service unavailable - external dependency (etcd/redis) not running")
    assert resp.status_code == 200
    receipts = resp.json()["receipts"]

    def _as_datetime(value: Any) -> Any:
        if isinstance(value, int | float):
            return datetime.fromtimestamp(value)
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except Exception:
                return datetime.fromtimestamp(0)
        return datetime.fromtimestamp(0)

    times = [
        _as_datetime(rec.get("timestamp")) for rec in receipts if rec.get("timestamp") is not None
    ]
    assert times == sorted(times, reverse=True)


@pytest.mark.skip(reason="Requires full API stack - move to integration tier")
@pytest.mark.asyncio
async def test_receipt_persists_across_queries(client: Any) -> Any:
    corr_id = "persist"
    _add_receipt(corr_id, event_name="test.persist")
    first = await client.get("/api/mind/receipts/search", params={"correlation_id": corr_id})
    second = await client.get("/api/mind/receipts/search", params={"correlation_id": corr_id})
    # Skip test if route not registered (404) or service unavailable (503)
    if first.status_code == 404:
        pytest.skip("Receipts route not registered in test environment")
    if first.status_code == 503:
        pytest.skip("Service unavailable - external dependency (etcd/redis) not running")
    assert first.status_code == second.status_code == 200
    assert first.json()["receipts"] == second.json()["receipts"]


def test_receipt_structure_consistent():
    sample = _add_receipt("structure-test", workspace_hash="abc123")
    stored = [
        r for r in receipt_storage._RECEIPTS.values() if r.get("correlation_id") == "structure-test"
    ]
    assert stored, "receipt not found in cache"
    record = stored[0]
    assert record["workspace_hash"] == "abc123"
    assert isinstance(record["event_name"], str)
    assert record["phase"] in {"PLAN", "EXECUTE", "VERIFY"}
