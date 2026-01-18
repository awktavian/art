//
// SpatialAnchorService.swift — Real-World Anchor Management
//
// Colony: Nexus (e₄) — Integration
//
// Features:
//   - Persistent world anchors for controls
//   - Surface detection for anchoring UI
//   - Proxemic zones based on Hall's theory
//   - Anchor persistence across sessions
//
// Proxemic Zones (Hall, 1966):
//   - Intimate: 0-45cm — Private notifications
//   - Personal: 45cm-1.2m — Control panels
//   - Social: 1.2m-3.6m — Room visualizations
//   - Public: 3.6m+ — Ambient awareness
//
// Architecture:
//   ARKit WorldTrackingProvider → SpatialAnchorService → UI Placement
//
// Created: December 31, 2025
// 鏡

import Foundation
import ARKit
import RealityKit
import Combine
import os.log

/// Manages persistent world anchors for spatial UI placement
@MainActor
class SpatialAnchorService: ObservableObject {

    // MARK: - Published State

    @Published var isTracking = false
    @Published var availableSurfaces: [DetectedSurface] = []
    @Published var activeAnchors: [SpatialAnchor] = []
    @Published var userProximity: ProxemicZone = .social
    @Published var headPosition: SIMD3<Float>?
    @Published var headForward: SIMD3<Float>?

    // MARK: - Types

    /// Proxemic zones based on Hall's 1966 research
    enum ProxemicZone: String, CaseIterable {
        case intimate = "intimate"   // 0-45cm — Private alerts
        case personal = "personal"   // 45cm-1.2m — Control panel
        case social = "social"       // 1.2m-3.6m — Room viz
        case ambient = "public"      // 3.6m+ — Background awareness

        var distanceRange: ClosedRange<Float> {
            switch self {
            case .intimate: return 0...0.45
            case .personal: return 0.45...1.2
            case .social: return 1.2...3.6
            case .ambient: return 3.6...Float.infinity
            }
        }

        /// Recommended UI scale for this zone
        var uiScale: Float {
            switch self {
            case .intimate: return 0.5
            case .personal: return 1.0
            case .social: return 1.5
            case .ambient: return 2.0
            }
        }

        /// Recommended opacity for glass materials
        var glassOpacity: Double {
            switch self {
            case .intimate: return 0.95
            case .personal: return 0.85
            case .social: return 0.7
            case .ambient: return 0.5
            }
        }
    }

    /// Anchor types for different UI placements
    enum AnchorType: String, Codable {
        case headRelative    // Follows user, fixed distance
        case worldLocked     // Fixed in physical space
        case surfaceLocked   // Attached to detected surface
        case floorAnchored   // On the floor plane
    }

    /// A spatial anchor with metadata
    struct SpatialAnchor: Identifiable, Codable {
        let id: UUID
        var position: SIMD3<Float>
        var rotation: simd_quatf
        let anchorType: AnchorType
        var label: String
        var isActive: Bool
        let createdAt: Date

        // For persistence
        var worldAnchorID: UUID?

        init(
            id: UUID = UUID(),
            position: SIMD3<Float>,
            rotation: simd_quatf = simd_quatf(angle: 0, axis: [0, 1, 0]),
            anchorType: AnchorType,
            label: String,
            isActive: Bool = true
        ) {
            self.id = id
            self.position = position
            self.rotation = rotation
            self.anchorType = anchorType
            self.label = label
            self.isActive = isActive
            self.createdAt = Date()
        }
    }

    /// A detected surface for anchoring
    struct DetectedSurface: Identifiable {
        let id: UUID
        let classification: SurfaceClassification
        let center: SIMD3<Float>
        let extent: SIMD2<Float>  // width, depth
        let normal: SIMD3<Float>

        enum SurfaceClassification {
            case floor
            case wall
            case ceiling
            case table
            case unknown
        }
    }

    // MARK: - Internal State

    private var arSession: ARKitSession?
    private var worldTracking: WorldTrackingProvider?
    private var planeDetection: PlaneDetectionProvider?
    private var updateTask: Task<Void, Never>?

