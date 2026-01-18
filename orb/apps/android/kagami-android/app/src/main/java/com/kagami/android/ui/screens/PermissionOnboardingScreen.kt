/**
 * PermissionOnboardingScreen — Unified Permission Onboarding
 *
 * Features:
 *   - Explains what Kagami can do with each permission
 *   - Shows privacy implications clearly
 *   - Allows granular opt-in (not all-or-nothing)
 *   - Graceful degradation if denied
 *   - Easy path to re-enable later in Settings
 */

package com.kagami.android.ui.screens

import android.Manifest
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.animateColorAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.kagami.android.services.KagamiAccessibilityService
import kotlinx.coroutines.launch

/**
 * Permission item data class
 */
data class PermissionItem(
    val id: String,
    val name: String,
    val description: String,
    val icon: ImageVector,
    val color: Color,
    val isEnabled: Boolean = true,
    val isGranted: Boolean = false,
    val requiresSettings: Boolean = false
)

/**
 * Unified permission onboarding screen
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PermissionOnboardingScreen(
    onComplete: () -> Unit,
    onSkip: () -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    // Permission state
    var permissions by remember { mutableStateOf(getInitialPermissions()) }
    var isRequesting by remember { mutableStateOf(false) }

    // Permission launchers
    val notificationLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        permissions = permissions.map {
            if (it.id == "notifications") it.copy(isGranted = granted) else it
        }
    }

    val healthConnectLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { results ->
        val allGranted = results.values.all { it }
        permissions = permissions.map {
            if (it.id == "health") it.copy(isGranted = allGranted) else it
        }
    }

    Scaffold(
        containerColor = Color(0xFF07060B)
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // Header
            item {
                HeaderSection()
            }

            // Permission cards
            items(permissions) { permission ->
                PermissionCard(
                    permission = permission,
                    onToggle = {
                        permissions = permissions.map {
                            if (it.id == permission.id) it.copy(isEnabled = !it.isEnabled) else it
                        }
                    },
                    onOpenSettings = {
                        openPermissionSettings(context, permission)
                    }
                )
            }

            // Continue button
            item {
                Spacer(modifier = Modifier.height(8.dp))

                Button(
                    onClick = {
                        scope.launch {
                            isRequesting = true
                            requestEnabledPermissions(
                                context,
                                permissions,
                                notificationLauncher,
                                healthConnectLauncher
                            )
                            isRequesting = false
                            context.getSharedPreferences("kagami", Context.MODE_PRIVATE)
                                .edit()
                                .putBoolean("permission_onboarding_completed", true)
                                .apply()
                            onComplete()
                        }
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(56.dp),
                    enabled = !isRequesting,
                    colors = ButtonDefaults.buttonColors(
                        containerColor = Color.Transparent
                    ),
                    contentPadding = PaddingValues(0.dp)
                ) {
                    Box(
                        modifier = Modifier
                            .fillMaxSize()
                            .background(
                                brush = Brush.horizontalGradient(
                                    colors = listOf(
                                        Color(0xFF9B7EBD),
                                        Color(0xFF67D4E4)
                                    )
                                ),
                                shape = RoundedCornerShape(12.dp)
                            ),
                        contentAlignment = Alignment.Center
                    ) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.Center
                        ) {
                            Text(
                                text = "Continue",
                                fontWeight = FontWeight.SemiBold,
                                color = Color.White
                            )
                            if (isRequesting) {
                                Spacer(modifier = Modifier.width(8.dp))
                                CircularProgressIndicator(
                                    modifier = Modifier.size(20.dp),
                                    color = Color.White,
                                    strokeWidth = 2.dp
                                )
                            }
                        }
                    }
                }
            }

            // Skip button
            item {
                TextButton(onClick = onSkip) {
                    Text(
                        text = "Skip for now",
                        color = Color.Gray
                    )
                }
            }
        }
    }
}

@Composable
private fun HeaderSection() {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = Modifier.padding(vertical = 24.dp)
    ) {
        // Logo
        Box(
            modifier = Modifier
                .size(80.dp)
                .clip(CircleShape)
                .background(
                    brush = Brush.linearGradient(
                        colors = listOf(
                            Color(0xFF9B7EBD).copy(alpha = 0.3f),
                            Color(0xFF67D4E4).copy(alpha = 0.3f)
                        )
                    )
                ),
            contentAlignment = Alignment.Center
        ) {
            Icon(
                imageVector = Icons.Filled.Hexagon,
                contentDescription = "Kagami",
                modifier = Modifier.size(48.dp),
                tint = Color(0xFF9B7EBD)
            )
        }

        Spacer(modifier = Modifier.height(16.dp))

        Text(
            text = "鏡 Kagami",
            fontSize = 28.sp,
            fontWeight = FontWeight.Bold,
            color = Color.White
        )

        Spacer(modifier = Modifier.height(8.dp))

        Text(
            text = "To give you the best experience, Kagami needs a few permissions. You can enable or disable these at any time.",
            fontSize = 14.sp,
            color = Color.Gray,
            textAlign = TextAlign.Center,
            modifier = Modifier.padding(horizontal = 16.dp)
        )
    }
}

@Composable
private fun PermissionCard(
    permission: PermissionItem,
    onToggle: () -> Unit,
    onOpenSettings: () -> Unit
) {
    val borderColor by animateColorAsState(
        targetValue = if (permission.isEnabled) permission.color.copy(alpha = 0.5f) else Color.Transparent,
        label = "border"
    )

    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .border(
                width = 1.dp,
                color = borderColor,
                shape = RoundedCornerShape(12.dp)
            ),
        shape = RoundedCornerShape(12.dp),
        color = Color.White.copy(alpha = 0.05f)
    ) {
        Row(
            modifier = Modifier.padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            // Icon
            Box(
                modifier = Modifier
                    .size(48.dp)
                    .clip(CircleShape)
                    .background(permission.color.copy(alpha = 0.15f)),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = permission.icon,
                    contentDescription = permission.name,
                    tint = permission.color,
                    modifier = Modifier.size(24.dp)
                )
            }

            Spacer(modifier = Modifier.width(16.dp))

            // Info
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = permission.name,
                    fontWeight = FontWeight.SemiBold,
                    color = Color.White
                )
                Text(
                    text = permission.description,
                    fontSize = 12.sp,
                    color = Color.Gray,
                    maxLines = 2
                )
            }

            Spacer(modifier = Modifier.width(8.dp))

            // Toggle or Settings button
            if (permission.requiresSettings) {
                IconButton(onClick = onOpenSettings) {
                    Icon(
                        imageVector = Icons.Filled.Settings,
                        contentDescription = "Open Settings",
                        tint = permission.color
                    )
                }
            } else {
                Switch(
                    checked = permission.isEnabled,
                    onCheckedChange = { onToggle() },
                    colors = SwitchDefaults.colors(
                        checkedThumbColor = permission.color,
                        checkedTrackColor = permission.color.copy(alpha = 0.5f)
                    )
                )
            }
        }
    }
}

private fun getInitialPermissions(): List<PermissionItem> {
    return listOf(
        PermissionItem(
            id = "health",
            name = "Health Connect",
            description = "Monitor heart rate, sleep, and activity to optimize your environment.",
            icon = Icons.Filled.Favorite,
            color = Color(0xFFFF6B6B),
            isEnabled = true
        ),
        PermissionItem(
            id = "notifications",
            name = "Notifications",
            description = "Receive alerts about your home, security events, and reminders.",
            icon = Icons.Filled.Notifications,
            color = Color(0xFFFFD93D),
            isEnabled = true
        ),
        PermissionItem(
            id = "accessibility",
            name = "Accessibility",
            description = "Enable full device control for automation (tap to configure).",
            icon = Icons.Filled.Accessibility,
            color = Color(0xFF9B7EBD),
            isEnabled = true,
            requiresSettings = true
        ),
        PermissionItem(
            id = "overlay",
            name = "Display Over Apps",
            description = "Show floating controls for quick access (tap to configure).",
            icon = Icons.Filled.Layers,
            color = Color(0xFF67D4E4),
            isEnabled = false,
            requiresSettings = true
        ),
        PermissionItem(
            id = "location",
            name = "Location",
            description = "Enable geofencing for automatic 'Welcome Home' scenes.",
            icon = Icons.Filled.LocationOn,
            color = Color(0xFF00FF88),
            isEnabled = false
        )
    )
}

private fun openPermissionSettings(context: Context, permission: PermissionItem) {
    when (permission.id) {
        "accessibility" -> {
            context.startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
        }
        "overlay" -> {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                context.startActivity(
                    Intent(
                        Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                        Uri.parse("package:${context.packageName}")
                    )
                )
            }
        }
        else -> {
            context.startActivity(
                Intent(
                    Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                    Uri.parse("package:${context.packageName}")
                )
            )
        }
    }
}

private suspend fun requestEnabledPermissions(
    context: Context,
    permissions: List<PermissionItem>,
    notificationLauncher: androidx.activity.result.ActivityResultLauncher<String>,
    healthConnectLauncher: androidx.activity.result.ActivityResultLauncher<Array<String>>
) {
    for (permission in permissions.filter { it.isEnabled && !it.requiresSettings }) {
        when (permission.id) {
            "notifications" -> {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                    notificationLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
                }
            }
            "health" -> {
                // Health Connect uses its own permission flow
                // Would launch Health Connect permission request
            }
            "location" -> {
                // Location permissions would be requested separately
            }
        }
    }
}

@Preview(showBackground = true)
@Composable
private fun PermissionOnboardingPreview() {
    PermissionOnboardingScreen(
        onComplete = {},
        onSkip = {}
    )
}

/*
 * 鏡
 * h(x) ≥ 0. Always.
 *
 * Permission is trust.
 * Explain clearly. Respect choices.
 * The user is always in control.
 */
