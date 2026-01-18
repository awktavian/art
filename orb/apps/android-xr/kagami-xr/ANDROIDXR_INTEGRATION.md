# Kagami AndroidXR Integration Plan

**Colony: Nexus (e4) - Integration**

## Executive Summary

AndroidXR is Google's extended reality platform that brings Android to XR headsets (Samsung Galaxy XR) and AI glasses. This document outlines the integration plan for Kagami on the AndroidXR platform, providing parity with the existing visionOS implementation while leveraging Android-specific strengths like Gemini AI integration.

## Platform Overview

### AndroidXR vs visionOS Comparison

| Aspect | AndroidXR | visionOS |
|--------|-----------|----------|
| **Launch** | October 2025 (SDK Preview Dec 2024) | June 2023 |
| **Hardware** | Samsung Galaxy XR, AI Glasses, partner devices | Apple Vision Pro only |
| **AI Integration** | Gemini AI (multimodal, conversational) | Siri (limited) |
| **Ecosystem** | Open, multi-vendor | Closed, Apple-only |
| **Framework** | Jetpack XR SDK, Unity, OpenXR, WebXR, Godot | RealityKit, Swift |
| **UI Framework** | Jetpack Compose for XR | SwiftUI for visionOS |
| **Price** | ~$1,799 (Galaxy XR) | $3,499 (Vision Pro) |
| **Developer Access** | Open (no approval needed) | Standard Apple developer |

### SDK Components

1. **Jetpack Compose for XR** - Declarative spatial UI
2. **Jetpack SceneCore** - 3D scene graph management
3. **ARCore for Jetpack XR** - Perception (hand tracking, plane detection)
4. **Material Design for XR** - Spatial design components
5. **Android XR Emulator** - Testing without hardware

## Architecture Design

### Kagami AndroidXR App Structure

```
apps/android-xr/kagami-xr/
├── app/
│   ├── build.gradle.kts
│   └── src/main/
│       ├── AndroidManifest.xml
│       ├── java/com/kagami/xr/
│       │   ├── KagamiXRApp.kt              # Application entry
│       │   ├── MainActivity.kt              # Main activity with spatial scenes
│       │   │
│       │   ├── ui/                          # Spatial UI layer
│       │   │   ├── spatial/
│       │   │   │   ├── SpatialHomeScreen.kt       # Main spatial home interface
│       │   │   │   ├── SpatialRoomView.kt         # 3D room visualization
│       │   │   │   ├── SpatialControlPanel.kt     # Device control panel
│       │   │   │   └── SpatialPresenceView.kt     # Kagami presence orb
│       │   │   ├── components/
│       │   │   │   ├── SpatialDeviceCard.kt       # Device control card
│       │   │   │   ├── SpatialRoomEntity.kt       # 3D room entity
│       │   │   │   └── SpatialLightGlow.kt        # Light visualization
│       │   │   └── theme/
│       │   │       ├── SpatialDesignSystem.kt     # Proxemic zones, materials
│       │   │       └── SpatialColors.kt           # Colony-aware colors
│       │   │
│       │   ├── services/                    # Core services
│       │   │   ├── HandTrackingService.kt         # ARCore hand tracking
│       │   │   ├── GazeTrackingService.kt         # Eye tracking
│       │   │   ├── SpatialAnchorService.kt        # Persistent anchors
│       │   │   ├── SpatialAudioService.kt         # 3D audio positioning
│       │   │   ├── GeminiAssistantService.kt      # Gemini AI integration
│       │   │   └── ThermalManager.kt              # Quality profiles
│       │   │
│       │   ├── gestures/                    # Gesture system
│       │   │   ├── GestureRecognizer.kt           # Pinch, point, fist detection
│       │   │   ├── GestureStateMachine.kt         # Conflict prevention
│       │   │   └── SemanticGestureMapper.kt       # Gesture to action mapping
│       │   │
│       │   ├── scene/                       # SceneCore integration
│       │   │   ├── HomeSceneManager.kt            # Main scene management
│       │   │   ├── RoomEntityFactory.kt           # Room entity creation
│       │   │   ├── DeviceEntityFactory.kt         # Device entity creation
│       │   │   └── LightingManager.kt             # Scene lighting
│       │   │
│       │   └── network/                     # API layer
│       │       ├── KagamiApiService.kt            # Kagami API client
│       │       └── WebSocketService.kt            # Real-time updates
│       │
│       └── res/
│           ├── values/
│           │   └── strings.xml
│           └── drawable/
│
├── gradle/
├── build.gradle.kts
├── settings.gradle.kts
└── ANDROIDXR_INTEGRATION.md                 # This file
```

