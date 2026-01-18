//
// KeychainServiceTests.swift — Keychain Service Unit Tests
//
// Note: Some tests may need to run on device/simulator for actual keychain access.
//
// h(x) >= 0. Always.
//

import XCTest
@testable import KagamiCore

final class KeychainServiceTests: XCTestCase {

    var keychainService: KeychainService!

    override func setUp() {
        super.setUp()
        // Use a unique service name to avoid conflicts
        keychainService = KeychainService(service: "com.kagami.tests")
        // Clean up any existing test data
        keychainService.clearAll()
    }

    override func tearDown() {
        keychainService.clearAll()
        keychainService = nil
        super.tearDown()
    }

    // MARK: - Token Operations

    func testSaveAndGetToken() {
        let token = "test-jwt-token-123"

        let saved = keychainService.saveToken(token)
        XCTAssertTrue(saved)

        let retrieved = keychainService.getToken()
        XCTAssertEqual(retrieved, token)
    }

    func testDeleteToken() {
        keychainService.saveToken("token-to-delete")
        XCTAssertTrue(keychainService.hasToken)

        let deleted = keychainService.deleteToken()
        XCTAssertTrue(deleted)
        XCTAssertFalse(keychainService.hasToken)
        XCTAssertNil(keychainService.getToken())
    }

    func testHasToken() {
        XCTAssertFalse(keychainService.hasToken)

        keychainService.saveToken("some-token")
        XCTAssertTrue(keychainService.hasToken)

        keychainService.deleteToken()
        XCTAssertFalse(keychainService.hasToken)
    }

    // MARK: - Refresh Token

    func testRefreshToken() {
        let refreshToken = "refresh-token-456"

        keychainService.saveRefreshToken(refreshToken)
        XCTAssertEqual(keychainService.getRefreshToken(), refreshToken)

        keychainService.deleteRefreshToken()
        XCTAssertNil(keychainService.getRefreshToken())
    }

    // MARK: - Username

    func testUsername() {
        let username = "testuser@kagami.com"

        keychainService.saveUsername(username)
        XCTAssertEqual(keychainService.getUsername(), username)
    }

    // MARK: - Server URL

    func testServerURL() {
        let url = "https://api.kagami.local"

        keychainService.saveServerURL(url)
        XCTAssertEqual(keychainService.getServerURL(), url)
    }

    // MARK: - Custom Keys

    func testCustomKey() {
        let key = "customKey"
        let value = "customValue"

        let saved = keychainService.save(key: key, value: value)
        XCTAssertTrue(saved)

        let retrieved = keychainService.get(key: key)
        XCTAssertEqual(retrieved, value)

        let deleted = keychainService.delete(key: key)
        XCTAssertTrue(deleted)
        XCTAssertNil(keychainService.get(key: key))
    }

    // MARK: - Clear All

    func testClearAll() {
        keychainService.saveToken("token")
        keychainService.saveRefreshToken("refresh")
        keychainService.saveUsername("user")
        keychainService.saveServerURL("https://api.kagami.local")

        keychainService.clearAll()

        XCTAssertNil(keychainService.getToken())
        XCTAssertNil(keychainService.getRefreshToken())
        XCTAssertNil(keychainService.getUsername())
        // Server URL should be preserved after clearAll
        XCTAssertNotNil(keychainService.getServerURL())
    }

    // MARK: - Update Existing

    func testUpdateExistingToken() {
        keychainService.saveToken("original-token")
        keychainService.saveToken("updated-token")

        XCTAssertEqual(keychainService.getToken(), "updated-token")
    }

    // MARK: - Legacy Compatibility

    func testLegacyKagamiKeychain() {
        // This tests the static compatibility layer
        // Note: Uses shared instance, may need isolation
        let token = "legacy-test-token"

        KagamiKeychain.saveToken(token)
        XCTAssertEqual(KagamiKeychain.getToken(), token)
        XCTAssertTrue(KagamiKeychain.hasToken)

        KagamiKeychain.deleteToken()
        XCTAssertFalse(KagamiKeychain.hasToken)
    }
}
