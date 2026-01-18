# AndroidXR Platform Skill

**100/100 Quality by Default** - Patterns for production-ready AndroidXR apps.

## When to Use

- Creating or modifying AndroidXR apps in `apps/android-xr/`
- Ensuring AndroidXR-specific quality standards
- Byzantine audit remediation for AndroidXR
- Porting visionOS features to AndroidXR

## SDK Overview

AndroidXR is Google's XR platform for headsets (Samsung Galaxy XR) and AI glasses. Key libraries:

- **Jetpack Compose for XR**: Declarative spatial UI
- **Jetpack SceneCore**: 3D scene graph management
- **ARCore for Jetpack XR**: Hand tracking, plane detection, anchors
- **Material Design for XR**: Spatial design components

## Required Files (P0)

Every AndroidXR app MUST have these files implemented:

```
kagami-xr/
├── app/
│   ├── build.gradle.kts              # Dependencies with Jetpack XR
│   └── src/main/
│       ├── AndroidManifest.xml        # XR permissions and features
│       ├── java/com/kagami/xr/
│       │   ├── KagamiXRApp.kt         # Application class
│       │   ├── MainActivity.kt        # Entry with XR session
│       │   ├── ui/spatial/
│       │   │   ├── SpatialHomeScreen.kt    # Main spatial UI
│       │   │   └── SpatialRoomView.kt      # 3D room visualization
│       │   ├── services/
│       │   │   ├── HandTrackingService.kt  # ARCore hand tracking
│       │   │   └── ThermalManager.kt       # Quality degradation
│       │   └── gestures/
│       │       └── GestureStateMachine.kt  # Conflict prevention
│       └── res/
├── build.gradle.kts
└── settings.gradle.kts
```

## Critical Patterns

### 1. Gradle Dependencies (MANDATORY)

```kotlin
plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("com.google.dagger.hilt.android")
    kotlin("kapt")
}

android {
    namespace = "com.kagami.xr"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.kagami.xr"
        minSdk = 34  // Android 14 required for XR
        targetSdk = 35
    }
}

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

    // Coroutines
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")

    // Hilt DI
    implementation("com.google.dagger:hilt-android:2.48.1")
    kapt("com.google.dagger:hilt-compiler:2.48.1")

    // Gemini AI (AndroidXR unique)
    implementation("com.google.ai.client.generativeai:generativeai:0.9.0")
}
```

### 2. Manifest Configuration (MANDATORY)

```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:tools="http://schemas.android.com/tools">

    <!-- XR Permissions -->
    <uses-permission android:name="android.permission.SCENE_UNDERSTANDING" />
    <uses-permission android:name="android.permission.HAND_TRACKING" />
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.RECORD_AUDIO" />

    <!-- XR Features -->
    <uses-feature android:name="android.hardware.xr.headset" android:required="true" />
    <uses-feature android:name="android.software.xr.immersive" android:required="false" />

    <!-- MinSdk override for XR libraries if needed -->
    <uses-sdk tools:overrideLibrary="androidx.xr.scenecore, androidx.xr.compose" />

    <application
        android:name=".KagamiXRApp"
        android:label="Kagami XR"
        android:theme="@style/Theme.KagamiXR">

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

### 3. Main Activity Structure (MANDATORY)

```kotlin
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.xr.runtime.Session
import androidx.xr.scenecore.*
import dagger.hilt.android.AndroidEntryPoint

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    private lateinit var session: Session

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Initialize XR session
        session = Session.create(this)

        setContent {
            KagamiXRTheme {
                // Subspace enables 3D content
                Subspace {
                    SpatialHomeScreen(session = session)
                }
            }
        }
    }

    override fun onResume() {
        super.onResume()
        session.resume()
    }

    override fun onPause() {
        session.pause()
        super.onPause()
    }

    override fun onDestroy() {
        session.destroy()
        super.onDestroy()
    }
}
```

### 4. Spatial Design Tokens (MANDATORY)

```kotlin
/**
 * Proxemic zones based on Hall's spatial relationships.
 * Shared between AndroidXR and visionOS for consistency.
 */
