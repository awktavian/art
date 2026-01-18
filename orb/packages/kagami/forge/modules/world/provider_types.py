from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class WorldGenerationResult:
    """Standardized result for world generation providers."""

    success: bool
    panorama_path: str | None
    world_dir: str | None
    error: str | None = None
    metadata: dict[str, Any] | None = None
    provider: str | None = None
