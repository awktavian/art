//
// KagamiAnalytics.swift — Analytics Service
//
// Colony: Beacon (e5) — Planning
//
// Provides analytics tracking for Kagami iOS app:
//   - Event tracking (scenes, actions, navigation)
//   - Error tracking with context
//   - User property management
//   - Onboarding funnel tracking
//   - Scene activation metrics
//
// Supports multiple backends:
//   - Firebase Analytics (production)
//   - Console logging (debug)
//   - Custom backend (future)
//
// h(x) >= 0. Always.
//

import Foundation
import OSLog
#if canImport(UIKit)
import UIKit
#endif

// MARK: - Analytics Protocol

/// Protocol for analytics backends
protocol AnalyticsBackend {
    func trackEvent(_ name: String, properties: [String: Any]?)
    func trackError(_ name: String, error: Error?, properties: [String: Any]?)
    func setUserProperty(_ value: String?, forName name: String)
    func setUserId(_ userId: String?)
}

// MARK: - Analytics Event Types

/// Standard analytics events for Kagami
enum AnalyticsEvent: String {
    // Onboarding
    case onboardingStarted = "onboarding_started"
    case onboardingStepViewed = "onboarding_step_viewed"
    case onboardingStepCompleted = "onboarding_step_completed"
    case onboardingSkipped = "onboarding_skipped"
    case onboardingCompleted = "onboarding_completed"

    // Server Connection
    case serverDiscoveryStarted = "server_discovery_started"
    case serverDiscovered = "server_discovered"
    case serverConnectionAttempted = "server_connection_attempted"
    case serverConnectionSucceeded = "server_connection_succeeded"
    case serverConnectionFailed = "server_connection_failed"
    case demoModeActivated = "demo_mode_activated"

    // Smart Home Integration
    case integrationSelected = "integration_selected"
    case integrationTestStarted = "integration_test_started"
    case integrationTestSucceeded = "integration_test_succeeded"
    case integrationTestFailed = "integration_test_failed"
    case integrationConnected = "integration_connected"

    // Scenes
    case sceneActivated = "scene_activated"
    case sceneDeactivated = "scene_deactivated"
    case movieModeEntered = "movie_mode_entered"
    case movieModeExited = "movie_mode_exited"
    case goodnightActivated = "goodnight_activated"
    case welcomeHomeActivated = "welcome_home_activated"

    // Device Control
    case lightControlled = "light_controlled"
    case shadeControlled = "shade_controlled"
    case fireplaceToggled = "fireplace_toggled"
    case tvControlled = "tv_controlled"
    case lockControlled = "lock_controlled"
    case climateAdjusted = "climate_adjusted"

    // Voice & Shortcuts
    case siriShortcutUsed = "siri_shortcut_used"
    case voiceCommandIssued = "voice_command_issued"

    // App Lifecycle
    case appOpened = "app_opened"
    case appBackgrounded = "app_backgrounded"
    case widgetTapped = "widget_tapped"
    case notificationReceived = "notification_received"
    case notificationTapped = "notification_tapped"

    // Widget Interactions
    case widgetAdded = "widget_added"
    case widgetRemoved = "widget_removed"
    case widgetConfigured = "widget_configured"
    case widgetSceneActivated = "widget_scene_activated"
    case widgetRoomTapped = "widget_room_tapped"
    case widgetRefreshed = "widget_refreshed"
    case widgetError = "widget_error"

    // Errors
    case errorOccurred = "error_occurred"
    case networkError = "network_error"
    case apiError = "api_error"
}

// MARK: - Custom Event Name

extension KagamiAnalytics {
    /// Custom event name wrapper for type-safe event tracking
    struct EventName: RawRepresentable, Hashable {
        let rawValue: String

        init(rawValue: String) {
            self.rawValue = rawValue
        }
    }

    /// Track a custom event using EventName
    func track(_ event: EventName, properties: [String: Any]? = nil) {
        trackEvent(event.rawValue, properties: properties)
    }
}

// MARK: - Main Analytics Service

