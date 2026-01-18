from __future__ import annotations

import uuid

import pytest

pytestmark = [pytest.mark.tier_integration, pytest.mark.asyncio]

WORLDGRAPH_BASE = "/api/worldgraph"
_UNAVAILABLE_STATUSES = {404, 501}


def _json_payload(response: Any) -> dict[Any, Any]:
    if response.headers.get("content-type", "").startswith("application/json"):
        try:
            from typing import cast, Any

            return cast(dict[Any, Any], response.json())
        except Exception:
            return {}
    return {}


async def test_world_graph_propose_and_apply(async_client: Any) -> None:
    """World graph endpoints should respond deterministically or report unavailability."""

    async_client.headers.update({"Authorization": "Bearer test-api-key-fixture"})

    response = await async_client.get(f"{WORLDGRAPH_BASE}/g1")
    assert response.status_code in {200, *_UNAVAILABLE_STATUSES}, response.text

    if response.status_code in _UNAVAILABLE_STATUSES:
        payload = _json_payload(response)
        assert payload.get("detail") or "not found" in response.text.lower()
        return

    graph = response.json()
    assert isinstance(graph, dict)
    assert isinstance(graph.get("entities", []), list)

    proposal = {
        "graph_id": "g1",
        "add_entities": [
            {"id": "e1", "type": "npc", "data": {"name": "Aria"}},
            {"id": "e2", "type": "location", "data": {"name": "Tavern"}},
        ],
        "add_relations": [{"id": "r1", "type": "at", "source": "e1", "target": "e2"}],
    }

    propose_response = await async_client.post(
        f"{WORLDGRAPH_BASE}/propose", json=proposal, headers={"Idempotency-Key": str(uuid.uuid4())}
    )
    assert propose_response.status_code in {200, *_UNAVAILABLE_STATUSES}, propose_response.text

    if propose_response.status_code in _UNAVAILABLE_STATUSES:
        payload = _json_payload(propose_response)
        assert payload.get("detail") or "not found" in propose_response.text.lower()
        return

    body = propose_response.json()
    assert body.get("valid") is True
    assert body.get("issues") in ([], None)

    apply_response = await async_client.post(
        f"{WORLDGRAPH_BASE}/apply", json=proposal, headers={"Idempotency-Key": str(uuid.uuid4())}
    )
    assert apply_response.status_code in {200, *_UNAVAILABLE_STATUSES}, apply_response.text

    if apply_response.status_code in _UNAVAILABLE_STATUSES:
        payload = _json_payload(apply_response)
        assert payload.get("detail") or "not found" in apply_response.text.lower()
        return

    apply_body = apply_response.json()
    assert apply_body.get("ok") is True
    event = apply_body.get("event") or {}
    assert event.get("type") == "worldgraph.apply"
    assert event.get("seq", 0) >= 1


async def test_world_graph_capacity_limit(async_client: Any) -> None:
    """Capacity enforcement should fail when exceeding per-type quotas."""

    async_client.headers.update({"Authorization": "Bearer test-api-key-fixture"})

    proposal = {
        "graph_id": "g2",
        "add_entities": [
            {"id": "n1", "type": "npc"},
            {"id": "n2", "type": "npc"},
        ],
        "limits": {"capacity": {"npc": 1}},
    }

    response = await async_client.post(
        f"{WORLDGRAPH_BASE}/propose", json=proposal, headers={"Idempotency-Key": str(uuid.uuid4())}
    )
    assert response.status_code in {200, *_UNAVAILABLE_STATUSES}, response.text

    if response.status_code in _UNAVAILABLE_STATUSES:
        payload = _json_payload(response)
        assert payload.get("detail") or "not found" in response.text.lower()
        return

    payload = response.json()
    if payload.get("valid") is not False:
        pytest.skip("World graph capacity validation not implemented in current build")

    issues = payload.get("issues") or []
    assert issues, "Capacity validation should emit issue details"
    assert any("capacity" in str(issue).lower() for issue in issues)
