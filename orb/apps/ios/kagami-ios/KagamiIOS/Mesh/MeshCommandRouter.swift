//
// MeshCommandRouter.swift -- Mesh Command Router
//
// Colony: Nexus (e4) -- Integration
//
// Routes commands through the Kagami mesh network instead of HTTP.
// Commands are signed with Ed25519 and routed to Hub peers.
//
// h(x) >= 0. Always.
//

import Foundation
import Combine
import Network

// MARK: - Mesh Command Types

/// Commands that can be sent through the mesh network
public enum MeshCommand: Codable, Sendable {
    // Device Control
    case setLights(level: Int, rooms: [String]?)
    case tvControl(action: String, preset: Int?)
    case fireplace(on: Bool)
    case shades(action: String, rooms: [String]?)
    case lockAll
    case unlock(lockId: String)
    case setTemperature(temp: Double, room: String)

    // Scenes
    case executeScene(sceneId: String)
    case exitMovieMode

    // Audio
    case announce(message: String, rooms: [String]?)

    // Status
    case healthCheck
    case fetchRooms
    case fetchStatus

    /// Command type string for routing
    var commandType: String {
        switch self {
        case .setLights: return "device.lights.set"
        case .tvControl: return "device.tv.control"
        case .fireplace: return "device.fireplace.toggle"
        case .shades: return "device.shades.control"
        case .lockAll: return "device.locks.lockAll"
        case .unlock: return "device.locks.unlock"
        case .setTemperature: return "device.climate.set"
        case .executeScene: return "scene.execute"
        case .exitMovieMode: return "scene.exitMovieMode"
        case .announce: return "audio.announce"
        case .healthCheck: return "status.health"
        case .fetchRooms: return "status.rooms"
        case .fetchStatus: return "status.home"
        }
    }

    /// Convert to JSON payload
    func toPayload() throws -> Data {
        let encoder = JSONEncoder()
        return try encoder.encode(self)
    }
}

/// Response from a mesh command
public struct MeshCommandResponse: Codable, Sendable {
    public let success: Bool
    public let commandId: String
    public let result: AnyCodable?
    public let error: String?
    public let timestamp: Date

    enum CodingKeys: String, CodingKey {
        case success, commandId, result, error, timestamp
    }

    public init(success: Bool, commandId: String, result: AnyCodable? = nil, error: String? = nil) {
        self.success = success
        self.commandId = commandId
        self.result = result
        self.error = error
        self.timestamp = Date()
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        success = try container.decode(Bool.self, forKey: .success)
        commandId = try container.decode(String.self, forKey: .commandId)
        result = try container.decodeIfPresent(AnyCodable.self, forKey: .result)
        error = try container.decodeIfPresent(String.self, forKey: .error)
        timestamp = try container.decodeIfPresent(Date.self, forKey: .timestamp) ?? Date()
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(success, forKey: .success)
        try container.encode(commandId, forKey: .commandId)
        try container.encodeIfPresent(result, forKey: .result)
        try container.encodeIfPresent(error, forKey: .error)
        try container.encode(timestamp, forKey: .timestamp)
    }
}

// Note: AnyCodable is defined in HubManager.swift

// MARK: - Mesh Command Router

/// Routes commands through the mesh network with Ed25519 signatures.
///
/// The router:
/// 1. Discovers Hub peers via the mesh service
/// 2. Signs commands with the local Ed25519 identity
/// 3. Encrypts payloads with XChaCha20-Poly1305
/// 4. Sends via the mesh transport layer
/// 5. Validates responses
///
/// Falls back to legacy HTTP if mesh is unavailable (for migration).
@MainActor
public final class MeshCommandRouter: ObservableObject {

    // MARK: - Singleton

    public static let shared = MeshCommandRouter()

    // MARK: - Dependencies

    private let meshService: MeshService

    // MARK: - Published State

    @Published public private(set) var isConnected = false
    @Published public private(set) var connectedHubs: [String] = []
    @Published public private(set) var pendingCommands = 0
    @Published public private(set) var lastError: MeshRouterError?

    // MARK: - Hub Discovery

    /// Known Hub peer IDs (discovered via mesh)
    private var hubPeers: Set<String> = []

    /// Hub encryption keys (derived via X25519)
    private var hubKeys: [String: String] = [:]

    /// Active WebSocket connections to Hubs
    private var hubConnections: [String: MeshWebSocketConnection] = [:]

    /// mDNS browser for Hub discovery
    private var mdnsBrowser: NWBrowser?

    /// Pending response continuations (commandId -> continuation)
    private var pendingResponses: [String: CheckedContinuation<MeshCommandResponse, Error>] = [:]

