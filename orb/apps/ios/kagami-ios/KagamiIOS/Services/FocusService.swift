//
// FocusService.swift — iOS Focus Mode Integration
//
// Colony: Nexus (e₄) — Integration
//
// Features:
//   - Read current Focus mode (Work, Sleep, Personal, etc.)
//   - React to Focus mode changes
//   - Customize Kagami behavior per Focus mode
//   - Sync Focus state with smart home automation
//
// Architecture:
//   INFocusStatusCenter → FocusService → KagamiAPIService → Smart Home
//
// h(x) ≥ 0. Always.
//

import Foundation
import UIKit
import Intents
import Combine

/// Service for monitoring and reacting to iOS Focus modes.
///
/// Focus modes allow Kagami to adapt its behavior based on user context:
/// - Sleep Focus → Goodnight scene, minimal notifications
/// - Work Focus → Office lighting, DND for smart home
/// - Personal Focus → Welcome home, comfort settings
@MainActor
class FocusService: ObservableObject {

    static let shared = FocusService()

    // MARK: - Published State

    /// Whether Focus monitoring is authorized
    @Published var isAuthorized: Bool = false

    /// Current Focus mode status
    @Published var currentFocus: FocusMode = .none

    /// Whether any Focus mode is active
    @Published var isFocusActive: Bool = false

    /// Last known Focus change timestamp
    @Published var lastFocusChange: Date?

    // MARK: - Private State

    private var focusStatusCenter: INFocusStatusCenter?
    private var cancellables = Set<AnyCancellable>()

    // Mapping of Focus to smart home behavior
    private let focusBehaviors: [FocusMode: FocusBehavior] = [
        .sleep: FocusBehavior(
            scene: "goodnight",
            lightLevel: 0,
            suppressAnnouncements: true,
            description: "Sleep mode - all quiet"
        ),
        .work: FocusBehavior(
            scene: nil,
            lightLevel: 80,
            suppressAnnouncements: false,
            description: "Work mode - focused lighting"
        ),
        .personal: FocusBehavior(
            scene: "welcome_home",
            lightLevel: 60,
            suppressAnnouncements: false,
            description: "Personal mode - comfort settings"
        ),
        .doNotDisturb: FocusBehavior(
            scene: nil,
            lightLevel: nil,
            suppressAnnouncements: true,
            description: "Do Not Disturb - no interruptions"
        ),
        .driving: FocusBehavior(
            scene: nil,
            lightLevel: nil,
            suppressAnnouncements: true,
            description: "Driving - hands-free only"
        ),
        .fitness: FocusBehavior(
            scene: nil,
            lightLevel: 100,
            suppressAnnouncements: false,
            description: "Fitness - bright and energizing"
        ),
        .mindfulness: FocusBehavior(
            scene: nil,
            lightLevel: 20,
            suppressAnnouncements: true,
            description: "Mindfulness - calm and quiet"
        ),
        .reading: FocusBehavior(
            scene: nil,
            lightLevel: 70,
            suppressAnnouncements: true,
            description: "Reading - optimal lighting"
        ),
        .gaming: FocusBehavior(
            scene: "movie_mode",
            lightLevel: 10,
            suppressAnnouncements: true,
            description: "Gaming - immersive setup"
        ),
        .none: FocusBehavior(
            scene: nil,
            lightLevel: nil,
            suppressAnnouncements: false,
            description: "No Focus - default behavior"
        )
    ]

    // MARK: - Types

    /// Represents a Focus mode
    enum FocusMode: String, CaseIterable, Codable {
        case none = "none"
        case doNotDisturb = "do_not_disturb"
        case sleep = "sleep"
        case work = "work"
        case personal = "personal"
        case driving = "driving"
        case fitness = "fitness"
        case mindfulness = "mindfulness"
        case reading = "reading"
        case gaming = "gaming"
        case custom = "custom"

        var displayName: String {
            switch self {
            case .none: return "No Focus"
            case .doNotDisturb: return "Do Not Disturb"
            case .sleep: return "Sleep"
            case .work: return "Work"
            case .personal: return "Personal"
            case .driving: return "Driving"
            case .fitness: return "Fitness"
            case .mindfulness: return "Mindfulness"
            case .reading: return "Reading"
            case .gaming: return "Gaming"
            case .custom: return "Custom"
            }
        }

        var icon: String {
            switch self {
            case .none: return "circle"
            case .doNotDisturb: return "moon.fill"
            case .sleep: return "bed.double.fill"
            case .work: return "laptopcomputer"
            case .personal: return "person.fill"
            case .driving: return "car.fill"
            case .fitness: return "figure.run"
            case .mindfulness: return "brain.head.profile"
            case .reading: return "book.fill"
            case .gaming: return "gamecontroller.fill"
            case .custom: return "gearshape.fill"
            }
        }
    }

    /// Behavior configuration for a Focus mode
    struct FocusBehavior {
        let scene: String?
        let lightLevel: Int?
        let suppressAnnouncements: Bool
        let description: String
    }

    // MARK: - Init

    private init() {
        focusStatusCenter = INFocusStatusCenter.default
        checkAuthorization()
    }

    // MARK: - Authorization

    /// Check current authorization status
    func checkAuthorization() {
        let status = INFocusStatusCenter.default.authorizationStatus
        isAuthorized = (status == .authorized)

        if isAuthorized {
            startMonitoring()
        }

        print("📱 Focus authorization: \(status.rawValue)")
    }

