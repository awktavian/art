# Kagami XR Design System

A unified design system for cross-platform XR/AR development across Meta Quest, Meta Ray-Ban, Apple Vision Pro, AndroidXR, and WebXR.

## Overview

This design system provides consistent design tokens, interaction patterns, and guidelines for building spatial computing experiences that work across all major XR platforms. It emphasizes:

- **Cross-platform consistency** - Shared vocabulary and patterns
- **Platform-appropriate adaptation** - Respect each platform's strengths
- **Human-centered design** - Comfort, accessibility, and safety first
- **Graceful degradation** - Progressive enhancement for varying capabilities

## Platform Reference

| Platform | Type | FOV | Primary Input | SDK |
|----------|------|-----|---------------|-----|
| Meta Quest 3 | MR Headset | 110 x 96 deg | Hands/Controllers | Meta Spatial SDK |
| Meta Ray-Ban Display | AR Glasses | 20 x 20 deg | Neural Band/Voice | Meta AR SDK |
| Apple Vision Pro | Spatial Computer | 100 x 90 deg | Eye + Pinch | visionOS SDK |
| Samsung Galaxy XR | MR Headset | 110 x 95 deg | Hands/Eye/Voice | Android XR SDK |
| WebXR | Web Standard | Device-dependent | Device-dependent | WebXR Device API |

### Platform Deep Dives

#### Meta Quest / Horizon OS

Meta's Spatial SDK provides comprehensive tools for mixed reality development. Key capabilities:

- **Spatial Anchoring**: Fix virtual objects to physical space for increased immersion
- **MRUK (Mixed Reality Utility Kit)**: Scene understanding and mesh access
- **Interaction SDK**: Pre-built grab, poke, ray, and distance grab interactions
- **Horizon UI Set**: Standard UI components for consistent experiences

**Design Guidelines:**
- Avoid HUD-locked content; anchor to physical space instead
- Support both hands and controllers as input
- Use ray-casting for distance interactions
- Keep passthrough content blended naturally with the environment

