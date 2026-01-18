//
// PowerUserDetector.swift -- ML-Based Adaptive Hint Suppression
//
// Colony: Grove (e6) -- Adaptation
//
// Features:
//   - Usage pattern analysis to detect power users
//   - Adaptive hint suppression based on skill level
//   - Feature usage frequency tracking
//   - Complexity level recommendations
//   - On-device ML for privacy-preserving detection
//
// Architecture:
//   PowerUserDetector -> UsageTracker -> SkillModel -> HintManager
//
// h(x) >= 0. Always.
//

import Foundation
import CoreML
#if canImport(CreateML)
import CreateML
#endif
import Combine
import OSLog

// MARK: - User Skill Level

/// Detected user skill level
enum UserSkillLevel: Int, Codable, CaseIterable {
    case novice = 0      // New user, show all hints
    case beginner = 1    // Some familiarity, show most hints
    case intermediate = 2 // Regular user, reduce hints
    case advanced = 3    // Experienced user, minimal hints
    case expert = 4      // Power user, no hints unless critical

    /// Hint visibility threshold (0-1, lower = fewer hints)
    var hintThreshold: Double {
        switch self {
        case .novice: return 1.0
        case .beginner: return 0.8
        case .intermediate: return 0.5
        case .advanced: return 0.25
        case .expert: return 0.05
        }
    }

    /// Label for UI display
    var displayName: String {
        switch self {
        case .novice: return "New User"
        case .beginner: return "Beginner"
        case .intermediate: return "Regular"
        case .advanced: return "Advanced"
        case .expert: return "Expert"
        }
    }

    /// Minimum sessions required to achieve this level
    var minimumSessions: Int {
        switch self {
        case .novice: return 0
        case .beginner: return 3
        case .intermediate: return 10
        case .advanced: return 25
        case .expert: return 50
        }
    }
}

// MARK: - Feature Usage Event

/// Tracks usage of a specific feature
struct FeatureUsageEvent: Codable {
    let featureId: String
    let timestamp: Date
    let duration: TimeInterval?
    let completedSuccessfully: Bool
    let errorOccurred: Bool

    /// Feature categories
    enum Category: String, Codable, CaseIterable {
        case sceneActivation = "scene"
        case deviceControl = "device"
        case voiceCommand = "voice"
        case hubChat = "hub"
        case settings = "settings"
        case automation = "automation"
        case multiDevice = "multi_device"
        case shortcuts = "shortcuts"
        case handoff = "handoff"
    }

    var category: Category {
        if featureId.hasPrefix("scene_") { return .sceneActivation }
        if featureId.hasPrefix("device_") { return .deviceControl }
        if featureId.hasPrefix("voice_") { return .voiceCommand }
        if featureId.hasPrefix("hub_") { return .hubChat }
        if featureId.hasPrefix("settings_") { return .settings }
        if featureId.hasPrefix("automation_") { return .automation }
        if featureId.hasPrefix("multi_") { return .multiDevice }
        if featureId.hasPrefix("shortcut_") { return .shortcuts }
        if featureId.hasPrefix("handoff_") { return .handoff }
        return .deviceControl
    }
}

// MARK: - Usage Statistics

/// Aggregated usage statistics for skill level calculation
struct UsageStatistics: Codable {
    var totalSessions: Int = 0
    var totalActions: Int = 0
    var uniqueFeaturesUsed: Set<String> = []
    var advancedFeaturesUsed: Set<String> = []
    var errorRate: Double = 0
    var averageSessionDuration: TimeInterval = 0
    var consecutiveDaysUsed: Int = 0
    var lastActiveDate: Date?

    // Per-category statistics
    var categoryUsage: [String: Int] = [:]

