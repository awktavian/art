//
// KagamiWebSocketService.swift — WebSocket Connection Management
//
// Colony: Nexus (e4) — Integration
//
// Features:
//   - WebSocket connection to Kagami backend
//   - Automatic reconnection with exponential backoff
//   - Real-time context and home status updates
//   - Thread-safe message handling
//
// Architecture:
//   KagamiWebSocketService -> URLSessionWebSocketTask -> Kagami Backend WS
//
// h(x) >= 0. Always.
//

import Foundation
import Combine

/// WebSocket service for real-time communication with Kagami backend
@MainActor
public final class KagamiWebSocketService: ObservableObject {

    // MARK: - Singleton

    public static let shared = KagamiWebSocketService()

    // MARK: - Published State

    @Published public private(set) var isConnected = false
    @Published public var safetyScore: Double?
    @Published public var movieMode: Bool = false

    /// Delegate for WebSocket events
    public weak var delegate: KagamiWebSocketDelegate?

    // MARK: - Internal State

    /// WebSocket task (package-internal for binary protocol extension)
    var webSocket: URLSessionWebSocketTask?
    private var webSocketRetryCount = 0
    private let maxRetryCount = 5
    private var clientId: String = ""
    private var baseURL: String = ""

    /// URLSession for WebSocket connections
    private let webSocketSession: URLSession

    // MARK: - Debouncing State

    /// Debounce interval in seconds (50ms)
    private let debounceInterval: TimeInterval = 0.05

    /// Pending messages to batch process
    private var pendingMessages: [[String: Any]] = []

    /// Debounce work item
    private var debounceWorkItem: DispatchWorkItem?

    // MARK: - Init

    public init() {
        let wsConfig = URLSessionConfiguration.default
        wsConfig.timeoutIntervalForRequest = 10
        self.webSocketSession = URLSession(configuration: wsConfig)
    }

    // MARK: - Configuration

    /// Configure the WebSocket service with connection details
    public func configure(baseURL: String, clientId: String) {
        self.baseURL = baseURL
        self.clientId = clientId
    }

    // MARK: - Connection Management

    /// Connect to WebSocket endpoint
    public func connect() {
        guard !clientId.isEmpty, !baseURL.isEmpty else {
            #if DEBUG
            print("[WebSocket] Cannot connect: clientId or baseURL not configured")
            #endif
            return
        }

        // Security: Convert HTTP(S) to WS(S) - always prefer secure WebSocket
        let wsURL = baseURL.replacingOccurrences(of: "https://", with: "wss://")
                          .replacingOccurrences(of: "http://", with: "wss://")

        guard let url = URL(string: "\(wsURL)/ws/client/\(clientId)") else {
            #if DEBUG
            print("[WebSocket] Invalid URL")
            #endif
            return
        }

        webSocket = webSocketSession.webSocketTask(with: url)
        webSocket?.resume()
        isConnected = true
        webSocketRetryCount = 0
        receiveMessage()

        #if DEBUG
        print("[WebSocket] Connected to \(url)")
        #endif
    }

    /// Disconnect from WebSocket
    public func disconnect() {
        webSocket?.cancel(with: .normalClosure, reason: nil)
        webSocket = nil
        isConnected = false
        webSocketRetryCount = 0

        #if DEBUG
        print("[WebSocket] Disconnected")
        #endif
    }

    /// Reconnect to WebSocket (called automatically on disconnect)
    private func reconnect() {
        guard webSocketRetryCount < maxRetryCount else {
            #if DEBUG
            print("[WebSocket] Max retry attempts reached")
            #endif
            return
        }

        let delay = pow(2.0, Double(webSocketRetryCount))
        webSocketRetryCount += 1

        #if DEBUG
        print("[WebSocket] Reconnecting in \(delay)s (attempt \(webSocketRetryCount))")
        #endif

        DispatchQueue.main.asyncAfter(deadline: .now() + delay) { [weak self] in
            self?.connect()
        }
    }

    // MARK: - Message Handling

    private func receiveMessage() {
        webSocket?.receive { [weak self] result in
            Task { @MainActor in
                switch result {
                case .success(let message):
                    self?.handleMessage(message)
                    self?.receiveMessage() // Continue listening
                case .failure(let error):
                    #if DEBUG
                    print("[WebSocket] Receive error: \(error)")
                    #endif
                    self?.handleDisconnect()
                }
            }
        }
    }

