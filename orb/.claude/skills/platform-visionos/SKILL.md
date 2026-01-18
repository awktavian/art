# visionOS Platform Skill

**100/100 Quality by Default** - Patterns for production-ready visionOS apps.

## When to Use

- Creating or modifying visionOS apps in `apps/vision/`
- Ensuring visionOS-specific quality standards
- Byzantine audit remediation for visionOS

## Required Files (P0)

Every visionOS app MUST have these files implemented:

```
KagamiVision/
├── KagamiVisionApp.swift           # App entry with WindowGroup + ImmersiveSpace
├── DesignSystem.swift              # Spatial design tokens
├── ECS/
│   ├── DeviceEntity.swift          # RealityKit entity for devices
│   ├── LightComponent.swift        # ECS component + system
│   ├── ShadeComponent.swift        # Shade control
│   └── InteractionComponent.swift  # Gesture handling
├── Spaces/
│   ├── FullSpatialExperienceView.swift  # Full immersive space
│   └── Spatial3DRoomView.swift     # Room visualization
├── Services/
│   ├── HandTrackingService.swift   # ARKit hand tracking
│   ├── GazeTrackingService.swift   # Eye tracking
│   ├── SpatialAudioService.swift   # Audio positioning
│   └── ThermalManager.swift        # Quality degradation
└── KagamiVision.entitlements       # Required entitlements
```

## Critical Patterns

### 1. App Structure (MANDATORY)

```swift
import SwiftUI
import RealityKit

@main
struct KagamiVisionApp: App {
    @State private var appModel = AppModel()

    var body: some Scene {
        // Main window
        WindowGroup {
            ContentView()
                .environment(appModel)
        }
        .windowStyle(.volumetric)
        .defaultSize(width: 1.0, height: 0.8, depth: 0.5, in: .meters)

        // Immersive spaces
        ImmersiveSpace(id: "spatial-rooms") {
            Spatial3DRoomView()
                .environment(appModel)
        }
        .immersionStyle(selection: .constant(.mixed), in: .mixed)

        ImmersiveSpace(id: "full-spatial") {
            FullSpatialExperienceView()
                .environment(appModel)
        }
        .immersionStyle(selection: .constant(.progressive), in: .progressive)
    }
}
```

### 2. Spatial Design Tokens (MANDATORY)

```swift
import SwiftUI
import RealityKit

// Proxemic zones (Hall's spatial relationships)
enum ProxemicZone {
    case intimate   // 0-0.45m - Direct manipulation
    case personal   // 0.45-1.2m - Comfortable interaction
    case social     // 1.2-3.6m - Standard viewing
    case public_    // 3.6m+ - Overview mode

    var typographyScale: CGFloat {
        switch self {
        case .intimate: return 0.8
        case .personal: return 1.0
        case .social: return 1.3
        case .public_: return 1.8
        }
    }

    var contentDensity: ContentDensity {
        switch self {
        case .intimate: return .high
        case .personal: return .medium
        case .social: return .low
        case .public_: return .minimal
        }
    }
}

// Spatial materials
enum SpatialMaterial {
    case primary     // Main glass background
    case secondary   // Secondary panels
    case prominent   // Highlighted elements
    case adaptive    // Context-aware

    var material: RealityKit.Material {
        // Return appropriate PhysicallyBasedMaterial
    }
}

// Animation for spatial
enum SpatialAnimation {
    static let appear: Double = 0.377    // 377ms - comfortable appearance
    static let transform: Double = 0.610 // 610ms - position changes
    static let dismiss: Double = 0.233   // 233ms - quick dismiss
}
```

### 3. ECS Device Entity (MANDATORY)

