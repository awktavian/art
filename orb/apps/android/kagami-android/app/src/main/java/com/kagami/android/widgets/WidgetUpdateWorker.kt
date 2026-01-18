/**
 * Widget Update Worker
 *
 * Colony: Grove (e6) - Maintenance & Background Operations
 * h(x) >= 0. Always.
 *
 * WorkManager-based background worker for keeping widgets updated.
 * Fetches latest data from Kagami server and updates all active widgets.
 *
 * Schedule:
 * - Periodic: Every 15 minutes (minimum WorkManager interval)
 * - On-demand: When user interacts with widget
 * - On connection change: When network becomes available
 *
 * Architecture Note: Uses HiltWorker for proper DI. The apiService is injected
 * via @AssistedInject rather than accessed via KagamiApp.instance.
 */

package com.kagami.android.widgets

import android.appwidget.AppWidgetManager
import android.content.ComponentName
import android.content.Context
import android.util.Log
import androidx.hilt.work.HiltWorker
import androidx.work.*
import com.kagami.android.services.KagamiApiService
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.GlobalScope
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.util.concurrent.TimeUnit

/**
 * Background worker for widget data synchronization.
 * Uses HiltWorker for proper dependency injection.
 */
@HiltWorker
class WidgetUpdateWorker @AssistedInject constructor(
    @Assisted private val context: Context,
    @Assisted workerParams: WorkerParameters,
    private val apiService: KagamiApiService
) : CoroutineWorker(context, workerParams) {

    companion object {
        private const val TAG = "WidgetUpdateWorker"
        const val WORK_NAME_PERIODIC = "widget_periodic_update"
        const val WORK_NAME_ONE_TIME = "widget_one_time_update"

        // Input data keys
        const val KEY_WIDGET_IDS = "widget_ids"
        const val KEY_FORCE_REFRESH = "force_refresh"

        /**
         * Schedule periodic widget updates.
         * Call this at app startup.
         */
        fun schedulePeriodicUpdate(context: Context) {
            val constraints = Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build()

            val periodicWork = PeriodicWorkRequestBuilder<WidgetUpdateWorker>(
                15, TimeUnit.MINUTES // Minimum WorkManager interval
            )
                .setConstraints(constraints)
                .setBackoffCriteria(
                    BackoffPolicy.EXPONENTIAL,
                    WorkRequest.MIN_BACKOFF_MILLIS,
                    TimeUnit.MILLISECONDS
                )
                .addTag("widget_update")
                .build()

            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                WORK_NAME_PERIODIC,
                ExistingPeriodicWorkPolicy.KEEP, // Don't restart if already scheduled
                periodicWork
            )

            Log.i(TAG, "Scheduled periodic widget updates")
        }

        /**
         * Request immediate widget update.
         * Use when user interacts with app or widget.
         */
        fun requestImmediateUpdate(context: Context, vararg widgetIds: Int) {
            val inputData = workDataOf(
                KEY_WIDGET_IDS to widgetIds.toList().toIntArray(),
                KEY_FORCE_REFRESH to true
            )

            val immediateWork = OneTimeWorkRequestBuilder<WidgetUpdateWorker>()
                .setInputData(inputData)
                .setExpedited(OutOfQuotaPolicy.RUN_AS_NON_EXPEDITED_WORK_REQUEST)
                .addTag("widget_update_immediate")
                .build()

            WorkManager.getInstance(context).enqueueUniqueWork(
                WORK_NAME_ONE_TIME,
                ExistingWorkPolicy.REPLACE, // Cancel any pending and run now
                immediateWork
            )

            Log.d(TAG, "Requested immediate widget update for ${widgetIds.size} widgets")
        }

        /**
         * Cancel all scheduled widget updates.
         * Use when user logs out or removes all widgets.
         */
        fun cancelAllUpdates(context: Context) {
            WorkManager.getInstance(context).cancelUniqueWork(WORK_NAME_PERIODIC)
            WorkManager.getInstance(context).cancelUniqueWork(WORK_NAME_ONE_TIME)
            Log.i(TAG, "Cancelled all widget updates")
        }
    }

    override suspend fun doWork(): Result {
        return withContext(Dispatchers.IO) {
            Log.d(TAG, "Starting widget update work")

            try {
                // Get repository (API service is injected via constructor)
                val repository = WidgetDataRepository(context)

                // Check if specific widgets requested
                val targetWidgetIds = inputData.getIntArray(KEY_WIDGET_IDS)
                val forceRefresh = inputData.getBoolean(KEY_FORCE_REFRESH, false)

                // Fetch latest data from server
                val safetyData = this@WidgetUpdateWorker.fetchSafetyData(apiService, forceRefresh)
                val scenes = this@WidgetUpdateWorker.fetchScenes(apiService)
                val rooms = this@WidgetUpdateWorker.fetchRooms(apiService)

                // Update repository with fresh data
                safetyData?.let { data ->
                    repository.updateSafetyData(
                        score = data.score,
                        status = data.status,
                        isConnected = data.isConnected,
                        latencyMs = data.latencyMs
                    )
                }

                if (scenes.isNotEmpty()) {
                    repository.updateFavoriteScenes(scenes)
                }

                if (rooms.isNotEmpty()) {
                    repository.updateRooms(rooms)
                }

                // Trigger widget UI updates
                this@WidgetUpdateWorker.updateWidgetUIs(targetWidgetIds)

                Log.i(TAG, "Widget update completed successfully")
                Result.success()

            } catch (e: Exception) {
                Log.e(TAG, "Widget update failed", e)

                // Retry with exponential backoff for transient errors
                if (runAttemptCount < 3) {
                    Result.retry()
                } else {
                    Result.failure()
                }
            }
        }
    }

    /**
     * Fetch safety data from API.
     */
    private suspend fun fetchSafetyData(
        apiService: com.kagami.android.services.KagamiApiService,
        forceRefresh: Boolean
    ): SafetyData? {
        return try {
            // Ensure connection
            if (forceRefresh || !apiService.isConnected.value) {
                apiService.connect()
            }

            SafetyData(
                score = apiService.safetyScore.value,
                status = SafetyStatus.fromScore(apiService.safetyScore.value),
                lastUpdate = System.currentTimeMillis(),
                isConnected = apiService.isConnected.value,
                latencyMs = apiService.latencyMs.value
            )
        } catch (e: Exception) {
            Log.w(TAG, "Failed to fetch safety data", e)
            null
        }
    }

    /**
     * Fetch scenes from API.
     */
    private suspend fun fetchScenes(
        apiService: com.kagami.android.services.KagamiApiService
    ): List<SceneInfo> {
        return try {
            val result = apiService.getScenes()
            when (result) {
                is com.kagami.android.data.Result.Success -> {
                    result.data.map { scene ->
                        SceneInfo(
                            id = scene.id,
                            name = scene.name,
                            icon = scene.icon ?: "star"
                        )
                    }
                }
                is com.kagami.android.data.Result.Error -> {
                    Log.w(TAG, "Failed to fetch scenes: ${result.message}")
                    emptyList()
                }
            }
        } catch (e: Exception) {
            Log.w(TAG, "Failed to fetch scenes", e)
            emptyList()
        }
    }

    /**
     * Fetch rooms from API.
     */
    private suspend fun fetchRooms(
        apiService: com.kagami.android.services.KagamiApiService
    ): List<RoomInfo> {
        return try {
            val result = apiService.getRooms()
            when (result) {
                is com.kagami.android.data.Result.Success -> {
                    result.data.map { room ->
                        RoomInfo(
                            id = room.id,
                            name = room.name,
                            floor = room.floor,
                            hasLights = room.hasLights,
                            hasShades = room.hasShades,
                            lightLevel = room.lightLevel ?: 0,
                            shadesOpen = room.shadesOpen ?: true
                        )
                    }
                }
                is com.kagami.android.data.Result.Error -> {
                    Log.w(TAG, "Failed to fetch rooms: ${result.message}")
                    emptyList()
                }
            }
        } catch (e: Exception) {
            Log.w(TAG, "Failed to fetch rooms", e)
            emptyList()
        }
    }

    /**
     * Trigger UI updates for all widget types.
     */
    private fun updateWidgetUIs(targetWidgetIds: IntArray?) {
        val appWidgetManager = AppWidgetManager.getInstance(context)

        // Update Safety Widget
        updateWidgetClass(
            appWidgetManager,
            targetWidgetIds,
            SafetyWidget::class.java
        )

        // Update Quick Actions Widget
        updateWidgetClass(
            appWidgetManager,
            targetWidgetIds,
            QuickActionsWidget::class.java
        )

        // Update Room Control Widget
        updateWidgetClass(
            appWidgetManager,
            targetWidgetIds,
            RoomControlWidget::class.java
        )
    }

    /**
     * Update specific widget class.
     */
    private fun <T> updateWidgetClass(
        appWidgetManager: AppWidgetManager,
        targetWidgetIds: IntArray?,
        widgetClass: Class<T>
    ) {
        val componentName = ComponentName(context, widgetClass)
        val allWidgetIds = appWidgetManager.getAppWidgetIds(componentName)

        // Filter to target widgets if specified
        val widgetsToUpdate = if (targetWidgetIds != null) {
            allWidgetIds.filter { it in targetWidgetIds }.toIntArray()
        } else {
            allWidgetIds
        }

        if (widgetsToUpdate.isNotEmpty()) {
            // Notify widget provider to update
            appWidgetManager.notifyAppWidgetViewDataChanged(widgetsToUpdate, android.R.id.list)
            Log.d(TAG, "Updated ${widgetsToUpdate.size} ${widgetClass.simpleName} widgets")
        }
    }
}

