/**
 * Kagami Accessibility Components
 *
 * Colony: Crystal (e7) — Verification & Polish
 *
 * Comprehensive accessible UI components:
 * - Focus management for TalkBack
 * - Semantic grouping for screen readers
 * - Live regions for announcements
 * - Custom actions support
 * - Touch exploration helpers
 *
 * All components follow WCAG 2.1 AA guidelines.
 *
 * h(x) >= 0. Always.
 */

package com.kagami.android.ui.components

import android.view.accessibility.AccessibilityManager
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.focusable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.material3.ripple
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.ExperimentalComposeUiApi
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.*
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.kagami.android.services.HapticPattern
import com.kagami.android.services.KagamiHaptics
import com.kagami.android.ui.LocalAccessibilityConfig
import com.kagami.android.ui.theme.*

// =============================================================================
// ACCESSIBLE BUTTON
// =============================================================================

/**
 * Accessible button with proper semantics and haptic feedback.
 */
@Composable
fun AccessibleButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    contentDescription: String,
    stateDescription: String? = null,
    hapticPattern: HapticPattern = HapticPattern.SELECTION,
    content: @Composable RowScope.() -> Unit
) {
    val context = LocalContext.current
    val haptics = remember { KagamiHaptics.getInstance(context) }

    Button(
        onClick = {
            haptics.play(hapticPattern)
            onClick()
        },
        modifier = modifier
            .defaultMinSize(minWidth = 48.dp, minHeight = 48.dp)
            .semantics {
                this.contentDescription = contentDescription
                stateDescription?.let { this.stateDescription = it }
            },
        enabled = enabled,
        content = content
    )
}

/**
 * Accessible icon button with minimum touch target.
 */
@Composable
fun AccessibleIconButton(
    onClick: () -> Unit,
    icon: @Composable () -> Unit,
    contentDescription: String,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    hapticPattern: HapticPattern = HapticPattern.SELECTION
) {
    val context = LocalContext.current
    val haptics = remember { KagamiHaptics.getInstance(context) }

    IconButton(
        onClick = {
            haptics.play(hapticPattern)
            onClick()
        },
        modifier = modifier
            .size(48.dp)
            .semantics {
                this.contentDescription = contentDescription
                role = Role.Button
            },
        enabled = enabled
    ) {
        icon()
    }
}

// =============================================================================
// ACCESSIBLE TOGGLE
// =============================================================================

/**
 * Accessible toggle with proper state announcements.
 */
@Composable
fun AccessibleToggle(
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit,
    label: String,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    description: String? = null
) {
    val context = LocalContext.current
    val haptics = remember { KagamiHaptics.getInstance(context) }

    val stateText = if (checked) "On" else "Off"
    val actionText = if (checked) "Double tap to turn off" else "Double tap to turn on"

    Row(
        modifier = modifier
            .fillMaxWidth()
            .defaultMinSize(minHeight = 56.dp)
            .toggleable(
                value = checked,
                onValueChange = { newValue ->
                    haptics.play(if (newValue) HapticPattern.SUCCESS else HapticPattern.SELECTION)
                    onCheckedChange(newValue)
                },
                enabled = enabled,
                role = Role.Switch
            )
            .semantics {
                contentDescription = "$label. $stateText. $actionText"
                this.stateDescription = stateText
            }
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = label,
                style = MaterialTheme.typography.bodyLarge
            )
            description?.let {
                Text(
                    text = it,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }

        Spacer(modifier = Modifier.width(16.dp))

        Switch(
            checked = checked,
            onCheckedChange = null, // Handled by parent
            enabled = enabled
        )
    }
}

// =============================================================================
// ACCESSIBLE SLIDER
// =============================================================================

/**
 * Accessible slider with value announcements.
 */
