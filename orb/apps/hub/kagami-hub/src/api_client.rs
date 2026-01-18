//! Kagami API Client for embedded hub
//!
//! This module provides a complete client for all Kagami smart home API endpoints.
//! Supports: lights, shades, climate, security, Tesla, Eight Sleep, outdoor lights,
//! presence, weather, Find My, and automation modes.
//!
//! Colony: Crystal (e₇) — Verification and execution

use anyhow::{Context, Result};
use reqwest::Client;
use serde::Deserialize;
use serde_json::Value;
use std::time::Duration;
use tracing::{debug, error, info};

// Operation-specific timeouts
const DEFAULT_TIMEOUT_SECS: u64 = 10;
const HEALTH_TIMEOUT_SECS: u64 = 5;
const TESLA_TIMEOUT_SECS: u64 = 30;

// Retry configuration
const MAX_RETRIES: u32 = 3;
const INITIAL_BACKOFF_MS: u64 = 100;

// ═══════════════════════════════════════════════════════════════════════════
// Security: Whitelisted actions to prevent path traversal
// ═══════════════════════════════════════════════════════════════════════════

/// Allowed actions for shades control - prevents path traversal attacks
const ALLOWED_SHADE_ACTIONS: &[&str] = &["open", "close", "stop", "up", "down", "preset"];

/// Allowed actions for TV control - prevents path traversal attacks
const ALLOWED_TV_ACTIONS: &[&str] = &[
    "on", "off", "power", "mute", "unmute", "volume-up", "volume-down",
    "channel-up", "channel-down", "pause", "play", "stop", "input",
];

/// Allowed music volume directions - prevents path traversal attacks
const ALLOWED_VOLUME_DIRECTIONS: &[&str] = &["up", "down", "mute", "unmute"];

/// Validate that an action is in the whitelist (case-insensitive, alphanumeric + hyphen only)
fn validate_action(action: &str, whitelist: &[&str], action_type: &str) -> Result<()> {
    // Reject empty or too long
    if action.is_empty() || action.len() > 32 {
        return Err(anyhow::anyhow!("Invalid {} action: must be 1-32 characters", action_type));
    }
    // Only allow alphanumeric and hyphen (no slashes, dots, or other traversal chars)
    if !action.chars().all(|c| c.is_ascii_alphanumeric() || c == '-') {
        return Err(anyhow::anyhow!("Invalid {} action: contains invalid characters", action_type));
    }
    // Check whitelist (case-insensitive)
    let action_lower = action.to_lowercase();
    if !whitelist.iter().any(|&a| a.eq_ignore_ascii_case(&action_lower)) {
        return Err(anyhow::anyhow!(
            "Invalid {} action '{}'. Allowed: {:?}",
            action_type,
            action,
            whitelist
        ));
    }
    Ok(())
}

// ═══════════════════════════════════════════════════════════════════════════
// Response Types
// ═══════════════════════════════════════════════════════════════════════════

#[derive(Debug, Deserialize)]
pub struct HealthResponse {
    #[serde(default)]
    pub status: String,
    #[serde(rename = "h_x", default)]
    pub safety_score: Option<f64>,
    #[serde(default)]
    pub uptime_ms: Option<u64>,
    #[serde(default)]
    pub ready: Option<bool>,
}

#[derive(Debug, Deserialize)]
pub struct CommandResponse {
    #[serde(default)]
    pub success: bool,
    #[serde(default)]
    pub message: Option<String>,
    #[serde(default)]
    pub error: Option<String>,
    #[serde(default)]
    pub result: Option<Value>,
}

#[derive(Debug, Deserialize)]
pub struct PresenceResponse {
    #[serde(default)]
    pub anyone_home: bool,
    #[serde(default)]
    pub occupants: Vec<String>,
    #[serde(default)]
    pub last_motion: Option<String>,
    #[serde(default)]
    pub home: Option<bool>,
    #[serde(default)]
    pub devices: Option<Vec<String>>,
}

