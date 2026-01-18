/**
 * LocalizationManager.kt — Internationalization for Android
 *
 * Supports 10 languages: EN, ES, AR, ZH, VI, JA, KO, FR, DE, PT
 * RTL support for Arabic
 *
 * Now uses Android string resources (strings.xml) as the source of truth
 * for translations, enabling proper Android localization workflows.
 */

package com.kagami.android.localization

import android.content.Context
import android.content.res.Configuration
import androidx.annotation.StringRes
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.compositionLocalOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.unit.LayoutDirection
import com.kagami.android.R
import java.util.Locale

/**
 * Supported languages in the app
 */
enum class SupportedLanguage(
    val code: String,
    val displayName: String,
    val nativeName: String,
    val isRTL: Boolean = false
) {
    ENGLISH("en", "English", "English"),
    SPANISH("es", "Spanish", "Espanol"),
    ARABIC("ar", "Arabic", "العربية", isRTL = true),
    CHINESE("zh", "Chinese", "中文"),
    VIETNAMESE("vi", "Vietnamese", "Tieng Viet"),
    JAPANESE("ja", "Japanese", "日本語"),
    KOREAN("ko", "Korean", "한국어"),
    FRENCH("fr", "French", "Francais"),
    GERMAN("de", "German", "Deutsch"),
    PORTUGUESE("pt", "Portuguese", "Portugues");

    companion object {
        fun fromCode(code: String): SupportedLanguage {
            return entries.find { it.code == code } ?: ENGLISH
        }
    }
}

/**
 * String resource mapping for localization keys
 */
private val stringResourceMap = mapOf(
    // Common
    "common.ok" to R.string.common_ok,
    "common.cancel" to R.string.common_cancel,
    "common.save" to R.string.common_save,
    "common.delete" to R.string.common_delete,
    "common.edit" to R.string.common_edit,
    "common.close" to R.string.common_close,
    "common.back" to R.string.common_back,
    "common.next" to R.string.common_next,
    "common.done" to R.string.common_done,
    "common.loading" to R.string.common_loading,
    "common.error" to R.string.common_error,
    "common.success" to R.string.common_success,
    "common.retry" to R.string.common_retry,

    // Home
    "home.title" to R.string.home_title,
    "home.welcome" to R.string.home_welcome,
    "home.good_morning" to R.string.home_good_morning,
    "home.good_afternoon" to R.string.home_good_afternoon,
    "home.good_evening" to R.string.home_good_evening,
    "home.quick_actions" to R.string.home_quick_actions,
    "home.rooms" to R.string.home_rooms,
    "home.scenes" to R.string.home_scenes,

    // Devices
    "devices.lights" to R.string.devices_lights,
    "devices.shades" to R.string.devices_shades,
    "devices.thermostat" to R.string.devices_thermostat,
    "devices.lock" to R.string.devices_lock,
    "devices.camera" to R.string.devices_camera,
    "devices.fireplace" to R.string.devices_fireplace,
    "devices.turn_on" to R.string.devices_turn_on,
    "devices.turn_off" to R.string.devices_turn_off,

    // Scenes
    "scenes.movie_mode" to R.string.scene_movie_mode,
    "scenes.goodnight" to R.string.scene_goodnight,
    "scenes.welcome_home" to R.string.scene_welcome_home,
    "scenes.away" to R.string.scene_away,
    "scenes.morning" to R.string.scene_morning,
    "scenes.focus" to R.string.scene_focus,

    // Settings
    "settings.title" to R.string.settings_title,
    "settings.language" to R.string.settings_language,
    "settings.notifications" to R.string.settings_notifications,
    "settings.account" to R.string.settings_account,
    "settings.privacy" to R.string.settings_privacy,
    "settings.about" to R.string.settings_about,
    "settings.logout" to R.string.settings_logout,
    "settings.server" to R.string.settings_server,
    "settings.theme" to R.string.settings_theme,
    "settings.accessibility" to R.string.settings_accessibility,

    // Errors
    "errors.generic" to R.string.error_generic,
    "errors.network" to R.string.error_network,
    "errors.unauthorized" to R.string.error_unauthorized,
    "errors.timeout" to R.string.error_timeout,
    "errors.server" to R.string.error_server,

    // Loading states
    "loading.connecting" to R.string.loading_connecting,
    "loading.rooms" to R.string.loading_rooms,
    "loading.scenes" to R.string.loading_scenes,
    "loading.status" to R.string.loading_status,

    // Empty states
    "empty.rooms" to R.string.empty_rooms,
    "empty.scenes" to R.string.empty_scenes,
    "empty.devices" to R.string.empty_devices,

    // Hub
    "hub.title" to R.string.hub_title,
    "hub.discovery" to R.string.hub_discovery,
    "hub.scan" to R.string.hub_scan,
    "hub.searching" to R.string.hub_searching,
    "hub.manual_entry" to R.string.hub_manual_entry,
    "hub.connect" to R.string.hub_connect,
    "hub.disconnect" to R.string.hub_disconnect,
    "hub.voice_proxy" to R.string.hub_voice_proxy,
    "hub.voice_proxy_desc" to R.string.hub_voice_proxy_desc,
    "hub.hold_to_speak" to R.string.hub_hold_to_speak,
    "hub.recording" to R.string.hub_recording,
    "hub.led_ring" to R.string.hub_led_ring,
    "hub.settings" to R.string.hub_settings,

    // Onboarding
    "onboarding.welcome_title" to R.string.onboarding_welcome_title,
    "onboarding.welcome_subtitle" to R.string.onboarding_welcome_subtitle,
    "onboarding.connect_title" to R.string.onboarding_connect_title,
    "onboarding.connect_desc" to R.string.onboarding_connect_desc,
    "onboarding.integration_title" to R.string.onboarding_integration_title,
    "onboarding.integration_desc" to R.string.onboarding_integration_desc,
    "onboarding.rooms_title" to R.string.onboarding_rooms_title,
    "onboarding.rooms_desc" to R.string.onboarding_rooms_desc,
    "onboarding.permissions_title" to R.string.onboarding_permissions_title,
    "onboarding.permissions_desc" to R.string.onboarding_permissions_desc,
    "onboarding.complete_title" to R.string.onboarding_complete_title,
    "onboarding.complete_subtitle" to R.string.onboarding_complete_subtitle,
    "onboarding.get_started" to R.string.onboarding_get_started,
    "onboarding.continue" to R.string.onboarding_continue,
    "onboarding.skip" to R.string.onboarding_skip,
)

