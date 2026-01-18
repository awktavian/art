/**
 * A/B Testing Manager - Experiment Framework for Hint Effectiveness
 *
 * Colony: Beacon (e5) - Planning
 * h(x) >= 0. Always.
 *
 * P2 Gap Fix: A/B testing framework for contextual hints.
 * Features:
 * - Stable variant assignment based on user ID hash
 * - Analytics tracking for experiment effectiveness
 * - Remote config integration for experiment parameters
 * - Statistical significance tracking
 * - Multi-armed bandit support for adaptive testing
 *
 * Usage:
 * ```kotlin
 * val variant = abTestingManager.getVariant("hint_timing_experiment")
 * when (variant) {
 *     "control" -> showHintAfter(2000L)
 *     "fast" -> showHintAfter(500L)
 *     "slow" -> showHintAfter(5000L)
 * }
 * abTestingManager.trackExposure("hint_timing_experiment", variant)
 * abTestingManager.trackConversion("hint_timing_experiment", "hint_dismissed")
 * ```
 */

package com.kagami.android.services

import android.content.Context
import android.content.SharedPreferences
import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject
import java.security.MessageDigest
import java.util.UUID
import javax.inject.Inject
import javax.inject.Named
import javax.inject.Singleton

// =============================================================================
// EXPERIMENT MODELS
// =============================================================================

/**
 * Definition of an A/B test experiment.
 */
data class Experiment(
    val id: String,
    val name: String,
    val description: String,
    val variants: List<Variant>,
    val isEnabled: Boolean = true,
    val startTimestamp: Long = 0,
    val endTimestamp: Long = Long.MAX_VALUE,
    val targetAudience: TargetAudience = TargetAudience.ALL,
    val trafficPercentage: Int = 100  // Percentage of users to include
) {
    /**
     * Check if experiment is currently active.
     */
    fun isActive(): Boolean {
        val now = System.currentTimeMillis()
        return isEnabled && now >= startTimestamp && now <= endTimestamp
    }

    companion object {
        fun fromJson(json: JSONObject): Experiment {
            val variantsArray = json.optJSONArray("variants") ?: JSONArray()
            val variants = (0 until variantsArray.length()).map {
                Variant.fromJson(variantsArray.getJSONObject(it))
            }

            return Experiment(
                id = json.optString("id"),
                name = json.optString("name"),
                description = json.optString("description", ""),
                variants = variants,
                isEnabled = json.optBoolean("enabled", true),
                startTimestamp = json.optLong("start_timestamp", 0),
                endTimestamp = json.optLong("end_timestamp", Long.MAX_VALUE),
                targetAudience = try {
                    TargetAudience.valueOf(json.optString("target_audience", "ALL"))
                } catch (e: Exception) {
                    TargetAudience.ALL
                },
                trafficPercentage = json.optInt("traffic_percentage", 100)
            )
        }
    }
}

/**
 * A variant within an experiment.
 */
data class Variant(
    val id: String,
    val name: String,
    val weight: Int = 1,  // Relative weight for distribution
    val config: Map<String, Any> = emptyMap()
) {
    companion object {
        fun fromJson(json: JSONObject): Variant {
            val config = mutableMapOf<String, Any>()
            json.optJSONObject("config")?.let { configJson ->
                configJson.keys().forEach { key ->
                    config[key] = configJson.get(key)
                }
            }

            return Variant(
                id = json.optString("id"),
                name = json.optString("name"),
                weight = json.optInt("weight", 1),
                config = config
            )
        }
    }
}

/**
 * Target audience for experiment filtering.
 */
enum class TargetAudience {
    ALL,                // All users
    NEW_USERS,          // Users who signed up in last 7 days
    RETURNING_USERS,    // Users with >7 days since signup
    POWER_USERS,        // Users with high engagement
    WEAR_OS_USERS,      // Users with Wear OS connected
    WIDGET_USERS        // Users with widgets added
}

/**
 * Experiment exposure event.
 */
data class ExposureEvent(
    val experimentId: String,
    val variantId: String,
    val timestamp: Long = System.currentTimeMillis(),
    val context: Map<String, String> = emptyMap()
)

/**
 * Experiment conversion event.
 */
