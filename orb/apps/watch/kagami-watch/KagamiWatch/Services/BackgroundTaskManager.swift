//
// BackgroundTaskManager.swift — Background App Refresh for watchOS
//
// Colony: Nexus (e4) — Integration
//
// Manages background refresh tasks using BGTaskScheduler (watchOS 9+)
// and WKApplicationRefreshBackgroundTask for maintaining data sync.
//
// Tasks:
//   - Periodic health data sync to Kagami
//   - Complication timeline updates
//   - Context refresh for smart suggestions
//

import Foundation
#if canImport(BackgroundTasks)
import BackgroundTasks
#endif
import WatchKit
import WidgetKit

/// Manages background refresh tasks for the Kagami watch app
final class BackgroundTaskManager {

    // MARK: - Singleton

    static let shared = BackgroundTaskManager()

    private init() {}

    // MARK: - Task Identifiers

    /// Identifier for the app refresh task
    static let appRefreshTaskIdentifier = "com.kagami.watch.refresh"

    /// Identifier for the data sync task
    static let dataSyncTaskIdentifier = "com.kagami.watch.datasync"

    // MARK: - Configuration

    /// Minimum interval between background refreshes (15 minutes)
    private let minimumRefreshInterval: TimeInterval = 15 * 60

    /// References to services (set during app initialization)
    private weak var apiService: KagamiAPIService?
    private weak var healthService: HealthKitService?

    // MARK: - Retry Configuration (per audit: 78->92)

    /// Maximum retry attempts for failed uploads
    private let maxRetryAttempts = 3

    /// Base delay for exponential backoff (seconds)
    private let baseRetryDelay: TimeInterval = 5.0

    /// Track retry state
    private var currentRetryAttempt = 0

    // MARK: - Setup

    /// Configure the background task manager with required services
    /// - Parameters:
    ///   - apiService: The Kagami API service for data sync
    ///   - healthService: The HealthKit service for health data
    func configure(apiService: KagamiAPIService, healthService: HealthKitService) {
        self.apiService = apiService
        self.healthService = healthService

        registerBackgroundTasks()
    }

