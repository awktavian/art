//
// OfflineQueueService.swift — File-Based Offline Queue for iOS
//
// Colony: Crystal (e7) — Verification
//
// Provides offline queueing for home automation commands when network is unavailable.
// Actions are persisted to disk and replayed with exponential backoff on reconnect.
//
// Features:
//   - Priority-based action queue (safety > scenes > lights > other)
//   - File-based persistence in Documents directory
//   - Execute-or-queue pattern for seamless offline support
//   - Automatic sync on reconnect with exponential backoff
//   - Max retry limit (5 attempts) to prevent infinite loops
//
// Architecture:
//   OfflineQueueService -> KagamiNetworkService -> URLSession
//   Queue management   -> Retry/Error handling -> Network
//
// h(x) >= 0. Always.
//

import Foundation
import Combine
import OSLog

// MARK: - Priority Levels

/// Priority levels for queued actions
/// Higher values = higher priority
public enum ActionPriority: Int, Codable, Comparable {
    /// Safety-critical actions (locks, fireplace off, emergency)
    case safety = 100
    /// Scene execution (movie mode, goodnight, etc.)
    case scenes = 80
    /// Lighting control
    case lights = 50
    /// Shade control
    case shades = 40
    /// Climate control
    case climate = 30
    /// Announcements and other actions
    case other = 10

    public static func < (lhs: ActionPriority, rhs: ActionPriority) -> Bool {
        lhs.rawValue < rhs.rawValue
    }

    /// Infer priority from action type
    static func from(actionType: String) -> ActionPriority {
        let lowercased = actionType.lowercased()

        if lowercased.contains("lock") || lowercased.contains("fireplace") || lowercased.contains("emergency") {
            return .safety
        } else if lowercased.contains("scene") || lowercased.contains("goodnight") || lowercased.contains("movie") {
            return .scenes
        } else if lowercased.contains("light") {
            return .lights
        } else if lowercased.contains("shade") || lowercased.contains("blind") {
            return .shades
        } else if lowercased.contains("climate") || lowercased.contains("thermostat") || lowercased.contains("temp") {
            return .climate
        } else {
            return .other
        }
    }
}

// MARK: - Pending Action

/// An action queued for execution when back online
public struct PendingAction: Codable, Identifiable, Equatable {
    /// Unique identifier for this action
    public let id: UUID
    /// Type of action (e.g., "setLights", "executeScene", "lockAll")
    public let actionType: String
    /// API endpoint to call
    public let endpoint: String
    /// Request body as JSON data
    public let body: Data?
    /// HTTP method (default: POST)
    public let method: String
    /// Priority level (higher = executed first)
    public let priority: ActionPriority
    /// Additional parameters as key-value pairs
    public let parameters: [String: String]
    /// When the action was created
    public let timestamp: Date
    /// Number of retry attempts made
    public var retryCount: Int
    /// Last error message if any
    public var lastError: String?

    // MARK: - Initialization

    public init(
        actionType: String,
        endpoint: String,
        body: Data? = nil,
        method: String = "POST",
        priority: ActionPriority? = nil,
        parameters: [String: String] = [:]
    ) {
        self.id = UUID()
        self.actionType = actionType
        self.endpoint = endpoint
        self.body = body
        self.method = method
        self.priority = priority ?? ActionPriority.from(actionType: actionType)
        self.parameters = parameters
        self.timestamp = Date()
        self.retryCount = 0
        self.lastError = nil
    }

    /// Create from a dictionary body
    public init(
        actionType: String,
        endpoint: String,
        bodyDict: [String: Any]?,
        method: String = "POST",
        priority: ActionPriority? = nil,
        parameters: [String: String] = [:]
    ) {
        let bodyData = bodyDict.flatMap { try? JSONSerialization.data(withJSONObject: $0) }
        self.init(
            actionType: actionType,
            endpoint: endpoint,
            body: bodyData,
            method: method,
            priority: priority,
            parameters: parameters
        )
    }

