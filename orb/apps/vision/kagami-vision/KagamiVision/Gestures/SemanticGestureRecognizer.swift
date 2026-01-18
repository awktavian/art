//
// SemanticGestureRecognizer.swift -- Semantic Hand Gesture Recognition
//
// Kagami Vision -- Contextual gesture recognition for home control
//
// Colony: Spark (e1) -- Exploration
//
// Per KAGAMI_REDESIGN_PLAN.md: Implement hand tracking gesture recognition
//
// Features:
// - Context-aware gesture interpretation
// - Home control semantic actions
// - Brightness/volume dial gestures
// - Room navigation gestures
// - Emergency stop gesture
// - Gesture hints and preview
// - Accessibility alternative inputs
//
// h(x) >= 0. Always.
//

import Foundation
import SwiftUI
import Combine
import ARKit

/// Recognizes semantic gestures from hand tracking data for home control
@MainActor
class SemanticGestureRecognizer: ObservableObject {

    // MARK: - Published State

    @Published var currentAction: SemanticAction = .none
    @Published var actionProgress: Float = 0
    @Published var gesturePreview: GesturePreview?
    @Published var isGestureInProgress = false

    // MARK: - Semantic Actions

    /// High-level actions mapped from hand gestures
    enum SemanticAction: String, CaseIterable {
        case none = "none"

        // Lighting control
        case brightnessUp = "brightness_up"
        case brightnessDown = "brightness_down"
        case lightsOff = "lights_off"
        case lightsOn = "lights_on"
        case dimLights = "dim_lights"

        // Room navigation
        case nextRoom = "next_room"
        case previousRoom = "previous_room"
        case selectRoom = "select_room"

        // Scene control
        case activateScene = "activate_scene"

        // Safety
        case emergencyStop = "emergency_stop"

        // UI Control
        case dismiss = "dismiss"
        case confirm = "confirm"
        case scroll = "scroll"
        case zoom = "zoom"

        var icon: String {
            switch self {
            case .none: return "hand.raised"
            case .brightnessUp: return "sun.max.fill"
            case .brightnessDown: return "sun.min.fill"
            case .lightsOff: return "lightbulb.slash.fill"
            case .lightsOn: return "lightbulb.fill"
            case .dimLights: return "lightbulb.min.fill"
            case .nextRoom: return "arrow.right"
            case .previousRoom: return "arrow.left"
            case .selectRoom: return "checkmark.circle"
            case .activateScene: return "theatermasks.fill"
            case .emergencyStop: return "exclamationmark.octagon.fill"
            case .dismiss: return "xmark"
            case .confirm: return "checkmark"
            case .scroll: return "arrow.up.arrow.down"
            case .zoom: return "plus.magnifyingglass"
            }
        }

        var label: String {
            switch self {
            case .none: return "No gesture"
            case .brightnessUp: return "Increase brightness"
            case .brightnessDown: return "Decrease brightness"
            case .lightsOff: return "Turn lights off"
            case .lightsOn: return "Turn lights on"
            case .dimLights: return "Dim lights"
            case .nextRoom: return "Next room"
            case .previousRoom: return "Previous room"
            case .selectRoom: return "Select room"
            case .activateScene: return "Activate scene"
            case .emergencyStop: return "Emergency stop"
            case .dismiss: return "Dismiss"
            case .confirm: return "Confirm"
            case .scroll: return "Scroll"
            case .zoom: return "Zoom"
            }
        }
    }

    /// Preview of what gesture is being formed
    struct GesturePreview {
        let potentialAction: SemanticAction
        let confidence: Float
        let hint: String
    }

    // MARK: - Gesture Patterns

    /// Patterns that map raw gestures + context to semantic actions
    struct GesturePattern {
        let baseGesture: HandTrackingService.HandGesture
        let modifier: GestureModifier?
        let movement: MovementType?
        let action: SemanticAction
        let requiredDuration: TimeInterval?

        enum GestureModifier {
            case twoHanded
            case sustained(TimeInterval)  // Hold for N seconds
            case repeated(Int)  // Repeat N times
        }

