//! SQLite State Persistence
//!
//! Persists hub state across restarts for offline resilience.
//! The hub can restore cached state and queued commands after power loss.
//!
//! Colony: Nexus (e₄) — State persistence bridge
//!
//! η → s → μ → a → η′
//! h(x) ≥ 0. Always.

use anyhow::{Context, Result};
use chrono::{DateTime, Utc};
use rusqlite::{params, Connection, OptionalExtension};
use serde::{Deserialize, Serialize};
use std::path::Path;
use std::sync::Arc;
use tokio::sync::Mutex;
use tracing::{debug, info, warn};

use crate::state_cache::{HomeState, TeslaState, WeatherState, ZoneLevel};

/// Database schema version for migrations
const SCHEMA_VERSION: i32 = 1;

/// SQL schema for state persistence
const SCHEMA: &str = r#"
-- State cache tables
CREATE TABLE IF NOT EXISTS tesla_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    data TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS home_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    data TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS weather_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    data TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Queued commands (for offline operation)
CREATE TABLE IF NOT EXISTS command_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    command_type TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    executed_at TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
);

CREATE INDEX IF NOT EXISTS idx_command_queue_status ON command_queue(status);

-- Zone history (for analytics)
CREATE TABLE IF NOT EXISTS zone_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zone TEXT NOT NULL,
    detected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    api_reachable INTEGER NOT NULL,
    internet_reachable INTEGER NOT NULL
);

-- Hub identity and mesh state
CREATE TABLE IF NOT EXISTS hub_identity (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    hub_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    genome_hash TEXT,
    last_boot TEXT
);

-- Peer discovery cache
CREATE TABLE IF NOT EXISTS known_peers (
    hub_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    address TEXT NOT NULL,
    port INTEGER NOT NULL,
    last_seen TEXT NOT NULL,
    is_leader INTEGER NOT NULL DEFAULT 0,
    public_key TEXT
);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"#;

/// Hub database for persistent storage
pub struct HubDatabase {
    conn: Arc<Mutex<Connection>>,
}

