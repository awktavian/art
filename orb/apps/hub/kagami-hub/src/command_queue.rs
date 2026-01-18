//! Command Queue with RocksDB Persistence
//!
//! Persists pending commands to survive crashes and restarts.
//! Provides durability guarantees for smart home operations.
//!
//! Features:
//! - WAL-based persistence via RocksDB
//! - Exponential backoff retry on replay
//! - Automatic cleanup after successful execution
//! - Command deduplication via request IDs
//!
//! Colony: Crystal (e7) - Clarity, verification
//!
//! h(x) >= 0. Always.

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::path::Path;
use std::sync::Arc;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tokio::sync::Mutex;
use tracing::{debug, error, info, warn};

// ============================================================================
// Configuration
// ============================================================================

/// Command queue configuration
#[derive(Debug, Clone)]
pub struct CommandQueueConfig {
    /// Path to RocksDB database directory
    pub db_path: String,
    /// Maximum number of retry attempts
    pub max_retries: u32,
    /// Initial retry delay in milliseconds
    pub initial_retry_delay_ms: u64,
    /// Maximum retry delay in milliseconds
    pub max_retry_delay_ms: u64,
    /// Retry delay multiplier
    pub retry_multiplier: f64,
    /// Command TTL in seconds (after which commands are discarded)
    pub command_ttl_secs: u64,
}

impl Default for CommandQueueConfig {
    fn default() -> Self {
        Self {
            db_path: "/var/lib/kagami-hub/command_queue".to_string(),
            max_retries: 10,
            initial_retry_delay_ms: 500,
            max_retry_delay_ms: 30000,
            retry_multiplier: 1.5,
            command_ttl_secs: 3600, // 1 hour
        }
    }
}

// ============================================================================
// Command Types
// ============================================================================

/// A queued command with metadata
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QueuedCommand {
    /// Unique command ID
    pub id: String,
    /// Command type (e.g., "lights", "shades", "lock")
    pub command_type: String,
    /// Command payload as JSON
    pub payload: serde_json::Value,
    /// Unix timestamp when command was queued
    pub queued_at: u64,
    /// Number of execution attempts
    pub attempts: u32,
    /// Last attempt timestamp (if any)
    pub last_attempt: Option<u64>,
    /// Error from last attempt (if any)
    pub last_error: Option<String>,
    /// Priority (higher = more important)
    pub priority: u8,
}

impl QueuedCommand {
    /// Create a new command
    pub fn new(command_type: &str, payload: serde_json::Value) -> Self {
        let timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();

        Self {
            id: generate_command_id(),
            command_type: command_type.to_string(),
            payload,
            queued_at: timestamp,
            attempts: 0,
            last_attempt: None,
            last_error: None,
            priority: 5, // Default priority
        }
    }

    /// Create with high priority (for safety-critical commands)
    pub fn new_high_priority(command_type: &str, payload: serde_json::Value) -> Self {
        let mut cmd = Self::new(command_type, payload);
        cmd.priority = 10;
        cmd
    }

    /// Check if command has expired
    pub fn is_expired(&self, ttl_secs: u64) -> bool {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();

        now - self.queued_at > ttl_secs
    }

    /// Calculate next retry delay with exponential backoff
    pub fn next_retry_delay(&self, config: &CommandQueueConfig) -> Duration {
        let base = config.initial_retry_delay_ms as f64;
        let delay = base * config.retry_multiplier.powi(self.attempts as i32);
        let capped = delay.min(config.max_retry_delay_ms as f64) as u64;
        Duration::from_millis(capped)
    }
}

/// Generate a unique command ID
fn generate_command_id() -> String {
    use std::sync::atomic::{AtomicU64, Ordering};
    static COUNTER: AtomicU64 = AtomicU64::new(0);

    let timestamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as u64;

    let counter = COUNTER.fetch_add(1, Ordering::Relaxed);
    format!("cmd-{}-{}", timestamp, counter)
}

// ============================================================================
// RocksDB Backend (Feature-gated)
// ============================================================================

/// Command queue with RocksDB persistence
pub struct CommandQueue {
    config: CommandQueueConfig,
    #[cfg(feature = "rocksdb")]
    db: rocksdb::DB,
    #[cfg(not(feature = "rocksdb"))]
    memory_store: Arc<Mutex<std::collections::HashMap<String, QueuedCommand>>>,
}

impl CommandQueue {
    /// Open or create the command queue database
    pub fn open(config: CommandQueueConfig) -> Result<Self> {
        #[cfg(feature = "rocksdb")]
        {
            // Ensure directory exists
            let db_path = Path::new(&config.db_path);
            if let Some(parent) = db_path.parent() {
                std::fs::create_dir_all(parent)
                    .context("Failed to create database directory")?;
            }

            // Open RocksDB with optimized options
            let mut opts = rocksdb::Options::default();
            opts.create_if_missing(true);
            opts.set_write_buffer_size(16 * 1024 * 1024); // 16MB
            opts.set_max_write_buffer_number(2);
            opts.set_compression_type(rocksdb::DBCompressionType::Lz4);

            let db = rocksdb::DB::open(&opts, &config.db_path)
                .context("Failed to open RocksDB")?;

            info!("Command queue opened at {}", config.db_path);

            Ok(Self { config, db })
        }

        #[cfg(not(feature = "rocksdb"))]
        {
            info!("Command queue using in-memory store (rocksdb feature disabled)");
            Ok(Self {
                config,
                memory_store: Arc::new(Mutex::new(std::collections::HashMap::new())),
            })
        }
    }

