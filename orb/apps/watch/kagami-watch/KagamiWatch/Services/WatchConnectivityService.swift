//
// WatchConnectivityService.swift — iPhone Companion Authentication
//
// Colony: Nexus (e4) — Integration
//
// WatchConnectivity handler for receiving authentication tokens from iOS companion app.
// The watch does NOT perform login directly - it receives tokens from the paired iPhone.
//
// Flow:
//   1. iPhone performs login (LoginView.swift in kagami-ios)
//   2. iPhone sends tokens via WCSession.sendMessage or updateApplicationContext
//   3. Watch receives tokens and stores in Keychain
//   4. Watch uses tokens for API authentication
//
// Security:
//   - Tokens stored in Keychain (encrypted at rest)
//   - No credentials stored on watch
//   - Watch requests refresh via iPhone when token expires
//
// Created: December 31, 2025
//

import Foundation
import WatchConnectivity
import Combine

/// Authentication state matching Python models (kagami_auth_client/models.py)
struct WatchAuthState: Codable, Equatable {
    enum Status: String, Codable {
        case unauthenticated
        case authenticating
        case authenticated
        case tokenExpired = "token_expired"
        case error
    }

    var status: Status = .unauthenticated
    var accessToken: String?
    var refreshToken: String?
    var expiresAt: Date?
    var userId: String?
    var username: String?
    var displayName: String?
    var serverURL: String?
    var errorMessage: String?

    var isAuthenticated: Bool {
        guard status == .authenticated,
              let token = accessToken,
              !token.isEmpty else {
            return false
        }

        // Check expiration
        if let expires = expiresAt, Date() >= expires {
            return false
        }

        return true
    }

    var needsRefresh: Bool {
        guard let expires = expiresAt else { return false }
        // Refresh 5 minutes before expiration
        return Date() >= expires.addingTimeInterval(-300)
    }
}

/// Message types for iPhone <-> Watch communication
enum WatchMessage: String {
    case authUpdate = "auth_update"         // iPhone -> Watch: Token update
    case authRequest = "auth_request"       // Watch -> iPhone: Request current auth
    case refreshRequest = "refresh_request" // Watch -> iPhone: Request token refresh
    case logoutRequest = "logout_request"   // Watch -> iPhone: Request logout
    case serverUpdate = "server_update"     // iPhone -> Watch: Server URL changed
}

/// WatchConnectivity service for iPhone companion app integration
@MainActor
class WatchConnectivityService: NSObject, ObservableObject {

    // MARK: - Published State

    @Published var authState = WatchAuthState()
    @Published var isReachable = false
    @Published var isPaired = false
    @Published var isWatchAppInstalled = false
    @Published var lastSyncDate: Date?

    // Combine publisher for auth changes
    var authStatePublisher: AnyPublisher<WatchAuthState, Never> {
        $authState.eraseToAnyPublisher()
    }

    // MARK: - Private State

    private var session: WCSession?
    private let keychainService = "com.kagami.watch.auth"

    // MARK: - Singleton

    static let shared = WatchConnectivityService()

    // MARK: - Initialization

    override init() {
        super.init()
        setupWatchConnectivity()
        loadStoredAuthState()
    }

    // MARK: - WCSession Setup

    private func setupWatchConnectivity() {
        guard WCSession.isSupported() else {
            KagamiLogger.connectivity.warning("WCSession not supported on this device")
            return
        }

        session = WCSession.default
        session?.delegate = self
        session?.activate()

        KagamiLogger.connectivity.info("WCSession activating...")
    }

    // MARK: - Auth State Persistence (Keychain)

    private func loadStoredAuthState() {
        guard let data = loadFromKeychain(key: "authState"),
              let state = try? JSONDecoder().decode(WatchAuthState.self, from: data) else {
            return
        }

        // Check if stored state is still valid
        if state.isAuthenticated {
            authState = state
            KagamiLogger.auth.info("Loaded valid auth state from Keychain: \(state.username ?? "unknown")")
        } else if state.refreshToken != nil {
            // Have refresh token, mark as needing refresh
            var needsRefresh = state
            needsRefresh.status = .tokenExpired
            authState = needsRefresh
            KagamiLogger.auth.info("Auth state loaded but needs refresh")
        }
    }

    private func saveAuthState() {
        guard let data = try? JSONEncoder().encode(authState) else { return }
        saveToKeychain(key: "authState", data: data)
    }

    private func clearAuthState() {
        authState = WatchAuthState()
        deleteFromKeychain(key: "authState")
    }

    // MARK: - Keychain Operations

    private func saveToKeychain(key: String, data: Data) {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: keychainService,
            kSecAttrAccount as String: key,
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlock
        ]

