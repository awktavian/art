"""Tests for SmartHome Advanced Automation.

Tests circadian rhythm, occupancy simulation, and predictive HVAC.

Created: December 30, 2025
"""

from __future__ import annotations

import pytest

from kagami_smarthome.advanced_automation import (
    AdvancedAutomationManager,
    CircadianPhase,
    CircadianSettings,
    GuestMode,
    GuestModeConfig,
    OccupancySimulator,
    PredictiveHVAC,
    SleepOptimizer,
    StateReconciler,
    VacationModeConfig,
    get_advanced_automation,
    get_circadian_color_temp,
    get_circadian_max_brightness,
    get_current_circadian_phase,
    start_advanced_automation,
)

# =============================================================================
# CIRCADIAN PHASE TESTS
# =============================================================================


class TestCircadianPhase:
    """Test CircadianPhase enum."""

    def test_all_phases_defined(self):
        """All circadian phases are defined."""
        assert CircadianPhase.DAWN is not None
        assert CircadianPhase.MORNING is not None
        assert CircadianPhase.MIDDAY is not None
        assert CircadianPhase.AFTERNOON is not None
        assert CircadianPhase.EVENING is not None
        assert CircadianPhase.NIGHT is not None
        assert CircadianPhase.LATE_NIGHT is not None

    def test_phase_values(self):
        """Phase values are strings."""
        assert isinstance(CircadianPhase.DAWN.value, str)
        assert isinstance(CircadianPhase.NIGHT.value, str)


# =============================================================================
# CIRCADIAN SETTINGS TESTS
# =============================================================================


class TestCircadianSettings:
    """Test CircadianSettings dataclass."""

    def test_creation(self):
        """CircadianSettings can be created."""
        settings = CircadianSettings(
            phase=CircadianPhase.MORNING,
            color_temp_kelvin=3500,
            max_brightness=100,
            bias_brightness=15,
        )
        assert settings is not None
        assert settings.phase == CircadianPhase.MORNING

    def test_for_phase_factory(self):
        """CircadianSettings.for_phase factory works."""
        settings = CircadianSettings.for_phase(CircadianPhase.EVENING)
        assert settings is not None
        assert settings.phase == CircadianPhase.EVENING

    def test_color_temp_ranges(self):
        """Color temperatures are in valid ranges."""
        for phase in CircadianPhase:
            settings = CircadianSettings.for_phase(phase)
            assert 2000 <= settings.color_temp_kelvin <= 7000

    def test_brightness_ranges(self):
        """Brightness values are in valid ranges."""
        for phase in CircadianPhase:
            settings = CircadianSettings.for_phase(phase)
            assert 0 <= settings.max_brightness <= 100
            assert 0 <= settings.bias_brightness <= 100


# =============================================================================
# CIRCADIAN FUNCTION TESTS
# =============================================================================


class TestCircadianFunctions:
    """Test circadian helper functions."""

    def test_get_current_phase(self):
        """get_current_circadian_phase returns a phase."""
        phase = get_current_circadian_phase()
        assert phase is not None
        assert isinstance(phase, CircadianPhase)

    def test_get_color_temp(self):
        """get_circadian_color_temp returns temperature."""
        temp = get_circadian_color_temp()
        assert temp is not None
        assert isinstance(temp, (int, float))
        # Color temp typically 2700K to 6500K
        assert 2000 <= temp <= 7000

    def test_get_max_brightness(self):
        """get_circadian_max_brightness returns brightness."""
        brightness = get_circadian_max_brightness()
        assert brightness is not None
        assert isinstance(brightness, (int, float))
        assert 0 <= brightness <= 100


# =============================================================================
# GUEST MODE TESTS
# =============================================================================


class TestGuestMode:
    """Test GuestMode enum."""

    def test_modes_defined(self):
        """Guest modes are defined."""
        assert GuestMode.NONE is not None
        assert GuestMode.GUEST_PRESENT is not None
        assert GuestMode.PARTY is not None
        assert GuestMode.AIRBNB is not None


class TestGuestModeConfig:
    """Test GuestModeConfig dataclass."""

    def test_creation(self):
        """GuestModeConfig can be created."""
        config = GuestModeConfig()
        assert config is not None


# =============================================================================
# VACATION MODE TESTS
# =============================================================================


class TestVacationModeConfig:
    """Test VacationModeConfig dataclass."""

    def test_creation(self):
        """VacationModeConfig can be created."""
        config = VacationModeConfig()
        assert config is not None


# =============================================================================
# OCCUPANCY SIMULATOR TESTS
# =============================================================================


class TestOccupancySimulator:
    """Test OccupancySimulator class."""

    def test_class_exists(self):
        """OccupancySimulator class is defined."""
        assert OccupancySimulator is not None
        assert callable(OccupancySimulator)


# =============================================================================
# PREDICTIVE HVAC TESTS
# =============================================================================


class TestPredictiveHVAC:
    """Test PredictiveHVAC class."""

    def test_class_exists(self):
        """PredictiveHVAC class is defined."""
        assert PredictiveHVAC is not None
        assert callable(PredictiveHVAC)


# =============================================================================
# SLEEP OPTIMIZER TESTS
# =============================================================================


class TestSleepOptimizer:
    """Test SleepOptimizer class."""

    def test_class_exists(self):
        """SleepOptimizer class is defined."""
        assert SleepOptimizer is not None
        assert callable(SleepOptimizer)


# =============================================================================
# STATE RECONCILER TESTS
# =============================================================================


class TestStateReconciler:
    """Test StateReconciler class."""

    def test_class_exists(self):
        """StateReconciler class is defined."""
        assert StateReconciler is not None
        assert callable(StateReconciler)


# =============================================================================
# ADVANCED AUTOMATION MANAGER TESTS
# =============================================================================


class TestAdvancedAutomationManager:
    """Test AdvancedAutomationManager class."""

    def test_class_exists(self):
        """AdvancedAutomationManager class is defined."""
        assert AdvancedAutomationManager is not None
        assert callable(AdvancedAutomationManager)

    def test_factory_function_exists(self):
        """get_advanced_automation function is callable."""
        assert callable(get_advanced_automation)

    def test_start_function_exists(self):
        """start_advanced_automation function is callable."""
        assert callable(start_advanced_automation)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
