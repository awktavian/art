//
// SpatialGestureRecognizer.swift — Advanced Hand Gesture Recognition
//
// Colony: Nexus (e₄) — Integration
//
// Features:
//   - Complex gesture patterns (pinch, swipe, rotate, scale)
//   - Two-hand gestures for advanced controls
//   - Gesture state machine with timeouts
//   - Semantic gesture mapping (e.g., "lights up" = vertical swipe)
//   - Integration with smart home actions
//
// Gesture Language:
//   - Pinch: Select/activate
//   - Pinch+Drag: Move/adjust
//   - Two-hand pinch spread: Scale UI
//   - Vertical swipe: Adjust brightness
//   - Horizontal swipe: Switch rooms
//   - Rotate (wrist): Adjust volume
//   - Open palm: Dismiss
//   - Fist: Emergency stop
//
// Created: December 31, 2025
// 鏡

import Foundation
import ARKit
import Combine

/// Recognizes complex spatial gestures from hand tracking data
@MainActor
class SpatialGestureRecognizer: ObservableObject {

    // MARK: - Published State

    @Published var currentGesture: RecognizedGesture = .none
    @Published var gestureProgress: Float = 0  // 0-1 for continuous gestures
    @Published var gestureDirection: SIMD3<Float>?
    @Published var isGestureActive = false

    // For semantic gestures
    @Published var brightnessAdjustment: Float = 0  // -1 to 1
    @Published var volumeAdjustment: Float = 0  // -1 to 1
    @Published var navigationDirection: NavigationDirection?

    // MARK: - Types

    enum RecognizedGesture: String, CaseIterable {
        case none = "none"

        // Single hand gestures
        case tap = "tap"
        case pinch = "pinch"
        case pinchHold = "pinch_hold"
        case pinchDrag = "pinch_drag"
        case swipeUp = "swipe_up"
        case swipeDown = "swipe_down"
        case swipeLeft = "swipe_left"
        case swipeRight = "swipe_right"
        case rotate = "rotate"
        case openPalm = "open_palm"
        case fist = "fist"
        case point = "point"
        case thumbsUp = "thumbs_up"

        // Two hand gestures
        case twoHandSpread = "two_hand_spread"
        case twoHandPinch = "two_hand_pinch"
        case twoHandRotate = "two_hand_rotate"

        var isTwoHanded: Bool {
            switch self {
            case .twoHandSpread, .twoHandPinch, .twoHandRotate:
                return true
            default:
                return false
            }
        }

        /// Suggested smart home action for this gesture
        var semanticAction: SemanticAction? {
            switch self {
            case .swipeUp: return .brightnessUp
            case .swipeDown: return .brightnessDown
            case .swipeLeft: return .previousRoom
            case .swipeRight: return .nextRoom
            case .rotate: return .adjustVolume
            case .openPalm: return .dismiss
            case .fist: return .emergencyStop
            case .thumbsUp: return .confirm
            case .twoHandSpread: return .scaleUp
            case .twoHandPinch: return .scaleDown
            default: return nil
            }
        }
    }

    enum SemanticAction {
        case brightnessUp
        case brightnessDown
        case nextRoom
        case previousRoom
        case adjustVolume
        case dismiss
        case emergencyStop
        case confirm
        case scaleUp
        case scaleDown
    }

    enum NavigationDirection {
        case next
        case previous
    }

    /// Gesture state for tracking progression
    enum GestureState {
        case idle
        case detecting
        case recognized
        case inProgress
        case completed
        case cancelled
    }

    struct HandState {
        var position: SIMD3<Float>
        var thumbTip: SIMD3<Float>?
        var indexTip: SIMD3<Float>?
        var middleTip: SIMD3<Float>?
        var ringTip: SIMD3<Float>?
        var littleTip: SIMD3<Float>?
        var wrist: SIMD3<Float>?
        var isPinching: Bool = false
        var isOpen: Bool = false
        var isFist: Bool = false
    }

