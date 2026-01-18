//
// KagamiAPIService.swift — iOS Core API Client
//
// Colony: Nexus (e4) — Integration
//
// Features:
//   - Service discovery via mDNS
//   - HTTP client with base URL management
//   - Authentication (login, register, logout)
//   - Health checks and version validation
//   - Client registration
//   - Delegates to KagamiNetworkService for HTTP with retry logic
//
// Architecture:
//   KagamiAPIService -> KagamiNetworkService -> URLSession
//   High-level API    -> Retry/Error handling -> Network
//
// Related Services (split from original god object):
//   - KagamiWebSocketService: WebSocket connection management
//   - SceneService: Scene execution (movie mode, goodnight, etc.)
//   - DeviceControlService: Lights, TV, fireplace, shades
//   - SensoryService: Sensory data uploads
//

import Foundation
import Combine
import UIKit
import KagamiCore

@MainActor
public class KagamiAPIService: ObservableObject {

    // MARK: - Singleton

    public static let shared = KagamiAPIService()

    // MARK: - Circuit Breaker (via MeshService)

    /// Circuit breaker for graceful network degradation - provided by MeshService
    /// MeshService wraps the kagami-mesh-sdk which provides unified circuit breaker state
    public var meshService: MeshService { MeshService.shared }

    // MARK: - Published State

    @Published public var isConnected = false
    @Published public var isRegistered = false
    @Published public var safetyScore: Double?
    @Published public var latencyMs: Int = 0
    @Published public var homeStatus: HomeStatus?

    /// Last API error for UI display
    @Published public var lastError: KagamiAPIError?

    /// Circuit breaker is open (for UI binding)
    public var isCircuitOpen: Bool { meshService.connectionState == .circuitOpen }

    // MARK: - Authentication State

    @Published public var isAuthenticated = false

    // MARK: - Internal State

    private var baseURL: String = "https://api.awkronos.com"

    /// Network service for HTTP requests with retry logic
    private let networkService: KagamiNetworkService

    private var statusTimer: Timer?
    private var cachedHealth: HealthResponse?
    private var lastFetch: Date?

    // Client registration
    private var clientId: String
    private let deviceName: String

    // Configuration
    private let pollInterval: TimeInterval = 15.0
    private let cacheValiditySeconds: TimeInterval = 5.0

    // MARK: - Init

    public init(networkService: KagamiNetworkService = .shared) {
        self.clientId = "ios-\(UUID().uuidString)"
        self.deviceName = UIDevice.current.name
        self.networkService = networkService
    }

    // MARK: - Service Discovery

    public func connect() async {
        if let discovered = await discoverKagamiAPI() {
            baseURL = discovered
        }

        await checkConnection()

        if isConnected {
            await registerWithKagami()

            // Configure and start related services
            configureRelatedServices()
        }

        startStatusPolling()
    }

    private func discoverKagamiAPI() async -> String? {
        // Discovery priority:
        // 1. Production API (always available)
        // 2. Local mDNS (home network, requires self-signed cert)
        //
        // Security: All connections use HTTPS to prevent MITM attacks.
        // NOTE: Hardcoded IP fallbacks removed (Jan 2026).
        // Use proper mDNS discovery or mesh routing instead.
        let candidates = [
            "https://api.awkronos.com",    // Production (primary)
            "https://kagami.local:8001",   // Local mDNS (self-signed cert)
        ]

        for candidate in candidates {
            if await testConnection(url: candidate) {
                return candidate
            }
        }
        return nil
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
        // Circuit breaker check — fail fast if open (unless recovery is due)
        // Allow request if: (1) circuit is not open, OR (2) circuit is open but recovery is due
        let circuitIsOpen = meshService.connectionState == .circuitOpen
        let shouldAllowRequest = !circuitIsOpen || meshService.shouldAttemptConnection

        guard shouldAllowRequest else {
            #if DEBUG
            print("[KagamiAPI] Circuit breaker OPEN — skipping connection check")
            #endif
            isConnected = false
            lastError = .requestFailed(message: "Service temporarily unavailable")
            return
        }

        let start = Date()

        do {
            // Signal connection attempt to MeshService
            try? meshService.onConnect()

            let health = try await fetchHealth()

            // Success — record with circuit breaker
            try? meshService.onConnected()

            isConnected = true
            safetyScore = health.safetyScore
            latencyMs = Int(Date().timeIntervalSince(start) * 1000)
        } catch {
            // Failure — record with circuit breaker
            try? meshService.onFailure(reason: error.localizedDescription)

            isConnected = false
        }
    }

