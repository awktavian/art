//
// KagamiNetworkService.swift — Centralized Network Configuration
//
// Colony: Nexus (e4) — Integration
//
// Provides:
//   - Singleton URLSession with optimized configuration
//   - Configurable timeouts and retry policies
//   - Network error tracking with analytics integration
//   - Request retry with exponential backoff
//
// h(x) >= 0. Always.
//

import Foundation
import OSLog

// MARK: - Network Configuration

/// Configuration for network requests
struct NetworkConfiguration: Sendable {
    /// Timeout for establishing a connection (seconds)
    let connectionTimeout: TimeInterval
    /// Timeout for the entire request (seconds)
    let requestTimeout: TimeInterval
    /// Maximum number of retry attempts
    let maxRetryAttempts: Int
    /// Base delay for exponential backoff (seconds)
    let baseRetryDelay: TimeInterval
    /// Maximum delay between retries (seconds)
    let maxRetryDelay: TimeInterval
    /// Whether to retry on timeout errors
    let retryOnTimeout: Bool
    /// Whether to retry on server errors (5xx)
    let retryOnServerError: Bool

    static let `default` = NetworkConfiguration(
        connectionTimeout: 10,
        requestTimeout: 30,
        maxRetryAttempts: 3,
        baseRetryDelay: 0.5,
        maxRetryDelay: 8,
        retryOnTimeout: true,
        retryOnServerError: true
    )

    static let aggressive = NetworkConfiguration(
        connectionTimeout: 5,
        requestTimeout: 15,
        maxRetryAttempts: 5,
        baseRetryDelay: 0.25,
        maxRetryDelay: 4,
        retryOnTimeout: true,
        retryOnServerError: true
    )

    static let conservative = NetworkConfiguration(
        connectionTimeout: 15,
        requestTimeout: 60,
        maxRetryAttempts: 2,
        baseRetryDelay: 1,
        maxRetryDelay: 16,
        retryOnTimeout: false,
        retryOnServerError: false
    )
}

// MARK: - Network Error

/// Enhanced network error with detailed context
public enum NetworkError: Error, LocalizedError {
    case invalidURL
    case requestFailed(statusCode: Int, data: Data?)
    case timeout
    case noConnection
    case serverError(statusCode: Int, message: String?)
    case decodingFailed(Error)
    case maxRetriesExceeded(lastError: Error?, attempts: Int)
    case cancelled
    case unknown(Error)

    public var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Invalid URL"
        case .requestFailed(let statusCode, _):
            return "Request failed with status \(statusCode)"
        case .timeout:
            return "Request timed out"
        case .noConnection:
            return "No network connection"
        case .serverError(let statusCode, let message):
            return message ?? "Server error (\(statusCode))"
        case .decodingFailed(let error):
            return "Failed to parse response: \(error.localizedDescription)"
        case .maxRetriesExceeded(_, let attempts):
            return "Request failed after \(attempts) attempts"
        case .cancelled:
            return "Request was cancelled"
        case .unknown(let error):
            return error.localizedDescription
        }
    }

    /// Error code for analytics tracking
    var errorCode: Int {
        switch self {
        case .invalidURL: return -1
        case .requestFailed(let statusCode, _): return statusCode
        case .timeout: return -1001
        case .noConnection: return -1009
        case .serverError(let statusCode, _): return statusCode
        case .decodingFailed: return -2
        case .maxRetriesExceeded: return -3
        case .cancelled: return -999
        case .unknown: return -99
        }
    }

    /// Whether this error is retryable
    var isRetryable: Bool {
        switch self {
        case .timeout, .noConnection:
            return true
        case .serverError(let statusCode, _):
            return statusCode >= 500 && statusCode < 600
        case .requestFailed(let statusCode, _):
            return statusCode >= 500 && statusCode < 600 || statusCode == 429
        default:
            return false
        }
    }
}

// MARK: - Network Service

/// Centralized network service with singleton URLSession
@MainActor
public final class KagamiNetworkService: Sendable {

    // MARK: - Singleton

    public static let shared = KagamiNetworkService()

    // MARK: - Properties

    /// Shared URLSession with optimized configuration
    nonisolated let session: URLSession

    /// Current configuration
    private let configuration: NetworkConfiguration

    /// Logger for network operations
    private let logger = Logger(subsystem: "com.kagami.ios", category: "Network")

    // MARK: - Init

    init(configuration: NetworkConfiguration = .default) {
        self.configuration = configuration

        // Configure URLSession
        let sessionConfig = URLSessionConfiguration.default

        // Timeouts
        sessionConfig.timeoutIntervalForRequest = configuration.requestTimeout
        sessionConfig.timeoutIntervalForResource = configuration.requestTimeout * 2

        // Connection settings
        sessionConfig.httpMaximumConnectionsPerHost = 6
        sessionConfig.waitsForConnectivity = true
        sessionConfig.allowsCellularAccess = true

        // Caching policy
        sessionConfig.requestCachePolicy = .reloadRevalidatingCacheData

        // HTTP settings
        sessionConfig.httpShouldUsePipelining = true
        sessionConfig.httpShouldSetCookies = false

        // Network service type (optimize for responsiveness)
        sessionConfig.networkServiceType = .responsiveData

        // TLS settings
        sessionConfig.tlsMinimumSupportedProtocolVersion = .TLSv12

        self.session = URLSession(configuration: sessionConfig)
    }

    // MARK: - Request Methods

