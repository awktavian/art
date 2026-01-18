/**
 * Kagami UI State Components — Loading, Error, Empty States
 *
 * Colony: Crystal (e7) — Verification
 *
 * Reusable UI state components for consistent UX across all screens.
 * Follows Material 3 guidelines with accessibility support.
 *
 * h(x) >= 0. Always.
 */

package com.kagami.android.ui.components

import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.kagami.android.R
import com.kagami.android.ui.LocalAccessibilityConfig
import com.kagami.android.ui.MinTouchTargetSize
import com.kagami.android.ui.theme.*

/**
 * UI State sealed class for representing different states
 */
sealed class UIState<out T> {
    object Loading : UIState<Nothing>()
    data class Success<T>(val data: T) : UIState<T>()
    data class Error(val message: String, val retryable: Boolean = true) : UIState<Nothing>()
    object Empty : UIState<Nothing>()
}

/**
 * Loading indicator with animated dots
 */
@Composable
fun LoadingIndicator(
    modifier: Modifier = Modifier,
    message: String = stringResource(R.string.common_loading),
    showMessage: Boolean = true
) {
    val accessibilityConfig = LocalAccessibilityConfig.current
    val infiniteTransition = rememberInfiniteTransition(label = "loading")

    // Animated dots
    val scales = (0..2).map { index ->
        infiniteTransition.animateFloat(
            initialValue = 0.5f,
            targetValue = 1f,
            animationSpec = infiniteRepeatable(
                animation = tween(
                    durationMillis = if (accessibilityConfig.isReducedMotionEnabled) 0 else 500,
                    easing = EaseInOutSine
                ),
                repeatMode = RepeatMode.Reverse,
                initialStartOffset = StartOffset(
                    if (accessibilityConfig.isReducedMotionEnabled) 0 else index * 150
                )
            ),
            label = "dot_$index"
        )
    }

    Column(
        modifier = modifier
            .fillMaxWidth()
            .padding(32.dp)
            .semantics {
                contentDescription = message
            },
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        // Animated dots row
        Row(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            scales.forEachIndexed { index, scale ->
                Box(
                    modifier = Modifier
                        .size(12.dp)
                        .scale(scale.value)
                        .clip(CircleShape)
                        .background(Crystal.copy(alpha = 0.5f + 0.5f * scale.value))
                )
            }
        }

        if (showMessage) {
            Spacer(modifier = Modifier.height(16.dp))
            Text(
                text = message,
                style = MaterialTheme.typography.bodyMedium,
                color = Color.White.copy(alpha = 0.7f)
            )
        }
    }
}

/**
 * Full screen loading state
 */
@Composable
fun LoadingScreen(
    modifier: Modifier = Modifier,
    message: String = stringResource(R.string.common_loading)
) {
    Box(
        modifier = modifier
            .fillMaxSize()
            .background(Void),
        contentAlignment = Alignment.Center
    ) {
        LoadingIndicator(message = message)
    }
}

/**
 * Error state with retry option
 */
@Composable
fun ErrorState(
    modifier: Modifier = Modifier,
    message: String = stringResource(R.string.error_generic),
    icon: ImageVector = Icons.Default.ErrorOutline,
    onRetry: (() -> Unit)? = null
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .padding(32.dp)
            .semantics {
                contentDescription = "Error: $message"
            },
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        // Error icon
        Box(
            modifier = Modifier
                .size(64.dp)
                .clip(CircleShape)
                .background(SafetyViolation.copy(alpha = 0.1f)),
            contentAlignment = Alignment.Center
        ) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                tint = SafetyViolation,
                modifier = Modifier.size(32.dp)
            )
        }

        Spacer(modifier = Modifier.height(16.dp))

        Text(
            text = stringResource(R.string.common_error),
            style = MaterialTheme.typography.titleMedium,
            color = Color.White
        )

        Spacer(modifier = Modifier.height(8.dp))

        Text(
            text = message,
            style = MaterialTheme.typography.bodyMedium,
            color = Color.White.copy(alpha = 0.7f),
            textAlign = TextAlign.Center
        )

        if (onRetry != null) {
            Spacer(modifier = Modifier.height(24.dp))

            Button(
                onClick = onRetry,
                modifier = Modifier
                    .defaultMinSize(minHeight = MinTouchTargetSize)
                    .semantics {
                        role = Role.Button
                        contentDescription = "Retry"
                    },
                colors = ButtonDefaults.buttonColors(
                    containerColor = SafetyViolation.copy(alpha = 0.2f),
                    contentColor = SafetyViolation
                )
            ) {
                Icon(
                    imageVector = Icons.Default.Refresh,
                    contentDescription = null,
                    modifier = Modifier.size(18.dp)
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(stringResource(R.string.common_retry))
            }
        }
    }
}

/**
 * Full screen error state
 */
@Composable
fun ErrorScreen(
    modifier: Modifier = Modifier,
    message: String = stringResource(R.string.error_generic),
    onRetry: (() -> Unit)? = null
) {
    Box(
        modifier = modifier
            .fillMaxSize()
            .background(Void),
        contentAlignment = Alignment.Center
    ) {
        ErrorState(message = message, onRetry = onRetry)
    }
}