        enum MovementType {
            case rotateClockwise
            case rotateCounterClockwise
            case swipeLeft
            case swipeRight
            case swipeUp
            case swipeDown
            case pullToward
            case pushAway
            case pinchAndDrag
        }
    }

    // MARK: - Internal State

    private var handTracking: HandTrackingService?
    private var cancellables = Set<AnyCancellable>()

    // Gesture timing
    private var gestureStartTime: Date?
    private var lastGesture: HandTrackingService.HandGesture = .none
    private var gestureHoldDuration: TimeInterval = 0

    // Movement tracking
    private var previousLeftPosition: SIMD3<Float>?
    private var previousRightPosition: SIMD3<Float>?
    private var movementVelocity: SIMD3<Float> = .zero
    private var rotationAccumulator: Float = 0

    // Two-hand tracking
    private var twoHandGestureActive = false
    private var initialHandDistance: Float?

    // Callback for semantic action
    var onSemanticAction: ((SemanticAction, Float) -> Void)?

    // MARK: - Gesture Patterns Library

    private let gesturePatterns: [GesturePattern] = [
        // Brightness control - pinch + rotate
        GesturePattern(
            baseGesture: .pinch,
            modifier: nil,
            movement: .rotateClockwise,
            action: .brightnessUp,
            requiredDuration: nil
        ),
        GesturePattern(
            baseGesture: .pinch,
            modifier: nil,
            movement: .rotateCounterClockwise,
            action: .brightnessDown,
            requiredDuration: nil
        ),

        // Lights off - open palm pushed away
        GesturePattern(
            baseGesture: .openPalm,
            modifier: nil,
            movement: .pushAway,
            action: .lightsOff,
            requiredDuration: nil
        ),

        // Lights on - open palm pulled toward
        GesturePattern(
            baseGesture: .openPalm,
            modifier: nil,
            movement: .pullToward,
            action: .lightsOn,
            requiredDuration: nil
        ),

        // Room navigation - point + swipe
        GesturePattern(
            baseGesture: .point,
            modifier: nil,
            movement: .swipeRight,
            action: .nextRoom,
            requiredDuration: nil
        ),
        GesturePattern(
            baseGesture: .point,
            modifier: nil,
            movement: .swipeLeft,
            action: .previousRoom,
            requiredDuration: nil
        ),

        // Confirm - thumbs up
        GesturePattern(
            baseGesture: .thumbsUp,
            modifier: nil,
            movement: nil,
            action: .confirm,
            requiredDuration: 0.5
        ),

        // Emergency stop - two fists held for 2 seconds
        GesturePattern(
            baseGesture: .fist,
            modifier: .twoHanded,
            movement: nil,
            action: .emergencyStop,
            requiredDuration: 2.0
        ),

        // Dismiss - swipe away with open palm
        GesturePattern(
            baseGesture: .openPalm,
            modifier: nil,
            movement: .swipeRight,
            action: .dismiss,
            requiredDuration: nil
        ),

        // Zoom - pinch with two hands (spread apart)
        GesturePattern(
            baseGesture: .pinch,
            modifier: .twoHanded,
            movement: nil,
            action: .zoom,
            requiredDuration: nil
        )
    ]

    // MARK: - Init

    init() {}

    // MARK: - Connection

    /// Connect to hand tracking service
    func connect(to handTracking: HandTrackingService) {
        self.handTracking = handTracking

        // Subscribe to gesture changes
        handTracking.$currentGesture
            .receive(on: DispatchQueue.main)
            .sink { [weak self] gesture in
                self?.handleGestureChange(gesture)
            }
            .store(in: &cancellables)

        // Subscribe to position changes for movement detection
        Publishers.CombineLatest(
            handTracking.$leftHandPosition,
            handTracking.$rightHandPosition
        )
        .receive(on: DispatchQueue.main)
        .sink { [weak self] leftPos, rightPos in
            self?.handlePositionUpdate(left: leftPos, right: rightPos)
        }
        .store(in: &cancellables)

        // Subscribe to detection state for two-hand tracking
        Publishers.CombineLatest(
            handTracking.$leftHandDetected,
            handTracking.$rightHandDetected
        )
        .receive(on: DispatchQueue.main)
        .sink { [weak self] leftDetected, rightDetected in
            self?.twoHandGestureActive = leftDetected && rightDetected
        }
        .store(in: &cancellables)
    }

