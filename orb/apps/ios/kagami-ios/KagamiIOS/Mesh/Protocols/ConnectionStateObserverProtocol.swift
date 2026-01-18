/// Connection State Observer Protocol — Unified state management
///
/// Defines the platform-agnostic interface for observing transport state changes.
/// Integrates with the Rust SDK's ConnectionStateMachine and circuit breaker.
///
/// This protocol mirrors the Rust SDK's ConnectionStateObserver trait.
///
/// h(x) >= 0. Always.

import Foundation
import Combine

// MARK: - Transport State

/// Connection state enumeration matching Rust SDK.
public enum TransportState: String, Sendable, Equatable, CaseIterable {
    /// Not connected to any peer.
    case disconnected
    /// Attempting to establish connection.
    case connecting
    /// Connected and ready for communication.
    case connected
    /// Connection lost, attempting to reconnect.
    case reconnecting
    /// Circuit breaker is open due to repeated failures.
    case circuitOpen
    /// Half-open state, testing recovery.
    case halfOpen

    /// Whether connection is usable.
    public var isConnected: Bool {
        self == .connected
    }

    /// Whether attempting to connect.
    public var isConnecting: Bool {
        self == .connecting || self == .reconnecting || self == .halfOpen
    }

    /// Whether connection is blocked.
    public var isBlocked: Bool {
        self == .circuitOpen
    }
}

// MARK: - Retry Strategy

/// Retry strategy returned from the retry service.
public struct RetryStrategy: Sendable {
    /// Whether a retry should be attempted.
    public let shouldRetry: Bool
    /// Delay before retry in milliseconds.
    public let delayMs: UInt64
    /// Current retry attempt number.
    public let attempt: UInt32
    /// Maximum attempts (0 = unlimited).
    public let maxAttempts: UInt32
    /// Reason for the retry decision.
    public let reason: String

    /// Create a no-retry strategy.
    public static func noRetry(reason: String) -> RetryStrategy {
        RetryStrategy(
            shouldRetry: false,
            delayMs: 0,
            attempt: 0,
            maxAttempts: 0,
            reason: reason
        )
    }

    /// Create a retry strategy.
    public static func retry(delayMs: UInt64, attempt: UInt32, maxAttempts: UInt32) -> RetryStrategy {
        RetryStrategy(
            shouldRetry: true,
            delayMs: delayMs,
            attempt: attempt,
            maxAttempts: maxAttempts,
            reason: "Retry attempt \(attempt) after \(delayMs)ms"
        )
    }

    /// Delay as TimeInterval.
    public var delay: TimeInterval {
        TimeInterval(delayMs) / 1000.0
    }
}

// MARK: - Command Result

/// Command execution result for retry decisions.
public enum CommandResult: Sendable {
    /// Command succeeded.
    case success
    /// Command failed with a retryable error.
    case retryableError(reason: String)
    /// Command failed with a non-retryable error.
    case permanentError(reason: String)
    /// Command timed out.
    case timeout
    /// Circuit breaker rejected the command.
    case circuitOpen

    /// Whether this result should trigger a retry.
    public var shouldRetry: Bool {
        switch self {
        case .retryableError, .timeout:
            return true
        default:
            return false
        }
    }

    /// Whether this result indicates success.
    public var isSuccess: Bool {
        if case .success = self { return true }
        return false
    }
}

// MARK: - Connection State Observer Protocol

/// Protocol for receiving transport state changes.
///
/// Platforms implement this protocol to receive state updates
/// from the connection state machine and retry service.
public protocol ConnectionStateObserverProtocol: AnyObject, Sendable {
    /// Called when transport state changes.
    func connectionObserver(didChangeState oldState: TransportState, newState: TransportState)

    /// Called when a retry is scheduled.
    func connectionObserver(didScheduleRetry strategy: RetryStrategy)

    /// Called when connection is established.
    func connectionObserver(didConnect peerId: String)

    /// Called when disconnected.
    func connectionObserver(didDisconnect reason: String)

    /// Called when circuit breaker opens.
    func connectionObserver(circuitBreakerOpened failureCount: UInt32)

    /// Called when circuit breaker begins recovery.
    func connectionObserverCircuitBreakerRecovery()
}

// MARK: - Default Implementations

