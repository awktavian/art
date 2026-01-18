//! OTA Firmware Updates with Secure Rollback
//!
//! Over-the-Air updates for Kagami Hubs with:
//! - SHA-256 verification
//! - Ed25519 signature validation
//! - Automatic rollback on boot failure
//! - A/B partition support (when available)
//! - Progress reporting to API
//!
//! Colony: Grove (e₆) → Learning and updating
//!
//! η → s → μ → a → η′
//! h(x) ≥ 0. Always.

use std::path::{Path, PathBuf};
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use anyhow::{Result, Context, anyhow};
use serde::{Deserialize, Serialize};
use sha2::{Sha256, Digest};
use tokio::io::AsyncWriteExt;
use tracing::{debug, info, warn, error};

#[cfg(feature = "mesh")]
use ed25519_dalek::{Signature, VerifyingKey, Verifier};

/// Current hub version
pub const CURRENT_VERSION: &str = env!("CARGO_PKG_VERSION");

/// Default update check URL
pub const DEFAULT_UPDATE_URL: &str = "https://awkronos.com/api/v1/hub/ota";

/// Default signing public key (Ed25519)
/// In production, embed the actual key
pub const SIGNING_PUBLIC_KEY: &str = "ed25519:kagami-hub-signing-key-placeholder";

// ============================================================================
// Update Information
// ============================================================================

/// Information about an available update
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UpdateInfo {
    /// Version string (semver)
    pub version: String,
    /// Release channel (stable, beta, canary)
    pub channel: String,
    /// Download URL for firmware
    pub download_url: String,
    /// SHA-256 checksum of the firmware
    pub sha256: String,
    /// Ed25519 signature of the checksum
    pub signature: String,
    /// Size in bytes
    pub size: u64,
    /// Release notes (markdown)
    pub release_notes: String,
    /// Whether this is a critical security update
    pub critical: bool,
    /// Minimum version required to update from
    pub min_version: Option<String>,
    /// Safe rollback target version
    pub rollback_version: Option<String>,
    /// Release timestamp
    pub released_at: u64,
}

/// OTA update status
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum UpdateStatus {
    /// Checking for updates
    Checking,
    /// No updates available
    UpToDate,
    /// Update available
    Available(UpdateInfo),
    /// Download in progress
    Downloading { progress_percent: f32, bytes_downloaded: u64 },
    /// Verifying download
    Verifying,
    /// Download complete, ready to apply
    ReadyToApply { path: PathBuf, version: String },
    /// Applying update
    Applying,
    /// Update applied, restart required
    PendingRestart,
    /// Update failed
    Failed { error: String, can_retry: bool },
    /// Rollback in progress
    RollingBack,
    /// Rollback completed
    RolledBack { to_version: String },
}

/// Update report sent to API
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UpdateReport {
    /// Hub ID
    pub hub_id: String,
    /// Previous version
    pub old_version: String,
    /// New version (or attempted)
    pub new_version: String,
    /// Whether update succeeded
    pub success: bool,
    /// Error message if failed
    pub error_message: Option<String>,
    /// Duration in seconds
    pub update_duration_seconds: Option<u64>,
    /// Whether rollback was performed
    pub rollback_performed: bool,
}

// ============================================================================
// Boot Health for Rollback
// ============================================================================

/// Boot health tracking for automatic rollback
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BootHealth {
    /// Version at last successful boot
    pub last_good_version: String,
    /// Current boot version
    pub current_version: String,
    /// Boot count since update
    pub boot_count: u32,
    /// Successful boot count (completed init)
    pub successful_boots: u32,
    /// Last boot timestamp
    pub last_boot: u64,
    /// Whether boot health check passed
    pub health_verified: bool,
}

impl BootHealth {
    /// Load boot health from disk
    pub fn load(path: &Path) -> Result<Self> {
        let contents = std::fs::read_to_string(path)?;
        Ok(serde_json::from_str(&contents)?)
    }

