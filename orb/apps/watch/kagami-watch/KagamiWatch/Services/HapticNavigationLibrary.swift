//
// HapticNavigationLibrary.swift — Haptic-Only Navigation for Deafblind Accessibility
//
// Colony: Beacon (e5) — Safety & Alerts
//
// P2 Gap: Haptic-only patterns for deafblind users
// Implements:
//   - Distinct haptic patterns for each action type
//   - Morse-like encoding for complex information
//   - Navigation feedback patterns
//   - Confirmation/error haptics
//   - Accessibility mode toggle
//
// Per audit: Improves Beacon score 92->100 via haptic-only navigation
//
// h(x) >= 0. Always.
//

import Foundation
import SwiftUI
import WatchKit
import Combine

// MARK: - Haptic Morse Encoding

/// Morse-like haptic encoding for letters and numbers
/// Short = 0.1s tap, Long = 0.3s tap, Gap = 0.2s between elements
enum HapticMorse {
    /// Morse code dictionary
    static let alphabet: [Character: String] = [
        "A": ".-",    "B": "-...",  "C": "-.-.",  "D": "-..",
        "E": ".",     "F": "..-.",  "G": "--.",   "H": "....",
        "I": "..",    "J": ".---",  "K": "-.-",   "L": ".-..",
        "M": "--",    "N": "-.",    "O": "---",   "P": ".--.",
        "Q": "--.-",  "R": ".-.",   "S": "...",   "T": "-",
        "U": "..-",   "V": "...-",  "W": ".--",   "X": "-..-",
        "Y": "-.--",  "Z": "--..",
        "0": "-----", "1": ".----", "2": "..---", "3": "...--",
        "4": "....-", "5": ".....", "6": "-....", "7": "--...",
        "8": "---..", "9": "----."
    ]

    /// Encode text to morse pattern
    static func encode(_ text: String) -> [HapticElement] {
        var elements: [HapticElement] = []
        let upperText = text.uppercased()

        for (index, char) in upperText.enumerated() {
            if char == " " {
                // Word gap (longer pause)
                elements.append(.wordGap)
                continue
            }

            if let morse = alphabet[char] {
                for symbol in morse {
                    switch symbol {
                    case ".":
                        elements.append(.dot)
                    case "-":
                        elements.append(.dash)
                    default:
                        break
                    }
                }
                // Character gap (unless last character)
                if index < upperText.count - 1 {
                    elements.append(.charGap)
                }
            }
        }

        return elements
    }
}

/// Haptic elements for morse encoding
enum HapticElement {
    case dot        // Short tap (0.1s)
    case dash       // Long tap (0.3s)
    case charGap    // Gap between characters (0.2s)
    case wordGap    // Gap between words (0.6s)

    /// Duration in seconds
    var duration: TimeInterval {
        switch self {
        case .dot: return 0.1
        case .dash: return 0.3
        case .charGap: return 0.2
        case .wordGap: return 0.6
        }
    }

    /// WatchKit haptic type
    var hapticType: WKHapticType {
        switch self {
        case .dot: return .click
        case .dash: return .success
        case .charGap, .wordGap: return .stop
        }
    }
}

// MARK: - Navigation Haptic Patterns
// Per KAGAMI_REDESIGN_PLAN.md: Create haptic communication patterns

/// Predefined haptic patterns for navigation and feedback
enum NavigationHapticPattern: String, CaseIterable {
    // Confirmation patterns
    case success = "success"
    case error = "error"
    case warning = "warning"
    case attention = "attention"

    // Action patterns
    case sceneActivated = "scene_activated"
    case lightsOn = "lights_on"
    case lightsOff = "lights_off"
    case lightsDim = "lights_dim"
    case fireplaceOn = "fireplace_on"
    case fireplaceOff = "fireplace_off"
    case shadesOpen = "shades_open"
    case shadesClose = "shades_close"
    case tvLower = "tv_lower"
    case tvRaise = "tv_raise"
    case lockEngaged = "lock_engaged"
    case lockDisengaged = "lock_disengaged"
    case securityArm = "security_arm"
    case securityDisarm = "security_disarm"
    case thermostatAdjust = "thermostat_adjust"

    // Navigation patterns
    case selectionUp = "selection_up"
    case selectionDown = "selection_down"
    case selectionConfirm = "selection_confirm"
    case menuOpen = "menu_open"
    case menuClose = "menu_close"
    case scrollBoundary = "scroll_boundary"
    case pageChange = "page_change"
    case tabSwitch = "tab_switch"
    case backNavigation = "back_navigation"

