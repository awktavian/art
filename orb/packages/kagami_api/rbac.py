"""Role-Based Access Control (RBAC) for Kagami API.

Provides decorators and utilities for enforcing role-based access control
on API endpoints. Uses FastAPI's dependency injection system.

Roles (hierarchical):
    guest:    Read-only access to public resources
    user:     Read/write own resources, basic operations
    api_user: Extended API access, widget installation
    tester:   Same as api_user (testing accounts)
    admin:    Full access, billing, user management

Permission Format:
    resource:action (e.g., "file:write", "user:admin")

Resources:
    system, user, file, widget, tool, plan, room, billing

Actions:
    read, write, delete, admin, execute, install, join

Usage:
    from kagami_api.rbac import require_permission, require_role, Permission

    @router.get("/users")
    async def list_users(
        principal: Principal = Depends(require_permission(Permission.USER_READ))
    ):
        ...

    @router.delete("/users/{user_id}")
    async def delete_user(
        principal: Principal = Depends(require_admin())
    ):
        ...
"""

import logging

from fastapi import Depends, HTTPException, status

from kagami_api.security import Principal, require_auth

logger = logging.getLogger(__name__)


class Permission:
    """Represents a permission in the RBAC system.

    Permission strings follow the format: resource:action
    where resource is a domain (system, user, file, etc.)
    and action is the operation (read, write, admin, etc.)

    Use these constants with require_permission() dependency.
    """

    # System permissions — server configuration and health
    SYSTEM_READ = "system:read"  # View system status
    SYSTEM_WRITE = "system:write"  # Modify system settings
    SYSTEM_ADMIN = "system:admin"  # Full system access

    # User permissions — user accounts and profiles
    USER_READ = "user:read"  # View user profiles
    USER_WRITE = "user:write"  # Update own profile
    USER_ADMIN = "user:admin"  # Manage all users

    # File permissions — document and asset management
    FILE_READ = "file:read"  # View files
    FILE_WRITE = "file:write"  # Create/update files
    FILE_DELETE = "file:delete"  # Delete files
    FILE_ADMIN = "file:admin"  # Manage all files

    # Widget permissions — UI components and extensions
    WIDGET_READ = "widget:read"  # View widgets
    WIDGET_WRITE = "widget:write"  # Create/update widgets
    WIDGET_INSTALL = "widget:install"  # Install widgets
    WIDGET_ADMIN = "widget:admin"  # Manage all widgets

    # Tool permissions — executable tools and agents
    TOOL_READ = "tool:read"  # View available tools
    TOOL_EXECUTE = "tool:execute"  # Execute tools
    TOOL_ADMIN = "tool:admin"  # Manage tools

    # Plan permissions — execution plans and schedules
    PLAN_READ = "plan:read"  # View plans
    PLAN_WRITE = "plan:write"  # Create/modify plans
    PLAN_ADMIN = "plan:admin"  # Manage all plans

    # Room permissions — collaborative workspaces
    ROOM_READ = "room:read"  # View rooms
    ROOM_JOIN = "room:join"  # Join rooms
    ROOM_ADMIN = "room:admin"  # Manage rooms

    # Billing permissions — subscription and payment
    BILLING_READ = "billing:read"  # View billing info
    BILLING_WRITE = "billing:write"  # Update payment methods
    BILLING_ADMIN = "billing:admin"  # Manage subscriptions


# =============================================================================
# ROLE → PERMISSION MAPPING
# =============================================================================
# Each role grants a set of permissions. Higher roles generally have superset
# permissions. Users can have multiple roles — permissions are combined.
# =============================================================================

