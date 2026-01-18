package com.kagami.wear.presentation

import android.content.Context
import androidx.compose.foundation.background
import androidx.compose.foundation.focusable
import androidx.compose.foundation.gestures.scrollBy
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Theaters
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.rotary.onRotaryScrollEvent
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.wear.compose.foundation.lazy.ScalingLazyColumn
import androidx.wear.compose.foundation.lazy.rememberScalingLazyListState
import androidx.wear.compose.material.*
import com.kagami.wear.ActionResult
import com.kagami.wear.R
import com.kagami.wear.services.KagamiWearApiService
import com.kagami.wear.theme.KagamiWearColors
import com.kagami.wear.util.HapticFeedback
import kotlinx.coroutines.launch
import java.time.LocalTime

/**
 * Home Screen - Context-Aware Hero Action
 *
 * Colony: Beacon (e5) - Planning
 *
 * Design Philosophy:
 * - Hero action always visible (one tap)
 * - Safety score at glance (human-readable)
 * - Context-appropriate suggestions
 * - Rotary input support
 * - Accessibility descriptions
 * - Haptic feedback via shared utility
 */
@Composable
fun HomeScreen(
    onNavigateToScenes: () -> Unit,
    onNavigateToRooms: () -> Unit,
    onNavigateToSettings: () -> Unit,
    actionResult: ActionResult? = null,
    onActionResultConsumed: () -> Unit = {}
) {
    val listState = rememberScalingLazyListState()
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    val focusRequester = remember { FocusRequester() }

    var isLoading by remember { mutableStateOf(true) }
    var isConnected by remember { mutableStateOf(false) }
    var safetyScore by remember { mutableStateOf<Double?>(null) }
    var heroActionActivated by remember { mutableStateOf(false) }

    val heroAction = remember { getHeroAction() }

    LaunchedEffect(actionResult) {
        actionResult?.let {
            when (it) {
                is ActionResult.Success -> {
                    kotlinx.coroutines.delay(2000)
                    onActionResultConsumed()
                }
                is ActionResult.Error -> {
                    kotlinx.coroutines.delay(3000)
                    onActionResultConsumed()
                }
            }
        }
    }

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
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            actionResult?.let { result ->
                item {
                    val (message, bgColor) = when (result) {
                        is ActionResult.Success -> result.message to KagamiWearColors.safetyOk.copy(alpha = 0.3f)
                        is ActionResult.Error -> result.message to KagamiWearColors.safetyViolation.copy(alpha = 0.3f)
                    }
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .background(bgColor, shape = RoundedCornerShape(8.dp))
                            .padding(8.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = message,
                            fontSize = 12.sp,
                            textAlign = TextAlign.Center
                        )
                    }
                }
            }

            item {
                HeroActionCard(
                    action = heroAction,
                    isActivated = heroActionActivated,
                    isLoading = isLoading && heroActionActivated,
                    onClick = {
                        scope.launch {
                            HapticFeedback.tap(context)
                            heroActionActivated = true
                            val success = KagamiWearApiService.executeScene(heroAction.sceneId)
                            if (success) {
                                HapticFeedback.success(context)
                            } else {
                                HapticFeedback.error(context)
                            }
                            kotlinx.coroutines.delay(1500)
                            heroActionActivated = false
                        }
                    }
                )
            }

            item {
                SafetyScoreChip(
                    score = safetyScore,
                    isConnected = isConnected,
                    isLoading = isLoading
                )
            }

            item {
                QuickActionsRow(
                    onScenes = {
                        HapticFeedback.tap(context)
                        onNavigateToScenes()
                    },
                    onRooms = {
                        HapticFeedback.tap(context)
                        onNavigateToRooms()
                    }
                )
            }

            item {
                Chip(
                    onClick = {
                        HapticFeedback.tap(context)
                        onNavigateToSettings()
                    },
                    label = { Text("Settings") },
                    icon = {
                        Icon(
                            imageVector = Icons.Default.Settings,
                            contentDescription = null,
                            modifier = Modifier.size(18.dp)
                        )
                    },
                    colors = ChipDefaults.secondaryChipColors(),
                    modifier = Modifier.semantics {
                        contentDescription = "Open settings"
                    }
                )
            }
        }
    }

    LaunchedEffect(Unit) {
        isLoading = true
        try {
            val health = KagamiWearApiService.fetchHealth()
            isConnected = health.isConnected
            safetyScore = health.safetyScore
        } catch (e: Exception) {
            isConnected = false
        }
        isLoading = false
    }
}

