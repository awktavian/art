from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, cast

logger = logging.getLogger(__name__)

_DEFAULT_SPACES = [
    {
        "id": "unrealzoo_forest_arena",
        "name": "Forest Arena",
        "description": "Dense forest with clearings for navigation benchmarks.",
    },
    {
        "id": "unrealzoo_desert_ruins",
        "name": "Desert Ruins",
        "description": "Open desert temple for visibility + long-range tasks.",
    },
    {
        "id": "unrealzoo_harbor_night",
        "name": "Harbor (Night)",
        "description": "Complex lighting scenario for perception tests.",
    },
]


def ensure_unrealzoo_assets(root: str | None = None) -> Path:
    """Ensure local cache for UnrealZoo benchmark assets."""

    base = (
        root or os.getenv("UNREALZOO_ASSETS_PATH") or os.path.join(Path.home(), ".kagami_unrealzoo")
    )
    root_path = Path(base)
    root_path.mkdir(parents=True, exist_ok=True)

    manifest = root_path / "spaces.json"
    if not manifest.exists():
        spaces = []
        for space in _DEFAULT_SPACES:
            space_dir = root_path / space["id"]
            space_dir.mkdir(parents=True, exist_ok=True)
            scene_graph = space_dir / "scene_graph.json"
            scene_graph.write_text(
                json.dumps(
                    {
                        "space_id": space["id"],
                        "nodes": [],
                        "relations": [],
                    },
                    indent=2,
                )
            )
            spaces.append(
                {
                    **space,
                    "path": str(space_dir),
                    "scene_graph": str(scene_graph),
                }
            )
        manifest.write_text(json.dumps(spaces, indent=2))

    return root_path


def list_unrealzoo_spaces(root: Path | None = None) -> list[dict[str, Any]]:
    root_path = ensure_unrealzoo_assets(str(root) if root else None)
    manifest = root_path / "spaces.json"
    try:
        return cast(list[dict[str, Any]], json.loads(manifest.read_text()))
    except Exception as exc:
        logger.warning("Failed to read UnrealZoo manifest: %s", exc)
        return []


def get_unrealzoo_space(
    space_id: str | None,
    assets_root: Path,
) -> dict[str, Any] | None:
    spaces = list_unrealzoo_spaces(assets_root)
    if space_id:
        for space in spaces:
            if space.get("id") == space_id:
                return space
    return spaces[0] if spaces else None


__all__ = ["ensure_unrealzoo_assets", "get_unrealzoo_space", "list_unrealzoo_spaces"]