### Feature Parity with visionOS

| Feature | visionOS (kagami-vision) | AndroidXR (kagami-xr) |
|---------|--------------------------|----------------------|
| **3D Room Model** | RealityKit entities | SceneCore entities |
| **Hand Tracking** | ARKit HandTrackingProvider | ARCore Hand tracking |
| **Eye/Gaze Tracking** | ARKit gaze tracking | ARCore gaze tracking |
| **Spatial Audio** | AVFoundation spatial | Android spatial audio |
| **Gestures** | pinch, point, palm, fist | pinch, point, palm, fist |
| **Proxemic Zones** | Hall's zones | Hall's zones (shared) |
| **Thermal Management** | ThermalManager | ThermalManager |
| **Immersive Spaces** | ImmersiveSpace | SubspaceSession |
| **Window Style** | .volumetric, .plain | SpatialPanel, Volume |
| **AI Assistant** | - | Gemini AI (AndroidXR unique) |

## Implementation Phases

### Phase 1: Foundation (2 weeks)

1. **Project Setup**
   - Create Gradle project with Jetpack XR dependencies
   - Configure AndroidManifest for XR permissions
   - Set up Android XR emulator for development

2. **Core Services**
   - Implement KagamiApiService (reuse from kagami-android)
   - Port WebSocketService for real-time updates
   - Create ThermalManager for quality profiles

3. **Basic UI**
   - Create SpatialHomeScreen with Compose for XR
   - Implement SpatialPanel windows for controls
   - Add Material Design for XR components

### Phase 2: Spatial Features (3 weeks)

1. **Hand Tracking**
   - Implement HandTrackingService with ARCore
   - Port gesture detection from visionOS (pinch, point, fist)
   - Create GestureStateMachine for conflict prevention

2. **3D Room Visualization**
   - Create SceneCore entities for rooms
   - Implement room layout with floor depth layers
   - Add light glow effects using emissive materials

3. **Spatial Anchors**
   - Persistent anchor service for room positions
   - World-locked control panels
   - Device placement in spatial context

### Phase 3: Smart Home Control (2 weeks)

1. **Device Control UI**
   - Spatial device cards for lights, shades, locks
   - Gesture-based brightness/position control
   - Voice command integration via Gemini

2. **Scene Activation**
   - Scene selection in spatial context
   - Preview before activation
   - Cross-device synchronization

3. **Safety Features**
   - Emergency stop gesture (two-hand stop)
   - Safety score visualization
   - Privacy indicators

### Phase 4: AI Integration (2 weeks) - AndroidXR Unique

1. **Gemini Assistant**
   - Contextual AI assistance in spatial view
   - Voice-based smart home control
   - Visual context understanding (see what user sees)

2. **Proactive Suggestions**
   - Time/location-based scene suggestions
   - Energy optimization recommendations
   - Security alerts with spatial context

## Technical Specifications

### Dependencies (build.gradle.kts)

```kotlin
dependencies {
    // Jetpack XR SDK
    implementation("androidx.xr.runtime:runtime:1.0.0-alpha07")
    implementation("androidx.xr.scenecore:scenecore:1.0.0-alpha08")
    implementation("androidx.xr.compose:compose:1.0.0-alpha08")
    implementation("androidx.xr.compose.material3:material3:1.0.0-alpha12")
    implementation("androidx.xr.arcore:arcore:1.0.0-alpha07")

    // Compose
    implementation(platform("androidx.compose:compose-bom:2024.12.01"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.material3:material3")

    // Kotlin Coroutines
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")

    // Networking (reuse from kagami-android)
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.squareup.moshi:moshi-kotlin:1.15.0")

    // Gemini AI
    implementation("com.google.ai.client.generativeai:generativeai:0.9.0")

    // Hilt DI
    implementation("com.google.dagger:hilt-android:2.48.1")
    kapt("com.google.dagger:hilt-compiler:2.48.1")
}
```

### Manifest Permissions

