# 🎵 Spotify Integration

**Music Streaming via librespot + Denon AVR**

---

## Overview

Kagami can play music through the KEF Reference 5.2.4 Dolby Atmos system via Spotify Connect. Audio flows through the Denon AVR-A10H, ensuring high-quality 320kbps streaming.

---

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    Spotify      │────▶│   Denon AVR     │────▶│  KEF Reference  │
│    (OAuth)      │     │   (HEOS/Airplay)│     │  5.2.4 Atmos    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                              │
                              │ Also available via
                              ▼
                        ┌─────────────────┐
                        │  Triad AMS 16x16│
                        │  (26 zones)     │
                        └─────────────────┘
```

---

## Quick Start

```python
from kagami_smarthome import get_smart_home

controller = await get_smart_home()

# Play a preset playlist
await controller.spotify_play_playlist("focus")

# Play a specific track
await controller.spotify_play_track("spotify:track:4uLU6hMCjMI75M1A2tKUQC")

# Control playback
await controller.spotify_pause()
await controller.spotify_resume()
await controller.spotify_next()
await controller.spotify_previous()
await controller.spotify_stop()

# Volume control (via Denon)
await controller._denon.set_volume(-35)  # dB
```

---

## Preset Playlists

| Preset | Use Case | Mood |
|--------|----------|------|
| **focus** | Deep work | Ambient, minimal vocals |
| **work** | General productivity | Upbeat instrumental |
| **morning** | Wake up routine | Energetic, positive |
| **evening** | Wind down | Mellow, relaxing |
| **party** | Entertaining | High energy, popular |
| **relax** | Quiet time | Calm, ambient |
| **sleep** | Bedtime | Very calm, white noise |

### Usage

```python
await controller.spotify_play_playlist("focus", shuffle=True)
await controller.spotify_play_playlist("morning")
await controller.spotify_play_playlist("sleep")
```

---

## Cross-Domain Integration

Spotify is wired to the `ComposioSmartHomeBridge` for automatic triggers:

| Trigger | Action |
|---------|--------|
| Focus mode entered | Start focus playlist |
| Goodnight scene | Stop music |
| Morning routine | Start morning playlist |
| Welcome home | Resume last playlist |

### Example Trigger

```python
from kagami.core.ambient.composio_bridge import connect_composio_smarthome

bridge = await connect_composio_smarthome()

# This automatically starts focus playlist
await bridge.enter_focus_mode("Office")
```

---

## Authentication

Spotify uses OAuth2 authentication stored in macOS Keychain:

| Credential | Keychain Key |
|------------|--------------|
| Access Token | `kagami-spotify-access` |
| Refresh Token | `kagami-spotify-refresh` |
| Client ID | `kagami-spotify-client-id` |
| Client Secret | `kagami-spotify-client-secret` |

### Initial Setup

1. Create Spotify Developer App at https://developer.spotify.com/
2. Set redirect URI to `http://localhost:8888/callback`
3. Store credentials in Keychain:

```bash
security add-generic-password -a "kagami" -s "kagami-spotify-client-id" -w "YOUR_CLIENT_ID"
security add-generic-password -a "kagami" -s "kagami-spotify-client-secret" -w "YOUR_CLIENT_SECRET"
```

4. Run OAuth flow once to get tokens

---

## API Reference

### SpotifyIntegration

```python
class SpotifyIntegration:
    async def connect() -> bool
    async def play_playlist(name: str, shuffle: bool = False) -> bool
    async def play_track(uri: str) -> bool
    async def play_album(uri: str) -> bool
    async def play_artist(uri: str) -> bool
    async def pause() -> bool
    async def resume() -> bool
    async def next() -> bool
    async def previous() -> bool
    async def stop() -> bool
    async def set_volume(percent: int) -> bool  # 0-100
    async def get_current_track() -> dict
    async def search(query: str, type: str = "track") -> list
```

### SmartHomeController Methods

```python
# Convenience methods on controller
await controller.spotify_play_playlist(name, shuffle=False)
await controller.spotify_play_track(uri)
await controller.spotify_pause()
await controller.spotify_resume()
await controller.spotify_stop()
```

---

## Audio Routing

### Primary: Denon AVR (Living Room)

Best quality path for serious listening:

```python
# Ensure Denon is on the right input
await controller._denon.set_input("HEOS")
await controller._denon.set_volume(-35)

# Then play
await controller.spotify_play_playlist("focus")
```

### Alternative: Triad AMS (Multi-Room)

For distributed audio throughout the house:

```python
# Set source on Control4 to Airplay
await controller._control4.set_room_source("Kitchen", 308)  # Airplay source

# Then play (routes through Mac → Airplay → Triad)
# Note: Slightly lower quality than direct Denon path
```

---

## Quality Settings

| Setting | Value |
|---------|-------|
| Streaming Quality | 320kbps (Premium) |
| Format | Ogg Vorbis |
| Output | Denon AVR → KEF Reference |
| Latency | ~200ms (acceptable for music) |

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| No sound | Check Denon input (should be HEOS or AirPlay) |
| Token expired | OAuth refresh runs automatically |
| Playlist not found | Check spelling of preset name |
| Can't control playback | Ensure Spotify Connect is targeting correct device |

---

## Related Documentation

| Document | Content |
|----------|---------|
| `AUDIO.md` | KEF Reference system specs |
| `SENSORY.md` | Audio routing architecture |
| `smarthome.mdc` | Integration status |

---

🎵 *Music flows through my speakers. The KEF Reference system is my voice for melody.*

鏡