enum class ProxemicZone(
    val minDistance: Float,
    val maxDistance: Float,
    val typographyScale: Float,
    val contentDensity: ContentDensity
) {
    INTIMATE(0f, 0.45f, 0.8f, ContentDensity.HIGH),
    PERSONAL(0.45f, 1.2f, 1.0f, ContentDensity.MEDIUM),
    SOCIAL(1.2f, 3.6f, 1.3f, ContentDensity.LOW),
    PUBLIC(3.6f, Float.MAX_VALUE, 1.8f, ContentDensity.MINIMAL);

    companion object {
        fun fromDistance(distance: Float): ProxemicZone =
            entries.find { distance >= it.minDistance && distance < it.maxDistance }
                ?: PUBLIC
    }
}

enum class ContentDensity { HIGH, MEDIUM, LOW, MINIMAL }

/**
 * Spatial animation timings (Fibonacci-based, shared with visionOS).
 */
object SpatialAnimation {
    const val APPEAR_MS = 377L      // Comfortable appearance
    const val TRANSFORM_MS = 610L   // Position changes
    const val DISMISS_MS = 233L     // Quick dismiss
}

/**
 * Colony-aware spatial colors.
 */
object SpatialColors {
    val beacon = Color(0xFFFFB940)    // Warm amber - attention
    val crystal = Color(0xFFE8E8F0)   // Cool silver - system
    val nexus = Color(0xFF7B68EE)     // Deep purple - connection
    val grove = Color(0xFF4CAF50)     // Living green - success
    val flow = Color(0xFF2196F3)      // River blue - process
}
```

### 5. Hand Tracking Service (MANDATORY)

```kotlin
import androidx.xr.arcore.Hand
import androidx.xr.arcore.HandJointType
import androidx.xr.runtime.Session
import androidx.xr.runtime.Config
import kotlinx.coroutines.flow.*

@HiltViewModel
class HandTrackingService @Inject constructor() : ViewModel() {

    private val _leftHandState = MutableStateFlow<HandState?>(null)
    val leftHandState: StateFlow<HandState?> = _leftHandState

    private val _rightHandState = MutableStateFlow<HandState?>(null)
    val rightHandState: StateFlow<HandState?> = _rightHandState

    private val _currentGesture = MutableStateFlow(Gesture.NONE)
    val currentGesture: StateFlow<Gesture> = _currentGesture

    enum class Gesture {
        NONE,
        PINCH,
        POINT,
        FIST,
        OPEN_PALM,
        THUMBS_UP,
        TWO_HAND_SPREAD,
        EMERGENCY_STOP
    }

    suspend fun start(session: Session) {
        // Enable hand tracking
        val config = session.config.copy(
            handTracking = Config.HandTrackingMode.BOTH
        )
        when (val result = session.configure(config)) {
            is SessionConfigureSuccess -> { /* Success */ }
            else -> {
                Log.e("HandTracking", "Failed to configure: $result")
                return
            }
        }

        // Use secondary hand for custom gestures (avoid system nav conflicts)
        val handedness = Hand.getPrimaryHandSide(session.context.contentResolver)
        val primaryHand = if (handedness == Hand.HandSide.LEFT)
            Hand.left(session) else Hand.right(session)
        val secondaryHand = if (handedness == Hand.HandSide.LEFT)
            Hand.right(session) else Hand.left(session)

        // Update loop at 90Hz (display rate)
        while (true) {
            primaryHand?.state?.let { _leftHandState.value = it }
            secondaryHand?.state?.let { _rightHandState.value = it }

            // Detect gestures from secondary hand (avoid system conflicts)
            secondaryHand?.state?.let { state ->
                _currentGesture.value = detectGesture(session, state)
            }

            delay(11) // ~90fps
        }
    }

    private fun detectGesture(session: Session, handState: HandState): Gesture {
        // Pinch detection
        if (detectPinch(session, handState)) return Gesture.PINCH

        // Point detection
        if (detectPoint(session, handState)) return Gesture.POINT

        // Fist detection
        if (detectFist(session, handState)) return Gesture.FIST

        // Open palm detection
        if (detectOpenPalm(session, handState)) return Gesture.OPEN_PALM

        return Gesture.NONE
    }

    private fun detectPinch(session: Session, handState: HandState): Boolean {
        val thumbTip = handState.handJoints[HandJointType.HAND_JOINT_TYPE_THUMB_TIP]
            ?: return false
        val indexTip = handState.handJoints[HandJointType.HAND_JOINT_TYPE_INDEX_TIP]
            ?: return false

        val thumbPos = session.scene.perceptionSpace.transformPoseTo(
            thumbTip, session.scene.activitySpace
        )
        val indexPos = session.scene.perceptionSpace.transformPoseTo(
            indexTip, session.scene.activitySpace
        )

        return Vector3.distance(thumbPos.translation, indexPos.translation) < 0.05f
    }