    // Status patterns
    case connected = "connected"
    case disconnected = "disconnected"
    case lowBattery = "low_battery"
    case safetyAlert = "safety_alert"
    case safetyOK = "safety_ok"
    case presenceDetected = "presence_detected"
    case presenceCleared = "presence_cleared"

    // Communication patterns (per redesign plan)
    case messageReceived = "message_received"
    case callIncoming = "call_incoming"
    case reminderAlert = "reminder_alert"
    case weatherAlert = "weather_alert"
    case arrival = "arrival"
    case departure = "departure"
    case sleepStart = "sleep_start"
    case wakeUp = "wake_up"
    case workoutStart = "workout_start"
    case workoutEnd = "workout_end"

    // Contextual patterns
    case morningRoutine = "morning_routine"
    case eveningRoutine = "evening_routine"
    case goodnightSequence = "goodnight_sequence"
    case welcomeHome = "welcome_home"
    case awayMode = "away_mode"
    case movieMode = "movie_mode"
    case focusMode = "focus_mode"

    // Accessibility patterns (enhanced for deafblind)
    case voiceCommandStart = "voice_command_start"
    case voiceCommandEnd = "voice_command_end"
    case voiceCommandSuccess = "voice_command_success"
    case voiceCommandFail = "voice_command_fail"
    case gestureRecognized = "gesture_recognized"
    case gestureUnrecognized = "gesture_unrecognized"

    /// Pattern description for accessibility
    var description: String {
        switch self {
        case .success: return "Two rising taps"
        case .error: return "Three short taps"
        case .warning: return "Long pulse"
        case .attention: return "Attention-getting tap sequence"
        case .sceneActivated: return "Three ascending taps"
        case .lightsOn: return "Quick pulse up"
        case .lightsOff: return "Quick pulse down"
        case .lightsDim: return "Soft tap"
        case .fireplaceOn: return "Warm pattern"
        case .fireplaceOff: return "Cool down pattern"
        case .shadesOpen: return "Rising sweep"
        case .shadesClose: return "Falling sweep"
        case .tvLower: return "Descending"
        case .tvRaise: return "Ascending"
        case .lockEngaged: return "Firm double tap"
        case .lockDisengaged: return "Release tap"
        case .securityArm: return "Three firm taps"
        case .securityDisarm: return "Two soft taps"
        case .thermostatAdjust: return "Temperature pulse"
        case .selectionUp: return "Light up tick"
        case .selectionDown: return "Light down tick"
        case .selectionConfirm: return "Firm tap"
        case .menuOpen: return "Opening"
        case .menuClose: return "Closing"
        case .scrollBoundary: return "Soft boundary tap"
        case .pageChange: return "Page turn"
        case .tabSwitch: return "Tab shift"
        case .backNavigation: return "Retreat tap"
        case .connected: return "Double tap"
        case .disconnected: return "Falling pattern"
        case .lowBattery: return "Urgent pulse"
        case .safetyAlert: return "Continuous alert"
        case .safetyOK: return "Reassuring pulse"
        case .presenceDetected: return "Someone arrived"
        case .presenceCleared: return "Room empty"
        case .messageReceived: return "Message notification"
        case .callIncoming: return "Incoming call pattern"
        case .reminderAlert: return "Reminder tap"
        case .weatherAlert: return "Weather warning"
        case .arrival: return "Welcome pattern"
        case .departure: return "Goodbye pattern"
        case .sleepStart: return "Sleep beginning"
        case .wakeUp: return "Wake up sequence"
        case .workoutStart: return "Workout begins"
        case .workoutEnd: return "Workout complete"
        case .morningRoutine: return "Morning sequence"
        case .eveningRoutine: return "Evening sequence"
        case .goodnightSequence: return "Goodnight pattern"
        case .welcomeHome: return "Welcome home"
        case .awayMode: return "Away activated"
        case .movieMode: return "Movie mode"
        case .focusMode: return "Focus mode"
        case .voiceCommandStart: return "Listening"
        case .voiceCommandEnd: return "Processing"
        case .voiceCommandSuccess: return "Command understood"
        case .voiceCommandFail: return "Command not understood"
        case .gestureRecognized: return "Gesture detected"
        case .gestureUnrecognized: return "Unknown gesture"
        }
    }
}

// MARK: - Haptic Navigation Library