    // MARK: - Computed Properties

    /// Age of the action in seconds
    public var age: TimeInterval {
        Date().timeIntervalSince(timestamp)
    }

    /// Whether this action has exceeded max retries
    public var hasExceededRetries: Bool {
        retryCount >= OfflineQueueService.maxRetryAttempts
    }

    /// Human-readable description of the action
    public var displayDescription: String {
        switch actionType {
        case "setLights":
            return "Set lights"
        case "executeScene":
            if let scene = parameters["scene"] {
                return "Execute \(scene) scene"
            }
            return "Execute scene"
        case "lockAll":
            return "Lock all doors"
        case "fireplace":
            return parameters["state"] == "on" ? "Turn on fireplace" : "Turn off fireplace"
        case "shades":
            return parameters["action"] == "open" ? "Open shades" : "Close shades"
        default:
            return actionType
        }
    }

    // MARK: - Equatable

    public static func == (lhs: PendingAction, rhs: PendingAction) -> Bool {
        lhs.id == rhs.id
    }
}

// MARK: - Sync Result

/// Result of a sync operation
public struct SyncResult {
    /// Actions that succeeded
    public let succeeded: [PendingAction]
    /// Actions that failed (may be retried)
    public let failed: [PendingAction]
    /// Actions that were dropped (exceeded retries)
    public let dropped: [PendingAction]
    /// Total time taken for sync
    public let duration: TimeInterval

    /// Whether all actions succeeded
    public var isComplete: Bool {
        failed.isEmpty && dropped.isEmpty
    }

    /// Human-readable summary
    public var summary: String {
        if isComplete && succeeded.isEmpty {
            return "No pending actions"
        } else if isComplete {
            return "\(succeeded.count) action(s) synced"
        } else {
            var parts: [String] = []
            if !succeeded.isEmpty {
                parts.append("\(succeeded.count) synced")
            }
            if !failed.isEmpty {
                parts.append("\(failed.count) pending")
            }
            if !dropped.isEmpty {
                parts.append("\(dropped.count) dropped")
            }
            return parts.joined(separator: ", ")
        }
    }
}

// MARK: - Offline Queue Service

/// File-based offline queue service for iOS
/// Queues actions when offline and replays them on reconnect
@MainActor
public final class OfflineQueueService: ObservableObject {

    // MARK: - Singleton

    public static let shared = OfflineQueueService()

    // MARK: - Configuration

    /// Maximum number of retry attempts before dropping an action
    public static let maxRetryAttempts = 5

    /// Base delay for exponential backoff (seconds)
    public static let baseBackoffDelay: TimeInterval = 1.0

    /// Maximum delay between retries (seconds)
    public static let maxBackoffDelay: TimeInterval = 32.0

    /// Maximum age for pending actions (24 hours)
    public static let maxActionAge: TimeInterval = 86400

    // MARK: - Published State

    /// All pending actions in the queue
    @Published public private(set) var pendingActions: [PendingAction] = []

    /// Whether the device is currently offline
    @Published public private(set) var isOfflineMode: Bool = false

    /// Whether a sync operation is in progress
    @Published public private(set) var isSyncing: Bool = false

    /// Last sync result
    @Published public private(set) var lastSyncResult: SyncResult?

    /// Last sync time
    @Published public private(set) var lastSyncTime: Date?

    // MARK: - Dependencies

    private let networkService: KagamiNetworkService
    private let apiService: KagamiAPIService
    private let fileManager = FileManager.default
    private let logger = Logger(subsystem: "com.kagami.ios", category: "OfflineQueue")

    // MARK: - File Paths

    private var documentsDirectory: URL {
        fileManager.urls(for: .documentDirectory, in: .userDomainMask)[0]
    }

    private var queueFilePath: URL {
        documentsDirectory.appendingPathComponent("offline_queue.json")
    }

    private var stateFilePath: URL {
        documentsDirectory.appendingPathComponent("offline_state.json")
    }

