
from __future__ import annotations

# Consolidated markers


import pytest

# Consolidated markers
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.tier_integration,
]
from httpx import ASGITransport, AsyncClient

from kagami_api import create_app



@pytest.mark.contract
async def test_metrics_endpoint_single_surface():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Canonical metrics surface exists
        r = await client.get("/metrics")
        assert r.status_code == 200
        text = r.text
        # At minimum, some kagami_ metrics should be present
        assert "kagami_" in text

        # No duplicate under /health/metrics
        r = await client.get("/health/metrics")
        assert r.status_code in (404, 405)
