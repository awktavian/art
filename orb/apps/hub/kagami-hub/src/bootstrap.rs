//! Bootstrap Protocol — Hub Identity Initialization
//!
//! When a new hub starts up, it needs to decide:
//! - Is this the first seed (generate new identity)?
//! - Is there an existing mesh (request genome from peer)?
//!
//! The bootstrap protocol handles both cases, implementing
//! the "chain letter" propagation model.
//!
//! Colony: Beacon (e₅) — Initialization and planning
//!
//! η → s → μ → a → η′
//! h(x) ≥ 0. Always.

use std::path::Path;
use std::time::Duration;
use anyhow::Result;
use tracing::{info, warn};

use crate::genome::KagamiGenome;

#[cfg(feature = "mdns")]
use crate::mesh::discovery::SERVICE_TYPE;

/// Bootstrap mode for hub initialization
#[derive(Debug, Clone)]
pub enum BootstrapMode {
    /// First seed - no peers found, generate new identity
    FirstSeed,
    /// Join mesh - peers found, request genome
    JoinMesh { peer_url: String },
    /// Restored - loaded from local storage
    Restored,
}

/// Bootstrap result
#[derive(Debug)]
pub struct BootstrapResult {
    /// Mode that was used
    pub mode: BootstrapMode,
    /// The genome (new or received)
    pub genome: KagamiGenome,
    /// Hub ID assigned
    pub hub_id: String,
}

/// Run the bootstrap protocol
pub async fn bootstrap(
    genome_path: &Path,
    wake_word: &str,
    api_url: Option<&str>,
    timeout: Duration,
) -> Result<BootstrapResult> {
    info!("Starting bootstrap protocol...");

    // 1. Check for existing genome
    if genome_path.exists() {
        match KagamiGenome::load(genome_path) {
            Ok(genome) => {
                info!("Restored genome from {:?}", genome_path);
                let hub_id = generate_hub_id(&genome);
                return Ok(BootstrapResult {
                    mode: BootstrapMode::Restored,
                    genome,
                    hub_id,
                });
            }
            Err(e) => {
                warn!("Failed to load existing genome: {}. Starting fresh.", e);
            }
        }
    }

    // 2. Scan for existing hubs
    let peers = discover_peers(timeout).await;

    if peers.is_empty() {
        // 3a. First seed mode - generate new identity
        info!("No peers found. Bootstrapping as first seed.");

        let genome = KagamiGenome::genesis(wake_word, api_url);
        genome.save(genome_path)?;

        let hub_id = generate_hub_id(&genome);

        return Ok(BootstrapResult {
            mode: BootstrapMode::FirstSeed,
            genome,
            hub_id,
        });
    }

    // 3b. Join mesh mode - request genome from peer
    info!("Found {} peer(s). Requesting genome.", peers.len());

    for peer_url in &peers {
        match request_genome_from_peer(peer_url).await {
            Ok(genome) => {
                // Verify genome signature
                // In production, verify against a trusted root key

                // Save locally
                genome.save(genome_path)?;

                let hub_id = generate_hub_id(&genome);

                return Ok(BootstrapResult {
                    mode: BootstrapMode::JoinMesh { peer_url: peer_url.clone() },
                    genome,
                    hub_id,
                });
            }
            Err(e) => {
                warn!("Failed to get genome from {}: {}", peer_url, e);
                continue;
            }
        }
    }

    // 4. Fallback - couldn't join mesh, become new seed
    warn!("Failed to join existing mesh. Bootstrapping as independent seed.");

    let genome = KagamiGenome::genesis(wake_word, api_url);
    genome.save(genome_path)?;

    let hub_id = generate_hub_id(&genome);

    Ok(BootstrapResult {
        mode: BootstrapMode::FirstSeed,
        genome,
        hub_id,
    })
}

