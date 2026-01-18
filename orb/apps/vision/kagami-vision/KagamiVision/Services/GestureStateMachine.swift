//
// GestureStateMachine.swift — Gesture Conflict Prevention with ML Confidence
//
// Colony: Nexus (e4) — Integration / Forge (e2) — Execution
//
// P1 FIX: GestureStateMachine prevents gesture conflicts
// P2 FIX: ML-based confidence scoring and gesture disambiguation
//
// Features:
//   - Single active gesture at a time
//   - Gesture queue for pending gestures
//   - Atomic entity updates via actor isolation
//   - Priority-based gesture handling
//   - Timeout-based gesture cancellation
//   - ML-based confidence scoring (P2)
//   - Gesture disambiguation using context (P2)
//   - Historical pattern learning (P2)
//
// Architecture:
//   HandTracking → GestureRecognizer → GestureStateMachine → Entity Updates
//                                    ↓
//                             MLConfidenceScorer
//                                    ↓
//                            GestureDisambiguator
//
// Created: January 2, 2026
// 鏡

import Foundation
import Combine
import simd
import CoreML
import Accelerate

/// P1 FIX: Actor-based gesture state machine that prevents gesture conflicts
/// by ensuring only one gesture is active at a time with queued fallback
/// P2 FIX: Includes ML-based confidence scoring for improved recognition
@MainActor
final class GestureStateMachine: ObservableObject {

    // MARK: - Published State

    @Published private(set) var currentState: GestureState = .idle
    @Published private(set) var activeGesture: ActiveGesture?
    @Published private(set) var queuedGestures: [QueuedGesture] = []
    @Published private(set) var lastCompletedGesture: SpatialGestureRecognizer.RecognizedGesture?

    // P2: ML confidence state
    @Published private(set) var currentConfidence: Float = 0.0
    @Published private(set) var disambiguationActive = false
    @Published private(set) var skillLevel: SkillLevel = .intermediate

    // MARK: - Types

    /// Gesture lifecycle states
    enum GestureState: String, CaseIterable {
        case idle           // No gesture active
        case pending        // Gesture detected, awaiting confirmation
        case active         // Gesture is being performed
        case completing     // Gesture is finishing
        case cancelled      // Gesture was cancelled
        case disambiguating // P2: Multiple gestures detected, resolving
    }

    /// Priority levels for gesture handling
    enum GesturePriority: Int, Comparable {
        case low = 0        // Background gestures
        case normal = 1     // Standard interactions
        case high = 2       // Navigation gestures
        case critical = 3   // Safety gestures (fist, emergency)

        static func < (lhs: GesturePriority, rhs: GesturePriority) -> Bool {
            return lhs.rawValue < rhs.rawValue
        }
    }

    /// P2: User skill level for adaptive gesture complexity
    enum SkillLevel: String, CaseIterable {
        case beginner = "beginner"
        case intermediate = "intermediate"
        case expert = "expert"

        var confidenceThreshold: Float {
            switch self {
            case .beginner: return 0.7    // Higher threshold for beginners
            case .intermediate: return 0.6
            case .expert: return 0.5      // Experts can use lower confidence
            }
        }

        var availableGestures: Set<SpatialGestureRecognizer.RecognizedGesture> {
            switch self {
            case .beginner:
                return [.pinch, .tap, .swipeUp, .swipeDown, .openPalm]
            case .intermediate:
                return [.pinch, .tap, .swipeUp, .swipeDown, .swipeLeft, .swipeRight,
                        .openPalm, .fist, .pinchDrag, .point]
            case .expert:
                return Set(SpatialGestureRecognizer.RecognizedGesture.allCases)
            }
        }
    }

    /// Currently active gesture with metadata
    struct ActiveGesture: Identifiable {
        let id: UUID
        let gesture: SpatialGestureRecognizer.RecognizedGesture
        let priority: GesturePriority
        let startTime: Date
        var progress: Float
        var targetEntityID: UUID?
        var confidence: Float  // P2: ML confidence score
        var contextualBoost: Float  // P2: Boost from contextual factors