#[derive(Debug, Deserialize)]
pub struct WeatherResponse {
    #[serde(default)]
    pub temperature_f: f64,
    #[serde(default)]
    pub condition: String,
    #[serde(default)]
    pub humidity: Option<f64>,
    #[serde(default)]
    pub forecast: Option<String>,
    #[serde(default)]
    pub temp: Option<f64>,
    #[serde(default)]
    pub description: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct TeslaStatusResponse {
    #[serde(default)]
    pub battery_level: i32,
    #[serde(default)]
    pub charging: bool,
    #[serde(default)]
    pub location: Option<String>,
    #[serde(default)]
    pub climate_on: bool,
    #[serde(default)]
    pub locked: bool,
    #[serde(default)]
    pub state: Option<String>,
    #[serde(default)]
    pub range_miles: Option<f64>,
}

#[derive(Debug, Deserialize)]
pub struct SleepStatusResponse {
    #[serde(default)]
    pub score: Option<i32>,
    #[serde(default)]
    pub duration_hours: Option<f64>,
    #[serde(default)]
    pub deep_sleep_pct: Option<f64>,
}

#[derive(Debug, Deserialize)]
pub struct HomeStatusResponse {
    #[serde(default)]
    pub lights_on: i32,
    #[serde(default)]
    pub shades_open: i32,
    #[serde(default)]
    pub temperature: Option<f64>,
    #[serde(default)]
    pub scene: Option<String>,
    #[serde(default)]
    pub safety_score: f64,
}

pub struct KagamiAPI {
    client: Client,
    health_client: Client,
    tesla_client: Client,
    base_url: String,
}

impl KagamiAPI {
    /// Create a new KagamiAPI client.
    ///
    /// Returns an error if HTTP clients cannot be created (e.g., TLS initialization failure).
    /// This replaces the previous panic-on-failure behavior with proper error handling.
    pub fn new(base_url: &str) -> Result<Self> {
        let client = Client::builder()
            .timeout(Duration::from_secs(DEFAULT_TIMEOUT_SECS))
            .build()
            .context("Failed to create HTTP client")?;

        let health_client = Client::builder()
            .timeout(Duration::from_secs(HEALTH_TIMEOUT_SECS))
            .build()
            .context("Failed to create health HTTP client")?;

        let tesla_client = Client::builder()
            .timeout(Duration::from_secs(TESLA_TIMEOUT_SECS))
            .build()
            .context("Failed to create Tesla HTTP client")?;

        Ok(Self {
            client,
            health_client,
            tesla_client,
            base_url: base_url.to_string(),
        })
    }

    /// Get the base URL of the API
    pub fn base_url(&self) -> &str {
        &self.base_url
    }

    /// Check API health with retry logic
    pub async fn health(&self) -> Result<HealthResponse> {
        let url = format!("{}/api/vitals/probes/ready", self.base_url);
        debug!("Checking health: {}", url);

        self.retry_get_with_client(&self.health_client, &url).await
    }

    /// Execute a scene
    pub async fn execute_scene(&self, scene: &str) -> Result<()> {
        let endpoint = match scene {
            "movie_mode" => "/home/movie-mode/enter",
            "goodnight" => "/home/goodnight",
            "welcome_home" => "/home/welcome-home",
            _ => return Err(anyhow::anyhow!("Unknown scene: {}", scene)),
        };

        self.post(endpoint, None).await
    }

    /// Control lights
    pub async fn set_lights(&self, level: i32, rooms: Option<Vec<String>>) -> Result<()> {
        let body = serde_json::json!({
            "level": level,
            "rooms": rooms,
        });

        self.post("/home/lights/set", Some(body)).await
    }

    /// Control fireplace
    pub async fn fireplace(&self, on: bool) -> Result<()> {
        let endpoint = if on {
            "/home/fireplace/on"
        } else {
            "/home/fireplace/off"
        };
        self.post(endpoint, None).await
    }

    /// Control shades (with path traversal protection)
    pub async fn shades(&self, action: &str, rooms: Option<Vec<String>>) -> Result<()> {
        // Security: Validate action against whitelist to prevent path traversal
        validate_action(action, ALLOWED_SHADE_ACTIONS, "shade")?;
        let body = serde_json::json!({ "rooms": rooms });
        self.post(&format!("/home/shades/{}", action), Some(body))
            .await
    }

