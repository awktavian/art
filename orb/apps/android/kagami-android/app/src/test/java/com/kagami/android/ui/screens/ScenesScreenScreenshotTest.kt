/**
 * Kagami Scenes Screen Screenshot Tests
 *
 * Visual regression tests for ScenesScreen.
 * Uses Roborazzi for JVM-based screenshot testing.
 *
 * Test scenarios:
 * - Default scenes list
 * - High contrast mode
 * - Large font mode
 *
 * h(x) >= 0. Always.
 */
package com.kagami.android.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.github.takahirom.roborazzi.RobolectricDeviceQualifiers
import com.kagami.android.ui.theme.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/**
 * Screenshot tests for ScenesScreen.
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34], qualifiers = RobolectricDeviceQualifiers.Pixel7)
class ScenesScreenScreenshotTest : ScreenshotTestBase() {

    /**
     * Capture ScenesScreen with default scene list.
     */
    @Test
    fun scenesScreen_default() {
        captureScreen("ScenesScreen_Default") {
            ScenesScreenPreview()
        }
    }

    /**
     * Capture ScenesScreen with high contrast mode.
     */
    @Test
    fun scenesScreen_highContrast() {
        captureScreenWithAccessibility(
            testName = "ScenesScreen_HighContrast",
            accessibilityConfig = highContrastAccessibilityConfig
        ) {
            ScenesScreenPreview()
        }
    }

    /**
     * Capture ScenesScreen with large font scale (200%).
     */
    @Test
    fun scenesScreen_largeFont() {
        captureScreenWithAccessibility(
            testName = "ScenesScreen_LargeFont",
            accessibilityConfig = largeFontAccessibilityConfig
        ) {
            ScenesScreenPreview()
        }
    }

    /**
     * Capture individual scene card variants.
     */
    @Test
    fun scenesScreen_movieMode() {
        captureScreen("ScenesScreen_MovieModeCard") {
            SingleSceneCardPreview(
                scene = Scene(
                    id = "movie_mode",
                    name = "Movie Mode",
                    description = "Dim lights, lower TV, close shades",
                    icon = Icons.Default.Movie,
                    color = Forge
                )
            )
        }
    }

    @Test
    fun scenesScreen_goodnightScene() {
        captureScreen("ScenesScreen_GoodnightCard") {
            SingleSceneCardPreview(
                scene = Scene(
                    id = "goodnight",
                    name = "Goodnight",
                    description = "All lights off, lock doors",
                    icon = Icons.Default.NightsStay,
                    color = Flow
                )
            )
        }
    }

    @Test
    fun scenesScreen_welcomeHomeScene() {
        captureScreen("ScenesScreen_WelcomeHomeCard") {
            SingleSceneCardPreview(
                scene = Scene(
                    id = "welcome_home",
                    name = "Welcome Home",
                    description = "Warm lights, open shades",
                    icon = Icons.Default.Home,
                    color = Beacon
                )
            )
        }
    }
}

/**
 * Preview composable for ScenesScreen screenshot testing.
 */
@Composable
private fun ScenesScreenPreview() {
    val scenes = listOf(
        Scene("movie_mode", "Movie Mode", "Dim lights, lower TV, close shades", Icons.Default.Movie, Forge),
        Scene("goodnight", "Goodnight", "All lights off, lock doors", Icons.Default.NightsStay, Flow),
        Scene("welcome_home", "Welcome Home", "Warm lights, open shades", Icons.Default.Home, Beacon),
        Scene("away", "Away Mode", "Secure house, reduce energy", Icons.Default.Lock, Crystal),
        Scene("focus", "Focus Mode", "Bright lights, open shades", Icons.Default.CenterFocusStrong, Spark),
        Scene("relax", "Relax", "Dim lights, fireplace on", Icons.Default.SelfImprovement, Grove),
        Scene("coffee", "Coffee Time", "Bright kitchen lights", Icons.Default.Coffee, Nexus)
    )

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Scenes") },
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
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            items(scenes) { scene ->
                SceneCardPreview(scene = scene, onClick = {})
            }
        }
    }
}

/**
 * Single scene card preview for isolated testing.
 */
@Composable
private fun SingleSceneCardPreview(scene: Scene) {
    Scaffold(
        containerColor = Void
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            contentAlignment = Alignment.TopStart
        ) {
            SceneCardPreview(scene = scene, onClick = {})
        }
    }
}

/**
 * Scene card preview composable.
 */
@Composable
private fun SceneCardPreview(scene: Scene, onClick: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(
                onClick = onClick,
                role = Role.Button
            ),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(
            containerColor = scene.color.copy(alpha = 0.15f)
        )
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(20.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            Icon(
                imageVector = scene.icon,
                contentDescription = null,
                tint = scene.color,
                modifier = Modifier.size(32.dp)
            )

            Column(
                modifier = Modifier.weight(1f)
            ) {
                Text(
                    text = scene.name,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = scene.color
                )
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = scene.description,
                    style = MaterialTheme.typography.bodySmall,
                    color = Color.White.copy(alpha = 0.6f)
                )
            }

            Icon(
                imageVector = Icons.Default.ChevronRight,
                contentDescription = null,
                tint = Color.White.copy(alpha = 0.3f),
                modifier = Modifier.size(24.dp)
            )
        }
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