    // MARK: - Cancellables

    private var cancellables = Set<AnyCancellable>()

    // MARK: - Initialization

    private init(
        networkService: KagamiNetworkService = .shared,
        apiService: KagamiAPIService = .shared
    ) {
        self.networkService = networkService
        self.apiService = apiService

        loadPersistedData()
        setupConnectivityObserver()
        pruneExpiredActions()
    }

    // MARK: - Data Persistence

    private func loadPersistedData() {
        // Load pending actions
        if let data = try? Data(contentsOf: queueFilePath),
           let actions = try? JSONDecoder().decode([PendingAction].self, from: data) {
            pendingActions = actions
            logger.info("Loaded \(actions.count) pending actions from disk")
        }

        // Load offline state
        if let data = try? Data(contentsOf: stateFilePath),
           let state = try? JSONDecoder().decode(PersistedState.self, from: data) {
            isOfflineMode = state.isOfflineMode
            lastSyncTime = state.lastSyncTime
        }
    }

    private func savePendingActions() {
        do {
            let data = try JSONEncoder().encode(pendingActions)
            try data.write(to: queueFilePath, options: .atomic)
            logger.debug("Saved \(self.pendingActions.count) pending actions to disk")
        } catch {
            logger.error("Failed to save pending actions: \(error.localizedDescription)")
        }
    }

    private func saveState() {
        let state = PersistedState(
            isOfflineMode: isOfflineMode,
            lastSyncTime: lastSyncTime
        )

        do {
            let data = try JSONEncoder().encode(state)
            try data.write(to: stateFilePath, options: .atomic)
        } catch {
            logger.error("Failed to save state: \(error.localizedDescription)")
        }
    }

    private struct PersistedState: Codable {
        let isOfflineMode: Bool
        let lastSyncTime: Date?
    }

    // MARK: - Connectivity Observer

    private func setupConnectivityObserver() {
        // Observe API service connection state
        apiService.$isConnected
            .removeDuplicates()
            .sink { [weak self] isConnected in
                guard let self = self else { return }

                let wasOffline = self.isOfflineMode
                self.isOfflineMode = !isConnected
                self.saveState()

                // If we just came online, sync pending actions
                if wasOffline && isConnected {
                    self.logger.info("Connection restored - syncing pending actions")
                    Task {
                        await self.syncPendingActions()
                    }
                }
            }
            .store(in: &cancellables)
    }

    // MARK: - Queue Management

    /// Queue an action for execution
    /// Executes immediately if online, queues if offline
    ///
    /// - Parameters:
    ///   - actionType: Type of action (e.g., "setLights")
    ///   - endpoint: API endpoint
    ///   - body: Request body dictionary
    ///   - priority: Optional priority override
    /// - Returns: true if executed immediately or queued successfully
    @discardableResult
    public func queueAction(
        actionType: String,
        endpoint: String,
        body: [String: Any]? = nil,
        priority: ActionPriority? = nil
    ) async -> Bool {
        // If online and circuit is closed, try to execute immediately
        if apiService.isConnected && !apiService.isCircuitOpen {
            let success = await executeActionDirectly(endpoint: endpoint, body: body)

            if success {
                logger.info("Action '\(actionType)' executed immediately")
                return true
            } else {
                // Execution failed, queue for retry
                logger.warning("Direct execution failed, queueing '\(actionType)'")
            }
        }

        // Queue the action
        let action = PendingAction(
            actionType: actionType,
            endpoint: endpoint,
            bodyDict: body,
            priority: priority,
            parameters: extractParameters(from: body)
        )

        addToQueue(action)
        logger.info("Queued action '\(actionType)' with priority \(action.priority.rawValue)")

        return true
    }