    /// Command queue for offline support
    private var commandQueue: [QueuedCommand] = []

    /// Maximum queue size
    private let maxQueueSize = 100

    /// Default command timeout
    private let commandTimeout: TimeInterval = 10.0

    // MARK: - Init

    private init() {
        self.meshService = MeshService.shared
    }

    // MARK: - Initialization

    /// Initialize the router and discover Hub peers.
    public func initialize() async throws {
        // Ensure mesh service is initialized
        if !meshService.isInitialized {
            try await meshService.initialize()
        }

        // Generate X25519 keypair for hub encryption
        let _ = try meshService.generateX25519KeyPair()

        // Start mDNS discovery for Hub peers
        startHubDiscovery()

        isConnected = meshService.isInitialized

        #if DEBUG
        print("[MeshCommandRouter] Initialized. Mesh peer ID: \(meshService.peerId ?? "unknown")")
        #endif
    }

    // MARK: - mDNS Hub Discovery

    /// Start mDNS discovery for Kagami Hub services.
    private func startHubDiscovery() {
        stopHubDiscovery()

        let parameters = NWParameters()
        parameters.includePeerToPeer = true

        // Browse for _kagami-hub._tcp services (same as HubManager)
        mdnsBrowser = NWBrowser(for: .bonjour(type: "_kagami-hub._tcp", domain: "local."), using: parameters)

        mdnsBrowser?.stateUpdateHandler = { [weak self] state in
            Task { @MainActor in
                switch state {
                case .ready:
                    #if DEBUG
                    print("[MeshCommandRouter] mDNS discovery ready")
                    #endif
                case .failed(let error):
                    self?.lastError = .commandFailed("discovery", error.localizedDescription)
                    #if DEBUG
                    print("[MeshCommandRouter] mDNS discovery failed: \(error)")
                    #endif
                default:
                    break
                }
            }
        }

        mdnsBrowser?.browseResultsChangedHandler = { [weak self] results, changes in
            Task { @MainActor in
                self?.handleDiscoveryResults(results)
            }
        }

        mdnsBrowser?.start(queue: .main)
    }

    /// Stop mDNS discovery.
    private func stopHubDiscovery() {
        mdnsBrowser?.cancel()
        mdnsBrowser = nil
    }

    /// Handle discovered Hub services.
    private func handleDiscoveryResults(_ results: Set<NWBrowser.Result>) {
        for result in results {
            if case .service(let name, _, _, _) = result.endpoint {
                resolveHubService(result: result, name: name)
            }
        }
    }

    /// Resolve a discovered Hub service to get its host/port.
    private func resolveHubService(result: NWBrowser.Result, name: String) {
        let connection = NWConnection(to: result.endpoint, using: .tcp)

        connection.stateUpdateHandler = { [weak self] state in
            if case .ready = state {
                if let endpoint = connection.currentPath?.remoteEndpoint,
                   case .hostPort(let host, let port) = endpoint {
                    let hostString = "\(host)"
                    let portInt = Int(port.rawValue)

                    Task { @MainActor [weak self] in
                        guard let self = self else { return }

                        // Connect to the Hub via WebSocket
                        let hubId = "\(hostString):\(portInt)"
                        if !self.hubConnections.keys.contains(hubId) {
                            await self.connectToHub(host: hostString, port: portInt, name: name)
                        }
                    }
                }
                connection.cancel()
            }
        }

        connection.start(queue: .global())
    }

    /// Connect to a discovered Hub via WebSocket.
    private func connectToHub(host: String, port: Int, name: String) async {
        let hubId = "\(host):\(port)"

        // Create WebSocket connection to the Hub's mesh endpoint
        let wsURL = URL(string: "wss://\(host):\(port)/mesh/ws")!

        let wsConnection = MeshWebSocketConnection(
            url: wsURL,
            hubId: hubId,
            onMessage: { [weak self] message in
                Task { @MainActor in
                    self?.handleHubMessage(message, from: hubId)
                }
            },
            onConnected: { [weak self] publicKeyX25519 in
                Task { @MainActor in
                    guard let self = self else { return }
                    // Derive shared key from Hub's X25519 public key
                    do {
                        let sharedKey = try self.meshService.deriveSharedKey(peerPublicKeyHex: publicKeyX25519)
                        self.hubKeys[hubId] = sharedKey
                        self.hubPeers.insert(hubId)
                        self.connectedHubs = Array(self.hubPeers)

                        // Process any queued commands
                        await self.processQueue()

                        #if DEBUG
                        print("[MeshCommandRouter] Connected to Hub \(hubId)")
                        #endif
                    } catch {
                        #if DEBUG
                        print("[MeshCommandRouter] Failed to derive shared key: \(error)")
                        #endif
                    }
                }
            },
            onDisconnected: { [weak self] in
                Task { @MainActor in
                    self?.hubPeers.remove(hubId)
                    self?.hubKeys.removeValue(forKey: hubId)
                    self?.hubConnections.removeValue(forKey: hubId)
                    self?.connectedHubs = Array(self?.hubPeers ?? [])
                }
            }
        )

        hubConnections[hubId] = wsConnection
        wsConnection.connect(localPublicKey: meshService.x25519PublicKeyHex ?? "")
    }

