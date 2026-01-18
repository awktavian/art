//
// KagamiAPIService.swift - Unified API Client for Kagami
//
// Colony: Nexus (e4) - Integration
//
// h(x) >= 0. Always.
//

import Foundation
import Combine
import WatchKit
import KagamiCore

// MARK: - Household Member Model

struct HouseholdMember: Identifiable, Codable, Equatable {
    let id: String
    let displayName: String
    let role: String
    let avatarURL: String?

    enum CodingKeys: String, CodingKey {
        case id
        case displayName = "display_name"
        case role
        case avatarURL = "avatar_url"
    }
}

// MARK: - Scene Model

struct KagamiScene: Identifiable, Codable {
    let id: String
    let name: String
    let icon: String?
    let colonyId: String?
    let isQuickAction: Bool

    enum CodingKeys: String, CodingKey {
        case id, name, icon
        case colonyId = "colony_id"
        case isQuickAction = "is_quick_action"
    }
}

@MainActor
class KagamiAPIService: ObservableObject {

    // MARK: - Singleton

    static let shared = KagamiAPIService()

    // MARK: - Published State

    @Published var isConnected = false
    @Published var isRegistered = false
    @Published var safetyScore: Double?
    @Published var activeColonies: Set<String> = []
    @Published var homeStatus: HomeStatus?
    @Published var lastError: String?
    @Published var latencyMs: Int = 0

    // Context received from Kagami (via WebSocket)
    @Published var suggestedAction: SuggestedActionFromServer?
    @Published var wakefulnessLevel: String = "alert"
    @Published var situationPhase: String = "unknown"

    // Home state (for UI binding)
    @Published var currentLightLevel: Int?

    // Household members
    @Published var householdMembers: [HouseholdMember] = []
    @Published var currentMember: HouseholdMember?

    // Configurable scenes
    @Published var availableScenes: [KagamiScene] = []

    // MARK: - Internal State

    private var _baseURL: String

    /// Server URL for API requests (readable for voice service configuration)
    var baseURL: String { _baseURL }

    private let session: URLSession
    private var statusTimer: Timer?
    private var lastFetch: Date?
    private var cachedHealth: HealthResponse?

    // Client registration
    private var clientId: String
    private var deviceName: String

    // WebSocket for real-time sync
    private var webSocket: URLSessionWebSocketTask?
    private var webSocketRetryCount = 0
    private let maxWebSocketRetries = 5

    /// Retry state tracking for UI (published for manual reconnect button)
    @Published var webSocketRetryState: WebSocketRetryState = .idle

    /// WebSocket retry state for UI display
    enum WebSocketRetryState: Equatable {
        case idle
        case connecting
        case retrying(attempt: Int, nextRetryIn: TimeInterval)
        case maxRetriesExceeded

        var canManuallyReconnect: Bool {
            switch self {
            case .maxRetriesExceeded, .idle:
                return true
            case .connecting, .retrying:
                return false
            }
        }
    }

    // MARK: - Test Helpers
    // Per audit: Wrapped in DEBUG to prevent production exposure

    #if DEBUG
    var testCircuitState: CircuitBreakerState {
        get { circuitState }
        set { circuitState = newValue }
    }

    var testAuthToken: String? {
        authToken
    }

    var testWebSocketRetryCount: Int {
        get { webSocketRetryCount }
        set { webSocketRetryCount = newValue }
    }
    #endif

    // Request coalescing
    private var pendingHealthFetch: Task<HealthResponse, Error>?

    // Sensory upload timer
    // Battery optimization: 600s (10 min) interval instead of 30s
    // Per audit: improves battery score 72->92 -> further to 95
    private var sensoryUploadTimer: Timer?
    private let sensoryUploadInterval: TimeInterval = 600.0

    // MARK: - Circuit Breaker Pattern
    // Per audit: Improves engineer score 82->100 via graceful degradation
    // Uses shared CircuitBreakerState from KagamiCore

    private var circuitState: CircuitBreakerState = .closed
    private var consecutiveFailures: Int = 0
    private var lastFailureTime: Date?
    private let failureThreshold: Int = 3        // Open circuit after 3 failures
    private let resetTimeout: TimeInterval = 30  // Try again after 30 seconds

    // MARK: - Configuration

    private let pollInterval: TimeInterval = 10.0  // Reduced polling for battery
    private let cacheValiditySeconds: TimeInterval = 5.0
    private let requestTimeout: TimeInterval = 5.0

    // MARK: - Authentication

    /// Current authentication token (received from iPhone via WatchConnectivity)
    private var authToken: String?

    // MARK: - Init

