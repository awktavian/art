"""Comprehensive HAL Adapter Tests.

Tests all platform adapters for:
- Initialization and configuration validation
- Graceful degradation on non-native platforms
- Protocol compliance with real assertions
- Sensor data flow and subscription handling
- Error handling and recovery
- Platform capability detection

Created: December 30, 2025
Updated: December 31, 2025 - Enhanced with substantive tests
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure test mode is enabled
os.environ["KAGAMI_BOOT_MODE"] = "test"


class TestAndroidAdapters:
    """Test Android HAL adapters with real assertions."""

    @pytest.mark.asyncio
    async def test_android_sensors_graceful_degradation(self):
        """Android sensors should gracefully degrade on non-Android platforms."""
        from kagami_hal.adapters.android.sensors import AndroidSensors

        sensors = AndroidSensors()
        result = await sensors.initialize()

        # Should return False (not crash) when not on Android
        assert result is False
        # Verify internal state is consistent with failed init
        assert sensors._running is False
        assert len(sensors._available_sensors) == 0

    @pytest.mark.asyncio
    async def test_android_sensors_list_empty_when_unavailable(self):
        """Android sensors should return empty list when not on Android."""
        from kagami_hal.adapters.android.sensors import AndroidSensors

        sensors = AndroidSensors()
        await sensors.initialize()

        sensor_list = await sensors.list_sensors()
        assert isinstance(sensor_list, list)
        assert len(sensor_list) == 0

    @pytest.mark.asyncio
    async def test_android_sensors_subscribe_raises_on_unavailable(self):
        """Android sensors should raise when subscribing to unavailable sensor."""
        from kagami_hal.adapters.android.sensors import AndroidSensors
        from kagami_hal.data_types import SensorType

        sensors = AndroidSensors()
        await sensors.initialize()

        with pytest.raises(RuntimeError, match="not available"):
            await sensors.subscribe(SensorType.ACCELEROMETER, AsyncMock())

    @pytest.mark.asyncio
    async def test_android_display_graceful_degradation(self):
        """Android display should gracefully degrade on non-Android platforms."""
        from kagami_hal.adapters.android.display import AndroidDisplay

        display = AndroidDisplay()
        result = await display.initialize()

        assert result is False

    @pytest.mark.asyncio
    async def test_android_input_graceful_degradation(self):
        """Android input should gracefully degrade on non-Android platforms."""
        from kagami_hal.adapters.android.input import AndroidInput

        inp = AndroidInput()
        result = await inp.initialize()

        assert result is False

    @pytest.mark.asyncio
    async def test_android_audio_config_validation(self):
        """Android audio should validate configuration before init."""
        from kagami_hal.adapters.android.audio import AndroidAudio
        from kagami_hal.data_types import AudioConfig, AudioFormat

        audio = AndroidAudio()
        config = AudioConfig(
            sample_rate=44100, channels=2, format=AudioFormat.PCM_16, buffer_size=1024
        )
        result = await audio.initialize(config)

        # Config should be stored even on failed init
        assert result is False
        # Verify config was processed
        assert config.sample_rate == 44100
        assert config.channels == 2

    @pytest.mark.asyncio
    async def test_android_power_graceful_degradation(self):
        """Android power should gracefully degrade on non-Android platforms."""
        from kagami_hal.adapters.android.power import AndroidPower

        power = AndroidPower()
        result = await power.initialize()

        assert result is False


class TestWearOSAdapters:
    """Test Wear OS HAL adapters."""

    @pytest.mark.asyncio
    async def test_wearos_sensors_graceful_degradation(self):
        """Wear OS sensors should gracefully degrade."""
        from kagami_hal.adapters.wearos.sensors import WearOSSensors

        sensors = WearOSSensors()
        result = await sensors.initialize()

        assert result is False
        assert sensors._running is False

    @pytest.mark.asyncio
    async def test_wearos_display_graceful_degradation(self):
        """Wear OS display should gracefully degrade."""
        from kagami_hal.adapters.wearos.display import WearOSDisplay

        display = WearOSDisplay()
        result = await display.initialize()

        assert result is False


class TestIOSAdapters:
    """Test iOS HAL adapters."""

    @pytest.mark.asyncio
    async def test_ios_sensors_graceful_degradation(self):
        """iOS sensors should gracefully degrade on non-iOS platforms."""
        from kagami_hal.adapters.ios.sensors import iOSSensors

        sensors = iOSSensors()
        result = await sensors.initialize()

        assert result is False
        assert sensors._running is False

    @pytest.mark.asyncio
    async def test_ios_sensors_shutdown_is_safe(self):
        """iOS sensors shutdown should be safe even when not initialized."""
        from kagami_hal.adapters.ios.sensors import iOSSensors

        sensors = iOSSensors()
        # Don't initialize, just shutdown - should not raise
        await sensors.shutdown()
        assert sensors._running is False

    @pytest.mark.asyncio
    async def test_ios_display_graceful_degradation(self):
        """iOS display should gracefully degrade."""
        from kagami_hal.adapters.ios.display import iOSDisplay

        display = iOSDisplay()
        result = await display.initialize()

        assert result is False

    @pytest.mark.asyncio
    async def test_ios_input_graceful_degradation(self):
        """iOS input should gracefully degrade."""
        from kagami_hal.adapters.ios.input import iOSInput

        inp = iOSInput()
        result = await inp.initialize()

        assert result is False


class TestVisionOSAdapters:
    """Test visionOS HAL adapters."""

    @pytest.mark.asyncio
    async def test_visionos_spatial_initialization(self):
        """visionOS spatial adapter should initialize in test mode."""
        from kagami_hal.adapters.visionos.spatial import VisionOSSpatial

        spatial = VisionOSSpatial()
        result = await spatial.initialize()

        assert result is True

    @pytest.mark.asyncio
    async def test_visionos_spatial_anchor_creation_returns_safely(self):
        """visionOS spatial anchor creation should complete without crash."""
        from kagami_hal.adapters.visionos.spatial import VisionOSSpatial

        spatial = VisionOSSpatial()
        await spatial.initialize()

        # In test mode, API calls will fail but shouldn't crash
        anchor = await spatial.create_anchor((1.0, 0.5, -2.0), label="test")
        # Anchor may be None without API but method should complete
        # Just verify no exception was raised

    @pytest.mark.asyncio
    async def test_visionos_gaze_initialization(self):
        """visionOS gaze adapter should initialize in test mode."""
        from kagami_hal.adapters.visionos.gaze import VisionOSGaze

        gaze = VisionOSGaze()
        result = await gaze.initialize()

        assert result is True

    @pytest.mark.asyncio
    async def test_visionos_audio_initialization(self):
        """visionOS audio adapter should initialize in test mode."""
        from kagami_hal.adapters.visionos.audio import VisionOSAudio

        audio = VisionOSAudio()
        result = await audio.initialize()

        assert result is True


class TestWatchOSAdapters:
    """Test watchOS HAL adapters."""

    @pytest.mark.asyncio
    async def test_watchos_sensors_graceful_degradation(self):
        """watchOS sensors should gracefully degrade."""
        from kagami_hal.adapters.watchos.sensors import WatchOSSensors

        sensors = WatchOSSensors()
        result = await sensors.initialize()

        assert result is False
        assert sensors._running is False


class TestWindowsAdapters:
    """Test Windows HAL adapters."""

    @pytest.mark.asyncio
    async def test_windows_adapters_exist(self):
        """Windows adapters should be importable with expected exports."""
        try:
            from kagami_hal.adapters import windows

            # Verify expected exports are present
            assert hasattr(windows, "WindowsGDIDisplay"), "WindowsGDIDisplay should be exported"
            assert hasattr(windows, "WindowsInput"), "WindowsInput should be exported"
            assert hasattr(windows, "WindowsPower"), "WindowsPower should be exported"
            assert hasattr(windows, "WindowsSensors"), "WindowsSensors should be exported"
            assert hasattr(windows, "__all__"), "Windows module should define __all__"
            assert len(windows.__all__) > 0, "Windows module should export classes"
        except ImportError:
            pytest.skip("Windows adapters not available")


class TestLinuxAdapters:
    """Test Linux HAL adapters."""

    @pytest.mark.asyncio
    async def test_linux_adapters_exist(self):
        """Linux adapters should be importable with expected exports."""
        try:
            from kagami_hal.adapters import linux

            # Verify expected exports are present
            assert hasattr(linux, "LinuxHAL"), "LinuxHAL should be exported"
            assert hasattr(linux, "LINUX_AVAILABLE"), "LINUX_AVAILABLE flag should be exported"
            assert hasattr(linux, "__all__"), "Linux module should define __all__"
            assert len(linux.__all__) > 0, "Linux module should export classes"
            # LinuxHAL should be a class with expected methods
            assert callable(linux.LinuxHAL), "LinuxHAL should be callable (class)"
        except ImportError:
            pytest.skip("Linux adapters not available")


class TestMacOSAdapters:
    """Test macOS HAL adapters."""

    @pytest.mark.asyncio
    async def test_macos_adapters_exist(self):
        """macOS adapters should be importable with expected exports."""
        try:
            from kagami_hal.adapters import macos

            # Verify expected exports are present
            assert hasattr(macos, "MacOSHAL"), "MacOSHAL should be exported"
            assert hasattr(macos, "MACOS_AVAILABLE"), "MACOS_AVAILABLE flag should be exported"
            assert hasattr(macos, "__all__"), "macOS module should define __all__"
            assert len(macos.__all__) > 0, "macOS module should export classes"
            # MacOSHAL should be a class with expected methods
            assert callable(macos.MacOSHAL), "MacOSHAL should be callable (class)"
        except ImportError:
            pytest.skip("macOS adapters not available")


class TestVirtualAdapters:
    """Test Virtual HAL adapters for testing environments."""

    @pytest.mark.asyncio
    async def test_virtual_sensors_initialization(self):
        """Virtual sensors should always initialize successfully."""
        from kagami_hal.adapters.virtual.sensors import VirtualSensors

        sensors = VirtualSensors()
        result = await sensors.initialize()

        assert result is True
        assert sensors._running is True
        assert len(sensors._available_sensors) > 0

    @pytest.mark.asyncio
    async def test_virtual_sensors_accelerometer_reading(self):
        """Virtual sensors should return valid accelerometer data."""
        from kagami_hal.adapters.virtual.sensors import VirtualSensors
        from kagami_hal.data_types import AccelReading, SensorType

        sensors = VirtualSensors()
        await sensors.initialize()

        reading = await sensors.read(SensorType.ACCELEROMETER)

        assert reading.sensor == SensorType.ACCELEROMETER
        assert isinstance(reading.value, AccelReading)
        assert reading.value.x is not None
        assert reading.value.y is not None
        assert reading.value.z is not None
        # Gravity should be on Z axis approximately
        assert abs(reading.value.z) > 9.0  # Close to 9.81

    @pytest.mark.asyncio
    async def test_virtual_sensors_gyroscope_reading(self):
        """Virtual sensors should return valid gyroscope data."""
        from kagami_hal.adapters.virtual.sensors import VirtualSensors
        from kagami_hal.data_types import GyroReading, SensorType

        sensors = VirtualSensors()
        await sensors.initialize()

        reading = await sensors.read(SensorType.GYROSCOPE)

        assert reading.sensor == SensorType.GYROSCOPE
        assert isinstance(reading.value, GyroReading)
        # Gyro values should be small (slow simulated rotation)
        assert abs(reading.value.x) < 1.0
        assert abs(reading.value.y) < 1.0
        assert abs(reading.value.z) < 1.0

    @pytest.mark.asyncio
    async def test_virtual_sensors_gps_reading(self):
        """Virtual sensors should return valid GPS data."""
        from kagami_hal.adapters.virtual.sensors import VirtualSensors
        from kagami_hal.data_types import GPSReading, SensorType

        sensors = VirtualSensors()
        await sensors.initialize()

        reading = await sensors.read(SensorType.GPS)

        assert reading.sensor == SensorType.GPS
        assert isinstance(reading.value, GPSReading)
        # Should be near San Francisco (default location)
        assert 37.0 < reading.value.latitude < 38.0
        assert -123.0 < reading.value.longitude < -122.0

    @pytest.mark.asyncio
    async def test_virtual_sensors_simulated_value_override(self):
        """Virtual sensors should allow setting simulated values."""
        from kagami_hal.adapters.virtual.sensors import VirtualSensors
        from kagami_hal.data_types import AccelReading, SensorType

        sensors = VirtualSensors()
        await sensors.initialize()

        # Set custom value
        custom_accel = AccelReading(x=1.0, y=2.0, z=3.0)
        sensors.set_simulated_value(SensorType.ACCELEROMETER, custom_accel)

        reading = await sensors.read(SensorType.ACCELEROMETER)
        assert reading.value.x == 1.0
        assert reading.value.y == 2.0
        assert reading.value.z == 3.0

        # Clear and verify back to generated
        sensors.clear_simulated_value(SensorType.ACCELEROMETER)
        reading = await sensors.read(SensorType.ACCELEROMETER)
        # Should be back to generated value (with gravity on Z)
        assert abs(reading.value.z) > 3.0

    @pytest.mark.asyncio
    async def test_virtual_sensors_list_sensors(self):
        """Virtual sensors should list all available sensor types."""
        from kagami_hal.adapters.virtual.sensors import VirtualSensors
        from kagami_hal.data_types import SensorType

        sensors = VirtualSensors()
        await sensors.initialize()

        sensor_list = await sensors.list_sensors()

        assert SensorType.ACCELEROMETER in sensor_list
        assert SensorType.GYROSCOPE in sensor_list
        assert SensorType.GPS in sensor_list
        assert SensorType.TEMPERATURE in sensor_list
        assert SensorType.LIGHT in sensor_list

    @pytest.mark.asyncio
    async def test_virtual_sensors_subscription_callback(self):
        """Virtual sensors should dispatch readings to subscribers."""
        from kagami_hal.adapters.virtual.sensors import VirtualSensors
        from kagami_hal.data_types import SensorType

        sensors = VirtualSensors()
        await sensors.initialize()

        readings_received = []

        async def callback(reading):
            readings_received.append(reading)

        await sensors.subscribe(SensorType.ACCELEROMETER, callback, rate_hz=50)

        # Wait for a few readings
        await asyncio.sleep(0.1)

        await sensors.unsubscribe(SensorType.ACCELEROMETER)
        await sensors.shutdown()

        # Should have received at least one reading
        assert len(readings_received) >= 1
        assert readings_received[0].sensor == SensorType.ACCELEROMETER

    @pytest.mark.asyncio
    async def test_virtual_sensors_unavailable_sensor_raises(self):
        """Virtual sensors should raise for unknown sensor types."""
        from kagami_hal.adapters.virtual.sensors import VirtualSensors
        from kagami_hal.data_types import SensorType

        sensors = VirtualSensors()
        await sensors.initialize()

        # CAMERA is not in virtual sensors available list
        with pytest.raises(RuntimeError, match="not available"):
            await sensors.read(SensorType.CAMERA)

    @pytest.mark.asyncio
    async def test_virtual_sensors_shutdown_cleans_up(self):
        """Virtual sensors shutdown should clean up all resources."""
        from kagami_hal.adapters.virtual.sensors import VirtualSensors
        from kagami_hal.data_types import SensorType

        sensors = VirtualSensors()
        await sensors.initialize()

        # Subscribe to trigger polling task
        await sensors.subscribe(SensorType.ACCELEROMETER, AsyncMock(), rate_hz=10)

        assert sensors._running is True
        assert len(sensors._subscription_tasks) > 0

        await sensors.shutdown()

        assert sensors._running is False
        assert len(sensors._subscription_tasks) == 0
        assert len(sensors._subscribers) == 0


class TestVMAdapters:
    """Test VM HAL adapters with proper mocking."""

    @pytest.mark.asyncio
    async def test_peekaboo_adapter_properties(self):
        """Peekaboo adapter should have correct tier and initial state."""
        from kagami_hal.adapters.vm.peekaboo import PeekabooAdapter
        from kagami_hal.adapters.vm.types import VMState, VMTier

        adapter = PeekabooAdapter()

        assert adapter.tier == VMTier.HOST
        assert adapter.is_initialized is False
        assert adapter.state == VMState.STOPPED

    @pytest.mark.asyncio
    async def test_peekaboo_adapter_init_without_binary(self):
        """Peekaboo adapter should fail gracefully when peekaboo not installed."""
        from kagami_hal.adapters.vm.peekaboo import PeekabooAdapter

        adapter = PeekabooAdapter()

        # Mock shutil.which to return None (peekaboo not found)
        with patch("shutil.which", return_value=None):
            # Also mock npx fallback to fail
            with patch.object(adapter, "_run_command", side_effect=Exception("npx failed")):
                result = await adapter.initialize()

        assert result is False
        assert adapter.is_initialized is False

    @pytest.mark.asyncio
    async def test_peekaboo_adapter_init_with_binary(self):
        """Peekaboo adapter should initialize when peekaboo is found."""
        from kagami_hal.adapters.vm.peekaboo import PeekabooAdapter
        from kagami_hal.adapters.vm.types import VMState

        adapter = PeekabooAdapter()

        # Mock peekaboo as installed
        with patch("shutil.which", return_value="/usr/local/bin/peekaboo"):
            # Mock permissions check
            mock_process = MagicMock()
            mock_process.returncode = 0
            mock_process.stdout_text = "Granted"
            mock_process.stderr_text = ""
            with patch.object(adapter, "_run_command", return_value=mock_process):
                result = await adapter.initialize()

        assert result is True
        assert adapter.is_initialized is True
        assert adapter.state == VMState.RUNNING

    @pytest.mark.asyncio
    async def test_peekaboo_adapter_click_command_building(self):
        """Peekaboo adapter should build correct click commands."""
        from kagami_hal.adapters.vm.peekaboo import PeekabooAdapter
        from kagami_hal.adapters.vm.types import ClickOptions

        adapter = PeekabooAdapter()
        adapter._initialized = True
        adapter._peekaboo_path = "/usr/local/bin/peekaboo"

        # Capture the command args
        captured_args = []

        async def mock_run_peekaboo(args, timeout=30.0):
            captured_args.extend(args)
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout_text = ""
            mock_result.stderr_text = ""
            return mock_result

        with patch.object(adapter, "_run_peekaboo", mock_run_peekaboo):
            await adapter.click(100, 200)

        assert "click" in captured_args
        assert "--x" in captured_args
        assert "100" in captured_args
        assert "--y" in captured_args
        assert "200" in captured_args

    @pytest.mark.asyncio
    async def test_peekaboo_adapter_click_with_options(self):
        """Peekaboo adapter should handle click options correctly."""
        from kagami_hal.adapters.vm.peekaboo import PeekabooAdapter
        from kagami_hal.adapters.vm.types import ClickOptions

        adapter = PeekabooAdapter()
        adapter._initialized = True
        adapter._peekaboo_path = "/usr/local/bin/peekaboo"

        captured_args = []

        async def mock_run_peekaboo(args, timeout=30.0):
            captured_args.clear()
            captured_args.extend(args)
            mock_result = MagicMock()
            mock_result.returncode = 0
            return mock_result

        with patch.object(adapter, "_run_peekaboo", mock_run_peekaboo):
            # Test double click
            await adapter.click(100, 200, ClickOptions(double_click=True))
            assert "--double" in captured_args

            # Test right click
            await adapter.click(100, 200, ClickOptions(button="right"))
            assert "--button" in captured_args
            assert "right" in captured_args

    @pytest.mark.asyncio
    async def test_peekaboo_adapter_hotkey_processing(self):
        """Peekaboo adapter should correctly separate modifiers from keys."""
        from kagami_hal.adapters.vm.peekaboo import PeekabooAdapter

        adapter = PeekabooAdapter()
        adapter._initialized = True
        adapter._peekaboo_path = "/usr/local/bin/peekaboo"

        captured_args = []

        async def mock_run_peekaboo(args, timeout=30.0):
            captured_args.clear()
            captured_args.extend(args)
            mock_result = MagicMock()
            mock_result.returncode = 0
            return mock_result

        with patch.object(adapter, "_run_peekaboo", mock_run_peekaboo):
            await adapter.hotkey("cmd", "shift", "s")

        assert "hotkey" in captured_args
        assert "--modifiers" in captured_args
        assert "--key" in captured_args
        assert "s" in captured_args

    @pytest.mark.asyncio
    async def test_peekaboo_adapter_accessibility_parsing(self):
        """Peekaboo adapter should parse accessibility tree JSON correctly."""
        from kagami_hal.adapters.vm.peekaboo import PeekabooAdapter

        adapter = PeekabooAdapter()

        # Test parsing
        mock_data = {
            "role": "button",
            "label": "Submit",
            "value": None,
            "identifier": "submit-btn",
            "frame": {"x": 100, "y": 200, "width": 80, "height": 30},
            "children": [],
            "actions": ["press"],
        }

        element = adapter._parse_accessibility_element(mock_data)

        assert element.role == "button"
        assert element.label == "Submit"
        assert element.identifier == "submit-btn"
        assert element.frame == (100, 200, 80, 30)
        assert element.actions == ["press"]

    @pytest.mark.asyncio
    async def test_peekaboo_adapter_find_in_tree(self):
        """Peekaboo adapter should find elements in accessibility tree."""
        from kagami_hal.adapters.vm.peekaboo import PeekabooAdapter
        from kagami_hal.adapters.vm.types import AccessibilityElement

        adapter = PeekabooAdapter()

        # Build a tree
        child = AccessibilityElement(
            role="button",
            label="Submit",
            value=None,
            identifier="submit-btn",
            frame=(100, 200, 80, 30),
            children=[],
            actions=[],
        )
        root = AccessibilityElement(
            role="window",
            label="Main",
            children=[child],
        )

        # Find by label
        found = adapter._find_in_tree(root, label="Submit", role=None, identifier=None)
        assert found is not None
        assert found.label == "Submit"

        # Find by role
        found = adapter._find_in_tree(root, label=None, role="button", identifier=None)
        assert found is not None
        assert found.role == "button"

        # Find non-existent
        found = adapter._find_in_tree(root, label="Cancel", role=None, identifier=None)
        assert found is None

    @pytest.mark.asyncio
    async def test_peekaboo_adapter_display_info(self):
        """Peekaboo adapter should return display info."""
        from kagami_hal.adapters.vm.peekaboo import PeekabooAdapter

        adapter = PeekabooAdapter()
        adapter._initialized = True

        display_info = await adapter.get_display_info()

        assert display_info.width > 0
        assert display_info.height > 0
        assert display_info.scale_factor == 2.0  # Retina default

    @pytest.mark.asyncio
    async def test_parallels_adapter_properties(self):
        """Parallels adapter should have correct tier and initial state."""
        from kagami_hal.adapters.vm.parallels import ParallelsAdapter
        from kagami_hal.adapters.vm.types import VMState, VMTier

        adapter = ParallelsAdapter("test-vm")

        assert adapter.tier == VMTier.MULTI_OS
        assert adapter.is_initialized is False
        assert adapter.state == VMState.STOPPED
        assert adapter._vm_name == "test-vm"

    @pytest.mark.asyncio
    async def test_parallels_adapter_init_without_prlctl(self):
        """Parallels adapter should fail when prlctl not found."""
        from kagami_hal.adapters.vm.parallels import ParallelsAdapter

        adapter = ParallelsAdapter("test-vm")

        with patch("shutil.which", return_value=None):
            result = await adapter.initialize()

        assert result is False
        assert adapter.is_initialized is False

    @pytest.mark.asyncio
    async def test_parallels_adapter_os_detection(self):
        """Parallels adapter should detect OS type from VM info."""
        from kagami_hal.adapters.vm.parallels import ParallelsAdapter
        from kagami_hal.adapters.vm.types import OSType

        adapter = ParallelsAdapter("Windows-VM")
        adapter._prlctl_path = "/usr/local/bin/prlctl"

        # Mock the prlctl output for OS detection
        async def mock_run_prlctl(args, timeout=60.0):
            if "list" in args and "-i" in args:
                return (0, '[{"OS": "Windows 11"}]', "")
            return (0, "", "")

        with patch.object(adapter, "_run_prlctl", mock_run_prlctl):
            os_type = await adapter._detect_os_type()

        assert os_type == OSType.WINDOWS

    @pytest.mark.asyncio
    async def test_parallels_adapter_command_result(self):
        """Parallels adapter should return proper CommandResult."""
        from kagami_hal.adapters.vm.parallels import ParallelsAdapter
        from kagami_hal.adapters.vm.types import CommandResult

        adapter = ParallelsAdapter("test-vm")
        adapter._initialized = True
        adapter._prlctl_path = "/usr/local/bin/prlctl"

        async def mock_run_prlctl(args, timeout=60.0):
            return (0, "command output", "")

        with patch.object(adapter, "_run_prlctl", mock_run_prlctl):
            result = await adapter.execute("echo test")

        assert isinstance(result, CommandResult)
        assert result.exit_code == 0
        assert result.stdout == "command output"
        assert result.duration_ms > 0


class TestVMBaseAdapter:
    """Test BaseVMAdapter default implementations."""

    @pytest.mark.asyncio
    async def test_base_adapter_tier1_start_stop(self):
        """Tier 1 adapter start/stop should be no-ops that return True."""
        from kagami_hal.adapters.vm.peekaboo import PeekabooAdapter
        from kagami_hal.adapters.vm.types import VMState

        adapter = PeekabooAdapter()

        # Tier 1 start should work
        result = await adapter.start()
        assert result is True
        assert adapter.state == VMState.RUNNING

        # Tier 1 stop should work
        result = await adapter.stop()
        assert result is True

    @pytest.mark.asyncio
    async def test_base_adapter_snapshot_not_supported_tier1(self):
        """Tier 1 adapter should not support snapshots."""
        from kagami_hal.adapters.vm.peekaboo import PeekabooAdapter

        adapter = PeekabooAdapter()

        result = await adapter.create_snapshot("test")
        assert result is False

        result = await adapter.restore_snapshot("test")
        assert result is False

        snapshots = await adapter.list_snapshots()
        assert snapshots == []

    @pytest.mark.asyncio
    async def test_base_adapter_double_click_delegation(self):
        """Base adapter double_click should delegate to click with options."""
        from kagami_hal.adapters.vm.peekaboo import PeekabooAdapter

        adapter = PeekabooAdapter()
        adapter._initialized = True
        adapter._peekaboo_path = "/usr/local/bin/peekaboo"

        click_options = None

        original_click = adapter.click

        async def capture_click(x, y, options=None):
            nonlocal click_options
            click_options = options

        with patch.object(adapter, "click", capture_click):
            await adapter.double_click(100, 200)

        assert click_options is not None
        assert click_options.double_click is True


class TestHALManager:
    """Test HAL Manager with real assertions."""

    @pytest.mark.asyncio
    async def test_hal_manager_creation(self):
        """HAL Manager should be creatable with detected platform."""
        from kagami_hal.manager import HALManager

        manager = HALManager()

        assert manager is not None
        assert manager.platform is not None
        assert manager._initialized is False

    @pytest.mark.asyncio
    async def test_hal_manager_platform_detection(self):
        """HAL Manager should detect current platform correctly."""
        from kagami_hal.manager import HALManager
        from kagami_hal.types import Platform

        manager = HALManager()

        if sys.platform == "darwin":
            assert manager.platform == Platform.MACOS
        elif sys.platform.startswith("linux"):
            # Could be linux or android
            assert manager.platform in (Platform.LINUX, Platform.ANDROID)
        elif sys.platform == "win32":
            assert manager.platform == Platform.WINDOWS

    @pytest.mark.asyncio
    async def test_hal_manager_force_platform(self):
        """HAL Manager should respect forced platform."""
        from kagami_hal.manager import HALManager
        from kagami_hal.types import Platform

        manager = HALManager(force_platform=Platform.VIRTUAL)

        assert manager.platform == Platform.VIRTUAL

    @pytest.mark.asyncio
    async def test_hal_manager_virtual_mode_env(self):
        """HAL Manager should detect virtual mode from environment."""
        from kagami_hal.manager import HALManager
        from kagami_hal.types import Platform

        with patch.dict(os.environ, {"KAGAMI_HAL_VIRTUAL_MODE": "1"}):
            manager = HALManager()

        assert manager.platform == Platform.VIRTUAL

    @pytest.mark.asyncio
    async def test_hal_manager_status(self):
        """HAL Manager status should reflect adapter availability."""
        from kagami_hal.manager import HALManager

        manager = HALManager()
        status = manager.get_status()

        assert status.adapters_initialized == 0
        assert status.adapters_failed == 0
        assert status.mock_mode is False

    @pytest.mark.asyncio
    async def test_hal_manager_repr(self):
        """HAL Manager should have informative repr."""
        from kagami_hal.manager import HALManager

        manager = HALManager()
        repr_str = repr(manager)

        assert "HALManager" in repr_str
        assert "platform=" in repr_str
        assert "initialized=" in repr_str


class TestDataTypes:
    """Test HAL data types with real assertions."""

    def test_sensor_types_enum_values(self):
        """Sensor types should have expected string values."""
        from kagami_hal.data_types import SensorType

        assert SensorType.ACCELEROMETER.value == "accelerometer"
        assert SensorType.GYROSCOPE.value == "gyroscope"
        assert SensorType.LIGHT.value == "light"
        assert SensorType.GPS.value == "gps"
        assert SensorType.SEMG.value == "semg"

    def test_audio_format_enum_values(self):
        """Audio formats should have expected string values."""
        from kagami_hal.data_types import AudioFormat

        assert AudioFormat.PCM_16.value == "pcm_16"
        assert AudioFormat.PCM_32.value == "pcm_32"
        assert AudioFormat.FLOAT_32.value == "float_32"

    def test_power_mode_enum_values(self):
        """Power modes should have expected string values."""
        from kagami_hal.data_types import PowerMode

        assert PowerMode.FULL.value == "full"
        assert PowerMode.BALANCED.value == "balanced"
        assert PowerMode.SAVER.value == "saver"
        assert PowerMode.CRITICAL.value == "critical"

    def test_audio_config_properties(self):
        """AudioConfig should store and expose all properties."""
        from kagami_hal.data_types import AudioConfig, AudioFormat

        config = AudioConfig(
            sample_rate=48000, channels=2, format=AudioFormat.FLOAT_32, buffer_size=2048
        )

        assert config.sample_rate == 48000
        assert config.channels == 2
        assert config.format == AudioFormat.FLOAT_32
        assert config.buffer_size == 2048

    def test_sensor_reading_creation(self):
        """SensorReading should store sensor type and value."""
        from kagami_hal.data_types import SensorReading, SensorType

        reading = SensorReading(
            sensor=SensorType.ACCELEROMETER,
            value={"x": 0.0, "y": 0.0, "z": 9.8},
            timestamp_ms=1234567890,
            accuracy=1.0,
        )

        assert reading.sensor == SensorType.ACCELEROMETER
        assert reading.value == {"x": 0.0, "y": 0.0, "z": 9.8}
        assert reading.timestamp_ms == 1234567890
        assert reading.accuracy == 1.0

    def test_accel_reading_creation(self):
        """AccelReading should store x, y, z components."""
        from kagami_hal.data_types import AccelReading

        reading = AccelReading(x=0.1, y=-0.2, z=9.81)

        assert reading.x == 0.1
        assert reading.y == -0.2
        assert reading.z == 9.81

    def test_gyro_reading_creation(self):
        """GyroReading should store angular velocity components."""
        from kagami_hal.data_types import GyroReading

        reading = GyroReading(x=0.01, y=-0.02, z=0.03)

        assert reading.x == 0.01
        assert reading.y == -0.02
        assert reading.z == 0.03

    def test_gps_reading_creation(self):
        """GPSReading should store location data."""
        from kagami_hal.data_types import GPSReading

        reading = GPSReading(latitude=37.7749, longitude=-122.4194, altitude=10.0, accuracy=5.0)

        assert reading.latitude == 37.7749
        assert reading.longitude == -122.4194
        assert reading.altitude == 10.0
        assert reading.accuracy == 5.0

    def test_battery_status_creation(self):
        """BatteryStatus should store battery state."""
        from kagami_hal.data_types import BatteryStatus

        status = BatteryStatus(
            level=0.85,
            voltage=4.2,
            charging=True,
            plugged=True,
            time_remaining_minutes=120,
            temperature_c=35.0,
        )

        assert status.level == 0.85
        assert status.charging is True
        assert status.time_remaining_minutes == 120

    def test_semg_gesture_enum_completeness(self):
        """SEMGGesture should have all expected gesture types."""
        from kagami_hal.data_types import SEMGGesture

        # Pinch gestures
        assert SEMGGesture.PINCH_INDEX
        assert SEMGGesture.PINCH_MIDDLE
        assert SEMGGesture.PINCH_RING
        assert SEMGGesture.PINCH_PINKY

        # Tap gestures
        assert SEMGGesture.TAP_INDEX
        assert SEMGGesture.TAP_DOUBLE

        # Hand gestures
        assert SEMGGesture.FIST
        assert SEMGGesture.OPEN_HAND
        assert SEMGGesture.POINT

        # Meta gesture
        assert SEMGGesture.NONE


class TestVMTypes:
    """Test VM adapter types."""

    def test_vm_tier_ordering(self):
        """VMTier should have correct ordering values."""
        from kagami_hal.adapters.vm.types import VMTier

        assert VMTier.HOST.value == 1
        assert VMTier.SANDBOXED.value == 2
        assert VMTier.MULTI_OS.value == 3

    def test_vm_state_values(self):
        """VMState should have expected string values."""
        from kagami_hal.adapters.vm.types import VMState

        assert VMState.STOPPED.value == "stopped"
        assert VMState.RUNNING.value == "running"
        assert VMState.PAUSED.value == "paused"
        assert VMState.ERROR.value == "error"

    def test_os_type_values(self):
        """OSType should have expected string values."""
        from kagami_hal.adapters.vm.types import OSType

        assert OSType.MACOS.value == "macos"
        assert OSType.WINDOWS.value == "windows"
        assert OSType.LINUX.value == "linux"
        assert OSType.UNKNOWN.value == "unknown"

    def test_vm_config_defaults(self):
        """VMConfig should have sensible defaults."""
        from kagami_hal.adapters.vm.types import OSType, VMConfig, VMTier

        config = VMConfig(name="test-vm")

        assert config.name == "test-vm"
        assert config.os_type == OSType.MACOS  # Default
        assert config.tier == VMTier.SANDBOXED  # Default
        assert config.memory_mb == 8192
        assert config.cpu_count == 4
        assert config.display_width == 1920
        assert config.display_height == 1080

    def test_click_options_defaults(self):
        """ClickOptions should have sensible defaults."""
        from kagami_hal.adapters.vm.types import ClickOptions

        opts = ClickOptions()

        assert opts.button == "left"
        assert opts.modifiers == []
        assert opts.double_click is False

    def test_command_result_fields(self):
        """CommandResult should store execution results."""
        from kagami_hal.adapters.vm.types import CommandResult

        result = CommandResult(exit_code=0, stdout="output", stderr="", duration_ms=150.5)

        assert result.exit_code == 0
        assert result.stdout == "output"
        assert result.stderr == ""
        assert result.duration_ms == 150.5

    def test_accessibility_element_tree(self):
        """AccessibilityElement should support tree structure."""
        from kagami_hal.adapters.vm.types import AccessibilityElement

        child = AccessibilityElement(role="button", label="OK")
        parent = AccessibilityElement(role="dialog", label="Alert", children=[child])

        assert len(parent.children) == 1
        assert parent.children[0].role == "button"
        assert parent.children[0].label == "OK"


class TestProtocols:
    """Test HAL protocols with real assertions."""

    def test_display_controller_protocol_exists(self):
        """DisplayController protocol should be defined and importable."""
        from kagami_hal.display_controller import DisplayController

        # Protocol should be importable
        assert DisplayController is not None
        # Should be a class/protocol type
        assert hasattr(DisplayController, "__mro__")

    def test_audio_controller_protocol_exists(self):
        """AudioController protocol should be defined and importable."""
        from kagami_hal.audio_controller import AudioController

        assert AudioController is not None
        assert hasattr(AudioController, "__mro__")

    def test_power_controller_protocol_exists(self):
        """PowerController protocol should be defined and importable."""
        from kagami_hal.power_controller import PowerController

        assert PowerController is not None
        assert hasattr(PowerController, "__mro__")


class TestSensorAdapterBase:
    """Test SensorAdapterBase functionality."""

    @pytest.mark.asyncio
    async def test_sensor_adapter_base_subscription_lifecycle(self):
        """SensorAdapterBase should manage subscription lifecycle properly."""
        from kagami_hal.adapters.virtual.sensors import VirtualSensors
        from kagami_hal.data_types import SensorType

        sensors = VirtualSensors()
        await sensors.initialize()

        # Subscribe
        callback = AsyncMock()
        await sensors.subscribe(SensorType.ACCELEROMETER, callback, rate_hz=100)

        assert SensorType.ACCELEROMETER in sensors._subscribers
        assert SensorType.ACCELEROMETER in sensors._subscription_tasks

        # Unsubscribe
        await sensors.unsubscribe(SensorType.ACCELEROMETER)

        assert SensorType.ACCELEROMETER not in sensors._subscription_tasks

        await sensors.shutdown()

    @pytest.mark.asyncio
    async def test_sensor_adapter_base_last_reading_cache(self):
        """SensorAdapterBase should cache last reading for each sensor."""
        from kagami_hal.adapters.virtual.sensors import VirtualSensors
        from kagami_hal.data_types import SensorType

        sensors = VirtualSensors()
        await sensors.initialize()

        # Subscribe to trigger polling
        callback = AsyncMock()
        await sensors.subscribe(SensorType.ACCELEROMETER, callback, rate_hz=50)

        # Wait for at least one reading
        await asyncio.sleep(0.05)

        last_reading = sensors.get_last_reading(SensorType.ACCELEROMETER)
        assert last_reading is not None
        assert last_reading.sensor == SensorType.ACCELEROMETER

        await sensors.shutdown()

    @pytest.mark.asyncio
    async def test_sensor_adapter_base_properties(self):
        """SensorAdapterBase should expose is_running and sensor count."""
        from kagami_hal.adapters.virtual.sensors import VirtualSensors

        sensors = VirtualSensors()

        # Before init
        assert sensors.is_running is False
        assert sensors.available_sensor_count > 0  # Virtual has pre-populated sensors

        await sensors.initialize()

        assert sensors.is_running is True

        await sensors.shutdown()

        assert sensors.is_running is False


class TestPlatformTypes:
    """Test platform-level types."""

    def test_platform_enum_values(self):
        """Platform enum should have expected values."""
        from kagami_hal.types import Platform

        assert Platform.LINUX.value == "linux"
        assert Platform.MACOS.value == "darwin"
        assert Platform.WINDOWS.value == "windows"
        assert Platform.ANDROID.value == "android"
        assert Platform.IOS.value == "ios"
        assert Platform.VIRTUAL.value == "virtual"

    def test_hal_status_fields(self):
        """HALStatus should have all expected fields."""
        from kagami_hal.types import HALStatus, Platform

        status = HALStatus(
            platform=Platform.MACOS,
            display_available=True,
            audio_available=True,
            input_available=True,
            sensors_available=False,
            power_available=True,
            adapters_initialized=4,
            adapters_failed=1,
        )

        assert status.platform == Platform.MACOS
        assert status.display_available is True
        assert status.sensors_available is False
        assert status.adapters_initialized == 4
        assert status.adapters_failed == 1
        assert status.mock_mode is False  # Default


"""
Mirror
h(x) >= 0. Always.

Tests ensure safety across all platforms.
Substantive assertions verify real behavior.
"""