impl HubDatabase {
    /// Open or create database at the given path
    pub fn new(path: impl AsRef<Path>) -> Result<Self> {
        let path = path.as_ref();

        // Ensure parent directory exists
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)?;
        }

        let conn = Connection::open(path)
            .with_context(|| format!("Failed to open database: {}", path.display()))?;

        // Enable WAL mode for better concurrency
        conn.pragma_update(None, "journal_mode", "WAL")?;

        // Apply schema
        conn.execute_batch(SCHEMA)?;

        // Check/apply migrations
        let db = Self {
            conn: Arc::new(Mutex::new(conn)),
        };

        info!("✓ Database opened: {}", path.display());

        Ok(db)
    }

    /// Create an in-memory database (for testing)
    pub fn in_memory() -> Result<Self> {
        let conn = Connection::open_in_memory()?;
        conn.execute_batch(SCHEMA)?;

        Ok(Self {
            conn: Arc::new(Mutex::new(conn)),
        })
    }

    // ========================================================================
    // Tesla State
    // ========================================================================

    /// Save Tesla state to database
    ///
    /// PERFORMANCE FIX (Jan 2026): Uses spawn_blocking to avoid blocking the async runtime
    /// with synchronous SQLite operations.
    pub async fn save_tesla_state(&self, state: &TeslaState, fetched_at: DateTime<Utc>) -> Result<()> {
        let data = serde_json::to_string(state)?;
        let fetched_str = fetched_at.to_rfc3339();
        let battery_level = state.battery_level;
        let conn = self.conn.clone();

        tokio::task::spawn_blocking(move || {
            let conn = conn.blocking_lock();
            conn.execute(
                "INSERT OR REPLACE INTO tesla_state (id, data, fetched_at) VALUES (1, ?1, ?2)",
                params![data, fetched_str],
            )?;
            debug!("Saved Tesla state (battery: {}%)", battery_level);
            Ok(())
        })
        .await?
    }

    /// Load Tesla state from database
    ///
    /// PERFORMANCE FIX (Jan 2026): Uses spawn_blocking for SQLite operations.
    pub async fn load_tesla_state(&self) -> Result<Option<(TeslaState, DateTime<Utc>)>> {
        let conn = self.conn.clone();

        tokio::task::spawn_blocking(move || {
            let conn = conn.blocking_lock();

            let result: Option<(String, String)> = conn.query_row(
                "SELECT data, fetched_at FROM tesla_state WHERE id = 1",
                [],
                |row| Ok((row.get(0)?, row.get(1)?)),
            ).optional()?;

            if let Some((data, fetched_str)) = result {
                let state: TeslaState = serde_json::from_str(&data)?;
                let fetched_at = DateTime::parse_from_rfc3339(&fetched_str)?.with_timezone(&Utc);
                Ok(Some((state, fetched_at)))
            } else {
                Ok(None)
            }
        })
        .await?
    }

    // ========================================================================
    // Home State
    // ========================================================================

    /// Save Home state to database
    ///
    /// PERFORMANCE FIX (Jan 2026): Uses spawn_blocking for SQLite operations.
    pub async fn save_home_state(&self, state: &HomeState, fetched_at: DateTime<Utc>) -> Result<()> {
        let data = serde_json::to_string(state)?;
        let fetched_str = fetched_at.to_rfc3339();
        let conn = self.conn.clone();

        tokio::task::spawn_blocking(move || {
            let conn = conn.blocking_lock();
            conn.execute(
                "INSERT OR REPLACE INTO home_state (id, data, fetched_at) VALUES (1, ?1, ?2)",
                params![data, fetched_str],
            )?;
            debug!("Saved Home state");
            Ok(())
        })
        .await?
    }

    /// Load Home state from database
    ///
    /// PERFORMANCE FIX (Jan 2026): Uses spawn_blocking for SQLite operations.
    pub async fn load_home_state(&self) -> Result<Option<(HomeState, DateTime<Utc>)>> {
        let conn = self.conn.clone();

        tokio::task::spawn_blocking(move || {
            let conn = conn.blocking_lock();

            let result: Option<(String, String)> = conn.query_row(
                "SELECT data, fetched_at FROM home_state WHERE id = 1",
                [],
                |row| Ok((row.get(0)?, row.get(1)?)),
            ).optional()?;

            if let Some((data, fetched_str)) = result {
                let state: HomeState = serde_json::from_str(&data)?;
                let fetched_at = DateTime::parse_from_rfc3339(&fetched_str)?.with_timezone(&Utc);
                Ok(Some((state, fetched_at)))
            } else {
                Ok(None)
            }
        })
        .await?
    }

    // ========================================================================
    // Weather State
    // ========================================================================

    /// Save Weather state to database
    ///
    /// PERFORMANCE FIX (Jan 2026): Uses spawn_blocking for SQLite operations.
    pub async fn save_weather_state(&self, state: &WeatherState, fetched_at: DateTime<Utc>) -> Result<()> {
        let data = serde_json::to_string(state)?;
        let fetched_str = fetched_at.to_rfc3339();
        let conn = self.conn.clone();

        tokio::task::spawn_blocking(move || {
            let conn = conn.blocking_lock();
            conn.execute(
                "INSERT OR REPLACE INTO weather_state (id, data, fetched_at) VALUES (1, ?1, ?2)",
                params![data, fetched_str],
            )?;
            debug!("Saved Weather state");
            Ok(())
        })
        .await?
    }

    /// Load Weather state from database
    ///
    /// PERFORMANCE FIX (Jan 2026): Uses spawn_blocking for SQLite operations.
    pub async fn load_weather_state(&self) -> Result<Option<(WeatherState, DateTime<Utc>)>> {
        let conn = self.conn.clone();

        tokio::task::spawn_blocking(move || {
            let conn = conn.blocking_lock();

            let result: Option<(String, String)> = conn.query_row(
                "SELECT data, fetched_at FROM weather_state WHERE id = 1",
                [],
                |row| Ok((row.get(0)?, row.get(1)?)),
            ).optional()?;

            if let Some((data, fetched_str)) = result {
                let state: WeatherState = serde_json::from_str(&data)?;
                let fetched_at = DateTime::parse_from_rfc3339(&fetched_str)?.with_timezone(&Utc);
                Ok(Some((state, fetched_at)))
            } else {
                Ok(None)
            }
        })
        .await?
    }

    // ========================================================================
    // Command Queue
    // ========================================================================

    /// Queue a command for later execution
    ///
    /// PERFORMANCE FIX (Jan 2026): Uses spawn_blocking for SQLite operations.
    pub async fn queue_command(&self, command_type: &str, payload: &str) -> Result<i64> {
        let conn = self.conn.clone();
        let command_type = command_type.to_string();
        let payload = payload.to_string();

        tokio::task::spawn_blocking(move || {
            let conn = conn.blocking_lock();
            conn.execute(
                "INSERT INTO command_queue (command_type, payload) VALUES (?1, ?2)",
                params![command_type, payload],
            )?;
            let id = conn.last_insert_rowid();
            info!("Queued command {} (type: {})", id, command_type);
            Ok(id)
        })
        .await?
    }

    /// Get pending commands
    ///
    /// PERFORMANCE FIX (Jan 2026): Uses spawn_blocking for SQLite operations.
    pub async fn get_pending_commands(&self) -> Result<Vec<QueuedCmd>> {
        let conn = self.conn.clone();

        tokio::task::spawn_blocking(move || {
            let conn = conn.blocking_lock();
            let mut stmt = conn.prepare(
                "SELECT id, command_type, payload, created_at FROM command_queue
                 WHERE status = 'pending' ORDER BY created_at ASC"
            )?;

            let commands = stmt.query_map([], |row| {
                Ok(QueuedCmd {
                    id: row.get(0)?,
                    command_type: row.get(1)?,
                    payload: row.get(2)?,
                    created_at: row.get(3)?,
                })
            })?
            .collect::<std::result::Result<Vec<_>, _>>()?;

            Ok(commands)
        })
        .await?
    }

    /// Mark command as executed
    ///
    /// PERFORMANCE FIX (Jan 2026): Uses spawn_blocking for SQLite operations.
    pub async fn mark_command_executed(&self, id: i64) -> Result<()> {
        let conn = self.conn.clone();
        let now = Utc::now().to_rfc3339();

        tokio::task::spawn_blocking(move || {
            let conn = conn.blocking_lock();
            conn.execute(
                "UPDATE command_queue SET status = 'executed', executed_at = ?1 WHERE id = ?2",
                params![now, id],
            )?;
            debug!("Marked command {} as executed", id);
            Ok(())
        })
        .await?
    }

    /// Mark command as failed
    ///
    /// PERFORMANCE FIX (Jan 2026): Uses spawn_blocking for SQLite operations.
    pub async fn mark_command_failed(&self, id: i64, error: &str) -> Result<()> {
        let conn = self.conn.clone();
        let error = error.to_string();

        tokio::task::spawn_blocking(move || {
            let conn = conn.blocking_lock();
            conn.execute(
                "UPDATE command_queue SET status = 'failed',
                 payload = payload || ' ERROR: ' || ?1 WHERE id = ?2",
                params![error, id],
            )?;
            warn!("Marked command {} as failed: {}", id, error);
            Ok(())
        })
        .await?
    }

    /// Clear old executed commands (cleanup)
    ///
    /// PERFORMANCE FIX (Jan 2026): Uses spawn_blocking for SQLite operations.
    pub async fn cleanup_old_commands(&self, days: i32) -> Result<usize> {
        let conn = self.conn.clone();

        tokio::task::spawn_blocking(move || {
            let conn = conn.blocking_lock();
            let deleted = conn.execute(
                "DELETE FROM command_queue
                 WHERE status IN ('executed', 'failed')
                 AND created_at < datetime('now', ?1)",
                params![format!("-{} days", days)],
            )?;

            if deleted > 0 {
                info!("Cleaned up {} old commands", deleted);
            }
            Ok(deleted)
        })
        .await?
    }

    // ========================================================================
    // Zone History
    // ========================================================================

    /// Record zone detection
    ///
    /// PERFORMANCE FIX (Jan 2026): Uses spawn_blocking for SQLite operations.
    pub async fn record_zone(&self, zone: ZoneLevel, api_reachable: bool, internet_reachable: bool) -> Result<()> {
        let conn = self.conn.clone();
        let zone_str = format!("{:?}", zone);

        tokio::task::spawn_blocking(move || {
            let conn = conn.blocking_lock();
            conn.execute(
                "INSERT INTO zone_history (zone, api_reachable, internet_reachable) VALUES (?1, ?2, ?3)",
                params![zone_str, api_reachable as i32, internet_reachable as i32],
            )?;
            debug!("Recorded zone: {}", zone_str);
            Ok(())
        })
        .await?
    }

    /// Get recent zone history
    ///
    /// PERFORMANCE FIX (Jan 2026): Uses spawn_blocking for SQLite operations.
    pub async fn get_zone_history(&self, limit: usize) -> Result<Vec<ZoneRecord>> {
        let conn = self.conn.clone();

        tokio::task::spawn_blocking(move || {
            let conn = conn.blocking_lock();
            let mut stmt = conn.prepare(
                "SELECT zone, detected_at, api_reachable, internet_reachable
                 FROM zone_history ORDER BY detected_at DESC LIMIT ?1"
            )?;

            let records = stmt.query_map(params![limit as i64], |row| {
                Ok(ZoneRecord {
                    zone: row.get(0)?,
                    detected_at: row.get(1)?,
                    api_reachable: row.get::<_, i32>(2)? != 0,
                    internet_reachable: row.get::<_, i32>(3)? != 0,
                })
            })?
            .collect::<std::result::Result<Vec<_>, _>>()?;

            Ok(records)
        })
        .await?
    }

    // ========================================================================
    // Hub Identity
    // ========================================================================

    /// Get or create hub identity
    ///
    /// PERFORMANCE FIX (Jan 2026): Uses spawn_blocking for SQLite operations.
    pub async fn get_or_create_hub_id(&self) -> Result<String> {
        let conn = self.conn.clone();

        tokio::task::spawn_blocking(move || {
            let conn = conn.blocking_lock();

            // Try to get existing
            let existing: Option<String> = conn.query_row(
                "SELECT hub_id FROM hub_identity WHERE id = 1",
                [],
                |row| row.get(0),
            ).optional()?;

            if let Some(hub_id) = existing {
                return Ok(hub_id);
            }

            // Generate new hub ID
            #[cfg(feature = "uuid")]
            let hub_id = uuid::Uuid::new_v4().to_string();

            #[cfg(not(feature = "uuid"))]
            let hub_id = {
                use std::time::{SystemTime, UNIX_EPOCH};
                let ts = SystemTime::now()
                    .duration_since(UNIX_EPOCH)
                    .unwrap()
                    .as_nanos();
                format!("hub-{:016x}", ts as u64)
            };

            conn.execute(
                "INSERT INTO hub_identity (id, hub_id) VALUES (1, ?1)",
                params![hub_id],
            )?;

            info!("Created hub identity: {}", hub_id);
            Ok(hub_id)
        })
        .await?
    }

    /// Update last boot time
    ///
    /// PERFORMANCE FIX (Jan 2026): Uses spawn_blocking for SQLite operations.
    pub async fn record_boot(&self) -> Result<()> {
        let conn = self.conn.clone();
        let now = Utc::now().to_rfc3339();

        tokio::task::spawn_blocking(move || {
            let conn = conn.blocking_lock();
            conn.execute(
                "UPDATE hub_identity SET last_boot = ?1 WHERE id = 1",
                params![now],
            )?;
            Ok(())
        })
        .await?
    }

    // ========================================================================
    // Peer Management
    // ========================================================================

    /// Record a discovered peer
    ///
    /// PERFORMANCE FIX (Jan 2026): Uses spawn_blocking for SQLite operations.
    pub async fn save_peer(&self, peer: &PeerInfo) -> Result<()> {
        let conn = self.conn.clone();
        let now = Utc::now().to_rfc3339();
        let peer = peer.clone();

        tokio::task::spawn_blocking(move || {
            let conn = conn.blocking_lock();
            conn.execute(
                "INSERT OR REPLACE INTO known_peers
                 (hub_id, name, address, port, last_seen, is_leader, public_key)
                 VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)",
                params![
                    peer.hub_id,
                    peer.name,
                    peer.address,
                    peer.port,
                    now,
                    peer.is_leader as i32,
                    peer.public_key,
                ],
            )?;
            debug!("Saved peer: {} at {}:{}", peer.name, peer.address, peer.port);
            Ok(())
        })
        .await?
    }

    /// Get all known peers
    ///
    /// PERFORMANCE FIX (Jan 2026): Uses spawn_blocking for SQLite operations.
    pub async fn get_peers(&self) -> Result<Vec<PeerInfo>> {
        let conn = self.conn.clone();

        tokio::task::spawn_blocking(move || {
            let conn = conn.blocking_lock();
            let mut stmt = conn.prepare(
                "SELECT hub_id, name, address, port, last_seen, is_leader, public_key
                 FROM known_peers ORDER BY last_seen DESC"
            )?;

            let peers = stmt.query_map([], |row| {
                Ok(PeerInfo {
                    hub_id: row.get(0)?,
                    name: row.get(1)?,
                    address: row.get(2)?,
                    port: row.get(3)?,
                    last_seen: row.get(4)?,
                    is_leader: row.get::<_, i32>(5)? != 0,
                    public_key: row.get(6)?,
                })
            })?
            .collect::<std::result::Result<Vec<_>, _>>()?;

            Ok(peers)
        })
        .await?
    }

    /// Remove stale peers (not seen recently)
    ///
    /// PERFORMANCE FIX (Jan 2026): Uses spawn_blocking for SQLite operations.
    pub async fn cleanup_stale_peers(&self, hours: i32) -> Result<usize> {
        let conn = self.conn.clone();

        tokio::task::spawn_blocking(move || {
            let conn = conn.blocking_lock();
            let deleted = conn.execute(
                "DELETE FROM known_peers WHERE last_seen < datetime('now', ?1)",
                params![format!("-{} hours", hours)],
            )?;

            if deleted > 0 {
                info!("Removed {} stale peers", deleted);
            }
            Ok(deleted)
        })
        .await?
    }

    // ========================================================================
    // Diagnostics
    // ========================================================================

    /// Get database statistics
    ///
    /// PERFORMANCE FIX (Jan 2026): Uses spawn_blocking for SQLite operations.
    pub async fn get_stats(&self) -> Result<DbStats> {
        let conn = self.conn.clone();

        tokio::task::spawn_blocking(move || {
            let conn = conn.blocking_lock();

            let pending_commands: i64 = conn.query_row(
                "SELECT COUNT(*) FROM command_queue WHERE status = 'pending'",
                [],
                |row| row.get(0),
            )?;

            let total_commands: i64 = conn.query_row(
                "SELECT COUNT(*) FROM command_queue",
                [],
                |row| row.get(0),
            )?;

            let peer_count: i64 = conn.query_row(
                "SELECT COUNT(*) FROM known_peers",
                [],
                |row| row.get(0),
            )?;

            let has_tesla: bool = conn.query_row(
                "SELECT COUNT(*) FROM tesla_state WHERE id = 1",
                [],
                |row| Ok(row.get::<_, i64>(0)? > 0),
            )?;

            let has_home: bool = conn.query_row(
                "SELECT COUNT(*) FROM home_state WHERE id = 1",
                [],
                |row| Ok(row.get::<_, i64>(0)? > 0),
            )?;

            Ok(DbStats {
                pending_commands: pending_commands as usize,
                total_commands: total_commands as usize,
                peer_count: peer_count as usize,
                has_tesla_state: has_tesla,
                has_home_state: has_home,
            })
        })
        .await?
    }
}

