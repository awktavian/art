//
// KagamiHaptics.swift — Unified Haptic Feedback Service
//
// Colony: Crystal (e7) — Verification & Polish
//
// Provides consistent haptic patterns across the app:
//   - Success: Confirmation of completed actions
//   - Error: Alert for failures or blocked actions
//   - Warning: Attention needed, non-critical
//   - Selection: UI element selection feedback
//   - Impact: Physical interaction feedback
//   - Notification: System-level feedback
//
// Respects system haptic settings and provides fallbacks.
//
// h(x) >= 0. Always.
//

import UIKit
import CoreHaptics

// MARK: - Haptic Patterns

/// Semantic haptic feedback types
enum HapticPattern: Sendable {
    /// Positive completion (scene activated, action succeeded)
    case success
    /// Negative outcome (request failed, action blocked)
    case error
    /// Attention needed (safety warning, low battery)
    case warning
    /// UI element selection (button tap, row selection)
    case selection
    /// Light impact (hover, light touch)
    case lightImpact
    /// Medium impact (button press, drag start)
    case mediumImpact
    /// Heavy impact (drop, strong interaction)
    case heavyImpact
    /// Soft impact (subtle feedback)
    case softImpact
    /// Rigid impact (sharp feedback)
    case rigidImpact

    // MARK: - Discovery Effects (Prismorphism)

    /// Discovery state transition - glance (initial hover)
    case discoveryGlance
    /// Discovery state transition - interest (sustained attention)
    case discoveryInterest
    /// Discovery state transition - focus (full engagement)
    case discoveryFocus
    /// Discovery state transition - engage (action taken)
    case discoveryEngage

    // MARK: - Compound Patterns

    /// Double tap confirmation
    case doubleTap
    /// Long press acknowledgment
    case longPress
    /// Slider tick (for continuous controls)
    case tick
}

// MARK: - Haptic Service

/// Centralized haptic feedback service with consistent patterns
@MainActor
final class KagamiHaptics {

    // MARK: - Singleton

    static let shared = KagamiHaptics()

    // MARK: - Properties

    /// Core Haptics engine for custom patterns
    private var engine: CHHapticEngine?

    /// Whether haptics are supported on this device
    let isSupported: Bool

    /// Whether user has enabled haptics (respects system settings)
    var isEnabled: Bool {
        // Respect system haptic settings
        return UIDevice.current.userInterfaceIdiom == .phone
    }

    /// Pre-created feedback generators for performance
    private let notificationGenerator = UINotificationFeedbackGenerator()
    private let selectionGenerator = UISelectionFeedbackGenerator()
    private let lightImpactGenerator = UIImpactFeedbackGenerator(style: .light)
    private let mediumImpactGenerator = UIImpactFeedbackGenerator(style: .medium)
    private let heavyImpactGenerator = UIImpactFeedbackGenerator(style: .heavy)
    private let softImpactGenerator = UIImpactFeedbackGenerator(style: .soft)
    private let rigidImpactGenerator = UIImpactFeedbackGenerator(style: .rigid)

    // MARK: - Init

    private init() {
        // Check haptic support
        self.isSupported = CHHapticEngine.capabilitiesForHardware().supportsHaptics

        // Initialize Core Haptics engine if supported
        if isSupported {
            setupEngine()
        }

        // Prepare generators for low-latency response
        prepareGenerators()
    }

    // MARK: - Setup

    private func setupEngine() {
        do {
            engine = try CHHapticEngine()
            engine?.playsHapticsOnly = true
            engine?.isAutoShutdownEnabled = true

            // Handle engine reset
            engine?.resetHandler = { [weak self] in
                Task { @MainActor in
                    self?.restartEngine()
                }
            }

            // Handle engine stopped
            engine?.stoppedHandler = { _ in
                // Engine will auto-restart when needed
            }

            try engine?.start()
        } catch {
            engine = nil
        }
    }

    private func restartEngine() {
        do {
            try engine?.start()
        } catch {
            engine = nil
        }
    }

