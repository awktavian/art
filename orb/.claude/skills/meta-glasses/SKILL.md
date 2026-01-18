# Meta Glasses Integration Skill

**First-Person Perspective for Kagami**

## When to Use This Skill

Load this skill when:
- Working with Meta Ray-Ban smart glasses
- Implementing visual context features
- Routing audio to open-ear speakers
- Enhancing presence detection with visual signals
- Integrating with Meta DAT SDK

## Key Concepts

### Visual Context
The glasses camera provides semantic features:
- Scene type (kitchen, office, outdoor)
- Detected objects and text
- Face detection and recognition
- Activity inference
- Lighting conditions

### Private Audio
Open-ear speakers enable:
- Whispered notifications only the wearer hears
- Discreet TTS announcements
- Audio routing based on wearing state

### Sensor Fusion
Visual signals enhance:
- PersonTracker (room hints from scene)
- PresenceEngine (activity inference)
- WakefulnessManager (eyes open/closed)

## Files and Locations

### HAL Adapters
```
packages/kagami_hal/adapters/meta_glasses/
├── __init__.py      # Module exports
├── protocol.py      # WebSocket communication
├── camera.py        # Camera streaming/capture
└── audio.py         # Microphone and speakers
```

### SmartHome Integration
```
packages/kagami_smarthome/integrations/meta_glasses.py
```

### Mobile Services
```
apps/ios/kagami-ios/KagamiIOS/Services/MetaGlassesService.swift
apps/android/kagami-android/.../services/MetaGlassesService.kt
```

### Sensor Fusion
```
packages/kagami_smarthome/sensor_fusion.py
```

## Quick Reference

### Connect and Get Context
```python
from kagami_smarthome.integrations.meta_glasses import get_meta_glasses

glasses = await get_meta_glasses()
await glasses.connect()

# Get visual context
context = await glasses.get_visual_context()
print(f"Scene: {context.scene_type}")
print(f"Activity: {context.activity_hint}")
```

### Private Audio
```python
# Whisper to glasses
await glasses.speak("Your meeting starts in 5 minutes")

# Or via audio bridge
bridge.set_meta_glasses(glasses)
await bridge.whisper_to_glasses("Dinner is ready")
```

### Sensor Fusion
```python
from kagami_smarthome.sensor_fusion import get_sensor_fusion

fusion = get_sensor_fusion()
fusion.register_meta_glasses(glasses)
await fusion.start()

state = await fusion.get_fused_state()
```

### Wakefulness Detection
```python
from kagami.core.integrations.wakefulness import get_wakefulness_manager

wakefulness = get_wakefulness_manager()
wakefulness.connect_meta_glasses(glasses)
await wakefulness.update_from_visual_context()
```

## Visual Context Fields

| Field | Type | Description |
|-------|------|-------------|
| `is_indoor` | bool | Indoor/outdoor |
| `lighting` | str | "bright", "dim", "dark" |
| `scene_type` | str | "kitchen", "office", etc. |
| `detected_objects` | list[str] | Objects in view |
| `detected_text` | list[str] | OCR text |
| `faces_detected` | int | Face count |
| `known_people` | list[str] | Recognized people |
| `activity_hint` | str | Inferred activity |
| `confidence` | float | 0.0 - 1.0 |

## Scene-to-Room Mapping

| Scene Type | Likely Rooms |
|------------|--------------|
| kitchen | Kitchen |
| office | Office |
| bedroom | Primary Bed, Bed 3, Bed 4 |
| bathroom | Primary Bath, Bath 3, Bath 4 |
| living | Living Room |
| gym | Gym |
| outdoor | Deck, Patio, Porch |

## Audio Routing Priority

1. **Glasses-only** (`glasses_only=True`): Only open-ear speakers
2. **Prefer glasses** (`prefer_glasses=True`): Glasses + room speakers
3. **Default**: Room speakers only (if glasses not worn)

## Privacy Principles

1. **Local-first**: Raw video stays on companion device
2. **Semantic only**: Only features sent to backend
3. **Consent required**: Per-session user approval
4. **Visual indicator**: LED shows camera active
5. **Opt-out**: Granular feature controls

## Integration Points

| System | Integration |
|--------|-------------|
| PersonTracker | `set_meta_glasses()` for visual context |
| PresenceEngine | `set_meta_glasses()` for activity inference |
| WakefulnessManager | `connect_meta_glasses()` for visual detection |
| AudioBridge | `set_meta_glasses()` for audio routing |
| SensorFusionBus | `register_meta_glasses()` for signal fusion |

## SDK Requirements

### iOS
```swift
// Package.swift
.package(url: "https://github.com/facebook/meta-wearables-dat-ios", from: "1.0.0")
```

### Android
```kotlin
// build.gradle.kts
implementation("com.facebook.meta:meta-wearables-dat-android:1.0.0")
```

## Common Patterns

### React to Visual Context
```python
context = await glasses.get_visual_context()

if context.scene_type == "kitchen" and context.activity_hint == "cooking":
    await controller.set_lights(100, rooms=["Kitchen"])
```

### Enhance Location with Vision
```python
# Visual context can boost location confidence
location = tracker.get_person_location("Tim")
if location.visual_scene == "kitchen":
    # Visual confirms WiFi location
    assert location.room == "Kitchen"
```

### Social Context Awareness
```python
if context.faces_detected > 0:
    # User has company - adjust behavior
    await controller.set_scene("entertaining")
```

## Safety

```
h(x) >= 0. Always.
```

- Never store raw camera data
- Respect privacy boundaries
- Provide opt-out controls
- Visual indicators for active capture

---

*First-person perspective extends the Markov blanket.*

鏡
