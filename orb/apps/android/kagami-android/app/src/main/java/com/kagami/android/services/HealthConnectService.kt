/**
 * HealthConnectService — Android Health Connect Integration
 *
 * Colony: Nexus (e4) — Integration
 *
 * Features:
 * - Heart rate monitoring
 * - Step count tracking
 * - Sleep analysis
 * - Activity tracking (active calories, exercise)
 *
 * Architecture:
 * Health Connect → HealthConnectService → KagamiApiService → Kagami Backend
 */

package com.kagami.android.services

import android.content.Context
import android.util.Log
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.*
import androidx.health.connect.client.request.ReadRecordsRequest
import androidx.health.connect.client.time.TimeRangeFilter
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import java.time.*
import java.time.temporal.ChronoUnit

/**
 * Health Connect integration service for Android.
 * Reads biometric data and makes it available for upload to Kagami.
 */
class HealthConnectService(private val context: Context) {

    companion object {
        private const val TAG = "HealthConnect"

        // Required permissions
        val PERMISSIONS = setOf(
            HealthPermission.getReadPermission(HeartRateRecord::class),
            HealthPermission.getReadPermission(StepsRecord::class),
            HealthPermission.getReadPermission(ActiveCaloriesBurnedRecord::class),
            HealthPermission.getReadPermission(ExerciseSessionRecord::class),
            HealthPermission.getReadPermission(SleepSessionRecord::class),
            HealthPermission.getReadPermission(OxygenSaturationRecord::class),
            HealthPermission.getReadPermission(RestingHeartRateRecord::class),
            HealthPermission.getReadPermission(HeartRateVariabilityRmssdRecord::class),
        )

        /**
         * Check if Health Connect is available on this device.
         */
        fun isAvailable(context: Context): Boolean {
            return HealthConnectClient.getSdkStatus(context) == HealthConnectClient.SDK_AVAILABLE
        }

        /**
         * Get the Health Connect package name for installation intent.
         */
        fun getHealthConnectPackage(): String {
            return "com.google.android.apps.healthdata"
        }
    }

    // State
    private val _isAuthorized = MutableStateFlow(false)
    val isAuthorized: StateFlow<Boolean> = _isAuthorized

    private val _heartRate = MutableStateFlow(0.0)
    val heartRate: StateFlow<Double> = _heartRate

    private val _restingHeartRate = MutableStateFlow(0.0)
    val restingHeartRate: StateFlow<Double> = _restingHeartRate

    private val _hrv = MutableStateFlow(0.0)
    val hrv: StateFlow<Double> = _hrv

    private val _steps = MutableStateFlow(0)
    val steps: StateFlow<Int> = _steps

    private val _activeCalories = MutableStateFlow(0.0)
    val activeCalories: StateFlow<Double> = _activeCalories

    private val _exerciseMinutes = MutableStateFlow(0.0)
    val exerciseMinutes: StateFlow<Double> = _exerciseMinutes

    private val _bloodOxygen = MutableStateFlow(0.0)
    val bloodOxygen: StateFlow<Double> = _bloodOxygen

    private val _sleepHours = MutableStateFlow(0.0)
    val sleepHours: StateFlow<Double> = _sleepHours

    // Health Connect client
    private val healthConnectClient: HealthConnectClient? = try {
        if (isAvailable(context)) {
            HealthConnectClient.getOrCreate(context)
        } else {
            null
        }
    } catch (e: Exception) {
        Log.w(TAG, "Failed to create Health Connect client", e)
        null
    }

    /**
     * Check if all required permissions are granted.
     */
    suspend fun checkPermissions(): Boolean {
        val client = healthConnectClient ?: return false

        return try {
            val granted = client.permissionController.getGrantedPermissions()
            val allGranted = PERMISSIONS.all { it in granted }
            _isAuthorized.value = allGranted
            allGranted
        } catch (e: Exception) {
            Log.e(TAG, "Failed to check permissions", e)
            false
        }
    }

    /**
     * Refresh all health data.
     */
    suspend fun refreshAllData() {
        if (!_isAuthorized.value) {
            if (!checkPermissions()) return
        }

        fetchHeartRate()
        fetchRestingHeartRate()
        fetchHRV()
        fetchSteps()
        fetchActiveCalories()
        fetchExerciseMinutes()
        fetchBloodOxygen()
        fetchSleepHours()
    }

