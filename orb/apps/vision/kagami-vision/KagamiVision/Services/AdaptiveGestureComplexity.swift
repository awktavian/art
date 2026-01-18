//
// AdaptiveGestureComplexity.swift — Adaptive Gesture Learning System
//
// Colony: Grove (e6) — Learning
//
// P2 FIX: Adaptive gesture complexity based on user skill
//
// Features:
//   - Skill level detection from performance metrics
//   - Progressive gesture unlocking
//   - Simplified mode for beginners
//   - Expert shortcuts for power users
//   - Automatic complexity adjustment
//   - Gesture tutorials and hints
//
// Architecture:
//   GesturePerformance → SkillAssessor → ComplexityController → GestureSet
//                                      → TutorialManager → UI Hints
//                                      → UnlockManager → Achievements
//
// Skill Levels:
//   - Novice: Basic taps and pinches only
//   - Beginner: + swipes
//   - Intermediate: + drag, hold, two-finger
//   - Advanced: + two-hand, rotation
//   - Expert: + complex combos, shortcuts
//
// Created: January 2, 2026
// 鏡

import Foundation
import Combine

// MARK: - Skill Level

/// User skill level for gesture complexity
enum GestureSkillLevel: Int, CaseIterable, Codable {
    case novice = 0
    case beginner = 1
    case intermediate = 2
    case advanced = 3
    case expert = 4

    var displayName: String {
        switch self {
        case .novice: return String(localized: "skill.novice")
        case .beginner: return String(localized: "skill.beginner")
        case .intermediate: return String(localized: "skill.intermediate")
        case .advanced: return String(localized: "skill.advanced")
        case .expert: return String(localized: "skill.expert")
        }
    }

    var description: String {
        switch self {
        case .novice: return String(localized: "skill.novice.description")
        case .beginner: return String(localized: "skill.beginner.description")
        case .intermediate: return String(localized: "skill.intermediate.description")
        case .advanced: return String(localized: "skill.advanced.description")
        case .expert: return String(localized: "skill.expert.description")
        }
    }

    /// Required successful gestures to advance
    var advancementThreshold: Int {
        switch self {
        case .novice: return 20
        case .beginner: return 40
        case .intermediate: return 80
        case .advanced: return 150
        case .expert: return Int.max
        }
    }

    /// Required success rate to advance
    var requiredSuccessRate: Float {
        switch self {
        case .novice: return 0.6
        case .beginner: return 0.7
        case .intermediate: return 0.75
        case .advanced: return 0.8
        case .expert: return 1.0
        }
    }

    /// Success rate that triggers demotion
    var demotionThreshold: Float {
        switch self {
        case .novice: return 0.0  // Can't go lower
        case .beginner: return 0.4
        case .intermediate: return 0.5
        case .advanced: return 0.55
        case .expert: return 0.6
        }
    }

    var next: GestureSkillLevel? {
        GestureSkillLevel(rawValue: rawValue + 1)
    }

    var previous: GestureSkillLevel? {
        GestureSkillLevel(rawValue: rawValue - 1)
    }
}

// MARK: - Gesture Complexity

/// Gesture complexity tier
enum GestureComplexity: Int, Comparable, CaseIterable {
    case basic = 0      // Tap, simple pinch
    case simple = 1     // Swipes, hold
    case moderate = 2   // Drag, two-finger
    case complex = 3    // Two-hand gestures
    case expert = 4     // Combos, shortcuts

    static func < (lhs: GestureComplexity, rhs: GestureComplexity) -> Bool {
        lhs.rawValue < rhs.rawValue
    }

