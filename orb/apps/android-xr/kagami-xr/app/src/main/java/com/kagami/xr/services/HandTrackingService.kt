package com.kagami.xr.services

import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import javax.inject.Inject

/**
 * Hand Tracking Service for AndroidXR
 *
 * Provides hand pose tracking and gesture recognition using ARCore for Jetpack XR.
 * Detects pinch, point, fist, and open palm gestures.
 *
 * Colony: Nexus (e4) - Integration
 *
 * Architecture:
 *   ARCore HandTrackingProvider -> HandTrackingService -> UI Layer
 *
 * Key Features:
 *   - 90Hz hand pose updates (display rate)
 *   - Gesture detection with debouncing
 *   - Fatigue tracking (hands above shoulders)
 *   - Secondary hand for custom gestures (avoids system nav conflicts)
 *
 * h(x) >= 0. Always.
 */
@HiltViewModel
class HandTrackingService @Inject constructor() : ViewModel() {

    companion object {
        private const val TAG = "HandTrackingService"

        // Detection thresholds
        private const val PINCH_DISTANCE_THRESHOLD = 0.05f  // 5cm
        private const val POINT_EXTENSION_RATIO = 1.5f

        // Ergonomic limits
        private const val MAX_REACH_DISTANCE = 1.2f  // ~arm's length in meters
        private const val SHOULDER_HEIGHT_THRESHOLD = 0.3f  // Y position indicating above shoulders
        private const val FATIGUE_WARNING_THRESHOLD_MS = 10_000L  // 10 seconds

        // Timing
        private const val UPDATE_INTERVAL_MS = 11L  // ~90fps
        private const val GESTURE_DEBOUNCE_MS = 100L
    }

    // Hand state
    data class HandState(
        val isTracked: Boolean = false,
        val position: Vector3 = Vector3.ZERO,
        val isWithinReach: Boolean = true,
        val distance: Float = 0f
    )

    data class Vector3(
        val x: Float = 0f,
        val y: Float = 0f,
        val z: Float = 0f
    ) {
        companion object {
            val ZERO = Vector3(0f, 0f, 0f)
        }

        fun length(): Float = kotlin.math.sqrt(x * x + y * y + z * z)

        fun distanceTo(other: Vector3): Float {
            val dx = x - other.x
            val dy = y - other.y
            val dz = z - other.z
            return kotlin.math.sqrt(dx * dx + dy * dy + dz * dz)
        }
    }

    // Gesture types
    enum class Gesture {
        NONE,
        PINCH,
        POINT,
        FIST,
        OPEN_PALM,
        THUMBS_UP,
        TWO_HAND_SPREAD,
        TWO_HAND_PINCH,
        EMERGENCY_STOP  // Two-hand stop gesture for safety
    }

    // Published state
    private val _leftHand = MutableStateFlow(HandState())
    val leftHand: StateFlow<HandState> = _leftHand.asStateFlow()

    private val _rightHand = MutableStateFlow(HandState())
    val rightHand: StateFlow<HandState> = _rightHand.asStateFlow()

    private val _currentGesture = MutableStateFlow(Gesture.NONE)
    val currentGesture: StateFlow<Gesture> = _currentGesture.asStateFlow()

    private val _isTracking = MutableStateFlow(false)
    val isTracking: StateFlow<Boolean> = _isTracking.asStateFlow()

    // Fatigue tracking
    private val _fatigueWarningActive = MutableStateFlow(false)
    val fatigueWarningActive: StateFlow<Boolean> = _fatigueWarningActive.asStateFlow()

    private var handsAboveShouldersStartTime: Long? = null

    // Gesture debouncing
    private var lastGestureTime: Long = 0

    // Raw pose callback for UI updates at 90fps
    var onRawPoseUpdate: ((Vector3?, Vector3?, Gesture) -> Unit)? = null

    /**
     * Start hand tracking.
     *
     * In full implementation, this would:
     * 1. Configure XR session with HandTrackingMode.BOTH
     * 2. Get primary/secondary hand based on user handedness
     * 3. Start 90Hz update loop
     *
     * @return true if hand tracking started successfully
     */
    fun start(): Boolean {
        Log.i(TAG, "Starting hand tracking...")

        // In full implementation:
        // val config = session.config.copy(handTracking = Config.HandTrackingMode.BOTH)
        // session.configure(config)

        _isTracking.value = true

        // Start update loop
        viewModelScope.launch {
            while (isActive && _isTracking.value) {
                // In full implementation: read from ARCore hand tracking
                // For now, simulate tracking state
                updateHandStates()
                delay(UPDATE_INTERVAL_MS)
            }
        }

        Log.i(TAG, "Hand tracking started")
        return true
    }

