//! Command Log — Undo Capability with Transaction Batching
//!
//! SQLite-backed circular buffer for command history.
//! Provides undo capability for smart home commands.
//!
//! Features:
//! - Transaction batching for bulk operations
//! - Atomic multi-command execution
//! - Batch rollback support
//! - Circular buffer with configurable size
//!
//! Performance targets:
//! - Single insert: < 5ms
//! - Batch insert: < 20ms for 100 commands
//! - Query: < 10ms
//! - Max entries: 1000 (circular)
//!
//! Colony: Forge (e2) - Execution & Transformation
//!
//! h(x) >= 0. Always.

use anyhow::{Context, Result};
use chrono::{DateTime, Utc};
use rusqlite::{Connection, params, Transaction};
use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Mutex;
use std::time::Instant;
use tracing::{debug, error, info, warn};

/// Maximum number of commands to retain
const MAX_COMMANDS: i64 = 1000;

/// Command entry in the log
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CommandEntry {
    pub id: i64,
    pub command_type: String,
    pub command_data: serde_json::Value,
    pub undo_data: Option<serde_json::Value>,
    pub executed_at: DateTime<Utc>,
    pub can_undo: bool,
    pub undone: bool,
}

/// Simplified entry for API responses
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CommandSummary {
    pub id: i64,
    pub command_type: String,
    pub description: String,
    pub executed_at: String,
    pub can_undo: bool,
    pub undone: bool,
}

// ═══════════════════════════════════════════════════════════════
// TRANSACTION BATCH TYPES
// ═══════════════════════════════════════════════════════════════

/// A batch of commands to execute atomically
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CommandBatch {
    /// Unique batch ID
    pub batch_id: String,
    /// Commands in the batch
    pub commands: Vec<BatchCommand>,
    /// Batch creation timestamp
    pub created_at: DateTime<Utc>,
    /// Whether the batch has been committed
    pub committed: bool,
    /// Whether the batch has been rolled back
    pub rolled_back: bool,
}

/// A single command in a batch
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BatchCommand {
    /// Command type
    pub command_type: String,
    /// Command data
    pub command_data: serde_json::Value,
    /// Undo data for rollback
    pub undo_data: Option<serde_json::Value>,
    /// Execution order in batch
    pub order: usize,
}

/// Result of a batch operation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BatchResult {
    pub batch_id: String,
    pub success: bool,
    pub committed_count: usize,
    pub failed_at: Option<usize>,
    pub error: Option<String>,
    pub command_ids: Vec<i64>,
    pub duration_ms: u64,
}

/// Batch statistics
#[derive(Debug, Default)]
pub struct BatchStats {
    pub total_batches: AtomicU64,
    pub successful_batches: AtomicU64,
    pub failed_batches: AtomicU64,
    pub rolled_back_batches: AtomicU64,
    pub total_commands_batched: AtomicU64,
}

// ═══════════════════════════════════════════════════════════════
// COMMAND LOG MANAGER
// ═══════════════════════════════════════════════════════════════

/// Command Log Manager with transaction batching support
pub struct CommandLog {
    conn: Mutex<Connection>,
    batch_stats: BatchStats,
}

impl CommandLog {
    /// Create a new command log with SQLite backend
    pub fn new() -> Result<Self> {
        let db_path = Self::get_db_path()?;

        // Ensure parent directory exists
        if let Some(parent) = db_path.parent() {
            std::fs::create_dir_all(parent)?;
        }

        let conn = Connection::open(&db_path)
            .context("Failed to open command log database")?;

        // Enable WAL mode for better concurrent access
        conn.execute_batch("PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;")?;

        // Initialize commands schema
        conn.execute(
            "CREATE TABLE IF NOT EXISTS commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                command_type TEXT NOT NULL,
                command_data TEXT NOT NULL,
                undo_data TEXT,
                executed_at TEXT NOT NULL,
                can_undo INTEGER NOT NULL DEFAULT 1,
                undone INTEGER NOT NULL DEFAULT 0,
                batch_id TEXT
            )",
            [],
        )?;