// ============================================================================
// Supporting Types
// ============================================================================

/// Queued command from database
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QueuedCmd {
    pub id: i64,
    pub command_type: String,
    pub payload: String,
    pub created_at: String,
}

/// Zone history record
#[derive(Debug, Clone)]
pub struct ZoneRecord {
    pub zone: String,
    pub detected_at: String,
    pub api_reachable: bool,
    pub internet_reachable: bool,
}

/// Peer information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PeerInfo {
    pub hub_id: String,
    pub name: String,
    pub address: String,
    pub port: i32,
    pub last_seen: String,
    pub is_leader: bool,
    pub public_key: Option<String>,
}

/// Database statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DbStats {
    pub pending_commands: usize,
    pub total_commands: usize,
    pub peer_count: usize,
    pub has_tesla_state: bool,
    pub has_home_state: bool,
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_create_database() {
        let db = HubDatabase::in_memory().unwrap();
        let stats = db.get_stats().await.unwrap();
        assert_eq!(stats.pending_commands, 0);
    }

    #[tokio::test]
    async fn test_queue_command() {
        let db = HubDatabase::in_memory().unwrap();

        let id = db.queue_command("tesla_climate", r#"{"on": true}"#).await.unwrap();
        assert!(id > 0);

        let pending = db.get_pending_commands().await.unwrap();
        assert_eq!(pending.len(), 1);
        assert_eq!(pending[0].command_type, "tesla_climate");
    }

    #[tokio::test]
    async fn test_hub_identity() {
        let db = HubDatabase::in_memory().unwrap();

        let id1 = db.get_or_create_hub_id().await.unwrap();
        let id2 = db.get_or_create_hub_id().await.unwrap();

        assert_eq!(id1, id2); // Should return same ID
        assert!(!id1.is_empty());
    }

    #[tokio::test]
    async fn test_tesla_state_roundtrip() {
        let db = HubDatabase::in_memory().unwrap();

        let state = TeslaState {
            battery_level: 75,
            battery_range: 250.0,
            charging: false,
            locked: true,
            climate_on: false,
            climate_temp: 70.0,
            inside_temp: 68.0,
            outside_temp: 55.0,
            frunk_open: false,
            trunk_open: false,
            ..Default::default()
        };

        let fetched_at = Utc::now();
        db.save_tesla_state(&state, fetched_at).await.unwrap();

        let (loaded, _) = db.load_tesla_state().await.unwrap().unwrap();
        assert_eq!(loaded.battery_level, 75);
        assert_eq!(loaded.battery_range, 250.0);
    }

    #[tokio::test]
    async fn test_peer_management() {
        let db = HubDatabase::in_memory().unwrap();

        let peer = PeerInfo {
            hub_id: "test-hub-1".to_string(),
            name: "Kitchen Hub".to_string(),
            address: "192.168.1.100".to_string(),
            port: 8080,
            last_seen: Utc::now().to_rfc3339(),
            is_leader: false,
            public_key: None,
        };

        db.save_peer(&peer).await.unwrap();

        let peers = db.get_peers().await.unwrap();
        assert_eq!(peers.len(), 1);
        assert_eq!(peers[0].name, "Kitchen Hub");
    }
}

/*
 * 鏡
 * State persists. Memory endures.
 */
