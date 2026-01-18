/**
 * Kagami Widget Provider — Base widget infrastructure
 *
 * Colony: Nexus (e4) — Integration
 *
 * Provides common widget functionality:
 * - Widget update service
 * - Data refresh from Kagami API
 * - Shared color/theme utilities
 *
 * h(x) >= 0. Always.
 */

package com.kagami.android.widgets

import android.content.Context
import android.content.Intent
import android.util.Log
import androidx.glance.appwidget.GlanceAppWidget
import androidx.glance.appwidget.GlanceAppWidgetManager
import androidx.glance.appwidget.updateAll
import androidx.work.*
import kotlinx.coroutines.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/**
 * Widget data holder for all Kagami widgets (legacy - for Glance compatibility)
 */
data class KagamiWidgetData(
    val isConnected: Boolean = false,
    val safetyScore: Double? = null,
    val movieMode: Boolean = false,
    val rooms: List<WidgetRoomData> = emptyList(),
    val lastUpdate: Long = System.currentTimeMillis()
)

data class WidgetRoomData(
    val id: String,
    val name: String,
    val avgLightLevel: Int,
    val occupied: Boolean
)

// Widget update worker moved to WidgetUpdateWorker.kt (HiltWorker implementation)

/*
 * Mirror
 * h(x) >= 0. Always.
 */
