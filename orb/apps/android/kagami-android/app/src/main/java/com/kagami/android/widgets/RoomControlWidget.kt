/**
 * Kagami Room Control Widget — Large (4x4) room-by-room control
 *
 * Colony: Nexus (e4) — Integration
 *
 * Features:
 * - Per-room light controls
 * - Occupancy indicators
 * - Quick scene access
 * - Scrollable room list
 *
 * h(x) >= 0. Always.
 */

package com.kagami.android.widgets

import android.content.Context
import android.content.Intent
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.glance.*
import androidx.glance.action.ActionParameters
import androidx.glance.action.actionParametersOf
import androidx.glance.action.clickable
import androidx.glance.appwidget.*
import androidx.glance.appwidget.action.ActionCallback
import androidx.glance.appwidget.action.actionRunCallback
import androidx.glance.appwidget.action.actionStartActivity
import androidx.glance.appwidget.lazy.LazyColumn
import androidx.glance.appwidget.lazy.items
import androidx.glance.layout.*
import androidx.glance.semantics.contentDescription
import androidx.glance.semantics.semantics
import androidx.glance.text.*
import androidx.glance.unit.ColorProvider
import com.kagami.android.MainActivity
import kotlinx.coroutines.MainScope
import kotlinx.coroutines.launch

// Action parameter keys
private val roomIdKey = ActionParameters.Key<String>("room_id")
private val roomNameKey = ActionParameters.Key<String>("room_name")
private val lightLevelKey = ActionParameters.Key<Int>("light_level")

/**
 * Room Control Widget - 4x4 large widget with per-room controls
 */
class RoomControlWidget : GlanceAppWidget() {

    override val sizeMode = SizeMode.Single

    override suspend fun provideGlance(context: Context, id: GlanceId) {
        val data = WidgetDataRepository.loadCachedData(context)

        provideContent {
            RoomControlWidgetContent(
                rooms = data.rooms,
                safetyScore = data.safetyScore,
                isConnected = data.isConnected
            )
        }
    }
}

@Composable
private fun RoomControlWidgetContent(
    rooms: List<WidgetRoomData>,
    safetyScore: Double?,
    isConnected: Boolean
) {
    val backgroundColor = Color(0xFF0A0A0D)  // Void
    val accentColor = Color(0xFF67D4E4)      // Crystal
    val safetyColor = getSafetyColorRoom(safetyScore)
    val statusText = if (isConnected) "Online" else "Offline"

    Column(
        modifier = GlanceModifier
            .fillMaxSize()
            .background(ColorProvider(backgroundColor))
            .cornerRadius(16.dp)
            .padding(12.dp)
            .semantics {
                contentDescription = "Kagami Room Control. ${rooms.size} rooms. $statusText."
            }
    ) {
        // Header
        Row(
            modifier = GlanceModifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column {
                Text(
                    text = "Kagami Home",
                    style = TextStyle(
                        color = ColorProvider(accentColor),
                        fontSize = 18.sp,
                        fontWeight = FontWeight.Bold
                    )
                )
                Text(
                    text = "${rooms.size} rooms",
                    style = TextStyle(
                        color = ColorProvider(Color(0xFF888888)),
                        fontSize = 12.sp
                    )
                )
            }

            Spacer(modifier = GlanceModifier.defaultWeight())

            // Safety and connection status
            Column(horizontalAlignment = Alignment.End) {
                Row(
                    modifier = GlanceModifier
                        .background(ColorProvider(safetyColor.copy(alpha = 0.2f)))
                        .cornerRadius(8.dp)
                        .padding(horizontal = 8.dp, vertical = 2.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "h(x)=",
                        style = TextStyle(
                            color = ColorProvider(safetyColor.copy(alpha = 0.7f)),
                            fontSize = 10.sp
                        )
                    )
                    Text(
                        text = safetyScore?.let { String.format("%.2f", it) } ?: "--",
                        style = TextStyle(
                            color = ColorProvider(safetyColor),
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Bold
                        )
                    )
                }

                Spacer(modifier = GlanceModifier.height(2.dp))

                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = GlanceModifier
                            .size(6.dp)
                            .background(
                                ColorProvider(
                                    if (isConnected) Color(0xFF00FF87) else Color(0xFF666666)
                                )
                            )
                            .cornerRadius(3.dp)
                    ) {}
                    Spacer(modifier = GlanceModifier.width(4.dp))
                    Text(
                        text = if (isConnected) "Online" else "Offline",
                        style = TextStyle(
                            color = ColorProvider(Color(0xFF888888)),
                            fontSize = 10.sp
                        )
                    )
                }
            }
        }

        Spacer(modifier = GlanceModifier.height(12.dp))

        // Quick actions row
        Row(
            modifier = GlanceModifier.fillMaxWidth(),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            QuickSceneButton(
                label = "All On",
                color = Color(0xFFF59E0B),
                onClick = actionRunCallback<AllLightsOnAction>()
            )

            Spacer(modifier = GlanceModifier.width(8.dp))

            QuickSceneButton(
                label = "All Off",
                color = Color(0xFF666666),
                onClick = actionRunCallback<AllLightsOffAction>()
            )

            Spacer(modifier = GlanceModifier.width(8.dp))

            QuickSceneButton(
                label = "Movie",
                color = Color(0xFF9B7EBD),
                onClick = actionRunCallback<MovieModeAction>()
            )

            Spacer(modifier = GlanceModifier.width(8.dp))

            QuickSceneButton(
                label = "Night",
                color = Color(0xFF7EB77F),
                onClick = actionRunCallback<GoodnightAction>()
            )
        }

        Spacer(modifier = GlanceModifier.height(12.dp))

        // Room list
        if (rooms.isEmpty()) {
            Box(
                modifier = GlanceModifier
                    .fillMaxWidth()
                    .defaultWeight()
                    .background(ColorProvider(Color(0xFF1E1E24)))
                    .cornerRadius(12.dp),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = if (isConnected) "Loading rooms..." else "Connect to view rooms",
                    style = TextStyle(
                        color = ColorProvider(Color(0xFF888888)),
                        fontSize = 14.sp
                    )
                )
            }
        } else {
            LazyColumn(
                modifier = GlanceModifier
                    .fillMaxWidth()
                    .defaultWeight()
            ) {
                items(rooms) { room ->
                    RoomRow(room = room)
                    Spacer(modifier = GlanceModifier.height(6.dp))
                }
            }
        }

        Spacer(modifier = GlanceModifier.height(8.dp))

        // Footer with app link
        Row(
            modifier = GlanceModifier.fillMaxWidth(),
            horizontalAlignment = Alignment.End
        ) {
            Text(
                text = "Open Kagami App",
                style = TextStyle(
                    color = ColorProvider(accentColor),
                    fontSize = 12.sp
                ),
                modifier = GlanceModifier.clickable(actionStartActivity(Intent(LocalContext.current, MainActivity::class.java)))
            )
        }
    }
}

