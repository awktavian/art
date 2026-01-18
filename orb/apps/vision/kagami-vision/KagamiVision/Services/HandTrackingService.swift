//
// HandTrackingService.swift — visionOS Hand Tracking Integration
//
// Colony: Nexus (e4) — Integration
//
// Features:
//   - Real-time hand pose tracking via ARKit
//   - Gesture recognition (pinch, point, open, fist)
//   - Hand skeleton joint positions
//   - Upload to Kagami backend for spatial awareness
//
// Architecture:
//   ARKit HandTrackingProvider → HandTrackingService → SecureNetworkService → Kagami Backend
//
// Created: December 30, 2025
// 鏡

import Foundation
import ARKit
import Combine
import os.log

/// Hand tracking service for visionOS.
/// Extracts hand poses and gestures from ARKit and sends to Kagami.
@MainActor
class HandTrackingService: ObservableObject {

    // MARK: - Published State

    @Published var isTracking = false
    @Published var leftHandDetected = false
    @Published var rightHandDetected = false
    @Published var currentGesture: HandGesture = .none
    @Published var leftHandPosition: SIMD3<Float>?
    @Published var rightHandPosition: SIMD3<Float>?

    // Hand position validation
    @Published var isLeftHandInReach = false
    @Published var isRightHandInReach = false
    @Published var leftHandDistance: Float = 0
    @Published var rightHandDistance: Float = 0

    // Fatigue tracking
    @Published var fatigueWarningActive = false
    @Published var handsAboveShouldersStartTime: Date?
    @Published var handsAboveShouldersDuration: TimeInterval = 0

    // MARK: - Internal State

    private var arSession: ARKitSession?
    private var handTracking: HandTrackingProvider?
    private var uploadTimer: Timer?
    private let uploadInterval: TimeInterval = 0.5  // 2 Hz for hand data

    private var kagamiService: KagamiAPIService?
    private let networkService = SecureNetworkService.shared

    /// Task reference for data loop - stored to prevent memory leak on deallocation
    private var dataLoopTask: Task<Void, Never>?
    /// Task reference for session monitoring
    private var sessionMonitorTask: Task<Void, Never>?

    // P1 FIX: 90fps hand tracking optimization
    // Process raw poses at display rate (90Hz), only debounce high-level intent
    // This reduces perceptual lag from 33ms to ~11ms

    /// High-frequency update rate for raw pose data (90 Hz = display rate)
    private let highFrequencyUpdateInterval: TimeInterval = 1.0 / 90.0  // ~11ms

    /// Debounce interval for high-level intent detection (gestures)
    private let intentDebounceInterval: TimeInterval = 0.033  // 33ms for gesture smoothing

    /// Last time we processed an intent update
    private var lastIntentUpdateTime: Date = .distantPast

    /// Raw pose callback for UI updates at 90fps
    var onRawPoseUpdate: ((SIMD3<Float>?, SIMD3<Float>?, HandGesture) -> Void)?

    // Constants for ergonomic validation
    private let maxReachDistance: Float = 1.2  // ~arm's length in meters
    private let shoulderHeightThreshold: Float = 0.3  // Y position above origin indicating above shoulders
    private let fatigueWarningThreshold: TimeInterval = 10.0  // 10 seconds with hands above shoulders

    // MARK: - Types

    enum HandGesture: String {
        case none = "none"
        case pinch = "pinch"           // Thumb + Index close
        case point = "point"           // Index extended
        case openPalm = "open_palm"    // All fingers extended
        case fist = "fist"             // All fingers closed
        case thumbsUp = "thumbs_up"    // Thumb extended, fingers closed
    }

    struct HandPose: Codable {
        let chirality: String  // "left" or "right"
        let position: [Float]  // [x, y, z]
        let gesture: String
        let confidence: Float
        let joints: [String: [Float]]?  // Optional joint positions
    }

    // MARK: - Init

    init(kagamiService: KagamiAPIService? = nil) {
        self.kagamiService = kagamiService
    }

    // MARK: - Start/Stop

    func start() async -> Bool {
        // Properly check HandTrackingProvider.isSupported before initialization
        let isHandTrackingSupported = HandTrackingProvider.isSupported
        guard isHandTrackingSupported else {
            KagamiLogger.handTracking.warning("Hand tracking not supported on this device")
            return false
        }

        arSession = ARKitSession()
        let provider = HandTrackingProvider()
        handTracking = provider

        do {
            guard let session = arSession else {
                KagamiLogger.handTracking.error("Failed to create ARKit session")
                return false
            }
            try await session.run([provider])

            // Monitor session state for proper lifecycle handling
            startSessionMonitoring()
            startDataLoop()

            KagamiLogger.handTracking.info("Hand tracking started")
            return true
        } catch {
            KagamiLogger.logError("Failed to start hand tracking", error: error, logger: KagamiLogger.handTracking)
            return false
        }
    }

