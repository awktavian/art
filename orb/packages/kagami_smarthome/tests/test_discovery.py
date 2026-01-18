#!/usr/bin/env python3
"""Test dynamic device discovery via UniFi.

This script tests the new auto-discovery system that resolves
all device IPs via UniFi Network API.

Credentials are loaded automatically from macOS Keychain.

Usage:
    # First time setup (stores credentials in Keychain):
    python -m kagami_smarthome.secrets setup

    # Then just run:
    python test_discovery.py
"""

import asyncio
import logging
import os
import sys

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kagami_smarthome import (
    DeviceDiscovery,
    DeviceType,
    SmartHomeConfig,
    SmartHomeController,
    create_adaptive_config,
)

# Enable logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


async def test_discovery_standalone():
    """Test DeviceDiscovery independently."""
    print("\n" + "=" * 60)
    print("TESTING: DeviceDiscovery (standalone)")
    print("=" * 60)

    # Load credentials from Keychain
    from kagami.core.security import get_secret

    username = get_secret("unifi_username")
    password = get_secret("unifi_password")
    host = os.environ.get("UNIFI_HOST", "192.168.1.1")

    if not username or not password:
        print("❌ Run 'python -m kagami_smarthome.secrets setup' first")
        return

    discovery = DeviceDiscovery(
        unifi_host=host,
        unifi_username=username,
        unifi_password=password,
        cache_ttl=300,
    )

    print(f"\n📡 Connecting to UniFi at {host}...")

    if await discovery.start():
        print("✅ Discovery started\n")

        # Show all discovered smart devices
        devices = discovery.get_all_smart_devices()
        print("Discovered Smart Devices:")
        print("-" * 40)
        for device_type, ip in devices.items():
            status = ip if ip else "Not found"
            print(f"  {device_type:20} {status}")

        # Show detailed registry
        print("\nAll Devices in Registry:")
        print("-" * 60)
        for mac, device in discovery.registry.devices.items():
            if device.device_type != DeviceType.UNKNOWN:
                print(
                    f"  {device.device_type.value:20} "
                    f"MAC: {mac} "
                    f"IP: {device.ip or 'N/A':15} "
                    f"Name: {device.name or device.hostname or 'Unknown'}"
                )

        # Show user devices
        print("\nUser Devices (for presence):")
        print("-" * 40)
        user_macs = discovery.get_user_device_macs()
        for mac in user_macs:
            device = discovery.registry.get_by_mac(mac)
            if device:
                print(
                    f"  {device.name or device.hostname}: {device.ip} ({'online' if device.is_online else 'offline'})"
                )

        print(f"\nIs user home? {discovery.is_user_home()}")

        await discovery.stop()
    else:
        print("❌ Discovery failed to start")


async def test_controller_discovery():
    """Test SmartHomeController with auto-discovery."""
    print("\n" + "=" * 60)
    print("TESTING: SmartHomeController with auto-discovery")
    print("=" * 60)

    # Create config - automatically loads credentials from Keychain
    config = create_adaptive_config(
        unifi_host=os.environ.get("UNIFI_HOST", "192.168.1.1"),
        load_from_keychain=True,  # This is the default
    )

    if not config.unifi_username or not config.unifi_password:
        print("❌ Run 'python -m kagami_smarthome.secrets setup' first")
        return

    print("\n📡 Initializing SmartHomeController...")
    print(f"   Auto-discover: {config.auto_discover}")

    controller = SmartHomeController(config)

    if await controller.initialize():
        print("\n✅ Controller initialized\n")

        # Show resolved IPs
        resolved = controller.get_resolved_ips()
        print("Resolved IPs:")
        print("-" * 40)
        for device_type, ip in resolved.items():
            status = ip if ip else "Not found"
            print(f"  {device_type:20} {status}")

        # Show integration status
        status = controller.get_integration_status()
        print("\nIntegration Status:")
        print("-" * 40)
        for integration, connected in status.items():
            emoji = "✅" if connected else "❌"
            print(f"  {emoji} {integration}")

        # Show stats
        stats = controller.get_stats()
        print("\nController Stats:")
        print("-" * 40)
        for key, value in stats.items():
            print(f"  {key}: {value}")

        await controller.stop()
    else:
        print("❌ Controller failed to initialize")


async def test_fallback_to_static():
    """Test fallback to static IPs when discovery fails."""
    print("\n" + "=" * 60)
    print("TESTING: Fallback to static IPs")
    print("=" * 60)

    # Create config with both auto-discover and static fallbacks
    config = SmartHomeConfig(
        unifi_host="192.168.1.1",
        unifi_username="invalid@example.com",  # Invalid creds
        unifi_password="wrong_password",
        auto_discover=True,
        # Static fallbacks
        denon_host="192.168.1.12",
        lg_tv_host="192.168.1.10",
        oelo_host="192.168.1.254",
    )

    print("\n📡 Initializing with invalid UniFi creds (should fallback)...")

    controller = SmartHomeController(config)

    # Note: This will try to connect to actual devices at static IPs
    # In a real test, we'd mock this
    status = controller.get_integration_status()
    print("\nInitial Status (before initialize):")
    for integration, connected in status.items():
        emoji = "✅" if connected else "⚠️"
        print(f"  {emoji} {integration}: {'configured' if connected else 'pending'}")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("KAGAMI SMART HOME - DEVICE DISCOVERY TEST")
    print("=" * 60)
    print("\nThis tests the new UniFi-based device discovery system.")
    print("No hardcoded IPs - everything resolved dynamically.\n")

    try:
        # Test standalone discovery
        await test_discovery_standalone()

        # Test controller with discovery
        await test_controller_discovery()

        # Test fallback
        await test_fallback_to_static()

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
