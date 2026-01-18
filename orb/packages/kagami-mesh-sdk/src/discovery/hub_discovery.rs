//! Hub discovery service abstraction.
//!
//! Unifies hub discovery patterns across iOS and Android:
//! - iOS: Uses NWBrowser (Network.framework)
//! - Android: Uses NsdManager
//!
//! Both platforms implement the HubDiscoveryDelegate trait.
//!
//! h(x) >= 0. Always.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::RwLock;
use std::time::{Duration, Instant};

/// Service type for mDNS discovery.
pub const KAGAMI_HUB_SERVICE_TYPE: &str = "_kagami-hub._tcp.";

/// Default hub HTTP port.
pub const DEFAULT_HUB_PORT: u16 = 8080;

/// Discovered hub information.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct DiscoveredHub {
    /// Unique identifier for this hub instance.
    pub id: String,
    /// Human-readable hub name.
    pub name: String,
    /// Location description.
    pub location: String,
    /// IP address or hostname.
    pub host: String,
    /// HTTP API port.
    pub port: u16,
    /// Discovery method used.
    pub discovery_method: DiscoveryMethod,
    /// Last seen timestamp (Unix epoch seconds).
    pub last_seen: i64,
    /// Whether this hub is currently reachable.
    pub is_reachable: bool,
    /// Hub version if known.
    pub version: Option<String>,
    /// TXT record attributes from mDNS.
    pub attributes: HashMap<String, String>,
}

impl DiscoveredHub {
    /// Create a new discovered hub.
    pub fn new(name: impl Into<String>, host: impl Into<String>, port: u16) -> Self {
        let host = host.into();
        let name = name.into();
        Self {
            id: format!("{}:{}", host, port),
            name,
            location: "Unknown".to_string(),
            host,
            port,
            discovery_method: DiscoveryMethod::Manual,
            last_seen: chrono::Utc::now().timestamp(),
            is_reachable: false,
            version: None,
            attributes: HashMap::new(),
        }
    }

    /// Get the base URL for HTTP API calls.
    pub fn base_url(&self) -> String {
        format!("http://{}:{}", self.host, self.port)
    }

    /// Get the WebSocket URL.
    pub fn websocket_url(&self) -> String {
        format!("ws://{}:{}/ws", self.host, self.port)
    }

    /// Get the health check URL.
    pub fn health_url(&self) -> String {
        format!("{}/health", self.base_url())
    }

    /// Update last seen timestamp.
    pub fn touch(&mut self) {
        self.last_seen = chrono::Utc::now().timestamp();
    }

    /// Check if hub was seen within a duration.
    pub fn seen_within(&self, duration: Duration) -> bool {
        let now = chrono::Utc::now().timestamp();
        let cutoff = now - duration.as_secs() as i64;
        self.last_seen >= cutoff
    }
}

/// Method by which a hub was discovered.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum DiscoveryMethod {
    /// Discovered via mDNS/Bonjour.
    MdnsBonjour,
    /// Discovered via Android NSD.
    AndroidNsd,
    /// Manual configuration.
    Manual,
    /// Direct IP probe.
    DirectProbe,
    /// Saved from previous session.
    Cached,
}

impl Default for DiscoveryMethod {
    fn default() -> Self {
        Self::Manual
    }
}

/// Discovery state.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum DiscoveryState {
    /// Discovery not started.
    Idle,
    /// Discovery in progress.
    Discovering,
    /// Discovery completed.
    Completed,
    /// Discovery failed.
    Failed,
}

impl Default for DiscoveryState {
    fn default() -> Self {
        Self::Idle
    }
}

/// Configuration for hub discovery.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiscoveryConfig {
    /// Service type for mDNS (default: _kagami-hub._tcp.).
    pub service_type: String,
    /// Discovery timeout in milliseconds.
    pub timeout_ms: u64,
    /// Whether to probe known addresses directly.
    pub probe_known_addresses: bool,
    /// Known addresses to probe.
    pub known_addresses: Vec<(String, u16)>,
    /// Whether to cache discovered hubs.
    pub enable_caching: bool,
    /// Hub cache TTL in seconds.
    pub cache_ttl_seconds: u64,
}

