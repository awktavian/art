/**
 * Kagami Dashboard Widget — Large (4x4) full home dashboard
 *
 * Colony: Nexus (e4) — Integration
 *
 * Full-featured widget providing:
 * - Complete home status overview
 * - Quick scene activation
 * - Room controls
 * - Safety score monitoring
 * - Weather/time integration
 * - Dynamic color support
 *
 * h(x) >= 0. Always.
 */

package com.kagami.android.widgets

import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.glance.*
import androidx.glance.action.ActionParameters
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
import androidx.compose.ui.unit.DpSize
import com.kagami.android.MainActivity
import java.text.SimpleDateFormat
import java.util.*

// =============================================================================
// DASHBOARD WIDGET
// =============================================================================

/**
 * Dashboard Widget - Large (4x4) full home dashboard.
 * Shows complete home status with all controls.
 */
class DashboardWidget : GlanceAppWidget() {

    override val sizeMode = SizeMode.Responsive(
        setOf(
            DpSize(200.dp, 200.dp),  // Small
            DpSize(300.dp, 300.dp),  // Medium
            DpSize(400.dp, 400.dp)   // Large
        )
    )

    override suspend fun provideGlance(context: Context, id: GlanceId) {
        val data = WidgetDataRepository.loadCachedData(context)
        val currentTime = SimpleDateFormat("h:mm a", Locale.getDefault()).format(Date())
        val currentDate = SimpleDateFormat("EEEE, MMM d", Locale.getDefault()).format(Date())

        provideContent {
            DashboardWidgetContent(
                data = data,
                currentTime = currentTime,
                currentDate = currentDate,
                size = LocalSize.current
            )
        }
    }
}

@Composable
private fun DashboardWidgetContent(
    data: KagamiWidgetData,
    currentTime: String,
    currentDate: String,
    size: DpSize
) {
    // Dynamic color support - use wallpaper-based colors on Android 12+
    val backgroundColor = Color(0xFF0A0A0F)  // Void
    val surfaceColor = Color(0xFF1E1E24)     // Surface
    val accentColor = Color(0xFF67D4E4)      // Crystal
    val safetyColor = getSafetyColorDashboard(data.safetyScore)

    val isLarge = size.width >= 350.dp
    val isMedium = size.width >= 250.dp

    Column(
        modifier = GlanceModifier
            .fillMaxSize()
            .background(ColorProvider(backgroundColor))
            .cornerRadius(20.dp)
            .padding(16.dp)
            .semantics {
                contentDescription = buildDashboardDescription(data, currentTime)
            }
    ) {
        // Header with time and status
        DashboardHeader(
            currentTime = currentTime,
            currentDate = currentDate,
            isConnected = data.isConnected,
            safetyScore = data.safetyScore,
            safetyColor = safetyColor,
            accentColor = accentColor
        )

        Spacer(modifier = GlanceModifier.height(16.dp))

        // Quick scenes row
        QuickScenesRow(
            movieModeActive = data.movieMode,
            isLarge = isLarge
        )

        if (isLarge || isMedium) {
            Spacer(modifier = GlanceModifier.height(16.dp))

            // Room controls (if large enough)
            RoomControlsSection(
                rooms = data.rooms,
                maxRooms = if (isLarge) 4 else 2
            )
        }

        Spacer(modifier = GlanceModifier.defaultWeight())

        // Footer with app link
        DashboardFooter(accentColor = accentColor)
    }
}

