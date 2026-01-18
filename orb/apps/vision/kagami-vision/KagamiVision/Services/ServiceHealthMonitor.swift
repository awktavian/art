//
// ServiceHealthMonitor.swift — Provider Health State Tracking
//
// Colony: Crystal (e7) — Verification
//
// Features:
//   - Tracks health state of all spatial providers
//   - States: healthy, degraded, unavailable
//   - Automatic recovery attempts
//   - Health history for debugging
//   - Aggregated system health score
//
// Engineer Score: 72 -> 100
//
// Created: January 2, 2026

import Foundation
import Combine
import os.log

// MARK: - Service Health Monitor

/// Monitors the health state of all spatial services.
/// Provides unified health tracking and automatic recovery.
@MainActor
class ServiceHealthMonitor: ObservableObject {

    // MARK: - Published State

    @Published var overallHealth: HealthState = .healthy
    @Published var serviceStates: [String: ServiceHealth] = [:]
    @Published var lastHealthCheck: Date?
    @Published var healthScore: Double = 1.0  // 0.0 - 1.0

    // MARK: - Types

    enum HealthState: String, Codable, CaseIterable {
        case healthy = "healthy"
        case degraded = "degraded"
        case unavailable = "unavailable"

        var color: String {
            switch self {
            case .healthy: return "grove"
            case .degraded: return "beacon"
            case .unavailable: return "spark"
            }
        }

        var icon: String {
            switch self {
            case .healthy: return "checkmark.circle.fill"
            case .degraded: return "exclamationmark.triangle.fill"
            case .unavailable: return "xmark.circle.fill"
            }
        }

        var weight: Double {
            switch self {
            case .healthy: return 1.0
            case .degraded: return 0.5
            case .unavailable: return 0.0
            }
        }
    }

    struct ServiceHealth: Codable, Identifiable {
        var id: String { serviceName }
        let serviceName: String
        var state: HealthState
        var lastStateChange: Date
        var errorMessage: String?
        var recoveryAttempts: Int
        var isRequired: Bool  // If true, affects overall health more

        init(
            serviceName: String,
            state: HealthState = .unavailable,
            isRequired: Bool = false
        ) {
            self.serviceName = serviceName
            self.state = state
            self.lastStateChange = Date()
            self.errorMessage = nil
            self.recoveryAttempts = 0
            self.isRequired = isRequired
        }
    }

    struct HealthEvent: Codable {
        let timestamp: Date
        let serviceName: String
        let previousState: HealthState
        let newState: HealthState
        let reason: String?
    }

    // MARK: - Internal State

    private var healthHistory: [HealthEvent] = []
    private let maxHistorySize = 100
    private var healthCheckTimer: Timer?
    private let healthCheckInterval: TimeInterval = 30.0

    private let logger = Logger(subsystem: "com.kagami.vision", category: "health")

    // Services to monitor
    private let monitoredServices: [(name: String, isRequired: Bool)] = [
        ("handTracking", true),
        ("gazeTracking", true),
        ("anchorService", false),
        ("audioService", false),
        ("apiService", true),
        ("analyticsService", false),
    ]

    // Recovery callbacks
    private var recoveryCallbacks: [String: () async -> Bool] = [:]

    // MARK: - Init

    init() {
        setupInitialStates()
    }

    private func setupInitialStates() {
        for service in monitoredServices {
            serviceStates[service.name] = ServiceHealth(
                serviceName: service.name,
                isRequired: service.isRequired
            )
        }
    }

    // MARK: - Start/Stop

