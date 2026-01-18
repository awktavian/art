//
// SensoryService.swift — Sensory Data Upload Service
//
// Colony: Nexus (e4) — Integration
//
// Features:
//   - Periodic sensory data uploads to Kagami backend
//   - Health data integration (via HealthKitService)
//   - Location data (when available)
//   - Client heartbeat management
//
// Architecture:
//   SensoryService -> HealthKitService -> HealthKit
//   SensoryService -> KagamiAPIService -> Kagami Backend
//
// h(x) >= 0. Always.
//

import Foundation
import Combine

/// Service for uploading sensory data to Kagami backend
@MainActor
public final class SensoryService: ObservableObject {

    // MARK: - Singleton

    public static let shared = SensoryService()

    // MARK: - Published State

    @Published public private(set) var isUploading = false
    @Published public private(set) var lastUploadTime: Date?
    @Published public private(set) var uploadCount: Int = 0
    @Published public private(set) var lastError: SensoryError?

    // MARK: - Configuration

    private let uploadInterval: TimeInterval
    private let heartbeatInterval: TimeInterval

    // MARK: - Internal State

    private var uploadTimer: Timer?
    private var heartbeatTimer: Timer?
    private var clientId: String = ""

    // MARK: - Dependencies

    private let apiService: KagamiAPIService
    private let healthService: HealthKitService

    // MARK: - Init

    /// Initialize the service with default singletons
    public init() {
        self.apiService = KagamiAPIService.shared
        self.healthService = HealthKitService.shared
        self.uploadInterval = 30.0
        self.heartbeatInterval = 60.0
    }

    /// Internal initializer for testing/custom configuration
    init(
        apiService: KagamiAPIService,
        healthService: HealthKitService,
        uploadInterval: TimeInterval = 30.0,
        heartbeatInterval: TimeInterval = 60.0
    ) {
        self.apiService = apiService
        self.healthService = healthService
        self.uploadInterval = uploadInterval
        self.heartbeatInterval = heartbeatInterval
    }

    // MARK: - Configuration

    /// Configure the service with client ID
    public func configure(clientId: String) {
        self.clientId = clientId
    }

    // MARK: - Start/Stop

    /// Start periodic sensory uploads and heartbeats
    public func start() {
        guard !clientId.isEmpty else {
            #if DEBUG
            print("[SensoryService] Cannot start: clientId not configured")
            #endif
            return
        }

        // Initial upload
        Task {
            await uploadSensoryData()
        }

        // Start upload timer
        uploadTimer?.invalidate()
        uploadTimer = Timer.scheduledTimer(withTimeInterval: uploadInterval, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in
                await self?.uploadSensoryData()
            }
        }

        // Start heartbeat timer
        heartbeatTimer?.invalidate()
        heartbeatTimer = Timer.scheduledTimer(withTimeInterval: heartbeatInterval, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in
                await self?.sendHeartbeat()
            }
        }

        #if DEBUG
        print("[SensoryService] Started with upload interval: \(uploadInterval)s, heartbeat: \(heartbeatInterval)s")
        #endif
    }

    /// Stop periodic uploads and heartbeats
    public func stop() {
        uploadTimer?.invalidate()
        uploadTimer = nil
        heartbeatTimer?.invalidate()
        heartbeatTimer = nil

        #if DEBUG
        print("[SensoryService] Stopped")
        #endif
    }

    // MARK: - Sensory Data Upload

    /// Upload current sensory data to Kagami backend
    public func uploadSensoryData() async {
        guard !clientId.isEmpty else {
            lastError = .notConfigured
            return
        }

        guard !isUploading else { return }

        isUploading = true
        lastError = nil

        // Gather sensory data from HealthKit
        var sensorData = healthService.toUploadDict()

        // Add additional context if available
        sensorData["timestamp"] = ISO8601DateFormatter().string(from: Date())
        sensorData["client_id"] = clientId

        // Only upload if we have data
        guard !sensorData.isEmpty else {
            isUploading = false
            return
        }

        let success = await apiService.postRequest(
            endpoint: "/api/home/clients/\(clientId)/sense",
            body: sensorData
        )

        if success {
            lastUploadTime = Date()
            uploadCount += 1

            #if DEBUG
            print("[SensoryService] Uploaded sensory data: \(sensorData.keys.joined(separator: ", "))")
            #endif
        } else {
            lastError = .uploadFailed

            #if DEBUG
            print("[SensoryService] Upload failed")
            #endif
        }

        isUploading = false
    }

    /// Send heartbeat to maintain client registration
    public func sendHeartbeat() async {
        guard !clientId.isEmpty else { return }

        let success = await apiService.postRequest(
            endpoint: "/api/home/clients/\(clientId)/heartbeat",
            body: nil
        )

        #if DEBUG
        if success {
            print("[SensoryService] Heartbeat sent")
        } else {
            print("[SensoryService] Heartbeat failed")
        }
        #endif
    }

    // MARK: - Manual Upload

    /// Force an immediate sensory data upload
    public func uploadNow() async {
        await uploadSensoryData()
    }

    /// Upload specific data (for custom sensor data)
    public func upload(data: [String: Any]) async -> Bool {
        guard !clientId.isEmpty else {
            lastError = .notConfigured
            return false
        }

        var payload = data
        payload["timestamp"] = ISO8601DateFormatter().string(from: Date())
        payload["client_id"] = clientId

        return await apiService.postRequest(
            endpoint: "/api/home/clients/\(clientId)/sense",
            body: payload
        )
    }
}

// MARK: - Sensory Error

public enum SensoryError: LocalizedError {
    case notConfigured
    case uploadFailed
    case noData

    public var errorDescription: String? {
        switch self {
        case .notConfigured:
            return "Service not configured with client ID"
        case .uploadFailed:
            return "Failed to upload sensory data"
        case .noData:
            return "No sensory data available"
        }
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
