/**
 * Kagami Quick Actions Widget — Medium (4x2) action buttons
 *
 * Colony: Nexus (e4) — Integration
 *
 * Provides quick access to:
 * - Movie Mode toggle
 * - Goodnight scene
 * - Lights control (On/Off)
 * - Current status display
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
import androidx.glance.action.clickable
import androidx.glance.appwidget.*
import androidx.glance.appwidget.action.ActionCallback
import androidx.glance.appwidget.action.actionRunCallback
import androidx.glance.appwidget.action.actionStartActivity
import androidx.glance.layout.*
import androidx.glance.semantics.contentDescription
import androidx.glance.semantics.semantics
import androidx.glance.text.*
import androidx.glance.unit.ColorProvider
import com.kagami.android.MainActivity
import kotlinx.coroutines.MainScope
import kotlinx.coroutines.launch

/**
 * Quick Actions Widget - 4x2 medium widget with action buttons
 */
class QuickActionsWidget : GlanceAppWidget() {

    override val sizeMode = SizeMode.Single

    override suspend fun provideGlance(context: Context, id: GlanceId) {
        val data = WidgetDataRepository.loadCachedData(context)

        provideContent {
            QuickActionsWidgetContent(
                safetyScore = data.safetyScore,
                movieMode = data.movieMode,
                isConnected = data.isConnected
            )
        }
    }
}

@Composable
private fun QuickActionsWidgetContent(
    safetyScore: Double?,
    movieMode: Boolean,
    isConnected: Boolean
) {
    val backgroundColor = Color(0xFF0A0A0D)  // Void
    val surfaceColor = Color(0xFF1E1E24)     // Surface
    val accentColor = Color(0xFF67D4E4)      // Crystal
    val safetyColor = getSafetyColorQuick(safetyScore)

    val statusText = if (isConnected) "Connected" else "Offline"
    val safetyText = safetyScore?.let { String.format("%.0f", it * 100) } ?: "Unknown"

    Column(
        modifier = GlanceModifier
            .fillMaxSize()
            .background(ColorProvider(backgroundColor))
            .cornerRadius(16.dp)
            .padding(12.dp)
            .semantics {
                contentDescription = "Kagami Quick Actions. $statusText. Safety score: $safetyText percent."
            }
    ) {
        // Header with branding and status
        Row(
            modifier = GlanceModifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalAlignment = Alignment.Start
        ) {
            Text(
                text = "Kagami",
                style = TextStyle(
                    color = ColorProvider(accentColor),
                    fontSize = 16.sp,
                    fontWeight = FontWeight.Bold
                )
            )

            Spacer(modifier = GlanceModifier.defaultWeight())

            // Safety score pill
            Row(
                modifier = GlanceModifier
                    .background(ColorProvider(safetyColor.copy(alpha = 0.2f)))
                    .cornerRadius(12.dp)
                    .padding(horizontal = 8.dp, vertical = 4.dp),
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
        }

        Spacer(modifier = GlanceModifier.height(12.dp))

        // Action buttons grid
        Row(
            modifier = GlanceModifier.fillMaxWidth(),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            // Movie Mode button
            ActionButton(
                icon = "M",
                label = "Movie",
                isActive = movieMode,
                activeColor = Color(0xFF9B7EBD),  // Nexus
                modifier = GlanceModifier.defaultWeight(),
                onClick = actionRunCallback<MovieModeAction>()
            )

            Spacer(modifier = GlanceModifier.width(8.dp))

            // Goodnight button
            ActionButton(
                icon = "N",
                label = "Night",
                isActive = false,
                activeColor = Color(0xFF7EB77F),  // Grove
                modifier = GlanceModifier.defaultWeight(),
                onClick = actionRunCallback<GoodnightAction>()
            )

            Spacer(modifier = GlanceModifier.width(8.dp))

            // Lights On button
            ActionButton(
                icon = "L",
                label = "Lights",
                isActive = false,
                activeColor = Color(0xFFF59E0B),  // Beacon
                modifier = GlanceModifier.defaultWeight(),
                onClick = actionRunCallback<LightsOnAction>()
            )

            Spacer(modifier = GlanceModifier.width(8.dp))

            // Lights Off button
            ActionButton(
                icon = "O",
                label = "Off",
                isActive = false,
                activeColor = Color(0xFF666666),
                modifier = GlanceModifier.defaultWeight(),
                onClick = actionRunCallback<LightsOffAction>()
            )
        }

        Spacer(modifier = GlanceModifier.height(8.dp))

        // Status bar
        Row(
            modifier = GlanceModifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            // Connection indicator
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
                text = if (isConnected) "Connected" else "Offline",
                style = TextStyle(
                    color = ColorProvider(Color(0xFF888888)),
                    fontSize = 10.sp
                )
            )

            Spacer(modifier = GlanceModifier.defaultWeight())

            // Open app button
            Text(
                text = "Open App",
                style = TextStyle(
                    color = ColorProvider(accentColor),
                    fontSize = 10.sp
                ),
                modifier = GlanceModifier.clickable(actionStartActivity(Intent(LocalContext.current, MainActivity::class.java)))
            )
        }
    }
}

