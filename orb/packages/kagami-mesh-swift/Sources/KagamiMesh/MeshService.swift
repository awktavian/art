//
// MeshService.swift -- Kagami Mesh Network SDK Integration
//
// Cross-platform Swift wrapper for kagami-mesh-sdk UniFFI bindings.
// Supports iOS, watchOS, tvOS, visionOS, and macOS.
//
// Features:
//   - Ed25519 identity management
//   - Circuit breaker for connection state management
//   - XChaCha20-Poly1305 encryption/decryption
//   - X25519 key exchange for peer encryption
//   - CRDT support (vector clocks, G-counters)
//
// Architecture:
//   MeshService wraps UniFFI bindings (kagami_mesh_sdk) with a clean Swift API.
//   The underlying Rust library provides cryptographic operations.
//
// DRY Philosophy:
//   Write cryptography once in Rust. Generate bindings. Every platform gets:
//   - Ed25519 signatures with zeroize on drop
//   - X25519 key exchange with HKDF salt "kagami-mesh-sdk-v1"
//   - XChaCha20-Poly1305 with OsRng nonces
//   - Vector clocks with automatic merge
//   - CRDTs for offline-first state sync
//
// h(x) >= 0. Always.
//

import Foundation

// MARK: - Mesh Service Errors

/// Errors specific to the Mesh service layer
public enum MeshServiceError: LocalizedError, Sendable {
    case notInitialized
    case identityLoadFailed(String)
    case identityStoreFailed(String)
    case signatureFailed(String)
    case verificationFailed(String)
    case encryptionFailed(String)
    case decryptionFailed(String)
    case keyDerivationFailed(String)
    case connectionStateError(String)
    case crdtError(String)

    public var errorDescription: String? {
        switch self {
        case .notInitialized:
            return "Mesh service not initialized. Call initialize() first."
        case .identityLoadFailed(let msg):
            return "Failed to load mesh identity: \(msg)"
        case .identityStoreFailed(let msg):
            return "Failed to store mesh identity: \(msg)"
        case .signatureFailed(let msg):
            return "Signature operation failed: \(msg)"
        case .verificationFailed(let msg):
            return "Signature verification failed: \(msg)"
        case .encryptionFailed(let msg):
            return "Encryption failed: \(msg)"
        case .decryptionFailed(let msg):
            return "Decryption failed: \(msg)"
        case .keyDerivationFailed(let msg):
            return "Key derivation failed: \(msg)"
        case .connectionStateError(let msg):
            return "Connection state error: \(msg)"
        case .crdtError(let msg):
            return "CRDT operation failed: \(msg)"
        }
    }
}

// MARK: - Connection State

/// Circuit breaker connection states mirroring the Rust SDK
public enum MeshConnectionState: String, CaseIterable, Sendable {
    case disconnected = "Disconnected"
    case connecting = "Connecting"
    case connected = "Connected"
    case circuitOpen = "CircuitOpen"

    /// Parse state from Rust SDK string
    public static func from(_ rustState: String) -> MeshConnectionState {
        switch rustState {
        case "Disconnected": return .disconnected
        case "Connecting": return .connecting
        case "Connected": return .connected
        case "CircuitOpen": return .circuitOpen
        default: return .disconnected
        }
    }
}

// MARK: - Vector Clock Comparison

/// Result of comparing two vector clocks
public enum VectorClockOrdering: String, Sendable {
    case before = "before"
    case after = "after"
    case concurrent = "concurrent"
    case equal = "equal"

    public static func from(_ result: String) -> VectorClockOrdering {
        switch result {
        case "before": return .before
        case "after": return .after
        case "concurrent": return .concurrent
        case "equal": return .equal
        default: return .concurrent
        }
    }
}

// MARK: - Keychain Protocol

/// Protocol for platform-specific keychain operations
public protocol MeshKeychainService: Sendable {
    func save(key: String, value: String) -> Bool
    func load(key: String) -> String?
    func delete(key: String) -> Bool
}

// MARK: - Default Keychain Implementation (Apple Platforms)

/// Default keychain service using Security framework
public final class AppleKeychainService: MeshKeychainService, @unchecked Sendable {
    private let service: String

    public init(service: String = "com.kagami.mesh") {
        self.service = service
    }

    public func save(key: String, value: String) -> Bool {
        guard let data = value.data(using: .utf8) else { return false }

        // Delete existing
        _ = delete(key: key)

        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly
        ]

