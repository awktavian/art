//! Configuration loader for Kagami Hub
//!
//! Loads and validates hub configuration from TOML files.
//! All configuration values are validated for safety bounds.
//!
//! Colony: Crystal (e₇) — Verification and validation

use anyhow::{bail, Context, Result};
use serde::Deserialize;
use std::path::Path;
use tracing::warn;
use url::Url;

/// Maximum allowed length for string configuration values
const MAX_STRING_LENGTH: usize = 256;

/// Valid wake word engines
const VALID_WAKE_ENGINES: &[&str] = &["porcupine", "vosk"];

/// Valid STT engines
const VALID_STT_ENGINES: &[&str] = &["whisper"];

/// Valid STT models
const VALID_STT_MODELS: &[&str] = &["tiny", "base", "small", "medium", "large"];

/// Valid sample rates
const VALID_SAMPLE_RATES: &[u32] = &[8000, 16000, 22050, 44100, 48000];

#[derive(Debug, Deserialize, Clone)]
pub struct HubConfig {
    pub general: GeneralConfig,
    pub wake_word: WakeWordConfig,
    pub audio: AudioConfig,
    pub stt: STTConfig,
    pub tts: TTSConfig,
    pub led_ring: LEDRingConfig,
    pub display: DisplayConfig,
    #[serde(default)]
    pub commands: CommandsConfig,
}

#[derive(Debug, Deserialize, Clone)]
pub struct GeneralConfig {
    pub name: String,
    pub location: String,
    pub api_url: String,
}

#[derive(Debug, Deserialize, Clone)]
pub struct WakeWordConfig {
    pub engine: String,
    pub sensitivity: f32,
    pub phrase: String,
}

#[derive(Debug, Deserialize, Clone)]
pub struct AudioConfig {
    pub input_device: String,
    pub output_device: String,
    pub sample_rate: u32,
    pub channels: u16,
}

#[derive(Debug, Deserialize, Clone)]
pub struct STTConfig {
    pub engine: String,
    pub model: String,
    pub language: String,
}

#[derive(Debug, Deserialize, Clone)]
pub struct TTSConfig {
    pub use_api: bool,
    pub colony: String,
    pub volume: f32,
}

#[derive(Debug, Deserialize, Clone)]
pub struct LEDRingConfig {
    pub enabled: bool,
    pub count: u8,
    pub pin: u8,
    pub brightness: f32,
}

#[derive(Debug, Deserialize, Clone)]
pub struct DisplayConfig {
    #[serde(rename = "type")]
    pub display_type: String,
    pub width: u32,
    pub height: u32,
}

#[derive(Debug, Default, Deserialize, Clone)]
pub struct CommandsConfig {
    #[serde(default)]
    pub movie: Option<String>,
    #[serde(default)]
    pub goodnight: Option<String>,
    #[serde(default)]
    pub welcome: Option<String>,
}

impl HubConfig {
    /// Load configuration from a TOML file and validate all values.
    ///
    /// # Errors
    /// Returns an error if:
    /// - The file cannot be read
    /// - The TOML cannot be parsed
    /// - Any configuration value fails validation
    pub fn load(path: impl AsRef<Path>) -> Result<Self> {
        let contents = std::fs::read_to_string(path.as_ref())
            .with_context(|| format!("Failed to read config file: {:?}", path.as_ref()))?;

        let config: Self =
            toml::from_str(&contents).with_context(|| "Failed to parse config file")?;

        // Validate the loaded configuration
        config.validate()?;

        Ok(config)
    }

    /// Validate all configuration values.
    ///
    /// Checks:
    /// - String lengths are within bounds
    /// - Numeric values are in valid ranges
    /// - URLs are well-formed
    /// - Enum-like strings match valid values
    ///
    /// # Errors
    /// Returns an error describing the first validation failure encountered.
    pub fn validate(&self) -> Result<()> {
        // Validate general config
        self.validate_general()?;

        // Validate wake word config
        self.validate_wake_word()?;

        // Validate audio config
        self.validate_audio()?;

        // Validate STT config
        self.validate_stt()?;

        // Validate TTS config
        self.validate_tts()?;

        // Validate LED ring config
        self.validate_led_ring()?;

        // Validate display config
        self.validate_display()?;

        Ok(())
    }