@Composable
private fun DashboardHeader(
    currentTime: String,
    currentDate: String,
    isConnected: Boolean,
    safetyScore: Double?,
    safetyColor: Color,
    accentColor: Color
) {
    Row(
        modifier = GlanceModifier.fillMaxWidth(),
        verticalAlignment = Alignment.Top
    ) {
        // Branding and time
        Column {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = "鏡",
                    style = TextStyle(
                        color = ColorProvider(accentColor),
                        fontSize = 20.sp,
                        fontWeight = FontWeight.Bold
                    )
                )
                Spacer(modifier = GlanceModifier.width(8.dp))
                Text(
                    text = "Kagami",
                    style = TextStyle(
                        color = ColorProvider(accentColor),
                        fontSize = 18.sp,
                        fontWeight = FontWeight.Medium
                    )
                )
            }

            Spacer(modifier = GlanceModifier.height(4.dp))

            Text(
                text = currentTime,
                style = TextStyle(
                    color = ColorProvider(Color.White),
                    fontSize = 28.sp,
                    fontWeight = FontWeight.Bold
                )
            )

            Text(
                text = currentDate,
                style = TextStyle(
                    color = ColorProvider(Color(0xFF888888)),
                    fontSize = 12.sp
                )
            )
        }

        Spacer(modifier = GlanceModifier.defaultWeight())

        // Status column
        Column(horizontalAlignment = Alignment.End) {
            // Safety score badge
            SafetyBadge(
                score = safetyScore,
                color = safetyColor
            )

            Spacer(modifier = GlanceModifier.height(8.dp))

            // Connection status
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    modifier = GlanceModifier
                        .size(8.dp)
                        .background(
                            ColorProvider(
                                if (isConnected) Color(0xFF00FF87) else Color(0xFF666666)
                            )
                        )
                        .cornerRadius(4.dp)
                ) {}
                Spacer(modifier = GlanceModifier.width(4.dp))
                Text(
                    text = if (isConnected) "Online" else "Offline",
                    style = TextStyle(
                        color = ColorProvider(Color(0xFF888888)),
                        fontSize = 11.sp
                    )
                )
            }
        }
    }
}

@Composable
private fun SafetyBadge(
    score: Double?,
    color: Color
) {
    Row(
        modifier = GlanceModifier
            .background(ColorProvider(color.copy(alpha = 0.15f)))
            .cornerRadius(12.dp)
            .padding(horizontal = 10.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = "h(x)",
            style = TextStyle(
                color = ColorProvider(color.copy(alpha = 0.8f)),
                fontSize = 11.sp
            )
        )
        Spacer(modifier = GlanceModifier.width(4.dp))
        Text(
            text = score?.let { String.format("%.2f", it) } ?: "--",
            style = TextStyle(
                color = ColorProvider(color),
                fontSize = 14.sp,
                fontWeight = FontWeight.Bold
            )
        )
    }
}

@Composable
private fun QuickScenesRow(
    movieModeActive: Boolean,
    isLarge: Boolean
) {
    Column {
        Text(
            text = "Quick Scenes",
            style = TextStyle(
                color = ColorProvider(Color(0xFF888888)),
                fontSize = 11.sp,
                fontWeight = FontWeight.Medium
            )
        )

        Spacer(modifier = GlanceModifier.height(8.dp))

        Row(
            modifier = GlanceModifier.fillMaxWidth(),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            // Good Morning
            SceneButton(
                icon = "☀️",
                label = "Morning",
                color = Color(0xFFF59E0B),  // Beacon
                onClick = actionRunCallback<GoodMorningAction>(),
                modifier = GlanceModifier.defaultWeight()
            )

            Spacer(modifier = GlanceModifier.width(8.dp))

            // Movie Mode
            SceneButton(
                icon = "🎬",
                label = "Movie",
                color = Color(0xFF9B7EBD),  // Nexus
                isActive = movieModeActive,
                onClick = actionRunCallback<MovieModeAction>(),
                modifier = GlanceModifier.defaultWeight()
            )

            Spacer(modifier = GlanceModifier.width(8.dp))

            // Focus
            SceneButton(
                icon = "🎯",
                label = "Focus",
                color = Color(0xFF4ECDC4),  // Flow
                onClick = actionRunCallback<FocusModeAction>(),
                modifier = GlanceModifier.defaultWeight()
            )

            Spacer(modifier = GlanceModifier.width(8.dp))

            // Goodnight
            SceneButton(
                icon = "🌙",
                label = "Night",
                color = Color(0xFF7EB77F),  // Grove
                onClick = actionRunCallback<GoodnightAction>(),
                modifier = GlanceModifier.defaultWeight()
            )
        }
    }
}

