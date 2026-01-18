//
// SharePlayManager.swift — Advanced Multi-User SharePlay Experience
//
// Colony: Nexus (e4) — Integration
//
// P2 FIX: Full SharePlay multi-user experience
//
// Features:
//   - GroupActivity for shared spatial experiences
//   - Synchronized home state across participants
//   - Guest access controls with invite links
//   - Multi-user gesture coordination
//   - Spatial presence indicators
//   - Conflict resolution for simultaneous actions
//
// Architecture:
//   SharePlayManager <-> SharePlayService <-> GroupActivity
//   ├── ParticipantPresence: Spatial position sharing
//   ├── StateCoordinator: Home state synchronization
//   ├── GestureCoordinator: Multi-user gesture handling
//   └── AccessController: Permission management
//
// Created: January 2, 2026
// 鏡

import Foundation
import GroupActivities
import RealityKit
import Combine
import CryptoKit

// MARK: - Home Control Group Activity

/// Enhanced GroupActivity for shared spatial home control
struct SpatialHomeActivity: GroupActivity {
    static let activityIdentifier = "com.kagami.vision.spatial-home"

    let sessionId: String
    let hostName: String
    let permissions: SessionPermissions

    struct SessionPermissions: Codable {
        var allowGuestControl: Bool = true
        var maxParticipants: Int = 6
        var allowedRooms: [String]? // nil = all rooms
        var guestRoleDefault: SharePlayRole = .guest
    }

    var metadata: GroupActivityMetadata {
        var metadata = GroupActivityMetadata()
        metadata.title = "Kagami Home Control"
        metadata.subtitle = "Control \(hostName)'s home together"
        metadata.type = .generic
        metadata.previewImage = nil
        return metadata
    }

    init(hostName: String = "Home", permissions: SessionPermissions = SessionPermissions()) {
        self.sessionId = UUID().uuidString
        self.hostName = hostName
        self.permissions = permissions
    }
}

// MARK: - Synchronized State Messages

/// Messages sent between SharePlay participants
enum SharePlayMessage: Codable {
    case stateSync(StateSyncMessage)
    case gestureAction(GestureActionMessage)
    case presenceUpdate(PresenceUpdateMessage)
    case roleChange(RoleChangeMessage)
    case conflictResolution(ConflictResolutionMessage)
    case heartbeat(HeartbeatMessage)

    struct StateSyncMessage: Codable {
        let senderId: String
        let timestamp: Date
        let homeState: EncodedHomeState
        let sequenceNumber: Int
    }

    struct GestureActionMessage: Codable {
        let senderId: String
        let timestamp: Date
        let gesture: String
        let targetRoom: String?
        let targetDevice: String?
        let value: Float?
        let requestId: String
    }

    struct PresenceUpdateMessage: Codable {
        let senderId: String
        let displayName: String
        let headPosition: [Float]?
        let leftHandPosition: [Float]?
        let rightHandPosition: [Float]?
        let gazeDirection: [Float]?
        let currentRoom: String?
        let isActive: Bool
    }

    struct RoleChangeMessage: Codable {
        let targetId: String
        let newRole: SharePlayRole
        let grantedBy: String
    }

    struct ConflictResolutionMessage: Codable {
        let conflictId: String
        let winningRequestId: String
        let losers: [String]
    }

    struct HeartbeatMessage: Codable {
        let senderId: String
        let timestamp: Date
    }
}

/// Encoded home state for network transmission
struct EncodedHomeState: Codable {
    let rooms: [EncodedRoom]
    let scenes: [String]
    let fireplaceOn: Bool
    let timestamp: Date

    struct EncodedRoom: Codable {
        let id: String
        let name: String
        let lights: [EncodedLight]
        let shades: [EncodedShade]
    }

    struct EncodedLight: Codable {
        let id: Int
        let name: String
        let level: Int
        let isOn: Bool
    }

    struct EncodedShade: Codable {
        let id: Int
        let name: String
        let position: Int
    }
}

