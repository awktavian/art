package com.kagami.xr.input

import android.content.Context
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import javax.inject.Inject

/**
 * Neural Input Service for AndroidXR
 *
 * Provides integration with Meta Neural Band (sEMG wristband) for
 * gesture-based control of XR experiences.
 *
 * Colony: Nexus (e4) - Integration
 *
 * The Meta Neural Band captures electrical signals from muscle movements
 * in the wrist to enable low-effort gesture recognition without cameras.
 *
 * Supported Input Types:
 *   - Thumb microgestures (tap, swipe on index finger)
 *   - Pinch gestures (thumb to finger)
 *   - Wrist rotation (via IMU + EMG confirmation)
 *
 * Integration with Kagami:
 *   - Maps EMG gestures to semantic actions
 *   - Provides haptic feedback via wrist actuators
 *   - Works alongside hand tracking for hybrid input
 *
 * References:
 *   - Meta EMG Technology: https://www.meta.com/emerging-tech/emg-wearable-technology/
 *   - Microgestures SDK: https://developers.meta.com/horizon/documentation/unity/unity-microgestures/
 *
 * h(x) >= 0. Always.
 */
@HiltViewModel
class NeuralInputService @Inject constructor(
    @ApplicationContext private val context: Context
) : ViewModel() {

    companion object {
        private const val TAG = "NeuralInputService"

        // Gesture confidence threshold
        private const val CONFIDENCE_THRESHOLD = 0.7f

        // Debounce timing
        private const val GESTURE_DEBOUNCE_MS = 100L

        // Haptic timing (Fibonacci-based for natural feel)
        private const val HAPTIC_QUICK = 55L
        private const val HAPTIC_SHORT = 89L
        private const val HAPTIC_MEDIUM = 144L
        private const val HAPTIC_STANDARD = 233L
        private const val HAPTIC_LONG = 377L
    }

    // =========================================================================
    // EMG Gesture Types
    // =========================================================================

    /**
     * EMG-detectable gestures from Meta Neural Band.
     *
     * Based on Meta's published gesture vocabulary for sEMG wristbands.
     * These gestures are detected via muscle activation patterns.
     */
    enum class EMGGesture {
        NONE,

        // Thumb microgestures (on index finger surface)
        THUMB_TAP,              // Quick tap on index finger
        THUMB_DOUBLE_TAP,       // Double tap
        THUMB_SWIPE_LEFT,       // Swipe toward fingertip
        THUMB_SWIPE_RIGHT,      // Swipe away from fingertip
        THUMB_SWIPE_FORWARD,    // Swipe away from palm
        THUMB_SWIPE_BACKWARD,   // Swipe toward palm

        // Pinch gestures
        PINCH_INDEX,            // Thumb to index finger
        PINCH_MIDDLE,           // Thumb to middle finger
        PINCH_HOLD,             // Sustained pinch
        PINCH_RELEASE,          // Release from pinch

        // Finger gestures
        INDEX_TAP,              // Index finger tap
        MIDDLE_TAP,             // Middle finger tap
        DOUBLE_FINGER_TAP,      // Two fingers together

        // Wrist rotations
        WRIST_ROTATE_CW,        // Clockwise rotation
        WRIST_ROTATE_CCW        // Counter-clockwise rotation
    }

    /**
     * Semantic actions that EMG gestures map to.
     */
    enum class SemanticAction {
        NONE,
        PRIMARY_ACTION,         // Confirm, select
        SECONDARY_ACTION,       // Cancel, back
        TOGGLE,                 // Toggle on/off
        NEXT,                   // Next item
        PREVIOUS,               // Previous item
        SCROLL_UP,              // Scroll up
        SCROLL_DOWN,            // Scroll down
        VOLUME_UP,              // Increase volume
        VOLUME_DOWN,            // Decrease volume
        VOICE_INPUT,            // Activate voice input
        QUICK_ACTION_1,         // First quick action
        QUICK_ACTION_2,         // Second quick action
        SELECT,                 // Selection
        CONFIRM                 // Confirm action
    }

    // =========================================================================
    // State
    // =========================================================================

    /**
     * Connection state for Neural Band.
     */
    enum class ConnectionState {
        DISCONNECTED,
        SCANNING,
        CONNECTING,
        CONNECTED,
        CALIBRATING,
        READY,
        ERROR
    }

    /**
     * Calibration state for Neural Band.
     */
    enum class CalibrationState {
        NOT_CALIBRATED,
        CALIBRATING,
        CALIBRATED,
        NEEDS_RECALIBRATION
    }

    data class NeuralBandState(
        val connectionState: ConnectionState = ConnectionState.DISCONNECTED,
        val calibrationState: CalibrationState = CalibrationState.NOT_CALIBRATED,
        val deviceName: String = "",
        val firmwareVersion: String = "",
        val batteryLevel: Int = 0,
        val isReady: Boolean = false
    )

    data class GestureEvent(
        val gesture: EMGGesture,
        val confidence: Float,
        val timestamp: Long = System.currentTimeMillis(),
        val action: SemanticAction = SemanticAction.NONE
    )

    // Published state
    private val _bandState = MutableStateFlow(NeuralBandState())
    val bandState: StateFlow<NeuralBandState> = _bandState.asStateFlow()

    private val _currentGesture = MutableStateFlow(EMGGesture.NONE)
    val currentGesture: StateFlow<EMGGesture> = _currentGesture.asStateFlow()

    private val _lastGestureEvent = MutableStateFlow<GestureEvent?>(null)
    val lastGestureEvent: StateFlow<GestureEvent?> = _lastGestureEvent.asStateFlow()

    // Internal state
    private var lastGestureTime: Long = 0
    private var vibrator: Vibrator? = null

    // Gesture callback
    var onGestureDetected: ((GestureEvent) -> Unit)? = null
    var onSemanticAction: ((SemanticAction) -> Unit)? = null

    init {
        // Get vibrator for haptic feedback
        vibrator = if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.S) {
            val vibratorManager = context.getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as VibratorManager
            vibratorManager.defaultVibrator
        } else {
            @Suppress("DEPRECATION")
            context.getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
        }

        Log.i(TAG, "NeuralInputService initialized")
    }

    // =========================================================================
    // Connection Management
    // =========================================================================

    /**
     * Start scanning for Neural Band.
     *
     * In full implementation, this would:
     * 1. Use Bluetooth LE to scan for Meta Neural Band devices
     * 2. Connect via companion app WebSocket for data streaming
     * 3. Initialize gesture recognition pipeline
     */
    fun startScanning() {
        Log.i(TAG, "Starting Neural Band scan...")

        _bandState.value = _bandState.value.copy(
            connectionState = ConnectionState.SCANNING
        )

        viewModelScope.launch {
            // Simulate scanning (in real impl: BLE scan)
            delay(2000)

            // For now, simulate connection for development
            simulateConnection()
        }
    }

    /**
     * Connect to a specific Neural Band device.
     */
    fun connect(deviceAddress: String) {
        Log.i(TAG, "Connecting to Neural Band: $deviceAddress")

        _bandState.value = _bandState.value.copy(
            connectionState = ConnectionState.CONNECTING
        )

        viewModelScope.launch {
            // In real implementation:
            // - Establish BLE connection
            // - Open WebSocket to companion app
            // - Start EMG data streaming

            delay(1000)
            simulateConnection()
        }
    }

    /**
     * Disconnect from Neural Band.
     */
    fun disconnect() {
        Log.i(TAG, "Disconnecting from Neural Band")

        _bandState.value = _bandState.value.copy(
            connectionState = ConnectionState.DISCONNECTED,
            isReady = false
        )

        _currentGesture.value = EMGGesture.NONE
    }

    private fun simulateConnection() {
        _bandState.value = _bandState.value.copy(
            connectionState = ConnectionState.CONNECTED,
            deviceName = "Meta Neural Band",
            firmwareVersion = "1.2.0",
            batteryLevel = 85
        )

        // Start simulated gesture detection
        startGestureDetection()
    }

    // =========================================================================
    // Calibration
    // =========================================================================

    /**
     * Start calibration process.
     *
     * Calibration captures baseline EMG signals to improve gesture
     * recognition accuracy for the current user.
     */
    fun startCalibration() {
        Log.i(TAG, "Starting Neural Band calibration...")

        _bandState.value = _bandState.value.copy(
            connectionState = ConnectionState.CALIBRATING,
            calibrationState = CalibrationState.CALIBRATING
        )

        viewModelScope.launch {
            // Simulate calibration (in real impl: collect baseline samples)
            delay(5000)

            _bandState.value = _bandState.value.copy(
                connectionState = ConnectionState.READY,
                calibrationState = CalibrationState.CALIBRATED,
                isReady = true
            )

            Log.i(TAG, "Neural Band calibration complete")

            // Play success haptic
            playHapticPattern(HapticPattern.CONFIRM_SUCCESS)
        }
    }

    // =========================================================================
    // Gesture Detection
    // =========================================================================

    private fun startGestureDetection() {
        viewModelScope.launch {
            while (isActive && _bandState.value.connectionState == ConnectionState.CONNECTED) {
                // In real implementation:
                // - Receive EMG data from WebSocket
                // - Process through ML model
                // - Emit recognized gestures

                delay(100)  // Polling interval
            }
        }
    }

    /**
     * Process incoming EMG gesture from Neural Band.
     *
     * Called by WebSocket receiver when gesture is detected.
     */
    fun processGesture(gesture: EMGGesture, confidence: Float) {
        val now = System.currentTimeMillis()

        // Debounce
        if (now - lastGestureTime < GESTURE_DEBOUNCE_MS) {
            return
        }

        // Filter by confidence
        if (confidence < CONFIDENCE_THRESHOLD) {
            return
        }

        lastGestureTime = now

        // Map to semantic action
        val action = mapToSemanticAction(gesture)

        // Update state
        _currentGesture.value = gesture

        val event = GestureEvent(
            gesture = gesture,
            confidence = confidence,
            timestamp = now,
            action = action
        )
        _lastGestureEvent.value = event

        Log.d(TAG, "EMG Gesture: $gesture (confidence: ${"%.2f".format(confidence)}) -> $action")

        // Fire callbacks
        onGestureDetected?.invoke(event)
        if (action != SemanticAction.NONE) {
            onSemanticAction?.invoke(action)
        }

        // Play haptic feedback for confirmed gestures
        playGestureHaptic(gesture)
    }

    /**
     * Clear current gesture (when released).
     */
    fun clearGesture() {
        if (_currentGesture.value != EMGGesture.NONE) {
            Log.d(TAG, "Gesture cleared: ${_currentGesture.value}")
            _currentGesture.value = EMGGesture.NONE
        }
    }

    // =========================================================================
    // Gesture Mapping
    // =========================================================================

    /**
     * Map EMG gesture to Kagami semantic action.
     *
     * Standard mappings based on natural gesture intent:
     *   - THUMB_TAP -> PRIMARY_ACTION (select/confirm)
     *   - THUMB_DOUBLE_TAP -> TOGGLE
     *   - THUMB_SWIPE_LEFT -> PREVIOUS
     *   - THUMB_SWIPE_RIGHT -> NEXT
     *   - PINCH_INDEX -> SELECT
     *   - PINCH_HOLD -> VOICE_INPUT
     *   - WRIST_ROTATE_CW -> VOLUME_UP
     *   - WRIST_ROTATE_CCW -> VOLUME_DOWN
     */
    private fun mapToSemanticAction(gesture: EMGGesture): SemanticAction {
        return when (gesture) {
            EMGGesture.NONE -> SemanticAction.NONE

            // Thumb microgestures
            EMGGesture.THUMB_TAP -> SemanticAction.PRIMARY_ACTION
            EMGGesture.THUMB_DOUBLE_TAP -> SemanticAction.TOGGLE
            EMGGesture.THUMB_SWIPE_LEFT -> SemanticAction.PREVIOUS
            EMGGesture.THUMB_SWIPE_RIGHT -> SemanticAction.NEXT
            EMGGesture.THUMB_SWIPE_FORWARD -> SemanticAction.SCROLL_UP
            EMGGesture.THUMB_SWIPE_BACKWARD -> SemanticAction.SCROLL_DOWN

            // Pinch gestures
            EMGGesture.PINCH_INDEX -> SemanticAction.SELECT
            EMGGesture.PINCH_MIDDLE -> SemanticAction.SECONDARY_ACTION
            EMGGesture.PINCH_HOLD -> SemanticAction.VOICE_INPUT
            EMGGesture.PINCH_RELEASE -> SemanticAction.CONFIRM

            // Finger taps
            EMGGesture.INDEX_TAP -> SemanticAction.QUICK_ACTION_1
            EMGGesture.MIDDLE_TAP -> SemanticAction.QUICK_ACTION_2
            EMGGesture.DOUBLE_FINGER_TAP -> SemanticAction.TOGGLE

            // Wrist rotation
            EMGGesture.WRIST_ROTATE_CW -> SemanticAction.VOLUME_UP
            EMGGesture.WRIST_ROTATE_CCW -> SemanticAction.VOLUME_DOWN
        }
    }

    // =========================================================================
    // Haptic Feedback
    // =========================================================================

    /**
     * Haptic patterns for different feedback types.
     */
    enum class HapticPattern {
        // Confirmation
        CONFIRM_TAP,
        CONFIRM_DOUBLE,
        CONFIRM_SUCCESS,

        // Alerts
        ALERT_NOTIFICATION,
        ALERT_WARNING,
        ALERT_ERROR,

        // Safety (h(x) >= 0)
        SAFETY_CRITICAL,
        SAFETY_STOP,

        // Navigation
        NAV_SELECT,
        NAV_BACK,

        // Scene activation
        SCENE_ACTIVATED,

        // Interaction
        SLIDER_TICK
    }

    /**
     * Play haptic feedback for gesture.
     */
    private fun playGestureHaptic(gesture: EMGGesture) {
        val pattern = when (gesture) {
            EMGGesture.THUMB_TAP -> HapticPattern.CONFIRM_TAP
            EMGGesture.THUMB_DOUBLE_TAP -> HapticPattern.CONFIRM_DOUBLE
            EMGGesture.PINCH_INDEX -> HapticPattern.NAV_SELECT
            EMGGesture.PINCH_RELEASE -> HapticPattern.CONFIRM_SUCCESS
            else -> null
        }

        pattern?.let { playHapticPattern(it) }
    }

    /**
     * Play a haptic pattern.
     *
     * Uses Fibonacci-based timing for natural feel:
     * 55ms, 89ms, 144ms, 233ms, 377ms
     */
    fun playHapticPattern(pattern: HapticPattern) {
        val vibrator = this.vibrator ?: return

        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
            val effect = when (pattern) {
                HapticPattern.CONFIRM_TAP -> {
                    VibrationEffect.createOneShot(HAPTIC_QUICK, 128)
                }

                HapticPattern.CONFIRM_DOUBLE -> {
                    VibrationEffect.createWaveform(
                        longArrayOf(0, HAPTIC_QUICK, HAPTIC_SHORT, HAPTIC_QUICK),
                        intArrayOf(0, 128, 0, 128),
                        -1
                    )
                }

                HapticPattern.CONFIRM_SUCCESS -> {
                    VibrationEffect.createWaveform(
                        longArrayOf(0, HAPTIC_SHORT, 30, HAPTIC_MEDIUM),
                        intArrayOf(0, 80, 0, 128),
                        -1
                    )
                }

                HapticPattern.ALERT_NOTIFICATION -> {
                    VibrationEffect.createWaveform(
                        longArrayOf(0, HAPTIC_SHORT, HAPTIC_MEDIUM, HAPTIC_SHORT),
                        intArrayOf(0, 80, 0, 80),
                        -1
                    )
                }

                HapticPattern.ALERT_WARNING -> {
                    VibrationEffect.createWaveform(
                        longArrayOf(0, HAPTIC_STANDARD, HAPTIC_SHORT, HAPTIC_STANDARD, HAPTIC_SHORT, HAPTIC_STANDARD),
                        intArrayOf(0, 180, 0, 180, 0, 180),
                        -1
                    )
                }

                HapticPattern.ALERT_ERROR -> {
                    VibrationEffect.createWaveform(
                        longArrayOf(0, HAPTIC_LONG, HAPTIC_MEDIUM, HAPTIC_LONG),
                        intArrayOf(0, 200, 0, 200),
                        -1
                    )
                }

                HapticPattern.SAFETY_CRITICAL -> {
                    // Maximum intensity for safety - h(x) >= 0
                    VibrationEffect.createWaveform(
                        longArrayOf(0, 500, HAPTIC_STANDARD, 500),
                        intArrayOf(0, 255, 0, 255),
                        -1
                    )
                }

                HapticPattern.SAFETY_STOP -> {
                    VibrationEffect.createOneShot(610, 255)
                }

                HapticPattern.NAV_SELECT -> {
                    VibrationEffect.createOneShot(HAPTIC_QUICK, 150)
                }

                HapticPattern.NAV_BACK -> {
                    VibrationEffect.createWaveform(
                        longArrayOf(0, HAPTIC_QUICK, 30, HAPTIC_QUICK),
                        intArrayOf(0, 80, 0, 80),
                        -1
                    )
                }

                HapticPattern.SCENE_ACTIVATED -> {
                    VibrationEffect.createWaveform(
                        longArrayOf(0, HAPTIC_SHORT, 30, HAPTIC_SHORT, 30, HAPTIC_MEDIUM),
                        intArrayOf(0, 100, 0, 120, 0, 150),
                        -1
                    )
                }

                HapticPattern.SLIDER_TICK -> {
                    VibrationEffect.createOneShot(30, 60)
                }
            }

            vibrator.vibrate(effect)
        } else {
            @Suppress("DEPRECATION")
            vibrator.vibrate(HAPTIC_SHORT)
        }
    }

    /**
     * Play safety-critical haptic feedback.
     *
     * Safety haptics always play regardless of user settings.
     * h(x) >= 0. Always.
     */
    fun playSafetyHaptic(pattern: HapticPattern = HapticPattern.SAFETY_CRITICAL) {
        Log.w(TAG, "Safety haptic: $pattern")
        playHapticPattern(pattern)
    }

    /**
     * Play scene activation haptic.
     *
     * @param colonyName Name of the Colony/scene being activated
     */
    fun playSceneActivationHaptic(colonyName: String) {
        Log.d(TAG, "Scene activation haptic: $colonyName")
        playHapticPattern(HapticPattern.SCENE_ACTIVATED)
    }

    // =========================================================================
    // Device State Changes
    // =========================================================================

    /**
     * Play haptic for device state change.
     *
     * @param isOn Whether device is turning on (true) or off (false)
     */
    fun playDeviceStateHaptic(isOn: Boolean) {
        val pattern = if (isOn) HapticPattern.CONFIRM_SUCCESS else HapticPattern.NAV_BACK
        playHapticPattern(pattern)
    }

    // =========================================================================
    // Integration with GestureStateMachine
    // =========================================================================

    /**
     * Check if Neural Band gesture should take priority over hand tracking.
     *
     * Neural Band input is preferred when:
     * - Band is connected and ready
     * - Hands are not in camera view (no hand tracking)
     * - User preference is set to neural input
     */
    fun shouldPrioritizeNeuralInput(): Boolean {
        return _bandState.value.isReady
    }

    // =========================================================================
    // Cleanup
    // =========================================================================

    override fun onCleared() {
        super.onCleared()
        disconnect()
        Log.i(TAG, "NeuralInputService cleared")
    }
}

/*
 * 鏡
 * h(x) >= 0. Always.
 *
 * Neural input speaks before motion forms:
 * - Muscle signals precede visible gesture
 * - Intent detected at the source
 * - Low-effort, high-precision control
 *
 * The wrist whispers what the hand would shout.
 */