    // Persistence
    private let anchorStorageKey = "kagami.spatial.anchors"

    // Critically damped spring motion parameters
    // Using c=0.7 (damping ratio) and k=1.0 (spring constant) for smooth motion
    private let springDampingRatio: Float = 0.7  // Critically damped (0.7-1.0)
    private let springStiffness: Float = 1.0     // Spring constant k
    private var anchorVelocities: [UUID: SIMD3<Float>] = [:]  // Velocity state for each anchor

    // MARK: - Init

    init() {
        loadPersistedAnchors()
    }

    // MARK: - Start/Stop

    func start() async -> Bool {
        guard WorldTrackingProvider.isSupported else {
            KagamiLogger.spatialAnchor.warning("World tracking not supported on this device")
            return false
        }

        arSession = ARKitSession()
        worldTracking = WorldTrackingProvider()
        planeDetection = PlaneDetectionProvider(alignments: [.horizontal, .vertical])

        do {
            var providers: [any DataProvider] = [worldTracking!]
            if PlaneDetectionProvider.isSupported {
                providers.append(planeDetection!)
            }

            try await arSession?.run(providers)

            // Monitor ARKit session state for proper lifecycle handling
            startSessionMonitoring()
            startUpdateLoop()

            KagamiLogger.spatialAnchor.info("Spatial anchor service started")
            return true
        } catch {
            KagamiLogger.logError("Failed to start anchor service", error: error, logger: KagamiLogger.spatialAnchor)
            return false
        }
    }

    /// Monitors ARKit session events for proper WorldTrackingProvider.State handling
    private func startSessionMonitoring() {
        guard let arSession = arSession else { return }

        Task {
            for await event in arSession.events {
                switch event {
                case .authorizationChanged(let type, let status):
                    KagamiLogger.logAuthorizationChange("ARKit \(type)", status: "\(status)", logger: KagamiLogger.spatialAnchor)
                    if status == .denied {
                        await handleSessionInterruption()
                    }

                case .dataProviderStateChanged(let providers, let newState, let error):
                    await handleProviderStateChange(providers: providers, newState: newState, error: error)

                @unknown default:
                    break
                }
            }
        }
    }

    /// Handles WorldTrackingProvider state changes per visionOS 2 guidelines
    private func handleProviderStateChange(providers: [any DataProvider], newState: DataProviderState, error: Error?) async {
        switch newState {
        case .initialized:
            KagamiLogger.spatialAnchor.info("ARKit providers initialized")

        case .running:
            isTracking = true
            KagamiLogger.spatialAnchor.info("ARKit tracking running")

        case .paused:
            isTracking = false
            KagamiLogger.spatialAnchor.notice("ARKit tracking paused")

        case .stopped:
            isTracking = false
            if let error = error {
                KagamiLogger.logError("ARKit stopped with error", error: error, logger: KagamiLogger.spatialAnchor)
                // Attempt recovery
                await attemptSessionRecovery()
            } else {
                KagamiLogger.spatialAnchor.info("ARKit tracking stopped")
            }

        @unknown default:
            break
        }
    }

    /// Handles session interruption gracefully
    private func handleSessionInterruption() async {
        isTracking = false
        // Preserve anchor state for recovery
        persistAnchors()
    }

    /// Attempts to recover ARKit session after interruption
    private func attemptSessionRecovery() async {
        // Wait briefly before attempting recovery
        try? await Task.sleep(nanoseconds: 1_000_000_000)

        guard WorldTrackingProvider.isSupported else { return }

        // Recreate providers
        worldTracking = WorldTrackingProvider()
        planeDetection = PlaneDetectionProvider(alignments: [.horizontal, .vertical])

        do {
            var providers: [any DataProvider] = [worldTracking!]
            if PlaneDetectionProvider.isSupported {
                providers.append(planeDetection!)
            }

            try await arSession?.run(providers)
            startUpdateLoop()
            KagamiLogger.spatialAnchor.info("ARKit session recovered")
        } catch {
            KagamiLogger.logError("Failed to recover ARKit session", error: error, logger: KagamiLogger.spatialAnchor)
        }
    }

