//
// AnalyticsService.swift
// KagamiVision
//
// Privacy-respecting analytics for visionOS.
// All data stays on-device or on the local Kagami server.
//
// Features:
//   - Usage patterns for optimization
//   - Feature adoption tracking
//   - Performance metrics
//   - No third-party analytics
//   - Local-only or Kagami server storage
//

import Foundation
import os.log

// MARK: - Analytics Event

struct AnalyticsEvent: Codable {
    let id: UUID
    let timestamp: Date
    let category: Category
    let action: String
    let label: String?
    let value: Double?
    let metadata: [String: String]?

    enum Category: String, Codable {
        case navigation      // Screen views, navigation
        case interaction     // User interactions
        case device          // Device control actions
        case spatial         // Spatial features usage
        case performance     // Performance metrics
        case error           // Errors and issues
        case handTracking    // Hand tracking events
        case gestureRecognition  // Gesture confidence metrics
        case voiceCommand    // Voice command analytics
    }

    init(
        category: Category,
        action: String,
        label: String? = nil,
        value: Double? = nil,
        metadata: [String: String]? = nil
    ) {
        self.id = UUID()
        self.timestamp = Date()
        self.category = category
        self.action = action
        self.label = label
        self.value = value
        self.metadata = metadata
    }
}

// MARK: - Analytics Service

@MainActor
class AnalyticsService: ObservableObject {

    // MARK: - Published State

    @Published var isEnabled = true
    @Published var eventCount = 0

    // MARK: - Internal State

    private var events: [AnalyticsEvent] = []
    private let maxLocalEvents = 1000
    private let logger = Logger(subsystem: "com.kagami.vision", category: "analytics")

    // Persistence
    private let storageKey = "kagami.analytics.events"

    // Upload to Kagami server
    private var apiService: KagamiAPIService?
    private let uploadBatchSize = 50
    private var uploadTimer: Timer?

    // MARK: - Init

    init(apiService: KagamiAPIService? = nil) {
        self.apiService = apiService
        loadPersistedEvents()
        startUploadTimer()
    }

    func setAPIService(_ service: KagamiAPIService) {
        self.apiService = service
    }

    // MARK: - Event Tracking

    /// Tracks a generic event
    func track(_ event: AnalyticsEvent) {
        guard isEnabled else { return }

        events.append(event)
        eventCount = events.count

        // Log for debugging
        logger.debug("Analytics: \(event.category.rawValue)/\(event.action)")

        // Trim if needed
        if events.count > maxLocalEvents {
            events.removeFirst(events.count - maxLocalEvents)
        }

        // Persist periodically
        if events.count % 10 == 0 {
            persistEvents()
        }
    }

    // MARK: - Convenience Methods

    /// Tracks a screen view
    func trackScreen(_ screenName: String) {
        track(AnalyticsEvent(
            category: .navigation,
            action: "screen_view",
            label: screenName
        ))
    }

    /// Tracks a user interaction
    func trackInteraction(action: String, target: String? = nil) {
        track(AnalyticsEvent(
            category: .interaction,
            action: action,
            label: target
        ))
    }

    /// Tracks a device control action
    func trackDeviceAction(device: String, action: String, value: Double? = nil) {
        track(AnalyticsEvent(
            category: .device,
            action: action,
            label: device,
            value: value
        ))
    }

    /// Tracks spatial feature usage
    func trackSpatialFeature(feature: String, duration: TimeInterval? = nil) {
        track(AnalyticsEvent(
            category: .spatial,
            action: "feature_used",
            label: feature,
            value: duration
        ))
    }

    /// Tracks a performance metric
    func trackPerformance(metric: String, value: Double, unit: String? = nil) {
        track(AnalyticsEvent(
            category: .performance,
            action: metric,
            label: unit,
            value: value
        ))
    }

    /// Tracks an error
    func trackError(_ error: String, context: String? = nil) {
        track(AnalyticsEvent(
            category: .error,
            action: error,
            label: context
        ))
    }

    // MARK: - Hand Tracking Analytics

    /// Tracks hand tracking availability changes
    func trackHandTrackingAvailability(isAvailable: Bool, reason: String? = nil) {
        track(AnalyticsEvent(
            category: .handTracking,
            action: isAvailable ? "available" : "unavailable",
            label: reason,
            metadata: ["timestamp": ISO8601DateFormatter().string(from: Date())]
        ))
    }

    /// Tracks hand detection events
    func trackHandDetection(leftHand: Bool, rightHand: Bool) {
        let handsDetected = [leftHand ? "left" : nil, rightHand ? "right" : nil]
            .compactMap { $0 }
            .joined(separator: ",")

        track(AnalyticsEvent(
            category: .handTracking,
            action: "hands_detected",
            label: handsDetected.isEmpty ? "none" : handsDetected
        ))
    }