    /// Save boot health to disk
    pub fn save(&self, path: &Path) -> Result<()> {
        let contents = serde_json::to_string_pretty(self)?;
        std::fs::write(path, contents)?;
        Ok(())
    }

    /// Create initial boot health
    pub fn new(version: &str) -> Self {
        Self {
            last_good_version: version.to_string(),
            current_version: version.to_string(),
            boot_count: 0,
            successful_boots: 0,
            last_boot: current_timestamp(),
            health_verified: false,
        }
    }

    /// Record a boot attempt
    pub fn record_boot(&mut self) {
        self.boot_count += 1;
        self.last_boot = current_timestamp();
    }

    /// Mark boot as successful (health check passed)
    pub fn mark_healthy(&mut self) {
        self.successful_boots += 1;
        self.health_verified = true;
        self.last_good_version = self.current_version.clone();
    }

    /// Check if rollback should be triggered
    pub fn should_rollback(&self) -> bool {
        // Rollback if:
        // - Boot count > 3 and no successful boots
        // - Or health check failed after update
        if self.current_version == self.last_good_version {
            return false;
        }

        self.boot_count > 3 && self.successful_boots == 0
    }
}

// ============================================================================
// OTA Updater
// ============================================================================

/// OTA updater with security and rollback
pub struct OTAUpdater {
    /// Hub ID
    hub_id: String,
    /// Current version
    current_version: String,
    /// Release channel preference
    channel: String,
    /// Update check URL
    update_url: String,
    /// Directory for storing downloads
    download_dir: PathBuf,
    /// Directory for backups
    backup_dir: PathBuf,
    /// Boot health file path
    boot_health_path: PathBuf,
    /// HTTP client
    client: reqwest::Client,
    /// Current status
    status: UpdateStatus,
}

impl OTAUpdater {
    /// Create a new OTA updater
    pub fn new(
        hub_id: String,
        update_url: Option<&str>,
        data_dir: Option<&Path>,
    ) -> Self {
        let data_dir = data_dir
            .map(PathBuf::from)
            .unwrap_or_else(|| {
                let home = dirs::home_dir().unwrap_or_else(|| PathBuf::from("/tmp"));
                home.join(".kagami")
            });

        let download_dir = data_dir.join("updates");
        let backup_dir = data_dir.join("backups");
        let boot_health_path = data_dir.join("boot_health.json");

        // Ensure directories exist
        let _ = std::fs::create_dir_all(&download_dir);
        let _ = std::fs::create_dir_all(&backup_dir);

        Self {
            hub_id,
            current_version: CURRENT_VERSION.to_string(),
            channel: "stable".to_string(),
            update_url: update_url.unwrap_or(DEFAULT_UPDATE_URL).to_string(),
            download_dir,
            backup_dir,
            boot_health_path,
            client: reqwest::Client::builder()
                .timeout(Duration::from_secs(300)) // 5 min for large downloads
                .build()
                .expect("Failed to create HTTP client"),
            status: UpdateStatus::UpToDate,
        }
    }

    /// Set release channel
    pub fn with_channel(mut self, channel: &str) -> Self {
        self.channel = channel.to_string();
        self
    }

    /// Get current status
    pub fn status(&self) -> &UpdateStatus {
        &self.status
    }

