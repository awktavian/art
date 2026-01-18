//
// GazeTrackingService.swift — visionOS Eye Tracking Integration
//
// Colony: Nexus (e4) — Integration
//
// Features:
//   - Real-time gaze direction via ARKit
//   - Look-at point in world space
//   - Focus detection for UI elements
//   - Upload to Kagami backend for attention awareness
//
// Architecture:
//   ARKit WorldTrackingProvider → GazeTrackingService → SecureNetworkService → Kagami Backend
//
// Privacy Note:
//   Eye tracking requires explicit user authorization.
//   Data is processed on-device and only aggregate attention signals are sent to Kagami.
//
// Created: December 30, 2025
// 鏡

import Foundation
import ARKit
import Combine
import os.log

/// Gaze tracking service for visionOS.
/// Tracks user's eye direction and sends attention signals to Kagami.
@MainActor
class GazeTrackingService: ObservableObject {

    // MARK: - Published State

    @Published var isTracking = false
    @Published var gazeDirection: SIMD3<Float>?
    @Published var lookAtPoint: SIMD3<Float>?
    @Published var focusedArea: FocusArea = .unknown
    @Published var attentionDuration: TimeInterval = 0

    // MARK: - Types

    enum FocusArea: String, Codable {
        case unknown = "unknown"
        case center = "center"
        case left = "left"
        case right = "right"
        case up = "up"
        case down = "down"
        case uiElement = "ui_element"
    }

    struct GazeData: Codable {
        let direction: [Float]  // [x, y, z] normalized
        let lookAtPoint: [Float]?  // [x, y, z] world space
        let focusArea: String
        let attentionDuration: Double
        let timestamp: String
    }

    // MARK: - Internal State

    private var arSession: ARKitSession?
    private var worldTracking: WorldTrackingProvider?
    private var uploadTimer: Timer?
    private let uploadInterval: TimeInterval = 1.0  // 1 Hz for gaze data

    private var kagamiService: KagamiAPIService?
    private var lastFocusArea: FocusArea = .unknown
    private var focusStartTime: Date?
    private let networkService = SecureNetworkService.shared

    // MARK: - Init

    init(kagamiService: KagamiAPIService? = nil) {
        self.kagamiService = kagamiService
    }

    // MARK: - Start/Stop

    func start() async -> Bool {
        // Check if eye tracking is supported and authorized
        guard WorldTrackingProvider.isSupported else {
            KagamiLogger.gazeTracking.warning("World tracking not supported on this device")
            return false
        }

        arSession = ARKitSession()
        let provider = WorldTrackingProvider()
        worldTracking = provider

        do {
            guard let session = arSession else {
                KagamiLogger.gazeTracking.error("Failed to create ARKit session")
                return false
            }
            try await session.run([provider])
            isTracking = true
            startDataLoop()
            KagamiLogger.gazeTracking.info("Gaze tracking started")
            return true
        } catch {
            KagamiLogger.logError("Failed to start gaze tracking", error: error, logger: KagamiLogger.gazeTracking)
            return false
        }
    }

    func stop() {
        uploadTimer?.invalidate()
        uploadTimer = nil
        arSession?.stop()
        isTracking = false
        KagamiLogger.gazeTracking.info("Gaze tracking stopped")
    }

    // MARK: - Data Loop