        let status = SecItemAdd(query as CFDictionary, nil)
        return status == errSecSuccess
    }

    public func load(key: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]

        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)

        guard status == errSecSuccess,
              let data = result as? Data,
              let string = String(data: data, encoding: .utf8) else {
            return nil
        }

        return string
    }

    public func delete(key: String) -> Bool {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key
        ]

        let status = SecItemDelete(query as CFDictionary)
        return status == errSecSuccess || status == errSecItemNotFound
    }
}

// MARK: - Mesh Service

/// Main service for interacting with the Kagami Mesh SDK.
///
/// This service provides:
/// - Ed25519 identity management with secure storage
/// - Message signing and verification
/// - XChaCha20-Poly1305 encryption
/// - X25519 key exchange
/// - Connection state management with circuit breaker
/// - CRDT helpers for distributed state
///
/// Thread Safety: This service is marked @MainActor for UI integration.
/// Cryptographic operations are performed on the Rust side which is thread-safe.
@MainActor
public final class MeshService: ObservableObject {

    // MARK: - Singleton

    public static let shared = MeshService()

    // MARK: - Keychain Keys

    public enum KeychainKey: String {
        case meshIdentity = "meshIdentity"
        case encryptionKey = "meshEncryptionKey"
        case x25519PrivateKey = "meshX25519PrivateKey"  // pragma: allowlist secret
    }

    // MARK: - Published State

    /// Whether the service is initialized with a valid identity
    @Published public private(set) var isInitialized = false

    /// The current mesh peer ID (hex-encoded public key)
    @Published public private(set) var peerId: String?

    /// Connection state managed by the circuit breaker
    @Published public private(set) var connectionState: MeshConnectionState = .disconnected

    /// Number of consecutive failures
    @Published public private(set) var failureCount: UInt32 = 0

    /// Current backoff delay in milliseconds (when circuit is open)
    @Published public private(set) var backoffMs: UInt64 = 0

    // MARK: - Private State

    /// The mesh identity (Ed25519 keypair) - stored in Keychain
    private var identity: MeshIdentity?

    /// Connection state tracker from Rust SDK
    private var connection: MeshConnection?

    /// X25519 keypair for key exchange
    private var x25519KeyPair: X25519KeyPair?

    /// Derived encryption key (from X25519 exchange)
    private var derivedEncryptionKey: String?

    /// Keychain service for secure storage
    private var keychainService: MeshKeychainService

    // MARK: - Init

    private init(keychainService: MeshKeychainService = AppleKeychainService()) {
        self.keychainService = keychainService
    }

    /// Create a MeshService with custom keychain implementation
    public static func create(keychainService: MeshKeychainService) -> MeshService {
        let service = MeshService(keychainService: keychainService)
        return service
    }

    // MARK: - Initialization

    /// Initialize the mesh service.
    ///
    /// This loads or creates a mesh identity and sets up the connection tracker.
    /// The identity is persisted in the platform keychain for security.
    ///
    /// - Throws: MeshServiceError if initialization fails
    public func initialize() async throws {
        // Initialize connection tracker
        connection = MeshConnection()

        // Try to load existing identity from Keychain
        if let storedIdentity = loadIdentityFromKeychain() {
            identity = storedIdentity
            peerId = storedIdentity.peerId()
        } else {
            // Generate new identity
            let newIdentity = MeshIdentity()
            identity = newIdentity
            peerId = newIdentity.peerId()

            // Persist to Keychain
            try saveIdentityToKeychain(newIdentity)
        }

        // Try to load X25519 keypair
        if let storedKeyPair = loadX25519KeyPairFromKeychain() {
            x25519KeyPair = storedKeyPair
        }

        isInitialized = true
        updateConnectionState()

        #if DEBUG
        print("[MeshService] Initialized with peer ID: \(peerId ?? "unknown")")
        #endif
    }

    /// Reset the mesh service, generating a new identity.
    ///
    /// WARNING: This will invalidate all existing signatures and peer relationships.
    public func resetIdentity() throws {
        let newIdentity = MeshIdentity()
        identity = newIdentity
        peerId = newIdentity.peerId()

        try saveIdentityToKeychain(newIdentity)

        // Clear derived keys
        derivedEncryptionKey = nil
        x25519KeyPair = nil
        _ = keychainService.delete(key: KeychainKey.x25519PrivateKey.rawValue)
        _ = keychainService.delete(key: KeychainKey.encryptionKey.rawValue)

        #if DEBUG
        print("[MeshService] Identity reset. New peer ID: \(peerId ?? "unknown")")
        #endif
    }

    // MARK: - Identity Operations

