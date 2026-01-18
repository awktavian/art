package com.kagami.android.services

import android.content.Context
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.withContext
import org.tensorflow.lite.Interpreter
import org.tensorflow.lite.gpu.CompatibilityList
import org.tensorflow.lite.gpu.GpuDelegate
import java.io.FileInputStream
import java.nio.MappedByteBuffer
import java.nio.channels.FileChannel
import javax.inject.Inject
import javax.inject.Singleton

/**
 * World Model inference service for Android using TensorFlow Lite.
 *
 * Runs the Base OrganismRSSM model (50M params) for predictive state modeling.
 *
 * ## Usage
 *
 * ```kotlin
 * val service = WorldModelService(context)
 * service.initialize()
 * val prediction = service.predict(observation, action)
 * ```
 *
 * Created: January 12, 2026
 */
@Singleton
class WorldModelService @Inject constructor(
    private val context: Context
) {
    companion object {
        private const val TAG = "WorldModelService"

        // Model configuration
        private const val MODEL_FILE = "organism_rssm_base.tflite"
        private const val OBS_DIM = 64
        private const val ACTION_DIM = 8
        private const val HIDDEN_DIM = 384
        private const val STOCH_DIM = 32
    }

    // State
    private val _isReady = MutableStateFlow(false)
    val isReady: StateFlow<Boolean> = _isReady.asStateFlow()

    private val _lastLatencyMs = MutableStateFlow(0.0)
    val lastLatencyMs: StateFlow<Double> = _lastLatencyMs.asStateFlow()

    private val _inferenceCount = MutableStateFlow(0)
    val inferenceCount: StateFlow<Int> = _inferenceCount.asStateFlow()

    // TFLite interpreter
    private var interpreter: Interpreter? = null
    private var gpuDelegate: GpuDelegate? = null

    // Cached hidden states
    private var cachedH: FloatArray? = null
    private var cachedZ: FloatArray? = null

    /**
     * World model prediction result.
     */
    data class Prediction(
        val obsPred: FloatArray,
        val reward: Float,
        val continueProb: Float,
        val latencyMs: Double
    ) {
        override fun equals(other: Any?): Boolean {
            if (this === other) return true
            if (javaClass != other?.javaClass) return false

            other as Prediction

            if (!obsPred.contentEquals(other.obsPred)) return false
            if (reward != other.reward) return false
            if (continueProb != other.continueProb) return false
            if (latencyMs != other.latencyMs) return false

            return true
        }

        override fun hashCode(): Int {
            var result = obsPred.contentHashCode()
            result = 31 * result + reward.hashCode()
            result = 31 * result + continueProb.hashCode()
            result = 31 * result + latencyMs.hashCode()
            return result
        }
    }

    /**
     * Initialize the world model.
     *
     * Loads the TFLite model from assets with optional GPU acceleration.
     */
    suspend fun initialize(): Result<Unit> = withContext(Dispatchers.IO) {
        try {
            Log.i(TAG, "Initializing world model: $MODEL_FILE")
            val start = System.nanoTime()

            // Load model from assets
            val modelBuffer = loadModelFile()
            if (modelBuffer == null) {
                Log.w(TAG, "World model not found, using placeholder mode")
                _isReady.value = true
                return@withContext Result.success(Unit)
            }

            // Configure interpreter options
            val options = Interpreter.Options().apply {
                setNumThreads(4) // Use multiple CPU threads

                // Try GPU delegate if available
                if (CompatibilityList().isDelegateSupportedOnThisDevice) {
                    gpuDelegate = GpuDelegate()
                    addDelegate(gpuDelegate)
                    Log.i(TAG, "GPU delegate enabled")
                }
            }

            interpreter = Interpreter(modelBuffer, options)

            val elapsed = (System.nanoTime() - start) / 1_000_000.0
            Log.i(TAG, "World model loaded in ${elapsed}ms")

            _isReady.value = true
            Result.success(Unit)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to initialize world model", e)
            Result.failure(e)
        }
    }

    private fun loadModelFile(): MappedByteBuffer? {
        return try {
            val assetFileDescriptor = context.assets.openFd(MODEL_FILE)
            val inputStream = FileInputStream(assetFileDescriptor.fileDescriptor)
            val fileChannel = inputStream.channel
            val startOffset = assetFileDescriptor.startOffset
            val declaredLength = assetFileDescriptor.declaredLength
            fileChannel.map(FileChannel.MapMode.READ_ONLY, startOffset, declaredLength)
        } catch (e: Exception) {
            Log.w(TAG, "Model file not found in assets: $MODEL_FILE")
            null
        }
    }

    /**
     * Predict next state given observation and action.
     *
     * @param observation Current observation vector [OBS_DIM].
     * @param action Action to take [ACTION_DIM].
     * @return Prediction with next state and reward.
     */
    suspend fun predict(observation: FloatArray, action: FloatArray): Result<Prediction> =
        withContext(Dispatchers.Default) {
            try {
                val start = System.nanoTime()

                // If interpreter not loaded, return placeholder
                val interp = interpreter
                if (interp == null) {
                    Log.d(TAG, "World model not loaded, returning placeholder prediction")
                    return@withContext Result.success(
                        Prediction(
                            obsPred = observation.copyOf(),
                            reward = 0f,
                            continueProb = 1f,
                            latencyMs = 0.0
                        )
                    )
                }

                // Prepare inputs
                val obsInput = Array(1) { Array(1) { observation } }
                val actionInput = Array(1) { Array(1) { action } }
                val hInput = Array(1) { cachedH ?: FloatArray(HIDDEN_DIM) }
                val zInput = Array(1) { cachedZ ?: FloatArray(STOCH_DIM) }

                // Prepare outputs
                val obsPredOutput = Array(1) { Array(1) { FloatArray(OBS_DIM) } }
                val hOutput = Array(1) { FloatArray(HIDDEN_DIM) }
                val zOutput = Array(1) { FloatArray(STOCH_DIM) }
                val rewardOutput = Array(1) { FloatArray(1) }
                val continueOutput = Array(1) { FloatArray(1) }

                // Map inputs and outputs
                val inputs = arrayOf(obsInput, actionInput, hInput, zInput)
                val outputs = mapOf(
                    0 to obsPredOutput,
                    1 to hOutput,
                    2 to zOutput,
                    3 to rewardOutput,
                    4 to continueOutput
                )

                // Run inference
                interp.runForMultipleInputsOutputs(inputs, outputs)

                // Update cached states
                cachedH = hOutput[0]
                cachedZ = zOutput[0]

                // Compute continue probability (sigmoid)
                val continueLogit = continueOutput[0][0]
                val continueProb = 1f / (1f + kotlin.math.exp(-continueLogit))

                val elapsed = (System.nanoTime() - start) / 1_000_000.0
                _lastLatencyMs.value = elapsed
                _inferenceCount.value = _inferenceCount.value + 1

                Result.success(
                    Prediction(
                        obsPred = obsPredOutput[0][0],
                        reward = rewardOutput[0][0],
                        continueProb = continueProb,
                        latencyMs = elapsed
                    )
                )
            } catch (e: Exception) {
                Log.e(TAG, "Prediction failed", e)
                Result.failure(e)
            }
        }

    /**
     * Imagine a trajectory given initial state and action sequence.
     *
     * @param initialObs Starting observation.
     * @param actions Sequence of actions.
     * @return Sequence of predictions.
     */
    suspend fun imagine(
        initialObs: FloatArray,
        actions: List<FloatArray>
    ): Result<List<Prediction>> = withContext(Dispatchers.Default) {
        try {
            val predictions = mutableListOf<Prediction>()
            var currentObs = initialObs

            // Reset state for imagination
            resetState()

            for (action in actions) {
                val prediction = predict(currentObs, action).getOrThrow()
                predictions.add(prediction)
                currentObs = prediction.obsPred
            }

            Result.success(predictions)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * Reset hidden states (e.g., at episode boundary).
     */
    fun resetState() {
        cachedH = null
        cachedZ = null
    }

    /**
     * Release resources.
     */
    fun close() {
        interpreter?.close()
        interpreter = null

        gpuDelegate?.close()
        gpuDelegate = null

        _isReady.value = false
    }
}
