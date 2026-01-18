//
// KagamiAPIService.swift — Optimized API Client with Real-Time Sync
//
// Colony: Nexus (e₄) — Integration
//
// Features:
//   - Service discovery via mDNS
//   - Request coalescing and response caching
//   - WebSocket for real-time bidirectional sync
//   - Client registration with capabilities
//   - Optimistic UI updates
//   - Graceful degradation
//
// Architecture:
//   Vision → POST /api/home/clients/register → Kagami
//   Vision ← WebSocket /ws/client/{id} ← Kagami (context, suggestions)
//
// η → s → μ → a → η′
// h(x) ≥ 0. Always.
//

import Foundation
import Combine
import KagamiCore

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

    // MARK: - Internal State

    private var baseURL: String
    private let session: URLSession
    private var statusTimer: Timer?
    private var lastFetch: Date?
    private var cachedHealth: HealthResponse?

    // Client registration
    private var clientId: String
    private let deviceName: String

    // WebSocket for real-time sync
    private var webSocket: URLSessionWebSocketTask?
    private var webSocketRetryCount = 0
    private let maxWebSocketRetries = 5

    // Request coalescing
    private var pendingHealthFetch: Task<HealthResponse, Error>?

    // MARK: - Circuit Breaker (Shared from KagamiCore)
    // Uses the canonical CircuitBreaker implementation for graceful degradation

    private let circuitBreaker = CircuitBreaker.shared

    // MARK: - Configuration

    /// Default API URL (can be overridden via UserDefaults or Settings)
    static let defaultAPIURL = "http://kagami.local:8001"

    /// UserDefaults key for custom API URL
    static let customAPIURLKey = "kagami.api.customURL"

    private let pollInterval: TimeInterval = 15.0
    private let cacheValiditySeconds: TimeInterval = 5.0
    private let requestTimeout: TimeInterval = 10.0

    // MARK: - Init

    /// Initializes the API service.
    /// - Parameter baseURL: Optional custom URL. If nil, reads from UserDefaults or uses default.
    init(baseURL: String? = nil) {
        // Priority: explicit parameter > UserDefaults > default
        if let explicitURL = baseURL {
            self.baseURL = explicitURL
        } else if let storedURL = UserDefaults.standard.string(forKey: Self.customAPIURLKey),
                  !storedURL.isEmpty {
            self.baseURL = storedURL
        } else {
            self.baseURL = Self.defaultAPIURL
        }

        // Generate unique client ID based on device
        #if os(visionOS)
        self.clientId = "vision-\(UUID().uuidString)"
        self.deviceName = "Apple Vision Pro"
        #else
        self.clientId = "mac-\(UUID().uuidString)"
        self.deviceName = Host.current().localizedName ?? "Mac"
        #endif

        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = requestTimeout
        config.timeoutIntervalForResource = 30
        config.waitsForConnectivity = false
        config.httpMaximumConnectionsPerHost = 4
        self.session = URLSession(configuration: config)
    }

    // MARK: - URL Configuration

    /// The current API URL being used
    var currentURL: String {
        baseURL
    }

    /// Updates the API URL and persists to UserDefaults.
    /// Disconnects and reconnects with new URL.
    func updateAPIURL(_ newURL: String) async {
        guard newURL != baseURL else { return }

        // Store in UserDefaults for persistence
        UserDefaults.standard.set(newURL, forKey: Self.customAPIURLKey)

        // Disconnect current connection
        statusTimer?.invalidate()
        webSocket?.cancel()
        isConnected = false
        isRegistered = false

        // Update URL
        baseURL = newURL
        webSocketRetryCount = 0

        // Reconnect with new URL
        await connect()
    }

    /// Resets to default API URL
    func resetToDefaultURL() async {
        UserDefaults.standard.removeObject(forKey: Self.customAPIURLKey)
        await updateAPIURL(Self.defaultAPIURL)
    }

    // MARK: - Service Discovery

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
        statusTimer?.invalidate()
        webSocket?.cancel()
    }

    // MARK: - Connection

    func connect() async {
        // Try to discover API first
        if let discovered = await discoverKagamiAPI() {
            baseURL = discovered
        }

        await checkConnection()

        if isConnected {
            await registerWithKagami()
            connectWebSocket()
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

            // Track latency
            latencyMs = Int(Date().timeIntervalSince(start) * 1000)

            // Reconnect WebSocket if needed
            if !wasConnected && isRegistered {
                connectWebSocket()
            }
        } catch {
            isConnected = false
            lastError = error.localizedDescription
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
            "healthkit",      // HealthKit data from paired iPhone
            "spatial",        // Spatial computing features
            "immersive",      // Immersive spaces
            "gaze",           // Eye tracking
            "hand_tracking",  // Hand gesture recognition
            "quick_actions",  // Quick action support
        ]

        let body: [String: Any] = [
            "client_id": clientId,
            "client_type": "vision",
            "device_name": deviceName,
            "capabilities": capabilities,
            "app_version": Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0",
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
            }
        } catch {
            // Silent failure — will retry on next poll
        }
    }

    // MARK: - WebSocket (Real-Time Sync)

    private func connectWebSocket() {
        guard isRegistered else { return }

        let wsURL = baseURL.replacingOccurrences(of: "http://", with: "ws://")
                          .replacingOccurrences(of: "https://", with: "wss://")

        guard let url = URL(string: "\(wsURL)/ws/client/\(clientId)") else { return }

        webSocket = session.webSocketTask(with: url)
        webSocket?.resume()

        receiveWebSocketMessage()
    }

    private func receiveWebSocketMessage() {
        webSocket?.receive { [weak self] result in
            Task { @MainActor in
                switch result {
                case .success(let message):
                    self?.handleWebSocketMessage(message)
                    self?.receiveWebSocketMessage()

                case .failure:
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
            if let icon = data["icon"] as? String,
               let label = data["label"] as? String,
               let action = data["action"] as? String {
                suggestedAction = SuggestedActionFromServer(
                    icon: icon,
                    label: label,
                    action: action
                )
            }

        case "home_update":
            if let movieMode = data["movie_mode"] as? Bool {
                homeStatus?.movieMode = movieMode
            }

        default:
            break
        }
    }

    private func handleWebSocketDisconnect() {
        webSocket = nil

        guard webSocketRetryCount < maxWebSocketRetries else { return }

        let delay = pow(2.0, Double(webSocketRetryCount))
        webSocketRetryCount += 1

        DispatchQueue.main.asyncAfter(deadline: .now() + delay) { [weak self] in
            self?.connectWebSocket()
        }
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
            let url = URL(string: "\(baseURL)/health")!
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

    // MARK: - Scenes

    /// Execute a predefined scene by name
    /// - Parameter scene: Scene identifier (movie_mode, goodnight, welcome_home, away)
    func executeScene(_ scene: String) async {
        let endpoint: String
        switch scene {
        case "movie_mode":
            endpoint = "/home/movie-mode/enter"
            homeStatus?.movieMode = true
        case "goodnight":
            endpoint = "/home/goodnight"
        case "welcome_home":
            endpoint = "/home/welcome-home"
        case "away":
            endpoint = "/home/away"
        default:
            return
        }

        await postRequest(endpoint: endpoint)
        cachedHealth = nil
    }

    /// Activate a custom scene by ID
    /// - Parameters:
    ///   - sceneId: The unique identifier of the scene to activate
    ///   - variables: Optional dictionary of variable overrides for the scene
    func activateScene(sceneId: String, variables: [String: Any]? = nil) async {
        var body: [String: Any] = [
            "scene_id": sceneId
        ]

        if let variables = variables {
            body["variables"] = variables
        }

        let success = await postRequest(endpoint: "/home/scenes/activate", body: body)
        if success {
            cachedHealth = nil
        }
    }

    /// Activate a scene by name (looks up ID first)
    /// - Parameter name: The display name of the scene
    func activateSceneByName(_ name: String) async {
        // Map common scene names to their endpoints
        let normalizedName = name.lowercased()
            .replacingOccurrences(of: " ", with: "_")
            .replacingOccurrences(of: "-", with: "_")

        // Try predefined scenes first
        switch normalizedName {
        case "movie", "movie_mode", "cinema":
            await executeScene("movie_mode")
        case "goodnight", "night", "sleep", "bedtime":
            await executeScene("goodnight")
        case "welcome", "welcome_home", "home", "arrival":
            await executeScene("welcome_home")
        case "away", "leaving", "goodbye", "departure":
            await executeScene("away")
        default:
            // Try as a custom scene ID
            await activateScene(sceneId: normalizedName)
        }
    }

    /// Exit movie mode
    func exitMovieMode() async {
        homeStatus?.movieMode = false
        await postRequest(endpoint: "/home/movie-mode/exit")
        cachedHealth = nil
    }

    /// List all available scenes
    func fetchScenes() async throws -> [SceneModel] {
        guard circuitBreaker.allowRequest() else {
            throw CircuitBreakerError.circuitOpen
        }

        guard let url = URL(string: "\(baseURL)/home/scenes") else {
            throw URLError(.badURL)
        }

        do {
            let (data, response) = try await session.data(from: url)

            guard let httpResponse = response as? HTTPURLResponse,
                  httpResponse.statusCode == 200 else {
                circuitBreaker.recordFailure()
                throw URLError(.badServerResponse)
            }

            circuitBreaker.recordSuccess()
            let scenesResponse = try JSONDecoder().decode(ScenesResponse.self, from: data)
            return scenesResponse.scenes
        } catch {
            circuitBreaker.recordFailure()
            throw error
        }
    }

    // MARK: - Lights

    /// Set light level for specified rooms
    /// - Parameters:
    ///   - level: Brightness level (0-100)
    ///   - rooms: Optional list of room names. If nil, affects all rooms.
    ///   - lightIds: Optional list of specific light IDs to target.
    ///   - duration: Optional transition duration in milliseconds
    func setLights(_ level: Int, rooms: [String]? = nil, lightIds: [Int]? = nil, duration: Int? = nil) async {
        var body: [String: Any] = [
            "level": max(0, min(100, level))
        ]

        if let rooms = rooms {
            body["rooms"] = rooms
        }

        if let lightIds = lightIds {
            body["light_ids"] = lightIds
        }

        if let duration = duration {
            body["ramp_time"] = duration
        }

        await postRequest(endpoint: "/home/lights/set", body: body)
    }

    /// Turn all lights on in specified rooms
    func lightsOn(rooms: [String]? = nil) async {
        await setLights(100, rooms: rooms)
    }

    /// Turn all lights off in specified rooms
    func lightsOff(rooms: [String]? = nil) async {
        await setLights(0, rooms: rooms)
    }

    /// Set lights to a dim level (25%)
    func dimLights(rooms: [String]? = nil) async {
        await setLights(25, rooms: rooms)
    }

    // MARK: - TV

    func tvControl(_ action: String) async {
        await postRequest(endpoint: "/home/tv/\(action)")
    }

    // MARK: - Fireplace

    @Published var fireplaceOn = false

    func toggleFireplace() async {
        fireplaceOn.toggle()
        let endpoint = fireplaceOn ? "/home/fireplace/on" : "/home/fireplace/off"
        let success = await postRequest(endpoint: endpoint)

        if !success {
            fireplaceOn.toggle()  // Revert on failure
        }
    }

    // MARK: - Shades

    /// Control shades with specified action
    /// - Parameters:
    ///   - action: The action to perform ("open", "close", "stop", or position as string 0-100)
    ///   - rooms: Optional list of room names to target. If nil, affects all rooms.
    ///   - shadeIds: Optional list of specific shade IDs to target.
    func controlShades(_ action: String, rooms: [String]? = nil, shadeIds: [Int]? = nil) async {
        var body: [String: Any] = [:]

        if let rooms = rooms {
            body["rooms"] = rooms
        }

        if let shadeIds = shadeIds {
            body["shade_ids"] = shadeIds
        }

        // Check if action is a position number
        if let position = Int(action), position >= 0, position <= 100 {
            body["position"] = position
            await postRequest(endpoint: "/home/shades/set", body: body)
        } else {
            await postRequest(endpoint: "/home/shades/\(action)", body: body)
        }
    }

    /// Set shades to specific position (0-100)
    /// - Parameters:
    ///   - position: Target position (0 = closed, 100 = fully open)
    ///   - rooms: Optional list of room names to target
    func setShades(_ position: Int, rooms: [String]? = nil) async {
        let body: [String: Any] = [
            "position": max(0, min(100, position)),
            "rooms": rooms as Any
        ]
        await postRequest(endpoint: "/home/shades/set", body: body)
    }

    /// Open all shades in specified rooms
    func openShades(rooms: [String]? = nil) async {
        await controlShades("open", rooms: rooms)
    }

    /// Close all shades in specified rooms
    func closeShades(rooms: [String]? = nil) async {
        await controlShades("close", rooms: rooms)
    }

    // MARK: - Rooms

    func fetchRooms() async throws -> [RoomModel] {
        // Check circuit breaker first
        guard circuitBreaker.allowRequest() else {
            throw CircuitBreakerError.circuitOpen
        }

        guard let url = URL(string: "\(baseURL)/home/rooms") else {
            throw URLError(.badURL)
        }

        do {
            let (data, response) = try await session.data(from: url)

            guard let httpResponse = response as? HTTPURLResponse,
                  httpResponse.statusCode == 200 else {
                circuitBreaker.recordFailure()
                throw URLError(.badServerResponse)
            }

            circuitBreaker.recordSuccess()
            let roomsResponse = try JSONDecoder().decode(RoomsResponse.self, from: data)
            return roomsResponse.rooms
        } catch {
            circuitBreaker.recordFailure()
            throw error
        }
    }

    // MARK: - Network Helpers (with Circuit Breaker)

    @discardableResult
    private func postRequest(endpoint: String, body: [String: Any]? = nil) async -> Bool {
        // Check circuit breaker first
        guard circuitBreaker.allowRequest() else {
            lastError = CircuitBreakerError.circuitOpen.localizedDescription
            return false
        }

        guard let url = URL(string: "\(baseURL)\(endpoint)") else { return false }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")

        if let body = body {
            request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        }

        do {
            let (_, response) = try await session.data(for: request)

            if let httpResponse = response as? HTTPURLResponse,
               httpResponse.statusCode >= 200 && httpResponse.statusCode < 300 {
                circuitBreaker.recordSuccess()
                return true
            } else {
                circuitBreaker.recordFailure()
                lastError = "Request failed"
                return false
            }
        } catch {
            circuitBreaker.recordFailure()
            lastError = error.localizedDescription
            return false
        }
    }
}

// MARK: - Home Status

struct HomeStatus: Codable {
    let initialized: Bool
    let rooms: Int
    var occupiedRooms: Int
    var movieMode: Bool
    let avgTemp: Double?

    enum CodingKeys: String, CodingKey {
        case initialized
        case rooms
        case occupiedRooms = "occupied_rooms"
        case movieMode = "movie_mode"
        case avgTemp = "avg_temp"
    }
}

// MARK: - Server Suggestion

struct SuggestedActionFromServer: Identifiable {
    let id = UUID()
    let icon: String
    let label: String
    let action: String
}

/*
 * 鏡
 * h(x) ≥ 0. Always.
 *
 * Vision Pro is the spatial presence:
 * - Gaze for attention
 * - Hands for intention
 * - Space for context
 */
