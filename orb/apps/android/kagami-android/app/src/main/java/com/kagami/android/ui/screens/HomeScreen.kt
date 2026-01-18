/**
 * Kagami Home Screen - Main Dashboard
 *
 * Colony: Nexus (e4) - Integration
 *
 * Primary landing screen showing:
 * - Connection status and safety score
 * - Quick hero actions (scenes)
 * - Quick device controls
 *
 * Accessibility (Phase 2):
 * - TalkBack content descriptions for all interactive elements
 * - Minimum 48dp touch targets
 * - Reduced motion support
 * - Font scaling support (200%)
 */

package com.kagami.android.ui.screens

import android.view.HapticFeedbackConstants
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.kagami.android.ui.MinTouchTargetSize
import com.kagami.android.ui.minTouchTarget
import com.kagami.android.ui.theme.*

/**
 * Hero scene data class for quick scene activation
 */
data class HeroScene(
    val id: String,
    val name: String,
    val icon: ImageVector,
    val description: String,
    val gradient: List<Color>
)

/**
 * Quick action data class
 */
data class QuickAction(
    val id: String,
    val name: String,
    val icon: ImageVector,
    val description: String,
    val color: Color
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    onNavigateToRooms: () -> Unit,
    onNavigateToScenes: () -> Unit,
    onNavigateToSettings: () -> Unit,
    onNavigateToVoice: () -> Unit = {},
    onNavigateToHub: () -> Unit = {},
    viewModel: HomeViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val isConnected by viewModel.isConnected.collectAsState()
    val safetyScore by viewModel.safetyScore.collectAsState()
    val latencyMs by viewModel.latencyMs.collectAsState()
    val view = LocalView.current
    val snackbarHostState = remember { SnackbarHostState() }

    // Hero scenes for quick activation
    val heroScenes = remember {
        listOf(
            HeroScene(
                id = "goodnight",
                name = "Goodnight",
                icon = Icons.Default.Bedtime,
                description = "Activate goodnight scene: turns off all lights and locks doors",
                gradient = listOf(Flow, Crystal)
            ),
            HeroScene(
                id = "movie_mode",
                name = "Movie",
                icon = Icons.Default.Tv,
                description = "Activate movie mode: dims lights and lowers TV",
                gradient = listOf(Forge, Beacon)
            ),
            HeroScene(
                id = "welcome_home",
                name = "Welcome",
                icon = Icons.Default.Home,
                description = "Activate welcome home scene: warm lights and music",
                gradient = listOf(Grove, Spark)
            ),
            HeroScene(
                id = "away",
                name = "Away",
                icon = Icons.Default.Lock,
                description = "Activate away scene: locks doors and arms security",
                gradient = listOf(Nexus, Flow)
            )
        )
    }

    // Quick actions for common controls
    val quickActions = remember {
        listOf(
            QuickAction("lights_on", "Lights On", Icons.Default.LightMode, "Turn all lights on", Crystal),
            QuickAction("lights_off", "Lights Off", Icons.Default.DarkMode, "Turn all lights off", VoidLight),
            QuickAction("shades_open", "Open Shades", Icons.Default.WbSunny, "Open all shades", Beacon),
            QuickAction("shades_close", "Close Shades", Icons.Default.Blinds, "Close all shades", Flow)
        )
    }

    // Error dialog
    if (uiState.showErrorDialog && uiState.errorMessage != null) {
        AlertDialog(
            onDismissRequest = { viewModel.dismissError() },
            title = { Text("Error") },
            text = { Text(uiState.errorMessage ?: "") },
            confirmButton = {
                TextButton(onClick = {
                    viewModel.dismissError()
                    viewModel.refresh()
                }) {
                    Text("Retry")
                }
            },
            dismissButton = {
                TextButton(onClick = { viewModel.dismissError() }) {
                    Text("Dismiss")
                }
            }
        )
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        topBar = {
            TopAppBar(
                title = {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        // Fano Plane logo placeholder
                        Box(
                            modifier = Modifier
                                .size(32.dp)
                                .clip(CircleShape)
                                .background(
                                    brush = Brush.linearGradient(
                                        colors = listOf(Crystal, Flow)
                                    )
                                ),
                            contentAlignment = Alignment.Center
                        ) {
                            Text(
                                "鏡",
                                style = MaterialTheme.typography.titleSmall,
                                color = Color.White
                            )
                        }
                        Text(
                            "Kagami",
                            modifier = Modifier.semantics { heading() },
                            fontWeight = FontWeight.Bold
                        )
                    }
                },
                actions = {
                    IconButton(
                        onClick = {
                            view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                            onNavigateToSettings()
                        },
                        modifier = Modifier
                            .minTouchTarget()
                            .semantics {
                                contentDescription = "Open settings"
                                role = Role.Button
                            }
                    ) {
                        Icon(Icons.Default.Settings, contentDescription = null)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = Void)
            )
        },
        containerColor = Void
    ) { padding ->
        PullToRefreshBox(
            isRefreshing = uiState.isRefreshing,
            onRefresh = { viewModel.refresh() },
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(horizontal = 16.dp),
                verticalArrangement = Arrangement.spacedBy(24.dp),
                contentPadding = PaddingValues(vertical = 16.dp)
            ) {
                // Status Card
                item {
                    StatusCard(
                        isConnected = isConnected,
                        safetyScore = safetyScore,
                        latencyMs = latencyMs,
                        isLoading = uiState.isInitialLoading
                    )
                }

                // Hero Scenes Section
                item {
                    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        Text(
                            "Quick Scenes",
                            style = MaterialTheme.typography.titleMedium,
                            color = Color.White,
                            modifier = Modifier.semantics { heading() }
                        )

                        LazyRow(
                            horizontalArrangement = Arrangement.spacedBy(12.dp)
                        ) {
                            items(heroScenes, key = { it.id }) { scene ->
                                HeroSceneCard(
                                    scene = scene,
                                    onClick = {
                                        view.performHapticFeedback(HapticFeedbackConstants.CONFIRM)
                                        viewModel.executeScene(scene.id)
                                    }
                                )
                            }
                        }
                    }
                }

                // Quick Actions Section
                item {
                    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        Text(
                            "Quick Actions",
                            style = MaterialTheme.typography.titleMedium,
                            color = Color.White,
                            modifier = Modifier.semantics { heading() }
                        )

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            quickActions.forEach { action ->
                                QuickActionButton(
                                    action = action,
                                    modifier = Modifier.weight(1f),
                                    onClick = {
                                        view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                                        viewModel.executeQuickAction(action.id)
                                    }
                                )
                            }
                        }
                    }
                }

                // Navigation Cards
                item {
                    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        Text(
                            "Control Center",
                            style = MaterialTheme.typography.titleMedium,
                            color = Color.White,
                            modifier = Modifier.semantics { heading() }
                        )

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(12.dp)
                        ) {
                            NavigationCard(
                                title = "Rooms",
                                subtitle = "Control by room",
                                icon = Icons.Default.MeetingRoom,
                                color = Grove,
                                modifier = Modifier.weight(1f),
                                onClick = {
                                    view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                                    onNavigateToRooms()
                                }
                            )
                            NavigationCard(
                                title = "Scenes",
                                subtitle = "All scenes",
                                icon = Icons.Default.AutoAwesome,
                                color = Beacon,
                                modifier = Modifier.weight(1f),
                                onClick = {
                                    view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                                    onNavigateToScenes()
                                }
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun StatusCard(
    isConnected: Boolean,
    safetyScore: Double?,
    latencyMs: Int,
    isLoading: Boolean
) {
    val statusColor = if (isConnected) Grove else Spark
    val statusText = if (isConnected) "Connected" else "Disconnected"
    val safetyText = safetyScore?.let { String.format("%.1f", it * 100) } ?: "--"
    val safetyColor = when {
        safetyScore == null -> Color.White.copy(alpha = 0.5f)
        safetyScore >= 0.9 -> Grove
        safetyScore >= 0.7 -> Beacon
        else -> Spark
    }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .semantics(mergeDescendants = true) {
                contentDescription = "System status: $statusText. Safety score: $safetyText percent. Latency: $latencyMs milliseconds"
            },
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = VoidLight)
    ) {
        if (isLoading) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(100.dp),
                contentAlignment = Alignment.Center
            ) {
                CircularProgressIndicator(
                    color = Crystal,
                    modifier = Modifier.semantics {
                        contentDescription = "Loading system status"
                    }
                )
            }
        } else {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                horizontalArrangement = Arrangement.SpaceEvenly,
                verticalAlignment = Alignment.CenterVertically
            ) {
                // Connection Status
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    modifier = Modifier.clearAndSetSemantics { }
                ) {
                    Box(
                        modifier = Modifier
                            .size(12.dp)
                            .clip(CircleShape)
                            .background(statusColor)
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        statusText,
                        style = MaterialTheme.typography.bodySmall,
                        color = Color.White.copy(alpha = 0.9f)
                    )
                }

                // Safety Score
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    modifier = Modifier.clearAndSetSemantics { }
                ) {
                    Text(
                        safetyText,
                        style = MaterialTheme.typography.headlineMedium,
                        color = safetyColor,
                        fontWeight = FontWeight.Bold
                    )
                    Text(
                        "Safety",
                        style = MaterialTheme.typography.bodySmall,
                        color = Color.White.copy(alpha = 0.9f)
                    )
                }

                // Latency
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    modifier = Modifier.clearAndSetSemantics { }
                ) {
                    Text(
                        "${latencyMs}ms",
                        style = MaterialTheme.typography.titleLarge,
                        color = if (latencyMs < 100) Grove else if (latencyMs < 300) Beacon else Spark,
                        fontWeight = FontWeight.Medium
                    )
                    Text(
                        "Latency",
                        style = MaterialTheme.typography.bodySmall,
                        color = Color.White.copy(alpha = 0.9f)
                    )
                }
            }
        }
    }
}