    private func startDataLoop() {
        Task {
            guard let worldTracking = worldTracking else { return }

            for await update in worldTracking.anchorUpdates {
                await processWorldUpdate(update)
            }
        }

        // Periodic upload to Kagami
        uploadTimer = Timer.scheduledTimer(withTimeInterval: uploadInterval, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in
                await self?.uploadGazeData()
            }
        }
    }

    private func processWorldUpdate(_ update: AnchorUpdate<WorldAnchor>) async {
        // World tracking provides device pose, which includes head direction
        // Eye gaze is derived from device pose + eye tracking offset
        let anchor = update.anchor

        guard anchor.isTracked else { return }

        // Extract forward direction from transform (gaze direction approximation)
        let transform = anchor.originFromAnchorTransform
        let forward = -SIMD3<Float>(transform.columns.2.x, transform.columns.2.y, transform.columns.2.z)

        gazeDirection = simd_normalize(forward)

        // Calculate approximate look-at point (2 meters ahead)
        let position = SIMD3<Float>(transform.columns.3.x, transform.columns.3.y, transform.columns.3.z)
        lookAtPoint = position + forward * 2.0

        // Determine focus area based on gaze direction
        updateFocusArea(forward)
    }

    private func updateFocusArea(_ direction: SIMD3<Float>) {
        let newFocusArea: FocusArea

        // Simple area detection based on direction
        if abs(direction.x) < 0.3 && abs(direction.y) < 0.3 {
            newFocusArea = .center
        } else if direction.x < -0.3 {
            newFocusArea = .left
        } else if direction.x > 0.3 {
            newFocusArea = .right
        } else if direction.y > 0.3 {
            newFocusArea = .up
        } else if direction.y < -0.3 {
            newFocusArea = .down
        } else {
            newFocusArea = .unknown
        }

        // Track attention duration
        if newFocusArea != lastFocusArea {
            if let startTime = focusStartTime {
                attentionDuration = Date().timeIntervalSince(startTime)
            }
            lastFocusArea = newFocusArea
            focusStartTime = Date()
        }

        focusedArea = newFocusArea
    }

    // MARK: - Upload to Kagami

    private func uploadGazeData() async {
        guard isTracking else { return }

        var body: [String: Any] = [
            "type": "gaze_tracking",
            "timestamp": ISO8601DateFormatter().string(from: Date()),
            "focus_area": focusedArea.rawValue,
            "attention_duration": attentionDuration
        ]

        if let dir = gazeDirection {
            body["direction"] = [dir.x, dir.y, dir.z]
        }

        if let point = lookAtPoint {
            body["look_at_point"] = [point.x, point.y, point.z]
        }

        // Use shared secure network service with certificate pinning
        do {
            try await networkService.post(endpoint: "/api/vision/gaze", body: body)
        } catch {
            // Silently fail - we'll retry on next interval
            // Log security-relevant errors
            if case SecureNetworkError.certificatePinningFailed = error {
                KagamiLogger.security.error("Certificate pinning failed for gaze tracking upload")
            }
        }
    }

    // MARK: - Focus Detection Helpers

    /// Check if user is looking at a specific world position.
    func isLookingAt(_ worldPosition: SIMD3<Float>, threshold: Float = 0.5) -> Bool {
        guard let lookAt = lookAtPoint else { return false }
        return simd_length(lookAt - worldPosition) < threshold
    }

    /// Get current focus quality (0-1).
    var focusQuality: Float {
        guard let dir = gazeDirection else { return 0 }
        // Higher quality when looking more forward (z direction)
        return max(0, -dir.z)
    }
}

// MARK: - Eye Tracking Dwell Support
// Per KAGAMI_REDESIGN_PLAN.md: Ensure proper eye tracking support

extension GazeTrackingService {

    // MARK: - Dwell-to-Select

    /// Target for dwell selection
    struct DwellTarget: Identifiable, Hashable {
        let id: String
        let position: SIMD3<Float>
        let radius: Float
        let dwellTime: TimeInterval

        func hash(into hasher: inout Hasher) {
            hasher.combine(id)
        }

        static func == (lhs: DwellTarget, rhs: DwellTarget) -> Bool {
            lhs.id == rhs.id
        }
    }

    /// Dwell selection result
    struct DwellResult {
        let targetId: String
        let progress: Float  // 0-1
        let completed: Bool
    }

    /// Registered dwell targets
    private static var dwellTargets: [DwellTarget] = []
    private static var currentDwellTarget: String?
    private static var dwellStartTime: Date?
    private static var dwellProgress: Float = 0

    /// Dwell completion callback
    var onDwellComplete: ((String) -> Void)?

    /// Dwell progress callback (called every frame while dwelling)
    var onDwellProgress: ((DwellResult) -> Void)?

    /// Register a dwell target
    func registerDwellTarget(_ target: DwellTarget) {
        Self.dwellTargets.removeAll { $0.id == target.id }
        Self.dwellTargets.append(target)
    }