extension ConnectionStateObserverProtocol {
    public func connectionObserver(didChangeState oldState: TransportState, newState: TransportState) {}
    public func connectionObserver(didScheduleRetry strategy: RetryStrategy) {}
    public func connectionObserver(didConnect peerId: String) {}
    public func connectionObserver(didDisconnect reason: String) {}
    public func connectionObserver(circuitBreakerOpened failureCount: UInt32) {}
    public func connectionObserverCircuitBreakerRecovery() {}
}

// MARK: - Transport Configuration

/// Configuration for transport behavior.
public struct TransportConfiguration: Sendable {
    /// Initial retry delay in milliseconds.
    public let initialRetryMs: UInt64
    /// Maximum retry delay in milliseconds.
    public let maxRetryMs: UInt64
    /// Retry delay multiplier for exponential backoff.
    public let retryMultiplier: Double
    /// Number of failures before opening circuit breaker.
    public let failureThreshold: UInt32
    /// Circuit breaker recovery timeout in milliseconds.
    public let circuitBreakerTimeoutMs: UInt64
    /// Ping interval in milliseconds.
    public let pingIntervalMs: UInt64
    /// Ping timeout in milliseconds.
    public let pingTimeoutMs: UInt64
    /// Maximum number of retry attempts (0 = unlimited).
    public let maxRetryAttempts: UInt32

    /// Default configuration.
    public static let `default` = TransportConfiguration(
        initialRetryMs: 500,
        maxRetryMs: 30_000,
        retryMultiplier: 2.0,
        failureThreshold: 5,
        circuitBreakerTimeoutMs: 30_000,
        pingIntervalMs: 30_000,
        pingTimeoutMs: 10_000,
        maxRetryAttempts: 0
    )

    /// Configuration for local network (more aggressive).
    public static let localNetwork = TransportConfiguration(
        initialRetryMs: 200,
        maxRetryMs: 5_000,
        retryMultiplier: 1.5,
        failureThreshold: 3,
        circuitBreakerTimeoutMs: 10_000,
        pingIntervalMs: 15_000,
        pingTimeoutMs: 5_000,
        maxRetryAttempts: 10
    )

    /// Configuration for cloud connections (more patient).
    public static let cloud = TransportConfiguration(
        initialRetryMs: 1_000,
        maxRetryMs: 60_000,
        retryMultiplier: 2.0,
        failureThreshold: 5,
        circuitBreakerTimeoutMs: 60_000,
        pingIntervalMs: 30_000,
        pingTimeoutMs: 10_000,
        maxRetryAttempts: 0
    )
}

// MARK: - Connection State Manager

/// Manages connection state and notifies observers.
///
/// Wraps the Rust SDK's MeshConnection and adds Swift-native conveniences.
public final class ConnectionStateManager: @unchecked Sendable {
    /// Current transport state.
    @Published public private(set) var state: TransportState = .disconnected

    /// Current failure count.
    @Published public private(set) var failureCount: UInt32 = 0

    /// Whether currently connected.
    public var isConnected: Bool { state.isConnected }

    /// Configuration.
    public let config: TransportConfiguration

    /// Observers.
    private var observers: [WeakObserver] = []
    private let observersLock = NSLock()

    /// The underlying Rust connection state machine.
    private var meshConnection: MeshConnection?

    /// Publisher for state changes.
    public var statePublisher: AnyPublisher<TransportState, Never> {
        $state.eraseToAnyPublisher()
    }

    public init(config: TransportConfiguration = .default) {
        self.config = config
        self.meshConnection = MeshConnection.withFailureThreshold(threshold: config.failureThreshold)
    }

    // MARK: - State Transitions

    /// Signal a connection attempt.
    public func beginConnecting() {
        let oldState = state
        state = .connecting

        if let connection = meshConnection {
            _ = try? connection.onConnect()
        }

        notifyStateChange(from: oldState, to: .connecting)
    }

    /// Signal a successful connection.
    public func didConnect(peerId: String) {
        let oldState = state
        state = .connected
        failureCount = 0

        if let connection = meshConnection {
            _ = try? connection.onConnected()
        }

        notifyStateChange(from: oldState, to: .connected)
        notifyConnect(peerId: peerId)
    }