    /// Perform a request with automatic retry
    func request(
        _ request: URLRequest,
        retryPolicy: NetworkConfiguration? = nil
    ) async throws -> (Data, URLResponse) {
        let config = retryPolicy ?? configuration
        var lastError: Error?
        var attempts = 0

        while attempts < config.maxRetryAttempts {
            attempts += 1

            do {
                let (data, response) = try await session.data(for: request)

                // Check for HTTP errors
                if let httpResponse = response as? HTTPURLResponse {
                    let statusCode = httpResponse.statusCode

                    // Success range
                    if (200..<300).contains(statusCode) {
                        // Track success
                        trackRequest(request, statusCode: statusCode, attempt: attempts, error: nil)
                        return (data, response)
                    }

                    // Server error (5xx)
                    if statusCode >= 500 && config.retryOnServerError {
                        let error = NetworkError.serverError(statusCode: statusCode, message: nil)
                        lastError = error

                        if attempts < config.maxRetryAttempts {
                            let delay = calculateRetryDelay(attempt: attempts, config: config)
                            try await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
                            continue
                        }
                    }

                    // Rate limited (429)
                    if statusCode == 429 {
                        let delay = parseRetryAfter(response: httpResponse) ?? calculateRetryDelay(attempt: attempts, config: config)
                        try await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
                        continue
                    }

                    // Client error (4xx) - don't retry
                    let error = NetworkError.requestFailed(statusCode: statusCode, data: data)
                    trackRequest(request, statusCode: statusCode, attempt: attempts, error: error)
                    throw error
                }

                return (data, response)

            } catch let error as URLError {
                lastError = mapURLError(error)

                // Check if retryable
                if let networkError = lastError as? NetworkError, networkError.isRetryable {
                    if attempts < config.maxRetryAttempts {
                        let delay = calculateRetryDelay(attempt: attempts, config: config)
                        logger.warning("Request failed (attempt \(attempts)), retrying in \(delay)s: \(error.localizedDescription)")
                        try await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
                        continue
                    }
                }

                // Track and throw
                trackRequest(request, statusCode: nil, attempt: attempts, error: lastError)
                throw lastError ?? error

            } catch {
                lastError = error
                trackRequest(request, statusCode: nil, attempt: attempts, error: error)
                throw error
            }
        }

        // Max retries exceeded
        let error = NetworkError.maxRetriesExceeded(lastError: lastError, attempts: attempts)
        trackRequest(request, statusCode: nil, attempt: attempts, error: error)
        throw error
    }

    /// Convenience method for GET requests
    func get(url: URL) async throws -> (Data, URLResponse) {
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        return try await self.request(request)
    }

    /// Convenience method for POST requests
    func post(url: URL, body: Data?, contentType: String = "application/json") async throws -> (Data, URLResponse) {
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.httpBody = body
        request.addValue(contentType, forHTTPHeaderField: "Content-Type")
        return try await self.request(request)
    }

    // MARK: - Helper Methods

    private func calculateRetryDelay(attempt: Int, config: NetworkConfiguration) -> TimeInterval {
        // Exponential backoff with jitter
        let exponentialDelay = config.baseRetryDelay * pow(2, Double(attempt - 1))
        let jitter = Double.random(in: 0...0.3) * exponentialDelay
        return min(exponentialDelay + jitter, config.maxRetryDelay)
    }

    private func parseRetryAfter(response: HTTPURLResponse) -> TimeInterval? {
        guard let retryAfter = response.value(forHTTPHeaderField: "Retry-After") else {
            return nil
        }

        // Try parsing as seconds
        if let seconds = Double(retryAfter) {
            return seconds
        }

        // Try parsing as HTTP date
        let formatter = DateFormatter()
        formatter.dateFormat = "EEE, dd MMM yyyy HH:mm:ss zzz"
        if let date = formatter.date(from: retryAfter) {
            return max(0, date.timeIntervalSinceNow)
        }

        return nil
    }

    private func mapURLError(_ error: URLError) -> NetworkError {
        switch error.code {
        case .timedOut:
            return .timeout
        case .notConnectedToInternet, .networkConnectionLost:
            return .noConnection
        case .cancelled:
            return .cancelled
        default:
            return .unknown(error)
        }
    }

    // MARK: - Analytics Integration

    private func trackRequest(
        _ request: URLRequest,
        statusCode: Int?,
        attempt: Int,
        error: Error?
    ) {
        Task { @MainActor in
            let endpoint = request.url?.path ?? "unknown"
            let method = request.httpMethod ?? "GET"

            if let error = error {
                let networkError = error as? NetworkError
                KagamiAnalytics.shared.trackEvent("network_request_failed", properties: [
                    "endpoint": endpoint,
                    "method": method,
                    "status_code": statusCode ?? (networkError?.errorCode ?? -1),
                    "error_code": networkError?.errorCode ?? -99,
                    "error_message": error.localizedDescription,
                    "attempt_count": attempt,
                    "is_retryable": networkError?.isRetryable ?? false
                ])
            } else if let statusCode = statusCode {
                // Only track non-success on debug or if there were retries
                if attempt > 1 {
                    KagamiAnalytics.shared.trackEvent("network_request_retried", properties: [
                        "endpoint": endpoint,
                        "method": method,
                        "status_code": statusCode,
                        "attempt_count": attempt
                    ])
                }
            }
        }
    }
}

// MARK: - URLRequest Extension

extension URLRequest {
    /// Create a request with default Kagami headers
    static func kagami(url: URL, method: String = "GET") -> URLRequest {
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.addValue("application/json", forHTTPHeaderField: "Accept")
        request.addValue("Kagami-iOS/1.0", forHTTPHeaderField: "User-Agent")
        return request
    }
}

/*
 * Mirror
 * Network reliability is foundational.
 * h(x) >= 0. Always.
 */
