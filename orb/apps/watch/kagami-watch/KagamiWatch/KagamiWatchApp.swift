//
// KagamiWatchApp.swift - Contextual Intelligence on Your Wrist
//
// Colony: Crystal (e7) - Verification
//
// Design Philosophy:
//   - Zero cognitive load: instant recognition
//   - Context-aware: actions adapt to situation
//   - One tap = optimal outcome
//   - Glance = full understanding
//
// h(x) >= 0. Always.
//

import SwiftUI
import WatchKit
import WidgetKit
import HealthKit
import WatchConnectivity
import Combine

@main
struct KagamiWatchApp: App {
    @WKApplicationDelegateAdaptor(ExtensionDelegate.self) var delegate
    @StateObject private var context = ContextEngine()
    @StateObject private var api = KagamiAPIService()
    @StateObject private var health = HealthKitService()
    @StateObject private var motion = MotionService()
    @StateObject private var connectivity = WatchConnectivityService.shared
    @StateObject private var analytics = KagamiAnalytics.shared
    @StateObject private var settings = WatchSettings.shared

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(context)
                .environmentObject(api)
                .environmentObject(health)
                .environmentObject(motion)
                .environmentObject(connectivity)
                .environmentObject(analytics)
                .environmentObject(settings)
                .task {
                    await health.requestAuthorization()
                    motion.startMonitoring()

                    if connectivity.authState.isAuthenticated {
                        api.configureAuth(
                            token: connectivity.authState.accessToken,
                            serverURL: connectivity.authState.serverURL
                        )
                    }

                    await api.connect()
                    delegate.configure(api: api, health: health, context: context)

                    analytics.trackAppLaunch()
                }
        }
    }
}

// MARK: - WKApplicationDelegate (Required for Background Tasks and Complications)

final class ExtensionDelegate: NSObject, WKApplicationDelegate, ObservableObject {

    private var syncTimer: Timer?
    private weak var apiService: KagamiAPIService?
    private weak var healthService: HealthKitService?
    private weak var contextEngine: ContextEngine?
    private var cancellables = Set<AnyCancellable>()

    func configure(api: KagamiAPIService, health: HealthKitService, context: ContextEngine) {
        self.apiService = api
        self.healthService = health
        self.contextEngine = context

        BackgroundTaskManager.shared.configure(apiService: api, healthService: health)
        BackgroundTaskManager.shared.scheduleAppRefresh()
        BackgroundTaskManager.shared.scheduleWatchKitBackgroundRefresh()

        startPeriodicSync()
        observeAuthChanges()
    }

    func applicationDidFinishLaunching() {
        KagamiAnalytics.shared.trackEvent("app_did_finish_launching")
    }

    func applicationDidBecomeActive() {
        Task { @MainActor in
            await apiService?.checkConnection()
            contextEngine?.updateContext()
        }
    }

    func applicationWillResignActive() {
        syncTimer?.invalidate()
    }

    func applicationDidEnterBackground() {
        BackgroundTaskManager.shared.scheduleWatchKitBackgroundRefresh()
    }

    func handle(_ backgroundTasks: Set<WKRefreshBackgroundTask>) {
        BackgroundTaskManager.shared.handleBackgroundTasks(backgroundTasks)
    }

    private func startPeriodicSync() {
        syncTimer?.invalidate()
        syncTimer = Timer.scheduledTimer(withTimeInterval: 30, repeats: true) { [weak self] _ in
            guard let self = self else { return }
            Task { @MainActor in
                if let health = self.healthService {
                    await self.apiService?.uploadSensoryData(health: health)
                }
                await self.apiService?.sendHeartbeat()

                if WatchConnectivityService.shared.authState.needsRefresh {
                    WatchConnectivityService.shared.requestTokenRefresh()
                }
            }
        }
    }

    private func observeAuthChanges() {
        WatchConnectivityService.shared.$authState
            .dropFirst()
            .sink { [weak self] state in
                if state.isAuthenticated {
                    self?.apiService?.configureAuth(
                        token: state.accessToken,
                        serverURL: state.serverURL
                    )
                } else {
                    self?.apiService?.clearAuth()
                }
            }
            .store(in: &cancellables)
    }

    deinit {
        syncTimer?.invalidate()
        syncTimer = nil
        cancellables.removeAll()
    }
}

// MARK: - Root View (Auth-Aware)

/// Root view that shows either ContentView or LoginView based on auth state
struct RootView: View {
    @EnvironmentObject var connectivity: WatchConnectivityService
    @AppStorage("requiresAuthentication") private var requiresAuth = true

    var body: some View {
        Group {
            if !requiresAuth || connectivity.authState.isAuthenticated {
                ContentView()
            } else {
                AuthRequiredView()
            }
        }
    }
}

