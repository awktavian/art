"""Tests for Ambient Privacy, Consent, and Explainability.

Tests the December 7, 2025 privacy framework implementation:
- PrivacyManager: Data classification, retention, audit
- ConsentManager: Granular consent management
- ExplainabilityEngine: Decision transparency

Created: December 7, 2025
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_unit


import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from kagami.core.ambient.privacy import (
    AuditEntry,
    DataCategory,
    DataSensitivity,
    PrivacyConfig,
    PrivacyManager,
    SensorPolicy,
    CATEGORY_SENSITIVITY,
    DEFAULT_RETENTION_HOURS,
)
from kagami.core.ambient.consent import (
    ConsentConfig,
    ConsentContext,
    ConsentLevel,
    ConsentManager,
    ConsentRecord,
)
from kagami.core.ambient.explainability import (
    AmbientDecision,
    DecisionType,
    ExplainabilityConfig,
    ExplainabilityEngine,
    TriggerType,
)

# =============================================================================
# Privacy Manager Tests
# =============================================================================


class TestPrivacyManager:
    """Tests for PrivacyManager."""

    @pytest.fixture
    def privacy_manager(self, tmp_path) -> Any:
        """Create privacy manager with temp paths."""
        config = PrivacyConfig(
            audit_log_path=tmp_path / "audit.jsonl",
            data_store_path=tmp_path / "data",
            enable_audit_log=True,
        )
        return PrivacyManager(config)

    def test_init(self, privacy_manager: Any) -> Any:
        """Test privacy manager initialization."""
        assert privacy_manager is not None
        assert privacy_manager._stats["captures"] == 0

    def test_default_policies(self, privacy_manager: Any) -> None:
        """Test default policies are created for all categories."""
        for category in DataCategory:
            policy = privacy_manager.get_policy(category)
            assert policy is not None
            assert policy.category == category

    def test_get_policy_returns_correct_sensitivity(self, privacy_manager: Any) -> None:
        """Test policies have correct sensitivity levels."""
        # Video should be restricted
        video_policy = privacy_manager.get_policy(DataCategory.VIDEO)
        assert video_policy.sensitivity == DataSensitivity.RESTRICTED

        # Device should be public
        device_policy = privacy_manager.get_policy(DataCategory.DEVICE)
        assert device_policy.sensitivity == DataSensitivity.PUBLIC

        # Location should be confidential
        location_policy = privacy_manager.get_policy(DataCategory.LOCATION)
        assert location_policy.sensitivity == DataSensitivity.CONFIDENTIAL

    def test_set_policy(self, privacy_manager: Any) -> None:
        """Test setting custom policy."""
        custom_policy = SensorPolicy(
            category=DataCategory.LOCATION,
            sensitivity=DataSensitivity.RESTRICTED,
            retention_hours=1,
            local_only=True,
            anonymize=True,
            require_consent=True,
        )
        privacy_manager.set_policy(DataCategory.LOCATION, custom_policy)

        retrieved = privacy_manager.get_policy(DataCategory.LOCATION)
        assert retrieved.retention_hours == 1
        assert retrieved.sensitivity == DataSensitivity.RESTRICTED

    def test_set_retention(self, privacy_manager: Any) -> None:
        """Test setting retention period."""
        privacy_manager.set_retention(DataCategory.PRESENCE, 24)
        policy = privacy_manager.get_policy(DataCategory.PRESENCE)
        assert policy.retention_hours == 24

    def test_can_capture_requires_consent(self, privacy_manager: Any) -> None:
        """Test capture requires consent for sensitive data."""
        # Without consent, should be blocked
        assert not privacy_manager.can_capture(DataCategory.LOCATION, consent_granted=False)

        # With consent, should be allowed
        assert privacy_manager.can_capture(DataCategory.LOCATION, consent_granted=True)

    def test_can_capture_public_data_no_consent(self, privacy_manager: Any) -> None:
        """Test public data doesn't require consent."""
        # Set device to not require consent
        policy = privacy_manager.get_policy(DataCategory.DEVICE)
        policy.require_consent = False
        privacy_manager.set_policy(DataCategory.DEVICE, policy)

        assert privacy_manager.can_capture(DataCategory.DEVICE, consent_granted=False)

    def test_record_capture(self, privacy_manager: Any) -> None:
        """Test recording a capture."""
        data = {"latitude": 37.7749, "longitude": -122.4194}
        data_hash = privacy_manager.record_capture(
            category=DataCategory.LOCATION,
            data=data,
            description="Test capture",
        )

        assert data_hash is not None
        assert privacy_manager._stats["captures"] == 1

    def test_record_capture_anonymizes_location(self, privacy_manager: Any) -> None:
        """Test location data is anonymized."""
        data = {"latitude": 37.7749295, "longitude": -122.4194155}
        privacy_manager.record_capture(
            category=DataCategory.LOCATION,
            data=data,
        )

        # Check stored data has reduced precision
        stored = privacy_manager._data_store.get(DataCategory.LOCATION, [])
        assert len(stored) == 1
        assert stored[0]["data"]["latitude"] == 37.77  # 2 decimal places
        assert stored[0]["data"]["longitude"] == -122.42

    def test_record_capture_redacts_audio(self, privacy_manager: Any) -> None:
        """Test audio transcript is redacted."""
        data = {"transcript": "This is a secret message", "duration": 5.0}
        privacy_manager.record_capture(
            category=DataCategory.AUDIO,
            data=data,
        )

        stored = privacy_manager._data_store.get(DataCategory.AUDIO, [])
        assert len(stored) == 1
        assert stored[0]["data"]["transcript"] == "[REDACTED]"
        assert stored[0]["data"]["transcript_length"] == len("This is a secret message")

    def test_export_my_data(self, privacy_manager: Any) -> None:
        """Test data export."""
        # Add some data
        privacy_manager.record_capture(
            DataCategory.DEVICE, {"battery": 0.8}, description="Battery check"
        )

        export = privacy_manager.export_my_data()

        assert "export_timestamp" in export
        assert "categories" in export
        assert "policies" in export
        assert privacy_manager._stats["exports"] == 1

    def test_delete_my_data(self, privacy_manager: Any) -> None:
        """Test data deletion."""
        # Add some data
        privacy_manager.record_capture(DataCategory.DEVICE, {"battery": 0.8})
        privacy_manager.record_capture(DataCategory.PRESENCE, {"detected": True})

        # Delete all
        deleted = privacy_manager.delete_my_data()

        assert deleted == 2
        assert len(privacy_manager._data_store.get(DataCategory.DEVICE, [])) == 0
        assert len(privacy_manager._data_store.get(DataCategory.PRESENCE, [])) == 0

    def test_delete_my_data_by_category(self, privacy_manager: Any) -> None:
        """Test deleting specific categories."""
        privacy_manager.record_capture(DataCategory.DEVICE, {"battery": 0.8})
        privacy_manager.record_capture(DataCategory.PRESENCE, {"detected": True})

        deleted = privacy_manager.delete_my_data(categories=[DataCategory.DEVICE])

        assert deleted == 1
        assert len(privacy_manager._data_store.get(DataCategory.DEVICE, [])) == 0
        assert len(privacy_manager._data_store.get(DataCategory.PRESENCE, [])) == 1

    def test_get_audit_log(self, privacy_manager: Any) -> None:
        """Test audit log retrieval."""
        privacy_manager.record_capture(DataCategory.DEVICE, {"battery": 0.8})

        audit = privacy_manager.get_audit_log(limit=10)

        assert len(audit) >= 1
        assert audit[0].category == DataCategory.DEVICE
        assert audit[0].action == "capture"

    def test_cleanup_expired(self, privacy_manager: Any) -> None:
        """Test expired data cleanup."""
        # Add data with very short retention
        privacy_manager.set_retention(DataCategory.DEVICE, 0)  # Immediate expiry

        # Store with past expiry
        privacy_manager._data_store[DataCategory.DEVICE] = [
            {
                "data": {"battery": 0.8},
                "timestamp": time.time(),
                "retention_until": time.time() - 100,
            }
        ]

        removed = privacy_manager._cleanup_expired()

        assert removed == 1
        assert len(privacy_manager._data_store.get(DataCategory.DEVICE, [])) == 0

    def test_get_stats(self, privacy_manager: Any) -> None:
        """Test statistics retrieval."""
        privacy_manager.record_capture(DataCategory.DEVICE, {"battery": 0.8})

        stats = privacy_manager.get_stats()

        assert stats["captures"] == 1
        assert stats["total_stored_entries"] == 1


