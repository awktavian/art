//! State Cache — Cached home and vehicle state for offline operation
//!
//! The hub caches state from the main API, enabling:
//! - Offline dashboard operation
//! - Reduced API calls
//! - Faster response times
//! - Zone-aware capability degradation
//!
//! # Safety
//! ```text
//! h(x) >= 0 always
//! ```

use serde::{Deserialize, Serialize};
use std::time::{Duration, Instant};
use tokio::sync::RwLock;
use tracing::{debug, info, warn};

// ═══════════════════════════════════════════════════════════════════════════
// Zone Levels (Vinge's Zones of Thought)
// ═══════════════════════════════════════════════════════════════════════════

/// Capability zone based on connectivity
#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ZoneLevel {
    /// Full cloud + API + LLM — all capabilities
    Transcend,
    /// LAN + API — home control, caching, local voice
    Beyond,
    /// Hub alone on LAN — cached state, pattern matching, local TTS
    SlowZone,
    /// Hub alone, no network — emergency responses only
    UnthinkingDepths,
}

impl std::fmt::Display for ZoneLevel {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ZoneLevel::Transcend => write!(f, "Transcend"),
            ZoneLevel::Beyond => write!(f, "Beyond"),
            ZoneLevel::SlowZone => write!(f, "SlowZone"),
            ZoneLevel::UnthinkingDepths => write!(f, "UnthinkingDepths"),
        }
    }
}

impl ZoneLevel {
    pub fn description(&self) -> &'static str {
        match self {
            ZoneLevel::Transcend => "Full cloud connectivity",
            ZoneLevel::Beyond => "API connected, limited cloud",
            ZoneLevel::SlowZone => "Offline, using cached state",
            ZoneLevel::UnthinkingDepths => "Isolated, minimal capabilities",
        }
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// Cached State Types
// ═══════════════════════════════════════════════════════════════════════════

/// Tesla vehicle state (cached from API)
#[derive(Clone, Debug, Default, Serialize, Deserialize, PartialEq)]
pub struct TeslaState {
    pub connected: bool,
    pub is_home: bool,
    pub battery_level: i32,
    pub battery_range: f64,
    pub charging: bool,
    pub charge_limit: i32,
    pub climate_on: bool,
    pub climate_temp: f64,
    pub inside_temp: f64,
    pub outside_temp: f64,
    pub locked: bool,
    pub sentry_mode: bool,
    pub frunk_open: bool,
    pub trunk_open: bool,
    pub driver_door_open: bool,
    pub passenger_door_open: bool,
    pub driver_rear_door_open: bool,
    pub passenger_rear_door_open: bool,
    pub odometer: Option<f64>,
    pub software_version: Option<String>,
}

/// Home state (cached from API)
#[derive(Clone, Debug, Default, Serialize, Deserialize, PartialEq)]
pub struct HomeState {
    pub connected: bool,
    pub presence: String,
    pub security_state: String,
    pub lights: Vec<LightState>,
    pub shades: Vec<ShadeState>,
    pub climate: ClimateState,
    pub locks: Vec<LockState>,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize, PartialEq)]
pub struct LightState {
    pub id: i32,
    pub name: String,
    pub room: String,
    pub level: i32,
    pub on: bool,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize, PartialEq)]
pub struct ShadeState {
    pub id: i32,
    pub name: String,
    pub room: String,
    pub level: i32,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize, PartialEq)]
pub struct ClimateState {
    pub hvac_mode: String,
    pub current_temp: Option<f64>,
    pub target_temp: Option<f64>,
    pub humidity: Option<f64>,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize, PartialEq)]
pub struct LockState {
    pub id: i32,
    pub name: String,
    pub locked: bool,
}

/// Weather state
#[derive(Clone, Debug, Default, Serialize, Deserialize, PartialEq)]
pub struct WeatherState {
    pub temp_f: f64,
    pub current_temp: f64,  // Alias for voice pipeline
    pub condition: String,
    pub humidity: i32,
    pub wind_mph: f64,
    pub forecast: Vec<ForecastDay>,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize, PartialEq)]
pub struct ForecastDay {
    pub day: String,
    pub high: f64,
    pub low: f64,
    pub condition: String,
}

// ═══════════════════════════════════════════════════════════════════════════
// Cached Entry with TTL
// ═══════════════════════════════════════════════════════════════════════════

struct CachedEntry<T> {
    data: T,
    fetched_at: Instant,
    ttl: Duration,
}

impl<T: Clone + Default> CachedEntry<T> {
    fn new(data: T, ttl: Duration) -> Self {
        Self {
            data,
            fetched_at: Instant::now(),
            ttl,
        }
    }

    fn is_valid(&self) -> bool {
        self.fetched_at.elapsed() < self.ttl
    }