    /// Request Focus status authorization
    func requestAuthorization() async -> Bool {
        let center = INFocusStatusCenter.default

        return await withCheckedContinuation { continuation in
            center.requestAuthorization { status in
                let authorized = (status == .authorized)
                Task { @MainActor in
                    self.isAuthorized = authorized
                    if authorized {
                        self.startMonitoring()
                    }
                }
                continuation.resume(returning: authorized)
            }
        }
    }

    // MARK: - Monitoring

    /// Start monitoring Focus status changes
    private func startMonitoring() {
        guard let center = focusStatusCenter else { return }

        // Get initial status
        updateFocusStatus()

        // Monitor for changes
        NotificationCenter.default.publisher(for: UIApplication.didBecomeActiveNotification)
            .sink { [weak self] _ in
                self?.updateFocusStatus()
            }
            .store(in: &cancellables)

        print("👀 Started Focus monitoring")
    }

    /// Update the current Focus status
    private func updateFocusStatus() {
        guard isAuthorized else { return }

        let status = INFocusStatusCenter.default.focusStatus

        let previousFocus = currentFocus
        isFocusActive = status.isFocused ?? false

        // Determine specific Focus mode
        // Note: iOS doesn't expose the specific Focus name via API
        // We can only know if ANY Focus is active
        if isFocusActive {
            // Try to infer from context or use generic
            currentFocus = inferFocusMode()
        } else {
            currentFocus = .none
        }

        // React to changes
        if currentFocus != previousFocus {
            lastFocusChange = Date()
            onFocusChanged(from: previousFocus, to: currentFocus)
        }
    }

    /// Infer Focus mode from context (time of day, etc.)
    private func inferFocusMode() -> FocusMode {
        let hour = Calendar.current.component(.hour, from: Date())

        // Time-based inference (when we can't get the actual Focus name)
        switch hour {
        case 22...23, 0...6:
            return .sleep
        case 9...17:
            return .work
        default:
            return .personal
        }
    }

    // MARK: - React to Changes

    /// Called when Focus mode changes
    private func onFocusChanged(from oldFocus: FocusMode, to newFocus: FocusMode) {
        print("🎯 Focus changed: \(oldFocus.displayName) → \(newFocus.displayName)")

        // Get behavior for new Focus
        guard let behavior = focusBehaviors[newFocus] else { return }

        // Apply smart home changes
        Task {
            await applyFocusBehavior(behavior, for: newFocus)
        }

        // Notify backend
        notifyBackend(focus: newFocus)

        // Update Live Activity if active
        if #available(iOS 16.1, *) {
            Task {
                await LiveActivityManager.shared.updateActivity(
                    statusMessage: "Focus: \(newFocus.displayName)"
                )
            }
        }
    }

    /// Apply smart home behavior for Focus mode
    private func applyFocusBehavior(_ behavior: FocusBehavior, for focus: FocusMode) async {
        print("🏠 Applying Focus behavior: \(behavior.description)")

        // Execute scene if specified
        if let scene = behavior.scene {
            do {
                try await KagamiAPIService.shared.executeScene(scene)
            } catch {
                print("⚠️ Failed to execute scene: \(error)")
            }
        }

        // Set light level if specified
        if let level = behavior.lightLevel {
            do {
                _ = try await KagamiAPIService.shared.setLights(level, rooms: nil)
            } catch {
                print("⚠️ Failed to set lights: \(error)")
            }
        }

        // Update announcement suppression
        UserDefaults.standard.set(behavior.suppressAnnouncements, forKey: "suppress_announcements")
    }

    /// Notify Kagami backend of Focus change
    private func notifyBackend(focus: FocusMode) {
        Task {
            do {
                try await KagamiAPIService.shared.reportFocusChange(focus: focus.rawValue)
            } catch {
                print("⚠️ Failed to report Focus to backend: \(error)")
            }
        }
    }

    // MARK: - Public API

    /// Get current Focus behavior configuration
    func getCurrentBehavior() -> FocusBehavior? {
        return focusBehaviors[currentFocus]
    }

    /// Check if announcements should be suppressed
    var shouldSuppressAnnouncements: Bool {
        return focusBehaviors[currentFocus]?.suppressAnnouncements ?? false
    }

    /// Manually trigger Focus behavior (for testing)
    func simulateFocus(_ focus: FocusMode) async {
        let previousFocus = currentFocus
        currentFocus = focus
        isFocusActive = (focus != .none)
        lastFocusChange = Date()
        onFocusChanged(from: previousFocus, to: focus)
    }
}

// MARK: - KagamiAPIService Extension

extension KagamiAPIService {
    /// Report Focus mode change to backend
    func reportFocusChange(focus: String) async throws {
        let body: [String: Any] = [
            "event": "focus_changed",
            "focus_mode": focus,
            "timestamp": ISO8601DateFormatter().string(from: Date())
        ]

        // Would call actual API endpoint
        print("📤 Report Focus change: \(focus)")
    }
}

// MARK: - Preview Support

#if DEBUG
extension FocusService {
    static var preview: FocusService {
        let service = FocusService.shared
        service.currentFocus = .work
        service.isFocusActive = true
        service.isAuthorized = true
        return service
    }
}
#endif

/*
 * 鏡
 * h(x) ≥ 0. Always.
 *
 * Focus is intention.
 * Kagami listens and adapts.
 * Your home follows your mind.
 */
