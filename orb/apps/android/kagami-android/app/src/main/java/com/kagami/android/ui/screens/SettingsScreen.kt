/**
 * Kagami Settings Screen - App Configuration
 *
 * Colony: Crystal (e7) - Verification & Polish
 *
 * Provides user settings including:
 * - Connection status and diagnostics
 * - Server configuration
 * - Notification preferences
 * - Accessibility options
 * - Font size settings
 * - Logout functionality
 *
 * Accessibility (Phase 2):
 * - TalkBack content descriptions for all interactive elements
 * - Minimum 48dp touch targets
 * - Reduced motion support
 * - Font scaling support (200%)
 * - RTL layout support
 */

package com.kagami.android.ui.screens

import android.view.HapticFeedbackConstants
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import com.kagami.android.ui.MinTouchTargetSize
import com.kagami.android.ui.minTouchTarget
import com.kagami.android.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    onBack: () -> Unit,
    onLogout: () -> Unit,
    viewModel: SettingsViewModel = hiltViewModel()
) {
    val view = LocalView.current
    val layoutDirection = LocalLayoutDirection.current
    val isConnected by viewModel.isConnected.collectAsState()
    val latencyMs by viewModel.latencyMs.collectAsState()

    var showLogoutDialog by remember { mutableStateOf(false) }
    var notificationsEnabled by remember { mutableStateOf(true) }
    var hapticFeedbackEnabled by remember { mutableStateOf(true) }
    var reducedMotionEnabled by remember { mutableStateOf(false) }
    var highContrastEnabled by remember { mutableStateOf(false) }
    var fontSizeMultiplier by remember { mutableStateOf(1.0f) }

    // Track screen view on first composition
    LaunchedEffect(Unit) {
        viewModel.trackScreenView()
    }

    // Logout confirmation dialog
    if (showLogoutDialog) {
        AlertDialog(
            onDismissRequest = { showLogoutDialog = false },
            icon = { Icon(Icons.Default.Logout, contentDescription = null) },
            title = { Text("Log Out?") },
            text = { Text("Are you sure you want to log out? You'll need to sign in again to control your home.") },
            confirmButton = {
                TextButton(
                    onClick = {
                        viewModel.trackLogout()
                        showLogoutDialog = false
                        onLogout()
                    }
                ) {
                    Text("Log Out", color = Spark)
                }
            },
            dismissButton = {
                TextButton(onClick = { showLogoutDialog = false }) {
                    Text("Cancel")
                }
            }
        )
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        "Settings",
                        modifier = Modifier.semantics { heading() }
                    )
                },
                navigationIcon = {
                    IconButton(
                        onClick = {
                            view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                            onBack()
                        },
                        modifier = Modifier
                            .minTouchTarget()
                            .semantics {
                                contentDescription = "Go back"
                                role = Role.Button
                            }
                    ) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = null)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = Void)
            )
        },
        containerColor = Void
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
            contentPadding = PaddingValues(vertical = 16.dp)
        ) {
            // Connection Status Section
            item {
                SettingsSection(title = "Connection") {
                    ConnectionStatusCard(
                        isConnected = isConnected,
                        latencyMs = latencyMs
                    )
                }
            }

            // Notifications Section
            item {
                SettingsSection(title = "Notifications", icon = Icons.Default.Notifications) {
                    SettingsToggleItem(
                        icon = Icons.Default.NotificationsActive,
                        title = "Push Notifications",
                        subtitle = "Get alerts when things happen at home",
                        checked = notificationsEnabled,
                        onCheckedChange = {
                            if (hapticFeedbackEnabled) {
                                view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                            }
                            notificationsEnabled = it
                        }
                    )
                }
            }

            // Accessibility Section
            item {
                SettingsSection(title = "Accessibility", icon = Icons.Default.Accessibility) {
                    Column(verticalArrangement = Arrangement.spacedBy(0.dp)) {
                        SettingsToggleItem(
                            icon = Icons.Default.Vibration,
                            title = "Haptic Feedback",
                            subtitle = "Feel every tap",
                            checked = hapticFeedbackEnabled,
                            onCheckedChange = {
                                if (hapticFeedbackEnabled) {
                                    view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                                }
                                hapticFeedbackEnabled = it
                            }
                        )
                        HorizontalDivider(
                            color = Color.White.copy(alpha = 0.08f),
                            modifier = Modifier.padding(start = 56.dp)
                        )
                        SettingsToggleItem(
                            icon = Icons.Default.SlowMotionVideo,
                            title = "Reduced Motion",
                            subtitle = "Simpler, calmer animations",
                            checked = reducedMotionEnabled,
                            onCheckedChange = {
                                if (hapticFeedbackEnabled) {
                                    view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                                }
                                reducedMotionEnabled = it
                            }
                        )
                        HorizontalDivider(
                            color = Color.White.copy(alpha = 0.08f),
                            modifier = Modifier.padding(start = 56.dp)
                        )
                        SettingsToggleItem(
                            icon = Icons.Default.Contrast,
                            title = "High Contrast",
                            subtitle = "Bolder colors for clarity",
                            checked = highContrastEnabled,
                            onCheckedChange = {
                                if (hapticFeedbackEnabled) {
                                    view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                                }
                                highContrastEnabled = it
                            }
                        )
                    }
                }
            }

            // Display Section (Font Size)
            item {
                SettingsSection(title = "Display", icon = Icons.Default.TextFields) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(16.dp)
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                "Text Size",
                                style = MaterialTheme.typography.bodyLarge,
                                color = Color.White
                            )
                            Text(
                                "${(fontSizeMultiplier * 100).toInt()}%",
                                style = MaterialTheme.typography.bodyMedium,
                                color = Crystal
                            )
                        }
                        Spacer(modifier = Modifier.height(12.dp))
                        // Preview text
                        Text(
                            "Preview: The quick brown fox",
                            style = MaterialTheme.typography.bodyMedium.copy(
                                fontSize = MaterialTheme.typography.bodyMedium.fontSize * fontSizeMultiplier
                            ),
                            color = Color.White.copy(alpha = 0.7f)
                        )
                        Spacer(modifier = Modifier.height(16.dp))
                        Slider(
                            value = fontSizeMultiplier,
                            onValueChange = {
                                if (hapticFeedbackEnabled) {
                                    view.performHapticFeedback(HapticFeedbackConstants.CLOCK_TICK)
                                }
                                fontSizeMultiplier = it
                            },
                            valueRange = 0.8f..1.5f,
                            steps = 6,
                            colors = SliderDefaults.colors(
                                thumbColor = Crystal,
                                activeTrackColor = Crystal,
                                inactiveTrackColor = Color.White.copy(alpha = 0.2f)
                            ),
                            modifier = Modifier.semantics {
                                contentDescription = "Text size: ${(fontSizeMultiplier * 100).toInt()} percent"
                            }
                        )
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text("A", style = MaterialTheme.typography.bodySmall, color = Color.White.copy(alpha = 0.5f))
                            Text("A", style = MaterialTheme.typography.titleLarge, color = Color.White.copy(alpha = 0.5f))
                        }
                    }
                }
            }

            // About Section
            item {
                SettingsSection(title = "About", icon = Icons.Default.Info) {
                    Column(verticalArrangement = Arrangement.spacedBy(0.dp)) {
                        SettingsNavigationItem(
                            icon = Icons.Default.NewReleases,
                            title = "Version",
                            subtitle = "1.0.0 (build 1)",
                            showChevron = false,
                            onClick = { }
                        )
                        HorizontalDivider(
                            color = Color.White.copy(alpha = 0.08f),
                            modifier = Modifier.padding(start = 56.dp)
                        )
                        SettingsNavigationItem(
                            icon = Icons.Default.Security,
                            title = "Privacy Policy",
                            subtitle = "Your data stays yours",
                            onClick = {
                                if (hapticFeedbackEnabled) {
                                    view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                                }
                                // TODO: Open privacy policy
                            }
                        )
                        HorizontalDivider(
                            color = Color.White.copy(alpha = 0.08f),
                            modifier = Modifier.padding(start = 56.dp)
                        )
                        SettingsNavigationItem(
                            icon = Icons.Default.Gavel,
                            title = "Terms of Service",
                            subtitle = "The fine print",
                            onClick = {
                                if (hapticFeedbackEnabled) {
                                    view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                                }
                                // TODO: Open terms of service
                            }
                        )
                    }
                }
            }

            // Logout Section
            item {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable {
                            if (hapticFeedbackEnabled) {
                                view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                            }
                            showLogoutDialog = true
                        }
                        .semantics {
                            contentDescription = "Log out of Kagami"
                            role = Role.Button
                        },
                    shape = RoundedCornerShape(16.dp),
                    colors = CardDefaults.cardColors(containerColor = Spark.copy(alpha = 0.1f))
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(16.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.Center
                    ) {
                        Icon(
                            imageVector = Icons.Default.Logout,
                            contentDescription = null,
                            tint = Spark
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            "Log Out",
                            style = MaterialTheme.typography.titleMedium,
                            color = Spark
                        )
                    }
                }
            }

            // Footer with safety badge
            item {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 24.dp),
                    horizontalArrangement = Arrangement.Center,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(
                        imageVector = Icons.Default.VerifiedUser,
                        contentDescription = null,
                        tint = Grove.copy(alpha = 0.5f),
                        modifier = Modifier.size(16.dp)
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        "Protected",
                        style = MaterialTheme.typography.bodySmall,
                        color = Grove.copy(alpha = 0.6f)
                    )
                }
            }
        }
    }
}