    /// Check for available updates
    pub async fn check_for_updates(&mut self) -> Result<Option<UpdateInfo>> {
        self.status = UpdateStatus::Checking;

        info!(
            "🔍 Checking for updates (current: {}, channel: {})",
            self.current_version, self.channel
        );

        let check_request = serde_json::json!({
            "current_version": self.current_version,
            "hub_id": self.hub_id,
            "channel": self.channel,
            "hardware_revision": std::env::consts::ARCH,
        });

        let url = format!("{}/check", self.update_url);

        let response = match self.client
            .post(&url)
            .json(&check_request)
            .send()
            .await
        {
            Ok(r) => r,
            Err(e) => {
                warn!("Failed to check for updates: {}", e);
                self.status = UpdateStatus::UpToDate;
                return Ok(None);
            }
        };

        if !response.status().is_success() {
            debug!("Update server returned {}", response.status());
            self.status = UpdateStatus::UpToDate;
            return Ok(None);
        }

        let check_response: UpdateCheckResponse = response.json().await?;

        if check_response.update_available {
            if let Some(info) = check_response.firmware_info {
                if self.can_upgrade_to(&info) {
                    info!("✅ Update available: {} -> {}", self.current_version, info.version);
                    self.status = UpdateStatus::Available(info.clone());
                    return Ok(Some(info));
                }
            }
        }

        info!("Hub is up to date (version {})", self.current_version);
        self.status = UpdateStatus::UpToDate;
        Ok(None)
    }

    /// Check if we can upgrade to a specific version
    fn can_upgrade_to(&self, info: &UpdateInfo) -> bool {
        // Must be newer
        if !self.version_is_newer(&info.version) {
            return false;
        }

        // Check minimum version requirement
        if let Some(ref min) = info.min_version {
            if self.compare_versions(&self.current_version, min) < 0 {
                warn!(
                    "Cannot upgrade: current {} < minimum required {}",
                    self.current_version, min
                );
                return false;
            }
        }

        true
    }

    /// Download an update with progress reporting
    pub async fn download_update(&mut self, info: &UpdateInfo) -> Result<PathBuf> {
        info!("📥 Downloading update {} ({} bytes)", info.version, info.size);

        let filename = format!("kagami-hub-{}.bin", info.version);
        let download_path = self.download_dir.join(&filename);
        let temp_path = download_path.with_extension("part");

        // Check if already downloaded and verified
        if download_path.exists() {
            if self.verify_checksum(&download_path, &info.sha256)? {
                info!("Update already downloaded and verified");
                self.status = UpdateStatus::ReadyToApply {
                    path: download_path.clone(),
                    version: info.version.clone(),
                };
                return Ok(download_path);
            }
            // Checksum mismatch, re-download
            std::fs::remove_file(&download_path)?;
        }

        // Download with progress
        let response = self.client
            .get(&info.download_url)
            .header("X-Hub-ID", &self.hub_id)
            .send()
            .await?
            .error_for_status()?;

        let total_size = response.content_length().unwrap_or(info.size);

        let mut file = tokio::fs::File::create(&temp_path).await?;
        let mut downloaded: u64 = 0;
        let mut stream = response.bytes_stream();

        use tokio_stream::StreamExt;

        while let Some(chunk) = stream.next().await {
            let chunk = chunk?;
            file.write_all(&chunk).await?;
            downloaded += chunk.len() as u64;

            let progress = (downloaded as f32 / total_size as f32) * 100.0;
            self.status = UpdateStatus::Downloading {
                progress_percent: progress,
                bytes_downloaded: downloaded,
            };

            // Log progress every 10%
            if (progress as u32) % 10 == 0 {
                debug!("Download progress: {:.0}%", progress);
            }
        }

        file.flush().await?;
        drop(file);

        // Verify checksum
        self.status = UpdateStatus::Verifying;
        info!("🔐 Verifying download integrity...");

        if !self.verify_checksum(&temp_path, &info.sha256)? {
            tokio::fs::remove_file(&temp_path).await?;
            self.status = UpdateStatus::Failed {
                error: "Checksum verification failed".to_string(),
                can_retry: true,
            };
            return Err(anyhow::anyhow!("Checksum verification failed"));
        }

        // Verify signature (optional in development)
        if !info.signature.is_empty() {
            if !self.verify_signature(&info.sha256, &info.signature)? {
                tokio::fs::remove_file(&temp_path).await?;
                self.status = UpdateStatus::Failed {
                    error: "Signature verification failed".to_string(),
                    can_retry: false,
                };
                return Err(anyhow::anyhow!("Signature verification failed"));
            }
            info!("✅ Signature verified");
        }

        // Move to final location
        tokio::fs::rename(&temp_path, &download_path).await?;

        info!("✅ Download complete: {:?}", download_path);
        self.status = UpdateStatus::ReadyToApply {
            path: download_path.clone(),
            version: info.version.clone(),
        };

        Ok(download_path)
    }