        // Delete existing item first
        SecItemDelete(query as CFDictionary)

        // Add new item
        let status = SecItemAdd(query as CFDictionary, nil)
        if status != errSecSuccess {
            KagamiLogger.auth.error("Keychain save error: \(status)")
        }
    }

    private func loadFromKeychain(key: String) -> Data? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: keychainService,
            kSecAttrAccount as String: key,
            kSecReturnData as String: true
        ]

        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)

        if status == errSecSuccess {
            return result as? Data
        }
        return nil
    }

    private func deleteFromKeychain(key: String) {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: keychainService,
            kSecAttrAccount as String: key
        ]
        SecItemDelete(query as CFDictionary)
    }

    // MARK: - Communication with iPhone

    /// Request current authentication state from iPhone
    /// Per audit: Uses updateApplicationContext for auth (lower latency than sendMessage)
    func requestAuthFromiPhone() {
        guard let session = session else {
            KagamiLogger.connectivity.warning("WCSession not available")
            authState.status = .error
            authState.errorMessage = "WCSession not available"
            return
        }

        // First check if we have cached auth in application context
        let context = session.receivedApplicationContext
        if let authData = context["auth"] as? [String: Any] {
            KagamiLogger.auth.info("Found cached auth in application context")
            updateAuthFromMessage(authData)
            return
        }

        // If iPhone is reachable, request fresh auth via sendMessage
        guard session.isReachable else {
            KagamiLogger.connectivity.warning("iPhone not reachable")
            authState.status = .error
            authState.errorMessage = "iPhone not reachable"
            return
        }

        authState.status = .authenticating

        let message: [String: Any] = [
            "type": WatchMessage.authRequest.rawValue
        ]

        session.sendMessage(message, replyHandler: { [weak self] reply in
            Task { @MainActor in
                self?.handleAuthReply(reply)
            }
        }, errorHandler: { [weak self] error in
            Task { @MainActor in
                self?.authState.status = .error
                self?.authState.errorMessage = error.localizedDescription
                KagamiLogger.auth.error("Auth request error: \(error.localizedDescription)")
            }
        })
    }

    /// Send auth update to iPhone via updateApplicationContext
    /// Per audit: Use for non-critical background sync (lower latency, more reliable)
    func sendAuthContextUpdate() {
        guard let session = session, session.activationState == .activated else { return }

        let context: [String: Any] = [
            "type": WatchMessage.authRequest.rawValue,
            "timestamp": ISO8601DateFormatter().string(from: Date()),
            "client_id": "watch-\(UUID().uuidString.prefix(8))"
        ]

        do {
            try session.updateApplicationContext(context)
            KagamiLogger.auth.logDebug("Auth context update sent")
        } catch {
            KagamiLogger.auth.error("Failed to update application context: \(error.localizedDescription)")
        }
    }

    /// Request token refresh from iPhone
    func requestTokenRefresh() {
        guard let session = session, session.isReachable else {
            KagamiLogger.connectivity.warning("iPhone not reachable for refresh")
            return
        }

        let message: [String: Any] = [
            "type": WatchMessage.refreshRequest.rawValue
        ]

        session.sendMessage(message, replyHandler: { [weak self] reply in
            Task { @MainActor in
                self?.handleAuthReply(reply)
            }
        }, errorHandler: { error in
            KagamiLogger.auth.error("Refresh request error: \(error.localizedDescription)")
        })
    }

    /// Request logout (tells iPhone to log out)
    func requestLogout() {
        guard let session = session, session.isReachable else {
            // Clear local state anyway
            clearAuthState()
            return
        }

        let message: [String: Any] = [
            "type": WatchMessage.logoutRequest.rawValue
        ]

        session.sendMessage(message, replyHandler: { [weak self] _ in
            Task { @MainActor in
                self?.clearAuthState()
            }
        }, errorHandler: { [weak self] _ in
            Task { @MainActor in
                // Clear local state even if message fails
                self?.clearAuthState()
            }
        })
    }

    // MARK: - Message Handling

    private func handleAuthReply(_ reply: [String: Any]) {
        // Check for success
        guard let success = reply["success"] as? Bool, success else {
            let errorMsg = reply["error"] as? String ?? "Authentication failed"
            authState.status = .error
            authState.errorMessage = errorMsg
            return
        }

        // Extract auth data
        if let tokenData = reply["auth"] as? [String: Any] {
            updateAuthFromMessage(tokenData)
        }
    }

    private func updateAuthFromMessage(_ data: [String: Any]) {
        // Parse status
        if let statusStr = data["status"] as? String,
           let status = WatchAuthState.Status(rawValue: statusStr) {
            authState.status = status
        }

        // Parse tokens
        if let accessToken = data["access_token"] as? String {
            authState.accessToken = accessToken
        }

        if let refreshToken = data["refresh_token"] as? String {
            authState.refreshToken = refreshToken
        }

        // Parse expiration
        if let expiresIn = data["expires_in"] as? Int {
            authState.expiresAt = Date().addingTimeInterval(TimeInterval(expiresIn))
        } else if let expiresAtStr = data["expires_at"] as? String {
            let formatter = ISO8601DateFormatter()
            authState.expiresAt = formatter.date(from: expiresAtStr)
        }

        // Parse user info
        if let userId = data["user_id"] as? String {
            authState.userId = userId
        }
        if let username = data["username"] as? String {
            authState.username = username
        }
        if let displayName = data["display_name"] as? String {
            authState.displayName = displayName
        }

        // Parse server URL
        if let serverURL = data["server_url"] as? String {
            authState.serverURL = serverURL
        }

        // Clear any errors
        if authState.status == .authenticated {
            authState.errorMessage = nil
        }

        // Persist to Keychain
        saveAuthState()
        lastSyncDate = Date()

        KagamiLogger.auth.info("Auth state updated: \(authState.status.rawValue), user: \(authState.username ?? "none")")
    }
}