```xml
<manifest>
    <!-- XR Permissions -->
    <uses-permission android:name="android.permission.SCENE_UNDERSTANDING" />
    <uses-permission android:name="android.permission.HAND_TRACKING" />

    <!-- Required Features -->
    <uses-feature android:name="android.hardware.xr.headset" android:required="true" />
    <uses-feature android:name="android.software.xr.immersive" android:required="false" />

    <!-- Network -->
    <uses-permission android:name="android.permission.INTERNET" />

    <!-- Audio -->
    <uses-permission android:name="android.permission.RECORD_AUDIO" />

    <application
        android:name=".KagamiXRApp"
        android:label="Kagami XR">

        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:launchMode="singleInstance"
            android:configChanges="orientation|screenSize|keyboardHidden">

            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
                <category android:name="android.intent.category.XR_APP" />
            </intent-filter>
        </activity>
    </application>
</manifest>
```

### Spatial Design Tokens (Shared with visionOS)

```kotlin
/**
 * Proxemic zones based on Hall's spatial relationships (1966).
 * These are shared between AndroidXR and visionOS for consistency.
 */
enum class ProxemicZone(
    val minDistance: Float,  // meters
    val maxDistance: Float,
    val typographyScale: Float,
    val contentDensity: ContentDensity
) {
    INTIMATE(0f, 0.45f, 0.8f, ContentDensity.HIGH),
    PERSONAL(0.45f, 1.2f, 1.0f, ContentDensity.MEDIUM),
    SOCIAL(1.2f, 3.6f, 1.3f, ContentDensity.LOW),
    PUBLIC(3.6f, Float.MAX_VALUE, 1.8f, ContentDensity.MINIMAL);

    companion object {
        fun fromDistance(distance: Float): ProxemicZone {
            return entries.find { distance >= it.minDistance && distance < it.maxDistance }
                ?: PUBLIC
        }
    }
}

enum class ContentDensity {
    HIGH,    // Direct manipulation, intimate zone
    MEDIUM,  // Comfortable interaction, personal zone
    LOW,     // Standard viewing, social zone
    MINIMAL  // Overview mode, public zone
}
```

### Hand Tracking Implementation

```kotlin
/**
 * Hand tracking service using ARCore for Jetpack XR.
 * Detects pinch, point, fist, and open palm gestures.
 */
@HiltViewModel
class HandTrackingService @Inject constructor(
    private val session: Session
) : ViewModel() {

    private val _leftHand = MutableStateFlow<HandState?>(null)
    val leftHand: StateFlow<HandState?> = _leftHand

    private val _rightHand = MutableStateFlow<HandState?>(null)
    val rightHand: StateFlow<HandState?> = _rightHand

    private val _currentGesture = MutableStateFlow(Gesture.NONE)
    val currentGesture: StateFlow<Gesture> = _currentGesture

    enum class Gesture {
        NONE, PINCH, POINT, FIST, OPEN_PALM, THUMBS_UP,
        TWO_HAND_SPREAD, TWO_HAND_PINCH, EMERGENCY_STOP
    }

    suspend fun start() {
        // Configure session for hand tracking
        val config = session.config.copy(
            handTracking = Config.HandTrackingMode.BOTH
        )
        session.configure(config)

        // Get secondary hand (avoid system navigation conflicts)
        val handedness = Hand.getPrimaryHandSide(context.contentResolver)
        val secondaryHand = if (handedness == Hand.HandSide.LEFT)
            Hand.right(session) else Hand.left(session)

        // Start tracking loop at 90Hz
        while (isActive) {
            updateHandStates()
            detectGestures()
            delay(11) // ~90fps
        }
    }

    private fun detectPinch(handState: HandState): Boolean {
        val thumbTip = handState.handJoints[HandJointType.THUMB_TIP] ?: return false
        val indexTip = handState.handJoints[HandJointType.INDEX_TIP] ?: return false

        val thumbPos = session.scene.perceptionSpace.transformPoseTo(
            thumbTip, session.scene.activitySpace
        )
        val indexPos = session.scene.perceptionSpace.transformPoseTo(
            indexTip, session.scene.activitySpace
        )

        return Vector3.distance(thumbPos.translation, indexPos.translation) < 0.05f
    }
}
```

## Development Environment

### Requirements

- **Android Studio**: Narwhal 4 Feature Drop (2025.1.4) or newer
- **JDK**: 17+
- **Kotlin**: 2.0.0+
- **Android SDK**: API 34+ (Android 14)
- **Hardware**: Samsung Galaxy XR or Android XR Emulator