    /// Handle incoming message from a Hub.
    private func handleHubMessage(_ messageData: Data, from hubId: String) {
        guard let encryptionKey = hubKeys[hubId] else { return }

        do {
            // Decrypt the message
            let decryptedData = try meshService.decrypt(
                ciphertextHex: String(data: messageData, encoding: .utf8) ?? "",
                keyHex: encryptionKey
            )

            // Parse the response
            let decoder = JSONDecoder()
            decoder.dateDecodingStrategy = .iso8601
            let response = try decoder.decode(MeshCommandResponse.self, from: decryptedData)

            // Resume the waiting continuation
            if let continuation = pendingResponses.removeValue(forKey: response.commandId) {
                continuation.resume(returning: response)
            }

        } catch {
            #if DEBUG
            print("[MeshCommandRouter] Failed to handle Hub message: \(error)")
            #endif
        }
    }

    /// Register a Hub peer for command routing.
    ///
    /// - Parameters:
    ///   - peerId: The Hub's Ed25519 public key (hex)
    ///   - publicKeyX25519: The Hub's X25519 public key for encryption
    public func registerHub(peerId: String, publicKeyX25519: String) async throws {
        // Derive shared encryption key
        let sharedKey = try meshService.deriveSharedKey(peerPublicKeyHex: publicKeyX25519)

        hubPeers.insert(peerId)
        hubKeys[peerId] = sharedKey
        connectedHubs = Array(hubPeers)

        #if DEBUG
        print("[MeshCommandRouter] Registered Hub peer: \(peerId.prefix(16))...")
        #endif
    }

    /// Unregister a Hub peer.
    public func unregisterHub(peerId: String) {
        hubPeers.remove(peerId)
        hubKeys.removeValue(forKey: peerId)
        connectedHubs = Array(hubPeers)
    }

    // MARK: - Command Execution

    /// Execute a command through the mesh network.
    ///
    /// The command is:
    /// 1. Serialized to JSON
    /// 2. Signed with Ed25519
    /// 3. Encrypted with the Hub's shared key
    /// 4. Sent to available Hub peers
    ///
    /// - Parameter command: The command to execute
    /// - Returns: The command response
    @discardableResult
    public func execute(_ command: MeshCommand) async throws -> MeshCommandResponse {
        guard meshService.isInitialized else {
            throw MeshRouterError.notInitialized
        }

        pendingCommands += 1
        defer { pendingCommands -= 1 }

        let commandId = UUID().uuidString

        // If no Hub peers, queue for later
        guard let hubPeerId = hubPeers.first,
              let encryptionKey = hubKeys[hubPeerId] else {
            // Queue command for when Hub connects
            queueCommand(command, id: commandId)
            return MeshCommandResponse(
                success: false,
                commandId: commandId,
                error: "No Hub available - command queued"
            )
        }

        do {
            // Build the command envelope
            let envelope = try buildCommandEnvelope(command: command, commandId: commandId)

            // Sign the envelope
            let signatureHex = try meshService.sign(message: envelope)

            // Encrypt the payload
            let encryptedPayload = try meshService.encrypt(plaintext: envelope, keyHex: encryptionKey)

            // Build the mesh message
            let meshMessage = MeshMessage(
                senderId: meshService.peerId ?? "",
                recipientId: hubPeerId,
                commandType: command.commandType,
                payload: encryptedPayload,
                signature: signatureHex,
                timestamp: Date()
            )

            // Send via WebSocket transport
            let response = try await sendToHub(message: meshMessage, hubId: hubPeerId, commandId: commandId)

            lastError = nil
            return response

        } catch {
            lastError = .commandFailed(command.commandType, error.localizedDescription)
            throw error
        }
    }

    /// Execute with automatic retry and fallback.
    @discardableResult
    public func executeWithFallback(_ command: MeshCommand, legacyFallback: (() async -> Bool)? = nil) async -> Bool {
        do {
            let response = try await execute(command)
            return response.success
        } catch {
            #if DEBUG
            print("[MeshCommandRouter] Mesh execution failed: \(error). Trying fallback...")
            #endif

            // Try legacy HTTP fallback if provided
            if let fallback = legacyFallback {
                return await fallback()
            }

            return false
        }
    }