        init(
            gesture: SpatialGestureRecognizer.RecognizedGesture,
            priority: GesturePriority = .normal,
            targetEntityID: UUID? = nil,
            confidence: Float = 1.0,
            contextualBoost: Float = 0.0
        ) {
            self.id = UUID()
            self.gesture = gesture
            self.priority = priority
            self.startTime = Date()
            self.progress = 0
            self.targetEntityID = targetEntityID
            self.confidence = confidence
            self.contextualBoost = contextualBoost
        }

        var duration: TimeInterval {
            return Date().timeIntervalSince(startTime)
        }

        /// Effective confidence including contextual boost
        var effectiveConfidence: Float {
            return min(1.0, confidence + contextualBoost)
        }
    }

    /// Queued gesture waiting to be processed
    struct QueuedGesture: Identifiable {
        let id: UUID
        let gesture: SpatialGestureRecognizer.RecognizedGesture
        let priority: GesturePriority
        let queuedAt: Date
        let targetEntityID: UUID?
        let timeout: TimeInterval
        let confidence: Float  // P2

        init(
            gesture: SpatialGestureRecognizer.RecognizedGesture,
            priority: GesturePriority = .normal,
            targetEntityID: UUID? = nil,
            timeout: TimeInterval = 2.0,
            confidence: Float = 1.0
        ) {
            self.id = UUID()
            self.gesture = gesture
            self.priority = priority
            self.queuedAt = Date()
            self.targetEntityID = targetEntityID
            self.timeout = timeout
            self.confidence = confidence
        }

        var isExpired: Bool {
            return Date().timeIntervalSince(queuedAt) > timeout
        }
    }

    /// Entity update operation for atomic processing
    struct EntityUpdate {
        let entityID: UUID
        let gestureID: UUID
        let updateType: UpdateType
        let value: Any?
        let timestamp: Date

        enum UpdateType {
            case position(SIMD3<Float>)
            case rotation(Float)
            case scale(Float)
            case brightness(Float)
            case selection(Bool)
            case custom(String)
        }
    }

    // MARK: - Configuration

    /// Maximum queue size to prevent memory issues
    private let maxQueueSize = 5

    /// Timeout for gesture confirmation
    private let confirmationTimeout: TimeInterval = 0.1

    /// Maximum active gesture duration before auto-cancel
    private let maxGestureDuration: TimeInterval = 10.0

    // MARK: - Internal State

    private var pendingUpdates: [EntityUpdate] = []
    private var timeoutTask: Task<Void, Never>?
    private var updateLock = NSLock()

    // P2: ML Confidence Scorer
    private let confidenceScorer = MLGestureConfidenceScorer()

    // P2: Gesture Disambiguator
    private let disambiguator = GestureDisambiguator()

    // P2: Historical pattern tracker
    private let patternTracker = GesturePatternTracker()

    /// Callback for entity updates
    var onEntityUpdate: ((EntityUpdate) -> Void)?

    /// Callback for gesture completion
    var onGestureCompleted: ((SpatialGestureRecognizer.RecognizedGesture, Bool) -> Void)?

    /// P2: Callback for confidence updates
    var onConfidenceUpdate: ((SpatialGestureRecognizer.RecognizedGesture, Float) -> Void)?

    // MARK: - Public API

