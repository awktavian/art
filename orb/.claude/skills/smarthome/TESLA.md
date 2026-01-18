# Tesla Integration — Vehicle Command Protocol

**Status: ✅ FULLY OPERATIONAL**

## Overview

Tesla vehicles require end-to-end authenticated commands via the Vehicle Command Protocol.
This integration uses Tesla's official `vehicle-command` SDK running as a local HTTP proxy.

## Architecture

```
Kagami → Tesla Integration → tesla-http-proxy → Fleet API → Vehicle
                                    ↓
                           Signs commands with
                           private key (P-256)
```

## Components

| Component | Location | Purpose |
|-----------|----------|---------|
| Private Key | `~/.kagami/tesla/fleet-key.pem` | Command signing (EC P-256) |
| TLS Cert | `~/.kagami/tesla/tls-cert.pem` | Proxy HTTPS |
| TLS Key | `~/.kagami/tesla/tls-key.pem` | Proxy HTTPS |
| Proxy Binary | `~/bin/tesla-http-proxy` | Signs commands |
| LaunchAgent | `~/Library/LaunchAgents/com.kagami.tesla-proxy.plist` | Auto-start |
| Proxy Log | `~/.kagami/tesla/proxy.log` | Debugging |

## Keychain Secrets

All stored in macOS Keychain with service `kagami`:

| Key | Description |
|-----|-------------|
| `tesla_client_id` | OAuth client ID |
| `tesla_client_secret` | OAuth client secret |
| `tesla_access_token` | Access token (auto-refreshes) |
| `tesla_refresh_token` | Refresh token |
| `tesla_private_key` | Private key (hex-encoded PEM) |

## Command Flow

1. **Data Queries** → Direct to Fleet API (no signing needed)
2. **Commands** → Routed through `tesla-http-proxy` on `localhost:4443`
   - Proxy signs with private key
   - Handles session state and retries
   - Returns result to Kagami

## Available Commands

### Climate
- `start_climate()` — Turn on HVAC
- `stop_climate()` — Turn off HVAC
- `set_temperature(temp_c)` — Set cabin temperature
- `set_seat_heater(seat, level)` — Seat heater (0-5 seat, 0-3 level)

### Charging
- `start_charging()` — Start charging
- `stop_charging()` — Stop charging
- `set_charge_limit(percent)` — Set limit (50-100%)
- `open_charge_port()` — Open charge port

### Security
- `lock()` — Lock all doors
- `unlock()` — Unlock all doors
- `honk()` — Honk horn
- `flash_lights()` — Flash headlights

### Trunk
- `open_trunk()` — Open rear trunk
- `open_frunk()` — Open front trunk

### Other
- `wake_up()` — Wake vehicle from sleep

## Usage

```python
from kagami_smarthome import get_smart_home

controller = await get_smart_home()

# Commands through controller (recommended)
await controller.honk_car()
await controller.flash_car_lights()
await controller.lock_car()

# Or use TeslaIntegration directly
tesla = controller._tesla
await tesla.honk()
await tesla.flash_lights()
await tesla.lock()
```

## Proxy Management

```bash
# Check proxy status
pgrep -f tesla-http-proxy

# View logs
tail -f ~/.kagami/tesla/proxy.log

# Restart proxy
launchctl unload ~/Library/LaunchAgents/com.kagami.tesla-proxy.plist
launchctl load ~/Library/LaunchAgents/com.kagami.tesla-proxy.plist

# Manual start (for debugging)
~/bin/tesla-http-proxy \
  -cert ~/.kagami/tesla/tls-cert.pem \
  -tls-key ~/.kagami/tesla/tls-key.pem \
  -key-file ~/.kagami/tesla/fleet-key.pem \
  -host localhost -port 4443
```

## Troubleshooting

### "Tesla proxy not running"
```bash
# Check if proxy is running
pgrep -f tesla-http-proxy

# Check logs
tail ~/.kagami/tesla/proxy.err

# Restart
launchctl kickstart -k gui/$(id -u)/com.kagami.tesla-proxy
```

### "Vehicle offline"
```bash
# Wake vehicle first
curl -s --cacert ~/.kagami/tesla/tls-cert.pem \
  -H "Authorization: Bearer $TOKEN" \
  -X POST "https://localhost:4443/api/1/vehicles/$VIN/wake_up"
```

### "Token expired"
Tokens auto-refresh. If issues persist:
```python
# Force refresh
await tesla._refresh_access_token()
```

## Reference

- [Tesla Vehicle Command SDK](https://github.com/teslamotors/vehicle-command)
- [Fleet API Vehicle Commands](https://developer.tesla.com/docs/fleet-api/endpoints/vehicle-commands)
- [Virtual Key Setup](https://developer.tesla.com/docs/fleet-api/virtual-keys/developer-guide)
