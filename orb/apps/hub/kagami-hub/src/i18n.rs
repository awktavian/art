//! Internationalization (i18n) Module for Kagami Hub
//!
//! Provides localized strings for UI, voice feedback, and system messages.
//! Supports multiple languages with fallback to English.
//!
//! Colony: Crystal (e7) - Communication and feedback
//!
//! h(x) >= 0 always

use std::collections::HashMap;
use std::sync::{OnceLock, RwLock};

// ============================================================================
// Language Configuration
// ============================================================================

/// Supported languages
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum Language {
    English,
    Spanish,
    French,
    German,
    Japanese,
    Chinese,
}

impl Default for Language {
    fn default() -> Self {
        Language::English
    }
}

impl Language {
    /// Get language code (ISO 639-1)
    pub fn code(&self) -> &'static str {
        match self {
            Language::English => "en",
            Language::Spanish => "es",
            Language::French => "fr",
            Language::German => "de",
            Language::Japanese => "ja",
            Language::Chinese => "zh",
        }
    }

    /// Parse language from code
    pub fn from_code(code: &str) -> Option<Self> {
        match code.to_lowercase().as_str() {
            "en" | "en-us" | "en-gb" => Some(Language::English),
            "es" | "es-es" | "es-mx" => Some(Language::Spanish),
            "fr" | "fr-fr" | "fr-ca" => Some(Language::French),
            "de" | "de-de" | "de-at" => Some(Language::German),
            "ja" | "ja-jp" => Some(Language::Japanese),
            "zh" | "zh-cn" | "zh-tw" => Some(Language::Chinese),
            _ => None,
        }
    }

    /// Get display name in the language itself
    pub fn native_name(&self) -> &'static str {
        match self {
            Language::English => "English",
            Language::Spanish => "Espanol",
            Language::French => "Francais",
            Language::German => "Deutsch",
            Language::Japanese => "Nihongo",
            Language::Chinese => "Zhongwen",
        }
    }
}

// ============================================================================
// Message Keys
// ============================================================================

/// Message keys for localization
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum MessageKey {
    // Voice feedback - confirmations
    LightsOn,
    LightsOff,
    LightsDimmed,
    LightsBrightened,
    SceneActivated,
    ShadesOpened,
    ShadesClosed,
    FireplaceOn,
    FireplaceOff,
    LockLocked,
    LockUnlocked,
    TVRaised,
    TVLowered,
    VolumeUp,
    VolumeDown,
    MusicPlaying,
    MusicPaused,

    // Voice feedback - errors
    CommandNotUnderstood,
    DeviceNotFound,
    ActionFailed,
    PermissionDenied,

    // Voice feedback - status
    SystemReady,
    ListeningForCommand,
    ProcessingCommand,
    ExecutingCommand,
    AllSystemsSafe,
    SafetyAlert,

    // Web UI - labels
    WebTitle,
    WebStatus,
    WebConnected,
    WebDisconnected,
    WebSettings,
    WebVoiceControl,
    WebDevices,
    WebScenes,
    WebAutomation,
    WebLEDControl,
    WebLEDPattern,
    WebBrightness,

    // Web UI - buttons
    WebSave,
    WebCancel,
    WebRefresh,
    WebConnect,
    WebDisconnect,

    // Room names
    RoomLivingRoom,
    RoomKitchen,
    RoomBedroom,
    RoomBathroom,
    RoomOffice,
    RoomGarage,
    RoomBasement,
    RoomHallway,
    RoomEntry,
    RoomPatio,
    RoomBackyard,

    // Scene names
    SceneMovieMode,
    SceneGoodnight,
    SceneWelcomeHome,
    SceneMorning,
    SceneDinner,
    SceneRomantic,
    SceneParty,
    SceneFocus,
    SceneRelax,
}

// ============================================================================
// Translation Store
// ============================================================================

type TranslationMap = HashMap<MessageKey, &'static str>;

/// Global translation store
static TRANSLATIONS: OnceLock<HashMap<Language, TranslationMap>> = OnceLock::new();

/// Current language setting
static CURRENT_LANGUAGE: OnceLock<RwLock<Language>> = OnceLock::new();