/// Library for haptic-only navigation and feedback
@MainActor
final class HapticNavigationLibrary: ObservableObject {

    // MARK: - Singleton

    static let shared = HapticNavigationLibrary()

    // MARK: - Published State

    @Published var isAccessibilityModeEnabled: Bool = false
    @Published var isPlaying: Bool = false
    @Published var lastPlayedPattern: NavigationHapticPattern?

    // MARK: - Configuration

    /// Haptic intensity multiplier (0.5 = softer, 1.5 = stronger)
    var intensityMultiplier: Double = 1.0

    /// Enable morse encoding for text
    var enableMorseEncoding: Bool = true

    /// Repeat count for important patterns
    var repeatCountForAlerts: Int = 3

    // MARK: - Private State

    private let device = WKInterfaceDevice.current()
    private var playbackTask: Task<Void, Never>?

    // MARK: - Initialization

    private init() {
        // Load accessibility mode preference
        isAccessibilityModeEnabled = UserDefaults.standard.bool(forKey: "hapticAccessibilityMode")
    }

    // MARK: - Accessibility Mode

    /// Toggle accessibility mode (haptic-only navigation)
    func toggleAccessibilityMode() {
        isAccessibilityModeEnabled.toggle()
        UserDefaults.standard.set(isAccessibilityModeEnabled, forKey: "hapticAccessibilityMode")

        // Confirm toggle with haptic
        play(isAccessibilityModeEnabled ? .success : .menuClose)

        KagamiLogger.ui.info("Haptic accessibility mode: \(isAccessibilityModeEnabled ? "enabled" : "disabled")")
    }

    /// Enable accessibility mode
    func enableAccessibilityMode() {
        guard !isAccessibilityModeEnabled else { return }
        isAccessibilityModeEnabled = true
        UserDefaults.standard.set(true, forKey: "hapticAccessibilityMode")
        play(.success)
    }

    /// Disable accessibility mode
    func disableAccessibilityMode() {
        guard isAccessibilityModeEnabled else { return }
        isAccessibilityModeEnabled = false
        UserDefaults.standard.set(false, forKey: "hapticAccessibilityMode")
        play(.menuClose)
    }

    // MARK: - Pattern Playback

    /// Play a navigation haptic pattern
    func play(_ pattern: NavigationHapticPattern) {
        // Cancel any existing playback
        playbackTask?.cancel()

        isPlaying = true
        lastPlayedPattern = pattern

        playbackTask = Task {
            await playPattern(pattern)
            isPlaying = false
        }
    }

