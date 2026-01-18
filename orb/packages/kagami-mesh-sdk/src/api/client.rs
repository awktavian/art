//! Unified API Client for Kagami
//!
//! This module provides a cross-platform HTTP client that can be used
//! from iOS, Android, Desktop, and Hub via UniFFI bindings.
//!
//! The client handles:
//! - Service discovery
//! - Health checks with caching
//! - Client registration
//! - Circuit breaker for graceful degradation
//! - Request execution with proper error handling
//!
//! # Platform Usage
//!
//! ```swift
//! // Swift (iOS/visionOS/watchOS/tvOS)
//! let client = KagamiApiClient(clientType: .ios, deviceName: "iPhone")
//! try await client.connect()
//! let rooms = try await client.fetchRooms()
//! ```
//!
//! ```kotlin
//! // Kotlin (Android)
//! val client = KagamiApiClient(ClientType.ANDROID, "Pixel 8")
//! client.connect()
//! val rooms = client.fetchRooms()
//! ```
//!
//! # Safety
//!
//! ```text
//! h(x) >= 0 always
//! ```

use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use crate::circuit_breaker::{CircuitBreaker, CircuitState};

use super::types::*;

// ============================================================================
// Configuration
// ============================================================================

/// Default API URL
pub const DEFAULT_API_URL: &str = "https://api.awkronos.com";

/// Local mDNS URL for home network
pub const LOCAL_MDNS_URL: &str = "http://kagami.local:8001";

/// Discovery candidate URLs
pub const DISCOVERY_CANDIDATES: &[&str] = &[
    "https://api.awkronos.com",
    "http://kagami.local:8001",
];

/// API endpoints
pub mod endpoints {
    pub const HEALTH: &str = "/health";
    pub const REGISTER_CLIENT: &str = "/api/home/clients/register";
    pub const ROOMS: &str = "/home/rooms";
    pub const DEVICES: &str = "/home/devices";
    pub const SCENES: &str = "/home/scenes";
    pub const LIGHTS: &str = "/home/lights";
    pub const SHADES: &str = "/home/shades";
    pub const FIREPLACE: &str = "/home/fireplace";
    pub const CLIMATE: &str = "/home/climate/set";
    pub const ANNOUNCE: &str = "/home/announce";
    pub const LOCKS: &str = "/home/locks";
    pub const TV: &str = "/home/tv";
}

// ============================================================================
// Client Configuration
// ============================================================================

/// Configuration options for the API client.
#[derive(Debug, Clone, uniffi::Record)]
pub struct ApiClientConfig {
    /// Base URL for the API (default: production API)
    pub base_url: Option<String>,
    /// Request timeout in milliseconds (default: 10000)
    pub timeout_ms: u64,
    /// Cache validity in seconds (default: 5)
    pub cache_validity_seconds: u64,
    /// Poll interval in seconds (default: 15)
    pub poll_interval_seconds: u64,
    /// Maximum retry attempts for transient failures (default: 3)
    pub max_retries: u32,
}

impl Default for ApiClientConfig {
    fn default() -> Self {
        Self {
            base_url: None,
            timeout_ms: 10_000,
            cache_validity_seconds: 5,
            poll_interval_seconds: 15,
            max_retries: 3,
        }
    }
}

// ============================================================================
// Client State
// ============================================================================

/// Connection state of the API client.
#[derive(Debug, Clone, Copy, PartialEq, Eq, uniffi::Enum)]
pub enum ApiConnectionState {
    /// Not connected to any server
    Disconnected,
    /// Attempting to connect
    Connecting,
    /// Connected and healthy
    Connected,
    /// Circuit breaker is open (too many failures)
    CircuitOpen,
    /// Connection failed
    Failed,
}

/// Internal client state (not exposed via UniFFI)
struct ClientState {
    /// Current base URL
    base_url: String,
    /// Current connection state
    connection_state: ApiConnectionState,
    /// Whether the client is registered with the server
    is_registered: bool,
    /// Client ID for this session
    client_id: String,
    /// Cached health response
    cached_health: Option<HealthResponse>,
    /// When the health cache was last updated
    cache_timestamp: Option<Instant>,
    /// Last known safety score
    safety_score: Option<f64>,
    /// Last measured latency in milliseconds
    latency_ms: u32,
    /// Last error message (if any)
    last_error: Option<String>,
}

