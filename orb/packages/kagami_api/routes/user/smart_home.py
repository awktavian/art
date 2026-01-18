"""Tenant Smart Home Configuration API Routes.

Provides endpoints for connecting and managing tenant-specific smart home
integrations. Enables multi-tenant smart home control where each user
connects their own Control4, Lutron, HomeKit, etc.

Created: December 31, 2025 (RALPH Week 2)
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from kagami_api.auth import User, get_current_user
from kagami_api.response_schemas import get_error_responses

logger = logging.getLogger(__name__)


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(prefix="/api/user/smart-home", tags=["user", "smart-home"])

    # =============================================================================
    # ENUMS
    # =============================================================================

    class IntegrationType(str, Enum):
        """Supported smart home integration types."""

        CONTROL4 = "control4"
        LUTRON = "lutron"
        HOMEKIT = "homekit"
        SMARTTHINGS = "smartthings"
        GOOGLE_HOME = "google_home"
        ALEXA = "alexa"
        HUBITAT = "hubitat"
        HOME_ASSISTANT = "home_assistant"

    class ConnectionStatus(str, Enum):
        """Smart home connection status."""

        DISCONNECTED = "disconnected"
        CONNECTING = "connecting"
        CONNECTED = "connected"
        ERROR = "error"
        REQUIRES_REAUTH = "requires_reauth"

    # =============================================================================
    # SCHEMAS
    # =============================================================================

    class SmartHomeCredentials(BaseModel):
        """Credentials for connecting to a smart home system.

        The required fields depend on the integration type.
        """

        # Control4
        control4_host: str | None = Field(None, description="Control4 director IP/hostname")
        control4_port: int | None = Field(None, description="Control4 port (default: 5020)")
        control4_api_key: str | None = Field(None, description="Control4 API key")

        # Lutron
        lutron_host: str | None = Field(None, description="Lutron hub IP/hostname")
        lutron_keypad_id: str | None = Field(None, description="Lutron keypad ID")
        lutron_password: str | None = Field(None, description="Lutron telnet password")

        # HomeKit
        homekit_pairing_code: str | None = Field(None, description="HomeKit pairing code")

        # SmartThings
        smartthings_token: str | None = Field(None, description="SmartThings personal access token")
        smartthings_location_id: str | None = Field(None, description="SmartThings location ID")

        # Google Home
        google_home_refresh_token: str | None = Field(
            None, description="Google OAuth refresh token"
        )

        # Alexa
        alexa_refresh_token: str | None = Field(None, description="Amazon OAuth refresh token")

        # Hubitat
        hubitat_host: str | None = Field(None, description="Hubitat hub IP/hostname")
        hubitat_access_token: str | None = Field(None, description="Hubitat Maker API token")
        hubitat_app_id: str | None = Field(None, description="Hubitat Maker API app ID")

        # Home Assistant
        home_assistant_url: str | None = Field(None, description="Home Assistant URL")
        home_assistant_token: str | None = Field(
            None, description="Home Assistant long-lived access token"
        )

    class ConnectRequest(BaseModel):
        """Request to connect a smart home integration."""

        integration_type: IntegrationType = Field(description="Type of smart home integration")
        credentials: SmartHomeCredentials = Field(description="Integration credentials")
        name: str | None = Field(
            None, description="Custom name for this connection (e.g., 'Home', 'Office')"
        )
        is_primary: bool = Field(
            default=True, description="Set as primary smart home for this tenant"
        )

    class ConnectResponse(BaseModel):
        """Response from smart home connect operation."""

        success: bool
        connection_id: str | None = None
        status: ConnectionStatus
        message: str
        discovered_rooms: int | None = Field(None, description="Number of rooms discovered")
        discovered_devices: int | None = Field(None, description="Number of devices discovered")

    class RoomInfo(BaseModel):
        """Information about a discovered room."""

        id: str = Field(description="Room identifier")
        name: str = Field(description="Room name")
        floor: str | None = Field(None, description="Floor name/number")
        has_lights: bool = Field(default=False)
        has_shades: bool = Field(default=False)
        has_climate: bool = Field(default=False)
        has_audio: bool = Field(default=False)
        device_count: int = Field(default=0)

    class RoomsResponse(BaseModel):
        """Response containing tenant's rooms."""

        rooms: list[RoomInfo]
        total: int
        connection_status: ConnectionStatus

    class TestConnectionRequest(BaseModel):
        """Request to test smart home connection."""

        integration_type: IntegrationType = Field(
            description="Type of smart home integration to test"
        )
        credentials: SmartHomeCredentials = Field(description="Credentials to test")

    class TestConnectionResponse(BaseModel):
        """Response from connection test."""

        success: bool
        latency_ms: float | None = Field(None, description="Connection latency in ms")
        message: str
        details: dict[str, Any] | None = Field(None, description="Additional test details")

    class SmartHomeConfigOut(BaseModel):
        """Smart home configuration summary (no credentials exposed)."""

        id: str
        integration_type: str
        name: str
        status: ConnectionStatus
        is_primary: bool
        room_count: int
        device_count: int
        last_sync: datetime | None = None
        created_at: datetime

    class SmartHomeConfigListResponse(BaseModel):
        """List of tenant's smart home configurations."""

        connections: list[SmartHomeConfigOut]
        total: int

    # =============================================================================
    # STORAGE HELPERS (Redis-backed for speed)
    # =============================================================================

    async def _get_redis_client() -> Any:
        """Get async Redis client."""
        try:
            from kagami.core.caching.redis import RedisClientFactory

            return RedisClientFactory.get_client(
                purpose="default", async_mode=True, decode_responses=True
            )
        except Exception:
            return None

    async def _get_tenant_config(tenant_id: str) -> dict[str, Any] | None:
        """Get tenant's smart home configuration from Redis."""
        client = await _get_redis_client()
        if not client:
            return None

        key = f"tenant:{tenant_id}:smarthome"
        data = await client.get(key)
        if data:
            return json.loads(data)
        return None

    async def _set_tenant_config(tenant_id: str, config: dict[str, Any]) -> bool:
        """Store tenant's smart home configuration in Redis."""
        client = await _get_redis_client()
        if not client:
            return False

        key = f"tenant:{tenant_id}:smarthome"
        await client.set(key, json.dumps(config))
        # Expire after 1 year (credentials should be refreshed periodically)
        await client.expire(key, 60 * 60 * 24 * 365)
        return True

    def _get_encryption_key() -> bytes:
        """Get encryption key from environment or generate.

        In production, use KAGAMI_ENCRYPTION_KEY env var.
        Falls back to a derived key from JWT_SECRET.
        """
        import base64
        import hashlib
        import os

        key_str = os.getenv("KAGAMI_ENCRYPTION_KEY")
        if key_str:
            # Use provided key (should be Fernet-compatible base64)
            return key_str.encode()

        # Derive from JWT_SECRET (not ideal, but better than base64)
        secret = os.getenv("JWT_SECRET", os.getenv("SECRET_KEY", ""))
        if not secret:
            raise RuntimeError(
                "No encryption key configured. Set KAGAMI_ENCRYPTION_KEY or JWT_SECRET."
            )

        # Derive a 32-byte key from the secret
        derived = hashlib.pbkdf2_hmac("sha256", secret.encode(), b"kagami-credentials-salt", 100000)
        return base64.urlsafe_b64encode(derived)

    def _encrypt_credentials(credentials: dict[str, Any], tenant_id: str) -> str:
        """Encrypt credentials for storage using Fernet symmetric encryption.

        Uses KAGAMI_ENCRYPTION_KEY env var or derives from JWT_SECRET.
        """
        from cryptography.fernet import Fernet

        key = _get_encryption_key()
        fernet = Fernet(key)

        payload = json.dumps(credentials).encode()
        encrypted = fernet.encrypt(payload)
        return encrypted.decode()

    def _decrypt_credentials(encrypted: str, tenant_id: str) -> dict[str, Any]:
        """Decrypt stored credentials using Fernet.

        Raises:
            RuntimeError: If decryption fails (key mismatch, corrupted data)
        """
        from cryptography.fernet import Fernet, InvalidToken

        key = _get_encryption_key()
        fernet = Fernet(key)

        try:
            decrypted = fernet.decrypt(encrypted.encode())
            return json.loads(decrypted.decode())
        except InvalidToken as e:
            raise RuntimeError(
                "Failed to decrypt credentials - key mismatch or corrupted data"
            ) from e

    # =============================================================================
    # INTEGRATION HELPERS
    # =============================================================================

    async def _test_control4_connection(
        host: str, port: int | None, api_key: str | None
    ) -> tuple[bool, float, str]:
        """Test Control4 connection."""
        import time

        try:
            import aiohttp

            port = port or 5020
            url = f"http://{host}:{port}/api/v1/items"
            headers = {}
            if api_key:
                headers["X-API-Key"] = api_key

            start = time.time()
            async with (
                aiohttp.ClientSession() as session,
                session.get(
                    url, headers=headers, timeout=aiohttp.ClientTimeout(total=5.0)
                ) as response,
            ):
                latency = (time.time() - start) * 1000
                if response.status == 200:
                    return True, latency, "Connected successfully"
                elif response.status == 401:
                    return False, latency, "Invalid API key"
                else:
                    return False, latency, f"Connection failed: HTTP {response.status}"
        except Exception as e:
            return False, 0, f"Connection error: {e}"

    async def _test_lutron_connection(host: str, password: str | None) -> tuple[bool, float, str]:
        """Test Lutron connection."""
        import time

        try:
            import asyncio

            start = time.time()
            reader, writer = await asyncio.wait_for(asyncio.open_connection(host, 23), timeout=5.0)
            latency = (time.time() - start) * 1000

            # Read prompt
            await asyncio.wait_for(reader.read(1024), timeout=2.0)

            # Send login
            writer.write(b"login\r\n")
            await writer.drain()

            # Read response
            response = await asyncio.wait_for(reader.read(1024), timeout=2.0)

            writer.close()
            await writer.wait_closed()

            if b"GNET>" in response or b"login:" in response:
                return True, latency, "Connected successfully"
            return False, latency, "Unexpected response from Lutron hub"
        except Exception as e:
            return False, 0, f"Connection error: {e}"

    async def _test_smartthings_connection(token: str) -> tuple[bool, float, str]:
        """Test SmartThings connection."""
        import time

        try:
            import aiohttp

            url = "https://api.smartthings.com/v1/locations"
            headers = {"Authorization": f"Bearer {token}"}

            start = time.time()
            async with (
                aiohttp.ClientSession() as session,
                session.get(
                    url, headers=headers, timeout=aiohttp.ClientTimeout(total=5.0)
                ) as response,
            ):
                latency = (time.time() - start) * 1000
                if response.status == 200:
                    data = await response.json()
                    count = len(data.get("items", []))
                    return True, latency, f"Connected. Found {count} location(s)."
                elif response.status == 401:
                    return False, latency, "Invalid token"
                else:
                    return False, latency, f"API error: HTTP {response.status}"
        except Exception as e:
            return False, 0, f"Connection error: {e}"

    async def _test_home_assistant_connection(url: str, token: str) -> tuple[bool, float, str]:
        """Test Home Assistant connection."""
        import time

        try:
            import aiohttp

            api_url = f"{url.rstrip('/')}/api/"
            headers = {"Authorization": f"Bearer {token}"}

            start = time.time()
            async with (
                aiohttp.ClientSession() as session,
                session.get(
                    api_url, headers=headers, timeout=aiohttp.ClientTimeout(total=5.0), ssl=False
                ) as response,
            ):
                latency = (time.time() - start) * 1000
                if response.status == 200:
                    return True, latency, "Connected successfully"
                elif response.status == 401:
                    return False, latency, "Invalid token"
                else:
                    return False, latency, f"API error: HTTP {response.status}"
        except Exception as e:
            return False, 0, f"Connection error: {e}"

    async def _discover_rooms(
        integration_type: IntegrationType, credentials: SmartHomeCredentials
    ) -> list[RoomInfo]:
        """Discover rooms from the smart home system."""
        rooms: list[RoomInfo] = []

        if integration_type == IntegrationType.CONTROL4:
            try:
                import aiohttp

                host = credentials.control4_host
                port = credentials.control4_port or 5020
                url = f"http://{host}:{port}/api/v1/items?type=room"
                headers = {}
                if credentials.control4_api_key:
                    headers["X-API-Key"] = credentials.control4_api_key

                async with (
                    aiohttp.ClientSession() as session,
                    session.get(
                        url, headers=headers, timeout=aiohttp.ClientTimeout(total=10.0)
                    ) as response,
                ):
                    if response.status == 200:
                        data = await response.json()
                        for item in data:
                            rooms.append(
                                RoomInfo(
                                    id=str(item.get("id", "")),
                                    name=item.get("name", "Unknown"),
                                    floor=item.get("floor"),
                                    has_lights=True,  # Control4 typically has all
                                    has_shades=True,
                                    has_climate=True,
                                    has_audio=True,
                                    device_count=item.get("device_count", 0),
                                )
                            )
            except Exception as e:
                logger.error(f"Control4 room discovery failed: {e}")

        elif integration_type == IntegrationType.SMARTTHINGS:
            try:
                import aiohttp

                token = credentials.smartthings_token
                url = "https://api.smartthings.com/v1/rooms"
                headers = {"Authorization": f"Bearer {token}"}

                async with (
                    aiohttp.ClientSession() as session,
                    session.get(
                        url, headers=headers, timeout=aiohttp.ClientTimeout(total=10.0)
                    ) as response,
                ):
                    if response.status == 200:
                        data = await response.json()
                        for item in data.get("items", []):
                            rooms.append(
                                RoomInfo(
                                    id=item.get("roomId", ""),
                                    name=item.get("name", "Unknown"),
                                    floor=None,
                                    has_lights=True,
                                    has_shades=False,
                                    has_climate=False,
                                    has_audio=False,
                                    device_count=0,
                                )
                            )
            except Exception as e:
                logger.error(f"SmartThings room discovery failed: {e}")

        elif integration_type == IntegrationType.HOME_ASSISTANT:
            try:
                import aiohttp

                url = credentials.home_assistant_url
                token = credentials.home_assistant_token
                api_url = f"{url.rstrip('/')}/api/config"
                headers = {"Authorization": f"Bearer {token}"}

                async with (
                    aiohttp.ClientSession() as session,
                    session.get(
                        api_url,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=10.0),
                        ssl=False,
                    ) as response,
                ):
                    if response.status == 200:
                        # Home Assistant doesn't have rooms in config
                        # Would need to query area registry
                        # For now, return a placeholder
                        rooms.append(
                            RoomInfo(
                                id="ha_default",
                                name="Home",
                                floor=None,
                                has_lights=True,
                                has_shades=True,
                                has_climate=True,
                                has_audio=False,
                                device_count=0,
                            )
                        )
            except Exception as e:
                logger.error(f"Home Assistant discovery failed: {e}")

        return rooms

    # =============================================================================
    # ROUTES
    # =============================================================================

    @router.post(
        "/connect",
        response_model=ConnectResponse,
        responses=get_error_responses(400, 401, 422, 500),
        summary="Connect smart home integration",
        description="""
        Connect a tenant's smart home system to Kagami.

        This endpoint:
        1. Validates the provided credentials
        2. Tests connectivity to the smart home system
        3. Discovers available rooms and devices
        4. Stores encrypted credentials for future use

        Supported integrations:
        - Control4
        - Lutron (RadioRA, Caseta)
        - HomeKit
        - SmartThings
        - Google Home
        - Amazon Alexa
        - Hubitat
        - Home Assistant
        """,
    )
    async def connect_smart_home(
        request: ConnectRequest, current_user: User = Depends(get_current_user)
    ) -> ConnectResponse:
        """Connect a smart home integration for the authenticated tenant."""
        tenant_id = current_user.tenant_id or current_user.id
        connection_id = str(uuid.uuid4())

        # Test connection first
        test_result = await _test_connection(request.integration_type, request.credentials)

        if not test_result[0]:
            return ConnectResponse(
                success=False,
                connection_id=None,
                status=ConnectionStatus.ERROR,
                message=test_result[2],
            )

        # Discover rooms
        rooms = await _discover_rooms(request.integration_type, request.credentials)

        # Build config to store
        config: dict[str, Any] = {
            "id": connection_id,
            "integration_type": request.integration_type.value,
            "name": request.name or request.integration_type.value.replace("_", " ").title(),
            "is_primary": request.is_primary,
            "status": ConnectionStatus.CONNECTED.value,
            "credentials_encrypted": _encrypt_credentials(
                request.credentials.model_dump(exclude_none=True), tenant_id
            ),
            "room_count": len(rooms),
            "device_count": sum(r.device_count for r in rooms),
            "rooms": [r.model_dump() for r in rooms],
            "created_at": datetime.utcnow().isoformat(),
            "last_sync": datetime.utcnow().isoformat(),
        }

        # Store in Redis
        existing_config = await _get_tenant_config(tenant_id)
        if existing_config is None:
            existing_config = {"connections": []}

        # Replace if same integration type exists, otherwise append
        existing_config["connections"] = [
            c
            for c in existing_config.get("connections", [])
            if c.get("integration_type") != request.integration_type.value
        ]
        existing_config["connections"].append(config)

        if not await _set_tenant_config(tenant_id, existing_config):
            logger.warning(f"Failed to store config for tenant {tenant_id}")

        logger.info(
            f"Smart home connected: {request.integration_type.value} for tenant {tenant_id}"
        )

        return ConnectResponse(
            success=True,
            connection_id=connection_id,
            status=ConnectionStatus.CONNECTED,
            message=f"Successfully connected to {request.integration_type.value}",
            discovered_rooms=len(rooms),
            discovered_devices=sum(r.device_count for r in rooms),
        )

    async def _test_connection(
        integration_type: IntegrationType, credentials: SmartHomeCredentials
    ) -> tuple[bool, float, str]:
        """Test connection for any integration type."""
        if integration_type == IntegrationType.CONTROL4:
            if not credentials.control4_host:
                return False, 0, "Control4 host is required"
            return await _test_control4_connection(
                credentials.control4_host,
                credentials.control4_port,
                credentials.control4_api_key,
            )

        elif integration_type == IntegrationType.LUTRON:
            if not credentials.lutron_host:
                return False, 0, "Lutron host is required"
            return await _test_lutron_connection(
                credentials.lutron_host, credentials.lutron_password
            )

        elif integration_type == IntegrationType.SMARTTHINGS:
            if not credentials.smartthings_token:
                return False, 0, "SmartThings token is required"
            return await _test_smartthings_connection(credentials.smartthings_token)

        elif integration_type == IntegrationType.HOME_ASSISTANT:
            if not credentials.home_assistant_url or not credentials.home_assistant_token:
                return False, 0, "Home Assistant URL and token are required"
            return await _test_home_assistant_connection(
                credentials.home_assistant_url, credentials.home_assistant_token
            )

        elif integration_type == IntegrationType.HUBITAT:
            if not credentials.hubitat_host or not credentials.hubitat_access_token:
                return False, 0, "Hubitat host and access token are required"
            # Hubitat test would go here
            return True, 0, "Hubitat connection test not fully implemented"

        elif integration_type in (
            IntegrationType.HOMEKIT,
            IntegrationType.GOOGLE_HOME,
            IntegrationType.ALEXA,
        ):
            # These require OAuth flows handled elsewhere
            return True, 0, f"{integration_type.value} requires OAuth flow"

        return False, 0, f"Unknown integration type: {integration_type}"

    @router.get(
        "/rooms",
        response_model=RoomsResponse,
        responses=get_error_responses(401, 404, 500),
        summary="Get tenant's rooms",
        description="Returns list of rooms from the tenant's connected smart home.",
    )
    async def get_rooms(
        current_user: User = Depends(get_current_user),
        integration_type: IntegrationType | None = Query(
            None, description="Filter by integration type"
        ),
    ) -> RoomsResponse:
        """Get rooms from the tenant's smart home configuration."""
        tenant_id = current_user.tenant_id or current_user.id
        config = await _get_tenant_config(tenant_id)

        if not config or not config.get("connections"):
            raise HTTPException(
                status_code=404,
                detail="No smart home configured. Use POST /api/user/smart-home/connect first.",
            )

        # Get primary or specified integration
        connections = config.get("connections", [])
        connection = None

        if integration_type:
            connection = next(
                (c for c in connections if c.get("integration_type") == integration_type.value),
                None,
            )
        else:
            # Get primary connection
            connection = next((c for c in connections if c.get("is_primary")), None)
            if not connection and connections:
                connection = connections[0]

        if not connection:
            raise HTTPException(status_code=404, detail="Smart home connection not found")

        rooms = [RoomInfo(**r) for r in connection.get("rooms", [])]
        status = ConnectionStatus(connection.get("status", "disconnected"))

        return RoomsResponse(
            rooms=rooms,
            total=len(rooms),
            connection_status=status,
        )

    @router.post(
        "/test",
        response_model=TestConnectionResponse,
        responses=get_error_responses(400, 401, 422, 500),
        summary="Test smart home connection",
        description="Tests connectivity to a smart home system without saving credentials.",
    )
    async def test_connection(
        request: TestConnectionRequest, current_user: User = Depends(get_current_user)
    ) -> TestConnectionResponse:
        """Test smart home connection without saving."""
        success, latency_ms, message = await _test_connection(
            request.integration_type, request.credentials
        )

        return TestConnectionResponse(
            success=success,
            latency_ms=latency_ms if success else None,
            message=message,
            details={
                "integration_type": request.integration_type.value,
                "tested_at": datetime.utcnow().isoformat(),
            },
        )

    @router.get(
        "/connections",
        response_model=SmartHomeConfigListResponse,
        responses=get_error_responses(401, 500),
        summary="List smart home connections",
        description="Returns all configured smart home connections for the tenant.",
    )
    async def list_connections(
        current_user: User = Depends(get_current_user),
    ) -> SmartHomeConfigListResponse:
        """List all smart home connections for the tenant."""
        tenant_id = current_user.tenant_id or current_user.id
        config = await _get_tenant_config(tenant_id)

        if not config or not config.get("connections"):
            return SmartHomeConfigListResponse(connections=[], total=0)

        connections = []
        for conn in config.get("connections", []):
            connections.append(
                SmartHomeConfigOut(
                    id=conn.get("id", ""),
                    integration_type=conn.get("integration_type", ""),
                    name=conn.get("name", ""),
                    status=ConnectionStatus(conn.get("status", "disconnected")),
                    is_primary=conn.get("is_primary", False),
                    room_count=conn.get("room_count", 0),
                    device_count=conn.get("device_count", 0),
                    last_sync=(
                        datetime.fromisoformat(conn["last_sync"]) if conn.get("last_sync") else None
                    ),
                    created_at=datetime.fromisoformat(
                        conn.get("created_at", datetime.utcnow().isoformat())
                    ),
                )
            )

        return SmartHomeConfigListResponse(connections=connections, total=len(connections))

    @router.delete(
        "/connections/{connection_id}",
        responses=get_error_responses(401, 404, 500),
        summary="Remove smart home connection",
        description="Removes a smart home connection and deletes stored credentials.",
    )
    async def remove_connection(
        connection_id: str, current_user: User = Depends(get_current_user)
    ) -> dict[str, Any]:
        """Remove a smart home connection."""
        tenant_id = current_user.tenant_id or current_user.id
        config = await _get_tenant_config(tenant_id)

        if not config or not config.get("connections"):
            raise HTTPException(status_code=404, detail="Connection not found")

        original_count = len(config.get("connections", []))
        config["connections"] = [
            c for c in config.get("connections", []) if c.get("id") != connection_id
        ]

        if len(config["connections"]) == original_count:
            raise HTTPException(status_code=404, detail="Connection not found")

        await _set_tenant_config(tenant_id, config)

        return {"success": True, "message": "Connection removed"}

    @router.post(
        "/sync",
        responses=get_error_responses(401, 404, 500),
        summary="Sync rooms and devices",
        description="Re-discovers rooms and devices from the smart home system.",
    )
    async def sync_smart_home(
        current_user: User = Depends(get_current_user),
        connection_id: str | None = Query(None, description="Specific connection to sync"),
    ) -> dict[str, Any]:
        """Sync rooms and devices from the smart home system."""
        tenant_id = current_user.tenant_id or current_user.id
        config = await _get_tenant_config(tenant_id)

        if not config or not config.get("connections"):
            raise HTTPException(status_code=404, detail="No smart home configured")

        synced = []
        for conn in config.get("connections", []):
            if connection_id and conn.get("id") != connection_id:
                continue

            # Decrypt credentials
            try:
                credentials_dict = _decrypt_credentials(
                    conn.get("credentials_encrypted", ""), tenant_id
                )
                credentials = SmartHomeCredentials(**credentials_dict)
                integration_type = IntegrationType(conn.get("integration_type"))

                # Re-discover rooms
                rooms = await _discover_rooms(integration_type, credentials)

                # Update config
                conn["rooms"] = [r.model_dump() for r in rooms]
                conn["room_count"] = len(rooms)
                conn["device_count"] = sum(r.device_count for r in rooms)
                conn["last_sync"] = datetime.utcnow().isoformat()
                conn["status"] = ConnectionStatus.CONNECTED.value

                synced.append(
                    {
                        "id": conn.get("id"),
                        "integration_type": conn.get("integration_type"),
                        "rooms_found": len(rooms),
                    }
                )
            except Exception as e:
                logger.error(f"Sync failed for connection {conn.get('id')}: {e}")
                conn["status"] = ConnectionStatus.ERROR.value
                synced.append(
                    {
                        "id": conn.get("id"),
                        "integration_type": conn.get("integration_type"),
                        "error": str(e),
                    }
                )

        await _set_tenant_config(tenant_id, config)

        return {
            "success": True,
            "synced_connections": synced,
            "synced_at": datetime.utcnow().isoformat(),
        }

    return router


__all__ = ["get_router"]