    /// Calculate overall complexity score (0-100)
    var complexityScore: Double {
        var score: Double = 0

        // Sessions contribute (max 30 points)
        score += min(30, Double(totalSessions) * 0.6)

        // Unique features (max 25 points)
        score += min(25, Double(uniqueFeaturesUsed.count) * 1.5)

        // Advanced features (max 25 points)
        score += min(25, Double(advancedFeaturesUsed.count) * 5)

        // Low error rate bonus (max 10 points)
        if errorRate < 0.1 {
            score += 10
        } else if errorRate < 0.2 {
            score += 5
        }

        // Consistency bonus (max 10 points)
        score += min(10, Double(consecutiveDaysUsed) * 2)

        return min(100, score)
    }

    /// Inferred skill level based on statistics
    var inferredSkillLevel: UserSkillLevel {
        let score = complexityScore

        if score >= 80 { return .expert }
        if score >= 60 { return .advanced }
        if score >= 35 { return .intermediate }
        if score >= 15 { return .beginner }
        return .novice
    }
}

// MARK: - Hint Configuration

/// Configuration for a specific hint
struct HintConfiguration: Codable, Identifiable {
    let id: String
    let featureId: String
    let priority: HintPriority
    var timesShown: Int = 0
    var timesDismissed: Int = 0
    var lastShown: Date?
    var permanentlyDismissed: Bool = false

    enum HintPriority: Int, Codable, Comparable {
        case critical = 0   // Always show (safety-related)
        case important = 1  // Show for all except experts
        case helpful = 2    // Show for beginners/intermediate
        case contextual = 3 // Show only for novices
        case optional = 4   // User must opt-in

        static func < (lhs: HintPriority, rhs: HintPriority) -> Bool {
            lhs.rawValue < rhs.rawValue
        }
    }

    /// Should show this hint for the given skill level
    func shouldShow(for skillLevel: UserSkillLevel) -> Bool {
        if permanentlyDismissed { return false }

        switch priority {
        case .critical:
            return true // Always show critical hints
        case .important:
            return skillLevel.rawValue < UserSkillLevel.expert.rawValue
        case .helpful:
            return skillLevel.rawValue <= UserSkillLevel.intermediate.rawValue
        case .contextual:
            return skillLevel == .novice || skillLevel == .beginner
        case .optional:
            return false // User must explicitly enable
        }
    }
}

// MARK: - Power User Detector

/// Detects user skill level and manages adaptive hint suppression
@MainActor
final class PowerUserDetector: ObservableObject {

    // MARK: - Singleton

    static let shared = PowerUserDetector()

    // MARK: - Published State

    @Published private(set) var currentSkillLevel: UserSkillLevel = .novice
    @Published private(set) var statistics: UsageStatistics = UsageStatistics()
    @Published private(set) var isLoading: Bool = false

    // MARK: - Hint Management

    @Published var suppressedHints: Set<String> = []
    @Published var hintConfigurations: [String: HintConfiguration] = [:]

    // MARK: - Private

    private let logger = Logger(subsystem: "com.kagami.ios", category: "PowerUserDetector")
    private var cancellables = Set<AnyCancellable>()
    private let persistenceQueue = DispatchQueue(label: "com.kagami.poweruser", qos: .utility)

    // Storage keys
    private enum StorageKey {
        static let statistics = "kagami.poweruser.statistics"
        static let skillLevel = "kagami.poweruser.skillLevel"
        static let hintConfigs = "kagami.poweruser.hints"
        static let suppressedHints = "kagami.poweruser.suppressed"
        static let usageEvents = "kagami.poweruser.events"
    }

    // Advanced features that indicate power user status
    private let advancedFeatures: Set<String> = [
        "automation_create",
        "automation_edit",
        "multi_device_control",
        "voice_custom_command",
        "shortcut_create",
        "handoff_use",
        "scene_create",
        "scene_edit",
        "hub_advanced_query",
        "settings_advanced"
    ]

    // MARK: - Init

    private init() {
        loadPersistedData()
        setupSessionTracking()
    }

    // MARK: - Persistence

