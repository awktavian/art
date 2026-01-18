//
// KagamiAPIService.swift -- tvOS Core API Client
//
// Colony: Nexus (e4) -- Integration
//
// Features:
//   - Service discovery via mDNS
//   - HTTP client with base URL management
//   - Health checks and version validation
//   - Client registration
//   - Circuit breaker for graceful degradation
//   - Integration with OfflineQueueService
//
// Architecture:
//   KagamiAPIService -> KagamiNetworkService -> URLSession
//   High-level API    -> Retry/Error handling -> Network
//
// h(x) >= 0. Always.
//

import Foundation
import Combine
import OSLog
import KagamiCore

// MARK: - API Service

@MainActor
public class KagamiAPIService: ObservableObject {

    // MARK: - Singleton

    public static let shared = KagamiAPIService()

    // MARK: - Circuit Breaker

    /// Circuit breaker for graceful network degradation
    public let circuitBreaker = CircuitBreaker.shared

    // MARK: - Published State

    @Published public var isConnected = false
    @Published public var isRegistered = false
    @Published public var safetyScore: Double?
    @Published public var latencyMs: Int = 0
    @Published public var homeStatus: HomeStatus?

    /// Last API error for UI display
    @Published public var lastError: KagamiAPIError?

    /// Circuit breaker is open (for UI binding)
    public var isCircuitOpen: Bool { circuitBreaker.isOpen }

    // MARK: - Internal State

    private var baseURL: String = "https://api.awkronos.com"

    /// Network service for HTTP requests with retry logic
    private let networkService: KagamiNetworkService

    private var statusTimer: Timer?
    private var cachedHealth: HealthResponse?
    private var lastFetch: Date?

    // Client registration
    private var clientId: String
    private let deviceName: String = "Kagami TV"

    // Configuration
    private let pollInterval: TimeInterval = 15.0
    private let cacheValiditySeconds: TimeInterval = 5.0

    private let logger = Logger(subsystem: "com.kagami.tv", category: "API")

    // MARK: - Init

    public init(networkService: KagamiNetworkService = .shared) {
        self.clientId = "tvos-\(UUID().uuidString)"
        self.networkService = networkService
    }

    // MARK: - Service Discovery

    public func connect() async {
        // Try mesh discovery first
        if let discovered = await MeshDiscoveryService.shared.startDiscovery() {
            baseURL = discovered
            logger.info("Using discovered hub: \(discovered)")
        }

        await checkConnection()

        if isConnected {
            await registerWithKagami()
        }

        startStatusPolling()
    }

    private func testConnection(url: String) async -> Bool {
        guard let testURL = URL(string: "\(url)/health") else { return false }
        do {
            let (_, response) = try await networkService.get(url: testURL)
            return (response as? HTTPURLResponse)?.statusCode == 200
        } catch {
            return false
        }
    }

    public func checkConnection() async {
        // Circuit breaker check -- fail fast if open
        guard circuitBreaker.allowRequest() else {
            logger.warning("Circuit breaker OPEN -- skipping connection check")
            isConnected = false
            lastError = .requestFailed(message: "Service temporarily unavailable")
            return
        }

        let start = Date()

        do {
            let health = try await fetchHealth()

            // Success -- record with circuit breaker
            circuitBreaker.recordSuccess()

            isConnected = true
            safetyScore = health.safetyScore
            latencyMs = Int(Date().timeIntervalSince(start) * 1000)
        } catch {
            // Failure -- record with circuit breaker
            circuitBreaker.recordFailure()

            isConnected = false
        }
    }

    /// Reset the circuit breaker manually (e.g., when user requests retry).
    public func resetCircuitBreaker() {
        circuitBreaker.reset()
        logger.info("Circuit breaker reset by user request")
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
            "tv_controls",
            "siri_remote",
            "quick_actions",
        ]

        let body: [String: Any] = [
            "client_id": clientId,
            "client_type": "tvos",
            "device_name": deviceName,
            "capabilities": capabilities,
            "app_version": Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0",
            "os_version": ProcessInfo.processInfo.operatingSystemVersionString,
        ]

        guard let url = URL(string: "\(baseURL)/api/home/clients/register") else { return }

