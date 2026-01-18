//
// CircuitBreakerTests.swift — Circuit Breaker Unit Tests
//
// h(x) >= 0. Always.
//

import XCTest
@testable import KagamiCore

@MainActor
final class CircuitBreakerTests: XCTestCase {

    var circuitBreaker: CircuitBreaker!

    override func setUp() {
        super.setUp()
        circuitBreaker = CircuitBreaker()
    }

    override func tearDown() {
        circuitBreaker = nil
        super.tearDown()
    }

    // MARK: - Initial State

    func testInitialState() {
        XCTAssertEqual(circuitBreaker.state, .closed)
        XCTAssertEqual(circuitBreaker.consecutiveFailures, 0)
        XCTAssertNil(circuitBreaker.lastFailureTime)
        XCTAssertTrue(circuitBreaker.allowRequest())
        XCTAssertFalse(circuitBreaker.isOpen)
    }

    // MARK: - Success Recording

    func testRecordSuccess() {
        circuitBreaker.recordSuccess()
        XCTAssertEqual(circuitBreaker.state, .closed)
        XCTAssertEqual(circuitBreaker.consecutiveFailures, 0)
    }

    func testSuccessAfterFailures() {
        circuitBreaker.recordFailure()
        circuitBreaker.recordFailure()
        circuitBreaker.recordSuccess()
        XCTAssertEqual(circuitBreaker.consecutiveFailures, 0)
        XCTAssertEqual(circuitBreaker.state, .closed)
    }

    // MARK: - Failure Recording

    func testRecordFailure() {
        circuitBreaker.recordFailure()
        XCTAssertEqual(circuitBreaker.consecutiveFailures, 1)
        XCTAssertEqual(circuitBreaker.state, .closed)
        XCTAssertNotNil(circuitBreaker.lastFailureTime)
    }

    func testCircuitOpensAfterThreshold() {
        for _ in 0..<CircuitBreaker.failureThreshold {
            circuitBreaker.recordFailure()
        }
        XCTAssertEqual(circuitBreaker.state, .open)
        XCTAssertTrue(circuitBreaker.isOpen)
        XCTAssertFalse(circuitBreaker.allowRequest())
    }

    // MARK: - Reset

    func testReset() {
        // Trip the circuit
        for _ in 0..<CircuitBreaker.failureThreshold {
            circuitBreaker.recordFailure()
        }
        XCTAssertEqual(circuitBreaker.state, .open)

        // Reset
        circuitBreaker.reset()
        XCTAssertEqual(circuitBreaker.state, .closed)
        XCTAssertEqual(circuitBreaker.consecutiveFailures, 0)
        XCTAssertNil(circuitBreaker.lastFailureTime)
    }

    // MARK: - Time Until Retry

    func testTimeUntilRetry() {
        // Closed state has no retry time
        XCTAssertNil(circuitBreaker.timeUntilRetry)

        // Open circuit
        for _ in 0..<CircuitBreaker.failureThreshold {
            circuitBreaker.recordFailure()
        }

        // Should have time remaining
        let time = circuitBreaker.timeUntilRetry
        XCTAssertNotNil(time)
        XCTAssertGreaterThan(time!, 0)
        XCTAssertLessThanOrEqual(time!, CircuitBreaker.resetTimeout)
    }

    // MARK: - Error

    func testCircuitBreakerError() {
        let error = CircuitBreakerError.circuitOpen
        XCTAssertNotNil(error.errorDescription)
        XCTAssertNotNil(error.recoverySuggestion)
    }
}
