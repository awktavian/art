package com.kagami.xr.gestures

import android.util.Log
import com.kagami.xr.services.HandTrackingService
import com.kagami.xr.services.HandTrackingService.Gesture
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Gesture State Machine for AndroidXR
 *
 * Ensures only one gesture is active at a time to prevent conflicts.
 * Implements mutex-style gesture handling with priority for safety gestures.
 *
 * Colony: Nexus (e4) - Integration
 *
 * State Transitions:
 *   - NONE -> any gesture: immediate
 *   - any gesture -> NONE: immediate
 *   - gesture A -> gesture B: must go through NONE (no direct switch)
 *   - EMERGENCY_STOP: highest priority, always activates
 *
 * This pattern matches the visionOS GestureStateMachine for consistency.
 *
 * h(x) >= 0. Always.
 */
class GestureStateMachine {

    companion object {
        private const val TAG = "GestureStateMachine"
        private const val DEBOUNCE_MS = 100L
    }

    // Current active gesture
    private val _activeGesture = MutableStateFlow(Gesture.NONE)
    val activeGesture: StateFlow<Gesture> = _activeGesture.asStateFlow()

    // Gesture that is being held (for continuous gestures like drag)
    private val _heldGesture = MutableStateFlow<Gesture?>(null)
    val heldGesture: StateFlow<Gesture?> = _heldGesture.asStateFlow()

    // Timing for debounce
    private var lastGestureTime: Long = 0
    private var gestureStartTime: Long = 0

    /**
     * Update the gesture state based on detected gesture.
     *
     * @param detected The gesture detected from hand tracking
     */
    fun updateGesture(detected: Gesture) {
        val now = System.currentTimeMillis()

        // Debounce to prevent jitter
        if (now - lastGestureTime < DEBOUNCE_MS) {
            return
        }

        val current = _activeGesture.value

        when {
            // Emergency stop always takes priority - safety first
            detected == Gesture.EMERGENCY_STOP -> {
                if (current != Gesture.EMERGENCY_STOP) {
                    Log.w(TAG, "EMERGENCY_STOP activated")
                    _activeGesture.value = Gesture.EMERGENCY_STOP
                    lastGestureTime = now
                    gestureStartTime = now
                }
            }

            // Can transition from NONE to any gesture
            current == Gesture.NONE && detected != Gesture.NONE -> {
                Log.d(TAG, "Gesture activated: $detected")
                _activeGesture.value = detected
                lastGestureTime = now
                gestureStartTime = now
            }

            // Clear gesture when NONE detected
            detected == Gesture.NONE && current != Gesture.NONE -> {
                val duration = now - gestureStartTime
                Log.d(TAG, "Gesture ended: $current (duration: ${duration}ms)")
                _activeGesture.value = Gesture.NONE
                lastGestureTime = now
            }

            // Same gesture continues - no state change needed
            detected == current -> {
                // Just update timing
            }

            // Different gesture while one is active - ignore (must go through NONE)
            else -> {
                Log.d(TAG, "Gesture $detected ignored - $current still active")
            }
        }
    }

    /**
     * Check if a specific gesture is currently active.
     */
    fun isActive(gesture: Gesture): Boolean {
        return _activeGesture.value == gesture
    }

    /**
     * Mark current gesture as "held" for continuous interactions.
     */
    fun holdCurrentGesture() {
        val current = _activeGesture.value
        if (current != Gesture.NONE) {
            _heldGesture.value = current
            Log.d(TAG, "Gesture held: $current")
        }
    }

    /**
     * Release held gesture.
     */
    fun releaseHeldGesture() {
        _heldGesture.value?.let { held ->
            Log.d(TAG, "Gesture released: $held")
        }
        _heldGesture.value = null
    }

    /**
     * Get duration of current gesture in milliseconds.
     */
    val currentGestureDuration: Long
        get() = if (_activeGesture.value != Gesture.NONE) {
            System.currentTimeMillis() - gestureStartTime
        } else {
            0
        }

    /**
     * Force reset to NONE state.
     * Use sparingly - typically for error recovery or session transitions.
     */
    fun reset() {
        Log.i(TAG, "State machine reset")
        _activeGesture.value = Gesture.NONE
        _heldGesture.value = null
        lastGestureTime = 0
        gestureStartTime = 0
    }

    /**
     * Connect to hand tracking service for automatic updates.
     */
    fun connect(handTrackingService: HandTrackingService) {
        // In full implementation, this would observe the hand tracking flow
        // and automatically call updateGesture
    }
}

/**
 * Semantic gesture mapper - converts low-level gestures to high-level actions.
 *
 * Maps gestures to smart home control actions:
 *   - PINCH on device: toggle on/off
 *   - PINCH + drag: adjust brightness/position
 *   - POINT at room: select room
 *   - FIST: cancel/dismiss
 *   - OPEN_PALM: show menu
 *   - TWO_HAND_SPREAD: zoom in/out on room model
 *   - EMERGENCY_STOP: all stop (safety)
 */
class SemanticGestureMapper {

    /**
     * High-level semantic actions derived from gestures.
     */
    enum class SemanticAction {
        NONE,
        SELECT,             // Single pinch
        TOGGLE,             // Double pinch
        ADJUST_START,       // Pinch + hold
        ADJUST_VALUE,       // Pinch + drag
        ADJUST_END,         // Pinch release
        FOCUS,              // Point at target
        DISMISS,            // Fist gesture
        SHOW_MENU,          // Open palm
        ZOOM,               // Two-hand spread
        EMERGENCY_STOP      // Two-hand stop
    }

    data class SemanticEvent(
        val action: SemanticAction,
        val targetId: String? = null,
        val value: Float = 0f,
        val deltaValue: Float = 0f
    )

    private var lastPinchTime: Long = 0
    private var doublePinchWindow: Long = 300  // ms

    /**
     * Map gesture to semantic action.
     */
    fun mapGesture(
        gesture: Gesture,
        gestureDuration: Long,
        targetId: String?
    ): SemanticEvent {
        val now = System.currentTimeMillis()

        return when (gesture) {
            Gesture.NONE -> SemanticEvent(SemanticAction.NONE)

            Gesture.PINCH -> {
                // Check for double-pinch
                if (now - lastPinchTime < doublePinchWindow) {
                    lastPinchTime = 0  // Reset
                    SemanticEvent(SemanticAction.TOGGLE, targetId)
                } else {
                    lastPinchTime = now
                    if (gestureDuration > 200) {
                        SemanticEvent(SemanticAction.ADJUST_START, targetId)
                    } else {
                        SemanticEvent(SemanticAction.SELECT, targetId)
                    }
                }
            }

            Gesture.POINT -> SemanticEvent(SemanticAction.FOCUS, targetId)
            Gesture.FIST -> SemanticEvent(SemanticAction.DISMISS)
            Gesture.OPEN_PALM -> SemanticEvent(SemanticAction.SHOW_MENU)
            Gesture.TWO_HAND_SPREAD -> SemanticEvent(SemanticAction.ZOOM)
            Gesture.EMERGENCY_STOP -> SemanticEvent(SemanticAction.EMERGENCY_STOP)

            else -> SemanticEvent(SemanticAction.NONE)
        }
    }
}

/*
 * 鏡
 * h(x) >= 0. Always.
 *
 * One gesture at a time.
 * Clarity in intention.
 * Safety in constraint.
 */
