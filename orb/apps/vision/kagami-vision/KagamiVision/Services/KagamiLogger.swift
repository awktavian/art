//
// KagamiLogger.swift - Unified Logging Service for visionOS
//
// Colony: Crystal (e7) - Verification
//
// Features:
//   - Unified logging using os.Logger
//   - Subsystem-based categorization
//   - Privacy-aware logging
//   - Debug vs Release configuration
//   - Performance metrics logging
//
// Architecture:
//   KagamiLogger -> os.Logger -> Console.app / Instruments
//
// h(x) >= 0. Always.
//
// Created: January 2, 2026

import Foundation
import os.log

// MARK: - Logger Subsystems

/// Centralized logging for Kagami Vision
enum KagamiLogger {

    // MARK: - Subsystems

    /// Hand tracking and gesture recognition
    static let handTracking = Logger(subsystem: "com.kagami.vision", category: "HandTracking")

    /// Gaze/eye tracking
    static let gazeTracking = Logger(subsystem: "com.kagami.vision", category: "GazeTracking")

    /// Spatial anchors and world tracking
    static let spatialAnchor = Logger(subsystem: "com.kagami.vision", category: "SpatialAnchor")

    /// Spatial audio (PHASE engine)
    static let spatialAudio = Logger(subsystem: "com.kagami.vision", category: "SpatialAudio")

    /// Network and API communication
    static let network = Logger(subsystem: "com.kagami.vision", category: "Network")

    /// HealthKit integration
    static let healthKit = Logger(subsystem: "com.kagami.vision", category: "HealthKit")

    /// SharePlay and collaboration
    static let sharePlay = Logger(subsystem: "com.kagami.vision", category: "SharePlay")

    /// UI and navigation
    static let ui = Logger(subsystem: "com.kagami.vision", category: "UI")

    /// ECS and RealityKit
    static let ecs = Logger(subsystem: "com.kagami.vision", category: "ECS")

    /// App lifecycle
    static let app = Logger(subsystem: "com.kagami.vision", category: "App")

    /// Performance and metrics
    static let performance = Logger(subsystem: "com.kagami.vision", category: "Performance")

    /// Thermal management
    static let thermal = Logger(subsystem: "com.kagami.vision", category: "Thermal")

    /// Analytics
    static let analytics = Logger(subsystem: "com.kagami.vision", category: "Analytics")

    /// Gesture complexity
    static let gestureComplexity = Logger(subsystem: "com.kagami.vision", category: "GestureComplexity")

    /// Security
    static let security = Logger(subsystem: "com.kagami.vision", category: "Security")

    /// Haptics
    static let haptics = Logger(subsystem: "com.kagami.vision", category: "Haptics")

    // MARK: - Convenience Methods

    /// Log service initialization status
    static func logServiceInit(_ service: String, success: Bool, logger: Logger) {
        if success {
            logger.info("\(service, privacy: .public) initialized successfully")
        } else {
            logger.error("\(service, privacy: .public) initialization failed")
        }
    }

    /// Log service availability
    static func logServiceAvailability(_ service: String, available: Bool, logger: Logger) {
        logger.info("\(service, privacy: .public): \(available ? "available" : "unavailable", privacy: .public)")
    }

    /// Log ARKit authorization change
    static func logAuthorizationChange(_ type: String, status: String, logger: Logger) {
        logger.info("Authorization changed - \(type, privacy: .public): \(status, privacy: .public)")
    }

    /// Log error with context
    static func logError(_ message: String, error: Error, logger: Logger) {
        logger.error("\(message, privacy: .public): \(error.localizedDescription, privacy: .public)")
    }

    /// Log frame budget warning (performance)
    static func logFrameBudgetExceeded(frameTime: Float, budget: Float) {
        performance.warning("Frame budget exceeded: \(frameTime, format: .fixed(precision: 2))ms (budget: \(budget, format: .fixed(precision: 2))ms)")
    }

    /// Log thermal state change
    static func logThermalChange(from oldState: String, to newState: String) {
        thermal.notice("Thermal state changed: \(oldState, privacy: .public) -> \(newState, privacy: .public)")
    }
}

// MARK: - Logger Extensions

extension Logger {

    /// Log with privacy-safe message
    func info(_ message: String) {
        self.info("\(message, privacy: .public)")
    }

    /// Log warning with privacy-safe message
    func warning(_ message: String) {
        self.warning("\(message, privacy: .public)")
    }

    /// Log error with privacy-safe message
    func error(_ message: String) {
        self.error("\(message, privacy: .public)")
    }

    /// Log notice with privacy-safe message
    func notice(_ message: String) {
        self.notice("\(message, privacy: .public)")
    }

    /// Log debug with privacy-safe message (only in DEBUG builds)
    func debug(_ message: String) {
        #if DEBUG
        self.debug("\(message, privacy: .public)")
        #endif
    }
}

/*
 * Kagami Logger
 *
 * All logging flows through os.Logger for proper:
 *   - Console.app integration
 *   - Instruments profiling
 *   - Privacy controls
 *   - Log level filtering
 *   - Production-safe output
 *
 * h(x) >= 0. Always.
 */