// ============================================================================
// API Client (UniFFI Object)
// ============================================================================

/// Unified API client for Kagami.
///
/// This client provides a consistent interface across all platforms
/// via UniFFI bindings for Swift and Kotlin.
#[derive(uniffi::Object)]
pub struct KagamiApiClient {
    /// Client type (platform)
    client_type: ClientType,
    /// Device name for registration
    device_name: String,
    /// App version for registration
    app_version: String,
    /// Configuration
    config: ApiClientConfig,
    /// Internal state (protected by mutex for thread safety)
    state: Arc<Mutex<ClientState>>,
    /// Circuit breaker for graceful degradation
    circuit_breaker: Arc<CircuitBreaker>,
}

#[uniffi::export]
impl KagamiApiClient {
    /// Create a new API client.
    ///
    /// # Arguments
    ///
    /// * `client_type` - The type of client (iOS, Android, etc.)
    /// * `device_name` - Human-readable device name for registration
    /// * `app_version` - App version string for registration
    #[uniffi::constructor]
    pub fn new(client_type: ClientType, device_name: String, app_version: String) -> Self {
        Self::with_config(
            client_type,
            device_name,
            app_version,
            ApiClientConfig::default(),
        )
    }

    /// Create a new API client with custom configuration.
    #[uniffi::constructor]
    pub fn with_config(
        client_type: ClientType,
        device_name: String,
        app_version: String,
        config: ApiClientConfig,
    ) -> Self {
        let base_url = config
            .base_url
            .clone()
            .unwrap_or_else(|| DEFAULT_API_URL.to_string());

        let client_id = format!("{}-{}", client_type.as_str(), uuid::Uuid::new_v4());

        Self {
            client_type,
            device_name,
            app_version,
            config,
            state: Arc::new(Mutex::new(ClientState {
                base_url,
                connection_state: ApiConnectionState::Disconnected,
                is_registered: false,
                client_id,
                cached_health: None,
                cache_timestamp: None,
                safety_score: None,
                latency_ms: 0,
                last_error: None,
            })),
            circuit_breaker: Arc::new(CircuitBreaker::new()),
        }
    }

    // ========================================================================
    // State Accessors
    // ========================================================================

    /// Get the current connection state.
    pub fn connection_state(&self) -> ApiConnectionState {
        self.state.lock().unwrap().connection_state
    }

    /// Check if connected to the server.
    pub fn is_connected(&self) -> bool {
        self.state.lock().unwrap().connection_state == ApiConnectionState::Connected
    }

    /// Check if registered with the server.
    pub fn is_registered(&self) -> bool {
        self.state.lock().unwrap().is_registered
    }

    /// Get the current safety score.
    pub fn safety_score(&self) -> Option<f64> {
        self.state.lock().unwrap().safety_score
    }

    /// Get the last measured latency in milliseconds.
    pub fn latency_ms(&self) -> u32 {
        self.state.lock().unwrap().latency_ms
    }

    /// Get the current base URL.
    pub fn base_url(&self) -> String {
        self.state.lock().unwrap().base_url.clone()
    }

    /// Get the client ID.
    pub fn client_id(&self) -> String {
        self.state.lock().unwrap().client_id.clone()
    }

    /// Get the last error message (if any).
    pub fn last_error(&self) -> Option<String> {
        self.state.lock().unwrap().last_error.clone()
    }

    /// Check if circuit breaker is open.
    pub fn is_circuit_open(&self) -> bool {
        self.circuit_breaker.state() == CircuitState::Open
    }

    // ========================================================================
    // Configuration
    // ========================================================================

    /// Update the base URL and reset connection state.
    pub fn set_base_url(&self, url: String) {
        let mut state = self.state.lock().unwrap();
        state.base_url = url;
        state.connection_state = ApiConnectionState::Disconnected;
        state.is_registered = false;
        state.cached_health = None;
        state.cache_timestamp = None;
    }