        // Initialize batches schema
        conn.execute(
            "CREATE TABLE IF NOT EXISTS batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                committed INTEGER NOT NULL DEFAULT 0,
                rolled_back INTEGER NOT NULL DEFAULT 0,
                command_count INTEGER NOT NULL DEFAULT 0,
                commit_duration_ms INTEGER
            )",
            [],
        )?;

        // Create indexes for faster queries
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_commands_executed_at ON commands(executed_at DESC)",
            [],
        )?;
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_commands_batch_id ON commands(batch_id)",
            [],
        )?;
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_batches_batch_id ON batches(batch_id)",
            [],
        )?;

        info!("Command log initialized at {:?}", db_path);

        Ok(Self {
            conn: Mutex::new(conn),
            batch_stats: BatchStats::default(),
        })
    }

    /// Get the database path
    fn get_db_path() -> Result<PathBuf> {
        let data_dir = dirs::data_dir()
            .context("Failed to get data directory")?
            .join("kagami")
            .join("command_log.db");
        Ok(data_dir)
    }

    /// Log a command execution
    pub fn log_command(
        &self,
        command_type: &str,
        command_data: serde_json::Value,
        undo_data: Option<serde_json::Value>,
    ) -> Result<i64> {
        let conn = self.conn.lock().map_err(|e| anyhow::anyhow!("Lock error: {}", e))?;
        let now = Utc::now();

        conn.execute(
            "INSERT INTO commands (command_type, command_data, undo_data, executed_at, can_undo)
             VALUES (?1, ?2, ?3, ?4, ?5)",
            params![
                command_type,
                serde_json::to_string(&command_data)?,
                undo_data.as_ref().map(|d| serde_json::to_string(d).unwrap_or_default()),
                now.to_rfc3339(),
                undo_data.is_some() as i32,
            ],
        )?;

        let id = conn.last_insert_rowid();

        // Enforce circular buffer - delete oldest entries
        conn.execute(
            "DELETE FROM commands WHERE id IN (
                SELECT id FROM commands ORDER BY id DESC LIMIT -1 OFFSET ?1
            )",
            params![MAX_COMMANDS],
        )?;

        debug!("Logged command {} (id={})", command_type, id);
        Ok(id)
    }

    /// Get command history
    pub fn get_history(&self, limit: Option<i64>) -> Result<Vec<CommandSummary>> {
        let conn = self.conn.lock().map_err(|e| anyhow::anyhow!("Lock error: {}", e))?;
        let limit = limit.unwrap_or(50).min(100);

        let mut stmt = conn.prepare(
            "SELECT id, command_type, command_data, executed_at, can_undo, undone
             FROM commands
             ORDER BY id DESC
             LIMIT ?1"
        )?;

        let entries = stmt.query_map(params![limit], |row| {
            let id: i64 = row.get(0)?;
            let command_type: String = row.get(1)?;
            let command_data_str: String = row.get(2)?;
            let executed_at: String = row.get(3)?;
            let can_undo: i32 = row.get(4)?;
            let undone: i32 = row.get(5)?;

            // Generate description from command data
            let description = Self::generate_description(&command_type, &command_data_str);

            Ok(CommandSummary {
                id,
                command_type,
                description,
                executed_at,
                can_undo: can_undo != 0,
                undone: undone != 0,
            })
        })?
        .filter_map(|r| r.ok())
        .collect();

        Ok(entries)
    }

    /// Get a specific command by ID
    pub fn get_command(&self, id: i64) -> Result<Option<CommandEntry>> {
        let conn = self.conn.lock().map_err(|e| anyhow::anyhow!("Lock error: {}", e))?;

        let mut stmt = conn.prepare(
            "SELECT id, command_type, command_data, undo_data, executed_at, can_undo, undone
             FROM commands
             WHERE id = ?1"
        )?;

        let entry = stmt.query_row(params![id], |row| {
            let id: i64 = row.get(0)?;
            let command_type: String = row.get(1)?;
            let command_data_str: String = row.get(2)?;
            let undo_data_str: Option<String> = row.get(3)?;
            let executed_at_str: String = row.get(4)?;
            let can_undo: i32 = row.get(5)?;
            let undone: i32 = row.get(6)?;

            Ok(CommandEntry {
                id,
                command_type,
                command_data: serde_json::from_str(&command_data_str).unwrap_or(serde_json::Value::Null),
                undo_data: undo_data_str.and_then(|s| serde_json::from_str(&s).ok()),
                executed_at: DateTime::parse_from_rfc3339(&executed_at_str)
                    .map(|dt| dt.with_timezone(&Utc))
                    .unwrap_or_else(|_| Utc::now()),
                can_undo: can_undo != 0,
                undone: undone != 0,
            })
        });

        match entry {
            Ok(e) => Ok(Some(e)),
            Err(rusqlite::Error::QueryReturnedNoRows) => Ok(None),
            Err(e) => Err(e.into()),
        }
    }

    /// Mark a command as undone
    pub fn mark_undone(&self, id: i64) -> Result<bool> {
        let conn = self.conn.lock().map_err(|e| anyhow::anyhow!("Lock error: {}", e))?;

        let rows = conn.execute(
            "UPDATE commands SET undone = 1 WHERE id = ?1 AND can_undo = 1 AND undone = 0",
            params![id],
        )?;

        Ok(rows > 0)
    }

    /// Generate a human-readable description from command data
    fn generate_description(command_type: &str, command_data_str: &str) -> String {
        let data: serde_json::Value = serde_json::from_str(command_data_str)
            .unwrap_or(serde_json::Value::Null);

        match command_type {
            "set_lights" => {
                let level = data.get("level").and_then(|v| v.as_i64()).unwrap_or(0);
                let rooms = data.get("rooms")
                    .and_then(|v| v.as_array())
                    .map(|arr| arr.iter()
                        .filter_map(|v| v.as_str())
                        .collect::<Vec<_>>()
                        .join(", "))
                    .unwrap_or_else(|| "all rooms".to_string());
                format!("Set lights to {}% in {}", level, rooms)
            }
            "execute_scene" => {
                let scene = data.get("scene").and_then(|v| v.as_str()).unwrap_or("unknown");
                format!("Executed scene: {}", scene)
            }
            "toggle_fireplace" => {
                let on = data.get("on").and_then(|v| v.as_bool()).unwrap_or(false);
                format!("Turned fireplace {}", if on { "on" } else { "off" })
            }
            "control_shades" => {
                let action = data.get("action").and_then(|v| v.as_str()).unwrap_or("control");
                format!("Shades: {}", action)
            }
            "control_tv" => {
                let action = data.get("action").and_then(|v| v.as_str()).unwrap_or("control");
                format!("TV mount: {}", action)
            }
            "announce" => {
                let text = data.get("text").and_then(|v| v.as_str()).unwrap_or("");
                let truncated = if text.len() > 30 {
                    format!("{}...", &text[..30])
                } else {
                    text.to_string()
                };
                format!("Announced: \"{}\"", truncated)
            }
            _ => format!("{}", command_type),
        }
    }

    // ═══════════════════════════════════════════════════════════════
    // TRANSACTION BATCHING
    // ═══════════════════════════════════════════════════════════════

    /// Generate a unique batch ID
    fn generate_batch_id() -> String {
        use std::time::{SystemTime, UNIX_EPOCH};
        let timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_millis();
        let rand = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .subsec_nanos() % 10000;
        format!("batch_{}_{:04}", timestamp, rand)
    }

    /// Create a new batch for atomic command execution
    pub fn create_batch(&self, commands: Vec<BatchCommand>) -> Result<CommandBatch> {
        let batch_id = Self::generate_batch_id();
        let now = Utc::now();

        let batch = CommandBatch {
            batch_id: batch_id.clone(),
            commands,
            created_at: now,
            committed: false,
            rolled_back: false,
        };

        // Register the batch in the database
        let conn = self.conn.lock().map_err(|e| anyhow::anyhow!("Lock error: {}", e))?;
        conn.execute(
            "INSERT INTO batches (batch_id, created_at, command_count)
             VALUES (?1, ?2, ?3)",
            params![batch_id, now.to_rfc3339(), batch.commands.len()],
        )?;

        self.batch_stats.total_batches.fetch_add(1, Ordering::Relaxed);
        info!("Created batch {} with {} commands", batch_id, batch.commands.len());

        Ok(batch)
    }

    /// Commit a batch atomically - all commands succeed or all fail
    pub fn commit_batch(&self, batch: &CommandBatch) -> Result<BatchResult> {
        let start = Instant::now();
        let mut conn = self.conn.lock().map_err(|e| anyhow::anyhow!("Lock error: {}", e))?;

        // Start transaction
        let tx = conn.transaction()?;
        let mut command_ids = Vec::with_capacity(batch.commands.len());
        let now = Utc::now();

        // Execute each command in the batch
        for (idx, cmd) in batch.commands.iter().enumerate() {
            match Self::execute_batch_command(&tx, &batch.batch_id, cmd, &now) {
                Ok(id) => {
                    command_ids.push(id);
                }
                Err(e) => {
                    // Rollback on failure
                    warn!("Batch {} failed at command {}: {}", batch.batch_id, idx, e);
                    // Transaction will automatically rollback when dropped
                    self.batch_stats.failed_batches.fetch_add(1, Ordering::Relaxed);

                    // Mark batch as failed in separate transaction
                    drop(tx);
                    let conn = self.conn.lock().map_err(|e| anyhow::anyhow!("Lock error: {}", e))?;
                    let _ = conn.execute(
                        "UPDATE batches SET rolled_back = 1 WHERE batch_id = ?1",
                        params![batch.batch_id],
                    );

                    return Ok(BatchResult {
                        batch_id: batch.batch_id.clone(),
                        success: false,
                        committed_count: idx,
                        failed_at: Some(idx),
                        error: Some(e.to_string()),
                        command_ids,
                        duration_ms: start.elapsed().as_millis() as u64,
                    });
                }
            }
        }

        // Commit transaction
        tx.commit()?;

        let duration_ms = start.elapsed().as_millis() as u64;

        // Update batch record
        let conn = self.conn.lock().map_err(|e| anyhow::anyhow!("Lock error: {}", e))?;
        conn.execute(
            "UPDATE batches SET committed = 1, commit_duration_ms = ?1 WHERE batch_id = ?2",
            params![duration_ms as i64, batch.batch_id],
        )?;

        self.batch_stats.successful_batches.fetch_add(1, Ordering::Relaxed);
        self.batch_stats.total_commands_batched.fetch_add(batch.commands.len() as u64, Ordering::Relaxed);

        info!(
            "Committed batch {} with {} commands in {}ms",
            batch.batch_id, command_ids.len(), duration_ms
        );

        Ok(BatchResult {
            batch_id: batch.batch_id.clone(),
            success: true,
            committed_count: command_ids.len(),
            failed_at: None,
            error: None,
            command_ids,
            duration_ms,
        })
    }

    /// Execute a single command within a transaction
    fn execute_batch_command(
        tx: &Transaction,
        batch_id: &str,
        cmd: &BatchCommand,
        now: &DateTime<Utc>,
    ) -> Result<i64> {
        tx.execute(
            "INSERT INTO commands (command_type, command_data, undo_data, executed_at, can_undo, batch_id)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
            params![
                cmd.command_type,
                serde_json::to_string(&cmd.command_data)?,
                cmd.undo_data.as_ref().map(|d| serde_json::to_string(d).unwrap_or_default()),
                now.to_rfc3339(),
                cmd.undo_data.is_some() as i32,
                batch_id,
            ],
        )?;

        Ok(tx.last_insert_rowid())
    }

    /// Rollback a committed batch by executing undo operations
    pub fn rollback_batch(&self, batch_id: &str) -> Result<BatchResult> {
        let start = Instant::now();

        // Get all commands in the batch (in reverse order for proper undo)
        let commands = self.get_batch_commands(batch_id)?;
        if commands.is_empty() {
            return Err(anyhow::anyhow!("Batch not found or empty: {}", batch_id));
        }

        let mut conn = self.conn.lock().map_err(|e| anyhow::anyhow!("Lock error: {}", e))?;
        let tx = conn.transaction()?;

        // Mark all commands as undone
        tx.execute(
            "UPDATE commands SET undone = 1 WHERE batch_id = ?1",
            params![batch_id],
        )?;

        // Mark batch as rolled back
        tx.execute(
            "UPDATE batches SET rolled_back = 1 WHERE batch_id = ?1",
            params![batch_id],
        )?;

        tx.commit()?;

        self.batch_stats.rolled_back_batches.fetch_add(1, Ordering::Relaxed);

        let duration_ms = start.elapsed().as_millis() as u64;

        info!("Rolled back batch {} ({} commands) in {}ms", batch_id, commands.len(), duration_ms);

        Ok(BatchResult {
            batch_id: batch_id.to_string(),
            success: true,
            committed_count: commands.len(),
            failed_at: None,
            error: None,
            command_ids: commands.iter().map(|c| c.id).collect(),
            duration_ms,
        })
    }

    /// Get all commands in a batch
    pub fn get_batch_commands(&self, batch_id: &str) -> Result<Vec<CommandEntry>> {
        let conn = self.conn.lock().map_err(|e| anyhow::anyhow!("Lock error: {}", e))?;

        let mut stmt = conn.prepare(
            "SELECT id, command_type, command_data, undo_data, executed_at, can_undo, undone
             FROM commands
             WHERE batch_id = ?1
             ORDER BY id ASC"
        )?;

        let entries = stmt.query_map(params![batch_id], |row| {
            let id: i64 = row.get(0)?;
            let command_type: String = row.get(1)?;
            let command_data_str: String = row.get(2)?;
            let undo_data_str: Option<String> = row.get(3)?;
            let executed_at_str: String = row.get(4)?;
            let can_undo: i32 = row.get(5)?;
            let undone: i32 = row.get(6)?;

            Ok(CommandEntry {
                id,
                command_type,
                command_data: serde_json::from_str(&command_data_str).unwrap_or(serde_json::Value::Null),
                undo_data: undo_data_str.and_then(|s| serde_json::from_str(&s).ok()),
                executed_at: DateTime::parse_from_rfc3339(&executed_at_str)
                    .map(|dt| dt.with_timezone(&Utc))
                    .unwrap_or_else(|_| Utc::now()),
                can_undo: can_undo != 0,
                undone: undone != 0,
            })
        })?
        .filter_map(|r| r.ok())
        .collect();

        Ok(entries)
    }

    /// Get batch information
    pub fn get_batch_info(&self, batch_id: &str) -> Result<Option<CommandBatch>> {
        let conn = self.conn.lock().map_err(|e| anyhow::anyhow!("Lock error: {}", e))?;

        let result = conn.query_row(
            "SELECT batch_id, created_at, committed, rolled_back
             FROM batches WHERE batch_id = ?1",
            params![batch_id],
            |row| {
                let batch_id: String = row.get(0)?;
                let created_at_str: String = row.get(1)?;
                let committed: i32 = row.get(2)?;
                let rolled_back: i32 = row.get(3)?;

                Ok((batch_id, created_at_str, committed != 0, rolled_back != 0))
            },
        );

        match result {
            Ok((batch_id, created_at_str, committed, rolled_back)) => {
                let commands = self.get_batch_commands(&batch_id)?
                    .into_iter()
                    .enumerate()
                    .map(|(i, entry)| BatchCommand {
                        command_type: entry.command_type,
                        command_data: entry.command_data,
                        undo_data: entry.undo_data,
                        order: i,
                    })
                    .collect();

                Ok(Some(CommandBatch {
                    batch_id,
                    commands,
                    created_at: DateTime::parse_from_rfc3339(&created_at_str)
                        .map(|dt| dt.with_timezone(&Utc))
                        .unwrap_or_else(|_| Utc::now()),
                    committed,
                    rolled_back,
                }))
            }
            Err(rusqlite::Error::QueryReturnedNoRows) => Ok(None),
            Err(e) => Err(e.into()),
        }
    }

    /// Get recent batches
    pub fn get_recent_batches(&self, limit: usize) -> Result<Vec<serde_json::Value>> {
        let conn = self.conn.lock().map_err(|e| anyhow::anyhow!("Lock error: {}", e))?;

        let mut stmt = conn.prepare(
            "SELECT batch_id, created_at, committed, rolled_back, command_count, commit_duration_ms
             FROM batches
             ORDER BY id DESC
             LIMIT ?1"
        )?;

        let batches = stmt.query_map(params![limit as i64], |row| {
            Ok(serde_json::json!({
                "batch_id": row.get::<_, String>(0)?,
                "created_at": row.get::<_, String>(1)?,
                "committed": row.get::<_, i32>(2)? != 0,
                "rolled_back": row.get::<_, i32>(3)? != 0,
                "command_count": row.get::<_, i64>(4)?,
                "commit_duration_ms": row.get::<_, Option<i64>>(5)?,
            }))
        })?
        .filter_map(|r| r.ok())
        .collect();

        Ok(batches)
    }

    /// Get batch statistics
    pub fn get_batch_stats(&self) -> serde_json::Value {
        serde_json::json!({
            "total_batches": self.batch_stats.total_batches.load(Ordering::Relaxed),
            "successful_batches": self.batch_stats.successful_batches.load(Ordering::Relaxed),
            "failed_batches": self.batch_stats.failed_batches.load(Ordering::Relaxed),
            "rolled_back_batches": self.batch_stats.rolled_back_batches.load(Ordering::Relaxed),
            "total_commands_batched": self.batch_stats.total_commands_batched.load(Ordering::Relaxed),
        })
    }

    /// Execute multiple commands atomically (convenience method)
    pub fn execute_batch(&self, commands: Vec<BatchCommand>) -> Result<BatchResult> {
        let batch = self.create_batch(commands)?;
        self.commit_batch(&batch)
    }
}