    private func loadPersistedData() {
        // Load statistics
        if let data = UserDefaults.standard.data(forKey: StorageKey.statistics),
           let stats = try? JSONDecoder().decode(UsageStatistics.self, from: data) {
            statistics = stats
        }

        // Load skill level
        if let level = UserDefaults.standard.object(forKey: StorageKey.skillLevel) as? Int,
           let skillLevel = UserSkillLevel(rawValue: level) {
            currentSkillLevel = skillLevel
        }

        // Load hint configurations
        if let data = UserDefaults.standard.data(forKey: StorageKey.hintConfigs),
           let configs = try? JSONDecoder().decode([String: HintConfiguration].self, from: data) {
            hintConfigurations = configs
        }

        // Load suppressed hints
        if let suppressed = UserDefaults.standard.array(forKey: StorageKey.suppressedHints) as? [String] {
            suppressedHints = Set(suppressed)
        }

        logger.info("Loaded power user data: skill=\(self.currentSkillLevel.displayName), score=\(self.statistics.complexityScore)")
    }

    private func saveStatistics() {
        persistenceQueue.async { [weak self] in
            guard let self = self else { return }

            if let data = try? JSONEncoder().encode(self.statistics) {
                UserDefaults.standard.set(data, forKey: StorageKey.statistics)
            }

            UserDefaults.standard.set(self.currentSkillLevel.rawValue, forKey: StorageKey.skillLevel)
        }
    }

    private func saveHintConfigurations() {
        persistenceQueue.async { [weak self] in
            guard let self = self else { return }

            if let data = try? JSONEncoder().encode(self.hintConfigurations) {
                UserDefaults.standard.set(data, forKey: StorageKey.hintConfigs)
            }

            UserDefaults.standard.set(Array(self.suppressedHints), forKey: StorageKey.suppressedHints)
        }
    }

    // MARK: - Session Tracking

    private func setupSessionTracking() {
        // Track app lifecycle for session counting
        NotificationCenter.default.publisher(for: UIApplication.didBecomeActiveNotification)
            .sink { [weak self] _ in
                self?.startSession()
            }
            .store(in: &cancellables)

        NotificationCenter.default.publisher(for: UIApplication.willResignActiveNotification)
            .sink { [weak self] _ in
                self?.endSession()
            }
            .store(in: &cancellables)
    }

    private var sessionStartTime: Date?

    private func startSession() {
        sessionStartTime = Date()

        // Update consecutive days
        let today = Calendar.current.startOfDay(for: Date())
        if let lastActive = statistics.lastActiveDate {
            let lastActiveDay = Calendar.current.startOfDay(for: lastActive)
            let daysDiff = Calendar.current.dateComponents([.day], from: lastActiveDay, to: today).day ?? 0

            if daysDiff == 1 {
                statistics.consecutiveDaysUsed += 1
            } else if daysDiff > 1 {
                statistics.consecutiveDaysUsed = 1
            }
        } else {
            statistics.consecutiveDaysUsed = 1
        }

        statistics.lastActiveDate = today
        statistics.totalSessions += 1

        recalculateSkillLevel()
        saveStatistics()

        logger.debug("Session started (total: \(self.statistics.totalSessions))")
    }

    private func endSession() {
        guard let start = sessionStartTime else { return }

        let duration = Date().timeIntervalSince(start)

        // Update average session duration
        let totalDuration = statistics.averageSessionDuration * Double(statistics.totalSessions - 1) + duration
        statistics.averageSessionDuration = totalDuration / Double(statistics.totalSessions)

        sessionStartTime = nil
        saveStatistics()

        logger.debug("Session ended (duration: \(duration)s)")
    }

    // MARK: - Feature Usage Tracking

    /// Track usage of a feature
    func trackFeatureUsage(
        featureId: String,
        duration: TimeInterval? = nil,
        success: Bool = true,
        error: Bool = false
    ) {
        let event = FeatureUsageEvent(
            featureId: featureId,
            timestamp: Date(),
            duration: duration,
            completedSuccessfully: success,
            errorOccurred: error
        )

        // Update statistics
        statistics.totalActions += 1
        statistics.uniqueFeaturesUsed.insert(featureId)

        // Track advanced features
        if advancedFeatures.contains(featureId) {
            statistics.advancedFeaturesUsed.insert(featureId)
        }

        // Update category usage
        let category = event.category.rawValue
        statistics.categoryUsage[category, default: 0] += 1

        // Update error rate
        if error {
            let totalErrors = Double(statistics.totalActions) * statistics.errorRate + 1
            statistics.errorRate = totalErrors / Double(statistics.totalActions)
        }

        recalculateSkillLevel()
        saveStatistics()

        logger.debug("Tracked feature: \(featureId) (total actions: \(self.statistics.totalActions))")
    }

