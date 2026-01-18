//
// CircuitBreaker.swift — Graceful Network Degradation
//
// Colony: Flow (e3) — Resilience
//
// Pattern: Closed → (failures ≥ threshold) → Open → (timeout) → HalfOpen → (success) → Closed
//
// Shared component for all Kagami Apple platforms.
//
// h(x) >= 0. Always.
//

import Foundation
import Combine

/// Circuit breaker states
public enum CircuitBreakerState: String, CaseIterable, Sendable {
    /// Normal operation — requests flow through
    case closed
    /// Circuit tripped — requests rejected immediately
    case open
    /// Testing recovery — one request allowed to test
    case halfOpen
}

/// Circuit breaker for graceful network degradation.
///
/// Prevents cascade failures by:
/// 1. Tracking consecutive failures
/// 2. Opening circuit when threshold exceeded
/// 3. Allowing recovery attempts after timeout
///
/// Usage:
/// ```swift
/// let circuitBreaker = CircuitBreaker.shared
///
/// func makeRequest() async throws -> T {
///     guard circuitBreaker.allowRequest() else {
///         throw CircuitBreakerError.circuitOpen
///     }
///
///     do {
///         let result = try await actualRequest()
///         circuitBreaker.recordSuccess()
///         return result
///     } catch {
///         circuitBreaker.recordFailure()
///         throw error
///     }
/// }
/// ```
@MainActor
public final class CircuitBreaker: ObservableObject {

    // MARK: - Singleton

    public static let shared = CircuitBreaker()

    // MARK: - Configuration

    /// Number of consecutive failures before opening circuit
    public static let failureThreshold = 3

    /// Time to wait before attempting recovery (seconds)
    public static let resetTimeout: TimeInterval = 30.0

    // MARK: - Published State

    @Published public private(set) var state: CircuitBreakerState = .closed
    @Published public private(set) var consecutiveFailures: Int = 0
    @Published public private(set) var lastFailureTime: Date?

    // MARK: - Init

    public init() {}

    // MARK: - Public Interface

    /// Check if a request should be allowed.
    ///
    /// - Returns: true if request can proceed, false if circuit is open
    public func allowRequest() -> Bool {
        switch state {
        case .closed:
            return true

        case .open:
            // Check if reset timeout has elapsed
            if let lastFailure = lastFailureTime,
               Date().timeIntervalSince(lastFailure) > Self.resetTimeout {
                state = .halfOpen
                #if DEBUG
                print("[CircuitBreaker] State: HALF_OPEN (testing recovery)")
                #endif
                return true
            }
            return false

        case .halfOpen:
            return true
        }
    }

    /// Record a successful request. Resets the circuit breaker.
    public func recordSuccess() {
        consecutiveFailures = 0
        if state != .closed {
            state = .closed
            #if DEBUG
            print("[CircuitBreaker] State: CLOSED (recovered)")
            #endif
        }
    }

    /// Record a failed request. May trip the circuit breaker.
    public func recordFailure() {
        consecutiveFailures += 1
        lastFailureTime = Date()

        switch state {
        case .closed:
            if consecutiveFailures >= Self.failureThreshold {
                state = .open
                #if DEBUG
                print("[CircuitBreaker] State: OPEN (threshold reached after \(consecutiveFailures) failures)")
                #endif
            }

        case .halfOpen:
            state = .open
            #if DEBUG
            print("[CircuitBreaker] State: OPEN (half-open test failed)")
            #endif

        case .open:
            break
        }
    }

    /// Reset the circuit breaker to closed state.
    /// Use carefully — this bypasses normal recovery flow.
    public func reset() {
        consecutiveFailures = 0
        lastFailureTime = nil
        state = .closed
        #if DEBUG
        print("[CircuitBreaker] RESET to CLOSED")
        #endif
    }

    /// Check if circuit is currently open.
    public var isOpen: Bool {
        state == .open
    }

    /// Time remaining until circuit can attempt recovery (if open).
    public var timeUntilRetry: TimeInterval? {
        guard state == .open, let lastFailure = lastFailureTime else { return nil }
        let elapsed = Date().timeIntervalSince(lastFailure)
        let remaining = Self.resetTimeout - elapsed
        return remaining > 0 ? remaining : 0
    }
}

/// Errors related to circuit breaker
public enum CircuitBreakerError: LocalizedError, Sendable {
    case circuitOpen

    public var errorDescription: String? {
        switch self {
        case .circuitOpen:
            return "Service temporarily unavailable. Please try again shortly."
        }
    }

    public var recoverySuggestion: String? {
        switch self {
        case .circuitOpen:
            return "The app is protecting against network issues. It will automatically retry soon."
        }
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 *
 * The circuit breaker protects against cascade failures.
 * When the backend is down, we fail fast rather than
 * accumulating timeouts.
 */