@Composable
fun SettingsSection(
    title: String,
    icon: ImageVector? = null,
    content: @Composable () -> Unit
) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(6.dp),
            modifier = Modifier
                .padding(start = 4.dp)
                .semantics { heading() }
        ) {
            if (icon != null) {
                Icon(
                    imageVector = icon,
                    contentDescription = null,
                    tint = Color.White.copy(alpha = 0.4f),
                    modifier = Modifier.size(14.dp)
                )
            }
            Text(
                title.uppercase(),
                style = MaterialTheme.typography.labelSmall,
                color = Color.White.copy(alpha = 0.5f),
                letterSpacing = 0.5.sp
            )
        }
        Card(
            shape = RoundedCornerShape(16.dp),
            colors = CardDefaults.cardColors(containerColor = VoidLight)
        ) {
            content()
        }
    }
}

@Composable
fun ConnectionStatusCard(
    isConnected: Boolean,
    latencyMs: Int
) {
    val statusColor = if (isConnected) Grove else Spark
    val statusText = if (isConnected) "Connected" else "Disconnected"
    val latencyColor = when {
        latencyMs < 100 -> Grove
        latencyMs < 300 -> Beacon
        else -> Spark
    }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(16.dp)
            .semantics(mergeDescendants = true) {
                contentDescription = "Connection status: $statusText. Latency: $latencyMs milliseconds"
            },
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            modifier = Modifier.clearAndSetSemantics { }
        ) {
            // Pulsing status indicator
            Box(
                modifier = Modifier
                    .size(12.dp)
                    .clip(CircleShape)
                    .background(statusColor)
            )
            Column {
                Text(
                    statusText,
                    style = MaterialTheme.typography.titleMedium,
                    color = Color.White
                )
                Text(
                    "Home Hub",  // Simplified from "kagami.local"
                    style = MaterialTheme.typography.bodySmall,
                    color = Color.White.copy(alpha = 0.6f)
                )
            }
        }

        // Latency badge
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(4.dp),
            modifier = Modifier
                .background(latencyColor.copy(alpha = 0.15f), RoundedCornerShape(8.dp))
                .padding(horizontal = 10.dp, vertical = 6.dp)
                .clearAndSetSemantics { }
        ) {
            Icon(
                imageVector = Icons.Default.Speed,
                contentDescription = null,
                tint = latencyColor,
                modifier = Modifier.size(14.dp)
            )
            Text(
                "${latencyMs}ms",
                style = MaterialTheme.typography.labelMedium,
                color = latencyColor
            )
        }
    }
}