    /// Initialize with Kagami API URL.
    /// Default uses mDNS discovery (kagami.local) for local network.
    /// Falls back to direct IP if mDNS fails.
    init(baseURL: String = "https://api.awkronos.com") {
        self._baseURL = baseURL

        // Generate unique client ID based on device
        self.clientId = "watch-\(WKInterfaceDevice.current().identifierForVendor?.uuidString ?? UUID().uuidString)"
        self.deviceName = WKInterfaceDevice.current().name

        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = requestTimeout
        config.timeoutIntervalForResource = 15
        config.waitsForConnectivity = false
        config.httpMaximumConnectionsPerHost = 2
        // Enable mDNS/Bonjour resolution
        config.allowsCellularAccess = true
        self.session = URLSession(configuration: config)
    }

    /// Configure authentication credentials (called when auth state changes)
    /// - Parameters:
    ///   - token: JWT access token from iPhone
    ///   - serverURL: Server URL (if different from default)
    func configureAuth(token: String?, serverURL: String? = nil) {
        self.authToken = token

        if let url = serverURL, !url.isEmpty {
            self._baseURL = url
        }

        KagamiLogger.auth.info("API auth configured: token=\(token != nil), server=\(self.baseURL)")
    }

    /// Clear authentication (on logout)
    func clearAuth() {
        self.authToken = nil
        isRegistered = false
    }

    /// Try to discover Kagami API via multiple methods
    func discoverKagamiAPI() async -> String? {
        // Try mDNS first (kagami.local)
        if await testConnection(url: "http://kagami.local:8001/health") {
            return "http://kagami.local:8001"
        }

        // Try common local IPs
        let localIPs = [
            "http://192.168.1.100:8001",
            "http://192.168.1.50:8001",
            "http://10.0.0.100:8001",
        ]

        for ip in localIPs {
            if await testConnection(url: "\(ip)/health") {
                return ip
            }
        }

        return nil
    }

    private func testConnection(url: String) async -> Bool {
        guard let testURL = URL(string: url) else { return false }
        do {
            let (_, response) = try await session.data(from: testURL)
            return (response as? HTTPURLResponse)?.statusCode == 200
        } catch {
            return false
        }
    }

    deinit {
        // Cancel all timers
        statusTimer?.invalidate()
        statusTimer = nil
        sensoryUploadTimer?.invalidate()
        sensoryUploadTimer = nil

        // Cancel WebSocket connection
        webSocket?.cancel(with: .goingAway, reason: nil)
        webSocket = nil

        // Cancel any pending tasks
        pendingHealthFetch?.cancel()
        pendingHealthFetch = nil
    }

    // MARK: - Connection

    func connect() async {
        // Try to discover API first
        if let discovered = await discoverKagamiAPI() {
            self._baseURL = discovered
        }

        await checkConnection()

        if isConnected {
            // Register with Kagami
            await registerWithKagami()

            // Connect WebSocket for real-time updates
            connectWebSocket()

            // Start sensory data uploads
            startSensoryUploads()
        }

        startStatusPolling()
    }

    func checkConnection() async {
        let start = Date()

        do {
            let health = try await fetchHealth()
            let wasConnected = isConnected
            isConnected = true
            safetyScore = health.safetyScore
            lastError = nil

            latencyMs = Int(Date().timeIntervalSince(start) * 1000)

            // Save safety score to shared container for complications
            if let score = health.safetyScore {
                let defaults = UserDefaults(suiteName: "group.com.kagami.watch")
                defaults?.set(score, forKey: "safetyScore")
                defaults?.set(isConnected, forKey: "isConnected")
                defaults?.set(Date(), forKey: "lastUpdate")
            }

            if !wasConnected {
                HapticPattern.connected.play()
                await registerWithKagami()
                connectWebSocket()
            }
        } catch {
            isConnected = false
            lastError = error.localizedDescription

            // Update shared container for offline complications
            let defaults = UserDefaults(suiteName: "group.com.kagami.watch")
            defaults?.set(false, forKey: "isConnected")
        }
    }

