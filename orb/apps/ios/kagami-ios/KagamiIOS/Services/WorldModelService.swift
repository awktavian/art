import Foundation
import CoreML
import os.log

/// World Model inference service for iOS using CoreML.
///
/// Runs the Base OrganismRSSM model (50M params) for predictive state modeling.
///
/// # Usage
///
/// ```swift
/// let service = WorldModelService.shared
/// try await service.initialize()
/// let prediction = try await service.predict(observation: obs, action: action)
/// ```
///
/// Created: January 12, 2026
@MainActor
public final class WorldModelService: ObservableObject {

    /// Shared singleton instance.
    public static let shared = WorldModelService()

    // MARK: - Published State

    /// Whether the model is loaded and ready.
    @Published public private(set) var isReady: Bool = false

    /// Last prediction latency in milliseconds.
    @Published public private(set) var lastLatencyMs: Double = 0

    /// Total inference count.
    @Published public private(set) var inferenceCount: Int = 0

    // MARK: - Private Properties

    private let logger = Logger(subsystem: "com.kagami.ios", category: "WorldModel")

    /// CoreML model instance.
    private var model: MLModel?

    /// Cached hidden state.
    private var cachedH: MLMultiArray?

    /// Cached stochastic state.
    private var cachedZ: MLMultiArray?

    /// Model configuration.
    private let config = WorldModelConfig.base

    // MARK: - Configuration

    /// World model configuration.
    public struct WorldModelConfig {
        let modelName: String
        let obsDim: Int
        let actionDim: Int
        let hiddenDim: Int
        let stochDim: Int

        /// Small model for embedded devices.
        public static let small = WorldModelConfig(
            modelName: "organism_rssm_small",
            obsDim: 64,
            actionDim: 8,
            hiddenDim: 256,
            stochDim: 16
        )

        /// Base model for mobile devices.
        public static let base = WorldModelConfig(
            modelName: "organism_rssm_base",
            obsDim: 64,
            actionDim: 8,
            hiddenDim: 384,
            stochDim: 32
        )
    }

    // MARK: - Initialization

    private init() {}

    /// Initialize the world model.
    ///
    /// Loads the CoreML model from the app bundle.
    public func initialize() async throws {
        logger.info("Initializing world model: \(self.config.modelName)")

        let start = CFAbsoluteTimeGetCurrent()

        // Load model from bundle
        guard let modelURL = Bundle.main.url(
            forResource: config.modelName,
            withExtension: "mlmodelc"
        ) else {
            // Try mlpackage
            guard let packageURL = Bundle.main.url(
                forResource: config.modelName,
                withExtension: "mlpackage"
            ) else {
                logger.warning("World model not found in bundle, using placeholder")
                isReady = true
                return
            }

            model = try await loadModel(from: packageURL)
            return
        }

        model = try await loadModel(from: modelURL)

        let elapsed = (CFAbsoluteTimeGetCurrent() - start) * 1000
        logger.info("World model loaded in \(elapsed, privacy: .public)ms")

        isReady = true
    }

    private func loadModel(from url: URL) async throws -> MLModel {
        let configuration = MLModelConfiguration()
        configuration.computeUnits = .all // Use Neural Engine + GPU + CPU

        return try await withCheckedThrowingContinuation { continuation in
            MLModel.load(contentsOf: url, configuration: configuration) { result in
                switch result {
                case .success(let model):
                    continuation.resume(returning: model)
                case .failure(let error):
                    continuation.resume(throwing: error)
                }
            }
        }
    }

    // MARK: - Prediction

    /// World model prediction result.
    public struct Prediction {
        /// Predicted next observation.
        public let obsPred: [Float]

        /// Predicted reward.
        public let reward: Float

        /// Episode continuation probability.
        public let continueProb: Float

        /// Inference latency in milliseconds.
        public let latencyMs: Double
    }