    private func handleMessage(_ message: URLSessionWebSocketTask.Message) {
        switch message {
        case .string(let text):
            if let data = text.data(using: .utf8),
               let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                enqueueMessage(json)
            }
        case .data(let data):
            if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                enqueueMessage(json)
            }
        @unknown default:
            break
        }
    }

    /// Enqueue a message for debounced batch processing
    private func enqueueMessage(_ json: [String: Any]) {
        pendingMessages.append(json)

        // Cancel existing debounce work item
        debounceWorkItem?.cancel()

        // Create new debounce work item
        let workItem = DispatchWorkItem { [weak self] in
            Task { @MainActor in
                self?.processBatchedMessages()
            }
        }
        debounceWorkItem = workItem

        // Schedule after debounce interval (50ms)
        DispatchQueue.main.asyncAfter(deadline: .now() + debounceInterval, execute: workItem)
    }

    /// Process all batched messages at once to prevent jank
    private func processBatchedMessages() {
        // Copy and clear pending messages
        let messages = pendingMessages
        pendingMessages = []

        // Batch state updates to minimize UI refreshes
        var latestSafetyScore: Double?
        var latestMovieMode: Bool?
        var deviceUpdates: [[String: Any]] = []
        var notifications: [(String, [String: Any])] = []

        // Process all messages
        for json in messages {
            guard let type = json["type"] as? String else { continue }
            let data = json["data"] as? [String: Any] ?? [:]

            switch type {
            case "context_update":
                if let safety = data["safety_score"] as? Double {
                    latestSafetyScore = safety
                }

            case "home_update":
                if let movie = data["movie_mode"] as? Bool {
                    latestMovieMode = movie
                }

            case "device_update":
                deviceUpdates.append(data)

            case "notification":
                if let message = data["message"] as? String {
                    notifications.append((message, data))
                }

            default:
                #if DEBUG
                print("[WebSocket] Unknown message type: \(type)")
                #endif
            }
        }

        // Apply batched state updates (single UI update)
        if let safety = latestSafetyScore {
            safetyScore = safety
            delegate?.webSocketDidReceiveSafetyScore(safety)
        }

        if let movie = latestMovieMode {
            movieMode = movie
            delegate?.webSocketDidReceiveHomeUpdate(["movie_mode": movie])
        }

        // Process device updates
        for update in deviceUpdates {
            delegate?.webSocketDidReceiveDeviceUpdate(update)
        }

        // Process notifications
        for (message, data) in notifications {
            delegate?.webSocketDidReceiveNotification(message, data: data)
        }

        #if DEBUG
        if messages.count > 1 {
            print("[WebSocket] Batched \(messages.count) messages in single update")
        }
        #endif
    }

    private func handleJSON(_ json: [String: Any]) {
        guard let type = json["type"] as? String else { return }
        let data = json["data"] as? [String: Any] ?? [:]

        switch type {
        case "context_update":
            if let safety = data["safety_score"] as? Double {
                safetyScore = safety
                delegate?.webSocketDidReceiveSafetyScore(safety)
            }

        case "home_update":
            if let movie = data["movie_mode"] as? Bool {
                movieMode = movie
                delegate?.webSocketDidReceiveHomeUpdate(["movie_mode": movie])
            }

        case "device_update":
            delegate?.webSocketDidReceiveDeviceUpdate(data)

        case "notification":
            if let message = data["message"] as? String {
                delegate?.webSocketDidReceiveNotification(message, data: data)
            }

        default:
            #if DEBUG
            print("[WebSocket] Unknown message type: \(type)")
            #endif
        }
    }

    private func handleDisconnect() {
        webSocket = nil
        isConnected = false
        delegate?.webSocketDidDisconnect()
        reconnect()
    }

    // MARK: - Send Messages

    /// Send a JSON message through the WebSocket
    public func send(_ message: [String: Any]) async throws {
        guard let webSocket = webSocket else {
            throw WebSocketError.notConnected
        }

        let data = try JSONSerialization.data(withJSONObject: message)
        let string = String(data: data, encoding: .utf8) ?? "{}"

        try await webSocket.send(.string(string))
    }

    /// Send a ping to keep connection alive
    public func ping() async throws {
        guard let webSocket = webSocket else {
            throw WebSocketError.notConnected
        }

        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            webSocket.sendPing { error in
                if let error = error {
                    continuation.resume(throwing: error)
                } else {
                    continuation.resume()
                }
            }
        }
    }
}

// MARK: - WebSocket Error

public enum WebSocketError: LocalizedError {
    case notConnected
    case connectionFailed(String)
    case sendFailed(String)

    public var errorDescription: String? {
        switch self {
        case .notConnected:
            return "WebSocket not connected"
        case .connectionFailed(let reason):
            return "Connection failed: \(reason)"
        case .sendFailed(let reason):
            return "Send failed: \(reason)"
        }
    }
}

// MARK: - WebSocket Delegate Protocol

/// Protocol for receiving WebSocket events
@MainActor
public protocol KagamiWebSocketDelegate: AnyObject {
    func webSocketDidConnect()
    func webSocketDidDisconnect()
    func webSocketDidReceiveSafetyScore(_ score: Double)
    func webSocketDidReceiveHomeUpdate(_ data: [String: Any])
    func webSocketDidReceiveDeviceUpdate(_ data: [String: Any])
    func webSocketDidReceiveNotification(_ message: String, data: [String: Any])
}

// Default implementations
public extension KagamiWebSocketDelegate {
    func webSocketDidConnect() {}
    func webSocketDidDisconnect() {}
    func webSocketDidReceiveSafetyScore(_ score: Double) {}
    func webSocketDidReceiveHomeUpdate(_ data: [String: Any]) {}
    func webSocketDidReceiveDeviceUpdate(_ data: [String: Any]) {}
    func webSocketDidReceiveNotification(_ message: String, data: [String: Any]) {}
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