    /// Signal a connection failure.
    public func didFail(reason: String) -> RetryStrategy {
        let oldState = state
        failureCount += 1

        if let connection = meshConnection {
            _ = try? connection.onFailure(reason: reason)

            // Check if circuit breaker should open
            if connection.failureCount() >= config.failureThreshold {
                state = .circuitOpen
                notifyStateChange(from: oldState, to: .circuitOpen)
                notifyCircuitBreakerOpened()
                return .noRetry(reason: "Circuit breaker opened")
            }
        }

        state = .reconnecting
        notifyStateChange(from: oldState, to: .reconnecting)

        // Calculate retry strategy
        let strategy = calculateRetryStrategy()
        notifyRetryScheduled(strategy: strategy)
        return strategy
    }

    /// Signal disconnection.
    public func didDisconnect(reason: String) {
        let oldState = state
        state = .disconnected

        if let connection = meshConnection {
            _ = try? connection.onDisconnect(reason: reason)
        }

        notifyStateChange(from: oldState, to: .disconnected)
        notifyDisconnect(reason: reason)
    }

    /// Attempt circuit breaker recovery.
    public func attemptRecovery() {
        guard state == .circuitOpen else { return }

        if let connection = meshConnection, connection.shouldAttemptRecovery() {
            let oldState = state
            state = .halfOpen
            notifyStateChange(from: oldState, to: .halfOpen)
            notifyCircuitBreakerRecovery()
        }
    }

    /// Reset the state machine.
    public func reset() {
        let oldState = state
        state = .disconnected
        failureCount = 0

        meshConnection?.reset()

        notifyStateChange(from: oldState, to: .disconnected)
    }

    // MARK: - Retry Calculation

    private func calculateRetryStrategy() -> RetryStrategy {
        let attempt = failureCount
        let delayMs = calculateBackoffMs(attempt: attempt)

        if config.maxRetryAttempts > 0 && attempt >= config.maxRetryAttempts {
            return .noRetry(reason: "Max retries exceeded")
        }

        return .retry(delayMs: delayMs, attempt: attempt, maxAttempts: config.maxRetryAttempts)
    }

    private func calculateBackoffMs(attempt: UInt32) -> UInt64 {
        let base = Double(config.initialRetryMs)
        let multiplier = config.retryMultiplier
        let delay = base * pow(multiplier, Double(attempt))
        return min(UInt64(delay), config.maxRetryMs)
    }

    /// Get current backoff from Rust connection.
    public var currentBackoffMs: UInt64 {
        meshConnection?.backoffMs() ?? 0
    }

    // MARK: - Observer Management

    /// Add an observer.
    public func addObserver(_ observer: ConnectionStateObserverProtocol) {
        observersLock.lock()
        defer { observersLock.unlock() }
        observers.append(WeakObserver(observer))
        observers.removeAll { $0.value == nil }
    }

    /// Remove an observer.
    public func removeObserver(_ observer: ConnectionStateObserverProtocol) {
        observersLock.lock()
        defer { observersLock.unlock() }
        observers.removeAll { $0.value === observer || $0.value == nil }
    }

    private func notifyStateChange(from oldState: TransportState, to newState: TransportState) {
        let current = getObservers()
        for observer in current {
            observer.connectionObserver(didChangeState: oldState, newState: newState)
        }
    }

    private func notifyRetryScheduled(strategy: RetryStrategy) {
        let current = getObservers()
        for observer in current {
            observer.connectionObserver(didScheduleRetry: strategy)
        }
    }

    private func notifyConnect(peerId: String) {
        let current = getObservers()
        for observer in current {
            observer.connectionObserver(didConnect: peerId)
        }
    }

    private func notifyDisconnect(reason: String) {
        let current = getObservers()
        for observer in current {
            observer.connectionObserver(didDisconnect: reason)
        }
    }

    private func notifyCircuitBreakerOpened() {
        let current = getObservers()
        for observer in current {
            observer.connectionObserver(circuitBreakerOpened: failureCount)
        }
    }

    private func notifyCircuitBreakerRecovery() {
        let current = getObservers()
        for observer in current {
            observer.connectionObserverCircuitBreakerRecovery()
        }
    }

    private func getObservers() -> [ConnectionStateObserverProtocol] {
        observersLock.lock()
        defer { observersLock.unlock() }
        observers.removeAll { $0.value == nil }
        return observers.compactMap { $0.value }
    }
}

// MARK: - Weak Observer Wrapper

private class WeakObserver {
    weak var value: ConnectionStateObserverProtocol?

    init(_ value: ConnectionStateObserverProtocol) {
        self.value = value
    }
}

/*
 * Kagami Connection State Observer
 * h(x) >= 0. Always.
 */