    /// Gestures available at this complexity level
    var availableGestures: Set<SpatialGestureRecognizer.RecognizedGesture> {
        switch self {
        case .basic:
            return [.tap, .pinch]
        case .simple:
            return [.tap, .pinch, .swipeUp, .swipeDown, .swipeLeft, .swipeRight, .pinchHold]
        case .moderate:
            return [.tap, .pinch, .swipeUp, .swipeDown, .swipeLeft, .swipeRight,
                    .pinchHold, .pinchDrag, .point, .openPalm, .fist]
        case .complex:
            return [.tap, .pinch, .swipeUp, .swipeDown, .swipeLeft, .swipeRight,
                    .pinchHold, .pinchDrag, .point, .openPalm, .fist,
                    .twoHandSpread, .twoHandPinch, .rotate]
        case .expert:
            return Set(SpatialGestureRecognizer.RecognizedGesture.allCases)
        }
    }

    /// Required skill level for this complexity
    var requiredSkillLevel: GestureSkillLevel {
        switch self {
        case .basic: return .novice
        case .simple: return .beginner
        case .moderate: return .intermediate
        case .complex: return .advanced
        case .expert: return .expert
        }
    }
}

// MARK: - Gesture Performance

/// Tracks performance metrics for a specific gesture
struct GesturePerformance: Codable {
    let gesture: String  // RecognizedGesture raw value
    var attempts: Int = 0
    var successes: Int = 0
    var averageConfidence: Float = 0
    var lastAttempt: Date?
    var bestConfidence: Float = 0
    var consecutiveSuccesses: Int = 0
    var consecutiveFailures: Int = 0

    var successRate: Float {
        attempts > 0 ? Float(successes) / Float(attempts) : 0
    }

    var isMastered: Bool {
        successRate >= 0.9 && attempts >= 20
    }

    mutating func recordAttempt(success: Bool, confidence: Float) {
        attempts += 1
        lastAttempt = Date()

        if success {
            successes += 1
            consecutiveSuccesses += 1
            consecutiveFailures = 0
            bestConfidence = max(bestConfidence, confidence)
        } else {
            consecutiveSuccesses = 0
            consecutiveFailures += 1
        }

        // Update running average
        let alpha: Float = 0.1
        averageConfidence = averageConfidence * (1 - alpha) + confidence * alpha
    }
}

// MARK: - Adaptive Gesture Complexity Controller

/// Main controller for adaptive gesture complexity
@MainActor
final class AdaptiveGestureComplexity: ObservableObject {

    // MARK: - Published State

    @Published private(set) var currentSkillLevel: GestureSkillLevel = .novice
    @Published private(set) var currentComplexity: GestureComplexity = .basic
    @Published private(set) var availableGestures: Set<SpatialGestureRecognizer.RecognizedGesture> = []
    @Published private(set) var lockedGestures: Set<SpatialGestureRecognizer.RecognizedGesture> = []
    @Published private(set) var recentlyUnlocked: [SpatialGestureRecognizer.RecognizedGesture] = []
    @Published private(set) var overallSuccessRate: Float = 0
    @Published private(set) var totalGestures: Int = 0

    // Tutorial state
    @Published var showTutorial = false
    @Published var currentTutorialGesture: SpatialGestureRecognizer.RecognizedGesture?
    @Published var pendingTutorials: [SpatialGestureRecognizer.RecognizedGesture] = []

    // Settings
    @Published var adaptiveMode = true
    @Published var manualSkillLevel: GestureSkillLevel?
    @Published var showGestureHints = true

    // MARK: - Internal State

    private var gesturePerformance: [String: GesturePerformance] = [:]
    private var sessionStats = SessionStats()
    private var cancellables = Set<AnyCancellable>()

    private let userDefaultsKey = "kagami.gesture.adaptiveComplexity"

    // MARK: - Types

    struct SessionStats: Codable {
        var sessionStart: Date = Date()
        var totalAttempts: Int = 0
        var totalSuccesses: Int = 0
        var gesturesUsed: Set<String> = []
        var peakSuccessRate: Float = 0

        var successRate: Float {
            totalAttempts > 0 ? Float(totalSuccesses) / Float(totalAttempts) : 0
        }
    }

    // MARK: - Init

