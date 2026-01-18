"""Server Discovery API Routes.

Provides public discovery endpoint for clients to detect and identify
Kagami servers on the network.

Used by:
- Client apps during server selection/onboarding
- mDNS/DNS-SD discovery validation
- Health monitoring systems

Created: December 31, 2025 (RALPH Week 2)
"""

from __future__ import annotations

import logging
import os
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(tags=["discovery"])

    # =============================================================================
    # SCHEMAS
    # =============================================================================

    class IntegrationCapability(BaseModel):
        """Description of an available integration."""

        id: str = Field(description="Integration identifier")
        name: str = Field(description="Human-readable name")
        type: str = Field(description="Integration type: smart_home, digital, biometric, media")
        requires_credentials: bool = Field(
            default=True, description="Whether credentials are required"
        )
        supported: bool = Field(default=True, description="Whether integration is available")
        documentation_url: str | None = Field(
            default=None, description="Link to setup documentation"
        )

    class ServerCapabilities(BaseModel):
        """Server capabilities advertised during discovery."""

        # Core features
        voice_control: bool = Field(default=True, description="Voice command processing")
        smart_home: bool = Field(default=True, description="Smart home control")
        digital_integrations: bool = Field(default=True, description="Gmail, Slack, etc.")
        biometrics: bool = Field(default=True, description="Health data processing")
        ar_support: bool = Field(default=False, description="AR/Vision Pro features")

        # Protocol support
        websocket: bool = Field(default=True, description="WebSocket streaming")
        webhooks: bool = Field(default=True, description="Webhook delivery")
        sse: bool = Field(default=True, description="Server-Sent Events")

        # Security features
        oauth2: bool = Field(default=True, description="OAuth 2.0 authentication")
        saml: bool = Field(default=False, description="SAML SSO (Enterprise)")
        api_keys: bool = Field(default=True, description="API key authentication")
        mfa: bool = Field(default=True, description="Multi-factor authentication")

    class SupportedIntegrations(BaseModel):
        """Available integrations organized by category."""

        smart_home: list[IntegrationCapability] = Field(
            default_factory=list, description="Smart home integrations"
        )
        digital: list[IntegrationCapability] = Field(
            default_factory=list, description="Digital/productivity integrations"
        )
        biometric: list[IntegrationCapability] = Field(
            default_factory=list, description="Health/biometric integrations"
        )
        media: list[IntegrationCapability] = Field(
            default_factory=list, description="Media/entertainment integrations"
        )

    class DiscoveryResponse(BaseModel):
        """Server discovery response.

        This response is designed to be consumed by:
        - Client apps during onboarding
        - mDNS service browsers
        - API documentation generators
        """

        # Server identity
        name: str = Field(description="Server name (human-readable)")
        version: str = Field(description="Server version")
        build: str | None = Field(default=None, description="Build identifier")
        instance_id: str | None = Field(default=None, description="Unique instance ID")

        # Capabilities
        capabilities: ServerCapabilities = Field(description="Server capabilities")

        # Available integrations
        integrations: SupportedIntegrations = Field(description="Available integrations")

        # API information
        api_version: str = Field(default="v1", description="API version")
        api_docs_url: str = Field(default="/docs", description="OpenAPI documentation URL")
        health_url: str = Field(default="/api/vitals/live", description="Health check URL")

        # Authentication
        auth_url: str = Field(default="/api/user/auth/login", description="Authentication endpoint")
        register_url: str | None = Field(
            default="/api/user/auth/register", description="Registration endpoint (if enabled)"
        )

        # Deployment info
        deployment: str = Field(
            default="self-hosted",
            description="Deployment type: self-hosted, cloud, enterprise, hub",
        )
        region: str | None = Field(default=None, description="Geographic region (cloud only)")

        # Timestamps
        server_time: datetime = Field(
            default_factory=datetime.utcnow, description="Server current time (UTC)"
        )
        uptime_seconds: int | None = Field(default=None, description="Server uptime")

    # =============================================================================
    # HELPERS
    # =============================================================================

    def _get_server_version() -> str:
        """Get server version from package or environment."""
        try:
            from importlib.metadata import version

            return version("kagami-api")
        except Exception:
            return os.getenv("KAGAMI_VERSION", "0.1.0")

    def _get_instance_id() -> str | None:
        """Get unique instance identifier."""
        instance_id = os.getenv("KAGAMI_INSTANCE_ID")
        if instance_id:
            return instance_id
        # Try to generate from hostname
        import socket

        try:
            hostname = socket.gethostname()
            return f"kagami-{hostname}"
        except Exception:
            return None

    def _get_uptime() -> int | None:
        """Get server uptime in seconds."""
        try:
            import psutil

            boot_time = psutil.boot_time()
            return int(datetime.utcnow().timestamp() - boot_time)
        except Exception:
            return None

    def _get_supported_integrations() -> SupportedIntegrations:
        """Build list of supported integrations."""
        # Smart home integrations
        smart_home = [
            IntegrationCapability(
                id="control4",
                name="Control4",
                type="smart_home",
                requires_credentials=True,
                documentation_url="https://docs.awkronos.com/integrations/control4",
            ),
            IntegrationCapability(
                id="lutron",
                name="Lutron (RadioRA, Caseta)",
                type="smart_home",
                requires_credentials=True,
                documentation_url="https://docs.awkronos.com/integrations/lutron",
            ),
            IntegrationCapability(
                id="homekit",
                name="Apple HomeKit",
                type="smart_home",
                requires_credentials=False,
                documentation_url="https://docs.awkronos.com/integrations/homekit",
            ),
            IntegrationCapability(
                id="smartthings",
                name="Samsung SmartThings",
                type="smart_home",
                requires_credentials=True,
                documentation_url="https://docs.awkronos.com/integrations/smartthings",
            ),
            IntegrationCapability(
                id="august",
                name="August/Yale Locks",
                type="smart_home",
                requires_credentials=True,
                documentation_url="https://docs.awkronos.com/integrations/august",
            ),
            IntegrationCapability(
                id="denon",
                name="Denon/Marantz AVR",
                type="smart_home",
                requires_credentials=False,
                documentation_url="https://docs.awkronos.com/integrations/denon",
            ),
        ]

        # Digital integrations (via Composio)
        digital = [
            IntegrationCapability(
                id="gmail",
                name="Gmail",
                type="digital",
                requires_credentials=True,
                documentation_url="https://docs.awkronos.com/integrations/gmail",
            ),
            IntegrationCapability(
                id="slack",
                name="Slack",
                type="digital",
                requires_credentials=True,
                documentation_url="https://docs.awkronos.com/integrations/slack",
            ),
            IntegrationCapability(
                id="google_calendar",
                name="Google Calendar",
                type="digital",
                requires_credentials=True,
                documentation_url="https://docs.awkronos.com/integrations/google-calendar",
            ),
            IntegrationCapability(
                id="todoist",
                name="Todoist",
                type="digital",
                requires_credentials=True,
                documentation_url="https://docs.awkronos.com/integrations/todoist",
            ),
            IntegrationCapability(
                id="notion",
                name="Notion",
                type="digital",
                requires_credentials=True,
                documentation_url="https://docs.awkronos.com/integrations/notion",
            ),
            IntegrationCapability(
                id="linear",
                name="Linear",
                type="digital",
                requires_credentials=True,
                documentation_url="https://docs.awkronos.com/integrations/linear",
            ),
        ]

        # Biometric integrations
        biometric = [
            IntegrationCapability(
                id="apple_health",
                name="Apple Health (via HealthKit)",
                type="biometric",
                requires_credentials=False,
                documentation_url="https://docs.awkronos.com/integrations/apple-health",
            ),
            IntegrationCapability(
                id="eight_sleep",
                name="Eight Sleep",
                type="biometric",
                requires_credentials=True,
                documentation_url="https://docs.awkronos.com/integrations/eight-sleep",
            ),
            IntegrationCapability(
                id="health_connect",
                name="Android Health Connect",
                type="biometric",
                requires_credentials=False,
                documentation_url="https://docs.awkronos.com/integrations/health-connect",
            ),
        ]

        # Media integrations
        media = [
            IntegrationCapability(
                id="spotify",
                name="Spotify",
                type="media",
                requires_credentials=True,
                documentation_url="https://docs.awkronos.com/integrations/spotify",
            ),
            IntegrationCapability(
                id="plex",
                name="Plex",
                type="media",
                requires_credentials=True,
                documentation_url="https://docs.awkronos.com/integrations/plex",
            ),
            IntegrationCapability(
                id="lg_tv",
                name="LG webOS TV",
                type="media",
                requires_credentials=False,
                documentation_url="https://docs.awkronos.com/integrations/lg-tv",
            ),
            IntegrationCapability(
                id="samsung_tv",
                name="Samsung Tizen TV",
                type="media",
                requires_credentials=False,
                documentation_url="https://docs.awkronos.com/integrations/samsung-tv",
            ),
        ]

        return SupportedIntegrations(
            smart_home=smart_home,
            digital=digital,
            biometric=biometric,
            media=media,
        )

    def _get_capabilities() -> ServerCapabilities:
        """Build server capabilities based on configuration."""
        # Check for AR support (Vision Pro integration)
        ar_support = os.getenv("KAGAMI_AR_ENABLED", "false").lower() == "true"

        # Check for SAML (Enterprise)
        saml_enabled = os.getenv("KAGAMI_SAML_ENABLED", "false").lower() == "true"

        return ServerCapabilities(
            voice_control=True,
            smart_home=True,
            digital_integrations=True,
            biometrics=True,
            ar_support=ar_support,
            websocket=True,
            webhooks=True,
            sse=True,
            oauth2=True,
            saml=saml_enabled,
            api_keys=True,
            mfa=True,
        )

    # =============================================================================
    # ROUTES
    # =============================================================================

    @router.get(
        "/api/discovery",
        response_model=DiscoveryResponse,
        summary="Discover server capabilities",
        description="""
        Returns server identification, capabilities, and available integrations.

        This endpoint is:
        - **Public** (no authentication required)
        - **Cacheable** (clients can cache for 5 minutes)
        - **Used by mDNS** for service validation

        Clients should call this endpoint to:
        1. Validate that a URL points to a Kagami server
        2. Discover available integrations before onboarding
        3. Check server version compatibility
        """,
        responses={
            200: {
                "description": "Server discovery information",
                "content": {
                    "application/json": {
                        "example": {
                            "name": "Kagami @ Tim's Home",
                            "version": "1.0.0",
                            "capabilities": {
                                "voice_control": True,
                                "smart_home": True,
                                "digital_integrations": True,
                            },
                            "api_version": "v1",
                        }
                    }
                },
            }
        },
    )
    async def discover() -> DiscoveryResponse:
        """Discover server capabilities and available integrations.

        This is a public endpoint (no auth required) designed for:
        - Client apps discovering servers via mDNS
        - Onboarding wizards checking available integrations
        - Health monitoring systems validating server identity
        """
        server_name = os.getenv("KAGAMI_SERVER_NAME", "Kagami Server")
        deployment = os.getenv("KAGAMI_DEPLOYMENT", "self-hosted")
        region = os.getenv("KAGAMI_REGION")

        # Check if registration is enabled
        registration_enabled = os.getenv("KAGAMI_REGISTRATION_ENABLED", "true").lower() == "true"

        return DiscoveryResponse(
            name=server_name,
            version=_get_server_version(),
            build=os.getenv("KAGAMI_BUILD"),
            instance_id=_get_instance_id(),
            capabilities=_get_capabilities(),
            integrations=_get_supported_integrations(),
            api_version="v1",
            api_docs_url="/docs",
            health_url="/api/vitals/live",
            auth_url="/api/user/auth/login",
            register_url="/api/user/auth/register" if registration_enabled else None,
            deployment=deployment,
            region=region,
            server_time=datetime.utcnow(),
            uptime_seconds=_get_uptime(),
        )

    @router.get(
        "/api/discovery/integrations",
        response_model=SupportedIntegrations,
        summary="List available integrations",
        description="Returns detailed list of all available integrations by category.",
    )
    async def list_integrations() -> SupportedIntegrations:
        """List all available integrations organized by category."""
        return _get_supported_integrations()

    @router.get(
        "/api/discovery/capabilities",
        response_model=ServerCapabilities,
        summary="Get server capabilities",
        description="Returns server feature flags and protocol support.",
    )
    async def get_capabilities() -> ServerCapabilities:
        """Get server capabilities and feature flags."""
        return _get_capabilities()

    return router


__all__ = ["get_router"]
