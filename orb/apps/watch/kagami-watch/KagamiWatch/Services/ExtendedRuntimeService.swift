//
// ExtendedRuntimeService.swift — watchOS Extended Runtime Sessions
//
// Colony: Nexus (e₄) — Integration
//
// Features:
//   - Extended runtime sessions for background execution
//   - Workout session integration for continuous sensor access
//   - Smart alarm functionality
//   - Self-care/mindfulness guidance
//
// Architecture:
//   WKExtendedRuntimeSession → ExtendedRuntimeService → KagamiAPIService
//
// watchOS 6+ required
//
// h(x) ≥ 0. Always.
//

import Foundation
import WatchKit
import HealthKit
import Combine

/// Service for managing extended runtime sessions on watchOS.
///
/// Extended runtime sessions allow Kagami to:
/// - Continue running in the background for specific tasks
/// - Maintain sensor access during workouts
/// - Deliver smart alarms
/// - Guide mindfulness sessions
@MainActor
class ExtendedRuntimeService: NSObject, ObservableObject {

    static let shared = ExtendedRuntimeService()

    // MARK: - Published State

    /// Whether an extended runtime session is active
    @Published var isSessionActive: Bool = false

    /// Current session type
    @Published var currentSessionType: SessionType = .none

    /// Session start time
    @Published var sessionStartTime: Date?

    /// Remaining session time (for timed sessions)
    @Published var remainingTime: TimeInterval?

    /// Session state
    @Published var sessionState: WKExtendedRuntimeSessionState = .notStarted

    // MARK: - Private State

    private var currentSession: WKExtendedRuntimeSession?
    private var workoutSession: HKWorkoutSession?
    private var healthStore = HKHealthStore()
    private var sessionTimer: Timer?
    private var cancellables = Set<AnyCancellable>()

    // MARK: - Types

    /// Types of extended runtime sessions
    enum SessionType: String, CaseIterable {
        case none = "none"
        case workout = "workout"
        case selfCare = "self_care"
        case smartAlarm = "smart_alarm"
        case mindfulness = "mindfulness"
        case physicalTherapy = "physical_therapy"

        var displayName: String {
            switch self {
            case .none: return "None"
            case .workout: return "Workout"
            case .selfCare: return "Self Care"
            case .smartAlarm: return "Smart Alarm"
            case .mindfulness: return "Mindfulness"
            case .physicalTherapy: return "Physical Therapy"
            }
        }

        var icon: String {
            switch self {
            case .none: return "circle"
            case .workout: return "figure.run"
            case .selfCare: return "heart.fill"
            case .smartAlarm: return "alarm.fill"
            case .mindfulness: return "brain.head.profile"
            case .physicalTherapy: return "figure.walk"
            }
        }

        /// Maximum duration for this session type
        var maxDuration: TimeInterval {
            switch self {
            case .none: return 0
            case .workout: return .infinity  // Unlimited during workout
            case .selfCare: return 30 * 60   // 30 minutes
            case .smartAlarm: return 30 * 60 // 30 minutes
            case .mindfulness: return 60 * 60 // 1 hour
            case .physicalTherapy: return 60 * 60 // 1 hour
            }
        }
    }

    /// Configuration for a session
    struct SessionConfig {
        let type: SessionType
        let duration: TimeInterval?
        let hapticFeedback: Bool
        let healthKitIntegration: Bool
        let smartHomeIntegration: Bool
    }

    // MARK: - Init

    private override init() {
        super.init()
    }

    // MARK: - Session Management

    /// Start an extended runtime session
    func startSession(config: SessionConfig) async -> Bool {
        // End any existing session
        if isSessionActive {
            await endSession()
        }

        switch config.type {
        case .workout:
            return await startWorkoutSession(config: config)
        case .selfCare, .mindfulness, .physicalTherapy:
            return startExtendedSession(config: config)
        case .smartAlarm:
            return startSmartAlarmSession(config: config)
        case .none:
            return false
        }
    }

