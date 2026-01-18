//
// WatchConnectivityServiceTests.swift
// Kagami Watch - Unit Tests for Watch Connectivity Service
//
// Tests for message send/receive, auth flow, and iPhone communication.
//
// h(x) >= 0. Always.
//

import XCTest
@testable import KagamiWatch

// MARK: - Watch Connectivity Service Tests

@MainActor
final class WatchConnectivityServiceTests: XCTestCase {

    var connectivityService: WatchConnectivityService!

    override func setUp() async throws {
        // Use shared instance for testing
        connectivityService = WatchConnectivityService.shared
        // Reset state for clean tests
        connectivityService.testResetState()
    }

    override func tearDown() async throws {
        connectivityService.testResetState()
        connectivityService = nil
    }

    // MARK: - Initial State Tests

    func testInitialAuthState() {
        let state = connectivityService.authState
        XCTAssertEqual(state.status, .unauthenticated)
        XCTAssertNil(state.accessToken)
        XCTAssertNil(state.refreshToken)
        XCTAssertNil(state.userId)
    }

    func testIsAuthenticatedWhenUnauthenticated() {
        XCTAssertFalse(connectivityService.authState.isAuthenticated)
    }

    // MARK: - Auth State Status Tests

    func testAuthenticatedStatus() {
        connectivityService.testSetAuthState(
            status: .authenticated,
            accessToken: "valid-token",
            expiresAt: Date().addingTimeInterval(3600) // 1 hour from now
        )

        XCTAssertTrue(connectivityService.authState.isAuthenticated)
        XCTAssertEqual(connectivityService.authState.status, .authenticated)
    }

    func testAuthenticatedWithExpiredToken() {
        connectivityService.testSetAuthState(
            status: .authenticated,
            accessToken: "expired-token",
            expiresAt: Date().addingTimeInterval(-60) // 1 minute ago
        )

        // Should not be considered authenticated if token is expired
        XCTAssertFalse(connectivityService.authState.isAuthenticated)
    }

    func testNeedsRefreshWithinFiveMinutes() {
        connectivityService.testSetAuthState(
            status: .authenticated,
            accessToken: "soon-expiring-token",
            expiresAt: Date().addingTimeInterval(180) // 3 minutes from now
        )

        // Should need refresh when less than 5 minutes until expiration
        XCTAssertTrue(connectivityService.authState.needsRefresh)
    }

    func testDoesNotNeedRefreshWhenFarFromExpiration() {
        connectivityService.testSetAuthState(
            status: .authenticated,
            accessToken: "valid-token",
            expiresAt: Date().addingTimeInterval(3600) // 1 hour from now
        )

        // Should not need refresh when expiration is far away
        XCTAssertFalse(connectivityService.authState.needsRefresh)
    }

    // MARK: - Message Handling Tests

    func testHandleAuthUpdateMessage() {
        let authData: [String: Any] = [
            "status": "authenticated",
            "access_token": "new-token-123",
            "refresh_token": "refresh-456",
            "expires_in": 3600,
            "user_id": "user-789",
            "username": "testuser",
            "display_name": "Test User",
            "server_url": "http://kagami.local:8001"
        ]

        let message: [String: Any] = [
            "type": "auth_update",
            "auth": authData
        ]

        connectivityService.testHandleMessage(message)

        XCTAssertEqual(connectivityService.authState.status, .authenticated)
        XCTAssertEqual(connectivityService.authState.accessToken, "new-token-123")
        XCTAssertEqual(connectivityService.authState.refreshToken, "refresh-456")
        XCTAssertEqual(connectivityService.authState.userId, "user-789")
        XCTAssertEqual(connectivityService.authState.username, "testuser")
        XCTAssertEqual(connectivityService.authState.displayName, "Test User")
        XCTAssertEqual(connectivityService.authState.serverURL, "http://kagami.local:8001")
    }

    func testHandleServerUpdateMessage() {
        let message: [String: Any] = [
            "type": "server_update",
            "server_url": "http://new-server.local:8001"
        ]

        connectivityService.testHandleMessage(message)

        XCTAssertEqual(connectivityService.authState.serverURL, "http://new-server.local:8001")
    }

    func testHandleUnknownMessage() {
        let message: [String: Any] = [
            "type": "unknown_type",
            "data": "something"
        ]

        // Should not crash, should just ignore
        connectivityService.testHandleMessage(message)

        // State should remain unchanged
        XCTAssertEqual(connectivityService.authState.status, .unauthenticated)
    }

    // MARK: - Auth Reply Handling Tests

    func testHandleSuccessfulAuthReply() {
        let reply: [String: Any] = [
            "success": true,
            "auth": [
                "status": "authenticated",
                "access_token": "reply-token",
                "expires_in": 7200
            ]
        ]

        connectivityService.testHandleAuthReply(reply)

        XCTAssertEqual(connectivityService.authState.status, .authenticated)
        XCTAssertEqual(connectivityService.authState.accessToken, "reply-token")
    }

