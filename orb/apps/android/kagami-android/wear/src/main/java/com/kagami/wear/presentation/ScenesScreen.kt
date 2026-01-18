package com.kagami.wear.presentation

import androidx.compose.foundation.focusable
import androidx.compose.foundation.gestures.scrollBy
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.input.rotary.onRotaryScrollEvent
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.wear.compose.foundation.lazy.ScalingLazyColumn
import androidx.wear.compose.foundation.lazy.items
import androidx.wear.compose.foundation.lazy.rememberScalingLazyListState
import androidx.wear.compose.material.*
import com.kagami.wear.services.KagamiWearApiService
import com.kagami.wear.theme.KagamiWearColors
import com.kagami.wear.util.HapticFeedback
import kotlinx.coroutines.launch

/**
 * Scenes Screen - Quick Scene Activation
 *
 * Colony: Beacon (e5) - Planning
 *
 * Features:
 * - All available scenes
 * - Material icons for each scene
 * - Haptic feedback via shared utility
 * - Accessibility descriptions
 * - Rotary input support
 */
@Composable
fun ScenesScreen() {
    val listState = rememberScalingLazyListState()
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    val focusRequester = remember { FocusRequester() }

    var activatingScene by remember { mutableStateOf<String?>(null) }

    val scenes = listOf(
        Scene("movie_mode", "Movie Mode", "Dim lights, lower TV", Icons.Default.Theaters, KagamiWearColors.forge),
        Scene("goodnight", "Goodnight", "All off, lock doors", Icons.Default.NightsStay, KagamiWearColors.flow),
        Scene("welcome_home", "Welcome Home", "Warm lights on", Icons.Default.Home, KagamiWearColors.beacon),
        Scene("away", "Away", "Secure the house", Icons.Default.Lock, KagamiWearColors.crystal),
        Scene("focus", "Focus Mode", "Bright office lights", Icons.Default.CenterFocusStrong, KagamiWearColors.grove),
        Scene("good_morning", "Good Morning", "Start the day", Icons.Default.WbSunny, KagamiWearColors.beacon),
    )

    LaunchedEffect(Unit) {
        focusRequester.requestFocus()
    }

    Scaffold(
        timeText = { TimeText() },
        vignette = { Vignette(vignettePosition = VignettePosition.TopAndBottom) }
    ) {
        ScalingLazyColumn(
            state = listState,
            modifier = Modifier
                .fillMaxSize()
                .onRotaryScrollEvent { event ->
                    scope.launch { listState.scrollBy(event.verticalScrollPixels) }
                    true
                }
                .focusRequester(focusRequester)
                .focusable(),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            item {
                Text(
                    text = "Scenes",
                    style = MaterialTheme.typography.title3,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.semantics {
                        contentDescription = "Scenes screen. ${scenes.size} scenes available."
                    }
                )
            }

            items(scenes) { scene ->
                SceneChip(
                    scene = scene,
                    isActivating = activatingScene == scene.id,
                    onActivate = {
                        scope.launch {
                            HapticFeedback.tap(context)
                            activatingScene = scene.id
                            val success = KagamiWearApiService.executeScene(scene.id)
                            if (success) {
                                HapticFeedback.success(context)
                            } else {
                                HapticFeedback.error(context)
                            }
                            kotlinx.coroutines.delay(1500)
                            activatingScene = null
                        }
                    }
                )
            }
        }
    }
}

@Composable
private fun SceneChip(
    scene: Scene,
    isActivating: Boolean,
    onActivate: () -> Unit
) {
    Chip(
        onClick = onActivate,
        label = {
            Column {
                Text(text = scene.name)
                Text(
                    text = scene.description,
                    fontSize = 10.sp,
                    color = Color.White.copy(alpha = 0.7f)
                )
            }
        },
        icon = {
            if (isActivating) {
                CircularProgressIndicator(
                    modifier = Modifier.size(18.dp),
                    strokeWidth = 2.dp,
                    indicatorColor = scene.color
                )
            } else {
                Icon(
                    imageVector = scene.icon,
                    contentDescription = null,
                    tint = scene.color,
                    modifier = Modifier.size(18.dp)
                )
            }
        },
        colors = ChipDefaults.chipColors(
            backgroundColor = scene.color.copy(alpha = 0.3f)
        ),
        enabled = !isActivating,
        modifier = Modifier
            .fillMaxWidth()
            .semantics {
                contentDescription = if (isActivating) {
                    "Activating ${scene.name}"
                } else {
                    "${scene.name}. ${scene.description}. Tap to activate."
                }
            }
    )
}

private data class Scene(
    val id: String,
    val name: String,
    val description: String,
    val icon: ImageVector,
    val color: Color
)
