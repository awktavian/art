//
// SiriRemoteHandler.swift -- Advanced Siri Remote Input Handling
//
// Kagami TV -- Game Controller and Press Events for tvOS
//
// Colony: Flow (e3) -- Execution
//
// Features:
// - UIPress handling for Siri Remote buttons
// - GCController support for extended gamepad features
// - Gesture recognizers for touch surface
// - Accelerometer/gyroscope input (when available)
// - Play/Pause button for quick actions
// - Menu button custom handling
//
// h(x) >= 0. Always.
//

import UIKit
import GameController
import Combine

/// Handles advanced Siri Remote input beyond standard SwiftUI focus system.
/// Provides game controller and physical button press event handling.
@MainActor
class SiriRemoteHandler: ObservableObject {

    // MARK: - Published State

    @Published var isRemoteConnected = false
    @Published var lastButtonPressed: RemoteButton = .none
    @Published var touchPadVelocity: CGPoint = .zero
    @Published var motionEnabled = false

    // MARK: - Types

    /// Siri Remote button types
    enum RemoteButton: String {
        case none
        case playPause = "play_pause"
        case menu = "menu"
        case select = "select"
        case up = "up"
        case down = "down"
        case left = "left"
        case right = "right"
        case volumeUp = "volume_up"
        case volumeDown = "volume_down"
        case home = "home"
        case siri = "siri"
    }

    /// Remote gesture types
    /// Per KAGAMI_REDESIGN_PLAN.md: Enhanced Siri Remote gesture handling
    enum RemoteGesture: String {
        case swipeUp = "swipe_up"
        case swipeDown = "swipe_down"
        case swipeLeft = "swipe_left"
        case swipeRight = "swipe_right"
        case tap = "tap"
        case longPress = "long_press"
        case doubleTap = "double_tap"
        case twoFingerTap = "two_finger_tap"
        case rotateClockwise = "rotate_clockwise"
        case rotateCounterClockwise = "rotate_counter_clockwise"
        case pinch = "pinch"
        case spread = "spread"
        case edgeSwipeLeft = "edge_swipe_left"
        case edgeSwipeRight = "edge_swipe_right"
        case scrubForward = "scrub_forward"
        case scrubBackward = "scrub_backward"
    }

    /// Gesture velocity for scrubbing
    struct GestureVelocity {
        let speed: Float  // 0-1 normalized
        let direction: Float  // -1 (left/backward) to 1 (right/forward)
    }

    /// Callback type for remote events
    typealias RemoteEventHandler = (RemoteButton) -> Void
    typealias GestureEventHandler = (RemoteGesture) -> Void
    typealias VelocityGestureHandler = (RemoteGesture, GestureVelocity) -> Void
    typealias LongPressHandler = (RemoteButton, TimeInterval) -> Void

    // MARK: - Callbacks

    var onButtonPress: RemoteEventHandler?
    var onGesture: GestureEventHandler?
    var onVelocityGesture: VelocityGestureHandler?
    var onLongPress: LongPressHandler?

    /// Quick action triggered by Play/Pause double-tap
    var onQuickAction: (() -> Void)?

    /// Brightness adjustment triggered by circular gesture
    var onBrightnessAdjust: ((Float) -> Void)?

    /// Volume adjustment (when Siri Remote volume buttons are captured)
    var onVolumeAdjust: ((Float) -> Void)?

    // MARK: - Internal State

    private var gameController: GCController?
    private var cancellables = Set<AnyCancellable>()
    private var lastPlayPauseTime: Date?
    private var lastSelectTime: Date?
    private var longPressTimer: Timer?
    private var longPressDuration: TimeInterval = 0
    private var circularGestureAccumulator: Float = 0
    private var lastDPadAngle: Float?
    private var scrubVelocity: Float = 0
    private var isScrubbing = false

    // MARK: - Init

    init() {
        setupControllerNotifications()
        checkForConnectedControllers()
    }

    // MARK: - Setup

    private func setupControllerNotifications() {
        // Controller connected
        NotificationCenter.default.publisher(for: .GCControllerDidConnect)
            .receive(on: DispatchQueue.main)
            .sink { [weak self] notification in
                if let controller = notification.object as? GCController {
                    self?.handleControllerConnected(controller)
                }
            }
            .store(in: &cancellables)

        // Controller disconnected
        NotificationCenter.default.publisher(for: .GCControllerDidDisconnect)
            .receive(on: DispatchQueue.main)
            .sink { [weak self] notification in
                if let controller = notification.object as? GCController {
                    self?.handleControllerDisconnected(controller)
                }
            }
            .store(in: &cancellables)
    }

    private func checkForConnectedControllers() {
        GCController.startWirelessControllerDiscovery {
            // Discovery completed
        }

        // Check already connected controllers
        if let controller = GCController.controllers().first {
            handleControllerConnected(controller)
        }
    }

    // MARK: - Controller Handling