    /// Attempts to begin a new gesture with ML confidence scoring
    /// Returns true if gesture was accepted, false if queued or rejected
    @discardableResult
    func beginGesture(
        _ gesture: SpatialGestureRecognizer.RecognizedGesture,
        priority: GesturePriority = .normal,
        targetEntityID: UUID? = nil,
        handData: GestureHandData? = nil
    ) -> Bool {
        // P2: Calculate ML confidence score
        let confidence = handData != nil
            ? confidenceScorer.scoreGesture(gesture, handData: handData!)
            : 1.0

        // P2: Check if gesture is available for current skill level
        guard skillLevel.availableGestures.contains(gesture) else {
            return false
        }

        // P2: Apply confidence threshold based on skill level
        guard confidence >= skillLevel.confidenceThreshold else {
            // Track failed attempt for pattern learning
            patternTracker.recordAttempt(gesture: gesture, success: false, confidence: confidence)
            return false
        }

        // P2: Calculate contextual boost from recent patterns
        let contextualBoost = patternTracker.getContextualBoost(for: gesture)

        // Update confidence state
        currentConfidence = confidence
        onConfidenceUpdate?(gesture, confidence)

        // Critical gestures always take priority
        if priority == .critical {
            cancelCurrentGesture()
            activateGesture(gesture, priority: priority, targetEntityID: targetEntityID,
                          confidence: confidence, contextualBoost: contextualBoost)
            return true
        }

        // If idle, accept immediately
        if currentState == .idle {
            activateGesture(gesture, priority: priority, targetEntityID: targetEntityID,
                          confidence: confidence, contextualBoost: contextualBoost)
            return true
        }

        // If same gesture type, update existing
        if let active = activeGesture, active.gesture == gesture {
            return true
        }

        // P2: Consider confidence in preemption decision
        if let active = activeGesture {
            // Higher priority always wins
            if priority > active.priority {
                cancelCurrentGesture()
                activateGesture(gesture, priority: priority, targetEntityID: targetEntityID,
                              confidence: confidence, contextualBoost: contextualBoost)
                return true
            }

            // Same priority: higher confidence wins
            if priority == active.priority && confidence > active.effectiveConfidence + 0.1 {
                cancelCurrentGesture()
                activateGesture(gesture, priority: priority, targetEntityID: targetEntityID,
                              confidence: confidence, contextualBoost: contextualBoost)
                return true
            }
        }

        // Queue the gesture if there's room
        if queuedGestures.count < maxQueueSize {
            queueGesture(gesture, priority: priority, targetEntityID: targetEntityID, confidence: confidence)
            return false
        }

        // Reject if queue is full
        return false
    }

    /// P2: Begin gesture with disambiguation when multiple candidates detected
    @discardableResult
    func beginGestureWithDisambiguation(
        candidates: [(SpatialGestureRecognizer.RecognizedGesture, Float)],
        handData: GestureHandData,
        targetEntityID: UUID? = nil
    ) -> Bool {
        guard !candidates.isEmpty else { return false }

        // If only one candidate with high confidence, use it directly
        if candidates.count == 1 && candidates[0].1 >= 0.8 {
            return beginGesture(candidates[0].0, targetEntityID: targetEntityID, handData: handData)
        }

        // Multiple candidates - disambiguate
        disambiguationActive = true
        currentState = .disambiguating

        // Use disambiguator to select best gesture
        let resolved = disambiguator.resolve(
            candidates: candidates,
            context: disambiguator.buildContext(
                recentGestures: patternTracker.recentGestures,
                currentRoom: nil,
                activeDevices: []
            )
        )

        disambiguationActive = false

        if let (gesture, confidence) = resolved {
            return beginGesture(gesture, targetEntityID: targetEntityID, handData: handData)
        }

        currentState = .idle
        return false
    }

    /// Updates progress of the active gesture
    func updateGestureProgress(_ progress: Float) {
        guard var active = activeGesture, currentState == .active else { return }
        active.progress = progress
        activeGesture = active
    }

    /// Completes the current gesture
    func completeGesture(success: Bool = true) {
        guard let active = activeGesture else { return }

        currentState = .completing
        lastCompletedGesture = active.gesture

        // P2: Record successful gesture for pattern learning
        patternTracker.recordAttempt(gesture: active.gesture, success: success, confidence: active.confidence)

        // P2: Update skill level based on performance
        updateSkillLevel()

        // Process pending updates atomically
        processPendingUpdates()

        // Notify completion
        onGestureCompleted?(active.gesture, success)

        // Clear active gesture
        activeGesture = nil
        currentConfidence = 0.0
        currentState = .idle

        // Process next queued gesture
        processQueue()
    }

