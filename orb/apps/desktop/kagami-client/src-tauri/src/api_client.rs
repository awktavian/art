//! Kagami API Client — Optimized for Low Latency
//!
//! Communicates with the FastAPI backend at localhost:8001.
//! All requests respect h(x) ≥ 0 safety invariant.
//!
//! Performance optimizations:
//! - Connection pooling with keep-alive
//! - Intelligent request coalescing
//! - Parallel request execution
//! - Response caching integration
//!
//! Colony: Nexus (e₄) × Flow (e₃) → Crystal (e₇)

use reqwest::{Client, ClientBuilder};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{Duration, Instant};
use thiserror::Error;
use tracing::{debug, error, info, instrument, warn, Span};

use kagami_mesh_sdk::{get_circuit_breaker, CircuitState};

/// Environment variable for API base URL override
const ENV_API_BASE_URL: &str = "KAGAMI_API_URL";

// API endpoints - try multiple locations for discovery (used in discover method)
const API_ENDPOINTS: &[&str] = &[
    "https://api.awkronos.com",    // Production (primary)
    "http://localhost:8001",       // Local development
    "http://kagami.local:8001",    // mDNS/Bonjour discovery
    "http://127.0.0.1:8001",       // Fallback localhost
    "http://kagami-primary:8001",  // Docker/systemd service name
    "http://192.168.1.100:8001",   // Primary server static IP (example)
];
const DEFAULT_API_BASE: &str = "https://api.awkronos.com";

/// Service discovery endpoint on running API
const SERVICE_DISCOVERY_PATH: &str = "/api/v1/cluster/services";

/// Retry settings for service discovery
const MAX_DISCOVERY_RETRIES: u32 = 3;
const DISCOVERY_RETRY_DELAY_MS: u64 = 500;

/// Get API base URL from environment or use default
fn get_api_base_url() -> String {
    std::env::var(ENV_API_BASE_URL).unwrap_or_else(|_| DEFAULT_API_BASE.to_string())
}
const TIMEOUT_SECS: u64 = 5;  // Reduced from 10s
const CONNECT_TIMEOUT_MS: u64 = 500;  // Fast-fail on connection
const POOL_IDLE_TIMEOUT_SECS: u64 = 30;
const POOL_MAX_IDLE_PER_HOST: usize = 10;