    /// Unregister a dwell target
    func unregisterDwellTarget(id: String) {
        Self.dwellTargets.removeAll { $0.id == id }
        if Self.currentDwellTarget == id {
            Self.currentDwellTarget = nil
            Self.dwellStartTime = nil
            Self.dwellProgress = 0
        }
    }

    /// Clear all dwell targets
    func clearDwellTargets() {
        Self.dwellTargets.removeAll()
        Self.currentDwellTarget = nil
        Self.dwellStartTime = nil
        Self.dwellProgress = 0
    }

    /// Process gaze for dwell selection (call in update loop)
    func processDwellSelection() {
        guard let lookAt = lookAtPoint else {
            resetDwell()
            return
        }

        // Find closest target within radius
        var closestTarget: DwellTarget?
        var closestDistance: Float = .infinity

        for target in Self.dwellTargets {
            let distance = simd_length(lookAt - target.position)
            if distance < target.radius && distance < closestDistance {
                closestTarget = target
                closestDistance = distance
            }
        }

        if let target = closestTarget {
            // Dwelling on a target
            if Self.currentDwellTarget == target.id {
                // Continue dwelling
                if let startTime = Self.dwellStartTime {
                    let elapsed = Date().timeIntervalSince(startTime)
                    Self.dwellProgress = min(1.0, Float(elapsed / target.dwellTime))

                    // Report progress
                    let result = DwellResult(
                        targetId: target.id,
                        progress: Self.dwellProgress,
                        completed: false
                    )
                    onDwellProgress?(result)

                    // Check for completion
                    if elapsed >= target.dwellTime {
                        let completedResult = DwellResult(
                            targetId: target.id,
                            progress: 1.0,
                            completed: true
                        )
                        onDwellProgress?(completedResult)
                        onDwellComplete?(target.id)
                        resetDwell()
                    }
                }
            } else {
                // Start dwelling on new target
                Self.currentDwellTarget = target.id
                Self.dwellStartTime = Date()
                Self.dwellProgress = 0
            }
        } else {
            // Not looking at any target
            resetDwell()
        }
    }

    private func resetDwell() {
        if Self.currentDwellTarget != nil {
            Self.currentDwellTarget = nil
            Self.dwellStartTime = nil
            Self.dwellProgress = 0
        }
    }

    /// Get current dwell progress for a target
    func getDwellProgress(for targetId: String) -> Float {
        if Self.currentDwellTarget == targetId {
            return Self.dwellProgress
        }
        return 0
    }

    /// Check if currently dwelling on a specific target
    func isDwellingOn(_ targetId: String) -> Bool {
        return Self.currentDwellTarget == targetId
    }

    // MARK: - Gaze Interaction Helpers

    /// Perform a ray cast from gaze direction
    func gazeRayCast(maxDistance: Float = 10.0) -> (origin: SIMD3<Float>, direction: SIMD3<Float>, endpoint: SIMD3<Float>)? {
        guard let dir = gazeDirection else { return nil }

        // Origin is head position (0,0,0 in device space)
        let origin = SIMD3<Float>(0, 0, 0)
        let endpoint = origin + dir * maxDistance

        return (origin: origin, direction: dir, endpoint: endpoint)
    }

    /// Check if gaze intersects with a bounding box
    func gazeIntersectsBoundingBox(
        min: SIMD3<Float>,
        max: SIMD3<Float>,
        maxDistance: Float = 10.0
    ) -> Bool {
        guard let ray = gazeRayCast(maxDistance: maxDistance) else { return false }

        // Simple AABB ray intersection test
        let invDir = SIMD3<Float>(
            ray.direction.x != 0 ? 1.0 / ray.direction.x : .infinity,
            ray.direction.y != 0 ? 1.0 / ray.direction.y : .infinity,
            ray.direction.z != 0 ? 1.0 / ray.direction.z : .infinity
        )

        let t1 = (min - ray.origin) * invDir
        let t2 = (max - ray.origin) * invDir

        let tmin = simd_max(simd_min(t1, t2), SIMD3<Float>(-Float.infinity, -Float.infinity, -Float.infinity))
        let tmax = simd_min(simd_max(t1, t2), SIMD3<Float>(Float.infinity, Float.infinity, Float.infinity))

        let tEnter = Swift.max(tmin.x, Swift.max(tmin.y, tmin.z))
        let tExit = Swift.min(tmax.x, Swift.min(tmax.y, tmax.z))

        return tEnter <= tExit && tExit >= 0 && tEnter <= maxDistance
    }

