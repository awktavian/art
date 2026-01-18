//
// RoomTrackingService.swift — visionOS Room Anchor Integration
//
// Colony: Nexus (e₄) — Integration
//
// Features:
//   - Detect and label rooms via ARKit Room Anchors
//   - Persist room identity across sessions
//   - Place room-specific spatial UI
//   - Sync with Kagami room definitions
//
// Architecture:
//   ARKit RoomTrackingProvider → RoomTrackingService → KagamiAPIService
//
// visionOS 2.0+ required for Room Anchors
//
// h(x) ≥ 0. Always.
//

import Foundation
import ARKit
import RealityKit
import Combine

/// Service for tracking and managing room anchors in visionOS.
///
/// Room anchors allow Kagami to:
/// - Identify which room the user is in
/// - Place persistent UI in specific rooms
/// - Sync spatial awareness with smart home
///
/// Note: Room anchors require visionOS 2.0+
@available(visionOS 2.0, *)
@MainActor
class RoomTrackingService: ObservableObject {

    // MARK: - Published State

    /// Whether room tracking is currently active
    @Published var isTracking: Bool = false

    /// Whether room tracking is supported on this device
    @Published var isSupported: Bool = false

    /// Currently detected rooms
    @Published var detectedRooms: [DetectedRoom] = []

    /// Current room the user is likely in
    @Published var currentRoom: DetectedRoom?

    /// Room tracking authorization status
    @Published var authorizationStatus: RoomTrackingAuthStatus = .notDetermined

    // MARK: - Private State

    private var arSession: ARKitSession?
    private var roomTrackingProvider: RoomTrackingProvider?
    private var cancellables = Set<AnyCancellable>()

    // Persistent room storage
    private let roomStorageKey = "kagami_room_anchors"

    // MARK: - Types

    /// Authorization status for room tracking
    enum RoomTrackingAuthStatus {
        case notDetermined
        case authorized
        case denied
        case unavailable
    }

    /// A detected room with its properties
    struct DetectedRoom: Identifiable, Codable {
        let id: UUID
        var name: String
        var kagamiRoomId: String?  // Mapped to Kagami room ID
        var anchorId: UUID
        var center: SIMD3<Float>
        var dimensions: SIMD3<Float>  // width, height, depth
        var lastSeen: Date
        var confidence: Float

        /// Human-readable size description
        var sizeDescription: String {
            let area = dimensions.x * dimensions.z
            if area < 10 { return "Small" }
            if area < 20 { return "Medium" }
            if area < 40 { return "Large" }
            return "Very Large"
        }
    }

    /// Room mapping to Kagami rooms
    struct KagamiRoomMapping: Codable {
        let detectedRoomId: UUID
        let kagamiRoomId: String
        let kagamiRoomName: String
    }

    // MARK: - Init

    init() {
        checkSupport()
        loadPersistedRooms()
    }

    // MARK: - Support Check

    /// Check if room tracking is supported
    private func checkSupport() {
        isSupported = RoomTrackingProvider.isSupported
        print("🏠 Room tracking supported: \(isSupported)")
    }

    // MARK: - Authorization

    /// Request authorization for room tracking
    func requestAuthorization() async -> Bool {
        guard isSupported else {
            authorizationStatus = .unavailable
            return false
        }

        // Room tracking uses World Sensing authorization
        // Query the ARKitSession for authorization status
        let session = arSession ?? ARKitSession()
        self.arSession = session

        let authResults = await session.queryAuthorization(for: [.worldSensing])
        let status = authResults[.worldSensing] ?? .notDetermined

        switch status {
        case .allowed:
            authorizationStatus = .authorized
            return true
        case .denied:
            authorizationStatus = .denied
            return false
        case .notDetermined:
            // Request authorization by trying to run
            authorizationStatus = .notDetermined
            return true  // Will be determined when we start
        @unknown default:
            authorizationStatus = .unavailable
            return false
        }
    }

    // MARK: - Start/Stop Tracking

    /// Start room tracking
    func startTracking() async -> Bool {
        guard isSupported else {
            print("⚠️ Room tracking not supported")
            return false
        }

        arSession = ARKitSession()
        roomTrackingProvider = RoomTrackingProvider()

        guard let session = arSession, let provider = roomTrackingProvider else {
            return false
        }

        do {
            try await session.run([provider])
            isTracking = true
            authorizationStatus = .authorized
            print("✅ Room tracking started")

            // Start processing room updates
            startRoomUpdateLoop()

            return true
        } catch {
            print("❌ Failed to start room tracking: \(error)")

            // ARKitSession errors don't have a notAuthorized case
            // Check if this is an authorization-related error via description
            if error.localizedDescription.contains("authorized") {
                authorizationStatus = .denied
            } else {
                authorizationStatus = .unavailable
            }

            return false
        }
    }

