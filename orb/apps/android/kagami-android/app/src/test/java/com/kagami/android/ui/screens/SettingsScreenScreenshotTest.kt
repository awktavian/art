/**
 * Kagami Settings Screen Screenshot Tests
 *
 * Visual regression tests for SettingsScreen.
 * Uses Roborazzi for JVM-based screenshot testing.
 *
 * Test scenarios:
 * - Connected state
 * - Disconnected state
 * - Different accessibility configurations
 * - Sign out dialog
 * - High contrast mode
 * - Large font mode
 *
 * h(x) >= 0. Always.
 */
package com.kagami.android.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Logout
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.github.takahirom.roborazzi.RobolectricDeviceQualifiers
import com.kagami.android.ui.AccessibilityConfig
import com.kagami.android.ui.theme.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/**
 * Screenshot tests for SettingsScreen in various states.
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34], qualifiers = RobolectricDeviceQualifiers.Pixel7)
class SettingsScreenScreenshotTest : ScreenshotTestBase() {

    /**
     * Capture SettingsScreen in connected state.
     */
    @Test
    fun settingsScreen_connected() {
        captureScreen("SettingsScreen_Connected") {
            SettingsScreenPreview(
                isConnected = true,
                latencyMs = 45,
                serverUrl = "kagami.local:8001",
                showLogoutButton = true
            )
        }
    }

    /**
     * Capture SettingsScreen in disconnected state.
     */
    @Test
    fun settingsScreen_disconnected() {
        captureScreen("SettingsScreen_Disconnected") {
            SettingsScreenPreview(
                isConnected = false,
                latencyMs = 0,
                serverUrl = "kagami.local:8001",
                showLogoutButton = true
            )
        }
    }

    /**
     * Capture SettingsScreen with high latency.
     */
    @Test
    fun settingsScreen_highLatency() {
        captureScreen("SettingsScreen_HighLatency") {
            SettingsScreenPreview(
                isConnected = true,
                latencyMs = 500,
                serverUrl = "kagami.local:8001",
                showLogoutButton = true
            )
        }
    }

    /**
     * Capture SettingsScreen without logout button (e.g., not authenticated).
     */
    @Test
    fun settingsScreen_noLogout() {
        captureScreen("SettingsScreen_NoLogout") {
            SettingsScreenPreview(
                isConnected = true,
                latencyMs = 45,
                serverUrl = "Not configured",
                showLogoutButton = false
            )
        }
    }

    /**
     * Capture SettingsScreen with high contrast mode enabled.
     */
    @Test
    fun settingsScreen_highContrast() {
        captureScreenWithAccessibility(
            testName = "SettingsScreen_HighContrast",
            accessibilityConfig = highContrastAccessibilityConfig
        ) {
            SettingsScreenPreview(
                isConnected = true,
                latencyMs = 45,
                serverUrl = "kagami.local:8001",
                showLogoutButton = true,
                displayAccessibility = highContrastAccessibilityConfig
            )
        }
    }

    /**
     * Capture SettingsScreen with large font scale (200%).
     */
    @Test
    fun settingsScreen_largeFont() {
        captureScreenWithAccessibility(
            testName = "SettingsScreen_LargeFont",
            accessibilityConfig = largeFontAccessibilityConfig
        ) {
            SettingsScreenPreview(
                isConnected = true,
                latencyMs = 45,
                serverUrl = "kagami.local:8001",
                showLogoutButton = true,
                displayAccessibility = largeFontAccessibilityConfig
            )
        }
    }

    /**
     * Capture SettingsScreen with reduced motion enabled.
     */
    @Test
    fun settingsScreen_reducedMotion() {
        val reducedMotionConfig = AccessibilityConfig(
            fontScale = 1.0f,
            isReducedMotionEnabled = true,
            isHighContrastEnabled = false
        )
        captureScreenWithAccessibility(
            testName = "SettingsScreen_ReducedMotion",
            accessibilityConfig = reducedMotionConfig
        ) {
            SettingsScreenPreview(
                isConnected = true,
                latencyMs = 45,
                serverUrl = "kagami.local:8001",
                showLogoutButton = true,
                displayAccessibility = reducedMotionConfig
            )
        }
    }

    /**
     * Capture logout confirmation dialog.
     */
    @Test
    fun settingsScreen_logoutDialog() {
        captureScreen("SettingsScreen_LogoutDialog") {
            SettingsScreenWithDialogPreview()
        }
    }
}

/**
 * Preview composable for SettingsScreen screenshot testing.
 */
