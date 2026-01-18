//
// KagamiLogger.swift - Unified Structured Logging
//
// Colony: Crystal (e7) - Verification
//
// Provides structured logging using os.log unified logging system.
// Replaces print() statements with proper log levels and categories.
//
// Log Levels:
//   - debug: Detailed debugging information
//   - info: General operational information
//   - notice: Notable events (default level)
//   - warning: Potential issues that may need attention
//   - error: Errors that need immediate attention
//   - fault: Critical failures
//
// Usage:
//   KagamiLogger.network.logInfo("WebSocket connected")
//   KagamiLogger.api.logError("Request failed: \(error)")
//   KagamiLogger.health.logDebug("Heart rate: \(bpm)")
//
// h(x) >= 0. Always.
//

import Foundation
import os

// MARK: - Kagami Logger

/// Simple logger wrapper for structured logging
struct KagamiLoggerCategory {
    let category: String
    private let osLog: OSLog

    init(category: String, subsystem: String = Bundle.main.bundleIdentifier ?? "com.kagami.watch") {
        self.category = category
        self.osLog = OSLog(subsystem: subsystem, category: category)
    }

    /// Log at debug level
    func logDebug(_ message: String, file: String = #file, line: Int = #line) {
        let filename = (file as NSString).lastPathComponent
        os_log(.debug, log: osLog, "%{public}@ [%{public}@:%d]", message, filename, line)
    }

    /// Log at info level
    func logInfo(_ message: String) {
        os_log(.info, log: osLog, "%{public}@", message)
    }

    /// Log at info level (convenience alias)
    func info(_ message: String) {
        os_log(.info, log: osLog, "%{public}@", message)
    }

    /// Log at notice level (default)
    func logNotice(_ message: String) {
        os_log(.default, log: osLog, "%{public}@", message)
    }

    /// Log at notice level (convenience alias)
    func notice(_ message: String) {
        os_log(.default, log: osLog, "%{public}@", message)
    }

    /// Log at warning level (uses error type)
    func logWarning(_ message: String, file: String = #file, line: Int = #line) {
        let filename = (file as NSString).lastPathComponent
        os_log(.error, log: osLog, "WARNING: %{public}@ [%{public}@:%d]", message, filename, line)
    }

    /// Log at warning level (convenience alias)
    func warning(_ message: String) {
        os_log(.error, log: osLog, "WARNING: %{public}@", message)
    }

    /// Log at error level
    func logError(_ message: String, file: String = #file, function: String = #function, line: Int = #line) {
        let filename = (file as NSString).lastPathComponent
        os_log(.error, log: osLog, "ERROR: %{public}@ [%{public}@:%{public}@:%d]", message, filename, function, line)
    }

    /// Log at error level (convenience alias)
    func error(_ message: String) {
        os_log(.error, log: osLog, "ERROR: %{public}@", message)
    }

    /// Log at fault level (critical)
    func logFault(_ message: String, file: String = #file, function: String = #function, line: Int = #line) {
        let filename = (file as NSString).lastPathComponent
        os_log(.fault, log: osLog, "FAULT: %{public}@ [%{public}@:%{public}@:%d]", message, filename, function, line)
    }

    /// Log at fault level (convenience alias)
    func fault(_ message: String) {
        os_log(.fault, log: osLog, "FAULT: %{public}@", message)
    }
}

/// Unified structured logging for the Kagami Watch app
/// Uses os.log for proper log levels, privacy, and system integration
enum KagamiLogger {

    // MARK: - Log Categories

    /// Network and WebSocket logging
    static let network = KagamiLoggerCategory(category: "network")

    /// API requests and responses
    static let api = KagamiLoggerCategory(category: "api")

    /// Authentication and security
    static let auth = KagamiLoggerCategory(category: "auth")

    /// HealthKit data and sync
    static let health = KagamiLoggerCategory(category: "health")

    /// Motion and sensor data
    static let motion = KagamiLoggerCategory(category: "motion")

    /// Watch connectivity (iPhone communication)
    static let connectivity = KagamiLoggerCategory(category: "connectivity")

    /// UI and user interactions
    static let ui = KagamiLoggerCategory(category: "ui")

    /// Voice commands and speech recognition
    static let voice = KagamiLoggerCategory(category: "voice")

    /// Background tasks and scheduling
    static let background = KagamiLoggerCategory(category: "background")

    /// Offline persistence and caching
    static let persistence = KagamiLoggerCategory(category: "persistence")

    /// Analytics and events
    static let analytics = KagamiLoggerCategory(category: "analytics")

    /// Colony and context engine
    static let context = KagamiLoggerCategory(category: "context")

    /// Complications and widgets
    static let complications = KagamiLoggerCategory(category: "complications")

    /// General/default logging
    static let general = KagamiLoggerCategory(category: "general")

    /// Watch agent-specific logging
    static let watch = KagamiLoggerCategory(category: "watch")
}

// MARK: - Signpost Support for Performance Tracking

extension KagamiLogger {
    private static let subsystem = Bundle.main.bundleIdentifier ?? "com.kagami.watch"

    /// Signpost logger for performance tracking
    static let signpost = OSSignposter(subsystem: subsystem, category: "performance")

    /// Begin a signpost interval for performance measurement
    static func beginInterval(_ name: StaticString) -> OSSignpostIntervalState {
        return signpost.beginInterval(name)
    }

    /// End a signpost interval
    static func endInterval(_ name: StaticString, _ state: OSSignpostIntervalState) {
        signpost.endInterval(name, state)
    }

    /// Emit a signpost event (instant marker)
    static func event(_ name: StaticString) {
        signpost.emitEvent(name)
    }
}

// MARK: - Migration Helper

/// Temporary helper to migrate from print() to structured logging
/// Usage: KagamiLog.info("Message") instead of print("Message")
enum KagamiLog {

    static func debug(_ message: String) {
        KagamiLogger.general.logDebug(message)
    }

    static func info(_ message: String) {
        KagamiLogger.general.info(message)
    }

    static func warning(_ message: String) {
        KagamiLogger.general.warning(message)
    }

    static func error(_ message: String) {
        KagamiLogger.general.error(message)
    }
}

/*
 * Logging Best Practices:
 *
 * 1. Use appropriate log levels:
 *    - debug: Verbose info useful only during development
 *    - info: General operational events
 *    - notice: Important events worth noting
 *    - warning: Recoverable issues
 *    - error: Non-recoverable errors
 *    - fault: Critical system failures
 *
 * 2. Use categories to filter logs:
 *    KagamiLogger.network.logInfo("...")
 *    KagamiLogger.health.logDebug("...")
 *
 * 3. Privacy: Use %{public}@ for non-sensitive data
 *    Sensitive data is redacted by default in release builds
 *
 * 4. Performance: Use signposts for measuring operations
 *    let state = KagamiLogger.beginInterval("API Call")
 *    // ... do work ...
 *    KagamiLogger.endInterval("API Call", state)
 *
 * 5. View logs: Use Console.app on Mac or Xcode console
 *    Filter by: subsystem:com.kagami.watch category:network
 *
 * h(x) >= 0. Always.
 */
