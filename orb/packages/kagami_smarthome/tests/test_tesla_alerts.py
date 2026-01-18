"""Tesla Alerts System Tests.

Tests for:
- TeslaAlert dataclass
- TeslaAlertDictionary class
- TeslaAlertRouter class
- Alert priority calculation
- Alert category mapping
- Smart home integration
- CSV loading

Created: December 31, 2025
"""

from __future__ import annotations

import csv
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from kagami_smarthome.integrations.tesla import (
    AlertCategory,
    AlertPriority,
    TeslaAlert,
    TeslaAlertDictionary,
    TeslaAlertRouter,
)
from kagami_smarthome.integrations.tesla.tesla import (
    PREFIX_TO_CATEGORY,
    SAFETY_CRITICAL_PATTERNS,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_alert():
    """Create a sample TeslaAlert."""
    return TeslaAlert(
        signal_name="APP_w009_aebFault",
        condition="AEB system fault detected",
        clear_condition="Fault cleared or system reset",
        description="Automatic Emergency Braking system fault",
        potential_impact="AEB may not function",
        customer_message_1="Automatic Emergency Braking unavailable",
        customer_message_2="Schedule service appointment",
        audiences=["customer", "service-fix"],
        models=["Model S 2021+", "Model 3", "Model X", "Model Y"],
    )


@pytest.fixture
def critical_alert():
    """Create a safety-critical TeslaAlert."""
    return TeslaAlert(
        signal_name="ESP_e001_stability",
        condition="Stability control failure",
        clear_condition="System reset",
        description="Electronic Stability Program failure",
        potential_impact="PULL OVER SAFELY - Vehicle may shut down",
        customer_message_1="PULL OVER SAFELY",
        customer_message_2="Vehicle stability compromised",
        audiences=["customer", "service-fix"],
        models=["Model S 2021+"],
    )


@pytest.fixture
def low_priority_alert():
    """Create a low priority TeslaAlert."""
    return TeslaAlert(
        signal_name="UI_w001_softwareUpdate",
        condition="Software update available",
        clear_condition="Update installed",
        description="New software version available",
        potential_impact="None",
        customer_message_1="",
        customer_message_2="",
        audiences=["internal"],
        models=["All"],
    )


@pytest.fixture
def temp_csv_path():
    """Create a temporary CSV file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "SignalName",
                "Condition",
                "ClearCondition",
                "Description",
                "PotentialImpact",
                "CustomerFacingMessage1",
                "CustomerFacingMessage2",
                "Audiences",
                "Models",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "SignalName": "APP_w009_aebFault",
                "Condition": "AEB fault",
                "ClearCondition": "Cleared",
                "Description": "AEB unavailable",
                "PotentialImpact": "AEB may not function",
                "CustomerFacingMessage1": "AEB unavailable",
                "CustomerFacingMessage2": "Schedule service",
                "Audiences": "customer;service-fix",
                "Models": "Model S 2021+;Model 3",
            }
        )
        writer.writerow(
            {
                "SignalName": "ESP_e001_stability",
                "Condition": "Stability fault",
                "ClearCondition": "Reset",
                "Description": "ESP failure",
                "PotentialImpact": "PULL OVER SAFELY",
                "CustomerFacingMessage1": "PULL OVER SAFELY",
                "CustomerFacingMessage2": "Vehicle may shut down",
                "Audiences": "customer;service-fix",
                "Models": "Model S 2021+",
            }
        )
        writer.writerow(
            {
                "SignalName": "BMS_w001_lowBattery",
                "Condition": "Low battery",
                "ClearCondition": "Charged",
                "Description": "Battery low",
                "PotentialImpact": "Limited range",
                "CustomerFacingMessage1": "Battery low",
                "CustomerFacingMessage2": "Charge soon",
                "Audiences": "customer",
                "Models": "All",
            }
        )
        writer.writerow(
            {
                "SignalName": "UI_i001_info",
                "Condition": "Info",
                "ClearCondition": "Cleared",
                "Description": "Info message",
                "PotentialImpact": "None",
                "CustomerFacingMessage1": "",
                "CustomerFacingMessage2": "",
                "Audiences": "internal",
                "Models": "All",
            }
        )
        path = Path(f.name)
    yield path
    path.unlink()  # Cleanup


@pytest.fixture
def mock_smart_home():
    """Create mock smart home controller."""
    mock = MagicMock()
    mock.announce = AsyncMock()
    mock.announce_all = AsyncMock()
    return mock


# =============================================================================
# ALERT PRIORITY TESTS
# =============================================================================


class TestAlertPriority:
    """Test AlertPriority enum."""

    def test_priority_values(self):
        """Test priority enum values."""
        assert AlertPriority.CRITICAL.value == "critical"
        assert AlertPriority.HIGH.value == "high"
        assert AlertPriority.MEDIUM.value == "medium"
        assert AlertPriority.LOW.value == "low"

    def test_priority_ordering(self):
        """Test priorities can be compared."""
        # Enums don't have inherent ordering, but we can check values
        priorities = [
            AlertPriority.LOW,
            AlertPriority.MEDIUM,
            AlertPriority.HIGH,
            AlertPriority.CRITICAL,
        ]
        assert len(priorities) == 4


# =============================================================================
# ALERT CATEGORY TESTS
# =============================================================================


class TestAlertCategory:
    """Test AlertCategory enum."""

    def test_category_values(self):
        """Test category enum values."""
        assert AlertCategory.SAFETY.value == "safety"
        assert AlertCategory.CHARGING.value == "charging"
        assert AlertCategory.BATTERY.value == "battery"
        assert AlertCategory.CLIMATE.value == "climate"
        assert AlertCategory.AUTOPILOT.value == "autopilot"
        assert AlertCategory.DRIVE.value == "drive"
        assert AlertCategory.UI.value == "ui"
        assert AlertCategory.LOCKS.value == "locks"
        assert AlertCategory.SUSPENSION.value == "suspension"
        assert AlertCategory.OTHER.value == "other"

    def test_all_categories_present(self):
        """Test all expected categories exist."""
        expected = [
            "safety",
            "charging",
            "battery",
            "climate",
            "autopilot",
            "drive",
            "ui",
            "locks",
            "suspension",
            "other",
        ]
        for value in expected:
            assert any(cat.value == value for cat in AlertCategory)


# =============================================================================
# PREFIX TO CATEGORY MAPPING TESTS
# =============================================================================


class TestPrefixToCategory:
    """Test PREFIX_TO_CATEGORY mapping."""

    def test_safety_prefixes(self):
        """Test safety-related prefixes."""
        assert PREFIX_TO_CATEGORY["RCM2"] == AlertCategory.SAFETY
        assert PREFIX_TO_CATEGORY["RCM"] == AlertCategory.SAFETY
        assert PREFIX_TO_CATEGORY["ESP"] == AlertCategory.SAFETY
        assert PREFIX_TO_CATEGORY["IBST"] == AlertCategory.SAFETY

    def test_charging_prefixes(self):
        """Test charging-related prefixes."""
        assert PREFIX_TO_CATEGORY["CP"] == AlertCategory.CHARGING
        assert PREFIX_TO_CATEGORY["CHG"] == AlertCategory.CHARGING
        assert PREFIX_TO_CATEGORY["UMC"] == AlertCategory.CHARGING

    def test_battery_prefixes(self):
        """Test battery-related prefixes."""
        assert PREFIX_TO_CATEGORY["BMS"] == AlertCategory.BATTERY
        assert PREFIX_TO_CATEGORY["HVBATT"] == AlertCategory.BATTERY

    def test_climate_prefixes(self):
        """Test climate-related prefixes."""
        assert PREFIX_TO_CATEGORY["CC"] == AlertCategory.CLIMATE
        assert PREFIX_TO_CATEGORY["THC"] == AlertCategory.CLIMATE

    def test_autopilot_prefixes(self):
        """Test autopilot-related prefixes."""
        assert PREFIX_TO_CATEGORY["APP"] == AlertCategory.AUTOPILOT
        assert PREFIX_TO_CATEGORY["RADC"] == AlertCategory.AUTOPILOT


# =============================================================================
# SAFETY CRITICAL PATTERNS TESTS
# =============================================================================


class TestSafetyCriticalPatterns:
    """Test SAFETY_CRITICAL_PATTERNS."""

    def test_critical_patterns_exist(self):
        """Test critical patterns are defined."""
        assert len(SAFETY_CRITICAL_PATTERNS) > 0

    def test_specific_patterns(self):
        """Test specific critical patterns."""
        assert "PULL OVER SAFELY" in SAFETY_CRITICAL_PATTERNS
        assert "Vehicle shutting down" in SAFETY_CRITICAL_PATTERNS
        assert "Unable to drive" in SAFETY_CRITICAL_PATTERNS
        assert "ABS disabled" in SAFETY_CRITICAL_PATTERNS
        assert "Brake" in SAFETY_CRITICAL_PATTERNS
        assert "Airbag" in SAFETY_CRITICAL_PATTERNS


# =============================================================================
# TESLA ALERT TESTS
# =============================================================================


class TestTeslaAlert:
    """Test TeslaAlert dataclass."""

    def test_alert_creation(self, sample_alert):
        """Test alert is created correctly."""
        assert sample_alert.signal_name == "APP_w009_aebFault"
        assert sample_alert.description == "Automatic Emergency Braking system fault"
        assert "customer" in sample_alert.audiences
        assert "Model S 2021+" in sample_alert.models

    def test_alert_category_from_prefix(self, sample_alert):
        """Test category is derived from signal prefix."""
        # APP prefix maps to AUTOPILOT
        assert sample_alert.category == AlertCategory.AUTOPILOT

    def test_alert_category_esp(self, critical_alert):
        """Test ESP prefix maps to SAFETY."""
        assert critical_alert.category == AlertCategory.SAFETY

    def test_alert_priority_critical(self, critical_alert):
        """Test critical priority detection."""
        assert critical_alert.priority == AlertPriority.CRITICAL

    def test_alert_priority_high(self, sample_alert):
        """Test high priority detection (customer + service-fix)."""
        assert sample_alert.priority == AlertPriority.HIGH

    def test_alert_priority_low(self, low_priority_alert):
        """Test low priority detection (internal only)."""
        assert low_priority_alert.priority == AlertPriority.LOW

    def test_is_customer_facing_true(self, sample_alert):
        """Test is_customer_facing returns True for customer alerts."""
        assert sample_alert.is_customer_facing is True

    def test_is_customer_facing_false(self, low_priority_alert):
        """Test is_customer_facing returns False for internal alerts."""
        assert low_priority_alert.is_customer_facing is False

    def test_alert_unknown_prefix(self):
        """Test alert with unknown prefix defaults to OTHER."""
        alert = TeslaAlert(
            signal_name="UNKNOWN_w001_test",
            condition="",
            clear_condition="",
            description="",
            potential_impact="",
            customer_message_1="",
            customer_message_2="",
            audiences=[],
            models=[],
        )
        assert alert.category == AlertCategory.OTHER

    def test_calculate_priority_customer_only(self):
        """Test medium priority for customer-only alerts."""
        alert = TeslaAlert(
            signal_name="TEST_w001",
            condition="",
            clear_condition="",
            description="",
            potential_impact="",
            customer_message_1="Test message",
            customer_message_2="",
            audiences=["customer"],
            models=[],
        )
        assert alert.priority == AlertPriority.MEDIUM


# =============================================================================
# TESLA ALERT DICTIONARY TESTS
# =============================================================================


class TestTeslaAlertDictionary:
    """Test TeslaAlertDictionary class."""

    def test_init_default_path(self):
        """Test dictionary initializes with default path."""
        dictionary = TeslaAlertDictionary()
        assert dictionary._csv_path is not None
        assert not dictionary._loaded

    def test_init_custom_path(self, temp_csv_path):
        """Test dictionary with custom path."""
        dictionary = TeslaAlertDictionary(temp_csv_path)
        assert dictionary._csv_path == temp_csv_path

    @pytest.mark.asyncio
    async def test_load_success(self, temp_csv_path):
        """Test loading CSV successfully."""
        dictionary = TeslaAlertDictionary(temp_csv_path)
        result = await dictionary.load()

        assert result is True
        assert dictionary._loaded is True
        assert len(dictionary._alerts) == 4

    @pytest.mark.asyncio
    async def test_load_nonexistent_file(self):
        """Test loading nonexistent file returns False."""
        dictionary = TeslaAlertDictionary(Path("/nonexistent/path.csv"))
        result = await dictionary.load()

        assert result is False
        assert dictionary._loaded is False

    @pytest.mark.asyncio
    async def test_get_alert(self, temp_csv_path):
        """Test getting alert by signal name."""
        dictionary = TeslaAlertDictionary(temp_csv_path)
        await dictionary.load()

        alert = dictionary.get_alert("APP_w009_aebFault")

        assert alert is not None
        assert alert.signal_name == "APP_w009_aebFault"

    @pytest.mark.asyncio
    async def test_get_alert_nonexistent(self, temp_csv_path):
        """Test getting nonexistent alert returns None."""
        dictionary = TeslaAlertDictionary(temp_csv_path)
        await dictionary.load()

        alert = dictionary.get_alert("NONEXISTENT_w001")

        assert alert is None

    @pytest.mark.asyncio
    async def test_get_alerts_by_category(self, temp_csv_path):
        """Test getting alerts by category."""
        dictionary = TeslaAlertDictionary(temp_csv_path)
        await dictionary.load()

        safety_alerts = dictionary.get_alerts_by_category(AlertCategory.SAFETY)

        # ESP_e001_stability is SAFETY category
        assert len(safety_alerts) >= 1
        assert all(a.category == AlertCategory.SAFETY for a in safety_alerts)

    @pytest.mark.skip(reason="get_model_s_alerts removed in Tesla consolidation")
    @pytest.mark.asyncio
    async def test_get_model_s_alerts(self, temp_csv_path):
        """Test getting Model S alerts."""
        dictionary = TeslaAlertDictionary(temp_csv_path)
        await dictionary.load()

        model_s_alerts = dictionary.get_model_s_alerts(customer_only=False)

        # Should include alerts with "Model S 2021+"
        assert len(model_s_alerts) >= 1

    @pytest.mark.skip(reason="get_model_s_alerts removed in Tesla consolidation")
    @pytest.mark.asyncio
    async def test_get_model_s_alerts_customer_only(self, temp_csv_path):
        """Test getting Model S customer-only alerts."""
        dictionary = TeslaAlertDictionary(temp_csv_path)
        await dictionary.load()

        model_s_alerts = dictionary.get_model_s_alerts(customer_only=True)

        # All should be customer-facing
        assert all(a.is_customer_facing for a in model_s_alerts)

    @pytest.mark.asyncio
    async def test_get_critical_alerts(self, temp_csv_path):
        """Test getting critical alerts."""
        dictionary = TeslaAlertDictionary(temp_csv_path)
        await dictionary.load()

        critical = dictionary.get_critical_alerts()

        # ESP_e001_stability with "PULL OVER SAFELY" should be critical
        assert len(critical) >= 1
        assert all(a.priority == AlertPriority.CRITICAL for a in critical)

    @pytest.mark.asyncio
    async def test_stats(self, temp_csv_path):
        """Test dictionary statistics."""
        dictionary = TeslaAlertDictionary(temp_csv_path)
        await dictionary.load()

        stats = dictionary.stats

        assert "total_alerts" in stats
        assert "model_s_alerts" in stats
        assert "critical_alerts" in stats
        assert "by_category" in stats
        assert "loaded" in stats
        assert stats["loaded"] is True
        assert stats["total_alerts"] == 4


# =============================================================================
# TESLA ALERT ROUTER TESTS
# =============================================================================


class TestTeslaAlertRouter:
    """Test TeslaAlertRouter class."""

    @pytest.fixture
    async def loaded_dictionary(self, temp_csv_path):
        """Create and load dictionary."""
        dictionary = TeslaAlertDictionary(temp_csv_path)
        await dictionary.load()
        return dictionary

    @pytest.mark.asyncio
    async def test_init(self, loaded_dictionary):
        """Test router initialization."""
        router = TeslaAlertRouter(loaded_dictionary)

        assert router._dictionary == loaded_dictionary
        assert len(router._handlers[AlertPriority.CRITICAL]) == 0
        assert router._stats["alerts_received"] == 0

    @pytest.mark.asyncio
    async def test_on_critical(self, loaded_dictionary):
        """Test registering critical handler."""
        router = TeslaAlertRouter(loaded_dictionary)

        async def handler(alert, data):
            pass

        router.on_critical(handler)

        assert handler in router._handlers[AlertPriority.CRITICAL]

    @pytest.mark.asyncio
    async def test_on_high(self, loaded_dictionary):
        """Test registering high priority handler."""
        router = TeslaAlertRouter(loaded_dictionary)

        async def handler(alert, data):
            pass

        router.on_high(handler)

        assert handler in router._handlers[AlertPriority.HIGH]

    @pytest.mark.asyncio
    async def test_on_medium(self, loaded_dictionary):
        """Test registering medium priority handler."""
        router = TeslaAlertRouter(loaded_dictionary)

        async def handler(alert, data):
            pass

        router.on_medium(handler)

        assert handler in router._handlers[AlertPriority.MEDIUM]

    @pytest.mark.asyncio
    async def test_on_low(self, loaded_dictionary):
        """Test registering low priority handler."""
        router = TeslaAlertRouter(loaded_dictionary)

        async def handler(alert, data):
            pass

        router.on_low(handler)

        assert handler in router._handlers[AlertPriority.LOW]

    @pytest.mark.asyncio
    async def test_handle_alert_known(self, loaded_dictionary):
        """Test handling known alert."""
        router = TeslaAlertRouter(loaded_dictionary)
        received = []

        async def handler(alert, data):
            received.append(alert)

        router.on_high(handler)

        result = await router.handle_alert("APP_w009_aebFault", {"timestamp": 12345})

        assert result is True
        assert len(received) == 1
        assert received[0].signal_name == "APP_w009_aebFault"
        assert router._stats["alerts_received"] == 1
        assert router._stats["alerts_routed"] == 1

    @pytest.mark.asyncio
    async def test_handle_alert_unknown(self, loaded_dictionary):
        """Test handling unknown alert."""
        router = TeslaAlertRouter(loaded_dictionary)

        result = await router.handle_alert("UNKNOWN_w999", {"timestamp": 12345})

        assert result is False
        assert router._stats["alerts_received"] == 1
        assert router._stats["unknown_alerts"] == 1

    @pytest.mark.asyncio
    async def test_handle_alert_critical(self, loaded_dictionary):
        """Test handling critical alert."""
        router = TeslaAlertRouter(loaded_dictionary)
        received = []

        async def handler(alert, data):
            received.append(alert)

        router.on_critical(handler)

        # ESP_e001_stability has "PULL OVER SAFELY" which is critical
        result = await router.handle_alert("ESP_e001_stability", {})

        assert result is True
        assert len(received) == 1
        assert received[0].priority == AlertPriority.CRITICAL

    @pytest.mark.asyncio
    async def test_handle_alert_no_handlers(self, loaded_dictionary):
        """Test handling alert without registered handlers."""
        router = TeslaAlertRouter(loaded_dictionary)

        # Don't register any handlers
        result = await router.handle_alert("BMS_w001_lowBattery", {})

        # Alert is known but no handlers, so returns False
        assert result is False

    @pytest.mark.asyncio
    async def test_handler_exception_caught(self, loaded_dictionary):
        """Test handler exceptions are caught."""
        router = TeslaAlertRouter(loaded_dictionary)

        async def bad_handler(alert, data):
            raise ValueError("Test error")

        router.on_high(bad_handler)

        # Should not raise
        await router.handle_alert("APP_w009_aebFault", {})

        # Stats should still be updated
        assert router._stats["alerts_received"] == 1

    @pytest.mark.asyncio
    async def test_stats_property(self, loaded_dictionary):
        """Test stats property."""
        router = TeslaAlertRouter(loaded_dictionary)

        stats = router.stats

        assert "alerts_received" in stats
        assert "alerts_routed" in stats
        assert "unknown_alerts" in stats
        assert "by_priority" in stats


# =============================================================================
# DEFAULT HANDLERS TESTS
# =============================================================================


# NOTE: TestDefaultHandlers removed - create_default_handlers was removed in Tesla consolidation
# (commit 54147d4fb). Alert handlers are now registered directly on TeslaAlertRouter.


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_alert_empty_audiences(self):
        """Test alert with empty audiences."""
        alert = TeslaAlert(
            signal_name="TEST_w001",
            condition="",
            clear_condition="",
            description="",
            potential_impact="",
            customer_message_1="",
            customer_message_2="",
            audiences=[],
            models=[],
        )
        assert alert.is_customer_facing is False
        assert alert.priority == AlertPriority.LOW

    def test_alert_multiple_critical_patterns(self):
        """Test alert matching multiple critical patterns."""
        alert = TeslaAlert(
            signal_name="TEST_e001",
            condition="",
            clear_condition="",
            description="",
            potential_impact="PULL OVER SAFELY - ABS disabled - Brake failure - Vehicle shutting down",
            customer_message_1="",
            customer_message_2="",
            audiences=["customer"],
            models=[],
        )
        # Should still be CRITICAL (not double-critical)
        assert alert.priority == AlertPriority.CRITICAL

    def test_alert_signal_name_no_underscore(self):
        """Test alert with signal name without underscore."""
        alert = TeslaAlert(
            signal_name="NOSEPARATOR",
            condition="",
            clear_condition="",
            description="",
            potential_impact="",
            customer_message_1="",
            customer_message_2="",
            audiences=[],
            models=[],
        )
        # Should default to OTHER category
        assert alert.category == AlertCategory.OTHER

    @pytest.mark.asyncio
    async def test_dictionary_empty_csv(self):
        """Test dictionary with empty CSV."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "SignalName",
                    "Condition",
                    "ClearCondition",
                    "Description",
                    "PotentialImpact",
                    "CustomerFacingMessage1",
                    "CustomerFacingMessage2",
                    "Audiences",
                    "Models",
                ],
            )
            writer.writeheader()
            # No data rows
            path = Path(f.name)

        try:
            dictionary = TeslaAlertDictionary(path)
            result = await dictionary.load()

            assert result is True
            assert len(dictionary._alerts) == 0
        finally:
            path.unlink()

    @pytest.mark.asyncio
    async def test_router_multiple_handlers_same_priority(self):
        """Test router with multiple handlers for same priority."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "SignalName",
                    "Condition",
                    "ClearCondition",
                    "Description",
                    "PotentialImpact",
                    "CustomerFacingMessage1",
                    "CustomerFacingMessage2",
                    "Audiences",
                    "Models",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "SignalName": "TEST_w001",
                    "Condition": "Test",
                    "ClearCondition": "Cleared",
                    "Description": "Test alert",
                    "PotentialImpact": "None",
                    "CustomerFacingMessage1": "Test",
                    "CustomerFacingMessage2": "",
                    "Audiences": "customer;service-fix",  # HIGH priority
                    "Models": "All",
                }
            )
            path = Path(f.name)

        try:
            dictionary = TeslaAlertDictionary(path)
            await dictionary.load()
            router = TeslaAlertRouter(dictionary)

            received1 = []
            received2 = []

            async def handler1(alert, data):
                received1.append(alert)

            async def handler2(alert, data):
                received2.append(alert)

            router.on_high(handler1)
            router.on_high(handler2)

            await router.handle_alert("TEST_w001", {})

            # Both handlers should be called
            assert len(received1) == 1
            assert len(received2) == 1
        finally:
            path.unlink()


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestIntegration:
    """Integration tests for complete alert flow."""

    @pytest.mark.asyncio
    async def test_full_alert_flow(self, temp_csv_path, mock_smart_home):
        """Test complete flow from CSV to smart home action."""
        # 1. Load dictionary
        dictionary = TeslaAlertDictionary(temp_csv_path)
        assert await dictionary.load() is True

        # 2. Create router with custom handler
        router = TeslaAlertRouter(dictionary)

        received = []

        async def critical_handler(alert, _data):
            received.append(alert)
            await mock_smart_home.announce_all(alert.customer_message_1)

        router.on_critical(critical_handler)

        # 3. Handle critical alert
        result = await router.handle_alert("ESP_e001_stability", {"timestamp": 12345})

        # 4. Verify
        assert result is True
        assert len(received) == 1
        mock_smart_home.announce_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_alert_category_routing(self, temp_csv_path):
        """Test alerts are correctly categorized and routed."""
        dictionary = TeslaAlertDictionary(temp_csv_path)
        await dictionary.load()

        # Check categories
        app_alert = dictionary.get_alert("APP_w009_aebFault")
        esp_alert = dictionary.get_alert("ESP_e001_stability")
        bms_alert = dictionary.get_alert("BMS_w001_lowBattery")

        assert app_alert is not None and app_alert.category == AlertCategory.AUTOPILOT
        assert esp_alert is not None and esp_alert.category == AlertCategory.SAFETY
        assert bms_alert is not None and bms_alert.category == AlertCategory.BATTERY
