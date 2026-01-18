/**
 * Kagami Contextual Hint Engine
 *
 * Colony: Beacon (e5) - Planning
 *
 * P1: System to show tips based on user behavior.
 * - Track feature usage
 * - Show contextual hints after thresholds
 * - Store hint_shown flags
 *
 * Accessibility:
 * - Announcements for screen readers
 * - Dismissible hints
 * - Non-intrusive positioning
 */

package com.kagami.android.ui.components

import android.content.Context
import android.content.SharedPreferences
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Lightbulb
import androidx.compose.material.icons.filled.Star
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.kagami.android.ui.LocalAccessibilityConfig
import com.kagami.android.ui.minTouchTarget
import com.kagami.android.ui.theme.Beacon
import com.kagami.android.ui.theme.Crystal
import com.kagami.android.ui.theme.Grove
import com.kagami.android.ui.theme.Spark
import com.kagami.android.ui.theme.VoidLight
import kotlinx.coroutines.delay
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Hint types with associated thresholds and content.
 */
enum class HintType(
    val id: String,
    val title: String,
    val message: String,
    val icon: ImageVector,
    val color: Color,
    val triggerThreshold: Int,
    val featureKey: String
) {
    VOICE_COMMAND(
        id = "hint_voice_command",
        title = "Try Voice Commands",
        message = "Tap the microphone button to control your home with voice.",
        icon = Icons.Default.Lightbulb,
        color = Beacon,
        triggerThreshold = 3,
        featureKey = "quick_action_count"
    ),
    QUICK_SCENES(
        id = "hint_quick_scenes",
        title = "Quick Tip: Scenes",
        message = "Use scenes to control multiple devices at once.",
        icon = Icons.Default.Star,
        color = Crystal,
        triggerThreshold = 5,
        featureKey = "room_visit_count"
    ),
    PULL_TO_REFRESH(
        id = "hint_pull_refresh",
        title = "Pull to Refresh",
        message = "Pull down anywhere to refresh your home status.",
        icon = Icons.Default.Info,
        color = Grove,
        triggerThreshold = 2,
        featureKey = "app_open_count"
    ),
    SWIPE_ACTIONS(
        id = "hint_swipe_actions",
        title = "Swipe for Quick Actions",
        message = "Swipe on room cards to quickly adjust lights.",
        icon = Icons.Default.Lightbulb,
        color = Spark,
        triggerThreshold = 4,
        featureKey = "room_tap_count"
    )
}

/**
 * Contextual Hint Engine - Manages hint display based on user behavior.
 */
@Singleton
class ContextualHintEngine @Inject constructor() {

    private lateinit var prefs: SharedPreferences

    companion object {
        private const val PREFS_NAME = "kagami_hints"
        private const val PREFIX_SHOWN = "hint_shown_"
        private const val PREFIX_COUNT = "feature_count_"
        private const val KEY_HINTS_ENABLED = "hints_enabled"
    }

    /**
     * Initialize with context.
     */
    fun initialize(context: Context) {
        prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    }

    /**
     * Check if engine is initialized.
     */
    fun isInitialized(): Boolean = ::prefs.isInitialized

    /**
     * Track feature usage.
     */
    fun trackFeatureUsage(featureKey: String) {
        if (!isInitialized()) return
        val currentCount = prefs.getInt(PREFIX_COUNT + featureKey, 0)
        prefs.edit().putInt(PREFIX_COUNT + featureKey, currentCount + 1).apply()
    }

    /**
     * Get current feature usage count.
     */
    fun getFeatureUsageCount(featureKey: String): Int {
        if (!isInitialized()) return 0
        return prefs.getInt(PREFIX_COUNT + featureKey, 0)
    }

    /**
     * Check if a hint has been shown.
     */
    fun isHintShown(hintType: HintType): Boolean {
        if (!isInitialized()) return true
        return prefs.getBoolean(PREFIX_SHOWN + hintType.id, false)
    }

    /**
     * Mark a hint as shown.
     */
    fun markHintShown(hintType: HintType) {
        if (!isInitialized()) return
        prefs.edit().putBoolean(PREFIX_SHOWN + hintType.id, true).apply()
    }

    /**
     * Reset all hint flags (for testing or user request).
     */
    fun resetAllHints() {
        if (!isInitialized()) return
        val editor = prefs.edit()
        HintType.values().forEach { hint ->
            editor.putBoolean(PREFIX_SHOWN + hint.id, false)
        }
        editor.apply()
    }

