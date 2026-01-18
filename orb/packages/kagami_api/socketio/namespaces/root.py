from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from kagami_api.socketio.namespaces.base import BaseNamespace

logger = logging.getLogger(__name__)


class KagamiOSNamespace(BaseNamespace):
    """Root namespace (/) for Rooms + generic realtime events."""

    async def on_join_room(self, sid: str, data: dict[str, Any]) -> None:
        """Join a room and receive current room_state payload."""
        try:
            room_id = str((data or {}).get("room_id") or "").strip()
            if not room_id:
                return

            await self.enter_room(sid, room_id)

            user_id = (self.session_users.get(sid) or {}).get("id", "anonymous")
            await self.emit(
                "user_joined",
                {"user_id": user_id, "sid": sid, "timestamp": datetime.utcnow().isoformat()},
                room=room_id,
                skip_sid=sid,
            )

            # Send current room state to joiner
            try:
                from kagami_api.rooms.state_service import (
                    get_all_cursors_3d,
                    get_anchors,
                    get_snapshot,
                    is_room_encryption_enabled,
                    upsert_member,
                )

                # Best-effort persist membership for non-Socket.IO readers
                try:
                    await upsert_member(room_id, str(user_id), {"sid": sid, "role": "user"})
                except Exception:
                    pass

                snapshot = await get_snapshot(room_id)
                anchors = await get_anchors(room_id)
                cursors = await get_all_cursors_3d(room_id)
                enc_enabled = False
                try:
                    enc_enabled = bool(await is_room_encryption_enabled(room_id))
                except Exception:
                    enc_enabled = False

                room_members: list[dict[str, Any]] = []
                if self.server:
                    members = (
                        getattr(self.server.manager, "rooms", {}).get("/", {}).get(room_id, set())
                    )
                    for member_sid in members:
                        u = self.session_users.get(member_sid)
                        if u:
                            uid = u.get("id")
                            pos = cursors.get(uid)  # type: ignore[arg-type]
                            room_members.append(
                                {"id": uid, "role": "user", "cursor_position_3d": pos}
                            )

                await self.emit(
                    "room_state",
                    {
                        "room_id": room_id,
                        "seq": snapshot.seq,
                        "users": room_members,
                        "anchors": list(anchors.values()),
                        "anchors_by_id": anchors,
                        "cursors_3d": cursors,
                        "state": snapshot.state,
                        "encryption": {"enabled": enc_enabled, "immutable": enc_enabled},
                        "timestamp": datetime.utcnow().timestamp(),
                    },
                    room=sid,
                )
            except Exception as e:
                logger.error("Error fetching room state for %s: %s", room_id, e)

        except Exception as e:
            logger.error("on_join_room error: %s", e)

    async def on_leave_room(self, sid: str, data: dict[str, Any]) -> None:
        try:
            room_id = str((data or {}).get("room_id") or "").strip()
            if not room_id:
                return

            await self.leave_room(sid, room_id)

            user_id = (self.session_users.get(sid) or {}).get("id", "anonymous")
            await self.emit("user_left", {"user_id": user_id, "sid": sid}, room=room_id)

            try:
                from kagami_api.rooms.state_service import remove_member

                await remove_member(room_id, str(user_id))
            except Exception:
                pass
        except Exception as e:
            logger.error("on_leave_room error: %s", e)

    # -------------------------------------------------------------------------
    # Constellation (devices) — multi-device Ambient OS wiring
    # -------------------------------------------------------------------------

    async def on_device_register(self, sid: str, data: dict[str, Any]) -> None:
        """Register a device with the Constellation coordinator and join its room.

        Expected payload (minimal):
          {
            "device_id": "watch-123",
            "name": "Tim’s Watch",
            "device_type": "wearable" | "phone" | "tablet" | "desktop" | "laptop",
            "capabilities": {...},  # optional
            "set_active": true,     # optional
          }
        """
        if not await self._require_auth(sid):
            return
        try:
            payload = data or {}
            device_id = str(payload.get("device_id") or payload.get("id") or "").strip()
            if not device_id:
                await self.emit(
                    "device.error",
                    {"error": "device_id_required"},
                    room=sid,
                )
                return

            name = str(payload.get("name") or device_id).strip()
            device_type_raw = str(
                payload.get("device_type") or payload.get("type") or "phone"
            ).strip()
            capabilities = payload.get("capabilities")

            # Map to enum (fallback to PHONE)
            from kagami.core.ambient.multi_device_coordinator import (
                DeviceType,
                get_multi_device_coordinator,
            )

            device_type = DeviceType.PHONE
            try:
                device_type = DeviceType(device_type_raw.lower())
            except Exception:
                # Common aliases
                aliases = {
                    "watch": "wearable",
                    "smartwatch": "wearable",
                    "mobile": "phone",
                    "pc": "desktop",
                }
                try:
                    device_type = DeviceType(aliases.get(device_type_raw.lower(), "phone"))
                except Exception:
                    device_type = DeviceType.PHONE

            coordinator = await get_multi_device_coordinator()
            device = coordinator.register_device(
                device_id=device_id,
                name=name,
                device_type=device_type,
                capabilities=capabilities,
            )

            # Join the device-specific room used by coordinator broadcasts
            room_id = f"device_{device_id}"
            await self.enter_room(sid, room_id)

            # Optionally mark as active device
            if bool(payload.get("set_active")):
                try:
                    coordinator.set_active_device(device_id)
                except Exception:
                    pass

            # Attach device_id to session for diagnostics
            try:
                if sid in self.session_users:
                    self.session_users[sid]["device_id"] = device_id
                    self.session_users[sid]["device_type"] = device_type.value
            except Exception:
                pass

            await self.emit(
                "device.registered",
                {
                    "device_id": device_id,
                    "room_id": room_id,
                    "device": {
                        "id": device.id,
                        "name": device.name,
                        "type": device.type.value,
                        "status": device.status.value,
                        "battery_level": device.battery_level,
                        "last_seen": device.last_seen,
                        "location": device.location,
                        "capabilities": device.capabilities,
                    },
                    "shared_state": dict(coordinator.shared_state),
                    "active_device": coordinator.active_device,
                },
                room=sid,
            )
        except Exception as e:
            logger.error("on_device_register error: %s", e, exc_info=True)
            await self.emit(
                "device.error",
                {"error": str(e)},
                room=sid,
            )

    async def on_device_heartbeat(self, sid: str, data: dict[str, Any]) -> None:
        """Heartbeat from a device (updates last_seen/battery/location/capabilities)."""
        if not await self._require_auth(sid):
            return
        try:
            payload = data or {}
            device_id = str(payload.get("device_id") or payload.get("id") or "").strip()
            if not device_id:
                return

            from kagami.core.ambient.multi_device_coordinator import (
                DeviceStatus,
                get_multi_device_coordinator,
            )

            coordinator = await get_multi_device_coordinator()

            status_raw = payload.get("status")
            status: DeviceStatus | None = None
            if isinstance(status_raw, str):
                try:
                    status = DeviceStatus(status_raw.lower())
                except Exception:
                    status = None

            battery = payload.get("battery_level")
            location = payload.get("location")
            capabilities = payload.get("capabilities")

            device = coordinator.heartbeat(
                device_id,
                status=status,
                battery_level=battery if battery is not None else None,
                location=str(location) if location is not None else None,
                capabilities=capabilities,
            )

            if device is None:
                # If device isn't registered yet, ignore (client should register first).
                return

            # Optional: device can declare itself active
            if bool(payload.get("set_active")):
                try:
                    coordinator.set_active_device(device_id)
                except Exception:
                    pass

            await self.emit(
                "device.heartbeat.ack",
                {
                    "device_id": device_id,
                    "active_device": coordinator.active_device,
                    "last_seen": device.last_seen,
                },
                room=sid,
            )
        except Exception as e:
            logger.debug("on_device_heartbeat error: %s", e)

    async def on_device_set_active(self, sid: str, data: dict[str, Any]) -> None:
        """Explicitly set the active device (handoff anchor)."""
        if not await self._require_auth(sid):
            return
        try:
            device_id = str((data or {}).get("device_id") or "").strip()
            if not device_id:
                return

            from kagami.core.ambient.multi_device_coordinator import get_multi_device_coordinator

            coordinator = await get_multi_device_coordinator()
            coordinator.set_active_device(device_id)

            await self.emit(
                "device.active",
                {"active_device": coordinator.active_device, "device_id": device_id},
                room=sid,
            )
        except Exception as e:
            logger.debug("on_device_set_active error: %s", e)

    async def on_device_state_update(self, sid: str, data: dict[str, Any]) -> None:
        """Allow a device to publish a shared-state delta into the constellation.

        Expected payload:
          {"device_id": "...", "delta": {...}}
        """
        if not await self._require_auth(sid):
            return
        try:
            payload = data or {}
            device_id = str(payload.get("device_id") or "").strip()
            delta = payload.get("delta")
            if not device_id or not isinstance(delta, dict):
                return

            from kagami.core.ambient.multi_device_coordinator import get_multi_device_coordinator

            coordinator = await get_multi_device_coordinator()
            await coordinator.sync_state(delta, from_device=device_id)

            await self.emit(
                "device.state_update.ack",
                {"device_id": device_id, "keys": list(delta.keys())[:50]},
                room=sid,
            )
        except Exception as e:
            logger.debug("on_device_state_update error: %s", e)

    async def on_device_request_handoff(self, sid: str, data: dict[str, Any]) -> None:
        """Request a handoff (context transfer) between devices.

        Expected payload:
          {"from_device": "...", "to_device": "...", "context": {...}}
        """
        if not await self._require_auth(sid):
            return
        try:
            payload = data or {}
            from_device = str(payload.get("from_device") or "").strip()
            to_device = str(payload.get("to_device") or "").strip()
            context = payload.get("context") or {}

            if not from_device or not to_device or not isinstance(context, dict):
                return

            from kagami.core.ambient.multi_device_coordinator import get_multi_device_coordinator

            coordinator = await get_multi_device_coordinator()
            ok = await coordinator.request_handoff(from_device, to_device, context)

            await self.emit(
                "device.handoff.ack",
                {"success": bool(ok), "from_device": from_device, "to_device": to_device},
                room=sid,
            )
        except Exception as e:
            logger.debug("on_device_request_handoff error: %s", e)

    async def on_device_get_state(self, sid: str, _data: dict[str, Any] | None = None) -> None:
        """Return current constellation shared state + devices list."""
        if not await self._require_auth(sid):
            return
        try:
            from kagami.core.ambient.multi_device_coordinator import get_multi_device_coordinator

            coordinator = await get_multi_device_coordinator()
            devices = []
            for d in coordinator.devices.values():
                devices.append(
                    {
                        "id": d.id,
                        "name": d.name,
                        "type": d.type.value,
                        "status": d.status.value,
                        "battery_level": d.battery_level,
                        "last_seen": d.last_seen,
                        "location": d.location,
                        "capabilities": d.capabilities,
                    }
                )

            await self.emit(
                "device.state",
                {
                    "active_device": coordinator.active_device,
                    "devices": devices,
                    "shared_state": dict(coordinator.shared_state),
                    "stats": coordinator.get_stats(),
                },
                room=sid,
            )
        except Exception as e:
            logger.debug("on_device_get_state error: %s", e)

    async def on_update_cursor_3d(self, sid: str, data: dict[str, Any]) -> None:
        """High-frequency cursor updates (broadcast + best-effort persistence)."""
        try:
            room_id = str((data or {}).get("room_id") or "").strip()
            position = (data or {}).get("position")
            if not room_id or not isinstance(position, list) or len(position) != 3:
                return

            user_id = (self.session_users.get(sid) or {}).get("id")
            if not user_id:
                return

            await self.emit(
                "user_cursor_3d",
                {"user_id": user_id, "position": position},
                room=room_id,
                skip_sid=sid,
            )

            try:
                from kagami_api.rooms.state_service import update_cursor_3d

                await update_cursor_3d(room_id, str(user_id), position)
            except Exception:
                pass
        except Exception as e:
            logger.debug("on_update_cursor_3d error: %s", e)

    async def on_apply_room_ops(self, sid: str, data: dict[str, Any]) -> None:
        """Apply CRDT room operations and broadcast replayable deltas.

        Expected payload:
          {
            "room_id": "room-123",
            "ops": [ {type, path, value, ...}, ... ],
            "include_snapshot": false
          }
        """
        if not await self._require_auth(sid):
            return
        try:
            room_id = str((data or {}).get("room_id") or "").strip()
            ops = (data or {}).get("ops") or (data or {}).get("operations") or []
            include_snapshot = bool((data or {}).get("include_snapshot", False))

            if not room_id:
                await self.emit(
                    "room.ops.error",
                    {"error": "room_id_required"},
                    room=sid,
                )
                return
            if not isinstance(ops, list) or not ops:
                await self.emit(
                    "room.ops.error",
                    {"room_id": room_id, "error": "ops_required"},
                    room=sid,
                )
                return

            # Require caller to already be in the room.
            try:
                if room_id not in set(self.rooms(sid)):
                    await self.emit(
                        "room.ops.error",
                        {"room_id": room_id, "error": "not_in_room"},
                        room=sid,
                    )
                    return
            except Exception:
                pass

            user_id = (self.session_users.get(sid) or {}).get("id") or "unknown"

            from kagami_api.rooms.state_service import apply_crdt_operations

            snap, applied = await apply_crdt_operations(
                room_id,
                ops,
                default_client_id=str(user_id),
            )

            # Broadcast deltas to room in parallel (skip sender)
            if applied:
                await asyncio.gather(
                    *[
                        self.emit(
                            "room.delta",
                            {
                                "room_id": room_id,
                                "seq": item.get("seq"),
                                "delta": item.get("delta"),
                            },
                            room=room_id,
                            skip_sid=sid,
                        )
                        for item in applied
                    ],
                    return_exceptions=True,
                )

            # ACK to sender with applied seqs
            ack: dict[str, Any] = {
                "room_id": room_id,
                "applied": [{"seq": x.get("seq")} for x in applied],
                "current_seq": getattr(snap, "seq", 0),
            }
            if include_snapshot:
                ack["state"] = getattr(snap, "state", {})
            await self.emit("room.ops.applied", ack, room=sid)
        except Exception as e:
            logger.error("on_apply_room_ops error: %s", e)
            await self.emit("room.ops.error", {"error": str(e)}, room=sid)

    async def on_enable_room_encryption(self, sid: str, data: dict[str, Any]) -> None:
        """Irreversibly enable encryption for a room (E2E UX action).

        Expected payload: {"room_id": "...", "confirm": true}
        """
        if not await self._require_auth(sid):
            return

        room_id = str((data or {}).get("room_id") or "").strip()
        confirm = bool((data or {}).get("confirm"))
        if not room_id:
            await self.emit(
                "room.encryption.error",
                {"room_id": room_id, "error": "room_id_required"},
                room=sid,
            )
            return
        if not confirm:
            await self.emit(
                "room.encryption.error",
                {
                    "room_id": room_id,
                    "error": "confirmation_required",
                    "message": "Enabling room encryption is irreversible. Resend with confirm=true.",
                },
                room=sid,
            )
            return

        # Require the caller to already be in the room (basic UX + safety)
        try:
            if room_id not in set(self.rooms(sid)):
                await self.emit(
                    "room.encryption.error",
                    {"room_id": room_id, "error": "not_in_room"},
                    room=sid,
                )
                return
        except Exception:
            pass

        try:
            from kagami_api.rooms.state_service import (
                get_crdt_meta,
                get_snapshot,
                persist_crdt_meta,
                persist_snapshot,
                set_room_encryption_enabled,
            )

            # 1) Latch room encryption (validates provider)
            await set_room_encryption_enabled(room_id, True)

            # 2) Immediately re-persist snapshot so the room becomes encrypted-at-rest now
            snap = await get_snapshot(room_id)
            await persist_snapshot(room_id, dict(snap.state or {}))
            # 2b) Re-persist CRDT metadata so it becomes encrypted-at-rest immediately
            try:
                meta = await get_crdt_meta(room_id)
                if meta:
                    await persist_crdt_meta(room_id, dict(meta))
            except Exception:
                pass

            # 3) Notify room members
            await self.emit(
                "room.encryption.enabled",
                {
                    "room_id": room_id,
                    "enabled": True,
                    "immutable": True,
                    "timestamp": datetime.utcnow().isoformat(),
                },
                room=room_id,
            )
            await self.emit(
                "room.encryption.ack",
                {"room_id": room_id, "enabled": True, "immutable": True},
                room=sid,
            )
        except Exception as e:
            await self.emit(
                "room.encryption.error",
                {"room_id": room_id, "error": str(e)},
                room=sid,
            )


__all__ = ["KagamiOSNamespace"]