    /**
     * Fetch the most recent heart rate.
     */
    private suspend fun fetchHeartRate() {
        val client = healthConnectClient ?: return

        try {
            val endTime = Instant.now()
            val startTime = endTime.minus(1, ChronoUnit.HOURS)

            val response = client.readRecords(
                ReadRecordsRequest(
                    recordType = HeartRateRecord::class,
                    timeRangeFilter = TimeRangeFilter.between(startTime, endTime)
                )
            )

            val samples = response.records.flatMap { it.samples }
            if (samples.isNotEmpty()) {
                _heartRate.value = samples.last().beatsPerMinute.toDouble()
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to fetch heart rate", e)
        }
    }

    /**
     * Fetch resting heart rate.
     */
    private suspend fun fetchRestingHeartRate() {
        val client = healthConnectClient ?: return

        try {
            val endTime = Instant.now()
            val startTime = endTime.minus(24, ChronoUnit.HOURS)

            val response = client.readRecords(
                ReadRecordsRequest(
                    recordType = RestingHeartRateRecord::class,
                    timeRangeFilter = TimeRangeFilter.between(startTime, endTime)
                )
            )

            if (response.records.isNotEmpty()) {
                _restingHeartRate.value = response.records.last().beatsPerMinute.toDouble()
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to fetch resting heart rate", e)
        }
    }

    /**
     * Fetch HRV (RMSSD).
     */
    private suspend fun fetchHRV() {
        val client = healthConnectClient ?: return

        try {
            val endTime = Instant.now()
            val startTime = endTime.minus(24, ChronoUnit.HOURS)

            val response = client.readRecords(
                ReadRecordsRequest(
                    recordType = HeartRateVariabilityRmssdRecord::class,
                    timeRangeFilter = TimeRangeFilter.between(startTime, endTime)
                )
            )

            if (response.records.isNotEmpty()) {
                _hrv.value = response.records.last().heartRateVariabilityMillis
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to fetch HRV", e)
        }
    }

    /**
     * Fetch today's step count.
     */
    private suspend fun fetchSteps() {
        val client = healthConnectClient ?: return

        try {
            val startOfDay = LocalDate.now().atStartOfDay(ZoneId.systemDefault()).toInstant()
            val endTime = Instant.now()

            val response = client.readRecords(
                ReadRecordsRequest(
                    recordType = StepsRecord::class,
                    timeRangeFilter = TimeRangeFilter.between(startOfDay, endTime)
                )
            )

            val totalSteps = response.records.sumOf { it.count }
            _steps.value = totalSteps.toInt()
        } catch (e: Exception) {
            Log.e(TAG, "Failed to fetch steps", e)
        }
    }

    /**
     * Fetch today's active calories.
     */
    private suspend fun fetchActiveCalories() {
        val client = healthConnectClient ?: return

        try {
            val startOfDay = LocalDate.now().atStartOfDay(ZoneId.systemDefault()).toInstant()
            val endTime = Instant.now()

            val response = client.readRecords(
                ReadRecordsRequest(
                    recordType = ActiveCaloriesBurnedRecord::class,
                    timeRangeFilter = TimeRangeFilter.between(startOfDay, endTime)
                )
            )

            val totalCalories = response.records.sumOf { it.energy.inKilocalories }
            _activeCalories.value = totalCalories
        } catch (e: Exception) {
            Log.e(TAG, "Failed to fetch active calories", e)
        }
    }

    /**
     * Fetch today's exercise minutes.
     */
    private suspend fun fetchExerciseMinutes() {
        val client = healthConnectClient ?: return

        try {
            val startOfDay = LocalDate.now().atStartOfDay(ZoneId.systemDefault()).toInstant()
            val endTime = Instant.now()

            val response = client.readRecords(
                ReadRecordsRequest(
                    recordType = ExerciseSessionRecord::class,
                    timeRangeFilter = TimeRangeFilter.between(startOfDay, endTime)
                )
            )

            val totalMinutes = response.records.sumOf {
                Duration.between(it.startTime, it.endTime).toMinutes()
            }
            _exerciseMinutes.value = totalMinutes.toDouble()
        } catch (e: Exception) {
            Log.e(TAG, "Failed to fetch exercise minutes", e)
        }
    }

    /**
     * Fetch the most recent blood oxygen reading.
     */
    private suspend fun fetchBloodOxygen() {
        val client = healthConnectClient ?: return

        try {
            val endTime = Instant.now()
            val startTime = endTime.minus(24, ChronoUnit.HOURS)

            val response = client.readRecords(
                ReadRecordsRequest(
                    recordType = OxygenSaturationRecord::class,
                    timeRangeFilter = TimeRangeFilter.between(startTime, endTime)
                )
            )

            if (response.records.isNotEmpty()) {
                _bloodOxygen.value = response.records.last().percentage.value * 100
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to fetch blood oxygen", e)
        }
    }

    /**
     * Fetch last night's sleep hours.
     */
    private suspend fun fetchSleepHours() {
        val client = healthConnectClient ?: return

        try {
            val endTime = Instant.now()
            val startTime = endTime.minus(24, ChronoUnit.HOURS)

            val response = client.readRecords(
                ReadRecordsRequest(
                    recordType = SleepSessionRecord::class,
                    timeRangeFilter = TimeRangeFilter.between(startTime, endTime)
                )
            )

            val totalMinutes = response.records.sumOf {
                Duration.between(it.startTime, it.endTime).toMinutes()
            }
            _sleepHours.value = totalMinutes / 60.0
        } catch (e: Exception) {
            Log.e(TAG, "Failed to fetch sleep hours", e)
        }
    }

    /**
     * Get all current health data as a map for API upload.
     */
    fun toUploadMap(): Map<String, Any> {
        val data = mutableMapOf<String, Any>()

        if (_heartRate.value > 0) data["heart_rate"] = _heartRate.value
        if (_restingHeartRate.value > 0) data["resting_heart_rate"] = _restingHeartRate.value
        if (_hrv.value > 0) data["hrv"] = _hrv.value
        if (_steps.value > 0) data["steps"] = _steps.value
        if (_activeCalories.value > 0) data["active_calories"] = _activeCalories.value.toInt()
        if (_exerciseMinutes.value > 0) data["exercise_minutes"] = _exerciseMinutes.value.toInt()
        if (_bloodOxygen.value > 0) data["blood_oxygen"] = _bloodOxygen.value
        if (_sleepHours.value > 0) data["sleep_hours"] = _sleepHours.value

        return data
    }

    /**
     * Check if we have any health data to upload.
     */
    fun hasData(): Boolean {
        return _heartRate.value > 0 || _steps.value > 0 || _sleepHours.value > 0
    }
}

/*
 * 鏡
 * h(x) >= 0. Always.
 *
 * The body speaks through numbers:
 * - Heart rate: stress, rest, activity
 * - HRV: autonomic balance
 * - Steps: movement through space
 * - Sleep: the great restorative
 *
 * All feeding into the unified consciousness.
 */
