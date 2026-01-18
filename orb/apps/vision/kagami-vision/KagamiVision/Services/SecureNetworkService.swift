//
// SecureNetworkService.swift — Secure Network Configuration
//
// Colony: Nexus (e4) — Integration
//
// Shared secure networking infrastructure for all visionOS services.
// Provides certificate pinning, TLS configuration, and secure sessions.
//
// Created: January 2, 2026
// 鏡

import Foundation
import CryptoKit
import Security
import os.log

// MARK: - Certificate Configuration

/// Certificate pinning configuration for secure API communication
public enum SecureNetworkConfig {
    /// Production API base URL (HTTPS required)
    public static let baseURL = "https://kagami.local:8001"

    /// Certificate pin keys in Keychain
    private static let primaryPinKey = "kagami_cert_pin_primary"
    private static let backupPinKey = "kagami_cert_pin_backup"

    /// SHA-256 public key pins for certificate pinning.
    /// Loaded from Keychain at runtime, with development fallback.
    public static var pinnedPublicKeyHashes: Set<String> {
        var pins = Set<String>()

        // Load from Keychain
        if let primary = loadCertPinFromKeychain(key: primaryPinKey) {
            pins.insert(primary)
        }
        if let backup = loadCertPinFromKeychain(key: backupPinKey) {
            pins.insert(backup)
        }

        // If no pins loaded, use development placeholder (allows all certs)
        if pins.isEmpty {
            #if DEBUG
            pins.insert("DEVELOPMENT_PLACEHOLDER")
            #endif
        }

        return pins
    }

    /// Returns true if running with development placeholders
    public static var isUsingDevelopmentCerts: Bool {
        pinnedPublicKeyHashes.contains("DEVELOPMENT_PLACEHOLDER")
    }

    /// Loads a certificate pin from the macOS/visionOS Keychain
    private static func loadCertPinFromKeychain(key: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: "kagami",
            kSecAttrAccount as String: key,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]

        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)

        guard status == errSecSuccess,
              let data = result as? Data,
              let pin = String(data: data, encoding: .utf8) else {
            return nil
        }

        return pin
    }

    /// Creates a URLSession with certificate pinning
    public static func createSecureSession() -> URLSession {
        let config = URLSessionConfiguration.default
        config.tlsMinimumSupportedProtocolVersion = .TLSv12
        config.tlsMaximumSupportedProtocolVersion = .TLSv13
        return URLSession(
            configuration: config,
            delegate: CertificatePinningDelegate.shared,
            delegateQueue: nil
        )
    }
}

// MARK: - Certificate Pinning Delegate

/// Shared URLSession delegate that implements certificate pinning
public final class CertificatePinningDelegate: NSObject, URLSessionDelegate {

    /// Shared instance for reuse across services
    public static let shared = CertificatePinningDelegate()

    private override init() {
        super.init()
    }

    public func urlSession(
        _ session: URLSession,
        didReceive challenge: URLAuthenticationChallenge,
        completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void
    ) {
        guard challenge.protectionSpace.authenticationMethod == NSURLAuthenticationMethodServerTrust,
              let serverTrust = challenge.protectionSpace.serverTrust else {
            completionHandler(.cancelAuthenticationChallenge, nil)
            return
        }

        // Evaluate server trust
        var error: CFError?
        let isServerTrusted = SecTrustEvaluateWithError(serverTrust, &error)

        guard isServerTrusted else {
            KagamiLogger.security.error("Server trust evaluation failed: \(String(describing: error))")
            completionHandler(.cancelAuthenticationChallenge, nil)
            return
        }

        // Extract and validate public key
        guard let serverCertificate = SecTrustGetCertificateAtIndex(serverTrust, 0),
              let publicKey = SecCertificateCopyKey(serverCertificate),
              let publicKeyData = SecKeyCopyExternalRepresentation(publicKey, nil) as Data? else {
            completionHandler(.cancelAuthenticationChallenge, nil)
            return
        }

        // Calculate SHA-256 hash of the public key
        let publicKeyHash = SHA256.hash(data: publicKeyData)
        let hashString = Data(publicKeyHash).base64EncodedString()

        // Get current pins
        let pins = SecureNetworkConfig.pinnedPublicKeyHashes

        // Verify against pinned keys
        if pins.contains(hashString) {
            completionHandler(.useCredential, URLCredential(trust: serverTrust))
        } else if SecureNetworkConfig.isUsingDevelopmentCerts {
            // Development mode - allow connection but log warning
            #if DEBUG
            KagamiLogger.security.debug("Development mode - bypassing certificate pinning")
            #endif
            completionHandler(.useCredential, URLCredential(trust: serverTrust))
        } else {
            KagamiLogger.security.error("Certificate pinning validation failed - public key hash mismatch")
            completionHandler(.cancelAuthenticationChallenge, nil)
        }
    }
}

// MARK: - Secure Network Service

/// Shared service for making secure network requests
@MainActor
public final class SecureNetworkService {

    /// Shared instance
    public static let shared = SecureNetworkService()

    /// The secure URL session with certificate pinning
    private lazy var session: URLSession = SecureNetworkConfig.createSecureSession()

    private init() {}

    /// Performs a secure POST request with JSON body
    public func post(
        endpoint: String,
        body: [String: Any]
    ) async throws {
        guard let url = URL(string: "\(SecureNetworkConfig.baseURL)\(endpoint)") else {
            throw SecureNetworkError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (_, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse,
              (200..<300).contains(httpResponse.statusCode) else {
            throw SecureNetworkError.requestFailed
        }
    }

    /// Performs a secure GET request
    public func get<T: Decodable>(
        endpoint: String,
        responseType: T.Type
    ) async throws -> T {
        guard let url = URL(string: "\(SecureNetworkConfig.baseURL)\(endpoint)") else {
            throw SecureNetworkError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.addValue("application/json", forHTTPHeaderField: "Accept")

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse,
              (200..<300).contains(httpResponse.statusCode) else {
            throw SecureNetworkError.requestFailed
        }

        return try JSONDecoder().decode(T.self, from: data)
    }
}

// MARK: - Errors

public enum SecureNetworkError: LocalizedError {
    case invalidURL
    case requestFailed
    case certificatePinningFailed

    public var errorDescription: String? {
        switch self {
        case .invalidURL:
            return String(localized: "error.network.invalidURL", defaultValue: "Invalid URL")
        case .requestFailed:
            return String(localized: "error.network.requestFailed", defaultValue: "Network request failed")
        case .certificatePinningFailed:
            return String(localized: "error.network.certificatePinning", defaultValue: "Security validation failed")
        }
    }
}

/*
 * 鏡
 * h(x) >= 0. Always.
 *
 * Secure communication is the foundation of trust.
 * Certificate pinning ensures we speak only to known servers.
 */