    /// P2: Sets the user skill level manually
    func setSkillLevel(_ level: SkillLevel) {
        skillLevel = level
        UserDefaults.standard.set(level.rawValue, forKey: "kagami.gesture.skillLevel")
    }

    /// P2: Updates skill level based on recent performance
    private func updateSkillLevel() {
        let stats = patternTracker.getPerformanceStats()

        // Require minimum attempts before adjusting
        guard stats.totalAttempts >= 20 else { return }

        let successRate = Float(stats.successfulAttempts) / Float(stats.totalAttempts)
        let avgConfidence = stats.averageConfidence

        // Promote to expert if consistently high performance
        if skillLevel == .intermediate && successRate >= 0.9 && avgConfidence >= 0.8 {
            skillLevel = .expert
        }
        // Promote beginner to intermediate
        else if skillLevel == .beginner && successRate >= 0.8 && avgConfidence >= 0.7 {
            skillLevel = .intermediate
        }
        // Demote if struggling
        else if skillLevel == .expert && successRate < 0.7 {
            skillLevel = .intermediate
        }
        else if skillLevel == .intermediate && successRate < 0.6 {
            skillLevel = .beginner
        }
    }

    /// Cancels the current gesture
    func cancelCurrentGesture() {
        guard let active = activeGesture else { return }

        currentState = .cancelled

        // Discard pending updates
        pendingUpdates.removeAll()

        // Notify cancellation
        onGestureCompleted?(active.gesture, false)

        // Clear state
        activeGesture = nil
        currentState = .idle
        timeoutTask?.cancel()

        // Process next queued gesture
        processQueue()
    }

    /// Queues an entity update to be applied atomically
    func queueEntityUpdate(
        entityID: UUID,
        updateType: EntityUpdate.UpdateType,
        value: Any? = nil
    ) {
        guard let active = activeGesture else { return }

        let update = EntityUpdate(
            entityID: entityID,
            gestureID: active.id,
            updateType: updateType,
            value: value,
            timestamp: Date()
        )

        updateLock.lock()
        pendingUpdates.append(update)
        updateLock.unlock()
    }

    /// Clears the gesture queue
    func clearQueue() {
        queuedGestures.removeAll()
    }

    /// Resets the state machine
    func reset() {
        cancelCurrentGesture()
        clearQueue()
        pendingUpdates.removeAll()
        lastCompletedGesture = nil
        currentState = .idle
        currentConfidence = 0.0
        disambiguationActive = false
    }

    // MARK: - Priority Calculation

    /// Returns the priority for a given gesture type
    static func priority(for gesture: SpatialGestureRecognizer.RecognizedGesture) -> GesturePriority {
        switch gesture {
        case .fist:
            return .critical  // Emergency stop

        case .openPalm:
            return .high  // Dismiss

        case .swipeLeft, .swipeRight, .swipeUp, .swipeDown:
            return .high  // Navigation

        case .twoHandSpread, .twoHandPinch, .twoHandRotate:
            return .normal  // Scaling

        case .pinch, .pinchDrag, .pinchHold:
            return .normal  // Selection

        case .tap, .point, .rotate, .thumbsUp:
            return .normal  // Interaction

        case .none:
            return .low
        }
    }

    // MARK: - Private Methods

