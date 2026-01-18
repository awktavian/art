//! Unified API Types for Kagami
//!
//! This module provides cross-platform data models that are shared across
//! iOS, Android, Desktop, and Hub clients via UniFFI bindings.
//!
//! These types eliminate ~3,900 lines of duplicated model code across platforms.
//!
//! # Platform Mapping
//!
//! | Rust Type | Swift (iOS/visionOS/watchOS/tvOS) | Kotlin (Android/WearOS) | TypeScript (Desktop) |
//! |-----------|-----------------------------------|-------------------------|----------------------|
//! | `Light` | `Light` | `Light` | `Light` |
//! | `Shade` | `Shade` | `Shade` | `Shade` |
//! | `RoomModel` | `RoomModel` | `RoomModel` | `RoomModel` |
//! | etc. | etc. | etc. | etc. |
//!
//! # Safety
//!
//! ```text
//! h(x) >= 0 always
//! ```

use serde::{Deserialize, Serialize};

// ============================================================================
// Device Models
// ============================================================================

/// A light fixture in the home.
///
/// Represents a controllable light with brightness level (0-100).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, uniffi::Record)]
pub struct Light {
    /// Unique identifier for the light
    pub id: i32,
    /// Human-readable name (e.g., "Living Room Main")
    pub name: String,
    /// Current brightness level (0 = off, 100 = full brightness)
    pub level: i32,
}

impl Light {
    /// Returns true if the light is on (level > 0)
    pub fn is_on(&self) -> bool {
        self.level > 0
    }
}

/// A motorized shade/blind.
///
/// Represents a controllable shade with position (0 = closed, 100 = fully open).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, uniffi::Record)]
pub struct Shade {
    /// Unique identifier for the shade
    pub id: i32,
    /// Human-readable name (e.g., "Bedroom Blinds")
    pub name: String,
    /// Current position (0 = closed, 100 = fully open)
    pub position: i32,
}

impl Shade {
    /// Returns true if the shade is open (position > 0)
    pub fn is_open(&self) -> bool {
        self.position > 0
    }
}

/// An audio zone for whole-home audio.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, uniffi::Record)]
pub struct AudioZone {
    /// Unique identifier for the audio zone
    pub id: i32,
    /// Human-readable name (e.g., "Kitchen Speakers")
    pub name: String,
    /// Whether audio is currently playing
    pub is_active: bool,
    /// Current audio source (e.g., "Spotify", "AirPlay")
    pub source: Option<String>,
    /// Volume level (0-100)
    pub volume: i32,
}

/// HVAC (heating/cooling) state for a room.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, uniffi::Record)]
pub struct HvacState {
    /// Current temperature in the room (Fahrenheit)
    pub current_temp: f64,
    /// Target/setpoint temperature (Fahrenheit)
    pub target_temp: f64,
    /// Operating mode: "heat", "cool", "auto", "off"
    pub mode: String,
}

/// State of a door lock.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, uniffi::Record)]
pub struct LockState {
    /// Human-readable name (e.g., "Front Door")
    pub name: String,
    /// Whether the lock is currently locked
    pub is_locked: bool,
    /// Door state: "open", "closed", "unknown"
    pub door_state: String,
}

/// State of the fireplace.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, uniffi::Record)]
pub struct FireplaceState {
    /// Whether the fireplace is currently on
    pub is_on: bool,
    /// Unix timestamp when fireplace was turned on (if on)
    pub on_since: Option<f64>,
    /// Minutes remaining before auto-shutoff (if applicable)
    pub remaining_minutes: Option<i32>,
}

/// State of the motorized TV mount.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, uniffi::Record)]
pub struct TvMountState {
    /// Current position: "up", "down", "moving"
    pub position: String,
    /// Preset position number (if applicable)
    pub preset: Option<i32>,
}

// ============================================================================
// Room Model
// ============================================================================

/// A room in the home with all its devices.
///
/// This is the primary model for room-based control and display.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, uniffi::Record)]
pub struct RoomModel {
    /// Unique identifier for the room
    pub id: String,
    /// Human-readable name (e.g., "Living Room")
    pub name: String,
    /// Floor designation (e.g., "Main Floor", "Upper Floor")
    pub floor: String,
    /// Lights in this room
    pub lights: Vec<Light>,
    /// Shades in this room
    pub shades: Vec<Shade>,
    /// Audio zone for this room (if any)
    pub audio_zone: Option<AudioZone>,
    /// HVAC state for this room (if any)
    pub hvac: Option<HvacState>,
    /// Whether the room is currently occupied
    pub occupied: bool,
}

