package com.kagami.android.mesh.protocols

import kotlinx.coroutines.flow.*
import kotlin.math.min
import kotlin.math.pow

/**
 * Connection State Observer — Unified state management
 *
 * Defines the platform-agnostic interface for observing transport state changes.
 * Integrates with the Rust SDK's ConnectionStateMachine and circuit breaker.
 *
 * 鏡 h(x) >= 0. Always.
 */

// ═══════════════════════════════════════════════════════════════════════════
// Transport State
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Connection state enumeration matching Rust SDK.
 */
enum class TransportState {
    /** Not connected to any peer. */
    DISCONNECTED,
    /** Attempting to establish connection. */
    CONNECTING,
    /** Connected and ready for communication. */
    CONNECTED,
    /** Connection lost, attempting to reconnect. */
    RECONNECTING,
    /** Circuit breaker is open due to repeated failures. */
    CIRCUIT_OPEN,
    /** Half-open state, testing recovery. */
    HALF_OPEN;

    /** Whether connection is usable. */
    val isConnected: Boolean get() = this == CONNECTED

    /** Whether attempting to connect. */
    val isConnecting: Boolean get() = this == CONNECTING || this == RECONNECTING || this == HALF_OPEN

    /** Whether connection is blocked. */
    val isBlocked: Boolean get() = this == CIRCUIT_OPEN
}

// ═══════════════════════════════════════════════════════════════════════════
// Retry Strategy
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Retry strategy returned from the retry service.
 */