    init() {
        loadState()
        updateAvailableGestures()
    }

    // MARK: - State Persistence

    private func loadState() {
        if let data = UserDefaults.standard.data(forKey: userDefaultsKey),
           let state = try? JSONDecoder().decode(PersistedState.self, from: data) {
            currentSkillLevel = state.skillLevel
            currentComplexity = GestureComplexity(rawValue: state.skillLevel.rawValue) ?? .basic
            gesturePerformance = state.performance
            totalGestures = state.totalGestures
        }
    }

    private func saveState() {
        let state = PersistedState(
            skillLevel: currentSkillLevel,
            performance: gesturePerformance,
            totalGestures: totalGestures
        )
        if let data = try? JSONEncoder().encode(state) {
            UserDefaults.standard.set(data, forKey: userDefaultsKey)
        }
    }

    struct PersistedState: Codable {
        let skillLevel: GestureSkillLevel
        let performance: [String: GesturePerformance]
        let totalGestures: Int
    }

    // MARK: - Gesture Recording

    /// Records a gesture attempt
    func recordGestureAttempt(
        _ gesture: SpatialGestureRecognizer.RecognizedGesture,
        success: Bool,
        confidence: Float
    ) {
        let key = gesture.rawValue

        // Update performance for this gesture
        if gesturePerformance[key] == nil {
            gesturePerformance[key] = GesturePerformance(gesture: key)
        }
        gesturePerformance[key]?.recordAttempt(success: success, confidence: confidence)

        // Update session stats
        sessionStats.totalAttempts += 1
        if success {
            sessionStats.totalSuccesses += 1
        }
        sessionStats.gesturesUsed.insert(key)
        sessionStats.peakSuccessRate = max(sessionStats.peakSuccessRate, sessionStats.successRate)

        // Update overall stats
        totalGestures += 1
        let allSuccesses = gesturePerformance.values.reduce(0) { $0 + $1.successes }
        let allAttempts = gesturePerformance.values.reduce(0) { $0 + $1.attempts }
        overallSuccessRate = allAttempts > 0 ? Float(allSuccesses) / Float(allAttempts) : 0

        // Check for skill level changes
        if adaptiveMode {
            evaluateSkillLevel()
        }

        // Save state
        saveState()
    }

    // MARK: - Skill Level Management

    /// Evaluates and potentially adjusts skill level
    private func evaluateSkillLevel() {
        let level = currentSkillLevel

        // Check for advancement
        if let next = level.next {
            let meetsThreshold = totalGestures >= level.advancementThreshold
            let meetsRate = overallSuccessRate >= level.requiredSuccessRate

            if meetsThreshold && meetsRate {
                advanceToLevel(next)
                return
            }
        }

        // Check for demotion
        if let previous = level.previous {
            // Only demote if clearly struggling
            let recentPerformance = calculateRecentPerformance()
            if recentPerformance < level.demotionThreshold && sessionStats.totalAttempts >= 10 {
                demoteToLevel(previous)
            }
        }
    }

    private func calculateRecentPerformance() -> Float {
        // Calculate success rate from recent attempts only
        let recentAttempts = sessionStats.totalAttempts
        let recentSuccesses = sessionStats.totalSuccesses
        return recentAttempts > 0 ? Float(recentSuccesses) / Float(recentAttempts) : 0
    }

    private func advanceToLevel(_ level: GestureSkillLevel) {
        let oldLevel = currentSkillLevel
        currentSkillLevel = level
        currentComplexity = GestureComplexity(rawValue: level.rawValue) ?? currentComplexity

        // Find newly unlocked gestures
        let oldGestures = GestureComplexity(rawValue: oldLevel.rawValue)?.availableGestures ?? []
        let newGestures = currentComplexity.availableGestures.subtracting(oldGestures)

        recentlyUnlocked = Array(newGestures)
        pendingTutorials.append(contentsOf: newGestures)

        updateAvailableGestures()

        print("Advanced to \(level.displayName)! Unlocked: \(newGestures)")

        // Notify
        NotificationCenter.default.post(
            name: .skillLevelAdvanced,
            object: self,
            userInfo: ["level": level, "unlocked": newGestures]
        )
    }