    /// Control TV (with path traversal protection)
    pub async fn tv(&self, action: &str) -> Result<()> {
        // Security: Validate action against whitelist to prevent path traversal
        validate_action(action, ALLOWED_TV_ACTIONS, "TV")?;
        self.post(&format!("/home/tv/{}", action), None).await
    }

    /// Announce via TTS
    pub async fn announce(
        &self,
        text: &str,
        rooms: Option<Vec<String>>,
        colony: Option<&str>,
    ) -> Result<()> {
        let body = serde_json::json!({
            "text": text,
            "rooms": rooms,
            "colony": colony.unwrap_or("kagami"),
        });

        self.post("/home/announce", Some(body)).await
    }

    /// Process a voice command intent
    pub async fn process_command(&self, command: impl AsRef<str>) -> Result<CommandResponse> {
        let body = serde_json::json!({
            "lang": command.as_ref(),
        });

        let url = format!("{}/api/command/execute", self.base_url);
        debug!("Processing command: {}", url);

        self.retry_post_json(&url, body).await
    }

    // ═══════════════════════════════════════════════════════════════════════
    // LOCK CONTROL
    // ═══════════════════════════════════════════════════════════════════════

    /// Lock all doors
    pub async fn lock_doors(&self) -> Result<()> {
        self.post("/home/locks/lock-all", None).await
    }

    /// Unlock all doors
    pub async fn unlock_doors(&self) -> Result<()> {
        self.post("/home/locks/unlock", None).await
    }

    // ═══════════════════════════════════════════════════════════════════════
    // CLIMATE CONTROL
    // ═══════════════════════════════════════════════════════════════════════

    /// Set whole-house temperature
    pub async fn set_temperature(&self, temp: i32) -> Result<()> {
        let body = serde_json::json!({ "temperature": temp });
        self.post("/home/climate/set", Some(body)).await
    }

    /// Set temperature for specific room
    pub async fn set_room_temperature(&self, room: &str, temp: i32) -> Result<()> {
        let body = serde_json::json!({
            "room": room,
            "temperature": temp
        });
        self.post("/home/climate/room", Some(body)).await
    }

    /// Set HVAC mode for room
    pub async fn set_hvac_mode(&self, room: Option<&str>, mode: &str) -> Result<()> {
        let body = serde_json::json!({
            "room": room,
            "mode": mode
        });
        self.post("/home/climate/mode", Some(body)).await
    }

    // ═══════════════════════════════════════════════════════════════════════
    // TESLA CONTROL
    // ═══════════════════════════════════════════════════════════════════════

    /// Set Tesla climate
    pub async fn tesla_climate(&self, temp: Option<i32>) -> Result<()> {
        let body = serde_json::json!({ "temperature": temp });
        self.tesla_post("/home/tesla/climate/start", Some(body))
            .await
    }

    /// Lock Tesla
    pub async fn tesla_lock(&self) -> Result<()> {
        self.tesla_post("/home/tesla/lock", None).await
    }

    /// Unlock Tesla
    pub async fn tesla_unlock(&self) -> Result<()> {
        self.tesla_post("/home/tesla/unlock", None).await
    }

    /// Get Tesla charge status
    pub async fn tesla_charge_status(&self) -> Result<TeslaStatusResponse> {
        self.tesla_get("/home/tesla/status").await
    }

    /// Start Tesla charging
    pub async fn tesla_start_charge(&self) -> Result<()> {
        self.tesla_post("/home/tesla/charge/start", None).await
    }

    /// Stop Tesla charging
    pub async fn tesla_stop_charge(&self) -> Result<()> {
        self.tesla_post("/home/tesla/charge/stop", None).await
    }

    /// Enable Tesla sentry mode
    pub async fn tesla_sentry_on(&self) -> Result<()> {
        self.tesla_post("/home/tesla/sentry/on", None).await
    }

    /// Disable Tesla sentry mode
    pub async fn tesla_sentry_off(&self) -> Result<()> {
        self.tesla_post("/home/tesla/sentry/off", None).await
    }

    /// Open Tesla frunk
    pub async fn tesla_open_frunk(&self) -> Result<()> {
        self.tesla_post("/home/tesla/frunk/open", None).await
    }