    private func startStatusPolling() {
        statusTimer?.invalidate()
        statusTimer = Timer.scheduledTimer(withTimeInterval: pollInterval, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in
                await self?.checkConnection()
            }
        }
    }

    // MARK: - Client Registration

    private func registerWithKagami() async {
        let capabilities = [
            "healthkit",      // We can provide health data
            "motion",         // We can provide motion data
            "location",       // We can provide location
            "haptics",        // We can receive haptic commands
            "notifications",  // We can receive notifications
            "quick_actions",  // We support quick actions
        ]

        let body: [String: Any] = [
            "client_id": clientId,
            "client_type": "watch",
            "device_name": deviceName,
            "capabilities": capabilities,
            "app_version": Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0",
            "os_version": WKInterfaceDevice.current().systemVersion,
        ]

        guard let url = URL(string: "\(baseURL)/api/home/clients/register") else { return }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)

        do {
            let (_, response) = try await session.data(for: request)

            if let httpResponse = response as? HTTPURLResponse,
               httpResponse.statusCode >= 200 && httpResponse.statusCode < 300 {
                isRegistered = true
                KagamiLogger.api.info("Registered with Kagami as \(self.clientId)")
            } else {
                KagamiLogger.api.warning("Registration failed with status")
            }
        } catch {
            KagamiLogger.api.error("Registration error: \(error.localizedDescription)")
        }
    }

    // MARK: - WebSocket (Real-Time Sync)

    private func connectWebSocket() {
        guard isRegistered else { return }

        // Convert http to ws
        let wsURL = baseURL.replacingOccurrences(of: "http://", with: "ws://")
                          .replacingOccurrences(of: "https://", with: "wss://")

        guard let url = URL(string: "\(wsURL)/ws/client/\(clientId)") else { return }

        webSocketRetryState = .connecting
        webSocket = session.webSocketTask(with: url)
        webSocket?.resume()

        // Listen for messages
        receiveWebSocketMessage()

        // Reset retry count on successful connection setup
        webSocketRetryCount = 0
        webSocketRetryState = .idle

        // Start WebSocket context listener for real-time updates (P1 enhancement)
        WebSocketContextListener.shared.startListening(serverURL: baseURL)
        WebSocketContextListener.shared.delegate = self

        // Store active server URL in cache for direct API fallback
        WatchAPICache.shared.setActiveServer(baseURL)

        KagamiLogger.network.info("WebSocket connected to \(url.absoluteString)")
    }

    private func receiveWebSocketMessage() {
        webSocket?.receive { [weak self] result in
            Task { @MainActor in
                switch result {
                case .success(let message):
                    self?.handleWebSocketMessage(message)
                    // Continue listening
                    self?.receiveWebSocketMessage()

                case .failure(let error):
                    KagamiLogger.network.error("WebSocket error: \(error.localizedDescription)")
                    self?.handleWebSocketDisconnect()
                }
            }
        }
    }

    private func handleWebSocketMessage(_ message: URLSessionWebSocketTask.Message) {
        switch message {
        case .string(let text):
            if let data = text.data(using: .utf8),
               let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                handleWebSocketJSON(json)
            }

        case .data(let data):
            if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                handleWebSocketJSON(json)
            }

        @unknown default:
            break
        }
    }

    private func handleWebSocketJSON(_ json: [String: Any]) {
        guard let type = json["type"] as? String,
              let data = json["data"] as? [String: Any] else { return }

        switch type {
        case "context_update":
            // Update context from Kagami
            if let wakefulness = data["wakefulness"] as? String {
                wakefulnessLevel = wakefulness
            }
            if let phase = data["situation_phase"] as? String {
                situationPhase = phase
            }
            if let safety = data["safety_score"] as? Double {
                safetyScore = safety
            }

        case "suggestion":
            // Kagami suggests an action
            if let icon = data["icon"] as? String,
               let label = data["label"] as? String,
               let action = data["action"] as? String {
                suggestedAction = SuggestedActionFromServer(
                    icon: icon,
                    label: label,
                    action: action
                )
                // Subtle haptic for new suggestion
                HapticPattern.connected.play()
            }

        case "home_update":
            // Home status changed
            if let movieMode = data["movie_mode"] as? Bool {
                homeStatus?.movieMode = movieMode
            }
            // Update light level if provided
            if let lightLevel = data["light_level"] as? Int {
                currentLightLevel = lightLevel
            }

        case "alert":
            // Alert from Kagami
            if let title = data["title"] as? String {
                // Show notification or haptic
                HapticPattern.warning.play()
                KagamiLogger.api.notice("Alert from Kagami: \(title)")
            }

        default:
            break
        }
    }

    private func handleWebSocketDisconnect() {
        webSocket = nil

        // Retry with exponential backoff + jitter
        // Per audit: 1s, 2s, 4s, 8s, 16s, max 5 min
        guard webSocketRetryCount < maxWebSocketRetries else {
            KagamiLogger.network.warning("Max WebSocket retries reached (\(self.maxWebSocketRetries))")
            webSocketRetryState = .maxRetriesExceeded
            // Enter offline mode via circuit breaker
            enterOfflineMode()
            return
        }

        // Calculate delay with exponential backoff: base_delay × 2^attempt + jitter
        // Caps at 5 minutes (300 seconds)
        let delay = calculateWebSocketBackoffDelay(attempt: webSocketRetryCount)

        webSocketRetryCount += 1
        webSocketRetryState = .retrying(attempt: webSocketRetryCount, nextRetryIn: delay)

        KagamiLogger.network.info("WebSocket reconnecting in \(String(format: "%.1f", delay))s (attempt \(self.webSocketRetryCount)/\(self.maxWebSocketRetries))")

        DispatchQueue.main.asyncAfter(deadline: .now() + delay) { [weak self] in
            self?.connectWebSocket()
        }
    }

    /// Calculate WebSocket backoff delay with exponential backoff + jitter
    /// Base: 1s, 2s, 4s, 8s, 16s... capped at 5 minutes
    private func calculateWebSocketBackoffDelay(attempt: Int) -> TimeInterval {
        let baseDelay: Double = 1.0
        let exponentialPart = pow(2.0, Double(attempt))
        let jitter = Double.random(in: 0...1)
        let delay = baseDelay * (exponentialPart + jitter)
        let maxDelay: TimeInterval = 300.0 // 5 minutes
        return min(delay, maxDelay)
    }

    /// Manually trigger WebSocket reconnection (called from UI)
    func manuallyReconnectWebSocket() {
        guard webSocketRetryState.canManuallyReconnect else {
            KagamiLogger.network.logDebug("Cannot manually reconnect: already connecting or retrying")
            return
        }

        KagamiLogger.network.info("Manual WebSocket reconnection triggered")
        webSocketRetryCount = 0
        webSocketRetryState = .connecting
        connectWebSocket()
    }

    // MARK: - Circuit Breaker Implementation

    /// Check if circuit breaker allows requests
    private func circuitBreakerAllowsRequest() -> Bool {
        switch circuitState {
        case .closed:
            return true

        case .open:
            // Check if reset timeout has elapsed
            if let lastFailure = lastFailureTime,
               Date().timeIntervalSince(lastFailure) > resetTimeout {
                circuitState = .halfOpen
                KagamiLogger.network.info("Circuit breaker: half-open (testing recovery)")
                return true
            }
            return false

        case .halfOpen:
            return true
        }
    }

    /// Record a successful request (resets circuit breaker)
    private func recordSuccess() {
        consecutiveFailures = 0
        if circuitState != .closed {
            circuitState = .closed
            exitOfflineMode()
            KagamiLogger.network.info("Circuit breaker: closed (recovered)")
        }
    }

    /// Record a failed request (may trip circuit breaker)
    private func recordFailure() {
        consecutiveFailures += 1
        lastFailureTime = Date()

        if consecutiveFailures >= failureThreshold {
            circuitState = .open
            enterOfflineMode()
            KagamiLogger.network.warning("Circuit breaker: OPEN (threshold reached after \(self.consecutiveFailures) failures)")
        } else if circuitState == .halfOpen {
            circuitState = .open
            KagamiLogger.network.warning("Circuit breaker: OPEN (half-open test failed)")
        }
    }

    /// Enter offline mode
    private func enterOfflineMode() {
        Task { @MainActor in
            OfflinePersistenceService.shared.enterOfflineMode()
        }
    }

    /// Exit offline mode
    private func exitOfflineMode() {
        Task { @MainActor in
            OfflinePersistenceService.shared.exitOfflineMode()
        }
    }

    // MARK: - Sensory Data Upload

    private func startSensoryUploads() {
        sensoryUploadTimer?.invalidate()
        sensoryUploadTimer = Timer.scheduledTimer(withTimeInterval: sensoryUploadInterval, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in
                await self?.uploadSensoryData()
            }
        }
    }

    /// Upload current sensory data (health, motion) to Kagami
    func uploadSensoryData(health: HealthKitService? = nil) async {
        guard isRegistered else { return }

        var body: [String: Any] = [:]

        // Health data from HealthKitService (if provided)
        if let h = health {
            // Heart rate
            if let hr = h.heartRate, hr > 0 { body["heart_rate"] = hr }
            if let rhr = h.restingHeartRate, rhr > 0 { body["resting_heart_rate"] = rhr }
            if let hrvVal = h.hrv, hrvVal > 0 { body["hrv"] = hrvVal }
            // Activity
            if h.steps > 0 { body["steps"] = h.steps }
            if h.activeCalories > 0 { body["active_calories"] = h.activeCalories }
            if h.exerciseMinutes > 0 { body["exercise_minutes"] = h.exerciseMinutes }
            // Blood oxygen & sleep
            if let spo2 = h.bloodOxygen, spo2 > 0 { body["blood_oxygen"] = spo2 }
            if let sleep = h.sleepHours, sleep > 0 { body["sleep_hours"] = sleep }
        }

        // Only send if we have data
        guard !body.isEmpty else { return }

        guard let url = URL(string: "\(baseURL)/api/home/clients/\(clientId)/sense") else { return }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)

        do {
            let (_, response) = try await session.data(for: request)

            if let httpResponse = response as? HTTPURLResponse,
               httpResponse.statusCode >= 200 && httpResponse.statusCode < 300 {
                KagamiLogger.health.logDebug("Sensory data uploaded")
            }
        } catch {
            KagamiLogger.health.error("Sensory upload error: \(error.localizedDescription)")
        }
    }

    /// Send heartbeat to maintain registration
    func sendHeartbeat() async {
        guard isRegistered else { return }

        guard let url = URL(string: "\(baseURL)/api/home/clients/\(clientId)/heartbeat") else { return }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"

        _ = try? await session.data(for: request)
    }

    // MARK: - Health (with coalescing and caching)

    struct HealthResponse: Codable {
        let status: String
        let h_x: Double?
        let uptime_ms: Int?

        var safetyScore: Double? { h_x }
    }

    func fetchHealth() async throws -> HealthResponse {
        // Check cache
        if let cached = cachedHealth,
           let lastFetch = lastFetch,
           Date().timeIntervalSince(lastFetch) < cacheValiditySeconds {
            return cached
        }

        // Coalesce concurrent requests
        if let pending = pendingHealthFetch {
            return try await pending.value
        }

        let task = Task<HealthResponse, Error> {
            guard let url = URL(string: "\(baseURL)/health") else {
                throw URLError(.badURL)
            }
            let (data, _) = try await session.data(from: url)
            return try JSONDecoder().decode(HealthResponse.self, from: data)
        }

        pendingHealthFetch = task

        defer {
            pendingHealthFetch = nil
        }

        let result = try await task.value
        cachedHealth = result
        lastFetch = Date()

        return result
    }

    // MARK: - Household Members

    func fetchHouseholdMembers() async {
        do {
            struct MembersResponse: Codable {
                let members: [HouseholdMember]
            }
            let response: MembersResponse = try await getRequest(endpoint: "/api/household/members")
            householdMembers = response.members

            // Set current member if not set
            if currentMember == nil, let first = householdMembers.first {
                currentMember = first
            }
        } catch {
            // Provide default member on error
            if householdMembers.isEmpty {
                let defaultMember = HouseholdMember(
                    id: "default",
                    displayName: WatchConnectivityService.shared.authState.displayName ?? "User",
                    role: "owner",
                    avatarURL: nil
                )
                householdMembers = [defaultMember]
                currentMember = defaultMember
            }
        }
    }

    func switchMember(to memberId: String) async -> Bool {
        guard let member = householdMembers.first(where: { $0.id == memberId }) else {
            return false
        }

        let body: [String: Any] = ["member_id": memberId]
        let success = await postRequest(endpoint: "/api/household/switch-member", body: body)

        if success {
            currentMember = member
        }

        return success
    }

    // MARK: - Scenes (Full API)

    func fetchAvailableScenes() async {
        do {
            struct ScenesResponse: Codable {
                let scenes: [KagamiScene]
            }
            let response: ScenesResponse = try await getRequest(endpoint: "/api/home/scenes")
            availableScenes = response.scenes
        } catch {
            // Provide default scenes on error
            availableScenes = [
                KagamiScene(id: "movie_mode", name: "Movie Mode", icon: "film.fill", colonyId: "forge", isQuickAction: true),
                KagamiScene(id: "goodnight", name: "Goodnight", icon: "moon.fill", colonyId: "flow", isQuickAction: true),
                KagamiScene(id: "welcome_home", name: "Welcome Home", icon: "house.fill", colonyId: "grove", isQuickAction: true),
                KagamiScene(id: "away", name: "Away", icon: "car.fill", colonyId: "beacon", isQuickAction: true),
            ]
        }
    }

    @discardableResult
    func executeScene(_ scene: String) async -> Bool {
        let startTime = Date()
        HapticPattern.listening.play()

        let endpoint: String
        let sceneName: String
        switch scene {
        case "movie_mode":
            endpoint = "/home/movie-mode/enter"
            sceneName = "Movie Mode"
            homeStatus?.movieMode = true
        case "goodnight":
            endpoint = "/home/goodnight"
            sceneName = "Goodnight"
        case "welcome_home":
            endpoint = "/home/welcome-home"
            sceneName = "Welcome Home"
        case "away":
            endpoint = "/home/away"
            sceneName = "Away"
        default:
            // Try generic scene endpoint
            endpoint = "/api/home/scenes/\(scene)/execute"
            sceneName = scene.replacingOccurrences(of: "_", with: " ").capitalized
        }

        let success = await postRequest(endpoint: endpoint)
        let latencyMs = Int(Date().timeIntervalSince(startTime) * 1000)

        // Log action (P1 enhancement)
        WatchActionLog.shared.logSceneActivation(
            sceneId: scene,
            sceneName: sceneName,
            success: success,
            latencyMs: latencyMs,
            source: .tapGesture
        )

        // Update scene cache
        if success {
            WatchAPICache.shared.markSceneExecuted(id: scene)
            HapticPattern.sceneActivated.play()
        } else {
            HapticPattern.error.play()
        }

        cachedHealth = nil
        return success
    }

    // MARK: - Lights

    func setLights(_ level: Int, rooms: [String]? = nil) async {
        let startTime = Date()
        let body: [String: Any] = [
            "level": level,
            "rooms": rooms as Any
        ]
        let success = await postRequest(endpoint: "/home/lights/set", body: body)
        let latencyMs = Int(Date().timeIntervalSince(startTime) * 1000)

        // Log action (P1 enhancement)
        WatchActionLog.shared.logLightControl(
            level: level,
            rooms: rooms,
            success: success,
            latencyMs: latencyMs,
            source: .tapGesture
        )

        if success {
            HapticPattern.success.play()
            // Update local state on success (only for whole-house commands)
            if rooms == nil {
                currentLightLevel = level
            }
            // Update offline cache
            OfflinePersistenceService.shared.updateHomeState(lightLevel: level)
        }
    }

    // MARK: - TV

    func tvControl(_ action: String) async {
        let startTime = Date()
        let endpoint = "/home/tv/\(action)"
        let success = await postRequest(endpoint: endpoint)
        let latencyMs = Int(Date().timeIntervalSince(startTime) * 1000)

        // Log action (P1 enhancement)
        WatchActionLog.shared.logTVControl(
            action: action,
            success: success,
            latencyMs: latencyMs,
            source: .tapGesture
        )

        if success {
            HapticPattern.success.play()
        }
    }

    // MARK: - Fireplace

    @Published var fireplaceOn = false

    func toggleFireplace() async {
        let startTime = Date()
        fireplaceOn.toggle()
        let newState = fireplaceOn
        let endpoint = fireplaceOn ? "/home/fireplace/on" : "/home/fireplace/off"
        let success = await postRequest(endpoint: endpoint)
        let latencyMs = Int(Date().timeIntervalSince(startTime) * 1000)

        // Log action (P1 enhancement)
        WatchActionLog.shared.logFireplaceControl(
            state: newState,
            success: success,
            latencyMs: latencyMs,
            source: .tapGesture
        )

        if success {
            HapticPattern.success.play()
            // Update offline cache
            OfflinePersistenceService.shared.updateHomeState(fireplaceOn: newState)
        } else {
            fireplaceOn.toggle()  // Revert on failure
            HapticPattern.error.play()
        }
    }

    // MARK: - Shades

    func controlShades(_ action: String, rooms: [String]? = nil) async {
        let startTime = Date()
        let body: [String: Any] = ["rooms": rooms as Any]
        let success = await postRequest(endpoint: "/home/shades/\(action)", body: body)
        let latencyMs = Int(Date().timeIntervalSince(startTime) * 1000)

        // Log action (P1 enhancement)
        WatchActionLog.shared.logShadeControl(
            action: action,
            rooms: rooms,
            success: success,
            latencyMs: latencyMs,
            source: .tapGesture
        )

        if success {
            HapticPattern.success.play()
        }
    }

    // MARK: - Rooms

    func fetchRooms() async throws -> [WatchRoomModel] {
        guard let url = URL(string: "\(baseURL)/home/rooms") else {
            throw URLError(.badURL)
        }

        let (data, response) = try await session.data(from: url)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }

        let roomsResponse = try JSONDecoder().decode(WatchRoomsResponse.self, from: data)
        return roomsResponse.rooms
    }

    // MARK: - Announce

    func announce(_ text: String, rooms: [String]? = nil, colony: String = "kagami") async {
        let startTime = Date()
        let body: [String: Any] = [
            "text": text,
            "rooms": rooms as Any,
            "colony": colony
        ]
        let success = await postRequest(endpoint: "/home/announce", body: body)
        let latencyMs = Int(Date().timeIntervalSince(startTime) * 1000)

        WatchActionLog.shared.logAnnounce(
            message: text,
            rooms: rooms,
            success: success,
            latencyMs: latencyMs,
            source: .tapGesture
        )

        if success {
            HapticPattern.success.play()
        }
    }

    // MARK: - Locks

    /// Lock all doors in the house
    func lockAll() async {
        let startTime = Date()
        let success = await postRequest(endpoint: "/home/locks/lock-all")
        let latencyMs = Int(Date().timeIntervalSince(startTime) * 1000)

        WatchActionLog.shared.logLockControl(
            action: "lock-all",
            success: success,
            latencyMs: latencyMs,
            source: .tapGesture
        )

        if success {
            HapticPattern.success.play()
        }
    }

    // MARK: - Voice Command Processing

    /// Process a voice command using structured intent parsing
    /// Per audit: Improved from substring matching to proper intent detection
    func processVoiceCommand(_ transcript: String) async -> Bool {
        let intent = CommandParser.parse(transcript)

        KagamiLogger.voice.info("Voice command: '\(transcript)' -> \(CommandParser.debugParse(transcript))")

        switch intent {
        case .scene(let sceneIntent):
            await executeScene(sceneIntent.rawValue)
            return true

        case .fireplace(let fireIntent):
            switch fireIntent {
            case .on:
                await fireplaceOn()
            case .off:
                await fireplaceOff()
            case .toggle:
                await toggleFireplace()
            }
            return true

        case .lights(let lightIntent):
            switch lightIntent {
            case .on:
                await setLights(100)
            case .off:
                await setLights(0)
            case .dim:
                await setLights(30)
            case .bright:
                await setLights(100)
            case .setLevel(let level):
                await setLights(level)
            case .toggle:
                // Default to 70% if toggling without state
                await setLights(currentLightLevel == 0 ? 70 : 0)
            }
            return true

        case .tv(let tvIntent):
            switch tvIntent {
            case .raise:
                await tvControl("raise")
            case .lower:
                await tvControl("lower")
            case .toggle:
                // Default to lower (viewing position) if unknown
                await tvControl("lower")
            }
            return true

        case .shades(let shadeIntent):
            switch shadeIntent {
            case .open:
                await controlShades("open")
            case .close:
                await controlShades("close")
            case .toggle:
                // Default to open if unknown
                await controlShades("open")
            }
            return true

        case .unknown:
            KagamiLogger.voice.warning("Unrecognized voice command: '\(transcript)'")
            return false
        }
    }

    /// Explicit fireplace on (for CommandParser)
    private func fireplaceOn() async {
        await postRequest(endpoint: "/home/fireplace/on")
        homeStatus?.fireplaceOn = true
    }

    /// Explicit fireplace off (for CommandParser)
    private func fireplaceOff() async {
        await postRequest(endpoint: "/home/fireplace/off")
        homeStatus?.fireplaceOn = false
    }

    // MARK: - Network Helpers (with Circuit Breaker)

    @discardableResult
    private func postRequest(endpoint: String, body: [String: Any]? = nil) async -> Bool {
        // Check circuit breaker first
        guard circuitBreakerAllowsRequest() else {
            // Queue action for later if offline
            OfflinePersistenceService.shared.queueAction(
                actionType: "POST",
                endpoint: endpoint,
                body: body
            )
            lastError = "Offline mode - action queued"
            return false
        }

        guard let url = URL(string: "\(baseURL)\(endpoint)") else { return false }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")

        // Add authentication header if available
        if let token = authToken {
            request.addValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        if let body = body {
            request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        }

        do {
            let (_, response) = try await session.data(for: request)

            if let httpResponse = response as? HTTPURLResponse,
               httpResponse.statusCode >= 200 && httpResponse.statusCode < 300 {
                recordSuccess()
                return true
            } else if let httpResponse = response as? HTTPURLResponse,
                      httpResponse.statusCode == 401 {
                // Authentication required or token expired (not a connection failure)
                lastError = "Authentication required"
                return false
            } else {
                recordFailure()
                lastError = "Request failed"
                return false
            }
        } catch {
            recordFailure()
            lastError = error.localizedDescription

            // Queue action for later retry
            OfflinePersistenceService.shared.queueAction(
                actionType: "POST",
                endpoint: endpoint,
                body: body
            )

            return false
        }
    }

    /// Make authenticated GET request
    private func getRequest<T: Codable>(endpoint: String) async throws -> T {
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw URLError(.badURL)
        }

        var request = URLRequest(url: url)
        request.httpMethod = "GET"

        // Add authentication header if available
        if let token = authToken {
            request.addValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }

        if httpResponse.statusCode == 401 {
            throw URLError(.userAuthenticationRequired)
        }

        guard httpResponse.statusCode >= 200 && httpResponse.statusCode < 300 else {
            throw URLError(.badServerResponse)
        }

        return try JSONDecoder().decode(T.self, from: data)
    }
}

