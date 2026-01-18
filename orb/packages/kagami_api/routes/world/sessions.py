from __future__ import annotations

"Session management for world composition."
import json
import time as _time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from kagami.core.boot_mode import is_test_mode
from kagami.core.caching.redis import RedisClientFactory
from kagami.core.safety.cbf_integration import check_cbf_for_operation
from kagami.forge.modules.world.unrealzoo_adapter import (
    ensure_unrealzoo_assets,
    get_unrealzoo_space,
)

from kagami_api.rbac import Permission, require_permission

from .models import SessionStartRequest, SessionStartResponse


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(tags=["rooms"])

    @router.post(
        "/session/start",
        dependencies=[Depends(require_permission(Permission.TOOL_EXECUTE))],  # type: ignore[func-returns-value]
    )
    async def start_session(request: Request, body: SessionStartRequest) -> SessionStartResponse:
        """Initialize session with world and optional character."""
        # CBF safety check
        cbf_result = await check_cbf_for_operation(
            operation="api.world.session.start",
            action="start",
            target="session",
            params=body.model_dump(),
            metadata={"endpoint": "/api/world/session/start", "world_id": body.world_id},
            source="api",
        )
        if not cbf_result.safe:
            raise HTTPException(
                status_code=403,
                detail=f"Safety check failed: {cbf_result.reason}",
            )

        # Import metrics for observability (optional)
        world_route_duration: Any = None
        try:
            from kagami.observability.metrics import WORLD_ROUTE_DURATION

            world_route_duration = WORLD_ROUTE_DURATION
        except Exception:
            pass  # Metrics are optional, silent failure is acceptable

        _t0 = _time.time()
        redis = RedisClientFactory.get_client(
            purpose="default", async_mode=True, decode_responses=True
        )
        wjson = await redis.hget(f"kagami:worlds:data:{body.world_id}", "json")
        provider = body.provider
        provider_meta: dict[str, Any] | None = None
        world_dir: str | None = None

        if not wjson:
            # In test mode, allow using current working directory as fallback
            if is_test_mode():
                world_dir = str(Path.cwd())
            else:
                raise HTTPException(status_code=404, detail="World not found") from None
        else:
            world_dir = json.loads(wjson).get("world_url")
        if body.use_unrealzoo:
            assets_root = ensure_unrealzoo_assets()
            space = get_unrealzoo_space(body.world_id, assets_root=assets_root)
            if space is None:
                raise HTTPException(status_code=404, detail="UnrealZoo space not found")
            world_dir = space["path"]
            provider = "unrealzoo"
            provider_meta = {
                "scene_graph": space.get("scene_graph"),
                "provider": provider,
                "space_id": space.get("id"),
            }
        if not world_dir:
            raise HTTPException(status_code=400, detail="World missing asset path")
        from kagami.core.config import get_bool_config as _get_bool

        physics_enabled = bool(_get_bool("KAGAMI_ROOM_ENABLE_PHYSICS", False))
        physics = None
        if physics_enabled:
            try:
                from kagami.forge.modules.genesis_physics_wrapper import (
                    GenesisPhysicsWrapper,
                )

                physics = GenesisPhysicsWrapper()
                await physics.create_physics_scene(  # type: ignore[call-arg]
                    scene_type=body.scene_type,
                    ambient_light=body.ambient_light,
                    background_color=body.background_color,
                    visual_quality=body.visual_quality,
                )
                winfo = await physics.import_world_environment(str(world_dir))  # type: ignore[attr-defined]
                if not winfo.get("success"):
                    raise HTTPException(status_code=500, detail="Failed to import world")
            except HTTPException:
                raise
            except Exception:
                physics = None
        if physics is not None and body.character_id:
            cjson = await redis.hget(f"kagami:characters:data:{body.character_id}", "json")
            if cjson:
                crec = json.loads(cjson)
                character_mesh = crec.get("asset_url")
                rigging_data = (crec.get("metadata") or {}).get("articulated")
                await physics.add_character_to_scene(  # type: ignore[attr-defined]
                    character_mesh_path=character_mesh, rigging_data=rigging_data
                )
        session_id = f"session_{Path(str(world_dir)).name}"
        session_payload = {
            "world_id": body.world_id,
            "character_id": body.character_id or "",
            "object_ids": json.dumps([]),
            "world_dir": str(world_dir),
        }
        if provider:
            session_payload["provider"] = provider
        if provider_meta:
            session_payload["world_generation"] = json.dumps(provider_meta)
        await redis.hset(f"kagami:sessions:{session_id}", mapping=session_payload)
        room_id = f"world:{body.world_id}"
        response = SessionStartResponse(session_id=session_id, room_id=room_id, provider=provider)

        # Record metrics if available
        try:
            if world_route_duration is not None:
                world_route_duration.labels(route="/api/rooms/session/start").observe(
                    max(0.0, _time.time() - _t0)
                )
        except Exception:
            pass  # Metrics are optional, silent failure is acceptable

        return response

    return router