    // MARK: - Gesture Processing

    private func handleGestureChange(_ gesture: HandTrackingService.HandGesture) {
        // Track gesture timing
        if gesture != lastGesture {
            gestureStartTime = gesture != .none ? Date() : nil
            gestureHoldDuration = 0
            lastGesture = gesture
            rotationAccumulator = 0
        }

        // Update hold duration
        if let startTime = gestureStartTime, gesture != .none {
            gestureHoldDuration = Date().timeIntervalSince(startTime)
        }

        // Generate preview
        updateGesturePreview(gesture)

        // Check for completed gestures
        checkForCompletedGesture(gesture)
    }

    private func handlePositionUpdate(left: SIMD3<Float>?, right: SIMD3<Float>?) {
        // Calculate movement
        if let currentLeft = left, let prevLeft = previousLeftPosition {
            let delta = currentLeft - prevLeft
            movementVelocity = delta
            detectMovement(delta)
        }

        if let currentRight = right, let prevRight = previousRightPosition {
            let delta = currentRight - prevRight
            if movementVelocity == .zero {
                movementVelocity = delta
            } else {
                movementVelocity = (movementVelocity + delta) / 2
            }
            detectMovement(delta)
        }

        // Two-hand distance tracking for zoom gesture
        if let l = left, let r = right, twoHandGestureActive {
            let currentDistance = simd_length(l - r)
            if let initial = initialHandDistance {
                let ratio = currentDistance / initial
                if ratio > 1.3 {
                    // Spread apart - zoom in
                    triggerAction(.zoom, value: ratio)
                } else if ratio < 0.7 {
                    // Pinch together - zoom out
                    triggerAction(.zoom, value: ratio)
                }
            } else {
                initialHandDistance = currentDistance
            }
        } else {
            initialHandDistance = nil
        }

        previousLeftPosition = left
        previousRightPosition = right
    }

    private func detectMovement(_ delta: SIMD3<Float>) {
        let threshold: Float = 0.02  // 2cm movement threshold

        // Detect directional movements
        if delta.x > threshold {
            currentMovement = .swipeRight
        } else if delta.x < -threshold {
            currentMovement = .swipeLeft
        } else if delta.y > threshold {
            currentMovement = .swipeUp
        } else if delta.y < -threshold {
            currentMovement = .swipeDown
        } else if delta.z > threshold {
            currentMovement = .pullToward
        } else if delta.z < -threshold {
            currentMovement = .pushAway
        }

        // Detect rotation (for dial gestures)
        if let left = previousLeftPosition, let right = handTracking?.rightHandPosition {
            let angle = atan2(left.y - right.y, left.x - right.x)
            if let lastAngle = lastRotationAngle {
                var angleDelta = angle - lastAngle
                // Normalize
                if angleDelta > .pi { angleDelta -= 2 * .pi }
                if angleDelta < -.pi { angleDelta += 2 * .pi }

                rotationAccumulator += angleDelta

                if rotationAccumulator > 0.3 {
                    currentMovement = .rotateClockwise
                    rotationAccumulator = 0
                } else if rotationAccumulator < -0.3 {
                    currentMovement = .rotateCounterClockwise
                    rotationAccumulator = 0
                }
            }
            lastRotationAngle = angle
        }
    }

    private var currentMovement: GesturePattern.MovementType?
    private var lastRotationAngle: Float?

    // MARK: - Gesture Recognition

    private func updateGesturePreview(_ gesture: HandTrackingService.HandGesture) {
        // Find potential actions based on current gesture
        let matchingPatterns = gesturePatterns.filter { pattern in
            pattern.baseGesture == gesture &&
            (pattern.modifier != .twoHanded || twoHandGestureActive)
        }

        if let firstMatch = matchingPatterns.first {
            var hint = "Hold to \(firstMatch.action.label.lowercased())"

            if let requiredDuration = firstMatch.requiredDuration {
                let remaining = max(0, requiredDuration - gestureHoldDuration)
                if remaining > 0 {
                    hint = "Hold for \(String(format: "%.1f", remaining)) more seconds"
                }
            }

            if let movement = firstMatch.movement {
                hint = movementHint(for: movement)
            }

            gesturePreview = GesturePreview(
                potentialAction: firstMatch.action,
                confidence: min(1.0, Float(gestureHoldDuration / (firstMatch.requiredDuration ?? 0.5))),
                hint: hint
            )
            isGestureInProgress = true
        } else {
            gesturePreview = nil
            isGestureInProgress = false
        }
    }

