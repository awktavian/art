"""Kagami Federation Protocol (KFP) — Simpler than OAuth.

Enables any domain owner to create a federated Kagami instance.
Like email (SMTP) or Mastodon (ActivityPub), but for home automation.

Discovery Flow:
```
1. DNS TXT Record:
   _kagami.example.com TXT "v=kfp1 hub=https://hub.example.com pk=ed25519:xxx"

2. WebFinger Lookup:
   GET /.well-known/webfinger?resource=acct:user@example.com
   → { "links": [{ "rel": "kagami", "href": "https://hub.example.com" }] }

3. Handshake (Kyber + X25519):
   POST /federation/handshake
   ← Quantum-safe key exchange

4. Consensus Join:
   Instance joins PBFT consensus network
```

Colony: Nexus (e₄) — Integration
h(x) ≥ 0. Federation IS freedom.

Created: January 2026
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

import dns.resolver
import httpx

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

KFP_VERSION = "kfp1"
KFP_DNS_PREFIX = "_kagami"
KFP_WEBFINGER_REL = "https://kagami.io/rel/hub"
KFP_HANDSHAKE_PATH = "/federation/handshake"
KFP_CONSENSUS_PATH = "/federation/consensus"


# =============================================================================
# Data Models
# =============================================================================


class FederationState(Enum):
    """State of federation with a remote instance."""

    UNKNOWN = auto()  # Never contacted
    DISCOVERED = auto()  # DNS/WebFinger found
    HANDSHAKING = auto()  # Handshake in progress
    CONNECTED = auto()  # Fully federated
    SUSPENDED = auto()  # Temporarily suspended
    BLOCKED = auto()  # Permanently blocked


@dataclass
class KFPRecord:
    """Parsed KFP DNS TXT record.

    Format: v=kfp1 hub=https://hub.example.com pk=ed25519:base64key

    Attributes:
        version: Protocol version (kfp1).
        hub_url: URL of the federation hub.
        public_key: Base64-encoded public key.
        key_type: Key type (ed25519, kyber768).
        extra: Additional key-value pairs.
    """

    version: str
    hub_url: str
    public_key: str
    key_type: str = "ed25519"
    extra: dict[str, str] = field(default_factory=dict)

    @classmethod
    def parse(cls, txt_record: str) -> KFPRecord | None:
        """Parse a KFP DNS TXT record.

        Args:
            txt_record: Raw TXT record value.

        Returns:
            KFPRecord or None if invalid.
        """
        parts = txt_record.split()
        params = {}

        for part in parts:
            if "=" in part:
                key, value = part.split("=", 1)
                params[key] = value

        # Validate required fields
        version = params.get("v")
        if not version or not version.startswith("kfp"):
            return None

        hub_url = params.get("hub")
        if not hub_url:
            return None

        pk_raw = params.get("pk", "")
        if ":" in pk_raw:
            key_type, public_key = pk_raw.split(":", 1)
        else:
            key_type = "ed25519"
            public_key = pk_raw

        # Extract extra params
        extra = {k: v for k, v in params.items() if k not in ("v", "hub", "pk")}

        return cls(
            version=version,
            hub_url=hub_url,
            public_key=public_key,
            key_type=key_type,
            extra=extra,
        )

    def to_txt(self) -> str:
        """Convert to TXT record format."""
        parts = [
            f"v={self.version}",
            f"hub={self.hub_url}",
            f"pk={self.key_type}:{self.public_key}",
        ]
        parts.extend(f"{k}={v}" for k, v in self.extra.items())
        return " ".join(parts)


@dataclass
class FederatedInstance:
    """A federated Kagami instance.

    Attributes:
        domain: Domain name (e.g., example.com).
        hub_url: Federation hub URL.
        public_key: Instance public key.
        state: Federation state.
        last_seen: Last successful communication.
        trust_score: Trust score (0-100).
        metadata: Additional instance metadata.
    """

    domain: str
    hub_url: str
    public_key: bytes
    state: FederationState = FederationState.DISCOVERED
    last_seen: float = 0.0
    trust_score: int = 50
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        """Check if instance is actively federated."""
        return self.state == FederationState.CONNECTED

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "domain": self.domain,
            "hub_url": self.hub_url,
            "public_key": base64.b64encode(self.public_key).decode(),
            "state": self.state.name,
            "last_seen": self.last_seen,
            "trust_score": self.trust_score,
            "metadata": self.metadata,
        }


@dataclass
class HandshakeRequest:
    """Federation handshake request.

    Attributes:
        from_domain: Requesting domain.
        from_hub: Requesting hub URL.
        challenge: Random challenge bytes.
        public_key: Ephemeral public key for key exchange.
        timestamp: Request timestamp.
        signature: Signature over request.
    """

    from_domain: str
    from_hub: str
    challenge: bytes
    public_key: bytes
    timestamp: float
    signature: bytes = b""

    def to_dict(self) -> dict[str, Any]:
        """Serialize for transmission."""
        return {
            "from_domain": self.from_domain,
            "from_hub": self.from_hub,
            "challenge": base64.b64encode(self.challenge).decode(),
            "public_key": base64.b64encode(self.public_key).decode(),
            "timestamp": self.timestamp,
            "signature": base64.b64encode(self.signature).decode(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HandshakeRequest:
        """Deserialize from transmission."""
        return cls(
            from_domain=data["from_domain"],
            from_hub=data["from_hub"],
            challenge=base64.b64decode(data["challenge"]),
            public_key=base64.b64decode(data["public_key"]),
            timestamp=data["timestamp"],
            signature=base64.b64decode(data.get("signature", "")),
        )


@dataclass
class HandshakeResponse:
    """Federation handshake response.

    Attributes:
        accepted: Whether handshake was accepted.
        challenge_response: Response to challenge.
        public_key: Responder's ephemeral public key.
        shared_secret_hash: Hash of derived shared secret.
        error: Error message if rejected.
    """

    accepted: bool
    challenge_response: bytes = b""
    public_key: bytes = b""
    shared_secret_hash: str = ""
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize for transmission."""
        return {
            "accepted": self.accepted,
            "challenge_response": base64.b64encode(self.challenge_response).decode(),
            "public_key": base64.b64encode(self.public_key).decode(),
            "shared_secret_hash": self.shared_secret_hash,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HandshakeResponse:
        """Deserialize from transmission."""
        return cls(
            accepted=data["accepted"],
            challenge_response=base64.b64decode(data.get("challenge_response", "")),
            public_key=base64.b64decode(data.get("public_key", "")),
            shared_secret_hash=data.get("shared_secret_hash", ""),
            error=data.get("error"),
        )


# =============================================================================
# Discovery
# =============================================================================


class KFPDiscovery:
    """Discover federated instances via DNS and WebFinger.

    Example:
        >>> discovery = KFPDiscovery()
        >>>
        >>> # Discover by domain
        >>> instance = await discovery.discover("example.com")
        >>> if instance:
        ...     print(f"Found hub at {instance.hub_url}")
        >>>
        >>> # Discover by user
        >>> instance = await discovery.discover_user("tim@example.com")
    """

    def __init__(self, timeout: float = 10.0) -> None:
        self._timeout = timeout
        self._cache: dict[str, FederatedInstance] = {}
        self._cache_ttl = 3600  # 1 hour

    async def discover(self, domain: str) -> FederatedInstance | None:
        """Discover a federated instance by domain.

        Args:
            domain: Domain to discover (e.g., example.com).

        Returns:
            FederatedInstance or None if not found.
        """
        # Check cache
        if domain in self._cache:
            instance = self._cache[domain]
            if time.time() - instance.last_seen < self._cache_ttl:
                return instance

        # Try DNS TXT record first
        record = await self._lookup_dns(domain)
        if record:
            instance = FederatedInstance(
                domain=domain,
                hub_url=record.hub_url,
                public_key=base64.b64decode(record.public_key) if record.public_key else b"",
                state=FederationState.DISCOVERED,
                last_seen=time.time(),
            )
            self._cache[domain] = instance
            return instance

        # Fallback to WebFinger
        webfinger = await self._lookup_webfinger(domain)
        if webfinger:
            instance = FederatedInstance(
                domain=domain,
                hub_url=webfinger["hub_url"],
                public_key=base64.b64decode(webfinger.get("public_key", ""))
                if webfinger.get("public_key")
                else b"",
                state=FederationState.DISCOVERED,
                last_seen=time.time(),
                metadata=webfinger.get("metadata", {}),
            )
            self._cache[domain] = instance
            return instance

        return None

    async def discover_user(self, address: str) -> FederatedInstance | None:
        """Discover instance for a user address.

        Args:
            address: User address (e.g., tim@example.com).

        Returns:
            FederatedInstance or None.
        """
        if "@" not in address:
            return None

        _, domain = address.rsplit("@", 1)
        return await self.discover(domain)

    async def _lookup_dns(self, domain: str) -> KFPRecord | None:
        """Look up KFP DNS TXT record.

        Args:
            domain: Domain to query.

        Returns:
            KFPRecord or None.
        """
        try:
            dns_name = f"{KFP_DNS_PREFIX}.{domain}"

            # Run DNS query in thread pool
            loop = asyncio.get_event_loop()
            answers = await loop.run_in_executor(
                None,
                lambda: dns.resolver.resolve(dns_name, "TXT"),
            )

            for answer in answers:
                txt_value = str(answer).strip('"')
                record = KFPRecord.parse(txt_value)
                if record:
                    logger.info(f"Found KFP record for {domain}: {record.hub_url}")
                    return record

        except dns.resolver.NXDOMAIN:
            logger.debug(f"No KFP DNS record for {domain}")
        except dns.resolver.NoAnswer:
            logger.debug(f"No TXT record for {domain}")
        except Exception as e:
            logger.warning(f"DNS lookup failed for {domain}: {e}")

        return None

    async def _lookup_webfinger(self, domain: str) -> dict[str, Any] | None:
        """Look up instance via WebFinger.

        Args:
            domain: Domain to query.

        Returns:
            WebFinger data or None.
        """
        try:
            url = f"https://{domain}/.well-known/webfinger"
            params = {"resource": f"acct:kagami@{domain}"}

            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, params=params)

                if response.status_code != 200:
                    return None

                data = response.json()

                # Find Kagami link
                for link in data.get("links", []):
                    if link.get("rel") == KFP_WEBFINGER_REL:
                        return {
                            "hub_url": link.get("href"),
                            "public_key": link.get("properties", {}).get("public_key"),
                            "metadata": link.get("properties", {}),
                        }

        except Exception as e:
            logger.debug(f"WebFinger lookup failed for {domain}: {e}")

        return None


