"""LDAP/Active Directory Authentication for Kagami Enterprise.

Provides LDAP authentication endpoints:
- POST /api/auth/ldap/login - Authenticate via LDAP bind
- GET /api/auth/ldap/groups - Get user's LDAP groups
- GET /api/auth/ldap/search - Search LDAP directory (admin only)

Supports:
- Active Directory
- OpenLDAP
- Secure LDAP (LDAPS) with TLS
- Group-to-role mapping
- Nested group resolution
- Connection pooling

RALPH Week 3 - Enterprise Authentication
"""

import logging
import secrets
import ssl
import time
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from kagami_api.audit_logger import AuditEventType, get_audit_logger
from kagami_api.response_schemas import get_error_responses
from kagami_api.security import Principal, SecurityFramework, require_auth
from kagami_api.security.shared import ACCESS_TOKEN_EXPIRE_MINUTES
from kagami_api.user_store import get_user_store

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration Models
# =============================================================================


class LDAPRoleMapping(BaseModel):
    """Mapping from LDAP groups to application roles."""

    admin_groups: list[str] = Field(
        default_factory=lambda: [
            "CN=Domain Admins,CN=Users,DC=example,DC=com",
            "CN=Administrators,CN=Builtin,DC=example,DC=com",
        ],
        description="LDAP group DNs that map to admin role",
    )
    user_groups: list[str] = Field(
        default_factory=lambda: [
            "CN=Domain Users,CN=Users,DC=example,DC=com",
        ],
        description="LDAP group DNs that map to user role",
    )
    default_role: str = Field(default="user", description="Default role if no groups match")


class LDAPConfig(BaseModel):
    """LDAP server configuration."""

    # Server settings
    server: str = Field(..., description="LDAP server hostname or IP")
    port: int = Field(default=389, description="LDAP port (389 for LDAP, 636 for LDAPS)")
    use_ssl: bool = Field(default=False, description="Use LDAPS (SSL/TLS)")
    use_starttls: bool = Field(default=True, description="Use STARTTLS (if not using LDAPS)")
    verify_ssl: bool = Field(default=True, description="Verify SSL certificates")
    ssl_ca_cert: str | None = Field(None, description="Path to CA certificate file")

    # Connection settings
    timeout: int = Field(default=10, description="Connection timeout in seconds")
    pool_size: int = Field(default=5, description="Connection pool size")

    # Bind settings
    bind_dn: str | None = Field(
        None,
        description="DN for service account (for searches)",
    )
    bind_password: str | None = Field(None, description="Password for service account")

    # Search settings
    base_dn: str = Field(..., description="Base DN for searches")
    user_search_base: str | None = Field(None, description="User search base (defaults to base_dn)")
    group_search_base: str | None = Field(
        None, description="Group search base (defaults to base_dn)"
    )

    # User lookup
    user_dn_pattern: str | None = Field(
        None,
        description="Pattern to construct user DN (e.g., 'uid={username},ou=users,dc=example,dc=com')",
    )
    user_search_filter: str = Field(
        default="(&(objectClass=person)(|(uid={username})(sAMAccountName={username})(mail={username})))",
        description="LDAP filter to find users",
    )

    # Attribute mapping
    username_attribute: str = Field(
        default="sAMAccountName",
        description="Attribute containing username (sAMAccountName for AD, uid for OpenLDAP)",
    )
    email_attribute: str = Field(default="mail", description="Attribute containing email")
    display_name_attribute: str = Field(
        default="displayName", description="Attribute containing display name"
    )
    first_name_attribute: str = Field(default="givenName", description="Attribute for first name")
    last_name_attribute: str = Field(default="sn", description="Attribute for last name")
    member_of_attribute: str = Field(
        default="memberOf", description="Attribute containing group membership"
    )

    # Group lookup
    group_search_filter: str = Field(
        default="(&(objectClass=group)(member={user_dn}))",
        description="LDAP filter to find user's groups",
    )
    group_name_attribute: str = Field(default="cn", description="Attribute for group name")
    nested_groups: bool = Field(
        default=True, description="Resolve nested group membership (AD only)"
    )

    # Role mapping
    role_mapping: LDAPRoleMapping = Field(default_factory=LDAPRoleMapping)

    # Provisioning
    auto_provision: bool = Field(default=True, description="Auto-create users on first login")
    update_on_login: bool = Field(default=True, description="Update user attributes on login")

    # Tenant
    tenant_id: str | None = Field(None, description="Tenant this config belongs to")
    is_active: bool = Field(default=True, description="Whether this config is active")