@Composable
fun AccessibleSlider(
    value: Float,
    onValueChange: (Float) -> Unit,
    label: String,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    valueRange: ClosedFloatingPointRange<Float> = 0f..100f,
    steps: Int = 0,
    formatValue: (Float) -> String = { "${it.toInt()}%" },
    onValueChangeFinished: (() -> Unit)? = null
) {
    val context = LocalContext.current
    val haptics = remember { KagamiHaptics.getInstance(context) }

    val formattedValue = formatValue(value)

    Column(
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 8.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text(
                text = label,
                style = MaterialTheme.typography.bodyLarge
            )
            Text(
                text = formattedValue,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.primary
            )
        }

        Spacer(modifier = Modifier.height(8.dp))

        Slider(
            value = value,
            onValueChange = { newValue ->
                // Play tick haptic at intervals
                val oldInt = value.toInt()
                val newInt = newValue.toInt()
                if (oldInt != newInt && newInt % 10 == 0) {
                    haptics.play(HapticPattern.TICK)
                }
                onValueChange(newValue)
            },
            onValueChangeFinished = {
                haptics.play(HapticPattern.SUCCESS)
                onValueChangeFinished?.invoke()
            },
            modifier = Modifier
                .fillMaxWidth()
                .semantics {
                    contentDescription = "$label. Currently $formattedValue. Swipe up or down to adjust."
                    stateDescription = formattedValue
                    setProgress { targetValue ->
                        onValueChange(targetValue)
                        true
                    }
                },
            enabled = enabled,
            valueRange = valueRange,
            steps = steps
        )
    }
}

// =============================================================================
// ACCESSIBLE CARD
// =============================================================================

/**
 * Accessible card with proper grouping and focus.
 */
@Composable
fun AccessibleCard(
    onClick: () -> Unit,
    contentDescription: String,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    isSelected: Boolean = false,
    hapticPattern: HapticPattern = HapticPattern.SELECTION,
    content: @Composable ColumnScope.() -> Unit
) {
    val context = LocalContext.current
    val haptics = remember { KagamiHaptics.getInstance(context) }

    val borderColor = if (isSelected) MaterialTheme.colorScheme.primary else Color.Transparent
    val selectedText = if (isSelected) "Selected. " else ""

    Card(
        onClick = {
            haptics.play(hapticPattern)
            onClick()
        },
        modifier = modifier
            .defaultMinSize(minHeight = 48.dp)
            .border(
                width = if (isSelected) 2.dp else 0.dp,
                color = borderColor,
                shape = RoundedCornerShape(12.dp)
            )
            .semantics(mergeDescendants = true) {
                this.contentDescription = "$selectedText$contentDescription"
                role = Role.Button
            },
        enabled = enabled
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            content = content
        )
    }
}

// =============================================================================
// ACCESSIBLE HEADING
// =============================================================================

/**
 * Accessible heading for TalkBack navigation.
 */
@Composable
fun AccessibleHeading(
    text: String,
    modifier: Modifier = Modifier,
    level: Int = 1, // 1-6 for heading levels
    style: androidx.compose.ui.text.TextStyle = MaterialTheme.typography.titleLarge
) {
    Text(
        text = text,
        style = style,
        modifier = modifier.semantics {
            heading()
            contentDescription = "$text, heading level $level"
        }
    )
}

// =============================================================================
// LIVE REGION FOR ANNOUNCEMENTS
// =============================================================================

/**
 * Live region that announces changes to screen readers.
 */
@Composable
fun LiveRegion(
    text: String,
    modifier: Modifier = Modifier,
    isPolite: Boolean = true
) {
    val liveRegionMode = if (isPolite) {
        LiveRegionMode.Polite
    } else {
        LiveRegionMode.Assertive
    }

    Text(
        text = text,
        modifier = modifier.semantics {
            liveRegion = liveRegionMode
        }
    )
}

/**
 * Invisible live region for status announcements.
 */
@Composable
fun StatusAnnouncement(
    message: String?,
    modifier: Modifier = Modifier
) {
    message?.let {
        Box(
            modifier = modifier
                .size(1.dp)
                .semantics {
                    liveRegion = LiveRegionMode.Assertive
                    contentDescription = it
                }
        )
    }
}

// =============================================================================
// SEMANTIC GROUPING
// =============================================================================

/**
 * Group related content for screen readers.
 */