    /// Stop room tracking
    func stopTracking() {
        arSession?.stop()
        isTracking = false
        print("🛑 Room tracking stopped")
    }

    // MARK: - Room Updates

    /// Process room anchor updates
    private func startRoomUpdateLoop() {
        guard let provider = roomTrackingProvider else { return }

        Task {
            for await update in provider.anchorUpdates {
                await processRoomUpdate(update)
            }
        }
    }

    /// Process a single room update
    private func processRoomUpdate(_ update: AnchorUpdate<RoomAnchor>) async {
        let anchor = update.anchor

        switch update.event {
        case .added:
            await addRoom(from: anchor)
        case .updated:
            await updateRoom(from: anchor)
        case .removed:
            removeRoom(anchorId: anchor.id)
        }

        // Update current room based on user position
        updateCurrentRoom()

        // Sync with backend
        await syncWithBackend()
    }

    /// Add a newly detected room
    private func addRoom(from anchor: RoomAnchor) async {
        let room = DetectedRoom(
            id: UUID(),
            name: generateRoomName(for: anchor),
            kagamiRoomId: nil,
            anchorId: anchor.id,
            center: anchor.originFromAnchorTransform.columns.3.xyz,
            dimensions: estimateRoomDimensions(anchor),
            lastSeen: Date(),
            confidence: 0.8
        )

        detectedRooms.append(room)
        persistRooms()

        print("🆕 Room added: \(room.name) at \(room.center)")

        // Try to auto-match with Kagami rooms
        await autoMatchRoom(room)
    }

    /// Update an existing room
    private func updateRoom(from anchor: RoomAnchor) async {
        guard let index = detectedRooms.firstIndex(where: { $0.anchorId == anchor.id }) else {
            return
        }

        detectedRooms[index].center = anchor.originFromAnchorTransform.columns.3.xyz
        detectedRooms[index].dimensions = estimateRoomDimensions(anchor)
        detectedRooms[index].lastSeen = Date()
        detectedRooms[index].confidence = min(detectedRooms[index].confidence + 0.05, 1.0)

        persistRooms()
    }

    /// Remove a room
    private func removeRoom(anchorId: UUID) {
        detectedRooms.removeAll { $0.anchorId == anchorId }
        persistRooms()
        print("🗑️ Room removed: \(anchorId)")
    }

    // MARK: - Room Identification

    /// Generate a default name for a room based on its properties
    private func generateRoomName(for anchor: RoomAnchor) -> String {
        let dimensions = estimateRoomDimensions(anchor)
        let area = dimensions.x * dimensions.z

        // Basic heuristics for room type
        if area < 8 {
            return "Bathroom"
        } else if area < 15 {
            return "Bedroom"
        } else if area < 25 {
            return "Office"
        } else if area < 40 {
            return "Living Room"
        } else {
            return "Great Room"
        }
    }

    /// Estimate room dimensions from anchor geometry
    private func estimateRoomDimensions(_ anchor: RoomAnchor) -> SIMD3<Float> {
        // Would use anchor.geometry in real implementation
        // For now, return placeholder
        return SIMD3<Float>(5.0, 2.7, 4.0)  // Default room size
    }

    /// Update which room the user is currently in
    private func updateCurrentRoom() {
        // In a real implementation, we'd use the user's head position
        // relative to room centers to determine current room

        // For now, use most recently seen room
        currentRoom = detectedRooms.max(by: { $0.lastSeen < $1.lastSeen })
    }

    // MARK: - Kagami Integration

    /// Auto-match detected room with Kagami room definitions
    private func autoMatchRoom(_ room: DetectedRoom) async {
        // Fetch Kagami rooms
        do {
            let kagamiRooms = try await KagamiAPIService.shared.getRooms()

            // Find best match based on name similarity
            let bestMatch = kagamiRooms.min { r1, r2 in
                levenshteinDistance(room.name, r1.name) < levenshteinDistance(room.name, r2.name)
            }

            if let match = bestMatch {
                await mapRoom(detectedRoomId: room.id, toKagamiRoom: match.id, name: match.name)
            }
        } catch {
            print("⚠️ Failed to fetch Kagami rooms: \(error)")
        }
    }