@Composable
private fun QuickSceneButton(
    label: String,
    color: Color,
    onClick: androidx.glance.action.Action
) {
    Box(
        modifier = GlanceModifier
            .background(ColorProvider(color.copy(alpha = 0.2f)))
            .cornerRadius(8.dp)
            .clickable(onClick)
            .padding(horizontal = 12.dp, vertical = 6.dp)
            .semantics {
                contentDescription = "$label button. Tap to activate."
            },
        contentAlignment = Alignment.Center
    ) {
        Text(
            text = label,
            style = TextStyle(
                color = ColorProvider(color),
                fontSize = 11.sp,
                fontWeight = FontWeight.Medium
            )
        )
    }
}

@Composable
private fun RoomRow(room: WidgetRoomData) {
    val bgColor = Color(0xFF1E1E24)
    val lightColor = when {
        room.avgLightLevel == 0 -> Color(0xFF444444)
        room.avgLightLevel < 50 -> Color(0xFFD4AF37)  // Forge (dim)
        else -> Color(0xFFF59E0B)                      // Beacon (bright)
    }
    val occupiedColor = if (room.occupied) Color(0xFF00FF87) else Color(0xFF333333)
    val lightStatus = when {
        room.avgLightLevel == 0 -> "lights off"
        room.avgLightLevel < 50 -> "${room.avgLightLevel}% dim"
        else -> "${room.avgLightLevel}% bright"
    }
    val occupancyStatus = if (room.occupied) "occupied" else "unoccupied"

    Row(
        modifier = GlanceModifier
            .fillMaxWidth()
            .background(ColorProvider(bgColor))
            .cornerRadius(10.dp)
            .padding(10.dp)
            .semantics {
                contentDescription = "${room.name}. $lightStatus. $occupancyStatus."
            },
        verticalAlignment = Alignment.CenterVertically
    ) {
        // Occupancy indicator
        Box(
            modifier = GlanceModifier
                .size(8.dp)
                .background(ColorProvider(occupiedColor))
                .cornerRadius(4.dp)
        ) {}

        Spacer(modifier = GlanceModifier.width(8.dp))

        // Room name and status
        Column(modifier = GlanceModifier.defaultWeight()) {
            Text(
                text = room.name,
                style = TextStyle(
                    color = ColorProvider(Color.White),
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Medium
                )
            )
            Text(
                text = when {
                    room.avgLightLevel == 0 -> "Off"
                    room.avgLightLevel < 50 -> "Dim (${room.avgLightLevel}%)"
                    else -> "On (${room.avgLightLevel}%)"
                },
                style = TextStyle(
                    color = ColorProvider(lightColor),
                    fontSize = 11.sp
                )
            )
        }

        // Light control buttons
        Row {
            // Dim button
            Box(
                modifier = GlanceModifier
                    .size(32.dp)
                    .background(ColorProvider(Color(0xFF2A2A32)))
                    .cornerRadius(8.dp)
                    .clickable(
                        actionRunCallback<SetRoomLightAction>(
                            actionParametersOf(
                                roomIdKey to room.id,
                                roomNameKey to room.name,
                                lightLevelKey to 30
                            )
                        )
                    ),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = "-",
                    style = TextStyle(
                        color = ColorProvider(Color(0xFFD4AF37)),
                        fontSize = 18.sp,
                        fontWeight = FontWeight.Bold
                    )
                )
            }

            Spacer(modifier = GlanceModifier.width(4.dp))

            // On button
            Box(
                modifier = GlanceModifier
                    .size(32.dp)
                    .background(ColorProvider(Color(0xFF2A2A32)))
                    .cornerRadius(8.dp)
                    .clickable(
                        actionRunCallback<SetRoomLightAction>(
                            actionParametersOf(
                                roomIdKey to room.id,
                                roomNameKey to room.name,
                                lightLevelKey to 80
                            )
                        )
                    ),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = "+",
                    style = TextStyle(
                        color = ColorProvider(Color(0xFFF59E0B)),
                        fontSize = 18.sp,
                        fontWeight = FontWeight.Bold
                    )
                )
            }

            Spacer(modifier = GlanceModifier.width(4.dp))

            // Off button
            Box(
                modifier = GlanceModifier
                    .size(32.dp)
                    .background(ColorProvider(Color(0xFF2A2A32)))
                    .cornerRadius(8.dp)
                    .clickable(
                        actionRunCallback<SetRoomLightAction>(
                            actionParametersOf(
                                roomIdKey to room.id,
                                roomNameKey to room.name,
                                lightLevelKey to 0
                            )
                        )
                    ),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = "O",
                    style = TextStyle(
                        color = ColorProvider(Color(0xFF666666)),
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Bold
                    )
                )
            }
        }
    }
}

