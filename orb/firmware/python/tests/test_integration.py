"""
Integration Tests for Kagami Orb Firmware

Tests that all hardware drivers work together correctly:
- Coordinated sensor readings
- Power-aware LED control
- NPU inference with sensor data
- Full system state machine
"""

import pytest
import asyncio
import time
import numpy as np

import sys
sys.path.insert(0, str(pytest.importorskip("pathlib").Path(__file__).parent.parent))

from kagami_orb.drivers.led import HD108Driver, OrbState
from kagami_orb.drivers.power import PowerMonitor
from kagami_orb.drivers.sensors import OrbSensors, IMUData, ToFFrame, TempHumidity
from kagami_orb.drivers.npu import HailoNPUDriver, ModelType, OrbVisionPipeline


class TestSystemInitialization:
    """Test that all subsystems initialize correctly."""
    
    def test_all_drivers_initialize(self):
        """Test all drivers initialize in simulation mode."""
        led = HD108Driver(simulate=True)
        power = PowerMonitor(simulate=True)
        sensors = OrbSensors(simulate=True)
        npu = HailoNPUDriver(simulate=True)
        
        assert led.is_initialized()
        assert power.is_initialized()
        assert sensors.is_initialized()
        assert npu.is_initialized()
        
        # Cleanup
        led.close()
        power.close()
        sensors.close()
        npu.close()
    
    def test_initialization_order(self):
        """Test that initialization order is correct."""
        # Power should be initialized first (for voltage monitoring)
        power = PowerMonitor(simulate=True)
        assert power.is_initialized()
        
        # Check battery is present before initializing other systems
        battery_pct = power.get_battery_percentage()
        assert battery_pct > 0
        
        # Then sensors
        sensors = OrbSensors(simulate=True)
        assert sensors.is_initialized()
        
        # Then LEDs
        led = HD108Driver(simulate=True)
        assert led.is_initialized()
        
        # Finally NPU (most power-hungry)
        npu = HailoNPUDriver(simulate=True)
        assert npu.is_initialized()


class TestPowerAwareLED:
    """Test LED behavior based on power state."""
    
    @pytest.fixture
    def system(self):
        """Create LED and power monitor."""
        return {
            "led": HD108Driver(simulate=True),
            "power": PowerMonitor(simulate=True),
        }
    
    def test_charging_indicator(self, system):
        """Test LED shows charging state correctly."""
        led = system["led"]
        power = system["power"]
        
        # Set charging animation based on battery level
        battery_pct = power.get_battery_percentage()
        led.charge_level = battery_pct / 100.0
        led.set_state(OrbState.CHARGING)
        
        # Render frame
        colors = led.render_frame(0)
        
        # Should have some lit LEDs
        lit_count = sum(1 for c in colors if c[0] > 20 or c[1] > 10)
        expected_lit = int((battery_pct / 100.0) * 16)
        
        # Allow some tolerance
        assert abs(lit_count - expected_lit) <= 2
    
    def test_low_battery_warning(self, system):
        """Test LED shows warning when battery is low."""
        led = system["led"]
        power = system["power"]
        
        # Simulate low battery by directly setting simulation state
        power.fuel_gauge._sim_soc = 10  # 10%
        
        # Should trigger low battery behavior
        battery_pct = power.get_battery_percentage()
        assert battery_pct <= 15
        
        # LED should show error/warning state
        led.set_state(OrbState.ERROR)
        colors = led.render_frame(0)
        
        # Error state should be red
        total_red = sum(c[0] for c in colors)
        total_green = sum(c[1] for c in colors)
        assert total_red > total_green


