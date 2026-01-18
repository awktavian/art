"""Audio subsystem — Earcon assets and spatial audio routing.

This module provides:
- AudioAssetStore: Earcon management with CDN and caching
- Unified audio event routing through spatial engine

Usage:
    from kagami.core.audio import get_audio_asset_store, AudioFormat

    store = await get_audio_asset_store()
    path = await store.get_earcon("success", AudioFormat.AAC)

Created: January 12, 2026
"""

from kagami.core.audio.asset_store import (
    TIER_1_EARCONS,
    AudioAssetStore,
    AudioFormat,
    EarconAssetMetadata,
    get_audio_asset_store,
    get_earcon_path,
)

__all__ = [
    "TIER_1_EARCONS",
    "AudioAssetStore",
    "AudioFormat",
    "EarconAssetMetadata",
    "get_audio_asset_store",
    "get_earcon_path",
]