/**
 * Observer for widget lifecycle events.
 * Schedules/cancels background work as widgets are added/removed.
 */
object WidgetLifecycleObserver {

    /**
     * Called when a widget is added.
     */
    fun onWidgetAdded(context: Context, appWidgetId: Int) {
        // Ensure periodic updates are scheduled
        WidgetUpdateWorker.schedulePeriodicUpdate(context)

        // Request immediate update for the new widget
        WidgetUpdateWorker.requestImmediateUpdate(context, appWidgetId)

        Log.d("WidgetLifecycle", "Widget $appWidgetId added, scheduled updates")
    }

    /**
     * Called when a widget is removed.
     */
    fun onWidgetRemoved(context: Context, appWidgetId: Int) {
        // Clean up widget config
        GlobalScope.launch(Dispatchers.IO) {
            val repository = WidgetDataRepository(context)
            repository.removeWidgetConfig(appWidgetId)
        }

        // Check if any widgets remain
        val appWidgetManager = AppWidgetManager.getInstance(context)

        val hasRemainingWidgets = listOf(
            SafetyWidget::class.java,
            QuickActionsWidget::class.java,
            RoomControlWidget::class.java
        ).any { widgetClass ->
            val component = ComponentName(context, widgetClass)
            appWidgetManager.getAppWidgetIds(component).isNotEmpty()
        }

        if (!hasRemainingWidgets) {
            // No widgets left, cancel background updates
            WidgetUpdateWorker.cancelAllUpdates(context)
            Log.d("WidgetLifecycle", "No widgets remaining, cancelled updates")
        }

        Log.d("WidgetLifecycle", "Widget $appWidgetId removed")
    }
}