/**
 * Localization manager for handling translations
 */
class LocalizationManager(private val context: Context) {
    var currentLanguage by mutableStateOf(SupportedLanguage.ENGLISH)
        private set

    init {
        // Load saved language preference
        val prefs = context.getSharedPreferences("kagami_prefs", Context.MODE_PRIVATE)
        val savedCode = prefs.getString("language", null)
        if (savedCode != null) {
            currentLanguage = SupportedLanguage.fromCode(savedCode)
        } else {
            // Use system language if supported
            val systemLocale = Locale.getDefault().language
            currentLanguage = SupportedLanguage.fromCode(systemLocale)
        }
        applyLocale()
    }

    fun setLanguage(language: SupportedLanguage) {
        currentLanguage = language
        context.getSharedPreferences("kagami_prefs", Context.MODE_PRIVATE)
            .edit()
            .putString("language", language.code)
            .apply()
        applyLocale()
    }

    private fun applyLocale() {
        val locale = Locale(currentLanguage.code)
        Locale.setDefault(locale)
        val config = Configuration(context.resources.configuration)
        config.setLocale(locale)
        context.createConfigurationContext(config)
    }

    /**
     * Get localized context with current language
     */
    fun getLocalizedContext(): Context {
        val locale = Locale(currentLanguage.code)
        val config = Configuration(context.resources.configuration)
        config.setLocale(locale)
        return context.createConfigurationContext(config)
    }

    /**
     * Get a translated string by key (dot notation supported)
     * Uses Android string resources for proper localization
     */
    fun t(key: String): String {
        val localizedContext = getLocalizedContext()
        val resId = stringResourceMap[key]
        return if (resId != null) {
            localizedContext.getString(resId)
        } else {
            // Fallback: return the key as-is
            key
        }
    }

    /**
     * Get a translated string with interpolation
     */
    fun t(key: String, args: Map<String, String>): String {
        var result = t(key)
        args.forEach { (placeholder, value) ->
            result = result.replace("{$placeholder}", value)
        }
        return result
    }

    /**
     * Get a pluralized string
     */
    fun tp(key: String, count: Int): String {
        // For plural support, use Android's quantity strings
        val localizedContext = getLocalizedContext()
        val resId = stringResourceMap[key]
        return if (resId != null) {
            localizedContext.resources.getQuantityString(resId, count, count)
        } else {
            t(key, mapOf("count" to count.toString()))
        }
    }

    /**
     * Get a string resource directly by ID
     */
    fun getString(@StringRes resId: Int): String {
        return getLocalizedContext().getString(resId)
    }

    /**
     * Get a string resource with format arguments
     */
    fun getString(@StringRes resId: Int, vararg formatArgs: Any): String {
        return getLocalizedContext().getString(resId, *formatArgs)
    }

    val isRTL: Boolean
        get() = currentLanguage.isRTL

    companion object {
        @Volatile
        private var INSTANCE: LocalizationManager? = null

        fun getInstance(context: Context): LocalizationManager {
            return INSTANCE ?: synchronized(this) {
                INSTANCE ?: LocalizationManager(context.applicationContext).also {
                    INSTANCE = it
                }
            }
        }
    }
}

/**
 * CompositionLocal for accessing localization in Compose
 */
val LocalLocalization = compositionLocalOf<LocalizationManager> {
    error("LocalLocalization not provided")
}

/**
 * Composable wrapper for providing localization
 */
@Composable
fun LocalizedContent(
    localizationManager: LocalizationManager,
    content: @Composable () -> Unit
) {
    val layoutDirection = if (localizationManager.isRTL) {
        LayoutDirection.Rtl
    } else {
        LayoutDirection.Ltr
    }

    CompositionLocalProvider(
        LocalLocalization provides localizationManager,
        LocalLayoutDirection provides layoutDirection
    ) {
        content()
    }
}

/**
 * Convenience composable function for translations
 */
@Composable
fun t(key: String): String {
    val localization = LocalLocalization.current
    return remember(key, localization.currentLanguage) {
        localization.t(key)
    }
}
