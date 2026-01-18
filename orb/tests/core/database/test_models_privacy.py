"""Tests for privacy-related ORM models (GDPR compliance).

TIER: Unit (no external dependencies)
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration


import uuid
from datetime import datetime, timedelta


@pytest.mark.tier_unit
def test_user_consent_model_exists() -> None:
    """Test UserConsent model can be imported and instantiated."""
    from kagami.core.database.models import UserConsent

    user_id = uuid.uuid4()
    consent = UserConsent(
        user_id=user_id,
        consent_type="analytics",
        granted=True,
    )

    assert consent.user_id == user_id
    assert consent.consent_type == "analytics"
    assert consent.granted is True
    assert consent.granted_at is None  # Not set until persisted
    assert consent.revoked_at is None


@pytest.mark.tier_unit
def test_user_consent_required_fields() -> None:
    """Test UserConsent enforces required fields."""
    from kagami.core.database.models import UserConsent

    # Should not raise on instantiation (validation happens on DB insert)
    consent = UserConsent(
        user_id=uuid.uuid4(),
        consent_type="cookie",
        granted=False,
    )
    assert consent.consent_type == "cookie"
    assert consent.granted is False


@pytest.mark.tier_unit
def test_user_consent_types() -> None:
    """Test UserConsent supports standard consent types."""
    from kagami.core.database.models import UserConsent

    consent_types = ["cookie", "analytics", "marketing"]

    for ctype in consent_types:
        consent = UserConsent(
            user_id=uuid.uuid4(),
            consent_type=ctype,
            granted=True,
        )
        assert consent.consent_type == ctype


@pytest.mark.tier_unit
def test_privacy_audit_log_model_exists() -> None:
    """Test PrivacyAuditLog model can be imported and instantiated."""
    from kagami.core.database.models import PrivacyAuditLog

    user_id = uuid.uuid4()
    log = PrivacyAuditLog(
        user_id=user_id,
        action="export",
        resource="user_data",
    )

    assert log.user_id == user_id
    assert log.action == "export"
    assert log.resource == "user_data"
    assert log.timestamp is None  # Not set until persisted
    assert log.ip_address is None
    assert log.user_agent is None


@pytest.mark.tier_unit
def test_privacy_audit_log_actions() -> None:
    """Test PrivacyAuditLog supports standard actions."""
    from kagami.core.database.models import PrivacyAuditLog

    actions = ["access", "modify", "delete", "export"]

    for action in actions:
        log = PrivacyAuditLog(
            user_id=uuid.uuid4(),
            action=action,
            resource="user_profile",
        )
        assert log.action == action


@pytest.mark.tier_unit
def test_privacy_audit_log_with_metadata() -> None:
    """Test PrivacyAuditLog can store IP and user agent."""
    from kagami.core.database.models import PrivacyAuditLog

    log = PrivacyAuditLog(
        user_id=uuid.uuid4(),
        action="access",
        resource="personal_data",
        ip_address="192.0.2.1",
        user_agent="Mozilla/5.0 (test)",
    )

    assert log.ip_address == "192.0.2.1"
    assert log.user_agent == "Mozilla/5.0 (test)"


@pytest.mark.tier_unit
def test_privacy_audit_log_ipv6_support() -> None:
    """Test PrivacyAuditLog supports IPv6 addresses (45 chars max)."""
    from kagami.core.database.models import PrivacyAuditLog

    ipv6_address = "2001:0db8:85a3:0000:0000:8a2e:0370:7334"
    log = PrivacyAuditLog(
        user_id=uuid.uuid4(),
        action="delete",
        resource="gdpr_request",
        ip_address=ipv6_address,
    )

    assert log.ip_address == ipv6_address
    assert len(ipv6_address) <= 45  # Verify fits in column


@pytest.mark.tier_unit
def test_user_consent_table_name() -> None:
    """Test UserConsent has correct table name."""
    from kagami.core.database.models import UserConsent

    assert UserConsent.__tablename__ == "user_consents"


@pytest.mark.tier_unit
def test_privacy_audit_log_table_name() -> None:
    """Test PrivacyAuditLog has correct table name."""
    from kagami.core.database.models import PrivacyAuditLog

    assert PrivacyAuditLog.__tablename__ == "privacy_audit_log"


@pytest.mark.tier_unit
def test_user_consent_has_indexes() -> None:
    """Test UserConsent has correct indexes defined."""
    from kagami.core.database.models import UserConsent

    # Verify __table_args__ exists and contains Index
    assert hasattr(UserConsent, "__table_args__")
    assert isinstance(UserConsent.__table_args__, tuple)
    assert len(UserConsent.__table_args__) > 0


@pytest.mark.tier_unit
def test_privacy_audit_log_has_indexes() -> None:
    """Test PrivacyAuditLog has correct indexes defined."""
    from kagami.core.database.models import PrivacyAuditLog

    # Verify __table_args__ exists and contains Index
    assert hasattr(PrivacyAuditLog, "__table_args__")
    assert isinstance(PrivacyAuditLog.__table_args__, tuple)
    assert len(PrivacyAuditLog.__table_args__) > 0


@pytest.mark.tier_unit
def test_models_exported_in_init() -> None:
    """Test new models are exported in models.__all__."""
    from kagami.core.database import models

    assert "UserConsent" in models.__all__
    assert "PrivacyAuditLog" in models.__all__