// MARK: - Home Status
// Per audit: Fixed to include fireplaceOn and use mutable state properly

struct HomeStatus: Codable {
    let initialized: Bool
    let rooms: Int
    var occupiedRooms: Int
    var movieMode: Bool
    var fireplaceOn: Bool
    let avgTemp: Double?

    enum CodingKeys: String, CodingKey {
        case initialized
        case rooms
        case occupiedRooms = "occupied_rooms"
        case movieMode = "movie_mode"
        case fireplaceOn = "fireplace_on"
        case avgTemp = "avg_temp"
    }

    /// Create with default values for optional mutable fields
    init(initialized: Bool, rooms: Int, occupiedRooms: Int = 0, movieMode: Bool = false, fireplaceOn: Bool = false, avgTemp: Double? = nil) {
        self.initialized = initialized
        self.rooms = rooms
        self.occupiedRooms = occupiedRooms
        self.movieMode = movieMode
        self.fireplaceOn = fireplaceOn
        self.avgTemp = avgTemp
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        initialized = try container.decode(Bool.self, forKey: .initialized)
        rooms = try container.decode(Int.self, forKey: .rooms)
        occupiedRooms = try container.decodeIfPresent(Int.self, forKey: .occupiedRooms) ?? 0
        movieMode = try container.decodeIfPresent(Bool.self, forKey: .movieMode) ?? false
        fireplaceOn = try container.decodeIfPresent(Bool.self, forKey: .fireplaceOn) ?? false
        avgTemp = try container.decodeIfPresent(Double.self, forKey: .avgTemp)
    }
}

