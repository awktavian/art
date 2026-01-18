//
// SharePlayService.swift
// KagamiVision
//
// SharePlay support for household collaboration in visionOS 2.
// Enables multiple Vision Pro users to control the home together.
//
// Features:
//   - Shared home control sessions
//   - Real-time device state synchronization
//   - Collaborative scene activation
//   - Spatial presence indicators for other users
//

import Foundation
import GroupActivities
import Combine
import SwiftUI

// MARK: - Home Control Activity

struct HomeControlActivity: GroupActivity {
    static let activityIdentifier = "com.kagami.vision.homecontrol"

    var metadata: GroupActivityMetadata {
        var metadata = GroupActivityMetadata()
        metadata.title = "Kagami Home Control"
        metadata.subtitle = "Control your smart home together"
        metadata.type = .generic
        metadata.previewImage = nil
        return metadata
    }
}

// MARK: - Shared Home State

struct SharedHomeState: Codable {
    let senderId: String
    let timestamp: Date
    let action: HomeAction

    enum HomeAction: Codable {
        case setLights(level: Int, room: String?)
        case activateScene(name: String)
        case toggleFireplace
        case controlShades(action: String, room: String?)
        case selectRoom(roomId: String)
        case deselectRoom

        var description: String {
            switch self {
            case .setLights(let level, let room):
                if let room = room {
                    return "Set \(room) lights to \(level)%"
                }
                return "Set all lights to \(level)%"
            case .activateScene(let name):
                return "Activated \(name)"
            case .toggleFireplace:
                return "Toggled fireplace"
            case .controlShades(let action, let room):
                if let room = room {
                    return "\(action.capitalized) \(room) shades"
                }
                return "\(action.capitalized) all shades"
            case .selectRoom(let roomId):
                return "Selected \(roomId)"
            case .deselectRoom:
                return "Deselected room"
            }
        }

        /// Returns the action category for role-based access control
        var category: SharePlayRole.ActionCategory {
            switch self {
            case .setLights:
                return .lights
            case .activateScene:
                return .scenes
            case .toggleFireplace:
                return .fireplace
            case .controlShades:
                return .shades
            case .selectRoom, .deselectRoom:
                return .lights  // Room selection is low-risk
            }
        }

        /// Whether this action reveals sensitive home state
        var isSensitive: Bool {
            switch self {
            case .toggleFireplace:
                return true
            default:
                return false
            }
        }
    }
}

// MARK: - Participant Roles & Privacy

/// Defines access levels for SharePlay participants
enum SharePlayRole: String, Codable, CaseIterable {
    /// Full access - can control all devices, see all state
    case owner = "owner"

    /// Standard household member - can control most devices
    case member = "member"

    /// Limited access - can only control designated devices
    case guest = "guest"

    /// View-only access - cannot control anything
    case viewer = "viewer"

    /// Actions this role can perform
    var allowedActions: Set<ActionCategory> {
        switch self {
        case .owner:
            return [.lights, .scenes, .locks, .fireplace, .shades, .climate, .security, .sensitive]
        case .member:
            return [.lights, .scenes, .shades, .climate]
        case .guest:
            return [.lights, .scenes]
        case .viewer:
            return []
        }
    }

    /// Whether this role can see detailed device state
    var canSeeDetailedState: Bool {
        switch self {
        case .owner, .member:
            return true
        case .guest, .viewer:
            return false
        }
    }

    /// Whether this role can see security-sensitive information
    var canSeeSensitiveInfo: Bool {
        switch self {
        case .owner:
            return true
        case .member, .guest, .viewer:
            return false
        }
    }

    /// Action categories for role-based filtering
    enum ActionCategory: String, Codable {
        case lights
        case scenes
        case locks
        case fireplace
        case shades
        case climate
        case security
        case sensitive  // Camera feeds, lock codes, etc.
    }
}

// MARK: - Participant Info

struct SharePlayParticipant: Identifiable, Codable {
    let id: String
    let name: String
    var headPosition: [Float]?
    var lastSeen: Date
    var role: SharePlayRole

    init(id: String, name: String, role: SharePlayRole = .guest) {
        self.id = id
        self.name = name
        self.lastSeen = Date()
        self.role = role
    }

    /// Checks if this participant can perform an action
    func canPerform(_ action: SharedHomeState.HomeAction) -> Bool {
        let category = action.category
        return role.allowedActions.contains(category)
    }
}

// MARK: - SharePlay Service

@MainActor
class SharePlayService: ObservableObject {

    // MARK: - Published State

    @Published var isActive = false
    @Published var isHost = false
    @Published var participants: [SharePlayParticipant] = []
    @Published var lastReceivedAction: SharedHomeState?
    @Published var connectionError: String?

    // MARK: - Internal State

    private var groupSession: GroupSession<HomeControlActivity>?
    private var messenger: GroupSessionMessenger?
    private var tasks = Set<Task<Void, Never>>()
    private var cancellables = Set<AnyCancellable>()

    private let deviceId: String
    private let deviceName: String