@Composable
private fun ActionButton(
    icon: String,
    label: String,
    isActive: Boolean,
    activeColor: Color,
    modifier: GlanceModifier = GlanceModifier,
    onClick: androidx.glance.action.Action
) {
    val bgColor = if (isActive) activeColor.copy(alpha = 0.3f) else Color(0xFF1E1E24)
    val textColor = if (isActive) activeColor else Color(0xFFCCCCCC)
    val activeStatus = if (isActive) "active" else "inactive"

    Column(
        modifier = modifier
            .background(ColorProvider(bgColor))
            .cornerRadius(12.dp)
            .clickable(onClick)
            .padding(vertical = 12.dp, horizontal = 8.dp)
            .semantics {
                contentDescription = "$label button. Currently $activeStatus. Tap to activate."
            },
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = icon,
            style = TextStyle(
                color = ColorProvider(textColor),
                fontSize = 20.sp,
                fontWeight = FontWeight.Bold
            )
        )

        Spacer(modifier = GlanceModifier.height(4.dp))

        Text(
            text = label,
            style = TextStyle(
                color = ColorProvider(textColor.copy(alpha = 0.8f)),
                fontSize = 10.sp
            )
        )
    }
}

private fun getSafetyColorQuick(score: Double?): Color = when {
    score == null -> Color(0xFF666666)
    score >= 0.5 -> Color(0xFF00FF87)
    score >= 0.0 -> Color(0xFFFFD600)
    else -> Color(0xFFFF4545)
}

/**
 * Glance widget receiver for Quick Actions Widget
 */
class QuickActionsWidgetReceiver : GlanceAppWidgetReceiver() {
    override val glanceAppWidget: GlanceAppWidget = QuickActionsWidget()

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
        const val ACTION_REFRESH = "com.kagami.android.widgets.REFRESH_QUICK_ACTIONS"
    }
}

// Action callbacks

class MovieModeAction : ActionCallback {
    override suspend fun onAction(
        context: Context,
        glanceId: GlanceId,
        parameters: ActionParameters
    ) {
        WidgetDataRepository.executeScene("movie_mode")
        WidgetDataRepository.refreshData(context)
        QuickActionsWidget().update(context, glanceId)
    }
}

class GoodnightAction : ActionCallback {
    override suspend fun onAction(
        context: Context,
        glanceId: GlanceId,
        parameters: ActionParameters
    ) {
        WidgetDataRepository.executeScene("goodnight")
        WidgetDataRepository.refreshData(context)
        QuickActionsWidget().update(context, glanceId)
    }
}

class LightsOnAction : ActionCallback {
    override suspend fun onAction(
        context: Context,
        glanceId: GlanceId,
        parameters: ActionParameters
    ) {
        WidgetDataRepository.setLights(80)
        WidgetDataRepository.refreshData(context)
        QuickActionsWidget().update(context, glanceId)
    }
}

class LightsOffAction : ActionCallback {
    override suspend fun onAction(
        context: Context,
        glanceId: GlanceId,
        parameters: ActionParameters
    ) {
        WidgetDataRepository.setLights(0)
        WidgetDataRepository.refreshData(context)
        QuickActionsWidget().update(context, glanceId)
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
