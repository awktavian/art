#!/usr/bin/env python3
"""Virtual HAL Platform Demo.

Demonstrates headless operation with recording mode.

Usage:
    # Basic demo
    python examples/virtual_hal_demo.py

    # With recording
    KAGAMI_VIRTUAL_RECORD_MODE=1 python examples/virtual_hal_demo.py

    # Deterministic mode
    KAGAMI_VIRTUAL_DETERMINISTIC=1 KAGAMI_VIRTUAL_SEED=42 python examples/virtual_hal_demo.py

Created: December 15, 2025
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from kagami_hal.manager import HALManager
from kagami_hal.data_types import SensorType
from kagami_hal.adapters.virtual.compute import detect_compute_capabilities


async def main():
    """Run virtual HAL demo."""
    print("=" * 60)
    print("Virtual HAL Platform Demo")
    print("=" * 60)

    # Check configuration
    record_mode = os.getenv("KAGAMI_VIRTUAL_RECORD_MODE", "0") == "1"
    deterministic = os.getenv("KAGAMI_VIRTUAL_DETERMINISTIC", "0") == "1"
    output_dir = os.getenv("KAGAMI_VIRTUAL_OUTPUT_DIR", "./virtual_hal_output")

    print("\nConfiguration:")
    print(f"  Record mode:    {record_mode}")
    print(f"  Deterministic:  {deterministic}")
    print(f"  Output dir:     {output_dir}")

    # Detect compute capabilities
    print("\nCompute Capabilities:")
    caps = detect_compute_capabilities()
    print(f"  Platform:       {caps.platform}")
    print(f"  CPU cores:      {caps.cpu_count}")
    print(f"  GPU:            {caps.has_gpu} ({caps.gpu_vendor if caps.has_gpu else 'none'})")
    print(f"  GPU memory:     {caps.gpu_memory_mb} MB" if caps.has_gpu else "")
    print(f"  Batch size:     {caps.recommended_batch_size}")
    print(f"  Precision:      {caps.recommended_precision}")

    # Initialize HAL
    print(f"\n{'=' * 60}")
    print("Initializing Virtual HAL...")
    print("=" * 60)

    hal = HALManager(force_mock=True)
    success = await hal.initialize()

    if not success:
        print("❌ HAL initialization failed")
        return 1

    print("✅ HAL initialized successfully")

    # Display info
    print("\nDisplay:")
    display_info = await hal.display.get_info()  # type: ignore[union-attr]
    print(f"  Resolution:     {display_info.width}x{display_info.height}")
    print(f"  Refresh rate:   {display_info.refresh_rate} Hz")
    print(f"  Color depth:    {display_info.bpp} bpp")

    # Write test frame
    print("\nWriting test frame...")
    test_frame = b"\xff\x00\x00\xff" * (display_info.width * display_info.height)
    await hal.display.write_frame(test_frame)  # type: ignore[union-attr]
    print(f"  ✅ Frame written ({len(test_frame)} bytes)")

    # Audio test
    print("\nAudio:")
    pattern = os.getenv("KAGAMI_VIRTUAL_MIC_PATTERN", "silence")
    print(f"  Microphone pattern: {pattern}")
    print("  Recording 500ms of audio...")
    audio_bytes = await hal.audio.record(500)  # type: ignore[union-attr]
    print(f"  ✅ Recorded {len(audio_bytes)} bytes")

    print("\n  Playing audio...")
    await hal.audio.play(audio_bytes)  # type: ignore[union-attr]
    print("  ✅ Audio played")

    # Sensor readings
    print("\nSensor Readings:")
    sensors = [
        SensorType.TEMPERATURE,
        SensorType.ACCELEROMETER,
        SensorType.GYROSCOPE,
        SensorType.LIGHT,
    ]

    for sensor in sensors:
        reading = await hal.sensors.read(sensor)  # type: ignore[union-attr]
        print(f"  {sensor.value:15s}: {reading.value}")

    # Power status
    print("\nPower Status:")
    battery = await hal.power.get_battery_status()  # type: ignore[union-attr]
    print(f"  Battery level:  {battery.level:.1f}%")
    print(f"  Voltage:        {battery.voltage:.2f}V")
    print(f"  Charging:       {battery.charging}")

    stats = await hal.power.get_power_stats()  # type: ignore[union-attr]
    print(f"  Current power:  {stats.current_watts:.2f}W")
    print(f"  Average power:  {stats.avg_watts:.2f}W")

    # Check recordings
    if record_mode:
        print("\nRecordings:")
        output_path = Path(output_dir)

        frames = list((output_path / "frames").glob("*.raw"))
        audio_files = list((output_path / "audio").glob("*.raw"))
        sensors_files = list((output_path / "sensors").glob("*.jsonl"))

        print(f"  Frames:         {len(frames)} files")
        print(f"  Audio:          {len(audio_files)} files")
        print(f"  Sensors:        {len(sensors_files)} files")
        print(f"  Location:       {output_path.absolute()}")

    # Shutdown
    print(f"\n{'=' * 60}")
    print("Shutting down HAL...")
    await hal.shutdown()
    print("✅ Shutdown complete")

    print(f"\n{'=' * 60}")
    print("Demo completed successfully!")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
