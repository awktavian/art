//! Hub Discovery via mDNS
//!
//! Discovers other Kagami Hubs on the local network using mDNS.
//! Service type: _kagami-hub._tcp.local.
//!
//! Colony: Nexus (e₄) — Finding peers
//!
//! η → s → μ → a → η′
//! h(x) ≥ 0. Always.

use std::collections::HashMap;
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::RwLock;
use tracing::{debug, info, warn};
use serde::{Deserialize, Serialize};

/// Service type for mDNS discovery
pub const SERVICE_TYPE: &str = "_kagami-hub._tcp.local.";

/// Get current Unix timestamp in seconds
fn now_unix() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
}

/// Information about a discovered peer
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Peer {
    /// Unique hub identifier
    pub hub_id: String,
    /// Human-readable name
    pub name: String,
    /// IP address
    pub address: String,
    /// Port number
    pub port: u16,
    /// When peer was last seen (Unix timestamp seconds)
    pub last_seen: u64,
    /// Whether this peer is the current leader
    pub is_leader: bool,
    /// Peer's public key (for authentication)
    pub public_key: Option<Vec<u8>>,
    /// Whether TLS is enabled for this peer (default: true for security)
    #[serde(default = "default_tls_enabled")]
    pub tls_enabled: bool,
    /// Additional properties from mDNS TXT records
    pub properties: HashMap<String, String>,
}

/// Default TLS enabled to true for security
fn default_tls_enabled() -> bool {
    true
}

impl Peer {
    /// Get the full URL to this peer's API (uses HTTPS for secure mesh communication)
    pub fn api_url(&self) -> String {
        let scheme = if self.tls_enabled { "https" } else { "http" };
        format!("{}://{}:{}", scheme, self.address, self.port)
    }

    /// Check if peer is still considered alive (seen within timeout)
    pub fn is_alive(&self, timeout: Duration) -> bool {
        let now = now_unix();
        now.saturating_sub(self.last_seen) < timeout.as_secs()
    }
}

/// mDNS-based peer discovery
pub struct MeshDiscovery {
    /// This hub's ID
    hub_id: String,
    /// This hub's name
    hub_name: String,
    /// Known peers
    peers: Arc<RwLock<Vec<Peer>>>,
    /// Port we're advertising
    port: u16,
}

impl MeshDiscovery {
    /// Create a new mesh discovery instance
    pub fn new(
        hub_id: String,
        hub_name: String,
        peers: Arc<RwLock<Vec<Peer>>>,
    ) -> Self {
        Self {
            hub_id,
            hub_name,
            peers,
            port: 8080,
        }
    }

    /// Set the port to advertise
    pub fn with_port(mut self, port: u16) -> Self {
        self.port = port;
        self
    }

    /// Start mDNS discovery and advertisement
    #[cfg(feature = "mdns")]
    pub async fn start(&self) -> anyhow::Result<()> {
        use mdns_sd::{ServiceDaemon, ServiceInfo, ServiceEvent};

        info!("Starting mDNS discovery for hub: {}", self.hub_id);

        let mdns = ServiceDaemon::new()
            .map_err(|e| anyhow::anyhow!("Failed to create mDNS daemon: {}", e))?;

        // Advertise ourselves
        self.advertise(&mdns)?;

        // Browse for peers
        let peers = self.peers.clone();
        let our_id = self.hub_id.clone();

        let browse_handle = mdns.browse(SERVICE_TYPE)
            .map_err(|e| anyhow::anyhow!("Failed to start mDNS browse: {}", e))?;

        // Spawn browse task
        tokio::spawn(async move {
            loop {
                match browse_handle.recv_async().await {
                    Ok(event) => {
                        match event {
                            ServiceEvent::ServiceResolved(info) => {
                                // Extract hub ID from properties
                                let hub_id = info.get_property_val_str("hub_id")
                                    .unwrap_or_default()
                                    .to_string();

                                // Don't add ourselves
                                if hub_id == our_id || hub_id.is_empty() {
                                    continue;
                                }

                                let name = info.get_property_val_str("name")
                                    .unwrap_or(info.get_fullname())
                                    .to_string();

                                let address = info.get_addresses()
                                    .iter()
                                    .next()
                                    .map(|a| a.to_string())
                                    .unwrap_or_default();

                                if address.is_empty() {
                                    continue;
                                }

                                let mut properties = HashMap::new();
                                for prop in info.get_properties().iter() {
                                    // TxtProperty in mdns-sd - val_str() returns &str
                                    let val = prop.val_str();
                                    properties.insert(prop.key().to_string(), val.to_string());
                                }

                                // Get public key bytes if present
                                // get_property_val returns Option<Option<&[u8]>> in mdns-sd 0.11
                                let public_key = info.get_property_val("public_key")
                                    .flatten()
                                    .map(|v| v.to_vec());

                                // Check if TLS is enabled (default to true for security)
                                let tls_enabled = properties.get("tls")
                                    .map(|v| v == "1" || v.to_lowercase() == "true")
                                    .unwrap_or(true);

                                let peer = Peer {
                                    hub_id: hub_id.clone(),
                                    name,
                                    address,
                                    port: info.get_port(),
                                    last_seen: now_unix(),
                                    is_leader: false,
                                    public_key,
                                    tls_enabled,
                                    properties,
                                };

                                info!("📡 Discovered peer: {} at {}", peer.name, peer.api_url());

                                // Add or update peer
                                let mut peers_guard = peers.write().await;
                                if let Some(existing) = peers_guard.iter_mut().find(|p| p.hub_id == hub_id) {
                                    existing.last_seen = now_unix();
                                    existing.address = peer.address.clone();
                                    existing.port = peer.port;
                                } else {
                                    peers_guard.push(peer);
                                }
                            }
                            ServiceEvent::ServiceRemoved(_, fullname) => {
                                debug!("mDNS service removed: {}", fullname);

                                // Remove peer by matching fullname pattern
                                let mut peers_guard = peers.write().await;
                                peers_guard.retain(|p| !fullname.contains(&p.hub_id));
                            }
                            _ => {}
                        }
                    }
                    Err(e) => {
                        warn!("mDNS browse error: {}", e);
                        break;
                    }
                }
            }
        });

        Ok(())
    }

