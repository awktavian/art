package com.kagami.xr.ui.spatial

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Lightbulb
import androidx.compose.material.icons.filled.Security
import androidx.compose.material.icons.filled.Thermostat
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.kagami.xr.services.HandTrackingService
import com.kagami.xr.services.ThermalManager
import com.kagami.xr.ui.theme.SpatialColors

/**
 * Spatial Home Screen for Kagami XR
 *
 * The main spatial interface for smart home control on AndroidXR.
 * In full implementation, this would be wrapped in Jetpack Compose for XR
 * Subspace and SpatialPanel composables.
 *
 * Colony: Nexus (e4) - Integration
 *
 * Layout Zones (Proxemic Design):
 *   - Header: Status indicators (fatigue, thermal, connection)
 *   - Primary: Room selection grid at personal distance (0.8m)
 *   - Secondary: Device controls floating at arm's reach
 *   - Ambient: Kagami presence orb in peripheral vision
 *
 * h(x) >= 0. Always.
 */
@Composable
fun SpatialHomeScreen(
    isXRActive: Boolean,
    handTrackingService: HandTrackingService,
    thermalManager: ThermalManager,
    modifier: Modifier = Modifier
) {
    val gesture by handTrackingService.currentGesture.collectAsState()
    val isTracking by handTrackingService.isTracking.collectAsState()
    val fatigueWarning by handTrackingService.fatigueWarningActive.collectAsState()
    val qualityProfile by thermalManager.currentProfile.collectAsState()

    Surface(
        modifier = modifier.fillMaxSize(),
        color = SpatialColors.background
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(24.dp)
        ) {
            // Status Header
            StatusHeader(
                isXRActive = isXRActive,
                isHandTracking = isTracking,
                fatigueWarning = fatigueWarning,
                qualityProfile = qualityProfile,
                currentGesture = gesture
            )

            Spacer(modifier = Modifier.height(32.dp))

            // Main Content
            Text(
                text = "Kagami XR",
                style = MaterialTheme.typography.headlineLarge,
                fontWeight = FontWeight.Light,
                color = SpatialColors.textPrimary
            )

            Text(
                text = "Spatial Smart Home Control",
                style = MaterialTheme.typography.bodyLarge,
                color = SpatialColors.textSecondary
            )

            Spacer(modifier = Modifier.height(32.dp))

            // Quick Actions Grid
            QuickActionsGrid()

            Spacer(modifier = Modifier.weight(1f))

            // Gesture Indicator
            if (isTracking) {
                GestureIndicator(gesture = gesture)
            }
        }
    }
}

@Composable
private fun StatusHeader(
    isXRActive: Boolean,
    isHandTracking: Boolean,
    fatigueWarning: Boolean,
    qualityProfile: ThermalManager.QualityProfile,
    currentGesture: HandTrackingService.Gesture
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        // Connection Status
        Row(verticalAlignment = Alignment.CenterVertically) {
            StatusDot(
                isActive = isXRActive,
                activeColor = SpatialColors.grove,
                label = "XR"
            )
            Spacer(modifier = Modifier.width(16.dp))
            StatusDot(
                isActive = isHandTracking,
                activeColor = SpatialColors.nexus,
                label = "Hands"
            )
        }

        // Warnings
        Row(verticalAlignment = Alignment.CenterVertically) {
            if (fatigueWarning) {
                WarningChip(
                    icon = Icons.Default.Warning,
                    text = "Fatigue",
                    color = SpatialColors.beacon
                )
                Spacer(modifier = Modifier.width(8.dp))
            }

            // Quality Profile Indicator
            QualityChip(profile = qualityProfile)
        }
    }
}

@Composable
private fun StatusDot(
    isActive: Boolean,
    activeColor: Color,
    label: String
) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Box(
            modifier = Modifier
                .size(8.dp)
                .clip(CircleShape)
                .background(if (isActive) activeColor else SpatialColors.textDisabled)
        )
        Spacer(modifier = Modifier.width(4.dp))
        Text(
            text = label,
            style = MaterialTheme.typography.labelSmall,
            color = SpatialColors.textSecondary
        )
    }
}

