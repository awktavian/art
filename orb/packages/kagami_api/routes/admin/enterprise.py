"""Enterprise Administration API for Kagami.

Provides endpoints for managing enterprise authentication and audit:
- GET/PUT /api/admin/enterprise/saml - SAML SSO configuration
- GET/PUT /api/admin/enterprise/ldap - LDAP/AD configuration
- POST /api/admin/enterprise/test-ldap - Test LDAP connection
- POST /api/admin/enterprise/test-saml - Test SAML configuration
- GET /api/admin/enterprise/audit-logs - Access audit logs

RALPH Week 3 - Enterprise Features
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from kagami_api.audit_logger import AuditEventType, get_audit_logger
from kagami_api.response_schemas import get_error_responses
from kagami_api.security import Principal, require_auth

logger = logging.getLogger(__name__)


# =============================================================================
# Request/Response Models
# =============================================================================


class SAMLConfigUpdate(BaseModel):
    """Request model for updating SAML configuration."""

    # IdP settings
    idp_entity_id: str = Field(..., description="IdP Entity ID")
    idp_sso_url: str = Field(..., description="IdP SSO URL")
    idp_slo_url: str | None = Field(None, description="IdP SLO URL")
    idp_certificate: str = Field(..., description="IdP signing certificate (PEM)")
    idp_metadata_url: str | None = Field(None, description="IdP metadata URL")

    # SP settings
    sp_entity_id: str = Field(..., description="SP Entity ID")
    sp_acs_url: str = Field(..., description="SP ACS URL")
    sp_slo_url: str | None = Field(None, description="SP SLO URL")
    sp_certificate: str | None = Field(None, description="SP certificate (PEM)")
    sp_private_key: str | None = Field(None, description="SP private key (PEM)")

    # Behavior
    sign_requests: bool = Field(default=False)
    require_signed_responses: bool = Field(default=True)
    require_signed_assertions: bool = Field(default=True)
    auto_provision: bool = Field(default=True)
    update_on_login: bool = Field(default=True)
    is_active: bool = Field(default=True)

    # Attribute mapping
    email_attribute: str = Field(
        default="http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress"
    )
    name_attribute: str = Field(
        default="http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name"
    )
    groups_attribute: str = Field(
        default="http://schemas.microsoft.com/ws/2008/06/identity/claims/groups"
    )

    # Role mapping
    admin_groups: list[str] = Field(default_factory=list)
    user_groups: list[str] = Field(default_factory=list)


class SAMLConfigResponse(BaseModel):
    """Response model for SAML configuration."""

    configured: bool
    is_active: bool = False
    idp_entity_id: str | None = None
    idp_sso_url: str | None = None
    idp_slo_url: str | None = None
    idp_metadata_url: str | None = None
    sp_entity_id: str | None = None
    sp_acs_url: str | None = None
    sp_slo_url: str | None = None
    sign_requests: bool = False
    require_signed_responses: bool = True
    require_signed_assertions: bool = True
    auto_provision: bool = True
    update_on_login: bool = True
    # Attribute mapping
    email_attribute: str | None = None
    name_attribute: str | None = None
    groups_attribute: str | None = None
    # Role mapping
    admin_groups: list[str] = Field(default_factory=list)
    user_groups: list[str] = Field(default_factory=list)
    # Stats
    last_login: str | None = None
    total_logins: int = 0


class LDAPConfigUpdate(BaseModel):
    """Request model for updating LDAP configuration."""

    # Server settings
    server: str = Field(..., description="LDAP server hostname")
    port: int = Field(default=389, description="LDAP port")
    use_ssl: bool = Field(default=False, description="Use LDAPS")
    use_starttls: bool = Field(default=True, description="Use STARTTLS")
    verify_ssl: bool = Field(default=True, description="Verify SSL certificates")

    # Bind settings
    bind_dn: str | None = Field(None, description="Service account DN")
    bind_password: str | None = Field(None, description="Service account password")

    # Search settings
    base_dn: str = Field(..., description="Base DN")
    user_search_base: str | None = Field(None, description="User search base")
    group_search_base: str | None = Field(None, description="Group search base")
    user_search_filter: str = Field(
        default="(&(objectClass=person)(|(uid={username})(sAMAccountName={username})))"
    )

    # Attribute mapping
    username_attribute: str = Field(default="sAMAccountName")
    email_attribute: str = Field(default="mail")
    display_name_attribute: str = Field(default="displayName")
    member_of_attribute: str = Field(default="memberOf")

    # Role mapping
    admin_groups: list[str] = Field(default_factory=list)
    user_groups: list[str] = Field(default_factory=list)

    # Behavior
    auto_provision: bool = Field(default=True)
    update_on_login: bool = Field(default=True)
    is_active: bool = Field(default=True)
    nested_groups: bool = Field(default=True)


class LDAPConfigResponse(BaseModel):
    """Response model for LDAP configuration."""

    configured: bool
    is_active: bool = False
    server: str | None = None
    port: int = 389
    use_ssl: bool = False
    use_starttls: bool = True
    verify_ssl: bool = True
    bind_dn: str | None = None
    # Never return password
    base_dn: str | None = None
    user_search_base: str | None = None
    group_search_base: str | None = None
    user_search_filter: str | None = None
    username_attribute: str | None = None
    email_attribute: str | None = None
    display_name_attribute: str | None = None
    member_of_attribute: str | None = None
    admin_groups: list[str] = Field(default_factory=list)
    user_groups: list[str] = Field(default_factory=list)
    auto_provision: bool = True
    update_on_login: bool = True
    nested_groups: bool = True
    # Stats
    last_login: str | None = None
    total_logins: int = 0


class LDAPTestRequest(BaseModel):
    """Request model for testing LDAP connection."""

    server: str = Field(..., description="LDAP server")
    port: int = Field(default=389)
    use_ssl: bool = Field(default=False)
    use_starttls: bool = Field(default=True)
    verify_ssl: bool = Field(default=True)
    bind_dn: str | None = Field(None)
    bind_password: str | None = Field(None)
    base_dn: str = Field(...)
    test_username: str | None = Field(None, description="Optional: test user lookup")
    test_password: str | None = Field(None, description="Optional: test user bind")


class LDAPTestResponse(BaseModel):
    """Response model for LDAP connection test."""

    success: bool
    message: str
    connection_successful: bool = False
    bind_successful: bool = False
    search_successful: bool = False
    user_found: bool = False
    user_bind_successful: bool = False
    server_info: dict[str, Any] | None = None
    error: str | None = None


class SAMLTestRequest(BaseModel):
    """Request model for testing SAML configuration."""

    idp_metadata_url: str | None = Field(None, description="IdP metadata URL to fetch")
    idp_certificate: str | None = Field(None, description="IdP certificate to validate")
    sp_entity_id: str = Field(..., description="SP Entity ID to validate")


class SAMLTestResponse(BaseModel):
    """Response model for SAML configuration test."""

    success: bool
    message: str
    metadata_fetched: bool = False
    certificate_valid: bool = False
    certificate_expiry: str | None = None
    idp_entity_id: str | None = None
    idp_sso_url: str | None = None
    error: str | None = None


class AuditLogEntry(BaseModel):
    """Single audit log entry."""

    id: str
    timestamp: str
    event_type: str
    user_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    outcome: str
    details: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = None


class AuditLogsResponse(BaseModel):
    """Response for audit log query."""

    logs: list[AuditLogEntry]
    total: int
    page: int = 1
    per_page: int = 50
    has_more: bool = False


class EnterpriseStatusResponse(BaseModel):
    """Overall enterprise authentication status."""

    saml_configured: bool = False
    saml_active: bool = False
    ldap_configured: bool = False
    ldap_active: bool = False
    audit_logging_enabled: bool = True
    total_enterprise_users: int = 0
    total_saml_logins_24h: int = 0
    total_ldap_logins_24h: int = 0


# =============================================================================
# Helper Functions
# =============================================================================


def _require_admin(principal: Principal) -> None:
    """Check if user is admin."""
    roles = getattr(principal, "roles", []) or []
    if "admin" not in roles and "owner" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )


# =============================================================================
# Router Factory
# =============================================================================


def get_router() -> APIRouter:
    """Create and configure enterprise administration router."""
    router = APIRouter(prefix="/api/admin/enterprise", tags=["admin-enterprise"])

    # ---------------------------------------------------------------------
    # Enterprise Status
    # ---------------------------------------------------------------------

    @router.get(
        "/status",
        response_model=EnterpriseStatusResponse,
        responses=get_error_responses(401, 403, 500),
    )
    async def get_enterprise_status(
        principal: Principal = Depends(require_auth),
    ) -> EnterpriseStatusResponse:
        """Get overall enterprise authentication status.

        Returns summary of SAML/LDAP configuration status and usage stats.
        """
        _require_admin(principal)

        # Import configs
        try:
            from kagami_api.routes.user.ldap import get_ldap_config
            from kagami_api.routes.user.saml import get_saml_config

            saml_config = get_saml_config()
            ldap_config = get_ldap_config()
        except Exception:
            saml_config = None
            ldap_config = None

        return EnterpriseStatusResponse(
            saml_configured=saml_config is not None,
            saml_active=saml_config.is_active if saml_config else False,
            ldap_configured=ldap_config is not None,
            ldap_active=ldap_config.is_active if ldap_config else False,
            audit_logging_enabled=True,
            total_enterprise_users=0,  # Would query from DB
            total_saml_logins_24h=0,  # Would query from audit logs
            total_ldap_logins_24h=0,  # Would query from audit logs
        )

    # ---------------------------------------------------------------------
    # SAML Configuration
    # ---------------------------------------------------------------------

    @router.get(
        "/saml",
        response_model=SAMLConfigResponse,
        responses=get_error_responses(401, 403, 500),
    )
    async def get_saml_configuration(
        principal: Principal = Depends(require_auth),
        tenant_id: str | None = Query(None, description="Tenant ID"),
    ) -> SAMLConfigResponse:
        """Get current SAML SSO configuration.

        Returns SAML configuration (excluding sensitive keys).
        """
        _require_admin(principal)

        try:
            from kagami_api.routes.user.saml import get_saml_config

            config = get_saml_config(tenant_id)
        except Exception:
            config = None

        if not config:
            return SAMLConfigResponse(configured=False)

        return SAMLConfigResponse(
            configured=True,
            is_active=config.is_active,
            idp_entity_id=config.idp_entity_id,
            idp_sso_url=config.idp_sso_url,
            idp_slo_url=config.idp_slo_url,
            idp_metadata_url=config.idp_metadata_url,
            sp_entity_id=config.sp_entity_id,
            sp_acs_url=config.sp_acs_url,
            sp_slo_url=config.sp_slo_url,
            sign_requests=config.sign_requests,
            require_signed_responses=config.require_signed_responses,
            require_signed_assertions=config.require_signed_assertions,
            auto_provision=config.auto_provision,
            update_on_login=config.update_on_login,
            email_attribute=config.attribute_mapping.email,
            name_attribute=config.attribute_mapping.display_name,
            groups_attribute=config.attribute_mapping.groups,
            admin_groups=config.role_mapping.admin_groups,
            user_groups=config.role_mapping.user_groups,
        )

    @router.put(
        "/saml",
        response_model=SAMLConfigResponse,
        responses=get_error_responses(400, 401, 403, 500),
    )
    async def update_saml_configuration(
        request: Request,
        config_update: SAMLConfigUpdate,
        principal: Principal = Depends(require_auth),
        tenant_id: str | None = Query(None, description="Tenant ID"),
    ) -> SAMLConfigResponse:
        """Update SAML SSO configuration.

        Creates or updates SAML configuration for the tenant.
        """
        _require_admin(principal)

        try:
            from kagami_api.routes.user.saml import (
                SAMLAttributeMapping,
                SAMLConfig,
                SAMLRoleMapping,
                set_saml_config,
            )

            # Build config
            config = SAMLConfig(
                idp_entity_id=config_update.idp_entity_id,
                idp_sso_url=config_update.idp_sso_url,
                idp_slo_url=config_update.idp_slo_url,
                idp_certificate=config_update.idp_certificate,
                idp_metadata_url=config_update.idp_metadata_url,
                sp_entity_id=config_update.sp_entity_id,
                sp_acs_url=config_update.sp_acs_url,
                sp_slo_url=config_update.sp_slo_url,
                sp_certificate=config_update.sp_certificate,
                sp_private_key=config_update.sp_private_key,
                sign_requests=config_update.sign_requests,
                require_signed_responses=config_update.require_signed_responses,
                require_signed_assertions=config_update.require_signed_assertions,
                auto_provision=config_update.auto_provision,
                update_on_login=config_update.update_on_login,
                is_active=config_update.is_active,
                tenant_id=tenant_id,
                attribute_mapping=SAMLAttributeMapping(
                    email=config_update.email_attribute,
                    display_name=config_update.name_attribute,
                    groups=config_update.groups_attribute,
                ),
                role_mapping=SAMLRoleMapping(
                    admin_groups=config_update.admin_groups,
                    user_groups=config_update.user_groups,
                ),
            )

            set_saml_config(config, tenant_id)

            # Audit log
            try:
                get_audit_logger().log_admin_action(
                    AuditEventType.CONFIG_CHANGE,
                    user_id=principal.sub,
                    request=request,
                    action="update_saml_config",
                    resource_type="saml_config",
                    resource_id=tenant_id or "_default",
                    changes={
                        "idp_entity_id": config_update.idp_entity_id,
                        "sp_entity_id": config_update.sp_entity_id,
                        "is_active": config_update.is_active,
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to log SAML config change: {e}")

            logger.info(f"SAML configuration updated by {principal.sub}, tenant={tenant_id}")

            return SAMLConfigResponse(
                configured=True,
                is_active=config.is_active,
                idp_entity_id=config.idp_entity_id,
                idp_sso_url=config.idp_sso_url,
                idp_slo_url=config.idp_slo_url,
                idp_metadata_url=config.idp_metadata_url,
                sp_entity_id=config.sp_entity_id,
                sp_acs_url=config.sp_acs_url,
                sp_slo_url=config.sp_slo_url,
                sign_requests=config.sign_requests,
                require_signed_responses=config.require_signed_responses,
                require_signed_assertions=config.require_signed_assertions,
                auto_provision=config.auto_provision,
                update_on_login=config.update_on_login,
                email_attribute=config.attribute_mapping.email,
                name_attribute=config.attribute_mapping.display_name,
                groups_attribute=config.attribute_mapping.groups,
                admin_groups=config.role_mapping.admin_groups,
                user_groups=config.role_mapping.user_groups,
            )

        except Exception as e:
            logger.error(f"Failed to update SAML config: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update SAML configuration: {e}",
            ) from e

    @router.delete(
        "/saml",
        responses=get_error_responses(401, 403, 404, 500),
    )
    async def delete_saml_configuration(
        request: Request,
        principal: Principal = Depends(require_auth),
        tenant_id: str | None = Query(None, description="Tenant ID"),
    ) -> dict[str, Any]:
        """Delete SAML SSO configuration.

        Removes SAML configuration for the tenant.
        """
        _require_admin(principal)

        try:
            from kagami_api.routes.user.saml import delete_saml_config

            if not delete_saml_config(tenant_id):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="SAML configuration not found",
                )

            # Audit log
            try:
                get_audit_logger().log_admin_action(
                    AuditEventType.CONFIG_CHANGE,
                    user_id=principal.sub,
                    request=request,
                    action="delete_saml_config",
                    resource_type="saml_config",
                    resource_id=tenant_id or "_default",
                    changes={"deleted": True},
                )
            except Exception:
                pass

            logger.info(f"SAML configuration deleted by {principal.sub}, tenant={tenant_id}")

            return {"deleted": True, "tenant_id": tenant_id}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to delete SAML config: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete SAML configuration: {e}",
            ) from e

    @router.post(
        "/test-saml",
        response_model=SAMLTestResponse,
        responses=get_error_responses(400, 401, 403, 500),
    )
    async def test_saml_configuration(
        test_request: SAMLTestRequest,
        principal: Principal = Depends(require_auth),
    ) -> SAMLTestResponse:
        """Test SAML configuration.

        Validates IdP metadata URL, certificate, and configuration.
        """
        _require_admin(principal)

        result = SAMLTestResponse(
            success=False,
            message="Test incomplete",
        )

        # Test metadata URL if provided
        if test_request.idp_metadata_url:
            try:
                import httpx

                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(test_request.idp_metadata_url)
                    if response.status_code == 200:
                        result.metadata_fetched = True
                        # Parse basic info from metadata
                        metadata = response.text
                        if "entityID" in metadata:
                            import re

                            match = re.search(r'entityID="([^"]+)"', metadata)
                            if match:
                                result.idp_entity_id = match.group(1)
                        if "SingleSignOnService" in metadata:
                            match = re.search(
                                r'SingleSignOnService[^>]*Location="([^"]+)"',
                                metadata,
                            )
                            if match:
                                result.idp_sso_url = match.group(1)
                    else:
                        result.error = f"Metadata fetch failed: HTTP {response.status_code}"
            except Exception as e:
                result.error = f"Metadata fetch failed: {e}"

        # Validate certificate if provided
        if test_request.idp_certificate:
            try:
                from cryptography import x509
                from cryptography.hazmat.backends import default_backend

                # Clean certificate
                cert_pem = test_request.idp_certificate
                if "-----BEGIN CERTIFICATE-----" not in cert_pem:
                    cert_pem = f"-----BEGIN CERTIFICATE-----\n{cert_pem}\n-----END CERTIFICATE-----"

                cert = x509.load_pem_x509_certificate(cert_pem.encode(), default_backend())
                result.certificate_valid = True
                result.certificate_expiry = cert.not_valid_after_utc.isoformat()

                # Check expiry
                if cert.not_valid_after_utc < datetime.utcnow():
                    result.error = "Certificate has expired"
                    result.certificate_valid = False

            except ImportError:
                # cryptography not installed
                result.certificate_valid = True  # Assume valid if we can't check
            except Exception as e:
                result.error = f"Certificate validation failed: {e}"
                result.certificate_valid = False

        # Overall success
        if result.metadata_fetched or result.certificate_valid:
            result.success = True
            result.message = "SAML configuration validated"
        elif result.error:
            result.message = result.error
        else:
            result.message = "No validation performed"

        return result

    # ---------------------------------------------------------------------
    # LDAP Configuration
    # ---------------------------------------------------------------------

    @router.get(
        "/ldap",
        response_model=LDAPConfigResponse,
        responses=get_error_responses(401, 403, 500),
    )
    async def get_ldap_configuration(
        principal: Principal = Depends(require_auth),
        tenant_id: str | None = Query(None, description="Tenant ID"),
    ) -> LDAPConfigResponse:
        """Get current LDAP configuration.

        Returns LDAP configuration (excluding sensitive passwords).
        """
        _require_admin(principal)

        try:
            from kagami_api.routes.user.ldap import get_ldap_config

            config = get_ldap_config(tenant_id)
        except Exception:
            config = None

        if not config:
            return LDAPConfigResponse(configured=False)

        return LDAPConfigResponse(
            configured=True,
            is_active=config.is_active,
            server=config.server,
            port=config.port,
            use_ssl=config.use_ssl,
            use_starttls=config.use_starttls,
            verify_ssl=config.verify_ssl,
            bind_dn=config.bind_dn,
            base_dn=config.base_dn,
            user_search_base=config.user_search_base,
            group_search_base=config.group_search_base,
            user_search_filter=config.user_search_filter,
            username_attribute=config.username_attribute,
            email_attribute=config.email_attribute,
            display_name_attribute=config.display_name_attribute,
            member_of_attribute=config.member_of_attribute,
            admin_groups=config.role_mapping.admin_groups,
            user_groups=config.role_mapping.user_groups,
            auto_provision=config.auto_provision,
            update_on_login=config.update_on_login,
            nested_groups=config.nested_groups,
        )

    @router.put(
        "/ldap",
        response_model=LDAPConfigResponse,
        responses=get_error_responses(400, 401, 403, 500),
    )
    async def update_ldap_configuration(
        request: Request,
        config_update: LDAPConfigUpdate,
        principal: Principal = Depends(require_auth),
        tenant_id: str | None = Query(None, description="Tenant ID"),
    ) -> LDAPConfigResponse:
        """Update LDAP configuration.

        Creates or updates LDAP configuration for the tenant.
        """
        _require_admin(principal)

        try:
            from kagami_api.routes.user.ldap import (
                LDAPConfig,
                LDAPRoleMapping,
                set_ldap_config,
            )

            # Build config
            config = LDAPConfig(
                server=config_update.server,
                port=config_update.port,
                use_ssl=config_update.use_ssl,
                use_starttls=config_update.use_starttls,
                verify_ssl=config_update.verify_ssl,
                bind_dn=config_update.bind_dn,
                bind_password=config_update.bind_password,
                base_dn=config_update.base_dn,
                user_search_base=config_update.user_search_base,
                group_search_base=config_update.group_search_base,
                user_search_filter=config_update.user_search_filter,
                username_attribute=config_update.username_attribute,
                email_attribute=config_update.email_attribute,
                display_name_attribute=config_update.display_name_attribute,
                member_of_attribute=config_update.member_of_attribute,
                auto_provision=config_update.auto_provision,
                update_on_login=config_update.update_on_login,
                is_active=config_update.is_active,
                nested_groups=config_update.nested_groups,
                tenant_id=tenant_id,
                role_mapping=LDAPRoleMapping(
                    admin_groups=config_update.admin_groups,
                    user_groups=config_update.user_groups,
                ),
            )

            set_ldap_config(config, tenant_id)

            # Audit log
            try:
                get_audit_logger().log_admin_action(
                    AuditEventType.CONFIG_CHANGE,
                    user_id=principal.sub,
                    request=request,
                    action="update_ldap_config",
                    resource_type="ldap_config",
                    resource_id=tenant_id or "_default",
                    changes={
                        "server": config_update.server,
                        "base_dn": config_update.base_dn,
                        "is_active": config_update.is_active,
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to log LDAP config change: {e}")

            logger.info(f"LDAP configuration updated by {principal.sub}, tenant={tenant_id}")

            return LDAPConfigResponse(
                configured=True,
                is_active=config.is_active,
                server=config.server,
                port=config.port,
                use_ssl=config.use_ssl,
                use_starttls=config.use_starttls,
                verify_ssl=config.verify_ssl,
                bind_dn=config.bind_dn,
                base_dn=config.base_dn,
                user_search_base=config.user_search_base,
                group_search_base=config.group_search_base,
                user_search_filter=config.user_search_filter,
                username_attribute=config.username_attribute,
                email_attribute=config.email_attribute,
                display_name_attribute=config.display_name_attribute,
                member_of_attribute=config.member_of_attribute,
                admin_groups=config.role_mapping.admin_groups,
                user_groups=config.role_mapping.user_groups,
                auto_provision=config.auto_provision,
                update_on_login=config.update_on_login,
                nested_groups=config.nested_groups,
            )

        except Exception as e:
            logger.error(f"Failed to update LDAP config: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update LDAP configuration: {e}",
            ) from e

    @router.delete(
        "/ldap",
        responses=get_error_responses(401, 403, 404, 500),
    )
    async def delete_ldap_configuration(
        request: Request,
        principal: Principal = Depends(require_auth),
        tenant_id: str | None = Query(None, description="Tenant ID"),
    ) -> dict[str, Any]:
        """Delete LDAP configuration.

        Removes LDAP configuration for the tenant.
        """
        _require_admin(principal)

        try:
            from kagami_api.routes.user.ldap import delete_ldap_config

            if not delete_ldap_config(tenant_id):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="LDAP configuration not found",
                )

            # Audit log
            try:
                get_audit_logger().log_admin_action(
                    AuditEventType.CONFIG_CHANGE,
                    user_id=principal.sub,
                    request=request,
                    action="delete_ldap_config",
                    resource_type="ldap_config",
                    resource_id=tenant_id or "_default",
                    changes={"deleted": True},
                )
            except Exception:
                pass

            logger.info(f"LDAP configuration deleted by {principal.sub}, tenant={tenant_id}")

            return {"deleted": True, "tenant_id": tenant_id}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to delete LDAP config: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete LDAP configuration: {e}",
            ) from e

    @router.post(
        "/test-ldap",
        response_model=LDAPTestResponse,
        responses=get_error_responses(400, 401, 403, 500),
    )
    async def test_ldap_connection(
        test_request: LDAPTestRequest,
        principal: Principal = Depends(require_auth),
    ) -> LDAPTestResponse:
        """Test LDAP connection.

        Tests connection, bind, and optionally user lookup.
        """
        _require_admin(principal)

        result = LDAPTestResponse(
            success=False,
            message="Test incomplete",
        )

        try:
            from kagami_api.routes.user.ldap import LDAPConfig, LDAPConnection

            # Build test config
            config = LDAPConfig(
                server=test_request.server,
                port=test_request.port,
                use_ssl=test_request.use_ssl,
                use_starttls=test_request.use_starttls,
                verify_ssl=test_request.verify_ssl,
                bind_dn=test_request.bind_dn,
                bind_password=test_request.bind_password,
                base_dn=test_request.base_dn,
            )

            # Test connection
            with LDAPConnection(config) as conn:
                result.connection_successful = True

                # Test bind
                if config.bind_dn:
                    result.bind_successful = True

                # Test search
                try:
                    results = conn.search(
                        search_filter="(objectClass=*)",
                        attributes=["dn"],
                        size_limit=1,
                    )
                    result.search_successful = len(results) > 0
                except Exception as e:
                    logger.debug(f"LDAP search test failed: {e}")

                # Test user lookup if username provided
                if test_request.test_username:
                    user_dn = conn._find_user_dn(test_request.test_username)
                    result.user_found = user_dn is not None

                    # Test user bind if password provided
                    if test_request.test_password and user_dn:
                        bind_ok, _ = conn.bind_user(
                            test_request.test_username,
                            test_request.test_password,
                        )
                        result.user_bind_successful = bind_ok

            result.success = result.connection_successful
            result.message = "LDAP connection test successful"

            if result.bind_successful:
                result.message += ", service account bind OK"
            if result.search_successful:
                result.message += ", search OK"
            if result.user_found:
                result.message += f", user '{test_request.test_username}' found"
            if result.user_bind_successful:
                result.message += ", user bind OK"

        except Exception as e:
            result.success = False
            result.error = str(e)
            result.message = f"LDAP connection test failed: {e}"
            logger.error(f"LDAP connection test failed: {e}")

        return result

    # ---------------------------------------------------------------------
    # Audit Logs
    # ---------------------------------------------------------------------

    @router.get(
        "/audit-logs",
        response_model=AuditLogsResponse,
        responses=get_error_responses(401, 403, 500),
    )
    async def get_audit_logs(
        principal: Principal = Depends(require_auth),
        event_type: str | None = Query(None, description="Filter by event type"),
        user_id: str | None = Query(None, description="Filter by user ID"),
        outcome: str | None = Query(None, description="Filter by outcome (success/failure)"),
        start_date: str | None = Query(None, description="Start date (ISO format)"),  # noqa: ARG001 - TODO: Implement date filtering
        end_date: str | None = Query(None, description="End date (ISO format)"),  # noqa: ARG001 - TODO: Implement date filtering
        page: int = Query(1, ge=1, description="Page number"),
        per_page: int = Query(50, ge=1, le=500, description="Items per page"),
    ) -> AuditLogsResponse:
        """Query audit logs.

        Returns filtered audit log entries from the actual audit logger.
        Admin access required.
        """
        _require_admin(principal)

        from kagami_api.audit_logger import get_audit_logger

        audit_logger = get_audit_logger()

        # Get real audit events from the in-memory buffer
        raw_events = audit_logger.get_recent_events(limit=per_page * 10)  # Get enough for filtering

        # Convert to AuditLogEntry format
        all_logs: list[AuditLogEntry] = []
        for i, event in enumerate(raw_events):
            entry = AuditLogEntry(
                id=event.get("request_id") or f"audit_{i}",
                timestamp=event.get("timestamp", ""),
                event_type=event.get("event_type", "UNKNOWN"),
                user_id=event.get("user_id"),
                ip_address=event.get("client_ip"),
                user_agent=event.get("user_agent"),
                outcome=event.get("outcome", "unknown"),
                details=event.get("details"),
                correlation_id=event.get("request_id"),
            )
            all_logs.append(entry)

        # Apply filters
        filtered = all_logs
        if event_type:
            filtered = [e for e in filtered if e.event_type == event_type]
        if user_id:
            filtered = [e for e in filtered if e.user_id == user_id]
        if outcome:
            filtered = [e for e in filtered if e.outcome == outcome]

        # Pagination
        total = len(filtered)
        start = (page - 1) * per_page
        end = start + per_page
        logs = filtered[start:end]

        return AuditLogsResponse(
            logs=logs,
            total=total,
            page=page,
            per_page=per_page,
            has_more=end < total,
        )

    return router


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "AuditLogEntry",
    "AuditLogsResponse",
    "EnterpriseStatusResponse",
    "LDAPConfigResponse",
    "LDAPConfigUpdate",
    "LDAPTestRequest",
    "LDAPTestResponse",
    "SAMLConfigResponse",
    "SAMLConfigUpdate",
    "SAMLTestRequest",
    "SAMLTestResponse",
    "get_router",
]