    private func movementHint(for movement: GesturePattern.MovementType) -> String {
        switch movement {
        case .rotateClockwise: return "Rotate clockwise to increase"
        case .rotateCounterClockwise: return "Rotate counter-clockwise to decrease"
        case .swipeLeft: return "Swipe left"
        case .swipeRight: return "Swipe right"
        case .swipeUp: return "Swipe up"
        case .swipeDown: return "Swipe down"
        case .pullToward: return "Pull toward you"
        case .pushAway: return "Push away"
        case .pinchAndDrag: return "Pinch and drag"
        }
    }

    private func checkForCompletedGesture(_ gesture: HandTrackingService.HandGesture) {
        for pattern in gesturePatterns {
            if matchesPattern(pattern, gesture: gesture) {
                triggerAction(pattern.action, value: 1.0)
                resetGestureState()
                break
            }
        }
    }

    private func matchesPattern(_ pattern: GesturePattern, gesture: HandTrackingService.HandGesture) -> Bool {
        // Check base gesture
        guard pattern.baseGesture == gesture else { return false }

        // Check two-handed modifier
        if case .twoHanded = pattern.modifier, !twoHandGestureActive {
            return false
        }

        // Check sustained duration
        if case .sustained(let duration) = pattern.modifier {
            guard gestureHoldDuration >= duration else { return false }
        }

        // Check required duration
        if let requiredDuration = pattern.requiredDuration {
            guard gestureHoldDuration >= requiredDuration else { return false }
        }

        // Check movement
        if let requiredMovement = pattern.movement {
            guard currentMovement == requiredMovement else { return false }
        }

        return true
    }

    private func triggerAction(_ action: SemanticAction, value: Float) {
        currentAction = action
        actionProgress = value
        onSemanticAction?(action, value)

        // Reset after trigger
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) { [weak self] in
            self?.currentAction = .none
            self?.actionProgress = 0
        }
    }

    private func resetGestureState() {
        gestureStartTime = nil
        gestureHoldDuration = 0
        currentMovement = nil
        rotationAccumulator = 0
        gesturePreview = nil
        isGestureInProgress = false
    }
}

// MARK: - Gesture Hint View

/// Shows visual hint for current gesture
struct GestureHintView: View {
    @ObservedObject var recognizer: SemanticGestureRecognizer

    var body: some View {
        if let preview = recognizer.gesturePreview, recognizer.isGestureInProgress {
            VStack(spacing: 12) {
                // Action icon
                Image(systemName: preview.potentialAction.icon)
                    .font(.system(size: 32))
                    .foregroundColor(.cyan)

                // Progress ring
                ZStack {
                    Circle()
                        .stroke(Color.white.opacity(0.2), lineWidth: 4)
                        .frame(width: 60, height: 60)

                    Circle()
                        .trim(from: 0, to: CGFloat(preview.confidence))
                        .stroke(Color.cyan, style: StrokeStyle(lineWidth: 4, lineCap: .round))
                        .frame(width: 60, height: 60)
                        .rotationEffect(.degrees(-90))
                        .animation(.linear(duration: 0.1), value: preview.confidence)
                }

                // Hint text
                Text(preview.hint)
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.8))
                    .multilineTextAlignment(.center)
            }
            .padding(20)
            .background(.ultraThinMaterial)
            .clipShape(RoundedRectangle(cornerRadius: 20))
            .transition(.scale.combined(with: .opacity))
        }
    }
}

/*
 * 鏡
 * h(x) >= 0. Always.
 *
 * Gestures are poems of intention.
 * The hands speak what the voice cannot.
 * Natural input for natural control.
 */