    /// Open with default config
    pub fn open_default() -> Result<Self> {
        Self::open(CommandQueueConfig::default())
    }

    /// Enqueue a command (logged before execution)
    pub async fn enqueue(&self, command: &QueuedCommand) -> Result<()> {
        let key = command.id.as_bytes();
        let value = serde_json::to_vec(command)?;

        #[cfg(feature = "rocksdb")]
        {
            self.db.put(key, value)?;
        }

        #[cfg(not(feature = "rocksdb"))]
        {
            let mut store = self.memory_store.lock().await;
            store.insert(command.id.clone(), command.clone());
        }

        debug!("Command queued: {} ({})", command.id, command.command_type);
        Ok(())
    }

    /// Dequeue a command (after successful execution)
    pub async fn dequeue(&self, command_id: &str) -> Result<()> {
        #[cfg(feature = "rocksdb")]
        {
            self.db.delete(command_id.as_bytes())?;
        }

        #[cfg(not(feature = "rocksdb"))]
        {
            let mut store = self.memory_store.lock().await;
            store.remove(command_id);
        }

        debug!("Command dequeued: {}", command_id);
        Ok(())
    }

    /// Update a command (after failed execution, increment attempts)
    pub async fn update(&self, command: &QueuedCommand) -> Result<()> {
        let key = command.id.as_bytes();
        let value = serde_json::to_vec(command)?;

        #[cfg(feature = "rocksdb")]
        {
            self.db.put(key, value)?;
        }

        #[cfg(not(feature = "rocksdb"))]
        {
            let mut store = self.memory_store.lock().await;
            store.insert(command.id.clone(), command.clone());
        }

        debug!("Command updated: {} (attempt {})", command.id, command.attempts);
        Ok(())
    }

    /// Get all pending commands (for replay on startup)
    pub async fn get_pending(&self) -> Result<Vec<QueuedCommand>> {
        let mut commands = Vec::new();

        #[cfg(feature = "rocksdb")]
        {
            let iter = self.db.iterator(rocksdb::IteratorMode::Start);
            for item in iter {
                let (_, value) = item?;
                if let Ok(cmd) = serde_json::from_slice::<QueuedCommand>(&value) {
                    // Skip expired commands
                    if !cmd.is_expired(self.config.command_ttl_secs) {
                        commands.push(cmd);
                    }
                }
            }
        }

        #[cfg(not(feature = "rocksdb"))]
        {
            let store = self.memory_store.lock().await;
            for cmd in store.values() {
                if !cmd.is_expired(self.config.command_ttl_secs) {
                    commands.push(cmd.clone());
                }
            }
        }

        // Sort by priority (descending) then by queued time (ascending)
        commands.sort_by(|a, b| {
            b.priority.cmp(&a.priority)
                .then(a.queued_at.cmp(&b.queued_at))
        });

        Ok(commands)
    }

    /// Get count of pending commands
    pub async fn pending_count(&self) -> usize {
        #[cfg(feature = "rocksdb")]
        {
            self.db.iterator(rocksdb::IteratorMode::Start).count()
        }

        #[cfg(not(feature = "rocksdb"))]
        {
            let store = self.memory_store.lock().await;
            store.len()
        }
    }

    /// Cleanup expired commands
    pub async fn cleanup_expired(&self) -> Result<usize> {
        let mut removed = 0;

        #[cfg(feature = "rocksdb")]
        {
            let mut to_remove = Vec::new();
            let iter = self.db.iterator(rocksdb::IteratorMode::Start);

            for item in iter {
                let (key, value) = item?;
                if let Ok(cmd) = serde_json::from_slice::<QueuedCommand>(&value) {
                    if cmd.is_expired(self.config.command_ttl_secs) {
                        to_remove.push(key.to_vec());
                    }
                }
            }

            for key in to_remove {
                self.db.delete(&key)?;
                removed += 1;
            }
        }

        #[cfg(not(feature = "rocksdb"))]
        {
            let mut store = self.memory_store.lock().await;
            let expired: Vec<_> = store.iter()
                .filter(|(_, cmd)| cmd.is_expired(self.config.command_ttl_secs))
                .map(|(id, _)| id.clone())
                .collect();

            for id in expired {
                store.remove(&id);
                removed += 1;
            }
        }

        if removed > 0 {
            info!("Cleaned up {} expired commands", removed);
        }

        Ok(removed)
    }

    /// Get configuration reference
    pub fn config(&self) -> &CommandQueueConfig {
        &self.config
    }
}