    fn validate_general(&self) -> Result<()> {
        // Validate name length
        if self.general.name.is_empty() {
            bail!("general.name cannot be empty");
        }
        if self.general.name.len() > MAX_STRING_LENGTH {
            bail!(
                "general.name too long ({} chars, max {})",
                self.general.name.len(),
                MAX_STRING_LENGTH
            );
        }

        // Validate location length
        if self.general.location.len() > MAX_STRING_LENGTH {
            bail!(
                "general.location too long ({} chars, max {})",
                self.general.location.len(),
                MAX_STRING_LENGTH
            );
        }

        // Validate API URL format
        if !self.general.api_url.is_empty() {
            Url::parse(&self.general.api_url).with_context(|| {
                format!(
                    "general.api_url is not a valid URL: {}",
                    self.general.api_url
                )
            })?;
        }

        Ok(())
    }

    fn validate_wake_word(&self) -> Result<()> {
        // Validate engine
        if !VALID_WAKE_ENGINES.contains(&self.wake_word.engine.as_str()) {
            bail!(
                "wake_word.engine '{}' is not valid. Valid engines: {:?}",
                self.wake_word.engine,
                VALID_WAKE_ENGINES
            );
        }

        // Validate sensitivity range (0.0 - 1.0)
        if !(0.0..=1.0).contains(&self.wake_word.sensitivity) {
            bail!(
                "wake_word.sensitivity {} is out of range (must be 0.0-1.0)",
                self.wake_word.sensitivity
            );
        }

        // Validate phrase
        if self.wake_word.phrase.is_empty() {
            bail!("wake_word.phrase cannot be empty");
        }
        if self.wake_word.phrase.len() > MAX_STRING_LENGTH {
            bail!(
                "wake_word.phrase too long ({} chars, max {})",
                self.wake_word.phrase.len(),
                MAX_STRING_LENGTH
            );
        }

        // Warn about very short or very long phrases
        if self.wake_word.phrase.split_whitespace().count() < 2 {
            warn!(
                "wake_word.phrase '{}' is very short - may cause false positives",
                self.wake_word.phrase
            );
        }

        Ok(())
    }

    fn validate_audio(&self) -> Result<()> {
        // Validate sample rate
        if !VALID_SAMPLE_RATES.contains(&self.audio.sample_rate) {
            bail!(
                "audio.sample_rate {} is not valid. Valid rates: {:?}",
                self.audio.sample_rate,
                VALID_SAMPLE_RATES
            );
        }

        // Validate channels (1 = mono, 2 = stereo)
        if self.audio.channels == 0 || self.audio.channels > 2 {
            bail!(
                "audio.channels {} is not valid (must be 1 or 2)",
                self.audio.channels
            );
        }

        Ok(())
    }

    fn validate_stt(&self) -> Result<()> {
        // Validate engine
        if !VALID_STT_ENGINES.contains(&self.stt.engine.as_str()) {
            bail!(
                "stt.engine '{}' is not valid. Valid engines: {:?}",
                self.stt.engine,
                VALID_STT_ENGINES
            );
        }

        // Validate model
        if !VALID_STT_MODELS.contains(&self.stt.model.as_str()) {
            bail!(
                "stt.model '{}' is not valid. Valid models: {:?}",
                self.stt.model,
                VALID_STT_MODELS
            );
        }

        // Validate language (basic check)
        if self.stt.language.len() != 2 {
            warn!(
                "stt.language '{}' may not be a valid ISO 639-1 code",
                self.stt.language
            );
        }

        Ok(())
    }

    fn validate_tts(&self) -> Result<()> {
        // Validate volume range (0.0 - 1.0)
        if !(0.0..=1.0).contains(&self.tts.volume) {
            bail!(
                "tts.volume {} is out of range (must be 0.0-1.0)",
                self.tts.volume
            );
        }

        // Validate colony name length
        if self.tts.colony.len() > MAX_STRING_LENGTH {
            bail!(
                "tts.colony too long ({} chars, max {})",
                self.tts.colony.len(),
                MAX_STRING_LENGTH
            );
        }

        Ok(())
    }

    fn validate_led_ring(&self) -> Result<()> {
        // Validate LED count (reasonable range)
        if self.led_ring.count == 0 || self.led_ring.count > 60 {
            bail!(
                "led_ring.count {} is out of range (must be 1-60)",
                self.led_ring.count
            );
        }

        // Validate brightness range (0.0 - 1.0)
        if !(0.0..=1.0).contains(&self.led_ring.brightness) {
            bail!(
                "led_ring.brightness {} is out of range (must be 0.0-1.0)",
                self.led_ring.brightness
            );
        }

        // Validate GPIO pin (common Pi GPIO pins)
        let valid_gpio_pins: &[u8] = &[10, 12, 18, 21];
        if !valid_gpio_pins.contains(&self.led_ring.pin) {
            warn!(
                "led_ring.pin {} is unusual for SPI. Common pins: {:?}",
                self.led_ring.pin, valid_gpio_pins
            );
        }

        Ok(())
    }