/**
 * Empty state with optional action
 */
@Composable
fun EmptyState(
    modifier: Modifier = Modifier,
    title: String,
    message: String,
    icon: ImageVector = Icons.Default.Inbox,
    actionLabel: String? = null,
    onAction: (() -> Unit)? = null
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .padding(32.dp)
            .semantics {
                contentDescription = "$title. $message"
            },
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        // Icon
        Box(
            modifier = Modifier
                .size(80.dp)
                .clip(CircleShape)
                .background(VoidLight),
            contentAlignment = Alignment.Center
        ) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                tint = Color.White.copy(alpha = 0.4f),
                modifier = Modifier.size(40.dp)
            )
        }

        Spacer(modifier = Modifier.height(20.dp))

        Text(
            text = title,
            style = MaterialTheme.typography.titleMedium,
            color = Color.White
        )

        Spacer(modifier = Modifier.height(8.dp))

        Text(
            text = message,
            style = MaterialTheme.typography.bodyMedium,
            color = Color.White.copy(alpha = 0.6f),
            textAlign = TextAlign.Center
        )

        if (actionLabel != null && onAction != null) {
            Spacer(modifier = Modifier.height(24.dp))

            OutlinedButton(
                onClick = onAction,
                modifier = Modifier
                    .defaultMinSize(minHeight = MinTouchTargetSize)
                    .semantics {
                        role = Role.Button
                        contentDescription = actionLabel
                    },
                colors = ButtonDefaults.outlinedButtonColors(
                    contentColor = Crystal
                )
            ) {
                Text(actionLabel)
            }
        }
    }
}

/**
 * Connection status indicator
 */
@Composable
fun ConnectionStatus(
    isConnected: Boolean,
    modifier: Modifier = Modifier,
    showLabel: Boolean = true
) {
    val statusColor = if (isConnected) SafetyOk else SafetyViolation
    val statusText = if (isConnected) {
        stringResource(R.string.a11y_connection_connected)
    } else {
        stringResource(R.string.a11y_connection_disconnected)
    }

    Row(
        modifier = modifier.semantics {
            contentDescription = statusText
        },
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(6.dp)
    ) {
        Box(
            modifier = Modifier
                .size(8.dp)
                .clip(CircleShape)
                .background(statusColor)
        )

        if (showLabel) {
            Text(
                text = if (isConnected) "Connected" else "Offline",
                style = MaterialTheme.typography.labelSmall,
                color = statusColor.copy(alpha = 0.8f)
            )
        }
    }
}

/**
 * Inline loading indicator (for buttons, etc.)
 */
@Composable
fun InlineLoadingIndicator(
    modifier: Modifier = Modifier,
    color: Color = Crystal,
    size: Int = 16
) {
    val accessibilityConfig = LocalAccessibilityConfig.current
    val infiniteTransition = rememberInfiniteTransition(label = "inline_loading")

    val rotation by infiniteTransition.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec = infiniteRepeatable(
            animation = tween(
                durationMillis = if (accessibilityConfig.isReducedMotionEnabled) 0 else 1000,
                easing = LinearEasing
            )
        ),
        label = "rotation"
    )

    CircularProgressIndicator(
        modifier = modifier
            .size(size.dp)
            .semantics { contentDescription = "Loading" },
        color = color,
        strokeWidth = 2.dp
    )
}

/**
 * State container that handles loading, error, and success states
 */
@Composable
fun <T> StateContainer(
    state: UIState<T>,
    modifier: Modifier = Modifier,
    loadingMessage: String = stringResource(R.string.common_loading),
    emptyTitle: String = "No Data",
    emptyMessage: String = "Nothing to display",
    onRetry: (() -> Unit)? = null,
    content: @Composable (T) -> Unit
) {
    when (state) {
        is UIState.Loading -> {
            LoadingScreen(modifier = modifier, message = loadingMessage)
        }
        is UIState.Error -> {
            ErrorScreen(
                modifier = modifier,
                message = state.message,
                onRetry = if (state.retryable) onRetry else null
            )
        }
        is UIState.Empty -> {
            Box(
                modifier = modifier.fillMaxSize(),
                contentAlignment = Alignment.Center
            ) {
                EmptyState(
                    title = emptyTitle,
                    message = emptyMessage
                )
            }
        }
        is UIState.Success -> {
            content(state.data)
        }
    }
}

/**
 * Shimmer effect for loading placeholders
 */
@Composable
fun ShimmerPlaceholder(
    modifier: Modifier = Modifier
) {
    val accessibilityConfig = LocalAccessibilityConfig.current
    val infiniteTransition = rememberInfiniteTransition(label = "shimmer")

    val alpha by infiniteTransition.animateFloat(
        initialValue = 0.3f,
        targetValue = 0.7f,
        animationSpec = infiniteRepeatable(
            animation = tween(
                durationMillis = if (accessibilityConfig.isReducedMotionEnabled) 0 else 1000,
                easing = EaseInOutSine
            ),
            repeatMode = RepeatMode.Reverse
        ),
        label = "shimmer_alpha"
    )

    Box(
        modifier = modifier
            .clip(RoundedCornerShape(8.dp))
            .background(VoidLight.copy(alpha = alpha))
    )
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