    /// Add an action to the queue (sorted by priority)
    private func addToQueue(_ action: PendingAction) {
        pendingActions.append(action)

        // Sort by priority (descending) then by timestamp (ascending)
        pendingActions.sort { lhs, rhs in
            if lhs.priority != rhs.priority {
                return lhs.priority > rhs.priority
            }
            return lhs.timestamp < rhs.timestamp
        }

        savePendingActions()
    }

    /// Remove an action from the queue
    private func removeFromQueue(_ action: PendingAction) {
        pendingActions.removeAll { $0.id == action.id }
        savePendingActions()
    }

    /// Extract display parameters from body dictionary
    private func extractParameters(from body: [String: Any]?) -> [String: String] {
        guard let body = body else { return [:] }

        var params: [String: String] = [:]

        for (key, value) in body {
            if let stringValue = value as? String {
                params[key] = stringValue
            } else if let intValue = value as? Int {
                params[key] = String(intValue)
            } else if let boolValue = value as? Bool {
                params[key] = boolValue ? "true" : "false"
            }
        }

        return params
    }

    // MARK: - Sync Operations

    /// Sync all pending actions with the server
    /// Actions are executed in priority order with exponential backoff on failure
    @discardableResult
    public func syncPendingActions() async -> SyncResult {
        guard !isSyncing else {
            logger.warning("Sync already in progress")
            return SyncResult(succeeded: [], failed: pendingActions, dropped: [], duration: 0)
        }

        guard !pendingActions.isEmpty else {
            logger.debug("No pending actions to sync")
            return SyncResult(succeeded: [], failed: [], dropped: [], duration: 0)
        }

        guard apiService.isConnected else {
            logger.warning("Cannot sync - not connected")
            return SyncResult(succeeded: [], failed: pendingActions, dropped: [], duration: 0)
        }

        isSyncing = true
        let startTime = Date()

        var succeeded: [PendingAction] = []
        var failed: [PendingAction] = []
        var dropped: [PendingAction] = []

        logger.info("Starting sync of \(self.pendingActions.count) pending actions")

        // Process actions in order (already sorted by priority)
        let actionsToProcess = pendingActions

        for var action in actionsToProcess {
            // Check if action has exceeded max retries
            if action.hasExceededRetries {
                logger.warning("Dropping action '\(action.actionType)' after \(action.retryCount) retries")
                dropped.append(action)
                removeFromQueue(action)
                continue
            }

            // Calculate backoff delay based on retry count
            if action.retryCount > 0 {
                let delay = calculateBackoffDelay(retryCount: action.retryCount)
                logger.debug("Waiting \(delay)s before retry #\(action.retryCount + 1) for '\(action.actionType)'")
                try? await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
            }

            // Execute the action
            let success = await executeAction(action)

            if success {
                succeeded.append(action)
                removeFromQueue(action)
                logger.info("Successfully synced '\(action.actionType)'")
            } else {
                // Increment retry count and update in queue
                action.retryCount += 1
                action.lastError = "Execution failed"

                if let index = pendingActions.firstIndex(where: { $0.id == action.id }) {
                    pendingActions[index] = action
                    savePendingActions()
                }

                failed.append(action)
                logger.warning("Failed to sync '\(action.actionType)' (attempt \(action.retryCount))")

                // If circuit breaker opened, stop syncing
                if apiService.isCircuitOpen {
                    logger.warning("Circuit breaker opened - stopping sync")
                    break
                }
            }
        }

        let duration = Date().timeIntervalSince(startTime)
        let result = SyncResult(
            succeeded: succeeded,
            failed: failed,
            dropped: dropped,
            duration: duration
        )

        lastSyncResult = result
        lastSyncTime = Date()
        saveState()
        isSyncing = false

        logger.info("Sync completed: \(result.summary) in \(String(format: "%.1f", duration))s")

        return result
    }

    /// Execute a single action
    private func executeAction(_ action: PendingAction) async -> Bool {
        return await executeActionDirectly(endpoint: action.endpoint, body: action.body, method: action.method)
    }