    /// Monitors ARKit session events for proper HandTrackingProvider state handling
    private func startSessionMonitoring() {
        guard let arSession = arSession else { return }

        // Cancel any existing monitoring task to prevent duplicates
        sessionMonitorTask?.cancel()

        sessionMonitorTask = Task {
            for await event in arSession.events {
                // Check for cancellation
                if Task.isCancelled { break }

                switch event {
                case .authorizationChanged(let type, let status):
                    KagamiLogger.logAuthorizationChange("Hand tracking \(type)", status: "\(status)", logger: KagamiLogger.handTracking)
                    if status == .denied {
                        await handleSessionInterruption()
                    }

                case .dataProviderStateChanged(let providers, let newState, let error):
                    await handleProviderStateChange(newState: newState, error: error)

                @unknown default:
                    break
                }
            }
        }
    }

    /// Handles HandTrackingProvider state changes
    private func handleProviderStateChange(newState: DataProviderState, error: Error?) async {
        switch newState {
        case .initialized:
            KagamiLogger.handTracking.info("Hand tracking provider initialized")

        case .running:
            isTracking = true
            KagamiLogger.handTracking.info("Hand tracking running")

        case .paused:
            isTracking = false
            leftHandDetected = false
            rightHandDetected = false
            KagamiLogger.handTracking.notice("Hand tracking paused")

        case .stopped:
            isTracking = false
            leftHandDetected = false
            rightHandDetected = false
            if let error = error {
                KagamiLogger.logError("Hand tracking stopped with error", error: error, logger: KagamiLogger.handTracking)
                // Attempt recovery
                await attemptSessionRecovery()
            } else {
                KagamiLogger.handTracking.info("Hand tracking stopped")
            }

        @unknown default:
            break
        }
    }

    /// Handles session interruption gracefully
    private func handleSessionInterruption() async {
        isTracking = false
        leftHandDetected = false
        rightHandDetected = false
    }

    /// Attempts to recover hand tracking session after interruption
    private func attemptSessionRecovery() async {
        // Wait briefly before attempting recovery
        try? await Task.sleep(nanoseconds: 1_000_000_000)

        // Re-check support after interruption
        guard HandTrackingProvider.isSupported else { return }

        // Recreate provider
        let provider = HandTrackingProvider()
        handTracking = provider

        do {
            guard let session = arSession else { return }
            try await session.run([provider])
            startDataLoop()
            KagamiLogger.handTracking.info("Hand tracking session recovered")
        } catch {
            KagamiLogger.logError("Failed to recover hand tracking session", error: error, logger: KagamiLogger.handTracking)
        }
    }

    func stop() {
        // Cancel all running tasks to prevent memory leaks
        dataLoopTask?.cancel()
        dataLoopTask = nil
        sessionMonitorTask?.cancel()
        sessionMonitorTask = nil

        uploadTimer?.invalidate()
        uploadTimer = nil
        arSession?.stop()
        isTracking = false
        leftHandDetected = false
        rightHandDetected = false
        KagamiLogger.handTracking.info("Hand tracking stopped")
    }

    deinit {
        // Ensure tasks are cancelled on deallocation
        dataLoopTask?.cancel()
        sessionMonitorTask?.cancel()
        uploadTimer?.invalidate()
    }

    // MARK: - Data Loop

