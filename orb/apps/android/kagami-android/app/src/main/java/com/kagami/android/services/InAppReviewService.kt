/**
 * Kagami In-App Review Service
 *
 * Colony: Beacon (e5) - Planning
 * h(x) >= 0. Always.
 *
 * Prompts for app review after:
 * - 7 days since first launch
 * - 5+ scene activations
 *
 * Uses Google Play In-App Review API (non-intrusive).
 */

package com.kagami.android.services

import android.app.Activity
import android.content.SharedPreferences
import com.google.android.play.core.review.ReviewManagerFactory
import kotlinx.coroutines.tasks.await
import javax.inject.Inject
import javax.inject.Named
import javax.inject.Singleton

@Singleton
class InAppReviewService @Inject constructor(
    @Named("encrypted") private val prefs: SharedPreferences
) {
    companion object {
        private const val KEY_FIRST_LAUNCH = "first_launch_timestamp"
        private const val KEY_ACTIVATION_COUNT = "scene_activation_count"
        private const val KEY_REVIEW_SHOWN = "review_already_shown"

        private const val DAYS_THRESHOLD = 7
        private const val ACTIVATION_THRESHOLD = 5
        private const val MILLIS_PER_DAY = 24 * 60 * 60 * 1000L
    }

    /**
     * Record that the app was launched. Sets first launch timestamp if not set.
     */
    fun recordLaunch() {
        if (prefs.getLong(KEY_FIRST_LAUNCH, 0L) == 0L) {
            prefs.edit().putLong(KEY_FIRST_LAUNCH, System.currentTimeMillis()).apply()
        }
    }

    /**
     * Record a scene activation. Increments the counter.
     */
    fun recordSceneActivation() {
        val current = prefs.getInt(KEY_ACTIVATION_COUNT, 0)
        prefs.edit().putInt(KEY_ACTIVATION_COUNT, current + 1).apply()
    }

    /**
     * Check if conditions are met to show review prompt.
     *
     * Conditions:
     * 1. Review has not been shown before
     * 2. At least 7 days since first launch
     * 3. At least 5 scene activations
     */
    fun shouldShowReview(): Boolean {
        // Already shown once
        if (prefs.getBoolean(KEY_REVIEW_SHOWN, false)) {
            return false
        }

        val firstLaunch = prefs.getLong(KEY_FIRST_LAUNCH, 0L)
        val activationCount = prefs.getInt(KEY_ACTIVATION_COUNT, 0)

        // Check time threshold (7 days)
        val daysSinceFirstLaunch = if (firstLaunch > 0) {
            (System.currentTimeMillis() - firstLaunch) / MILLIS_PER_DAY
        } else {
            0
        }

        return daysSinceFirstLaunch >= DAYS_THRESHOLD && activationCount >= ACTIVATION_THRESHOLD
    }

    /**
     * Request in-app review using Google Play Review API.
     *
     * This shows the native Play Store review dialog if conditions are met.
     * The actual dialog appearance is controlled by Play Store quotas.
     *
     * @param activity The activity to launch the review flow from
     */
    suspend fun requestReview(activity: Activity) {
        if (!shouldShowReview()) return

        try {
            val reviewManager = ReviewManagerFactory.create(activity)
            val reviewInfo = reviewManager.requestReviewFlow().await()

            // Launch the review flow
            reviewManager.launchReviewFlow(activity, reviewInfo).await()

            // Mark as shown (even if user dismissed - we don't know the outcome)
            prefs.edit().putBoolean(KEY_REVIEW_SHOWN, true).apply()
        } catch (e: Exception) {
            // Silently fail - review is non-critical
            // Don't mark as shown so we can retry later
        }
    }

    /**
     * Get current stats for debugging/testing.
     */
    fun getStats(): ReviewStats {
        val firstLaunch = prefs.getLong(KEY_FIRST_LAUNCH, 0L)
        val daysSince = if (firstLaunch > 0) {
            ((System.currentTimeMillis() - firstLaunch) / MILLIS_PER_DAY).toInt()
        } else {
            0
        }

        return ReviewStats(
            daysSinceFirstLaunch = daysSince,
            sceneActivationCount = prefs.getInt(KEY_ACTIVATION_COUNT, 0),
            reviewAlreadyShown = prefs.getBoolean(KEY_REVIEW_SHOWN, false),
            readyForReview = shouldShowReview()
        )
    }

    /**
     * Reset all review tracking (for testing only).
     */
    fun resetForTesting() {
        prefs.edit()
            .remove(KEY_FIRST_LAUNCH)
            .remove(KEY_ACTIVATION_COUNT)
            .remove(KEY_REVIEW_SHOWN)
            .apply()
    }
}

/**
 * Stats for review eligibility tracking.
 */
data class ReviewStats(
    val daysSinceFirstLaunch: Int,
    val sceneActivationCount: Int,
    val reviewAlreadyShown: Boolean,
    val readyForReview: Boolean
)
