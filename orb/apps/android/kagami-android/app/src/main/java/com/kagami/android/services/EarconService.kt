package com.kagami.android.services

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioManager
import android.media.MediaPlayer
import android.net.Uri
import android.os.Build
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.*
import java.io.File
import java.net.URL
import javax.inject.Inject
import javax.inject.Singleton

/**
 * EarconService — BBC Symphony Orchestra Earcons for Android
 *
 * Features:
 * - 36 BBC Symphony Orchestra earcons (REAPER + BBC SO VST)
 * - Tier 1 earcons bundled with app in assets/earcons/
 * - Tier 2 earcons lazy-loaded from CDN
 * - Integrated with KagamiHaptics for coordinated feedback
 * - ExoPlayer for high-quality playback
 *
 * Architecture:
 *   Event → EarconService → MediaPlayer → Audio Output
 *                        → KagamiHaptics → Vibration
 *
 * h(x) >= 0. Always.
 */

/**
 * Available earcons (36 total)
 */
enum class Earcon(val fileName: String) {
    // Tier 1 — Core (14 bundled)
    NOTIFICATION("notification"),
    SUCCESS("success"),
    ERROR("error"),
    ALERT("alert"),
    ARRIVAL("arrival"),
    DEPARTURE("departure"),
    CELEBRATION("celebration"),
    SETTLING("settling"),
    AWAKENING("awakening"),
    CINEMATIC("cinematic"),
    FOCUS("focus"),
    SECURITY_ARM("security_arm"),
    PACKAGE("package"),
    MEETING_SOON("meeting_soon"),

    // Tier 2 — Extended (22 CDN)
    ROOM_ENTER("room_enter"),
    DOOR_OPEN("door_open"),
    DOOR_CLOSE("door_close"),
    LOCK_ENGAGED("lock_engaged"),
    VOICE_ACKNOWLEDGE("voice_acknowledge"),
    VOICE_COMPLETE("voice_complete"),
    WASHER_COMPLETE("washer_complete"),
    COFFEE_READY("coffee_ready"),
    MORNING_SEQUENCE("morning_sequence"),
    EVENING_TRANSITION("evening_transition"),
    MIDNIGHT("midnight"),
    STORM_APPROACHING("storm_approaching"),
    RAIN_STARTING("rain_starting"),
    MOTION_DETECTED("motion_detected"),
    CAMERA_ALERT("camera_alert"),
    MESSAGE_RECEIVED("message_received"),
    HOME_EMPTY("home_empty"),
    FIRST_HOME("first_home"),
    OVEN_PREHEAT("oven_preheat"),
    DISHWASHER_COMPLETE("dishwasher_complete"),
    DRYER_COMPLETE("dryer_complete");

    /** Whether this earcon is bundled (Tier 1) */
    val isTier1: Boolean
        get() = when (this) {
            NOTIFICATION, SUCCESS, ERROR, ALERT, ARRIVAL, DEPARTURE,
            CELEBRATION, SETTLING, AWAKENING, CINEMATIC, FOCUS,
            SECURITY_ARM, PACKAGE, MEETING_SOON -> true
            else -> false
        }

    /** Corresponding haptic pattern */
    val hapticPattern: HapticPattern
        get() = when (this) {
            SUCCESS, CELEBRATION, ARRIVAL -> HapticPattern.SUCCESS
            ERROR -> HapticPattern.ERROR
            ALERT, CAMERA_ALERT -> HapticPattern.WARNING
            NOTIFICATION, MESSAGE_RECEIVED, PACKAGE -> HapticPattern.MEDIUM_IMPACT
            FOCUS, ROOM_ENTER -> HapticPattern.LIGHT_IMPACT
            LOCK_ENGAGED, SECURITY_ARM -> HapticPattern.HEAVY_IMPACT
            DEPARTURE, SETTLING, HOME_EMPTY -> HapticPattern.SOFT_IMPACT
            VOICE_ACKNOWLEDGE -> HapticPattern.SELECTION
            VOICE_COMPLETE -> HapticPattern.SUCCESS
            else -> HapticPattern.LIGHT_IMPACT
        }