@Composable
fun HeroSceneCard(
    scene: HeroScene,
    onClick: () -> Unit
) {
    // Jobs: "Make it BOLD — 160×120 minimum"
    // Ive: "Animation brings life. Static is dead."
    var isPressed by remember { mutableStateOf(false) }
    val scale by animateFloatAsState(
        targetValue = if (isPressed) 0.95f else 1f,
        animationSpec = spring(dampingRatio = 0.7f, stiffness = 400f),
        label = "hero_press"
    )

    Card(
        modifier = Modifier
            .width(160.dp)  // Ive: Bolder presence
            .height(120.dp)
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
            .semantics {
                contentDescription = scene.description
                role = Role.Button
            },
        shape = RoundedCornerShape(20.dp),  // Ive: More generous radius
        colors = CardDefaults.cardColors(containerColor = Color.Transparent)
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(
                    brush = Brush.linearGradient(
                        colors = scene.gradient.map { it.copy(alpha = 0.65f) }  // Slightly more vibrant
                    )
                )
                .border(
                    width = 1.5.dp,  // Ive: Visible edge definition
                    brush = Brush.linearGradient(
                        colors = scene.gradient.map { it.copy(alpha = 0.4f) }
                    ),
                    shape = RoundedCornerShape(20.dp)
                )
                .padding(16.dp),  // More breathing room
            contentAlignment = Alignment.BottomStart
        ) {
            Column {
                Icon(
                    imageVector = scene.icon,
                    contentDescription = null,
                    tint = Color.White,
                    modifier = Modifier.size(32.dp)  // Ive: More presence
                )
                Spacer(modifier = Modifier.height(12.dp))
                Text(
                    scene.name,
                    style = MaterialTheme.typography.titleMedium,  // Slightly larger
                    color = Color.White,
                    fontWeight = FontWeight.SemiBold
                )
            }
        }
    }
}