Reference: [Meta MR Design Guidelines](https://developers.meta.com/horizon/design/mr-design-guideline/)

#### Meta Ray-Ban Display Glasses

Designed for glanceable, short interactions rather than extended immersive sessions:

- **600x600 pixel display** with 20-degree FOV
- **5,000 nits brightness** for outdoor visibility
- **Neural Band input** via sEMG muscle detection
- **Meta AI integration** for contextual assistance

**Design Guidelines:**
- Design for 5-10 second interaction bursts
- Prioritize voice and neural input over visual navigation
- Keep visual UI minimal and non-intrusive
- Process EMG data on-device for privacy

Reference: [Meta Ray-Ban Display](https://www.meta.com/blog/meta-ray-ban-display-ai-glasses-connect-2025/)

#### Apple Vision Pro (visionOS)

Apple's spatial computing approach emphasizes:

- **Windows, Volumes, and Spaces**: Three paradigms for content
- **Eye + Pinch selection**: Look to target, pinch to select
- **SwiftUI + RealityKit**: Native spatial UI frameworks
- **Shared Space**: Multiple apps coexisting in the user's environment

**Design Guidelines:**
- Start in a window, let users control immersion level
- Never place users in full immersion without orientation
- Center content in the field of view for comfort
- Use spatial audio positioned to match visual sources

Reference: [Designing for visionOS](https://developer.apple.com/design/human-interface-guidelines/designing-for-visionos)

#### Android XR (Samsung Galaxy XR)

Google's Android XR platform combines familiar Android development with spatial capabilities:

- **Jetpack Compose XR**: Familiar UI framework extended for 3D
- **Gemini integration**: Built-in AI assistance aware of context
- **Multi-OEM ecosystem**: Open platform for various hardware
- **ARCore integration**: Scene understanding and anchors

**Design Guidelines:**
- Leverage existing Android/Compose knowledge
- Take advantage of Gemini for contextual AI features
- Design for varied hardware capabilities
- Support 2D app mode as entry point before spatial upgrade

Reference: [Android XR Development Guide](https://framesixty.com/android-xr-development-guide/)

#### WebXR

The W3C standard for immersive web experiences:

- **Session modes**: inline, immersive-vr, immersive-ar
- **Cross-device compatibility**: Works across all WebXR-capable browsers
- **No installation required**: Instant access via URL
- **Progressive enhancement**: Graceful fallback to 2D

**Design Guidelines:**
- Feature-detect capabilities before use
- Provide meaningful 2D fallback
- Optimize for performance (web constraints)
- Request immersive session only with user gesture

Reference: [WebXR Device API](https://developer.mozilla.org/en-US/docs/Web/API/WebXR_Device_API)

---

## Proxemic Zones

Based on Hall's proxemic theory, adapted for XR spatial computing:

```
+-------------------+------------------+-------------------+
|     INTIMATE      |     PERSONAL     |      SOCIAL       |    PUBLIC
|    0 - 0.45m      |   0.45 - 1.2m    |    1.2 - 3.6m     |    > 3.6m
|                   |                  |                   |
| - Personal UI     | - Workspaces     | - Shared content  | - Environment
| - Private data    | - Menus          | - Collaboration   | - Landmarks
| - Focus elements  | - Hand reach     | - Ray pointing    | - Navigation
|                   |                  |                   |
| Direct manipulation| Hand-based      | Ray-based         | Gaze/Voice
+-------------------+------------------+-------------------+
```

### Optimal Content Zone: 1.25m - 5.0m

This is the recommended zone for primary AR content. Content closer than 1.25m can cause vergence-accommodation conflict (eye strain). Content beyond 5m becomes difficult to interact with precisely.

### Social Safety

In social XR:
- **Never allow uninvited entry into intimate zone (0-0.45m)**
- Avatars should bounce or fade when approaching personal space without consent
- Provide clear boundaries users can set for their comfort

---

## Input Modalities

### Hand Tracking

Universal hand gestures supported across platforms:

| Gesture | Description | Use Cases | Platforms |
|---------|-------------|-----------|-----------|
| Pinch | Thumb + index touch | Select, confirm, grab | All |
| Poke | Index finger touch | Button press, UI | Quest, Vision Pro, AndroidXR |
| Grab | Close hand | Object manipulation | All |
| Palm Open | Open hand forward | Menu summon, stop | Quest, Vision Pro, AndroidXR |
| Two-Hand Scale | Both hands pinch + spread | Scale, zoom | All |

**Design Requirements:**
- Minimum target size: 44mm (0.044m)
- Recommended target size: 60mm (0.06m)
- Hover detection distance: 100mm (0.1m)
- Always provide visual feedback on hover

### Eye Tracking

Available on Quest Pro, Vision Pro, and Galaxy XR:

| Behavior | Duration | Use Case |
|----------|----------|----------|
| Dwell | 800ms | Selection (use sparingly) |
| Glance | 200ms | Preview, hover states |
| Saccade | Rapid | Navigation scanning |

**Critical Rule: Never use gaze-only for activation.**

Apple's eye+pinch pattern is the gold standard: look to target, pinch to select. This prevents accidental activation and "Midas Touch" problem.

### Neural Band (Meta)

Meta's EMG wristband enables:
- **Click**: Subtle finger tap
- **Swipe**: Finger motion for scrolling
- **Pinch**: Thumb-to-finger for grab/zoom
- **Draw**: Finger tracing on any surface for text input

All EMG processing happens on-device. Only simple commands like "click" are transmitted, protecting biometric privacy.

### Voice

Wake words and command patterns:

| Platform | Wake Word | Command Style |
|----------|-----------|---------------|
| Meta | "Hey Meta" | Natural language |
| Apple | "Siri" | Natural language |
| Android | "Hey Google" | Natural language |

**Design for voice:**
- Confirm destructive actions visually
- Provide visual feedback during listening
- Handle ambient noise gracefully
- Offer voice as alternative, not only path

### Controllers

Standard 6DOF controller mappings:

| Control | Primary Action | Secondary |
|---------|----------------|-----------|
| Trigger | Select/Grab | Fire |
| Grip | Context menu | Secondary grab |
| Thumbstick | Locomotion | Scroll |
| A/X Button | Confirm | Jump |
| B/Y Button | Back/Cancel | Menu |

Vision Pro now supports PlayStation VR2 Sense controllers (visionOS 26) for gaming applications.

---

## Haptic Feedback

### Standard Haptic Patterns

```json
{
  "confirm": { "duration_ms": 50, "intensity": 0.6, "frequency_hz": 200 },
  "error": { "pattern": [100ms ON, 50ms OFF, 100ms ON], "intensity": 0.8 },
  "hover": { "duration_ms": 20, "intensity": 0.3, "frequency_hz": 250 },
  "grab": { "duration_ms": 100, "ramp": "up", "intensity": 0.5-0.7 },
  "release": { "duration_ms": 50, "ramp": "down", "intensity": 0.6 }
}
```

### Wrist Haptics (Neural Band)

The Meta Neural Band provides:
- **Squeeze feedback**: Simulates object weight and resistance
- **Vibrotactile feedback**: Notifications and texture simulation
- Intensity range: 0.1 to 1.0
- Frequency range: 50-300 Hz

### Design Guidelines

1. **Make haptics optional** - Users can disable
2. **Allow intensity adjustment** - Sensitivity varies
3. **Maintain consistency** - Same action = same haptic
4. **Avoid overuse** - Reserve for meaningful feedback
5. **Test without haptics** - App must remain usable

---

## Spatial Audio

### HRTF (Head-Related Transfer Function)

3D audio requires head tracking with <20ms latency. When head moves, audio must update instantly to maintain spatialization.

Platform HRTFs:
- **Meta**: Universal HRTF optimized for Quest
- **Apple**: Generic + personalized ear scanning option
- **Android**: Device-dependent

### Audio Distance Zones

| Zone | Distance | Behavior |
|------|----------|----------|
| Intimate | 0-0.5m | Mono/centered, no attenuation |
| Personal | 0.5-2m | Full spatialization |
| Social | 2-10m | Distance attenuation (-3dB/m) |
| Ambient | >10m | Environmental reverb |

### Integration Points

1. **UI Sounds**: Head-locked, -6dB relative to world sounds
2. **Object Audio**: Source-positioned, respecting physics
3. **Voice Chat**: Positioned at avatar mouth
4. **Ambient**: Environmental, matching scene acoustics
5. **Passthrough AR**: Match reverb to real room when possible

### Recommended Formats

- **Object-based audio** for maximum flexibility
- **Ambisonics** for captured environments
- **Dolby Atmos** for cinematic content
- **Stereo fallback** for unsupported devices

---

## Display Modes

### Immersive VR
- Full virtual environment
- World-anchored content
- Use for games, training, virtual tourism

### Passthrough AR (Mixed Reality)
- Virtual content over real world
- Spatial anchors for persistence
- Use for productivity, navigation, assistance

### 2D Panels
- Traditional UI floating in space
- Entry point before spatial features
- Use for apps, browsing, video

### Volumes
- 3D content viewable from any angle
- Showcase mode for objects
- Use for 3D models, data viz, art

### Glanceable HUD (Ray-Ban Display)
- Minimal, short-duration UI
- Voice/neural primary input
- Use for notifications, navigation cues

---

## UI Components

### Panels

Flat surfaces for traditional UI:

```
Size Presets:
- Small:  0.3m x 0.2m
- Medium: 0.6m x 0.4m
- Large:  1.0m x 0.7m
- Full:   2.0m x 1.2m

Properties:
- Corner radius: 20mm
- Depth offset: 1mm (for layering)
- Shadow: 5mm offset, 10mm blur, 30% opacity
```

### Buttons

```
Minimum size: 44mm (touch target)
Recommended: 60mm
Depth: 8mm
Press depth: -4mm (inward)

States:
- Default: 100% opacity
- Hover: 105% scale + glow
- Pressed: Depth offset -4mm, 90% opacity
- Disabled: 50% opacity
```

### Animation Timing

Fibonacci-based durations for natural motion:

| Name | Duration | Use Case |
|------|----------|----------|
| Instant | 89ms | Micro-interactions |
| Fast | 144ms | Button responses |
| Normal | 233ms | Panel transitions |
| Slow | 377ms | Page changes |
| Dramatic | 610ms | Mode changes |
| Cinematic | 987ms | Scene transitions |

**Easing:**
- Entrance: `ease-out` (fast start, slow end)
- Exit: `ease-in` (slow start, fast end)
- Movement: `ease-in-out` (smooth)
- Interactive: Spring physics (stiffness: 300, damping: 30)

---

## Comfort Guidelines

### Viewing Angles

```
Horizontal:
  Optimal: 30 deg center
  Comfortable: 50 deg
  Maximum: 70 deg (avoid)

Vertical:
  Up: 15 deg (optimal), 25 deg (comfortable), 35 deg (max)
  Down: 20 deg (optimal), 40 deg (comfortable), 60 deg (max)
```

### Locomotion

1. **Teleportation** (recommended)
   - Fade duration: 150ms
   - Avoids motion sickness

2. **Smooth Locomotion** (optional)
   - Max speed: 3 m/s
   - Use vignette during motion
   - Ease in/out acceleration

3. **Rotation**
   - Snap: 30 deg increments
   - Smooth: Max 90 deg/s

### Session Duration

- Reminder every 30 minutes
- Maximum recommended: 2 hours
- Break duration: 10 minutes minimum

### Accessibility

| Requirement | Minimum |
|-------------|---------|
| Text height | 10mm (at 1m) |
| Contrast ratio | 4.5:1 |
| Motion reduction | Optional |
| One-handed operation | Supported |
| Voice alternative | Available |

---

## Safety

### Guardian/Boundary System

- Warning at 0.5m from boundary
- Passthrough activates at 0.3m
- Visual and haptic warnings

### Social Safety

- Personal space bubble: 0.45m
- Consent required for proximity
- Block intimate zone entry in social apps

### Eye Care

- Optimal focus distance: 2m
- Blue light filter option
- Auto-brightness adjustment

### Privacy Indicators

- Recording LED always visible to others
- Camera active indicator
- Microphone indicator

---

## Cross-Platform Strategy

### Feature Detection

```javascript
// Example: WebXR feature detection
if (navigator.xr) {
  const supported = await navigator.xr.isSessionSupported('immersive-ar');
  if (supported) {
    // Full AR experience
  } else {
    // Graceful fallback
  }
}
```

### Graceful Degradation

| Feature | Fallback |
|---------|----------|
| Hand tracking | Controllers |
| Eye tracking | Head gaze |
| Spatial audio | Stereo |
| Haptics | Visual feedback |
| Neural band | Touch/voice |

### Progressive Enhancement

1. Start with baseline 2D experience
2. Add spatial UI if supported
3. Enable hand tracking if available
4. Add eye tracking for precision
5. Enable platform-specific features

---

## Implementation Examples

### Unity (Meta Spatial SDK)

```csharp
// Using Meta Interaction SDK
using Oculus.Interaction;

// Grabbable object setup
[RequireComponent(typeof(Grabbable))]
public class InteractiveObject : MonoBehaviour {
    private Grabbable _grabbable;

    void Start() {
        _grabbable = GetComponent<Grabbable>();
        _grabbable.WhenPointerEventRaised += OnPointerEvent;
    }

    void OnPointerEvent(PointerEvent evt) {
        if (evt.Type == PointerEventType.Select) {
            // Play haptic feedback
            OVRInput.SetControllerVibration(0.5f, 0.5f,
                OVRInput.Controller.RTouch);
        }
    }
}
```

### SwiftUI (visionOS)

```swift
import SwiftUI
import RealityKit

struct SpatialView: View {
    var body: some View {
        RealityView { content in
            let model = ModelEntity(mesh: .generateBox(size: 0.1))
            model.components.set(InputTargetComponent())
            model.components.set(CollisionComponent(
                shapes: [.generateBox(size: [0.1, 0.1, 0.1])]
            ))
            content.add(model)
        }
        .gesture(TapGesture().targetedToAnyEntity().onEnded { value in
            // Eye + pinch selection
        })
    }
}
```

### Jetpack Compose (Android XR)

```kotlin
@Composable
fun SpatialPanel() {
    Subspace {
        SpatialPanel(
            modifier = SubspaceModifier.width(600.dp).height(400.dp)
        ) {
            Column {
                Text("Spatial UI Panel")
                Button(onClick = { /* handle */ }) {
                    Text("Interact")
                }
            }
        }
    }
}
```

### WebXR (JavaScript)

```javascript
async function initXR() {
    const session = await navigator.xr.requestSession('immersive-ar', {
        requiredFeatures: ['local-floor', 'hit-test'],
        optionalFeatures: ['hand-tracking']
    });

    const glLayer = new XRWebGLLayer(session, gl);
    session.updateRenderState({ baseLayer: glLayer });

    session.requestAnimationFrame(onXRFrame);
}

function onXRFrame(time, frame) {
    const pose = frame.getViewerPose(referenceSpace);
    if (pose) {
        // Render spatial content
    }
    frame.session.requestAnimationFrame(onXRFrame);
}
```

---

## Resources

### Official Documentation

- [Meta Spatial SDK](https://developers.meta.com/horizon/develop/spatial-sdk)
- [Meta MR Design Guidelines](https://developers.meta.com/horizon/design/mr-design-guideline/)
- [Meta Haptics SDK](https://developers.meta.com/horizon/design/haptics-overview)
- [Apple visionOS Design](https://developer.apple.com/design/human-interface-guidelines/designing-for-visionos)
- [Android XR Developer Guide](https://developer.android.com/xr)
- [WebXR Device API (MDN)](https://developer.mozilla.org/en-US/docs/Web/API/WebXR_Device_API)
- [Immersive Web Dev](https://immersiveweb.dev/)

### Research & Standards

- [W3C WebXR Specification](https://www.w3.org/TR/webxr/)
- [Hall's Proxemic Theory](https://www.interaction-design.org/literature/article/spatial-ui-design-tips-and-best-practices)
- [HRTF and Spatial Audio](https://embody.co/blogs/technology/a-sound-architects-guide-to-spatial-audio-on-xr-devices)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-01 | Initial unified design system |

---

*This design system is part of the Kagami project. For development skills and implementation guidance, see `.claude/skills/platform-xr-unified/SKILL.md`.*