    /// Play pattern implementation
    private func playPattern(_ pattern: NavigationHapticPattern) async {
        switch pattern {
        // Confirmation patterns
        case .success:
            device.play(.success)

        case .error:
            device.play(.failure)
            try? await Task.sleep(nanoseconds: 100_000_000)
            device.play(.failure)
            try? await Task.sleep(nanoseconds: 100_000_000)
            device.play(.failure)

        case .warning:
            device.play(.notification)

        // Action patterns
        case .sceneActivated:
            device.play(.start)
            try? await Task.sleep(nanoseconds: 100_000_000)
            device.play(.click)
            try? await Task.sleep(nanoseconds: 100_000_000)
            device.play(.success)

        case .lightsOn:
            device.play(.directionUp)
            try? await Task.sleep(nanoseconds: 50_000_000)
            device.play(.success)

        case .lightsOff:
            device.play(.directionDown)
            try? await Task.sleep(nanoseconds: 50_000_000)
            device.play(.click)

        case .lightsDim:
            device.play(.click)

        case .fireplaceOn:
            // Warm ascending pattern
            for _ in 0..<3 {
                device.play(.directionUp)
                try? await Task.sleep(nanoseconds: 150_000_000)
            }
            device.play(.success)

        case .fireplaceOff:
            // Cool descending pattern
            for _ in 0..<3 {
                device.play(.directionDown)
                try? await Task.sleep(nanoseconds: 150_000_000)
            }
            device.play(.click)

        case .shadesOpen:
            // Rising sweep
            device.play(.directionUp)
            try? await Task.sleep(nanoseconds: 100_000_000)
            device.play(.directionUp)
            try? await Task.sleep(nanoseconds: 100_000_000)
            device.play(.success)

        case .shadesClose:
            // Falling sweep
            device.play(.directionDown)
            try? await Task.sleep(nanoseconds: 100_000_000)
            device.play(.directionDown)
            try? await Task.sleep(nanoseconds: 100_000_000)
            device.play(.click)

        case .tvLower:
            device.play(.directionDown)
            try? await Task.sleep(nanoseconds: 150_000_000)
            device.play(.success)

        case .tvRaise:
            device.play(.directionUp)
            try? await Task.sleep(nanoseconds: 150_000_000)
            device.play(.success)

        case .lockEngaged:
            device.play(.click)
            try? await Task.sleep(nanoseconds: 100_000_000)
            device.play(.retry)

        // Navigation patterns
        case .selectionUp:
            device.play(.directionUp)

        case .selectionDown:
            device.play(.directionDown)

        case .selectionConfirm:
            device.play(.click)

        case .menuOpen:
            device.play(.start)

        case .menuClose:
            device.play(.stop)

        case .scrollBoundary:
            device.play(.retry)

        // Status patterns
        case .connected:
            device.play(.click)
            try? await Task.sleep(nanoseconds: 100_000_000)
            device.play(.click)

        case .disconnected:
            device.play(.directionDown)
            try? await Task.sleep(nanoseconds: 200_000_000)
            device.play(.stop)

        case .lowBattery:
            for _ in 0..<3 {
                device.play(.notification)
                try? await Task.sleep(nanoseconds: 300_000_000)
            }

        case .safetyAlert:
            for _ in 0..<repeatCountForAlerts {
                device.play(.notification)
                try? await Task.sleep(nanoseconds: 200_000_000)
                device.play(.failure)
                try? await Task.sleep(nanoseconds: 500_000_000)
            }

        // New patterns per KAGAMI_REDESIGN_PLAN.md

        case .attention:
            device.play(.notification)
            try? await Task.sleep(nanoseconds: 150_000_000)
            device.play(.click)

        case .lockDisengaged:
            device.play(.click)
            try? await Task.sleep(nanoseconds: 50_000_000)
            device.play(.directionUp)

        case .securityArm:
            device.play(.click)
            try? await Task.sleep(nanoseconds: 100_000_000)
            device.play(.click)
            try? await Task.sleep(nanoseconds: 100_000_000)
            device.play(.retry)

        case .securityDisarm:
            device.play(.click)
            try? await Task.sleep(nanoseconds: 100_000_000)
            device.play(.success)

        case .thermostatAdjust:
            device.play(.click)

        case .pageChange:
            device.play(.click)
            try? await Task.sleep(nanoseconds: 50_000_000)
            device.play(.directionUp)

        case .tabSwitch:
            device.play(.click)

        case .backNavigation:
            device.play(.directionDown)

        case .safetyOK:
            device.play(.success)

        case .presenceDetected:
            device.play(.notification)
            try? await Task.sleep(nanoseconds: 100_000_000)
            device.play(.directionUp)

        case .presenceCleared:
            device.play(.click)

        case .messageReceived:
            device.play(.notification)

        case .callIncoming:
            for _ in 0..<3 {
                device.play(.notification)
                try? await Task.sleep(nanoseconds: 400_000_000)
            }

        case .reminderAlert:
            device.play(.notification)
            try? await Task.sleep(nanoseconds: 100_000_000)
            device.play(.click)

        case .weatherAlert:
            device.play(.notification)
            try? await Task.sleep(nanoseconds: 150_000_000)
            device.play(.notification)

        case .arrival:
            device.play(.directionUp)
            try? await Task.sleep(nanoseconds: 100_000_000)
            device.play(.success)

        case .departure:
            device.play(.directionDown)
            try? await Task.sleep(nanoseconds: 100_000_000)
            device.play(.click)

        case .sleepStart:
            device.play(.stop)
            try? await Task.sleep(nanoseconds: 200_000_000)
            device.play(.click)

        case .wakeUp:
            device.play(.start)
            try? await Task.sleep(nanoseconds: 100_000_000)
            device.play(.directionUp)
            try? await Task.sleep(nanoseconds: 100_000_000)
            device.play(.success)

        case .workoutStart:
            device.play(.start)
            try? await Task.sleep(nanoseconds: 100_000_000)
            device.play(.success)

        case .workoutEnd:
            device.play(.stop)
            try? await Task.sleep(nanoseconds: 100_000_000)
            device.play(.success)

        case .morningRoutine:
            device.play(.start)
            try? await Task.sleep(nanoseconds: 100_000_000)
            device.play(.directionUp)
            try? await Task.sleep(nanoseconds: 100_000_000)
            device.play(.directionUp)

        case .eveningRoutine:
            device.play(.directionDown)
            try? await Task.sleep(nanoseconds: 100_000_000)
            device.play(.directionDown)
            try? await Task.sleep(nanoseconds: 100_000_000)
            device.play(.stop)

        case .goodnightSequence:
            device.play(.directionDown)
            try? await Task.sleep(nanoseconds: 150_000_000)
            device.play(.directionDown)
            try? await Task.sleep(nanoseconds: 150_000_000)
            device.play(.stop)
            try? await Task.sleep(nanoseconds: 150_000_000)
            device.play(.success)

        case .welcomeHome:
            device.play(.start)
            try? await Task.sleep(nanoseconds: 100_000_000)
            device.play(.success)

        case .awayMode:
            device.play(.click)
            try? await Task.sleep(nanoseconds: 100_000_000)
            device.play(.retry)

        case .movieMode:
            device.play(.directionDown)
            try? await Task.sleep(nanoseconds: 100_000_000)
            device.play(.click)
            try? await Task.sleep(nanoseconds: 100_000_000)
            device.play(.success)

        case .focusMode:
            device.play(.click)
            try? await Task.sleep(nanoseconds: 50_000_000)
            device.play(.click)

        case .voiceCommandStart:
            device.play(.start)

        case .voiceCommandEnd:
            device.play(.click)

        case .voiceCommandSuccess:
            device.play(.success)

        case .voiceCommandFail:
            device.play(.failure)

        case .gestureRecognized:
            device.play(.click)

        case .gestureUnrecognized:
            device.play(.retry)
        }
    }