    companion object {
        fun fromFileName(name: String): Earcon? = entries.find { it.fileName == name }
    }
}

/**
 * Semantic feedback events that map to earcons
 */
enum class FeedbackEvent(val earcon: Earcon) {
    TAP(Earcon.FOCUS),
    SELECT(Earcon.FOCUS),
    SCENE_ACTIVATED(Earcon.SUCCESS),
    LIGHTS_ON(Earcon.DOOR_OPEN),
    LIGHTS_OFF(Earcon.DOOR_CLOSE),
    SHADE_OPEN(Earcon.DOOR_OPEN),
    SHADE_CLOSE(Earcon.DOOR_CLOSE),
}

@Singleton
class EarconService @Inject constructor(
    @ApplicationContext private val context: Context
) {
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private val mainScope = CoroutineScope(Dispatchers.Main + SupervisorJob())

    // Audio
    private var mediaPlayer: MediaPlayer? = null
    private val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager

    // Caching
    private val cacheDir = File(context.cacheDir, "earcons")
    private val loadingJobs = mutableMapOf<String, Job>()

    // State
    var isInitialized = false
        private set
    var isMuted = false
    var masterVolume = 0.7f
        set(value) {
            field = value.coerceIn(0f, 1f)
            mediaPlayer?.setVolume(field, field)
        }
    var tier1Loaded = false
        private set

    // Haptics integration
    private val haptics: KagamiHaptics by lazy { KagamiHaptics.getInstance(context) }

    // CDN
    private val cdnBaseUrl = "https://storage.googleapis.com/kagami-media-public/earcons/v1/mp3"

    init {
        initialize()
    }

    /**
     * Initialize the earcon service
     */
    fun initialize() {
        if (isInitialized) return

        // Create cache directory
        cacheDir.mkdirs()

        // Setup media player
        mediaPlayer = MediaPlayer().apply {
            setAudioAttributes(
                AudioAttributes.Builder()
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                    .setUsage(AudioAttributes.USAGE_NOTIFICATION_EVENT)
                    .build()
            )
            setVolume(masterVolume, masterVolume)
        }

        isInitialized = true

        // Preload Tier 1 earcons
        scope.launch {
            preloadTier1()
        }
    }

    /**
     * Preload all Tier 1 earcons from assets
     */
    private suspend fun preloadTier1() {
        val tier1Earcons = Earcon.entries.filter { it.isTier1 }
        var loadedCount = 0

        for (earcon in tier1Earcons) {
            if (loadFromAssets(earcon.fileName)) {
                loadedCount++
            }
        }

        tier1Loaded = loadedCount > 0
        println("EarconService: Loaded $loadedCount/${tier1Earcons.size} Tier 1 earcons")
    }

    // ========================================================================
    // Playback
    // ========================================================================

    /**
     * Play an earcon with optional haptic feedback
     */
    fun play(
        earcon: Earcon,
        withHaptic: Boolean = true,
    ) {
        if (!isInitialized || isMuted) return

        // Play haptic first (lower latency)
        if (withHaptic) {
            haptics.play(earcon.hapticPattern)
        }

        // Play audio
        scope.launch {
            playAudio(earcon.fileName)
        }
    }

    /**
     * Play a semantic feedback event
     */
    fun play(event: FeedbackEvent, withHaptic: Boolean = true) {
        play(event.earcon, withHaptic)
    }

    /**
     * Play an earcon by name (for dynamic usage)
     */
    fun playByName(name: String, withHaptic: Boolean = true) {
        val earcon = Earcon.fromFileName(name)
        if (earcon != null) {
            play(earcon, withHaptic)
        } else {
            println("EarconService: Unknown earcon: $name")
        }
    }

    private suspend fun playAudio(name: String) {
        val file = getCachedFile(name)

        if (file?.exists() == true) {
            playFile(file)
        } else {
            // Try to load
            val loaded = if (Earcon.fromFileName(name)?.isTier1 == true) {
                loadFromAssets(name)
            } else {
                loadFromCDN(name)
            }

            if (loaded) {
                getCachedFile(name)?.let { playFile(it) }
            }
        }
    }

    private fun playFile(file: File) {
        mainScope.launch {
            try {
                mediaPlayer?.apply {
                    reset()
                    setDataSource(file.absolutePath)
                    prepare()
                    setVolume(masterVolume, masterVolume)
                    start()
                }
            } catch (e: Exception) {
                println("EarconService: Playback failed: ${e.message}")
            }
        }
    }

    // ========================================================================
    // Loading
    // ========================================================================

    private fun getCachedFile(name: String): File? {
        val file = File(cacheDir, "$name.mp3")
        return if (file.exists()) file else null
    }

    private suspend fun loadFromAssets(name: String): Boolean {
        val cacheFile = File(cacheDir, "$name.mp3")
        if (cacheFile.exists()) return true

        return try {
            context.assets.open("earcons/$name.mp3").use { input ->
                cacheFile.outputStream().use { output ->
                    input.copyTo(output)
                }
            }
            true
        } catch (e: Exception) {
            // Asset not found, will try CDN
            false
        }
    }

    private suspend fun loadFromCDN(name: String): Boolean {
        val cacheFile = File(cacheDir, "$name.mp3")
        if (cacheFile.exists()) return true

        // Check for existing loading job
        if (loadingJobs.containsKey(name)) {
            loadingJobs[name]?.join()
            return cacheFile.exists()
        }

        val job = scope.launch {
            try {
                val url = URL("$cdnBaseUrl/$name.mp3")
                val connection = url.openConnection()
                connection.connectTimeout = 10000
                connection.readTimeout = 30000

                connection.getInputStream().use { input ->
                    cacheFile.outputStream().use { output ->
                        input.copyTo(output)
                    }
                }

                println("EarconService: Downloaded from CDN: $name")

            } catch (e: Exception) {
                println("EarconService: CDN download failed for $name: ${e.message}")
                cacheFile.delete()
            }
        }

        loadingJobs[name] = job
        job.join()
        loadingJobs.remove(name)

        return cacheFile.exists()
    }

    // ========================================================================
    // Controls
    // ========================================================================

    fun mute() {
        isMuted = true
    }

    fun unmute() {
        isMuted = false
    }

    /**
     * Check if an earcon is loaded
     */
    fun isLoaded(earcon: Earcon): Boolean {
        return getCachedFile(earcon.fileName)?.exists() == true
    }

    /**
     * Preload specific earcons
     */
    fun preload(earcons: List<Earcon>) {
        scope.launch {
            for (earcon in earcons) {
                if (!isLoaded(earcon)) {
                    if (earcon.isTier1) {
                        loadFromAssets(earcon.fileName)
                    } else {
                        loadFromCDN(earcon.fileName)
                    }
                }
            }
        }
    }

    /**
     * Clear Tier 2 cache (keep Tier 1)
     */
    fun clearTier2Cache() {
        cacheDir.listFiles()?.forEach { file ->
            val name = file.nameWithoutExtension
            if (Earcon.fromFileName(name)?.isTier1 == false) {
                file.delete()
            }
        }
    }

    /**
     * Get total cache size in bytes
     */
    fun getCacheSize(): Long {
        return cacheDir.listFiles()?.sumOf { it.length() } ?: 0
    }

    /**
     * Release resources
     */
    fun release() {
        mediaPlayer?.release()
        mediaPlayer = null
        scope.cancel()
        mainScope.cancel()
        isInitialized = false
    }

    companion object {
        @Volatile
        private var instance: EarconService? = null

        fun getInstance(context: Context): EarconService {
            return instance ?: synchronized(this) {
                instance ?: EarconService(context.applicationContext).also { instance = it }
            }
        }
    }
}

/*
 * 鏡
 * h(x) >= 0. Always.
 *
 * BBC Symphony Orchestra earcons provide virtuoso audio feedback.
 * Each earcon is a complete musical phrase with emotional intent.
 * Coordinated with haptics for multi-sensory experience.
 */