private fun getSafetyColorRoom(score: Double?): Color = when {
    score == null -> Color(0xFF666666)
    score >= 0.5 -> Color(0xFF00FF87)
    score >= 0.0 -> Color(0xFFFFD600)
    else -> Color(0xFFFF4545)
}

/**
 * Glance widget receiver for Room Control Widget
 */
class RoomControlWidgetReceiver : GlanceAppWidgetReceiver() {
    override val glanceAppWidget: GlanceAppWidget = RoomControlWidget()

    override fun onEnabled(context: Context) {
        super.onEnabled(context)
        WidgetUpdateWorker.schedulePeriodicUpdate(context)
    }

    override fun onReceive(context: Context, intent: Intent) {
        super.onReceive(context, intent)
        if (intent.action == ACTION_REFRESH) {
            WidgetUpdateWorker.requestImmediateUpdate(context)
        }
    }

    companion object {
        const val ACTION_REFRESH = "com.kagami.android.widgets.REFRESH_ROOM_CONTROL"
    }
}

// Action callbacks

class AllLightsOnAction : ActionCallback {
    override suspend fun onAction(
        context: Context,
        glanceId: GlanceId,
        parameters: ActionParameters
    ) {
        WidgetDataRepository.setLights(80)
        WidgetDataRepository.refreshData(context)
        RoomControlWidget().update(context, glanceId)
    }
}

class AllLightsOffAction : ActionCallback {
    override suspend fun onAction(
        context: Context,
        glanceId: GlanceId,
        parameters: ActionParameters
    ) {
        WidgetDataRepository.setLights(0)
        WidgetDataRepository.refreshData(context)
        RoomControlWidget().update(context, glanceId)
    }
}

class SetRoomLightAction : ActionCallback {
    override suspend fun onAction(
        context: Context,
        glanceId: GlanceId,
        parameters: ActionParameters
    ) {
        val roomName = parameters[roomNameKey] ?: return
        val level = parameters[lightLevelKey] ?: return

        WidgetDataRepository.setLights(level, listOf(roomName))
        WidgetDataRepository.refreshData(context)
        RoomControlWidget().update(context, glanceId)
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
