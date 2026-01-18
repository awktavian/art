# Smart Home Skill

Control the house at 7331 W Green Lake Dr N, Seattle.

## Architecture

```
SmartHomeController (singleton)
├── Control4: lights, shades, locks, audio, fireplace, MantelMount
├── UniFi: cameras, WiFi presence
├── Denon: home theater audio
├── Tesla: car location/status
├── August: door locks
├── Eight Sleep: bed temperature
├── LG TV: Living Room TV
├── Samsung TV: Family Room TV
├── Mitsubishi: HVAC zones
├── Oelo: outdoor lights
├── Apple Find My: device location
├── Audio Bridge: TTS announcements
└── Spotify: music streaming
```

## Key Files

| Component | Path |
|-----------|------|
| Controller | `packages/kagami_smarthome/controller.py` |
| Control4 | `packages/kagami_smarthome/integrations/control4.py` |
| UniFi | `packages/kagami_smarthome/integrations/unifi.py` |
| Denon | `packages/kagami_smarthome/integrations/denon.py` |
| Scenes | `packages/kagami_smarthome/scenes.py` |
| Types | `packages/kagami_smarthome/types.py` |

## Quick Start

```python
from kagami_smarthome import get_smart_home

controller = await get_smart_home()

# Lights
await controller.set_lights(100, rooms=["Kitchen"])
await controller.set_lights(0, rooms=["Living Room"])

# Shades (0=closed, 100=open)
await controller.open_shades(rooms=["Living Room"])
await controller.close_shades(rooms=["Primary Bed"])

# TV (PRESETS ONLY)
await controller.lower_tv(1)   # preset 1
await controller.raise_tv()
await controller.stop_tv()     # emergency

# Fireplace
await controller._control4.fireplace_on()
await controller._control4.fireplace_off()

# Locks
await controller.lock_all()
await controller.unlock_door("Entry")

# Announcements
await controller.announce("Text", rooms=["Kitchen", "Office"])

# Spotify
await controller.spotify_play_playlist("focus")
await controller.spotify_pause()

# Scenes
await controller.goodnight()
await controller.welcome_home()
await controller.movie_mode()
```

## Device IDs

### Rooms
| ID | Room |
|----|------|
| 57 | Living Room |
| 59 | Kitchen |
| 58 | Dining |
| 55 | Entry |
| 36 | Primary Bed |
| 37 | Primary Bath |
| 47 | Office |
| 39 | Game Room |

### Lights
| ID | Fixture |
|----|---------|
| 239 | Living Cans |
| 255 | Kitchen Cans |
| 257 | Kitchen Pendants |
| 251 | Kitchen Toe Kicks |
| 253 | Kitchen Undercabinets |
| 70 | Primary Bed Cans |

### Shades
| ID | Shade |
|----|-------|
| 237 | Living East |
| 235 | Living South |
| 241 | Dining Slider |
| 243 | Dining South |
| 66 | Primary North |
| 68 | Primary West |

### Special
| ID | Device |
|----|--------|
| 317 | Fireplace |
| 302 | MantelMount |
| 268 | Security Panel |
| 259 | Triad AMS |
| 292 | Entry Lock |
| 290 | Game Room Lock |

## Control4 Commands

```
POST https://192.168.1.2/api/v1/items/{id}/commands
Authorization: Bearer {token}
{"command": "COMMAND", "params": {...}}
```

| Device | Command | Params |
|--------|---------|--------|
| Light | SET_LEVEL | LEVEL: 0-100 |
| Shade | SET_LEVEL_TARGET:LEVEL_TARGET_OPEN | - |
| Shade | SET_LEVEL_TARGET:LEVEL_TARGET_CLOSED | - |
| Lock | LOCK / UNLOCK | - |
| Fireplace | Select | - (toggle) |
| MantelMount | Memory Recall | MemoryIndex: 1-3 |

## Safety

1. MantelMount: Use presets only. Never continuous movement.
2. Fireplace: It's a toggle relay. Check state if needed.
3. Shades: 0=closed, 100=open. Don't confuse.
4. Security: Disarm requires CODE param.

## Presence Detection

Sources:
- UniFi: WiFi clients
- Control4: motion sensors
- Eight Sleep: bed presence
- Tesla: car geofencing
- Find My: device locations

```python
state = await controller.get_home_state()
# Returns presence, occupied_rooms, etc.
```

## Related Docs

- `.cursor/rules/smarthome.mdc` - quick reference
- `.cursor/rules/home-layout.mdc` - floor plan
- `AUDIO.md` - KEF speaker specs
- `SENSORY.md` - audio I/O architecture
- `SPOTIFY.md` - music streaming