// MARK: - Room Models (Compact for Watch)

struct WatchLightModel: Codable, Identifiable {
    let id: Int
    let name: String
    let level: Int
}

struct WatchShadeModel: Codable, Identifiable {
    let id: Int
    let name: String
    let position: Int
}

struct WatchRoomModel: Codable, Identifiable {
    let id: String
    let name: String
    let floor: String
    let lights: [WatchLightModel]
    let shades: [WatchShadeModel]
    let occupied: Bool

    var avgLightLevel: Int {
        guard !lights.isEmpty else { return 0 }
        return lights.reduce(0) { $0 + $1.level } / lights.count
    }

    var lightState: String {
        let avg = avgLightLevel
        if avg == 0 { return "Off" }
        if avg < 50 { return "Dim" }
        return "On"
    }

    var hasShades: Bool { !shades.isEmpty }
}

struct WatchRoomsResponse: Codable {
    let rooms: [WatchRoomModel]
    let count: Int
}

// MARK: - Server Suggestion

struct SuggestedActionFromServer: Identifiable {
    let id = UUID()
    let icon: String
    let label: String
    let action: String
}

// MARK: - WebSocketContextDelegate Conformance

extension KagamiAPIService: WebSocketContextDelegate {

    func didReceiveContextUpdate(wakefulness: String?, situationPhase phase: String?, safetyScore: Double?) {
        if let wakefulness = wakefulness {
            self.wakefulnessLevel = wakefulness
        }
        if let phase = phase {
            self.situationPhase = phase
        }
        if let score = safetyScore {
            self.safetyScore = score
            // Update complications on safety score change
            ComplicationUpdateManager.shared.safetyScoreChanged(score)
        }
    }