fn get_current_language() -> Language {
    CURRENT_LANGUAGE
        .get_or_init(|| RwLock::new(Language::English))
        .read()
        .map(|l| *l)
        .unwrap_or(Language::English)
}

/// Set the current language
pub fn set_language(lang: Language) {
    let lock = CURRENT_LANGUAGE.get_or_init(|| RwLock::new(Language::English));
    if let Ok(mut current) = lock.write() {
        *current = lang;
    }
}

/// Get the current language
pub fn language() -> Language {
    get_current_language()
}

fn get_translations() -> &'static HashMap<Language, TranslationMap> {
    TRANSLATIONS.get_or_init(|| {
        let mut all_translations = HashMap::new();

        // English translations
        let mut en = HashMap::new();
        // Confirmations
        en.insert(MessageKey::LightsOn, "Lights on");
        en.insert(MessageKey::LightsOff, "Lights off");
        en.insert(MessageKey::LightsDimmed, "Lights dimmed");
        en.insert(MessageKey::LightsBrightened, "Lights brightened");
        en.insert(MessageKey::SceneActivated, "Scene activated");
        en.insert(MessageKey::ShadesOpened, "Shades opened");
        en.insert(MessageKey::ShadesClosed, "Shades closed");
        en.insert(MessageKey::FireplaceOn, "Fireplace on");
        en.insert(MessageKey::FireplaceOff, "Fireplace off");
        en.insert(MessageKey::LockLocked, "Door locked");
        en.insert(MessageKey::LockUnlocked, "Door unlocked");
        en.insert(MessageKey::TVRaised, "TV raised");
        en.insert(MessageKey::TVLowered, "TV lowered");
        en.insert(MessageKey::VolumeUp, "Volume up");
        en.insert(MessageKey::VolumeDown, "Volume down");
        en.insert(MessageKey::MusicPlaying, "Playing music");
        en.insert(MessageKey::MusicPaused, "Music paused");
        // Errors
        en.insert(MessageKey::CommandNotUnderstood, "Sorry, I didn't understand that");
        en.insert(MessageKey::DeviceNotFound, "Device not found");
        en.insert(MessageKey::ActionFailed, "Action failed");
        en.insert(MessageKey::PermissionDenied, "Permission denied");
        // Status
        en.insert(MessageKey::SystemReady, "Kagami ready");
        en.insert(MessageKey::ListeningForCommand, "Listening");
        en.insert(MessageKey::ProcessingCommand, "Processing");
        en.insert(MessageKey::ExecutingCommand, "Executing");
        en.insert(MessageKey::AllSystemsSafe, "All systems safe");
        en.insert(MessageKey::SafetyAlert, "Safety alert");
        // Web UI labels
        en.insert(MessageKey::WebTitle, "Kagami Hub");
        en.insert(MessageKey::WebStatus, "Status");
        en.insert(MessageKey::WebConnected, "Connected");
        en.insert(MessageKey::WebDisconnected, "Disconnected");
        en.insert(MessageKey::WebSettings, "Settings");
        en.insert(MessageKey::WebVoiceControl, "Voice Control");
        en.insert(MessageKey::WebDevices, "Devices");
        en.insert(MessageKey::WebScenes, "Scenes");
        en.insert(MessageKey::WebAutomation, "Automation");
        en.insert(MessageKey::WebLEDControl, "LED Control");
        en.insert(MessageKey::WebLEDPattern, "Pattern");
        en.insert(MessageKey::WebBrightness, "Brightness");
        // Web UI buttons
        en.insert(MessageKey::WebSave, "Save");
        en.insert(MessageKey::WebCancel, "Cancel");
        en.insert(MessageKey::WebRefresh, "Refresh");
        en.insert(MessageKey::WebConnect, "Connect");
        en.insert(MessageKey::WebDisconnect, "Disconnect");
        // Room names
        en.insert(MessageKey::RoomLivingRoom, "Living Room");
        en.insert(MessageKey::RoomKitchen, "Kitchen");
        en.insert(MessageKey::RoomBedroom, "Bedroom");
        en.insert(MessageKey::RoomBathroom, "Bathroom");
        en.insert(MessageKey::RoomOffice, "Office");
        en.insert(MessageKey::RoomGarage, "Garage");
        en.insert(MessageKey::RoomBasement, "Basement");
        en.insert(MessageKey::RoomHallway, "Hallway");
        en.insert(MessageKey::RoomEntry, "Entry");
        en.insert(MessageKey::RoomPatio, "Patio");
        en.insert(MessageKey::RoomBackyard, "Backyard");
        // Scene names
        en.insert(MessageKey::SceneMovieMode, "Movie Mode");
        en.insert(MessageKey::SceneGoodnight, "Goodnight");
        en.insert(MessageKey::SceneWelcomeHome, "Welcome Home");
        en.insert(MessageKey::SceneMorning, "Morning");
        en.insert(MessageKey::SceneDinner, "Dinner");
        en.insert(MessageKey::SceneRomantic, "Romantic");
        en.insert(MessageKey::SceneParty, "Party Mode");
        en.insert(MessageKey::SceneFocus, "Focus");
        en.insert(MessageKey::SceneRelax, "Relax");
        all_translations.insert(Language::English, en);

        // Spanish translations
        let mut es = HashMap::new();
        es.insert(MessageKey::LightsOn, "Luces encendidas");
        es.insert(MessageKey::LightsOff, "Luces apagadas");
        es.insert(MessageKey::LightsDimmed, "Luces atenuadas");
        es.insert(MessageKey::LightsBrightened, "Luces intensificadas");
        es.insert(MessageKey::SceneActivated, "Escena activada");
        es.insert(MessageKey::ShadesOpened, "Persianas abiertas");
        es.insert(MessageKey::ShadesClosed, "Persianas cerradas");
        es.insert(MessageKey::FireplaceOn, "Chimenea encendida");
        es.insert(MessageKey::FireplaceOff, "Chimenea apagada");
        es.insert(MessageKey::LockLocked, "Puerta cerrada con llave");
        es.insert(MessageKey::LockUnlocked, "Puerta desbloqueada");
        es.insert(MessageKey::CommandNotUnderstood, "Lo siento, no entendi eso");
        es.insert(MessageKey::SystemReady, "Kagami listo");
        es.insert(MessageKey::WebTitle, "Centro Kagami");
        es.insert(MessageKey::WebStatus, "Estado");
        es.insert(MessageKey::WebConnected, "Conectado");
        es.insert(MessageKey::WebDisconnected, "Desconectado");
        es.insert(MessageKey::WebSettings, "Configuracion");
        es.insert(MessageKey::WebSave, "Guardar");
        es.insert(MessageKey::WebCancel, "Cancelar");
        es.insert(MessageKey::RoomLivingRoom, "Sala de estar");
        es.insert(MessageKey::RoomKitchen, "Cocina");
        es.insert(MessageKey::RoomBedroom, "Dormitorio");
        all_translations.insert(Language::Spanish, es);

        // French translations
        let mut fr = HashMap::new();
        fr.insert(MessageKey::LightsOn, "Lumieres allumees");
        fr.insert(MessageKey::LightsOff, "Lumieres eteintes");
        fr.insert(MessageKey::SceneActivated, "Scene activee");
        fr.insert(MessageKey::CommandNotUnderstood, "Desole, je n'ai pas compris");
        fr.insert(MessageKey::SystemReady, "Kagami pret");
        fr.insert(MessageKey::WebTitle, "Hub Kagami");
        fr.insert(MessageKey::WebStatus, "Statut");
        fr.insert(MessageKey::WebConnected, "Connecte");
        fr.insert(MessageKey::WebDisconnected, "Deconnecte");
        fr.insert(MessageKey::WebSettings, "Parametres");
        fr.insert(MessageKey::WebSave, "Sauvegarder");
        fr.insert(MessageKey::WebCancel, "Annuler");
        fr.insert(MessageKey::RoomLivingRoom, "Salon");
        fr.insert(MessageKey::RoomKitchen, "Cuisine");
        fr.insert(MessageKey::RoomBedroom, "Chambre");
        all_translations.insert(Language::French, fr);

        // German translations
        let mut de = HashMap::new();
        de.insert(MessageKey::LightsOn, "Lichter an");
        de.insert(MessageKey::LightsOff, "Lichter aus");
        de.insert(MessageKey::SceneActivated, "Szene aktiviert");
        de.insert(MessageKey::CommandNotUnderstood, "Entschuldigung, das habe ich nicht verstanden");
        de.insert(MessageKey::SystemReady, "Kagami bereit");
        de.insert(MessageKey::WebTitle, "Kagami Hub");
        de.insert(MessageKey::WebStatus, "Status");
        de.insert(MessageKey::WebConnected, "Verbunden");
        de.insert(MessageKey::WebDisconnected, "Getrennt");
        de.insert(MessageKey::WebSettings, "Einstellungen");
        de.insert(MessageKey::WebSave, "Speichern");
        de.insert(MessageKey::WebCancel, "Abbrechen");
        de.insert(MessageKey::RoomLivingRoom, "Wohnzimmer");
        de.insert(MessageKey::RoomKitchen, "Kueche");
        de.insert(MessageKey::RoomBedroom, "Schlafzimmer");
        all_translations.insert(Language::German, de);

        // Japanese translations
        let mut ja = HashMap::new();
        ja.insert(MessageKey::LightsOn, "Raito on");
        ja.insert(MessageKey::LightsOff, "Raito ofu");
        ja.insert(MessageKey::SceneActivated, "Shin kado");
        ja.insert(MessageKey::CommandNotUnderstood, "Sumimasen, wakaranakatta");
        ja.insert(MessageKey::SystemReady, "Kagami junbi kanryo");
        ja.insert(MessageKey::WebTitle, "Kagami Habu");
        ja.insert(MessageKey::WebStatus, "Suteetasu");
        ja.insert(MessageKey::WebConnected, "Setsuzoku-chuu");
        ja.insert(MessageKey::WebDisconnected, "Setsuzoku kaijo");
        ja.insert(MessageKey::WebSettings, "Settei");
        ja.insert(MessageKey::WebSave, "Hozon");
        ja.insert(MessageKey::WebCancel, "Kyanseru");
        ja.insert(MessageKey::RoomLivingRoom, "Ribingu ruumu");
        ja.insert(MessageKey::RoomKitchen, "Kicchin");
        ja.insert(MessageKey::RoomBedroom, "Shinshitsu");
        all_translations.insert(Language::Japanese, ja);

        // Chinese translations
        let mut zh = HashMap::new();
        zh.insert(MessageKey::LightsOn, "Deng kai le");
        zh.insert(MessageKey::LightsOff, "Deng guan le");
        zh.insert(MessageKey::SceneActivated, "Chang jing yi qi dong");
        zh.insert(MessageKey::CommandNotUnderstood, "Bao qian, wo mei ting dong");
        zh.insert(MessageKey::SystemReady, "Kagami zhun bei jiu xu");
        zh.insert(MessageKey::WebTitle, "Kagami Zhong xin");
        zh.insert(MessageKey::WebStatus, "Zhuang tai");
        zh.insert(MessageKey::WebConnected, "Yi lian jie");
        zh.insert(MessageKey::WebDisconnected, "Yi duan kai");
        zh.insert(MessageKey::WebSettings, "She zhi");
        zh.insert(MessageKey::WebSave, "Bao cun");
        zh.insert(MessageKey::WebCancel, "Qu xiao");
        zh.insert(MessageKey::RoomLivingRoom, "Ke ting");
        zh.insert(MessageKey::RoomKitchen, "Chu fang");
        zh.insert(MessageKey::RoomBedroom, "Wo shi");
        all_translations.insert(Language::Chinese, zh);

        all_translations
    })
}