    /// Apply a downloaded update
    pub async fn apply_update(&mut self, update_path: &Path, info: &UpdateInfo) -> Result<()> {
        self.status = UpdateStatus::Applying;
        let start_time = std::time::Instant::now();

        info!("🔄 Applying update from {:?}", update_path);

        // Get current executable path
        let current_exe = std::env::current_exe()
            .context("Failed to get current executable path")?;

        // Create backup
        let backup_filename = format!(
            "kagami-hub-{}-{}.backup",
            self.current_version,
            current_timestamp()
        );
        let backup_path = self.backup_dir.join(&backup_filename);

        std::fs::copy(&current_exe, &backup_path)
            .context("Failed to create backup")?;
        info!("📦 Created backup: {:?}", backup_path);

        // Update boot health
        let mut boot_health = BootHealth::load(&self.boot_health_path)
            .unwrap_or_else(|_| BootHealth::new(&self.current_version));
        boot_health.current_version = info.version.clone();
        boot_health.boot_count = 0;
        boot_health.successful_boots = 0;
        boot_health.health_verified = false;
        boot_health.save(&self.boot_health_path)?;

        // Replace binary
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;

            std::fs::copy(update_path, &current_exe)
                .context("Failed to copy new binary")?;

            let mut perms = std::fs::metadata(&current_exe)?.permissions();
            perms.set_mode(0o755);
            std::fs::set_permissions(&current_exe, perms)?;
        }

        #[cfg(not(unix))]
        {
            std::fs::copy(update_path, &current_exe)
                .context("Failed to copy new binary")?;
        }

        let duration = start_time.elapsed().as_secs();
        info!("✅ Update applied successfully (took {}s)", duration);

        // Report to API
        self.report_update(UpdateReport {
            hub_id: self.hub_id.clone(),
            old_version: self.current_version.clone(),
            new_version: info.version.clone(),
            success: true,
            error_message: None,
            update_duration_seconds: Some(duration),
            rollback_performed: false,
        }).await;

        self.status = UpdateStatus::PendingRestart;

