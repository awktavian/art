# Unified XR Platform Development Skill

## Overview

This skill covers cross-platform XR/AR development across Meta Quest, Meta Ray-Ban, Apple Vision Pro, AndroidXR, and WebXR. Use this when building spatial computing experiences that need to work across multiple platforms or when implementing XR features on any single platform.

## When to Use This Skill

- Building cross-platform XR applications
- Implementing spatial interactions (grab, poke, ray, gaze)
- Designing spatial UI layouts and components
- Integrating haptic feedback patterns
- Setting up spatial audio
- Implementing hand, eye, or neural band input
- Ensuring XR accessibility and comfort

## Design System Location

**Design Tokens:** `packages/kagami-xr-design/tokens.json`
**Documentation:** `packages/kagami-xr-design/DESIGN_SYSTEM.md`

## Quick Reference

### Platform SDKs

| Platform | SDK | Language | Framework |
|----------|-----|----------|-----------|
| Meta Quest | Meta Spatial SDK | Kotlin/Java | Android |
| Meta Quest (Unity) | Meta XR SDK | C# | Unity |
| Meta Ray-Ban | Meta AR SDK | Kotlin | Android |
| Apple Vision Pro | visionOS SDK | Swift | SwiftUI + RealityKit |
| Android XR | Android XR SDK | Kotlin | Jetpack Compose XR |
| WebXR | WebXR Device API | JavaScript/TypeScript | Three.js/A-Frame/Babylon |

### Key Design Tokens

```json
{
  "proxemic_zones": {
    "intimate": { "range_m": [0, 0.45], "style": "direct_manipulation" },
    "personal": { "range_m": [0.45, 1.2], "style": "hand_reach" },
    "social": { "range_m": [1.2, 3.6], "style": "ray_pointing" },
    "public": { "range_m": [3.6, null], "style": "gaze_voice" }
  },
  "optimal_content_zone": { "min_m": 1.25, "max_m": 5.0 },
  "button_min_size_m": 0.044,
  "animation_timing_ms": [89, 144, 233, 377, 610, 987]
}
```

## Platform-Specific Guidelines

### Meta Quest / Horizon OS

**Build Commands:**
```bash
# Unity project
/Applications/Unity/Hub/Editor/2022.3.*/Unity.app/Contents/MacOS/Unity \
  -batchmode -buildTarget Android -executeMethod BuildScript.BuildQuest

# Native Spatial SDK
cd apps/xr/kagami-quest && ./gradlew assembleDebug
```

**Key Patterns:**
- Use Meta XR Interaction SDK for consistent grab/poke/ray interactions
- Anchor content to physical space, avoid head-locked HUD
- Support both hand tracking and controllers
- Use Horizon UI Set for consistent system UI

**Interaction SDK Setup:**
```csharp
// Add Interactable to objects
gameObject.AddComponent<Grabbable>();
gameObject.AddComponent<RayInteractable>();
gameObject.AddComponent<PokeInteractable>();
```

### Meta Ray-Ban Display

**Design Constraints:**
- 600x600 pixel, 20-degree FOV display
- Design for 5-10 second interaction bursts
- Neural Band EMG is primary input alongside voice
- Glanceable UI only - no complex navigation

**Neural Band Gestures:**
- Click: Subtle finger tap
- Swipe: Finger motion for scrolling
- Pinch: Thumb-to-finger for grab/zoom
- Draw: Surface tracing for text input

**Best Practices:**
- Prefer voice commands over visual navigation
- Keep text large and high contrast (5000 nits outdoor)
- Process EMG on-device for privacy
- Design for ambient awareness, not immersion

### Apple Vision Pro (visionOS)

**Build Commands:**
```bash
# visionOS build
xcodebuild -project apps/visionos/kagami-visionos/KagamiVision.xcodeproj \
  -scheme KagamiVision -configuration Debug \
  -destination 'platform=visionOS Simulator' build
```

**Key Patterns:**
- Start in a Window, let users control immersion
- Eye + Pinch is primary selection (look, then pinch)
- Use SwiftUI for 2D panels, RealityKit for 3D content
- Volumes for 3D objects viewable from any angle

**SwiftUI Spatial Setup:**
```swift
import SwiftUI
import RealityKit

@main
struct KagamiVisionApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        .windowStyle(.volumetric)

        ImmersiveSpace(id: "immersive") {
            ImmersiveView()
        }
    }
}
```

### Android XR (Samsung Galaxy XR)

**Build Commands:**
```bash
# Android XR build
cd apps/xr/kagami-androidxr && ./gradlew assembleDebug
```

**Key Patterns:**
- Jetpack Compose XR for spatial UI
- Gemini integration for contextual AI
- 2D app compatibility as entry point
- ARCore for scene understanding

**Compose XR Setup:**
```kotlin
@Composable
fun SpatialContent() {
    Subspace {
        SpatialPanel(
            modifier = SubspaceModifier.width(600.dp).height(400.dp)
        ) {
            KagamiUI()
        }
    }
}
```

### WebXR

**Key Patterns:**
- Feature detect before requesting session
- Provide meaningful 2D fallback
- Request immersive session only on user gesture
- Use Three.js, A-Frame, or Babylon.js

**Session Setup:**
```javascript
async function initXR() {
    if (!navigator.xr) {
        return show2DFallback();
    }

    const arSupported = await navigator.xr.isSessionSupported('immersive-ar');
    const vrSupported = await navigator.xr.isSessionSupported('immersive-vr');

    if (arSupported) {
        await startARSession();
    } else if (vrSupported) {
        await startVRSession();
    } else {
        await startInlineSession();
    }
}
```