    private func activateGesture(
        _ gesture: SpatialGestureRecognizer.RecognizedGesture,
        priority: GesturePriority,
        targetEntityID: UUID?,
        confidence: Float = 1.0,
        contextualBoost: Float = 0.0
    ) {
        let active = ActiveGesture(
            gesture: gesture,
            priority: priority,
            targetEntityID: targetEntityID,
            confidence: confidence,
            contextualBoost: contextualBoost
        )

        activeGesture = active
        currentState = .pending

        // Start confirmation timeout
        timeoutTask?.cancel()
        timeoutTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: UInt64(self?.confirmationTimeout ?? 0.1 * 1_000_000_000))
            guard !Task.isCancelled else { return }
            await self?.confirmGesture()
        }

        // Start duration timeout
        Task { [weak self] in
            try? await Task.sleep(nanoseconds: UInt64((self?.maxGestureDuration ?? 10.0) * 1_000_000_000))
            guard !Task.isCancelled else { return }
            if self?.activeGesture?.id == active.id {
                self?.cancelCurrentGesture()
            }
        }
    }

    private func confirmGesture() {
        guard currentState == .pending else { return }
        currentState = .active
    }

    private func queueGesture(
        _ gesture: SpatialGestureRecognizer.RecognizedGesture,
        priority: GesturePriority,
        targetEntityID: UUID?,
        confidence: Float = 1.0
    ) {
        let queued = QueuedGesture(
            gesture: gesture,
            priority: priority,
            targetEntityID: targetEntityID,
            confidence: confidence
        )

        queuedGestures.append(queued)

        // Sort by priority (highest first), then by confidence
        queuedGestures.sort {
            if $0.priority != $1.priority {
                return $0.priority > $1.priority
            }
            return $0.confidence > $1.confidence
        }

        // Clean up expired gestures
        cleanupExpiredGestures()
    }

    private func processQueue() {
        // Clean up expired gestures first
        cleanupExpiredGestures()

        // Get highest priority queued gesture
        guard let next = queuedGestures.first else { return }

        // Remove from queue
        queuedGestures.removeFirst()

        // Activate it
        activateGesture(next.gesture, priority: next.priority, targetEntityID: next.targetEntityID)
    }

    private func cleanupExpiredGestures() {
        queuedGestures.removeAll { $0.isExpired }
    }

    private func processPendingUpdates() {
        updateLock.lock()
        let updates = pendingUpdates
        pendingUpdates.removeAll()
        updateLock.unlock()

        // Apply updates atomically
        for update in updates {
            onEntityUpdate?(update)
        }
    }
}

// MARK: - Integration with SpatialGestureRecognizer

extension GestureStateMachine {
    /// Connects to a SpatialGestureRecognizer for automatic gesture handling
    func connect(to recognizer: SpatialGestureRecognizer) {
        recognizer.onGestureRecognized = { [weak self] gesture in
            guard let self = self else { return }

            let priority = GestureStateMachine.priority(for: gesture)
            self.beginGesture(gesture, priority: priority)
        }
    }
}

// MARK: - P2: ML Gesture Confidence Scorer

/// ML-based confidence scoring for gesture recognition
class MLGestureConfidenceScorer {

    // Feature weights learned from training data (simulated)
    private var featureWeights: [String: Float] = [
        "jointDistanceVariance": -0.3,
        "velocityStability": 0.4,
        "poseConsistency": 0.5,
        "fingerExtension": 0.3,
        "thumbDistance": 0.4,
        "handStability": 0.5
    ]

    /// Scores a gesture based on hand tracking data
    func scoreGesture(_ gesture: SpatialGestureRecognizer.RecognizedGesture, handData: GestureHandData) -> Float {
        var score: Float = 0.5  // Base score

        // Feature 1: Joint distance variance (lower is better)
        let jointVariance = calculateJointVariance(handData)
        score += featureWeights["jointDistanceVariance"]! * jointVariance

        // Feature 2: Velocity stability (steady hand)
        let velocityStability = calculateVelocityStability(handData)
        score += featureWeights["velocityStability"]! * velocityStability

        // Feature 3: Pose consistency with expected gesture
        let poseConsistency = calculatePoseConsistency(gesture, handData: handData)
        score += featureWeights["poseConsistency"]! * poseConsistency

        // Feature 4: Gesture-specific features
        score += gestureSpecificScore(gesture, handData: handData)

        // Clamp to 0-1
        return max(0.0, min(1.0, score))
    }