    // MARK: - Command Helpers

    private func buildCommandEnvelope(command: MeshCommand, commandId: String) throws -> Data {
        let envelope = CommandEnvelope(
            id: commandId,
            type: command.commandType,
            payload: try command.toPayload(),
            timestamp: Date(),
            peerId: meshService.peerId ?? ""
        )

        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        return try encoder.encode(envelope)
    }

    private func sendToHub(message: MeshMessage, hubId: String, commandId: String) async throws -> MeshCommandResponse {
        guard let wsConnection = hubConnections[hubId] else {
            throw MeshRouterError.noHubAvailable
        }

        #if DEBUG
        print("[MeshCommandRouter] Sending command '\(message.commandType)' to Hub \(hubId.prefix(16))...")
        #endif

        // Serialize the message
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        let messageData = try encoder.encode(message)

        // Send via WebSocket and wait for response with timeout
        return try await withCheckedThrowingContinuation { continuation in
            // Store the continuation using the original commandId
            // The Hub will respond with this same commandId
            self.pendingResponses[commandId] = continuation

            // Send the message
            wsConnection.send(data: messageData)

            // Set up timeout
            Task {
                try? await Task.sleep(nanoseconds: UInt64(self.commandTimeout * 1_000_000_000))

                // If still pending, timeout
                if let pendingContinuation = self.pendingResponses.removeValue(forKey: commandId) {
                    pendingContinuation.resume(throwing: MeshRouterError.timeout)
                }
            }
        }
    }

    // MARK: - Command Queue

    private func queueCommand(_ command: MeshCommand, id: String) {
        let queued = QueuedCommand(id: id, command: command, timestamp: Date())

        if commandQueue.count >= maxQueueSize {
            // Remove oldest command
            commandQueue.removeFirst()
        }

        commandQueue.append(queued)

        #if DEBUG
        print("[MeshCommandRouter] Queued command \(id) (queue size: \(commandQueue.count))")
        #endif
    }

    /// Process queued commands when Hub becomes available.
    public func processQueue() async {
        guard !hubPeers.isEmpty else { return }

        let commands = commandQueue
        commandQueue.removeAll()

        for queued in commands {
            do {
                let _ = try await execute(queued.command)
            } catch {
                #if DEBUG
                print("[MeshCommandRouter] Failed to process queued command \(queued.id): \(error)")
                #endif
            }
        }
    }

    /// Get the number of queued commands.
    public var queuedCommandCount: Int {
        commandQueue.count
    }
}

// MARK: - Supporting Types

struct CommandEnvelope: Codable {
    let id: String
    let type: String
    let payload: Data
    let timestamp: Date
    let peerId: String
}

struct MeshMessage: Codable {
    let senderId: String
    let recipientId: String
    let commandType: String
    let payload: String // Encrypted hex
    let signature: String // Ed25519 hex
    let timestamp: Date
}

struct QueuedCommand {
    let id: String
    let command: MeshCommand
    let timestamp: Date
}

// MARK: - Mesh Router Error

public enum MeshRouterError: LocalizedError {
    case notInitialized
    case noHubAvailable
    case commandFailed(String, String)
    case encryptionFailed(String)
    case signatureFailed(String)
    case timeout
    case invalidResponse

    public var errorDescription: String? {
        switch self {
        case .notInitialized:
            return "Mesh router not initialized"
        case .noHubAvailable:
            return "No Hub peers available"
        case .commandFailed(let cmd, let reason):
            return "Command '\(cmd)' failed: \(reason)"
        case .encryptionFailed(let msg):
            return "Encryption failed: \(msg)"
        case .signatureFailed(let msg):
            return "Signature failed: \(msg)"
        case .timeout:
            return "Command timed out"
        case .invalidResponse:
            return "Invalid response from Hub"
        }
    }
}

// MARK: - Convenience Extensions for DeviceControlService

extension MeshCommandRouter {

    /// Execute a lights command.
    @discardableResult
    public func setLights(_ level: Int, rooms: [String]? = nil) async -> Bool {
        return await executeWithFallback(.setLights(level: level, rooms: rooms))
    }

    /// Execute a TV control command.
    @discardableResult
    public func tvControl(_ action: String, preset: Int? = nil) async -> Bool {
        return await executeWithFallback(.tvControl(action: action, preset: preset))
    }

