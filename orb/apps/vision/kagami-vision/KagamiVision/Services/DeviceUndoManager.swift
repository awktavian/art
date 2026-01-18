//
// DeviceUndoManager.swift
// KagamiVision
//
// Undo support for device actions in visionOS.
// Allows users to quickly revert accidental changes.
//
// Features:
//   - Undo stack for recent device actions
//   - Automatic cleanup of old actions
//   - Spatial notification for undo availability
//   - Shake gesture support (via hand tracking)
//   - Localized error messages
//

import Foundation
import Combine
import SwiftUI

// MARK: - Device Action

struct DeviceAction: Identifiable {
    let id: UUID
    let timestamp: Date
    let type: ActionType
    let previousState: ActionState
    let newState: ActionState

    enum ActionType {
        case lights
        case shades
        case fireplace
        case scene
        case lock
    }

    struct ActionState: Codable {
        var lightLevel: Int?
        var shadePosition: Int?
        var fireplaceOn: Bool?
        var sceneName: String?
        var roomIds: [String]?
    }

    var description: String {
        switch type {
        case .lights:
            let level = newState.lightLevel ?? 0
            if let rooms = newState.roomIds, !rooms.isEmpty {
                return "Set \(rooms.joined(separator: ", ")) lights to \(level)%"
            }
            return "Set all lights to \(level)%"
        case .shades:
            let position = newState.shadePosition ?? 0
            return "Set shades to \(position)%"
        case .fireplace:
            let state = newState.fireplaceOn ?? false
            return "Turned fireplace \(state ? "on" : "off")"
        case .scene:
            return "Activated \(newState.sceneName ?? "scene")"
        case .lock:
            return "Locked doors"
        }
    }

    var undoDescription: String {
        switch type {
        case .lights:
            let level = previousState.lightLevel ?? 0
            return "Restore lights to \(level)%"
        case .shades:
            let position = previousState.shadePosition ?? 0
            return "Restore shades to \(position)%"
        case .fireplace:
            let state = previousState.fireplaceOn ?? false
            return "Turn fireplace \(state ? "on" : "off")"
        case .scene:
            return "Undo \(newState.sceneName ?? "scene")"
        case .lock:
            return "Unlock doors"
        }
    }
}

// MARK: - Device Undo Manager

@MainActor
class DeviceUndoManager: ObservableObject {

    // MARK: - Published State

    @Published var canUndo = false
    @Published var lastAction: DeviceAction?
    @Published var undoStack: [DeviceAction] = []

    // Time window for undo availability (30 seconds)
    private let undoWindow: TimeInterval = 30.0

    // Maximum undo stack size
    private let maxStackSize = 10

    // API Service reference
    private weak var apiService: KagamiAPIService?

    // Cleanup timer
    private var cleanupTimer: Timer?

    // MARK: - Init

    init(apiService: KagamiAPIService? = nil) {
        self.apiService = apiService
        startCleanupTimer()
    }

    func setAPIService(_ service: KagamiAPIService) {
        self.apiService = service
    }

    // MARK: - Recording Actions

    /// Records a lights action for potential undo
    func recordLightsAction(previousLevel: Int, newLevel: Int, rooms: [String]? = nil) {
        let action = DeviceAction(
            id: UUID(),
            timestamp: Date(),
            type: .lights,
            previousState: DeviceAction.ActionState(lightLevel: previousLevel, roomIds: rooms),
            newState: DeviceAction.ActionState(lightLevel: newLevel, roomIds: rooms)
        )
        pushAction(action)
    }

    /// Records a shades action for potential undo
    func recordShadesAction(previousPosition: Int, newPosition: Int, rooms: [String]? = nil) {
        let action = DeviceAction(
            id: UUID(),
            timestamp: Date(),
            type: .shades,
            previousState: DeviceAction.ActionState(shadePosition: previousPosition, roomIds: rooms),
            newState: DeviceAction.ActionState(shadePosition: newPosition, roomIds: rooms)
        )
        pushAction(action)
    }

    /// Records a fireplace action for potential undo
    func recordFireplaceAction(wasOn: Bool, isNowOn: Bool) {
        let action = DeviceAction(
            id: UUID(),
            timestamp: Date(),
            type: .fireplace,
            previousState: DeviceAction.ActionState(fireplaceOn: wasOn),
            newState: DeviceAction.ActionState(fireplaceOn: isNowOn)
        )
        pushAction(action)
    }

    /// Records a scene activation for potential undo
    func recordSceneAction(sceneName: String, previousLightLevels: [String: Int]?) {
        let action = DeviceAction(
            id: UUID(),
            timestamp: Date(),
            type: .scene,
            previousState: DeviceAction.ActionState(sceneName: "previous"),
            newState: DeviceAction.ActionState(sceneName: sceneName)
        )
        pushAction(action)
    }

    private func pushAction(_ action: DeviceAction) {
        undoStack.insert(action, at: 0)

        // Limit stack size
        if undoStack.count > maxStackSize {
            undoStack = Array(undoStack.prefix(maxStackSize))
        }

        lastAction = action
        canUndo = true
    }

    // MARK: - Undo Execution

    /// Undoes the most recent action
    func undo() async -> Bool {
        guard let action = undoStack.first,
              Date().timeIntervalSince(action.timestamp) < undoWindow else {
            canUndo = false
            return false
        }

        // Remove from stack
        undoStack.removeFirst()

        // Execute undo
        let success = await executeUndo(action)

        // Update state
        lastAction = undoStack.first
        canUndo = !undoStack.isEmpty && undoStack.first.map {
            Date().timeIntervalSince($0.timestamp) < undoWindow
        } ?? false

        return success
    }

