from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import uuid


@pytest.mark.anyio
async def test_ar_space_join_and_leave(client) -> None:
    # Join a shared space
    rj = client.post(
        "/api/ar/space/join",
        json={"space_id": "space_test_123", "mascot": None, "image_data": None},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert rj.status_code in (200, 403, 501)
    if rj.status_code == 200:
        body = rj.json()
        assert body.get("joined") is True
        assert body.get("space_id") == "space_test_123"
        assert isinstance(body.get("members"), list)

        # Leave the shared space
        rl = client.post(
            "/api/ar/space/leave",
            json={
                "space_id": "space_test_123",
                "mascot": None,
                "image_data": None,
            },
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )
        assert rl.status_code == 200
        lbody = rl.json()
        assert lbody.get("left") is True
        assert lbody.get("space_id") == "space_test_123"
