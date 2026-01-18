/**
 * Circuit Breaker Pattern — Graceful Degradation
 *
 * Colony: Flow (e3) — Resilience
 *
 * Pattern: Closed → (failures ≥ threshold) → Open → (timeout) → HalfOpen → (success) → Closed
 *
 * Ported from watchOS KagamiAPIService for consistency across platforms.
 *
 * h(x) ≥ 0. Always.
 */

package com.kagami.android.network

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicLong
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Circuit breaker states.
 */
enum class CircuitBreakerState {
    /** Normal operation — requests flow through */
    CLOSED,
    /** Circuit tripped — requests are rejected immediately */
    OPEN,
    /** Testing recovery — one request allowed through to test */
    HALF_OPEN
}

/**
 * Circuit breaker for graceful network degradation.
 *
 * Prevents cascade failures by:
 * 1. Tracking consecutive failures
 * 2. Opening circuit when threshold exceeded
 * 3. Allowing recovery attempts after timeout
 *
 * Usage:
 * ```kotlin
 * val circuitBreaker = CircuitBreaker()
 *
 * suspend fun makeRequest(): Result<T> {
 *     if (!circuitBreaker.allowRequest()) {
 *         return Result.failure(CircuitBreakerOpenException())
 *     }
 *
 *     return try {
 *         val result = actualRequest()
 *         circuitBreaker.recordSuccess()
 *         Result.success(result)
 *     } catch (e: Exception) {
 *         circuitBreaker.recordFailure()
 *         Result.failure(e)
 *     }
 * }
 * ```
 */
@Singleton
class CircuitBreaker @Inject constructor() {

    companion object {
        /** Number of consecutive failures before opening circuit */
        const val FAILURE_THRESHOLD = 3

        /** Time to wait before attempting recovery (ms) */
        const val RESET_TIMEOUT_MS = 30_000L

        private const val TAG = "CircuitBreaker"
    }

    // Thread-safe state
    private val _state = MutableStateFlow(CircuitBreakerState.CLOSED)
    val state: StateFlow<CircuitBreakerState> = _state

    private val consecutiveFailures = AtomicInteger(0)
    private val lastFailureTime = AtomicLong(0)
    private val mutex = Mutex()

    /**
     * Check if a request should be allowed.
     *
     * @return true if request can proceed, false if circuit is open
     */
    suspend fun allowRequest(): Boolean = mutex.withLock {
        when (_state.value) {
            CircuitBreakerState.CLOSED -> true

            CircuitBreakerState.OPEN -> {
                // Check if reset timeout has elapsed
                val elapsed = System.currentTimeMillis() - lastFailureTime.get()
                if (elapsed > RESET_TIMEOUT_MS) {
                    _state.value = CircuitBreakerState.HALF_OPEN
                    android.util.Log.i(TAG, "Circuit breaker: HALF_OPEN (testing recovery)")
                    true
                } else {
                    false
                }
            }

            CircuitBreakerState.HALF_OPEN -> true
        }
    }

    /**
     * Record a successful request. Resets the circuit breaker.
     */
    suspend fun recordSuccess() = mutex.withLock {
        consecutiveFailures.set(0)
        if (_state.value != CircuitBreakerState.CLOSED) {
            _state.value = CircuitBreakerState.CLOSED
            android.util.Log.i(TAG, "Circuit breaker: CLOSED (recovered)")
        }
    }

    /**
     * Record a failed request. May trip the circuit breaker.
     */
    suspend fun recordFailure() = mutex.withLock {
        val failures = consecutiveFailures.incrementAndGet()
        lastFailureTime.set(System.currentTimeMillis())

        when {
            failures >= FAILURE_THRESHOLD && _state.value == CircuitBreakerState.CLOSED -> {
                _state.value = CircuitBreakerState.OPEN
                android.util.Log.w(TAG, "Circuit breaker: OPEN (threshold reached after $failures failures)")
            }
            _state.value == CircuitBreakerState.HALF_OPEN -> {
                _state.value = CircuitBreakerState.OPEN
                android.util.Log.w(TAG, "Circuit breaker: OPEN (half-open test failed)")
            }
        }
    }

    /**
     * Reset the circuit breaker to closed state.
     * Use carefully — this bypasses normal recovery flow.
     */
    suspend fun reset() = mutex.withLock {
        consecutiveFailures.set(0)
        lastFailureTime.set(0)
        _state.value = CircuitBreakerState.CLOSED
        android.util.Log.i(TAG, "Circuit breaker: RESET to CLOSED")
    }

    /**
     * Get current failure count (for debugging/UI).
     */
    fun getFailureCount(): Int = consecutiveFailures.get()

    /**
     * Check if circuit is currently open.
     */
    fun isOpen(): Boolean = _state.value == CircuitBreakerState.OPEN
}

/**
 * Exception thrown when circuit breaker is open.
 */
class CircuitBreakerOpenException : Exception("Circuit breaker is open — service unavailable")

/*
 * Mirror
 * h(x) >= 0. Always.
 *
 * The circuit breaker protects against cascade failures.
 * When the backend is down, we fail fast rather than
 * accumulating timeouts.
 */