    /// Execute a fireplace command.
    @discardableResult
    public func fireplace(on: Bool) async -> Bool {
        return await executeWithFallback(.fireplace(on: on))
    }

    /// Execute a shades command.
    @discardableResult
    public func shades(_ action: String, rooms: [String]? = nil) async -> Bool {
        return await executeWithFallback(.shades(action: action, rooms: rooms))
    }

    /// Execute a scene.
    @discardableResult
    public func executeScene(_ sceneId: String) async -> Bool {
        return await executeWithFallback(.executeScene(sceneId: sceneId))
    }

    /// Announce message.
    @discardableResult
    public func announce(_ message: String, rooms: [String]? = nil) async -> Bool {
        return await executeWithFallback(.announce(message: message, rooms: rooms))
    }
}

// MARK: - WebSocket Connection

/// WebSocket connection handler for mesh communication with a Hub.
final class MeshWebSocketConnection: NSObject, URLSessionWebSocketDelegate {
    private let url: URL
    private let hubId: String
    private var webSocketTask: URLSessionWebSocketTask?
    private var session: URLSession!

    private let onMessage: (Data) -> Void
    private let onConnected: (String) -> Void  // Receives Hub's X25519 public key
    private let onDisconnected: () -> Void

    private var isConnected = false

    init(
        url: URL,
        hubId: String,
        onMessage: @escaping (Data) -> Void,
        onConnected: @escaping (String) -> Void,
        onDisconnected: @escaping () -> Void
    ) {
        self.url = url
        self.hubId = hubId
        self.onMessage = onMessage
        self.onConnected = onConnected
        self.onDisconnected = onDisconnected
        super.init()

        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30
        self.session = URLSession(configuration: config, delegate: self, delegateQueue: nil)
    }

    /// Connect to the Hub, sending our X25519 public key for key exchange.
    func connect(localPublicKey: String) {
        // Create WebSocket task
        var request = URLRequest(url: url)
        request.setValue(localPublicKey, forHTTPHeaderField: "X-Mesh-PublicKey")

        webSocketTask = session.webSocketTask(with: request)
        webSocketTask?.resume()

        // Start receiving messages
        receiveMessage()
    }

    func disconnect() {
        webSocketTask?.cancel(with: .goingAway, reason: nil)
        webSocketTask = nil
        isConnected = false
    }

    func send(data: Data) {
        guard isConnected else {
            #if DEBUG
            print("[MeshWebSocket] Cannot send - not connected to \(hubId)")
            #endif
            return
        }

        webSocketTask?.send(.data(data)) { error in
            if let error = error {
                #if DEBUG
                print("[MeshWebSocket] Send error to \(self.hubId): \(error)")
                #endif
            }
        }
    }

    private func receiveMessage() {
        webSocketTask?.receive { [weak self] result in
            guard let self = self else { return }

            switch result {
            case .success(let message):
                switch message {
                case .data(let data):
                    self.onMessage(data)

                case .string(let text):
                    // Check for handshake response (Hub sends its public key)
                    if text.hasPrefix("MESH_HANDSHAKE:") {
                        let hubPublicKey = String(text.dropFirst("MESH_HANDSHAKE:".count))
                        self.isConnected = true
                        self.onConnected(hubPublicKey)
                    } else if let data = text.data(using: .utf8) {
                        self.onMessage(data)
                    }

                @unknown default:
                    break
                }

                // Continue receiving
                self.receiveMessage()

            case .failure(let error):
                #if DEBUG
                print("[MeshWebSocket] Receive error from \(self.hubId): \(error)")
                #endif
                self.handleDisconnect()
            }
        }
    }

    private func handleDisconnect() {
        guard isConnected else { return }
        isConnected = false
        onDisconnected()
    }

    // MARK: - URLSessionWebSocketDelegate

    nonisolated func urlSession(
        _ session: URLSession,
        webSocketTask: URLSessionWebSocketTask,
        didOpenWithProtocol protocol: String?
    ) {
        #if DEBUG
        print("[MeshWebSocket] Connected to Hub")
        #endif
    }

    nonisolated func urlSession(
        _ session: URLSession,
        webSocketTask: URLSessionWebSocketTask,
        didCloseWith closeCode: URLSessionWebSocketTask.CloseCode,
        reason: Data?
    ) {
        Task { @MainActor [weak self] in
            self?.handleDisconnect()
        }
    }
}

/*
 * Mirror
 *
 * The mesh command router provides a cryptographically secure alternative
 * to legacy HTTP API calls. Commands are authenticated with Ed25519 signatures
 * and encrypted with XChaCha20-Poly1305.
 *
 * h(x) >= 0. Always.
 */