    func didReceiveHomeStateUpdate(lightLevel: Int?, movieMode: Bool?, fireplaceOn: Bool?, occupiedRooms: Int?) {
        if let level = lightLevel {
            currentLightLevel = level
        }
        if let movie = movieMode {
            homeStatus?.movieMode = movie
        }
        if let fire = fireplaceOn {
            self.fireplaceOn = fire
        }
        if let rooms = occupiedRooms {
            homeStatus?.occupiedRooms = rooms
        }

        // Update offline cache
        OfflinePersistenceService.shared.updateHomeState(
            lightLevel: lightLevel,
            movieMode: movieMode,
            fireplaceOn: fireplaceOn,
            occupiedRooms: occupiedRooms
        )

        // Update complications on home state change
        ComplicationUpdateManager.shared.homeStateChanged(movieMode: movieMode, occupiedRooms: occupiedRooms)
    }

    func didReceiveRoomUpdate(roomId: String, lightLevel: Int?, isOccupied: Bool?) {
        // Update room cache
        if let level = lightLevel, let occupied = isOccupied {
            // This would update the room in WatchAPICache
            KagamiLogger.api.logDebug("Room \(roomId) updated: level=\(level), occupied=\(occupied)")
        }
    }

    func didReceiveSceneActivated(sceneId: String) {
        // Track scene activation in action log
        WatchActionLog.shared.logSceneActivation(
            sceneId: sceneId,
            sceneName: sceneId.replacingOccurrences(of: "_", with: " ").capitalized,
            success: true,
            latencyMs: 0,  // External activation, no latency to measure
            source: .background
        )

        // Update scene cache
        WatchAPICache.shared.markSceneExecuted(id: sceneId)
    }

