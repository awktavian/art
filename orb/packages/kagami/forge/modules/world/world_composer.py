from __future__ import annotations

"""World Composer - brings characters to life inside generated worlds.

Responsibilities:
- Create a physics scene
- Import HunyuanWorld-generated environment assets
- Export the character to an on-disk mesh format (GLB) if needed
- Add the character entity to the scene
- Simulate motion forces to make the scene feel alive
- Optionally export a USD recording of the session
"""
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kagami.core.di.container import try_resolve
from kagami.core.interfaces import EventBroadcaster, RealtimeBroadcaster

# Avoid importing heavy physics wrapper at import time to keep tests/light envs stable


logger = logging.getLogger(__name__)


@dataclass
class WorldComposeOptions:
    scene_type: str = "character_studio"
    duration: float = 6.0
    fps: int = 60
    motion_type: str | None = "walk"  # walk, jump, spin, push
    export_usd: bool = True
    export_basename: str = "session"
    provider_metadata: dict[str, Any] | None = None


@dataclass
class WorldComposeResult:
    success: bool
    session_id: str
    world_assets: list[str]
    character_id: str | None
    export_path: str | None
    performance: dict[str, Any]
    error: str | None = None


class WorldComposer:
    def __init__(
        self,
        physics: Any | None = None,
        export_manager: Any | None = None,
    ) -> None:
        # Physics is optional for UI-only helpers
        self.physics = physics
        self.export_manager = export_manager

    async def compose(
        self,
        *,
        character_data: dict[str, Any],
        world_dir: str,
        options: WorldComposeOptions | None = None,
    ) -> WorldComposeResult:
        """Compose a world with character and physics simulation."""
        if not self.physics:
            raise RuntimeError("Physics engine required for world composition")

        opts = options or WorldComposeOptions()
        provider_metadata = opts.provider_metadata or (character_data.get("metadata") or {}).get(
            "world_generation"
        )

        # 1) Create physics scene
        await self.physics.create_physics_scene(scene_type=opts.scene_type)

        # 2) Import world assets
        world_import = await self.physics.import_world_environment(world_dir)
        if not world_import.get("success"):
            raise RuntimeError(f"World import failed: {world_import.get('error')}")
        loaded_assets = world_import.get("assets", [])

        # 3) Resolve and add character
        mesh_path = await self._resolve_character_mesh_path(character_data)
        if not mesh_path:
            raise RuntimeError("Character mesh not available. Ensure exportable mesh data.")
        rigging_data = self._extract_rigging_data(character_data)
        character_id = await self.physics.add_character_to_scene(
            mesh_path, rigging_data=rigging_data
        )

        # 4) Simulate motion
        sim = await self.physics.simulate_character_motion(
            motion_type=opts.motion_type, duration=opts.duration, capture_rate=opts.fps
        )

        # 5) Broadcast scene snapshot (best-effort)
        await self._broadcast_scene_snapshot(sim, world_dir, provider_metadata)

        # 6) Export session if requested
        export_path = await self._export_session(opts, world_dir) if opts.export_usd else None

        # 7) Build performance metrics
        perf = {"physics": self.physics.get_performance_metrics(), "sim": sim}
        if provider_metadata:
            perf["provider_metadata"] = provider_metadata

        # 8) Write session manifest
        self._write_manifest(
            world_dir,
            opts,
            loaded_assets,
            character_id,
            export_path,
            perf,
            provider_metadata,
            character_data,
        )

        return WorldComposeResult(
            success=True,
            session_id=f"session_{Path(world_dir).name}",
            world_assets=loaded_assets,
            character_id=character_id,
            export_path=export_path,
            performance=perf,
        )

    def _extract_rigging_data(self, character_data: dict[str, Any]) -> dict[str, Any] | None:
        """Extract rigging data from character metadata."""
        art = character_data.get("metadata", {}).get("articulated", {})
        if isinstance(art, dict):
            urdf_path = art.get("urdf_path")
            mjcf_path = art.get("mjcf_path")
            if urdf_path or mjcf_path:
                return {"urdf_path": urdf_path, "mjcf_path": mjcf_path}
        return None

    async def _broadcast_scene_snapshot(
        self, sim: dict[str, Any], world_dir: str, provider_metadata: dict[str, Any] | None
    ) -> None:
        """Broadcast scene graph snapshot (best-effort)."""
        try:
            broadcaster = try_resolve(EventBroadcaster)
            realtime = try_resolve(RealtimeBroadcaster)
            if (
                (not broadcaster and not realtime)
                or not isinstance(sim, dict)
                or not sim.get("success")
            ):
                return

            snapshot = sim.get("snapshot") or {}
            room_id = f"world:{Path(world_dir).name}"

            payload = {
                "type": "scene_graph",
                "room_id": room_id,
                "graph": {
                    "nodes": snapshot.get("entities", []),
                    "relations": [],
                    "timestamp": snapshot.get("timestamp", 0.0),
                },
            }
            # Room-scoped: do not leak scene graphs globally.
            if realtime:
                await realtime.emit("scene_graph", payload, room=room_id, namespace="/")
            elif broadcaster:
                safe_payload = dict(payload)
                safe_payload.pop("room_id", None)
                await broadcaster.broadcast("scene_graph", safe_payload)

            if provider_metadata and provider_metadata.get("scene_graph"):
                scene_path = Path(str(provider_metadata["scene_graph"]))
                if scene_path.exists():
                    provider_graph = json.loads(scene_path.read_text())
                    provider_payload = {
                        "type": "scene_graph",
                        "room_id": room_id,
                        "provider": provider_metadata.get("provider"),
                        "graph": provider_graph,
                    }
                    if realtime:
                        await realtime.emit(
                            "scene_graph", provider_payload, room=room_id, namespace="/"
                        )
                    elif broadcaster:
                        safe_payload = dict(provider_payload)
                        safe_payload.pop("room_id", None)
                        await broadcaster.broadcast("scene_graph", safe_payload)
        except Exception as exc:
            logger.debug("Scene graph broadcast skipped: %s", exc)

    async def _export_session(self, opts: WorldComposeOptions, world_dir: str) -> str:
        """Export simulation to USD format."""
        out_dir = Path(world_dir) / "sessions"
        out_dir.mkdir(parents=True, exist_ok=True)
        export_base = out_dir / opts.export_basename

        exp = await self.physics.export_simulation(str(export_base), format="usd")  # type: ignore[union-attr]
        if not exp.get("success"):
            raise RuntimeError(f"Simulation export failed: {exp.get('error')}")
        return f"{export_base}.usd"

    def _write_manifest(
        self,
        world_dir: str,
        opts: WorldComposeOptions,
        loaded_assets: list[Any],
        character_id: str | None,
        export_path: str | None,
        perf: dict[str, Any],
        provider_metadata: dict[str, Any] | None,
        character_data: dict[str, Any],
    ) -> None:
        """Write session manifest for downstream consumers."""
        try:
            manifest = {
                "world_dir": world_dir,
                "world_assets": loaded_assets,
                "character_id": character_id,
                "export_path": export_path,
                "performance": perf,
                "provider_metadata": provider_metadata,
                "panorama_path": character_data.get("metadata", {})
                .get("world", {})
                .get("panorama_path"),
            }
            manifest_path = Path(world_dir) / "sessions" / f"{opts.export_basename}.manifest.json"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            with open(manifest_path, "w") as f:
                json.dump(manifest, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to write world session manifest: {e}")

    async def _resolve_character_mesh_path(self, character_data: dict[str, Any]) -> str | None:
        # If character_data already references a mesh file
        meta = character_data.get("metadata", {})
        export_data = meta.get("export_data", {})
        if isinstance(export_data, dict):
            path = export_data.get("glb") or export_data.get("gltf") or export_data.get("obj")
            if path and os.path.exists(str(path)):
                return str(path)

        # Try ExportManager if available
        if self.export_manager is None:
            return None
        try:
            result = None
            # Export to GLB for Genesis import
            result = await self.export_manager.export(character_data, format="glb")
            file_path = getattr(result, "file_path", None) if result is not None else None
            if file_path and os.path.exists(file_path):
                # Mirror into metadata for reuse
                meta.setdefault("export_data", {})
                meta["export_data"]["glb"] = file_path
                return dict(file_path) if isinstance(file_path, dict) else {}  # type: ignore[return-value]
        except Exception as e:
            logger.error(f"Character export failed: {e}")
            return None
        return None