@Composable
fun QuickActionButton(
    action: QuickAction,
    modifier: Modifier = Modifier,
    onClick: () -> Unit
) {
    // Ive: "Every tap should be an event"
    var isPressed by remember { mutableStateOf(false) }
    val scale by animateFloatAsState(
        targetValue = if (isPressed) 0.92f else 1f,
        animationSpec = spring(dampingRatio = 0.7f, stiffness = 500f),
        label = "action_press"
    )

    Button(
        onClick = onClick,
        modifier = modifier
            .defaultMinSize(minHeight = MinTouchTargetSize)
            .graphicsLayer {
                scaleX = scale
                scaleY = scale
            }
            .semantics {
                contentDescription = action.description
                role = Role.Button
            },
        shape = RoundedCornerShape(14.dp),  // Slightly more generous
        colors = ButtonDefaults.buttonColors(
            containerColor = action.color.copy(alpha = 0.15f),  // Match iOS opacity
            contentColor = Color.White
        ),
        contentPadding = PaddingValues(vertical = 14.dp, horizontal = 10.dp)
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Icon(
                imageVector = action.icon,
                contentDescription = null,
                modifier = Modifier.size(24.dp)  // Ive: Icons need presence (was 20dp)
            )
            Spacer(modifier = Modifier.height(6.dp))
            Text(
                action.name,
                style = MaterialTheme.typography.labelMedium,  // Slightly larger
                maxLines = 1
            )
        }
    }
}

@Composable
fun NavigationCard(
    title: String,
    subtitle: String,
    icon: ImageVector,
    color: Color,
    modifier: Modifier = Modifier,
    onClick: () -> Unit
) {
    // Ive: "Press feedback is non-negotiable"
    var isPressed by remember { mutableStateOf(false) }
    val scale by animateFloatAsState(
        targetValue = if (isPressed) 0.97f else 1f,
        animationSpec = spring(dampingRatio = 0.75f, stiffness = 400f),
        label = "nav_press"
    )
    // Jobs: Remove redundant subtitle
    val displaySubtitle = when (title) {
        "Rooms" -> "By location"  // Simpler, more purposeful
        "Scenes" -> "Automations"
        else -> subtitle
    }

    Card(
        modifier = modifier
            .height(100.dp)
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
            .semantics {
                contentDescription = "$title: $displaySubtitle"
                role = Role.Button
            },
        shape = RoundedCornerShape(18.dp),  // Slightly more generous
        colors = CardDefaults.cardColors(containerColor = VoidLight)
    ) {
        Row(
            modifier = Modifier
                .fillMaxSize()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            Box(
                modifier = Modifier
                    .size(48.dp)
                    .clip(RoundedCornerShape(14.dp))
                    .background(color.copy(alpha = 0.15f)),  // Match iOS opacity
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = icon,
                    contentDescription = null,
                    tint = color,
                    modifier = Modifier.size(26.dp)  // Slightly larger
                )
            }
            Column {
                Text(
                    title,
                    style = MaterialTheme.typography.titleMedium,
                    color = Color.White,
                    fontWeight = FontWeight.Medium
                )
                Text(
                    displaySubtitle,
                    style = MaterialTheme.typography.bodySmall,
                    color = Color.White.copy(alpha = 0.6f)
                )
            }
        }
    }
}