    func stop() {
        updateTask?.cancel()
        updateTask = nil
        arSession?.stop()
        isTracking = false
        KagamiLogger.spatialAnchor.info("Spatial anchor service stopped")
    }

    // MARK: - Update Loop

    private func startUpdateLoop() {
        // Track head position for proxemic zones
        updateTask = Task {
            guard let worldTracking = worldTracking else { return }

            for await update in worldTracking.anchorUpdates {
                await processWorldUpdate(update)
            }
        }

        // Track plane detection
        if let planeDetection = planeDetection {
            Task {
                for await update in planeDetection.anchorUpdates {
                    await processPlaneUpdate(update)
                }
            }
        }
    }

    private func processWorldUpdate(_ update: AnchorUpdate<WorldAnchor>) async {
        let anchor = update.anchor
        guard anchor.isTracked else { return }

        let transform = anchor.originFromAnchorTransform
        headPosition = SIMD3<Float>(
            transform.columns.3.x,
            transform.columns.3.y,
            transform.columns.3.z
        )
        headForward = -SIMD3<Float>(
            transform.columns.2.x,
            transform.columns.2.y,
            transform.columns.2.z
        )

        // Update head-relative anchors
        updateHeadRelativeAnchors()
    }

    private func processPlaneUpdate(_ update: AnchorUpdate<PlaneAnchor>) async {
        let anchor = update.anchor

        switch update.event {
        case .added:
            let surface = DetectedSurface(
                id: anchor.id,
                classification: mapClassification(anchor.classification),
                center: SIMD3<Float>(
                    anchor.originFromAnchorTransform.columns.3.x,
                    anchor.originFromAnchorTransform.columns.3.y,
                    anchor.originFromAnchorTransform.columns.3.z
                ),
                extent: SIMD2<Float>(anchor.geometry.extent.width, anchor.geometry.extent.height),
                normal: SIMD3<Float>(0, 1, 0)  // Approximate
            )
            availableSurfaces.append(surface)

        case .updated:
            if let index = availableSurfaces.firstIndex(where: { $0.id == anchor.id }) {
                availableSurfaces[index] = DetectedSurface(
                    id: anchor.id,
                    classification: mapClassification(anchor.classification),
                    center: SIMD3<Float>(
                        anchor.originFromAnchorTransform.columns.3.x,
                        anchor.originFromAnchorTransform.columns.3.y,
                        anchor.originFromAnchorTransform.columns.3.z
                    ),
                    extent: SIMD2<Float>(anchor.geometry.extent.width, anchor.geometry.extent.height),
                    normal: SIMD3<Float>(0, 1, 0)
                )
            }

        case .removed:
            availableSurfaces.removeAll { $0.id == anchor.id }
        }
    }

    private func mapClassification(_ classification: PlaneAnchor.Classification) -> DetectedSurface.SurfaceClassification {
        switch classification {
        case .floor: return .floor
        case .wall: return .wall
        case .ceiling: return .ceiling
        case .table: return .table
        default: return .unknown
        }
    }

    // MARK: - Anchor Management

    /// Creates a new spatial anchor
    func createAnchor(
        at position: SIMD3<Float>,
        type: AnchorType,
        label: String
    ) -> SpatialAnchor {
        let anchor = SpatialAnchor(
            position: position,
            anchorType: type,
            label: label
        )
        activeAnchors.append(anchor)
        persistAnchors()
        return anchor
    }

    /// Creates an anchor at the optimal personal zone distance
    func createControlPanelAnchor(label: String = "Control Panel") -> SpatialAnchor {
        guard let head = headPosition, let forward = headForward else {
            // Fallback position
            return createAnchor(
                at: SIMD3<Float>(0, 1.4, -0.8),
                type: .headRelative,
                label: label
            )
        }

        // Place at personal zone distance (80cm ahead, slightly below eye level)
        let position = head + simd_normalize(forward) * 0.8 + SIMD3<Float>(0, -0.1, 0)

        return createAnchor(
            at: position,
            type: .headRelative,
            label: label
        )
    }