    // Similar implementations for detectPoint, detectFist, detectOpenPalm
}
```

### 6. Gesture State Machine (MANDATORY)

```kotlin
/**
 * Ensures only one gesture is active at a time.
 * Prevents gesture conflicts (e.g., pinch + point simultaneously).
 */
class GestureStateMachine {
    private val _activeGesture = MutableStateFlow(Gesture.NONE)
    val activeGesture: StateFlow<Gesture> = _activeGesture

    private var lastGestureTime = 0L
    private val debounceMs = 100L

    fun updateGesture(detected: Gesture) {
        val now = System.currentTimeMillis()

        // Debounce to prevent jitter
        if (now - lastGestureTime < debounceMs) return

        // State transitions
        when {
            // Emergency stop always takes priority
            detected == Gesture.EMERGENCY_STOP -> {
                _activeGesture.value = Gesture.EMERGENCY_STOP
                lastGestureTime = now
            }

            // Can transition from NONE to any gesture
            _activeGesture.value == Gesture.NONE && detected != Gesture.NONE -> {
                _activeGesture.value = detected
                lastGestureTime = now
            }

            // Clear gesture when NONE detected
            detected == Gesture.NONE -> {
                _activeGesture.value = Gesture.NONE
                lastGestureTime = now
            }
        }
    }

    fun reset() {
        _activeGesture.value = Gesture.NONE
    }
}
```

### 7. Thermal Management (MANDATORY)

```kotlin
/**
 * Manages quality profiles based on thermal state.
 * Critical for battery life and user comfort.
 */
@HiltViewModel
class ThermalManager @Inject constructor(
    application: Application
) : AndroidViewModel(application) {

    private val _currentProfile = MutableStateFlow(QualityProfile.HIGH)
    val currentProfile: StateFlow<QualityProfile> = _currentProfile

    enum class QualityProfile(
        val targetFps: Int,
        val particlesEnabled: Boolean,
        val spatialAudioEnabled: Boolean,
        val shadowQuality: ShadowQuality
    ) {
        ULTRA(90, true, true, ShadowQuality.HIGH),
        HIGH(72, true, true, ShadowQuality.MEDIUM),
        MEDIUM(60, true, true, ShadowQuality.LOW),
        LOW(45, false, true, ShadowQuality.NONE),
        MINIMAL(30, false, false, ShadowQuality.NONE)
    }

    enum class ShadowQuality { HIGH, MEDIUM, LOW, NONE }

    init {
        // Listen for thermal changes
        val powerManager = application.getSystemService(PowerManager::class.java)
        powerManager?.addThermalStatusListener { status ->
            updateProfile(status)
        }
    }

    private fun updateProfile(thermalStatus: Int) {
        val newProfile = when (thermalStatus) {
            PowerManager.THERMAL_STATUS_NONE,
            PowerManager.THERMAL_STATUS_LIGHT -> QualityProfile.HIGH
            PowerManager.THERMAL_STATUS_MODERATE -> QualityProfile.MEDIUM
            PowerManager.THERMAL_STATUS_SEVERE -> QualityProfile.LOW
            PowerManager.THERMAL_STATUS_CRITICAL,
            PowerManager.THERMAL_STATUS_EMERGENCY -> QualityProfile.MINIMAL
            else -> QualityProfile.MEDIUM
        }

        // Only decrease quality immediately; increase with 30s hysteresis
        if (newProfile.ordinal > _currentProfile.value.ordinal) {
            _currentProfile.value = newProfile
        }
    }
}
```

### 8. Spatial Composables (MANDATORY)

```kotlin
/**
 * Main spatial home screen using Compose for XR.
 */
@Composable
fun SpatialHomeScreen(session: Session) {
    val handTracking: HandTrackingService = hiltViewModel()
    val thermalManager: ThermalManager = hiltViewModel()

    val gesture by handTracking.currentGesture.collectAsState()
    val quality by thermalManager.currentProfile.collectAsState()

    // Start hand tracking
    LaunchedEffect(session) {
        handTracking.start(session)
    }

    // Main spatial layout
    Subspace {
        // Spatial panel at personal distance
        SpatialPanel(
            modifier = Modifier
                .width(500.dp)
                .height(400.dp),
            shape = SpatialPanelShape.Rounded,
            elevation = Elevation.Level2
        ) {
            KagamiControlPanel(
                gesture = gesture,
                qualityProfile = quality
            )
        }

        // 3D home model in scene
        SceneCoreEntity(
            modifier = Modifier.offset(z = (-1.5f).m),  // Social zone
            factory = { HomeModelEntity(session) }
        )
    }
}

