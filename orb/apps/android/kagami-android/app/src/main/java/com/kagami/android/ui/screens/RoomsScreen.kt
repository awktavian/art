/**
 * Kagami Rooms Screen - Room Control
 *
 * Fetches rooms from API and displays interactive controls
 *
 * Accessibility (Phase 2):
 * - TalkBack content descriptions for all interactive elements
 * - Minimum 48dp touch targets
 * - Reduced motion support
 * - Font scaling support (200%)
 */

package com.kagami.android.ui.screens

import android.view.HapticFeedbackConstants
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.DarkMode
import androidx.compose.material.icons.filled.LightMode
import androidx.compose.material.icons.filled.PowerSettingsNew
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.kagami.android.services.RoomModel
import com.kagami.android.ui.MinTouchTargetSize
import com.kagami.android.ui.buildRoomDescription
import com.kagami.android.ui.minTouchTarget
import com.kagami.android.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RoomsScreen(
    onBack: () -> Unit,
    viewModel: RoomsViewModel = hiltViewModel()
) {
    // Use ViewModel for proper DI instead of KagamiApp.instance
    val uiState by viewModel.uiState.collectAsState()
    val view = LocalView.current
    val snackbarHostState = remember { SnackbarHostState() }

    // Show error snackbar for action errors
    LaunchedEffect(uiState.showActionError) {
        if (uiState.showActionError && uiState.actionErrorMessage != null) {
            val result = snackbarHostState.showSnackbar(
                message = uiState.actionErrorMessage ?: "",
                actionLabel = "Retry",
                duration = SnackbarDuration.Short
            )
            if (result == SnackbarResult.ActionPerformed) {
                // User can retry from the room card
            }
            viewModel.dismissActionError()
        }
    }

    // Error dialog for loading errors
    if (uiState.showErrorDialog && uiState.errorMessage != null) {
        AlertDialog(
            onDismissRequest = { viewModel.dismissError() },
            title = { Text("Unable to Load Rooms") },
            text = { Text(uiState.errorMessage ?: "") },
            confirmButton = {
                TextButton(onClick = {
                    viewModel.dismissError()
                    viewModel.fetchRooms()
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
                    Text(
                        "Rooms",
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
                            Icons.Default.ArrowBack,
                            contentDescription = null // Handled by parent semantics
                        )
                    }
                },
                actions = {
                    IconButton(
                        onClick = {
                            view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                            viewModel.refreshRooms()
                        },
                        modifier = Modifier
                            .minTouchTarget()
                            .semantics {
                                contentDescription = "Refresh rooms"
                                role = Role.Button
                            }
                    ) {
                        Icon(
                            Icons.Default.Refresh,
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
            onRefresh = {
                viewModel.refreshRooms()
            },
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            when {
                uiState.isLoading && !uiState.isRefreshing -> {
                    Box(modifier = Modifier.fillMaxSize()) {
                        CircularProgressIndicator(
                            modifier = Modifier
                                .align(Alignment.Center)
                                .semantics {
                                    contentDescription = "Loading rooms"
                                },
                            color = Crystal
                        )
                    }
                }
                uiState.errorMessage != null && uiState.rooms.isEmpty() -> {
                    Box(modifier = Modifier.fillMaxSize()) {
                        Column(
                            modifier = Modifier
                                .align(Alignment.Center)
                                .padding(32.dp),
                            horizontalAlignment = Alignment.CenterHorizontally
                        ) {
                            Text(
                                text = uiState.errorMessage ?: "Error",
                                color = Color.White.copy(alpha = 0.9f) // Improved contrast from 0.7f
                            )
                            Spacer(modifier = Modifier.height(16.dp))
                            Button(
                                onClick = { viewModel.fetchRooms() },
                                modifier = Modifier
                                    .minTouchTarget()
                                    .semantics {
                                        contentDescription = "Retry loading rooms"
                                        role = Role.Button
                                    }
                            ) {
                                Text("Retry")
                            }
                        }
                    }
                }
                uiState.rooms.isEmpty() -> {
                    Box(modifier = Modifier.fillMaxSize()) {
                        Text(
                            text = "No rooms found",
                            modifier = Modifier.align(Alignment.Center),
                            color = Color.White.copy(alpha = 0.7f) // Improved contrast from 0.5f
                        )
                    }
                }
                else -> {
                    LazyColumn(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        items(uiState.rooms, key = { it.id }) { room ->
                            RoomCard(
                                room = room,
                                onLightsOn = {
                                    view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                                    viewModel.setLightsOn(room.id, room.name)
                                },
                                onLightsOff = {
                                    view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                                    viewModel.setLightsOff(room.id, room.name)
                                },
                                onLightsDim = {
                                    view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                                    viewModel.setLightsDim(room.id, room.name)
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
fun RoomCard(
    room: RoomModel,
    onLightsOn: () -> Unit,
    onLightsOff: () -> Unit,
    onLightsDim: () -> Unit
) {
    val avgLight = room.avgLightLevel
    val lightState = room.lightState
    val hasShades = room.shades.isNotEmpty()

    val roomDescription = buildRoomDescription(
        roomName = room.name,
        floor = room.floor,
        lightLevel = avgLight,
        isOccupied = room.occupied
    )

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .semantics(mergeDescendants = true) {
                contentDescription = roomDescription
            },
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (room.occupied) VoidLight.copy(alpha = 0.9f) else VoidLight
        ),
        border = if (room.occupied) CardDefaults.outlinedCardBorder().copy(
            brush = androidx.compose.ui.graphics.SolidColor(Grove.copy(alpha = 0.5f))
        ) else null
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp)
        ) {
            // Header row
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.clearAndSetSemantics { }) {
                    Text(
                        text = room.name,
                        style = MaterialTheme.typography.titleMedium,
                        color = Color.White
                    )
                    Text(
                        text = room.floor,
                        style = MaterialTheme.typography.bodySmall,
                        color = Color.White.copy(alpha = 0.8f) // Improved contrast from 0.5f
                    )
                }

                // Light status indicator
                Row(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier.clearAndSetSemantics { }
                ) {
                    Box(
                        modifier = Modifier
                            .size(10.dp)
                            .clip(CircleShape)
                            .background(
                                when (lightState) {
                                    "On" -> Grove
                                    "Dim" -> Beacon
                                    else -> Color.White.copy(alpha = 0.2f)
                                }
                            )
                    )
                    Text(
                        text = if (avgLight > 0) "${avgLight}%" else "Off",
                        style = MaterialTheme.typography.bodySmall,
                        color = Color.White.copy(alpha = 0.9f) // Improved contrast from 0.7f
                    )
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            // Brightness bar
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(4.dp)
                    .clip(RoundedCornerShape(2.dp))
                    .background(Color.White.copy(alpha = 0.1f))
                    .clearAndSetSemantics { }
            ) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth(avgLight / 100f)
                        .fillMaxHeight()
                        .background(
                            brush = androidx.compose.ui.graphics.Brush.horizontalGradient(
                                colors = listOf(Crystal, Forge)
                            )
                        )
                )
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Action buttons
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                RoomActionButton(
                    icon = Icons.Default.LightMode,
                    label = "Full",
                    description = "Set ${room.name} lights to full brightness",
                    color = Crystal,
                    modifier = Modifier.weight(1f),
                    onClick = onLightsOn
                )
                RoomActionButton(
                    icon = Icons.Default.DarkMode,
                    label = "Dim",
                    description = "Dim ${room.name} lights to 30 percent",
                    color = Beacon,
                    modifier = Modifier.weight(1f),
                    onClick = onLightsDim
                )
                RoomActionButton(
                    icon = Icons.Default.PowerSettingsNew,
                    label = "Off",
                    description = "Turn off ${room.name} lights",
                    color = VoidLight,
                    modifier = Modifier.weight(1f),
                    onClick = onLightsOff
                )
            }
        }
    }
}

@Composable
fun RoomActionButton(
    icon: ImageVector,
    label: String,
    description: String,
    color: Color,
    modifier: Modifier = Modifier,
    onClick: () -> Unit
) {
    Button(
        onClick = onClick,
        modifier = modifier
            .defaultMinSize(minHeight = MinTouchTargetSize)
            .semantics {
                contentDescription = description
                role = Role.Button
            },
        shape = RoundedCornerShape(8.dp),
        colors = ButtonDefaults.buttonColors(
            containerColor = color.copy(alpha = 0.3f),
            contentColor = Color.White
        ),
        contentPadding = PaddingValues(vertical = 12.dp)
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.Center
        ) {
            Icon(
                imageVector = icon,
                contentDescription = null, // Handled by parent semantics
                modifier = Modifier.size(18.dp)
            )
            Spacer(modifier = Modifier.width(4.dp))
            Text(
                label,
                style = MaterialTheme.typography.labelMedium
            )
        }
    }
}