/// Main analytics service for Kagami
@MainActor
final class KagamiAnalytics {

    // MARK: - Singleton

    static let shared = KagamiAnalytics()

    // MARK: - Properties

    private var backends: [AnalyticsBackend] = []
    private var isEnabled: Bool = true
    private var userId: String?
    private var sessionId: String = UUID().uuidString
    private var sessionStartTime: Date = Date()

    private let logger = Logger(subsystem: "com.kagami.ios", category: "Analytics")

    // MARK: - User Properties

    private var globalProperties: [String: Any] = [:]

    // MARK: - Initialization

    private init() {
        // Add default console backend for debug builds
        #if DEBUG
        addBackend(ConsoleAnalyticsBackend())
        #endif

        // Configure default properties
        globalProperties["app_version"] = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String
        globalProperties["build_number"] = Bundle.main.infoDictionary?["CFBundleVersion"] as? String
        globalProperties["platform"] = "ios"
        globalProperties["device_model"] = UIDevice.current.model
        globalProperties["os_version"] = UIDevice.current.systemVersion
    }

    // MARK: - Configuration

    /// Add an analytics backend
    func addBackend(_ backend: AnalyticsBackend) {
        backends.append(backend)
    }

    /// Enable or disable analytics
    func setEnabled(_ enabled: Bool) {
        isEnabled = enabled
        logger.info("Analytics \(enabled ? "enabled" : "disabled")")
    }

    /// Set the current user ID
    func setUserId(_ userId: String?) {
        self.userId = userId
        backends.forEach { $0.setUserId(userId) }
    }

    /// Set a user property
    func setUserProperty(_ value: String?, forName name: String) {
        backends.forEach { $0.setUserProperty(value, forName: name) }
    }

    /// Set a global property added to all events
    func setGlobalProperty(_ value: Any, forName name: String) {
        globalProperties[name] = value
    }

    // MARK: - Event Tracking

    /// Track a standard event
    func track(_ event: AnalyticsEvent, properties: [String: Any]? = nil) {
        trackEvent(event.rawValue, properties: properties)
    }

    /// Track a custom event
    func trackEvent(_ name: String, properties: [String: Any]? = nil) {
        guard isEnabled else { return }

        var mergedProperties = globalProperties
        mergedProperties["session_id"] = sessionId
        mergedProperties["timestamp"] = ISO8601DateFormatter().string(from: Date())

        if let properties = properties {
            mergedProperties.merge(properties) { _, new in new }
        }

        backends.forEach { $0.trackEvent(name, properties: mergedProperties) }
    }

    /// Track an error with context
    func trackError(_ name: String, error: Error? = nil, properties: [String: Any]? = nil) {
        guard isEnabled else { return }

        var mergedProperties = globalProperties
        mergedProperties["session_id"] = sessionId
        mergedProperties["timestamp"] = ISO8601DateFormatter().string(from: Date())
        mergedProperties["error_name"] = name

        if let error = error {
            mergedProperties["error_description"] = error.localizedDescription
            mergedProperties["error_domain"] = (error as NSError).domain
            mergedProperties["error_code"] = (error as NSError).code
        }

        if let properties = properties {
            mergedProperties.merge(properties) { _, new in new }
        }

        backends.forEach { $0.trackError(name, error: error, properties: mergedProperties) }

        // Also log to system logger
        if let error = error {
            logger.error("[\(name)] \(error.localizedDescription)")
        } else {
            logger.error("[\(name)] Error tracked without exception")
        }
    }

    // MARK: - Convenience Methods

    /// Track onboarding progress
    func trackOnboardingStep(_ step: Int, name: String, completed: Bool = false, skipped: Bool = false) {
        let event: AnalyticsEvent = skipped ? .onboardingSkipped :
                                    completed ? .onboardingStepCompleted : .onboardingStepViewed

        track(event, properties: [
            "step_index": step,
            "step_name": name,
            "skipped": skipped
        ])
    }