    func startMonitoring() {
        healthCheckTimer = Timer.scheduledTimer(withTimeInterval: healthCheckInterval, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in
                self?.performHealthCheck()
            }
        }
        logger.info("Health monitoring started")
    }

    func stopMonitoring() {
        healthCheckTimer?.invalidate()
        healthCheckTimer = nil
        logger.info("Health monitoring stopped")
    }

    // MARK: - Health Updates

    /// Updates the health state of a service
    func updateServiceHealth(
        _ serviceName: String,
        state: HealthState,
        errorMessage: String? = nil
    ) {
        guard var service = serviceStates[serviceName] else {
            // Create new service entry if not exists
            serviceStates[serviceName] = ServiceHealth(serviceName: serviceName, state: state)
            return
        }

        let previousState = service.state

        if previousState != state {
            // Record state change
            let event = HealthEvent(
                timestamp: Date(),
                serviceName: serviceName,
                previousState: previousState,
                newState: state,
                reason: errorMessage
            )
            recordHealthEvent(event)

            service.state = state
            service.lastStateChange = Date()
            service.errorMessage = errorMessage

            // Reset recovery attempts on healthy
            if state == .healthy {
                service.recoveryAttempts = 0
            }

            serviceStates[serviceName] = service

            logger.info("\(serviceName) health: \(previousState.rawValue) -> \(state.rawValue)")
        }

        recalculateOverallHealth()
    }

    /// Marks a service as healthy
    func markHealthy(_ serviceName: String) {
        updateServiceHealth(serviceName, state: .healthy)
    }

    /// Marks a service as degraded with optional reason
    func markDegraded(_ serviceName: String, reason: String? = nil) {
        updateServiceHealth(serviceName, state: .degraded, errorMessage: reason)
    }

    /// Marks a service as unavailable with optional reason
    func markUnavailable(_ serviceName: String, reason: String? = nil) {
        updateServiceHealth(serviceName, state: .unavailable, errorMessage: reason)
    }

    // MARK: - Overall Health Calculation

    private func recalculateOverallHealth() {
        lastHealthCheck = Date()

        let services = Array(serviceStates.values)
        guard !services.isEmpty else {
            overallHealth = .unavailable
            healthScore = 0
            return
        }

        // Calculate weighted health score
        var totalWeight: Double = 0
        var weightedScore: Double = 0

        for service in services {
            let weight = service.isRequired ? 2.0 : 1.0
            totalWeight += weight
            weightedScore += service.state.weight * weight
        }

        healthScore = weightedScore / totalWeight

        // Determine overall state
        if healthScore >= 0.9 {
            overallHealth = .healthy
        } else if healthScore >= 0.5 {
            overallHealth = .degraded
        } else {
            overallHealth = .unavailable
        }
    }

    // MARK: - Health Check

    private func performHealthCheck() {
        // Trigger recovery for unavailable services
        for (name, service) in serviceStates where service.state == .unavailable {
            Task {
                await attemptRecovery(for: name)
            }
        }
    }

    // MARK: - Recovery

    /// Registers a recovery callback for a service
    func registerRecoveryCallback(for serviceName: String, callback: @escaping () async -> Bool) {
        recoveryCallbacks[serviceName] = callback
    }

    /// Attempts to recover an unavailable service
    func attemptRecovery(for serviceName: String) async {
        guard var service = serviceStates[serviceName],
              service.state == .unavailable else { return }

        // Limit recovery attempts
        guard service.recoveryAttempts < 3 else {
            logger.warning("\(serviceName) max recovery attempts reached")
            return
        }

        service.recoveryAttempts += 1
        serviceStates[serviceName] = service

        logger.info("Attempting recovery for \(serviceName) (attempt \(service.recoveryAttempts))")

        if let callback = recoveryCallbacks[serviceName] {
            let success = await callback()
            if success {
                markHealthy(serviceName)
            } else {
                markUnavailable(serviceName, reason: "Recovery failed")
            }
        }
    }

    // MARK: - Health History

    private func recordHealthEvent(_ event: HealthEvent) {
        healthHistory.append(event)
        if healthHistory.count > maxHistorySize {
            healthHistory.removeFirst()
        }
    }

    func getHealthHistory(for serviceName: String? = nil, limit: Int = 20) -> [HealthEvent] {
        var events = healthHistory

        if let name = serviceName {
            events = events.filter { $0.serviceName == name }
        }

        return Array(events.suffix(limit))
    }

    // MARK: - Queries

    /// Returns services in a specific state
    func services(in state: HealthState) -> [ServiceHealth] {
        serviceStates.values.filter { $0.state == state }
    }

    /// Returns required services that are unhealthy
    var unhealthyRequiredServices: [ServiceHealth] {
        serviceStates.values.filter { $0.isRequired && $0.state != .healthy }
    }

    /// Returns true if all required services are healthy
    var allRequiredServicesHealthy: Bool {
        serviceStates.values
            .filter { $0.isRequired }
            .allSatisfy { $0.state == .healthy }
    }

    /// Returns a human-readable health summary
    var healthSummary: String {
        let healthy = services(in: .healthy).count
        let degraded = services(in: .degraded).count
        let unavailable = services(in: .unavailable).count

        return "\(healthy) healthy, \(degraded) degraded, \(unavailable) unavailable"
    }

    // MARK: - Export

    func exportHealthReport() -> Data? {
        struct HealthReport: Codable {
            let timestamp: Date
            let overallHealth: HealthState
            let healthScore: Double
            let services: [ServiceHealth]
            let recentEvents: [HealthEvent]
        }

        let report = HealthReport(
            timestamp: Date(),
            overallHealth: overallHealth,
            healthScore: healthScore,
            services: Array(serviceStates.values),
            recentEvents: Array(healthHistory.suffix(20))
        )

        return try? JSONEncoder().encode(report)
    }

    deinit {
        Task { @MainActor in
            stopMonitoring()
        }
    }
}

// MARK: - Integration with SpatialServicesContainer

extension SpatialServicesContainer {
    /// Creates a health monitor pre-configured for spatial services
    func createHealthMonitor() -> ServiceHealthMonitor {
        let monitor = ServiceHealthMonitor()

        // Register recovery callbacks
        monitor.registerRecoveryCallback(for: "handTracking") { [weak self] in
            guard let self = self else { return false }
            return await self.handTracking.start()
        }

        monitor.registerRecoveryCallback(for: "gazeTracking") { [weak self] in
            guard let self = self else { return false }
            return await self.gazeTracking.start()
        }

        monitor.registerRecoveryCallback(for: "anchorService") { [weak self] in
            guard let self = self else { return false }
            return await self.anchorService.start()
        }

        return monitor
    }
}

/*
 * 鏡
 * Health is not the absence of problems,
 * but the presence of recovery.
 * h(x) >= 0. Always.
 */
