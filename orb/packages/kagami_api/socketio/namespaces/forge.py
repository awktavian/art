"""Forge Namespace - Socket.IO namespace for Forge generation events.

Uses consolidated idempotency handling from socketio_helpers.

Updated: December 24, 2025 - Consolidated idempotency handling (Socket.IO migration)
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from kagami_api.socketio.namespaces.root import KagamiOSNamespace
from kagami_api.socketio.telemetry import traced_operation

logger = logging.getLogger(__name__)


class ForgeNamespace(KagamiOSNamespace):
    """Namespace for Forge generation events."""

    def __init__(self) -> None:
        super().__init__("/forge")

    async def on_generate(self, sid: str, data: dict[str, Any]) -> None:
        """Handle Forge generation request.

        Requires authentication and idempotency key for mutations.
        Uses consolidated idempotency handling from socketio_helpers.
        """
        if not await self._require_auth(sid):
            return

        with traced_operation("socketio.forge.generate", attributes={"sid": sid}):
            from kagami_api.socketio_helpers import (
                build_error_response,
                extract_idempotency_key,
                handle_ws_idempotency,
            )

            prompt = (data or {}).get("prompt")
            options = (
                (data or {}).get("options", {})
                if isinstance((data or {}).get("options", {}), dict)
                else {}
            )

            try:
                # Use consolidated idempotency handling
                idem_key = extract_idempotency_key(data or {})
                user = self.session_users.get(sid, {})
                user_id = user.get("id", "unknown")

                idem_status, _idem_error = await handle_ws_idempotency(
                    idem_key,
                    user_id,
                    is_mutation=True,  # Forge generation is always a mutation
                )

                if idem_status == "missing":
                    await self.emit(
                        "forge.error",
                        build_error_response(
                            "IDEMPOTENCY_KEY_REQUIRED", "idempotency_key_required"
                        ),
                        room=sid,
                    )
                    return

                if idem_status == "duplicate":
                    await self.emit(
                        "forge.error",
                        build_error_response("DUPLICATE_REQUEST", "duplicate_request"),
                        room=sid,
                    )
                    return

                # Execute forge generation
                from kagami.core.di import try_resolve
                from kagami.core.interfaces import PrivacyProvider
                from kagami.forge.service import (
                    ForgeOperation,
                    ForgeRequest,
                    get_forge_service,
                )

                from kagami_api.forge_room_events import finalize_forge_generation

                quality_mode = str(options.get("quality_mode") or "preview")
                export_formats = options.get("export_formats")
                if not isinstance(export_formats, list) or not export_formats:
                    export_formats = ["gltf"]

                room_id = (data or {}).get("room_id")
                if room_id is not None:
                    room_id = str(room_id).strip() or None

                service = get_forge_service()
                forge_request = ForgeRequest(
                    capability=ForgeOperation.CHARACTER_GENERATION,
                    params={"concept": str(prompt or "").strip()},
                    quality_mode=quality_mode,
                    export_formats=[str(x) for x in export_formats],
                    correlation_id=f"ws-{sid}-{int(datetime.utcnow().timestamp())}",
                    metadata={"source": "socketio", "sid": sid, "idempotency_key": idem_key},
                )
                response = await service.execute(forge_request)
                if not response.success:
                    await self.emit(
                        "forge.error",
                        build_error_response("FORGE_FAILED", response.error or "forge_failed"),
                        room=sid,
                    )
                    return

                result = {
                    **(response.data or {}),
                    "correlation_id": forge_request.correlation_id,
                    "cached": response.cached,
                    "duration_ms": response.duration_ms,
                }
                privacy_provider = try_resolve(PrivacyProvider)
                result = await finalize_forge_generation(
                    result=result,
                    correlation_id=forge_request.correlation_id or "",
                    concept=str(prompt or ""),
                    room_id=room_id,
                    auto_insert=bool(options.get("auto_insert", True)) if room_id else False,
                    privacy_provider=privacy_provider,
                )

                await self.emit(
                    "forge.completed",
                    {"result": result, "status": "success"},
                    room=sid,
                )

            except Exception as e:
                logger.error("Forge generation failed: %s", e)
                await self.emit("forge.error", {"error": str(e), "status": "error"}, room=sid)


__all__ = ["ForgeNamespace"]