impl RoomModel {
    /// Calculate average light level across all lights in the room.
    pub fn avg_light_level(&self) -> i32 {
        if self.lights.is_empty() {
            return 0;
        }
        let sum: i32 = self.lights.iter().map(|l| l.level).sum();
        sum / self.lights.len() as i32
    }

    /// Get a human-readable light state description.
    pub fn light_state(&self) -> String {
        let avg = self.avg_light_level();
        if avg == 0 {
            "Off".to_string()
        } else if avg < 50 {
            "Dim".to_string()
        } else {
            "On".to_string()
        }
    }

    /// Returns true if any lights are present in the room.
    pub fn has_lights(&self) -> bool {
        !self.lights.is_empty()
    }

    /// Returns true if any shades are present in the room.
    pub fn has_shades(&self) -> bool {
        !self.shades.is_empty()
    }
}

// ============================================================================
// Home Status
// ============================================================================

/// Overall home status summary.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, uniffi::Record)]
pub struct HomeStatus {
    /// Whether the home system has been initialized
    pub initialized: bool,
    /// Total number of rooms
    pub rooms: i32,
    /// Number of currently occupied rooms
    pub occupied_rooms: i32,
    /// Whether movie mode is active
    pub movie_mode: bool,
    /// Average temperature across all zones (Fahrenheit)
    pub avg_temp: Option<f64>,
}

/// Devices response from GET /home/devices
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, uniffi::Record)]
pub struct DevicesResponse {
    /// All lights in the home
    pub lights: Vec<Light>,
    /// All shades in the home
    pub shades: Vec<Shade>,
    /// All audio zones in the home
    pub audio_zones: Vec<AudioZone>,
    /// All locks in the home
    pub locks: Vec<LockState>,
    /// Fireplace state
    pub fireplace: FireplaceState,
    /// TV mount state
    pub tv_mount: TvMountState,
}

/// Rooms response from GET /home/rooms
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, uniffi::Record)]
pub struct RoomsResponse {
    /// List of rooms
    pub rooms: Vec<RoomModel>,
    /// Total count of rooms
    pub count: i32,
}

// ============================================================================
// API Request/Response Types
// ============================================================================

/// Health check response from GET /health
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, uniffi::Record)]
pub struct HealthResponse {
    /// Status string: "healthy", "ok", etc.
    pub status: String,
    /// Safety score h(x) (should always be >= 0)
    pub h_x: Option<f64>,
    /// Server version
    pub version: Option<String>,
    /// Number of rooms
    pub rooms_count: Option<i32>,
    /// Uptime in milliseconds
    pub uptime_ms: Option<i64>,
}

impl HealthResponse {
    /// Convenience accessor for safety score
    pub fn safety_score(&self) -> Option<f64> {
        self.h_x
    }

    /// Check if the server reports healthy status
    pub fn is_healthy(&self) -> bool {
        self.status == "healthy" || self.status == "ok"
    }
}

/// Client registration request for POST /api/home/clients/register
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, uniffi::Record)]
pub struct ClientRegistrationRequest {
    /// Unique client identifier (e.g., "ios-uuid", "android-uuid")
    pub client_id: String,
    /// Client type: "ios", "android", "visionos", "tvos", "watchos", "desktop"
    pub client_type: String,
    /// Human-readable device name
    pub device_name: String,
    /// List of capabilities this client supports
    pub capabilities: Vec<String>,
    /// App version string
    pub app_version: String,
    /// OS version string (optional)
    pub os_version: Option<String>,
}

/// Scene information
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, uniffi::Record)]
pub struct SceneInfo {
    /// Scene identifier (e.g., "movie_mode", "goodnight")
    pub id: String,
    /// Human-readable name
    pub name: String,
    /// Description of what the scene does
    pub description: Option<String>,
    /// Icon identifier (SF Symbol name or emoji)
    pub icon: Option<String>,
}

/// Scenes response from GET /home/scenes
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, uniffi::Record)]
pub struct ScenesResponse {
    /// List of available scenes
    pub scenes: Vec<SceneInfo>,
}