impl Default for DiscoveryConfig {
    fn default() -> Self {
        Self {
            service_type: KAGAMI_HUB_SERVICE_TYPE.to_string(),
            timeout_ms: 10_000,
            probe_known_addresses: true,
            known_addresses: vec![
                ("kagami-hub.local".to_string(), DEFAULT_HUB_PORT),
                ("raspberrypi.local".to_string(), DEFAULT_HUB_PORT),
            ],
            enable_caching: true,
            cache_ttl_seconds: 300, // 5 minutes
        }
    }
}

/// Events emitted during discovery.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum DiscoveryEvent {
    /// Discovery started.
    Started,
    /// A hub was discovered.
    HubFound(DiscoveredHub),
    /// A hub was lost (no longer advertising).
    HubLost { id: String },
    /// A hub's reachability changed.
    ReachabilityChanged { id: String, is_reachable: bool },
    /// Discovery completed.
    Completed { hub_count: usize },
    /// Discovery failed.
    Failed { reason: String },
    /// Discovery timed out.
    Timeout,
}

/// Delegate trait for receiving discovery events.
///
/// Platforms implement this to receive hub discovery updates.
pub trait HubDiscoveryDelegate: Send + Sync {
    /// Called when a hub is discovered.
    fn on_hub_found(&self, hub: &DiscoveredHub);

    /// Called when a hub is lost.
    fn on_hub_lost(&self, hub_id: &str);

    /// Called when discovery state changes.
    fn on_state_changed(&self, state: DiscoveryState);

    /// Called when an error occurs.
    fn on_error(&self, error: &str);
}

/// No-op delegate for when callbacks aren't needed.
pub struct NoOpDiscoveryDelegate;

impl HubDiscoveryDelegate for NoOpDiscoveryDelegate {
    fn on_hub_found(&self, _hub: &DiscoveredHub) {}
    fn on_hub_lost(&self, _hub_id: &str) {}
    fn on_state_changed(&self, _state: DiscoveryState) {}
    fn on_error(&self, _error: &str) {}
}

/// Hub discovery service that manages discovered hubs.
///
/// This is the Rust-side manager. Platforms call methods on this
/// to report discovered hubs, and query the hub list.
pub struct HubDiscoveryService {
    /// Configuration.
    config: DiscoveryConfig,
    /// Discovered hubs by ID.
    hubs: RwLock<HashMap<String, DiscoveredHub>>,
    /// Current discovery state.
    state: RwLock<DiscoveryState>,
    /// Discovery start time for timeout tracking.
    discovery_started: RwLock<Option<Instant>>,
}

impl HubDiscoveryService {
    /// Create a new discovery service with default config.
    pub fn new() -> Self {
        Self::with_config(DiscoveryConfig::default())
    }

    /// Create with custom config.
    pub fn with_config(config: DiscoveryConfig) -> Self {
        Self {
            config,
            hubs: RwLock::new(HashMap::new()),
            state: RwLock::new(DiscoveryState::Idle),
            discovery_started: RwLock::new(None),
        }
    }

    /// Get the current discovery state.
    pub fn state(&self) -> DiscoveryState {
        *self.state.read().unwrap()
    }

    /// Set the discovery state.
    pub fn set_state(&self, state: DiscoveryState) {
        *self.state.write().unwrap() = state;
        if state == DiscoveryState::Discovering {
            *self.discovery_started.write().unwrap() = Some(Instant::now());
        }
    }

    /// Check if discovery has timed out.
    pub fn has_timed_out(&self) -> bool {
        if let Some(started) = *self.discovery_started.read().unwrap() {
            started.elapsed() > Duration::from_millis(self.config.timeout_ms)
        } else {
            false
        }
    }

    /// Report a discovered hub (called by platform discovery code).
    pub fn report_hub_found(&self, hub: DiscoveredHub) -> bool {
        let mut hubs = self.hubs.write().unwrap();
        let is_new = !hubs.contains_key(&hub.id);
        hubs.insert(hub.id.clone(), hub);
        is_new
    }

    /// Report a hub was lost.
    pub fn report_hub_lost(&self, hub_id: &str) -> bool {
        self.hubs.write().unwrap().remove(hub_id).is_some()
    }