    private func demoteToLevel(_ level: GestureSkillLevel) {
        currentSkillLevel = level
        currentComplexity = GestureComplexity(rawValue: level.rawValue) ?? currentComplexity

        updateAvailableGestures()

        print("Adjusted to \(level.displayName)")

        // Notify
        NotificationCenter.default.post(
            name: .skillLevelAdjusted,
            object: self,
            userInfo: ["level": level]
        )
    }

    /// Sets skill level manually
    func setSkillLevel(_ level: GestureSkillLevel) {
        manualSkillLevel = level
        currentSkillLevel = level
        currentComplexity = GestureComplexity(rawValue: level.rawValue) ?? .basic
        updateAvailableGestures()
        saveState()
    }

    /// Returns to adaptive mode
    func enableAdaptiveMode() {
        manualSkillLevel = nil
        adaptiveMode = true
        evaluateSkillLevel()
    }

    // MARK: - Available Gestures

    private func updateAvailableGestures() {
        let effectiveLevel = manualSkillLevel ?? currentSkillLevel
        let effectiveComplexity = GestureComplexity(rawValue: effectiveLevel.rawValue) ?? currentComplexity

        availableGestures = effectiveComplexity.availableGestures
        lockedGestures = Set(SpatialGestureRecognizer.RecognizedGesture.allCases).subtracting(availableGestures)
    }

    /// Checks if a gesture is currently available
    func isGestureAvailable(_ gesture: SpatialGestureRecognizer.RecognizedGesture) -> Bool {
        availableGestures.contains(gesture)
    }

    /// Gets the complexity tier of a gesture
    func gestureComplexity(_ gesture: SpatialGestureRecognizer.RecognizedGesture) -> GestureComplexity {
        for complexity in GestureComplexity.allCases.reversed() {
            if complexity.availableGestures.contains(gesture) {
                return complexity
            }
        }
        return .expert
    }

    /// Gets the skill level required to unlock a gesture
    func requiredLevelForGesture(_ gesture: SpatialGestureRecognizer.RecognizedGesture) -> GestureSkillLevel {
        gestureComplexity(gesture).requiredSkillLevel
    }

    // MARK: - Tutorial Management

    /// Starts tutorial for the next pending gesture
    func startNextTutorial() {
        guard let gesture = pendingTutorials.first else {
            showTutorial = false
            currentTutorialGesture = nil
            return
        }

        currentTutorialGesture = gesture
        showTutorial = true
    }

    /// Completes the current tutorial
    func completeTutorial() {
        if let gesture = currentTutorialGesture {
            pendingTutorials.removeAll { $0 == gesture }
            recentlyUnlocked.removeAll { $0 == gesture }
        }

        startNextTutorial()
    }

    /// Skips the current tutorial
    func skipTutorial() {
        completeTutorial()
    }

    /// Skips all tutorials
    func skipAllTutorials() {
        pendingTutorials.removeAll()
        recentlyUnlocked.removeAll()
        showTutorial = false
        currentTutorialGesture = nil
    }

    // MARK: - Hints

    /// Gets hint for a gesture
    func gestureHint(_ gesture: SpatialGestureRecognizer.RecognizedGesture) -> GestureHint? {
        guard showGestureHints else { return nil }

        let performance = gesturePerformance[gesture.rawValue]

        // Show hint if struggling with gesture
        if let perf = performance, perf.consecutiveFailures >= 3 {
            return GestureHint(
                gesture: gesture,
                type: .struggling,
                message: String(localized: "hint.struggling \(gesture.displayName)")
            )
        }

        // Show hint for new gestures
        if recentlyUnlocked.contains(gesture) {
            return GestureHint(
                gesture: gesture,
                type: .newlyUnlocked,
                message: String(localized: "hint.new \(gesture.displayName)")
            )
        }

        return nil
    }