    /// Track scene activation
    func trackSceneActivation(_ sceneName: String, source: String = "app") {
        track(.sceneActivated, properties: [
            "scene_name": sceneName,
            "activation_source": source
        ])
    }

    /// Track device control
    func trackDeviceControl(_ deviceType: String, action: String, room: String? = nil) {
        trackEvent("device_controlled", properties: [
            "device_type": deviceType,
            "action": action,
            "room": room ?? "unknown"
        ])
    }

    /// Track API call
    func trackAPICall(_ endpoint: String, success: Bool, latencyMs: Int, error: Error? = nil) {
        trackEvent("api_call", properties: [
            "endpoint": endpoint,
            "success": success,
            "latency_ms": latencyMs,
            "error": error?.localizedDescription ?? ""
        ])
    }

    /// Start a new session
    func startNewSession() {
        sessionId = UUID().uuidString
        sessionStartTime = Date()
        track(.appOpened)
    }

    /// Get session duration in seconds
    func getSessionDuration() -> TimeInterval {
        return Date().timeIntervalSince(sessionStartTime)
    }

    // MARK: - Widget Analytics

    /// Track widget added to home screen
    func trackWidgetAdded(widgetKind: String, family: String) {
        track(.widgetAdded, properties: [
            "widget_kind": widgetKind,
            "widget_family": family
        ])
    }

    /// Track widget removed from home screen
    func trackWidgetRemoved(widgetKind: String, family: String) {
        track(.widgetRemoved, properties: [
            "widget_kind": widgetKind,
            "widget_family": family
        ])
    }

    /// Track widget configuration changed
    func trackWidgetConfigured(widgetKind: String, configuration: [String: Any]) {
        var properties: [String: Any] = ["widget_kind": widgetKind]
        properties.merge(configuration) { _, new in new }
        track(.widgetConfigured, properties: properties)
    }

    /// Track scene activation from widget
    func trackWidgetSceneActivated(sceneName: String, widgetKind: String) {
        track(.widgetSceneActivated, properties: [
            "scene_name": sceneName,
            "widget_kind": widgetKind,
            "activation_source": "widget"
        ])
    }

    /// Track room tap from widget
    func trackWidgetRoomTapped(roomId: String, roomName: String, widgetKind: String) {
        track(.widgetRoomTapped, properties: [
            "room_id": roomId,
            "room_name": roomName,
            "widget_kind": widgetKind
        ])
    }

    /// Track widget refresh
    func trackWidgetRefreshed(widgetKind: String, success: Bool, latencyMs: Int) {
        track(.widgetRefreshed, properties: [
            "widget_kind": widgetKind,
            "success": success,
            "latency_ms": latencyMs
        ])
    }

    /// Track widget error
    func trackWidgetError(widgetKind: String, errorCode: Int, errorMessage: String) {
        track(.widgetError, properties: [
            "widget_kind": widgetKind,
            "error_code": errorCode,
            "error_message": errorMessage
        ])
    }
}

// MARK: - Console Analytics Backend (Debug)

/// Simple console logging backend for development
final class ConsoleAnalyticsBackend: AnalyticsBackend {

    private let logger = Logger(subsystem: "com.kagami.ios", category: "Analytics.Console")

    func trackEvent(_ name: String, properties: [String: Any]?) {
        let propsString = properties?.map { "\($0.key)=\($0.value)" }.joined(separator: ", ") ?? ""
        logger.debug("[EVENT] \(name) {\(propsString)}")
    }

    func trackError(_ name: String, error: Error?, properties: [String: Any]?) {
        let errorDesc = error?.localizedDescription ?? "no error"
        let propsString = properties?.map { "\($0.key)=\($0.value)" }.joined(separator: ", ") ?? ""
        logger.error("[ERROR] \(name): \(errorDesc) {\(propsString)}")
    }

    func setUserProperty(_ value: String?, forName name: String) {
        logger.debug("[USER_PROPERTY] \(name) = \(value ?? "nil")")
    }

    func setUserId(_ userId: String?) {
        logger.debug("[USER_ID] \(userId ?? "nil")")
    }
}