// ============================================================================
// Command Executor
// ============================================================================

/// Command executor with retry logic
pub struct CommandExecutor {
    queue: Arc<CommandQueue>,
}

impl CommandExecutor {
    /// Create a new executor
    pub fn new(queue: Arc<CommandQueue>) -> Self {
        Self { queue }
    }

    /// Execute a command with retry logic
    /// Returns Ok(()) if command succeeds, Err if max retries exceeded
    pub async fn execute<F, Fut>(&self, mut command: QueuedCommand, execute_fn: F) -> Result<()>
    where
        F: Fn(&QueuedCommand) -> Fut,
        Fut: std::future::Future<Output = Result<()>>,
    {
        let config = self.queue.config();

        // Enqueue before execution
        self.queue.enqueue(&command).await?;

        loop {
            command.attempts += 1;
            command.last_attempt = Some(
                SystemTime::now()
                    .duration_since(UNIX_EPOCH)
                    .unwrap_or_default()
                    .as_secs()
            );

            match execute_fn(&command).await {
                Ok(()) => {
                    // Success - remove from queue
                    self.queue.dequeue(&command.id).await?;
                    info!("Command {} executed successfully", command.id);
                    return Ok(());
                }
                Err(e) => {
                    command.last_error = Some(e.to_string());

                    if command.attempts >= config.max_retries {
                        // Max retries exceeded - remove from queue
                        error!(
                            "Command {} failed after {} attempts: {}",
                            command.id, command.attempts, e
                        );
                        self.queue.dequeue(&command.id).await?;
                        return Err(e);
                    }

                    // Update and retry
                    self.queue.update(&command).await?;
                    let delay = command.next_retry_delay(config);
                    warn!(
                        "Command {} failed (attempt {}), retrying in {:?}: {}",
                        command.id, command.attempts, delay, e
                    );
                    tokio::time::sleep(delay).await;
                }
            }
        }
    }

    /// Replay pending commands on startup
    pub async fn replay_pending<F, Fut>(&self, execute_fn: F) -> Result<usize>
    where
        F: Fn(&QueuedCommand) -> Fut + Clone,
        Fut: std::future::Future<Output = Result<()>>,
    {
        let pending = self.queue.get_pending().await?;
        let count = pending.len();

        if count == 0 {
            debug!("No pending commands to replay");
            return Ok(0);
        }

        info!("Replaying {} pending commands", count);

        for command in pending {
            let exec_fn = execute_fn.clone();
            let _ = self.execute(command, exec_fn).await;
        }

        Ok(count)
    }
}

// ============================================================================
// Module-Level API
// ============================================================================

use std::sync::OnceLock;

static QUEUE: OnceLock<Arc<CommandQueue>> = OnceLock::new();

/// Initialize the global command queue
pub fn init(config: CommandQueueConfig) -> Result<()> {
    let queue = CommandQueue::open(config)?;
    QUEUE.set(Arc::new(queue))
        .map_err(|_| anyhow::anyhow!("Command queue already initialized"))?;
    Ok(())
}

/// Initialize with default configuration
pub fn init_default() -> Result<()> {
    init(CommandQueueConfig::default())
}

/// Get the global queue instance
pub fn get_queue() -> Option<Arc<CommandQueue>> {
    QUEUE.get().cloned()
}

/// Enqueue a command globally
pub async fn enqueue(command: &QueuedCommand) -> Result<()> {
    let queue = get_queue().context("Command queue not initialized")?;
    queue.enqueue(command).await
}

/// Dequeue a command globally
pub async fn dequeue(command_id: &str) -> Result<()> {
    let queue = get_queue().context("Command queue not initialized")?;
    queue.dequeue(command_id).await
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_command_id_unique() {
        let id1 = generate_command_id();
        let id2 = generate_command_id();
        assert_ne!(id1, id2);
    }

    #[test]
    fn test_command_expiry() {
        let mut cmd = QueuedCommand::new("test", serde_json::json!({}));
        cmd.queued_at = 0; // Way in the past
        assert!(cmd.is_expired(3600));
    }

    #[test]
    fn test_retry_delay_exponential() {
        let config = CommandQueueConfig {
            initial_retry_delay_ms: 100,
            max_retry_delay_ms: 10000,
            retry_multiplier: 2.0,
            ..Default::default()
        };

        let mut cmd = QueuedCommand::new("test", serde_json::json!({}));

        cmd.attempts = 0;
        assert_eq!(cmd.next_retry_delay(&config).as_millis(), 100);

        cmd.attempts = 1;
        assert_eq!(cmd.next_retry_delay(&config).as_millis(), 200);

        cmd.attempts = 5;
        assert_eq!(cmd.next_retry_delay(&config).as_millis(), 3200);

        cmd.attempts = 10;
        // Should be capped at max
        assert_eq!(cmd.next_retry_delay(&config).as_millis(), 10000);
    }
}

/*
 * Crystal (e7) - Clarity, verification
 * Commands persist. Reliability matters.
 * h(x) >= 0. Always.
 */