    #[cfg(not(feature = "mdns"))]
    pub async fn start(&self) -> anyhow::Result<()> {
        warn!("mDNS discovery disabled (compile with --features mdns)");
        Ok(())
    }

    /// Advertise this hub via mDNS
    #[cfg(feature = "mdns")]
    fn advertise(&self, mdns: &mdns_sd::ServiceDaemon) -> anyhow::Result<()> {
        use mdns_sd::ServiceInfo;

        let hostname = hostname::get()
            .map(|h| h.to_string_lossy().to_string())
            .unwrap_or_else(|_| "kagami-hub".to_string());

        let mut properties = HashMap::new();
        properties.insert("hub_id".to_string(), self.hub_id.clone());
        properties.insert("name".to_string(), self.hub_name.clone());
        properties.insert("version".to_string(), env!("CARGO_PKG_VERSION").to_string());
        properties.insert("tls".to_string(), "1".to_string()); // Always advertise TLS support

        let service = ServiceInfo::new(
            SERVICE_TYPE,
            &self.hub_name,
            &format!("{}.local.", hostname),
            (),
            self.port,
            properties,
        ).map_err(|e| anyhow::anyhow!("Failed to create service info: {}", e))?;

        mdns.register(service)
            .map_err(|e| anyhow::anyhow!("Failed to register mDNS service: {}", e))?;

        info!("📡 Advertising hub via mDNS: {} on port {}", self.hub_name, self.port);

        Ok(())
    }

    /// Remove stale peers (not seen recently)
    pub async fn cleanup_stale_peers(&self, timeout: Duration) {
        let mut peers = self.peers.write().await;
        let before = peers.len();
        peers.retain(|p| p.is_alive(timeout));
        let removed = before - peers.len();
        if removed > 0 {
            info!("Removed {} stale peers", removed);
        }
    }

    /// Get all known peers
    pub async fn get_peers(&self) -> Vec<Peer> {
        self.peers.read().await.clone()
    }

    /// Find a specific peer by hub ID
    pub async fn find_peer(&self, hub_id: &str) -> Option<Peer> {
        self.peers.read().await
            .iter()
            .find(|p| p.hub_id == hub_id)
            .cloned()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_peer_api_url_https() {
        let peer = Peer {
            hub_id: "test-1".to_string(),
            name: "Test Hub".to_string(),
            address: "192.168.1.100".to_string(),
            port: 8080,
            last_seen: now_unix(),
            is_leader: false,
            public_key: None,
            tls_enabled: true,
            properties: HashMap::new(),
        };

        assert_eq!(peer.api_url(), "https://192.168.1.100:8080");
    }

    #[test]
    fn test_peer_api_url_http_fallback() {
        let peer = Peer {
            hub_id: "test-1".to_string(),
            name: "Test Hub".to_string(),
            address: "192.168.1.100".to_string(),
            port: 8080,
            last_seen: now_unix(),
            is_leader: false,
            public_key: None,
            tls_enabled: false,
            properties: HashMap::new(),
        };

        assert_eq!(peer.api_url(), "http://192.168.1.100:8080");
    }

    #[test]
    fn test_peer_is_alive() {
        let peer = Peer {
            hub_id: "test-1".to_string(),
            name: "Test Hub".to_string(),
            address: "192.168.1.100".to_string(),
            port: 8080,
            last_seen: now_unix(),
            is_leader: false,
            public_key: None,
            tls_enabled: true,
            properties: HashMap::new(),
        };

        assert!(peer.is_alive(Duration::from_secs(60)));
    }
}

/*
 * 鏡
 * Find the others. Form the mesh.
 */