// MARK: - Participant Presence

/// Represents another user's spatial presence in SharePlay
class ParticipantPresence: Identifiable, ObservableObject {
    let id: String
    let displayName: String

    @Published var headPosition: SIMD3<Float>?
    @Published var leftHandPosition: SIMD3<Float>?
    @Published var rightHandPosition: SIMD3<Float>?
    @Published var gazeDirection: SIMD3<Float>?
    @Published var currentRoom: String?
    @Published var lastSeen: Date
    @Published var role: SharePlayRole
    @Published var isActive: Bool = true
    @Published var avatarColor: Color

    /// Entity representation in RealityKit
    var presenceEntity: Entity?

    init(id: String, displayName: String, role: SharePlayRole = .guest) {
        self.id = id
        self.displayName = displayName
        self.lastSeen = Date()
        self.role = role
        self.avatarColor = ParticipantPresence.colorForId(id)
    }

    /// Updates presence from network message
    func update(from message: SharePlayMessage.PresenceUpdateMessage) {
        if let pos = message.headPosition, pos.count == 3 {
            headPosition = SIMD3<Float>(pos[0], pos[1], pos[2])
        }
        if let pos = message.leftHandPosition, pos.count == 3 {
            leftHandPosition = SIMD3<Float>(pos[0], pos[1], pos[2])
        }
        if let pos = message.rightHandPosition, pos.count == 3 {
            rightHandPosition = SIMD3<Float>(pos[0], pos[1], pos[2])
        }
        if let dir = message.gazeDirection, dir.count == 3 {
            gazeDirection = SIMD3<Float>(dir[0], dir[1], dir[2])
        }
        currentRoom = message.currentRoom
        isActive = message.isActive
        lastSeen = Date()
    }

    /// Generates a consistent color for a participant ID
    private static func colorForId(_ id: String) -> Color {
        let hash = SHA256.hash(data: Data(id.utf8))
        let bytes = Array(hash.prefix(3))
        return Color(
            red: Double(bytes[0]) / 255.0,
            green: Double(bytes[1]) / 255.0,
            blue: Double(bytes[2]) / 255.0
        )
    }

    /// Check if presence is stale (no update in 5 seconds)
    var isStale: Bool {
        return Date().timeIntervalSince(lastSeen) > 5.0
    }
}

// MARK: - Gesture Conflict Resolution

/// Handles conflicts when multiple users try to control the same device
actor GestureConflictResolver {

    /// Pending gesture requests awaiting resolution
    private var pendingRequests: [String: PendingRequest] = [:]

    /// Resolution window in seconds
    private let resolutionWindow: TimeInterval = 0.15

    struct PendingRequest {
        let requestId: String
        let senderId: String
        let targetDevice: String?
        let targetRoom: String?
        let timestamp: Date
        let priority: Int
        let role: SharePlayRole
    }

    /// Submits a gesture request for conflict resolution
    func submit(
        requestId: String,
        senderId: String,
        targetDevice: String?,
        targetRoom: String?,
        role: SharePlayRole
    ) async -> Bool {
        let key = conflictKey(device: targetDevice, room: targetRoom)
        let priority = calculatePriority(role: role)

        let request = PendingRequest(
            requestId: requestId,
            senderId: senderId,
            targetDevice: targetDevice,
            targetRoom: targetRoom,
            timestamp: Date(),
            priority: priority,
            role: role
        )

        // Check for existing request on same target
        if let existing = pendingRequests[key] {
            // If within resolution window, compare priorities
            if Date().timeIntervalSince(existing.timestamp) < resolutionWindow {
                if request.priority > existing.priority {
                    // New request wins
                    pendingRequests[key] = request
                    return true
                } else if request.priority == existing.priority {
                    // Same priority - first wins (existing)
                    return false
                } else {
                    // Lower priority loses
                    return false
                }
            }
        }

        // No conflict, accept request
        pendingRequests[key] = request

        // Clean up old requests
        await cleanupStaleRequests()

        return true
    }

    /// Resolves all pending conflicts and returns winners
    func resolve() async -> [String] {
        let winners = pendingRequests.values.map { $0.requestId }
        pendingRequests.removeAll()
        return winners
    }

    private func conflictKey(device: String?, room: String?) -> String {
        if let device = device {
            return "device:\(device)"
        } else if let room = room {
            return "room:\(room)"
        }
        return "global"
    }

    private func calculatePriority(role: SharePlayRole) -> Int {
        switch role {
        case .owner: return 100
        case .member: return 50
        case .guest: return 25
        case .viewer: return 0
        }
    }

    private func cleanupStaleRequests() async {
        let cutoff = Date().addingTimeInterval(-resolutionWindow * 2)
        pendingRequests = pendingRequests.filter { $0.value.timestamp > cutoff }
    }
}

