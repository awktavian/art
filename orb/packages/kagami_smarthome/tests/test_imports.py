"""Test that all imports work correctly."""


def test_types_import():
    """Test type imports."""
    from kagami_smarthome import (
        ActivityContext,
        HomeState,
        PresenceEvent,
        PresenceState,
        SecurityState,
        SmartHomeConfig,
    )

    assert ActivityContext is not None
    assert HomeState is not None
    assert PresenceEvent is not None
    assert PresenceState is not None
    assert SecurityState is not None
    assert SmartHomeConfig is not None


def test_controller_import():
    """Test controller imports."""
    from kagami_smarthome import SmartHomeController

    # Use DI - create instance directly, no singletons
    assert SmartHomeController is not None


def test_presence_import():
    """Test presence engine import."""
    from kagami_smarthome import PresenceEngine

    assert PresenceEngine is not None


def test_integrations_import():
    """Test integration imports."""
    from kagami_smarthome import (
        Control4Integration,
        DenonIntegration,
        UniFiIntegration,
    )

    assert Control4Integration is not None
    assert DenonIntegration is not None
    assert UniFiIntegration is not None


def test_config_creation():
    """Test SmartHomeConfig instantiation."""
    from kagami_smarthome import SmartHomeConfig

    config = SmartHomeConfig(
        unifi_host="192.168.1.1",
        control4_host="192.168.1.2",
        denon_host="192.168.1.12",
        known_devices=["aa:bb:cc:dd:ee:ff"],
    )

    assert config.unifi_host == "192.168.1.1"
    assert config.control4_host == "192.168.1.2"
    assert config.denon_host == "192.168.1.12"
    assert config.known_devices == ["aa:bb:cc:dd:ee:ff"]


def test_controller_creation():
    """Test SmartHomeController instantiation."""
    from kagami_smarthome import SmartHomeConfig, SmartHomeController

    config = SmartHomeConfig()
    controller = SmartHomeController(config)

    assert controller is not None
    assert controller.config == config


def test_presence_engine_creation():
    """Test PresenceEngine instantiation."""
    from kagami_smarthome import PresenceEngine, SmartHomeConfig

    config = SmartHomeConfig()
    engine = PresenceEngine(config)

    assert engine is not None
    state = engine.get_state()
    assert state.presence == state.presence  # Just verify it exists


def test_presence_states():
    """Test PresenceState enum values."""
    from kagami_smarthome import PresenceState

    assert PresenceState.AWAY.value == "away"
    assert PresenceState.HOME.value == "home"
    assert PresenceState.ACTIVE.value == "active"
    assert PresenceState.SLEEPING.value == "sleeping"
    assert PresenceState.ARRIVING.value == "arriving"


def test_activity_contexts():
    """Test ActivityContext enum values."""
    from kagami_smarthome import ActivityContext

    assert ActivityContext.UNKNOWN.value == "unknown"
    assert ActivityContext.WAKING.value == "waking"
    assert ActivityContext.WORKING.value == "working"
    assert ActivityContext.COOKING.value == "cooking"
    assert ActivityContext.RELAXING.value == "relaxing"
    assert ActivityContext.SLEEPING.value == "sleeping"


def test_security_states():
    """Test SecurityState enum values."""
    from kagami_smarthome import SecurityState

    assert SecurityState.DISARMED.value == "disarmed"
    assert SecurityState.ARMED_STAY.value == "armed_stay"
    assert SecurityState.ARMED_AWAY.value == "armed_away"
    assert SecurityState.ARMED_NIGHT.value == "armed_night"
    assert SecurityState.ALARM.value == "alarm"