    /// Get Tesla location
    pub async fn tesla_location(&self) -> Result<Value> {
        self.tesla_get("/home/tesla/location").await
    }

    // ═══════════════════════════════════════════════════════════════════════
    // EIGHT SLEEP (BED) CONTROL
    // ═══════════════════════════════════════════════════════════════════════

    /// Set bed temperature (both sides)
    pub async fn bed_set_temp(&self, level: i32) -> Result<()> {
        let body = serde_json::json!({ "level": level, "side": "both" });
        self.post("/bed/temperature", Some(body)).await
    }

    /// Set bed temperature for one side
    pub async fn bed_set_side_temp(&self, side: &str, level: i32) -> Result<()> {
        let body = serde_json::json!({ "level": level, "side": side });
        self.post("/bed/temperature", Some(body)).await
    }

    /// Turn bed off
    pub async fn bed_off(&self) -> Result<()> {
        self.post("/bed/off", None).await
    }

    /// Get sleep status
    pub async fn bed_sleep_status(&self) -> Result<SleepStatusResponse> {
        self.get("/bed/sleep").await
    }

    // ═══════════════════════════════════════════════════════════════════════
    // OUTDOOR LIGHTS (OELO)
    // ═══════════════════════════════════════════════════════════════════════

    /// Turn outdoor lights on
    pub async fn outdoor_on(&self) -> Result<()> {
        self.post("/outdoor/on", None).await
    }

    /// Turn outdoor lights off
    pub async fn outdoor_off(&self) -> Result<()> {
        self.post("/outdoor/off", None).await
    }

    /// Set outdoor light color
    pub async fn outdoor_color(&self, color: &str) -> Result<()> {
        let body = serde_json::json!({ "color": color });
        self.post("/outdoor/color", Some(body)).await
    }

    /// Set outdoor light pattern
    pub async fn outdoor_pattern(&self, pattern: &str) -> Result<()> {
        let body = serde_json::json!({ "pattern": pattern });
        self.post("/outdoor/pattern", Some(body)).await
    }

    /// Christmas mode for outdoor lights
    pub async fn outdoor_christmas(&self) -> Result<()> {
        self.post("/outdoor/christmas", None).await
    }

    /// Party mode for outdoor lights
    pub async fn outdoor_party(&self) -> Result<()> {
        self.post("/outdoor/party", None).await
    }

    // ═══════════════════════════════════════════════════════════════════════
    // SECURITY
    // ═══════════════════════════════════════════════════════════════════════

    /// Arm the alarm system
    pub async fn security_arm(&self) -> Result<()> {
        self.post("/security/arm", None).await
    }

    /// Arm in stay mode
    pub async fn security_arm_stay(&self) -> Result<()> {
        self.post("/security/arm/stay", None).await
    }

    /// Disarm the alarm
    pub async fn security_disarm(&self) -> Result<()> {
        self.post("/security/disarm", None).await
    }

    /// Get security status
    pub async fn security_status(&self) -> Result<Value> {
        self.get("/security/status").await
    }

    // ═══════════════════════════════════════════════════════════════════════
    // PRESENCE & WEATHER
    // ═══════════════════════════════════════════════════════════════════════

    /// Get presence status
    pub async fn get_presence(&self) -> Result<PresenceResponse> {
        self.get("/api/ambient/presence/current").await
    }

    /// Get weather information
    pub async fn get_weather(&self) -> Result<WeatherResponse> {
        self.get("/home/weather").await
    }

    /// Get home status summary
    pub async fn get_home_status(&self) -> Result<HomeStatusResponse> {
        self.get("/home/status").await
    }

    // ═══════════════════════════════════════════════════════════════════════
    // FIND MY DEVICE
    // ═══════════════════════════════════════════════════════════════════════

    /// Find a device (play sound)
    pub async fn find_device(&self, device: &str) -> Result<()> {
        let body = serde_json::json!({ "device": device });
        self.post("/home/findmy/sound", Some(body)).await
    }

    /// Get device location
    pub async fn find_device_location(&self, device: &str) -> Result<Value> {
        let url = format!("/home/findmy/locate?device={}", device);
        self.get(&url).await
    }