    private func executeUndo(_ action: DeviceAction) async -> Bool {
        guard let apiService = apiService else { return false }

        switch action.type {
        case .lights:
            if let level = action.previousState.lightLevel {
                await apiService.setLights(level, rooms: action.previousState.roomIds)
                return true
            }

        case .shades:
            if let position = action.previousState.shadePosition {
                let shadeAction = position > 50 ? "open" : "close"
                await apiService.controlShades(shadeAction, rooms: action.previousState.roomIds)
                return true
            }

        case .fireplace:
            if let wasOn = action.previousState.fireplaceOn {
                // Need to set it back to previous state
                if apiService.fireplaceOn != wasOn {
                    await apiService.toggleFireplace()
                }
                return true
            }

        case .scene:
            // Scene undo is more complex - would need to restore previous state
            // Provide feedback to user about why undo failed
            lastUndoError = .sceneUndoNotSupported
            return false

        case .lock:
            // Cannot undo lock for safety reasons
            lastUndoError = .lockUndoNotAllowed
            return false
        }

        return false
    }

    // MARK: - Undo Error Handling

    /// The last undo error, if any
    @Published var lastUndoError: UndoError?

    /// Errors that can occur during undo operations
    enum UndoError: LocalizedError {
        case sceneUndoNotSupported
        case lockUndoNotAllowed
        case undoWindowExpired
        case noApiService

        var errorDescription: String? {
            switch self {
            case .sceneUndoNotSupported:
                return String(localized: "undo.failure.scene", defaultValue: "Cannot undo scene - previous state not saved")
            case .lockUndoNotAllowed:
                return String(localized: "undo.failure.lock", defaultValue: "Cannot undo lock for safety reasons")
            case .undoWindowExpired:
                return String(localized: "undo.failure.expired", defaultValue: "Undo window expired")
            case .noApiService:
                return String(localized: "undo.failure.no_service", defaultValue: "Home control service unavailable")
            }
        }

        var recoverySuggestion: String? {
            switch self {
            case .sceneUndoNotSupported:
                return "Manually adjust devices to restore previous state."
            case .lockUndoNotAllowed:
                return "Use the lock controls directly to unlock if needed."
            case .undoWindowExpired:
                return "Actions can only be undone within 30 seconds."
            case .noApiService:
                return "Check your network connection and try again."
            }
        }
    }

    /// Clears the last error
    func clearError() {
        lastUndoError = nil
    }

    // MARK: - Cleanup

    private func startCleanupTimer() {
        cleanupTimer = Timer.scheduledTimer(withTimeInterval: 5.0, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in
                self?.cleanupExpiredActions()
            }
        }
    }

    private func cleanupExpiredActions() {
        let now = Date()
        undoStack.removeAll { now.timeIntervalSince($0.timestamp) > undoWindow }

        // Update canUndo
        if let first = undoStack.first {
            canUndo = now.timeIntervalSince(first.timestamp) < undoWindow
        } else {
            canUndo = false
        }

        lastAction = undoStack.first
    }

    /// Clears all undo history
    func clearHistory() {
        undoStack.removeAll()
        lastAction = nil
        canUndo = false
    }

    deinit {
        cleanupTimer?.invalidate()
    }
}

// MARK: - Undo Banner View

struct UndoBannerView: View {
    @ObservedObject var undoManager: DeviceUndoManager
    @State private var showingError = false

    var body: some View {
        VStack(spacing: 8) {
            // Error alert
            if let error = undoManager.lastUndoError {
                HStack(spacing: 12) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundColor(.orange)

                    VStack(alignment: .leading, spacing: 2) {
                        Text(error.localizedDescription)
                            .font(.system(size: 14, weight: .medium))
                        if let suggestion = error.recoverySuggestion {
                            Text(suggestion)
                                .font(.system(size: 12))
                                .foregroundColor(.secondary)
                        }
                    }

                    Spacer()

                    Button(action: {
                        undoManager.clearError()
                    }) {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundColor(.secondary)
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel(String(localized: "common.dismiss", defaultValue: "Dismiss"))
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 12)
                .background(Color.orange.opacity(0.15))
                .cornerRadius(12)
                .transition(.move(edge: .top).combined(with: .opacity))
            }

            // Undo banner
            if undoManager.canUndo, let action = undoManager.lastAction {
                HStack(spacing: 12) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(action.description)
                            .font(.system(size: 14, weight: .medium))
                        Text(String(localized: "undo.banner.tap_to_undo", defaultValue: "Tap to undo"))
                            .font(.system(size: 12))
                            .foregroundColor(.secondary)
                    }

                    Spacer()

                    Button(action: {
                        Task {
                            _ = await undoManager.undo()
                        }
                    }) {
                        Text(String(localized: "undo.button.undo", defaultValue: "Undo"))
                            .font(.system(size: 14, weight: .semibold))
                            .foregroundColor(.crystal)
                    }
                    .frame(minWidth: 60, minHeight: 44)
                    .contentShape(.hoverEffect, .capsule)
                    .hoverEffect(.lift)
                    .buttonStyle(.plain)
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 12)
                .glassBackgroundEffect()
                .transition(.move(edge: .bottom).combined(with: .opacity))
            }
        }
        .animation(.spring(response: 0.377, dampingFraction: 0.8), value: undoManager.canUndo)  // 377ms Fibonacci
        .animation(.spring(response: 0.377, dampingFraction: 0.8), value: undoManager.lastUndoError != nil)
        .accessibilityElement(children: .combine)
        .accessibilityLabel(undoManager.lastAction?.undoDescription ?? "")
        .accessibilityAddTraits(.isButton)
    }
}

/*
 * Device undo allows quick reversal of accidental actions.
 * Actions expire after 30 seconds for safety.
 * Critical actions like locks cannot be undone.
 */