    /// Predict next state given observation and action.
    ///
    /// - Parameters:
    ///   - observation: Current observation vector [obs_dim].
    ///   - action: Action to take [action_dim].
    ///
    /// - Returns: Prediction with next state and reward.
    public func predict(observation: [Float], action: [Float]) async throws -> Prediction {
        let start = CFAbsoluteTimeGetCurrent()

        // If model not loaded, return placeholder prediction
        guard model != nil else {
            logger.debug("World model not loaded, returning placeholder prediction")
            return Prediction(
                obsPred: observation,
                reward: 0.0,
                continueProb: 1.0,
                latencyMs: 0.0
            )
        }

        // Prepare inputs
        let obsArray = try createMultiArray(
            from: observation,
            shape: [1, 1, NSNumber(value: config.obsDim)]
        )

        let actionArray = try createMultiArray(
            from: action,
            shape: [1, 1, NSNumber(value: config.actionDim)]
        )

        // Get or initialize hidden states
        let h = try cachedH ?? createMultiArray(
            from: [Float](repeating: 0, count: config.hiddenDim),
            shape: [1, NSNumber(value: config.hiddenDim)]
        )

        let z = try cachedZ ?? createMultiArray(
            from: [Float](repeating: 0, count: config.stochDim),
            shape: [1, NSNumber(value: config.stochDim)]
        )

        // Create feature provider
        let inputFeatures = try MLDictionaryFeatureProvider(dictionary: [
            "obs": MLFeatureValue(multiArray: obsArray),
            "actions": MLFeatureValue(multiArray: actionArray),
            "h": MLFeatureValue(multiArray: h),
            "z": MLFeatureValue(multiArray: z),
        ])

        // Run inference
        let output = try await model!.prediction(from: inputFeatures)

        // Extract outputs
        let obsPredArray = output.featureValue(for: "obs_pred")?.multiArrayValue
        let obsPred = extractFloats(from: obsPredArray, count: config.obsDim)

        let rewardValue = output.featureValue(for: "reward")?.multiArrayValue
        let reward = rewardValue?[0].floatValue ?? 0.0

        let continueValue = output.featureValue(for: "continue_prob")?.multiArrayValue
        let continueLogit = continueValue?[0].floatValue ?? 0.0
        let continueProb = 1.0 / (1.0 + exp(-continueLogit)) // Sigmoid

        // Update cached states
        if let hOut = output.featureValue(for: "h_out")?.multiArrayValue {
            cachedH = hOut
        }
        if let zOut = output.featureValue(for: "z_out")?.multiArrayValue {
            cachedZ = zOut
        }

        let elapsed = (CFAbsoluteTimeGetCurrent() - start) * 1000
        lastLatencyMs = elapsed
        inferenceCount += 1

        return Prediction(
            obsPred: obsPred,
            reward: reward,
            continueProb: continueProb,
            latencyMs: elapsed
        )
    }

    /// Imagine a trajectory given initial state and action sequence.
    ///
    /// - Parameters:
    ///   - initialObs: Starting observation.
    ///   - actions: Sequence of actions.
    ///
    /// - Returns: Sequence of predictions.
    public func imagine(initialObs: [Float], actions: [[Float]]) async throws -> [Prediction] {
        var predictions: [Prediction] = []
        var currentObs = initialObs

        // Reset state for imagination
        resetState()

        for action in actions {
            let prediction = try await predict(observation: currentObs, action: action)
            predictions.append(prediction)
            currentObs = prediction.obsPred
        }

        return predictions
    }

    /// Reset hidden states (e.g., at episode boundary).
    public func resetState() {
        cachedH = nil
        cachedZ = nil
    }

    // MARK: - Helpers

    private func createMultiArray(from array: [Float], shape: [NSNumber]) throws -> MLMultiArray {
        let multiArray = try MLMultiArray(shape: shape, dataType: .float32)

        for (index, value) in array.enumerated() {
            multiArray[index] = NSNumber(value: value)
        }

        return multiArray
    }

    private func extractFloats(from multiArray: MLMultiArray?, count: Int) -> [Float] {
        guard let array = multiArray else {
            return [Float](repeating: 0, count: count)
        }

        var result: [Float] = []
        for i in 0..<min(count, array.count) {
            result.append(array[i].floatValue)
        }

        // Pad if needed
        while result.count < count {
            result.append(0)
        }

        return result
    }
}

// MARK: - SwiftUI Preview Support

#if DEBUG
extension WorldModelService {
    /// Create a mock service for previews.
    static var preview: WorldModelService {
        let service = WorldModelService()
        service.isReady = true
        return service
    }
}
#endif