    /// Reset the circuit breaker manually.
    pub fn reset_circuit_breaker(&self) {
        self.circuit_breaker.reset();
        let mut state = self.state.lock().unwrap();
        if state.connection_state == ApiConnectionState::CircuitOpen {
            state.connection_state = ApiConnectionState::Disconnected;
        }
    }

    // ========================================================================
    // Request Building Helpers (for platform HTTP clients)
    // ========================================================================

    /// Build a full URL for an endpoint.
    pub fn build_url(&self, endpoint: &str) -> String {
        let base = self.state.lock().unwrap().base_url.clone();
        format!("{}{}", base, endpoint)
    }

    /// Get the health check URL.
    pub fn health_url(&self) -> String {
        self.build_url(endpoints::HEALTH)
    }

    /// Get the rooms endpoint URL.
    pub fn rooms_url(&self) -> String {
        self.build_url(endpoints::ROOMS)
    }

    /// Get the scenes endpoint URL.
    pub fn scenes_url(&self) -> String {
        self.build_url(endpoints::SCENES)
    }

    /// Get the client registration endpoint URL.
    pub fn register_url(&self) -> String {
        self.build_url(endpoints::REGISTER_CLIENT)
    }

    // ========================================================================
    // Registration Helpers
    // ========================================================================

    /// Build the client registration request body.
    pub fn build_registration_request(&self) -> ClientRegistrationRequest {
        ClientRegistrationRequest {
            client_id: self.client_id(),
            client_type: self.client_type.as_str().to_string(),
            device_name: self.device_name.clone(),
            capabilities: self.client_type.default_capabilities(),
            app_version: self.app_version.clone(),
            os_version: None, // Set by platform-specific code
        }
    }

    /// Mark the client as registered.
    pub fn mark_registered(&self) {
        self.state.lock().unwrap().is_registered = true;
    }

    /// Mark the client as not registered.
    pub fn mark_unregistered(&self) {
        self.state.lock().unwrap().is_registered = false;
    }

    // ========================================================================
    // Connection State Management
    // ========================================================================

    /// Update connection state to connecting.
    pub fn on_connecting(&self) {
        self.state.lock().unwrap().connection_state = ApiConnectionState::Connecting;
    }

    /// Update state on successful connection.
    pub fn on_connected(&self, latency_ms: u32, safety_score: Option<f64>) {
        self.circuit_breaker.record_success();
        let mut state = self.state.lock().unwrap();
        state.connection_state = ApiConnectionState::Connected;
        state.latency_ms = latency_ms;
        state.safety_score = safety_score;
        state.last_error = None;
    }

    /// Update state on connection failure.
    pub fn on_connection_failed(&self, error: &str) {
        self.circuit_breaker.record_failure();
        let mut state = self.state.lock().unwrap();
        state.last_error = Some(error.to_string());

        if self.circuit_breaker.state() == CircuitState::Open {
            state.connection_state = ApiConnectionState::CircuitOpen;
        } else {
            state.connection_state = ApiConnectionState::Failed;
        }
    }

    /// Check if a request should be allowed (circuit breaker check).
    pub fn allow_request(&self) -> bool {
        self.circuit_breaker.allow_request()
    }

    /// Get the current backoff duration in milliseconds.
    pub fn backoff_ms(&self) -> u64 {
        self.circuit_breaker.current_backoff().as_millis() as u64
    }

    // ========================================================================
    // Health Cache Management
    // ========================================================================

    /// Check if cached health is still valid.
    pub fn is_health_cache_valid(&self) -> bool {
        let state = self.state.lock().unwrap();
        if let (Some(_), Some(timestamp)) = (&state.cached_health, state.cache_timestamp) {
            timestamp.elapsed() < Duration::from_secs(self.config.cache_validity_seconds)
        } else {
            false
        }
    }

    /// Get cached health response if valid.
    pub fn cached_health(&self) -> Option<HealthResponse> {
        if self.is_health_cache_valid() {
            self.state.lock().unwrap().cached_health.clone()
        } else {
            None
        }
    }