@Composable
private fun HeroActionCard(
    action: HeroAction,
    isActivated: Boolean,
    isLoading: Boolean,
    onClick: () -> Unit
) {
    val actionDescription = "${action.label}. Tap to activate."

    Button(
        onClick = onClick,
        modifier = Modifier
            .fillMaxWidth()
            .height(100.dp)
            .semantics {
                contentDescription = if (isActivated) "${action.label} activated" else actionDescription
            },
        colors = ButtonDefaults.buttonColors(
            backgroundColor = action.color.copy(alpha = 0.3f)
        ),
        enabled = !isActivated
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            if (isLoading) {
                CircularProgressIndicator(
                    modifier = Modifier.size(32.dp),
                    strokeWidth = 2.dp
                )
            } else {
                if (isActivated) {
                    Icon(
                        imageVector = Icons.Default.Check,
                        contentDescription = null,
                        tint = KagamiWearColors.safetyOk,
                        modifier = Modifier.size(32.dp)
                    )
                } else {
                    Text(
                        text = action.label,
                        fontSize = 18.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = Color.White
                    )
                }
            }

            if (!isActivated && !isLoading) {
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = "Tap to activate",
                    fontSize = 10.sp,
                    color = Color.White.copy(alpha = 0.7f)
                )
            }
        }
    }
}

@Composable
private fun SafetyScoreChip(
    score: Double?,
    isConnected: Boolean,
    isLoading: Boolean
) {
    val (statusText, statusColor, statusDescription) = when {
        isLoading -> Triple(
            stringResource(R.string.loading),
            Color.Gray,
            "Loading home status"
        )
        score == null -> Triple(
            stringResource(R.string.safety_unknown),
            Color.Gray,
            "Home status unknown"
        )
        score >= 0.7 -> Triple(
            stringResource(R.string.safety_secure),
            KagamiWearColors.safetyOk,
            "Home is secure. All systems normal."
        )
        score >= 0.3 -> Triple(
            stringResource(R.string.safety_caution),
            KagamiWearColors.safetyCaution,
            "Attention needed. Some items require review."
        )
        else -> Triple(
            stringResource(R.string.safety_alert),
            KagamiWearColors.safetyViolation,
            "Action required. Please check home status."
        )
    }

    val connectionDescription = if (isConnected) "Connected" else "Offline"

    Chip(
        onClick = { },
        label = {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Box(
                    modifier = Modifier
                        .size(8.dp)
                        .background(
                            color = if (isConnected) KagamiWearColors.safetyOk else KagamiWearColors.safetyCaution,
                            shape = androidx.compose.foundation.shape.CircleShape
                        )
                )

                if (isLoading) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(16.dp),
                        strokeWidth = 2.dp
                    )
                } else {
                    Text(
                        text = statusText,
                        color = statusColor,
                        fontWeight = FontWeight.Medium
                    )
                }
            }
        },
        colors = ChipDefaults.secondaryChipColors(),
        modifier = Modifier.semantics {
            contentDescription = "$statusDescription $connectionDescription."
        }
    )
}

@Composable
private fun QuickActionsRow(
    onScenes: () -> Unit,
    onRooms: () -> Unit
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        CompactChip(
            onClick = onScenes,
            label = { Text("Scenes", fontSize = 10.sp) },
            icon = {
                Icon(
                    imageVector = Icons.Default.Theaters,
                    contentDescription = null,
                    modifier = Modifier.size(14.dp)
                )
            },
            modifier = Modifier
                .weight(1f)
                .semantics { contentDescription = "Open scenes list" }
        )

        CompactChip(
            onClick = onRooms,
            label = { Text("Rooms", fontSize = 10.sp) },
            icon = {
                Icon(
                    imageVector = Icons.Default.Home,
                    contentDescription = null,
                    modifier = Modifier.size(14.dp)
                )
            },
            modifier = Modifier
                .weight(1f)
                .semantics { contentDescription = "Open rooms list" }
        )
    }
}

data class HeroAction(
    val label: String,
    val sceneId: String,
    val color: Color
)

private fun getHeroAction(): HeroAction {
    val hour = LocalTime.now().hour

    return when (hour) {
        in 5..8 -> HeroAction("Good Morning", "good_morning", KagamiWearColors.beacon)
        in 9..16 -> HeroAction("Focus Mode", "focus", KagamiWearColors.grove)
        in 17..20 -> HeroAction("Movie Mode", "movie_mode", KagamiWearColors.forge)
        in 21..23 -> HeroAction("Goodnight", "goodnight", KagamiWearColors.flow)
        else -> HeroAction("Sleep", "sleep", KagamiWearColors.flow)
    }
}