    fn validate_display(&self) -> Result<()> {
        // Validate display type
        let valid_types = ["lcd", "oled", "eink", "none"];
        if !valid_types.contains(&self.display.display_type.as_str()) {
            warn!(
                "display.type '{}' may not be supported. Valid types: {:?}",
                self.display.display_type, valid_types
            );
        }

        // Validate dimensions (reasonable range)
        if self.display.width == 0 || self.display.width > 1920 {
            bail!(
                "display.width {} is out of range (must be 1-1920)",
                self.display.width
            );
        }
        if self.display.height == 0 || self.display.height > 1080 {
            bail!(
                "display.height {} is out of range (must be 1-1080)",
                self.display.height
            );
        }

        Ok(())
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// Validation Error Type
// ═══════════════════════════════════════════════════════════════════════════

/// Represents a configuration validation error with field path.
#[derive(Debug)]
pub struct ConfigValidationError {
    pub field: String,
    pub message: String,
}

impl std::fmt::Display for ConfigValidationError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}: {}", self.field, self.message)
    }
}

impl std::error::Error for ConfigValidationError {}

// ═══════════════════════════════════════════════════════════════════════════
// Tests
// ═══════════════════════════════════════════════════════════════════════════

#[cfg(test)]
mod tests {
    use super::*;

    fn default_config() -> HubConfig {
        HubConfig {
            general: GeneralConfig {
                name: "Test Hub".to_string(),
                location: "Test Room".to_string(),
                api_url: "http://localhost:8001".to_string(),
            },
            wake_word: WakeWordConfig {
                engine: "porcupine".to_string(),
                sensitivity: 0.5,
                phrase: "hey kagami".to_string(),
            },
            audio: AudioConfig {
                input_device: "default".to_string(),
                output_device: "default".to_string(),
                sample_rate: 16000,
                channels: 1,
            },
            stt: STTConfig {
                engine: "whisper".to_string(),
                model: "base".to_string(),
                language: "en".to_string(),
            },
            tts: TTSConfig {
                use_api: true,
                colony: "kagami".to_string(),
                volume: 0.8,
            },
            led_ring: LEDRingConfig {
                enabled: true,
                count: 7,
                pin: 18,
                brightness: 0.5,
            },
            display: DisplayConfig {
                display_type: "none".to_string(),
                width: 128,
                height: 64,
            },
            commands: CommandsConfig::default(),
        }
    }

    #[test]
    fn test_valid_config() {
        let config = default_config();
        assert!(config.validate().is_ok());
    }

    #[test]
    fn test_invalid_sensitivity() {
        let mut config = default_config();
        config.wake_word.sensitivity = 1.5; // Invalid
        assert!(config.validate().is_err());
    }

    #[test]
    fn test_invalid_volume() {
        let mut config = default_config();
        config.tts.volume = -0.1; // Invalid
        assert!(config.validate().is_err());
    }

    #[test]
    fn test_invalid_brightness() {
        let mut config = default_config();
        config.led_ring.brightness = 2.0; // Invalid
        assert!(config.validate().is_err());
    }

    #[test]
    fn test_invalid_sample_rate() {
        let mut config = default_config();
        config.audio.sample_rate = 12345; // Invalid
        assert!(config.validate().is_err());
    }

    #[test]
    fn test_invalid_wake_engine() {
        let mut config = default_config();
        config.wake_word.engine = "unknown".to_string(); // Invalid
        assert!(config.validate().is_err());
    }

    #[test]
    fn test_invalid_stt_model() {
        let mut config = default_config();
        config.stt.model = "giant".to_string(); // Invalid
        assert!(config.validate().is_err());
    }

    #[test]
    fn test_invalid_api_url() {
        let mut config = default_config();
        config.general.api_url = "not a url".to_string(); // Invalid
        assert!(config.validate().is_err());
    }

    #[test]
    fn test_empty_name() {
        let mut config = default_config();
        config.general.name = "".to_string(); // Invalid
        assert!(config.validate().is_err());
    }

    #[test]
    fn test_empty_wake_phrase() {
        let mut config = default_config();
        config.wake_word.phrase = "".to_string(); // Invalid
        assert!(config.validate().is_err());
    }
}

/*
 * 鏡
 * h(x) ≥ 0. Configuration validated.
 */