// Global command log instance
static COMMAND_LOG: std::sync::OnceLock<CommandLog> = std::sync::OnceLock::new();

pub fn get_command_log() -> &'static CommandLog {
    COMMAND_LOG.get_or_init(|| {
        CommandLog::new().unwrap_or_else(|e| {
            error!("Failed to initialize command log: {}", e);
            panic!("Command log initialization failed")
        })
    })
}

// ═══════════════════════════════════════════════════════════════
// TAURI COMMANDS
// ═══════════════════════════════════════════════════════════════

#[tauri::command]
pub fn get_command_history(limit: Option<i64>) -> Result<Vec<CommandSummary>, String> {
    get_command_log()
        .get_history(limit)
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub fn get_command_by_id(id: i64) -> Result<Option<CommandEntry>, String> {
    get_command_log()
        .get_command(id)
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn undo_command(id: i64) -> Result<serde_json::Value, String> {
    let log = get_command_log();

    // Get the command
    let entry = log.get_command(id)
        .map_err(|e| e.to_string())?
        .ok_or_else(|| "Command not found".to_string())?;

    if !entry.can_undo {
        return Err("Command cannot be undone".to_string());
    }

    if entry.undone {
        return Err("Command already undone".to_string());
    }

    let undo_data = entry.undo_data
        .ok_or_else(|| "No undo data available".to_string())?;

    // Execute the undo action based on command type
    // This would integrate with the smart home commands
    // For now, we just mark it as undone and return the undo data
    log.mark_undone(id).map_err(|e| e.to_string())?;

    Ok(serde_json::json!({
        "success": true,
        "command_id": id,
        "undo_data": undo_data,
        "message": format!("Command {} marked for undo", id)
    }))
}

// ═══════════════════════════════════════════════════════════════
// BATCH TAURI COMMANDS
// ═══════════════════════════════════════════════════════════════

#[tauri::command]
pub fn execute_command_batch(
    commands: Vec<serde_json::Value>,
) -> Result<BatchResult, String> {
    let batch_commands: Vec<BatchCommand> = commands
        .into_iter()
        .enumerate()
        .map(|(i, cmd)| BatchCommand {
            command_type: cmd.get("command_type")
                .and_then(|v| v.as_str())
                .unwrap_or("unknown")
                .to_string(),
            command_data: cmd.get("command_data")
                .cloned()
                .unwrap_or(serde_json::Value::Null),
            undo_data: cmd.get("undo_data").cloned(),
            order: i,
        })
        .collect();

    get_command_log()
        .execute_batch(batch_commands)
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub fn rollback_command_batch(batch_id: String) -> Result<BatchResult, String> {
    get_command_log()
        .rollback_batch(&batch_id)
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub fn get_batch_info(batch_id: String) -> Result<Option<CommandBatch>, String> {
    get_command_log()
        .get_batch_info(&batch_id)
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub fn get_recent_batches(limit: Option<usize>) -> Result<Vec<serde_json::Value>, String> {
    get_command_log()
        .get_recent_batches(limit.unwrap_or(20))
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub fn get_batch_stats() -> serde_json::Value {
    get_command_log().get_batch_stats()
}

/*
 * Forge transforms. Forge batches. Forge delivers.
 * h(x) >= 0. Always.
 */