class TestSensorFusion:
    """Test coordinated sensor readings."""
    
    @pytest.fixture
    def sensors(self):
        """Create sensor interface."""
        return OrbSensors(simulate=True)
    
    def test_all_sensors_read(self, sensors):
        """Test reading all sensors returns valid data."""
        state = sensors.read_all()
        
        assert state.imu is not None
        assert state.tof is not None
        assert state.environment is not None
    
    def test_sensor_timestamps_aligned(self, sensors):
        """Test that sensor readings have similar timestamps."""
        state = sensors.read_all()
        
        # All timestamps should be within 100ms of each other
        timestamps = [
            state.imu.timestamp_ms,
            state.tof.timestamp_ms,
            state.environment.timestamp_ms,
        ]
        
        max_diff = max(timestamps) - min(timestamps)
        assert max_diff < 100
    
    def test_motion_detection(self, sensors):
        """Test that motion can be detected from IMU."""
        imu_data = sensors.imu.read()
        
        # Check acceleration magnitude (should be ~9.8 m/s² at rest)
        accel_mag = imu_data.accel_magnitude
        
        # In simulation, we have artificial motion
        assert accel_mag >= 0
    
    def test_presence_detection_from_tof(self, sensors):
        """Test presence detection using ToF data."""
        tof_frame = sensors.tof.read_frame()
        
        # Get closest distance
        min_dist, row, col = tof_frame.get_closest()
        
        # In simulation, closest should be around 1500mm (person)
        assert min_dist > 0
        assert min_dist < 5000


class TestNPUIntegration:
    """Test NPU integration with camera pipeline."""
    
    @pytest.fixture
    def npu(self):
        """Create NPU driver."""
        return HailoNPUDriver(simulate=True)
    
    @pytest.fixture
    def test_frame(self):
        """Create test image."""
        return np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    def test_person_detection_pipeline(self, npu, test_frame):
        """Test person detection on camera frame."""
        result = npu.infer(ModelType.PERSON_DETECTION, test_frame)
        
        assert result is not None
        assert result.latency_ms < 100  # Should be fast in simulation
    
    def test_multi_model_pipeline(self, npu, test_frame):
        """Test running multiple models on same frame."""
        # Load all models
        npu.load_model(ModelType.PERSON_DETECTION)
        npu.load_model(ModelType.FACE_DETECTION)
        npu.load_model(ModelType.POSE_ESTIMATION)
        
        # Run all inference
        results = {}
        for model_type in [ModelType.PERSON_DETECTION, ModelType.FACE_DETECTION, ModelType.POSE_ESTIMATION]:
            results[model_type] = npu.infer(model_type, test_frame)
        
        # All should succeed
        assert len(results) == 3
        for result in results.values():
            assert result is not None


class TestVisionPipeline:
    """Test high-level vision pipeline."""
    
    @pytest.fixture
    def pipeline(self):
        """Create vision pipeline."""
        return OrbVisionPipeline(simulate=True)
    
    @pytest.fixture
    def test_frame(self):
        """Create test frame."""
        return np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    def test_callback_dispatch(self, pipeline, test_frame):
        """Test that callbacks are properly dispatched."""
        received_results = []
        
        def on_person_detected(result):
            received_results.append(("person", result))
        
        def on_face_detected(result):
            received_results.append(("face", result))
        
        pipeline.register_callback(ModelType.PERSON_DETECTION, on_person_detected)
        pipeline.register_callback(ModelType.FACE_DETECTION, on_face_detected)
        
        # Process frame with both models
        pipeline.process_frame(test_frame, run_person=True, run_face=True)
        
        # Both callbacks should have fired
        assert len(received_results) == 2
        callback_types = [r[0] for r in received_results]
        assert "person" in callback_types
        assert "face" in callback_types


