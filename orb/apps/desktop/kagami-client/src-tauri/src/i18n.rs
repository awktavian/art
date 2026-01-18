//! Internationalization (i18n) Module
//!
//! Provides locale-aware string resolution for the Kagami client.
//! Supports JSON-based locale files with fallback to English.
//!
//! Colony: Beacon (e5) - Communication

use once_cell::sync::Lazy;
use serde_json::Value;
use std::collections::HashMap;
use std::sync::RwLock;
use tracing::{debug, warn};

/// Embedded locale files
const LOCALE_EN: &str = include_str!("../locales/en.json");
const LOCALE_ES: &str = include_str!("../locales/es.json");

/// Supported locales
const SUPPORTED_LOCALES: &[&str] = &["en", "es"];

/// Default locale
const DEFAULT_LOCALE: &str = "en";

/// Global locale state
static CURRENT_LOCALE: Lazy<RwLock<String>> = Lazy::new(|| {
    RwLock::new(detect_system_locale())
});

/// Loaded translations cache
static TRANSLATIONS: Lazy<RwLock<HashMap<String, Value>>> = Lazy::new(|| {
    let mut map = HashMap::new();

    // Load embedded locales
    if let Ok(en) = serde_json::from_str(LOCALE_EN) {
        map.insert("en".to_string(), en);
    }
    if let Ok(es) = serde_json::from_str(LOCALE_ES) {
        map.insert("es".to_string(), es);
    }

    RwLock::new(map)
});

/// Detect system locale from environment
fn detect_system_locale() -> String {
    // Try common environment variables
    for var in &["LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"] {
        if let Ok(lang) = std::env::var(var) {
            let locale = lang.split('.').next().unwrap_or(&lang);
            let locale = locale.split('_').next().unwrap_or(locale);

            if SUPPORTED_LOCALES.contains(&locale) {
                debug!("Detected system locale: {} from {}", locale, var);
                return locale.to_string();
            }
        }
    }

    // macOS-specific detection
    #[cfg(target_os = "macos")]
    {
        if let Ok(output) = std::process::Command::new("defaults")
            .args(["read", "-g", "AppleLanguages"])
            .output()
        {
            let stdout = String::from_utf8_lossy(&output.stdout);
            for locale in SUPPORTED_LOCALES {
                if stdout.contains(locale) {
                    debug!("Detected macOS locale: {}", locale);
                    return locale.to_string();
                }
            }
        }
    }

    // Windows-specific detection
    #[cfg(target_os = "windows")]
    {
        if let Ok(output) = std::process::Command::new("powershell")
            .args(["-Command", "(Get-Culture).TwoLetterISOLanguageName"])
            .output()
        {
            let locale = String::from_utf8_lossy(&output.stdout).trim().to_string();
            if SUPPORTED_LOCALES.contains(&locale.as_str()) {
                debug!("Detected Windows locale: {}", locale);
                return locale;
            }
        }
    }

    debug!("Using default locale: {}", DEFAULT_LOCALE);
    DEFAULT_LOCALE.to_string()
}

/// Get the current locale
pub fn get_locale() -> String {
    CURRENT_LOCALE
        .read()
        .map(|guard| guard.clone())
        .unwrap_or_else(|_| DEFAULT_LOCALE.to_string())
}

/// Set the current locale
pub fn set_locale(locale: &str) {
    if let Ok(mut guard) = CURRENT_LOCALE.write() {
        if SUPPORTED_LOCALES.contains(&locale) {
            *guard = locale.to_string();
            debug!("Locale set to: {}", locale);
        } else {
            warn!("Unsupported locale: {}, using default", locale);
            *guard = DEFAULT_LOCALE.to_string();
        }
    }
}

/// Get a translated string by key path (e.g., "greetings.good_morning")
pub fn t(key: &str) -> String {
    let locale = get_locale();
    t_with_locale(key, &locale)
}

