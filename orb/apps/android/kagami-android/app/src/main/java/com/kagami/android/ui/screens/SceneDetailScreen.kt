/**
 * Scene Detail Screen - Individual Scene Activation
 *
 * Colony: Beacon (e5) - Planning
 *
 * Features:
 * - Deep link support (kagami://scene/{id})
 * - Scene preview
 * - One-tap activation
 * - Haptic feedback
 */

package com.kagami.android.ui.screens

import android.view.HapticFeedbackConstants
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.kagami.android.ui.minTouchTarget
import com.kagami.android.ui.theme.*
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

private data class SceneInfo(
    val id: String,
    val name: String,
    val description: String,
    val icon: ImageVector,
    val color: Color
)

private val scenes = mapOf(
    "movie_mode" to SceneInfo("movie_mode", "Movie Mode", "Dim lights, lower TV, close shades", Icons.Default.Movie, Forge),
    "goodnight" to SceneInfo("goodnight", "Goodnight", "All lights off, lock doors", Icons.Default.NightsStay, Flow),
    "welcome_home" to SceneInfo("welcome_home", "Welcome Home", "Warm lights, open shades", Icons.Default.Home, Beacon),
    "away" to SceneInfo("away", "Away Mode", "Secure house, reduce energy", Icons.Default.Lock, Crystal),
    "focus" to SceneInfo("focus", "Focus Mode", "Bright lights, open shades", Icons.Default.CenterFocusStrong, Spark),
    "relax" to SceneInfo("relax", "Relax", "Dim lights, fireplace on", Icons.Default.SelfImprovement, Grove),
    "coffee" to SceneInfo("coffee", "Coffee Time", "Bright kitchen lights", Icons.Default.Coffee, Nexus),
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SceneDetailScreen(
    sceneId: String,
    onBack: () -> Unit,
    viewModel: NavViewModel = hiltViewModel()
) {
    val apiService = viewModel.apiService
    val scope = rememberCoroutineScope()
    val view = LocalView.current

    var isActivating by remember { mutableStateOf(false) }
    var activationSuccess by remember { mutableStateOf<Boolean?>(null) }

    val scene = scenes[sceneId]

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        scene?.name ?: "Scene",
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
                        Icon(Icons.Default.ArrowBack, contentDescription = null)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = Void)
            )
        },
        containerColor = Void
    ) { padding ->
        if (scene == null) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentAlignment = Alignment.Center
            ) {
                Text("Scene not found", color = Color.White.copy(alpha = 0.65f))
            }
        } else {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .padding(16.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(24.dp)
            ) {
                Spacer(modifier = Modifier.height(32.dp))

                // Scene Icon
                Card(
                    modifier = Modifier.size(120.dp),
                    shape = RoundedCornerShape(60.dp),
                    colors = CardDefaults.cardColors(containerColor = scene.color.copy(alpha = 0.2f))
                ) {
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center
                    ) {
                        when {
                            isActivating -> {
                                CircularProgressIndicator(
                                    color = scene.color,
                                    modifier = Modifier.size(48.dp)
                                )
                            }
                            activationSuccess == true -> {
                                Icon(
                                    Icons.Default.Check,
                                    contentDescription = null,
                                    tint = Grove,
                                    modifier = Modifier.size(64.dp)
                                )
                            }
                            activationSuccess == false -> {
                                Icon(
                                    Icons.Default.Error,
                                    contentDescription = null,
                                    tint = Forge,
                                    modifier = Modifier.size(64.dp)
                                )
                            }
                            else -> {
                                Icon(
                                    scene.icon,
                                    contentDescription = null,
                                    tint = scene.color,
                                    modifier = Modifier.size(64.dp)
                                )
                            }
                        }
                    }
                }

                // Scene Name
                Text(
                    scene.name,
                    style = MaterialTheme.typography.headlineLarge,
                    color = Color.White
                )

                // Scene Description
                Text(
                    scene.description,
                    style = MaterialTheme.typography.bodyLarge,
                    color = Color.White.copy(alpha = 0.7f)
                )

                Spacer(modifier = Modifier.weight(1f))

                // Activation Button
                Button(
                    onClick = {
                        scope.launch {
                            view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                            isActivating = true
                            activationSuccess = null

                            val result = apiService.executeScene(scene.id)
                            result.onSuccess {
                                view.performHapticFeedback(HapticFeedbackConstants.CONFIRM)
                                activationSuccess = true
                            }.onError { _ ->
                                view.performHapticFeedback(HapticFeedbackConstants.REJECT)
                                activationSuccess = false
                            }

                            isActivating = false

                            // Reset after delay
                            delay(2000)
                            activationSuccess = null
                        }
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(56.dp),
                    enabled = !isActivating,
                    colors = ButtonDefaults.buttonColors(containerColor = scene.color),
                    shape = RoundedCornerShape(16.dp)
                ) {
                    if (isActivating) {
                        CircularProgressIndicator(
                            color = Color.White,
                            modifier = Modifier.size(24.dp),
                            strokeWidth = 2.dp
                        )
                    } else {
                        Icon(
                            Icons.Default.PlayArrow,
                            contentDescription = null,
                            modifier = Modifier.size(24.dp)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            if (activationSuccess == true) "Activated!"
                            else if (activationSuccess == false) "Failed - Retry"
                            else "Activate Scene"
                        )
                    }
                }

                Spacer(modifier = Modifier.height(32.dp))
            }
        }
    }
}
