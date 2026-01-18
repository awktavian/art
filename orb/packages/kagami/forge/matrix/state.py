"""Forge state management."""

import logging
from dataclasses import fields as dataclass_fields
from typing import Any

from kagami.forge.schema import CharacterRequest

logger = logging.getLogger(__name__)


def coerce_request(request_like: Any) -> CharacterRequest:
    """Coerce various legacy/request-like inputs into CharacterRequest."""
    if isinstance(request_like, CharacterRequest):
        return request_like
    data: dict[str, Any] = {}
    try:
        if isinstance(request_like, dict):
            data = dict(request_like)
        else:
            data = {k: getattr(request_like, k) for k in dir(request_like) if not k.startswith("_")}
    except Exception:
        data = {}
    if "prompt" in data and "concept" not in data:
        data["concept"] = data.pop("prompt")
    export_formats = data.get("export_formats")
    if export_formats is not None and (not isinstance(export_formats, list)):
        export_formats = [export_formats]
    data["export_formats"] = export_formats
    metadata = data.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {} if metadata is None else {"value": metadata}
    data["metadata"] = metadata
    try:
        if "technical_constraints" in data:
            meta = data.get("metadata")
            if not isinstance(meta, dict):
                meta = {}
            meta["technical_constraints"] = data.pop("technical_constraints")
            data["metadata"] = meta
    except (KeyError, TypeError, AttributeError) as e:
        logger.debug(f"Could not migrate technical_constraints: {e}")
    valid_field_names = {f.name for f in dataclass_fields(CharacterRequest)}
    filtered = {k: v for k, v in data.items() if k in valid_field_names}
    try:
        return CharacterRequest(**filtered)
    except Exception:
        return CharacterRequest(concept=str(data.get("concept") or "character"))