## Input Modality Implementation

### Hand Tracking

**Universal Gestures:**
| Gesture | Action | Detection |
|---------|--------|-----------|
| Pinch | Select/Grab | Thumb + index distance < 2cm |
| Poke | Button press | Index tip in collision |
| Grab | Object hold | Hand closure > 70% |
| Palm Open | Menu/Stop | All fingers extended, palm forward |

**Minimum Target Sizes:**
- Touch/Poke: 44mm (0.044m)
- Grab zone: 50mm (0.05m)
- Hover detection: 100mm (0.1m)

### Eye Tracking

**Pattern: Eye + Gesture Confirmation**
```
1. User looks at target (gaze ray hit)
2. Visual feedback on hover (scale 1.05x, glow)
3. User performs confirming gesture (pinch)
4. Action executes with haptic feedback
```

**Never use gaze-only activation for critical actions.**

### Voice Commands

**Universal Command Categories:**
- Navigation: "go to", "open", "show"
- Control: "pause", "play", "stop", "mute"
- Query: "what is", "how do I", "tell me about"
- Action: "take photo", "send message", "save"

## Haptic Feedback Patterns

Load from `packages/kagami-xr-design/tokens.json`:

```javascript
const haptics = {
    confirm: { duration: 50, intensity: 0.6, freq: 200 },
    error: { pattern: [[100, 0.8], [50, 0], [100, 0.8]], freq: 150 },
    hover: { duration: 20, intensity: 0.3, freq: 250 },
    grab: { duration: 100, intensity: 0.5, ramp: 'up', freq: 180 }
};
```

**Guidelines:**
- Make haptics optional and adjustable
- Maintain consistency (same action = same haptic)
- Avoid overuse; reserve for meaningful feedback

## Spatial Audio Integration

**HRTF Requirements:**
- Head tracking latency: <20ms
- Use platform-provided universal HRTF
- Headphones required for proper spatialization

**Distance Attenuation:**
```
0-0.5m:   No attenuation (intimate)
0.5-2m:   Full spatialization (personal)
2-10m:    -3dB per meter (social)
>10m:     Environmental reverb (ambient)
```

**UI Sounds:**
- Position: head-locked
- Volume: -6dB relative to world sounds

## Comfort & Accessibility

### Critical Thresholds

| Parameter | Value |
|-----------|-------|
| Optimal horizontal view | 30 deg from center |
| Comfortable horizontal | 50 deg max |
| Content distance | 1.25m - 5m optimal |
| Text minimum height | 10mm at 1m |
| Contrast ratio | 4.5:1 minimum |
| Locomotion max speed | 3 m/s |
| Session reminder | Every 30 min |

### Accessibility Checklist

- [ ] Motion reduction option available
- [ ] One-handed operation supported
- [ ] Voice alternative for all actions
- [ ] High contrast mode
- [ ] Scalable text/UI
- [ ] Closed captions for audio
- [ ] Reduce vestibular triggers option

## Cross-Platform Fallbacks

| Feature | Primary | Fallback |
|---------|---------|----------|
| Hand tracking | Gesture recognition | Controller input |
| Eye tracking | Gaze selection | Head-based reticle |
| Spatial audio | HRTF 3D | Stereo panning |
| Haptics | Controller/wrist | Visual feedback |
| Neural band | EMG gestures | Touch/voice |

## Testing Checklist

### Interaction Testing
- [ ] All gestures respond correctly
- [ ] Haptic feedback fires appropriately
- [ ] Visual feedback on hover/select states
- [ ] Voice commands recognized accurately
- [ ] Eye tracking calibration works

### Comfort Testing
- [ ] No motion sickness triggers
- [ ] Content within comfortable view angles
- [ ] Session duration reminders work
- [ ] Break suggestions appropriate

### Accessibility Testing
- [ ] Screen reader announces elements
- [ ] Motion reduction mode works
- [ ] One-handed operation verified
- [ ] Voice navigation complete
- [ ] Color blind safe palettes

### Platform Testing
- [ ] Meta Quest 3 hand tracking
- [ ] Meta Quest 3 controller input
- [ ] Vision Pro eye + pinch
- [ ] Android XR Compose layout
- [ ] WebXR feature detection
- [ ] 2D fallback mode

## Troubleshooting

### Hand Tracking Issues
- Ensure good lighting
- Check hand model loading
- Verify collision layers
- Test with both hands

### Eye Tracking Calibration
- Recalibrate in system settings
- Ensure proper headset fit
- Clean eye tracking sensors

### Haptic Not Working
- Check controller connection
- Verify haptic intensity not at 0
- Test with system haptic patterns

### Spatial Audio Positioning Wrong
- Verify head tracking active
- Check audio source positioning
- Ensure HRTF enabled

## Related Skills

- `.claude/skills/platform-visionos/SKILL.md` - visionOS specific
- `.claude/skills/platform-android/SKILL.md` - Android general
- `.claude/skills/design/SKILL.md` - Design principles
- `.claude/skills/safety-verification/SKILL.md` - Safety checks

## Resources

- [Kagami XR Design Tokens](../../packages/kagami-xr-design/tokens.json)
- [Kagami XR Design System](../../packages/kagami-xr-design/DESIGN_SYSTEM.md)
- [Meta Spatial SDK Docs](https://developers.meta.com/horizon/develop/spatial-sdk)
- [visionOS HIG](https://developer.apple.com/design/human-interface-guidelines/designing-for-visionos)
- [Android XR Docs](https://developer.android.com/xr)
- [WebXR MDN](https://developer.mozilla.org/en-US/docs/Web/API/WebXR_Device_API)