    /// Reset the circuit breaker manually (e.g., when user requests retry).
    public func resetCircuitBreaker() {
        meshService.resetConnection()
        #if DEBUG
        print("[KagamiAPI] Circuit breaker reset by user request")
        #endif
    }

    private func startStatusPolling() {
        statusTimer?.invalidate()
        statusTimer = Timer.scheduledTimer(withTimeInterval: pollInterval, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in
                await self?.checkConnection()
            }
        }
    }

    // MARK: - Related Services Configuration

    private func configureRelatedServices() {
        // Configure WebSocket service
        KagamiWebSocketService.shared.configure(baseURL: baseURL, clientId: clientId)
        KagamiWebSocketService.shared.connect()

        // Configure Sensory service
        SensoryService.shared.configure(clientId: clientId)
        SensoryService.shared.start()
    }

    // MARK: - Client Registration

    private func registerWithKagami() async {
        let capabilities = [
            "healthkit",
            "location",
            "notifications",
            "quick_actions",
            "widgets",
        ]

        let body: [String: Any] = [
            "client_id": clientId,
            "client_type": "ios",
            "device_name": deviceName,
            "capabilities": capabilities,
            "app_version": Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0",
            "os_version": UIDevice.current.systemVersion,
        ]

        guard let url = URL(string: "\(baseURL)/api/home/clients/register") else { return }

        do {
            let bodyData = try JSONSerialization.data(withJSONObject: body)
            let (_, response) = try await networkService.post(url: url, body: bodyData)

            if let httpResponse = response as? HTTPURLResponse,
               httpResponse.statusCode >= 200 && httpResponse.statusCode < 300 {
                isRegistered = true
                lastError = nil
            } else {
                let statusCode = (response as? HTTPURLResponse)?.statusCode ?? -1
                lastError = .requestFailed(message: "Registration failed with status \(statusCode)")
                #if DEBUG
                print("[KagamiAPI] Registration failed with status: \(statusCode)")
                #endif
            }
        } catch let error as NetworkError {
            lastError = .networkError(error)
            #if DEBUG
            print("[KagamiAPI] Registration error: \(error.localizedDescription)")
            #endif
        } catch {
            lastError = .requestFailed(message: error.localizedDescription)
            #if DEBUG
            print("[KagamiAPI] Registration error: \(error.localizedDescription)")
            #endif
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

    /// Extended health check response for onboarding
    public struct HealthCheckResult {
        public let status: String
        public let version: String?
        public let safetyScore: Double?
        public let roomCount: Int?
        public let isHealthy: Bool
    }

    /// Perform a full health check (for onboarding)
    public func healthCheck() async throws -> HealthCheckResult {
        let health = try await fetchHealth()
        return HealthCheckResult(
            status: health.status,
            version: health.version,
            safetyScore: health.safetyScore,
            roomCount: health.rooms_count,
            isHealthy: health.status == "healthy" || health.status == "ok"
        )
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

    // MARK: - Version Check

    /// Minimum server version required by this client
    private static let minimumServerVersion = "1.0.0"

    /// Check if the server version is compatible with this client
    public func checkServerVersion() async -> VersionCheckResult {
        do {
            let health = try await fetchHealth()

            guard let serverVersion = health.version else {
                return VersionCheckResult(isCompatible: true, serverVersion: nil, minimumRequired: Self.minimumServerVersion, updateRequired: false)
            }

            let isCompatible = isVersionCompatible(serverVersion, minVersion: Self.minimumServerVersion)

            return VersionCheckResult(
                isCompatible: isCompatible,
                serverVersion: serverVersion,
                minimumRequired: Self.minimumServerVersion,
                updateRequired: !isCompatible
            )
        } catch {
            // If we can't fetch health, assume compatible
            return VersionCheckResult(isCompatible: true, serverVersion: nil, minimumRequired: Self.minimumServerVersion, updateRequired: false)
        }
    }

    private func isVersionCompatible(_ version: String, minVersion: String) -> Bool {
        let versionParts = version.split(separator: ".").compactMap { Int($0) }
        let minParts = minVersion.split(separator: ".").compactMap { Int($0) }

        // Pad arrays to same length
        let maxLength = max(versionParts.count, minParts.count)
        let paddedVersion = versionParts + Array(repeating: 0, count: maxLength - versionParts.count)
        let paddedMin = minParts + Array(repeating: 0, count: maxLength - minParts.count)

        for (v, m) in zip(paddedVersion, paddedMin) {
            if v > m { return true }
            if v < m { return false }
        }
        return true
    }

    public struct VersionCheckResult {
        public let isCompatible: Bool
        public let serverVersion: String?
        public let minimumRequired: String
        public let updateRequired: Bool
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

    // MARK: - Auth Errors

    public enum AuthError: LocalizedError {
        case invalidCredentials
        case serverError(String)
        case networkError
        case invalidResponse
        case registrationFailed(String)

        public var errorDescription: String? {
            switch self {
            case .invalidCredentials:
                return "Invalid username or password"
            case .serverError(let message):
                return message
            case .networkError:
                return "Unable to connect to server"
            case .invalidResponse:
                return "Invalid response from server"
            case .registrationFailed(let message):
                return message
            }
        }
    }

    // MARK: - Auth Token Storage (Keychain-backed)

    /// Auth token stored securely in Keychain
    private var authToken: String? {
        get {
            KeychainService.shared.getToken()
        }
        set {
            if let token = newValue {
                KeychainService.shared.saveToken(token)
            } else {
                KeychainService.shared.deleteToken()
            }
            // Update isAuthenticated state
            Task { @MainActor in
                self.isAuthenticated = newValue != nil
            }
        }
    }

    /// Check if user is authenticated (has valid token in Keychain)
    public var hasStoredToken: Bool {
        KeychainService.shared.hasToken
    }

    // MARK: - Authentication

    /// Login with username and password, returns JWT token
    public func login(username: String, password: String) async throws -> String {
        guard let url = URL(string: "\(baseURL)/api/user/token") else {
            let error = AuthError.networkError
            lastError = .auth(error)
            throw error
        }

        // OAuth2 password grant format
        let bodyParams = [
            "grant_type": "password",
            "username": username,
            "password": password
        ]
        let bodyString = bodyParams
            .map { "\($0.key)=\($0.value.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? $0.value)" }
            .joined(separator: "&")

        guard let bodyData = bodyString.data(using: .utf8) else {
            let error = AuthError.invalidResponse
            lastError = .auth(error)
            throw error
        }

        do {
            let (data, response) = try await networkService.post(
                url: url,
                body: bodyData,
                contentType: "application/x-www-form-urlencoded"
            )

            guard let httpResponse = response as? HTTPURLResponse else {
                let error = AuthError.invalidResponse
                lastError = .auth(error)
                throw error
            }

            switch httpResponse.statusCode {
            case 200..<300:
                let tokenResponse = try JSONDecoder().decode(TokenResponse.self, from: data)
                self.authToken = tokenResponse.accessToken
                lastError = nil
                return tokenResponse.accessToken

            case 401:
                let error = AuthError.invalidCredentials
                lastError = .auth(error)
                throw error

            case 422:
                // Validation error
                if let errorResponse = try? JSONDecoder().decode(ValidationErrorResponse.self, from: data) {
                    let error = AuthError.serverError(errorResponse.detail.first?.msg ?? "Validation error")
                    lastError = .auth(error)
                    throw error
                }
                let error = AuthError.invalidCredentials
                lastError = .auth(error)
                throw error

            default:
                if let errorResponse = try? JSONDecoder().decode(ErrorResponse.self, from: data) {
                    let error = AuthError.serverError(errorResponse.detail)
                    lastError = .auth(error)
                    throw error
                }
                let error = AuthError.serverError("Server error (\(httpResponse.statusCode))")
                lastError = .auth(error)
                throw error
            }
        } catch let error as AuthError {
            lastError = .auth(error)
            throw error
        } catch let error as NetworkError {
            lastError = .networkError(error)
            throw AuthError.networkError
        } catch {
            let authError = AuthError.networkError
            lastError = .auth(authError)
            throw authError
        }
    }

    /// Register a new user account
    public func register(username: String, email: String, password: String) async throws -> String {
        guard let url = URL(string: "\(baseURL)/api/user/register") else {
            let error = AuthError.networkError
            lastError = .auth(error)
            throw error
        }

        let body: [String: Any] = [
            "username": username,
            "email": email,
            "password": password
        ]

        guard let bodyData = try? JSONSerialization.data(withJSONObject: body) else {
            let error = AuthError.invalidResponse
            lastError = .auth(error)
            throw error
        }

        do {
            let (data, response) = try await networkService.post(url: url, body: bodyData)

            guard let httpResponse = response as? HTTPURLResponse else {
                let error = AuthError.invalidResponse
                lastError = .auth(error)
                throw error
            }

            switch httpResponse.statusCode {
            case 200..<300:
                // Registration successful, now login to get token
                return try await login(username: username, password: password)

            case 400:
                if let errorResponse = try? JSONDecoder().decode(ErrorResponse.self, from: data) {
                    let error = AuthError.registrationFailed(errorResponse.detail)
                    lastError = .auth(error)
                    throw error
                }
                let error = AuthError.registrationFailed("Registration failed")
                lastError = .auth(error)
                throw error

            case 409:
                let error = AuthError.registrationFailed("Username or email already exists")
                lastError = .auth(error)
                throw error

            case 422:
                if let errorResponse = try? JSONDecoder().decode(ValidationErrorResponse.self, from: data) {
                    let error = AuthError.registrationFailed(errorResponse.detail.first?.msg ?? "Validation error")
                    lastError = .auth(error)
                    throw error
                }
                let error = AuthError.registrationFailed("Invalid registration data")
                lastError = .auth(error)
                throw error

            default:
                let error = AuthError.registrationFailed("Server error (\(httpResponse.statusCode))")
                lastError = .auth(error)
                throw error
            }
        } catch let error as AuthError {
            lastError = .auth(error)
            throw error
        } catch let error as NetworkError {
            lastError = .networkError(error)
            throw AuthError.networkError
        } catch {
            let authError = AuthError.networkError
            lastError = .auth(authError)
            throw authError
        }
    }

    /// Logout and clear stored credentials
    public func logout() {
        // Clear all stored credentials from Keychain
        KeychainService.shared.clearAll()

        // Reset state
        isRegistered = false
        isConnected = false
        isAuthenticated = false
        lastError = nil

        // Stop related services
        KagamiWebSocketService.shared.disconnect()
        SensoryService.shared.stop()

        // Post logout notification
        NotificationCenter.default.post(name: .kagamiDidLogout, object: nil)
    }

    /// Set auth token from stored value (on app launch)
    /// Note: Token is now stored in Keychain, so this just validates the stored token
    public func setAuthToken(_ token: String) {
        // Store in Keychain (will update isAuthenticated via didSet)
        KeychainService.shared.saveToken(token)
        self.isAuthenticated = true
    }

    /// Restore authentication state from Keychain (call on app launch)
    public func restoreAuthenticationState() {
        if KeychainService.shared.hasToken {
            isAuthenticated = true
        }
    }

    // MARK: - Auth Response Types

    struct TokenResponse: Codable {
        let accessToken: String
        let tokenType: String

        enum CodingKeys: String, CodingKey {
            case accessToken = "access_token"
            case tokenType = "token_type"
        }
    }

    struct ErrorResponse: Codable {
        let detail: String
    }

    struct ValidationErrorResponse: Codable {
        let detail: [ValidationError]
    }

    struct ValidationError: Codable {
        let loc: [String]
        let msg: String
        let type: String
    }

    // MARK: - Rooms (kept for backward compatibility, delegates to DeviceControlService)

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

    /// Execute a POST request (used by SceneService, DeviceControlService, etc.)
    @discardableResult
    public func postRequest(endpoint: String, body: [String: Any]? = nil) async -> Bool {
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
            return false
        } catch {
            lastError = .requestFailed(message: error.localizedDescription)
            return false
        }
    }

    // MARK: - Backward Compatibility Methods

    // These methods delegate to the new specialized services but maintain
    // the original API for existing code that uses KagamiAPIService directly.

    /// Execute a scene (backward compatibility - delegates to SceneService)
    @discardableResult
    public func executeScene(_ scene: String) async -> Bool {
        return await SceneService.shared.execute(scene)
    }

    /// Set lights (backward compatibility - delegates to DeviceControlService)
    @discardableResult
    public func setLights(_ level: Int, rooms: [String]? = nil) async -> Bool {
        return await DeviceControlService.shared.setLights(level, rooms: rooms)
    }

    /// TV control (backward compatibility - delegates to DeviceControlService)
    @discardableResult
    public func tvControl(_ action: String) async -> Bool {
        guard let tvAction = DeviceControlService.TVAction(rawValue: action) else {
            return false
        }
        return await DeviceControlService.shared.tvControl(tvAction)
    }

    /// Toggle fireplace (backward compatibility - delegates to DeviceControlService)
    @discardableResult
    public func toggleFireplace(on: Bool) async -> Bool {
        return await DeviceControlService.shared.setFireplace(on: on)
    }

    /// Control shades (backward compatibility - delegates to DeviceControlService)
    @discardableResult
    public func controlShades(_ action: String, rooms: [String]? = nil) async -> Bool {
        guard let shadeAction = DeviceControlService.ShadeAction(rawValue: action) else {
            return false
        }
        return await DeviceControlService.shared.controlShades(shadeAction, rooms: rooms)
    }

    /// Announce message through speakers (backward compatibility)
    @discardableResult
    public func announce(_ message: String, rooms: [String]? = nil) async -> Bool {
        var body: [String: Any] = ["message": message]
        if let rooms = rooms {
            body["rooms"] = rooms
        }
        return await postRequest(endpoint: "/home/announce", body: body)
    }

    /// Set thermostat temperature (backward compatibility)
    @discardableResult
    public func setThermostat(_ temperature: Int, room: String? = nil) async -> Bool {
        var body: [String: Any] = ["temperature": temperature]
        if let room = room {
            body["room"] = room
        }
        return await postRequest(endpoint: "/home/climate/set", body: body)
    }

    /// Lock all doors (backward compatibility)
    @discardableResult
    public func lockAll() async -> Bool {
        return await postRequest(endpoint: "/home/locks/lock-all")
    }
}

// MARK: - Kagami API Error (Unified)

/// Unified error type for the API service that wraps all error types
public enum KagamiAPIError: Error, LocalizedError {
    case api(KagamiAPIService.APIError)
    case auth(KagamiAPIService.AuthError)
    case networkError(NetworkError)
    case requestFailed(message: String)

    public var errorDescription: String? {
        switch self {
        case .api(let error):
            return error.localizedDescription
        case .auth(let error):
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
        case .auth(let error):
            switch error {
            case .invalidCredentials:
                return "Check your username and password."
            case .networkError:
                return "Check your network connection and try again."
            default:
                return "Please try again."
            }
        case .networkError(let error):
            return error.isRetryable ? "Please try again." : "Check your network connection."
        case .requestFailed:
            return "Please try again."
        }
    }

    /// Whether the error is likely recoverable by retrying
    public var isRetryable: Bool {
        switch self {
        case .api(let error):
            switch error {
            case .requestFailed, .notConnected:
                return true
            default:
                return false
            }
        case .auth(let error):
            switch error {
            case .networkError:
                return true
            default:
                return false
            }
        case .networkError(let error):
            return error.isRetryable
        case .requestFailed:
            return true
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
