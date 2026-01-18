from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration
from kagami_api.rbac import (
    ROLE_PERMISSIONS,
    Permission,
    get_user_permissions,
    has_permission,
)
def test_role_permissions_coverage():
    # api_user should include tool execute and plan write
    perms = set(ROLE_PERMISSIONS["api_user"])
    assert Permission.TOOL_EXECUTE in perms
    assert Permission.PLAN_WRITE in perms
def test_get_user_permissions_aggregates_roles():
    perms = set(get_user_permissions(["guest", "user"]))
    assert Permission.SYSTEM_READ in perms
    assert Permission.USER_WRITE in perms
def test_has_permission_true_and_false():
    assert has_permission(["api_user"], Permission.SYSTEM_WRITE)
    assert not has_permission(["guest"], Permission.SYSTEM_WRITE)