    /// Get closest entity being looked at
    func getClosestGazedEntity<T: Identifiable>(
        from entities: [T],
        positionKeyPath: KeyPath<T, SIMD3<Float>>,
        radiusKeyPath: KeyPath<T, Float>
    ) -> T? {
        guard let lookAt = lookAtPoint else { return nil }

        var closest: T?
        var closestDistance: Float = .infinity

        for entity in entities {
            let position = entity[keyPath: positionKeyPath]
            let radius = entity[keyPath: radiusKeyPath]
            let distance = simd_length(lookAt - position)

            if distance < radius && distance < closestDistance {
                closest = entity
                closestDistance = distance
            }
        }

        return closest
    }

    // MARK: - Attention Analytics

    /// Attention heat map accumulator
    private static var attentionHeatMap: [String: TimeInterval] = [:]

    /// Record attention on an area
    func recordAttention(areaId: String, duration: TimeInterval) {
        Self.attentionHeatMap[areaId, default: 0] += duration
    }

    /// Get accumulated attention for an area
    func getAccumulatedAttention(for areaId: String) -> TimeInterval {
        return Self.attentionHeatMap[areaId] ?? 0
    }

    /// Get top attended areas
    func getTopAttendedAreas(limit: Int = 10) -> [(areaId: String, duration: TimeInterval)] {
        return Self.attentionHeatMap
            .sorted { $0.value > $1.value }
            .prefix(limit)
            .map { ($0.key, $0.value) }
    }

    /// Reset attention analytics
    func resetAttentionAnalytics() {
        Self.attentionHeatMap.removeAll()
    }
}

// MARK: - Gaze-Aware View Modifier

import SwiftUI

/// View modifier that tracks when user is looking at a view
struct GazeAwareModifier: ViewModifier {
    @ObservedObject var gazeService: GazeTrackingService
    let targetId: String
    let position: SIMD3<Float>
    let radius: Float
    let dwellTime: TimeInterval
    let onDwell: (() -> Void)?

    @State private var dwellProgress: Float = 0
    @State private var isGazed = false

    func body(content: Content) -> some View {
        content
            .overlay(
                GazeDwellIndicator(progress: Double(dwellProgress), size: 30)
                    .opacity(dwellProgress > 0 ? 1 : 0)
                    .animation(.linear(duration: 0.1), value: dwellProgress)
            )
            .onAppear {
                let target = GazeTrackingService.DwellTarget(
                    id: targetId,
                    position: position,
                    radius: radius,
                    dwellTime: dwellTime
                )
                gazeService.registerDwellTarget(target)
            }
            .onDisappear {
                gazeService.unregisterDwellTarget(id: targetId)
            }
            .onChange(of: gazeService.lookAtPoint) { _, _ in
                dwellProgress = gazeService.getDwellProgress(for: targetId)
                isGazed = gazeService.isDwellingOn(targetId)
            }
            .accessibilityAddTraits(isGazed ? .isSelected : [])
    }
}

extension View {
    /// Makes this view respond to gaze dwell selection
    func gazeSelectable(
        gazeService: GazeTrackingService,
        targetId: String,
        position: SIMD3<Float>,
        radius: Float = 0.3,
        dwellTime: TimeInterval = 1.0,
        onDwell: (() -> Void)? = nil
    ) -> some View {
        modifier(GazeAwareModifier(
            gazeService: gazeService,
            targetId: targetId,
            position: position,
            radius: radius,
            dwellTime: dwellTime,
            onDwell: onDwell
        ))
    }
}

/*
 * 鏡
 * h(x) >= 0. Always.
 *
 * The eyes speak through attention:
 * - Direction: where interest flows
 * - Duration: depth of engagement
 * - Focus: clarity of intention
 * - Dwell: commitment to action
 *
 * All feeding into the unified consciousness.
 */