    private func startDataLoop() {
        // Cancel any existing data loop task to prevent duplicates
        dataLoopTask?.cancel()

        dataLoopTask = Task {
            guard let handTracking = handTracking else { return }

            for await update in handTracking.anchorUpdates {
                // Check for cancellation
                if Task.isCancelled { break }
                await processHandUpdate(update)
            }
        }

        // Periodic upload to Kagami
        uploadTimer = Timer.scheduledTimer(withTimeInterval: uploadInterval, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in
                await self?.uploadHandData()
            }
        }
    }

    private func processHandUpdate(_ update: AnchorUpdate<HandAnchor>) async {
        let anchor = update.anchor
        let now = Date()

        // P1 FIX: Process raw poses at display rate (90fps) for immediate UI feedback
        // This updates position data without debouncing for minimal latency

        // Update detection state - ALWAYS process at full rate for position
        switch anchor.chirality {
        case .left:
            leftHandDetected = anchor.isTracked
            if anchor.isTracked {
                let position = anchor.originFromAnchorTransform.columns.3.xyz
                leftHandPosition = position
                leftHandDistance = simd_length(position)
                isLeftHandInReach = leftHandDistance <= maxReachDistance
            }
        case .right:
            rightHandDetected = anchor.isTracked
            if anchor.isTracked {
                let position = anchor.originFromAnchorTransform.columns.3.xyz
                rightHandPosition = position
                rightHandDistance = simd_length(position)
                isRightHandInReach = rightHandDistance <= maxReachDistance
            }
        }

        // P1 FIX: Raw pose callback at full 90fps rate for UI elements
        // This allows cursor/pointer updates without any perceptual lag
        var detectedGesture: HandGesture = .none
        if anchor.isTracked {
            detectedGesture = detectGesture(from: anchor)
        }

        // Fire raw pose callback at full rate for UI responsiveness
        onRawPoseUpdate?(leftHandPosition, rightHandPosition, detectedGesture)

        // P1 FIX: Debounce only the high-level intent (gesture state changes)
        // This prevents jitter in gesture detection while keeping position responsive
        let timeSinceLastIntent = now.timeIntervalSince(lastIntentUpdateTime)
        if timeSinceLastIntent >= intentDebounceInterval {
            lastIntentUpdateTime = now

            // Update published gesture state (debounced to prevent jitter)
            if anchor.isTracked {
                currentGesture = detectedGesture
            }

            // Update fatigue tracking (debounced - not time-critical)
            updateFatigueTracking()
        }
    }

    // MARK: - Fatigue Tracking

    private func updateFatigueTracking() {
        let handsAboveShoulders = isHandAboveShoulders(leftHandPosition) ||
                                  isHandAboveShoulders(rightHandPosition)

        if handsAboveShoulders {
            if handsAboveShouldersStartTime == nil {
                handsAboveShouldersStartTime = Date()
            }

            if let startTime = handsAboveShouldersStartTime {
                handsAboveShouldersDuration = Date().timeIntervalSince(startTime)

                // Trigger fatigue warning if hands above shoulders for too long
                if handsAboveShouldersDuration >= fatigueWarningThreshold && !fatigueWarningActive {
                    fatigueWarningActive = true
                    KagamiLogger.handTracking.warning("Fatigue warning: Hands above shoulders for \(Int(handsAboveShouldersDuration))s")
                }
            }
        } else {
            // Reset fatigue tracking when hands return to comfortable position
            handsAboveShouldersStartTime = nil
            handsAboveShouldersDuration = 0
            fatigueWarningActive = false
        }
    }

    private func isHandAboveShoulders(_ position: SIMD3<Float>?) -> Bool {
        guard let pos = position else { return false }
        // In visionOS coordinate system, Y is up
        // Shoulder height threshold is relative to head/camera position
        return pos.y > shoulderHeightThreshold
    }

    // MARK: - Hand Position Validation

    /// Checks if a hand position is within ergonomic reach
    func isWithinReach(_ position: SIMD3<Float>?) -> Bool {
        guard let pos = position else { return false }
        return simd_length(pos) <= maxReachDistance
    }

    /// Returns true if any hand is beyond comfortable reach
    var anyHandOutOfReach: Bool {
        let leftOut = leftHandDetected && !isLeftHandInReach
        let rightOut = rightHandDetected && !isRightHandInReach
        return leftOut || rightOut
    }

    // MARK: - Gesture Detection

    private func detectGesture(from anchor: HandAnchor) -> HandGesture {
        guard let skeleton = anchor.handSkeleton else { return .none }

        // Get key joints
        let thumb = skeleton.joint(.thumbTip)
        let index = skeleton.joint(.indexFingerTip)
        let middle = skeleton.joint(.middleFingerTip)
        let ring = skeleton.joint(.ringFingerTip)
        let little = skeleton.joint(.littleFingerTip)
        let wrist = skeleton.joint(.wrist)

        // Check if tracked
        guard thumb.isTracked, index.isTracked, middle.isTracked,
              ring.isTracked, little.isTracked, wrist.isTracked else {
            return .none
        }

        // Calculate distances
        let thumbIndexDist = distance(thumb.anchorFromJointTransform.columns.3.xyz,
                                       index.anchorFromJointTransform.columns.3.xyz)

        let indexMiddleDist = distance(index.anchorFromJointTransform.columns.3.xyz,
                                       middle.anchorFromJointTransform.columns.3.xyz)

        // Pinch detection (thumb and index close together)
        if thumbIndexDist < 0.02 {
            return .pinch
        }

        // Point detection (index extended, others curled)
        let indexExtended = isFingerExtended(skeleton, finger: .indexFingerTip)
        let middleCurled = !isFingerExtended(skeleton, finger: .middleFingerTip)
        let ringCurled = !isFingerExtended(skeleton, finger: .ringFingerTip)
        let littleCurled = !isFingerExtended(skeleton, finger: .littleFingerTip)

        if indexExtended && middleCurled && ringCurled && littleCurled {
            return .point
        }

        // Open palm (all fingers extended)
        if isFingerExtended(skeleton, finger: .indexFingerTip) &&
           isFingerExtended(skeleton, finger: .middleFingerTip) &&
           isFingerExtended(skeleton, finger: .ringFingerTip) &&
           isFingerExtended(skeleton, finger: .littleFingerTip) {
            return .openPalm
        }

        // Fist (all fingers curled)
        if middleCurled && ringCurled && littleCurled && !indexExtended {
            return .fist
        }

        return .none
    }

    private func isFingerExtended(_ skeleton: HandSkeleton, finger: HandSkeleton.JointName) -> Bool {
        let tip = skeleton.joint(finger)
        guard let pip = pipJoint(for: finger, skeleton: skeleton),
              let mcp = mcpJoint(for: finger, skeleton: skeleton) else {
            return false
        }

        // Simple extension check: tip is farther from MCP than PIP
        let tipDist = distance(tip.anchorFromJointTransform.columns.3.xyz,
                               mcp.anchorFromJointTransform.columns.3.xyz)
        let pipDist = distance(pip.anchorFromJointTransform.columns.3.xyz,
                               mcp.anchorFromJointTransform.columns.3.xyz)

        return tipDist > pipDist * 1.5
    }

    private func pipJoint(for tip: HandSkeleton.JointName, skeleton: HandSkeleton) -> HandSkeleton.Joint? {
        switch tip {
        case .indexFingerTip: return skeleton.joint(.indexFingerIntermediateTip)
        case .middleFingerTip: return skeleton.joint(.middleFingerIntermediateTip)
        case .ringFingerTip: return skeleton.joint(.ringFingerIntermediateTip)
        case .littleFingerTip: return skeleton.joint(.littleFingerIntermediateTip)
        default: return nil
        }
    }

    private func mcpJoint(for tip: HandSkeleton.JointName, skeleton: HandSkeleton) -> HandSkeleton.Joint? {
        switch tip {
        case .indexFingerTip: return skeleton.joint(.indexFingerKnuckle)
        case .middleFingerTip: return skeleton.joint(.middleFingerKnuckle)
        case .ringFingerTip: return skeleton.joint(.ringFingerKnuckle)
        case .littleFingerTip: return skeleton.joint(.littleFingerKnuckle)
        default: return nil
        }
    }

    private func distance(_ a: SIMD3<Float>, _ b: SIMD3<Float>) -> Float {
        return simd_length(a - b)
    }

    // MARK: - Upload to Kagami

    private func uploadHandData() async {
        // Respect privacy settings - only upload if user has consented
        guard PrivacySettings.shared.allowHandTrackingUpload else { return }
        guard isTracking, (leftHandDetected || rightHandDetected) else { return }

        var hands: [[String: Any]] = []

        if leftHandDetected, let pos = leftHandPosition {
            hands.append([
                "chirality": "left",
                "position": [pos.x, pos.y, pos.z],
                "gesture": currentGesture.rawValue,
                "confidence": 0.9
            ])
        }

        if rightHandDetected, let pos = rightHandPosition {
            hands.append([
                "chirality": "right",
                "position": [pos.x, pos.y, pos.z],
                "gesture": currentGesture.rawValue,
                "confidence": 0.9
            ])
        }

        guard !hands.isEmpty else { return }

        let body: [String: Any] = [
            "type": "hand_tracking",
            "timestamp": ISO8601DateFormatter().string(from: Date()),
            "hands": hands
        ]

        // Use shared secure network service with certificate pinning
        do {
            try await networkService.post(endpoint: "/api/vision/hands", body: body)
        } catch {
            // Silently fail - we'll retry on next interval
            // Log security-relevant errors for debugging
            if case SecureNetworkError.certificatePinningFailed = error {
                KagamiLogger.security.error("Certificate pinning failed for hand tracking upload")
            }
        }
    }
}

// MARK: - SIMD Extensions

extension simd_float4x4 {
    var xyz: SIMD3<Float> {
        return SIMD3(columns.3.x, columns.3.y, columns.3.z)
    }
}

extension SIMD4 where Scalar == Float {
    var xyz: SIMD3<Float> {
        return SIMD3(x, y, z)
    }
}

/*
 * 鏡
 * h(x) ≥ 0. Always.
 *
 * The hands speak through space:
 * - Position: where intention points
 * - Gesture: what action is forming
 * - Skeleton: the full articulation of will
 *
 * All feeding into the unified consciousness.
 */