@Composable
fun SettingsToggleItem(
    icon: ImageVector,
    title: String,
    subtitle: String,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .defaultMinSize(minHeight = MinTouchTargetSize)
            .clickable { onCheckedChange(!checked) }
            .padding(horizontal = 16.dp, vertical = 12.dp)
            .semantics(mergeDescendants = true) {
                contentDescription = "$title: $subtitle. Currently ${if (checked) "enabled" else "disabled"}"
                role = Role.Switch
            },
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            tint = Color.White.copy(alpha = 0.7f),
            modifier = Modifier.size(24.dp)
        )
        Spacer(modifier = Modifier.width(16.dp))
        Column(
            modifier = Modifier
                .weight(1f)
                .clearAndSetSemantics { }
        ) {
            Text(
                title,
                style = MaterialTheme.typography.bodyLarge,
                color = Color.White
            )
            Text(
                subtitle,
                style = MaterialTheme.typography.bodySmall,
                color = Color.White.copy(alpha = 0.6f)
            )
        }
        Switch(
            checked = checked,
            onCheckedChange = null, // Handled by row click
            colors = SwitchDefaults.colors(
                checkedThumbColor = Color.White,
                checkedTrackColor = Crystal,
                uncheckedThumbColor = Color.White.copy(alpha = 0.7f),
                uncheckedTrackColor = Color.White.copy(alpha = 0.2f)
            ),
            modifier = Modifier.clearAndSetSemantics { }
        )
    }
}

