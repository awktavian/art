//
// KagamiIOSApp.swift — iOS Application Entry Point
//

import SwiftUI
import KagamiCore

@main
struct KagamiIOSApp: App {
    @StateObject private var appModel = AppModel()
    @StateObject private var deepLinkRouter = DeepLinkRouter()
    @StateObject private var ecosystemState = KagamiEcosystemState.shared
    @AppStorage("hasCompletedOnboarding") private var hasCompletedOnboarding = false

    var body: some Scene {
        WindowGroup {
            RootView(hasCompletedOnboarding: $hasCompletedOnboarding)
                .environmentObject(appModel)
                .environmentObject(deepLinkRouter)
                .environmentObject(ecosystemState)
                .preferredColorScheme(.dark)
                .onOpenURL { url in
                    deepLinkRouter.handle(url: url)
                }
                .onReceive(NotificationCenter.default.publisher(for: .kagamiDeepLink)) { notification in
                    if let urlString = notification.userInfo?["url"] as? String,
                       let url = URL(string: urlString) {
                        deepLinkRouter.handle(url: url)
                    }
                }
                .task {
                    // Initialize mesh network for device control
                    await DeviceControlService.shared.initializeMesh()

                    // Log ecosystem self-description on startup (debug only)
                    #if DEBUG
                    print(KagamiEcosystemRegistry.describe())
                    #endif
                }
        }
    }
}

// MARK: - Deep Link Router

/// Handles deep link URL routing for the app
/// Supports URLs like:
/// - kagami://room/{id}
/// - kagami://scene/{name}
/// - kagami://settings
/// - kagami://hub
/// - kagami://cameras/{id}
@MainActor
class DeepLinkRouter: ObservableObject {
    @Published var activeRoute: DeepLinkRoute?
    @Published var pendingRoute: DeepLinkRoute?

    /// Handle incoming URL
    func handle(url: URL) {
        guard url.scheme == "kagami" else { return }

        let path = url.host ?? ""
        let pathComponents = url.pathComponents.filter { $0 != "/" }

        switch path {
        case "room":
            if let roomId = pathComponents.first {
                navigate(to: .room(id: roomId))
            }

        case "scene":
            if let sceneName = pathComponents.first {
                navigate(to: .scene(name: sceneName.replacingOccurrences(of: "_", with: " ")))
            }

        case "settings":
            navigate(to: .settings)

        case "hub":
            navigate(to: .hub)

        case "cameras":
            if let cameraId = pathComponents.first {
                navigate(to: .camera(id: cameraId))
            } else {
                navigate(to: .cameras)
            }

        case "command":
            if let command = pathComponents.first {
                navigate(to: .command(text: command.removingPercentEncoding ?? command))
            }

        case "routine":
            if let routineId = pathComponents.first {
                navigate(to: .routine(id: routineId))
            }

        default:
            // Try to parse as a shorthand
            handleShorthand(path: path)
        }
    }

    /// Handle shorthand URLs like kagami://movie_mode
    private func handleShorthand(path: String) {
        // Map common shortcuts
        let shortcuts: [String: DeepLinkRoute] = [
            "movie_mode": .scene(name: "Movie Mode"),
            "movie": .scene(name: "Movie Mode"),
            "goodnight": .scene(name: "Goodnight"),
            "welcome_home": .scene(name: "Welcome Home"),
            "welcome": .scene(name: "Welcome Home"),
            "away": .scene(name: "Away"),
        ]

        if let route = shortcuts[path.lowercased()] {
            navigate(to: route)
        }
    }

    /// Navigate to a route
    func navigate(to route: DeepLinkRoute) {
        activeRoute = route

        // Post notification for any listeners
        NotificationCenter.default.post(
            name: .kagamiRouteChanged,
            object: nil,
            userInfo: ["route": route]
        )
    }

    /// Clear the active route
    func clearRoute() {
        activeRoute = nil
    }
}

/// Represents a deep link destination
enum DeepLinkRoute: Hashable {
    case room(id: String)
    case scene(name: String)
    case settings
    case hub
    case camera(id: String)
    case cameras
    case command(text: String)
    case routine(id: String)

    var title: String {
        switch self {
        case .room(let id): return "Room \(id)"
        case .scene(let name): return name
        case .settings: return "Settings"
        case .hub: return "Hub"
        case .camera(let id): return "Camera \(id)"
        case .cameras: return "Cameras"
        case .command(let text): return "Command: \(text)"
        case .routine(let id): return "Routine \(id)"
        }
    }
}

/// Notification for route changes
extension Notification.Name {
    static let kagamiRouteChanged = Notification.Name("kagamiRouteChanged")
}

// MARK: - Root View (Navigation Controller)

struct RootView: View {
    @EnvironmentObject var appModel: AppModel
    @Binding var hasCompletedOnboarding: Bool
    @State private var isAuthenticated = false