    /// Tracks hand position out of reach events
    func trackHandOutOfReach(hand: String, distance: Float) {
        track(AnalyticsEvent(
            category: .handTracking,
            action: "out_of_reach",
            label: hand,
            value: Double(distance)
        ))
    }

    /// Tracks fatigue warning triggers
    func trackFatigueWarning(duration: TimeInterval) {
        track(AnalyticsEvent(
            category: .handTracking,
            action: "fatigue_warning",
            value: duration
        ))
    }

    // MARK: - Gesture Recognition Analytics

    /// Tracks gesture recognition with confidence
    func trackGestureRecognition(gesture: String, confidence: Float, successful: Bool) {
        track(AnalyticsEvent(
            category: .gestureRecognition,
            action: gesture,
            label: successful ? "success" : "failed",
            value: Double(confidence),
            metadata: ["gesture_type": gesture]
        ))
    }

    /// Tracks gesture attempts that failed recognition
    func trackGestureFailure(attemptedGesture: String?, reason: String) {
        track(AnalyticsEvent(
            category: .gestureRecognition,
            action: "recognition_failed",
            label: attemptedGesture ?? "unknown",
            metadata: ["reason": reason]
        ))
    }

    // MARK: - Voice Command Analytics

    /// Tracks voice command attempts
    func trackVoiceCommand(command: String, understood: Bool, executionTime: TimeInterval?) {
        track(AnalyticsEvent(
            category: .voiceCommand,
            action: understood ? "understood" : "not_understood",
            label: command,
            value: executionTime
        ))
    }

    /// Tracks voice recognition confidence
    func trackVoiceRecognitionConfidence(transcript: String, confidence: Float) {
        track(AnalyticsEvent(
            category: .voiceCommand,
            action: "recognition_confidence",
            label: transcript.prefix(50).description,  // Truncate for privacy
            value: Double(confidence)
        ))
    }

    // MARK: - Persistence

    private func loadPersistedEvents() {
        guard let data = UserDefaults.standard.data(forKey: storageKey),
              let loaded = try? JSONDecoder().decode([AnalyticsEvent].self, from: data) else {
            return
        }
        events = loaded
        eventCount = events.count
    }

    private func persistEvents() {
        if let data = try? JSONEncoder().encode(events) {
            UserDefaults.standard.set(data, forKey: storageKey)
        }
    }

    // MARK: - Upload to Server

    private func startUploadTimer() {
        uploadTimer = Timer.scheduledTimer(withTimeInterval: 300, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in
                await self?.uploadEvents()
            }
        }
    }

    private func uploadEvents() async {
        guard let apiService = apiService,
              apiService.isConnected,
              events.count >= uploadBatchSize else { return }

        let batch = Array(events.prefix(uploadBatchSize))

        // Would send to Kagami server
        // await apiService.uploadAnalytics(batch)

        // For now, just clear uploaded events
        events.removeFirst(min(uploadBatchSize, events.count))
        persistEvents()
    }

    // MARK: - Data Management

    /// Clears all analytics data
    func clearAllData() {
        events.removeAll()
        eventCount = 0
        UserDefaults.standard.removeObject(forKey: storageKey)
    }

    /// Exports analytics data for user
    func exportData() -> Data? {
        try? JSONEncoder().encode(events)
    }

    // MARK: - Summary Statistics

    struct UsageSummary {
        let totalEvents: Int
        let screenViews: Int
        let deviceActions: Int
        let spatialFeatureUsage: Int
        let mostUsedFeature: String?
        let averageSessionLength: TimeInterval?
    }

    func generateSummary() -> UsageSummary {
        let screenViews = events.filter { $0.category == .navigation && $0.action == "screen_view" }.count
        let deviceActions = events.filter { $0.category == .device }.count
        let spatialUsage = events.filter { $0.category == .spatial }.count

        // Find most used feature
        let featureCounts = Dictionary(grouping: events.filter { $0.category == .spatial }) { $0.label ?? "unknown" }
            .mapValues { $0.count }
        let mostUsed = featureCounts.max(by: { $0.value < $1.value })?.key

        return UsageSummary(
            totalEvents: events.count,
            screenViews: screenViews,
            deviceActions: deviceActions,
            spatialFeatureUsage: spatialUsage,
            mostUsedFeature: mostUsed,
            averageSessionLength: nil
        )
    }

    deinit {
        uploadTimer?.invalidate()
        Task { @MainActor in
            persistEvents()
        }
    }
}

/*
 * Analytics respects user privacy.
 * All data stays local or on your Kagami server.
 * No third-party tracking.
 */