// MARK: - WCSessionDelegate

extension WatchConnectivityService: WCSessionDelegate {

    nonisolated func session(_ session: WCSession, activationDidCompleteWith activationState: WCSessionActivationState, error: Error?) {
        Task { @MainActor in
            switch activationState {
            case .activated:
                KagamiLogger.connectivity.info("WCSession activated")
                self.isReachable = session.isReachable

                // Request auth state from iPhone on activation
                if session.isReachable {
                    self.requestAuthFromiPhone()
                }

            case .inactive:
                KagamiLogger.connectivity.info("WCSession inactive")
                self.isReachable = false

            case .notActivated:
                KagamiLogger.connectivity.warning("WCSession not activated")
                self.isReachable = false

            @unknown default:
                break
            }

            if let error = error {
                KagamiLogger.connectivity.error("WCSession activation error: \(error.localizedDescription)")
            }
        }
    }

    nonisolated func sessionReachabilityDidChange(_ session: WCSession) {
        Task { @MainActor in
            self.isReachable = session.isReachable
            KagamiLogger.connectivity.info("iPhone reachability changed: \(session.isReachable)")

            // Request auth when iPhone becomes reachable
            if session.isReachable && !self.authState.isAuthenticated {
                self.requestAuthFromiPhone()
            }
        }
    }

    // Receive messages from iPhone
    nonisolated func session(_ session: WCSession, didReceiveMessage message: [String : Any]) {
        Task { @MainActor in
            self.processReceivedMessage(message)
        }
    }

    nonisolated func session(_ session: WCSession, didReceiveMessage message: [String : Any], replyHandler: @escaping ([String : Any]) -> Void) {
        Task { @MainActor in
            self.processReceivedMessage(message)
            replyHandler(["received": true])
        }
    }

    // Receive application context (background updates)
    nonisolated func session(_ session: WCSession, didReceiveApplicationContext applicationContext: [String : Any]) {
        Task { @MainActor in
            self.processReceivedMessage(applicationContext)
        }
    }