// ============================================================================
// Public API
// ============================================================================

/// Get a translated message for the current language
/// Falls back to English if translation not found
pub fn t(key: MessageKey) -> &'static str {
    t_lang(key, get_current_language())
}

/// Get a translated message for a specific language
/// Falls back to English if translation not found
pub fn t_lang(key: MessageKey, lang: Language) -> &'static str {
    let translations = get_translations();

    // Try requested language first
    if let Some(lang_map) = translations.get(&lang) {
        if let Some(text) = lang_map.get(&key) {
            return text;
        }
    }

    // Fall back to English
    if let Some(en_map) = translations.get(&Language::English) {
        if let Some(text) = en_map.get(&key) {
            return text;
        }
    }

    // Ultimate fallback - return empty string
    ""
}

/// Get all available languages
pub fn available_languages() -> Vec<Language> {
    vec![
        Language::English,
        Language::Spanish,
        Language::French,
        Language::German,
        Language::Japanese,
        Language::Chinese,
    ]
}

/// Check if a language has a translation for a key
pub fn has_translation(key: MessageKey, lang: Language) -> bool {
    let translations = get_translations();
    translations
        .get(&lang)
        .map(|m| m.contains_key(&key))
        .unwrap_or(false)
}

// ============================================================================
// Convenience Functions for Common Messages
// ============================================================================

