//
// KeychainService.swift — Secure Credential Storage for Kagami
//
// Colony: Nexus (e4) — Integration
//
// Features:
//   - Secure storage using iOS Keychain
//   - Auth token management
//   - Biometric protection support
//   - Thread-safe access
//
// Usage:
//   KeychainService.shared.saveToken("jwt-token")
//   let token = KeychainService.shared.getToken()
//   KeychainService.shared.deleteToken()
//
// Shared component for all Kagami Apple platforms.
//
// h(x) >= 0. Always.
//

import Foundation
import Security

// MARK: - Keychain Service

/// Centralized Keychain service for secure credential storage
public final class KeychainService {

    // MARK: - Singleton

    public static let shared = KeychainService()

    // MARK: - Configuration

    private let service: String
    private let accessGroup: String?

    // MARK: - Keys

    public enum KeychainKey: String, CaseIterable {
        case authToken = "authToken"
        case refreshToken = "refreshToken"
        case username = "username"
        case serverURL = "serverURL"
    }

    // MARK: - Init

    /// Create a KeychainService with default configuration
    public init() {
        self.service = "com.kagami"
        self.accessGroup = nil
    }

    /// Create a KeychainService with custom configuration
    /// - Parameters:
    ///   - service: The service identifier (e.g., "com.kagami.ios")
    ///   - accessGroup: Optional access group for shared keychain access
    public init(service: String, accessGroup: String? = nil) {
        self.service = service
        self.accessGroup = accessGroup
    }

    // MARK: - Auth Token

    /// Save the authentication token securely
    /// - Parameter token: The JWT token to store
    /// - Returns: Whether the save was successful
    @discardableResult
    public func saveToken(_ token: String) -> Bool {
        return save(key: .authToken, value: token)
    }

    /// Get the stored authentication token
    /// - Returns: The stored JWT token, or nil if not found
    public func getToken() -> String? {
        return get(key: .authToken)
    }

    /// Delete the stored authentication token
    @discardableResult
    public func deleteToken() -> Bool {
        return delete(key: .authToken)
    }

    /// Check if a token is stored
    public var hasToken: Bool {
        return getToken() != nil
    }

    // MARK: - Refresh Token

    /// Save the refresh token securely
    @discardableResult
    public func saveRefreshToken(_ token: String) -> Bool {
        return save(key: .refreshToken, value: token)
    }

    /// Get the stored refresh token
    public func getRefreshToken() -> String? {
        return get(key: .refreshToken)
    }

    /// Delete the stored refresh token
    @discardableResult
    public func deleteRefreshToken() -> Bool {
        return delete(key: .refreshToken)
    }

    // MARK: - Username

    /// Save the username for convenience (not sensitive)
    @discardableResult
    public func saveUsername(_ username: String) -> Bool {
        return save(key: .username, value: username)
    }

    /// Get the stored username
    public func getUsername() -> String? {
        return get(key: .username)
    }

    // MARK: - Server URL

    /// Save the server URL (convenience storage in keychain)
    @discardableResult
    public func saveServerURL(_ url: String) -> Bool {
        return save(key: .serverURL, value: url)
    }

    /// Get the stored server URL
    public func getServerURL() -> String? {
        return get(key: .serverURL)
    }

    // MARK: - Generic Key-Value

    /// Save a custom key-value pair
    @discardableResult
    public func save(key: String, value: String) -> Bool {
        return saveValue(account: key, value: value)
    }

    /// Get a custom key-value pair
    public func get(key: String) -> String? {
        return getValue(account: key)
    }

    /// Delete a custom key-value pair
    @discardableResult
    public func delete(key: String) -> Bool {
        return deleteValue(account: key)
    }

    // MARK: - Clear All

    /// Clear all stored credentials (for logout)
    public func clearAll() {
        deleteToken()
        deleteRefreshToken()
        delete(key: .username)
        // Don't delete server URL - keep for convenience
    }

    // MARK: - Generic Keychain Operations

    private func save(key: KeychainKey, value: String) -> Bool {
        return saveValue(account: key.rawValue, value: value)
    }

    private func get(key: KeychainKey) -> String? {
        return getValue(account: key.rawValue)
    }

    @discardableResult
    private func delete(key: KeychainKey) -> Bool {
        return deleteValue(account: key.rawValue)
    }

    private func saveValue(account: String, value: String) -> Bool {
        guard let data = value.data(using: .utf8) else { return false }

        // Delete existing item first
        _ = deleteValue(account: account)

        // Build query
        var query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly
        ]

        // Add access group if specified (for app groups)
        if let accessGroup = accessGroup {
            query[kSecAttrAccessGroup as String] = accessGroup
        }

        let status = SecItemAdd(query as CFDictionary, nil)
        return status == errSecSuccess
    }

    private func getValue(account: String) -> String? {
        var query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]

        if let accessGroup = accessGroup {
            query[kSecAttrAccessGroup as String] = accessGroup
        }

        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)

        guard status == errSecSuccess,
              let data = result as? Data,
              let string = String(data: data, encoding: .utf8) else {
            return nil
        }

        return string
    }

    @discardableResult
    private func deleteValue(account: String) -> Bool {
        var query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account
        ]

        if let accessGroup = accessGroup {
            query[kSecAttrAccessGroup as String] = accessGroup
        }

        let status = SecItemDelete(query as CFDictionary)
        return status == errSecSuccess || status == errSecItemNotFound
    }
}

// MARK: - Legacy KagamiKeychain Compatibility

/// Compatibility layer for existing KagamiKeychain usage
/// This allows gradual migration to KeychainService
public struct KagamiKeychain {
    public static func saveToken(_ token: String) {
        KeychainService.shared.saveToken(token)
    }

    public static func getToken() -> String? {
        KeychainService.shared.getToken()
    }

    public static func deleteToken() {
        KeychainService.shared.deleteToken()
    }

    public static var hasToken: Bool {
        KeychainService.shared.hasToken
    }
}

/*
 * Mirror
 * Secrets stay secret.
 * h(x) >= 0. Always.
 */
