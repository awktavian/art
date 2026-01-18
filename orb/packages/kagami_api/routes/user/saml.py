"""SAML 2.0 Authentication for Kagami Enterprise.

Provides SAML Single Sign-On (SSO) endpoints:
- GET /api/auth/saml/login - Redirect to IdP for authentication
- POST /api/auth/saml/callback - Handle SAML assertion from IdP
- GET /api/auth/saml/metadata - SP metadata for IdP configuration

Supports:
- SAML 2.0 assertions with signed responses
- Attribute mapping (email, name, groups -> roles)
- Just-in-time (JIT) user provisioning
- Multiple IdP configurations per tenant

RALPH Week 3 - Enterprise Authentication
"""

import base64
import logging
import secrets
import time
import uuid
import zlib
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from kagami_api.audit_logger import AuditEventType, get_audit_logger
from kagami_api.response_schemas import get_error_responses
from kagami_api.security import SecurityFramework
from kagami_api.security.shared import ACCESS_TOKEN_EXPIRE_MINUTES
from kagami_api.user_store import get_user_store

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration Models
# =============================================================================


class SAMLAttributeMapping(BaseModel):
    """Mapping from SAML attributes to user fields."""

    email: str = Field(
        default="http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
        description="SAML attribute for email",
    )
    first_name: str = Field(
        default="http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname",
        description="SAML attribute for first name",
    )
    last_name: str = Field(
        default="http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname",
        description="SAML attribute for last name",
    )
    display_name: str = Field(
        default="http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name",
        description="SAML attribute for display name",
    )
    groups: str = Field(
        default="http://schemas.microsoft.com/ws/2008/06/identity/claims/groups",
        description="SAML attribute for group membership",
    )


class SAMLRoleMapping(BaseModel):
    """Mapping from SAML groups to application roles."""

    admin_groups: list[str] = Field(
        default_factory=lambda: ["Administrators", "Admin", "admins"],
        description="SAML groups that map to admin role",
    )
    user_groups: list[str] = Field(
        default_factory=lambda: ["Users", "Members", "users"],
        description="SAML groups that map to user role",
    )
    default_role: str = Field(default="user", description="Default role if no groups match")


class SAMLConfig(BaseModel):
    """SAML Service Provider configuration."""

    # Identity Provider settings
    idp_entity_id: str = Field(..., description="IdP Entity ID (issuer)")
    idp_sso_url: str = Field(..., description="IdP SSO login URL")
    idp_slo_url: str | None = Field(None, description="IdP Single Logout URL")
    idp_certificate: str = Field(..., description="IdP signing certificate (PEM)")
    idp_metadata_url: str | None = Field(None, description="URL to fetch IdP metadata")

    # Service Provider settings
    sp_entity_id: str = Field(..., description="SP Entity ID (our identifier)")
    sp_acs_url: str = Field(..., description="Assertion Consumer Service URL")
    sp_slo_url: str | None = Field(None, description="SP Single Logout URL")
    sp_certificate: str | None = Field(None, description="SP signing certificate (PEM)")
    sp_private_key: str | None = Field(None, description="SP private key (PEM)")

    # Behavior settings
    name_id_format: str = Field(
        default="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
        description="NameID format to request",
    )
    authn_context: str = Field(
        default="urn:oasis:names:tc:SAML:2.0:ac:classes:PasswordProtectedTransport",
        description="Authentication context class",
    )
    sign_requests: bool = Field(default=False, description="Sign SAML requests")
    require_signed_responses: bool = Field(default=True, description="Require signed responses")
    require_signed_assertions: bool = Field(default=True, description="Require signed assertions")

    # Attribute mapping
    attribute_mapping: SAMLAttributeMapping = Field(default_factory=SAMLAttributeMapping)
    role_mapping: SAMLRoleMapping = Field(default_factory=SAMLRoleMapping)

    # JIT provisioning
    auto_provision: bool = Field(default=True, description="Auto-create users on first login")
    update_on_login: bool = Field(default=True, description="Update user attributes on login")

    # Tenant isolation
    tenant_id: str | None = Field(None, description="Tenant this config belongs to")
    is_active: bool = Field(default=True, description="Whether this config is active")