# =============================================================================
# Federation Manager
# =============================================================================


class FederationManager:
    """Manage federated instances and consensus participation.

    Example:
        >>> manager = await get_federation_manager()
        >>>
        >>> # Federate with another instance
        >>> success = await manager.federate("example.com")
        >>>
        >>> # List federated instances
        >>> instances = manager.list_instances()
        >>>
        >>> # Send state update to federation
        >>> await manager.broadcast_state({"presence": {"tim": "home"}})
    """

    def __init__(
        self,
        my_domain: str = "",
        my_hub_url: str = "",
    ) -> None:
        self._my_domain = my_domain or os.environ.get("KAGAMI_DOMAIN", "localhost")
        self._my_hub_url = my_hub_url or os.environ.get("KAGAMI_HUB_URL", "http://localhost:8000")

        self._discovery = KFPDiscovery()
        self._instances: dict[str, FederatedInstance] = {}
        self._keypair: Any = None  # HybridKeypair
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize federation manager."""
        if self._initialized:
            return

        # Generate keypair for federation
        from kagami.core.security.quantum_safe import HybridCrypto

        hybrid = HybridCrypto()
        self._keypair = hybrid.generate_keypair()

        self._initialized = True
        logger.info(f"✅ FederationManager initialized for {self._my_domain}")

    async def federate(self, domain: str) -> bool:
        """Establish federation with another instance.

        Args:
            domain: Domain to federate with.

        Returns:
            True if federation successful.
        """
        if not self._initialized:
            await self.initialize()

        # Discover instance
        instance = await self._discovery.discover(domain)
        if not instance:
            logger.warning(f"Could not discover {domain}")
            return False

        # Perform handshake
        try:
            instance.state = FederationState.HANDSHAKING

            success = await self._handshake(instance)

            if success:
                instance.state = FederationState.CONNECTED
                instance.last_seen = time.time()
                instance.trust_score = 60  # Initial trust after handshake
                self._instances[domain] = instance
                logger.info(f"✅ Federated with {domain}")
                return True
            else:
                instance.state = FederationState.SUSPENDED
                logger.warning(f"Handshake failed with {domain}")
                return False

        except Exception as e:
            logger.error(f"Federation failed with {domain}: {e}")
            instance.state = FederationState.SUSPENDED
            return False

    async def _handshake(self, instance: FederatedInstance) -> bool:
        """Perform federation handshake.

        Args:
            instance: Instance to handshake with.

        Returns:
            True if handshake successful.
        """
        # Create handshake request
        challenge = os.urandom(32)

        request = HandshakeRequest(
            from_domain=self._my_domain,
            from_hub=self._my_hub_url,
            challenge=challenge,
            public_key=self._keypair.pq_public,  # Kyber public key
            timestamp=time.time(),
        )

        # Sign the request
        from kagami.core.security.quantum_safe import HybridCrypto

        hybrid = HybridCrypto()
        request_bytes = json.dumps(request.to_dict(), sort_keys=True).encode()
        request.signature = hybrid.sign(request_bytes, self._keypair)

        # Send handshake
        try:
            url = f"{instance.hub_url}{KFP_HANDSHAKE_PATH}"

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    json=request.to_dict(),
                    headers={"Content-Type": "application/json"},
                )

                if response.status_code != 200:
                    logger.warning(f"Handshake returned {response.status_code}")
                    return False

                result = HandshakeResponse.from_dict(response.json())

                if not result.accepted:
                    logger.warning(f"Handshake rejected: {result.error}")
                    return False

                # Verify challenge response
                expected_response = hashlib.sha256(challenge + self._keypair.pq_public).digest()

                if result.challenge_response != expected_response:
                    logger.warning("Invalid challenge response")
                    return False

                return True

        except Exception as e:
            logger.error(f"Handshake request failed: {e}")
            return False

    def list_instances(self) -> list[FederatedInstance]:
        """List all federated instances.

        Returns:
            List of federated instances.
        """
        return list(self._instances.values())

    def get_instance(self, domain: str) -> FederatedInstance | None:
        """Get a specific federated instance.

        Args:
            domain: Domain to look up.

        Returns:
            FederatedInstance or None.
        """
        return self._instances.get(domain)

    async def broadcast_state(
        self,
        state: dict[str, Any],
        exclude: list[str] | None = None,
    ) -> dict[str, bool]:
        """Broadcast state update to all federated instances.

        Args:
            state: State to broadcast.
            exclude: Domains to exclude.

        Returns:
            Dict of domain -> success.
        """
        exclude = exclude or []
        results = {}

        for domain, instance in self._instances.items():
            if domain in exclude:
                continue

            if instance.state != FederationState.CONNECTED:
                continue

            try:
                url = f"{instance.hub_url}/federation/state"

                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        url,
                        json={
                            "from_domain": self._my_domain,
                            "state": state,
                            "timestamp": time.time(),
                        },
                    )

                    results[domain] = response.status_code == 200

            except Exception as e:
                logger.debug(f"Broadcast to {domain} failed: {e}")
                results[domain] = False

        return results

    def get_status(self) -> dict[str, Any]:
        """Get federation status."""
        connected = sum(1 for i in self._instances.values() if i.state == FederationState.CONNECTED)

        return {
            "initialized": self._initialized,
            "my_domain": self._my_domain,
            "my_hub_url": self._my_hub_url,
            "total_instances": len(self._instances),
            "connected_instances": connected,
            "instances": [
                {
                    "domain": i.domain,
                    "state": i.state.name,
                    "trust_score": i.trust_score,
                }
                for i in self._instances.values()
            ],
        }


# =============================================================================
# WebFinger Handler
# =============================================================================


def create_webfinger_response(
    domain: str,
    hub_url: str,
    public_key: bytes,
) -> dict[str, Any]:
    """Create WebFinger response for Kagami discovery.

    Args:
        domain: Instance domain.
        hub_url: Hub URL.
        public_key: Instance public key.

    Returns:
        WebFinger response dict.
    """
    return {
        "subject": f"acct:kagami@{domain}",
        "aliases": [
            hub_url,
            f"https://{domain}",
        ],
        "links": [
            {
                "rel": KFP_WEBFINGER_REL,
                "type": "application/json",
                "href": hub_url,
                "properties": {
                    "public_key": base64.b64encode(public_key).decode(),
                    "protocol_version": KFP_VERSION,
                },
            },
            {
                "rel": "self",
                "type": "application/activity+json",
                "href": f"{hub_url}/federation/actor",
            },
        ],
    }


# =============================================================================
# FastAPI Integration
# =============================================================================


def create_federation_router():
    """Create FastAPI router for federation endpoints.

    Returns:
        FastAPI APIRouter.
    """
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel

    router = APIRouter(prefix="/federation", tags=["Federation"])

    class HandshakeIn(BaseModel):
        from_domain: str
        from_hub: str
        challenge: str
        public_key: str
        timestamp: float
        signature: str

    @router.post("/handshake")
    async def handle_handshake(request: HandshakeIn):
        """Handle incoming federation handshake."""
        manager = await get_federation_manager()

        # Parse request
        handshake = HandshakeRequest(
            from_domain=request.from_domain,
            from_hub=request.from_hub,
            challenge=base64.b64decode(request.challenge),
            public_key=base64.b64decode(request.public_key),
            timestamp=request.timestamp,
            signature=base64.b64decode(request.signature),
        )

        # Validate timestamp (prevent replay)
        if abs(time.time() - handshake.timestamp) > 300:  # 5 minute window
            return HandshakeResponse(
                accepted=False,
                error="Request expired",
            ).to_dict()

        # Generate response
        challenge_response = hashlib.sha256(
            handshake.challenge + manager._keypair.pq_public
        ).digest()

        return HandshakeResponse(
            accepted=True,
            challenge_response=challenge_response,
            public_key=manager._keypair.pq_public,
            shared_secret_hash=hashlib.sha256(
                handshake.public_key + manager._keypair.pq_public
            ).hexdigest()[:16],
        ).to_dict()

    @router.get("/status")
    async def get_status():
        """Get federation status."""
        manager = await get_federation_manager()
        return manager.get_status()

    @router.get("/instances")
    async def list_instances():
        """List federated instances."""
        manager = await get_federation_manager()
        return {
            "instances": [i.to_dict() for i in manager.list_instances()],
        }

    @router.post("/discover")
    async def discover_instance(domain: str):
        """Discover and federate with an instance."""
        manager = await get_federation_manager()

        success = await manager.federate(domain)

        if success:
            instance = manager.get_instance(domain)
            return {
                "success": True,
                "instance": instance.to_dict() if instance else None,
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Could not federate with {domain}",
            )

    return router


# =============================================================================
# Factory Functions
# =============================================================================


_federation_manager: FederationManager | None = None


async def get_federation_manager() -> FederationManager:
    """Get or create the singleton federation manager.

    Returns:
        FederationManager instance.
    """
    global _federation_manager

    if _federation_manager is None:
        _federation_manager = FederationManager()
        await _federation_manager.initialize()

    return _federation_manager


async def shutdown_federation() -> None:
    """Shutdown federation manager."""
    global _federation_manager
    _federation_manager = None


# =============================================================================
# Exports
# =============================================================================


__all__ = [
    "KFP_VERSION",
    "FederatedInstance",
    "FederationManager",
    "FederationState",
    "HandshakeRequest",
    "HandshakeResponse",
    "KFPDiscovery",
    "KFPRecord",
    "create_federation_router",
    "create_webfinger_response",
    "get_federation_manager",
    "shutdown_federation",
]
