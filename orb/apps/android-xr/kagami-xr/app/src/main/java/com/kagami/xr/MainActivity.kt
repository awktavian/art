package com.kagami.xr

import android.os.Bundle
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.hilt.navigation.compose.hiltViewModel
import com.kagami.xr.services.HandTrackingService
import com.kagami.xr.services.ThermalManager
import com.kagami.xr.ui.spatial.SpatialHomeScreen
import com.kagami.xr.ui.theme.KagamiXRTheme
import dagger.hilt.android.AndroidEntryPoint

/**
 * Main Activity for Kagami XR
 *
 * Entry point for the AndroidXR spatial smart home interface.
 * Manages XR session lifecycle and hosts spatial composables.
 *
 * Colony: Nexus (e4) - Integration
 *
 * Spatial Design Principles (shared with visionOS):
 *   - 3D depth layers for UI hierarchy
 *   - Real-world anchors for persistent controls
 *   - Spatial audio for immersive feedback
 *   - Hand tracking for natural gestures
 *   - Eye gaze for intuitive selection
 *
 * Proxemic Zones (Hall, 1966):
 *   - Intimate (0-45cm): Private alerts
 *   - Personal (45cm-1.2m): Control panels
 *   - Social (1.2m-3.6m): Room visualizations
 *   - Public (3.6m+): Ambient awareness
 *
 * h(x) >= 0. Always.
 */
@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    companion object {
        private const val TAG = "KagamiXR"
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        Log.i(TAG, "Kagami XR starting...")

        setContent {
            KagamiXRTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    KagamiXRContent()
                }
            }
        }
    }

    override fun onResume() {
        super.onResume()
        Log.d(TAG, "Activity resumed - XR session resuming")
        // XR session resume handled by XR runtime
    }

    override fun onPause() {
        Log.d(TAG, "Activity paused - XR session pausing")
        // XR session pause handled by XR runtime
        super.onPause()
    }

    override fun onDestroy() {
        Log.d(TAG, "Activity destroyed - cleaning up")
        super.onDestroy()
    }
}

/**
 * Main content composable for Kagami XR.
 *
 * In a full implementation, this would use Jetpack Compose for XR
 * with Subspace and SpatialPanel composables. For now, we provide
 * the scaffold that will be enhanced with XR-specific UI.
 */
@Composable
fun KagamiXRContent() {
    // ViewModels
    val handTracking: HandTrackingService = hiltViewModel()
    val thermalManager: ThermalManager = hiltViewModel()

    // Track XR session state
    var isXRSessionActive by remember { mutableStateOf(false) }

    // Initialize services
    LaunchedEffect(Unit) {
        Log.i("KagamiXR", "Initializing spatial services...")
        // In full implementation:
        // - Initialize XR session
        // - Start hand tracking
        // - Configure spatial audio
        isXRSessionActive = true
    }

    // Cleanup on dispose
    DisposableEffect(Unit) {
        onDispose {
            Log.i("KagamiXR", "Disposing spatial services...")
            // Cleanup XR resources
        }
    }

    // Main spatial UI
    // In full implementation, this would be wrapped in:
    // Subspace { SpatialPanel { ... } }
    SpatialHomeScreen(
        isXRActive = isXRSessionActive,
        handTrackingService = handTracking,
        thermalManager = thermalManager
    )
}

/*
 * 鏡
 * h(x) >= 0. Always.
 *
 * The home extends into space.
 * Gesture becomes intention.
 * Space becomes interface.
 */