/// View shown when authentication is required but not present
struct AuthRequiredView: View {
    @EnvironmentObject var connectivity: WatchConnectivityService

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 20) {
                    // Logo
                    Text("Kagami")
                        .font(.system(size: 36))
                        .foregroundColor(.white)
                        .padding(.top, 20)

                    // Status indicator
                    VStack(spacing: 8) {
                        switch connectivity.authState.status {
                        case .unauthenticated:
                            SignInPromptView()

                        case .authenticating:
                            ProgressView()
                                .progressViewStyle(.circular)
                            Text("Connecting...")
                                .font(.caption)
                                .foregroundColor(.secondary)

                        case .error:
                            Image(systemName: "exclamationmark.triangle")
                                .font(.title)
                                .foregroundColor(.safetyViolation)
                            Text(connectivity.authState.errorMessage ?? "Connection error")
                                .font(.caption)
                                .foregroundColor(.secondary)
                                .multilineTextAlignment(.center)
                            RetryButton()

                        case .tokenExpired:
                            Image(systemName: "clock.badge.exclamationmark")
                                .font(.title)
                                .foregroundColor(.beacon)
                            Text("Session expired")
                                .font(.caption)
                                .foregroundColor(.secondary)
                            RefreshButton()

                        case .authenticated:
                            // Should not reach here
                            EmptyView()
                        }
                    }
                    .padding(.horizontal)
                }
            }
            .background(Color.void)
        }
    }
}

private struct SignInPromptView: View {
    @EnvironmentObject var connectivity: WatchConnectivityService

    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: "iphone.and.arrow.forward")
                .font(.system(size: 40))
                .foregroundColor(.nexus)

            Text("Sign In Required")
                .font(.headline)
                .foregroundColor(.white)

            Text("Open Kagami on your iPhone to sign in")
                .font(.caption)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)

            // iPhone status
            HStack(spacing: 6) {
                Circle()
                    .fill(connectivity.isReachable ? Color.safetyOk : Color.safetyCaution)
                    .frame(width: 8, height: 8)
                Text(connectivity.isReachable ? "iPhone connected" : "iPhone not available")
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
            .padding(.top, 8)

            if connectivity.isReachable {
                RetryButton()
            }
        }
    }
}

private struct RetryButton: View {
    @EnvironmentObject var connectivity: WatchConnectivityService

    var body: some View {
        Button {
            HapticPattern.listening.play()
            connectivity.requestAuthFromiPhone()
        } label: {
            HStack {
                Image(systemName: "arrow.clockwise")
                Text("Retry")
            }
            .font(.footnote)
            .padding(.horizontal, 20)
            .padding(.vertical, 10)
            .background(Color.nexus.opacity(0.2))
            .cornerRadius(8)
        }
        .buttonStyle(.plain)
    }
}

private struct RefreshButton: View {
    @EnvironmentObject var connectivity: WatchConnectivityService