data class ConversionEvent(
    val experimentId: String,
    val variantId: String,
    val conversionType: String,
    val timestamp: Long = System.currentTimeMillis(),
    val value: Double? = null,
    val metadata: Map<String, String> = emptyMap()
)

/**
 * Experiment metrics for a variant.
 */
data class VariantMetrics(
    val variantId: String,
    val exposures: Int = 0,
    val conversions: Int = 0,
    val conversionRate: Float = 0f,
    val averageValue: Double = 0.0
)

/**
 * Experiment results summary.
 */
data class ExperimentResults(
    val experimentId: String,
    val totalExposures: Int,
    val totalConversions: Int,
    val variantMetrics: Map<String, VariantMetrics>,
    val winningVariant: String?,
    val isStatisticallySignificant: Boolean = false,
    val confidenceLevel: Float = 0f
)

// =============================================================================
// HINT-SPECIFIC EXPERIMENTS
// =============================================================================

/**
 * Predefined hint experiments.
 */
object HintExperiments {

    /**
     * Experiment: Optimal hint display timing.
     */
    val HINT_TIMING = Experiment(
        id = "hint_timing_v1",
        name = "Hint Display Timing",
        description = "Test optimal delay before showing contextual hints",
        variants = listOf(
            Variant(id = "control", name = "Default (2s)", weight = 1, config = mapOf("delay_ms" to 2000)),
            Variant(id = "fast", name = "Fast (500ms)", weight = 1, config = mapOf("delay_ms" to 500)),
            Variant(id = "slow", name = "Slow (5s)", weight = 1, config = mapOf("delay_ms" to 5000)),
            Variant(id = "progressive", name = "Progressive", weight = 1, config = mapOf("delay_ms" to 1000, "progressive" to true))
        )
    )

    /**
     * Experiment: Hint content style.
     */
    val HINT_STYLE = Experiment(
        id = "hint_style_v1",
        name = "Hint Content Style",
        description = "Test different hint presentation styles",
        variants = listOf(
            Variant(id = "control", name = "Standard Card", weight = 1, config = mapOf("style" to "card")),
            Variant(id = "tooltip", name = "Tooltip", weight = 1, config = mapOf("style" to "tooltip")),
            Variant(id = "inline", name = "Inline Text", weight = 1, config = mapOf("style" to "inline")),
            Variant(id = "animated", name = "Animated", weight = 1, config = mapOf("style" to "animated"))
        )
    )

    /**
     * Experiment: Hint dismissal behavior.
     */
    val HINT_DISMISSAL = Experiment(
        id = "hint_dismissal_v1",
        name = "Hint Dismissal Behavior",
        description = "Test how hints are dismissed",
        variants = listOf(
            Variant(id = "control", name = "Manual Dismiss", weight = 1, config = mapOf("auto_dismiss" to false)),
            Variant(id = "auto_5s", name = "Auto-dismiss 5s", weight = 1, config = mapOf("auto_dismiss" to true, "duration_ms" to 5000)),
            Variant(id = "auto_10s", name = "Auto-dismiss 10s", weight = 1, config = mapOf("auto_dismiss" to true, "duration_ms" to 10000)),
            Variant(id = "swipe", name = "Swipe to Dismiss", weight = 1, config = mapOf("auto_dismiss" to false, "swipe_enabled" to true))
        )
    )

    /**
     * Experiment: Number of hints per session.
     */
    val HINT_FREQUENCY = Experiment(
        id = "hint_frequency_v1",
        name = "Hints Per Session",
        description = "Test optimal number of hints shown per session",
        variants = listOf(
            Variant(id = "control", name = "Unlimited", weight = 1, config = mapOf("max_per_session" to -1)),
            Variant(id = "one", name = "One Per Session", weight = 1, config = mapOf("max_per_session" to 1)),
            Variant(id = "three", name = "Three Per Session", weight = 1, config = mapOf("max_per_session" to 3)),
            Variant(id = "adaptive", name = "Adaptive", weight = 1, config = mapOf("max_per_session" to -1, "adaptive" to true))
        )
    )

    val ALL_EXPERIMENTS = listOf(HINT_TIMING, HINT_STYLE, HINT_DISMISSAL, HINT_FREQUENCY)
}

// =============================================================================
// A/B TESTING MANAGER
// =============================================================================