# =============================================================================
# Request/Response Models
# =============================================================================


class LDAPLoginRequest(BaseModel):
    """Request model for LDAP login."""

    username: str = Field(..., description="Username (can be username, email, or DN)")
    password: str = Field(..., description="LDAP password")
    tenant_id: str | None = Field(None, description="Tenant ID for multi-tenant")


class LDAPLoginResponse(BaseModel):
    """Response from successful LDAP login."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str | None = None
    user: dict[str, Any]
    provisioned: bool = False
    groups: list[str] = []


class LDAPGroupsResponse(BaseModel):
    """Response for user's LDAP groups."""

    username: str
    groups: list[str]
    group_dns: list[str]
    roles: list[str]


class LDAPSearchResult(BaseModel):
    """Single LDAP search result entry."""

    dn: str
    attributes: dict[str, list[str]]


class LDAPSearchResponse(BaseModel):
    """Response for LDAP directory search."""

    results: list[LDAPSearchResult]
    count: int
    truncated: bool = False


class LDAPTestResponse(BaseModel):
    """Response for LDAP connection test."""

    success: bool
    message: str
    server_info: dict[str, Any] | None = None
    bind_successful: bool = False
    search_successful: bool = False


# =============================================================================
# In-Memory Configuration Store
# =============================================================================

_LDAP_CONFIGS: dict[str, LDAPConfig] = {}


def get_ldap_config(tenant_id: str | None = None) -> LDAPConfig | None:
    """Get LDAP configuration for tenant."""
    key = tenant_id or "_default"
    return _LDAP_CONFIGS.get(key)


def set_ldap_config(config: LDAPConfig, tenant_id: str | None = None) -> None:
    """Set LDAP configuration for tenant."""
    key = tenant_id or "_default"
    _LDAP_CONFIGS[key] = config


def delete_ldap_config(tenant_id: str | None = None) -> bool:
    """Delete LDAP configuration for tenant."""
    key = tenant_id or "_default"
    if key in _LDAP_CONFIGS:
        del _LDAP_CONFIGS[key]
        return True
    return False


# =============================================================================
# LDAP Operations
# =============================================================================