/// Lights control request for POST /home/lights
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, uniffi::Record)]
pub struct LightsRequest {
    /// Target brightness level (0-100)
    pub level: i32,
    /// Optional list of room IDs to target (all rooms if None)
    pub rooms: Option<Vec<String>>,
}

/// Shades control request for POST /home/shades
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, uniffi::Record)]
pub struct ShadesRequest {
    /// Action: "open", "close", "stop"
    pub action: String,
    /// Optional list of room IDs to target (all rooms if None)
    pub rooms: Option<Vec<String>>,
}

/// Fireplace control request for POST /home/fireplace
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, uniffi::Record)]
pub struct FireplaceRequest {
    /// Desired state: "on" or "off"
    pub state: String,
}

/// Climate control request for POST /home/climate
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, uniffi::Record)]
pub struct ClimateRequest {
    /// Target temperature (Fahrenheit)
    pub temperature: i32,
    /// Optional room ID to target
    pub room: Option<String>,
    /// Optional mode: "heat", "cool", "auto", "off"
    pub mode: Option<String>,
}

/// Announce request for POST /home/announce
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, uniffi::Record)]
pub struct AnnounceRequest {
    /// Message to announce
    pub message: String,
    /// Optional list of room IDs to announce in (all rooms if None)
    pub rooms: Option<Vec<String>>,
}

// ============================================================================
// WebSocket Message Types
// ============================================================================

/// WebSocket message type enumeration
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, uniffi::Enum)]
pub enum WebSocketMessageType {
    /// Context update with environment state
    ContextUpdate,
    /// Suggestion for user action
    Suggestion,
    /// Home state update
    HomeUpdate,
    /// Error message
    Error,
    /// Unknown message type
    Unknown,
}

/// Context update received via WebSocket
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, uniffi::Record)]
pub struct ContextUpdateMessage {
    /// Current wakefulness level: "alert", "drowsy", "asleep"
    pub wakefulness: Option<String>,
    /// Current situation phase
    pub situation_phase: Option<String>,
    /// Current safety score
    pub safety_score: Option<f64>,
}

/// Suggested action from server
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, uniffi::Record)]
pub struct SuggestedAction {
    /// Icon (SF Symbol name or emoji)
    pub icon: String,
    /// Human-readable label
    pub label: String,
    /// Action identifier to execute
    pub action: String,
}

/// Home update received via WebSocket
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, uniffi::Record)]
pub struct HomeUpdateMessage {
    /// Whether movie mode is active
    pub movie_mode: Option<bool>,
    /// Room that changed (if applicable)
    pub room_id: Option<String>,
}

// ============================================================================
// Error Types
// ============================================================================

/// API error types
#[derive(Debug, Clone, PartialEq, uniffi::Enum)]
pub enum ApiErrorKind {
    /// Invalid URL
    InvalidUrl,
    /// Network error (connection failed, timeout, etc.)
    NetworkError,
    /// Request failed (non-2xx response)
    RequestFailed,
    /// Failed to decode response
    DecodingFailed,
    /// Not connected to server
    NotConnected,
    /// Circuit breaker is open
    CircuitOpen,
    /// Authentication required
    AuthRequired,
    /// Invalid credentials
    InvalidCredentials,
    /// Server version incompatible
    ServerVersionIncompatible,
}

/// API error with details
#[derive(Debug, Clone, thiserror::Error, uniffi::Error)]
pub enum ApiError {
    #[error("Invalid URL: {message}")]
    InvalidUrl { message: String },

    #[error("Network error: {message}")]
    NetworkError { message: String },

    #[error("Request failed: {message}")]
    RequestFailed { message: String },

    #[error("Decoding failed: {message}")]
    DecodingFailed { message: String },

    #[error("Not connected to server")]
    NotConnected,

    #[error("Circuit breaker open: service temporarily unavailable")]
    CircuitOpen,

    #[error("Authentication required")]
    AuthRequired,

    #[error("Invalid credentials")]
    InvalidCredentials,

    #[error("Server version {server} incompatible (requires {required})")]
    ServerVersionIncompatible { server: String, required: String },
}