    /// Get the public key as hex string.
    public var publicKeyHex: String? {
        identity?.publicKeyHex()
    }

    /// Export the identity as base64 for backup.
    ///
    /// WARNING: This exports the secret key. Handle with extreme care.
    public func exportIdentity() -> String? {
        identity?.toBase64()
    }

    /// Import an identity from base64 backup.
    ///
    /// - Parameter base64: The base64-encoded identity
    /// - Throws: MeshServiceError if import fails
    public func importIdentity(_ base64: String) throws {
        do {
            let imported = try MeshIdentity.fromBase64(encoded: base64)
            identity = imported
            peerId = imported.peerId()
            try saveIdentityToKeychain(imported)

            #if DEBUG
            print("[MeshService] Imported identity with peer ID: \(peerId ?? "unknown")")
            #endif
        } catch {
            throw MeshServiceError.identityLoadFailed(error.localizedDescription)
        }
    }

    // MARK: - Signing & Verification

    /// Sign a message with the mesh identity.
    ///
    /// - Parameter message: The message data to sign
    /// - Returns: Hex-encoded Ed25519 signature
    /// - Throws: MeshServiceError if not initialized or signing fails
    public func sign(message: Data) throws -> String {
        guard let identity = identity else {
            throw MeshServiceError.notInitialized
        }

        return identity.sign(message: message)
    }

    /// Sign a string message.
    ///
    /// - Parameter message: The string message to sign (UTF-8 encoded)
    /// - Returns: Hex-encoded Ed25519 signature
    public func sign(message: String) throws -> String {
        guard let data = message.data(using: .utf8) else {
            throw MeshServiceError.signatureFailed("Failed to encode message as UTF-8")
        }
        return try sign(message: data)
    }

    /// Verify a signature from this identity.
    ///
    /// - Parameters:
    ///   - message: The original message data
    ///   - signatureHex: The hex-encoded signature
    /// - Returns: true if signature is valid
    public func verify(message: Data, signatureHex: String) throws -> Bool {
        guard let identity = identity else {
            throw MeshServiceError.notInitialized
        }

        do {
            return try identity.verify(message: message, signatureHex: signatureHex)
        } catch {
            throw MeshServiceError.verificationFailed(error.localizedDescription)
        }
    }

    /// Verify a signature from any public key.
    ///
    /// - Parameters:
    ///   - publicKeyHex: The hex-encoded public key of the signer
    ///   - message: The original message data
    ///   - signatureHex: The hex-encoded signature
    /// - Returns: true if signature is valid
    public func verifyFromPeer(publicKeyHex: String, message: Data, signatureHex: String) throws -> Bool {
        do {
            return try verifySignature(publicKeyHex: publicKeyHex, message: message, signatureHex: signatureHex)
        } catch {
            throw MeshServiceError.verificationFailed(error.localizedDescription)
        }
    }

    // MARK: - Encryption & Decryption

    /// Generate a new encryption key.
    ///
    /// - Returns: Hex-encoded XChaCha20-Poly1305 key
    public func generateEncryptionKey() -> String {
        return generateCipherKey()
    }

    /// Encrypt data with a key.
    ///
    /// - Parameters:
    ///   - plaintext: The data to encrypt
    ///   - keyHex: The hex-encoded encryption key
    /// - Returns: Hex-encoded ciphertext (includes nonce)
    public func encrypt(plaintext: Data, keyHex: String) throws -> String {
        do {
            return try encryptData(keyHex: keyHex, plaintext: plaintext)
        } catch {
            throw MeshServiceError.encryptionFailed(error.localizedDescription)
        }
    }

    /// Encrypt a string message.
    public func encrypt(message: String, keyHex: String) throws -> String {
        guard let data = message.data(using: .utf8) else {
            throw MeshServiceError.encryptionFailed("Failed to encode message as UTF-8")
        }
        return try encrypt(plaintext: data, keyHex: keyHex)
    }

    /// Decrypt ciphertext.
    ///
    /// - Parameters:
    ///   - ciphertextHex: The hex-encoded ciphertext
    ///   - keyHex: The hex-encoded encryption key
    /// - Returns: The decrypted data
    public func decrypt(ciphertextHex: String, keyHex: String) throws -> Data {
        do {
            return try decryptData(keyHex: keyHex, ciphertextHex: ciphertextHex)
        } catch {
            throw MeshServiceError.decryptionFailed(error.localizedDescription)
        }
    }