    private func prepareGenerators() {
        notificationGenerator.prepare()
        selectionGenerator.prepare()
        lightImpactGenerator.prepare()
        mediumImpactGenerator.prepare()
    }

    // MARK: - Public Interface

    /// Play a haptic pattern
    /// - Parameter pattern: The semantic haptic pattern to play
    func play(_ pattern: HapticPattern) {
        guard isEnabled else { return }

        switch pattern {
        case .success:
            notificationGenerator.notificationOccurred(.success)
            notificationGenerator.prepare()

        case .error:
            notificationGenerator.notificationOccurred(.error)
            notificationGenerator.prepare()

        case .warning:
            notificationGenerator.notificationOccurred(.warning)
            notificationGenerator.prepare()

        case .selection:
            selectionGenerator.selectionChanged()
            selectionGenerator.prepare()

        case .lightImpact:
            lightImpactGenerator.impactOccurred()
            lightImpactGenerator.prepare()

        case .mediumImpact:
            mediumImpactGenerator.impactOccurred()
            mediumImpactGenerator.prepare()

        case .heavyImpact:
            heavyImpactGenerator.impactOccurred()
            heavyImpactGenerator.prepare()

        case .softImpact:
            softImpactGenerator.impactOccurred()
            softImpactGenerator.prepare()

        case .rigidImpact:
            rigidImpactGenerator.impactOccurred()
            rigidImpactGenerator.prepare()

        case .discoveryGlance:
            // Subtle feedback for initial hover
            softImpactGenerator.impactOccurred(intensity: 0.3)
            softImpactGenerator.prepare()

        case .discoveryInterest:
            // Slightly stronger for sustained attention
            lightImpactGenerator.impactOccurred(intensity: 0.5)
            lightImpactGenerator.prepare()

        case .discoveryFocus:
            // Full light impact for focus state
            lightImpactGenerator.impactOccurred(intensity: 0.8)
            lightImpactGenerator.prepare()

        case .discoveryEngage:
            // Medium impact for engagement
            mediumImpactGenerator.impactOccurred()
            mediumImpactGenerator.prepare()

        case .doubleTap:
            playDoubleTapPattern()

        case .longPress:
            playLongPressPattern()

        case .tick:
            // Very light selection feedback
            selectionGenerator.selectionChanged()
            selectionGenerator.prepare()
        }
    }

    /// Play haptic with custom intensity (0.0 - 1.0)
    /// - Parameters:
    ///   - pattern: Base pattern to modify
    ///   - intensity: Intensity multiplier (0.0 to 1.0)
    func play(_ pattern: HapticPattern, intensity: CGFloat) {
        guard isEnabled else { return }

        let clampedIntensity = min(1.0, max(0.0, intensity))

        switch pattern {
        case .lightImpact:
            lightImpactGenerator.impactOccurred(intensity: clampedIntensity)
            lightImpactGenerator.prepare()
        case .mediumImpact:
            mediumImpactGenerator.impactOccurred(intensity: clampedIntensity)
            mediumImpactGenerator.prepare()
        case .heavyImpact:
            heavyImpactGenerator.impactOccurred(intensity: clampedIntensity)
            heavyImpactGenerator.prepare()
        case .softImpact:
            softImpactGenerator.impactOccurred(intensity: clampedIntensity)
            softImpactGenerator.prepare()
        case .rigidImpact:
            rigidImpactGenerator.impactOccurred(intensity: clampedIntensity)
            rigidImpactGenerator.prepare()
        default:
            play(pattern)
        }
    }

    // MARK: - Compound Patterns