    /// Update hub reachability.
    pub fn set_hub_reachable(&self, hub_id: &str, is_reachable: bool) {
        if let Some(hub) = self.hubs.write().unwrap().get_mut(hub_id) {
            hub.is_reachable = is_reachable;
            if is_reachable {
                hub.touch();
            }
        }
    }

    /// Get all discovered hubs.
    pub fn get_hubs(&self) -> Vec<DiscoveredHub> {
        self.hubs.read().unwrap().values().cloned().collect()
    }

    /// Get reachable hubs only.
    pub fn get_reachable_hubs(&self) -> Vec<DiscoveredHub> {
        self.hubs
            .read()
            .unwrap()
            .values()
            .filter(|h| h.is_reachable)
            .cloned()
            .collect()
    }

    /// Get a specific hub by ID.
    pub fn get_hub(&self, hub_id: &str) -> Option<DiscoveredHub> {
        self.hubs.read().unwrap().get(hub_id).cloned()
    }

    /// Get hub count.
    pub fn hub_count(&self) -> usize {
        self.hubs.read().unwrap().len()
    }

    /// Clear all discovered hubs.
    pub fn clear(&self) {
        self.hubs.write().unwrap().clear();
    }

    /// Remove stale hubs not seen within the cache TTL.
    pub fn prune_stale_hubs(&self) -> usize {
        let ttl = Duration::from_secs(self.config.cache_ttl_seconds);
        let mut hubs = self.hubs.write().unwrap();
        let before = hubs.len();
        hubs.retain(|_, hub| hub.seen_within(ttl));
        before - hubs.len()
    }

    /// Get the configuration.
    pub fn config(&self) -> &DiscoveryConfig {
        &self.config
    }

    /// Get known addresses to probe.
    pub fn known_addresses(&self) -> &[(String, u16)] {
        &self.config.known_addresses
    }
}

impl Default for HubDiscoveryService {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_discovered_hub() {
        let hub = DiscoveredHub::new("Test Hub", "192.168.1.100", 8080);
        assert_eq!(hub.base_url(), "http://192.168.1.100:8080");
        assert_eq!(hub.websocket_url(), "ws://192.168.1.100:8080/ws");
        assert_eq!(hub.id, "192.168.1.100:8080");
    }

    #[test]
    fn test_discovery_service() {
        let service = HubDiscoveryService::new();
        assert_eq!(service.state(), DiscoveryState::Idle);
        assert_eq!(service.hub_count(), 0);

        // Report a hub
        let hub = DiscoveredHub::new("Hub 1", "192.168.1.100", 8080);
        assert!(service.report_hub_found(hub.clone()));

        // Second report of same hub is not "new"
        assert!(!service.report_hub_found(hub));

        assert_eq!(service.hub_count(), 1);
        assert!(service.get_hub("192.168.1.100:8080").is_some());
    }

    #[test]
    fn test_hub_reachability() {
        let service = HubDiscoveryService::new();

        let mut hub = DiscoveredHub::new("Hub 1", "192.168.1.100", 8080);
        hub.is_reachable = false;
        service.report_hub_found(hub);

        assert_eq!(service.get_reachable_hubs().len(), 0);

        service.set_hub_reachable("192.168.1.100:8080", true);
        assert_eq!(service.get_reachable_hubs().len(), 1);
    }

    #[test]
    fn test_discovery_state() {
        let service = HubDiscoveryService::new();

        service.set_state(DiscoveryState::Discovering);
        assert_eq!(service.state(), DiscoveryState::Discovering);

        service.set_state(DiscoveryState::Completed);
        assert_eq!(service.state(), DiscoveryState::Completed);
    }

    #[test]
    fn test_hub_lost() {
        let service = HubDiscoveryService::new();

        let hub = DiscoveredHub::new("Hub 1", "192.168.1.100", 8080);
        service.report_hub_found(hub);
        assert_eq!(service.hub_count(), 1);

        assert!(service.report_hub_lost("192.168.1.100:8080"));
        assert_eq!(service.hub_count(), 0);

        // Losing non-existent hub returns false
        assert!(!service.report_hub_lost("non-existent"));
    }

    #[test]
    fn test_default_config() {
        let config = DiscoveryConfig::default();
        assert_eq!(config.service_type, KAGAMI_HUB_SERVICE_TYPE);
        assert!(config.probe_known_addresses);
        assert!(!config.known_addresses.is_empty());
    }
}