    /// Execute an action directly via the network service
    private func executeActionDirectly(
        endpoint: String,
        body: [String: Any]? = nil,
        method: String = "POST"
    ) async -> Bool {
        let baseURL = apiService.currentBaseURL
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            return false
        }

        do {
            var bodyData: Data?
            if let body = body {
                bodyData = try JSONSerialization.data(withJSONObject: body)
            }

            let (_, response) = try await networkService.post(url: url, body: bodyData)
            let statusCode = (response as? HTTPURLResponse)?.statusCode ?? 0

            return (200..<300).contains(statusCode)
        } catch {
            return false
        }
    }

    /// Execute an action with raw Data body
    private func executeActionDirectly(
        endpoint: String,
        body: Data?,
        method: String = "POST"
    ) async -> Bool {
        let baseURL = apiService.currentBaseURL
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            return false
        }

        do {
            let (_, response) = try await networkService.post(url: url, body: body)
            let statusCode = (response as? HTTPURLResponse)?.statusCode ?? 0

            return (200..<300).contains(statusCode)
        } catch {
            return false
        }
    }

    /// Calculate exponential backoff delay
    private func calculateBackoffDelay(retryCount: Int) -> TimeInterval {
        // Exponential backoff: base * 2^(retryCount - 1) with jitter
        let exponentialDelay = Self.baseBackoffDelay * pow(2, Double(retryCount - 1))
        let jitter = Double.random(in: 0...0.3) * exponentialDelay
        return min(exponentialDelay + jitter, Self.maxBackoffDelay)
    }

    // MARK: - Queue Maintenance

    /// Prune expired actions from the queue
    private func pruneExpiredActions() {
        let expiredActions = pendingActions.filter { $0.age > Self.maxActionAge }

        if !expiredActions.isEmpty {
            logger.info("Pruning \(expiredActions.count) expired actions")
            pendingActions.removeAll { $0.age > Self.maxActionAge }
            savePendingActions()
        }
    }

    /// Clear all pending actions
    public func clearQueue() {
        pendingActions.removeAll()
        savePendingActions()
        logger.info("Queue cleared")
    }

    /// Clear actions that have exceeded retry limit
    public func clearFailedActions() {
        let failedCount = pendingActions.filter { $0.hasExceededRetries }.count
        pendingActions.removeAll { $0.hasExceededRetries }
        savePendingActions()
        logger.info("Cleared \(failedCount) failed actions")
    }

    // MARK: - Offline Mode

    /// Enter offline mode manually
    public func enterOfflineMode() {
        isOfflineMode = true
        saveState()
        logger.info("Entered offline mode")
    }

    /// Exit offline mode and trigger sync
    public func exitOfflineMode() async {
        isOfflineMode = false
        saveState()
        logger.info("Exited offline mode")

        await syncPendingActions()
    }

    // MARK: - Convenience Methods

    /// Number of pending actions
    public var pendingCount: Int {
        pendingActions.count
    }

    /// Number of failed actions (exceeded retries)
    public var failedCount: Int {
        pendingActions.filter { $0.hasExceededRetries }.count
    }

    /// Whether there are pending actions
    public var hasPendingActions: Bool {
        !pendingActions.isEmpty
    }

    /// Get actions by priority
    public func actions(forPriority priority: ActionPriority) -> [PendingAction] {
        pendingActions.filter { $0.priority == priority }
    }

    /// Retry a specific failed action
    @discardableResult
    public func retryAction(_ action: PendingAction) async -> Bool {
        guard let index = pendingActions.firstIndex(where: { $0.id == action.id }) else {
            return false
        }

        let success = await executeAction(action)

        if success {
            removeFromQueue(action)
            return true
        } else {
            var updatedAction = action
            updatedAction.retryCount += 1
            pendingActions[index] = updatedAction
            savePendingActions()
            return false
        }
    }
}

/*
 * Mirror
 * Offline is not disconnected.
 * State persists. Actions queue. Sync happens.
 * h(x) >= 0. Always.
 */