    // ═══════════════════════════════════════════════════════════════════════
    // AUTOMATION MODES
    // ═══════════════════════════════════════════════════════════════════════

    /// Set vacation mode
    pub async fn set_vacation_mode(&self, enabled: bool) -> Result<()> {
        let endpoint = if enabled {
            "/automation/vacation/on"
        } else {
            "/automation/vacation/off"
        };
        self.post(endpoint, None).await
    }

    /// Set guest mode
    pub async fn set_guest_mode(&self, enabled: bool) -> Result<()> {
        let endpoint = if enabled {
            "/automation/guest/on"
        } else {
            "/automation/guest/off"
        };
        self.post(endpoint, None).await
    }

    // ═══════════════════════════════════════════════════════════════════════
    // MUSIC (SPOTIFY)
    // ═══════════════════════════════════════════════════════════════════════

    /// Play music (optionally a specific playlist)
    pub async fn music_play(&self, playlist: Option<&str>) -> Result<()> {
        let body = serde_json::json!({ "playlist": playlist });
        self.post("/spotify/play", Some(body)).await
    }

    /// Pause music
    pub async fn music_pause(&self) -> Result<()> {
        self.post("/spotify/pause", None).await
    }

    /// Skip to next track
    pub async fn music_skip(&self) -> Result<()> {
        self.post("/spotify/skip", None).await
    }

    /// Adjust volume (with path traversal protection)
    pub async fn music_volume(&self, direction: &str) -> Result<()> {
        // Security: Validate direction against whitelist to prevent path traversal
        validate_action(direction, ALLOWED_VOLUME_DIRECTIONS, "volume")?;
        let endpoint = format!("/spotify/volume/{}", direction);
        self.post(&endpoint, None).await
    }

    // ═══════════════════════════════════════════════════════════════════════
    // INTERNAL HTTP METHODS
    // ═══════════════════════════════════════════════════════════════════════

    /// Generic GET request with retry logic
    async fn get<T: for<'de> Deserialize<'de>>(&self, endpoint: &str) -> Result<T> {
        let url = format!("{}{}", self.base_url, endpoint);
        self.retry_get_with_client(&self.client, &url).await
    }

    /// GET request with specific client and retry logic
    async fn retry_get_with_client<T: for<'de> Deserialize<'de>>(
        &self,
        client: &Client,
        url: &str,
    ) -> Result<T> {
        debug!("GET {}", url);

        let mut last_error = None;
        for attempt in 0..MAX_RETRIES {
            if attempt > 0 {
                let backoff = Duration::from_millis(INITIAL_BACKOFF_MS * 2u64.pow(attempt - 1));
                debug!("Retry {} after {:?}", attempt, backoff);
                tokio::time::sleep(backoff).await;
            }

            match client.get(url).send().await {
                Ok(response) => {
                    if response.status().is_success() {
                        return response.json().await.context("Failed to parse response");
                    }
                    let status = response.status();
                    // Don't retry client errors (4xx)
                    if status.is_client_error() {
                        error!("GET {} failed with client error: {}", url, status);
                        return Err(anyhow::anyhow!("GET failed: {}", status));
                    }
                    last_error = Some(anyhow::anyhow!("GET failed: {}", status));
                }
                Err(e) => {
                    last_error = Some(anyhow::anyhow!("GET request failed: {}", e));
                }
            }
        }

        let err = last_error
            .unwrap_or_else(|| anyhow::anyhow!("GET failed after {} retries", MAX_RETRIES));
        error!("GET {} failed after {} attempts: {}", url, MAX_RETRIES, err);
        Err(err)
    }

    /// Generic POST request with retry logic
    async fn post(&self, endpoint: &str, body: Option<Value>) -> Result<()> {
        let url = format!("{}{}", self.base_url, endpoint);
        self.retry_post_with_client(&self.client, &url, body).await
    }

    /// Public POST JSON method for agent bridge
    pub async fn post_json<T: for<'de> Deserialize<'de>>(
        &self,
        endpoint: &str,
        body: Value,
    ) -> Result<T> {
        let url = format!("{}{}", self.base_url, endpoint);
        self.retry_post_json(&url, body).await
    }