@Composable
private fun SceneButton(
    icon: String,
    label: String,
    color: Color,
    isActive: Boolean = false,
    onClick: androidx.glance.action.Action,
    modifier: GlanceModifier = GlanceModifier
) {
    val bgColor = if (isActive) color.copy(alpha = 0.3f) else Color(0xFF1E1E24)
    val textColor = if (isActive) color else Color(0xFFCCCCCC)
    val stateDesc = if (isActive) "active" else "tap to activate"

    Column(
        modifier = modifier
            .background(ColorProvider(bgColor))
            .cornerRadius(12.dp)
            .clickable(onClick)
            .padding(vertical = 12.dp, horizontal = 6.dp)
            .semantics {
                contentDescription = "$label scene. $stateDesc."
            },
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(
            text = icon,
            style = TextStyle(
                fontSize = 20.sp
            )
        )

        Spacer(modifier = GlanceModifier.height(4.dp))

        Text(
            text = label,
            style = TextStyle(
                color = ColorProvider(textColor),
                fontSize = 10.sp,
                fontWeight = FontWeight.Medium
            )
        )
    }
}

@Composable
private fun RoomControlsSection(
    rooms: List<WidgetRoomData>,
    maxRooms: Int
) {
    Column {
        Row(
            modifier = GlanceModifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "Rooms",
                style = TextStyle(
                    color = ColorProvider(Color(0xFF888888)),
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Medium
                )
            )

            Spacer(modifier = GlanceModifier.defaultWeight())

            // All lights controls
            Row {
                Box(
                    modifier = GlanceModifier
                        .background(ColorProvider(Color(0xFF1E1E24)))
                        .cornerRadius(8.dp)
                        .clickable(actionRunCallback<AllLightsOnAction>())
                        .padding(horizontal = 8.dp, vertical = 4.dp)
                ) {
                    Text(
                        text = "All On",
                        style = TextStyle(
                            color = ColorProvider(Color(0xFFF59E0B)),
                            fontSize = 10.sp
                        )
                    )
                }

                Spacer(modifier = GlanceModifier.width(4.dp))

                Box(
                    modifier = GlanceModifier
                        .background(ColorProvider(Color(0xFF1E1E24)))
                        .cornerRadius(8.dp)
                        .clickable(actionRunCallback<AllLightsOffAction>())
                        .padding(horizontal = 8.dp, vertical = 4.dp)
                ) {
                    Text(
                        text = "All Off",
                        style = TextStyle(
                            color = ColorProvider(Color(0xFF666666)),
                            fontSize = 10.sp
                        )
                    )
                }
            }
        }

        Spacer(modifier = GlanceModifier.height(8.dp))

        if (rooms.isEmpty()) {
            Box(
                modifier = GlanceModifier
                    .fillMaxWidth()
                    .background(ColorProvider(Color(0xFF1E1E24)))
                    .cornerRadius(12.dp)
                    .padding(16.dp),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = "No rooms configured",
                    style = TextStyle(
                        color = ColorProvider(Color(0xFF666666)),
                        fontSize = 12.sp
                    )
                )
            }
        } else {
            Column {
                rooms.take(maxRooms).forEachIndexed { index, room ->
                    CompactRoomRow(room = room)
                    if (index < rooms.size - 1 && index < maxRooms - 1) {
                        Spacer(modifier = GlanceModifier.height(6.dp))
                    }
                }

                if (rooms.size > maxRooms) {
                    Spacer(modifier = GlanceModifier.height(4.dp))
                    Text(
                        text = "+${rooms.size - maxRooms} more rooms",
                        style = TextStyle(
                            color = ColorProvider(Color(0xFF666666)),
                            fontSize = 10.sp
                        )
                    )
                }
            }
        }
    }
}