    /**
     * Check if hints are enabled globally.
     */
    fun areHintsEnabled(): Boolean {
        if (!isInitialized()) return true
        return prefs.getBoolean(KEY_HINTS_ENABLED, true)
    }

    /**
     * Enable or disable hints globally.
     */
    fun setHintsEnabled(enabled: Boolean) {
        if (!isInitialized()) return
        prefs.edit().putBoolean(KEY_HINTS_ENABLED, enabled).apply()
    }

    /**
     * Get the next hint to show based on current usage.
     * Returns null if no hint should be shown.
     */
    fun getNextHint(): HintType? {
        if (!isInitialized() || !areHintsEnabled()) return null

        return HintType.values().find { hint ->
            val usageCount = getFeatureUsageCount(hint.featureKey)
            val alreadyShown = isHintShown(hint)
            usageCount >= hint.triggerThreshold && !alreadyShown
        }
    }
}

/**
 * Contextual hint card composable.
 */
@Composable
fun ContextualHintCard(
    hint: HintType,
    onDismiss: () -> Unit,
    modifier: Modifier = Modifier
) {
    val accessibilityConfig = LocalAccessibilityConfig.current
    var isVisible by remember { mutableStateOf(true) }

    val alpha by animateFloatAsState(
        targetValue = if (isVisible) 1f else 0f,
        animationSpec = tween(
            durationMillis = if (accessibilityConfig.isReducedMotionEnabled) 0 else 300
        ),
        label = "hint_alpha"
    )

    AnimatedVisibility(
        visible = isVisible,
        enter = if (accessibilityConfig.isReducedMotionEnabled) {
            fadeIn(animationSpec = tween(0))
        } else {
            fadeIn() + expandVertically()
        },
        exit = if (accessibilityConfig.isReducedMotionEnabled) {
            fadeOut(animationSpec = tween(0))
        } else {
            fadeOut() + shrinkVertically()
        }
    ) {
        Box(
            modifier = modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 8.dp)
                .clip(RoundedCornerShape(16.dp))
                .background(hint.color.copy(alpha = 0.15f))
                .alpha(alpha)
                .semantics {
                    contentDescription = "Tip: ${hint.title}. ${hint.message}. Double tap to dismiss."
                    liveRegion = LiveRegionMode.Polite
                }
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                verticalAlignment = Alignment.Top,
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Icon(
                    imageVector = hint.icon,
                    contentDescription = null,
                    tint = hint.color,
                    modifier = Modifier.size(24.dp)
                )

                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = hint.title,
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.SemiBold,
                        color = hint.color
                    )
                    Text(
                        text = hint.message,
                        style = MaterialTheme.typography.bodySmall,
                        color = Color.White.copy(alpha = 0.8f)
                    )
                }

                IconButton(
                    onClick = {
                        isVisible = false
                        onDismiss()
                    },
                    modifier = Modifier
                        .minTouchTarget()
                        .semantics {
                            contentDescription = "Dismiss tip"
                            role = Role.Button
                        }
                ) {
                    Icon(
                        imageVector = Icons.Default.Close,
                        contentDescription = null,
                        tint = Color.White.copy(alpha = 0.5f),
                        modifier = Modifier.size(20.dp)
                    )
                }
            }
        }
    }
}

/**
 * Composable that automatically shows contextual hints.
 */
@Composable
fun ContextualHintProvider(
    hintEngine: ContextualHintEngine,
    modifier: Modifier = Modifier,
    autoShowDelay: Long = 2000L,
    content: @Composable () -> Unit
) {
    val context = LocalContext.current
    var currentHint by remember { mutableStateOf<HintType?>(null) }

    // Initialize engine if needed
    LaunchedEffect(Unit) {
        if (!hintEngine.isInitialized()) {
            hintEngine.initialize(context)
        }
    }

    // Check for hints after delay
    LaunchedEffect(Unit) {
        delay(autoShowDelay)
        currentHint = hintEngine.getNextHint()
    }

    Column(modifier = modifier) {
        // Show hint if available
        currentHint?.let { hint ->
            ContextualHintCard(
                hint = hint,
                onDismiss = {
                    hintEngine.markHintShown(hint)
                    currentHint = hintEngine.getNextHint()
                }
            )
        }

        // Main content
        content()
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
