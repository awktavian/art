/// Identity Storage Protocol — Platform-agnostic credential storage
///
/// Defines the interface for secure credential storage. iOS implements
/// using Keychain Services, Android uses EncryptedSharedPreferences.
///
/// This protocol mirrors the Rust SDK's IdentityStorage trait for
/// cross-platform consistency.
///
/// h(x) >= 0. Always.

import Foundation

// MARK: - Storage Keys

/// Consistent storage key names across platforms.
public enum IdentityStorageKeys {
    /// Primary Ed25519 identity.
    public static let meshIdentity = "kagami.mesh.identity"
    /// X25519 keypair for encryption.
    public static let x25519Keypair = "kagami.mesh.x25519"
    /// Hub shared key for local communication.
    public static let hubSharedKey = "kagami.mesh.hub_key"  // pragma: allowlist secret
    /// Cloud API authentication token.
    public static let cloudAuthToken = "kagami.cloud.auth_token"
    /// Device registration info.
    public static let deviceRegistration = "kagami.device.registration"
}

// MARK: - Storage Accessibility

/// Storage accessibility requirements matching iOS Keychain options.
public enum StorageAccessibility: Sendable {
    /// Available only when device is unlocked.
    case whenUnlocked
    /// Available after first unlock until device restart.
    case afterFirstUnlock
    /// Available when unlocked, does not migrate to new device.
    case whenUnlockedThisDeviceOnly
    /// Available after first unlock, does not migrate.
    case afterFirstUnlockThisDeviceOnly

    /// Convert to Keychain attribute.
    var keychainAttribute: CFString {
        switch self {
        case .whenUnlocked:
            return kSecAttrAccessibleWhenUnlocked
        case .afterFirstUnlock:
            return kSecAttrAccessibleAfterFirstUnlock
        case .whenUnlockedThisDeviceOnly:
            return kSecAttrAccessibleWhenUnlockedThisDeviceOnly
        case .afterFirstUnlockThisDeviceOnly:
            return kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        }
    }
}

// MARK: - Stored Identity

/// Complete identity data for mesh network participation.
public struct StoredIdentity: Codable, Sendable {
    /// Ed25519 identity as base64-encoded secret key.
    public let ed25519Identity: String
    /// X25519 secret key as hex for key exchange.
    public let x25519SecretKey: String?
    /// X25519 public key as hex.
    public let x25519PublicKey: String?
    /// Peer ID (derived from Ed25519 public key).
    public let peerId: String
    /// Human-readable device name.
    public let deviceName: String?
    /// Creation timestamp (Unix epoch seconds).
    public let createdAt: Int64
    /// Last used timestamp.
    public let lastUsedAt: Int64?

    public init(
        ed25519Identity: String,
        x25519SecretKey: String? = nil,
        x25519PublicKey: String? = nil,
        peerId: String,
        deviceName: String? = nil,
        createdAt: Int64 = Int64(Date().timeIntervalSince1970),
        lastUsedAt: Int64? = nil
    ) {
        self.ed25519Identity = ed25519Identity
        self.x25519SecretKey = x25519SecretKey
        self.x25519PublicKey = x25519PublicKey
        self.peerId = peerId
        self.deviceName = deviceName
        self.createdAt = createdAt
        self.lastUsedAt = lastUsedAt
    }
}

// MARK: - Load Result

/// Result of an identity load operation.
public enum IdentityLoadResult: Sendable {
    /// Identity loaded successfully.
    case loaded(StoredIdentity)
    /// No identity exists yet.
    case notFound
    /// Identity exists but is inaccessible (device locked, etc).
    case inaccessible(reason: String)
    /// Identity data is corrupted.
    case corrupted(reason: String)
}

// MARK: - Storage Error

/// Errors that can occur during identity storage operations.
public enum IdentityStorageError: Error, Sendable {
    case keyNotFound(key: String)
    case storageUnavailable(reason: String)
    case accessDenied(reason: String)
    case serializationFailed(reason: String)
    case corruptionDetected(reason: String)
    case platformError(code: Int, message: String)

    var localizedDescription: String {
        switch self {
        case .keyNotFound(let key):
            return "Key not found: \(key)"
        case .storageUnavailable(let reason):
            return "Storage unavailable: \(reason)"
        case .accessDenied(let reason):
            return "Access denied: \(reason)"
        case .serializationFailed(let reason):
            return "Serialization failed: \(reason)"
        case .corruptionDetected(let reason):
            return "Corruption detected: \(reason)"
        case .platformError(let code, let message):
            return "Platform error \(code): \(message)"
        }
    }
}

// MARK: - Storage Configuration

