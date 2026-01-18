//
// MeshServiceTests.swift
// KagamiMeshTests
//
// h(x) >= 0. Always.
//

import XCTest
@testable import KagamiMesh

final class MeshServiceTests: XCTestCase {

    // Note: These tests require the compiled Rust static library
    // to be linked. Without it, they will fail at runtime.

    func testMeshConnectionStateFromRustString() {
        XCTAssertEqual(MeshConnectionState.from("Disconnected"), .disconnected)
        XCTAssertEqual(MeshConnectionState.from("Connecting"), .connecting)
        XCTAssertEqual(MeshConnectionState.from("Connected"), .connected)
        XCTAssertEqual(MeshConnectionState.from("CircuitOpen"), .circuitOpen)
        XCTAssertEqual(MeshConnectionState.from("Unknown"), .disconnected)
    }

    func testVectorClockOrderingFromString() {
        XCTAssertEqual(VectorClockOrdering.from("before"), .before)
        XCTAssertEqual(VectorClockOrdering.from("after"), .after)
        XCTAssertEqual(VectorClockOrdering.from("concurrent"), .concurrent)
        XCTAssertEqual(VectorClockOrdering.from("equal"), .equal)
        XCTAssertEqual(VectorClockOrdering.from("unknown"), .concurrent)
    }

    func testAppleKeychainServiceSaveAndLoad() {
        let keychain = AppleKeychainService(service: "com.kagami.mesh.test")
        let key = "testKey"
        let value = "testValue"

        // Save
        XCTAssertTrue(keychain.save(key: key, value: value))

        // Load
        XCTAssertEqual(keychain.load(key: key), value)

        // Delete
        XCTAssertTrue(keychain.delete(key: key))

        // Verify deleted
        XCTAssertNil(keychain.load(key: key))
    }

    func testMeshServiceErrorDescriptions() {
        let errors: [MeshServiceError] = [
            .notInitialized,
            .identityLoadFailed("test"),
            .signatureFailed("test"),
            .encryptionFailed("test"),
            .crdtError("test")
        ]

        for error in errors {
            XCTAssertNotNil(error.errorDescription)
            XCTAssertFalse(error.errorDescription?.isEmpty ?? true)
        }
    }
}
