from __future__ import annotations
from typing import Any

import pytest

from kagami.forge.service import ForgeOperation, ForgeRequest, ForgeResponse, ForgeService


@pytest.mark.asyncio
async def test_forge_service_genesis_video_calls_creator_api(monkeypatch) -> None:
    service = ForgeService(matrix=None)

    async def mock_generate(payload: Any) -> Dict[str, Any]:
        assert payload["output_dir"] == "/tmp/out"
        return {"output_dir": "/tmp/out", "spec": {"name": "x"}}

    monkeypatch.setattr(
        "kagami.forge.creator_api.generate_genesis_video",
        mock_generate,
    )

    req = ForgeRequest(capability=ForgeOperation.GENESIS_VIDEO, params={"output_dir": "/tmp/out"})
    resp = await service.execute(req)

    assert isinstance(resp, ForgeResponse)
    assert resp.success is True
    assert resp.capability == "genesis.video"
    assert resp.data["output_dir"] == "/tmp/out"


@pytest.mark.asyncio
async def test_forge_service_genesis_video_invalid_spec() -> Any:
    service = ForgeService(matrix=None)
    req = ForgeRequest(capability=ForgeOperation.GENESIS_VIDEO, params={"spec": "not_a_dict"})
    resp = await service.execute(req)
    assert resp.success is False
    assert resp.error_code == "invalid_spec"