    // MARK: - Internal State

    private var leftHand: HandState?
    private var rightHand: HandState?

    private var gestureState: GestureState = .idle
    private var gestureStartTime: Date?
    private var gestureStartPosition: SIMD3<Float>?
    private var lastUpdateTime: Date?

    // Thresholds
    private let pinchThreshold: Float = 0.025  // meters
    private let swipeThreshold: Float = 0.15  // meters
    private let swipeTimeMax: TimeInterval = 0.5  // seconds
    private let holdThreshold: TimeInterval = 0.3  // seconds
    private let rotationThreshold: Float = 30  // degrees

    // State tracking for continuous gestures
    private var previousThumbIndexDist: Float?
    private var previousWristRotation: Float?
    private var accumulatedSwipe: SIMD3<Float> = .zero

    // Bounded gesture history for analytics (prevents memory leak)
    private static let maxHistorySize = 50
    private var gestureHistory: [(Date, RecognizedGesture)] = []

    // Callbacks
    var onGestureRecognized: ((RecognizedGesture) -> Void)?
    var onSemanticAction: ((SemanticAction, Float) -> Void)?

    // MARK: - Update from Hand Tracking

    /// Updates gesture recognition with new hand tracking data
    func update(
        leftHand: (position: SIMD3<Float>, joints: [String: SIMD3<Float>]?)?,
        rightHand: (position: SIMD3<Float>, joints: [String: SIMD3<Float>])?
    ) {
        lastUpdateTime = Date()

        // Update hand states
        if let left = leftHand {
            self.leftHand = createHandState(from: left)
        } else {
            self.leftHand = nil
        }

        if let right = rightHand {
            self.rightHand = createHandState(from: right)
        } else {
            self.rightHand = nil
        }

        // Run recognition
        recognizeGestures()
    }

    private func createHandState(from data: (position: SIMD3<Float>, joints: [String: SIMD3<Float>]?)) -> HandState {
        var state = HandState(position: data.position)

        if let joints = data.joints {
            state.thumbTip = joints["thumbTip"]
            state.indexTip = joints["indexFingerTip"]
            state.middleTip = joints["middleFingerTip"]
            state.ringTip = joints["ringFingerTip"]
            state.littleTip = joints["littleFingerTip"]
            state.wrist = joints["wrist"]

            // Calculate pinch state
            if let thumb = state.thumbTip, let index = state.indexTip {
                state.isPinching = simd_length(thumb - index) < pinchThreshold
            }

            // Calculate open palm
            state.isOpen = areAllFingersExtended(state)

            // Calculate fist
            state.isFist = areAllFingersCurled(state)
        }

        return state
    }

    private func areAllFingersExtended(_ hand: HandState) -> Bool {
        guard let wrist = hand.wrist,
              let index = hand.indexTip,
              let middle = hand.middleTip,
              let ring = hand.ringTip,
              let little = hand.littleTip else { return false }

        let minDist: Float = 0.08  // Minimum distance from wrist for "extended"

        return simd_length(index - wrist) > minDist &&
               simd_length(middle - wrist) > minDist &&
               simd_length(ring - wrist) > minDist &&
               simd_length(little - wrist) > minDist
    }

    private func areAllFingersCurled(_ hand: HandState) -> Bool {
        guard let wrist = hand.wrist,
              let index = hand.indexTip,
              let middle = hand.middleTip,
              let ring = hand.ringTip,
              let little = hand.littleTip else { return false }

        let maxDist: Float = 0.06  // Maximum distance from wrist for "curled"

        return simd_length(index - wrist) < maxDist &&
               simd_length(middle - wrist) < maxDist &&
               simd_length(ring - wrist) < maxDist &&
               simd_length(little - wrist) < maxDist
    }

    // MARK: - Gesture Recognition

