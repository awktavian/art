/**
 * Kagami Rooms Screen Screenshot Tests
 *
 * Visual regression tests for RoomsScreen in different states.
 * Uses Roborazzi for JVM-based screenshot testing.
 *
 * Test scenarios:
 * - Loading state
 * - Empty state (no rooms)
 * - Populated state with multiple rooms
 * - Error state
 * - Room with lights on/off/dim
 * - Occupied vs unoccupied rooms
 *
 * h(x) >= 0. Always.
 */
package com.kagami.android.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.github.takahirom.roborazzi.RobolectricDeviceQualifiers
import com.kagami.android.services.RoomModel
import com.kagami.android.ui.theme.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/**
 * Screenshot tests for RoomsScreen in various states.
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34], qualifiers = RobolectricDeviceQualifiers.Pixel7)
class RoomsScreenScreenshotTest : ScreenshotTestBase() {

    /**
     * Capture RoomsScreen in loading state.
     */
    @Test
    fun roomsScreen_loading() {
        captureScreen("RoomsScreen_Loading") {
            RoomsScreenPreview(
                isLoading = true,
                rooms = emptyList(),
                errorMessage = null
            )
        }
    }

    /**
     * Capture RoomsScreen with empty state (no rooms found).
     */
    @Test
    fun roomsScreen_empty() {
        captureScreen("RoomsScreen_Empty") {
            RoomsScreenPreview(
                isLoading = false,
                rooms = emptyList(),
                errorMessage = null
            )
        }
    }

    /**
     * Capture RoomsScreen with error state.
     */
    @Test
    fun roomsScreen_error() {
        captureScreen("RoomsScreen_Error") {
            RoomsScreenPreview(
                isLoading = false,
                rooms = emptyList(),
                errorMessage = "Failed to load rooms"
            )
        }
    }

    /**
     * Capture RoomsScreen with populated rooms list.
     */
    @Test
    fun roomsScreen_populated() {
        captureScreen("RoomsScreen_Populated") {
            RoomsScreenPreview(
                isLoading = false,
                rooms = sampleRooms,
                errorMessage = null
            )
        }
    }

    /**
     * Capture RoomsScreen with rooms having various light states.
     */
    @Test
    fun roomsScreen_lightStates() {
        captureScreen("RoomsScreen_LightStates") {
            RoomsScreenPreview(
                isLoading = false,
                rooms = lightStateRooms,
                errorMessage = null
            )
        }
    }

    /**
     * Capture RoomsScreen with occupied rooms.
     */
    @Test
    fun roomsScreen_occupiedRooms() {
        captureScreen("RoomsScreen_OccupiedRooms") {
            RoomsScreenPreview(
                isLoading = false,
                rooms = occupiedRooms,
                errorMessage = null
            )
        }
    }

    /**
     * Capture RoomsScreen with high contrast mode.
     */
    @Test
    fun roomsScreen_highContrast() {
        captureScreenWithAccessibility(
            testName = "RoomsScreen_HighContrast",
            accessibilityConfig = highContrastAccessibilityConfig
        ) {
            RoomsScreenPreview(
                isLoading = false,
                rooms = sampleRooms,
                errorMessage = null
            )
        }
    }

    /**
     * Capture RoomsScreen with large font scale (200%).
     */
    @Test
    fun roomsScreen_largeFont() {
        captureScreenWithAccessibility(
            testName = "RoomsScreen_LargeFont",
            accessibilityConfig = largeFontAccessibilityConfig
        ) {
            RoomsScreenPreview(
                isLoading = false,
                rooms = sampleRooms.take(3),
                errorMessage = null
            )
        }
    }

    // Sample test data

    private val sampleRooms = listOf(
        createRoom("1", "Living Room", "Main Floor", 75, true),
        createRoom("2", "Primary Bedroom", "Upper Floor", 0, false),
        createRoom("3", "Office", "Main Floor", 100, true),
        createRoom("4", "Kitchen", "Main Floor", 50, false),
        createRoom("5", "Guest Room", "Upper Floor", 30, false)
    )

    private val lightStateRooms = listOf(
        createRoom("1", "Lights Full", "Main Floor", 100, false),
        createRoom("2", "Lights Dim", "Main Floor", 30, false),
        createRoom("3", "Lights Off", "Main Floor", 0, false)
    )

    private val occupiedRooms = listOf(
        createRoom("1", "Living Room", "Main Floor", 75, true),
        createRoom("2", "Office", "Main Floor", 100, true),
        createRoom("3", "Empty Room", "Upper Floor", 0, false)
    )

    private fun createRoom(
        id: String,
        name: String,
        floor: String,
        avgLight: Int,
        occupied: Boolean
    ) = RoomModel(
        id = id,
        name = name,
        floor = floor,
        lights = listOf(
            RoomModel.Light(id = "light_$id", name = "Main Light", level = avgLight)
        ),
        shades = emptyList(),
        occupied = occupied
    )
}

/**
 * Preview composable for RoomsScreen screenshot testing.
 */
@Composable
private fun RoomsScreenPreview(
    isLoading: Boolean,
    rooms: List<RoomModel>,
    errorMessage: String?
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Rooms") },
                navigationIcon = {
                    IconButton(onClick = {}) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    IconButton(onClick = {}) {
                        Icon(Icons.Default.Refresh, contentDescription = "Refresh")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = Void)
            )
        },
        containerColor = Void
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            when {
                isLoading -> {
                    CircularProgressIndicator(
                        modifier = Modifier.align(Alignment.Center),
                        color = Crystal
                    )
                }
                errorMessage != null -> {
                    Column(
                        modifier = Modifier
                            .align(Alignment.Center)
                            .padding(32.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Text(
                            text = errorMessage,
                            color = Color.White.copy(alpha = 0.7f)
                        )
                        Spacer(modifier = Modifier.height(16.dp))
                        Button(onClick = {}) {
                            Text("Retry")
                        }
                    }
                }
                rooms.isEmpty() -> {
                    Text(
                        text = "No rooms found",
                        modifier = Modifier.align(Alignment.Center),
                        color = Color.White.copy(alpha = 0.5f)
                    )
                }
                else -> {
                    LazyColumn(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        items(rooms, key = { it.id }) { room ->
                            RoomCard(
                                room = room,
                                onLightsOn = {},
                                onLightsOff = {},
                                onLightsDim = {}
                            )
                        }
                    }
                }
            }
        }
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