    var body: some View {
        Group {
            if !hasCompletedOnboarding {
                // First launch: Show onboarding
                OnboardingView(hasCompletedOnboarding: $hasCompletedOnboarding)
            } else if !isAuthenticated {
                // Require authentication
                LoginView(isAuthenticated: $isAuthenticated)
            } else {
                // Authenticated: Show main app
                ContentView()
            }
        }
        .onAppear {
            checkAuthenticationState()
        }
        .onChange(of: hasCompletedOnboarding) { _, completed in
            if completed {
                checkAuthenticationState()
            }
        }
        .onReceive(NotificationCenter.default.publisher(for: .kagamiDidLogout)) { _ in
            // Handle logout notification
            withAnimation(.easeInOut(duration: KagamiMotion.normal)) {
                isAuthenticated = false
            }
        }
    }

    private func checkAuthenticationState() {
        // Check for stored token
        if let token = KagamiKeychain.getToken() {
            appModel.apiService.setAuthToken(token)
            isAuthenticated = true

            // Reconnect with stored credentials
            Task {
                await appModel.connect()
            }
        } else {
            isAuthenticated = false
        }
    }
}

// MARK: - App Model

@MainActor
class AppModel: ObservableObject {
    @Published var isConnected = false
    @Published var safetyScore: Double?
    @Published var rooms: [RoomModel] = []
    @Published var isLoading = false
    @Published var error: String?

    /// Flag to show error alert
    @Published var showErrorAlert = false

    /// Current error for display
    @Published var currentError: KagamiAPIError?

    /// Demo mode flag
    @Published var isDemoMode: Bool = false

    /// Service initialization status (from visionOS pattern)
    @Published var serviceStatus: [String: Bool] = [:]

    let apiService = KagamiAPIService()

    init() {
        // Load saved server URL if available
        if let savedURL = UserDefaults.standard.string(forKey: "kagamiServerURL") {
            apiService.configure(baseURL: savedURL)
        }

        // Load demo mode flag
        isDemoMode = UserDefaults.standard.bool(forKey: "isDemoMode")

        Task {
            await connect()
        }
    }

    /// Connect to the server and fetch data using parallel initialization (visionOS pattern).
    ///
    /// P0 FIX: Uses async let for parallel service initialization to minimize startup time.
    func connect() async {
        isLoading = true
        error = nil
        serviceStatus = [:]

        // P0 FIX: Parallel initialization like visionOS SpatialServicesContainer
        // Initialize API connection, WebSocket, and Sensory services in parallel
        async let apiTask = initializeAPI()
        async let roomsTask = fetchRoomsAsync()
        async let healthKitTask = initializeHealthKit()

        // Await all in parallel
        let (apiSuccess, fetchedRooms, healthKitSuccess) = await (apiTask, roomsTask, healthKitTask)

        // Update service status
        serviceStatus["api"] = apiSuccess
        serviceStatus["rooms"] = !fetchedRooms.isEmpty
        serviceStatus["healthKit"] = healthKitSuccess

        // Update state from results
        isConnected = apiSuccess
        safetyScore = apiService.safetyScore
        rooms = fetchedRooms

        if !apiSuccess {
            if let apiError = apiService.lastError {
                currentError = apiError
                showErrorAlert = true
            }
        } else {
            currentError = nil
        }

        isLoading = false

        #if DEBUG
        print("[AppModel] Parallel init complete - API: \(apiSuccess), Rooms: \(fetchedRooms.count), HealthKit: \(healthKitSuccess)")
        #endif
    }

    /// Initialize API connection (for parallel init)
    private func initializeAPI() async -> Bool {
        await apiService.connect()
        return apiService.isConnected
    }

    /// Fetch rooms asynchronously (for parallel init)
    private func fetchRoomsAsync() async -> [RoomModel] {
        do {
            return try await apiService.fetchRooms()
        } catch {
            self.error = error.localizedDescription
            return []
        }
    }

    /// Initialize HealthKit (for parallel init)
    private func initializeHealthKit() async -> Bool {
        // HealthKit authorization happens on first use
        // This is a placeholder for future health integration
        return true
    }

    /// Refresh all data from the server
    func refresh() async {
        await connect()
    }

    /// Configure server URL and reconnect
    func configureServer(_ serverURL: String) async {
        UserDefaults.standard.set(serverURL, forKey: "kagamiServerURL")
        apiService.configure(baseURL: serverURL)
        await connect()
    }

    /// Clear the current error
    func clearError() {
        currentError = nil
        showErrorAlert = false
        error = nil
    }

    /// Retry the last failed operation
    func retryLastOperation() async {
        // Reset circuit breaker before retry (if user explicitly requests)
        MeshService.shared.resetConnection()
        await connect()
    }

    /// Check if a specific service is available
    func isServiceAvailable(_ service: String) -> Bool {
        serviceStatus[service] ?? false
    }
}

// MARK: - Color System
// NOTE: All Color tokens are defined in DesignTokens.generated.swift.
// Access via Color.crystal, Color.void, Color.safetyColor(for:), etc.