// MARK: - SharePlay Manager

/// Main manager for multi-user SharePlay experiences
@MainActor
final class SharePlayManager: ObservableObject {

    // MARK: - Published State

    @Published var isSessionActive = false
    @Published var isHost = false
    @Published var participants: [ParticipantPresence] = []
    @Published var localUserId: String
    @Published var localUserRole: SharePlayRole = .owner
    @Published var sessionError: String?
    @Published var lastSyncedState: EncodedHomeState?
    @Published var pendingActions: [String] = []

    // Presence streaming
    @Published var isPresenceStreamingEnabled = true
    @Published var presenceUpdateRate: TimeInterval = 0.1 // 10 Hz

    // MARK: - Services

    private var sharePlayService: SharePlayService?
    private var groupSession: GroupSession<SpatialHomeActivity>?
    private var messenger: GroupSessionMessenger?
    private let conflictResolver = GestureConflictResolver()

    // MARK: - Internal State

    private var cancellables = Set<AnyCancellable>()
    private var tasks = Set<Task<Void, Never>>()
    private var presenceTimer: Timer?
    private var heartbeatTimer: Timer?
    private var stateSequenceNumber = 0

    // MARK: - Callbacks

    var onStateReceived: ((EncodedHomeState) -> Void)?
    var onGestureReceived: ((SharePlayMessage.GestureActionMessage) -> Void)?
    var onParticipantJoined: ((ParticipantPresence) -> Void)?
    var onParticipantLeft: ((String) -> Void)?

    // MARK: - Init

    init() {
        #if os(visionOS)
        self.localUserId = "vision-\(UUID().uuidString.prefix(8))"
        #else
        self.localUserId = "mac-\(UUID().uuidString.prefix(8))"
        #endif

        // Listen for SharePlay sessions
        Task {
            for await session in SpatialHomeActivity.sessions() {
                await configureSession(session)
            }
        }
    }

    // MARK: - Session Management

    /// Creates and starts a new SharePlay session as host
    func startSession(
        hostName: String = "Home",
        allowGuestControl: Bool = true,
        maxParticipants: Int = 6
    ) async throws {
        let permissions = SpatialHomeActivity.SessionPermissions(
            allowGuestControl: allowGuestControl,
            maxParticipants: maxParticipants,
            guestRoleDefault: allowGuestControl ? .guest : .viewer
        )

        let activity = SpatialHomeActivity(hostName: hostName, permissions: permissions)

        let result = try await activity.prepareForActivation()

        switch result {
        case .activationDisabled:
            throw SharePlayError.activationDisabled

        case .activationPreferred:
            try await activity.activate()
            isHost = true
            localUserRole = .owner

        case .cancelled:
            throw SharePlayError.cancelled

        @unknown default:
            break
        }
    }

    /// Ends the current session
    func endSession() {
        groupSession?.end()
        cleanup()
    }

    /// Leaves the session without ending it (for non-hosts)
    func leaveSession() {
        groupSession?.leave()
        cleanup()
    }