    @MainActor
    private func processReceivedMessage(_ message: [String: Any]) {
        // Per audit: Handle messages without type (direct auth updates)
        guard let typeStr = message["type"] as? String else {
            // If no type, try to handle as direct auth update
            if let authData = message["auth"] as? [String: Any] {
                updateAuthFromMessage(authData)
            }
            return
        }

        switch typeStr {
        case WatchMessage.authUpdate.rawValue:
            // iPhone sent auth update
            if let authData = message["auth"] as? [String: Any] {
                updateAuthFromMessage(authData)
            }

        case WatchMessage.serverUpdate.rawValue:
            // Server URL changed
            if let serverURL = message["server_url"] as? String {
                authState.serverURL = serverURL
                saveAuthState()
            }

        // Per KAGAMI_REDESIGN_PLAN.md: Complication refresh integration via WatchConnectivity
        case "safety_update":
            // Safety score changed - update complications
            if let score = message["safety_score"] as? Double {
                ComplicationUpdateManager.shared.safetyScoreChanged(score)
            }

        case "home_state_update":
            // Home state changed - update complications
            let movieMode = message["movie_mode"] as? Bool
            let occupiedRooms = message["occupied_rooms"] as? Int
            ComplicationUpdateManager.shared.homeStateChanged(movieMode: movieMode, occupiedRooms: occupiedRooms)

        case "sleep_update":
            // Sleep score from Eight Sleep - update complications
            if let sleepScore = message["sleep_score"] as? Int {
                let defaults = UserDefaults(suiteName: "group.com.kagami.watch")
                defaults?.set(sleepScore, forKey: "sleepScore")
                defaults?.set(message["sleep_quality"] as? String ?? "", forKey: "sleepQuality")
                ComplicationUpdateManager.shared.reloadAllComplications()
            }

        case "critical_alert":
            // Critical safety alert - immediate complication update
            if let severity = message["severity"] as? String {
                ComplicationUpdateManager.shared.criticalAlertReceived(severity: severity)
                // Play haptic for critical alert
                HapticNavigationLibrary.shared.play(.safetyAlert)
            }

        case "room_update":
            // Room state changed - update room complications
            if let roomData = message["room"] as? [String: Any] {
                let defaults = UserDefaults(suiteName: "group.com.kagami.watch")
                defaults?.set(roomData["name"] as? String ?? "", forKey: "lastActiveRoom")
                defaults?.set(roomData["light_level"] as? Int ?? 0, forKey: "lastRoomLightLevel")
                defaults?.set(roomData["occupied"] as? Bool ?? false, forKey: "lastRoomOccupied")
                ComplicationUpdateManager.shared.reloadKagamiWidgets()
            }

        case "complication_refresh":
            // Explicit complication refresh request from iPhone
            ComplicationUpdateManager.shared.forceUpdate()

        default:
            KagamiLogger.connectivity.logDebug("Unknown message type: \(typeStr)")
        }
    }
}

// MARK: - WatchConnectivity Complication Refresh Extension
// Per KAGAMI_REDESIGN_PLAN.md: Ensure proper complication data refresh

extension WatchConnectivityService {

    /// Request fresh data from iPhone for complications
    func requestComplicationData() {
        guard let session = session, session.isReachable else {
            KagamiLogger.connectivity.warning("iPhone not reachable for complication data")
            return
        }

        let message: [String: Any] = [
            "type": "complication_data_request",
            "requested_data": ["safety_score", "sleep_score", "home_state", "room_status"]
        ]

        session.sendMessage(message, replyHandler: { [weak self] reply in
            Task { @MainActor in
                self?.handleComplicationDataReply(reply)
            }
        }, errorHandler: { error in
            KagamiLogger.connectivity.error("Complication data request failed: \(error.localizedDescription)")
        })
    }

    /// Handle complication data reply from iPhone
    @MainActor
    private func handleComplicationDataReply(_ reply: [String: Any]) {
        let defaults = UserDefaults(suiteName: "group.com.kagami.watch")

        // Safety score
        if let safetyScore = reply["safety_score"] as? Double {
            defaults?.set(safetyScore, forKey: "safetyScore")
        }

        // Sleep score
        if let sleepScore = reply["sleep_score"] as? Int {
            defaults?.set(sleepScore, forKey: "sleepScore")
        }
        if let sleepQuality = reply["sleep_quality"] as? String {
            defaults?.set(sleepQuality, forKey: "sleepQuality")
        }

        // Home state
        if let movieMode = reply["movie_mode"] as? Bool {
            defaults?.set(movieMode, forKey: "movieMode")
        }
        if let occupiedRooms = reply["occupied_rooms"] as? Int {
            defaults?.set(occupiedRooms, forKey: "occupiedRooms")
        }

        // Trigger complication refresh
        ComplicationUpdateManager.shared.reloadAllComplications()

        KagamiLogger.connectivity.info("Complication data updated from iPhone")
    }
}

// MARK: - Test Helpers
// Per audit: Minimal test helpers that delegate to internal methods

#if DEBUG
extension WatchConnectivityService {
    /// Handle received message for testing (delegates to processReceivedMessage)
    func handleReceivedMessage(_ message: [String: Any]) {
        processReceivedMessage(message)
    }

    /// Handle auth reply for testing (delegates to internal handler)
    func testHandleAuthReply(_ reply: [String: Any]) {
        guard let success = reply["success"] as? Bool, success else {
            let errorMsg = reply["error"] as? String ?? "Authentication failed"
            authState.status = .error
            authState.errorMessage = errorMsg
            return
        }

        if let tokenData = reply["auth"] as? [String: Any] {
            updateAuthFromMessage(tokenData)
        }
    }
}
#endif

/*
 * Kagami Watch Authentication
 *
 * The watch acts as a trusted extension of the iPhone.
 * No credentials are stored - only tokens received from the companion app.
 *
 * h(x) >= 0. Always.
 */