        Ok(())
    }

    /// Rollback to previous version
    pub async fn rollback(&mut self) -> Result<String> {
        self.status = UpdateStatus::RollingBack;

        info!("⏪ Initiating rollback...");

        let current_exe = std::env::current_exe()?;

        // Find most recent backup
        let backups: Vec<_> = std::fs::read_dir(&self.backup_dir)?
            .filter_map(|e| e.ok())
            .filter(|e| e.path().extension().map(|ext| ext == "backup").unwrap_or(false))
            .collect();

        if backups.is_empty() {
            self.status = UpdateStatus::Failed {
                error: "No backup found for rollback".to_string(),
                can_retry: false,
            };
            return Err(anyhow::anyhow!("No backup found for rollback"));
        }

        // Get most recent backup (by filename timestamp)
        let mut backups: Vec<_> = backups.iter().map(|e| e.path()).collect();
        backups.sort();
        let backup_path = backups.last().unwrap();

        // Extract version from filename
        let filename = backup_path.file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("unknown");
        let rollback_version = filename
            .strip_prefix("kagami-hub-")
            .and_then(|s| s.split('-').next())
            .unwrap_or("unknown")
            .to_string();

        // Restore backup
        std::fs::copy(backup_path, &current_exe)
            .context("Failed to restore backup")?;

        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let mut perms = std::fs::metadata(&current_exe)?.permissions();
            perms.set_mode(0o755);
            std::fs::set_permissions(&current_exe, perms)?;
        }

        info!("✅ Rolled back to version {}", rollback_version);

        // Report rollback
        self.report_update(UpdateReport {
            hub_id: self.hub_id.clone(),
            old_version: self.current_version.clone(),
            new_version: rollback_version.clone(),
            success: false,
            error_message: Some("Rollback performed".to_string()),
            update_duration_seconds: None,
            rollback_performed: true,
        }).await;

        self.status = UpdateStatus::RolledBack {
            to_version: rollback_version.clone(),
        };

        Ok(rollback_version)
    }

    /// Check boot health and trigger rollback if needed
    pub async fn check_boot_health(&mut self) -> Result<bool> {
        let health_path = &self.boot_health_path;

        let mut boot_health = BootHealth::load(health_path)
            .unwrap_or_else(|_| BootHealth::new(&self.current_version));

        boot_health.record_boot();
        boot_health.save(health_path)?;

        if boot_health.should_rollback() {
            warn!("🚨 Boot health check failed, initiating rollback...");
            self.rollback().await?;
            return Ok(false);
        }

        Ok(true)
    }

    /// Mark current boot as healthy
    pub fn mark_boot_healthy(&self) -> Result<()> {
        let mut boot_health = BootHealth::load(&self.boot_health_path)
            .unwrap_or_else(|_| BootHealth::new(&self.current_version));

        boot_health.mark_healthy();
        boot_health.save(&self.boot_health_path)?;

        info!("✅ Boot marked healthy");
        Ok(())
    }

    /// Report update status to API
    async fn report_update(&self, report: UpdateReport) {
        let url = format!("{}/report", self.update_url);

        if let Err(e) = self.client
            .post(&url)
            .json(&report)
            .send()
            .await
        {
            warn!("Failed to report update status: {}", e);
        }
    }

    /// Verify SHA-256 checksum
    fn verify_checksum(&self, path: &Path, expected: &str) -> Result<bool> {
        let contents = std::fs::read(path)?;
        let mut hasher = Sha256::new();
        hasher.update(&contents);
        let result = hasher.finalize();
        let hash = format!("{:x}", result);

        Ok(hash == expected.to_lowercase())
    }

    /// Verify Ed25519 signature
    #[cfg(feature = "mesh")]
    fn verify_signature(&self, message: &str, signature: &str) -> Result<bool> {
        // Development mode - no verification if placeholder key
        if SIGNING_PUBLIC_KEY.contains("placeholder") {
            warn!("Signature verification skipped (development mode - no production key configured)");
            return Ok(true);
        }

        // Parse the public key (format: "ed25519:<hex_or_base64>")
        let key_str = SIGNING_PUBLIC_KEY
            .strip_prefix("ed25519:")
            .ok_or_else(|| anyhow!("Invalid public key format: must start with 'ed25519:'"))?;

        // Decode public key (try hex first, then base64)
        let key_bytes = hex::decode(key_str)
            .or_else(|_| base64::Engine::decode(&base64::engine::general_purpose::STANDARD, key_str))
            .map_err(|_| anyhow!("Failed to decode public key: not valid hex or base64"))?;

        if key_bytes.len() != 32 {
            return Err(anyhow!("Invalid public key length: expected 32 bytes, got {}", key_bytes.len()));
        }

        let public_key = VerifyingKey::from_bytes(
            key_bytes.as_slice().try_into().map_err(|_| anyhow!("Invalid key bytes"))?
        ).map_err(|e| anyhow!("Invalid Ed25519 public key: {}", e))?;

        // Decode signature (hex or base64)
        let sig_bytes = hex::decode(signature)
            .or_else(|_| base64::Engine::decode(&base64::engine::general_purpose::STANDARD, signature))
            .map_err(|_| anyhow!("Failed to decode signature: not valid hex or base64"))?;

        if sig_bytes.len() != 64 {
            return Err(anyhow!("Invalid signature length: expected 64 bytes, got {}", sig_bytes.len()));
        }

        let signature = Signature::from_bytes(
            sig_bytes.as_slice().try_into().map_err(|_| anyhow!("Invalid signature bytes"))?
        );

        // Verify
        match public_key.verify(message.as_bytes(), &signature) {
            Ok(()) => {
                info!("OTA signature verified successfully");
                Ok(true)
            }
            Err(e) => {
                error!("OTA signature verification failed: {}", e);
                Ok(false)
            }
        }
    }

    /// Verify Ed25519 signature (stub when mesh feature disabled)
    #[cfg(not(feature = "mesh"))]
    fn verify_signature(&self, _message: &str, _signature: &str) -> Result<bool> {
        // Without mesh feature, ed25519-dalek is not available
        // Reject all signatures in production, allow in development
        if SIGNING_PUBLIC_KEY.contains("placeholder") {
            warn!("Signature verification skipped (development mode - mesh feature disabled)");
            return Ok(true);
        }
        error!("OTA signature verification requires 'mesh' feature to be enabled");
        Ok(false)
    }

    /// Compare version strings (returns -1, 0, or 1)
    fn compare_versions(&self, a: &str, b: &str) -> i32 {
        let parse = |v: &str| -> Vec<u32> {
            v.split('-').next().unwrap_or(v)
                .split('.')
                .filter_map(|s| s.parse().ok())
                .collect()
        };

        let va = parse(a);
        let vb = parse(b);

        for (a, b) in va.iter().zip(vb.iter()) {
            if a > b { return 1; }
            if a < b { return -1; }
        }

        match va.len().cmp(&vb.len()) {
            std::cmp::Ordering::Greater => 1,
            std::cmp::Ordering::Less => -1,
            std::cmp::Ordering::Equal => 0,
        }
    }

    /// Check if a version string is newer than current
    fn version_is_newer(&self, version: &str) -> bool {
        self.compare_versions(version, &self.current_version) > 0
    }

    /// Get current version
    pub fn current_version(&self) -> &str {
        &self.current_version
    }

    /// Clean up old downloads and backups
    pub fn cleanup(&self, keep_backups: usize) -> Result<usize> {
        let mut count = 0;

        // Clean old downloads
        if let Ok(entries) = std::fs::read_dir(&self.download_dir) {
            for entry in entries.flatten() {
                let path = entry.path();
                if path.extension().map(|e| e == "bin" || e == "part").unwrap_or(false) {
                    if !path.to_string_lossy().contains(&self.current_version) {
                        std::fs::remove_file(&path)?;
                        count += 1;
                    }
                }
            }
        }

        // Keep only N most recent backups
        if let Ok(entries) = std::fs::read_dir(&self.backup_dir) {
            let mut backups: Vec<_> = entries
                .filter_map(|e| e.ok())
                .filter(|e| e.path().extension().map(|ext| ext == "backup").unwrap_or(false))
                .map(|e| e.path())
                .collect();

            backups.sort();
            backups.reverse();

            for backup in backups.into_iter().skip(keep_backups) {
                std::fs::remove_file(&backup)?;
                count += 1;
            }
        }

        if count > 0 {
            info!("🧹 Cleaned up {} old files", count);
        }

        Ok(count)
    }
}