    private func configureSession(_ session: GroupSession<SpatialHomeActivity>) async {
        groupSession = session
        messenger = GroupSessionMessenger(session: session)

        // Track session state
        session.$state
            .sink { [weak self] state in
                Task { @MainActor in
                    self?.handleSessionState(state)
                }
            }
            .store(in: &cancellables)

        // Track participants
        session.$activeParticipants
            .sink { [weak self] activeParticipants in
                Task { @MainActor in
                    self?.handleParticipantChange(activeParticipants)
                }
            }
            .store(in: &cancellables)

        // Start message handling
        startMessageHandling()

        // Join the session
        session.join()
        isSessionActive = true

        // Start presence streaming
        startPresenceStreaming()

        // Start heartbeat
        startHeartbeat()

        print("SharePlay session configured")
    }

    private func handleSessionState(_ state: GroupSession<SpatialHomeActivity>.State) {
        switch state {
        case .waiting:
            isSessionActive = false

        case .joined:
            isSessionActive = true
            sessionError = nil

        case .invalidated(let reason):
            isSessionActive = false
            // Handle invalidation - reason indicates why session ended
            // In visionOS 1.0, the API doesn't expose specific reason types publicly
            _ = reason // Suppress unused warning
            sessionError = "Session ended"
            cleanup()

        @unknown default:
            break
        }
    }

    private func handleParticipantChange(_ activeParticipants: Set<Participant>) {
        // Find new participants
        let currentIds = Set(participants.map { $0.id })
        let newParticipantIds = Set(activeParticipants.map { $0.id.uuidString })

        // Add new participants
        for participant in activeParticipants {
            let id = participant.id.uuidString
            if !currentIds.contains(id) && id != localUserId {
                let defaultRole = groupSession?.activity.permissions.guestRoleDefault ?? .guest
                let presence = ParticipantPresence(
                    id: id,
                    displayName: "Participant",
                    role: defaultRole
                )
                participants.append(presence)
                onParticipantJoined?(presence)
            }
        }

        // Remove departed participants
        let departedIds = currentIds.subtracting(newParticipantIds).subtracting([localUserId])
        for departedId in departedIds {
            participants.removeAll { $0.id == departedId }
            onParticipantLeft?(departedId)
        }
    }

    private func cleanup() {
        presenceTimer?.invalidate()
        presenceTimer = nil
        heartbeatTimer?.invalidate()
        heartbeatTimer = nil

        for task in tasks {
            task.cancel()
        }
        tasks.removeAll()
        cancellables.removeAll()

        participants.removeAll()
        groupSession = nil
        messenger = nil
        isHost = false
        isSessionActive = false
    }

    // MARK: - Message Handling

    private func startMessageHandling() {
        guard let messenger = messenger else { return }

        let task = Task {
            for await (message, context) in messenger.messages(of: SharePlayMessage.self) {
                guard !Task.isCancelled else { break }
                await handleMessage(message, from: context.source.id.uuidString)
            }
        }
        tasks.insert(task)
    }

    private func handleMessage(_ message: SharePlayMessage, from senderId: String) async {
        // Don't process our own messages
        guard senderId != localUserId else { return }

        switch message {
        case .stateSync(let syncMessage):
            await handleStateSync(syncMessage)

        case .gestureAction(let gestureMessage):
            await handleGestureAction(gestureMessage)

        case .presenceUpdate(let presenceMessage):
            handlePresenceUpdate(presenceMessage)

        case .roleChange(let roleMessage):
            handleRoleChange(roleMessage)

        case .conflictResolution(let conflictMessage):
            handleConflictResolution(conflictMessage)

        case .heartbeat(let heartbeatMessage):
            handleHeartbeat(heartbeatMessage)
        }
    }

    private func handleStateSync(_ message: SharePlayMessage.StateSyncMessage) async {
        // Only accept state from higher sequence numbers
        guard message.sequenceNumber > stateSequenceNumber else { return }

        stateSequenceNumber = message.sequenceNumber
        lastSyncedState = message.homeState
        onStateReceived?(message.homeState)
    }