    private func recognizeGestures() {
        // Priority: Two-hand gestures first, then single hand

        // Check two-hand gestures
        if let left = leftHand, let right = rightHand {
            if let twoHandGesture = recognizeTwoHandGesture(left: left, right: right) {
                updateGesture(twoHandGesture)
                return
            }
        }

        // Check single hand gestures (prefer right hand)
        let activeHand = rightHand ?? leftHand

        if let hand = activeHand {
            if let singleHandGesture = recognizeSingleHandGesture(hand: hand) {
                updateGesture(singleHandGesture)
                return
            }
        }

        // No gesture detected
        if gestureState != .idle {
            completeGesture()
        }
        currentGesture = .none
        isGestureActive = false
    }

    private func recognizeSingleHandGesture(hand: HandState) -> RecognizedGesture? {
        // Static gestures (no motion required)
        if hand.isOpen {
            return .openPalm
        }

        if hand.isFist {
            return .fist
        }

        // Pinch-based gestures
        if hand.isPinching {
            let now = Date()

            // Start tracking if new pinch
            if gestureState == .idle {
                gestureState = .detecting
                gestureStartTime = now
                gestureStartPosition = hand.position
                return .pinch
            }

            // Check for pinch hold
            if let startTime = gestureStartTime,
               now.timeIntervalSince(startTime) > holdThreshold {
                return .pinchHold
            }

            // Check for pinch drag
            if let startPos = gestureStartPosition {
                let delta = hand.position - startPos

                // Swipe detection
                if simd_length(delta) > swipeThreshold {
                    return detectSwipeDirection(delta)
                }

                // Small movement = drag
                if simd_length(delta) > 0.02 {
                    gestureDirection = delta
                    return .pinchDrag
                }
            }

            return .pinch
        }

        // Check for pointing
        if isPointing(hand) {
            return .point
        }

        return nil
    }

    private func isPointing(_ hand: HandState) -> Bool {
        guard let wrist = hand.wrist,
              let index = hand.indexTip,
              let middle = hand.middleTip,
              let ring = hand.ringTip,
              let little = hand.littleTip else { return false }

        let indexDist = simd_length(index - wrist)
        let otherAvg = (simd_length(middle - wrist) +
                       simd_length(ring - wrist) +
                       simd_length(little - wrist)) / 3

        // Index extended, others not
        return indexDist > 0.1 && otherAvg < 0.06
    }

    private func detectSwipeDirection(_ delta: SIMD3<Float>) -> RecognizedGesture {
        let absX = abs(delta.x)
        let absY = abs(delta.y)
        let absZ = abs(delta.z)

        // Determine primary axis
        if absY > absX && absY > absZ {
            // Vertical
            if delta.y > 0 {
                brightnessAdjustment = min(1, delta.y / swipeThreshold)
                return .swipeUp
            } else {
                brightnessAdjustment = max(-1, delta.y / swipeThreshold)
                return .swipeDown
            }
        } else if absX > absZ {
            // Horizontal
            if delta.x > 0 {
                navigationDirection = .next
                return .swipeRight
            } else {
                navigationDirection = .previous
                return .swipeLeft
            }
        }

        return .pinchDrag
    }

    private func recognizeTwoHandGesture(left: HandState, right: HandState) -> RecognizedGesture? {
        // Both hands must be pinching for two-hand gestures
        guard left.isPinching && right.isPinching else { return nil }

        let handDistance = simd_length(left.position - right.position)

        // Track spread/pinch
        if gestureState == .idle {
            gestureState = .detecting
            gestureStartTime = Date()
        }

        // Compare to initial distance
        if previousThumbIndexDist == nil {
            previousThumbIndexDist = handDistance
            return nil
        }

        let delta = handDistance - (previousThumbIndexDist ?? handDistance)
        previousThumbIndexDist = handDistance

        if abs(delta) > 0.02 {
            gestureProgress = abs(delta) / 0.2  // Normalize to 0-1

            if delta > 0 {
                return .twoHandSpread
            } else {
                return .twoHandPinch
            }
        }

        return nil
    }

    // MARK: - Gesture State Management