### Emulator Setup

```bash
# Install Android XR emulator via SDK Manager
# Create AVD with:
# - Device: google-xr headset
# - System Image: Android 14 arm64-v8a
# - Disk Size: 12GB

# Run with spatial features enabled
emulator -avd Android_XR_Headset -feature XR_Spatial_Mode
```

### Build Commands

```bash
# Build debug APK
cd apps/android-xr/kagami-xr
./gradlew assembleDebug

# Run tests
./gradlew test

# Install on device/emulator
./gradlew installDebug

# Build release
./gradlew assembleRelease
```

## Unique AndroidXR Features (Not in visionOS)

### 1. Gemini AI Integration

```kotlin
/**
 * Gemini-powered assistant for contextual smart home control.
 * This is unique to AndroidXR - visionOS only has basic Siri.
 */
class GeminiAssistantService(
    private val generativeModel: GenerativeModel
) {
    suspend fun processContextualQuery(
        query: String,
        visibleDevices: List<Device>,
        currentRoom: String?
    ): AssistantResponse {
        val prompt = buildPrompt(query, visibleDevices, currentRoom)
        val response = generativeModel.generateContent(prompt)
        return parseResponse(response)
    }

    // Gemini can see what the user sees and provide contextual assistance
    suspend fun analyzeVisualContext(
        cameraFrame: Bitmap,
        query: String
    ): AssistantResponse {
        val content = content {
            image(cameraFrame)
            text(query)
        }
        return generativeModel.generateContent(content)
    }
}
```

### 2. PC Connect / Cross-Device

```kotlin
/**
 * Stream PC/Mac applications alongside AndroidXR apps.
 * Similar to Vision Pro Mac integration but with Windows support.
 */
class PCConnectService {
    suspend fun connectToPC(pcAddress: String): Boolean
    suspend fun streamWindow(windowId: String): SurfaceTexture
}
```

### 3. Multi-Device Ecosystem

AndroidXR integrates with the broader Android ecosystem:
- Galaxy Watch for quick controls
- Galaxy phone for companion app
- Galaxy Tab for shared display
- Windows PC for productivity

## CI/CD Integration

### GitHub Actions Workflow

```yaml
# .github/workflows/android-xr.yml
name: Android XR CI

on:
  push:
    paths:
      - 'apps/android-xr/**'
  pull_request:
    paths:
      - 'apps/android-xr/**'

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up JDK 17
        uses: actions/setup-java@v4
        with:
          java-version: '17'
          distribution: 'temurin'

      - name: Setup Gradle
        uses: gradle/actions/setup-gradle@v3

      - name: Build
        working-directory: apps/android-xr/kagami-xr
        run: ./gradlew assembleDebug

      - name: Test
        working-directory: apps/android-xr/kagami-xr
        run: ./gradlew test
```

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| SDK still in Developer Preview | Medium | Focus on stable APIs, abstract platform specifics |
| Limited hardware availability | Medium | Develop primarily on emulator, test on device later |
| API changes between previews | High | Pin dependency versions, monitor release notes |
| Performance on mobile XR chipset | Medium | Implement ThermalManager, quality profiles |
| Gesture conflicts with system | Low | Use secondary hand, respect system gestures |

## Success Metrics

1. **Feature Parity**: All visionOS features available on AndroidXR
2. **Performance**: 72fps minimum on Galaxy XR
3. **Gesture Accuracy**: >95% recognition for primary gestures
4. **Latency**: <100ms for control actions
5. **AI Response Time**: <2s for Gemini queries

## References

- [Android XR Developer Portal](https://developer.android.com/develop/xr)
- [Jetpack XR SDK Getting Started](https://developer.android.com/develop/xr/jetpack-xr-sdk/getting-started)
- [ARCore for Jetpack XR - Hand Tracking](https://developer.android.com/develop/xr/jetpack-xr-sdk/arcore/hands)
- [Android XR Design Guidelines](https://developer.android.com/design/ui/xr)
- [Android XR Samples (GitHub)](https://github.com/android/xr-samples)

---

```
h(x) >= 0. Always.
craft(x) -> Infinity always.

The room becomes the interface.
Space becomes the canvas.
Kagami extends into three dimensions.
```