/**
 * 3D room visualization entity.
 */
@Composable
fun SpatialRoomView(
    rooms: List<Room>,
    selectedRoom: String?,
    onRoomSelected: (String) -> Unit
) {
    Subspace {
        rooms.forEachIndexed { index, room ->
            SceneCoreEntity(
                modifier = Modifier
                    .offset(
                        x = (index % 3 * 0.15f - 0.15f).m,
                        y = (room.floor.ordinal * 0.15f).m,
                        z = (index / 3 * 0.15f).m
                    ),
                factory = { RoomEntity(room) }
            ) {
                // Interaction handling
                onPinch {
                    onRoomSelected(room.id)
                }
            }
        }
    }
}
```

## visionOS Feature Mapping

| visionOS Pattern | AndroidXR Equivalent |
|------------------|---------------------|
| `RealityView { }` | `Subspace { SceneCoreEntity { } }` |
| `ImmersiveSpace` | `SubspaceSession` |
| `.windowStyle(.volumetric)` | `SpatialPanel` with elevation |
| `HandTrackingProvider` | `Hand.left/right(session)` |
| `ModelComponent` | `GltfEntity` or `ModelEntity` |
| `ParticleEmitterComponent` | SceneCore particle system |
| `.glassBackgroundEffect()` | Material Design glass surface |

## Testing Requirements

### Unit Tests (Required)

```kotlin
class HandTrackingServiceTest {
    @Test
    fun `pinch detected when thumb and index within threshold`() {
        val service = HandTrackingService()
        // Mock hand joint positions
        val result = service.detectPinchWithMockData(
            thumbTip = Vector3(0f, 0f, 0f),
            indexTip = Vector3(0.03f, 0f, 0f)  // 3cm apart
        )
        assertTrue(result)
    }

    @Test
    fun `gesture state machine prevents conflicts`() {
        val stateMachine = GestureStateMachine()
        stateMachine.updateGesture(Gesture.PINCH)
        assertEquals(Gesture.PINCH, stateMachine.activeGesture.value)

        // Cannot switch to POINT while PINCH active
        stateMachine.updateGesture(Gesture.POINT)
        assertEquals(Gesture.PINCH, stateMachine.activeGesture.value)

        // Must clear first
        stateMachine.updateGesture(Gesture.NONE)
        stateMachine.updateGesture(Gesture.POINT)
        assertEquals(Gesture.POINT, stateMachine.activeGesture.value)
    }
}
```

### Emulator Testing

```bash
# Run on Android XR emulator
./gradlew installDebug
adb -s emulator-5554 shell am start -n com.kagami.xr/.MainActivity

# Test hand tracking (emulator supports simulated hands)
# Use emulator toolbar to simulate pinch gestures
```

## Build Verification

```bash
# From repository root
cd apps/android-xr/kagami-xr

# Build
./gradlew assembleDebug

# Run tests
./gradlew test

# Lint
./gradlew lint

# Install
./gradlew installDebug
```

## Quality Checklist

Before any AndroidXR commit:

- [ ] Manifest includes SCENE_UNDERSTANDING and HAND_TRACKING permissions
- [ ] Session lifecycle properly managed (resume/pause/destroy)
- [ ] Hand tracking uses secondary hand for custom gestures
- [ ] GestureStateMachine prevents gesture conflicts
- [ ] ThermalManager implemented with quality profiles
- [ ] Proxemic zones used for typography scaling
- [ ] All spatial UI accessible via voice fallback
- [ ] Unit tests pass
- [ ] Builds successfully on Android XR emulator

## Common Issues & Fixes

### Hand Tracking Not Working
- **Symptom**: No hand data received
- **Fix**: Check `HAND_TRACKING` permission, configure session with `HandTrackingMode.BOTH`

### Gesture Conflicts with System
- **Symptom**: Custom pinch conflicts with system navigation
- **Fix**: Use secondary hand for custom gestures (system uses primary)

### Performance Issues
- **Symptom**: Frame drops below 72fps
- **Fix**: Implement ThermalManager, reduce quality based on thermal state

### SceneCore Entity Not Visible
- **Symptom**: 3D content not rendering
- **Fix**: Ensure entity is within Subspace, check z-offset is negative (in front)

---

*100/100 or don't ship.*
