/**
 * Kagami Widget Configuration Activity
 *
 * Colony: Nexus (e4) — Integration
 *
 * Allows users to configure widget settings:
 * - Select rooms to display (for Room Control widget)
 * - Choose default light levels
 * - Set update frequency
 *
 * h(x) >= 0. Always.
 */

package com.kagami.android.widgets

import android.app.Activity
import android.appwidget.AppWidgetManager
import android.content.Context
import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.glance.appwidget.GlanceAppWidgetManager
import androidx.glance.appwidget.updateAll
import com.kagami.android.ui.theme.KagamiTheme
import kotlinx.coroutines.launch

/**
 * Widget Configuration Activity
 *
 * Launched when user adds a widget to configure initial settings.
 */
class WidgetConfigActivity : ComponentActivity() {

    private var appWidgetId = AppWidgetManager.INVALID_APPWIDGET_ID

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Get the widget ID from the intent
        val extras = intent.extras
        if (extras != null) {
            appWidgetId = extras.getInt(
                AppWidgetManager.EXTRA_APPWIDGET_ID,
                AppWidgetManager.INVALID_APPWIDGET_ID
            )
        }

        // If invalid widget ID, finish immediately
        if (appWidgetId == AppWidgetManager.INVALID_APPWIDGET_ID) {
            setResult(Activity.RESULT_CANCELED)
            finish()
            return
        }

        // Set result to CANCELED initially - changed to OK when config is complete
        setResult(Activity.RESULT_CANCELED, Intent().apply {
            putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, appWidgetId)
        })

        setContent {
            KagamiTheme {
                WidgetConfigScreen(
                    onComplete = { selectedRooms ->
                        completeConfiguration(selectedRooms)
                    },
                    onCancel = {
                        finish()
                    }
                )
            }
        }
    }

    private fun completeConfiguration(selectedRooms: List<String>) {
        // Save configuration
        saveWidgetConfig(this, appWidgetId, selectedRooms)

        // Schedule widget updates
        WidgetUpdateWorker.schedulePeriodicUpdate(this)

        // Request immediate update
        WidgetUpdateWorker.requestImmediateUpdate(this)

        // Return success
        setResult(Activity.RESULT_OK, Intent().apply {
            putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, appWidgetId)
        })
        finish()
    }

    companion object {
        private const val PREFS_NAME = "kagami_widget_config"
        private const val KEY_SELECTED_ROOMS = "selected_rooms_"

        fun saveWidgetConfig(context: Context, widgetId: Int, rooms: List<String>) {
            context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .edit()
                .putStringSet(KEY_SELECTED_ROOMS + widgetId, rooms.toSet())
                .apply()
        }

        fun getWidgetConfig(context: Context, widgetId: Int): Set<String> {
            return context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .getStringSet(KEY_SELECTED_ROOMS + widgetId, emptySet()) ?: emptySet()
        }

        fun deleteWidgetConfig(context: Context, widgetId: Int) {
            context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .edit()
                .remove(KEY_SELECTED_ROOMS + widgetId)
                .apply()
        }
    }
}

@Composable
private fun WidgetConfigScreen(
    onComplete: (List<String>) -> Unit,
    onCancel: () -> Unit
) {
    val scope = rememberCoroutineScope()

    // Available rooms (these would normally come from the API)
    val availableRooms = remember {
        listOf(
            "Living Room",
            "Kitchen",
            "Primary Bedroom",
            "Office",
            "Dining Room",
            "Entry",
            "Garage",
            "Basement"
        )
    }

    var selectedRooms by remember { mutableStateOf(setOf<String>()) }

    // Colors
    val backgroundColor = Color(0xFF0A0A0D)
    val surfaceColor = Color(0xFF1E1E24)
    val accentColor = Color(0xFF67D4E4)
    val textColor = Color.White

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(backgroundColor)
            .padding(16.dp)
    ) {
        // Header
        Text(
            text = "Configure Widget",
            color = accentColor,
            fontSize = 24.sp,
            fontWeight = FontWeight.Bold
        )

        Spacer(modifier = Modifier.height(8.dp))

        Text(
            text = "Select rooms to display in the widget",
            color = Color(0xFF888888),
            fontSize = 14.sp
        )

        Spacer(modifier = Modifier.height(24.dp))

        // Room selection list
        LazyColumn(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            items(availableRooms) { room ->
                val isSelected = selectedRooms.contains(room)

                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(12.dp))
                        .background(if (isSelected) accentColor.copy(alpha = 0.2f) else surfaceColor)
                        .clickable {
                            selectedRooms = if (isSelected) {
                                selectedRooms - room
                            } else {
                                selectedRooms + room
                            }
                        }
                        .padding(16.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Checkbox(
                        checked = isSelected,
                        onCheckedChange = { checked ->
                            selectedRooms = if (checked) {
                                selectedRooms + room
                            } else {
                                selectedRooms - room
                            }
                        },
                        colors = CheckboxDefaults.colors(
                            checkedColor = accentColor,
                            uncheckedColor = Color(0xFF666666)
                        )
                    )

                    Spacer(modifier = Modifier.width(12.dp))

                    Text(
                        text = room,
                        color = if (isSelected) accentColor else textColor,
                        fontSize = 16.sp
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        // Action buttons
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            OutlinedButton(
                onClick = onCancel,
                modifier = Modifier.weight(1f),
                colors = ButtonDefaults.outlinedButtonColors(
                    contentColor = Color(0xFF888888)
                )
            ) {
                Text("Cancel")
            }

            Button(
                onClick = { onComplete(selectedRooms.toList()) },
                modifier = Modifier.weight(1f),
                colors = ButtonDefaults.buttonColors(
                    containerColor = accentColor
                )
            ) {
                Text(
                    text = if (selectedRooms.isEmpty()) "Show All Rooms" else "Done",
                    color = Color.Black
                )
            }
        }
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