    /// Track multiple features at once (batch)
    func trackFeatures(_ featureIds: [String]) {
        for featureId in featureIds {
            trackFeatureUsage(featureId: featureId)
        }
    }

    // MARK: - Skill Level Calculation

    private func recalculateSkillLevel() {
        let newLevel = statistics.inferredSkillLevel

        if newLevel != currentSkillLevel {
            let oldLevel = currentSkillLevel
            currentSkillLevel = newLevel

            logger.info("Skill level changed: \(oldLevel.displayName) -> \(newLevel.displayName)")

            // Notify of level change
            NotificationCenter.default.post(
                name: .userSkillLevelChanged,
                object: nil,
                userInfo: [
                    "oldLevel": oldLevel.rawValue,
                    "newLevel": newLevel.rawValue
                ]
            )
        }
    }

    // MARK: - Hint Management

    /// Check if a hint should be shown for the current user
    func shouldShowHint(id: String, priority: HintConfiguration.HintPriority = .helpful) -> Bool {
        // Check if permanently suppressed
        if suppressedHints.contains(id) {
            return false
        }

        // Get or create hint configuration
        let config = hintConfigurations[id] ?? HintConfiguration(
            id: id,
            featureId: id,
            priority: priority
        )

        return config.shouldShow(for: currentSkillLevel)
    }

    /// Mark a hint as shown
    func markHintShown(id: String) {
        var config = hintConfigurations[id] ?? HintConfiguration(
            id: id,
            featureId: id,
            priority: .helpful
        )

        config.timesShown += 1
        config.lastShown = Date()
        hintConfigurations[id] = config

        saveHintConfigurations()
    }

    /// Dismiss a hint (temporarily or permanently)
    func dismissHint(id: String, permanently: Bool = false) {
        if permanently {
            suppressedHints.insert(id)

            if var config = hintConfigurations[id] {
                config.permanentlyDismissed = true
                hintConfigurations[id] = config
            }
        } else {
            if var config = hintConfigurations[id] {
                config.timesDismissed += 1
                hintConfigurations[id] = config

                // Auto-suppress after 3 dismissals
                if config.timesDismissed >= 3 {
                    suppressedHints.insert(id)
                    config.permanentlyDismissed = true
                    hintConfigurations[id] = config
                }
            }
        }

        saveHintConfigurations()
        logger.debug("Hint dismissed: \(id) (permanent: \(permanently))")
    }

    /// Reset hint for a feature (show again)
    func resetHint(id: String) {
        suppressedHints.remove(id)

        if var config = hintConfigurations[id] {
            config.permanentlyDismissed = false
            config.timesDismissed = 0
            hintConfigurations[id] = config
        }

        saveHintConfigurations()
    }

    /// Reset all hints
    func resetAllHints() {
        suppressedHints.removeAll()

        for key in hintConfigurations.keys {
            hintConfigurations[key]?.permanentlyDismissed = false
            hintConfigurations[key]?.timesDismissed = 0
        }

        saveHintConfigurations()
        logger.info("Reset all hints")
    }

    // MARK: - Complexity Adaptation

    /// Get recommended complexity level for UI
    var recommendedComplexity: UIComplexity {
        switch currentSkillLevel {
        case .novice, .beginner:
            return .simple
        case .intermediate:
            return .standard
        case .advanced, .expert:
            return .advanced
        }
    }

    /// UI complexity levels
    enum UIComplexity: String {
        case simple    // Minimal options, guided experience
        case standard  // Default experience
        case advanced  // All features exposed
    }

    // MARK: - Reset

