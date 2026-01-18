/**
 * Room Detail Screen - Individual Room Controls
 *
 * Colony: Nexus (e4) - Integration
 *
 * Features:
 * - Deep link support (kagami://room/{id})
 * - Light level slider
 * - Shade controls
 * - Occupancy status
 */

package com.kagami.android.ui.screens

import android.view.HapticFeedbackConstants
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.LightMode
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Window
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.kagami.android.services.KagamiApiService
import com.kagami.android.services.RoomModel
import com.kagami.android.ui.MinTouchTargetSize
import com.kagami.android.ui.minTouchTarget
import com.kagami.android.ui.theme.*
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RoomDetailScreen(
    roomId: String,
    onBack: () -> Unit,
    viewModel: NavViewModel = hiltViewModel()
) {
    val apiService = viewModel.apiService
    val scope = rememberCoroutineScope()
    val view = LocalView.current

    var room by remember { mutableStateOf<RoomModel?>(null) }
    var isLoading by remember { mutableStateOf(true) }
    var lightLevel by remember { mutableStateOf(0f) }

    LaunchedEffect(roomId) {
        isLoading = true
        val result = apiService.fetchRooms()
        result.onSuccess { rooms ->
            room = rooms.find { it.id == roomId }
            room?.let { lightLevel = it.avgLightLevel.toFloat() }
        }
        isLoading = false
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        room?.name ?: "Room",
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
        if (isLoading) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentAlignment = Alignment.Center
            ) {
                CircularProgressIndicator(color = Crystal)
            }
        } else if (room == null) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentAlignment = Alignment.Center
            ) {
                Text("Room not found", color = Color.White.copy(alpha = 0.65f))
            }
        } else {
            room?.let { currentRoom ->
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(padding)
                        .padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(24.dp)
                ) {
                    // Room Info Card
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(16.dp),
                        colors = CardDefaults.cardColors(containerColor = VoidLight)
                    ) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    currentRoom.name,
                                    style = MaterialTheme.typography.headlineMedium,
                                    color = Color.White
                                )
                                if (currentRoom.occupied) {
                                    Row(
                                        verticalAlignment = Alignment.CenterVertically,
                                        horizontalArrangement = Arrangement.spacedBy(4.dp)
                                    ) {
                                        Icon(
                                            Icons.Default.Person,
                                            contentDescription = null,
                                            tint = Grove,
                                            modifier = Modifier.size(16.dp)
                                        )
                                        Text(
                                            "Occupied",
                                            style = MaterialTheme.typography.labelMedium,
                                            color = Grove
                                        )
                                    }
                                }
                            }
                            Text(
                                currentRoom.floor,
                                style = MaterialTheme.typography.bodyMedium,
                                color = Color.White.copy(alpha = 0.6f)
                            )
                        }
                    }

                    // Light Control
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(16.dp),
                        colors = CardDefaults.cardColors(containerColor = VoidLight)
                    ) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                Icon(
                                    Icons.Default.LightMode,
                                    contentDescription = null,
                                    tint = Beacon,
                                    modifier = Modifier.size(24.dp)
                                )
                                Text(
                                    "Lights",
                                    style = MaterialTheme.typography.titleMedium,
                                    color = Color.White
                                )
                                Spacer(modifier = Modifier.weight(1f))
                                Text(
                                    "${lightLevel.toInt()}%",
                                    style = MaterialTheme.typography.titleMedium,
                                    color = Beacon
                                )
                            }

                            Spacer(modifier = Modifier.height(16.dp))

                            Slider(
                                value = lightLevel,
                                onValueChange = { lightLevel = it },
                                valueRange = 0f..100f,
                                onValueChangeFinished = {
                                    scope.launch {
                                        view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                                        apiService.setLights(lightLevel.toInt(), listOf(currentRoom.id))
                                    }
                                },
                                colors = SliderDefaults.colors(
                                    thumbColor = Beacon,
                                    activeTrackColor = Beacon
                                ),
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .defaultMinSize(minHeight = MinTouchTargetSize)
                                    .semantics {
                                        contentDescription = "Light level slider at ${lightLevel.toInt()} percent"
                                    }
                            )

                            Spacer(modifier = Modifier.height(8.dp))

                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                listOf(0, 30, 70, 100).forEach { level ->
                                    OutlinedButton(
                                        onClick = {
                                            view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                                            lightLevel = level.toFloat()
                                            scope.launch {
                                                apiService.setLights(level, listOf(currentRoom.id))
                                            }
                                        },
                                        modifier = Modifier
                                            .weight(1f)
                                            .defaultMinSize(minHeight = MinTouchTargetSize)
                                    ) {
                                        Text(if (level == 0) "Off" else "$level%")
                                    }
                                }
                            }
                        }
                    }

                    // Shades Control (if available)
                    if (currentRoom.shades.isNotEmpty()) {
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(16.dp),
                            colors = CardDefaults.cardColors(containerColor = VoidLight)
                        ) {
                            Column(modifier = Modifier.padding(16.dp)) {
                                Row(
                                    verticalAlignment = Alignment.CenterVertically,
                                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                                ) {
                                    Icon(
                                        Icons.Default.Window,
                                        contentDescription = null,
                                        tint = Crystal,
                                        modifier = Modifier.size(24.dp)
                                    )
                                    Text(
                                        "Shades",
                                        style = MaterialTheme.typography.titleMedium,
                                        color = Color.White
                                    )
                                }

                                Spacer(modifier = Modifier.height(16.dp))

                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                                ) {
                                    Button(
                                        onClick = {
                                            view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                                            scope.launch {
                                                apiService.controlShades("open", listOf(currentRoom.id))
                                            }
                                        },
                                        modifier = Modifier.weight(1f),
                                        colors = ButtonDefaults.buttonColors(containerColor = Crystal)
                                    ) {
                                        Text("Open")
                                    }
                                    Button(
                                        onClick = {
                                            view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
                                            scope.launch {
                                                apiService.controlShades("close", listOf(currentRoom.id))
                                            }
                                        },
                                        modifier = Modifier.weight(1f),
                                        colors = ButtonDefaults.buttonColors(containerColor = VoidLight)
                                    ) {
                                        Text("Close")
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