    /// Creates an anchor on the nearest suitable surface
    func createSurfaceAnchor(
        preferredClassification: DetectedSurface.SurfaceClassification = .table,
        label: String
    ) -> SpatialAnchor? {
        guard let head = headPosition else { return nil }

        // Find closest matching surface
        let suitable = availableSurfaces
            .filter { $0.classification == preferredClassification || preferredClassification == .unknown }
            .sorted { simd_length($0.center - head) < simd_length($1.center - head) }

        guard let surface = suitable.first else { return nil }

        return createAnchor(
            at: surface.center + SIMD3<Float>(0, 0.05, 0),  // Slightly above surface
            type: .surfaceLocked,
            label: label
        )
    }

    /// Removes an anchor
    func removeAnchor(_ id: UUID) {
        // Clear velocity state for this anchor
        clearAnchorVelocity(id)
        activeAnchors.removeAll { $0.id == id }
        persistAnchors()
    }

    /// Updates head-relative anchors to maintain position relative to user
    /// Uses critically damped spring motion for smooth, jitter-free movement
    private func updateHeadRelativeAnchors() {
        guard let head = headPosition, let forward = headForward else { return }

        let deltaTime: Float = 1.0 / 60.0  // Assume 60 FPS update rate

        for i in activeAnchors.indices {
            guard activeAnchors[i].anchorType == .headRelative else { continue }

            let anchorId = activeAnchors[i].id

            // Keep at personal zone distance, facing user
            let targetPosition = head + simd_normalize(forward) * 0.8 + SIMD3<Float>(0, -0.1, 0)

            // Apply critically damped spring motion instead of linear interpolation
            activeAnchors[i].position = dampedSpringPosition(
                current: activeAnchors[i].position,
                target: targetPosition,
                velocity: &anchorVelocities[anchorId],
                deltaTime: deltaTime
            )
        }
    }

    /// Calculates new position using critically damped spring dynamics
    /// This produces smooth, natural motion without oscillation or jitter
    ///
    /// - Parameters:
    ///   - current: Current position
    ///   - target: Target position to move toward
    ///   - velocity: Current velocity (inout, will be updated)
    ///   - deltaTime: Time step for integration
    /// - Returns: New position after applying spring dynamics
    private func dampedSpringPosition(
        current: SIMD3<Float>,
        target: SIMD3<Float>,
        velocity: inout SIMD3<Float>?,
        deltaTime: Float
    ) -> SIMD3<Float> {
        // Initialize velocity if needed
        if velocity == nil {
            velocity = SIMD3<Float>(repeating: 0)
        }

        guard var vel = velocity else {
            return current
        }

        // Critically damped spring equation:
        // F = -k * (x - target) - c * v
        // where c = 2 * sqrt(k) for critical damping
        //
        // Using damping ratio zeta = c / (2 * sqrt(k * m))
        // For critical damping, zeta = 1.0 (we use 0.7 for slightly underdamped, smoother feel)

        let displacement = current - target
        let dampingCoefficient = 2.0 * springDampingRatio * sqrt(springStiffness)

        // Calculate spring force: F = -k*x - c*v
        let springForce = -springStiffness * displacement
        let dampingForce = -dampingCoefficient * vel
        let acceleration = springForce + dampingForce

        // Semi-implicit Euler integration for stability
        vel = vel + acceleration * deltaTime
        let newPosition = current + vel * deltaTime

        // Update velocity reference
        velocity = vel

        // If very close to target and low velocity, snap to target
        let distanceToTarget = simd_length(newPosition - target)
        let speed = simd_length(vel)
        if distanceToTarget < 0.001 && speed < 0.01 {
            velocity = SIMD3<Float>(repeating: 0)
            return target
        }

        return newPosition
    }

    /// Clears velocity state for an anchor (call when anchor is removed or reset)
    private func clearAnchorVelocity(_ anchorId: UUID) {
        anchorVelocities.removeValue(forKey: anchorId)
    }