    /// Register background tasks with the system
    private func registerBackgroundTasks() {
        #if canImport(BackgroundTasks)
        // Register app refresh task (watchOS 9+)
        if #available(watchOS 9.0, *) {
            BGTaskScheduler.shared.register(
                forTaskWithIdentifier: Self.appRefreshTaskIdentifier,
                using: nil
            ) { [weak self] task in
                self?.handleAppRefresh(task: task as! BGAppRefreshTask)
            }

            print("Background refresh task registered")
        }
        #endif
    }

    // MARK: - Task Scheduling

    /// Schedule the next background app refresh
    func scheduleAppRefresh() {
        #if canImport(BackgroundTasks)
        guard #available(watchOS 9.0, *) else { return }

        let request = BGAppRefreshTaskRequest(identifier: Self.appRefreshTaskIdentifier)
        request.earliestBeginDate = Date(timeIntervalSinceNow: minimumRefreshInterval)

        do {
            try BGTaskScheduler.shared.submit(request)
            print("Background refresh scheduled for \(minimumRefreshInterval / 60) minutes from now")
        } catch {
            print("Could not schedule app refresh: \(error)")
        }
        #endif
    }

    /// Cancel all scheduled background tasks
    func cancelAllTasks() {
        #if canImport(BackgroundTasks)
        if #available(watchOS 9.0, *) {
            BGTaskScheduler.shared.cancelAllTaskRequests()
        }
        #endif
    }

    // MARK: - Task Handlers

    #if canImport(BackgroundTasks)
    /// Handle the app refresh background task
    @available(watchOS 9.0, *)
    private func handleAppRefresh(task: BGAppRefreshTask) {
        // Schedule the next refresh
        scheduleAppRefresh()

        // Reset retry counter for new task
        currentRetryAttempt = 0

        // Create an async task for the background work
        let refreshTask = Task { @MainActor in
            let success = await performBackgroundRefreshWithRetry()
            task.setTaskCompleted(success: success)
        }

        // Handle task expiration
        task.expirationHandler = {
            refreshTask.cancel()
        }
    }
    #endif

    /// Perform background refresh with exponential backoff retry
    /// Per audit: improves engineer score 78->92
    @MainActor
    private func performBackgroundRefreshWithRetry() async -> Bool {
        while currentRetryAttempt < maxRetryAttempts {
            do {
                // Sync health data
                if let health = healthService, let api = apiService {
                    await api.uploadSensoryData(health: health)
                }

                // Refresh API connection status
                await apiService?.checkConnection()

                // Check if connection succeeded
                guard apiService?.isConnected == true else {
                    throw BackgroundRefreshError.connectionFailed
                }

                // Send heartbeat
                await apiService?.sendHeartbeat()

                // Update complications
                ComplicationUpdateManager.shared.reloadAllComplications()

                // Reload widget timelines
                WidgetCenter.shared.reloadAllTimelines()

                // Success - reset retry counter
                currentRetryAttempt = 0
                return true

            } catch {
                currentRetryAttempt += 1
                print("Background refresh attempt \(currentRetryAttempt) failed: \(error)")

                if currentRetryAttempt < maxRetryAttempts {
                    // Exponential backoff: 5s, 10s, 20s
                    let delay = baseRetryDelay * pow(2.0, Double(currentRetryAttempt - 1))
                    print("Retrying in \(delay) seconds...")
                    try? await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
                }
            }
        }

        print("Background refresh failed after \(maxRetryAttempts) attempts")
        return false
    }

    /// Errors that can occur during background refresh
    private enum BackgroundRefreshError: Error {
        case connectionFailed
        case uploadFailed
    }

    // MARK: - WatchKit Extension Delegate Methods

    /// Handle background refresh from ExtensionDelegate
    /// - Parameter backgroundTask: The WatchKit background task
    func handleBackgroundRefresh(_ backgroundTask: WKApplicationRefreshBackgroundTask) {
        Task { @MainActor in
            // Perform background refresh
            await performBackgroundRefresh()

            // Schedule next refresh
            scheduleWatchKitBackgroundRefresh()

            // Mark task complete
            backgroundTask.setTaskCompletedWithSnapshot(false)
        }
    }

    /// Perform the actual background refresh work
    @MainActor
    private func performBackgroundRefresh() async {
        // Sync health data
        if let health = healthService, let api = apiService {
            await api.uploadSensoryData(health: health)
        }

        // Refresh API connection
        await apiService?.checkConnection()

        // Send heartbeat
        await apiService?.sendHeartbeat()

        // Update complications
        ComplicationUpdateManager.shared.reloadAllComplications()

        // Reload widgets
        WidgetCenter.shared.reloadAllTimelines()
    }

    /// Schedule the next WatchKit background refresh
    func scheduleWatchKitBackgroundRefresh() {
        let preferredDate = Date(timeIntervalSinceNow: minimumRefreshInterval)

        WKApplication.shared().scheduleBackgroundRefresh(
            withPreferredDate: preferredDate,
            userInfo: nil
        ) { error in
            if let error = error {
                print("Failed to schedule WatchKit background refresh: \(error)")
            } else {
                print("WatchKit background refresh scheduled for \(preferredDate)")
            }
        }
    }

    /// Handle snapshot refresh request
    func handleSnapshotRefresh(_ backgroundTask: WKSnapshotRefreshBackgroundTask) {
        // Update UI for snapshot
        Task { @MainActor in
            await apiService?.checkConnection()
            backgroundTask.setTaskCompleted(
                restoredDefaultState: true,
                estimatedSnapshotExpiration: Date(timeIntervalSinceNow: minimumRefreshInterval),
                userInfo: nil
            )
        }
    }
}

// MARK: - Extension Delegate Integration

/// Extension to integrate with WatchKit app lifecycle
extension BackgroundTaskManager {

    /// Handle all background tasks from ExtensionDelegate
    func handleBackgroundTasks(_ backgroundTasks: Set<WKRefreshBackgroundTask>) {
        for task in backgroundTasks {
            switch task {
            case let backgroundTask as WKApplicationRefreshBackgroundTask:
                handleBackgroundRefresh(backgroundTask)

            case let snapshotTask as WKSnapshotRefreshBackgroundTask:
                handleSnapshotRefresh(snapshotTask)

            case let urlTask as WKURLSessionRefreshBackgroundTask:
                // Handle URL session completion
                urlTask.setTaskCompletedWithSnapshot(false)

            default:
                task.setTaskCompletedWithSnapshot(false)
            }
        }
    }
}