    /// Decrypt to a string.
    public func decryptToString(ciphertextHex: String, keyHex: String) throws -> String {
        let data = try decrypt(ciphertextHex: ciphertextHex, keyHex: keyHex)
        guard let string = String(data: data, encoding: .utf8) else {
            throw MeshServiceError.decryptionFailed("Decrypted data is not valid UTF-8")
        }
        return string
    }

    // MARK: - X25519 Key Exchange

    /// Generate an X25519 keypair for Diffie-Hellman key exchange.
    ///
    /// The keypair is stored in Keychain for persistence.
    ///
    /// - Returns: The public key hex for sharing with peers
    public func generateX25519KeyPair() throws -> String {
        let keyPair = generateX25519Keypair()
        x25519KeyPair = keyPair

        // Store in Keychain
        _ = keychainService.save(key: KeychainKey.x25519PrivateKey.rawValue, value: keyPair.secretKeyHex)

        return keyPair.publicKeyHex
    }

    /// Get the current X25519 public key.
    public var x25519PublicKeyHex: String? {
        x25519KeyPair?.publicKeyHex
    }

    /// Derive a shared encryption key from peer's X25519 public key.
    ///
    /// This performs Diffie-Hellman key exchange to derive a shared secret
    /// that can be used for encryption between the two parties.
    ///
    /// - Parameter peerPublicKeyHex: The peer's X25519 public key
    /// - Returns: Hex-encoded shared encryption key
    public func deriveSharedKey(peerPublicKeyHex: String) throws -> String {
        guard let keyPair = x25519KeyPair else {
            throw MeshServiceError.keyDerivationFailed("No X25519 keypair. Call generateX25519KeyPair() first.")
        }

        do {
            let sharedKey = try x25519DeriveKey(
                secretKeyHex: keyPair.secretKeyHex,
                peerPublicKeyHex: peerPublicKeyHex
            )
            derivedEncryptionKey = sharedKey
            return sharedKey
        } catch {
            throw MeshServiceError.keyDerivationFailed(error.localizedDescription)
        }
    }

    // MARK: - Connection State Management

    /// Signal that a connection attempt is starting.
    public func onConnect() throws {
        guard let connection = connection else {
            throw MeshServiceError.connectionStateError("Connection tracker not initialized")
        }

        do {
            let _ = try connection.onConnect()
            updateConnectionState()
        } catch {
            throw MeshServiceError.connectionStateError(error.localizedDescription)
        }
    }

    /// Signal that connection succeeded.
    public func onConnected() throws {
        guard let connection = connection else {
            throw MeshServiceError.connectionStateError("Connection tracker not initialized")
        }

        do {
            let _ = try connection.onConnected()
            updateConnectionState()
        } catch {
            throw MeshServiceError.connectionStateError(error.localizedDescription)
        }
    }

    /// Signal that a connection attempt failed.
    ///
    /// - Parameter reason: Description of the failure
    public func onFailure(reason: String) throws {
        guard let connection = connection else {
            throw MeshServiceError.connectionStateError("Connection tracker not initialized")
        }

        do {
            let _ = try connection.onFailure(reason: reason)
            updateConnectionState()
        } catch {
            throw MeshServiceError.connectionStateError(error.localizedDescription)
        }
    }

    /// Signal that a disconnection occurred.
    ///
    /// - Parameter reason: Description of the disconnection
    public func onDisconnect(reason: String) throws {
        guard let connection = connection else {
            throw MeshServiceError.connectionStateError("Connection tracker not initialized")
        }

        do {
            let _ = try connection.onDisconnect(reason: reason)
            updateConnectionState()
        } catch {
            throw MeshServiceError.connectionStateError(error.localizedDescription)
        }
    }

    /// Check if a connection attempt should be made (circuit breaker check).
    public var shouldAttemptConnection: Bool {
        connection?.shouldAttemptRecovery() ?? false
    }

    /// Check if currently connected.
    public var isConnected: Bool {
        connection?.isConnected() ?? false
    }

    /// Reset the connection state machine.
    public func resetConnection() {
        connection?.reset()
        updateConnectionState()
    }

    private func updateConnectionState() {
        guard let connection = connection else { return }

        connectionState = MeshConnectionState.from(connection.state())
        failureCount = connection.failureCount()
        backoffMs = connection.backoffMs()
    }

    // MARK: - CRDT: Vector Clocks

    /// Create a new vector clock for this node.
    ///
    /// - Returns: JSON representation of the vector clock
    public func createVectorClock() throws -> String {
        guard let peerId = peerId else {
            throw MeshServiceError.notInitialized
        }
        return vectorClockNew(nodeId: peerId)
    }