@Composable
fun SemanticGroup(
    contentDescription: String,
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit
) {
    Box(
        modifier = modifier.semantics(mergeDescendants = true) {
            this.contentDescription = contentDescription
        }
    ) {
        content()
    }
}

/**
 * Hide decorative elements from screen readers.
 */
fun Modifier.decorative(): Modifier = this.semantics {
    invisibleToUser()
}

// =============================================================================
// FOCUS MANAGEMENT
// =============================================================================

/**
 * Composable that requests focus when it becomes visible.
 * Useful for announcing new content to screen reader users.
 */
@Composable
fun FocusOnMount(
    requestFocus: Boolean = true,
    content: @Composable (FocusRequester) -> Unit
) {
    val focusRequester = remember { FocusRequester() }

    LaunchedEffect(requestFocus) {
        if (requestFocus) {
            focusRequester.requestFocus()
        }
    }

    content(focusRequester)
}

/**
 * Modifier to handle focus state with visual feedback.
 */
fun Modifier.accessibleFocus(
    onFocusChanged: (Boolean) -> Unit = {}
): Modifier = this
    .focusable()
    .onFocusChanged { focusState ->
        onFocusChanged(focusState.isFocused)
    }

// =============================================================================
// TOUCH EXPLORATION HELPERS
// =============================================================================

/**
 * Accessible touch target that meets minimum size requirements.
 */
@Composable
fun TouchTarget(
    onClick: () -> Unit,
    contentDescription: String,
    modifier: Modifier = Modifier,
    minSize: Dp = 48.dp,
    content: @Composable BoxScope.() -> Unit
) {
    val context = LocalContext.current
    val haptics = remember { KagamiHaptics.getInstance(context) }
    val interactionSource = remember { MutableInteractionSource() }

    Box(
        modifier = modifier
            .defaultMinSize(minWidth = minSize, minHeight = minSize)
            .clickable(
                interactionSource = interactionSource,
                indication = ripple(bounded = false, radius = minSize / 2),
                onClick = {
                    haptics.play(HapticPattern.SELECTION)
                    onClick()
                }
            )
            .semantics {
                this.contentDescription = contentDescription
                role = Role.Button
            },
        contentAlignment = Alignment.Center,
        content = content
    )
}

// =============================================================================
// ACCESSIBILITY STATE HELPERS
// =============================================================================

/**
 * Check if TalkBack is active.
 */
@Composable
fun isTalkBackActive(): Boolean {
    val context = LocalContext.current
    val accessibilityManager = remember {
        context.getSystemService(android.content.Context.ACCESSIBILITY_SERVICE) as AccessibilityManager
    }
    return accessibilityManager.isTouchExplorationEnabled
}

/**
 * Get accessibility configuration from local composition.
 */
@Composable
fun rememberAccessibilityState(): AccessibilityState {
    val config = LocalAccessibilityConfig.current
    return remember(config) {
        AccessibilityState(
            isReducedMotionEnabled = config.isReducedMotionEnabled,
            isHighContrastEnabled = config.isHighContrastEnabled,
            isTalkBackEnabled = config.isTalkBackEnabled,
            fontScale = config.fontScale
        )
    }
}

data class AccessibilityState(
    val isReducedMotionEnabled: Boolean,
    val isHighContrastEnabled: Boolean,
    val isTalkBackEnabled: Boolean,
    val fontScale: Float
)

// =============================================================================
// CUSTOM ACTIONS FOR COMPLEX COMPONENTS
// =============================================================================

/**
 * Add custom accessibility actions to a modifier.
 */
fun Modifier.withCustomActions(
    actions: List<KagamiAccessibilityAction>
): Modifier = this.semantics {
    customActions = actions.map { kagamiAction ->
        androidx.compose.ui.semantics.CustomAccessibilityAction(kagamiAction.label) {
            kagamiAction.action()
            true
        }
    }
}

data class KagamiAccessibilityAction(
    val label: String,
    val action: () -> Unit
)

/*
 * Mirror
 * Accessibility is not optional.
 * Every user deserves equal access.
 * h(x) >= 0. Always.
 */