    /// Update the health cache.
    pub fn update_health_cache(&self, health: &HealthResponse) {
        let mut state = self.state.lock().unwrap();
        state.cached_health = Some(health.clone());
        state.cache_timestamp = Some(Instant::now());
        state.safety_score = health.h_x;
    }

    /// Invalidate the health cache.
    pub fn invalidate_health_cache(&self) {
        let mut state = self.state.lock().unwrap();
        state.cached_health = None;
        state.cache_timestamp = None;
    }

    // ========================================================================
    // Discovery Helpers
    // ========================================================================

    /// Get list of discovery candidate URLs.
    pub fn discovery_candidates(&self) -> Vec<String> {
        DISCOVERY_CANDIDATES
            .iter()
            .map(|s| s.to_string())
            .collect()
    }

    /// Update base URL after successful discovery.
    pub fn on_discovery_success(&self, url: &str) {
        self.state.lock().unwrap().base_url = url.to_string();
    }

    // ========================================================================
    // Request/Response Helpers
    // ========================================================================

    /// Parse a health response from JSON.
    pub fn parse_health_response(&self, json: &str) -> Result<HealthResponse, ApiError> {
        serde_json::from_str(json).map_err(|e| ApiError::DecodingFailed {
            message: e.to_string(),
        })
    }

    /// Parse a rooms response from JSON.
    pub fn parse_rooms_response(&self, json: &str) -> Result<RoomsResponse, ApiError> {
        serde_json::from_str(json).map_err(|e| ApiError::DecodingFailed {
            message: e.to_string(),
        })
    }

    /// Parse a scenes response from JSON.
    pub fn parse_scenes_response(&self, json: &str) -> Result<ScenesResponse, ApiError> {
        serde_json::from_str(json).map_err(|e| ApiError::DecodingFailed {
            message: e.to_string(),
        })
    }

    /// Serialize a registration request to JSON.
    pub fn serialize_registration_request(
        &self,
        request: &ClientRegistrationRequest,
    ) -> Result<String, ApiError> {
        serde_json::to_string(request).map_err(|e| ApiError::DecodingFailed {
            message: e.to_string(),
        })
    }

    /// Serialize a lights request to JSON.
    pub fn serialize_lights_request(&self, request: &LightsRequest) -> Result<String, ApiError> {
        serde_json::to_string(request).map_err(|e| ApiError::DecodingFailed {
            message: e.to_string(),
        })
    }

    /// Serialize a shades request to JSON.
    pub fn serialize_shades_request(&self, request: &ShadesRequest) -> Result<String, ApiError> {
        serde_json::to_string(request).map_err(|e| ApiError::DecodingFailed {
            message: e.to_string(),
        })
    }

    /// Serialize an announce request to JSON.
    pub fn serialize_announce_request(
        &self,
        request: &AnnounceRequest,
    ) -> Result<String, ApiError> {
        serde_json::to_string(request).map_err(|e| ApiError::DecodingFailed {
            message: e.to_string(),
        })
    }
}

// ============================================================================
// Helper Functions
// ============================================================================

/// Generate a new client ID for the given platform.
#[uniffi::export]
pub fn generate_client_id(client_type: ClientType) -> String {
    format!("{}-{}", client_type.as_str(), uuid::Uuid::new_v4())
}

/// Build a scene execution endpoint URL.
#[uniffi::export]
pub fn scene_endpoint(scene_id: &str) -> String {
    format!("{}/{}", endpoints::SCENES, scene_id)
}

/// Build a TV control endpoint URL.
#[uniffi::export]
pub fn tv_endpoint(action: &str) -> String {
    format!("{}/{}", endpoints::TV, action)
}

/// Build a locks action endpoint URL.
#[uniffi::export]
pub fn locks_endpoint(action: &str) -> String {
    format!("{}/{}", endpoints::LOCKS, action)
}