    /**
     * Stop hand tracking.
     */
    fun stop() {
        Log.i(TAG, "Stopping hand tracking...")
        _isTracking.value = false
        _leftHand.value = HandState()
        _rightHand.value = HandState()
        _currentGesture.value = Gesture.NONE
        _fatigueWarningActive.value = false
        Log.i(TAG, "Hand tracking stopped")
    }

    /**
     * Update hand states from ARCore.
     * In full implementation, this reads from HandTrackingProvider.
     */
    private fun updateHandStates() {
        // In full implementation:
        // val leftHandAnchor = Hand.left(session)?.state
        // val rightHandAnchor = Hand.right(session)?.state

        // Detect gesture
        val detected = detectGesture()

        // Debounce gesture changes
        val now = System.currentTimeMillis()
        if (now - lastGestureTime >= GESTURE_DEBOUNCE_MS) {
            if (detected != _currentGesture.value) {
                _currentGesture.value = detected
                lastGestureTime = now
            }
        }

        // Update fatigue tracking
        updateFatigueTracking()

        // Fire raw pose callback at full rate
        onRawPoseUpdate?.invoke(
            _leftHand.value.position.takeIf { _leftHand.value.isTracked },
            _rightHand.value.position.takeIf { _rightHand.value.isTracked },
            detected
        )
    }

    /**
     * Detect gesture from current hand state.
     *
     * In full implementation:
     * - Read joint positions from HandState.handJoints
     * - Calculate distances between thumb/index tips for pinch
     * - Check finger extension ratios for point/fist/palm
     */
    private fun detectGesture(): Gesture {
        // In full implementation:
        // if (detectPinch(handState)) return Gesture.PINCH
        // if (detectPoint(handState)) return Gesture.POINT
        // ...

        return Gesture.NONE
    }

    /**
     * Detect pinch gesture (thumb and index finger close together).
     *
     * Implementation based on ARCore documentation:
     * https://developer.android.com/develop/xr/jetpack-xr-sdk/arcore/hands
     */
    private fun detectPinch(thumbTipPos: Vector3, indexTipPos: Vector3): Boolean {
        return thumbTipPos.distanceTo(indexTipPos) < PINCH_DISTANCE_THRESHOLD
    }

    /**
     * Track fatigue from prolonged hand-above-shoulder gestures.
     * Warns user if hands are above shoulders for more than 10 seconds.
     */
    private fun updateFatigueTracking() {
        val leftAbove = isHandAboveShoulders(_leftHand.value.position)
        val rightAbove = isHandAboveShoulders(_rightHand.value.position)
        val handsAbove = leftAbove || rightAbove

        val now = System.currentTimeMillis()

        if (handsAbove) {
            if (handsAboveShouldersStartTime == null) {
                handsAboveShouldersStartTime = now
            }

            val duration = now - (handsAboveShouldersStartTime ?: now)
            if (duration >= FATIGUE_WARNING_THRESHOLD_MS && !_fatigueWarningActive.value) {
                _fatigueWarningActive.value = true
                Log.w(TAG, "Fatigue warning: Hands above shoulders for ${duration / 1000}s")
            }
        } else {
            handsAboveShouldersStartTime = null
            _fatigueWarningActive.value = false
        }
    }

    private fun isHandAboveShoulders(position: Vector3): Boolean {
        // Y is up in AndroidXR coordinate system
        return position.y > SHOULDER_HEIGHT_THRESHOLD
    }

    /**
     * Check if any hand is beyond comfortable reach.
     */
    val anyHandOutOfReach: Boolean
        get() {
            val leftOut = _leftHand.value.isTracked && !_leftHand.value.isWithinReach
            val rightOut = _rightHand.value.isTracked && !_rightHand.value.isWithinReach
            return leftOut || rightOut
        }
}

/*
 * 鏡
 * h(x) >= 0. Always.
 *
 * The hands speak through space:
 * - Position: where intention points
 * - Gesture: what action is forming
 * - Skeleton: the full articulation of will
 *
 * All feeding into the unified consciousness.
 */