ROLE_PERMISSIONS = {
    # Guest: Read-only access to public resources
    "guest": [
        Permission.SYSTEM_READ,
        Permission.USER_READ,
        Permission.FILE_READ,
        Permission.WIDGET_READ,
        Permission.TOOL_READ,
        Permission.PLAN_READ,
        Permission.ROOM_READ,
    ],
    # User: Standard authenticated user — read/write own resources
    "user": [
        Permission.SYSTEM_READ,
        Permission.USER_READ,
        Permission.FILE_READ,
        Permission.WIDGET_READ,
        Permission.TOOL_READ,
        Permission.PLAN_READ,
        Permission.USER_WRITE,
        Permission.FILE_WRITE,
        Permission.WIDGET_WRITE,
        Permission.TOOL_EXECUTE,
        Permission.PLAN_WRITE,
        Permission.ROOM_READ,
        Permission.ROOM_JOIN,
    ],
    # API User: Extended API access — widget installation, system write
    "api_user": [
        Permission.SYSTEM_READ,
        Permission.SYSTEM_WRITE,
        Permission.USER_READ,
        Permission.USER_WRITE,
        Permission.FILE_READ,
        Permission.FILE_WRITE,
        Permission.WIDGET_READ,
        Permission.WIDGET_WRITE,
        Permission.WIDGET_INSTALL,
        Permission.TOOL_READ,
        Permission.TOOL_EXECUTE,
        Permission.PLAN_READ,
        Permission.PLAN_WRITE,
        Permission.ROOM_READ,
        Permission.ROOM_JOIN,
    ],
    # Tester: Same as api_user — for testing accounts
    "tester": [
        Permission.SYSTEM_READ,
        Permission.SYSTEM_WRITE,
        Permission.USER_READ,
        Permission.USER_WRITE,
        Permission.FILE_READ,
        Permission.FILE_WRITE,
        Permission.WIDGET_READ,
        Permission.WIDGET_WRITE,
        Permission.WIDGET_INSTALL,
        Permission.TOOL_READ,
        Permission.TOOL_EXECUTE,
        Permission.PLAN_READ,
        Permission.PLAN_WRITE,
        Permission.ROOM_READ,
        Permission.ROOM_JOIN,
    ],
    # Admin: Full access — all permissions including billing and user management
    "admin": [
        Permission.SYSTEM_READ,
        Permission.SYSTEM_WRITE,
        Permission.SYSTEM_ADMIN,
        Permission.USER_READ,
        Permission.USER_WRITE,
        Permission.USER_ADMIN,
        Permission.FILE_READ,
        Permission.FILE_WRITE,
        Permission.FILE_DELETE,
        Permission.FILE_ADMIN,
        Permission.WIDGET_READ,
        Permission.WIDGET_WRITE,
        Permission.WIDGET_INSTALL,
        Permission.WIDGET_ADMIN,
        Permission.TOOL_READ,
        Permission.TOOL_EXECUTE,
        Permission.TOOL_ADMIN,
        Permission.PLAN_READ,
        Permission.PLAN_WRITE,
        Permission.PLAN_ADMIN,
        Permission.ROOM_READ,
        Permission.ROOM_JOIN,
        Permission.ROOM_ADMIN,
        Permission.BILLING_READ,
        Permission.BILLING_WRITE,
        Permission.BILLING_ADMIN,
    ],
}


def get_user_permissions(roles: list[str]) -> list[str]:
    """Get all permissions for a user based on their roles.

    Args:
        roles: List of user roles

    Returns:
        List of permissions the user has
    """
    permissions = set()
    for role in roles:
        role_perms = ROLE_PERMISSIONS.get(role, [])
        permissions.update(role_perms)
    return list(permissions)


def has_permission(user_roles: list[str], required_permission: str) -> bool:
    """Check if user has a specific permission based on their roles.

    Args:
        user_roles: List of roles assigned to the user
        required_permission: Permission string to check (e.g., Permission.SYSTEM_WRITE)

    Returns:
        True if user has the permission via any of their roles, False otherwise
    """
    user_permissions = get_user_permissions(user_roles)
    return required_permission in user_permissions


def has_any_role(user_roles: list[str], required_roles: list[str]) -> bool:
    """Check if user has any of the required roles.

    Args:
        user_roles: List of user roles
        required_roles: List of roles to check for

    Returns:
        True if user has at least one of the required roles
    """
    return bool(set(user_roles) & set(required_roles))


def require_permission(permission: str) -> None:
    """Decorator to require a specific permission for an endpoint.

    Args:
        permission: Required permission string

    Returns:
        Dependency function for FastAPI
    """

    def permission_dependency(
        principal: Principal = Depends(require_auth),
    ) -> Principal:
        if not has_permission(principal.roles, permission):
            try:
                from kagami_api.audit_logger import audit_permission_denied

                audit_permission_denied(
                    principal.sub,
                    "unknown",
                    permission,
                    None,
                    {
                        "user_roles": principal.roles,
                        "required_permission": permission,
                        "action": "access_denied",
                    },
                )
            except Exception as _e:
                logger.warning("Audit logging failed (permission denied): %s", _e)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {permission}",
            )
        if permission in [Permission.SYSTEM_ADMIN, Permission.USER_ADMIN, Permission.FILE_DELETE]:
            try:
                from kagami_api.audit_logger import AuditEventType, get_audit_logger

                get_audit_logger().log_authorization(
                    AuditEventType.ACCESS_GRANTED,
                    principal.sub,
                    "unknown",
                    permission,
                    None,
                    "granted",
                    {"user_roles": principal.roles},
                )
            except Exception as _e:
                logger.warning("Audit logging failed (access granted): %s", _e)
        return principal

    return permission_dependency  # type: ignore[return-value]


def require_role(roles: str | list[str]) -> None:
    """Decorator to require specific roles for an endpoint.

    Args:
        roles: Required role(s) - can be a string or list of strings

    Returns:
        Dependency function for FastAPI
    """
    if isinstance(roles, str):
        roles = [roles]

    def role_dependency(principal: Principal = Depends(require_auth)) -> Principal:
        if not has_any_role(principal.roles, roles):
            logger.warning(
                f"Role access denied: User {principal.sub} with roles {principal.roles} attempted to access endpoint requiring one of {roles}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient privileges. Required role: {' or '.join(roles)}",
            )
        return principal

    return role_dependency  # type: ignore[return-value]


def require_admin() -> None:
    """Decorator to require admin role for an endpoint.

    Returns:
        Dependency function for FastAPI
    """
    return require_role(["admin"])