    private func calculateJointVariance(_ handData: GestureHandData) -> Float {
        guard !handData.recentPositions.isEmpty else { return 0.5 }

        // Calculate variance in joint positions over recent frames
        var totalVariance: Float = 0
        let positions = handData.recentPositions

        if positions.count > 1 {
            var sum = SIMD3<Float>(0, 0, 0)
            for pos in positions {
                sum += pos
            }
            let mean = sum / Float(positions.count)

            var varianceSum: Float = 0
            for pos in positions {
                let diff = pos - mean
                varianceSum += simd_length_squared(diff)
            }
            totalVariance = varianceSum / Float(positions.count)
        }

        // Normalize (0 variance = 1.0, high variance = 0.0)
        return max(0, 1.0 - totalVariance * 10)
    }

    private func calculateVelocityStability(_ handData: GestureHandData) -> Float {
        guard handData.recentVelocities.count > 1 else { return 0.5 }

        // Calculate how stable the velocity is
        let velocities = handData.recentVelocities
        var avgVelocity = SIMD3<Float>(0, 0, 0)

        for vel in velocities {
            avgVelocity += vel
        }
        avgVelocity /= Float(velocities.count)

        var deviationSum: Float = 0
        for vel in velocities {
            deviationSum += simd_length(vel - avgVelocity)
        }
        let avgDeviation = deviationSum / Float(velocities.count)

        // Lower deviation = higher stability score
        return max(0, 1.0 - avgDeviation * 5)
    }

    private func calculatePoseConsistency(_ gesture: SpatialGestureRecognizer.RecognizedGesture, handData: GestureHandData) -> Float {
        // Compare current pose to expected pose for gesture
        guard let thumbIndex = handData.thumbIndexDistance else { return 0.5 }

        switch gesture {
        case .pinch, .pinchDrag, .pinchHold:
            // Pinch expects thumb and index close together
            return thumbIndex < 0.03 ? 1.0 : max(0, 1.0 - (thumbIndex - 0.03) * 20)

        case .openPalm:
            // Open palm expects fingers spread
            let fingerSpread = handData.fingerSpread ?? 0
            return fingerSpread > 0.1 ? 1.0 : fingerSpread * 10

        case .fist:
            // Fist expects all fingers curled
            return handData.isFist ? 1.0 : 0.3

        case .point:
            // Point expects index extended, others curled
            return handData.isPointing ? 1.0 : 0.3

        default:
            return 0.6
        }
    }

    private func gestureSpecificScore(_ gesture: SpatialGestureRecognizer.RecognizedGesture, handData: GestureHandData) -> Float {
        switch gesture {
        case .swipeUp, .swipeDown, .swipeLeft, .swipeRight:
            // Swipe requires clear directional movement
            guard let velocity = handData.currentVelocity else { return 0 }
            let speed = simd_length(velocity)
            return speed > 0.2 ? 0.2 : speed

        case .twoHandSpread, .twoHandPinch:
            // Two-hand gestures require both hands detected
            return handData.bothHandsDetected ? 0.2 : -0.2

        default:
            return 0
        }
    }

    /// Updates feature weights based on user feedback
    func updateWeights(gesture: SpatialGestureRecognizer.RecognizedGesture, wasCorrect: Bool) {
        // Simple online learning: adjust weights based on feedback
        let learningRate: Float = 0.01
        let adjustment = wasCorrect ? learningRate : -learningRate

        for key in featureWeights.keys {
            featureWeights[key] = featureWeights[key]! * (1 + adjustment)
        }
    }
}

// MARK: - P2: Gesture Hand Data

/// Hand tracking data for ML confidence scoring
struct GestureHandData {
    var position: SIMD3<Float>
    var recentPositions: [SIMD3<Float>] = []
    var currentVelocity: SIMD3<Float>?
    var recentVelocities: [SIMD3<Float>] = []
    var thumbIndexDistance: Float?
    var fingerSpread: Float?
    var isFist: Bool = false
    var isPointing: Bool = false
    var bothHandsDetected: Bool = false
    var handedness: Handedness = .right

    enum Handedness {
        case left, right
    }
}