/// Configuration for identity storage.
public struct IdentityStorageConfig: Sendable {
    /// Service name for keychain.
    public let serviceName: String
    /// Accessibility level for stored credentials.
    public let accessibility: StorageAccessibility
    /// Whether to sync to iCloud Keychain.
    public let syncToCloud: Bool
    /// Access group for keychain sharing.
    public let accessGroup: String?

    public init(
        serviceName: String = "com.kagami.mesh",
        accessibility: StorageAccessibility = .afterFirstUnlock,
        syncToCloud: Bool = false,
        accessGroup: String? = nil
    ) {
        self.serviceName = serviceName
        self.accessibility = accessibility
        self.syncToCloud = syncToCloud
        self.accessGroup = accessGroup
    }
}

// MARK: - Identity Storage Protocol

/// Protocol for identity storage implementations.
///
/// Platforms implement this protocol to provide secure credential storage.
/// The default iOS implementation uses Keychain Services.
public protocol IdentityStorageProtocol: Sendable {
    /// The storage configuration.
    var config: IdentityStorageConfig { get }

    /// Store an identity securely.
    func storeIdentity(_ identity: StoredIdentity) throws

    /// Load the stored identity.
    func loadIdentity() -> IdentityLoadResult

    /// Delete the stored identity.
    func deleteIdentity() throws

    /// Check if an identity exists.
    func identityExists() -> Bool

    /// Store a raw string value.
    func storeString(_ value: String, forKey key: String) throws

    /// Load a raw string value.
    func loadString(forKey key: String) throws -> String?

    /// Delete a specific key.
    func deleteKey(_ key: String) throws

    /// Store binary data.
    func storeData(_ data: Data, forKey key: String) throws

    /// Load binary data.
    func loadData(forKey key: String) throws -> Data?

    /// Clear all stored data for this service.
    func clearAll() throws
}

// MARK: - Keychain Identity Storage

/// iOS Keychain-based identity storage implementation.
public final class KeychainIdentityStorage: IdentityStorageProtocol, @unchecked Sendable {
    public let config: IdentityStorageConfig
    private let queue = DispatchQueue(label: "com.kagami.identity-storage", qos: .userInitiated)

    public init(config: IdentityStorageConfig = IdentityStorageConfig()) {
        self.config = config
    }

    public func storeIdentity(_ identity: StoredIdentity) throws {
        let encoder = JSONEncoder()
        let data = try encoder.encode(identity)
        try storeData(data, forKey: IdentityStorageKeys.meshIdentity)
    }

    public func loadIdentity() -> IdentityLoadResult {
        do {
            guard let data = try loadData(forKey: IdentityStorageKeys.meshIdentity) else {
                return .notFound
            }
            let decoder = JSONDecoder()
            let identity = try decoder.decode(StoredIdentity.self, from: data)
            return .loaded(identity)
        } catch let error as IdentityStorageError {
            switch error {
            case .keyNotFound:
                return .notFound
            case .accessDenied(let reason):
                return .inaccessible(reason: reason)
            default:
                return .corrupted(reason: error.localizedDescription)
            }
        } catch {
            return .corrupted(reason: error.localizedDescription)
        }
    }

    public func deleteIdentity() throws {
        try deleteKey(IdentityStorageKeys.meshIdentity)
    }

    public func identityExists() -> Bool {
        do {
            return try loadData(forKey: IdentityStorageKeys.meshIdentity) != nil
        } catch {
            return false
        }
    }

    public func storeString(_ value: String, forKey key: String) throws {
        guard let data = value.data(using: .utf8) else {
            throw IdentityStorageError.serializationFailed(reason: "Failed to encode string as UTF-8")
        }
        try storeData(data, forKey: key)
    }

    public func loadString(forKey key: String) throws -> String? {
        guard let data = try loadData(forKey: key) else {
            return nil
        }
        guard let string = String(data: data, encoding: .utf8) else {
            throw IdentityStorageError.corruptionDetected(reason: "Failed to decode string as UTF-8")
        }
        return string
    }

    public func deleteKey(_ key: String) throws {
        try queue.sync {
            var query = baseQuery(forKey: key)

            let status = SecItemDelete(query as CFDictionary)
            if status != errSecSuccess && status != errSecItemNotFound {
                throw IdentityStorageError.platformError(
                    code: Int(status),
                    message: SecCopyErrorMessageString(status, nil) as String? ?? "Unknown error"
                )
            }
        }
    }