impl ApiError {
    /// Returns true if this error is retryable
    pub fn is_retryable(&self) -> bool {
        matches!(
            self,
            ApiError::NetworkError { .. }
                | ApiError::RequestFailed { .. }
                | ApiError::NotConnected
                | ApiError::CircuitOpen
        )
    }

    /// Get a user-friendly recovery suggestion
    pub fn recovery_suggestion(&self) -> String {
        match self {
            ApiError::NetworkError { .. } | ApiError::NotConnected => {
                "Check your network connection and try again.".to_string()
            }
            ApiError::CircuitOpen => {
                "The service is temporarily unavailable. Please try again later.".to_string()
            }
            ApiError::InvalidCredentials => {
                "Check your username and password.".to_string()
            }
            ApiError::AuthRequired => {
                "Please log in to continue.".to_string()
            }
            _ => "Please try again.".to_string(),
        }
    }
}

// ============================================================================
// Client Types
// ============================================================================

/// Supported client platform types
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, uniffi::Enum)]
pub enum ClientType {
    /// iOS (iPhone/iPad)
    Ios,
    /// Android phone/tablet
    Android,
    /// visionOS (Apple Vision Pro)
    VisionOs,
    /// tvOS (Apple TV)
    TvOs,
    /// watchOS (Apple Watch)
    WatchOs,
    /// WearOS (Android Watch)
    WearOs,
    /// Desktop (macOS/Windows/Linux via Tauri)
    Desktop,
    /// Hub device
    Hub,
}

impl ClientType {
    /// Get the string identifier for this client type
    pub fn as_str(&self) -> &'static str {
        match self {
            ClientType::Ios => "ios",
            ClientType::Android => "android",
            ClientType::VisionOs => "visionos",
            ClientType::TvOs => "tvos",
            ClientType::WatchOs => "watchos",
            ClientType::WearOs => "wearos",
            ClientType::Desktop => "desktop",
            ClientType::Hub => "hub",
        }
    }

    /// Get default capabilities for this client type
    pub fn default_capabilities(&self) -> Vec<String> {
        match self {
            ClientType::Ios => vec![
                "healthkit".to_string(),
                "location".to_string(),
                "notifications".to_string(),
                "quick_actions".to_string(),
                "widgets".to_string(),
            ],
            ClientType::Android => vec![
                "health_connect".to_string(),
                "location".to_string(),
                "notifications".to_string(),
                "quick_actions".to_string(),
            ],
            ClientType::VisionOs => vec![
                "healthkit".to_string(),
                "spatial".to_string(),
                "immersive".to_string(),
                "gaze".to_string(),
                "hand_tracking".to_string(),
                "quick_actions".to_string(),
            ],
            ClientType::TvOs => vec![
                "tv_controls".to_string(),
                "siri_remote".to_string(),
                "quick_actions".to_string(),
            ],
            ClientType::WatchOs => vec![
                "healthkit".to_string(),
                "complications".to_string(),
                "quick_actions".to_string(),
            ],
            ClientType::WearOs => vec![
                "health_connect".to_string(),
                "quick_actions".to_string(),
            ],
            ClientType::Desktop => vec![
                "notifications".to_string(),
                "keyboard_shortcuts".to_string(),
                "system_tray".to_string(),
            ],
            ClientType::Hub => vec![
                "local_processing".to_string(),
                "device_control".to_string(),
                "automation".to_string(),
            ],
        }
    }
}

// ============================================================================
// Scene Icons (Unified)
// ============================================================================

/// Scene icon constants for consistent UI across platforms.
///
/// Uses SF Symbol names for Apple platforms, with emoji fallbacks for others.
pub struct SceneIcons;

impl SceneIcons {
    /// Movie mode scene icon
    pub const MOVIE_MODE: &'static str = "film.fill";
    /// Goodnight scene icon
    pub const GOODNIGHT: &'static str = "moon.fill";
    /// Welcome home scene icon
    pub const WELCOME_HOME: &'static str = "house.fill";
    /// Away scene icon
    pub const AWAY: &'static str = "lock.fill";
    /// Fireplace control icon
    pub const FIREPLACE: &'static str = "flame.fill";
    /// Lights control icon
    pub const LIGHTS: &'static str = "lightbulb.fill";
    /// Shades control icon
    pub const SHADES: &'static str = "blinds.vertical.open";
    /// TV control icon
    pub const TV: &'static str = "tv.fill";
}