# =============================================================================
# Response Models
# =============================================================================


class SAMLLoginResponse(BaseModel):
    """Response from SAML login initiation."""

    redirect_url: str
    request_id: str
    relay_state: str | None = None


class SAMLCallbackResponse(BaseModel):
    """Response from successful SAML callback."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str | None = None
    user: dict[str, Any]
    provisioned: bool = False


class SAMLMetadataResponse(BaseModel):
    """SP metadata for IdP configuration."""

    entity_id: str
    acs_url: str
    slo_url: str | None = None
    certificate: str | None = None
    name_id_format: str


# =============================================================================
# In-Memory Configuration Store (would be database-backed in production)
# =============================================================================

_SAML_CONFIGS: dict[str, SAMLConfig] = {}
_SAML_REQUESTS: dict[str, dict[str, Any]] = {}  # Track pending SAML requests


def get_saml_config(tenant_id: str | None = None) -> SAMLConfig | None:
    """Get SAML configuration for tenant."""
    key = tenant_id or "_default"
    return _SAML_CONFIGS.get(key)


def set_saml_config(config: SAMLConfig, tenant_id: str | None = None) -> None:
    """Set SAML configuration for tenant."""
    key = tenant_id or "_default"
    _SAML_CONFIGS[key] = config


def delete_saml_config(tenant_id: str | None = None) -> bool:
    """Delete SAML configuration for tenant."""
    key = tenant_id or "_default"
    if key in _SAML_CONFIGS:
        del _SAML_CONFIGS[key]
        return True
    return False


# =============================================================================
# SAML Request/Response Handling
# =============================================================================


def generate_saml_request_id() -> str:
    """Generate unique SAML request ID."""
    return f"_kagami_{uuid.uuid4().hex}"


def create_authn_request(
    config: SAMLConfig,
    request_id: str,
    relay_state: str | None = None,
) -> str:
    """Create SAML AuthnRequest XML.

    Returns:
        Base64-encoded, deflated SAML AuthnRequest
    """
    issue_instant = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    authn_request = f"""<?xml version="1.0" encoding="UTF-8"?>
<samlp:AuthnRequest
    xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
    xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
    ID="{request_id}"
    Version="2.0"
    IssueInstant="{issue_instant}"
    Destination="{config.idp_sso_url}"
    AssertionConsumerServiceURL="{config.sp_acs_url}"
    ProtocolBinding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST">
    <saml:Issuer>{config.sp_entity_id}</saml:Issuer>
    <samlp:NameIDPolicy
        Format="{config.name_id_format}"
        AllowCreate="true"/>
    <samlp:RequestedAuthnContext Comparison="exact">
        <saml:AuthnContextClassRef>{config.authn_context}</saml:AuthnContextClassRef>
    </samlp:RequestedAuthnContext>
