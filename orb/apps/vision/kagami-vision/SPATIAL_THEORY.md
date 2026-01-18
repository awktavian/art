# Spatial Theory — Embodied Interaction in Space

**Grounding visionOS design in spatial computing theory.**

## Overview

Kagami Vision operates in three-dimensional space, requiring design principles rooted in spatial cognition, proxemics, and embodied interaction.

## Theoretical Foundations

### Embodied Interaction (Dourish, 2001)

> "Embodied interaction is the creation, manipulation, and sharing of meaning through engaged interaction with artifacts."

**Key principles**:
1. **Participation**: Users act within the world, not on representations
2. **Presence**: Physical and social context matters
3. **Embodiment**: Interaction engages the body

### Proxemics (Hall, 1966)

Spatial relationships communicate meaning:

| Zone | Distance | Appropriate For |
|------|----------|-----------------|
| Intimate | 0-45cm | Personal notifications |
| Personal | 45cm-1.2m | Conversational UI |
| Social | 1.2m-3.6m | Shared displays |
| Public | > 3.6m | Ambient information |

**Kagami Vision application**:
- **Intimate**: Private alerts, safety warnings
- **Personal**: Main control panel, voice interaction
- **Social**: Room visualization, shared scenes
- **Public**: Status displays, ambient awareness

## Spatial Interaction Design

### Gaze-Based Interaction

Gaze as primary selection mechanism:

```swift
class GazeInteractionManager {
    /// Dwell time before selection (ms)
    let dwellThreshold: TimeInterval = 400

    /// Gaze tracking requirements
    var targetRequirements: GazeRequirements {
        GazeRequirements(
            minTargetSize: 44,  // Points (Apple HIG)
            maxLatency: 16,     // ms (60fps)
            accuracy: 0.5       // Degrees visual angle
        )
    }
}
```

### Hand Tracking

Natural gestures grounded in everyday actions:

| Gesture | Meaning | Precedent |
|---------|---------|-----------|
| Pinch | Select | Picking up |
| Drag | Move | Physical movement |
| Expand | Open/zoom | Spreading |
| Wave | Dismiss | Goodbye gesture |
| Point | Direct | Indicating |

### Spatial Anchoring

UI elements anchored to physical or virtual space:

```swift
enum AnchorType {
    case headLocked      // Follows user (HUD)
    case worldLocked     // Fixed in space
    case surfaceLocked   // Attached to surface
    case deviceRelative  // Relative to device position
}

// Control panel: personal distance, head-relative
let controlPanel = SpatialPanel(
    anchor: .headLocked,
    distance: 0.8,  // meters
    size: CGSize(width: 0.4, height: 0.3)
)
```

## Spatial Presence Design

### Kagami's Presence

Kagami manifests as a spatial presence, not just an interface:

```
User's Space
    │
    ├── Intimate Zone (< 45cm)
    │   └── 🔮 Presence indicator (subtle glow)
    │
    ├── Personal Zone (45cm - 1.2m)
    │   └── 💬 Conversation UI
    │   └── 🎛️ Control panel
    │
    ├── Social Zone (1.2m - 3.6m)
    │   └── 🏠 Room visualization
    │   └── 📊 Status displays
    │
    └── Public Zone (> 3.6m)
        └── 🌐 Ambient awareness
```

### Presence States

| State | Visual | Spatial Position |
|-------|--------|-----------------|
| Idle | Subtle particle field | Peripheral |
| Listening | Converging particles | Facing user |
| Speaking | Animated emission | Personal zone |
| Processing | Rotating elements | Personal zone |
| Alert | Attention-grabbing | Intimate zone |

## Room-Scale Visualization

### Home as Spatial Model

```
┌─────────────────────────────────────────────────────────┐
│                    USER'S PHYSICAL SPACE                │
│                                                         │
│      ┌─────────────┐                                   │
│      │             │    ← Physical room bounds         │
│      │   Virtual   │                                   │
│      │   Home      │    ← Miniature 3D model          │
│      │   Model     │                                   │
│      │             │                                   │
│      └─────────────┘                                   │
│           │                                            │
│           ↓                                            │
│      Point to interact with rooms                      │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Device Interaction

Point at physical location → see/control devices:

```swift
func handlePointGesture(direction: simd_float3) {
    // Ray cast to find intersected room
    if let room = spatialModel.raycast(direction) {
        // Show room controls
        showRoomControls(for: room)

        // Haptic feedback
        haptics.play(.selection)
    }
}
```

## Performance Requirements

### Latency Budgets

| Component | Budget | Impact |
|-----------|--------|--------|
| Gaze tracking | < 16ms | Feels responsive |
| Hand tracking | < 20ms | Natural gesture feel |
| UI updates | < 8ms | No judder |
| Scene rendering | < 11ms | 90fps target |

### Foveated Rendering

Reduce rendering cost by matching visual acuity:

```
Central vision (fovea): Full resolution
Peripheral (5-30°): 50% resolution
Far peripheral (> 30°): 25% resolution
```

## Accessibility

### Spatial Accessibility

| Need | Accommodation |
|------|---------------|
| Limited mobility | Voice control as primary |
| Low vision | High contrast mode, larger targets |
| Vestibular | Reduced motion, stable anchors |
| Cognitive | Simplified layouts, clear hierarchy |

### Alternative Inputs

```swift
// Always support voice as fallback
func accessibleAction(for element: UIElement) -> Action {
    Action(
        primary: .gaze_pinch,
        alternatives: [
            .voice("Activate \(element.name)"),
            .controller_select,
            .head_gesture
        ]
    )
}
```

## References

1. **Dourish, P. (2001)**
   "Where the Action Is: The Foundations of Embodied Interaction"
   MIT Press.

2. **Hall, E. T. (1966)**
   "The Hidden Dimension"
   Anchor Books.

3. **Gibson, J. J. (1979)**
   "The Ecological Approach to Visual Perception"
   Houghton Mifflin.

4. **Apple visionOS Human Interface Guidelines (2024)**
   *developer.apple.com/design/human-interface-guidelines/visionos*

5. **Bowman, D. A., et al. (2004)**
   "3D User Interfaces: Theory and Practice"
   Addison-Wesley.

---

*In spatial computing, the interface IS the space.*

🗼 Beacon Colony