    fn get(&self) -> Option<T> {
        if self.is_valid() {
            Some(self.data.clone())
        } else {
            None
        }
    }

    fn age_secs(&self) -> u64 {
        self.fetched_at.elapsed().as_secs()
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// State Cache
// ═══════════════════════════════════════════════════════════════════════════

/// Central state cache for the hub
pub struct StateCache {
    api_url: String,
    client: reqwest::Client,

    // Cached state with TTL
    tesla: RwLock<Option<CachedEntry<TeslaState>>>,
    home: RwLock<Option<CachedEntry<HomeState>>>,
    weather: RwLock<Option<CachedEntry<WeatherState>>>,

    // Zone tracking
    zone: RwLock<ZoneLevel>,
    last_api_contact: RwLock<Option<Instant>>,
}

impl StateCache {
    pub fn new(api_url: &str) -> Self {
        Self {
            api_url: api_url.to_string(),
            client: reqwest::Client::builder()
                .timeout(Duration::from_secs(10))
                .build()
                .expect("Failed to create HTTP client"),
            tesla: RwLock::new(None),
            home: RwLock::new(None),
            weather: RwLock::new(None),
            zone: RwLock::new(ZoneLevel::SlowZone),
            last_api_contact: RwLock::new(None),
        }
    }

    /// Get current zone level
    pub async fn get_zone(&self) -> ZoneLevel {
        *self.zone.read().await
    }

    /// Update zone based on connectivity probe
    pub async fn probe_zone(&self) -> ZoneLevel {
        // Try to reach API
        let api_ok = self
            .client
            .get(format!("{}/health", self.api_url))
            .send()
            .await
            .map(|r| r.status().is_success())
            .unwrap_or(false);

        // Try to reach internet (simple check)
        let internet_ok = self
            .client
            .get("https://1.1.1.1/cdn-cgi/trace")
            .timeout(Duration::from_secs(3))
            .send()
            .await
            .map(|r| r.status().is_success())
            .unwrap_or(false);

        let zone = match (internet_ok, api_ok) {
            (true, true) => ZoneLevel::Transcend,
            (_, true) => ZoneLevel::Beyond,
            (true, false) => ZoneLevel::SlowZone,
            (false, false) => ZoneLevel::UnthinkingDepths,
        };

        *self.zone.write().await = zone;

        if api_ok {
            *self.last_api_contact.write().await = Some(Instant::now());
        }

        debug!("Zone probed: {:?}", zone);
        zone
    }

    // ─────────────── TESLA STATE ───────────────

    /// Get Tesla state (from cache or fetch)
    pub async fn get_tesla(&self) -> Option<TeslaState> {
        // Check cache first
        {
            let cache = self.tesla.read().await;
            if let Some(entry) = cache.as_ref() {
                if let Some(data) = entry.get() {
                    return Some(data);
                }
            }
        }

        // Cache miss or expired, try to fetch
        self.refresh_tesla().await
    }

    /// Force refresh Tesla state from API
    pub async fn refresh_tesla(&self) -> Option<TeslaState> {
        let url = format!("{}/home/tesla/status", self.api_url);
        debug!("Fetching Tesla state from {}", url);

        match self.client.get(&url).send().await {
            Ok(resp) if resp.status().is_success() => {
                match resp.json::<TeslaState>().await {
                    Ok(state) => {
                        let mut cache = self.tesla.write().await;
                        *cache = Some(CachedEntry::new(state.clone(), Duration::from_secs(60)));
                        *self.last_api_contact.write().await = Some(Instant::now());
                        info!("Tesla state refreshed: {}% battery", state.battery_level);
                        Some(state)
                    }
                    Err(e) => {
                        warn!("Failed to parse Tesla state: {}", e);
                        None
                    }
                }
            }
            Ok(resp) => {
                warn!("Tesla API returned {}", resp.status());
                // Return stale cache if available
                self.tesla.read().await.as_ref().map(|e| e.data.clone())
            }
            Err(e) => {
                warn!("Failed to fetch Tesla state: {}", e);
                // Return stale cache if available
                self.tesla.read().await.as_ref().map(|e| e.data.clone())
            }
        }
    }

    /// Get Tesla state age in seconds
    pub async fn tesla_age(&self) -> Option<u64> {
        self.tesla.read().await.as_ref().map(|e| e.age_secs())
    }

    // ─────────────── HOME STATE ───────────────

    /// Get home state (from cache or fetch)
    pub async fn get_home(&self) -> Option<HomeState> {
        // Check cache first
        {
            let cache = self.home.read().await;
            if let Some(entry) = cache.as_ref() {
                if let Some(data) = entry.get() {
                    return Some(data);
                }
            }
        }

        // Cache miss or expired, try to fetch
        self.refresh_home().await
    }

    /// Force refresh home state from API
    pub async fn refresh_home(&self) -> Option<HomeState> {
        let url = format!("{}/home/state", self.api_url);
        debug!("Fetching home state from {}", url);

        match self.client.get(&url).send().await {
            Ok(resp) if resp.status().is_success() => {
                match resp.json::<HomeState>().await {
                    Ok(state) => {
                        let mut cache = self.home.write().await;
                        *cache = Some(CachedEntry::new(state.clone(), Duration::from_secs(30)));
                        *self.last_api_contact.write().await = Some(Instant::now());
                        info!("Home state refreshed");
                        Some(state)
                    }
                    Err(e) => {
                        warn!("Failed to parse home state: {}", e);
                        None
                    }
                }
            }
            Ok(resp) => {
                warn!("Home API returned {}", resp.status());
                self.home.read().await.as_ref().map(|e| e.data.clone())
            }
            Err(e) => {
                warn!("Failed to fetch home state: {}", e);
                self.home.read().await.as_ref().map(|e| e.data.clone())
            }
        }
    }

    // ─────────────── WEATHER STATE ───────────────

    /// Get weather state (from cache or fetch)
    pub async fn get_weather(&self) -> Option<WeatherState> {
        {
            let cache = self.weather.read().await;
            if let Some(entry) = cache.as_ref() {
                if let Some(data) = entry.get() {
                    return Some(data);
                }
            }
        }

        self.refresh_weather().await
    }

    /// Force refresh weather from API
    pub async fn refresh_weather(&self) -> Option<WeatherState> {
        let url = format!("{}/weather", self.api_url);

        match self.client.get(&url).send().await {
            Ok(resp) if resp.status().is_success() => {
                match resp.json::<WeatherState>().await {
                    Ok(state) => {
                        let mut cache = self.weather.write().await;
                        *cache = Some(CachedEntry::new(state.clone(), Duration::from_secs(300)));
                        Some(state)
                    }
                    Err(_) => None,
                }
            }
            _ => self.weather.read().await.as_ref().map(|e| e.data.clone()),
        }
    }

    // ─────────────── CONTROL COMMANDS ───────────────

    /// Execute a command (forward to API or handle locally)
    pub async fn execute_command(&self, command: &str, params: serde_json::Value) -> Result<serde_json::Value, String> {
        let zone = self.get_zone().await;

        match zone {
            ZoneLevel::Transcend | ZoneLevel::Beyond => {
                // Forward to API
                let url = format!("{}{}", self.api_url, command);
                match self.client.post(&url).json(&params).send().await {
                    Ok(resp) => {
                        let json: serde_json::Value = resp.json().await.unwrap_or_default();
                        Ok(json)
                    }
                    Err(e) => Err(format!("API error: {}", e)),
                }
            }
            ZoneLevel::SlowZone | ZoneLevel::UnthinkingDepths => {
                // Local handling or queued for later
                Err(format!(
                    "Command queued — currently in {} zone",
                    zone.description()
                ))
            }
        }
    }

    /// Set lights (forward to API)
    pub async fn set_lights(&self, level: i32, rooms: Option<&[String]>) -> Result<(), String> {
        let params = serde_json::json!({
            "level": level,
            "rooms": rooms,
        });
        self.execute_command("/home/lights/set", params).await?;
        Ok(())
    }

    /// Control Tesla climate
    pub async fn tesla_climate(&self, on: bool, temp_c: Option<f64>) -> Result<(), String> {
        let endpoint = if on {
            "/home/tesla/climate/start"
        } else {
            "/home/tesla/climate/stop"
        };
        let params = serde_json::json!({ "temp_c": temp_c.unwrap_or(21.0) });
        self.execute_command(endpoint, params).await?;
        Ok(())
    }

    /// Lock/unlock Tesla
    pub async fn tesla_lock(&self, lock: bool) -> Result<(), String> {
        let endpoint = if lock {
            "/home/tesla/lock"
        } else {
            "/home/tesla/unlock"
        };
        self.execute_command(endpoint, serde_json::json!({})).await?;
        Ok(())
    }

    /// Open Tesla trunk/frunk
    pub async fn tesla_trunk(&self, which: &str) -> Result<(), String> {
        let params = serde_json::json!({ "which": which });
        self.execute_command("/home/tesla/trunk", params).await?;
        Ok(())
    }

    /// Honk Tesla horn
    pub async fn tesla_honk(&self) -> Result<(), String> {
        self.execute_command("/home/tesla/honk", serde_json::json!({}))
            .await?;
        Ok(())
    }

    /// Flash Tesla lights
    pub async fn tesla_flash(&self) -> Result<(), String> {
        self.execute_command("/home/tesla/flash", serde_json::json!({}))
            .await?;
        Ok(())
    }
}

/*
 * 鏡
 */