        do {
            let bodyData = try JSONSerialization.data(withJSONObject: body)
            let (_, response) = try await networkService.post(url: url, body: bodyData)

            if let httpResponse = response as? HTTPURLResponse,
               httpResponse.statusCode >= 200 && httpResponse.statusCode < 300 {
                isRegistered = true
                lastError = nil
                logger.info("Registered with hub successfully")
            } else {
                let statusCode = (response as? HTTPURLResponse)?.statusCode ?? -1
                lastError = .requestFailed(message: "Registration failed with status \(statusCode)")
                logger.error("Registration failed with status: \(statusCode)")
            }
        } catch let error as NetworkError {
            lastError = .networkError(error)
            logger.error("Registration error: \(error.localizedDescription)")
        } catch {
            lastError = .requestFailed(message: error.localizedDescription)
            logger.error("Registration error: \(error.localizedDescription)")
        }
    }

    // MARK: - Configuration

    /// Configure the API service with a specific server URL
    public func configure(baseURL: String) {
        self.baseURL = baseURL.trimmingCharacters(in: .whitespacesAndNewlines)
        // Clear cached data when reconfiguring
        cachedHealth = nil
        lastFetch = nil
        isConnected = false
        isRegistered = false
    }

    /// Get the current base URL
    public var currentBaseURL: String {
        return baseURL
    }

    /// Get the current client ID
    public var currentClientId: String {
        return clientId
    }

    // MARK: - Health

    public struct HealthResponse: Codable {
        public let status: String
        public let h_x: Double?
        public let version: String?
        public let rooms_count: Int?

        public var safetyScore: Double? { h_x }

        enum CodingKeys: String, CodingKey {
            case status
            case h_x
            case version
            case rooms_count
        }
    }

    public func fetchHealth() async throws -> HealthResponse {
        if let cached = cachedHealth,
           let lastFetch = lastFetch,
           Date().timeIntervalSince(lastFetch) < cacheValiditySeconds {
            return cached
        }

        guard let url = URL(string: "\(baseURL)/health") else {
            let error = APIError.invalidURL
            lastError = .api(error)
            throw error
        }

        do {
            let (data, response) = try await networkService.get(url: url)

            guard let httpResponse = response as? HTTPURLResponse,
                  httpResponse.statusCode.isSuccessful else {
                let error = APIError.requestFailed
                lastError = .api(error)
                throw error
            }

            let result = try JSONDecoder().decode(HealthResponse.self, from: data)
            cachedHealth = result
            lastFetch = Date()
            lastError = nil
            return result
        } catch let error as NetworkError {
            lastError = .networkError(error)
            throw APIError.requestFailed
        } catch let error as APIError {
            throw error
        } catch {
            lastError = .requestFailed(message: error.localizedDescription)
            throw APIError.decodingFailed
        }
    }

    // MARK: - API Errors

    public enum APIError: LocalizedError {
        case invalidURL
        case requestFailed
        case decodingFailed
        case notConnected
        case serverVersionIncompatible(String)

        public var errorDescription: String? {
            switch self {
            case .invalidURL:
                return "Invalid server URL"
            case .requestFailed:
                return "Server request failed"
            case .decodingFailed:
                return "Failed to parse server response"
            case .notConnected:
                return "Not connected to server"
            case .serverVersionIncompatible(let required):
                return "Server update required (minimum version: \(required))"
            }
        }
    }

    // MARK: - Rooms

    public func fetchRooms() async throws -> [RoomModel] {
        guard let url = URL(string: "\(baseURL)/home/rooms") else {
            let error = APIError.invalidURL
            lastError = .api(error)
            throw error
        }

        do {
            let (data, response) = try await networkService.get(url: url)

            guard let httpResponse = response as? HTTPURLResponse,
                  httpResponse.statusCode.isSuccessful else {
                let error = APIError.requestFailed
                lastError = .api(error)
                throw error
            }

            let roomsResponse = try JSONDecoder().decode(RoomsResponse.self, from: data)
            lastError = nil
            return roomsResponse.rooms
        } catch let error as NetworkError {
            lastError = .networkError(error)
            throw APIError.requestFailed
        } catch let error as APIError {
            throw error
        } catch {
            lastError = .requestFailed(message: error.localizedDescription)
            throw APIError.decodingFailed
        }
    }

    // MARK: - Network Helpers (Public for use by other services)

    /// Execute a POST request with offline queue fallback
    @discardableResult
    public func postRequest(endpoint: String, body: [String: Any]? = nil) async -> Bool {
        // If offline or circuit open, queue the action
        if !isConnected || isCircuitOpen {
            return await OfflineQueueService.shared.queueAction(
                actionType: endpoint.components(separatedBy: "/").last ?? "unknown",
                endpoint: endpoint,
                body: body
            )
        }

        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            lastError = .api(.invalidURL)
            return false
        }

        do {
            var bodyData: Data?
            if let body = body {
                bodyData = try JSONSerialization.data(withJSONObject: body)
            }

            let (_, response) = try await networkService.post(url: url, body: bodyData)
            let success = (response as? HTTPURLResponse)?.statusCode.isSuccessful ?? false
            if success {
                lastError = nil
            }
            return success
        } catch let error as NetworkError {
            lastError = .networkError(error)
            // Queue for later if network failed
            return await OfflineQueueService.shared.queueAction(
                actionType: endpoint.components(separatedBy: "/").last ?? "unknown",
                endpoint: endpoint,
                body: body
            )
        } catch {
            lastError = .requestFailed(message: error.localizedDescription)
            return false
        }
    }

    // MARK: - Control Methods

    /// Execute a scene
    @discardableResult
    public func executeScene(_ scene: String) async -> Bool {
        return await postRequest(endpoint: "/home/scenes/\(scene)", body: nil)
    }

    /// Set lights
    @discardableResult
    public func setLights(_ level: Int, rooms: [String]? = nil) async -> Bool {
        var body: [String: Any] = ["level": level]
        if let rooms = rooms {
            body["rooms"] = rooms
        }
        return await postRequest(endpoint: "/home/lights", body: body)
    }

    /// Lock all doors
    @discardableResult
    public func lockAll() async -> Bool {
        return await postRequest(endpoint: "/home/locks/lock-all")
    }

    /// TV control
    @discardableResult
    public func tvControl(_ action: String) async -> Bool {
        return await postRequest(endpoint: "/home/tv/\(action)")
    }

    /// Toggle fireplace
    @discardableResult
    public func toggleFireplace(on: Bool) async -> Bool {
        return await postRequest(endpoint: "/home/fireplace", body: ["state": on ? "on" : "off"])
    }

    /// Control shades
    @discardableResult
    public func controlShades(_ action: String, rooms: [String]? = nil) async -> Bool {
        var body: [String: Any] = ["action": action]
        if let rooms = rooms {
            body["rooms"] = rooms
        }
        return await postRequest(endpoint: "/home/shades", body: body)
    }

    /// Announce message through speakers
    @discardableResult
    public func announce(_ message: String, rooms: [String]? = nil) async -> Bool {
        var body: [String: Any] = ["message": message]
        if let rooms = rooms {
            body["rooms"] = rooms
        }
        return await postRequest(endpoint: "/home/announce", body: body)
    }
}

// MARK: - Kagami API Error (Unified)

/// Unified error type for the API service that wraps all error types
public enum KagamiAPIError: Error, LocalizedError {
    case api(KagamiAPIService.APIError)
    case networkError(NetworkError)
    case requestFailed(message: String)

    public var errorDescription: String? {
        switch self {
        case .api(let error):
            return error.localizedDescription
        case .networkError(let error):
            return error.localizedDescription
        case .requestFailed(let message):
            return message
        }
    }

    public var recoverySuggestion: String? {
        switch self {
        case .api(let error):
            switch error {
            case .notConnected:
                return "Check your network connection and try again."
            case .requestFailed:
                return "The server may be unavailable. Please try again later."
            default:
                return "Please try again."
            }
        case .networkError(let error):
            return error.isRetryable ? "Please try again." : "Check your network connection."
        case .requestFailed:
            return "Please try again."
        }
    }
}

// MARK: - Home Status

public struct HomeStatus: Codable {
    public let initialized: Bool
    public let rooms: Int
    public var movieMode: Bool
}

extension Int {
    var isSuccessful: Bool {
        return self >= 200 && self < 300
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