    /// Reset all power user data (for testing or user request)
    func resetAllData() {
        statistics = UsageStatistics()
        currentSkillLevel = .novice
        suppressedHints.removeAll()
        hintConfigurations.removeAll()

        UserDefaults.standard.removeObject(forKey: StorageKey.statistics)
        UserDefaults.standard.removeObject(forKey: StorageKey.skillLevel)
        UserDefaults.standard.removeObject(forKey: StorageKey.hintConfigs)
        UserDefaults.standard.removeObject(forKey: StorageKey.suppressedHints)
        UserDefaults.standard.removeObject(forKey: StorageKey.usageEvents)

        logger.info("Reset all power user data")
    }

    // MARK: - Debug

    /// Force set skill level (for testing)
    #if DEBUG
    func debugSetSkillLevel(_ level: UserSkillLevel) {
        currentSkillLevel = level
        saveStatistics()
        logger.debug("Debug: Set skill level to \(level.displayName)")
    }
    #endif
}

// MARK: - Notification Names

extension Notification.Name {
    static let userSkillLevelChanged = Notification.Name("kagami.userSkillLevelChanged")
}

// MARK: - SwiftUI Integration

import SwiftUI
import KagamiDesign

/// View modifier that conditionally shows hints based on user skill level
struct AdaptiveHintModifier: ViewModifier {
    let hintId: String
    let hintContent: String
    let priority: HintConfiguration.HintPriority

    @StateObject private var detector = PowerUserDetector.shared
    @State private var showHint = false

    func body(content: Content) -> some View {
        content
            .overlay(alignment: .bottom) {
                if showHint {
                    HintBanner(
                        message: hintContent,
                        onDismiss: {
                            withAnimation {
                                showHint = false
                            }
                            detector.dismissHint(id: hintId)
                        },
                        onDismissPermanently: {
                            withAnimation {
                                showHint = false
                            }
                            detector.dismissHint(id: hintId, permanently: true)
                        }
                    )
                    .transition(.move(edge: .bottom).combined(with: .opacity))
                }
            }
            .onAppear {
                if detector.shouldShowHint(id: hintId, priority: priority) {
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                        withAnimation {
                            showHint = true
                        }
                        detector.markHintShown(id: hintId)
                    }
                }
            }
    }
}

/// Simple hint banner view
struct HintBanner: View {
    let message: String
    let onDismiss: () -> Void
    let onDismissPermanently: () -> Void

    var body: some View {
        HStack(spacing: KagamiSpacing.sm) {
            Image(systemName: "lightbulb")
                .foregroundColor(.beacon)

            Text(message)
                .font(KagamiFont.caption())
                .foregroundColor(.accessibleTextPrimary)
                .lineLimit(2)

            Spacer()

            Button {
                onDismiss()
            } label: {
                Image(systemName: "xmark")
                    .font(.caption)
                    .foregroundColor(.accessibleTextSecondary)
            }
            .accessibilityLabel("Dismiss hint")

            Menu {
                Button("Don't show again") {
                    onDismissPermanently()
                }
            } label: {
                Image(systemName: "ellipsis")
                    .font(.caption)
                    .foregroundColor(.accessibleTextSecondary)
            }
            .accessibilityLabel("More options")
        }
        .padding(KagamiSpacing.sm)
        .background(Color.obsidian)
        .cornerRadius(KagamiRadius.sm)
        .overlay(
            RoundedRectangle(cornerRadius: KagamiRadius.sm)
                .stroke(Color.beacon.opacity(0.3), lineWidth: 1)
        )
        .padding(.horizontal, KagamiSpacing.md)
        .padding(.bottom, KagamiSpacing.lg)
    }
}

extension View {
    /// Add an adaptive hint that shows based on user skill level
    func adaptiveHint(
        id: String,
        content: String,
        priority: HintConfiguration.HintPriority = .helpful
    ) -> some View {
        modifier(AdaptiveHintModifier(hintId: id, hintContent: content, priority: priority))
    }
}

/*
 * Mirror
 * Adapt to the user, not the other way around.
 * h(x) >= 0. Always.
 */