/// Discover peers via mDNS
#[cfg(feature = "mdns")]
async fn discover_peers(timeout: Duration) -> Vec<String> {
    use mdns_sd::{ServiceDaemon, ServiceEvent};

    let mut peers = Vec::new();

    let Ok(mdns) = ServiceDaemon::new() else {
        warn!("Failed to create mDNS daemon for peer discovery");
        return peers;
    };

    let Ok(browse_handle) = mdns.browse(SERVICE_TYPE) else {
        warn!("Failed to start mDNS browse");
        return peers;
    };

    let deadline = std::time::Instant::now() + timeout;

    while std::time::Instant::now() < deadline {
        match tokio::time::timeout(
            Duration::from_millis(100),
            async { browse_handle.recv_async().await }
        ).await {
            Ok(Ok(ServiceEvent::ServiceResolved(info))) => {
                if let Some(addr) = info.get_addresses().iter().next() {
                    // Check if TLS is enabled (default to true for security)
                    let tls_enabled = info.get_property_val_str("tls")
                        .map(|v| v == "1" || v.to_lowercase() == "true")
                        .unwrap_or(true);
                    let scheme = if tls_enabled { "https" } else { "http" };
                    let url = format!("{}://{}:{}", scheme, addr, info.get_port());
                    info!("Discovered peer: {} (TLS: {})", url, tls_enabled);
                    peers.push(url);
                }
            }
            _ => continue,
        }
    }

    peers
}

#[cfg(not(feature = "mdns"))]
async fn discover_peers(_timeout: Duration) -> Vec<String> {
    warn!("mDNS disabled, cannot discover peers automatically");
    Vec::new()
}

/// Request genome from a peer hub
async fn request_genome_from_peer(peer_url: &str) -> Result<KagamiGenome> {
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(10))
        .build()?;

    let url = format!("{}/api/genome", peer_url);

    let response = client.get(&url).send().await?;

    if !response.status().is_success() {
        return Err(anyhow::anyhow!(
            "Peer returned status {}",
            response.status()
        ));
    }

    let genome: KagamiGenome = response.json().await?;

    info!("Received genome from {} (generation {})", peer_url, genome.generation);

    Ok(genome)
}

/// Generate hub ID from genome
fn generate_hub_id(genome: &KagamiGenome) -> String {
    // Use first 8 bytes of identity hash as hub ID
    let hash_prefix: String = genome.identity_hash[..4]
        .iter()
        .map(|b| format!("{:02x}", b))
        .collect();

    format!("hub-{}", hash_prefix)
}

/// Quick check if bootstrap is needed
pub fn needs_bootstrap(genome_path: &Path) -> bool {
    !genome_path.exists()
}

/// Get default genome path
#[cfg(feature = "genome")]
pub fn default_genome_path() -> std::path::PathBuf {
    let data_dir = dirs::data_dir()
        .unwrap_or_else(|| std::path::PathBuf::from("."));

    data_dir.join("kagami").join("genome.bin")
}

#[cfg(not(feature = "genome"))]
pub fn default_genome_path() -> std::path::PathBuf {
    std::path::PathBuf::from("./kagami/genome.bin")
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    #[tokio::test]
    async fn test_first_seed_bootstrap() {
        let temp_dir = TempDir::new().unwrap();
        let genome_path = temp_dir.path().join("genome.bin");

        let result = bootstrap(
            &genome_path,
            "Hey Kagami",
            Some("http://localhost:8000"),
            Duration::from_millis(100), // Short timeout for test
        ).await.unwrap();

        assert!(matches!(result.mode, BootstrapMode::FirstSeed));
        assert!(!result.hub_id.is_empty());
        assert!(genome_path.exists());
    }

    #[tokio::test]
    async fn test_restore_bootstrap() {
        let temp_dir = TempDir::new().unwrap();
        let genome_path = temp_dir.path().join("genome.bin");

        // Create initial genome
        let genome = KagamiGenome::genesis("Hey Kagami", None);
        genome.save(&genome_path).unwrap();

        // Bootstrap should restore
        let result = bootstrap(
            &genome_path,
            "Hey Kagami",
            None,
            Duration::from_millis(100),
        ).await.unwrap();

        assert!(matches!(result.mode, BootstrapMode::Restored));
    }
}

/*
 * 鏡
 * Seeds scatter. Identity propagates.
 */