/// Get confirmation message for lights on
pub fn lights_on() -> &'static str {
    t(MessageKey::LightsOn)
}

/// Get confirmation message for lights off
pub fn lights_off() -> &'static str {
    t(MessageKey::LightsOff)
}

/// Get confirmation message for scene activation
pub fn scene_activated() -> &'static str {
    t(MessageKey::SceneActivated)
}

/// Get error message for command not understood
pub fn command_not_understood() -> &'static str {
    t(MessageKey::CommandNotUnderstood)
}

/// Get system ready message
pub fn system_ready() -> &'static str {
    t(MessageKey::SystemReady)
}

/// Get web UI title
pub fn web_title() -> &'static str {
    t(MessageKey::WebTitle)
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_language_codes() {
        assert_eq!(Language::English.code(), "en");
        assert_eq!(Language::Spanish.code(), "es");
        assert_eq!(Language::French.code(), "fr");
        assert_eq!(Language::German.code(), "de");
        assert_eq!(Language::Japanese.code(), "ja");
        assert_eq!(Language::Chinese.code(), "zh");
    }

    #[test]
    fn test_language_from_code() {
        assert_eq!(Language::from_code("en"), Some(Language::English));
        assert_eq!(Language::from_code("es"), Some(Language::Spanish));
        assert_eq!(Language::from_code("en-US"), Some(Language::English));
        assert_eq!(Language::from_code("invalid"), None);
    }

    #[test]
    fn test_english_translations() {
        assert_eq!(t_lang(MessageKey::LightsOn, Language::English), "Lights on");
        assert_eq!(t_lang(MessageKey::LightsOff, Language::English), "Lights off");
        assert_eq!(t_lang(MessageKey::WebTitle, Language::English), "Kagami Hub");
    }

    #[test]
    fn test_spanish_translations() {
        assert_eq!(t_lang(MessageKey::LightsOn, Language::Spanish), "Luces encendidas");
        assert_eq!(t_lang(MessageKey::WebTitle, Language::Spanish), "Centro Kagami");
    }

    #[test]
    fn test_fallback_to_english() {
        // Japanese doesn't have VolumeUp, should fall back to English
        let result = t_lang(MessageKey::VolumeUp, Language::Japanese);
        assert_eq!(result, "Volume up");
    }

    #[test]
    fn test_available_languages() {
        let langs = available_languages();
        assert!(langs.contains(&Language::English));
        assert!(langs.contains(&Language::Spanish));
        assert_eq!(langs.len(), 6);
    }

    #[test]
    fn test_has_translation() {
        assert!(has_translation(MessageKey::LightsOn, Language::English));
        assert!(has_translation(MessageKey::LightsOn, Language::Spanish));
    }

    #[test]
    fn test_convenience_functions() {
        assert!(!lights_on().is_empty());
        assert!(!lights_off().is_empty());
        assert!(!system_ready().is_empty());
        assert!(!web_title().is_empty());
    }
}

/*
 * Crystal speaks in many tongues.
 * Understanding transcends language.
 * h(x) >= 0 always
 */