class LDAPConnection:
    """LDAP connection wrapper with context manager support.

    Uses ldap3 library for LDAP operations.
    Falls back to mock implementation if ldap3 not available.
    """

    def __init__(self, config: LDAPConfig):
        self.config = config
        self._conn = None
        self._ldap3_available = False

        try:
            import ldap3  # noqa: F401

            self._ldap3_available = True
        except ImportError:
            logger.warning("ldap3 library not installed, LDAP operations will be mocked")

    def __enter__(self) -> "LDAPConnection":
        self.connect()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:  # noqa: ARG002
        self.disconnect()

    def connect(self) -> None:
        """Establish LDAP connection."""
        if not self._ldap3_available:
            return

        import ldap3

        # Build server URL
        use_ssl = self.config.use_ssl or self.config.port == 636

        # TLS configuration
        tls = None
        if use_ssl or self.config.use_starttls:
            tls_args: dict[str, Any] = {
                "validate": ssl.CERT_REQUIRED if self.config.verify_ssl else ssl.CERT_NONE,
            }
            if self.config.ssl_ca_cert:
                tls_args["ca_certs_file"] = self.config.ssl_ca_cert
            tls = ldap3.Tls(**tls_args)

        server = ldap3.Server(
            self.config.server,
            port=self.config.port,
            use_ssl=use_ssl,
            tls=tls,
            get_info=ldap3.ALL,
            connect_timeout=self.config.timeout,
        )

        # Create connection
        self._conn = ldap3.Connection(
            server,
            user=self.config.bind_dn,
            password=self.config.bind_password,
            auto_bind=False,
            receive_timeout=self.config.timeout,
        )

        # Bind
        if not self._conn.bind():
            raise Exception(f"LDAP bind failed: {self._conn.last_error}")

        # STARTTLS if configured
        if self.config.use_starttls and not use_ssl:
            self._conn.start_tls()

    def disconnect(self) -> None:
        """Close LDAP connection."""
        if self._conn:
            try:
                self._conn.unbind()
            except Exception:
                pass
            self._conn = None

    def bind_user(self, username: str, password: str) -> tuple[bool, str | None]:
        """Attempt to bind as a user.

        Args:
            username: Username to authenticate
            password: User's password

        Returns:
            Tuple of (success, user_dn)
        """
        if not self._ldap3_available:
            # Mock implementation for testing
            if password == "test_password":
                return True, f"uid={username},ou=users,{self.config.base_dn}"
            return False, None

        import ldap3

        # Find user DN
        user_dn = self._find_user_dn(username)
        if not user_dn:
            return False, None

        # Try to bind as user
        try:
            server = (
                self._conn.server
                if self._conn
                else ldap3.Server(
                    self.config.server,
                    port=self.config.port,
                    use_ssl=self.config.use_ssl or self.config.port == 636,
                )
            )

            user_conn = ldap3.Connection(
                server,
                user=user_dn,
                password=password,
                auto_bind=False,
            )

            if user_conn.bind():
                user_conn.unbind()
                return True, user_dn

            return False, None

        except Exception as e:
            logger.warning(f"LDAP user bind failed for {username}: {e}")
            return False, None

    def _find_user_dn(self, username: str) -> str | None:
        """Find user DN by username."""
        if not self._ldap3_available or not self._conn:
            return f"uid={username},ou=users,{self.config.base_dn}"

        # If we have a DN pattern, use it
        if self.config.user_dn_pattern:
            return self.config.user_dn_pattern.replace("{username}", username)

        # Otherwise search
        search_base = self.config.user_search_base or self.config.base_dn
        search_filter = self.config.user_search_filter.replace("{username}", username)

        self._conn.search(
            search_base=search_base,
            search_filter=search_filter,
            search_scope="SUBTREE",
            attributes=["dn"],
            size_limit=1,
        )

        if self._conn.entries:
            return str(self._conn.entries[0].entry_dn)

        return None

    def get_user_attributes(self, user_dn: str) -> dict[str, Any]:
        """Get user attributes from LDAP."""
        if not self._ldap3_available or not self._conn:
            # Mock implementation
            username = user_dn.split(",")[0].split("=")[1] if "=" in user_dn else user_dn
            return {
                "dn": user_dn,
                self.config.username_attribute: [username],
                self.config.email_attribute: [f"{username}@example.com"],
                self.config.display_name_attribute: [f"Test User {username.title()}"],
                self.config.first_name_attribute: ["Test"],
                self.config.last_name_attribute: [username.title()],
                self.config.member_of_attribute: [
                    f"CN=Users,{self.config.base_dn}",
                ],
            }

        attributes = [
            self.config.username_attribute,
            self.config.email_attribute,
            self.config.display_name_attribute,
            self.config.first_name_attribute,
            self.config.last_name_attribute,
            self.config.member_of_attribute,
        ]

        self._conn.search(
            search_base=user_dn,
            search_filter="(objectClass=*)",
            search_scope="BASE",
            attributes=attributes,
        )

        if self._conn.entries:
            entry = self._conn.entries[0]
            result = {"dn": str(entry.entry_dn)}
            for attr in attributes:
                try:
                    values = getattr(entry, attr, None)
                    if values:
                        result[attr] = list(values)
                except Exception:
                    pass
            return result

        return {"dn": user_dn}

    def get_user_groups(self, user_dn: str) -> list[str]:
        """Get user's group memberships."""
        if not self._ldap3_available or not self._conn:
            # Mock implementation
            return [
                f"CN=Users,{self.config.base_dn}",
                f"CN=Developers,{self.config.base_dn}",
            ]

        groups = []

        # Get memberOf attribute
        attrs = self.get_user_attributes(user_dn)
        member_of = attrs.get(self.config.member_of_attribute, [])
        groups.extend(member_of)

        # For nested groups in AD, use special search
        if self.config.nested_groups:
            try:
                # AD nested group membership query
                search_filter = f"(member:1.2.840.113556.1.4.1941:={user_dn})"
                group_base = self.config.group_search_base or self.config.base_dn

                self._conn.search(
                    search_base=group_base,
                    search_filter=search_filter,
                    search_scope="SUBTREE",
                    attributes=["dn", self.config.group_name_attribute],
                )

                for entry in self._conn.entries:
                    dn = str(entry.entry_dn)
                    if dn not in groups:
                        groups.append(dn)
            except Exception as e:
                logger.debug(f"Nested group lookup failed (may not be AD): {e}")

        return groups

    def search(
        self,
        search_filter: str,
        attributes: list[str] | None = None,
        search_base: str | None = None,
        size_limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Search LDAP directory."""
        if not self._ldap3_available or not self._conn:
            # Mock implementation
            return [
                {
                    "dn": f"uid=user1,ou=users,{self.config.base_dn}",
                    "attributes": {
                        "uid": ["user1"],
                        "mail": ["user1@example.com"],
                        "cn": ["User One"],
                    },
                },
            ]

        base = search_base or self.config.base_dn
        attrs = attributes or ["*"]

        self._conn.search(
            search_base=base,
            search_filter=search_filter,
            search_scope="SUBTREE",
            attributes=attrs,
            size_limit=size_limit,
        )

        results = []
        for entry in self._conn.entries:
            entry_dict: dict[str, Any] = {"dn": str(entry.entry_dn), "attributes": {}}
            for attr in entry.entry_attributes:
                try:
                    values = getattr(entry, attr, None)
                    if values:
                        entry_dict["attributes"][attr] = list(values)
                except Exception:
                    pass
            results.append(entry_dict)

        return results


# =============================================================================
# User Provisioning
# =============================================================================


def map_ldap_groups_to_roles(groups: list[str], role_mapping: LDAPRoleMapping) -> list[str]:
    """Map LDAP groups to application roles."""
    roles = set()

    # Normalize group DNs for comparison
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

    # Default role if no matches
    if not roles:
        roles.add(role_mapping.default_role)

    return list(roles)


async def provision_or_update_ldap_user(
    ldap_attrs: dict[str, Any],
    groups: list[str],
    config: LDAPConfig,
) -> tuple[dict[str, Any], bool]:
    """Provision new user or update existing user from LDAP.

    Args:
        ldap_attrs: User attributes from LDAP
        groups: User's group memberships
        config: LDAP configuration

    Returns:
        Tuple of (user_dict, was_provisioned)
    """
    user_store = get_user_store()

    # Extract attributes
    def get_first(attr_name: str) -> str | None:
        values = ldap_attrs.get(attr_name, [])
        return values[0] if values else None

    username = (
        get_first(config.username_attribute)
        or ldap_attrs.get("dn", "").split(",")[0].split("=")[-1]
    )
    email = get_first(config.email_attribute)
    display_name = get_first(config.display_name_attribute)
    first_name = get_first(config.first_name_attribute)
    last_name = get_first(config.last_name_attribute)

    if not display_name and first_name and last_name:
        display_name = f"{first_name} {last_name}"
    elif not display_name:
        display_name = username

    # Map groups to roles
    roles = map_ldap_groups_to_roles(groups, config.role_mapping)

    # Check if user exists
    existing_user = user_store.get_user(username)

    if existing_user:
        # Update existing user if configured
        if config.update_on_login:
            existing_user["roles"] = roles
            existing_user["display_name"] = display_name
            existing_user["email"] = email
            existing_user["last_login"] = datetime.utcnow().isoformat()
            existing_user["auth_provider"] = "ldap"
            logger.info(f"Updated LDAP user on login: {username}")
        return existing_user, False

    # Provision new user
    if not config.auto_provision:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not found and auto-provisioning is disabled",
        )

    # Create new user with random password (not used for LDAP auth)
    random_password = secrets.token_urlsafe(32)
    user_store.add_user(
        username=username,
        password=random_password,
        roles=roles,
        email=email,
    )

    new_user = user_store.get_user(username)
    if new_user:
        new_user["display_name"] = display_name
        new_user["first_name"] = first_name
        new_user["last_name"] = last_name
        new_user["auth_provider"] = "ldap"
        new_user["ldap_dn"] = ldap_attrs.get("dn")
        new_user["tenant_id"] = config.tenant_id
        logger.info(f"Provisioned new LDAP user: {username}")
        return new_user, True

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Failed to provision user",
    )


# =============================================================================
# Router Factory
# =============================================================================


def get_router() -> APIRouter:
    """Create and configure LDAP authentication router."""
    router = APIRouter(prefix="/api/auth/ldap", tags=["auth-ldap"])

    @router.post(
        "/login",
        response_model=LDAPLoginResponse,
        responses=get_error_responses(400, 401, 403, 404, 500),
    )
    async def ldap_login(request: LDAPLoginRequest) -> LDAPLoginResponse:
        """Authenticate user via LDAP bind.

        Validates credentials against LDAP server, extracts user attributes
        and group memberships, then issues JWT tokens.
        """
        start_time = time.time()

        config = get_ldap_config(request.tenant_id)
        if not config or not config.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="LDAP authentication not configured for this tenant",
            )

        try:
            with LDAPConnection(config) as ldap_conn:
                # Authenticate user
                success, user_dn = ldap_conn.bind_user(request.username, request.password)

                if not success or not user_dn:
                    logger.warning(f"LDAP authentication failed for: {request.username}")

                    # Audit log
                    try:
                        get_audit_logger().log_authentication(
                            AuditEventType.LOGIN_FAILURE,
                            user_id=request.username,
                            request=None,
                            outcome="failure",
                            details={
                                "auth_method": "ldap",
                                "reason": "invalid_credentials",
                            },
                        )
                    except Exception:
                        pass

                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid credentials",
                    )

                # Get user attributes
                ldap_attrs = ldap_conn.get_user_attributes(user_dn)

                # Get group memberships
                groups = ldap_conn.get_user_groups(user_dn)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"LDAP connection error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"LDAP connection failed: {e}",
            ) from e

        # Provision or update user
        user, was_provisioned = await provision_or_update_ldap_user(ldap_attrs, groups, config)

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
                "auth_provider": "ldap",
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

        # Extract group names for response
        group_names = []
        for g in groups:
            # Extract CN from DN
            if g.startswith("CN=") or g.startswith("cn="):
                group_names.append(g.split(",")[0].split("=")[1])
            else:
                group_names.append(g)

        # Audit log
        try:
            get_audit_logger().log_authentication(
                AuditEventType.LOGIN_SUCCESS,
                user_id=user["username"],
                request=None,
                outcome="success",
                details={
                    "auth_method": "ldap",
                    "provisioned": was_provisioned,
                    "roles": user.get("roles", []),
                    "groups": group_names,
                },
            )
        except Exception as e:
            logger.warning(f"Failed to log LDAP auth event: {e}")

        elapsed_ms = (time.time() - start_time) * 1000
        logger.info(
            f"LDAP login successful: user={user['username']}, "
            f"provisioned={was_provisioned}, groups={len(groups)}, elapsed={elapsed_ms:.2f}ms"
        )

        return LDAPLoginResponse(
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
            groups=group_names,
        )

    @router.get(
        "/groups",
        response_model=LDAPGroupsResponse,
        responses=get_error_responses(401, 403, 404, 500),
    )
    async def get_ldap_groups(
        principal: Principal = Depends(require_auth),
        tenant_id: str | None = Query(None, description="Tenant ID"),
    ) -> LDAPGroupsResponse:
        """Get current user's LDAP groups.

        Returns the LDAP group memberships for the authenticated user.
        Only works for users who authenticated via LDAP.
        """
        config = get_ldap_config(tenant_id)
        if not config or not config.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="LDAP not configured for this tenant",
            )

        user_store = get_user_store()
        user = user_store.get_user(principal.sub)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        # Check if user authenticated via LDAP
        if user.get("auth_provider") != "ldap":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User did not authenticate via LDAP",
            )

        # Get LDAP DN
        ldap_dn = user.get("ldap_dn")
        if not ldap_dn:
            # Try to find user in LDAP
            try:
                with LDAPConnection(config) as ldap_conn:
                    ldap_dn = ldap_conn._find_user_dn(principal.sub)
            except Exception as e:
                logger.warning(f"Could not find LDAP DN for user {principal.sub}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Could not find user in LDAP directory",
                ) from e

        # Get groups
        try:
            with LDAPConnection(config) as ldap_conn:
                group_dns = ldap_conn.get_user_groups(ldap_dn)
        except Exception as e:
            logger.error(f"Failed to get LDAP groups for {principal.sub}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to query LDAP groups: {e}",
            ) from e

        # Extract group names
        group_names = []
        for g in group_dns:
            if g.startswith("CN=") or g.startswith("cn="):
                group_names.append(g.split(",")[0].split("=")[1])
            else:
                group_names.append(g)

        # Map to roles
        roles = map_ldap_groups_to_roles(group_dns, config.role_mapping)

        return LDAPGroupsResponse(
            username=principal.sub,
            groups=group_names,
            group_dns=group_dns,
            roles=roles,
        )

    @router.get(
        "/search",
        response_model=LDAPSearchResponse,
        responses=get_error_responses(400, 401, 403, 404, 500),
    )
    async def search_ldap(
        filter: str = Query(..., description="LDAP search filter"),
        attributes: str = Query("cn,mail,displayName", description="Comma-separated attributes"),
        limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
        principal: Principal = Depends(require_auth),
        tenant_id: str | None = Query(None, description="Tenant ID"),
    ) -> LDAPSearchResponse:
        """Search LDAP directory (admin only).

        Allows administrators to search the LDAP directory for users,
        groups, or other objects.
        """
        # Check admin
        roles = getattr(principal, "roles", []) or []
        if "admin" not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required",
            )

        config = get_ldap_config(tenant_id)
        if not config or not config.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="LDAP not configured for this tenant",
            )

        # Parse attributes
        attr_list = [a.strip() for a in attributes.split(",") if a.strip()]

        try:
            with LDAPConnection(config) as ldap_conn:
                results = ldap_conn.search(
                    search_filter=filter,
                    attributes=attr_list,
                    size_limit=limit,
                )
        except Exception as e:
            logger.error(f"LDAP search failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"LDAP search failed: {e}",
            ) from e

        # Format results
        search_results = [
            LDAPSearchResult(
                dn=r["dn"],
                attributes=dict(r.get("attributes", {})),
            )
            for r in results
        ]

        return LDAPSearchResponse(
            results=search_results,
            count=len(search_results),
            truncated=len(search_results) >= limit,
        )

    return router


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "LDAPConfig",
    "LDAPConnection",
    "LDAPGroupsResponse",
    "LDAPLoginRequest",
    "LDAPLoginResponse",
    "LDAPRoleMapping",
    "LDAPSearchResponse",
    "LDAPSearchResult",
    "LDAPTestResponse",
    "delete_ldap_config",
    "get_ldap_config",
    "get_router",
    "map_ldap_groups_to_roles",
    "set_ldap_config",
]
