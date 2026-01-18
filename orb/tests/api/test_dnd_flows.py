from __future__ import annotations


from typing import Any

import uuid


def test_dnd_hp_and_conditions_and_tick(client: Any, csrf_headers: Any) -> None:
    headers = {**csrf_headers, "Idempotency-Key": str(uuid.uuid4())}
    # Upsert a party
    r = client.post(
        "/api/creation/encounter/party/upsert",
        json={
            "party_id": "party:test",
            "members": ["pc:one", "pc:two"],
            "active_index": 0,
        },
        headers=headers,
    )
    # DnD flows are optional; accept 200 when enabled, 404/503 when disabled
    assert r.status_code in (200, 404, 503), r.text
    if r.status_code != 200:
        return

    # Update HP
    r2 = client.post(
        "/api/creation/encounter/hp/update",
        json={"party_id": "party:test", "member_id": "pc:one", "set": 12},
        headers=headers,
    )
    assert r2.status_code in (200, 404, 503), r2.text
    if r2.status_code == 200:
        assert r2.json().get("hp") == 12

    # Add condition
    r3 = client.post(
        "/api/creation/encounter/condition/update",
        json={"party_id": "party:test", "member_id": "pc:one", "add": ["blessed"]},
        headers=headers,
    )
    assert r3.status_code in (200, 404, 503), r3.text
    if r3.status_code == 200:
        assert "blessed" in (r3.json().get("conditions") or [])

    # Tick initiative manually and ensure no error
    r4 = client.post(
        "/api/creation/encounter/initiative/tick",
        json={"party_id": "party:test", "room_id": "default"},
        headers=headers,
    )
    assert r4.status_code in (200, 404, 503), r4.text