    /// Local user's role (owner by default for device owner)
    @Published var localUserRole: SharePlayRole = .owner

    /// Role assignments for participants (keyed by participant ID)
    private var participantRoles: [String: SharePlayRole] = [:]

    // Callbacks
    var onActionReceived: ((SharedHomeState.HomeAction) -> Void)?

    /// Called when an action is blocked due to insufficient permissions
    var onActionBlocked: ((SharedHomeState.HomeAction, SharePlayRole) -> Void)?

    // MARK: - Init

    init() {
        #if os(visionOS)
        self.deviceId = "vision-\(UUID().uuidString.prefix(8))"
        self.deviceName = "Vision Pro"
        #else
        self.deviceId = "mac-\(UUID().uuidString.prefix(8))"
        self.deviceName = "Mac"
        #endif

        // Observe group sessions
        Task {
            for await session in HomeControlActivity.sessions() {
                configureGroupSession(session)
            }
        }
    }

    // MARK: - Session Management

    func startSession() async {
        let activity = HomeControlActivity()

        do {
            let result = try await activity.prepareForActivation()

            switch result {
            case .activationDisabled:
                connectionError = "SharePlay is not available"

            case .activationPreferred:
                try await activity.activate()
                isHost = true

            case .cancelled:
                connectionError = "Session was cancelled"

            @unknown default:
                break
            }
        } catch {
            connectionError = "Failed to start session: \(error.localizedDescription)"
        }
    }

    func endSession() {
        groupSession?.end()
        cleanup()
    }

    private func configureGroupSession(_ session: GroupSession<HomeControlActivity>) {
        groupSession = session
        messenger = GroupSessionMessenger(session: session)

        // Observe session state
        session.$state
            .sink { [weak self] state in
                self?.handleSessionState(state)
            }
            .store(in: &cancellables)

        // Observe participants
        session.$activeParticipants
            .sink { [weak self] activeParticipants in
                self?.updateParticipants(activeParticipants)
            }
            .store(in: &cancellables)

        // Receive messages
        let receiveTask = Task { [weak self] in
            guard let messenger = self?.messenger else { return }

            for await (message, _) in messenger.messages(of: SharedHomeState.self) {
                await self?.handleReceivedMessage(message)
            }
        }
        tasks.insert(receiveTask)

        // Join the session
        session.join()
        isActive = true
    }

    private func handleSessionState(_ state: GroupSession<HomeControlActivity>.State) {
        switch state {
        case .waiting:
            isActive = false

        case .joined:
            isActive = true
            connectionError = nil

        case .invalidated(let reason):
            isActive = false
            // Handle invalidation - reason indicates why session ended
            // In visionOS 1.0, the API doesn't expose specific reason types publicly
            _ = reason // Suppress unused warning
            connectionError = "Session ended"
            cleanup()

        @unknown default:
            break
        }
    }

    private func updateParticipants(_ activeParticipants: Set<Participant>) {
        participants = activeParticipants.map { participant in
            SharePlayParticipant(
                id: participant.id.uuidString,
                name: "Participant"
            )
        }
    }

    private func handleReceivedMessage(_ message: SharedHomeState) async {
        // Ignore our own messages
        guard message.senderId != deviceId else { return }

        // Get the sender's role (default to guest for unknown participants)
        let senderRole = participantRoles[message.senderId] ?? .guest

        // Role-based filtering: check if sender is allowed to perform this action
        let actionCategory = message.action.category
        guard senderRole.allowedActions.contains(actionCategory) else {
            print("SharePlay action blocked: \(message.action.description) - sender role '\(senderRole.rawValue)' lacks permission for '\(actionCategory.rawValue)'")
            onActionBlocked?(message.action, senderRole)
            return
        }

        // Additional check for sensitive actions
        if message.action.isSensitive && !senderRole.canSeeSensitiveInfo {
            print("SharePlay sensitive action blocked for role: \(senderRole.rawValue)")
            onActionBlocked?(message.action, senderRole)
            return
        }

        lastReceivedAction = message
        onActionReceived?(message.action)
    }

    private func cleanup() {
        tasks.forEach { $0.cancel() }
        tasks.removeAll()
        cancellables.removeAll()
        groupSession = nil
        messenger = nil
        participants = []
        isHost = false
    }

    // MARK: - Sending Actions

    func sendAction(_ action: SharedHomeState.HomeAction) async {
        guard isActive, let messenger = messenger else { return }

        let state = SharedHomeState(
            senderId: deviceId,
            timestamp: Date(),
            action: action
        )

        do {
            try await messenger.send(state)
        } catch {
            print("Failed to send action: \(error)")
        }
    }

    // Convenience methods
    func sendLightsChange(level: Int, room: String? = nil) async {
        await sendAction(.setLights(level: level, room: room))
    }

    func sendSceneActivation(_ scene: String) async {
        await sendAction(.activateScene(name: scene))
    }

    func sendFireplaceToggle() async {
        await sendAction(.toggleFireplace)
    }