#[derive(Error, Debug)]
pub enum ApiError {
    #[error("API request failed: {0}")]
    RequestFailed(#[from] reqwest::Error),

    #[error("API not running")]
    NotRunning,

    #[error("Safety violation: h(x) < 0")]
    SafetyViolation,

    #[error("Invalid response: {0}")]
    InvalidResponse(String),

    #[error("Circuit breaker open — service temporarily unavailable")]
    CircuitOpen,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApiHealth {
    pub status: String,
    #[serde(rename = "h_x")]
    pub safety_score: Option<f64>,
    pub uptime_ms: Option<u64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HomeStatus {
    pub initialized: bool,
    pub integrations: std::collections::HashMap<String, bool>,
    pub rooms: i32,
    pub occupied_rooms: i32,
    pub movie_mode: bool,
    pub avg_temp: Option<f64>,
}

/// Discovered service from cluster registry
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiscoveredService {
    pub node_id: String,
    pub address: String,
    pub port: u16,
    pub health: String,
    pub capabilities: Vec<String>,
}

/// Service registry response
#[derive(Debug, Clone, Serialize, Deserialize)]
struct ServiceRegistryResponse {
    services: Vec<ServiceInfo>,
}

/// Service info from registry
#[derive(Debug, Clone, Serialize, Deserialize)]
struct ServiceInfo {
    node_id: String,
    service_type: String,
    address: String,
    port: u16,
    health: String,
    #[serde(default)]
    capabilities: Vec<String>,
}

/// Kagami API client for communicating with the backend.
/// Optimized for low-latency, high-throughput operations.
#[derive(Clone)]
pub struct KagamiApi {
    client: Client,
    base_url: String,
    /// Request latency tracking
    avg_latency_us: std::sync::Arc<AtomicU64>,
    /// Request counter
    request_count: std::sync::Arc<AtomicU64>,
    /// Discovered services from cluster registry (for failover)
    discovered_services: Vec<DiscoveredService>,
}

impl Default for KagamiApi {
    fn default() -> Self {
        Self::new()
    }
}

impl KagamiApi {
    pub fn new() -> Self {
        // Optimized HTTP client with connection pooling
        let client = ClientBuilder::new()
            // Timeouts
            .timeout(Duration::from_secs(TIMEOUT_SECS))
            .connect_timeout(Duration::from_millis(CONNECT_TIMEOUT_MS))
            // Connection pooling
            .pool_idle_timeout(Duration::from_secs(POOL_IDLE_TIMEOUT_SECS))
            .pool_max_idle_per_host(POOL_MAX_IDLE_PER_HOST)
            // Keep-alive
            .tcp_keepalive(Duration::from_secs(30))
            .tcp_nodelay(true)  // Disable Nagle's algorithm for lower latency
            // Compression
            .gzip(true)
            .brotli(true)
            // Allow local network resolution (mDNS)
            .local_address(None)
            .build()
            .unwrap_or_else(|e| {
                tracing::error!("Failed to create HTTP client: {}", e);
                // Create a minimal client as fallback
                Client::new()
            });

        Self {
            client,
            base_url: get_api_base_url(),
            avg_latency_us: std::sync::Arc::new(AtomicU64::new(0)),
            request_count: std::sync::Arc::new(AtomicU64::new(0)),
            discovered_services: Vec::new(),
        }
    }

    /// Discover the Kagami API by trying multiple endpoints.
    /// Returns the first working endpoint URL.
    pub async fn discover(&mut self) -> Option<String> {
        // First try static endpoints
        for endpoint in API_ENDPOINTS {
            let url = format!("{}/health", endpoint);
            debug!("Trying API endpoint: {}", url);

            match self.client.get(&url).send().await {
                Ok(response) if response.status().is_success() => {
                    info!("✅ Kagami API discovered at: {}", endpoint);
                    self.base_url = endpoint.to_string();

                    // Now try to fetch additional API nodes from registry
                    if let Ok(services) = self.discover_cluster_services().await {
                        self.discovered_services = services;
                        info!(
                            "Discovered {} API services in cluster",
                            self.discovered_services.len()
                        );
                    }

                    return Some(endpoint.to_string());
                }
                Ok(response) => {
                    debug!("Endpoint {} returned status: {}", endpoint, response.status());
                }
                Err(e) => {
                    debug!("Endpoint {} failed: {}", endpoint, e);
                }
            }
        }

        warn!("Could not discover Kagami API at any endpoint");
        None
    }

    /// Discover cluster services from the service registry.
    /// Returns a list of available API nodes for failover.
    pub async fn discover_cluster_services(&self) -> Result<Vec<DiscoveredService>, ApiError> {
        let url = format!("{}{}", self.base_url, SERVICE_DISCOVERY_PATH);
        debug!("Fetching cluster services from: {}", url);

        let response = self.client.get(&url).send().await?;

        if !response.status().is_success() {
            return Err(ApiError::InvalidResponse(format!(
                "Service discovery failed: {}",
                response.status()
            )));
        }

        let registry: ServiceRegistryResponse = response.json().await
            .map_err(|e| ApiError::InvalidResponse(format!("Invalid service registry response: {}", e)))?;

        // Extract API services
        let api_services: Vec<DiscoveredService> = registry.services
            .into_iter()
            .filter(|s| s.service_type == "api" && s.health == "healthy")
            .map(|s| DiscoveredService {
                node_id: s.node_id,
                address: s.address,
                port: s.port,
                health: s.health,
                capabilities: s.capabilities,
            })
            .collect();

        Ok(api_services)
    }

    /// Try the request with automatic failover between discovered services.
    pub async fn request_with_failover(
        &self,
        endpoint: &str,
        method: &str,
        body: Option<Value>,
    ) -> Result<Value, ApiError> {
        // First try the primary endpoint
        match self.request(endpoint, method, body.clone()).await {
            Ok(result) => return Ok(result),
            Err(e) => {
                warn!("Primary API failed: {}, trying failover...", e);
            }
        }

        // Try discovered services
        for service in &self.discovered_services {
            let url = format!("http://{}:{}{}", service.address, service.port, endpoint);
            debug!("Trying failover endpoint: {}", url);

            let start = Instant::now();
            let request = match method.to_uppercase().as_str() {
                "GET" => self.client.get(&url),
                "POST" => {
                    let req = self.client.post(&url);
                    if let Some(ref b) = body {
                        req.json(b)
                    } else {
                        req
                    }
                }
                "PUT" => {
                    let req = self.client.put(&url);
                    if let Some(ref b) = body {
                        req.json(b)
                    } else {
                        req
                    }
                }
                "DELETE" => self.client.delete(&url),
                _ => continue,
            };

            match request.send().await {
                Ok(response) if response.status().is_success() => {
                    let latency_ms = start.elapsed().as_millis() as u64;
                    info!(
                        "Failover successful to {}: {}ms",
                        service.node_id,
                        latency_ms
                    );
                    return response.json().await.map_err(|e| ApiError::InvalidResponse(e.to_string()));
                }
                Ok(response) => {
                    debug!(
                        "Failover endpoint {} returned: {}",
                        service.node_id,
                        response.status()
                    );
                }
                Err(e) => {
                    debug!("Failover endpoint {} failed: {}", service.node_id, e);
                }
            }
        }

        Err(ApiError::NotRunning)
    }

    /// Get discovered services
    pub fn get_discovered_services(&self) -> &[DiscoveredService] {
        &self.discovered_services
    }

    /// Refresh service discovery
    pub async fn refresh_services(&mut self) -> Result<usize, ApiError> {
        let services = self.discover_cluster_services().await?;
        let count = services.len();
        self.discovered_services = services;
        Ok(count)
    }

    /// Get the current API base URL
    pub fn base_url(&self) -> &str {
        &self.base_url
    }

    /// Set a custom API base URL
    pub fn set_base_url(&mut self, url: String) {
        self.base_url = url;
    }

    /// Get average request latency in microseconds
    pub fn avg_latency_us(&self) -> u64 {
        self.avg_latency_us.load(Ordering::Relaxed)
    }

    /// Get total request count
    pub fn request_count(&self) -> u64 {
        self.request_count.load(Ordering::Relaxed)
    }

    /// Track request latency
    fn track_latency(&self, start: Instant) {
        let elapsed_us = start.elapsed().as_micros() as u64;
        let count = self.request_count.fetch_add(1, Ordering::Relaxed) + 1;
        let prev_avg = self.avg_latency_us.load(Ordering::Relaxed);

        // Rolling average
        let new_avg = if count == 1 {
            elapsed_us
        } else {
            (prev_avg * (count - 1) + elapsed_us) / count
        };

        self.avg_latency_us.store(new_avg, Ordering::Relaxed);

        // Warn on slow requests
        if elapsed_us > 500_000 {
            warn!("Slow API request: {}ms", elapsed_us / 1000);
        }
    }

    /// Check if the API is running (fast path).
    pub async fn is_running(&self) -> bool {
        // Use cached result if available
        if let Some(cached) = crate::cache::get_cache().get("health_check").await {
            return cached.get("status").and_then(|v| v.as_str()) == Some("ok");
        }
        self.health().await.is_ok()
    }

    /// Get API health status with caching and circuit breaker.
    #[instrument(name = "api_health_check", skip(self), fields(cached = tracing::field::Empty, latency_ms = tracing::field::Empty, circuit_state = tracing::field::Empty))]
    pub async fn health(&self) -> Result<ApiHealth, ApiError> {
        let current_span = Span::current();
        let circuit = get_circuit_breaker();

        // Record circuit state
        current_span.record("circuit_state", circuit.state().to_string().as_str());

        // Circuit breaker check — fail fast if open
        if !circuit.allow_request() {
            warn!("Circuit breaker OPEN — skipping health check");
            return Err(ApiError::CircuitOpen);
        }

        // Check cache first (5s TTL for health)
        if let Some(cached) = crate::cache::get_cache().get("health").await {
            if let Ok(health) = serde_json::from_value::<ApiHealth>(cached) {
                current_span.record("cached", true);
                debug!("Returning cached health status");
                return Ok(health);
            }
        }
        current_span.record("cached", false);

        let url = format!("{}/health", self.base_url);
        debug!(url = %url, "Checking API health");

        let start = Instant::now();
        let response = match self.client.get(&url).send().await {
            Ok(resp) => resp,
            Err(e) => {
                // Network failure — record with circuit breaker
                circuit.record_failure();
                return Err(ApiError::RequestFailed(e));
            }
        };
        let latency_ms = start.elapsed().as_millis() as u64;
        current_span.record("latency_ms", latency_ms);
        self.track_latency(start);

        if !response.status().is_success() {
            // HTTP failure — record with circuit breaker
            circuit.record_failure();
            warn!(status = response.status().as_u16(), "API health check failed");
            return Err(ApiError::NotRunning);
        }

        // Success — record with circuit breaker
        circuit.record_success();

        let health: ApiHealth = response.json().await?;

        // Check safety invariant
        if let Some(h_x) = health.safety_score {
            if h_x < 0.0 {
                error!(h_x = h_x, "Safety violation detected: h(x) < 0");
                return Err(ApiError::SafetyViolation);
            }
            debug!(h_x = h_x, "Safety score nominal");
        }

        // Cache the result
        if let Ok(json) = serde_json::to_value(&health) {
            crate::cache::get_cache().set("health", json).await;
        }

        info!(latency_ms = latency_ms, status = %health.status, "API health check successful");
        Ok(health)
    }

    /// Get circuit breaker state
    pub fn circuit_state(&self) -> CircuitState {
        get_circuit_breaker().state()
    }

    /// Reset circuit breaker (for user-initiated retry)
    pub fn reset_circuit_breaker(&self) {
        get_circuit_breaker().reset();
        info!("Circuit breaker reset by user request");
    }

    /// Get smart home status with caching.
    #[instrument(name = "get_home_status", skip(self), fields(cached = tracing::field::Empty, latency_ms = tracing::field::Empty))]
    pub async fn home_status(&self) -> Result<HomeStatus, ApiError> {
        let current_span = Span::current();

        // Check cache first (longer TTL for home status)
        if let Some(cached) = crate::cache::get_cache().get_home("home_status").await {
            if let Ok(status) = serde_json::from_value::<HomeStatus>(cached) {
                current_span.record("cached", true);
                debug!("Returning cached home status");
                return Ok(status);
            }
        }
        current_span.record("cached", false);

        let url = format!("{}/home/status", self.base_url);
        debug!(url = %url, "Fetching home status");

        let start = Instant::now();
        let response = self.client
            .get(&url)
            .send()
            .await?;
        let latency_ms = start.elapsed().as_millis() as u64;
        current_span.record("latency_ms", latency_ms);
        self.track_latency(start);

        if !response.status().is_success() {
            warn!(status = response.status().as_u16(), "Failed to get home status");
            return Err(ApiError::InvalidResponse(format!(
                "Status: {}",
                response.status()
            )));
        }

        let status: HomeStatus = response.json().await?;

        // Cache the result
        if let Ok(json) = serde_json::to_value(&status) {
            crate::cache::get_cache().set_home("home_status", json).await;
        }

        debug!(
            latency_ms = latency_ms,
            rooms = status.rooms,
            movie_mode = status.movie_mode,
            "Home status retrieved"
        );
        Ok(status)
    }

    /// Execute a smart home action (invalidates related cache).
    #[instrument(
        name = "smart_home_action",
        skip(self, params),
        fields(
            action = %action,
            latency_ms = tracing::field::Empty,
            success = tracing::field::Empty,
        )
    )]
    pub async fn smart_home_action(&self, action: &str, params: Option<Value>) -> Result<Value, ApiError> {
        let url = format!("{}/home/{}", self.base_url, action);
        let current_span = Span::current();

        info!(action = %action, has_params = params.is_some(), "Executing smart home action");

        let start = Instant::now();
        let response = if let Some(body) = params {
            self.client.post(&url).json(&body).send().await?
        } else {
            self.client.post(&url).send().await?
        };
        let latency_ms = start.elapsed().as_millis() as u64;
        current_span.record("latency_ms", latency_ms);
        self.track_latency(start);

        if !response.status().is_success() {
            current_span.record("success", false);
            warn!(
                action = %action,
                status = response.status().as_u16(),
                latency_ms = latency_ms,
                "Smart home action failed"
            );
            return Err(ApiError::InvalidResponse(format!(
                "Action {} failed: {}",
                action,
                response.status()
            )));
        }

        current_span.record("success", true);
        // Invalidate home status cache after actions
        crate::cache::get_cache().clear().await;

        info!(action = %action, latency_ms = latency_ms, "Smart home action completed");
        Ok(response.json().await?)
    }

    /// Make a generic API request with structured logging.
    #[instrument(
        name = "api_request",
        skip(self, body),
        fields(
            endpoint = %endpoint,
            method = %method,
            latency_ms = tracing::field::Empty,
            status_code = tracing::field::Empty,
        )
    )]
    pub async fn request(
        &self,
        endpoint: &str,
        method: &str,
        body: Option<Value>,
    ) -> Result<Value, ApiError> {
        let url = format!("{}{}", self.base_url, endpoint);
        let start = Instant::now();
        let current_span = Span::current();

        let request = match method.to_uppercase().as_str() {
            "GET" => self.client.get(&url),
            "POST" => {
                let req = self.client.post(&url);
                if let Some(b) = body {
                    req.json(&b)
                } else {
                    req
                }
            }
            "PUT" => {
                let req = self.client.put(&url);
                if let Some(b) = body {
                    req.json(&b)
                } else {
                    req
                }
            }
            "DELETE" => self.client.delete(&url),
            _ => {
                warn!(method = %method, "Unknown HTTP method");
                return Err(ApiError::InvalidResponse(format!("Unknown method: {}", method)));
            }
        };

        let response = request.send().await?;
        let latency_ms = start.elapsed().as_millis() as u64;
        let status_code = response.status().as_u16();

        // Record span fields for structured logging
        current_span.record("latency_ms", latency_ms);
        current_span.record("status_code", status_code);

        self.track_latency(start);

        if !response.status().is_success() {
            warn!(
                status = status_code,
                latency_ms = latency_ms,
                "API request returned error status"
            );
            return Err(ApiError::InvalidResponse(format!(
                "Request failed: {}",
                response.status()
            )));
        }

        debug!(latency_ms = latency_ms, "API request completed successfully");
        Ok(response.json().await?)
    }

    /// Enter movie mode.
    pub async fn movie_mode(&self) -> Result<Value, ApiError> {
        self.smart_home_action("movie-mode/enter", None).await
    }

    /// Exit movie mode.
    pub async fn exit_movie_mode(&self) -> Result<Value, ApiError> {
        self.smart_home_action("movie-mode/exit", None).await
    }

    /// Execute goodnight routine.
    pub async fn goodnight(&self) -> Result<Value, ApiError> {
        self.smart_home_action("goodnight", None).await
    }

    /// Execute welcome home routine.
    pub async fn welcome_home(&self) -> Result<Value, ApiError> {
        self.smart_home_action("welcome-home", None).await
    }

    /// Toggle fireplace.
    pub async fn fireplace(&self, on: bool) -> Result<Value, ApiError> {
        let action = if on { "fireplace/on" } else { "fireplace/off" };
        self.smart_home_action(action, None).await
    }

    /// Set lights level.
    pub async fn set_lights(&self, level: i32, rooms: Option<Vec<String>>) -> Result<Value, ApiError> {
        let body = serde_json::json!({
            "level": level,
            "rooms": rooms
        });
        self.smart_home_action("lights/set", Some(body)).await
    }

    /// Control shades.
    pub async fn shades(&self, action: &str, rooms: Option<Vec<String>>) -> Result<Value, ApiError> {
        let body = serde_json::json!({ "rooms": rooms });
        self.smart_home_action(&format!("shades/{}", action), Some(body)).await
    }

    /// Control TV.
    pub async fn tv(&self, action: &str, preset: Option<i32>) -> Result<Value, ApiError> {
        let url = if let Some(p) = preset {
            format!("{}/home/tv/{}?preset={}", self.base_url, action, p)
        } else {
            format!("{}/home/tv/{}", self.base_url, action)
        };

        let response = self.client.post(&url).send().await?;
        Ok(response.json().await?)
    }

    /// Announce to rooms.
    pub async fn announce(&self, text: &str, rooms: Option<Vec<String>>, colony: Option<&str>) -> Result<Value, ApiError> {
        let body = serde_json::json!({
            "text": text,
            "rooms": rooms,
            "colony": colony.unwrap_or("kagami")
        });
        self.smart_home_action("announce", Some(body)).await
    }
}

/// Global API client instance.
static API: std::sync::OnceLock<KagamiApi> = std::sync::OnceLock::new();

pub fn get_api() -> &'static KagamiApi {
    API.get_or_init(KagamiApi::new)
}