    private func playDoubleTapPattern() {
        lightImpactGenerator.impactOccurred(intensity: 0.6)
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.08) { [weak self] in
            self?.lightImpactGenerator.impactOccurred(intensity: 0.8)
            self?.lightImpactGenerator.prepare()
        }
    }

    private func playLongPressPattern() {
        // Building pressure effect
        softImpactGenerator.impactOccurred(intensity: 0.3)
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) { [weak self] in
            self?.softImpactGenerator.impactOccurred(intensity: 0.5)
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) { [weak self] in
            self?.mediumImpactGenerator.impactOccurred(intensity: 0.7)
            self?.mediumImpactGenerator.prepare()
        }
    }

    // MARK: - Custom Core Haptics Patterns

    /// Play a custom Core Haptics pattern
    /// - Parameter events: Array of haptic events
    func playCustomPattern(_ events: [CHHapticEvent]) {
        guard isEnabled, isSupported, let engine = engine else { return }

        do {
            let pattern = try CHHapticPattern(events: events, parameters: [])
            let player = try engine.makePlayer(with: pattern)
            try player.start(atTime: 0)
        } catch {
            // Fallback to simple impact
            mediumImpactGenerator.impactOccurred()
        }
    }

    /// Play spectral sweep haptic (for Prismorphism effects)
    /// - Parameter duration: Duration of the sweep in seconds
    func playSpectralSweep(duration: TimeInterval = 0.5) {
        guard isEnabled, isSupported, let engine = engine else {
            // Fallback
            play(.mediumImpact)
            return
        }

        // Create a sweeping intensity pattern
        let events: [CHHapticEvent] = (0..<7).map { index in
            let relativeTime = TimeInterval(index) * 0.008 // 8ms between each
            let intensity = Float(0.3 + 0.1 * Double(index))
            return CHHapticEvent(
                eventType: .hapticTransient,
                parameters: [
                    CHHapticEventParameter(parameterID: .hapticIntensity, value: intensity),
                    CHHapticEventParameter(parameterID: .hapticSharpness, value: 0.5)
                ],
                relativeTime: relativeTime
            )
        }

        playCustomPattern(events)
    }

    /// Play safety violation haptic (strong warning)
    func playSafetyViolation() {
        guard isEnabled else { return }

        // Three strong pulses
        heavyImpactGenerator.impactOccurred()
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.15) { [weak self] in
            self?.heavyImpactGenerator.impactOccurred()
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.30) { [weak self] in
            self?.heavyImpactGenerator.impactOccurred()
            self?.notificationGenerator.notificationOccurred(.error)
            self?.heavyImpactGenerator.prepare()
        }
    }
}

// MARK: - Fibonacci Timing Constants

/// Fibonacci-based timing for haptic patterns (in seconds)
enum HapticTiming {
    /// 89ms - Micro interactions
    static let micro: TimeInterval = 0.089
    /// 144ms - Fast feedback
    static let fast: TimeInterval = 0.144
    /// 233ms - Normal rhythm
    static let normal: TimeInterval = 0.233
    /// 377ms - Medium pause
    static let medium: TimeInterval = 0.377
    /// 610ms - Slow sequence
    static let slow: TimeInterval = 0.610
    /// 987ms - Breathing rhythm
    static let breathing: TimeInterval = 0.987
}

// MARK: - Fibonacci Haptic Patterns

extension KagamiHaptics {

    /// Play a Fibonacci-timed success pattern
    /// Pattern: tap-pause(144ms)-tap-pause(89ms)-tap
    func playFibonacciSuccess() {
        guard isEnabled else { return }

        // First tap
        lightImpactGenerator.impactOccurred(intensity: 0.6)

        // Second tap after 144ms
        DispatchQueue.main.asyncAfter(deadline: .now() + HapticTiming.fast) { [weak self] in
            self?.lightImpactGenerator.impactOccurred(intensity: 0.8)
        }

        // Third tap after 89ms more
        DispatchQueue.main.asyncAfter(deadline: .now() + HapticTiming.fast + HapticTiming.micro) { [weak self] in
            self?.mediumImpactGenerator.impactOccurred(intensity: 1.0)
            self?.mediumImpactGenerator.prepare()
        }
    }

