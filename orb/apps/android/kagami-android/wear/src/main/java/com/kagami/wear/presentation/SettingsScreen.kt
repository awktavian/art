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
import androidx.compose.ui.input.rotary.onRotaryScrollEvent
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.wear.compose.foundation.lazy.ScalingLazyColumn
import androidx.wear.compose.foundation.lazy.rememberScalingLazyListState
import androidx.wear.compose.material.*
import com.google.android.gms.wearable.Wearable
import com.kagami.wear.R
import com.kagami.wear.services.KagamiWearApiService
import com.kagami.wear.theme.KagamiWearColors
import com.kagami.wear.util.HapticFeedback
import kotlinx.coroutines.launch
import kotlinx.coroutines.tasks.await

/**
 * Settings Screen - Watch Configuration
 *
 * Colony: Crystal (e7) - Verification
 *
 * Features:
 * - Server URL display
 * - Phone sync status via WearableDataClient
 * - Connection testing
 * - Material icons (no text icons)
 * - Haptic feedback via shared utility
 * - Accessibility descriptions
 */
@Composable
fun SettingsScreen() {
    val listState = rememberScalingLazyListState()
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    val focusRequester = remember { FocusRequester() }

    var serverUrl by remember { mutableStateOf("") }
    var isConnected by remember { mutableStateOf<Boolean?>(null) }
    var isTesting by remember { mutableStateOf(false) }
    var phoneSyncStatus by remember { mutableStateOf<PhoneSyncStatus>(PhoneSyncStatus.Checking) }

    LaunchedEffect(Unit) {
        serverUrl = KagamiWearApiService.getServerUrl()
        focusRequester.requestFocus()

        // Check phone sync via Wearable API
        phoneSyncStatus = try {
            val nodes = Wearable.getNodeClient(context).connectedNodes.await()
            if (nodes.isNotEmpty()) {
                PhoneSyncStatus.Connected(nodes.first().displayName)
            } else {
                PhoneSyncStatus.Disconnected
            }
        } catch (e: Exception) {
            PhoneSyncStatus.Disconnected
        }
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
                    text = "Settings",
                    style = MaterialTheme.typography.title3,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.semantics {
                        contentDescription = "Settings screen"
                    }
                )
            }

            // Phone Sync Status
            item {
                val (icon, label, color, description) = when (val status = phoneSyncStatus) {
                    is PhoneSyncStatus.Connected -> Quadruple(
                        Icons.Default.PhonelinkRing,
                        status.phoneName,
                        KagamiWearColors.safetyOk,
                        "Connected to ${status.phoneName}"
                    )
                    PhoneSyncStatus.Disconnected -> Quadruple(
                        Icons.Default.PhonelinkOff,
                        stringResource(R.string.phone_not_found),
                        KagamiWearColors.safetyCaution,
                        "Phone not connected"
                    )
                    PhoneSyncStatus.Checking -> Quadruple(
                        Icons.Default.PhonelinkSetup,
                        "Checking...",
                        Color.Gray,
                        "Checking phone connection"
                    )
                }

                Chip(
                    onClick = {
                        scope.launch {
                            HapticFeedback.tap(context)
                            phoneSyncStatus = PhoneSyncStatus.Checking
                            phoneSyncStatus = try {
                                val nodes = Wearable.getNodeClient(context).connectedNodes.await()
                                if (nodes.isNotEmpty()) {
                                    HapticFeedback.success(context)
                                    PhoneSyncStatus.Connected(nodes.first().displayName)
                                } else {
                                    HapticFeedback.error(context)
                                    PhoneSyncStatus.Disconnected
                                }
                            } catch (e: Exception) {
                                HapticFeedback.error(context)
                                PhoneSyncStatus.Disconnected
                            }
                        }
                    },
                    label = { Text("Phone") },
                    secondaryLabel = { Text(label, fontSize = 10.sp, color = color) },
                    icon = {
                        Icon(
                            imageVector = icon,
                            contentDescription = null,
                            tint = color,
                            modifier = Modifier.size(18.dp)
                        )
                    },
                    colors = ChipDefaults.secondaryChipColors(),
                    modifier = Modifier
                        .fillMaxWidth()
                        .semantics { contentDescription = description }
                )
            }

            // Server URL
            item {
                Chip(
                    onClick = { },
                    label = { Text("Server") },
                    secondaryLabel = {
                        Text(
                            text = serverUrl.replace("http://", "").replace(":8001", ""),
                            fontSize = 10.sp
                        )
                    },
                    icon = {
                        Icon(
                            imageVector = Icons.Default.Dns,
                            contentDescription = null,
                            modifier = Modifier.size(18.dp)
                        )
                    },
                    colors = ChipDefaults.secondaryChipColors(),
                    modifier = Modifier
                        .fillMaxWidth()
                        .semantics {
                            contentDescription = "Server URL: $serverUrl"
                        }
                )
            }

            // Test Connection
            item {
                val (icon, label, color) = when {
                    isTesting -> Triple(
                        Icons.Default.HourglassTop,
                        "Testing...",
                        Color.Gray
                    )
                    isConnected == true -> Triple(
                        Icons.Default.CheckCircle,
                        stringResource(R.string.settings_connected),
                        KagamiWearColors.safetyOk
                    )
                    isConnected == false -> Triple(
                        Icons.Default.Error,
                        "Failed",
                        KagamiWearColors.safetyViolation
                    )
                    else -> Triple(
                        Icons.Default.NetworkCheck,
                        "Test Connection",
                        Color.White
                    )
                }

                Chip(
                    onClick = {
                        scope.launch {
                            HapticFeedback.tap(context)
                            isTesting = true
                            isConnected = KagamiWearApiService.testConnection()
                            if (isConnected == true) {
                                HapticFeedback.success(context)
                            } else {
                                HapticFeedback.error(context)
                            }
                            isTesting = false
                        }
                    },
                    label = { Text(label) },
                    icon = {
                        if (isTesting) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(18.dp),
                                strokeWidth = 2.dp
                            )
                        } else {
                            Icon(
                                imageVector = icon,
                                contentDescription = null,
                                tint = color,
                                modifier = Modifier.size(18.dp)
                            )
                        }
                    },
                    colors = ChipDefaults.chipColors(
                        backgroundColor = color.copy(alpha = 0.3f)
                    ),
                    enabled = !isTesting,
                    modifier = Modifier
                        .fillMaxWidth()
                        .semantics {
                            contentDescription = if (isTesting) {
                                "Testing connection"
                            } else {
                                "Test connection to Kagami server"
                            }
                        }
                )
            }

            // Refresh Data
            item {
                Chip(
                    onClick = {
                        scope.launch {
                            HapticFeedback.tap(context)
                            try {
                                KagamiWearApiService.fetchHealth()
                                KagamiWearApiService.fetchRooms()
                                HapticFeedback.success(context)
                            } catch (e: Exception) {
                                HapticFeedback.error(context)
                            }
                        }
                    },
                    label = { Text("Refresh Data") },
                    icon = {
                        Icon(
                            imageVector = Icons.Default.Refresh,
                            contentDescription = null,
                            modifier = Modifier.size(18.dp)
                        )
                    },
                    colors = ChipDefaults.secondaryChipColors(),
                    modifier = Modifier
                        .fillMaxWidth()
                        .semantics {
                            contentDescription = "Refresh all data from server"
                        }
                )
            }

            // App Version
            item {
                Chip(
                    onClick = { },
                    label = { Text("Version") },
                    secondaryLabel = { Text("1.0.0", fontSize = 10.sp) },
                    icon = {
                        Icon(
                            imageVector = Icons.Default.Info,
                            contentDescription = null,
                            modifier = Modifier.size(18.dp)
                        )
                    },
                    colors = ChipDefaults.secondaryChipColors(),
                    modifier = Modifier
                        .fillMaxWidth()
                        .semantics {
                            contentDescription = "App version 1.0.0"
                        }
                )
            }
        }
    }
}

private sealed class PhoneSyncStatus {
    data object Checking : PhoneSyncStatus()
    data class Connected(val phoneName: String) : PhoneSyncStatus()
    data object Disconnected : PhoneSyncStatus()
}

private data class Quadruple<A, B, C, D>(val first: A, val second: B, val third: C, val fourth: D)
