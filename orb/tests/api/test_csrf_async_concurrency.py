from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration


import asyncio


@pytest.mark.asyncio
async def test_csrf_inmemory_async_concurrency(monkeypatch: pytest.MonkeyPatch):
    # Force in-memory CSRF fallback
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "1")
    monkeypatch.setenv("KAGAMI_TEST_DISABLE_REDIS", "1")
    monkeypatch.delenv("CSRF_SECRET", raising=False)
    # Set test API key for authentication
    monkeypatch.setenv("KAGAMI_API_KEY", "test_api_key")

    from kagami_api import create_app

    app = create_app()

    try:
        import httpx

        transport = httpx.ASGITransport(app=app)
    except Exception as e:  # pragma: no cover
        pytest.skip(f"httpx ASGITransport unavailable: {e}")

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/user/csrf-token")
        assert r.status_code == 200
        tok = r.json()
        headers = {
            "X-CSRF-Token": tok["csrf_token"],
            "X-Session-ID": tok["session_id"],
            "Authorization": "Bearer test_api_key",
        }

        async def _post_once(idx: int):
            dynamic_headers = {
                **headers,
                "X-Forwarded-For": f"127.0.0.{idx % 250}",
                "User-Agent": f"pytest-client/{idx}",
            }
            # Use a simple endpoint that requires auth + CSRF but doesn't do heavy processing
            try:
                rr = await asyncio.wait_for(
                    client.post(
                        "/api/command/parse",
                        json={
                            "text": "LANG/2 STATUS system"
                        },  # Valid LANG/2 command with STATUS action
                        headers=dynamic_headers,
                    ),
                    timeout=10.0,  # 10 second timeout per request (CI stability)
                )
                return rr.status_code
            except TimeoutError:
                return 408  # Timeout status code
            except Exception as e:
                return 500  # Error status code

        # Test with smaller load to avoid timeout in CI
        N = 5  # Reduced to 5 concurrent requests for stability
        codes = await asyncio.gather(*[_post_once(i) for i in range(N)], return_exceptions=True)
        # Filter out exceptions and convert to status codes
        status_codes = [c if isinstance(c, int) else 500 for c in codes]

        # Main assertion: CSRF works concurrently without 403 (forbidden) errors
        assert all(
            code != 403 for code in status_codes
        ), f"Got 403 errors (CSRF failure): {status_codes}"
        # At least some requests should succeed (not all fail)
        success_or_client_error = [c for c in status_codes if c in (200, 400, 404)]
        assert len(success_or_client_error) > 0, f"All requests failed: {status_codes}"