    private func handleControllerConnected(_ controller: GCController) {
        gameController = controller
        isRemoteConnected = true

        // Configure Siri Remote (microGamepad profile)
        if let microGamepad = controller.microGamepad {
            configureMicroGamepad(microGamepad)
        }

        // Configure extended gamepad if available
        if let extendedGamepad = controller.extendedGamepad {
            configureExtendedGamepad(extendedGamepad)
        }

        // Enable motion if supported
        if let motion = controller.motion {
            configureMotion(motion)
        }

        print("Controller connected: \(controller.vendorName ?? "Unknown")")
    }

    private func handleControllerDisconnected(_ controller: GCController) {
        if controller == gameController {
            gameController = nil
            isRemoteConnected = false
            motionEnabled = false
        }
    }

    // MARK: - Micro Gamepad (Siri Remote)

    private func configureMicroGamepad(_ pad: GCMicroGamepad) {
        // Enable absolute dPad values for precise tracking
        pad.reportsAbsoluteDpadValues = true

        // Button A (Select/Click)
        pad.buttonA.pressedChangedHandler = { [weak self] _, _, pressed in
            if pressed {
                self?.handleButton(.select)
            }
        }

        // Button X (Play/Pause)
        pad.buttonX.pressedChangedHandler = { [weak self] _, _, pressed in
            if pressed {
                self?.handlePlayPause()
            }
        }

        // Button Menu
        pad.buttonMenu.pressedChangedHandler = { [weak self] _, _, pressed in
            if pressed {
                self?.handleButton(.menu)
            }
        }

        // D-Pad (Touch surface)
        pad.dpad.valueChangedHandler = { [weak self] _, xValue, yValue in
            self?.handleDPadChange(x: xValue, y: yValue)
        }
    }

    // MARK: - Extended Gamepad

    private func configureExtendedGamepad(_ pad: GCExtendedGamepad) {
        // Full directional control
        pad.dpad.up.pressedChangedHandler = { [weak self] _, _, pressed in
            if pressed { self?.handleButton(.up) }
        }
        pad.dpad.down.pressedChangedHandler = { [weak self] _, _, pressed in
            if pressed { self?.handleButton(.down) }
        }
        pad.dpad.left.pressedChangedHandler = { [weak self] _, _, pressed in
            if pressed { self?.handleButton(.left) }
        }
        pad.dpad.right.pressedChangedHandler = { [weak self] _, _, pressed in
            if pressed { self?.handleButton(.right) }
        }

        // Additional buttons
        pad.buttonA.pressedChangedHandler = { [weak self] _, _, pressed in
            if pressed { self?.handleButton(.select) }
        }
        pad.buttonB.pressedChangedHandler = { [weak self] _, _, pressed in
            if pressed { self?.handleButton(.menu) }
        }
    }

    // MARK: - Motion

    private func configureMotion(_ motion: GCMotion) {
        motionEnabled = true

        // Handle motion data for tilt-based interactions
        motion.valueChangedHandler = { [weak self] motion in
            // Could use for tilt-based brightness adjustment
            let pitch = motion.attitude.pitch
            let roll = motion.attitude.roll
            // Future: implement motion-based controls
            _ = pitch
            _ = roll
        }
    }

    // MARK: - Input Processing

    private func handleButton(_ button: RemoteButton) {
        lastButtonPressed = button
        onButtonPress?(button)

        // Log for debugging
        print("Remote button: \(button.rawValue)")
    }

    private func handlePlayPause() {
        let now = Date()

        // Double-tap detection for quick action
        if let lastTime = lastPlayPauseTime,
           now.timeIntervalSince(lastTime) < 0.4 {
            // Double-tap: trigger quick action
            onQuickAction?()
            lastPlayPauseTime = nil
            return
        }

        lastPlayPauseTime = now
        handleButton(.playPause)
    }

    private func handleDPadChange(x: Float, y: Float) {
        touchPadVelocity = CGPoint(x: CGFloat(x), y: CGFloat(y))

        // Detect circular gestures (rotation)
        detectCircularGesture(x: x, y: y)

        // Detect scrubbing gestures
        detectScrubGesture(x: x, y: y)

        // Convert to directional gestures
        if abs(x) > 0.5 || abs(y) > 0.5 {
            let gesture: RemoteGesture
            if abs(y) > abs(x) {
                gesture = y > 0 ? .swipeUp : .swipeDown
            } else {
                gesture = x > 0 ? .swipeRight : .swipeLeft
            }
            onGesture?(gesture)

            // Check for edge swipes
            if abs(x) > 0.9 {
                onGesture?(x > 0 ? .edgeSwipeRight : .edgeSwipeLeft)
            }
        }
    }

    // MARK: - Enhanced Gesture Detection