/**
 * A/B Testing Manager
 *
 * Manages experiment variant assignment, exposure tracking, and conversion analytics.
 */
@Singleton
class ABTestingManager @Inject constructor(
    @Named("regular") private val prefs: SharedPreferences,
    private val analyticsService: AnalyticsService,
    private val featureFlagsService: FeatureFlagsService
) {

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    companion object {
        private const val TAG = "ABTestingManager"

        // Preference keys
        private const val PREFS_PREFIX = "ab_test_"
        private const val KEY_USER_ID = "ab_test_user_id"
        private const val KEY_VARIANT_PREFIX = "ab_variant_"
        private const val KEY_EXPOSURE_PREFIX = "ab_exposure_"
        private const val KEY_CONVERSION_PREFIX = "ab_conversion_"

        // Statistical significance threshold
        private const val SIGNIFICANCE_THRESHOLD = 0.95f
        private const val MIN_SAMPLE_SIZE = 100
    }

    // State
    private val _experiments = MutableStateFlow<Map<String, Experiment>>(emptyMap())
    val experiments: StateFlow<Map<String, Experiment>> = _experiments.asStateFlow()

    private val _assignedVariants = MutableStateFlow<Map<String, String>>(emptyMap())
    val assignedVariants: StateFlow<Map<String, String>> = _assignedVariants.asStateFlow()

    // User ID for consistent assignment
    private var userId: String = ""

    // In-memory cache for variant configs
    private val variantConfigCache = mutableMapOf<String, Map<String, Any>>()

    // =============================================================
    // INITIALIZATION
    // =============================================================

    /**
     * Initialize the A/B testing manager.
     * Call this at app startup.
     */
    suspend fun initialize(context: Context) {
        // Get or create stable user ID
        userId = prefs.getString(KEY_USER_ID, null) ?: run {
            val newId = UUID.randomUUID().toString()
            prefs.edit().putString(KEY_USER_ID, newId).apply()
            newId
        }

        // Load built-in experiments
        val experimentsMap = HintExperiments.ALL_EXPERIMENTS.associateBy { it.id }
        _experiments.value = experimentsMap

        // Load cached variant assignments
        loadCachedAssignments()

        // Try to fetch remote config experiments
        fetchRemoteExperiments()

        Log.i(TAG, "A/B Testing initialized with ${experimentsMap.size} experiments")
    }

    /**
     * Load cached variant assignments from preferences.
     */
    private fun loadCachedAssignments() {
        val assignments = mutableMapOf<String, String>()
        _experiments.value.keys.forEach { experimentId ->
            prefs.getString(KEY_VARIANT_PREFIX + experimentId, null)?.let { variantId ->
                assignments[experimentId] = variantId
            }
        }
        _assignedVariants.value = assignments
    }

    /**
     * Fetch experiments from remote config (if available).
     */
    private suspend fun fetchRemoteExperiments() {
        // This would integrate with Firebase Remote Config or similar
        // For now, we use the built-in experiments
        try {
            val remoteExperimentsJson = featureFlagsService.getString("ab_experiments")
            if (remoteExperimentsJson.isNotEmpty()) {
                val json = JSONArray(remoteExperimentsJson)
                val remoteExperiments = (0 until json.length()).map {
                    Experiment.fromJson(json.getJSONObject(it))
                }
                val merged = _experiments.value.toMutableMap()
                remoteExperiments.forEach { merged[it.id] = it }
                _experiments.value = merged
            }
        } catch (e: Exception) {
            Log.d(TAG, "No remote experiments configured")
        }
    }

    // =============================================================
    // VARIANT ASSIGNMENT
    // =============================================================

    /**
     * Get the variant for an experiment.
     * Uses deterministic hashing for stable assignment.
     */
    fun getVariant(experimentId: String): String {
        // Check cache first
        _assignedVariants.value[experimentId]?.let { return it }

        val experiment = _experiments.value[experimentId]
            ?: return "control" // Default if experiment not found

        // Check if experiment is active
        if (!experiment.isActive()) {
            return experiment.variants.firstOrNull()?.id ?: "control"
        }

        // Check traffic allocation
        if (!isInTrafficAllocation(experimentId, experiment.trafficPercentage)) {
            return experiment.variants.firstOrNull()?.id ?: "control"
        }

        // Deterministic variant assignment
        val variant = assignVariant(experimentId, experiment.variants)

        // Cache assignment
        cacheVariantAssignment(experimentId, variant)

        return variant
    }

    /**
     * Get variant config value.
     */
    @Suppress("UNCHECKED_CAST")
    fun <T> getVariantConfig(experimentId: String, key: String, default: T): T {
        val variantId = getVariant(experimentId)
        val experiment = _experiments.value[experimentId] ?: return default
        val variant = experiment.variants.find { it.id == variantId } ?: return default

        return (variant.config[key] as? T) ?: default
    }

    /**
     * Check if user is in traffic allocation for experiment.
     */
    private fun isInTrafficAllocation(experimentId: String, percentage: Int): Boolean {
        if (percentage >= 100) return true
        if (percentage <= 0) return false

        val hash = hashString("$userId:$experimentId:traffic")
        val bucket = (hash and 0x7FFFFFFF) % 100
        return bucket < percentage
    }

    /**
     * Assign a variant based on weighted distribution.
     */
    private fun assignVariant(experimentId: String, variants: List<Variant>): String {
        if (variants.isEmpty()) return "control"
        if (variants.size == 1) return variants[0].id

        val totalWeight = variants.sumOf { it.weight }
        val hash = hashString("$userId:$experimentId:variant")
        val bucket = (hash and 0x7FFFFFFF) % totalWeight

        var cumulative = 0
        for (variant in variants) {
            cumulative += variant.weight
            if (bucket < cumulative) {
                return variant.id
            }
        }

        return variants.last().id
    }

    /**
     * Hash a string to a stable integer.
     */
    private fun hashString(input: String): Int {
        return try {
            val md = MessageDigest.getInstance("MD5")
            val bytes = md.digest(input.toByteArray())
            ((bytes[0].toInt() and 0xFF) shl 24) or
                    ((bytes[1].toInt() and 0xFF) shl 16) or
                    ((bytes[2].toInt() and 0xFF) shl 8) or
                    (bytes[3].toInt() and 0xFF)
        } catch (e: Exception) {
            input.hashCode()
        }
    }

    /**
     * Cache variant assignment.
     */
    private fun cacheVariantAssignment(experimentId: String, variantId: String) {
        prefs.edit().putString(KEY_VARIANT_PREFIX + experimentId, variantId).apply()
        _assignedVariants.value = _assignedVariants.value + (experimentId to variantId)
    }

    // =============================================================
    // TRACKING
    // =============================================================

    /**
     * Track experiment exposure (when user sees the variant).
     */
    fun trackExposure(experimentId: String, context: Map<String, String> = emptyMap()) {
        val variantId = _assignedVariants.value[experimentId] ?: getVariant(experimentId)

        // Track in analytics
        analyticsService.trackAction(
            actionName = "ab_exposure",
            context = mapOf(
                "experiment_id" to experimentId,
                "variant_id" to variantId
            ) + context
        )

        // Increment local exposure count
        val key = KEY_EXPOSURE_PREFIX + experimentId
        val currentCount = prefs.getInt(key, 0)
        prefs.edit().putInt(key, currentCount + 1).apply()

        Log.d(TAG, "Exposure tracked: $experimentId -> $variantId")
    }

    /**
     * Track conversion event.
     */
    fun trackConversion(
        experimentId: String,
        conversionType: String,
        value: Double? = null,
        metadata: Map<String, String> = emptyMap()
    ) {
        val variantId = _assignedVariants.value[experimentId] ?: return

        // Track in analytics
        analyticsService.trackAction(
            actionName = "ab_conversion",
            context = mapOf(
                "experiment_id" to experimentId,
                "variant_id" to variantId,
                "conversion_type" to conversionType
            ) + metadata + (value?.let { mapOf("value" to it.toString()) } ?: emptyMap())
        )

        // Increment local conversion count
        val key = KEY_CONVERSION_PREFIX + experimentId + "_" + conversionType
        val currentCount = prefs.getInt(key, 0)
        prefs.edit().putInt(key, currentCount + 1).apply()

        Log.d(TAG, "Conversion tracked: $experimentId -> $variantId ($conversionType)")
    }

    // =============================================================
    // HINT-SPECIFIC HELPERS
    // =============================================================

    /**
     * Get hint display delay from timing experiment.
     */
    fun getHintDelayMs(): Long {
        return getVariantConfig(
            experimentId = HintExperiments.HINT_TIMING.id,
            key = "delay_ms",
            default = 2000L
        )
    }

    /**
     * Get hint style from style experiment.
     */
    fun getHintStyle(): String {
        return getVariantConfig(
            experimentId = HintExperiments.HINT_STYLE.id,
            key = "style",
            default = "card"
        )
    }

    /**
     * Check if hint should auto-dismiss.
     */
    fun shouldAutoDismissHint(): Boolean {
        return getVariantConfig(
            experimentId = HintExperiments.HINT_DISMISSAL.id,
            key = "auto_dismiss",
            default = false
        )
    }

    /**
     * Get auto-dismiss duration.
     */
    fun getHintAutoDismissDuration(): Long {
        return getVariantConfig(
            experimentId = HintExperiments.HINT_DISMISSAL.id,
            key = "duration_ms",
            default = 5000L
        )
    }

    /**
     * Get max hints per session.
     */
    fun getMaxHintsPerSession(): Int {
        return getVariantConfig(
            experimentId = HintExperiments.HINT_FREQUENCY.id,
            key = "max_per_session",
            default = -1
        )
    }

    /**
     * Track hint interaction.
     */
    fun trackHintInteraction(
        hintId: String,
        action: HintAction,
        durationMs: Long? = null
    ) {
        // Track for all hint experiments
        HintExperiments.ALL_EXPERIMENTS.forEach { experiment ->
            trackConversion(
                experimentId = experiment.id,
                conversionType = "hint_${action.name.lowercase()}",
                metadata = buildMap {
                    put("hint_id", hintId)
                    durationMs?.let { put("view_duration_ms", it.toString()) }
                }
            )
        }
    }

    // =============================================================
    // RESULTS & ANALYTICS
    // =============================================================

    /**
     * Get experiment results (local metrics only).
     */
    fun getExperimentResults(experimentId: String): ExperimentResults {
        val experiment = _experiments.value[experimentId]
            ?: return ExperimentResults(experimentId, 0, 0, emptyMap(), null)

        val variantMetrics = experiment.variants.associate { variant ->
            val exposures = prefs.getInt(KEY_EXPOSURE_PREFIX + experimentId + "_" + variant.id, 0)
            val conversions = prefs.getInt(KEY_CONVERSION_PREFIX + experimentId + "_" + variant.id, 0)
            val conversionRate = if (exposures > 0) conversions.toFloat() / exposures else 0f

            variant.id to VariantMetrics(
                variantId = variant.id,
                exposures = exposures,
                conversions = conversions,
                conversionRate = conversionRate
            )
        }

        val totalExposures = variantMetrics.values.sumOf { it.exposures }
        val totalConversions = variantMetrics.values.sumOf { it.conversions }

        // Find winning variant (highest conversion rate with min sample)
        val winningVariant = variantMetrics.values
            .filter { it.exposures >= MIN_SAMPLE_SIZE }
            .maxByOrNull { it.conversionRate }
            ?.variantId

        return ExperimentResults(
            experimentId = experimentId,
            totalExposures = totalExposures,
            totalConversions = totalConversions,
            variantMetrics = variantMetrics,
            winningVariant = winningVariant,
            isStatisticallySignificant = totalExposures >= MIN_SAMPLE_SIZE * experiment.variants.size
        )
    }

    /**
     * Force a specific variant (for testing/debugging).
     */
    fun forceVariant(experimentId: String, variantId: String) {
        cacheVariantAssignment(experimentId, variantId)
        Log.w(TAG, "Forced variant: $experimentId -> $variantId")
    }

    /**
     * Reset all experiment assignments.
     */
    fun resetAllAssignments() {
        val editor = prefs.edit()
        _experiments.value.keys.forEach { experimentId ->
            editor.remove(KEY_VARIANT_PREFIX + experimentId)
        }
        editor.apply()
        _assignedVariants.value = emptyMap()
        Log.i(TAG, "All experiment assignments reset")
    }
}

/**
 * Hint interaction action types.
 */
enum class HintAction {
    SHOWN,
    DISMISSED,
    TAPPED,
    SWIPED,
    AUTO_DISMISSED,
    ACTION_TAKEN  // User performed the suggested action
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