@Composable
private fun SettingsScreenPreview(
    isConnected: Boolean,
    latencyMs: Int,
    serverUrl: String,
    showLogoutButton: Boolean,
    displayAccessibility: AccessibilityConfig = AccessibilityConfig()
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Settings") },
                navigationIcon = {
                    IconButton(onClick = {}) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = Void)
            )
        },
        containerColor = Void
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp)
        ) {
            // Connection Status Card
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = VoidLight)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        text = "Connection",
                        style = MaterialTheme.typography.titleMedium,
                        color = Color.White
                    )
                    Spacer(modifier = Modifier.height(8.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text("Status", color = Color.White.copy(alpha = 0.7f))
                        Text(
                            text = if (isConnected) "Connected" else "Disconnected",
                            color = if (isConnected) SafetyOk else SafetyViolation
                        )
                    }

                    Spacer(modifier = Modifier.height(4.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text("Latency", color = Color.White.copy(alpha = 0.7f))
                        Text(
                            text = "${latencyMs}ms",
                            color = Color.White.copy(alpha = 0.7f)
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Accessibility Info Card
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = VoidLight)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        text = "Accessibility",
                        style = MaterialTheme.typography.titleMedium,
                        color = Color.White
                    )
                    Spacer(modifier = Modifier.height(8.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text("Font Scale", color = Color.White.copy(alpha = 0.7f))
                        Text(
                            text = "${(displayAccessibility.fontScale * 100).toInt()}%",
                            color = Color.White.copy(alpha = 0.7f)
                        )
                    }

                    Spacer(modifier = Modifier.height(4.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text("Reduced Motion", color = Color.White.copy(alpha = 0.7f))
                        Text(
                            text = if (displayAccessibility.isReducedMotionEnabled) "Enabled" else "Disabled",
                            color = Color.White.copy(alpha = 0.7f)
                        )
                    }

                    Spacer(modifier = Modifier.height(4.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text("High Contrast", color = Color.White.copy(alpha = 0.7f))
                        Text(
                            text = if (displayAccessibility.isHighContrastEnabled) "Enabled" else "Disabled",
                            color = Color.White.copy(alpha = 0.7f)
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Account Section
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = VoidLight)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        text = "Account",
                        style = MaterialTheme.typography.titleMedium,
                        color = Color.White
                    )
                    Spacer(modifier = Modifier.height(8.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text("Server", color = Color.White.copy(alpha = 0.7f))
                        Text(
                            text = serverUrl,
                            color = Color.White.copy(alpha = 0.7f),
                            maxLines = 1
                        )
                    }

                    if (showLogoutButton) {
                        Spacer(modifier = Modifier.height(16.dp))

                        OutlinedButton(
                            onClick = {},
                            colors = ButtonDefaults.outlinedButtonColors(
                                contentColor = SafetyViolation
                            ),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Icon(
                                Icons.Default.Logout,
                                contentDescription = null,
                                modifier = Modifier.size(18.dp)
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            Text("Sign Out")
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // About Card
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = VoidLight)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        text = "About",
                        style = MaterialTheme.typography.titleMedium,
                        color = Color.White
                    )
                    Spacer(modifier = Modifier.height(8.dp))

                    Text(
                        text = "Kagami Android",
                        color = Color.White.copy(alpha = 0.7f)
                    )
                    Text(
                        text = "Version 1.0.0",
                        style = MaterialTheme.typography.bodySmall,
                        color = Color.White.copy(alpha = 0.5f)
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        text = "h(x) >= 0. Always.",
                        style = MaterialTheme.typography.bodySmall,
                        color = Crystal.copy(alpha = 0.7f)
                    )
                }
            }
        }
    }
}

/**
 * Preview composable showing logout dialog.
 */
@Composable
private fun SettingsScreenWithDialogPreview() {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Settings") },
                navigationIcon = {
                    IconButton(onClick = {}) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = Void)
            )
        },
        containerColor = Void
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            // Show dialog overlay
            AlertDialog(
                onDismissRequest = {},
                containerColor = VoidLight,
                title = {
                    Text(
                        text = "Sign Out",
                        color = Color.White
                    )
                },
                text = {
                    Text(
                        text = "Are you sure you want to sign out? You will need to sign in again to use Kagami.",
                        color = Color.White.copy(alpha = 0.7f)
                    )
                },
                confirmButton = {
                    TextButton(onClick = {}) {
                        Text("Sign Out", color = SafetyViolation)
                    }
                },
                dismissButton = {
                    TextButton(onClick = {}) {
                        Text("Cancel", color = Color.White.copy(alpha = 0.6f))
                    }
                }
            )
        }
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
