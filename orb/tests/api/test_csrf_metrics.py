from __future__ import annotations
from typing import Any

import uuid

import anyio
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from kagami_api import create_app

pytestmark = [pytest.mark.tier_integration, pytest.mark.asyncio]


async def _metrics_text(client: AsyncClient) -> str:
    response = await client.get("/metrics")
    assert response.status_code == 200
    return response.text


@pytest_asyncio.fixture
async def csrf_metrics_client(monkeypatch: Any) -> None:
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "1")
    monkeypatch.setenv("ALLOW_REGISTRATION", "1")
    monkeypatch.setenv("KAGAMI_ALLOW_WEAK_HASH", "1")
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def test_csrf_metrics_pass_increments(csrf_metrics_client: AsyncClient) -> None:
    before = await _metrics_text(csrf_metrics_client)
    base_pass = 0
    for line in before.splitlines():
        if line.startswith("kagami_csrf_validation_total") and 'result="pass"' in line:
            try:
                base_pass = int(float(line.rsplit(" ", 1)[-1]))
            except Exception:
                base_pass = 0

    # Valid CSRF — use registration route (open when ALLOW_REGISTRATION=1)
    tok = (await csrf_metrics_client.get("/api/user/csrf-token")).json()
    headers = {
        "X-CSRF-Token": tok["csrf_token"],
        "X-Session-ID": tok["session_id"],
        "Idempotency-Key": str(uuid.uuid4()),
    }
    payload = {
        "username": f"csrf-user-{uuid.uuid4().hex}",
        "password": "StrongP@ssw0rd!",
        "email": f"{uuid.uuid4().hex}@example.com",
    }
    r = await csrf_metrics_client.post("/api/user/register", json=payload, headers=headers)
    assert r.status_code in (200, 201), r.text

    await anyio.sleep(0.6)

    after = await _metrics_text(csrf_metrics_client)
    new_pass = None
    for line in after.splitlines():
        if line.startswith("kagami_csrf_validation_total") and 'result="pass"' in line:
            try:
                new_pass = int(float(line.rsplit(" ", 1)[-1]))
            except Exception:
                pass
    assert new_pass is not None and new_pass >= base_pass + 1


async def test_csrf_metrics_fail_increments(csrf_metrics_client: AsyncClient) -> None:
    before = await _metrics_text(csrf_metrics_client)
    base_fail = 0
    for line in before.splitlines():
        if line.startswith("kagami_csrf_validation_total") and 'result="fail"' in line:
            try:
                base_fail = int(float(line.rsplit(" ", 1)[-1]))
            except Exception:
                base_fail = 0

    # Missing CSRF token → fail — use registration route (no Authorization header)
    # Include idempotency key to avoid 400 error
    payload = {
        "username": f"csrf-fail-{uuid.uuid4().hex}",
        "password": "StrongP@ssw0rd!",
        "email": f"{uuid.uuid4().hex}@example.com",
    }
    headers = {"Idempotency-Key": str(uuid.uuid4())}
    r = await csrf_metrics_client.post("/api/user/register", json=payload, headers=headers)
    # Should get 403 for CSRF failure or 400 for validation
    assert r.status_code in (400, 403)

    await anyio.sleep(0.6)

    after = await _metrics_text(csrf_metrics_client)
    new_fail = None
    for line in after.splitlines():
        if line.startswith("kagami_csrf_validation_total") and 'result="fail"' in line:
            try:
                new_fail = int(float(line.rsplit(" ", 1)[-1]))
            except Exception:
                pass
    assert new_fail is not None and new_fail >= base_fail + 1
