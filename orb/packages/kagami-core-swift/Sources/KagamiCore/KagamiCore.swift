//
// KagamiCore.swift — Shared Components for Kagami Apple Platforms
//
// This package provides common functionality shared across:
// - iOS (kagami-ios)
// - watchOS (kagami-watch)
// - visionOS (kagami-vision)
// - tvOS (kagami-tv)
// - macOS (kagami-desktop)
//
// Components:
// - CircuitBreaker: Graceful network degradation pattern
// - KeychainService: Secure credential storage
//
// Usage:
// ```swift
// import KagamiCore
//
// // Circuit breaker
// if CircuitBreaker.shared.allowRequest() {
//     // Make request
// }
//
// // Keychain
// KeychainService.shared.saveToken("jwt-token")
// ```
//
// h(x) >= 0. Always.
//

// Re-export public types
@_exported import Foundation

// Version info
public struct KagamiCoreInfo {
    public static let version = "1.0.0"
    public static let name = "KagamiCore"
}