    struct GestureHint {
        let gesture: SpatialGestureRecognizer.RecognizedGesture
        let type: HintType
        let message: String

        enum HintType {
            case newlyUnlocked
            case struggling
            case tip
        }
    }

    // MARK: - Expert Shortcuts

    /// Gets available shortcuts for current skill level
    func availableShortcuts() -> [GestureShortcut] {
        guard currentSkillLevel == .expert else { return [] }

        return [
            GestureShortcut(
                name: String(localized: "shortcut.quickscene"),
                gesture: .thumbsUp,
                description: String(localized: "shortcut.quickscene.description")
            ),
            GestureShortcut(
                name: String(localized: "shortcut.alloff"),
                gesture: .fist,
                description: String(localized: "shortcut.alloff.description")
            ),
            GestureShortcut(
                name: String(localized: "shortcut.roomscan"),
                gesture: .twoHandRotate,
                description: String(localized: "shortcut.roomscan.description")
            )
        ]
    }

    struct GestureShortcut {
        let name: String
        let gesture: SpatialGestureRecognizer.RecognizedGesture
        let description: String
    }

    // MARK: - Statistics

    /// Gets detailed statistics for all gestures
    func getAllStats() -> [GesturePerformance] {
        Array(gesturePerformance.values).sorted { $0.attempts > $1.attempts }
    }

    /// Gets the most used gestures
    func topGestures(count: Int = 5) -> [GesturePerformance] {
        Array(getAllStats().prefix(count))
    }

    /// Gets gestures that need practice
    func gesturesNeedingPractice() -> [SpatialGestureRecognizer.RecognizedGesture] {
        gesturePerformance.values
            .filter { $0.successRate < 0.7 && $0.attempts >= 5 }
            .compactMap { SpatialGestureRecognizer.RecognizedGesture(rawValue: $0.gesture) }
    }

    /// Resets all progress
    func resetProgress() {
        gesturePerformance.removeAll()
        currentSkillLevel = .novice
        currentComplexity = .basic
        totalGestures = 0
        overallSuccessRate = 0
        sessionStats = SessionStats()
        updateAvailableGestures()
        saveState()
    }

    /// Resets session stats only
    func resetSession() {
        sessionStats = SessionStats()
    }
}

// MARK: - Gesture Display Name Extension

extension SpatialGestureRecognizer.RecognizedGesture {
    var displayName: String {
        switch self {
        case .tap: return String(localized: "gesture.tap")
        case .pinch: return String(localized: "gesture.pinch")
        case .pinchHold: return String(localized: "gesture.pinchhold")
        case .pinchDrag: return String(localized: "gesture.pinchdrag")
        case .swipeUp: return String(localized: "gesture.swipeup")
        case .swipeDown: return String(localized: "gesture.swipedown")
        case .swipeLeft: return String(localized: "gesture.swipeleft")
        case .swipeRight: return String(localized: "gesture.swiperight")
        case .point: return String(localized: "gesture.point")
        case .openPalm: return String(localized: "gesture.openpalm")
        case .fist: return String(localized: "gesture.fist")
        case .thumbsUp: return String(localized: "gesture.thumbsup")
        case .rotate: return String(localized: "gesture.rotate")
        case .twoHandSpread: return String(localized: "gesture.twohandspread")
        case .twoHandPinch: return String(localized: "gesture.twohandpinch")
        case .twoHandRotate: return String(localized: "gesture.twohandrotate")
        case .none: return String(localized: "gesture.none")
        }
    }