// ============================================================================
// Colony Colors (Unified Design System)
// ============================================================================

/// Colony color definitions for the Kagami design system.
///
/// Based on octonion basis e1-e7, these colors provide consistent theming.
#[derive(Debug, Clone, Copy, PartialEq, uniffi::Record)]
pub struct ColonyColor {
    /// Red component (0-255)
    pub r: u8,
    /// Green component (0-255)
    pub g: u8,
    /// Blue component (0-255)
    pub b: u8,
}

impl ColonyColor {
    /// Create a new color from RGB components
    pub const fn new(r: u8, g: u8, b: u8) -> Self {
        Self { r, g, b }
    }

    /// Convert to hex string (e.g., "#FF6B35")
    pub fn to_hex(&self) -> String {
        format!("#{:02X}{:02X}{:02X}", self.r, self.g, self.b)
    }
}

/// Colony color palette
pub struct ColonyColors;

impl ColonyColors {
    /// e1 - Spark (Ideation) - Orange
    pub const SPARK: ColonyColor = ColonyColor::new(0xFF, 0x6B, 0x35);
    /// e2 - Forge (Implementation) - Gold
    pub const FORGE: ColonyColor = ColonyColor::new(0xD4, 0xAF, 0x37);
    /// e3 - Flow (Adaptation) - Teal
    pub const FLOW: ColonyColor = ColonyColor::new(0x4E, 0xCD, 0xC4);
    /// e4 - Nexus (Integration) - Purple
    pub const NEXUS: ColonyColor = ColonyColor::new(0x9B, 0x7E, 0xBD);
    /// e5 - Beacon (Planning) - Amber
    pub const BEACON: ColonyColor = ColonyColor::new(0xF5, 0x9E, 0x0B);
    /// e6 - Grove (Research) - Green
    pub const GROVE: ColonyColor = ColonyColor::new(0x7E, 0xB7, 0x7F);
    /// e7 - Crystal (Verification) - Cyan
    pub const CRYSTAL: ColonyColor = ColonyColor::new(0x67, 0xD4, 0xE4);

    /// Void background (dark)
    pub const VOID: ColonyColor = ColonyColor::new(0x0A, 0x0A, 0x0F);
    /// Void light background
    pub const VOID_LIGHT: ColonyColor = ColonyColor::new(0x1C, 0x1C, 0x24);

    /// Safety OK (green)
    pub const SAFETY_OK: ColonyColor = ColonyColor::new(0x32, 0xD7, 0x4B);
    /// Safety Caution (yellow)
    pub const SAFETY_CAUTION: ColonyColor = ColonyColor::new(0xFF, 0xD6, 0x0A);
    /// Safety Violation (red)
    pub const SAFETY_VIOLATION: ColonyColor = ColonyColor::new(0xFF, 0x3B, 0x30);
}

/// Get the appropriate safety color for a given score.
///
/// # Arguments
///
/// * `score` - Safety score h(x). Should always be >= 0 in normal operation.
///
/// # Returns
///
/// The appropriate color based on the safety score:
/// - >= 0.5: Green (OK)
/// - >= 0.0: Yellow (Caution)
/// - < 0.0: Red (Violation)
/// - None: Gray (Unknown)
#[uniffi::export]
pub fn safety_color(score: Option<f64>) -> ColonyColor {
    match score {
        Some(s) if s >= 0.5 => ColonyColors::SAFETY_OK,
        Some(s) if s >= 0.0 => ColonyColors::SAFETY_CAUTION,
        Some(_) => ColonyColors::SAFETY_VIOLATION,
        None => ColonyColor::new(0x80, 0x80, 0x80), // Gray for unknown
    }
}

// ============================================================================
// Validation Helpers
// ============================================================================

/// Validate a light level (must be 0-100)
#[uniffi::export]
pub fn validate_light_level(level: i32) -> Result<i32, ApiError> {
    if level < 0 || level > 100 {
        Err(ApiError::InvalidUrl {
            message: format!("Light level must be 0-100, got {}", level),
        })
    } else {
        Ok(level)
    }
}