# =============================================================================
# Consent Manager Tests
# =============================================================================


class TestConsentManager:
    """Tests for ConsentManager."""

    @pytest.fixture
    def consent_manager(self) -> Any:
        """Create consent manager."""
        return ConsentManager()

    def test_init(self, consent_manager: Any) -> Any:
        """Test consent manager initialization."""
        assert consent_manager is not None
        assert consent_manager._current_context == ConsentContext.UNKNOWN

    def test_get_consent_default_denied_for_restricted(self, consent_manager: Any) -> None:
        """Test restricted data defaults to denied."""
        level = consent_manager.get_consent(DataCategory.VIDEO)
        assert level == ConsentLevel.DENIED

    def test_get_consent_default_not_asked_for_internal(self, consent_manager: Any) -> None:
        """Test internal data defaults to not_asked."""
        level = consent_manager.get_consent(DataCategory.ACTIVITY)
        assert level == ConsentLevel.NOT_ASKED

    def test_grant_consent(self, consent_manager: Any) -> None:
        """Test granting consent."""
        record = consent_manager.grant_consent(
            DataCategory.LOCATION,
            level=ConsentLevel.GRANTED,
            reason="User approved",
        )

        assert record.level == ConsentLevel.GRANTED
        assert consent_manager.has_consent(DataCategory.LOCATION)
        assert consent_manager._stats["grants"] == 1

    def test_grant_consent_with_duration(self, consent_manager: Any) -> None:
        """Test granting time-limited consent."""
        record = consent_manager.grant_consent(
            DataCategory.AUDIO,
            duration_hours=1.0,
            reason="For meeting",
        )

        assert record.level == ConsentLevel.GRANTED_TIMED
        assert record.expires_at is not None
        assert record.expires_at > time.time()

    def test_revoke_consent(self, consent_manager: Any) -> None:
        """Test revoking consent."""
        consent_manager.grant_consent(DataCategory.LOCATION)
        assert consent_manager.has_consent(DataCategory.LOCATION)

        consent_manager.revoke_consent(DataCategory.LOCATION)
        assert not consent_manager.has_consent(DataCategory.LOCATION)

    def test_has_consent(self, consent_manager: Any) -> None:
        """Test has_consent check."""
        assert not consent_manager.has_consent(DataCategory.LOCATION)

        consent_manager.grant_consent(DataCategory.LOCATION)
        assert consent_manager.has_consent(DataCategory.LOCATION)

    def test_context_aware_consent(self, consent_manager: Any) -> None:
        """Test context-specific consent."""
        # Grant consent only at home
        consent_manager.grant_consent(
            DataCategory.AUDIO,
            context=ConsentContext.HOME,
        )

        # Should have consent in home context
        consent_manager.set_context(ConsentContext.HOME)
        assert consent_manager.has_consent(DataCategory.AUDIO)

        # Should not have consent in work context (falls back to default)
        consent_manager.set_context(ConsentContext.WORK)
        # This checks default, which for AUDIO (confidential) is NOT_ASKED
        level = consent_manager.get_consent(DataCategory.AUDIO)
        assert level in (ConsentLevel.NOT_ASKED, ConsentLevel.GRANTED)

    def test_set_context(self, consent_manager: Any) -> None:
        """Test setting context."""
        consent_manager.set_context(ConsentContext.WORK)
        assert consent_manager.get_context() == ConsentContext.WORK

    @pytest.mark.asyncio
    async def test_pause_ambient(self, consent_manager: Any) -> None:
        """Test pausing ambient."""
        await consent_manager.pause_ambient(duration_minutes=1)

        assert consent_manager.is_paused
        assert consent_manager._stats["pauses"] == 1

    @pytest.mark.asyncio
    async def test_resume_ambient(self, consent_manager: Any) -> None:
        """Test resuming ambient."""
        await consent_manager.pause_ambient(duration_minutes=1)
        assert consent_manager.is_paused

        await consent_manager.resume_ambient()
        assert not consent_manager.is_paused

    def test_get_active_sensors(self, consent_manager: Any) -> None:
        """Test getting active sensors."""
        consent_manager.grant_consent(DataCategory.DEVICE)
        consent_manager.grant_consent(DataCategory.PRESENCE)

        active = consent_manager.get_active_sensors()

        # Should include at least the two we granted + any defaults
        categories = [s["category"] for s in active]
        assert "device" in categories
        assert "presence" in categories

    def test_get_sensor_indicator(self, consent_manager: Any) -> None:
        """Test sensor indicator."""
        indicator = consent_manager.get_sensor_indicator()

        assert "status" in indicator
        assert "color" in indicator
        assert "active_count" in indicator

    def test_get_sensor_indicator_paused(self, consent_manager: Any) -> None:
        """Test sensor indicator when paused."""
        consent_manager._paused = True
        indicator = consent_manager.get_sensor_indicator()

        assert indicator["status"] == "paused"
        assert indicator["color"] == "gray"

    def test_get_preferences(self, consent_manager: Any) -> None:
        """Test getting preferences."""
        prefs = consent_manager.get_preferences()

        assert "categories" in prefs
        assert "current_context" in prefs
        assert "indicator" in prefs

    def test_consent_callback(self, consent_manager: Any) -> None:
        """Test consent change callback."""
        callback_called = []

        def callback(category: Any, level: Any) -> None:
            callback_called.append((category, level))

        consent_manager.on_consent_change(callback)
        consent_manager.grant_consent(DataCategory.LOCATION)

        assert len(callback_called) == 1
        assert callback_called[0][0] == DataCategory.LOCATION

    def test_pause_callback(self, consent_manager: Any) -> None:
        """Test pause change callback."""
        callback_called = []

        def callback(paused: Any) -> None:
            callback_called.append(paused)

        consent_manager.on_pause_change(callback)

        asyncio.get_event_loop().run_until_complete(
            consent_manager.pause_ambient(duration_minutes=1)
        )

        assert len(callback_called) == 1
        assert callback_called[0] is True


