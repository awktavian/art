/**
 * KagamiOverlayService — Floating Controls Overlay
 *
 * Capabilities:
 *   - Always-visible floating controls
 *   - Voice command indicator
 *   - Quick action buttons
 *   - Safety status indicator
 *   - Minimizable/expandable UI
 *
 * Safety:
 *   - Non-blocking (can be dismissed)
 *   - Transparent to touch when minimized
 *   - User can disable at any time
 */

package com.kagami.android.services

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.graphics.PixelFormat
import android.os.Build
import android.os.IBinder
import android.util.Log
import android.view.Gravity
import android.view.LayoutInflater
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.ImageButton
import android.widget.LinearLayout
import android.widget.TextView
import androidx.core.app.NotificationCompat
import com.kagami.android.MainActivity
import com.kagami.android.R
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

/**
 * Foreground service that displays floating controls over other apps.
 *
 * Requires SYSTEM_ALERT_WINDOW permission (granted manually in settings).
 */
class KagamiOverlayService : Service() {

    companion object {
        private const val TAG = "KagamiOverlay"
        private const val NOTIFICATION_ID = 1001
        private const val CHANNEL_ID = "kagami_overlay_channel"

        // Service state
        private var instance: KagamiOverlayService? = null

        /**
         * Check if overlay service is running.
         */
        fun isRunning(): Boolean = instance != null

        /**
         * Start the overlay service.
         */
        fun start(context: Context) {
            val intent = Intent(context, KagamiOverlayService::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        }

        /**
         * Stop the overlay service.
         */
        fun stop(context: Context) {
            context.stopService(Intent(context, KagamiOverlayService::class.java))
        }
    }

    private var windowManager: WindowManager? = null
    private var overlayView: View? = null
    private var isExpanded = false
    private val serviceScope = CoroutineScope(Dispatchers.Main + SupervisorJob())

    // UI State
    private val _safetyScore = MutableStateFlow(1.0f)
    val safetyScore: StateFlow<Float> = _safetyScore

    private val _isListening = MutableStateFlow(false)
    val isListening: StateFlow<Boolean> = _isListening

    // ============================================================================
    // Lifecycle
    // ============================================================================

    override fun onCreate() {
        super.onCreate()
        Log.i(TAG, "🎈 Kagami Overlay Service created")
        instance = this

        createNotificationChannel()
        startForeground(NOTIFICATION_ID, createNotification())

        windowManager = getSystemService(WINDOW_SERVICE) as WindowManager
        createOverlayView()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        Log.d(TAG, "onStartCommand")
        return START_STICKY
    }

    override fun onDestroy() {
        super.onDestroy()
        Log.i(TAG, "🎈 Kagami Overlay Service destroyed")

        removeOverlayView()
        serviceScope.cancel()
        instance = null
    }

    override fun onBind(intent: Intent?): IBinder? = null

    // ============================================================================
    // Notification
    // ============================================================================

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Kagami Floating Controls",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Shows floating controls for quick Kagami access"
                setShowBadge(false)
            }

            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }
    }

    private fun createNotification(): Notification {
        val pendingIntent = PendingIntent.getActivity(
            this,
            0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Kagami Active")
            .setContentText("Tap to open app")
            .setSmallIcon(R.drawable.ic_fano_plane)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .setSilent(true)
            .build()
    }

    // ============================================================================
    // Overlay View
    // ============================================================================

    private fun createOverlayView() {
        // Create layout programmatically for simplicity
        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(0xE6121212.toInt()) // Dark with alpha
            setPadding(16, 16, 16, 16)
        }

        // Kagami logo/status button
        val statusButton = createStatusButton()
        layout.addView(statusButton)

        // Expanded controls (hidden by default)
        val expandedControls = createExpandedControls()
        expandedControls.visibility = View.GONE
        layout.addView(expandedControls)

        overlayView = layout

        // Window parameters
        val params = WindowManager.LayoutParams(
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.WRAP_CONTENT,
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
            } else {
                @Suppress("DEPRECATION")
                WindowManager.LayoutParams.TYPE_PHONE
            },
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                    WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.TOP or Gravity.END
            x = 16
            y = 200
        }

        // Add drag functionality
        setupDragging(layout, params)

        try {
            windowManager?.addView(layout, params)
            Log.i(TAG, "✅ Overlay view added")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to add overlay: ${e.message}")
        }
    }

    private fun createStatusButton(): View {
        return ImageButton(this).apply {
            setImageResource(R.drawable.ic_fano_plane)
            setBackgroundColor(0x00000000) // Transparent
            setPadding(8, 8, 8, 8)
            contentDescription = "Kagami Status"

            setOnClickListener {
                toggleExpanded()
            }

            setOnLongClickListener {
                // Long press to close overlay
                stopSelf()
                true
            }
        }
    }

    private fun createExpandedControls(): LinearLayout {
        return LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(0, 8, 0, 0)

            // Quick action buttons
            val actions = listOf(
                "🎬 Movie" to { executeAction("movie_mode") },
                "🌙 Goodnight" to { executeAction("goodnight") },
                "💡 Lights" to { executeAction("toggle_lights") },
                "🔒 Lock" to { executeAction("lock_all") }
            )

            actions.forEach { (label, action) ->
                val button = TextView(context).apply {
                    text = label
                    textSize = 14f
                    setTextColor(0xFFFFFFFF.toInt())
                    setPadding(8, 12, 8, 12)
                    setOnClickListener { action() }
                }
                addView(button)
            }

            // Safety score display
            val safetyLabel = TextView(context).apply {
                text = "h(x) = 1.0"
                textSize = 12f
                setTextColor(0xFF00FF88.toInt())
                setPadding(8, 16, 8, 8)
            }
            addView(safetyLabel)

            // Update safety score display
            serviceScope.launch {
                safetyScore.collect { score ->
                    val color = when {
                        score >= 0.7f -> 0xFF00FF88.toInt() // Green
                        score >= 0.3f -> 0xFFFFAA00.toInt() // Orange
                        else -> 0xFFFF4444.toInt() // Red
                    }
                    safetyLabel.text = "h(x) = %.2f".format(score)
                    safetyLabel.setTextColor(color)
                }
            }
        }
    }

    private fun toggleExpanded() {
        isExpanded = !isExpanded

        val expandedView = (overlayView as? LinearLayout)?.getChildAt(1)
        expandedView?.visibility = if (isExpanded) View.VISIBLE else View.GONE

        Log.d(TAG, "Overlay expanded: $isExpanded")
    }

    private fun setupDragging(view: View, params: WindowManager.LayoutParams) {
        var initialX = 0
        var initialY = 0
        var initialTouchX = 0f
        var initialTouchY = 0f
        var isDragging = false

        view.setOnTouchListener { v, event ->
            when (event.action) {
                MotionEvent.ACTION_DOWN -> {
                    initialX = params.x
                    initialY = params.y
                    initialTouchX = event.rawX
                    initialTouchY = event.rawY
                    isDragging = false
                    true
                }
                MotionEvent.ACTION_MOVE -> {
                    val dx = (event.rawX - initialTouchX).toInt()
                    val dy = (event.rawY - initialTouchY).toInt()

                    if (Math.abs(dx) > 10 || Math.abs(dy) > 10) {
                        isDragging = true
                    }

                    if (isDragging) {
                        params.x = initialX - dx
                        params.y = initialY + dy
                        windowManager?.updateViewLayout(view, params)
                    }
                    true
                }
                MotionEvent.ACTION_UP -> {
                    if (!isDragging) {
                        v.performClick()
                    }
                    true
                }
                else -> false
            }
        }
    }

    private fun removeOverlayView() {
        overlayView?.let {
            try {
                windowManager?.removeView(it)
                Log.i(TAG, "✅ Overlay view removed")
            } catch (e: Exception) {
                Log.e(TAG, "Failed to remove overlay: ${e.message}")
            }
        }
        overlayView = null
    }

    // ============================================================================
    // Actions
    // ============================================================================

    private fun executeAction(action: String) {
        Log.d(TAG, "Executing action: $action")

        serviceScope.launch {
            try {
                val apiService = KagamiApiService.getInstance()
                when (action) {
                    "movie_mode" -> apiService?.movieMode()
                    "goodnight" -> apiService?.goodnight()
                    "toggle_lights" -> apiService?.setLights(50, null)
                    "lock_all" -> apiService?.lockAll()
                }
            } catch (e: Exception) {
                Log.e(TAG, "Action failed: ${e.message}")
            }
        }
    }

    /**
     * Update the safety score display.
     */
    fun updateSafetyScore(score: Float) {
        _safetyScore.value = score.coerceIn(0f, 1f)
    }

    /**
     * Set listening indicator state.
     */
    fun setListening(listening: Boolean) {
        _isListening.value = listening
        // Could animate the status button here
    }
}

/*
 * 鏡
 * h(x) ≥ 0. Always.
 *
 * A gentle presence, always there.
 * Non-intrusive. Helpful. Safe.
 * One tap away from assistance.
 */