/// Validate a shade position (must be 0-100)
#[uniffi::export]
pub fn validate_shade_position(position: i32) -> Result<i32, ApiError> {
    if position < 0 || position > 100 {
        Err(ApiError::InvalidUrl {
            message: format!("Shade position must be 0-100, got {}", position),
        })
    } else {
        Ok(position)
    }
}

/// Validate a volume level (must be 0-100)
#[uniffi::export]
pub fn validate_volume(volume: i32) -> Result<i32, ApiError> {
    if volume < 0 || volume > 100 {
        Err(ApiError::InvalidUrl {
            message: format!("Volume must be 0-100, got {}", volume),
        })
    } else {
        Ok(volume)
    }
}

/// Validate a temperature (must be reasonable: 40-100F)
#[uniffi::export]
pub fn validate_temperature(temp: i32) -> Result<i32, ApiError> {
    if temp < 40 || temp > 100 {
        Err(ApiError::InvalidUrl {
            message: format!("Temperature must be 40-100F, got {}", temp),
        })
    } else {
        Ok(temp)
    }
}

/*
 * 鏡
 * Unified API Types: One truth, many platforms.
 * h(x) >= 0. Always.
 */

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_light_is_on() {
        let light_off = Light {
            id: 1,
            name: "Test".to_string(),
            level: 0,
        };
        assert!(!light_off.is_on());

        let light_on = Light {
            id: 2,
            name: "Test".to_string(),
            level: 50,
        };
        assert!(light_on.is_on());
    }

    #[test]
    fn test_room_avg_light_level() {
        let room = RoomModel {
            id: "1".to_string(),
            name: "Living Room".to_string(),
            floor: "Main".to_string(),
            lights: vec![
                Light {
                    id: 1,
                    name: "L1".to_string(),
                    level: 100,
                },
                Light {
                    id: 2,
                    name: "L2".to_string(),
                    level: 50,
                },
            ],
            shades: vec![],
            audio_zone: None,
            hvac: None,
            occupied: true,
        };

        assert_eq!(room.avg_light_level(), 75);
        assert_eq!(room.light_state(), "On");
    }

    #[test]
    fn test_room_empty_lights() {
        let room = RoomModel {
            id: "1".to_string(),
            name: "Empty".to_string(),
            floor: "Main".to_string(),
            lights: vec![],
            shades: vec![],
            audio_zone: None,
            hvac: None,
            occupied: false,
        };

        assert_eq!(room.avg_light_level(), 0);
        assert_eq!(room.light_state(), "Off");
        assert!(!room.has_lights());
    }

    #[test]
    fn test_health_response() {
        let health = HealthResponse {
            status: "healthy".to_string(),
            h_x: Some(0.95),
            version: Some("1.0.0".to_string()),
            rooms_count: Some(10),
            uptime_ms: Some(86400000),
        };

        assert!(health.is_healthy());
        assert_eq!(health.safety_score(), Some(0.95));
    }

    #[test]
    fn test_client_type_capabilities() {
        let ios_caps = ClientType::Ios.default_capabilities();
        assert!(ios_caps.contains(&"healthkit".to_string()));

        let android_caps = ClientType::Android.default_capabilities();
        assert!(android_caps.contains(&"health_connect".to_string()));
    }

    #[test]
    fn test_colony_color_hex() {
        assert_eq!(ColonyColors::SPARK.to_hex(), "#FF6B35");
        assert_eq!(ColonyColors::VOID.to_hex(), "#0A0A0F");
    }

    #[test]
    fn test_safety_color() {
        let ok = safety_color(Some(0.8));
        assert_eq!(ok, ColonyColors::SAFETY_OK);

        let caution = safety_color(Some(0.3));
        assert_eq!(caution, ColonyColors::SAFETY_CAUTION);

        let violation = safety_color(Some(-0.1));
        assert_eq!(violation, ColonyColors::SAFETY_VIOLATION);
    }

    #[test]
    fn test_validation() {
        assert!(validate_light_level(50).is_ok());
        assert!(validate_light_level(150).is_err());
        assert!(validate_temperature(72).is_ok());
        assert!(validate_temperature(150).is_err());
    }

    #[test]
    fn test_api_error_retryable() {
        let network_err = ApiError::NetworkError {
            message: "timeout".to_string(),
        };
        assert!(network_err.is_retryable());

        let auth_err = ApiError::InvalidCredentials;
        assert!(!auth_err.is_retryable());
    }
}