    /// Detect circular rotation gestures for brightness/volume control
    private func detectCircularGesture(x: Float, y: Float) {
        guard abs(x) > 0.1 || abs(y) > 0.1 else {
            lastDPadAngle = nil
            return
        }

        let currentAngle = atan2(y, x)

        if let lastAngle = lastDPadAngle {
            var delta = currentAngle - lastAngle

            // Normalize delta to handle wrap-around
            if delta > .pi { delta -= 2 * .pi }
            if delta < -.pi { delta += 2 * .pi }

            // Accumulate rotation
            circularGestureAccumulator += delta

            // Trigger rotation gesture at threshold
            let rotationThreshold: Float = 0.3

            if circularGestureAccumulator > rotationThreshold {
                onGesture?(.rotateClockwise)
                onBrightnessAdjust?(0.05)  // Increase brightness
                circularGestureAccumulator = 0
            } else if circularGestureAccumulator < -rotationThreshold {
                onGesture?(.rotateCounterClockwise)
                onBrightnessAdjust?(-0.05)  // Decrease brightness
                circularGestureAccumulator = 0
            }
        }

        lastDPadAngle = currentAngle
    }

    /// Detect horizontal scrubbing gestures with velocity
    private func detectScrubGesture(x: Float, y: Float) {
        // Scrubbing requires horizontal movement with minimal vertical
        if abs(x) > 0.3 && abs(y) < 0.2 {
            if !isScrubbing {
                isScrubbing = true
            }

            // Calculate velocity based on position
            scrubVelocity = x

            let velocity = GestureVelocity(speed: abs(x), direction: x)
            let gesture: RemoteGesture = x > 0 ? .scrubForward : .scrubBackward
            onVelocityGesture?(gesture, velocity)

        } else if isScrubbing && abs(x) < 0.1 {
            // Scrubbing ended
            isScrubbing = false
            scrubVelocity = 0
        }
    }

    /// Handle double-tap on select button
    private func handleSelectWithDoubleTap() {
        let now = Date()

        if let lastTime = lastSelectTime,
           now.timeIntervalSince(lastTime) < 0.4 {
            // Double-tap detected
            onGesture?(.doubleTap)
            lastSelectTime = nil
            return
        }

        lastSelectTime = now
        handleButton(.select)
    }

    /// Start long press detection
    private func startLongPressDetection(for button: RemoteButton) {
        longPressDuration = 0
        longPressTimer?.invalidate()
        longPressTimer = Timer.scheduledTimer(withTimeInterval: 0.1, repeats: true) { [weak self] timer in
            guard let self = self else {
                timer.invalidate()
                return
            }

            self.longPressDuration += 0.1

            // Trigger long press at 0.5 seconds
            if self.longPressDuration >= 0.5 {
                self.onLongPress?(button, self.longPressDuration)
            }

            // Trigger very long press events at 1 second intervals
            if self.longPressDuration >= 1.0 && self.longPressDuration.truncatingRemainder(dividingBy: 1.0) < 0.1 {
                self.onGesture?(.longPress)
            }
        }
    }

    /// Stop long press detection
    private func stopLongPressDetection() {
        longPressTimer?.invalidate()
        longPressTimer = nil
        longPressDuration = 0
    }

    // MARK: - UIPress Handling

    /// Handle press events from UIResponder chain.
    /// Call this from your UIViewController or custom responder.
    func handlePressBegin(_ presses: Set<UIPress>) {
        for press in presses {
            guard let key = press.key else { continue }

            let button: RemoteButton
            switch key.keyCode {
            case .keyboardUpArrow:
                button = .up
            case .keyboardDownArrow:
                button = .down
            case .keyboardLeftArrow:
                button = .left
            case .keyboardRightArrow:
                button = .right
            case .keyboardReturnOrEnter, .keyboardSpacebar:
                button = .select
            case .keyboardEscape:
                button = .menu
            default:
                continue
            }

            handleButton(button)
        }
    }

    // MARK: - Convenience Actions

    /// Trigger a haptic feedback (if supported)
    func triggerHaptic() {
        // Note: tvOS doesn't have direct haptic API, but some controllers support it
        gameController?.microGamepad?.buttonA.sfSymbolsName = "hand.tap"
    }
}

// MARK: - SwiftUI Integration

import SwiftUI

/// View modifier for easy remote handler integration
struct RemoteHandlerModifier: ViewModifier {
    @StateObject private var remoteHandler = SiriRemoteHandler()
    let onButton: SiriRemoteHandler.RemoteEventHandler?
    let onGesture: SiriRemoteHandler.GestureEventHandler?

    func body(content: Content) -> some View {
        content
            .environmentObject(remoteHandler)
            .onAppear {
                remoteHandler.onButtonPress = onButton
                remoteHandler.onGesture = onGesture
            }
    }
}

extension View {
    /// Adds Siri Remote advanced handling to a view.
    func onRemoteInput(
        button: SiriRemoteHandler.RemoteEventHandler? = nil,
        gesture: SiriRemoteHandler.GestureEventHandler? = nil
    ) -> some View {
        modifier(RemoteHandlerModifier(onButton: button, onGesture: gesture))
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 *
 * The Siri Remote becomes an extension of intent.
 * Every press, every gesture, every motion.
 * Direct connection to the smart home.
 */
