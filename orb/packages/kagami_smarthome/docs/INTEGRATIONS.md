# SmartHome Integrations

## Overview

The SmartHome package integrates with 35+ devices across multiple ecosystems. Each integration handles authentication, connection management, and device-specific protocols.

## Integration Status

| Integration | Status | Protocol | Auth |
|-------------|--------|----------|------|
| Control4 | ✅ Production | REST API | Bearer Token |
| UniFi Protect | ✅ Production | REST + WebSocket | Local Admin |
| UniFi Network | ✅ Production | REST | Local Admin |
| Denon AVR | ✅ Production | Telnet | None |
| Tesla | ✅ Production | Fleet API + VCP | OAuth2 |
| Eight Sleep | ✅ Production | REST API | OAuth2 |
| August Locks | ✅ Production | REST API | OAuth |
| LG TV | ✅ Production | WebSocket | Pairing |
| Samsung TV | ✅ Production | REST + WebSocket | Pairing |
| Mitsubishi HVAC | ✅ Production | Kumo Cloud | Basic Auth |
| Envisalink (DSC) | ✅ Production | TPI Protocol | Code |
| Spotify | ✅ Production | librespot | OAuth |
| Apple Find My | ✅ Production | pyicloud | iCloud |
| Apple Health | ⚠️ Beta | HealthKit | N/A |
| Formlabs | ⚠️ Beta | Local API | N/A |
| Glowforge | ⚠️ Beta | Cloud API | OAuth |

## Control4

Primary home automation controller for:
- Lights (Lutron Radio RA3)
- Shades (Lutron)
- Audio zones (Triad AMS)
- Fireplace
- MantelMount TV

### Configuration

Credentials stored in macOS Keychain:
```bash
security add-generic-password -s kagami -a control4_host -w "192.168.1.100"
security add-generic-password -s kagami -a control4_username -w "admin"
security add-generic-password -s kagami -a control4_password -w "password"
```

### Usage

```python
from kagami_smarthome.integrations.control4 import Control4Integration

c4 = Control4Integration()
await c4.connect()

# Get all lights
lights = await c4.get_lights()

# Set light level
await c4.set_light_level(239, 50)  # 50%

# Get all rooms
rooms = await c4.get_rooms()
```

## UniFi

UniFi Protect for cameras and Network for WiFi presence.

### Configuration

```bash
security add-generic-password -s kagami -a unifi_host -w "192.168.1.1"
security add-generic-password -s kagami -a unifi_local_username -w "admin"
security add-generic-password -s kagami -a unifi_local_password -w "password"
```

### Usage

```python
from kagami_smarthome.integrations.unifi import UniFiIntegration

unifi = UniFiIntegration()
await unifi.connect()

# Get WiFi clients (presence)
clients = await unifi.get_clients()

# Get cameras
cameras = await unifi.get_cameras()

# Subscribe to events (motion, doorbell)
await unifi.subscribe_events(callback=on_event)
```

## Tesla

Vehicle integration via Fleet API and local command signing proxy.

### Setup

1. Register at developer.tesla.com
2. Generate keypair and virtual key
3. Pair key to vehicle via NFC
4. Configure local proxy for command signing

### Configuration

```bash
security add-generic-password -s kagami -a tesla_client_id -w "..."
security add-generic-password -s kagami -a tesla_client_secret -w "..."
security add-generic-password -s kagami -a tesla_refresh_token -w "..."
```

### Usage

```python
from kagami_smarthome.integrations.tesla import TeslaIntegration

tesla = TeslaIntegration()
await tesla.connect()

# Get vehicle state
state = await tesla.get_state()
print(f"Location: {state.latitude}, {state.longitude}")
print(f"Battery: {state.battery_level}%")

# Control (requires signed commands via proxy)
await tesla.climate_on()
await tesla.lock()
```

## Denon AVR

Home theater receiver via telnet protocol.

### Configuration

```bash
security add-generic-password -s kagami -a denon_host -w "192.168.1.50"
```

### Usage