    public func storeData(_ data: Data, forKey key: String) throws {
        try queue.sync {
            // First try to update existing item
            var query = baseQuery(forKey: key)
            let updateAttributes: [String: Any] = [
                kSecValueData as String: data
            ]

            var status = SecItemUpdate(query as CFDictionary, updateAttributes as CFDictionary)

            if status == errSecItemNotFound {
                // Item doesn't exist, add it
                query[kSecValueData as String] = data
                query[kSecAttrAccessible as String] = config.accessibility.keychainAttribute

                if !config.syncToCloud {
                    query[kSecAttrSynchronizable as String] = kCFBooleanFalse
                }

                status = SecItemAdd(query as CFDictionary, nil)
            }

            guard status == errSecSuccess else {
                throw IdentityStorageError.platformError(
                    code: Int(status),
                    message: SecCopyErrorMessageString(status, nil) as String? ?? "Unknown error"
                )
            }
        }
    }

    public func loadData(forKey key: String) throws -> Data? {
        try queue.sync {
            var query = baseQuery(forKey: key)
            query[kSecReturnData as String] = kCFBooleanTrue
            query[kSecMatchLimit as String] = kSecMatchLimitOne

            var result: AnyObject?
            let status = SecItemCopyMatching(query as CFDictionary, &result)

            switch status {
            case errSecSuccess:
                return result as? Data
            case errSecItemNotFound:
                return nil
            case errSecInteractionNotAllowed:
                throw IdentityStorageError.accessDenied(reason: "Device is locked")
            default:
                throw IdentityStorageError.platformError(
                    code: Int(status),
                    message: SecCopyErrorMessageString(status, nil) as String? ?? "Unknown error"
                )
            }
        }
    }

    public func clearAll() throws {
        try queue.sync {
            var query: [String: Any] = [
                kSecClass as String: kSecClassGenericPassword,
                kSecAttrService as String: config.serviceName
            ]

            if let accessGroup = config.accessGroup {
                query[kSecAttrAccessGroup as String] = accessGroup
            }

            let status = SecItemDelete(query as CFDictionary)
            if status != errSecSuccess && status != errSecItemNotFound {
                throw IdentityStorageError.platformError(
                    code: Int(status),
                    message: SecCopyErrorMessageString(status, nil) as String? ?? "Unknown error"
                )
            }
        }
    }

    // MARK: - Private Helpers

    private func baseQuery(forKey key: String) -> [String: Any] {
        var query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: config.serviceName,
            kSecAttrAccount as String: key
        ]

        if let accessGroup = config.accessGroup {
            query[kSecAttrAccessGroup as String] = accessGroup
        }

        return query
    }
}

// MARK: - In-Memory Storage (for testing)

/// In-memory storage for testing purposes.
public final class InMemoryIdentityStorage: IdentityStorageProtocol, @unchecked Sendable {
    public let config: IdentityStorageConfig
    private var storage: [String: Data] = [:]
    private let lock = NSLock()

    public init(config: IdentityStorageConfig = IdentityStorageConfig()) {
        self.config = config
    }

    public func storeIdentity(_ identity: StoredIdentity) throws {
        let encoder = JSONEncoder()
        let data = try encoder.encode(identity)
        try storeData(data, forKey: IdentityStorageKeys.meshIdentity)
    }

    public func loadIdentity() -> IdentityLoadResult {
        do {
            guard let data = try loadData(forKey: IdentityStorageKeys.meshIdentity) else {
                return .notFound
            }
            let decoder = JSONDecoder()
            let identity = try decoder.decode(StoredIdentity.self, from: data)
            return .loaded(identity)
        } catch {
            return .corrupted(reason: error.localizedDescription)
        }
    }

    public func deleteIdentity() throws {
        try deleteKey(IdentityStorageKeys.meshIdentity)
    }

    public func identityExists() -> Bool {
        lock.lock()
        defer { lock.unlock() }
        return storage[IdentityStorageKeys.meshIdentity] != nil
    }

    public func storeString(_ value: String, forKey key: String) throws {
        guard let data = value.data(using: .utf8) else {
            throw IdentityStorageError.serializationFailed(reason: "Failed to encode string")
        }
        try storeData(data, forKey: key)
    }

    public func loadString(forKey key: String) throws -> String? {
        guard let data = try loadData(forKey: key) else { return nil }
        return String(data: data, encoding: .utf8)
    }

    public func deleteKey(_ key: String) throws {
        lock.lock()
        defer { lock.unlock() }
        storage.removeValue(forKey: key)
    }

    public func storeData(_ data: Data, forKey key: String) throws {
        lock.lock()
        defer { lock.unlock() }
        storage[key] = data
    }

    public func loadData(forKey key: String) throws -> Data? {
        lock.lock()
        defer { lock.unlock() }
        return storage[key]
    }

    public func clearAll() throws {
        lock.lock()
        defer { lock.unlock() }
        storage.removeAll()
    }
}

/*
 * Kagami Mesh Identity Storage
 * h(x) >= 0. Always.
 */