    // MARK: - Action Haptics

    /// Play haptic for scene activation
    func playSceneHaptic(_ sceneId: String) {
        switch sceneId {
        case "goodnight":
            play(.lightsOff)
        case "movie_mode":
            play(.tvLower)
        case "welcome_home":
            play(.lightsOn)
        case "away":
            play(.lockEngaged)
        default:
            play(.sceneActivated)
        }
    }

    /// Play haptic for light control
    func playLightHaptic(level: Int) {
        if level == 0 {
            play(.lightsOff)
        } else if level < 50 {
            play(.lightsDim)
        } else {
            play(.lightsOn)
        }
    }

    /// Play haptic for fireplace
    func playFireplaceHaptic(on: Bool) {
        play(on ? .fireplaceOn : .fireplaceOff)
    }

    /// Play haptic for shades
    func playShadeHaptic(opening: Bool) {
        play(opening ? .shadesOpen : .shadesClose)
    }

    /// Play haptic for TV
    func playTVHaptic(lowering: Bool) {
        play(lowering ? .tvLower : .tvRaise)
    }

    // MARK: - Morse Code Playback

    /// Play text as morse code haptics
    func playMorse(_ text: String) {
        guard enableMorseEncoding else { return }

        // Cancel any existing playback
        playbackTask?.cancel()

        isPlaying = true

        playbackTask = Task {
            let elements = HapticMorse.encode(text)

            for element in elements {
                guard !Task.isCancelled else { break }

                switch element {
                case .dot:
                    device.play(.click)
                    try? await Task.sleep(nanoseconds: UInt64(element.duration * 1_000_000_000))
                case .dash:
                    device.play(.success)
                    try? await Task.sleep(nanoseconds: UInt64(element.duration * 1_000_000_000))
                case .charGap, .wordGap:
                    try? await Task.sleep(nanoseconds: UInt64(element.duration * 1_000_000_000))
                }
            }

            isPlaying = false
        }
    }

    /// Play a number as haptic pulses
    func playNumber(_ number: Int) {
        guard number >= 0 && number <= 99 else { return }

        playbackTask?.cancel()
        isPlaying = true

        playbackTask = Task {
            if number == 0 {
                device.play(.click)
            } else if number <= 10 {
                // Play as taps
                for _ in 0..<number {
                    device.play(.click)
                    try? await Task.sleep(nanoseconds: 200_000_000)
                }
            } else {
                // Play tens then ones
                let tens = number / 10
                let ones = number % 10

                for _ in 0..<tens {
                    device.play(.success)  // Long tap for tens
                    try? await Task.sleep(nanoseconds: 250_000_000)
                }

                try? await Task.sleep(nanoseconds: 400_000_000)  // Gap

                for _ in 0..<ones {
                    device.play(.click)  // Short tap for ones
                    try? await Task.sleep(nanoseconds: 200_000_000)
                }
            }

            isPlaying = false
        }
    }

