# 🎤 Kagami Sensory I/O — Audio Input/Output Architecture

## Overview

Kagami's sensory system enables two-way audio communication throughout the home:
- **Voice Output (TTS):** Multi-room announcements via ElevenLabs neural voices with colony personalities
- **Voice Input (STT):** Microphone capture via UniFi cameras RTSP streams

---

## Voice Output Architecture

### Audio Routing

```
┌─────────────┐     ┌───────────────┐     ┌──────────────────┐
│ Mac Studio  │────▶│ Denon AVR-A10H│────▶│ Living Room      │
│ (ElevenLabs)│     │ (HDMI Input)  │     │ KEF Reference 5.2.4
└─────────────┘     └───────────────┘     └──────────────────┘
       │
       │ afplay → HDMI
       ▼
┌─────────────────────────────────────────────────────────────┐
│                    Control4 Airplay                          │
│                    (Audio-Jack: analog)                      │
└─────────────────────────────────────────────────────────────┘
       │
       │ Control4 Core 5 AUDIO OUT 1-3
       ▼
┌─────────────────────────────────────────────────────────────┐
│              Triad AMS 16x16 Audio Matrix                    │
│              (Inputs 1-3 from Control4)                      │
└─────────────────────────────────────────────────────────────┘
       │
       │ 16 Output Zones
       ▼
┌─────────────────────────────────────────────────────────────┐
│  Kitchen │ Primary Bed │ Office │ Patio │ Deck │ ...        │
│  Output5 │ Output7     │ Output10│ Output8│ Output9│         │
└─────────────────────────────────────────────────────────────┘
```

### Room → Triad Output Mapping

| Room | Triad Output | Source Input |
|------|--------------|--------------|
| Kitchen | 5 | 3002 (Control4 Core 5 OUT 1) |
| Primary Bath | 3 | 3002 |
| Game Room | 4 | 3002 |
| Primary Bed | 7 | 3002 |
| Patio | 8 | 3002 |
| Deck | 9 | 3002 |
| Office | 10 | 3002 |

### Control4 Device IDs

| Device | ID | Purpose |
|--------|-----|---------|
| Control4 Airplay | 308 | Streaming source for Triad |
| Triad AMS 16x16 | 259 | Audio matrix switch |
| Digital Media | 100002 | Streaming coordinator |
| Control4 Core 5 | 16 | Audio outputs to Triad |

### Multi-Room Playback

```python
from kagami_smarthome import get_smart_home

controller = await get_smart_home()

# Single room
await controller.announce("Dinner is ready!", rooms=["Kitchen"], colony="spark")

# Parallel multi-room
await controller.announce(
    "Attention all rooms.",
    rooms=["living room", "kitchen", "primary bed"],
    colony="beacon",
    volume=60,
)

# Whole-house
await controller.announce_all(
    "Good night everyone!",
    colony="flow",
    exclude_rooms=["garage", "rack room"],
)
```

### Colony Voices

| Colony | Character | Best For |
|--------|-----------|----------|
| kagami | Balanced, warm | General announcements |
| spark | Energetic | Alerts, good news |
| forge | Confident, technical | Status updates |
| flow | Calm, soothing | Bedtime, relaxation |
| nexus | Connected, integrative | System coordination |
| beacon | Clear, commanding | Important announcements |
| grove | Curious, exploratory | Information sharing |
| crystal | Precise, analytical | Verification, reports |

---

## Voice Input Architecture

### UniFi Camera Microphones

| Camera | Location | Microphone | Speaker |
|--------|----------|------------|---------|
| UVC-AI-Pro | Driveway | ✅ Built-in | ✅ Built-in |
| UVC-AI-Pro | Back Deck | ✅ Built-in | ✅ Built-in |
| UVC-AI-Pro | Front Door | ✅ Built-in | ✅ Built-in |
| UVC-AI-Pro | Garage | ✅ Built-in | ✅ Built-in |

### RTSP Audio Streams

```python
from kagami_smarthome import get_smart_home

controller = await get_smart_home()
unifi = controller._unifi

# Get RTSP URL for a camera
rtsp_url = unifi.get_rtsp_url("Driveway", quality="high")
# rtsp://192.168.1.1:7447/<camera_id>?quality=0

# Get audio capabilities
audio_info = unifi.get_camera_audio_info("Driveway")
# {
#     "has_microphone": True,
#     "has_speaker": True,
#     "microphone_enabled": True/False,
#     "mic_volume": 100,
#     "rtsp_url": "rtsp://..."
# }

# Get all cameras with audio
all_audio = unifi.get_all_cameras_audio()
```