    func sendShadesControl(action: String, room: String? = nil) async {
        await sendAction(.controlShades(action: action, room: room))
    }

    func sendRoomSelection(_ roomId: String) async {
        await sendAction(.selectRoom(roomId: roomId))
    }

    func sendRoomDeselection() async {
        await sendAction(.deselectRoom)
    }

    // MARK: - Participant Presence

    func updateMyPosition(_ position: SIMD3<Float>) async {
        // Could extend to share spatial position with other participants
        // for rendering presence indicators in shared space
    }

    // MARK: - Role Management

    /// Sets the role for a participant (only owner can change roles)
    func setParticipantRole(_ participantId: String, role: SharePlayRole) {
        guard localUserRole == .owner else {
            print("Only owners can change participant roles")
            return
        }

        participantRoles[participantId] = role

        // Update the participant in the published list
        if let index = participants.firstIndex(where: { $0.id == participantId }) {
            participants[index].role = role
        }

        print("Set role for participant \(participantId) to \(role.rawValue)")
    }

    /// Gets the role for a participant
    func getParticipantRole(_ participantId: String) -> SharePlayRole {
        return participantRoles[participantId] ?? .guest
    }

    /// Checks if the local user can perform an action
    func canPerformAction(_ action: SharedHomeState.HomeAction) -> Bool {
        return localUserRole.allowedActions.contains(action.category)
    }

    /// Returns filtered home state based on participant's role
    func filterStateForRole(_ state: [String: Any], role: SharePlayRole) -> [String: Any] {
        var filteredState = state

        // Remove sensitive information for non-owners
        if !role.canSeeSensitiveInfo {
            filteredState.removeValue(forKey: "lock_codes")
            filteredState.removeValue(forKey: "camera_feeds")
            filteredState.removeValue(forKey: "security_status")
            filteredState.removeValue(forKey: "alarm_state")
        }

        // Simplify detailed state for guests/viewers
        if !role.canSeeDetailedState {
            // Replace exact values with simplified states
            if let lights = filteredState["lights"] as? [[String: Any]] {
                let simplified = lights.map { light -> [String: Any] in
                    var simple = light
                    if let level = light["level"] as? Int {
                        simple["level"] = level > 0 ? "on" : "off"  // Hide exact percentages
                    }
                    return simple
                }
                filteredState["lights"] = simplified
            }

            // Hide temperature details
            if filteredState["hvac"] != nil {
                filteredState["hvac"] = ["status": "active"]
            }
        }

        return filteredState
    }

    /// Promotes a participant to a higher role
    func promoteParticipant(_ participantId: String) {
        guard localUserRole == .owner else { return }

        let currentRole = participantRoles[participantId] ?? .guest
        let newRole: SharePlayRole

        switch currentRole {
        case .viewer:
            newRole = .guest
        case .guest:
            newRole = .member
        case .member:
            newRole = .owner
        case .owner:
            return  // Already at highest
        }

        setParticipantRole(participantId, role: newRole)
    }

    /// Demotes a participant to a lower role
    func demoteParticipant(_ participantId: String) {
        guard localUserRole == .owner else { return }

        let currentRole = participantRoles[participantId] ?? .guest
        let newRole: SharePlayRole

        switch currentRole {
        case .owner:
            newRole = .member
        case .member:
            newRole = .guest
        case .guest:
            newRole = .viewer
        case .viewer:
            return  // Already at lowest
        }

        setParticipantRole(participantId, role: newRole)
    }
}

// MARK: - SharePlay View Modifier

struct SharePlayModifier: ViewModifier {
    @StateObject private var sharePlayService = SharePlayService()

    let onActionReceived: (SharedHomeState.HomeAction) -> Void

    func body(content: Content) -> some View {
        content
            .environmentObject(sharePlayService)
            .onAppear {
                sharePlayService.onActionReceived = onActionReceived
            }
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    SharePlayButton(service: sharePlayService)
                }
            }
    }
}

// MARK: - SharePlay Button

struct SharePlayButton: View {
    @ObservedObject var service: SharePlayService

    var body: some View {
        Button(action: {
            Task {
                if service.isActive {
                    service.endSession()
                } else {
                    await service.startSession()
                }
            }
        }) {
            HStack(spacing: 6) {
                Image(systemName: service.isActive ? "shareplay" : "shareplay.slash")
                if service.isActive {
                    Text("\(service.participants.count)")
                        .font(.system(size: 12))
                }
            }
        }
        .contentShape(.hoverEffect, .capsule)
        .hoverEffect(.lift)
        .accessibilityLabel(service.isActive ? "End SharePlay session" : "Start SharePlay session")
    }
}

// MARK: - View Extension

extension View {
    func sharePlayEnabled(onAction: @escaping (SharedHomeState.HomeAction) -> Void) -> some View {
        modifier(SharePlayModifier(onActionReceived: onAction))
    }
}

/*
 * SharePlay enables collaborative home control.
 * Multiple Vision Pro users can control the house together.
 * Actions sync in real-time across all participants.
 */