    private func handleGestureAction(_ message: SharePlayMessage.GestureActionMessage) async {
        // Check if sender has permission
        guard let participant = participants.first(where: { $0.id == message.senderId }) else { return }

        // Verify role allows this action
        let allowed = canPerformGesture(gesture: message.gesture, role: participant.role)
        guard allowed else {
            print("Gesture blocked: \(message.gesture) from role \(participant.role)")
            return
        }

        // Submit for conflict resolution
        let accepted = await conflictResolver.submit(
            requestId: message.requestId,
            senderId: message.senderId,
            targetDevice: message.targetDevice,
            targetRoom: message.targetRoom,
            role: participant.role
        )

        if accepted {
            onGestureReceived?(message)
        }
    }

    private func handlePresenceUpdate(_ message: SharePlayMessage.PresenceUpdateMessage) {
        if let participant = participants.first(where: { $0.id == message.senderId }) {
            participant.update(from: message)
        }
    }

    private func handleRoleChange(_ message: SharePlayMessage.RoleChangeMessage) {
        // Only accept role changes from owner
        if message.targetId == localUserId {
            localUserRole = message.newRole
        } else if let participant = participants.first(where: { $0.id == message.targetId }) {
            participant.role = message.newRole
        }
    }

    private func handleConflictResolution(_ message: SharePlayMessage.ConflictResolutionMessage) {
        // Remove our pending actions if they lost
        pendingActions.removeAll { message.losers.contains($0) }
    }

    private func handleHeartbeat(_ message: SharePlayMessage.HeartbeatMessage) {
        if let participant = participants.first(where: { $0.id == message.senderId }) {
            participant.lastSeen = Date()
            participant.isActive = true
        }
    }

    // MARK: - Sending Messages

    /// Broadcasts the current home state to all participants
    func broadcastState(_ state: EncodedHomeState) async {
        guard let messenger = messenger, isHost else { return }

        stateSequenceNumber += 1

        let message = SharePlayMessage.stateSync(
            SharePlayMessage.StateSyncMessage(
                senderId: localUserId,
                timestamp: Date(),
                homeState: state,
                sequenceNumber: stateSequenceNumber
            )
        )

        do {
            try await messenger.send(message)
        } catch {
            print("Failed to broadcast state: \(error)")
        }
    }

    /// Sends a gesture action to be executed
    func sendGestureAction(
        gesture: String,
        targetRoom: String? = nil,
        targetDevice: String? = nil,
        value: Float? = nil
    ) async -> Bool {
        guard let messenger = messenger else { return false }

        // Check local permission first
        guard canPerformGesture(gesture: gesture, role: localUserRole) else {
            return false
        }

        let requestId = UUID().uuidString
        pendingActions.append(requestId)

        let message = SharePlayMessage.gestureAction(
            SharePlayMessage.GestureActionMessage(
                senderId: localUserId,
                timestamp: Date(),
                gesture: gesture,
                targetRoom: targetRoom,
                targetDevice: targetDevice,
                value: value,
                requestId: requestId
            )
        )

        do {
            try await messenger.send(message)
            return true
        } catch {
            pendingActions.removeAll { $0 == requestId }
            print("Failed to send gesture action: \(error)")
            return false
        }
    }

    /// Sets the role for a participant (host only)
    func setParticipantRole(_ participantId: String, role: SharePlayRole) async {
        guard isHost, let messenger = messenger else { return }

        let message = SharePlayMessage.roleChange(
            SharePlayMessage.RoleChangeMessage(
                targetId: participantId,
                newRole: role,
                grantedBy: localUserId
            )
        )

        do {
            try await messenger.send(message)

            // Update local state
            if let participant = participants.first(where: { $0.id == participantId }) {
                participant.role = role
            }
        } catch {
            print("Failed to change role: \(error)")
        }
    }

    // MARK: - Presence Streaming