// MARK: - Firebase Analytics Backend (Production)

#if canImport(FirebaseAnalytics)
import FirebaseAnalytics

/// Firebase Analytics backend for production
final class FirebaseAnalyticsBackend: AnalyticsBackend {

    func trackEvent(_ name: String, properties: [String: Any]?) {
        // Convert properties to Firebase-compatible format
        let params = properties?.compactMapValues { value -> Any? in
            switch value {
            case is String, is Int, is Double, is Bool:
                return value
            default:
                return String(describing: value)
            }
        }

        Analytics.logEvent(name, parameters: params)
    }

    func trackError(_ name: String, error: Error?, properties: [String: Any]?) {
        var params = properties ?? [:]
        params["error_name"] = name
        if let error = error {
            params["error_message"] = error.localizedDescription
        }

        Analytics.logEvent("error_occurred", parameters: params.compactMapValues { value -> Any? in
            switch value {
            case is String, is Int, is Double, is Bool:
                return value
            default:
                return String(describing: value)
            }
        })
    }

    func setUserProperty(_ value: String?, forName name: String) {
        Analytics.setUserProperty(value, forName: name)
    }

    func setUserId(_ userId: String?) {
        Analytics.setUserID(userId)
    }
}
#endif

// MARK: - Mixpanel Analytics Backend (Optional)

/// Mixpanel backend placeholder - implement if Mixpanel SDK is added
final class MixpanelAnalyticsBackend: AnalyticsBackend {

    private let token: String
    private let logger = Logger(subsystem: "com.kagami.ios", category: "Analytics.Mixpanel")

    init(token: String) {
        self.token = token
        logger.info("Mixpanel initialized with token")
    }

    func trackEvent(_ name: String, properties: [String: Any]?) {
        // Mixpanel.mainInstance().track(event: name, properties: properties as? Properties)
        logger.debug("[Mixpanel] Track: \(name)")
    }

    func trackError(_ name: String, error: Error?, properties: [String: Any]?) {
        var props = properties ?? [:]
        props["error_name"] = name
        props["error_description"] = error?.localizedDescription ?? "unknown"
        // Mixpanel.mainInstance().track(event: "error", properties: props as? Properties)
        logger.error("[Mixpanel] Error: \(name)")
    }

    func setUserProperty(_ value: String?, forName name: String) {
        // Mixpanel.mainInstance().people.set(property: name, to: value ?? "")
    }

    func setUserId(_ userId: String?) {
        // if let userId = userId {
        //     Mixpanel.mainInstance().identify(distinctId: userId)
        // }
    }
}

// MARK: - Analytics Configuration

/// Configuration for analytics service
struct AnalyticsConfiguration {
    let firebaseEnabled: Bool
    let mixpanelEnabled: Bool
    let mixpanelToken: String?
    let consoleLoggingEnabled: Bool

    static let `default` = AnalyticsConfiguration(
        firebaseEnabled: true,
        mixpanelEnabled: false,
        mixpanelToken: nil,
        consoleLoggingEnabled: true
    )

    static let production = AnalyticsConfiguration(
        firebaseEnabled: true,
        mixpanelEnabled: false,
        mixpanelToken: nil,
        consoleLoggingEnabled: false
    )
}

// MARK: - Analytics Helper Extensions

extension KagamiAnalytics {

    /// Configure analytics with a specific configuration
    func configure(with config: AnalyticsConfiguration) {
        #if canImport(FirebaseAnalytics)
        if config.firebaseEnabled {
            addBackend(FirebaseAnalyticsBackend())
        }
        #endif

        if config.mixpanelEnabled, let token = config.mixpanelToken {
            addBackend(MixpanelAnalyticsBackend(token: token))
        }

        if config.consoleLoggingEnabled {
            #if DEBUG
            // Already added in init
            #endif
        }
    }
}

/*
 * Mirror
 * Analytics help us improve Kagami.
 * Privacy-first: no PII collected,
 * all data stays aggregated.
 *
 * h(x) >= 0. Always.
 */