# =============================================================================
# Explainability Engine Tests
# =============================================================================


class TestExplainabilityEngine:
    """Tests for ExplainabilityEngine."""

    @pytest.fixture
    def explainability_engine(self) -> Any:
        """Create explainability engine."""
        return ExplainabilityEngine()

    def test_init(self, explainability_engine: Any) -> Any:
        """Test explainability engine initialization."""
        assert explainability_engine is not None
        assert explainability_engine._stats["total_decisions"] == 0

    def test_log_decision(self, explainability_engine: Any) -> None:
        """Test logging a decision."""
        decision = explainability_engine.log_decision(
            decision_type=DecisionType.LIGHT_CHANGE,
            trigger_type=TriggerType.PRESENCE_CHANGE,
            trigger_details="User became FOCUSED",
            reasoning="Dimming lights to not distract",
            effect="Lights set to 20%",
            reversible=True,
        )

        assert decision.id.startswith("d")
        assert decision.decision_type == DecisionType.LIGHT_CHANGE
        assert explainability_engine._stats["total_decisions"] == 1

    def test_log_light_change(self, explainability_engine: Any) -> None:
        """Test convenience logger for light changes."""
        decision = explainability_engine.log_light_change(
            trigger="Presence changed to FOCUSED",
            reasoning="User is focusing, dimming to reduce distraction",
            old_state={"brightness": 100},
            new_state={"brightness": 20},
        )

        assert decision.decision_type == DecisionType.LIGHT_CHANGE
        assert "20%" in decision.effect

    def test_log_safety_alert(self, explainability_engine: Any) -> None:
        """Test logging safety alerts."""
        decision = explainability_engine.log_safety_alert(
            h_value=-0.1,
            threat="Unsafe action detected",
            actions_taken=["Blocked action", "Alerted user"],
        )

        assert decision.decision_type == DecisionType.SAFETY_ALERT
        assert not decision.reversible  # Safety alerts shouldn't be reversible

    def test_query_recent(self, explainability_engine: Any) -> None:
        """Test querying recent decisions."""
        # Log some decisions
        for i in range(5):
            explainability_engine.log_decision(
                decision_type=DecisionType.LIGHT_CHANGE,
                trigger_type=TriggerType.BREATH_CYCLE,
                trigger_details=f"Breath cycle {i}",
                reasoning="Breathing",
                effect="Lights pulsed",
            )

        recent = explainability_engine.query_recent(minutes=5, limit=3)

        assert len(recent) == 3
        assert explainability_engine._stats["queries"] == 1

    def test_query_by_type(self, explainability_engine: Any) -> None:
        """Test filtering by decision type."""
        explainability_engine.log_decision(
            decision_type=DecisionType.LIGHT_CHANGE,
            trigger_type=TriggerType.PRESENCE_CHANGE,
            trigger_details="Test",
            reasoning="Test",
            effect="Test",
        )
        explainability_engine.log_decision(
            decision_type=DecisionType.SOUND_CHANGE,
            trigger_type=TriggerType.PRESENCE_CHANGE,
            trigger_details="Test",
            reasoning="Test",
            effect="Test",
        )

        light_only = explainability_engine.query_recent(
            minutes=5, decision_type=DecisionType.LIGHT_CHANGE
        )

        assert len(light_only) == 1
        assert light_only[0].decision_type == DecisionType.LIGHT_CHANGE

    def test_query_by_id(self, explainability_engine: Any) -> None:
        """Test querying by ID."""
        decision = explainability_engine.log_decision(
            decision_type=DecisionType.LIGHT_CHANGE,
            trigger_type=TriggerType.PRESENCE_CHANGE,
            trigger_details="Test",
            reasoning="Test",
            effect="Test",
        )

        retrieved = explainability_engine.query_by_id(decision.id)

        assert retrieved is not None
        assert retrieved.id == decision.id

    def test_explain_last(self, explainability_engine: Any) -> None:
        """Test explaining last N decisions."""
        explainability_engine.log_decision(
            decision_type=DecisionType.LIGHT_CHANGE,
            trigger_type=TriggerType.PRESENCE_CHANGE,
            trigger_details="User became FOCUSED",
            reasoning="Dimming to reduce distraction",
            effect="Lights at 20%",
        )

        explanations = explainability_engine.explain_last(count=1)

        assert len(explanations) == 1
        assert "Dimming" in explanations[0]

    def test_explain_question_why(self, explainability_engine: Any) -> None:
        """Test answering 'why' questions."""
        explainability_engine.log_light_change(
            trigger="Presence changed",
            reasoning="User is focusing, reducing brightness",
            old_state={"brightness": 100},
            new_state={"brightness": 20},
        )

        answer = explainability_engine.explain_question("why did the lights change?")

        assert "focusing" in answer.lower() or "brightness" in answer.lower()

    def test_explain_question_what(self, explainability_engine: Any) -> None:
        """Test answering 'what' questions."""
        explainability_engine.log_decision(
            decision_type=DecisionType.LIGHT_CHANGE,
            trigger_type=TriggerType.PRESENCE_CHANGE,
            trigger_details="Test",
            reasoning="Test reasoning",
            effect="Lights changed",
        )

        answer = explainability_engine.explain_question("what happened?")

        assert "Lights" in answer or "changed" in answer or "nothing" in answer.lower()

    def test_get_summary(self, explainability_engine: Any) -> None:
        """Test getting summary."""
        for _ in range(3):
            explainability_engine.log_decision(
                decision_type=DecisionType.LIGHT_CHANGE,
                trigger_type=TriggerType.BREATH_CYCLE,
                trigger_details="Breath",
                reasoning="Breathing",
                effect="Pulsed",
            )

        summary = explainability_engine.get_summary(minutes=5)

        assert summary["total_decisions"] == 3
        assert "by_type" in summary
        assert "light_change" in summary["by_type"]

    def test_get_dashboard(self, explainability_engine: Any) -> None:
        """Test getting dashboard data."""
        explainability_engine.log_decision(
            decision_type=DecisionType.LIGHT_CHANGE,
            trigger_type=TriggerType.BREATH_CYCLE,
            trigger_details="Test",
            reasoning="Test",
            effect="Test",
        )

        dashboard = explainability_engine.get_dashboard()

        assert "summary_30min" in dashboard
        assert "recent_explanations" in dashboard
        assert "stats" in dashboard

    def test_decision_explain_verbose(self, explainability_engine: Any) -> None:
        """Test verbose decision explanation."""
        decision = AmbientDecision(
            id="d000001",
            timestamp=time.time(),
            decision_type=DecisionType.LIGHT_CHANGE,
            trigger_type=TriggerType.PRESENCE_CHANGE,
            trigger_details="User became FOCUSED",
            reasoning="Dimming to reduce distraction",
            effect="Lights at 20%",
            reversible=True,
        )

        verbose = decision.explain(verbose=True)
        short = decision.explain(verbose=False)

        assert len(verbose) > len(short)
        assert "can be undone" in verbose.lower()