    func testHandleFailedAuthReply() {
        let reply: [String: Any] = [
            "success": false,
            "error": "Invalid credentials"
        ]

        connectivityService.testHandleAuthReply(reply)

        XCTAssertEqual(connectivityService.authState.status, .error)
        XCTAssertEqual(connectivityService.authState.errorMessage, "Invalid credentials")
    }

    func testHandleAuthReplyWithNoSuccess() {
        let reply: [String: Any] = [
            "error": "Server error"
        ]

        connectivityService.testHandleAuthReply(reply)

        XCTAssertEqual(connectivityService.authState.status, .error)
    }

    // MARK: - Expiration Parsing Tests

    func testParseExpiresInSeconds() {
        let authData: [String: Any] = [
            "status": "authenticated",
            "access_token": "token",
            "expires_in": 3600
        ]

        let message: [String: Any] = [
            "type": "auth_update",
            "auth": authData
        ]

        let beforeUpdate = Date()
        connectivityService.testHandleMessage(message)
        let afterUpdate = Date()

        // Expiration should be approximately 1 hour from now
        guard let expiresAt = connectivityService.authState.expiresAt else {
            XCTFail("expiresAt should be set")
            return
        }

        let expectedMin = beforeUpdate.addingTimeInterval(3600)
        let expectedMax = afterUpdate.addingTimeInterval(3600)

        XCTAssertTrue(expiresAt >= expectedMin && expiresAt <= expectedMax)
    }

    func testParseExpiresAtISO8601() {
        let futureDate = Date().addingTimeInterval(7200)
        let formatter = ISO8601DateFormatter()
        let isoString = formatter.string(from: futureDate)

        let authData: [String: Any] = [
            "status": "authenticated",
            "access_token": "token",
            "expires_at": isoString
        ]

        let message: [String: Any] = [
            "type": "auth_update",
            "auth": authData
        ]

        connectivityService.testHandleMessage(message)

        guard let expiresAt = connectivityService.authState.expiresAt else {
            XCTFail("expiresAt should be set")
            return
        }

        // Should be within a few seconds of the expected time
        let difference = abs(expiresAt.timeIntervalSince(futureDate))
        XCTAssertTrue(difference < 2.0, "Parsed expiration should match ISO8601 string")
    }

    // MARK: - Clear Auth Tests

    func testClearAuthState() {
        // First set some auth state
        connectivityService.testSetAuthState(
            status: .authenticated,
            accessToken: "token-to-clear",
            expiresAt: Date().addingTimeInterval(3600)
        )

        XCTAssertTrue(connectivityService.authState.isAuthenticated)

        // Clear it
        connectivityService.testClearAuthState()

        XCTAssertEqual(connectivityService.authState.status, .unauthenticated)
        XCTAssertNil(connectivityService.authState.accessToken)
        XCTAssertNil(connectivityService.authState.refreshToken)
        XCTAssertNil(connectivityService.authState.expiresAt)
    }

    // MARK: - Reachability Tests

    func testIsReachableDefault() {
        // In test environment, should start as false
        XCTAssertFalse(connectivityService.isReachable)
    }

    func testSetReachability() {
        connectivityService.testSetReachable(true)
        XCTAssertTrue(connectivityService.isReachable)

        connectivityService.testSetReachable(false)
        XCTAssertFalse(connectivityService.isReachable)
    }

    // MARK: - Last Sync Date Tests

    func testLastSyncDateUpdatesOnAuthMessage() {
        XCTAssertNil(connectivityService.lastSyncDate)

        let message: [String: Any] = [
            "type": "auth_update",
            "auth": [
                "status": "authenticated",
                "access_token": "token"
            ]
        ]

        connectivityService.testHandleMessage(message)

        XCTAssertNotNil(connectivityService.lastSyncDate)
    }
}

// MARK: - Test Helpers Extension

extension WatchConnectivityService {
    /// Reset state for testing
    func testResetState() {
        authState = WatchAuthState()
        isReachable = false
        lastSyncDate = nil
    }

    /// Set auth state for testing
    func testSetAuthState(
        status: WatchAuthState.Status,
        accessToken: String? = nil,
        refreshToken: String? = nil,
        expiresAt: Date? = nil,
        userId: String? = nil
    ) {
        var state = WatchAuthState()
        state.status = status
        state.accessToken = accessToken
        state.refreshToken = refreshToken
        state.expiresAt = expiresAt
        state.userId = userId
        authState = state
    }

    /// Handle message for testing (exposes private method)
    func testHandleMessage(_ message: [String: Any]) {
        handleReceivedMessage(message)
    }

    /// Handle auth reply for testing (exposes private method)
    func testHandleAuthReply(_ reply: [String: Any]) {
        handleAuthReply(reply)
    }

    /// Clear auth state for testing
    func testClearAuthState() {
        authState = WatchAuthState()
    }

    /// Set reachability for testing
    func testSetReachable(_ reachable: Bool) {
        isReachable = reachable
    }
}