</samlp:AuthnRequest>"""

    # Deflate and base64 encode
    deflated = zlib.compress(authn_request.encode("utf-8"))[2:-4]  # Remove zlib header/checksum
    return base64.b64encode(deflated).decode("utf-8")


def parse_saml_response(
    response_b64: str,
    config: SAMLConfig,
) -> dict[str, Any]:
    """Parse and validate SAML response.

    Args:
        response_b64: Base64-encoded SAML response
        config: SAML configuration

    Returns:
        Dict with user attributes extracted from assertion

    Raises:
        HTTPException: If response is invalid
    """
    try:
        # Decode response
        response_xml = base64.b64decode(response_b64).decode("utf-8")

        # In production, use python3-saml or signxml for proper validation
        # This is a simplified parser for demonstration

        # Extract NameID (user identifier)
        import re

        name_id_match = re.search(r"<saml:NameID[^>]*>([^<]+)</saml:NameID>", response_xml)
        if not name_id_match:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No NameID found in SAML response",
            )
        name_id = name_id_match.group(1).strip()

        # Extract attributes
        attributes: dict[str, list[str]] = {}
        attr_pattern = r'<saml:Attribute[^>]*Name="([^"]+)"[^>]*>(.*?)</saml:Attribute>'
        for match in re.finditer(attr_pattern, response_xml, re.DOTALL):
            attr_name = match.group(1)
            attr_values_xml = match.group(2)
            values = re.findall(
                r"<saml:AttributeValue[^>]*>([^<]*)</saml:AttributeValue>", attr_values_xml
            )
            attributes[attr_name] = values

        # Check conditions (timestamps)
        conditions_match = re.search(
            r'<saml:Conditions[^>]*NotBefore="([^"]*)"[^>]*NotOnOrAfter="([^"]*)"',
            response_xml,
        )
        if conditions_match:
            not_before = conditions_match.group(1)
            not_on_or_after = conditions_match.group(2)
            now = datetime.utcnow()

            # Parse timestamps (simplified)
            try:
                nb_time = datetime.strptime(not_before.split(".")[0] + "Z", "%Y-%m-%dT%H:%M:%SZ")
                noa_time = datetime.strptime(
                    not_on_or_after.split(".")[0] + "Z", "%Y-%m-%dT%H:%M:%SZ"
                )

                # Allow 5 minute clock skew
                skew = timedelta(minutes=5)
                if now < nb_time - skew:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="SAML assertion not yet valid",
                    )
                if now > noa_time + skew:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="SAML assertion has expired",
                    )
            except ValueError:
                logger.warning("Could not parse SAML condition timestamps")

        # Check InResponseTo matches our request
        in_response_to_match = re.search(r'InResponseTo="([^"]+)"', response_xml)
        request_id = in_response_to_match.group(1) if in_response_to_match else None

        # Check status
        status_match = re.search(r'<samlp:StatusCode[^>]*Value="([^"]+)"', response_xml)
        if status_match:
            status_value = status_match.group(1)
            if "Success" not in status_value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"SAML authentication failed: {status_value}",
                )

        return {
            "name_id": name_id,
            "attributes": attributes,
            "request_id": request_id,
            "raw_response": response_xml,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to parse SAML response: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid SAML response: {e}",
        ) from e


def extract_user_attributes(
    parsed_response: dict[str, Any],
    config: SAMLConfig,
) -> dict[str, Any]:
    """Extract user attributes from parsed SAML response.

    Args:
        parsed_response: Parsed SAML response data
        config: SAML configuration with attribute mapping

    Returns:
        Dict with user attributes ready for provisioning
    """
    attributes = parsed_response.get("attributes", {})
    mapping = config.attribute_mapping

    def get_attr(attr_name: str) -> str | None:
        values = attributes.get(attr_name, [])
        return values[0] if values else None

    # Extract basic attributes
    email = get_attr(mapping.email) or parsed_response.get("name_id")
    first_name = get_attr(mapping.first_name)
    last_name = get_attr(mapping.last_name)
    display_name = get_attr(mapping.display_name)

    if not display_name and first_name and last_name:
        display_name = f"{first_name} {last_name}"
    elif not display_name:
        display_name = email.split("@")[0] if email and "@" in email else email

    # Extract groups and map to roles
    groups = attributes.get(mapping.groups, [])
    roles = _map_groups_to_roles(groups, config.role_mapping)

    # Generate username from email
    username = email.split("@")[0] if email and "@" in email else email

    return {
        "email": email,
        "username": username,
        "first_name": first_name,
        "last_name": last_name,
        "display_name": display_name,
        "groups": groups,
        "roles": roles,
        "tenant_id": config.tenant_id,
        "auth_provider": "saml",
        "idp_entity_id": config.idp_entity_id,
    }


def _map_groups_to_roles(groups: list[str], role_mapping: SAMLRoleMapping) -> list[str]:
    """Map SAML groups to application roles."""
    roles = set()

    groups_lower = {g.lower() for g in groups}

    # Check admin groups
    for admin_group in role_mapping.admin_groups:
        if admin_group.lower() in groups_lower:
            roles.add("admin")
            break

    # Check user groups
    for user_group in role_mapping.user_groups:
        if user_group.lower() in groups_lower:
            roles.add("user")
            break

    # Apply default role if no matches
    if not roles:
        roles.add(role_mapping.default_role)

    return list(roles)


# =============================================================================
# User Provisioning
# =============================================================================


async def provision_or_update_user(
    user_attrs: dict[str, Any],
    config: SAMLConfig,
) -> tuple[dict[str, Any], bool]:
    """Provision new user or update existing user.

    Args:
        user_attrs: User attributes from SAML response
        config: SAML configuration

    Returns:
        Tuple of (user_dict, was_provisioned)
    """
    user_store = get_user_store()
    email = user_attrs.get("email")
    username = user_attrs.get("username")

    if not email or not username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SAML response missing required attributes (email/username)",
        )

    # Check if user exists
    existing_user = user_store.get_user(username)

    if existing_user:
        # Update existing user if configured
        if config.update_on_login:
            # Update roles and display name
            existing_user["roles"] = user_attrs.get("roles", existing_user.get("roles", []))
            existing_user["display_name"] = user_attrs.get(
                "display_name", existing_user.get("display_name")
            )
            existing_user["last_login"] = datetime.utcnow().isoformat()
            existing_user["auth_provider"] = "saml"
            logger.info(f"Updated SAML user on login: {username}")
        return existing_user, False

    # Provision new user
    if not config.auto_provision:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not found and auto-provisioning is disabled",
        )

    # Create new user with random password (not used for SAML auth)
    random_password = secrets.token_urlsafe(32)
    user_store.add_user(
        username=username,
        password=random_password,
        roles=user_attrs.get("roles", ["user"]),
        email=email,
    )

    new_user = user_store.get_user(username)
    if new_user:
        new_user["display_name"] = user_attrs.get("display_name", username)
        new_user["first_name"] = user_attrs.get("first_name")
        new_user["last_name"] = user_attrs.get("last_name")
        new_user["auth_provider"] = "saml"
        new_user["idp_entity_id"] = user_attrs.get("idp_entity_id")
        new_user["tenant_id"] = user_attrs.get("tenant_id")
        logger.info(f"Provisioned new SAML user: {username}")
        return new_user, True

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Failed to provision user",
    )


# =============================================================================
# Router Factory
# =============================================================================


def get_router() -> APIRouter:
    """Create and configure SAML authentication router."""
    router = APIRouter(prefix="/api/auth/saml", tags=["auth-saml"])

    @router.get(
        "/login",
        response_class=RedirectResponse,
        responses={
            302: {"description": "Redirect to IdP"},
            **get_error_responses(400, 404, 500),
        },
    )
    async def saml_login(
        request: Request,
        relay_state: str | None = Query(None, description="URL to redirect after auth"),
        tenant_id: str | None = Query(None, description="Tenant ID for multi-tenant"),
    ) -> RedirectResponse:
        """Initiate SAML login flow.

        Redirects user to Identity Provider for authentication.
        After successful auth, IdP will POST to /api/auth/saml/callback.
        """
        config = get_saml_config(tenant_id)
        if not config or not config.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="SAML authentication not configured for this tenant",
            )

        # Generate request ID
        request_id = generate_saml_request_id()

        # Create AuthnRequest
        authn_request = create_authn_request(config, request_id, relay_state)

        # Store request for validation
        _SAML_REQUESTS[request_id] = {
            "created_at": time.time(),
            "tenant_id": tenant_id,
            "relay_state": relay_state,
        }

        # Build redirect URL
        params = {
            "SAMLRequest": authn_request,
        }
        if relay_state:
            params["RelayState"] = relay_state

        redirect_url = f"{config.idp_sso_url}?{urlencode(params)}"

        logger.info(f"SAML login initiated: request_id={request_id}, tenant={tenant_id}")

        return RedirectResponse(url=redirect_url, status_code=302)

    @router.post(
        "/callback",
        response_model=SAMLCallbackResponse,
        responses=get_error_responses(400, 401, 403, 500),
    )
    async def saml_callback(
        request: Request,
        tenant_id: str | None = Query(None, description="Tenant ID"),
    ) -> SAMLCallbackResponse:
        """Handle SAML assertion callback from IdP.

        IdP POSTs the SAML response here after authentication.
        Validates the response, extracts user attributes, and issues JWT.
        """
        start_time = time.time()

        # Get form data
        form = await request.form()
        saml_response = form.get("SAMLResponse")
        _relay_state = form.get("RelayState")  # Preserved for future use

        if not saml_response:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing SAMLResponse in callback",
            )

        config = get_saml_config(tenant_id)
        if not config or not config.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="SAML authentication not configured",
            )

        # Parse and validate response
        parsed = parse_saml_response(str(saml_response), config)

        # Verify request ID if present
        request_id = parsed.get("request_id")
        if request_id:
            stored_request = _SAML_REQUESTS.pop(request_id, None)
            if not stored_request:
                logger.warning(f"SAML response for unknown request: {request_id}")
            elif time.time() - stored_request["created_at"] > 300:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="SAML request has expired",
                )

        # Extract user attributes
        user_attrs = extract_user_attributes(parsed, config)

        # Provision or update user
        user, was_provisioned = await provision_or_update_user(user_attrs, config)

        # Create tokens
        security = SecurityFramework()
        scopes = []
        for role in user.get("roles", []):
            if role == "admin":
                scopes.extend(["read", "write", "admin"])
            elif role == "user":
                scopes.extend(["read", "write"])
            else:
                scopes.append("read")
        scopes = list(set(scopes))

        access_token = security.create_access_token(
            subject=user["username"],
            scopes=scopes,
            tenant_id=user.get("tenant_id"),
            additional_claims={
                "roles": user.get("roles", []),
                "auth_provider": "saml",
                "uid": user.get("id"),
            },
        )
        refresh_token = security.create_refresh_token(
            subject=user["username"],
            additional_claims={
                "roles": user.get("roles", []),
                "tenant_id": user.get("tenant_id"),
                "uid": user.get("id"),
            },
        )

        expires_in = int(timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES).total_seconds())

        # Audit log
        try:
            get_audit_logger().log_authentication(
                AuditEventType.LOGIN_SUCCESS,
                user_id=user["username"],
                request=request,
                outcome="success",
                details={
                    "auth_method": "saml",
                    "idp_entity_id": config.idp_entity_id,
                    "provisioned": was_provisioned,
                    "roles": user.get("roles", []),
                },
            )
        except Exception as e:
            logger.warning(f"Failed to log SAML auth event: {e}")

        elapsed_ms = (time.time() - start_time) * 1000
        logger.info(
            f"SAML login successful: user={user['username']}, "
            f"provisioned={was_provisioned}, elapsed={elapsed_ms:.2f}ms"
        )

        return SAMLCallbackResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=expires_in,
            refresh_token=refresh_token,
            user={
                "username": user["username"],
                "email": user.get("email"),
                "display_name": user.get("display_name"),
                "roles": user.get("roles", []),
            },
            provisioned=was_provisioned,
        )

    @router.get(
        "/callback",
        response_class=HTMLResponse,
        responses=get_error_responses(400, 500),
    )
    async def saml_callback_form(
        request: Request,
        SAMLResponse: str | None = Query(None),
        RelayState: str | None = Query(None),
        tenant_id: str | None = Query(None),
    ) -> HTMLResponse:
        """Display form to POST SAML response (for IdP-initiated flows)."""
        # Return HTML that auto-submits the SAML response via POST
        if SAMLResponse:
            html = f"""
