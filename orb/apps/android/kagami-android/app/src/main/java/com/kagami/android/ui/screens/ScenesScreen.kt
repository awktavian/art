/**
 * Kagami Scenes Screen - Scene Activation
 *
 * Accessibility (Phase 2):
 * - TalkBack content descriptions for all interactive elements
 * - Minimum 48dp touch targets
 * - High contrast mode support
 * - Font scaling support (200%)
 * - RTL layout support
 * - Microinteractions & delight
 */

package com.kagami.android.ui.screens

import android.view.HapticFeedbackConstants
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.scaleIn
import androidx.compose.animation.scaleOut
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
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
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.kagami.android.ui.MinTouchTargetSize
import com.kagami.android.ui.buildSceneDescription
import com.kagami.android.ui.minTouchTarget
import com.kagami.android.ui.theme.*

data class Scene(
    val id: String,
    val name: String,
    val description: String,
    val shortcut: String,  // Voice shortcut phrase
    val icon: ImageVector,
    val color: Color
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ScenesScreen(
    onBack: () -> Unit,
    viewModel: ScenesViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val view = LocalView.current

    // Track screen view
    LaunchedEffect(Unit) {
        viewModel.trackScreenView()
    }

    val scenes = listOf(
        Scene("movie_mode", "Movie Mode", "Dim lights, lower TV, close shades", "\"OK Google, movie mode\"", Icons.Default.Movie, Forge),
        Scene("goodnight", "Goodnight", "All lights off, lock doors, sweet dreams", "\"OK Google, goodnight\"", Icons.Default.NightsStay, Flow),
        Scene("welcome_home", "Welcome Home", "Warm lights, open shades, you're back!", "\"OK Google, I'm home\"", Icons.Default.Home, Beacon),
        Scene("away", "Away Mode", "Secure house, reduce energy", "\"OK Google, I'm leaving\"", Icons.Default.Lock, Crystal),
        Scene("focus", "Focus Mode", "Bright lights, no distractions", "\"OK Google, focus mode\"", Icons.Default.CenterFocusStrong, Spark),
        Scene("relax", "Relax", "Dim lights, fireplace on, unwind", "\"OK Google, relax mode\"", Icons.Default.SelfImprovement, Grove),
        Scene("coffee", "Coffee Time", "Bright kitchen, start the day right", "\"OK Google, coffee time\"", Icons.Default.Coffee, Nexus),
    )

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        "Scenes",
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
                        Icon(
                            Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = null // Handled by parent semantics
                        )
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
                    .padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                items(scenes) { scene ->
                    SceneCard(
                        scene = scene,
                        onClick = {
                            view.performHapticFeedback(HapticFeedbackConstants.CONFIRM)
                            viewModel.activateScene(scene.id)
                        }
                    )
                }
            }
        }
    }
}

@Composable
fun SceneCard(scene: Scene, onClick: () -> Unit) {
    val description = buildSceneDescription(scene.name, scene.description)
    val layoutDirection = LocalLayoutDirection.current
    val view = LocalView.current

    var isPressed by remember { mutableStateOf(false) }
    var showSuccess by remember { mutableStateOf(false) }

    val scale by animateFloatAsState(
        targetValue = if (isPressed) 0.97f else 1f,
        animationSpec = spring(dampingRatio = 0.7f, stiffness = 400f),
        label = "scene_press"
    )

    // Reset success state after delay
    LaunchedEffect(showSuccess) {
        if (showSuccess) {
            kotlinx.coroutines.delay(2000)
            showSuccess = false
        }
    }

    Card(
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
                    onTap = {
                        view.performHapticFeedback(HapticFeedbackConstants.CONFIRM)
                        showSuccess = true
                        onClick()
                    }
                )
            }
            .semantics {
                contentDescription = description
                role = Role.Button
            },
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = scene.color.copy(alpha = 0.12f)
        ),
        border = CardDefaults.outlinedCardBorder().copy(
            brush = Brush.linearGradient(
                colors = listOf(scene.color.copy(alpha = 0.3f), scene.color.copy(alpha = 0.1f))
            )
        )
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 20.dp, vertical = 16.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // Icon with glow effect
            Box(
                modifier = Modifier
                    .size(52.dp)
                    .clip(CircleShape)
                    .background(scene.color.copy(alpha = 0.15f)),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = scene.icon,
                    contentDescription = null,
                    tint = scene.color,
                    modifier = Modifier.size(28.dp)
                )
            }

            Column(
                modifier = Modifier
                    .weight(1f)
                    .clearAndSetSemantics { }
            ) {
                Text(
                    text = scene.name,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = Color.White
                )
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = scene.description,
                    style = MaterialTheme.typography.bodyMedium,
                    color = Color.White.copy(alpha = 0.7f)
                )
                Spacer(modifier = Modifier.height(6.dp))
                // Voice shortcut hint
                Text(
                    text = scene.shortcut,
                    style = MaterialTheme.typography.bodySmall,
                    fontStyle = FontStyle.Italic,
                    color = scene.color.copy(alpha = 0.7f)
                )
            }

            // Success checkmark or chevron
            AnimatedVisibility(
                visible = showSuccess,
                enter = scaleIn() + fadeIn(),
                exit = scaleOut() + fadeOut()
            ) {
                Icon(
                    imageVector = Icons.Default.CheckCircle,
                    contentDescription = "Activated",
                    tint = Grove,
                    modifier = Modifier.size(28.dp)
                )
            }

            AnimatedVisibility(
                visible = !showSuccess,
                enter = fadeIn(),
                exit = fadeOut()
            ) {
                Icon(
                    imageVector = if (layoutDirection == LayoutDirection.Rtl)
                        Icons.Default.ChevronLeft else Icons.Default.ChevronRight,
                    contentDescription = null,
                    tint = Color.White.copy(alpha = 0.3f),
                    modifier = Modifier.size(24.dp)
                )
            }
        }
    }
}