@Composable
private fun WarningChip(
    icon: ImageVector,
    text: String,
    color: Color
) {
    Surface(
        color = color.copy(alpha = 0.2f),
        shape = RoundedCornerShape(16.dp)
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 4.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                tint = color,
                modifier = Modifier.size(16.dp)
            )
            Spacer(modifier = Modifier.width(4.dp))
            Text(
                text = text,
                style = MaterialTheme.typography.labelSmall,
                color = color
            )
        }
    }
}

@Composable
private fun QualityChip(profile: ThermalManager.QualityProfile) {
    val (color, label) = when (profile) {
        ThermalManager.QualityProfile.ULTRA -> SpatialColors.grove to "Ultra"
        ThermalManager.QualityProfile.HIGH -> SpatialColors.nexus to "High"
        ThermalManager.QualityProfile.MEDIUM -> SpatialColors.beacon to "Medium"
        ThermalManager.QualityProfile.LOW -> SpatialColors.flow to "Low"
        ThermalManager.QualityProfile.MINIMAL -> SpatialColors.error to "Minimal"
    }

    Surface(
        color = color.copy(alpha = 0.2f),
        shape = RoundedCornerShape(16.dp)
    ) {
        Text(
            text = "${profile.targetFps}fps",
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 4.dp),
            style = MaterialTheme.typography.labelSmall,
            color = color
        )
    }
}

@Composable
private fun QuickActionsGrid() {
    Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            QuickActionCard(
                icon = Icons.Default.Home,
                title = "Rooms",
                subtitle = "26 rooms",
                color = SpatialColors.nexus,
                modifier = Modifier.weight(1f)
            )
            QuickActionCard(
                icon = Icons.Default.Lightbulb,
                title = "Lights",
                subtitle = "41 lights",
                color = SpatialColors.beacon,
                modifier = Modifier.weight(1f)
            )
        }
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            QuickActionCard(
                icon = Icons.Default.Security,
                title = "Security",
                subtitle = "All secure",
                color = SpatialColors.grove,
                modifier = Modifier.weight(1f)
            )
            QuickActionCard(
                icon = Icons.Default.Thermostat,
                title = "Climate",
                subtitle = "72F",
                color = SpatialColors.flow,
                modifier = Modifier.weight(1f)
            )
        }
    }
}

@Composable
private fun QuickActionCard(
    icon: ImageVector,
    title: String,
    subtitle: String,
    color: Color,
    modifier: Modifier = Modifier
) {
    Card(
        modifier = modifier,
        colors = CardDefaults.cardColors(
            containerColor = SpatialColors.surface
        ),
        shape = RoundedCornerShape(16.dp)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(20.dp)
        ) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                tint = color,
                modifier = Modifier.size(32.dp)
            )
            Spacer(modifier = Modifier.height(12.dp))
            Text(
                text = title,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                color = SpatialColors.textPrimary
            )
            Text(
                text = subtitle,
                style = MaterialTheme.typography.bodySmall,
                color = SpatialColors.textSecondary
            )
        }
    }
}

@Composable
private fun GestureIndicator(gesture: HandTrackingService.Gesture) {
    if (gesture != HandTrackingService.Gesture.NONE) {
        Surface(
            modifier = Modifier.fillMaxWidth(),
            color = SpatialColors.surface,
            shape = RoundedCornerShape(12.dp)
        ) {
            Row(
                modifier = Modifier.padding(16.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.Center
            ) {
                Text(
                    text = "Gesture: ",
                    style = MaterialTheme.typography.bodyMedium,
                    color = SpatialColors.textSecondary
                )
                Text(
                    text = gesture.name.lowercase().replace("_", " "),
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = SpatialColors.nexus
                )
            }
        }
    }
}

/*
 * 鏡
 * h(x) >= 0. Always.
 *
 * The home floats before you.
 * Space becomes interface.
 * Gesture becomes intention.
 */