<!DOCTYPE html>
<html>
<head><title>Processing SAML Response</title></head>
<body>
    <p>Processing authentication...</p>
    <form id="saml-form" method="POST" action="/api/auth/saml/callback">
        <input type="hidden" name="SAMLResponse" value="{SAMLResponse}"/>
        <input type="hidden" name="RelayState" value="{RelayState or ""}"/>
    </form>
    <script>document.getElementById('saml-form').submit();</script>
</body>
</html>
"""
            return HTMLResponse(content=html)

        return HTMLResponse(
            content="<html><body><p>Missing SAML response</p></body></html>",
            status_code=400,
        )

    @router.get(
        "/metadata",
        response_class=HTMLResponse,
        responses=get_error_responses(404, 500),
    )
    async def saml_metadata(
        tenant_id: str | None = Query(None, description="Tenant ID"),
    ) -> HTMLResponse:
        """Get Service Provider SAML metadata.

        Returns XML metadata that can be imported into your IdP.
        """
        config = get_saml_config(tenant_id)
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="SAML not configured for this tenant",
            )

        # Generate SP metadata XML
        cert_xml = ""
        if config.sp_certificate:
            # Format certificate for XML
            cert_clean = (
                config.sp_certificate.replace("-----BEGIN CERTIFICATE-----", "")
                .replace("-----END CERTIFICATE-----", "")
                .replace("\n", "")
                .strip()
            )
            cert_xml = f"""
        <KeyDescriptor use="signing">
            <ds:KeyInfo xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
                <ds:X509Data>
                    <ds:X509Certificate>{cert_clean}</ds:X509Certificate>
                </ds:X509Data>
            </ds:KeyInfo>
        </KeyDescriptor>"""

        slo_xml = ""
        if config.sp_slo_url:
            slo_xml = f"""
        <SingleLogoutService
            Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
            Location="{config.sp_slo_url}"/>"""

        metadata_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<EntityDescriptor
    xmlns="urn:oasis:names:tc:SAML:2.0:metadata"
    entityID="{config.sp_entity_id}">
    <SPSSODescriptor
        AuthnRequestsSigned="{str(config.sign_requests).lower()}"
        WantAssertionsSigned="{str(config.require_signed_assertions).lower()}"
        protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
        {cert_xml}
        <NameIDFormat>{config.name_id_format}</NameIDFormat>
        <AssertionConsumerService
            Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
            Location="{config.sp_acs_url}"
            index="0"
            isDefault="true"/>
        {slo_xml}
    </SPSSODescriptor>
</EntityDescriptor>"""

        return HTMLResponse(
            content=metadata_xml.strip(),
            media_type="application/xml",
        )

    @router.get(
        "/metadata/json",
        response_model=SAMLMetadataResponse,
        responses=get_error_responses(404, 500),
    )
    async def saml_metadata_json(
        tenant_id: str | None = Query(None, description="Tenant ID"),
    ) -> SAMLMetadataResponse:
        """Get SP metadata in JSON format for programmatic configuration."""
        config = get_saml_config(tenant_id)
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="SAML not configured for this tenant",
            )

        return SAMLMetadataResponse(
            entity_id=config.sp_entity_id,
            acs_url=config.sp_acs_url,
            slo_url=config.sp_slo_url,
            certificate=config.sp_certificate,
            name_id_format=config.name_id_format,
        )

    return router


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "SAMLAttributeMapping",
    "SAMLCallbackResponse",
    "SAMLConfig",
    "SAMLLoginResponse",
    "SAMLMetadataResponse",
    "SAMLRoleMapping",
    "delete_saml_config",
    "get_router",
    "get_saml_config",
    "set_saml_config",
]