    /// Public GET JSON method for agent bridge
    pub async fn get_json<T: for<'de> Deserialize<'de>>(&self, endpoint: &str) -> Result<T> {
        let url = format!("{}{}", self.base_url, endpoint);
        self.retry_get_with_client(&self.client, &url).await
    }

    /// POST request returning JSON response with retry logic
    async fn retry_post_json<T: for<'de> Deserialize<'de>>(
        &self,
        url: &str,
        body: Value,
    ) -> Result<T> {
        debug!("POST (json) {}", url);

        let mut last_error = None;
        for attempt in 0..MAX_RETRIES {
            if attempt > 0 {
                let backoff = Duration::from_millis(INITIAL_BACKOFF_MS * 2u64.pow(attempt - 1));
                debug!("Retry {} after {:?}", attempt, backoff);
                tokio::time::sleep(backoff).await;
            }

            match self.client.post(url).json(&body).send().await {
                Ok(response) => {
                    if response.status().is_success() {
                        return response.json().await.context("Failed to parse response");
                    }
                    let status = response.status();
                    if status.is_client_error() {
                        error!("POST {} failed with client error: {}", url, status);
                        return Err(anyhow::anyhow!("POST failed: {}", status));
                    }
                    last_error = Some(anyhow::anyhow!("POST failed: {}", status));
                }
                Err(e) => {
                    last_error = Some(anyhow::anyhow!("POST request failed: {}", e));
                }
            }
        }

        let err = last_error
            .unwrap_or_else(|| anyhow::anyhow!("POST failed after {} retries", MAX_RETRIES));
        error!(
            "POST {} failed after {} attempts: {}",
            url, MAX_RETRIES, err
        );
        Err(err)
    }

    /// POST request with specific client and retry logic
    async fn retry_post_with_client(
        &self,
        client: &Client,
        url: &str,
        body: Option<Value>,
    ) -> Result<()> {
        info!("POST {}", url);

        let mut last_error = None;
        for attempt in 0..MAX_RETRIES {
            if attempt > 0 {
                let backoff = Duration::from_millis(INITIAL_BACKOFF_MS * 2u64.pow(attempt - 1));
                debug!("Retry {} after {:?}", attempt, backoff);
                tokio::time::sleep(backoff).await;
            }

            let mut request = client.post(url);
            if let Some(ref b) = body {
                request = request.json(b);
            }

            match request.send().await {
                Ok(response) => {
                    if response.status().is_success() {
                        return Ok(());
                    }
                    let status = response.status();
                    if status.is_client_error() {
                        error!("POST {} failed with client error: {}", url, status);
                        return Err(anyhow::anyhow!("POST failed: {}", status));
                    }
                    last_error = Some(anyhow::anyhow!("POST failed: {}", status));
                }
                Err(e) => {
                    last_error = Some(anyhow::anyhow!("POST request failed: {}", e));
                }
            }
        }

        let err = last_error
            .unwrap_or_else(|| anyhow::anyhow!("POST failed after {} retries", MAX_RETRIES));
        error!(
            "POST {} failed after {} attempts: {}",
            url, MAX_RETRIES, err
        );
        Err(err)
    }

    // ═══════════════════════════════════════════════════════════════════════
    // TESLA-SPECIFIC HTTP METHODS (30s timeout)
    // ═══════════════════════════════════════════════════════════════════════

    /// Tesla GET request with extended timeout and retry
    async fn tesla_get<T: for<'de> Deserialize<'de>>(&self, endpoint: &str) -> Result<T> {
        let url = format!("{}{}", self.base_url, endpoint);
        self.retry_get_with_client(&self.tesla_client, &url).await
    }

    /// Tesla POST request with extended timeout and retry
    async fn tesla_post(&self, endpoint: &str, body: Option<Value>) -> Result<()> {
        let url = format!("{}{}", self.base_url, endpoint);
        self.retry_post_with_client(&self.tesla_client, &url, body)
            .await
    }
}

/*
 * 鏡
 * h(x) ≥ 0. API calls verified.
 */