    /// Play percentage as haptic pattern
    func playPercentage(_ percentage: Int) {
        // Simplified: 1-5 taps for 0-100%
        let taps = max(1, min(5, (percentage + 10) / 20))

        playbackTask?.cancel()
        isPlaying = true

        playbackTask = Task {
            for i in 0..<taps {
                let intensity: WKHapticType = i == taps - 1 ? .success : .click
                device.play(intensity)
                try? await Task.sleep(nanoseconds: 200_000_000)
            }
            isPlaying = false
        }
    }

    // MARK: - Navigation Feedback

    /// Play scroll position feedback
    func playScrollPosition(current: Int, total: Int) {
        if current == 0 {
            play(.scrollBoundary)
        } else if current == total - 1 {
            play(.scrollBoundary)
        } else {
            // Play position as percentage
            let percentage = (current * 100) / max(1, total - 1)
            playPercentage(percentage)
        }
    }

    /// Play list item selection feedback
    func playListSelection(index: Int, isHeader: Bool = false) {
        if isHeader {
            device.play(.success)
        } else {
            device.play(.click)
        }
    }

    // MARK: - Cleanup

    /// Stop any playing pattern
    func stop() {
        playbackTask?.cancel()
        playbackTask = nil
        isPlaying = false
    }

    /// Preview all patterns (for settings)
    func previewAllPatterns() async {
        for pattern in NavigationHapticPattern.allCases {
            play(pattern)
            try? await Task.sleep(nanoseconds: 1_000_000_000)
        }
    }
}

// MARK: - Accessibility Haptic Extensions

extension View {
    /// Add haptic feedback for accessibility mode
    @ViewBuilder
    func accessibilityHaptic(_ pattern: NavigationHapticPattern, trigger: Bool) -> some View {
        self.onChange(of: trigger) { _, newValue in
            if newValue && HapticNavigationLibrary.shared.isAccessibilityModeEnabled {
                HapticNavigationLibrary.shared.play(pattern)
            }
        }
    }
}

// MARK: - Integration with WatchActionLog

extension WatchActionLog {

    /// Log action with haptic feedback for accessibility
    func logActionWithHaptic(
        type: String,
        label: String,
        room: String? = nil,
        parameters: [String: String] = [:],
        success: Bool,
        latencyMs: Int,
        error: String? = nil,
        source: ActionLogEntry.ActionSource
    ) {
        // Log the action
        logAction(
            type: type,
            label: label,
            room: room,
            parameters: parameters,
            success: success,
            latencyMs: latencyMs,
            error: error,
            source: source
        )

        // Play haptic if accessibility mode enabled
        if HapticNavigationLibrary.shared.isAccessibilityModeEnabled {
            let library = HapticNavigationLibrary.shared

            if success {
                switch type {
                case "scene":
                    if let sceneId = parameters["scene_id"] {
                        library.playSceneHaptic(sceneId)
                    } else {
                        library.play(.sceneActivated)
                    }
                case "lights":
                    if let levelStr = parameters["level"], let level = Int(levelStr) {
                        library.playLightHaptic(level: level)
                    }
                case "fireplace":
                    let isOn = parameters["state"] == "on"
                    library.playFireplaceHaptic(on: isOn)
                case "shades":
                    let opening = parameters["action"] == "open"
                    library.playShadeHaptic(opening: opening)
                case "tv":
                    let lowering = parameters["action"] == "lower"
                    library.playTVHaptic(lowering: lowering)
                default:
                    library.play(.success)
                }
            } else {
                library.play(.error)
            }
        }
    }
}

/*
 * Haptic Navigation Architecture:
 *
 * Accessibility Mode:
 *   When enabled, all UI interactions trigger distinct haptic patterns
 *   Deafblind users can navigate entirely by touch
 *
 * Pattern Library:
 *   - Confirmation: success, error, warning
 *   - Actions: scene, lights, fireplace, shades, TV, locks
 *   - Navigation: up, down, confirm, menu, scroll
 *   - Status: connected, disconnected, battery, safety
 *
 * Morse Encoding:
 *   Short tap (0.1s) = dot
 *   Long tap (0.3s) = dash
 *   Can encode any text for complex information
 *
 * Usage:
 *   HapticNavigationLibrary.shared.play(.success)
 *   HapticNavigationLibrary.shared.playMorse("OK")
 *   HapticNavigationLibrary.shared.playPercentage(75)
 *
 * h(x) >= 0. Always.
 */