@Composable
fun SettingsNavigationItem(
    icon: ImageVector,
    title: String,
    subtitle: String,
    showChevron: Boolean = true,
    onClick: () -> Unit
) {
    val layoutDirection = LocalLayoutDirection.current
    var isPressed by remember { mutableStateOf(false) }
    val scale by animateFloatAsState(
        targetValue = if (isPressed) 0.98f else 1f,
        animationSpec = spring(dampingRatio = 0.7f, stiffness = 400f),
        label = "nav_press"
    )

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .defaultMinSize(minHeight = MinTouchTargetSize)
            .graphicsLayer {
                scaleX = scale
                scaleY = scale
            }
            .pointerInput(Unit) {
                detectTapGestures(
                    onPress = {
                        isPressed = true
                        tryAwaitRelease()
                        isPressed = false
                    },
                    onTap = { onClick() }
                )
            }
            .padding(horizontal = 16.dp, vertical = 12.dp)
            .semantics {
                contentDescription = "$title: $subtitle"
                role = Role.Button
            },
        verticalAlignment = Alignment.CenterVertically
    ) {
        // Icon badge
        Box(
            modifier = Modifier
                .size(32.dp)
                .background(Crystal.copy(alpha = 0.1f), RoundedCornerShape(8.dp)),
            contentAlignment = Alignment.Center
        ) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                tint = Crystal,
                modifier = Modifier.size(18.dp)
            )
        }
        Spacer(modifier = Modifier.width(12.dp))
        Column(
            modifier = Modifier
                .weight(1f)
                .clearAndSetSemantics { }
        ) {
            Text(
                title,
                style = MaterialTheme.typography.bodyLarge,
                color = Color.White
            )
            Text(
                subtitle,
                style = MaterialTheme.typography.bodySmall,
                color = Color.White.copy(alpha = 0.6f)
            )
        }
        if (showChevron) {
            Icon(
                imageVector = if (layoutDirection == LayoutDirection.Rtl)
                    Icons.Default.ChevronLeft else Icons.Default.ChevronRight,
                contentDescription = null,
                tint = Color.White.copy(alpha = 0.3f)
            )
        }
    }
}