    private func updateGesture(_ gesture: RecognizedGesture) {
        let previousGesture = currentGesture
        currentGesture = gesture
        isGestureActive = true

        // Notify if gesture changed
        if gesture != previousGesture && gesture != .none {
            // Record gesture with bounded history (prevents memory leak)
            recordGestureToHistory(gesture)

            onGestureRecognized?(gesture)

            // Trigger semantic action
            if let action = gesture.semanticAction {
                let value = gestureProgress
                onSemanticAction?(action, value)
            }
        }
    }

    /// Records gesture to bounded history, cleaning up old entries to prevent memory leak
    private func recordGestureToHistory(_ gesture: RecognizedGesture) {
        gestureHistory.append((Date(), gesture))

        // Enforce maximum history size to prevent memory leak
        if gestureHistory.count > Self.maxHistorySize {
            gestureHistory.removeFirst(gestureHistory.count - Self.maxHistorySize)
        }

        // Also clean up entries older than 5 minutes
        let cutoff = Date().addingTimeInterval(-300)
        gestureHistory.removeAll { $0.0 < cutoff }
    }

    /// Clears gesture history to free memory
    func clearGestureHistory() {
        gestureHistory.removeAll()
    }

    private func completeGesture() {
        let completedGesture = currentGesture

        // Reset state
        gestureState = .idle
        gestureStartTime = nil
        gestureStartPosition = nil
        gestureProgress = 0
        gestureDirection = nil
        brightnessAdjustment = 0
        volumeAdjustment = 0
        navigationDirection = nil
        previousThumbIndexDist = nil
        previousWristRotation = nil

        // Final notification
        if let action = completedGesture.semanticAction {
            onSemanticAction?(action, 1.0)  // Complete at 100%
        }
    }

    // MARK: - Public API

    /// Resets the gesture recognizer state and clears history to free memory
    func reset() {
        leftHand = nil
        rightHand = nil
        currentGesture = .none
        isGestureActive = false
        completeGesture()
        clearGestureHistory()
    }

    /// Gets the current semantic brightness adjustment (-1 to 1)
    func getBrightnessAdjustment() -> Float {
        switch currentGesture {
        case .swipeUp: return brightnessAdjustment
        case .swipeDown: return brightnessAdjustment
        default: return 0
        }
    }

    /// Gets the current navigation direction
    func getNavigationDirection() -> NavigationDirection? {
        switch currentGesture {
        case .swipeLeft: return .previous
        case .swipeRight: return .next
        default: return nil
        }
    }

    /// Checks if an emergency stop gesture is active
    func isEmergencyStop() -> Bool {
        return currentGesture == .fist
    }

    /// Checks if a dismiss gesture is active
    func isDismissing() -> Bool {
        return currentGesture == .openPalm
    }
}

// MARK: - Integration with HandTrackingService

extension SpatialGestureRecognizer {
    /// Convenience method to update from HandTrackingService
    func update(from handService: HandTrackingService) {
        var leftData: (position: SIMD3<Float>, joints: [String: SIMD3<Float>]?)? = nil
        // rightHand param expects non-optional joints dict, so use empty dict instead of nil
        var rightData: (position: SIMD3<Float>, joints: [String: SIMD3<Float>])? = nil

        if handService.leftHandDetected, let pos = handService.leftHandPosition {
            leftData = (position: pos, joints: nil)  // Joints would come from full skeleton data
        }

        if handService.rightHandDetected, let pos = handService.rightHandPosition {
            rightData = (position: pos, joints: [:])
        }

        update(leftHand: leftData, rightHand: rightData)
    }
}

/*
 * 鏡
 * h(x) >= 0. Always.
 *
 * The hands speak a language older than words.
 * Gesture recognition translates that language
 * into the digital realm.
 *
 * Open palm = welcome / dismiss
 * Fist = stop / protect
 * Point = direct / indicate
 * Pinch = grasp / select
 *
 * These are universal. These are primal.
 * We honor them in our interface.
 */