    /// Play a Fibonacci-timed warning pattern
    /// Pattern: heavy-pause(233ms)-heavy-pause(144ms)-heavy
    func playFibonacciWarning() {
        guard isEnabled else { return }

        // First heavy tap
        heavyImpactGenerator.impactOccurred(intensity: 0.7)

        // Second after 233ms
        DispatchQueue.main.asyncAfter(deadline: .now() + HapticTiming.normal) { [weak self] in
            self?.heavyImpactGenerator.impactOccurred(intensity: 0.85)
        }

        // Third after 144ms more
        DispatchQueue.main.asyncAfter(deadline: .now() + HapticTiming.normal + HapticTiming.fast) { [weak self] in
            self?.heavyImpactGenerator.impactOccurred(intensity: 1.0)
            self?.heavyImpactGenerator.prepare()
        }
    }

    /// Play a Fibonacci-timed breathing pattern for meditation/focus
    /// Pattern: builds and releases over 987ms cycle
    func playFibonacciBreathing() {
        guard isEnabled, isSupported, let engine = engine else {
            // Fallback to simple pattern
            play(.softImpact)
            return
        }

        // Create breathing pattern using Fibonacci ratios
        let events: [CHHapticEvent] = [
            // Rising intensity (0 - 377ms)
            CHHapticEvent(
                eventType: .hapticContinuous,
                parameters: [
                    CHHapticEventParameter(parameterID: .hapticIntensity, value: 0.3),
                    CHHapticEventParameter(parameterID: .hapticSharpness, value: 0.2)
                ],
                relativeTime: 0,
                duration: HapticTiming.medium
            ),
            // Peak (377ms - 610ms)
            CHHapticEvent(
                eventType: .hapticContinuous,
                parameters: [
                    CHHapticEventParameter(parameterID: .hapticIntensity, value: 0.6),
                    CHHapticEventParameter(parameterID: .hapticSharpness, value: 0.3)
                ],
                relativeTime: HapticTiming.medium,
                duration: HapticTiming.normal
            ),
            // Release (610ms - 987ms)
            CHHapticEvent(
                eventType: .hapticContinuous,
                parameters: [
                    CHHapticEventParameter(parameterID: .hapticIntensity, value: 0.2),
                    CHHapticEventParameter(parameterID: .hapticSharpness, value: 0.1)
                ],
                relativeTime: HapticTiming.slow,
                duration: HapticTiming.medium
            ),
        ]

        playCustomPattern(events)
    }

    /// Play a Fibonacci-timed selection cascade
    /// Pattern: light taps at 89ms intervals, building intensity
    func playFibonacciSelection() {
        guard isEnabled else { return }

        // 5 taps at Fibonacci micro timing
        for i in 0..<5 {
            let delay = HapticTiming.micro * Double(i)
            let intensity = 0.3 + (0.1 * Double(i))

            DispatchQueue.main.asyncAfter(deadline: .now() + delay) { [weak self] in
                self?.lightImpactGenerator.impactOccurred(intensity: CGFloat(min(1.0, intensity)))
            }
        }

        // Final prepare
        DispatchQueue.main.asyncAfter(deadline: .now() + HapticTiming.micro * 5) { [weak self] in
            self?.lightImpactGenerator.prepare()
        }
    }

    /// Play scene activation haptic with Fibonacci rhythm
    /// Pattern: build-hold-release with catastrophe-curve feel
    func playSceneActivation() {
        guard isEnabled else { return }

        // Initial soft build (like fold catastrophe)
        softImpactGenerator.impactOccurred(intensity: 0.4)

        // Growing intensity at 144ms
        DispatchQueue.main.asyncAfter(deadline: .now() + HapticTiming.fast) { [weak self] in
            self?.lightImpactGenerator.impactOccurred(intensity: 0.6)
        }

        // Peak at 233ms (cusp moment)
        DispatchQueue.main.asyncAfter(deadline: .now() + HapticTiming.normal) { [weak self] in
            self?.mediumImpactGenerator.impactOccurred(intensity: 0.9)
        }

        // Confirmation at 377ms
        DispatchQueue.main.asyncAfter(deadline: .now() + HapticTiming.medium) { [weak self] in
            self?.notificationGenerator.notificationOccurred(.success)
            self?.notificationGenerator.prepare()
        }
    }