@Composable
private fun CompactRoomRow(room: WidgetRoomData) {
    val lightColor = when {
        room.avgLightLevel == 0 -> Color(0xFF444444)
        room.avgLightLevel < 50 -> Color(0xFFD4AF37)
        else -> Color(0xFFF59E0B)
    }

    Row(
        modifier = GlanceModifier
            .fillMaxWidth()
            .background(ColorProvider(Color(0xFF1E1E24)))
            .cornerRadius(10.dp)
            .padding(10.dp)
            .semantics {
                contentDescription = "${room.name}. Lights at ${room.avgLightLevel} percent."
            },
        verticalAlignment = Alignment.CenterVertically
    ) {
        // Occupancy indicator
        Box(
            modifier = GlanceModifier
                .size(6.dp)
                .background(
                    ColorProvider(
                        if (room.occupied) Color(0xFF00FF87) else Color(0xFF333333)
                    )
                )
                .cornerRadius(3.dp)
        ) {}

        Spacer(modifier = GlanceModifier.width(8.dp))

        // Room name
        Text(
            text = room.name,
            style = TextStyle(
                color = ColorProvider(Color.White),
                fontSize = 13.sp,
                fontWeight = FontWeight.Medium
            ),
            modifier = GlanceModifier.defaultWeight()
        )

        // Light level
        Text(
            text = "${room.avgLightLevel}%",
            style = TextStyle(
                color = ColorProvider(lightColor),
                fontSize = 12.sp,
                fontWeight = FontWeight.Medium
            )
        )
    }
}

@Composable
private fun DashboardFooter(accentColor: Color) {
    Row(
        modifier = GlanceModifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically
    ) {
        // Refresh button
        Box(
            modifier = GlanceModifier
                .background(ColorProvider(Color(0xFF1E1E24)))
                .cornerRadius(8.dp)
                .clickable(actionRunCallback<RefreshDashboardAction>())
                .padding(horizontal = 12.dp, vertical = 6.dp)
        ) {
            Text(
                text = "↻ Refresh",
                style = TextStyle(
                    color = ColorProvider(Color(0xFF888888)),
                    fontSize = 11.sp
                )
            )
        }

        Spacer(modifier = GlanceModifier.defaultWeight())

        // Open app
        Text(
            text = "Open Kagami →",
            style = TextStyle(
                color = ColorProvider(accentColor),
                fontSize = 12.sp,
                fontWeight = FontWeight.Medium
            ),
            modifier = GlanceModifier.clickable(
                actionStartActivity(Intent(LocalContext.current, MainActivity::class.java))
            )
        )
    }
}

private fun getSafetyColorDashboard(score: Double?): Color = when {
    score == null -> Color(0xFF666666)
    score >= 0.5 -> Color(0xFF00FF87)
    score >= 0.0 -> Color(0xFFFFD600)
    else -> Color(0xFFFF4545)
}

private fun buildDashboardDescription(data: KagamiWidgetData, time: String): String {
    val status = if (data.isConnected) "connected" else "offline"
    val safety = data.safetyScore?.let { "${(it * 100).toInt()} percent" } ?: "unknown"
    return "Kagami Dashboard. Time: $time. Status: $status. Safety score: $safety."
}

// =============================================================================
// WIDGET RECEIVER
// =============================================================================

/**
 * Glance widget receiver for Dashboard Widget
 */
class DashboardWidgetReceiver : GlanceAppWidgetReceiver() {
    override val glanceAppWidget: GlanceAppWidget = DashboardWidget()

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
        const val ACTION_REFRESH = "com.kagami.android.widgets.REFRESH_DASHBOARD"
    }
}

// =============================================================================
// ACTION CALLBACKS
// =============================================================================

class GoodMorningAction : ActionCallback {
    override suspend fun onAction(
        context: Context,
        glanceId: GlanceId,
        parameters: ActionParameters
    ) {
        WidgetDataRepository.executeScene("good_morning")
        WidgetDataRepository.refreshData(context)
        DashboardWidget().update(context, glanceId)
    }
}

class FocusModeAction : ActionCallback {
    override suspend fun onAction(
        context: Context,
        glanceId: GlanceId,
        parameters: ActionParameters
    ) {
        WidgetDataRepository.executeScene("focus")
        WidgetDataRepository.refreshData(context)
        DashboardWidget().update(context, glanceId)
    }
}

class RefreshDashboardAction : ActionCallback {
    override suspend fun onAction(
        context: Context,
        glanceId: GlanceId,
        parameters: ActionParameters
    ) {
        WidgetDataRepository.refreshData(context)
        DashboardWidget().update(context, glanceId)
    }
}

/*
 * Mirror
 * The dashboard is the home's heartbeat.
 * h(x) >= 0. Always.
 */
