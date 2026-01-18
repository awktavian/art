from __future__ import annotations

from typing import Any

import pytest

pytestmark = [pytest.mark.tier_integration, pytest.mark.asyncio]


async def test_world_graph_routes_exist(async_client: Any) -> None:
    """Ensure room/worldgraph surfaces are discoverable via OpenAPI."""

    response = await async_client.get("/openapi.json")
    assert response.status_code == 200

    paths = response.json().get("paths", {})
    worldgraph_paths = {path for path in paths if "worldgraph" in path}
    if worldgraph_paths:
        assert all(path.startswith("/api/worldgraph") for path in worldgraph_paths)
        return

    # Fallback: ensure at least the /api/rooms surface is published
    rooms_paths = [path for path in paths if path.startswith("/api/rooms")]
    assert rooms_paths, "room/world endpoints missing from OpenAPI"