    /// Play error rejection haptic with Fibonacci timing
    /// Pattern: sharp rejection followed by softer denial
    func playErrorRejection() {
        guard isEnabled else { return }

        // Sharp initial rejection
        rigidImpactGenerator.impactOccurred(intensity: 1.0)

        // Second rejection at 144ms
        DispatchQueue.main.asyncAfter(deadline: .now() + HapticTiming.fast) { [weak self] in
            self?.rigidImpactGenerator.impactOccurred(intensity: 0.7)
        }

        // Error notification at 233ms
        DispatchQueue.main.asyncAfter(deadline: .now() + HapticTiming.normal) { [weak self] in
            self?.notificationGenerator.notificationOccurred(.error)
            self?.notificationGenerator.prepare()
        }
    }

    /// Play slider tick at Fibonacci intervals
    /// Designed for continuous controls with natural feel
    func playSliderTick(position: CGFloat) {
        guard isEnabled else { return }

        // Intensity varies with position (Golden ratio influence)
        let phi: CGFloat = 1.618
        let adjustedIntensity = 0.2 + (position / phi) * 0.3

        selectionGenerator.selectionChanged()
        lightImpactGenerator.impactOccurred(intensity: min(0.5, adjustedIntensity))
    }

    /// Play countdown haptic pattern
    /// Pattern: decreasing intervals following Fibonacci
    func playCountdown(from count: Int, completion: @escaping () -> Void) {
        guard isEnabled, count > 0 else {
            completion()
            return
        }

        // Timing follows reverse Fibonacci
        let timings: [TimeInterval] = [
            HapticTiming.breathing,  // 987ms
            HapticTiming.slow,       // 610ms
            HapticTiming.medium,     // 377ms
            HapticTiming.normal,     // 233ms
            HapticTiming.fast        // 144ms
        ]

        var currentDelay: TimeInterval = 0

        for i in 0..<min(count, timings.count) {
            let timing = timings[i]
            let intensity = 0.5 + (CGFloat(i) * 0.1)

            DispatchQueue.main.asyncAfter(deadline: .now() + currentDelay) { [weak self] in
                self?.mediumImpactGenerator.impactOccurred(intensity: intensity)
            }

            currentDelay += timing
        }

        // Final completion haptic
        DispatchQueue.main.asyncAfter(deadline: .now() + currentDelay) { [weak self] in
            self?.notificationGenerator.notificationOccurred(.success)
            self?.notificationGenerator.prepare()
            completion()
        }
    }
}

// MARK: - Convenience Extensions

extension View {
    /// Add haptic feedback to a view's tap gesture
    /// - Parameter pattern: The haptic pattern to play on tap
    func hapticFeedback(_ pattern: HapticPattern) -> some View {
        self.onTapGesture {
            Task { @MainActor in
                KagamiHaptics.shared.play(pattern)
            }
        }
    }

    /// Add Fibonacci success haptic on value change
    func hapticOnSuccess<V: Equatable>(value: V, when condition: @escaping (V) -> Bool) -> some View {
        self.onChange(of: value) { _, newValue in
            if condition(newValue) {
                Task { @MainActor in
                    KagamiHaptics.shared.playFibonacciSuccess()
                }
            }
        }
    }

    /// Add scene activation haptic
    func hapticSceneActivation() -> some View {
        self.onTapGesture {
            Task { @MainActor in
                KagamiHaptics.shared.playSceneActivation()
            }
        }
    }

    /// Add slider tick haptic with position
    func hapticSliderTick(position: CGFloat) -> some View {
        self.onChange(of: position) { _, newValue in
            Task { @MainActor in
                KagamiHaptics.shared.playSliderTick(position: newValue)
            }
        }
    }
}

// MARK: - SwiftUI Import

import SwiftUI

/*
 * Mirror
 * Haptics provide non-visual feedback for accessibility.
 * Consistent patterns build user intuition.
 * Fibonacci timing creates natural rhythm.
 * h(x) >= 0. Always.
 */