/// Get a translated string with specific locale
pub fn t_with_locale(key: &str, locale: &str) -> String {
    let Ok(translations) = TRANSLATIONS.read() else {
        // Fallback if lock is poisoned - return the key itself
        return key.to_string();
    };

    // Try requested locale first
    if let Some(value) = get_nested_value(&translations, locale, key) {
        if let Some(s) = value.as_str() {
            return s.to_string();
        }
    }

    // Fallback to English
    if locale != DEFAULT_LOCALE {
        if let Some(value) = get_nested_value(&translations, DEFAULT_LOCALE, key) {
            if let Some(s) = value.as_str() {
                return s.to_string();
            }
        }
    }

    // Return key if not found
    warn!("Translation not found for key: {}", key);
    key.to_string()
}

/// Get a translated string with variable substitution
/// Variables are specified as {name} in the translation string
pub fn t_fmt(key: &str, vars: &[(&str, &str)]) -> String {
    let mut result = t(key);
    for (name, value) in vars {
        result = result.replace(&format!("{{{}}}", name), value);
    }
    result
}

/// Get nested value from translations
fn get_nested_value<'a>(
    translations: &'a HashMap<String, Value>,
    locale: &str,
    key: &str,
) -> Option<&'a Value> {
    let root = translations.get(locale)?;
    let parts: Vec<&str> = key.split('.').collect();

    let mut current = root;
    for part in parts {
        current = current.get(part)?;
    }

    Some(current)
}

/// Get all supported locales
pub fn supported_locales() -> &'static [&'static str] {
    SUPPORTED_LOCALES
}

// ============================================================================
// Convenience Functions for Common Strings
// ============================================================================

/// Get greeting based on time of day
pub fn greeting_for_hour(hour: u32) -> String {
    if hour >= 22 || hour < 6 {
        t("greetings.night_mode")
    } else if hour < 12 {
        t("greetings.good_morning")
    } else if hour < 17 {
        t("greetings.good_afternoon")
    } else {
        t("greetings.good_evening")
    }
}

/// Get status text for movie mode
pub fn movie_mode_status() -> String {
    t("greetings.movie_mode_active")
}

/// Get tooltip for tray icon
pub fn tray_tooltip(connected: bool, movie_mode: bool, alert: bool) -> String {
    if alert {
        t("app.tooltip_alert")
    } else if !connected {
        t("app.tooltip_offline")
    } else if movie_mode {
        t("app.tooltip_movie_mode")
    } else {
        t("app.tooltip")
    }
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_t_returns_english_by_default() {
        set_locale("en");
        assert_eq!(t("app.name"), "Kagami");
        assert_eq!(t("status.ready"), "Ready");
    }

    #[test]
    fn test_t_returns_spanish() {
        set_locale("es");
        assert_eq!(t("status.ready"), "Listo");
        assert_eq!(t("greetings.good_morning"), "Buenos dias");
    }

    #[test]
    fn test_t_fallback_to_english() {
        set_locale("es");
        // Test a key that might only exist in English
        let result = t("app.name");
        assert_eq!(result, "Kagami");
    }

    #[test]
    fn test_t_returns_key_if_not_found() {
        set_locale("en");
        let result = t("nonexistent.key");
        assert_eq!(result, "nonexistent.key");
    }

    #[test]
    fn test_t_fmt_substitutes_variables() {
        set_locale("en");
        let result = t_fmt("errors.window_not_found", &[("name", "main")]);
        assert_eq!(result, "Window not found: main");
    }

    #[test]
    fn test_greeting_for_hour() {
        set_locale("en");
        assert_eq!(greeting_for_hour(8), "Good Morning");
        assert_eq!(greeting_for_hour(14), "Good Afternoon");
        assert_eq!(greeting_for_hour(19), "Good Evening");
        assert_eq!(greeting_for_hour(23), "Night Mode");
    }

    #[test]
    fn test_tray_tooltip() {
        set_locale("en");
        assert_eq!(tray_tooltip(true, false, false), "Kagami");
        assert_eq!(tray_tooltip(false, false, false), "Kagami (Offline)");
        assert_eq!(tray_tooltip(true, true, false), "Kagami - Movie Mode");
        assert_eq!(tray_tooltip(true, false, true), "Kagami - Alert");
    }
}