### RTSP Stream Processing

```python
import subprocess

# Capture audio from camera RTSP stream
rtsp_url = "rtsp://192.168.1.1:7447/<camera_id>"

# Extract audio with ffmpeg
proc = subprocess.Popen([
    "ffmpeg", "-i", rtsp_url,
    "-vn",  # No video
    "-acodec", "pcm_s16le",
    "-ar", "16000",
    "-ac", "1",
    "-f", "wav",
    "pipe:1"
], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

# Read audio chunks for STT
audio_data = proc.stdout.read(chunk_size)
```

### Two-Way Audio (Future)

UniFi AI Pro cameras support two-way audio. To speak through a camera:
1. Enable speaker in UniFi Protect settings
2. Stream audio to camera via WebRTC or RTSP push

---

## Latency Characteristics

### TTS Pipeline

| Stage | Typical Latency |
|-------|-----------------|
| ElevenLabs Flash TTFA (streaming) | ~75ms |
| ElevenLabs Turbo TTFA | ~150ms |
| Full synthesis | ~500ms-2s (cached after) |
| afplay start | ~50ms |
| Control4 room setup | ~100ms parallel |
| **Total (streaming)** | **~1.2s to first audio** |

### STT Pipeline (Planned)

| Stage | Expected Latency |
|-------|------------------|
| RTSP stream decode | ~200ms |
| VAD (voice activity) | ~100ms |
| Whisper STT | ~500ms-2s |
| **Total** | **~1-2.5s** |

---

## API Reference

### RoomAudioBridge

```python
# NOTE: Voice output uses UnifiedVoiceEffector, not RoomAudioBridge
# from kagami.core.effectors.voice import speak, VoiceTarget
# await speak("Hello", target=VoiceTarget.HOME_ROOM, rooms=["Living Room"])

class RoomAudioBridge:
    """Room routing utilities only - voice playback removed."""

    def get_available_rooms() -> list[str]
    def get_denon_rooms() -> list[str]  # Living Room
    def get_triad_rooms() -> list[str]  # All others

    async def wake_shairbridge(rooms: list[str] | None = None) -> bool
    async def get_shairbridge_status() -> dict[str, Any]
```

---

## Hardware Reference

### Voice Output

- **Mac Studio M2 Ultra** — TTS host, HDMI audio
- **Denon AVR-A10H** — 15.4ch receiver, Living Room
- **KEF Reference 5.2.4** — 5 Meta, 2x THX subs, 4 Atmos
- **Control4 Core 5** — Streaming controller
- **Triad AMS 16x16** — Multi-room matrix
- **Episode amplifiers** — 12ch + 8ch = 20ch driving zones

### Voice Input

- **4x UniFi AI Pro** — 4K cameras with mic/speaker
- **UDM Pro Max** — NVR with 22TB, RTSP server

### Voice Control (Ordered)

- **Josh Core** — Flagship natural language processor
- **7x Josh Nano** — Flush-mount architectural microphones
- See: [JOSH_AI.md](./JOSH_AI.md) for full specification

---

## Josh.ai Integration (Ordered Jan 4, 2026)

Josh.ai will handle natural voice control throughout the home:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Josh Nano  │────▶│  Josh Core  │────▶│  Control4   │
│ (7 rooms)   │     │  (Local NLU)│     │  Driver     │
└─────────────┘     └─────────────┘     └─────────────┘
                                               │
                                               ▼
                    ┌─────────────────────────────────────┐
                    │  Lutron │ Denon │ Triad │ August    │
                    └─────────────────────────────────────┘
```

### Josh Nano Locations

| Room | Coverage | Commands |
|------|----------|----------|
| Living Room (2) | 450 SF open concept | Lights, TV, fireplace, audio |
| Kitchen | Adjacent to living | Lights, audio, timers |
| Primary Bedroom | Vaulted ceiling | Wake/sleep, lights, shades |
| Office | 9' ceiling | Lights, focus mode |
| Game Room | Basement ADU | Lights, audio, gaming |
| Entry | Welcome zone | Arrival/departure scenes |

### Voice vs Text

| Input | Path | Use Case |
|-------|------|----------|
| "OK Josh, movie time" | Josh → Control4 | Natural voice control |
| Text to Kagami | Kagami → Control4 | AI assistant queries |

**Both systems complement each other:**
- Josh.ai for instant voice commands
- Kagami for complex queries, cross-domain orchestration, intelligence

---

鏡