    /// End the current session
    func endSession() async {
        // End extended runtime session
        if let session = currentSession {
            session.invalidate()
            currentSession = nil
        }

        // End workout session
        if let workout = workoutSession {
            workout.end()
            workoutSession = nil
        }

        // Stop timer
        sessionTimer?.invalidate()
        sessionTimer = nil

        // Update state
        isSessionActive = false
        currentSessionType = .none
        sessionStartTime = nil
        remainingTime = nil
        sessionState = .notStarted

        print("🛑 Extended runtime session ended")

        // Notify backend
        await notifySessionEnded()
    }

    // MARK: - Workout Session

    /// Start a workout session for continuous background execution
    private func startWorkoutSession(config: SessionConfig) async -> Bool {
        guard HKHealthStore.isHealthDataAvailable() else {
            print("⚠️ HealthKit not available")
            return false
        }

        // Create workout configuration
        let workoutConfig = HKWorkoutConfiguration()
        workoutConfig.activityType = .other
        workoutConfig.locationType = .indoor

        do {
            // Create and start workout session
            let session = try HKWorkoutSession(
                healthStore: healthStore,
                configuration: workoutConfig
            )

            session.delegate = self
            workoutSession = session

            session.startActivity(with: Date())

            // Update state
            isSessionActive = true
            currentSessionType = .workout
            sessionStartTime = Date()
            sessionState = .running

            print("✅ Workout session started")

            // Notify backend
            await notifySessionStarted(type: .workout)

            // Start health monitoring
            if config.healthKitIntegration {
                await startHealthMonitoring()
            }

            // Trigger smart home integration
            if config.smartHomeIntegration {
                await triggerWorkoutSmartHome()
            }

            return true
        } catch {
            print("❌ Failed to start workout session: \(error)")
            return false
        }
    }

    // MARK: - Extended Runtime Session

    /// Start an extended runtime session (non-workout)
    private func startExtendedSession(config: SessionConfig) -> Bool {
        let session = WKExtendedRuntimeSession()
        session.delegate = self
        currentSession = session

        session.start()

        // Update state
        isSessionActive = true
        currentSessionType = config.type
        sessionStartTime = Date()
        sessionState = .running

        // Start duration timer if needed
        if let duration = config.duration {
            remainingTime = duration
            startSessionTimer(duration: duration)
        }

        print("✅ Extended runtime session started: \(config.type.displayName)")

        // Notify backend
        Task {
            await notifySessionStarted(type: config.type)
        }

        return true
    }

    /// Start a smart alarm session
    private func startSmartAlarmSession(config: SessionConfig) -> Bool {
        let session = WKExtendedRuntimeSession()
        session.delegate = self
        currentSession = session

        // Smart alarm sessions use a different start method
        session.start(at: Date().addingTimeInterval(config.duration ?? 300))

        // Update state
        isSessionActive = true
        currentSessionType = .smartAlarm
        sessionStartTime = Date()
        remainingTime = config.duration
        sessionState = .scheduled

        print("✅ Smart alarm scheduled for \(config.duration ?? 0) seconds")

        return true
    }

    // MARK: - Timer Management