// MARK: - P2: Gesture Disambiguator

/// Resolves ambiguous gesture detections using context
class GestureDisambiguator {

    /// Context for disambiguation
    struct DisambiguationContext {
        var recentGestures: [SpatialGestureRecognizer.RecognizedGesture]
        var currentRoom: String?
        var activeDevices: [String]
        var timeOfDay: TimeOfDay

        enum TimeOfDay {
            case morning, afternoon, evening, night
        }
    }

    /// Resolves multiple gesture candidates to a single gesture
    func resolve(
        candidates: [(SpatialGestureRecognizer.RecognizedGesture, Float)],
        context: DisambiguationContext
    ) -> (SpatialGestureRecognizer.RecognizedGesture, Float)? {
        guard !candidates.isEmpty else { return nil }

        // Score each candidate with contextual factors
        var scoredCandidates: [(SpatialGestureRecognizer.RecognizedGesture, Float)] = []

        for (gesture, baseConfidence) in candidates {
            var adjustedConfidence = baseConfidence

            // Boost if gesture follows common pattern
            if followsCommonPattern(gesture, recent: context.recentGestures) {
                adjustedConfidence += 0.1
            }

            // Boost if gesture is contextually appropriate
            if isContextuallyAppropriate(gesture, context: context) {
                adjustedConfidence += 0.05
            }

            // Penalize if gesture was recently cancelled
            if wasRecentlyCancelled(gesture, recent: context.recentGestures) {
                adjustedConfidence -= 0.1
            }

            scoredCandidates.append((gesture, adjustedConfidence))
        }

        // Sort by adjusted confidence
        scoredCandidates.sort { $0.1 > $1.1 }

        // Return highest confidence if it's significantly better than second
        if scoredCandidates.count >= 2 {
            let margin = scoredCandidates[0].1 - scoredCandidates[1].1
            if margin >= 0.1 {
                return scoredCandidates[0]
            }
            // Too close to call - wait for more data
            return nil
        }

        return scoredCandidates.first
    }

    /// Builds context from current state
    func buildContext(
        recentGestures: [SpatialGestureRecognizer.RecognizedGesture],
        currentRoom: String?,
        activeDevices: [String]
    ) -> DisambiguationContext {
        let hour = Calendar.current.component(.hour, from: Date())
        let timeOfDay: DisambiguationContext.TimeOfDay

        switch hour {
        case 6..<12: timeOfDay = .morning
        case 12..<17: timeOfDay = .afternoon
        case 17..<21: timeOfDay = .evening
        default: timeOfDay = .night
        }

        return DisambiguationContext(
            recentGestures: recentGestures,
            currentRoom: currentRoom,
            activeDevices: activeDevices,
            timeOfDay: timeOfDay
        )
    }

    private func followsCommonPattern(
        _ gesture: SpatialGestureRecognizer.RecognizedGesture,
        recent: [SpatialGestureRecognizer.RecognizedGesture]
    ) -> Bool {
        guard let last = recent.last else { return false }

        // Common patterns
        let patterns: [SpatialGestureRecognizer.RecognizedGesture: Set<SpatialGestureRecognizer.RecognizedGesture>] = [
            .pinch: [.pinchDrag, .pinchHold],  // Pinch often followed by drag/hold
            .swipeUp: [.swipeUp],  // Repeated swipes
            .swipeDown: [.swipeDown],
            .point: [.pinch],  // Point then select
        ]

        return patterns[last]?.contains(gesture) ?? false
    }

    private func isContextuallyAppropriate(
        _ gesture: SpatialGestureRecognizer.RecognizedGesture,
        context: DisambiguationContext
    ) -> Bool {
        // Swipes are appropriate for room navigation
        if context.activeDevices.isEmpty && (gesture == .swipeLeft || gesture == .swipeRight) {
            return true
        }

        // Pinch is appropriate when devices are active
        if !context.activeDevices.isEmpty && (gesture == .pinch || gesture == .pinchDrag) {
            return true
        }

        // Open palm is always appropriate (dismiss)
        if gesture == .openPalm {
            return true
        }

        return false
    }