data class RetryStrategy(
    /** Whether a retry should be attempted. */
    val shouldRetry: Boolean,
    /** Delay before retry in milliseconds. */
    val delayMs: Long,
    /** Current retry attempt number. */
    val attempt: Int,
    /** Maximum attempts (0 = unlimited). */
    val maxAttempts: Int,
    /** Reason for the retry decision. */
    val reason: String
) {
    companion object {
        /** Create a no-retry strategy. */
        fun noRetry(reason: String) = RetryStrategy(
            shouldRetry = false,
            delayMs = 0,
            attempt = 0,
            maxAttempts = 0,
            reason = reason
        )

        /** Create a retry strategy. */
        fun retry(delayMs: Long, attempt: Int, maxAttempts: Int) = RetryStrategy(
            shouldRetry = true,
            delayMs = delayMs,
            attempt = attempt,
            maxAttempts = maxAttempts,
            reason = "Retry attempt $attempt after ${delayMs}ms"
        )
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// Command Result
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Command execution result for retry decisions.
 */
sealed class CommandResult {
    /** Command succeeded. */
    object Success : CommandResult()
    /** Command failed with a retryable error. */
    data class RetryableError(val reason: String) : CommandResult()
    /** Command failed with a non-retryable error. */
    data class PermanentError(val reason: String) : CommandResult()
    /** Command timed out. */
    object Timeout : CommandResult()
    /** Circuit breaker rejected the command. */
    object CircuitOpen : CommandResult()

    /** Whether this result should trigger a retry. */
    val shouldRetry: Boolean get() = this is RetryableError || this is Timeout

    /** Whether this result indicates success. */
    val isSuccess: Boolean get() = this is Success
}

// ═══════════════════════════════════════════════════════════════════════════
// Transport Configuration
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Configuration for transport behavior.
 */
data class TransportConfiguration(
    /** Initial retry delay in milliseconds. */
    val initialRetryMs: Long = 500,
    /** Maximum retry delay in milliseconds. */
    val maxRetryMs: Long = 30_000,
    /** Retry delay multiplier for exponential backoff. */
    val retryMultiplier: Double = 2.0,
    /** Number of failures before opening circuit breaker. */
    val failureThreshold: Int = 5,
    /** Circuit breaker recovery timeout in milliseconds. */
    val circuitBreakerTimeoutMs: Long = 30_000,
    /** Ping interval in milliseconds. */
    val pingIntervalMs: Long = 30_000,
    /** Ping timeout in milliseconds. */
    val pingTimeoutMs: Long = 10_000,
    /** Maximum number of retry attempts (0 = unlimited). */
    val maxRetryAttempts: Int = 0
) {
    companion object {
        /** Default configuration. */
        val DEFAULT = TransportConfiguration()

        /** Configuration for local network (more aggressive). */
        val LOCAL_NETWORK = TransportConfiguration(
            initialRetryMs = 200,
            maxRetryMs = 5_000,
            retryMultiplier = 1.5,
            failureThreshold = 3,
            circuitBreakerTimeoutMs = 10_000,
            pingIntervalMs = 15_000,
            pingTimeoutMs = 5_000,
            maxRetryAttempts = 10
        )

        /** Configuration for cloud connections (more patient). */
        val CLOUD = TransportConfiguration(
            initialRetryMs = 1_000,
            maxRetryMs = 60_000,
            retryMultiplier = 2.0,
            failureThreshold = 5,
            circuitBreakerTimeoutMs = 60_000,
            pingIntervalMs = 30_000,
            pingTimeoutMs = 10_000,
            maxRetryAttempts = 0
        )
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// Connection State Observer Interface
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Interface for receiving transport state changes.
 */
interface ConnectionStateObserver {
    /** Called when transport state changes. */
    fun onStateChanged(oldState: TransportState, newState: TransportState)

    /** Called when a retry is scheduled. */
    fun onRetryScheduled(strategy: RetryStrategy)

    /** Called when connection is established. */
    fun onConnected(peerId: String)

    /** Called when disconnected. */
    fun onDisconnected(reason: String)

    /** Called when circuit breaker opens. */
    fun onCircuitBreakerOpened(failureCount: Int)

    /** Called when circuit breaker begins recovery. */
    fun onCircuitBreakerRecovery()
}

// ═══════════════════════════════════════════════════════════════════════════
// Connection State Manager
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Manages connection state and notifies observers.
 */
class ConnectionStateManager(
    val config: TransportConfiguration = TransportConfiguration.DEFAULT
) {
    private val _stateFlow = MutableStateFlow(TransportState.DISCONNECTED)
    val stateFlow: StateFlow<TransportState> = _stateFlow.asStateFlow()

    private val _failureCountFlow = MutableStateFlow(0)
    val failureCountFlow: StateFlow<Int> = _failureCountFlow.asStateFlow()

    val state: TransportState get() = _stateFlow.value
    val failureCount: Int get() = _failureCountFlow.value
    val isConnected: Boolean get() = state.isConnected

    private val observers = mutableListOf<ConnectionStateObserver>()
    private val observersLock = Any()

    private var circuitBreakerOpenTime: Long? = null

    // ═══════════════════════════════════════════════════════════════════════
    // State Transitions
    // ═══════════════════════════════════════════════════════════════════════

    /** Signal a connection attempt. */
    fun beginConnecting() {
        val oldState = state
        _stateFlow.value = TransportState.CONNECTING
        notifyStateChange(oldState, TransportState.CONNECTING)
    }

    /** Signal a successful connection. */
    fun didConnect(peerId: String) {
        val oldState = state
        _stateFlow.value = TransportState.CONNECTED
        _failureCountFlow.value = 0
        circuitBreakerOpenTime = null

        notifyStateChange(oldState, TransportState.CONNECTED)
        notifyConnect(peerId)
    }

    /** Signal a connection failure. */
    fun didFail(reason: String): RetryStrategy {
        val oldState = state
        _failureCountFlow.value++

        // Check if circuit breaker should open
        if (failureCount >= config.failureThreshold) {
            _stateFlow.value = TransportState.CIRCUIT_OPEN
            circuitBreakerOpenTime = System.currentTimeMillis()
            notifyStateChange(oldState, TransportState.CIRCUIT_OPEN)
            notifyCircuitBreakerOpened()
            return RetryStrategy.noRetry("Circuit breaker opened")
        }

        _stateFlow.value = TransportState.RECONNECTING
        notifyStateChange(oldState, TransportState.RECONNECTING)

        // Calculate retry strategy
        val strategy = calculateRetryStrategy()
        notifyRetryScheduled(strategy)
        return strategy
    }

    /** Signal disconnection. */
    fun didDisconnect(reason: String) {
        val oldState = state
        _stateFlow.value = TransportState.DISCONNECTED

        notifyStateChange(oldState, TransportState.DISCONNECTED)
        notifyDisconnect(reason)
    }

    /** Attempt circuit breaker recovery. */
    fun attemptRecovery(): Boolean {
        if (state != TransportState.CIRCUIT_OPEN) return false

        val openTime = circuitBreakerOpenTime ?: return false
        val elapsed = System.currentTimeMillis() - openTime

        if (elapsed >= config.circuitBreakerTimeoutMs) {
            val oldState = state
            _stateFlow.value = TransportState.HALF_OPEN
            notifyStateChange(oldState, TransportState.HALF_OPEN)
            notifyCircuitBreakerRecovery()
            return true
        }

        return false
    }

    /** Reset the state machine. */
    fun reset() {
        val oldState = state
        _stateFlow.value = TransportState.DISCONNECTED
        _failureCountFlow.value = 0
        circuitBreakerOpenTime = null

        notifyStateChange(oldState, TransportState.DISCONNECTED)
    }

    // ═══════════════════════════════════════════════════════════════════════
    // Retry Calculation
    // ═══════════════════════════════════════════════════════════════════════

    private fun calculateRetryStrategy(): RetryStrategy {
        val attempt = failureCount
        val delayMs = calculateBackoffMs(attempt)

        if (config.maxRetryAttempts > 0 && attempt >= config.maxRetryAttempts) {
            return RetryStrategy.noRetry("Max retries exceeded")
        }

        return RetryStrategy.retry(delayMs, attempt, config.maxRetryAttempts)
    }

    private fun calculateBackoffMs(attempt: Int): Long {
        val base = config.initialRetryMs.toDouble()
        val multiplier = config.retryMultiplier
        val delay = base * multiplier.pow(attempt.toDouble())
        return min(delay.toLong(), config.maxRetryMs)
    }

    /** Get current backoff in milliseconds. */
    val currentBackoffMs: Long get() = calculateBackoffMs(failureCount)

    /** Get time until circuit breaker recovery (or null if not in circuit open state). */
    val timeUntilRecoveryMs: Long? get() {
        if (state != TransportState.CIRCUIT_OPEN) return null
        val openTime = circuitBreakerOpenTime ?: return null
        val elapsed = System.currentTimeMillis() - openTime
        val remaining = config.circuitBreakerTimeoutMs - elapsed
        return if (remaining > 0) remaining else 0
    }

    // ═══════════════════════════════════════════════════════════════════════
    // Observer Management
    // ═══════════════════════════════════════════════════════════════════════

    /** Add an observer. */
    fun addObserver(observer: ConnectionStateObserver) {
        synchronized(observersLock) {
            observers.add(observer)
        }
    }

    /** Remove an observer. */
    fun removeObserver(observer: ConnectionStateObserver) {
        synchronized(observersLock) {
            observers.remove(observer)
        }
    }

    private fun getObservers(): List<ConnectionStateObserver> {
        synchronized(observersLock) {
            return observers.toList()
        }
    }

    private fun notifyStateChange(oldState: TransportState, newState: TransportState) {
        getObservers().forEach { it.onStateChanged(oldState, newState) }
    }

    private fun notifyRetryScheduled(strategy: RetryStrategy) {
        getObservers().forEach { it.onRetryScheduled(strategy) }
    }

    private fun notifyConnect(peerId: String) {
        getObservers().forEach { it.onConnected(peerId) }
    }

    private fun notifyDisconnect(reason: String) {
        getObservers().forEach { it.onDisconnected(reason) }
    }

    private fun notifyCircuitBreakerOpened() {
        getObservers().forEach { it.onCircuitBreakerOpened(failureCount) }
    }

    private fun notifyCircuitBreakerRecovery() {
        getObservers().forEach { it.onCircuitBreakerRecovery() }
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// Fibonacci Backoff
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Fibonacci backoff calculator for voice streaming reconnection.
 *
 * Uses Fibonacci sequence for more natural backoff progression:
 * 1, 1, 2, 3, 5, 8, 13, 21, 34, 55 seconds
 */
class FibonacciBackoff(
    private val maxDelaySeconds: Long = 60
) {
    private var current: Long = 1
    private var next: Long = 1
    private var _attempt: Int = 0

    val attempt: Int get() = _attempt

    /** Get the next backoff delay in milliseconds. */
    fun nextDelayMs(): Long {
        val delay = min(current, maxDelaySeconds) * 1000
        val newNext = current + next
        current = next
        next = newNext
        _attempt++
        return delay
    }

    /** Get current delay without advancing. */
    val currentDelayMs: Long get() = min(current, maxDelaySeconds) * 1000

    /** Reset the backoff. */
    fun reset() {
        current = 1
        next = 1
        _attempt = 0
    }
}

/*
 * 鏡 Kagami Connection State Observer
 * h(x) >= 0. Always.
 */