    /// Start a timer to track session duration
    private func startSessionTimer(duration: TimeInterval) {
        remainingTime = duration

        sessionTimer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in
                guard let self = self, var remaining = self.remainingTime else { return }

                remaining -= 1

                if remaining <= 0 {
                    await self.endSession()
                } else {
                    self.remainingTime = remaining

                    // Periodic haptic feedback
                    if Int(remaining) % 60 == 0 {
                        WKInterfaceDevice.current().play(.notification)
                    }
                }
            }
        }
    }

    // MARK: - Health Monitoring

    /// Start continuous health monitoring during session
    private func startHealthMonitoring() async {
        // Health monitoring is now done through the shared instance
        // injected via the environment. Skip direct access here.

        // Start heart rate monitoring
        // Would use HKWorkoutBuilder and HKLiveWorkoutBuilder for real-time data
        print("💓 Health monitoring started")
    }

    // MARK: - Smart Home Integration

    /// Trigger smart home actions for workout start
    private func triggerWorkoutSmartHome() async {
        do {
            // Increase lighting in gym
            try await KagamiAPIService.shared.setLights(level: 100, rooms: ["Gym"])

            // Start energizing playlist
            // try await KagamiAPIService.shared.playPlaylist("workout")

            print("🏠 Smart home configured for workout")
        } catch {
            print("⚠️ Failed to configure smart home: \(error)")
        }
    }

    // MARK: - Backend Notification

    /// Notify backend when session starts
    private func notifySessionStarted(type: SessionType) async {
        let body: [String: Any] = [
            "event": "watch_session_started",
            "session_type": type.rawValue,
            "timestamp": ISO8601DateFormatter().string(from: Date())
        ]

        // Would call actual API
        print("📤 Session started: \(type.displayName)")
    }

    /// Notify backend when session ends
    private func notifySessionEnded() async {
        guard let startTime = sessionStartTime else { return }

        let duration = Date().timeIntervalSince(startTime)
        let body: [String: Any] = [
            "event": "watch_session_ended",
            "session_type": currentSessionType.rawValue,
            "duration_seconds": Int(duration),
            "timestamp": ISO8601DateFormatter().string(from: Date())
        ]

        // Would call actual API
        print("📤 Session ended after \(Int(duration))s")
    }

    // MARK: - Haptic Feedback

    /// Play haptic pattern for session event
    func playHaptic(for event: HapticEvent) {
        let device = WKInterfaceDevice.current()

        switch event {
        case .sessionStart:
            device.play(.start)
        case .sessionEnd:
            device.play(.stop)
        case .milestone:
            device.play(.success)
        case .alert:
            device.play(.notification)
        case .breath:
            device.play(.directionUp)
        }
    }

    enum HapticEvent {
        case sessionStart
        case sessionEnd
        case milestone
        case alert
        case breath
    }

    // MARK: - Digital Crown Integration

    /// Handle Digital Crown rotation during session
    func handleCrownRotation(_ delta: Double) {
        // Could adjust volume, intensity, etc.
        print("👑 Crown rotation: \(delta)")
    }
}

// MARK: - WKExtendedRuntimeSessionDelegate

extension ExtendedRuntimeService: WKExtendedRuntimeSessionDelegate {
    nonisolated func extendedRuntimeSessionDidStart(_ session: WKExtendedRuntimeSession) {
        Task { @MainActor in
            sessionState = .running
            print("📱 Extended runtime session running")
        }
    }

    nonisolated func extendedRuntimeSessionWillExpire(_ session: WKExtendedRuntimeSession) {
        Task { @MainActor in
            print("⚠️ Extended runtime session will expire")
            playHaptic(for: .alert)
        }
    }

    nonisolated func extendedRuntimeSession(
        _ session: WKExtendedRuntimeSession,
        didInvalidateWith reason: WKExtendedRuntimeSessionInvalidationReason,
        error: Error?
    ) {
        Task { @MainActor in
            sessionState = .notStarted
            isSessionActive = false

            print("🛑 Session invalidated: \(reason.rawValue)")
            if let error = error {
                print("   Error: \(error)")
            }
        }
    }
}

// MARK: - HKWorkoutSessionDelegate

extension ExtendedRuntimeService: HKWorkoutSessionDelegate {
    nonisolated func workoutSession(
        _ workoutSession: HKWorkoutSession,
        didChangeTo toState: HKWorkoutSessionState,
        from fromState: HKWorkoutSessionState,
        date: Date
    ) {
        Task { @MainActor in
            switch toState {
            case .running:
                sessionState = .running
                print("🏃 Workout running")
            case .paused:
                print("⏸️ Workout paused")
            case .ended:
                sessionState = .notStarted
                isSessionActive = false
                print("🏁 Workout ended")
            default:
                break
            }
        }
    }

    nonisolated func workoutSession(
        _ workoutSession: HKWorkoutSession,
        didFailWithError error: Error
    ) {
        Task { @MainActor in
            print("❌ Workout session error: \(error)")
            await endSession()
        }
    }
}

// MARK: - KagamiAPIService Extension

extension KagamiAPIService {
    /// Set lights in specific rooms
    func setLights(level: Int, rooms: [String]?) async throws {
        print("💡 Set lights to \(level)% in \(rooms?.joined(separator: ", ") ?? "all rooms")")
    }
}

/*
 * 鏡
 * h(x) ≥ 0. Always.
 *
 * Time extends for important moments.
 * The watch keeps running.
 * Your health, your home, always connected.
 */