// ============================================================================
// API Response Types
// ============================================================================

#[derive(Debug, Deserialize)]
struct UpdateCheckResponse {
    update_available: bool,
    firmware_info: Option<UpdateInfo>,
}

// ============================================================================
// Utility Functions
// ============================================================================

fn current_timestamp() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs()
}

// ============================================================================
// Auto Updater Service
// ============================================================================

/// Automatic update checker that runs periodically
pub struct AutoUpdater {
    updater: OTAUpdater,
    check_interval: Duration,
    auto_download: bool,
    auto_apply_critical: bool,
}

impl AutoUpdater {
    /// Create a new auto updater
    pub fn new(updater: OTAUpdater) -> Self {
        Self {
            updater,
            check_interval: Duration::from_secs(24 * 60 * 60), // Daily
            auto_download: true,
            auto_apply_critical: false,
        }
    }

    /// Set check interval
    pub fn with_interval(mut self, interval: Duration) -> Self {
        self.check_interval = interval;
        self
    }

    /// Enable auto-apply for critical updates only
    pub fn with_auto_apply_critical(mut self, enabled: bool) -> Self {
        self.auto_apply_critical = enabled;
        self
    }

    /// Start the auto-update loop
    pub async fn start(&mut self, mut shutdown: tokio::sync::watch::Receiver<bool>) {
        info!("🔄 Starting auto-updater (interval: {:?})", self.check_interval);

        // Check boot health on startup
        if let Err(e) = self.updater.check_boot_health().await {
            error!("Boot health check failed: {}", e);
        }

        let mut interval = tokio::time::interval(self.check_interval);

        loop {
            tokio::select! {
                _ = interval.tick() => {
                    if let Err(e) = self.check_and_handle().await {
                        warn!("Auto-update check failed: {}", e);
                    }
                }
                _ = shutdown.changed() => {
                    if *shutdown.borrow() {
                        info!("Auto-updater shutting down");
                        break;
                    }
                }
            }
        }
    }