    private func wasRecentlyCancelled(
        _ gesture: SpatialGestureRecognizer.RecognizedGesture,
        recent: [SpatialGestureRecognizer.RecognizedGesture]
    ) -> Bool {
        // Check if this gesture appears multiple times recently (possible repeated failure)
        let recentFive = recent.suffix(5)
        let count = recentFive.filter { $0 == gesture }.count
        return count >= 3
    }
}

// MARK: - P2: Gesture Pattern Tracker

/// Tracks gesture patterns for learning and contextual boosts
class GesturePatternTracker {

    /// Recent gesture history
    private(set) var recentGestures: [SpatialGestureRecognizer.RecognizedGesture] = []
    private let maxHistory = 100

    /// Performance statistics
    private var attempts: [(gesture: SpatialGestureRecognizer.RecognizedGesture, success: Bool, confidence: Float, timestamp: Date)] = []

    /// Transition probabilities (Markov chain)
    private var transitionCounts: [SpatialGestureRecognizer.RecognizedGesture: [SpatialGestureRecognizer.RecognizedGesture: Int]] = [:]

    /// Records a gesture attempt
    func recordAttempt(gesture: SpatialGestureRecognizer.RecognizedGesture, success: Bool, confidence: Float) {
        let timestamp = Date()

        attempts.append((gesture, success, confidence, timestamp))

        // Keep only last 1000 attempts
        if attempts.count > 1000 {
            attempts.removeFirst(attempts.count - 1000)
        }

        if success {
            // Update recent gestures
            if let last = recentGestures.last {
                // Update transition counts
                if transitionCounts[last] == nil {
                    transitionCounts[last] = [:]
                }
                transitionCounts[last]![gesture, default: 0] += 1
            }

            recentGestures.append(gesture)

            // Trim history
            if recentGestures.count > maxHistory {
                recentGestures.removeFirst(recentGestures.count - maxHistory)
            }
        }
    }

    /// Gets contextual boost for a gesture based on recent patterns
    func getContextualBoost(for gesture: SpatialGestureRecognizer.RecognizedGesture) -> Float {
        guard let last = recentGestures.last,
              let transitions = transitionCounts[last],
              let count = transitions[gesture] else {
            return 0
        }

        let totalTransitions = transitions.values.reduce(0, +)
        guard totalTransitions > 0 else { return 0 }

        let probability = Float(count) / Float(totalTransitions)

        // Boost proportional to transition probability
        return probability * 0.1
    }

    /// Performance statistics
    struct PerformanceStats {
        let totalAttempts: Int
        let successfulAttempts: Int
        let averageConfidence: Float
        let mostCommonGesture: SpatialGestureRecognizer.RecognizedGesture?
    }

    /// Gets performance statistics
    func getPerformanceStats() -> PerformanceStats {
        let successes = attempts.filter { $0.success }
        let avgConfidence = successes.isEmpty ? 0 : successes.map { $0.confidence }.reduce(0, +) / Float(successes.count)

        // Find most common gesture
        var gestureCounts: [SpatialGestureRecognizer.RecognizedGesture: Int] = [:]
        for attempt in attempts where attempt.success {
            gestureCounts[attempt.gesture, default: 0] += 1
        }
        let mostCommon = gestureCounts.max { $0.value < $1.value }?.key

        return PerformanceStats(
            totalAttempts: attempts.count,
            successfulAttempts: successes.count,
            averageConfidence: avgConfidence,
            mostCommonGesture: mostCommon
        )
    }

    /// Clears all tracking data
    func reset() {
        recentGestures.removeAll()
        attempts.removeAll()
        transitionCounts.removeAll()
    }
}

/*
 * 鏡
 * h(x) >= 0. Always.
 *
 * One gesture at a time.
 * Queue the rest.
 * Safety first.
 *
 * The state machine ensures order from chaos.
 * ML confidence provides clarity.
 */