    // MARK: - Proxemic Zone Calculation

    /// Determines which proxemic zone a position falls into relative to user
    func proxemicZone(for position: SIMD3<Float>) -> ProxemicZone {
        guard let head = headPosition else { return .social }

        let distance = simd_length(position - head)

        for zone in ProxemicZone.allCases {
            if zone.distanceRange.contains(distance) {
                return zone
            }
        }

        return .ambient
    }

    /// Gets the ideal position for a given proxemic zone
    func idealPosition(for zone: ProxemicZone, direction: SIMD3<Float>? = nil) -> SIMD3<Float> {
        guard let head = headPosition else {
            return SIMD3<Float>(0, 1.4, -1.0)
        }

        let forward = direction ?? headForward ?? SIMD3<Float>(0, 0, -1)
        let normalizedForward = simd_normalize(forward)

        // Center of the zone range
        let distance: Float
        switch zone {
        case .intimate: distance = 0.3
        case .personal: distance = 0.8
        case .social: distance = 2.0
        case .ambient: distance = 4.0
        }

        return head + normalizedForward * distance
    }

    // MARK: - Persistence

    private func loadPersistedAnchors() {
        guard let data = UserDefaults.standard.data(forKey: anchorStorageKey),
              let anchors = try? JSONDecoder().decode([SpatialAnchor].self, from: data) else {
            return
        }

        // Only load world-locked anchors (head-relative make no sense to persist)
        activeAnchors = anchors.filter { $0.anchorType == .worldLocked || $0.anchorType == .surfaceLocked }
        KagamiLogger.spatialAnchor.info("Loaded \(activeAnchors.count) persisted anchors")
    }

    private func persistAnchors() {
        let persistable = activeAnchors.filter {
            $0.anchorType == .worldLocked || $0.anchorType == .surfaceLocked
        }

        if let data = try? JSONEncoder().encode(persistable) {
            UserDefaults.standard.set(data, forKey: anchorStorageKey)
        }
    }

    // MARK: - Spatial Queries

    /// Finds the nearest anchor to a position
    func nearestAnchor(to position: SIMD3<Float>) -> SpatialAnchor? {
        activeAnchors
            .filter { $0.isActive }
            .min { simd_length($0.position - position) < simd_length($1.position - position) }
    }

    /// Gets all anchors within a proxemic zone
    func anchors(in zone: ProxemicZone) -> [SpatialAnchor] {
        guard let head = headPosition else { return [] }

        return activeAnchors.filter { anchor in
            let distance = simd_length(anchor.position - head)
            return zone.distanceRange.contains(distance)
        }
    }

    /// Checks if user is looking at an anchor
    func isLookingAt(_ anchor: SpatialAnchor, threshold: Float = 0.3) -> Bool {
        guard let head = headPosition, let forward = headForward else { return false }

        let toAnchor = simd_normalize(anchor.position - head)
        let dotProduct = simd_dot(forward, toAnchor)

        // Dot product > threshold means looking roughly at it
        return dotProduct > (1.0 - threshold)
    }
}

// MARK: - SIMD Extensions

extension simd_quatf: Codable {
    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        let array = try container.decode([Float].self)
        guard array.count == 4 else {
            throw DecodingError.dataCorrupted(.init(codingPath: [], debugDescription: "Invalid quaternion"))
        }
        self.init(ix: array[0], iy: array[1], iz: array[2], r: array[3])
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        try container.encode([imag.x, imag.y, imag.z, real])
    }
}

extension SIMD3: Codable where Scalar == Float {
    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        let array = try container.decode([Float].self)
        guard array.count == 3 else {
            throw DecodingError.dataCorrupted(.init(codingPath: [], debugDescription: "Invalid SIMD3"))
        }
        self.init(array[0], array[1], array[2])
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        try container.encode([x, y, z])
    }
}

/*
 * 鏡
 * h(x) >= 0. Always.
 *
 * Spatial anchors ground the interface in physical reality.
 * Proxemic zones ensure appropriate intimacy of interaction.
 * The world becomes the interface.
 */