```swift
import RealityKit

final class DeviceEntity: Entity, HasModel, HasCollision {
    var deviceId: String = ""
    var deviceType: DeviceType = .light

    required init() {
        super.init()
        setupComponents()
    }

    private func setupComponents() {
        // Add physics for interaction
        components.set(CollisionComponent(
            shapes: [.generateBox(size: [0.1, 0.1, 0.1])],
            mode: .trigger
        ))

        // Add accessibility
        components.set(AccessibilityComponent(
            isAccessibilityElement: true,
            label: "Device Control",
            value: "Off",
            traits: .isButton
        ))

        // Add interaction component
        components.set(InteractionComponent())
    }

    func updateState(_ newState: DeviceState) {
        // Update visual representation
        Task { @MainActor in
            await animateStateChange(to: newState)
        }
    }

    @MainActor
    private func animateStateChange(to state: DeviceState) async {
        // Use RealityKit animation, not DispatchQueue
        let animation = FromToByAnimation(
            from: transform,
            to: computeTargetTransform(for: state),
            duration: SpatialAnimation.transform
        )
        try? await playAnimation(animation)
    }
}
```

### 4. Hand Tracking (MANDATORY)

```swift
import ARKit
import RealityKit

@MainActor
final class HandTrackingService: ObservableObject {
    @Published private(set) var leftHand: HandAnchor?
    @Published private(set) var rightHand: HandAnchor?
    @Published private(set) var currentGesture: HandGesture = .none

    private var handTracking: HandTrackingProvider?
    private var arSession: ARKitSession?

    enum HandGesture {
        case none
        case pinch
        case point
        case openPalm
        case fist
        case thumbsUp
        case twoHandSpread
        case twoHandPinch
        case twoHandRotate
    }

    func start() async throws {
        guard HandTrackingProvider.isSupported else {
            throw HandTrackingError.notSupported
        }

        let session = ARKitSession()
        let provider = HandTrackingProvider()

        try await session.run([provider])

        self.arSession = session
        self.handTracking = provider

        // Start update loop at 90Hz
        for await update in provider.anchorUpdates {
            await processHandUpdate(update)
        }
    }

    private func processHandUpdate(_ update: AnchorUpdate<HandAnchor>) async {
        switch update.anchor.chirality {
        case .left:
            leftHand = update.anchor
        case .right:
            rightHand = update.anchor
        }

        // Detect gesture
        currentGesture = detectGesture(left: leftHand, right: rightHand)

        // Fatigue tracking - warn if hands above shoulders for >10s
        await checkHandFatigue()
    }
}
```

### 5. Thermal Management (MANDATORY)

```swift
import Foundation

@MainActor
final class ThermalManager: ObservableObject {
    @Published private(set) var currentProfile: QualityProfile = .high
    @Published private(set) var thermalState: ProcessInfo.ThermalState = .nominal

    enum QualityProfile: CaseIterable {
        case ultra    // 90fps, all effects
        case high     // 72fps, most effects
        case medium   // 60fps, reduced effects
        case low      // 45fps, minimal effects
        case minimal  // 30fps, essential only

        var targetFrameRate: Int {
            switch self {
            case .ultra: return 90
            case .high: return 72
            case .medium: return 60
            case .low: return 45
            case .minimal: return 30
            }
        }

        var enableParticles: Bool {
            self <= .medium
        }

        var enableSpatialAudio: Bool {
            self <= .low
        }
    }

    init() {
        // Observe thermal state
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(thermalStateChanged),
            name: ProcessInfo.thermalStateDidChangeNotification,
            object: nil
        )
    }

    @objc private func thermalStateChanged() {
        thermalState = ProcessInfo.processInfo.thermalState
        adjustQualityProfile()
    }

    private func adjustQualityProfile() {
        // Hysteresis: wait 30s before increasing quality
        let newProfile: QualityProfile
        switch thermalState {
        case .nominal:
            newProfile = .high
        case .fair:
            newProfile = .medium
        case .serious:
            newProfile = .low
        case .critical:
            newProfile = .minimal
        @unknown default:
            newProfile = .medium
        }

        // Only decrease immediately, increase with delay
        if newProfile < currentProfile {
            currentProfile = newProfile
        }
    }
}
```

### 6. Accessibility (MANDATORY)

