/**
 * Kagami Safety Widget — Small (2x1) safety score display
 *
 * Colony: Nexus (e4) — Integration
 *
 * Shows:
 * - Current h(x) safety score
 * - Color-coded safety status (green/yellow/red)
 * - Connection status indicator
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
 * Safety Widget - 2x1 small widget showing h(x) safety score
 */
class SafetyWidget : GlanceAppWidget() {

    override val sizeMode = SizeMode.Single

    override suspend fun provideGlance(context: Context, id: GlanceId) {
        val data = WidgetDataRepository.loadCachedData(context)

        provideContent {
            SafetyWidgetContent(
                safetyScore = data.safetyScore,
                isConnected = data.isConnected
            )
        }
    }
}

@Composable
private fun SafetyWidgetContent(
    safetyScore: Double?,
    isConnected: Boolean
) {
    val backgroundColor = Color(0xFF0A0A0D) // Void
    val safetyColor = getSafetyColor(safetyScore)
    val scoreText = safetyScore?.let { String.format("%.2f", it) } ?: "--"
    val statusText = getSafetyStatusText(safetyScore)
    val connectionText = if (isConnected) "connected" else "offline"
    val scorePercent = safetyScore?.let { "${String.format("%.0f", it * 100)} percent" } ?: "unknown"

    Box(
        modifier = GlanceModifier
            .fillMaxSize()
            .background(ColorProvider(backgroundColor))
            .cornerRadius(16.dp)
            .clickable(actionStartActivity(Intent(LocalContext.current, MainActivity::class.java)))
            .padding(12.dp)
            .semantics {
                contentDescription = "Kagami Safety Widget. Status: $statusText. Safety score: $scorePercent. $connectionText. Tap to open app."
            }
    ) {
        Row(
            modifier = GlanceModifier.fillMaxSize(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            // Safety indicator circle
            Box(
                modifier = GlanceModifier
                    .size(48.dp)
                    .background(ColorProvider(safetyColor.copy(alpha = 0.2f)))
                    .cornerRadius(24.dp),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = "h",
                    style = TextStyle(
                        color = ColorProvider(safetyColor),
                        fontSize = 24.sp,
                        fontWeight = FontWeight.Bold
                    )
                )
            }

            Spacer(modifier = GlanceModifier.width(12.dp))

            // Score and status
            Column(
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = scoreText,
                    style = TextStyle(
                        color = ColorProvider(Color.White),
                        fontSize = 28.sp,
                        fontWeight = FontWeight.Bold
                    )
                )

                Row(verticalAlignment = Alignment.CenterVertically) {
                    // Connection dot
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
                        text = getSafetyStatusText(safetyScore),
                        style = TextStyle(
                            color = ColorProvider(safetyColor),
                            fontSize = 12.sp
                        )
                    )
                }
            }
        }
    }
}

private fun getSafetyColor(score: Double?): Color = when {
    score == null -> Color(0xFF666666)
    score >= 0.5 -> Color(0xFF00FF87)  // SafetyOk
    score >= 0.0 -> Color(0xFFFFD600)  // SafetyCaution
    else -> Color(0xFFFF4545)          // SafetyViolation
}

private fun getSafetyStatusText(score: Double?): String = when {
    score == null -> "Offline"
    score >= 0.5 -> "Safe"
    score >= 0.0 -> "Caution"
    else -> "Alert"
}

/**
 * Glance widget receiver for Safety Widget
 */
class SafetyWidgetReceiver : GlanceAppWidgetReceiver() {
    override val glanceAppWidget: GlanceAppWidget = SafetyWidget()

    override fun onEnabled(context: Context) {
        super.onEnabled(context)
        // Schedule periodic updates when widget is added
        WidgetUpdateWorker.schedulePeriodicUpdate(context)
    }

    override fun onReceive(context: Context, intent: Intent) {
        super.onReceive(context, intent)

        // Handle refresh action
        if (intent.action == ACTION_REFRESH) {
            WidgetUpdateWorker.requestImmediateUpdate(context)
        }
    }

    companion object {
        const val ACTION_REFRESH = "com.kagami.android.widgets.REFRESH_SAFETY"
    }
}

/**
 * Refresh action callback
 */
class RefreshSafetyAction : ActionCallback {
    override suspend fun onAction(
        context: Context,
        glanceId: GlanceId,
        parameters: ActionParameters
    ) {
        // Refresh data and update widget
        WidgetDataRepository.refreshData(context)
        SafetyWidget().update(context, glanceId)
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