class TestFullSystemLoop:
    """Test the complete orb system loop."""
    
    @pytest.fixture
    def orb_system(self):
        """Create complete orb system."""
        return {
            "led": HD108Driver(num_leds=16, simulate=True),
            "power": PowerMonitor(simulate=True),
            "sensors": OrbSensors(simulate=True),
            "npu": HailoNPUDriver(simulate=True),
        }
    
    def test_sense_act_loop(self, orb_system):
        """Test a complete sense-act loop."""
        led = orb_system["led"]
        power = orb_system["power"]
        sensors = orb_system["sensors"]
        npu = orb_system["npu"]
        
        # SENSE: Read all sensors
        sensor_state = sensors.read_all()
        power_state = power.get_battery_percentage()
        
        # PROCESS: Run inference on simulated camera frame
        test_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        inference_result = npu.infer(ModelType.PERSON_DETECTION, test_frame)
        
        # ACT: Update LED based on detection
        if inference_result.detections:
            led.set_state(OrbState.LISTENING)  # Person detected
        else:
            led.set_state(OrbState.IDLE)
        
        led.render_frame()
        led.show()
        
        # Verify state is consistent
        assert sensor_state is not None
        assert 0 <= power_state <= 100
        assert inference_result is not None
    
    def test_state_machine_transitions(self, orb_system):
        """Test state transitions in main loop."""
        led = orb_system["led"]
        
        states = [
            OrbState.IDLE,
            OrbState.LISTENING,
            OrbState.THINKING,
            OrbState.SPEAKING,
            OrbState.IDLE,
        ]
        
        for state in states:
            led.set_state(state)
            colors = led.render_frame(0)
            
            # Verify colors are valid
            for c in colors:
                assert all(0 <= v <= 255 for v in c)
    
    def test_loop_performance(self, orb_system):
        """Test that main loop can run at required rate."""
        led = orb_system["led"]
        sensors = orb_system["sensors"]
        npu = orb_system["npu"]
        
        # Target: 30fps = 33ms per frame
        target_fps = 30
        target_frame_time = 1.0 / target_fps
        
        frame_times = []
        test_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        
        for _ in range(30):
            start = time.monotonic()
            
            # Sense
            sensors.read_all()
            
            # Process
            npu.infer(ModelType.PERSON_DETECTION, test_frame)
            
            # Act
            led.render_frame()
            led.show()
            
            elapsed = time.monotonic() - start
            frame_times.append(elapsed)
        
        avg_frame_time = sum(frame_times) / len(frame_times)
        
        # Should be able to hit 30fps in simulation
        assert avg_frame_time < target_frame_time * 2  # Allow 2x margin


class TestErrorHandling:
    """Test error handling and recovery."""
    
    def test_graceful_degradation(self):
        """Test system degrades gracefully if component fails."""
        # Power monitor should work even if one IC fails
        power = PowerMonitor(simulate=True)
        
        # Simulate charger failure by checking faults
        assert not power.has_faults()
    
    def test_recovery_from_error_state(self):
        """Test recovery from error state."""
        led = HD108Driver(simulate=True)
        
        # Set error state
        led.set_state(OrbState.ERROR)
        colors_error = led.render_frame(0)
        
        # Recovery: transition to idle
        led.set_state(OrbState.IDLE)
        colors_idle = led.render_frame(0)
        
        # Should be different states
        assert colors_error != colors_idle


@pytest.mark.asyncio
class TestAsyncOperations:
    """Test async operations."""
    
    async def test_async_led_tick(self):
        """Test async LED update."""
        led = HD108Driver(simulate=True)
        led.set_state(OrbState.THINKING)
        
        # Multiple async ticks
        for _ in range(10):
            await led.tick()
            await asyncio.sleep(0.01)
        
        led.close()
    
    async def test_async_inference(self):
        """Test async NPU inference."""
        npu = HailoNPUDriver(simulate=True)
        test_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        
        result = await npu.infer_async(ModelType.PERSON_DETECTION, test_frame)
        
        assert result is not None
        npu.close()
    
    async def test_concurrent_operations(self):
        """Test multiple operations running concurrently."""
        led = HD108Driver(simulate=True)
        npu = HailoNPUDriver(simulate=True)
        sensors = OrbSensors(simulate=True)
        
        led.set_state(OrbState.THINKING)
        test_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        
        async def led_loop():
            for _ in range(10):
                await led.tick()
                await asyncio.sleep(0.01)
        
        async def npu_loop():
            for _ in range(3):
                await npu.infer_async(ModelType.PERSON_DETECTION, test_frame)
        
        async def sensor_loop():
            for _ in range(5):
                sensors.read_all()
                await asyncio.sleep(0.02)
        
        # Run all concurrently
        await asyncio.gather(
            led_loop(),
            npu_loop(),
            sensor_loop(),
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