```swift
import RealityKit

// Accessibility component for all RealityKit entities
struct AccessibilityComponent: Component {
    var isAccessibilityElement: Bool = true
    var label: String = ""
    var value: String = ""
    var hint: String = ""
    var traits: UIAccessibilityTraits = []
    var customActions: [AccessibilityAction] = []
}

struct AccessibilityAction {
    let name: String
    let action: () -> Void
}

// Register system
extension AccessibilityComponent {
    static func registerSystem() {
        AccessibilitySystem.registerSystem()
    }
}

// VoiceOver gesture hints
enum SpatialGestureHint {
    case pinchToActivate
    case pinchAndDrag
    case twoHandsToResize

    var voiceOverHint: String {
        switch self {
        case .pinchToActivate:
            return "Pinch to activate"
        case .pinchAndDrag:
            return "Pinch and drag to adjust"
        case .twoHandsToResize:
            return "Use two hands to resize"
        }
    }
}
```

## Testing Requirements

### Unit Tests (Required)

```swift
import XCTest
@testable import KagamiVision

final class GestureRecognitionTests: XCTestCase {
    func testPinchDetection() {
        let service = HandTrackingService()
        // Test gesture detection logic
    }

    func testStateMachineTransitions() {
        let stateMachine = GestureStateMachine()
        // Only one gesture active at a time
        stateMachine.activate(.pinch)
        XCTAssertTrue(stateMachine.isActive(.pinch))
        XCTAssertFalse(stateMachine.isActive(.point))
    }
}
```

### Spatial Tests (Required)

```swift
import XCTest
import RealityKit
@testable import KagamiVision

final class SpatialServicesTests: XCTestCase {
    func testThermalManagerQualityDegradation() async {
        let manager = ThermalManager()
        // Simulate thermal state changes
    }

    func testDeviceEntityAccessibility() {
        let entity = DeviceEntity()
        entity.deviceId = "light_1"
        entity.components[AccessibilityComponent.self]?.label = "Living Room Light"

        XCTAssertNotNil(entity.components[AccessibilityComponent.self])
    }
}
```

## Entitlements (MANDATORY)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <!-- Hand tracking -->
    <key>com.apple.developer.arkit.hand-tracking</key>
    <true/>

    <!-- World sensing for spatial experiences -->
    <key>com.apple.developer.arkit.world-sensing</key>
    <true/>

    <!-- SharePlay for collaborative control -->
    <key>com.apple.developer.group-session</key>
    <true/>

    <!-- Network access -->
    <key>com.apple.security.network.client</key>
    <true/>
</dict>
</plist>
```

## Build Verification

```bash
# Verify visionOS build passes
cd apps/vision/kagami-vision

# Build for Vision Pro
xcodebuild -scheme KagamiVision build \
    -destination 'platform=visionOS Simulator,name=Apple Vision Pro'

# Run tests
xcodebuild test -scheme KagamiVision \
    -destination 'platform=visionOS Simulator,name=Apple Vision Pro'
```

## Quality Checklist

Before any visionOS commit:

- [ ] App entry has both WindowGroup and ImmersiveSpace
- [ ] Proxemic zones implemented for typography scaling
- [ ] All entities have AccessibilityComponent
- [ ] ThermalManager gracefully degrades quality
- [ ] Hand tracking uses 90Hz updates
- [ ] GestureStateMachine prevents conflicts
- [ ] Entitlements include hand-tracking and world-sensing
- [ ] Unit tests pass
- [ ] All spatial audio positioned correctly

## Common Issues & Fixes

### Hand Tracking Not Working
- **Symptom**: Gestures not detected
- **Fix**: Check entitlements for `com.apple.developer.arkit.hand-tracking`

### Thermal Throttling
- **Symptom**: Frame rate drops significantly
- **Fix**: Implement ThermalManager with quality profiles

### Gesture Conflicts
- **Symptom**: Multiple gestures trigger simultaneously
- **Fix**: Use GestureStateMachine for mutex

---

*100/100 or don't ship.*