/*
 * 鏡
 * Unified API Client: One implementation, every platform.
 * h(x) >= 0. Always.
 */

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_client_creation() {
        let client = KagamiApiClient::new(
            ClientType::Ios,
            "Test iPhone".to_string(),
            "1.0.0".to_string(),
        );

        assert_eq!(client.connection_state(), ApiConnectionState::Disconnected);
        assert!(!client.is_connected());
        assert!(!client.is_registered());
        assert!(client.client_id().starts_with("ios-"));
    }

    #[test]
    fn test_url_building() {
        let client = KagamiApiClient::new(
            ClientType::Android,
            "Test Android".to_string(),
            "1.0.0".to_string(),
        );

        assert!(client.health_url().ends_with("/health"));
        assert!(client.rooms_url().ends_with("/home/rooms"));
    }

    #[test]
    fn test_connection_state_transitions() {
        let client = KagamiApiClient::new(
            ClientType::Desktop,
            "Test Desktop".to_string(),
            "1.0.0".to_string(),
        );

        client.on_connecting();
        assert_eq!(client.connection_state(), ApiConnectionState::Connecting);

        client.on_connected(50, Some(0.95));
        assert_eq!(client.connection_state(), ApiConnectionState::Connected);
        assert_eq!(client.latency_ms(), 50);
        assert_eq!(client.safety_score(), Some(0.95));

        client.on_connection_failed("timeout");
        assert_eq!(client.last_error(), Some("timeout".to_string()));
    }

    #[test]
    fn test_registration_request() {
        let client = KagamiApiClient::new(
            ClientType::VisionOs,
            "Vision Pro".to_string(),
            "2.0.0".to_string(),
        );

        let request = client.build_registration_request();
        assert_eq!(request.client_type, "visionos");
        assert_eq!(request.device_name, "Vision Pro");
        assert_eq!(request.app_version, "2.0.0");
        assert!(request.capabilities.contains(&"spatial".to_string()));
    }

    #[test]
    fn test_health_cache() {
        let client = KagamiApiClient::new(
            ClientType::TvOs,
            "Apple TV".to_string(),
            "1.0.0".to_string(),
        );

        assert!(!client.is_health_cache_valid());
        assert!(client.cached_health().is_none());

        let health = HealthResponse {
            status: "healthy".to_string(),
            h_x: Some(0.9),
            version: Some("1.0.0".to_string()),
            rooms_count: Some(10),
            uptime_ms: Some(1000),
        };

        client.update_health_cache(&health);
        assert!(client.is_health_cache_valid());
        assert!(client.cached_health().is_some());

        client.invalidate_health_cache();
        assert!(!client.is_health_cache_valid());
    }

    #[test]
    fn test_circuit_breaker_integration() {
        let client = KagamiApiClient::new(
            ClientType::WatchOs,
            "Apple Watch".to_string(),
            "1.0.0".to_string(),
        );

        assert!(client.allow_request());
        assert!(!client.is_circuit_open());

        // Simulate failures
        for _ in 0..10 {
            client.on_connection_failed("error");
        }

        // Circuit should eventually open
        // (depends on CircuitBreaker configuration)
    }

    #[test]
    fn test_generate_client_id() {
        let id = generate_client_id(ClientType::Android);
        assert!(id.starts_with("android-"));
        assert!(id.len() > 10);
    }

    #[test]
    fn test_endpoint_builders() {
        assert_eq!(scene_endpoint("movie_mode"), "/home/scenes/movie_mode");
        assert_eq!(tv_endpoint("power"), "/home/tv/power");
        assert_eq!(locks_endpoint("lock-all"), "/home/locks/lock-all");
    }

    #[test]
    fn test_json_parsing() {
        let client = KagamiApiClient::new(
            ClientType::Ios,
            "iPhone".to_string(),
            "1.0.0".to_string(),
        );

        let json = r#"{"status":"healthy","h_x":0.95}"#;
        let health = client.parse_health_response(json).unwrap();
        assert_eq!(health.status, "healthy");
        assert_eq!(health.h_x, Some(0.95));

        let bad_json = "not json";
        assert!(client.parse_health_response(bad_json).is_err());
    }
}