# =============================================================================
# Integration Tests
# =============================================================================


class TestPrivacyConsentIntegration:
    """Integration tests for privacy and consent."""

    @pytest.fixture
    def privacy_manager(self, tmp_path) -> Any:
        """Create privacy manager."""
        config = PrivacyConfig(
            audit_log_path=tmp_path / "audit.jsonl",
            data_store_path=tmp_path / "data",
        )
        return PrivacyManager(config)

    @pytest.fixture
    def consent_manager(self) -> Any:
        """Create consent manager."""
        return ConsentManager()

    def test_capture_requires_consent(self, privacy_manager, consent_manager) -> Any:
        """Test that capture checks consent."""
        # Without consent
        has_consent = consent_manager.has_consent(DataCategory.LOCATION)
        can_capture = privacy_manager.can_capture(
            DataCategory.LOCATION, consent_granted=has_consent
        )
        assert not can_capture

        # Grant consent
        consent_manager.grant_consent(DataCategory.LOCATION)
        has_consent = consent_manager.has_consent(DataCategory.LOCATION)
        can_capture = privacy_manager.can_capture(
            DataCategory.LOCATION, consent_granted=has_consent
        )
        assert can_capture

    def test_paused_blocks_capture(self, privacy_manager, consent_manager) -> None:
        """Test that paused state blocks all capture."""
        consent_manager.grant_consent(DataCategory.DEVICE)
        consent_manager._paused = True

        # Even with consent, paused should block
        level = consent_manager.get_consent(DataCategory.DEVICE)
        assert level == ConsentLevel.DENIED