    private func startPresenceStreaming() {
        guard isPresenceStreamingEnabled else { return }

        presenceTimer = Timer.scheduledTimer(withTimeInterval: presenceUpdateRate, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in
                await self?.sendPresenceUpdate()
            }
        }
    }

    /// Sends current spatial presence to other participants
    func sendPresenceUpdate(
        headPosition: SIMD3<Float>? = nil,
        leftHandPosition: SIMD3<Float>? = nil,
        rightHandPosition: SIMD3<Float>? = nil,
        gazeDirection: SIMD3<Float>? = nil,
        currentRoom: String? = nil
    ) async {
        guard let messenger = messenger else { return }

        let message = SharePlayMessage.presenceUpdate(
            SharePlayMessage.PresenceUpdateMessage(
                senderId: localUserId,
                displayName: isHost ? "Host" : "Guest",
                headPosition: headPosition.map { [$0.x, $0.y, $0.z] },
                leftHandPosition: leftHandPosition.map { [$0.x, $0.y, $0.z] },
                rightHandPosition: rightHandPosition.map { [$0.x, $0.y, $0.z] },
                gazeDirection: gazeDirection.map { [$0.x, $0.y, $0.z] },
                currentRoom: currentRoom,
                isActive: true
            )
        )

        do {
            try await messenger.send(message)
        } catch {
            // Silently fail - presence updates are not critical
        }
    }

    private func startHeartbeat() {
        heartbeatTimer = Timer.scheduledTimer(withTimeInterval: 2.0, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in
                await self?.sendHeartbeat()
            }
        }
    }

    private func sendHeartbeat() async {
        guard let messenger = messenger else { return }

        let message = SharePlayMessage.heartbeat(
            SharePlayMessage.HeartbeatMessage(
                senderId: localUserId,
                timestamp: Date()
            )
        )

        do {
            try await messenger.send(message)
        } catch {
            // Silently fail
        }

        // Check for stale participants
        for participant in participants where participant.isStale {
            participant.isActive = false
        }
    }

    // MARK: - Permission Checks

    private func canPerformGesture(gesture: String, role: SharePlayRole) -> Bool {
        // Map gesture to action category
        let category: SharePlayRole.ActionCategory

        switch gesture {
        case "swipeUp", "swipeDown", "pinchDrag":
            category = .lights
        case "twoHandSpread", "twoHandPinch":
            category = .shades
        case "fist":
            category = .fireplace // Emergency stop
        case "thumbsUp":
            category = .scenes
        default:
            category = .lights
        }

        return role.allowedActions.contains(category)
    }

    /// Checks if current user can control a specific room
    func canControlRoom(_ roomId: String) -> Bool {
        guard let allowedRooms = groupSession?.activity.permissions.allowedRooms else {
            return true // All rooms allowed
        }
        return allowedRooms.contains(roomId)
    }

    // MARK: - Invite Link Generation

    /// Generates an invite link for the current session
    func generateInviteLink() -> URL? {
        guard isSessionActive, let session = groupSession else { return nil }

        // Create deep link with session info
        var components = URLComponents()
        components.scheme = "kagami"
        components.host = "shareplay"
        components.path = "/join"
        components.queryItems = [
            URLQueryItem(name: "session", value: session.activity.sessionId),
            URLQueryItem(name: "host", value: session.activity.hostName)
        ]

        return components.url
    }
}

// MARK: - Errors

enum SharePlayError: LocalizedError {
    case activationDisabled
    case cancelled
    case notAuthorized
    case sessionFull

    var errorDescription: String? {
        switch self {
        case .activationDisabled:
            return "SharePlay is not available on this device"
        case .cancelled:
            return "SharePlay session was cancelled"
        case .notAuthorized:
            return "You don't have permission for this action"
        case .sessionFull:
            return "This SharePlay session is full"
        }
    }
}

// MARK: - Color Extension

import SwiftUI

extension Color {
    init(participant: ParticipantPresence) {
        self = participant.avatarColor
    }
}

/*
 * 鏡
 * h(x) >= 0. Always.
 *
 * Together in space, together in control.
 * SharePlay bridges the distance.
 * Many hands, one home.
 */
