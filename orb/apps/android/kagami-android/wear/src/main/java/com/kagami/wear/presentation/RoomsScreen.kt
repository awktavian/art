package com.kagami.wear.presentation

import androidx.compose.foundation.background
import androidx.compose.foundation.focusable
import androidx.compose.foundation.gestures.scrollBy
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.LightMode
import androidx.compose.material.icons.filled.ModeNight
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Refresh
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
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.wear.compose.foundation.lazy.ScalingLazyColumn
import androidx.wear.compose.foundation.lazy.items
import androidx.wear.compose.foundation.lazy.rememberScalingLazyListState
import androidx.wear.compose.material.*
import com.kagami.wear.R
import com.kagami.wear.services.KagamiWearApiService
import com.kagami.wear.theme.KagamiWearColors
import com.kagami.wear.util.HapticFeedback
import kotlinx.coroutines.launch

/**
 * Rooms Screen - Room List with Quick Controls
 *
 * Colony: Nexus (e4) - Integration
 *
 * Features:
 * - Fetches rooms from API
 * - Loading state with skeleton
 * - Rotary input support
 * - Accessibility descriptions
 * - Haptic feedback via shared utility
 * - Material icons instead of text
 */
@Composable
fun RoomsScreen() {
    val listState = rememberScalingLazyListState()
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    val focusRequester = remember { FocusRequester() }

    var rooms by remember { mutableStateOf<List<KagamiWearApiService.Room>>(emptyList()) }
    var isLoading by remember { mutableStateOf(true) }
    var hasError by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        isLoading = true
        hasError = false
        try {
            rooms = KagamiWearApiService.fetchRooms()
        } catch (e: Exception) {
            hasError = true
        }
        isLoading = false
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
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            item {
                Text(
                    text = "Rooms",
                    style = MaterialTheme.typography.title3,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.semantics {
                        contentDescription = "Rooms screen. ${rooms.size} rooms available."
                    }
                )
            }

            when {
                isLoading -> {
                    // Skeleton loading items
                    items(4) {
                        SkeletonChip()
                    }
                }
                hasError -> {
                    item {
                        Chip(
                            onClick = {
                                scope.launch {
                                    HapticFeedback.tap(context)
                                    isLoading = true
                                    hasError = false
                                    try {
                                        rooms = KagamiWearApiService.fetchRooms()
                                    } catch (e: Exception) {
                                        hasError = true
                                    }
                                    isLoading = false
                                }
                            },
                            label = { Text(stringResource(R.string.error_connection)) },
                            secondaryLabel = { Text(stringResource(R.string.error_retry)) },
                            icon = {
                                Icon(
                                    imageVector = Icons.Default.Refresh,
                                    contentDescription = null,
                                    modifier = Modifier.size(18.dp)
                                )
                            },
                            colors = ChipDefaults.chipColors(
                                backgroundColor = KagamiWearColors.safetyViolation.copy(alpha = 0.3f)
                            ),
                            modifier = Modifier
                                .fillMaxWidth()
                                .semantics { contentDescription = "Connection failed. Tap to retry." }
                        )
                    }
                }
                else -> {
                    items(rooms) { room ->
                        RoomChip(
                            room = room,
                            onToggleLights = {
                                scope.launch {
                                    HapticFeedback.tap(context)
                                    val newLevel = if (room.lightLevel > 0) 0 else 80
                                    val success = KagamiWearApiService.setLights(newLevel, listOf(room.name))
                                    if (success) {
                                        HapticFeedback.success(context)
                                        rooms = rooms.map {
                                            if (it.id == room.id) it.copy(lightLevel = newLevel) else it
                                        }
                                    } else {
                                        HapticFeedback.error(context)
                                    }
                                }
                            }
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun RoomChip(
    room: KagamiWearApiService.Room,
    onToggleLights: () -> Unit
) {
    val isOn = room.lightLevel > 0
    val lightStatusText = if (isOn) "${room.lightLevel} percent" else "off"
    val occupiedText = if (room.isOccupied) ", occupied" else ""
    val actionText = if (isOn) "Turn lights off" else "Turn lights on"

    Chip(
        onClick = onToggleLights,
        label = {
            Column {
                Text(text = room.name)
                Text(
                    text = if (isOn) "${room.lightLevel}%" else "Off",
                    fontSize = 10.sp,
                    color = Color.White.copy(alpha = 0.7f)
                )
            }
        },
        icon = {
            Icon(
                imageVector = if (isOn) Icons.Default.LightMode else Icons.Default.ModeNight,
                contentDescription = null,
                tint = if (isOn) KagamiWearColors.beacon else Color.Gray,
                modifier = Modifier.size(18.dp)
            )
        },
        secondaryLabel = {
            if (room.isOccupied) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    Icon(
                        imageVector = Icons.Default.Person,
                        contentDescription = null,
                        tint = KagamiWearColors.safetyOk,
                        modifier = Modifier.size(12.dp)
                    )
                    Text(
                        text = "Occupied",
                        fontSize = 8.sp,
                        color = KagamiWearColors.safetyOk
                    )
                }
            }
        },
        colors = ChipDefaults.chipColors(
            backgroundColor = if (isOn)
                KagamiWearColors.beacon.copy(alpha = 0.3f)
            else
                Color.DarkGray.copy(alpha = 0.3f)
        ),
        modifier = Modifier
            .fillMaxWidth()
            .semantics {
                contentDescription = "${room.name}. Lights $lightStatusText$occupiedText. $actionText."
            }
    )
}

@Composable
private fun SkeletonChip() {
    Chip(
        onClick = { },
        label = {
            Box(
                modifier = Modifier
                    .width(100.dp)
                    .height(14.dp)
                    .padding(vertical = 2.dp)
                    .shimmerEffect()
            )
        },
        icon = {
            Box(
                modifier = Modifier
                    .size(18.dp)
                    .shimmerEffect()
            )
        },
        colors = ChipDefaults.secondaryChipColors(),
        enabled = false,
        modifier = Modifier.fillMaxWidth()
    )
}

@Composable
private fun Modifier.shimmerEffect(): Modifier {
    return this.then(
        Modifier.background(
            color = Color.Gray.copy(alpha = 0.3f),
            shape = androidx.compose.foundation.shape.RoundedCornerShape(4.dp)
        )
    )
}