    var body: some View {
        Button {
            HapticPattern.listening.play()
            connectivity.requestTokenRefresh()
        } label: {
            HStack {
                Image(systemName: "arrow.clockwise")
                Text("Refresh")
            }
            .font(.footnote)
            .padding(.horizontal, 20)
            .padding(.vertical, 10)
            .background(Color.beacon.opacity(0.2))
            .cornerRadius(8)
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Colony Type (Unified)

enum Colony: String, CaseIterable, Identifiable {
    case kagami = "kagami"
    case spark = "spark"
    case forge = "forge"
    case flow = "flow"
    case nexus = "nexus"
    case beacon = "beacon"
    case grove = "grove"
    case crystal = "crystal"

    var id: String { rawValue }

    var color: Color {
        switch self {
        case .kagami: return .white
        case .spark: return .spark
        case .forge: return .forge
        case .flow: return .flow
        case .nexus: return .nexus
        case .beacon: return .beacon
        case .grove: return .grove
        case .crystal: return .crystal
        }
    }

    var icon: String {
        switch self {
        case .kagami: return "house.fill"
        case .spark: return "flame.fill"
        case .forge: return "hammer.fill"
        case .flow: return "drop.fill"
        case .nexus: return "link"
        case .beacon: return "light.beacon.max.fill"
        case .grove: return "leaf.fill"
        case .crystal: return "sparkles"
        }
    }

    var displayName: String {
        rawValue.capitalized
    }
}

// MARK: - Context Engine

@MainActor
class ContextEngine: ObservableObject {

    @Published var timeContext: TimeContext = .morning
    @Published var locationContext: LocationContext = .home
    @Published var activityInference: ActivityInference = .idle
    @Published var suggestedAction: SuggestedAction?
    @Published var isOfflineMode: Bool = false

    private var contextTimer: Timer?

    enum TimeContext: String, CaseIterable {
        case earlyMorning, morning, workDay, evening, lateEvening, night, lateNight

        var greeting: String {
            switch self {
            case .earlyMorning: return "Good morning"
            case .morning: return "Morning"
            case .workDay: return ""
            case .evening: return "Welcome home"
            case .lateEvening: return "Relaxing"
            case .night: return "Good night"
            case .lateNight: return "Rest well"
            }
        }

        var primaryColor: Color {
            switch self {
            case .earlyMorning, .morning: return .beacon
            case .workDay: return .grove
            case .evening, .lateEvening: return .nexus
            case .night, .lateNight: return .flow
            }
        }

        static func current() -> TimeContext {
            let hour = Calendar.current.component(.hour, from: Date())
            switch hour {
            case 5..<7: return .earlyMorning
            case 7..<9: return .morning
            case 9..<17: return .workDay
            case 17..<20: return .evening
            case 20..<22: return .lateEvening
            case 22..<24: return .night
            default: return .lateNight
            }
        }
    }

    enum LocationContext: String {
        case home, away, arriving, leaving, unknown

        var icon: String {
            switch self {
            case .home: return "house.fill"
            case .away: return "car.fill"
            case .arriving: return "figure.walk.arrival"
            case .leaving: return "figure.walk.departure"
            case .unknown: return "location.fill"
            }
        }
    }

    enum ActivityInference: String {
        case sleeping, waking, working, cooking, relaxing, watching, hosting, idle

        var icon: String {
            switch self {
            case .sleeping: return "bed.double.fill"
            case .waking: return "sun.max.fill"
            case .working: return "laptopcomputer"
            case .cooking: return "frying.pan.fill"
            case .relaxing: return "sofa.fill"
            case .watching: return "tv.fill"
            case .hosting: return "person.3.fill"
            case .idle: return "house.fill"
            }
        }
    }

    struct SuggestedAction: Identifiable {
        let id = UUID()
        let icon: String
        let label: String
        let shortLabel: String
        let action: ActionType
        let priority: Int
        let colony: Colony

        enum ActionType: String {
            case movieMode, goodnight, welcomeHome, away
            case lightsOn, lightsOff, fireplace, coffee, focusMode
        }
    }

    init() {
        updateContext()
        startContextTimer()
    }

    private func startContextTimer() {
        contextTimer?.invalidate()
        contextTimer = Timer.scheduledTimer(withTimeInterval: 60, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in
                self?.updateContext()
            }
        }
    }

    func updateContext() {
        timeContext = TimeContext.current()
        calculateSuggestedActions()
    }

    func updateFromAPI(homeStatus: HomeStatus?, isConnected: Bool) {
        isOfflineMode = !isConnected

        if let status = homeStatus {
            if status.movieMode {
                activityInference = .watching
            } else if status.occupiedRooms == 0 {
                locationContext = .away
            } else {
                locationContext = .home
                activityInference = inferActivity(from: status)
            }
        }

        calculateSuggestedActions()
    }

    private func inferActivity(from status: HomeStatus) -> ActivityInference {
        switch timeContext {
        case .earlyMorning, .morning: return .waking
        case .workDay: return .working
        case .evening: return .relaxing
        case .lateEvening: return status.movieMode ? .watching : .relaxing
        case .night, .lateNight: return .sleeping
        }
    }

    private func calculateSuggestedActions() {
        var actions: [SuggestedAction] = []

        switch (timeContext, locationContext) {
        case (.earlyMorning, .home), (.morning, .home):
            actions.append(SuggestedAction(
                icon: "sun.max.fill", label: "Start Day", shortLabel: "Start",
                action: .lightsOn, priority: 10, colony: .beacon
            ))
            actions.append(SuggestedAction(
                icon: "cup.and.saucer.fill", label: "Coffee Time", shortLabel: "Coffee",
                action: .coffee, priority: 8, colony: .forge
            ))

        case (.workDay, .home):
            actions.append(SuggestedAction(
                icon: "target", label: "Focus Mode", shortLabel: "Focus",
                action: .focusMode, priority: 5, colony: .grove
            ))

        case (.evening, .home), (.lateEvening, .home):
            actions.append(SuggestedAction(
                icon: "film.fill", label: "Movie Mode", shortLabel: "Movie",
                action: .movieMode, priority: 10, colony: .forge
            ))
            actions.append(SuggestedAction(
                icon: "flame.fill", label: "Fireplace", shortLabel: "Fire",
                action: .fireplace, priority: 8, colony: .spark
            ))

        case (.night, .home), (.lateNight, .home):
            actions.append(SuggestedAction(
                icon: "moon.fill", label: "Goodnight", shortLabel: "Night",
                action: .goodnight, priority: 10, colony: .flow
            ))

        case (_, .away):
            actions.append(SuggestedAction(
                icon: "house.fill", label: "Welcome Home", shortLabel: "Home",
                action: .welcomeHome, priority: 10, colony: .grove
            ))

        case (_, .arriving):
            actions.append(SuggestedAction(
                icon: "hand.wave.fill", label: "I'm Home", shortLabel: "Home",
                action: .welcomeHome, priority: 10, colony: .grove
            ))

        default:
            break
        }

        actions.sort { $0.priority > $1.priority }
        suggestedAction = actions.first
    }

    deinit {
        contextTimer?.invalidate()
        contextTimer = nil
    }
}

// MARK: - Analytics Service

@MainActor
final class KagamiAnalytics: ObservableObject {
    static let shared = KagamiAnalytics()

    @Published var sessionId: String = UUID().uuidString
    @Published var eventsThisSession: Int = 0

    private var sessionStartTime: Date = Date()

    private init() {}

    func trackAppLaunch() {
        trackEvent("app_launch", properties: ["session_id": sessionId])
    }

    func trackEvent(_ name: String, properties: [String: Any]? = nil) {
        eventsThisSession += 1

        var event: [String: Any] = [
            "event": name,
            "timestamp": ISO8601DateFormatter().string(from: Date()),
            "session_id": sessionId,
            "session_duration": Date().timeIntervalSince(sessionStartTime)
        ]

        if let props = properties {
            event["properties"] = props
        }

        #if DEBUG
        print("[Analytics] \(name): \(properties ?? [:])")
        #endif
    }

    func trackSceneActivation(_ sceneName: String) {
        trackEvent("scene_activated", properties: ["scene": sceneName])
    }

    func trackError(_ error: String, context: String? = nil) {
        trackEvent("error", properties: [
            "error_message": error,
            "context": context ?? "unknown"
        ])
    }

    func trackVoiceCommand(_ transcript: String, success: Bool) {
        trackEvent("voice_command", properties: [
            "success": success,
            "length": transcript.count
        ])
    }

    func trackOnboardingStep(_ step: Int) {
        trackEvent("onboarding_step", properties: ["step": step])
    }

    func trackOnboardingComplete() {
        trackEvent("onboarding_complete")
    }
}

// MARK: - Watch Settings

@MainActor
final class WatchSettings: ObservableObject {
    static let shared = WatchSettings()

    @Published var hapticFeedbackEnabled: Bool {
        didSet { UserDefaults.standard.set(hapticFeedbackEnabled, forKey: "hapticFeedbackEnabled") }
    }

    @Published var showNavigationBar: Bool {
        didSet { UserDefaults.standard.set(showNavigationBar, forKey: "showNavigationBar") }
    }

    @Published var doubleTapHintDuration: TimeInterval {
        didSet { UserDefaults.standard.set(doubleTapHintDuration, forKey: "doubleTapHintDuration") }
    }

    @Published var offlineModeEnabled: Bool {
        didSet { UserDefaults.standard.set(offlineModeEnabled, forKey: "offlineModeEnabled") }
    }

    @Published var currentMemberId: String? {
        didSet { UserDefaults.standard.set(currentMemberId, forKey: "currentMemberId") }
    }

    @Published var hasCompletedOnboarding: Bool {
        didSet { UserDefaults.standard.set(hasCompletedOnboarding, forKey: "hasCompletedOnboarding") }
    }

    private init() {
        // Initialize ALL stored properties first before any conditional logic
        let storedHaptic = UserDefaults.standard.bool(forKey: "hapticFeedbackEnabled")
        let storedNavBar = UserDefaults.standard.bool(forKey: "showNavigationBar")
        let storedDoubleTap = UserDefaults.standard.double(forKey: "doubleTapHintDuration")
        let storedOffline = UserDefaults.standard.bool(forKey: "offlineModeEnabled")
        let storedMemberId = UserDefaults.standard.string(forKey: "currentMemberId")
        let storedOnboarding = UserDefaults.standard.bool(forKey: "hasCompletedOnboarding")

        // Set defaults for unset values
        self.hapticFeedbackEnabled = UserDefaults.standard.bool(forKey: "hapticFeedbackEnabled_set") ? storedHaptic : true
        self.showNavigationBar = UserDefaults.standard.bool(forKey: "showNavigationBar_set") ? storedNavBar : true
        self.doubleTapHintDuration = storedDoubleTap > 0 ? storedDoubleTap : 5.0
        self.offlineModeEnabled = storedOffline
        self.currentMemberId = storedMemberId
        self.hasCompletedOnboarding = storedOnboarding

        // Mark defaults as set
        if !UserDefaults.standard.bool(forKey: "hapticFeedbackEnabled_set") {
            UserDefaults.standard.set(true, forKey: "hapticFeedbackEnabled_set")
        }
        if !UserDefaults.standard.bool(forKey: "showNavigationBar_set") {
            UserDefaults.standard.set(true, forKey: "showNavigationBar_set")
        }
    }
}