    /// Map a detected room to a Kagami room
    func mapRoom(detectedRoomId: UUID, toKagamiRoom kagamiId: String, name: String) async {
        guard let index = detectedRooms.firstIndex(where: { $0.id == detectedRoomId }) else {
            return
        }

        detectedRooms[index].kagamiRoomId = kagamiId
        detectedRooms[index].name = name
        persistRooms()

        print("🔗 Mapped room to Kagami: \(name) (\(kagamiId))")

        // Notify backend
        await syncWithBackend()
    }

    /// Sync room state with Kagami backend
    private func syncWithBackend() async {
        guard let current = currentRoom, let kagamiId = current.kagamiRoomId else {
            return
        }

        do {
            try await KagamiAPIService.shared.reportUserLocation(roomId: kagamiId)
        } catch {
            print("⚠️ Failed to sync room with backend: \(error)")
        }
    }

    // MARK: - Persistence

    /// Load persisted rooms
    private func loadPersistedRooms() {
        guard let data = UserDefaults.standard.data(forKey: roomStorageKey),
              let rooms = try? JSONDecoder().decode([DetectedRoom].self, from: data) else {
            return
        }

        detectedRooms = rooms
        print("📂 Loaded \(rooms.count) persisted rooms")
    }

    /// Persist rooms to storage
    private func persistRooms() {
        guard let data = try? JSONEncoder().encode(detectedRooms) else {
            return
        }

        UserDefaults.standard.set(data, forKey: roomStorageKey)
    }

    // MARK: - Spatial UI Placement

    /// Get position for placing UI in a specific room
    func getUIPlacementPosition(for roomId: UUID, offset: SIMD3<Float> = .zero) -> SIMD3<Float>? {
        guard let room = detectedRooms.first(where: { $0.id == roomId }) else {
            return nil
        }

        // Place UI at room center plus offset
        return room.center + offset
    }

    /// Get position for placing UI in current room
    func getCurrentRoomUIPosition(offset: SIMD3<Float> = .zero) -> SIMD3<Float>? {
        guard let room = currentRoom else { return nil }
        return room.center + offset
    }

    // MARK: - Utilities

    /// Simple Levenshtein distance for string matching
    private func levenshteinDistance(_ s1: String, _ s2: String) -> Int {
        let s1 = Array(s1.lowercased())
        let s2 = Array(s2.lowercased())

        var dist = [[Int]]()
        for i in 0...s1.count {
            dist.append([Int](repeating: 0, count: s2.count + 1))
            dist[i][0] = i
        }
        for j in 0...s2.count {
            dist[0][j] = j
        }

        for i in 1...s1.count {
            for j in 1...s2.count {
                if s1[i-1] == s2[j-1] {
                    dist[i][j] = dist[i-1][j-1]
                } else {
                    dist[i][j] = min(
                        dist[i-1][j] + 1,
                        dist[i][j-1] + 1,
                        dist[i-1][j-1] + 1
                    )
                }
            }
        }

        return dist[s1.count][s2.count]
    }
}

// MARK: - SIMD Extensions
// Note: simd_float4x4.xyz is defined in HandTrackingService.swift

// MARK: - KagamiAPIService Extension

extension KagamiAPIService {
    /// Report user location to backend
    func reportUserLocation(roomId: String) async throws {
        let body: [String: Any] = [
            "event": "user_location",
            "room_id": roomId,
            "timestamp": ISO8601DateFormatter().string(from: Date()),
            "source": "vision_room_tracking"
        ]

        // Would call actual API endpoint
        print("📍 Report location: \(roomId)")
    }

    /// Get Kagami room definitions
    func getRooms() async throws -> [KagamiRoom] {
        // Would fetch from actual API
        return [
            KagamiRoom(id: "57", name: "Living Room", floor: "1st"),
            KagamiRoom(id: "59", name: "Kitchen", floor: "1st"),
            KagamiRoom(id: "47", name: "Office", floor: "2nd"),
            KagamiRoom(id: "36", name: "Primary Bedroom", floor: "2nd"),
        ]
    }

    struct KagamiRoom: Codable {
        let id: String
        let name: String
        let floor: String
    }
}

// Note: SIMD4.xyz extension defined in HandTrackingService.swift

/*
 * 鏡
 * h(x) ≥ 0. Always.
 *
 * Rooms are containers of experience.
 * Kagami sees the space around you.
 * Your home becomes aware.
 */