    /// Increment the vector clock for this node.
    ///
    /// - Parameter clockJson: The current vector clock JSON
    /// - Returns: Updated vector clock JSON
    public func incrementVectorClock(_ clockJson: String) throws -> String {
        guard let peerId = peerId else {
            throw MeshServiceError.notInitialized
        }

        do {
            return try vectorClockIncrement(clockJson: clockJson, nodeId: peerId)
        } catch {
            throw MeshServiceError.crdtError(error.localizedDescription)
        }
    }

    /// Merge two vector clocks.
    ///
    /// - Parameters:
    ///   - clock1Json: First vector clock JSON
    ///   - clock2Json: Second vector clock JSON
    /// - Returns: Merged vector clock JSON
    public func mergeVectorClocks(_ clock1Json: String, _ clock2Json: String) throws -> String {
        do {
            return try vectorClockMerge(clock1Json: clock1Json, clock2Json: clock2Json)
        } catch {
            throw MeshServiceError.crdtError(error.localizedDescription)
        }
    }

    /// Compare two vector clocks to determine ordering.
    ///
    /// - Parameters:
    ///   - clock1Json: First vector clock JSON
    ///   - clock2Json: Second vector clock JSON
    /// - Returns: The ordering relationship between the clocks
    public func compareVectorClocks(_ clock1Json: String, _ clock2Json: String) throws -> VectorClockOrdering {
        do {
            let result = try vectorClockCompare(clock1Json: clock1Json, clock2Json: clock2Json)
            return VectorClockOrdering.from(result)
        } catch {
            throw MeshServiceError.crdtError(error.localizedDescription)
        }
    }

    // MARK: - CRDT: G-Counter

    /// Create a new G-Counter.
    ///
    /// - Returns: JSON representation of the counter
    public func createGCounter() -> String {
        return gCounterNew()
    }

    /// Increment the G-Counter for this node.
    ///
    /// - Parameter counterJson: The current counter JSON
    /// - Returns: Updated counter JSON
    public func incrementGCounter(_ counterJson: String) throws -> String {
        guard let peerId = peerId else {
            throw MeshServiceError.notInitialized
        }

        do {
            return try gCounterIncrement(counterJson: counterJson, nodeId: peerId)
        } catch {
            throw MeshServiceError.crdtError(error.localizedDescription)
        }
    }

    /// Merge two G-Counters.
    ///
    /// - Parameters:
    ///   - counter1Json: First counter JSON
    ///   - counter2Json: Second counter JSON
    /// - Returns: Merged counter JSON
    public func mergeGCounters(_ counter1Json: String, _ counter2Json: String) throws -> String {
        do {
            return try gCounterMerge(counter1Json: counter1Json, counter2Json: counter2Json)
        } catch {
            throw MeshServiceError.crdtError(error.localizedDescription)
        }
    }

    /// Get the value of a G-Counter.
    ///
    /// - Parameter counterJson: The counter JSON
    /// - Returns: The counter value
    public func getGCounterValue(_ counterJson: String) throws -> UInt64 {
        do {
            return try gCounterValue(counterJson: counterJson)
        } catch {
            throw MeshServiceError.crdtError(error.localizedDescription)
        }
    }

    // MARK: - Keychain Operations

    private func loadIdentityFromKeychain() -> MeshIdentity? {
        guard let base64 = keychainService.load(key: KeychainKey.meshIdentity.rawValue) else {
            return nil
        }

        do {
            return try MeshIdentity.fromBase64(encoded: base64)
        } catch {
            #if DEBUG
            print("[MeshService] Failed to load identity from Keychain: \(error)")
            #endif
            return nil
        }
    }

    private func saveIdentityToKeychain(_ identity: MeshIdentity) throws {
        let base64 = identity.toBase64()
        if !keychainService.save(key: KeychainKey.meshIdentity.rawValue, value: base64) {
            throw MeshServiceError.identityStoreFailed("Keychain write failed")
        }
    }

    private func loadX25519KeyPairFromKeychain() -> X25519KeyPair? {
        guard let _ = keychainService.load(key: KeychainKey.x25519PrivateKey.rawValue) else {
            return nil
        }

        // X25519 keypair needs regeneration to derive public key
        // In production, store both or implement public key derivation
        return nil
    }
}

/*
 * Mirror
 *
 * The mesh identity is the cryptographic foundation of peer trust.
 * Ed25519 provides strong authentication without key exchange overhead.
 * X25519 enables forward-secure encryption between peers.
 *
 * One crate. All platforms. Zero duplication.
 *
 * h(x) >= 0. Always.
 */