```python
from kagami_smarthome.integrations.denon import DenonIntegration

denon = DenonIntegration()
await denon.connect()

# Power
await denon.power_on()

# Volume
await denon.set_volume(40)

# Input
await denon.set_input_source("HDMI1")

# Sound mode
await denon.set_sound_mode("DOLBY_ATMOS")
```

## Eight Sleep

Smart mattress for sleep tracking and temperature control.

### Configuration

```bash
security add-generic-password -s kagami -a eight_sleep_email -w "..."
security add-generic-password -s kagami -a eight_sleep_password -w "..."
```

### Usage

```python
from kagami_smarthome.integrations.eight_sleep import EightSleepIntegration

eight = EightSleepIntegration()
await eight.connect()

# Get sleep state
state = await eight.get_sleep_state()
print(f"In bed: {state.in_bed}")
print(f"Sleep stage: {state.stage}")

# Set temperature
await eight.set_bed_temperature("left", 0)  # Neutral
await eight.set_bed_temperature("right", -2)  # Cooler
```

## August Locks

Smart lock control via yalexs library.

### Configuration

```bash
security add-generic-password -s kagami -a august_email -w "..."
security add-generic-password -s kagami -a august_password -w "..."
```

### Usage

```python
from kagami_smarthome.integrations.august import AugustIntegration

august = AugustIntegration()
await august.connect()

# Get locks
locks = await august.get_locks()

# Lock/unlock
await august.lock("Front Door")
await august.unlock("Garage Entry")

# Get state
state = await august.get_lock_state("Front Door")
print(f"Locked: {state.locked}")
print(f"Door: {state.door_state}")
```

## Envisalink (DSC Security)

Security panel integration via TPI protocol.

### Configuration

```bash
security add-generic-password -s kagami -a dsc_host -w "192.168.1.200"
security add-generic-password -s kagami -a dsc_code -w "1234"
security add-generic-password -s kagami -a dsc_password -w "user"
```

### Usage

```python
from kagami_smarthome.integrations.envisalink import EnvisalinkIntegration

dsc = EnvisalinkIntegration()
await dsc.connect()

# Get zone status
zones = await dsc.get_zones()
for zone in zones:
    print(f"Zone {zone.num}: {zone.name} - {zone.state}")

# Arm/disarm
await dsc.arm_away()
await dsc.disarm("1234")
```

## Spotify

Music streaming via librespot-python.

### Configuration

First-time setup opens browser for OAuth:
```bash
security add-generic-password -s kagami -a spotify_credentials -w '{"username":"...","token":"..."}'
```

### Usage

```python
from kagami_smarthome.integrations.spotify import SpotifyIntegration

spotify = SpotifyIntegration()
await spotify.initialize()

# Play
await spotify.play_playlist("Focus")
await spotify.play_track("spotify:track:...")

# Control
await spotify.pause()
await spotify.next()
await spotify.set_volume(50)
```

## Creating New Integrations

### Standard Interface

```python
class MyIntegration:
    def __init__(self):
        self._connected = False
        self._client = None

    async def connect(self) -> bool:
        """Establish connection. Return True on success."""
        try:
            # Connect logic
            self._connected = True
            return True
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

    async def disconnect(self) -> None:
        """Clean disconnect."""
        if self._client:
            await self._client.close()
        self._connected = False

    def is_connected(self) -> bool:
        """Check connection status."""
        return self._connected

    async def health_check(self) -> HealthStatus:
        """Return health status for monitoring."""
        if not self._connected:
            return HealthStatus.DISCONNECTED
        try:
            await self._ping()
            return HealthStatus.HEALTHY
        except:
            return HealthStatus.UNHEALTHY
```

### Best Practices

1. **Credential Storage**: Use macOS Keychain via `kagami_smarthome.secrets`
2. **Error Handling**: Catch and log exceptions, use exponential backoff
3. **Connection Management**: Implement auto-reconnect
4. **Rate Limiting**: Respect API limits, use rate_limiter.py
5. **Logging**: Use structured logging with appropriate levels
6. **Testing**: Create mock for offline testing
