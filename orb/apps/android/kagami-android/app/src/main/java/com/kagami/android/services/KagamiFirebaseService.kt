/**
 * Kagami Firebase Messaging Service
 *
 * Colony: Nexus (e4) -- Integration
 *
 * Features:
 *   - FCM token management
 *   - Push notification handling
 *   - Notification channels
 *   - Deep link handling
 *
 * Created: December 31, 2025 (RALPH Week 3)
 */

package com.kagami.android.services

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.AudioAttributes
import android.media.RingtoneManager
import android.os.Build
import android.util.Log
import androidx.core.app.ActivityCompat
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import com.kagami.android.KagamiApp
import com.kagami.android.MainActivity
import com.kagami.android.R
import com.kagami.android.network.ApiConfig
import kotlinx.coroutines.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/**
 * Firebase Cloud Messaging service for Kagami push notifications.
 *
 * Handles:
 * - Token refresh and registration with backend
 * - Incoming notification display
 * - Notification action handling
 */
class KagamiFirebaseService : FirebaseMessagingService() {

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.SECONDS)
        .build()

    companion object {
        private const val TAG = "KagamiFirebase"

        // Notification Channels
        const val CHANNEL_HOME_ALERTS = "kagami_home_alerts"
        const val CHANNEL_SECURITY = "kagami_security"
        const val CHANNEL_REMINDERS = "kagami_reminders"
        const val CHANNEL_UPDATES = "kagami_updates"
        const val CHANNEL_DEFAULT = "kagami_notifications"

        // Notification Types
        const val TYPE_SMART_HOME_ALERT = "smart_home_alert"
        const val TYPE_ROUTINE_REMINDER = "routine_reminder"
        const val TYPE_SECURITY_ALERT = "security_alert"
        const val TYPE_SYSTEM_UPDATE = "system_update"

        // Action Intents
        const val ACTION_ACKNOWLEDGE = "com.kagami.android.ACTION_ACKNOWLEDGE"
        const val ACTION_VIEW_DETAILS = "com.kagami.android.ACTION_VIEW_DETAILS"
        const val ACTION_VIEW_CAMERA = "com.kagami.android.ACTION_VIEW_CAMERA"
        const val ACTION_RUN_ROUTINE = "com.kagami.android.ACTION_RUN_ROUTINE"
        const val ACTION_SNOOZE_ROUTINE = "com.kagami.android.ACTION_SNOOZE_ROUTINE"
        const val ACTION_ARM_SYSTEM = "com.kagami.android.ACTION_ARM_SYSTEM"
        const val ACTION_DISARM_SYSTEM = "com.kagami.android.ACTION_DISARM_SYSTEM"

        // Preferences
        private const val PREFS_NAME = "kagami_notifications"
        private const val KEY_FCM_TOKEN = "fcm_token"
        private const val KEY_TOKEN_SENT = "token_sent_to_server"

        /**
         * Get the current base URL from ApiConfig or use default.
         */
        private fun getBaseUrl(): String {
            return try {
                KagamiApp.instance.apiService.getServerUrl() ?: ApiConfig.DEFAULT_BASE_URL
            } catch (e: Exception) {
                ApiConfig.DEFAULT_BASE_URL
            }
        }

        /**
         * Create notification channels for Android 8.0+
         */
        fun createNotificationChannels(context: Context) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                val notificationManager = context.getSystemService(NotificationManager::class.java)

                // Home Alerts Channel (High importance)
                val homeAlertsChannel = NotificationChannel(
                    CHANNEL_HOME_ALERTS,
                    "Home Alerts",
                    NotificationManager.IMPORTANCE_HIGH
                ).apply {
                    description = "Smart home alerts and events"
                    enableVibration(true)
                    enableLights(true)
                }

                // Security Channel (Max importance)
                val securityChannel = NotificationChannel(
                    CHANNEL_SECURITY,
                    "Security Alerts",
                    NotificationManager.IMPORTANCE_HIGH
                ).apply {
                    description = "Security and safety alerts"
                    enableVibration(true)
                    enableLights(true)
                    setSound(
                        RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM),
                        AudioAttributes.Builder()
                            .setUsage(AudioAttributes.USAGE_ALARM)
                            .build()
                    )
                }

                // Reminders Channel (Default importance)
                val remindersChannel = NotificationChannel(
                    CHANNEL_REMINDERS,
                    "Routine Reminders",
                    NotificationManager.IMPORTANCE_DEFAULT
                ).apply {
                    description = "Routine and schedule reminders"
                }

                // Updates Channel (Low importance)
                val updatesChannel = NotificationChannel(
                    CHANNEL_UPDATES,
                    "System Updates",
                    NotificationManager.IMPORTANCE_LOW
                ).apply {
                    description = "System updates and announcements"
                }

                // Default Channel
                val defaultChannel = NotificationChannel(
                    CHANNEL_DEFAULT,
                    "Kagami Notifications",
                    NotificationManager.IMPORTANCE_DEFAULT
                ).apply {
                    description = "General Kagami notifications"
                }

                notificationManager.createNotificationChannels(listOf(
                    homeAlertsChannel,
                    securityChannel,
                    remindersChannel,
                    updatesChannel,
                    defaultChannel
                ))

                Log.i(TAG, "Notification channels created")
            }
        }

        /**
         * Get the stored FCM token
         */
        fun getStoredToken(context: Context): String? {
            val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            return prefs.getString(KEY_FCM_TOKEN, null)
        }

        /**
         * Check if token has been sent to server
         */
        fun isTokenSentToServer(context: Context): Boolean {
            val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            return prefs.getBoolean(KEY_TOKEN_SENT, false)
        }

    }

    override fun onCreate() {
        super.onCreate()
        createNotificationChannels(this)
    }

    override fun onDestroy() {
        super.onDestroy()
        scope.cancel()
    }

    /**
     * Called when a new FCM token is generated.
     * This happens on:
     * - App first install
     * - User uninstalls/reinstalls
     * - User clears app data
     * - App is restored on a new device
     */
    override fun onNewToken(token: String) {
        Log.d(TAG, "New FCM token: $token")

        // Store token locally
        storeToken(token)

        // Send to backend
        scope.launch {
            sendTokenToServer(token)
        }
    }

    /**
     * Called when a message is received.
     *
     * FCM messages can contain:
     * - notification: Display payload (handled by system if app in background)
     * - data: Custom data payload (always handled by this method)
     */
    override fun onMessageReceived(message: RemoteMessage) {
        Log.d(TAG, "Message received from: ${message.from}")

        // Extract data
        val data = message.data
        val notificationType = data["notification_type"] ?: TYPE_SMART_HOME_ALERT
        val priority = data["priority"] ?: "normal"
        val notificationId = data["notification_id"]

        // If there's a notification payload, display it
        message.notification?.let { notification ->
            displayNotification(
                title = notification.title ?: "Kagami",
                body = notification.body ?: "",
                notificationType = notificationType,
                priority = priority,
                data = data
            )
        }

        // If there's only data payload (no notification), display manually
        if (message.notification == null && data.isNotEmpty()) {
            val title = data["title"] ?: "Kagami"
            val body = data["body"] ?: ""

            displayNotification(
                title = title,
                body = body,
                notificationType = notificationType,
                priority = priority,
                data = data
            )
        }

        // Mark notification as delivered on backend
        notificationId?.let { id ->
            scope.launch {
                markNotificationDelivered(id)
            }
        }
    }

    /**
     * Display a notification with appropriate channel and actions.
     */
    private fun displayNotification(
        title: String,
        body: String,
        notificationType: String,
        priority: String,
        data: Map<String, String>
    ) {
        // Get appropriate channel
        val channelId = getChannelForType(notificationType)

        // Create content intent (opens app)
        val contentIntent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            data["action_url"]?.let { putExtra("deep_link", it) }
            data["notification_id"]?.let { putExtra("notification_id", it) }
        }

        val contentPendingIntent = PendingIntent.getActivity(
            this,
            System.currentTimeMillis().toInt(),
            contentIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        // Build notification
        val builder = NotificationCompat.Builder(this, channelId)
            .setSmallIcon(R.drawable.ic_launcher_foreground)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setContentIntent(contentPendingIntent)
            .setAutoCancel(true)
            .setPriority(getPriorityForType(priority))

        // Add actions based on notification type
        addActionsForType(builder, notificationType, data)

        // Show notification
        val notificationId = System.currentTimeMillis().toInt()

        if (ActivityCompat.checkSelfPermission(
                this,
                Manifest.permission.POST_NOTIFICATIONS
            ) == PackageManager.PERMISSION_GRANTED
        ) {
            NotificationManagerCompat.from(this).notify(notificationId, builder.build())
            Log.d(TAG, "Notification displayed: $title")
        } else {
            Log.w(TAG, "Notification permission not granted")
        }
    }

    /**
     * Get notification channel for notification type.
     */
    private fun getChannelForType(type: String): String {
        return when (type) {
            TYPE_SMART_HOME_ALERT -> CHANNEL_HOME_ALERTS
            TYPE_SECURITY_ALERT -> CHANNEL_SECURITY
            TYPE_ROUTINE_REMINDER -> CHANNEL_REMINDERS
            TYPE_SYSTEM_UPDATE -> CHANNEL_UPDATES
            else -> CHANNEL_DEFAULT
        }
    }

    /**
     * Get notification priority.
     */
    private fun getPriorityForType(priority: String): Int {
        return when (priority) {
            "critical" -> NotificationCompat.PRIORITY_MAX
            "high" -> NotificationCompat.PRIORITY_HIGH
            "low" -> NotificationCompat.PRIORITY_LOW
            else -> NotificationCompat.PRIORITY_DEFAULT
        }
    }

    /**
     * Add action buttons based on notification type.
     */
    private fun addActionsForType(
        builder: NotificationCompat.Builder,
        type: String,
        data: Map<String, String>
    ) {
        when (type) {
            TYPE_SMART_HOME_ALERT -> {
                // Acknowledge action
                val acknowledgeIntent = createActionIntent(ACTION_ACKNOWLEDGE, data)
                builder.addAction(
                    R.drawable.ic_launcher_foreground,
                    "Acknowledge",
                    acknowledgeIntent
                )

                // View Details action
                val viewIntent = createActionIntent(ACTION_VIEW_DETAILS, data)
                builder.addAction(
                    R.drawable.ic_launcher_foreground,
                    "View",
                    viewIntent
                )
            }

            TYPE_SECURITY_ALERT -> {
                // View Camera action
                val cameraIntent = createActionIntent(ACTION_VIEW_CAMERA, data)
                builder.addAction(
                    R.drawable.ic_launcher_foreground,
                    "View Camera",
                    cameraIntent
                )

                // Arm System action
                val armIntent = createActionIntent(ACTION_ARM_SYSTEM, data)
                builder.addAction(
                    R.drawable.ic_launcher_foreground,
                    "Arm",
                    armIntent
                )
            }

            TYPE_ROUTINE_REMINDER -> {
                // Run Now action
                val runIntent = createActionIntent(ACTION_RUN_ROUTINE, data)
                builder.addAction(
                    R.drawable.ic_launcher_foreground,
                    "Run Now",
                    runIntent
                )

                // Snooze action
                val snoozeIntent = createActionIntent(ACTION_SNOOZE_ROUTINE, data)
                builder.addAction(
                    R.drawable.ic_launcher_foreground,
                    "Snooze",
                    snoozeIntent
                )
            }

            TYPE_SYSTEM_UPDATE -> {
                // View Details action
                val viewIntent = createActionIntent(ACTION_VIEW_DETAILS, data)
                builder.addAction(
                    R.drawable.ic_launcher_foreground,
                    "View Details",
                    viewIntent
                )
            }
        }
    }

    /**
     * Create a pending intent for notification action.
     */
    private fun createActionIntent(action: String, data: Map<String, String>): PendingIntent {
        val intent = Intent(this, NotificationActionReceiver::class.java).apply {
            this.action = action
            data.forEach { (key, value) -> putExtra(key, value) }
        }

        return PendingIntent.getBroadcast(
            this,
            action.hashCode(),
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
    }

    /**
     * Store FCM token locally.
     */
    private fun storeToken(token: String) {
        val prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit()
            .putString(KEY_FCM_TOKEN, token)
            .putBoolean(KEY_TOKEN_SENT, false)
            .apply()
    }

    /**
     * Send FCM token to Kagami backend.
     */
    private suspend fun sendTokenToServer(token: String) = withContext(Dispatchers.IO) {
        val deviceId = getKagamiDeviceId()

        val body = JSONObject().apply {
            put("device_token", token)
            put("platform", "android")
            put("device_id", deviceId)
            put("device_name", Build.MODEL)
            put("app_version", getAppVersion())
        }

        try {
            val request = Request.Builder()
                .url("${getBaseUrl()}${ApiConfig.Companion.Endpoints.NOTIFICATIONS_REGISTER}")
                .post(body.toString().toRequestBody("application/json".toMediaType()))
                .build()

            val response = client.newCall(request).execute()

            if (response.isSuccessful) {
                // Mark as sent
                val prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                prefs.edit().putBoolean(KEY_TOKEN_SENT, true).apply()

                Log.i(TAG, "FCM token sent to server successfully")
            } else {
                Log.w(TAG, "Failed to send FCM token: ${response.code}")
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error sending FCM token to server", e)
        }
    }

    /**
     * Mark notification as delivered on backend.
     */
    private suspend fun markNotificationDelivered(notificationId: String) = withContext(Dispatchers.IO) {
        try {
            val request = Request.Builder()
                .url("${getBaseUrl()}${ApiConfig.Companion.Endpoints.notificationDelivered(notificationId)}")
                .post("".toRequestBody(null))
                .build()

            client.newCall(request).execute()
        } catch (e: Exception) {
            Log.w(TAG, "Failed to mark notification delivered", e)
        }
    }

    /**
     * Get unique Kagami device identifier.
     */
    private fun getKagamiDeviceId(): String {
        val prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        var deviceId = prefs.getString("device_id", null)

        if (deviceId == null) {
            deviceId = java.util.UUID.randomUUID().toString()
            prefs.edit().putString("device_id", deviceId).apply()
        }

        return deviceId
    }

    /**
     * Get app version.
     */
    private fun getAppVersion(): String {
        return try {
            packageManager.getPackageInfo(packageName, 0).versionName ?: "1.0.0"
        } catch (e: Exception) {
            "1.0.0"
        }
    }
}

/**
 * Broadcast receiver for notification actions.
 */
class NotificationActionReceiver : android.content.BroadcastReceiver() {

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .build()

    companion object {
        private const val TAG = "KagamiActionReceiver"

        /**
         * Get the current base URL from ApiConfig or use default.
         */
        private fun getBaseUrl(): String {
            return try {
                KagamiApp.instance.apiService.getServerUrl() ?: ApiConfig.DEFAULT_BASE_URL
            } catch (e: Exception) {
                ApiConfig.DEFAULT_BASE_URL
            }
        }
    }

    override fun onReceive(context: Context, intent: Intent) {
        val action = intent.action ?: return
        Log.d(TAG, "Action received: $action")

        // Extract data
        val notificationId = intent.getStringExtra("notification_id")
        val alertId = intent.getStringExtra("alert_id")
        val routineId = intent.getStringExtra("routine_id")
        val cameraId = intent.getStringExtra("camera_id")

        // Mark notification as read
        notificationId?.let { id ->
            scope.launch { markNotificationRead(id) }
        }

        // Handle action
        when (action) {
            KagamiFirebaseService.ACTION_ACKNOWLEDGE -> {
                alertId?.let { scope.launch { acknowledgeAlert(it) } }
            }

            KagamiFirebaseService.ACTION_VIEW_DETAILS -> {
                // Open app with deep link
                val deepLink = intent.getStringExtra("action_url")
                openApp(context, deepLink)
            }

            KagamiFirebaseService.ACTION_VIEW_CAMERA -> {
                openApp(context, "kagami://cameras/$cameraId")
            }

            KagamiFirebaseService.ACTION_RUN_ROUTINE -> {
                routineId?.let { scope.launch { executeRoutine(it) } }
            }

            KagamiFirebaseService.ACTION_SNOOZE_ROUTINE -> {
                routineId?.let { scope.launch { snoozeRoutine(it) } }
            }

            KagamiFirebaseService.ACTION_ARM_SYSTEM -> {
                scope.launch { armSecuritySystem() }
            }

            KagamiFirebaseService.ACTION_DISARM_SYSTEM -> {
                scope.launch { disarmSecuritySystem() }
            }
        }

        // Dismiss notification
        val notificationManager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        notificationId?.toIntOrNull()?.let { notificationManager.cancel(it) }
    }

    private fun openApp(context: Context, deepLink: String?) {
        val intent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            deepLink?.let { putExtra("deep_link", it) }
        }
        context.startActivity(intent)
    }

    private suspend fun markNotificationRead(notificationId: String) = withContext(Dispatchers.IO) {
        try {
            val request = Request.Builder()
                .url("${getBaseUrl()}${ApiConfig.Companion.Endpoints.notificationRead(notificationId)}")
                .post("".toRequestBody(null))
                .build()
            client.newCall(request).execute()
        } catch (e: Exception) {
            Log.w(TAG, "Failed to mark notification read", e)
        }
    }

    private suspend fun acknowledgeAlert(alertId: String) = withContext(Dispatchers.IO) {
        try {
            val request = Request.Builder()
                .url("${getBaseUrl()}${ApiConfig.Companion.Endpoints.acknowledgeAlert(alertId)}")
                .post("".toRequestBody(null))
                .build()
            client.newCall(request).execute()
            Log.d(TAG, "Alert acknowledged: $alertId")
        } catch (e: Exception) {
            Log.w(TAG, "Failed to acknowledge alert", e)
        }
    }

    private suspend fun executeRoutine(routineId: String) = withContext(Dispatchers.IO) {
        try {
            val request = Request.Builder()
                .url("${getBaseUrl()}${ApiConfig.Companion.Endpoints.executeRoutine(routineId)}")
                .post("".toRequestBody(null))
                .build()
            client.newCall(request).execute()
            Log.d(TAG, "Routine executed: $routineId")
        } catch (e: Exception) {
            Log.w(TAG, "Failed to execute routine", e)
        }
    }

    private suspend fun snoozeRoutine(routineId: String) = withContext(Dispatchers.IO) {
        try {
            val body = JSONObject().put("minutes", 15)
            val request = Request.Builder()
                .url("${getBaseUrl()}${ApiConfig.Companion.Endpoints.snoozeRoutine(routineId)}")
                .post(body.toString().toRequestBody("application/json".toMediaType()))
                .build()
            client.newCall(request).execute()
            Log.d(TAG, "Routine snoozed: $routineId")
        } catch (e: Exception) {
            Log.w(TAG, "Failed to snooze routine", e)
        }
    }

    private suspend fun armSecuritySystem() = withContext(Dispatchers.IO) {
        try {
            val request = Request.Builder()
                .url("${getBaseUrl()}${ApiConfig.Companion.Endpoints.SECURITY_ARM}")
                .post("".toRequestBody(null))
                .build()
            client.newCall(request).execute()
            Log.d(TAG, "Security system armed")
        } catch (e: Exception) {
            Log.w(TAG, "Failed to arm security system", e)
        }
    }

    private suspend fun disarmSecuritySystem() = withContext(Dispatchers.IO) {
        try {
            val request = Request.Builder()
                .url("${getBaseUrl()}${ApiConfig.Companion.Endpoints.SECURITY_DISARM}")
                .post("".toRequestBody(null))
                .build()
            client.newCall(request).execute()
            Log.d(TAG, "Security system disarmed")
        } catch (e: Exception) {
            Log.w(TAG, "Failed to disarm security system", e)
        }
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