    var tutorialDescription: String {
        switch self {
        case .tap: return String(localized: "tutorial.tap")
        case .pinch: return String(localized: "tutorial.pinch")
        case .pinchHold: return String(localized: "tutorial.pinchhold")
        case .pinchDrag: return String(localized: "tutorial.pinchdrag")
        case .swipeUp: return String(localized: "tutorial.swipeup")
        case .swipeDown: return String(localized: "tutorial.swipedown")
        case .swipeLeft: return String(localized: "tutorial.swipeleft")
        case .swipeRight: return String(localized: "tutorial.swiperight")
        case .point: return String(localized: "tutorial.point")
        case .openPalm: return String(localized: "tutorial.openpalm")
        case .fist: return String(localized: "tutorial.fist")
        case .thumbsUp: return String(localized: "tutorial.thumbsup")
        case .rotate: return String(localized: "tutorial.rotate")
        case .twoHandSpread: return String(localized: "tutorial.twohandspread")
        case .twoHandPinch: return String(localized: "tutorial.twohandpinch")
        case .twoHandRotate: return String(localized: "tutorial.twohandrotate")
        case .none: return ""
        }
    }
}

// MARK: - Notification Names

extension Notification.Name {
    static let skillLevelAdvanced = Notification.Name("kagami.gesture.skillLevelAdvanced")
    static let skillLevelAdjusted = Notification.Name("kagami.gesture.skillLevelAdjusted")
    static let gestureUnlocked = Notification.Name("kagami.gesture.gestureUnlocked")
}

// MARK: - SwiftUI Views

import SwiftUI

/// Skill level indicator view
struct SkillLevelIndicator: View {
    @EnvironmentObject var complexity: AdaptiveGestureComplexity

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: skillIcon)
                .foregroundColor(skillColor)

            VStack(alignment: .leading, spacing: 2) {
                Text(complexity.currentSkillLevel.displayName)
                    .font(.caption.bold())

                // Progress to next level
                if complexity.currentSkillLevel != .expert {
                    ProgressView(value: progress)
                        .progressViewStyle(.linear)
                        .frame(width: 60)
                }
            }
        }
        .padding(8)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 8))
    }

    private var skillIcon: String {
        switch complexity.currentSkillLevel {
        case .novice: return "star"
        case .beginner: return "star.leadinghalf.filled"
        case .intermediate: return "star.fill"
        case .advanced: return "star.circle.fill"
        case .expert: return "crown.fill"
        }
    }

    private var skillColor: Color {
        switch complexity.currentSkillLevel {
        case .novice: return .secondary
        case .beginner: return .blue
        case .intermediate: return .green
        case .advanced: return .orange
        case .expert: return .purple
        }
    }

    private var progress: Double {
        let threshold = Double(complexity.currentSkillLevel.advancementThreshold)
        return min(1.0, Double(complexity.totalGestures) / threshold)
    }
}

/// Gesture unlock celebration view
struct GestureUnlockView: View {
    let gesture: SpatialGestureRecognizer.RecognizedGesture
    let onDismiss: () -> Void

    @State private var scale: CGFloat = 0.5
    @State private var opacity: Double = 0

    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "sparkles")
                .font(.system(size: 48))
                .foregroundColor(.yellow)

            Text(String(localized: "unlock.title"))
                .font(.headline)

            Text(gesture.displayName)
                .font(.title2.bold())
                .foregroundColor(.crystal)

            Text(gesture.tutorialDescription)
                .font(.caption)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal)

            Button(String(localized: "unlock.continue"), action: onDismiss)
                .buttonStyle(.borderedProminent)
        }
        .padding(24)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 16))
        .scaleEffect(scale)
        .opacity(opacity)
        .onAppear {
            withAnimation(.spring(response: 0.5, dampingFraction: 0.7)) {
                scale = 1.0
                opacity = 1.0
            }
        }
    }
}

/*
 * 鏡
 * h(x) >= 0. Always.
 *
 * The novice learns to tap.
 * The beginner discovers swipes.
 * The intermediate masters drag.
 * The advanced wields two hands.
 * The expert commands all.
 *
 * Each gesture unlocked is a new word
 * in the language of spatial control.
 */