    /// Check and optionally download/apply update
    async fn check_and_handle(&mut self) -> Result<()> {
        let Some(info) = self.updater.check_for_updates().await? else {
            return Ok(());
        };

        if self.auto_download {
            let path = self.updater.download_update(&info).await?;

            // Only auto-apply critical updates
            if self.auto_apply_critical && info.critical {
                info!("🚨 Applying critical security update automatically");
                self.updater.apply_update(&path, &info).await?;
            } else {
                info!("📦 Update downloaded and ready. Manual approval required.");
            }
        }

        Ok(())
    }
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_version_comparison() {
        let updater = OTAUpdater::new("test-hub".to_string(), None, None);

        assert_eq!(updater.compare_versions("1.0.0", "1.0.0"), 0);
        assert_eq!(updater.compare_versions("1.1.0", "1.0.0"), 1);
        assert_eq!(updater.compare_versions("1.0.0", "1.1.0"), -1);
        assert_eq!(updater.compare_versions("2.0.0", "1.9.9"), 1);
        assert_eq!(updater.compare_versions("1.0.1", "1.0.0"), 1);
    }

    #[test]
    fn test_version_is_newer() {
        let updater = OTAUpdater::new("test-hub".to_string(), None, None);

        // These depend on CURRENT_VERSION
        assert!(updater.version_is_newer("99.0.0"));
        assert!(!updater.version_is_newer("0.0.0"));
        assert!(!updater.version_is_newer(CURRENT_VERSION));
    }

    #[test]
    fn test_boot_health() {
        let mut health = BootHealth::new("1.0.0");

        // New install shouldn't rollback
        assert!(!health.should_rollback());

        // Simulate update
        health.current_version = "1.1.0".to_string();
        health.boot_count = 0;

        // First few boots shouldn't trigger rollback
        health.record_boot();
        health.record_boot();
        health.record_boot();
        assert!(!health.should_rollback());

        // After 4 boots with no success, should rollback
        health.record_boot();
        assert!(health.should_rollback());

        // If we mark healthy, shouldn't rollback
        health.mark_healthy();
        assert!(!health.should_rollback());
    }

    #[test]
    fn test_checksum_verification() {
        let updater = OTAUpdater::new("test-hub".to_string(), None, None);

        // Create temp file
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("test.bin");
        std::fs::write(&path, b"test content").unwrap();

        // SHA-256 of "test content"
        let expected = "6ae8a75555209fd6c44157c0aed8016e763ff435a19cf186f76863140143ff72";  // pragma: allowlist secret

        assert!(updater.verify_checksum(&path, expected).unwrap());
        assert!(!updater.verify_checksum(&path, "wrong").unwrap());
    }
}

/*
 * 鏡
 * Seeds update securely. The mesh evolves safely.
 * h(x) ≥ 0. Always.
 */
