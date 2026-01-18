from __future__ import annotations

from typing import Any

import uuid

import pytest

pytestmark = [pytest.mark.tier_integration, pytest.mark.asyncio]

CRDT_ENDPOINT = "/api/rooms/crdt/apply"
_ACCEPTABLE_UNAVAILABLE = {404, 501}


async def test_rooms_crdt_apply_sequence(async_client: Any) -> None:
    """Verify CRDT ops apply sequentially or explicitly report unavailability."""

    async_client.headers.update({"Authorization": "Bearer test-api-key-fixture"})

    first_payload = {
        "room_id": "world:demo",
        "ops": [
            {"path": "hud.turn", "op": "set", "value": {"party": "p1", "index": 0}},
        ],
    }
    response1 = await async_client.post(
        CRDT_ENDPOINT, json=first_payload, headers={"Idempotency-Key": str(uuid.uuid4())}
    )

    assert response1.status_code in {200, *_ACCEPTABLE_UNAVAILABLE}, response1.text

    if response1.status_code in _ACCEPTABLE_UNAVAILABLE:
        payload = (
            response1.json()
            if response1.headers.get("content-type", "").startswith("application/json")
            else {}
        )
        assert "detail" in payload or "not found" in response1.text.lower()
        return

    seq1 = response1.json().get("seq")
    assert isinstance(seq1, int) and seq1 >= 1

    followup_payload = {
        "room_id": "world:demo",
        "ops": [
            {"path": "hud.turn.index", "op": "set", "value": 1},
        ],
    }
    response2 = await async_client.post(
        CRDT_ENDPOINT, json=followup_payload, headers={"Idempotency-Key": str(uuid.uuid4())}
    )
    assert response2.status_code == 200, response2.text
    seq2 = response2.json().get("seq")
    assert isinstance(seq2, int) and seq2 > seq1
