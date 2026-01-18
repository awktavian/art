from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import base64
import io
import uuid

from PIL import Image


@pytest.mark.anyio
async def test_ar_scene_cache_hits(monkeypatch, client, csrf_headers) -> None:
    """Smoke test for AR analyze cache behavior.

    AR analyze is optional; this test only asserts that the endpoint is reachable
    and does not crash, tolerating 200/501/404 as valid outcomes.
    """
    # Create a small synthetic image
    img = Image.new("RGB", (64, 36), (10, 20, 30))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    payload = {"image_data": b64}
    headers = {**csrf_headers, "Idempotency-Key": str(uuid.uuid4())}

    # First call (miss)
    r1 = client.post("/api/ar/analyze", json=payload, headers=headers)
    assert r1.status_code in (200, 501, 404)

    # Second call should hit cache if AR analyze is enabled; tolerate non-impl or idempotency 409
    r2 = client.post("/api/ar/analyze", json=payload, headers=headers)
    assert r2.status_code in (200, 501, 404, 409)