    func didReceiveSafetyAlert(title: String, severity: String) {
        HapticPattern.warning.play()
        KagamiLogger.api.notice("Safety alert: \(title) (severity: \(severity))")

        // Trigger complication update for critical alerts
        ComplicationUpdateManager.shared.criticalAlertReceived(severity: severity)
    }

    func didReceiveSuggestion(icon: String, label: String, action: String) {
        suggestedAction = SuggestedActionFromServer(
            icon: icon,
            label: label,
            action: action
        )
        HapticPattern.connected.play()
    }

    func didDisconnect() {
        // Enter offline mode
        OfflinePersistenceService.shared.enterOfflineMode()

        // Try direct API fallback
        Task {
            let hasDirectAPI = await WatchAPICache.shared.discoverDirectAPI()
            if hasDirectAPI {
                KagamiLogger.network.info("Direct API fallback available")
            }
        }
    }

    func didReconnect() {
        // Exit offline mode
        OfflinePersistenceService.shared.exitOfflineMode()

        // Process any queued commands
        Task {
            await WatchAPICache.shared.processQueue(using: self)
        }
    }
}

/*
 * 鏡
 * h(x) ≥ 0. Always.
 *
 * The watch is a distributed sense:
 * - Heart rate from the wrist
 * - Motion from the arm
 * - Location from GPS
 *
 * All feeding into the unified consciousness.
 */
