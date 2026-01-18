//! Session State Machine — Robust Connection Management
//!
//! Implements a formal state machine for session lifecycle:
//! - Disconnected -> Connecting -> Connected -> Reconnecting -> Error
//! - Automatic recovery with exponential backoff
//! - Cross-restart persistence via SQLite
//!
//! Colony: Nexus (e4) - Integration & Coordination
//!
//! State transitions:
//! ```
//! Disconnected --(connect)--> Connecting
//! Connecting --(success)--> Connected
//! Connecting --(failure)--> Error --(retry)--> Connecting
//! Connected --(disconnect)--> Disconnected
//! Connected --(network_error)--> Reconnecting
//! Reconnecting --(success)--> Connected
//! Reconnecting --(max_retries)--> Error
//! Error --(reset)--> Disconnected
//! ```
//!
//! h(x) >= 0. Always.

use anyhow::{Context, Result};
use chrono::{DateTime, Utc};
use rusqlite::{Connection, params};
use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use std::sync::atomic::{AtomicU32, Ordering};
use std::sync::Mutex;
use std::time::{Duration, Instant};
use tracing::{debug, error, info, warn};

// ═══════════════════════════════════════════════════════════════
// SESSION STATES
// ═══════════════════════════════════════════════════════════════

/// Session connection state
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SessionState {
    /// Not connected, ready to connect
    Disconnected,
    /// Attempting initial connection
    Connecting,
    /// Successfully connected
    Connected,
    /// Connection lost, attempting reconnection
    Reconnecting,
    /// Error state, requires manual intervention or reset
    Error,
}

impl Default for SessionState {
    fn default() -> Self {
        Self::Disconnected
    }
}

impl std::fmt::Display for SessionState {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Disconnected => write!(f, "disconnected"),
            Self::Connecting => write!(f, "connecting"),
            Self::Connected => write!(f, "connected"),
            Self::Reconnecting => write!(f, "reconnecting"),
            Self::Error => write!(f, "error"),
        }
    }
}

// ═══════════════════════════════════════════════════════════════
// SESSION EVENTS
// ═══════════════════════════════════════════════════════════════

/// Events that trigger state transitions
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SessionEvent {
    /// User or system initiates connection
    Connect,
    /// Connection attempt succeeded
    ConnectionSuccess,
    /// Connection attempt failed
    ConnectionFailure { reason: String },
    /// User or system requests disconnection
    Disconnect,
    /// Network error during active connection
    NetworkError { reason: String },
    /// Retry timer fired
    RetryTick,
    /// Max retries exceeded
    MaxRetriesExceeded,
    /// Manual reset from error state
    Reset,
}

// ═══════════════════════════════════════════════════════════════
// SESSION INFO
// ═══════════════════════════════════════════════════════════════

/// Complete session information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionInfo {
    /// Unique session identifier
    pub session_id: String,
    /// Current state
    pub state: SessionState,
    /// Server URL
    pub server_url: String,
    /// Time session started
    pub started_at: Option<DateTime<Utc>>,
    /// Time of last successful connection
    pub last_connected_at: Option<DateTime<Utc>>,
    /// Time of last state change
    pub state_changed_at: DateTime<Utc>,
    /// Number of reconnection attempts
    pub reconnect_attempts: u32,
    /// Last error message if in error state
    pub last_error: Option<String>,
    /// Connection uptime in seconds (when connected)
    pub uptime_seconds: Option<u64>,
}

impl Default for SessionInfo {
    fn default() -> Self {
        Self {
            session_id: generate_session_id(),
            state: SessionState::Disconnected,
            server_url: String::new(),
            started_at: None,
            last_connected_at: None,
            state_changed_at: Utc::now(),
            reconnect_attempts: 0,
            last_error: None,
            uptime_seconds: None,
        }
    }
}

// ═══════════════════════════════════════════════════════════════
// BACKOFF CONFIGURATION
// ═══════════════════════════════════════════════════════════════

/// Exponential backoff configuration
#[derive(Debug, Clone)]
pub struct BackoffConfig {
    /// Initial delay in milliseconds
    pub initial_delay_ms: u64,
    /// Maximum delay in milliseconds
    pub max_delay_ms: u64,
    /// Multiplier for each retry
    pub multiplier: f64,
    /// Maximum number of retries before giving up
    pub max_retries: u32,
    /// Jitter factor (0.0-1.0)
    pub jitter: f64,
}

impl Default for BackoffConfig {
    fn default() -> Self {
        Self {
            initial_delay_ms: 1000,
            max_delay_ms: 30_000,
            multiplier: 2.0,
            max_retries: 10,
            jitter: 0.3,
        }
    }
}

impl BackoffConfig {
    /// Calculate delay for given attempt number
    pub fn delay_for_attempt(&self, attempt: u32) -> Duration {
        let base_delay = (self.initial_delay_ms as f64)
            * self.multiplier.powi(attempt.min(10) as i32);
        let capped_delay = base_delay.min(self.max_delay_ms as f64);

        // Add jitter
        let jitter_range = capped_delay * self.jitter;
        let jitter = if jitter_range > 0.0 {
            let now = std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .subsec_nanos() as f64;
            (now % 1000.0) / 1000.0 * jitter_range
        } else {
            0.0
        };

        Duration::from_millis((capped_delay + jitter) as u64)
    }
}

// ═══════════════════════════════════════════════════════════════
// STATE MACHINE
// ═══════════════════════════════════════════════════════════════

/// Session state machine with persistence
pub struct SessionStateMachine {
    info: Mutex<SessionInfo>,
    backoff: BackoffConfig,
    conn: Mutex<Connection>,
    reconnect_attempts: AtomicU32,
    connected_since: Mutex<Option<Instant>>,
}

impl SessionStateMachine {
    /// Create a new session state machine
    pub fn new() -> Result<Self> {
        let db_path = Self::get_db_path()?;

        // Ensure parent directory exists
        if let Some(parent) = db_path.parent() {
            std::fs::create_dir_all(parent)?;
        }

        let conn = Connection::open(&db_path)
            .context("Failed to open session state database")?;

        // Initialize schema
        conn.execute(
            "CREATE TABLE IF NOT EXISTS session_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                session_id TEXT NOT NULL,
                state TEXT NOT NULL,
                server_url TEXT NOT NULL DEFAULT '',
                started_at TEXT,
                last_connected_at TEXT,
                state_changed_at TEXT NOT NULL,
                reconnect_attempts INTEGER NOT NULL DEFAULT 0,
                last_error TEXT
            )",
            [],
        )?;

        // Create state history table
        conn.execute(
            "CREATE TABLE IF NOT EXISTS state_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                from_state TEXT NOT NULL,
                to_state TEXT NOT NULL,
                event TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )",
            [],
        )?;

        // Create index for history queries
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_state_history_session
             ON state_history(session_id, timestamp DESC)",
            [],
        )?;

        let state_machine = Self {
            info: Mutex::new(SessionInfo::default()),
            backoff: BackoffConfig::default(),
            conn: Mutex::new(conn),
            reconnect_attempts: AtomicU32::new(0),
            connected_since: Mutex::new(None),
        };

        // Try to restore previous session
        state_machine.restore_session()?;

        info!("Session state machine initialized");
        Ok(state_machine)
    }

    /// Get the database path
    fn get_db_path() -> Result<PathBuf> {
        let data_dir = dirs::data_dir()
            .context("Failed to get data directory")?
            .join("kagami")
            .join("session_state.db");
        Ok(data_dir)
    }

    /// Restore session from database
    fn restore_session(&self) -> Result<()> {
        let conn = self.conn.lock().map_err(|e| anyhow::anyhow!("Lock error: {}", e))?;

        let result = conn.query_row(
            "SELECT session_id, state, server_url, started_at, last_connected_at,
                    state_changed_at, reconnect_attempts, last_error
             FROM session_state WHERE id = 1",
            [],
            |row| {
                Ok(SessionInfo {
                    session_id: row.get(0)?,
                    state: parse_state(&row.get::<_, String>(1)?),
                    server_url: row.get(2)?,
                    started_at: row.get::<_, Option<String>>(3)?
                        .and_then(|s| DateTime::parse_from_rfc3339(&s).ok())
                        .map(|dt| dt.with_timezone(&Utc)),
                    last_connected_at: row.get::<_, Option<String>>(4)?
                        .and_then(|s| DateTime::parse_from_rfc3339(&s).ok())
                        .map(|dt| dt.with_timezone(&Utc)),
                    state_changed_at: row.get::<_, String>(5)?
                        .parse::<DateTime<Utc>>()
                        .unwrap_or_else(|_| Utc::now()),
                    reconnect_attempts: row.get(6)?,
                    last_error: row.get(7)?,
                    uptime_seconds: None,
                })
            },
        );

        match result {
            Ok(info) => {
                // If previous session was connected or reconnecting, start as disconnected
                let restored_state = match info.state {
                    SessionState::Connected | SessionState::Reconnecting | SessionState::Connecting => {
                        info!("Previous session was {}, starting as disconnected", info.state);
                        SessionState::Disconnected
                    }
                    _ => info.state,
                };

                let mut current_info = self.info.lock().map_err(|e| anyhow::anyhow!("Lock error: {}", e))?;
                *current_info = SessionInfo {
                    state: restored_state,
                    ..info
                };
                self.reconnect_attempts.store(current_info.reconnect_attempts, Ordering::Relaxed);

                info!("Restored session {} in state {}", current_info.session_id, restored_state);
            }
            Err(rusqlite::Error::QueryReturnedNoRows) => {
                debug!("No previous session to restore");
            }
            Err(e) => {
                warn!("Failed to restore session: {}", e);
            }
        }

        Ok(())
    }

    /// Persist current session state
    fn persist_session(&self) -> Result<()> {
        let info = self.info.lock().map_err(|e| anyhow::anyhow!("Lock error: {}", e))?;
        let conn = self.conn.lock().map_err(|e| anyhow::anyhow!("Lock error: {}", e))?;

        conn.execute(
            "INSERT OR REPLACE INTO session_state
             (id, session_id, state, server_url, started_at, last_connected_at,
              state_changed_at, reconnect_attempts, last_error)
             VALUES (1, ?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)",
            params![
                info.session_id,
                info.state.to_string(),
                info.server_url,
                info.started_at.map(|dt| dt.to_rfc3339()),
                info.last_connected_at.map(|dt| dt.to_rfc3339()),
                info.state_changed_at.to_rfc3339(),
                info.reconnect_attempts,
                info.last_error,
            ],
        )?;

        Ok(())
    }

    /// Record state transition in history
    fn record_transition(&self, from: SessionState, to: SessionState, event: &SessionEvent) -> Result<()> {
        let info = self.info.lock().map_err(|e| anyhow::anyhow!("Lock error: {}", e))?;
        let conn = self.conn.lock().map_err(|e| anyhow::anyhow!("Lock error: {}", e))?;

        let event_str = serde_json::to_string(event).unwrap_or_else(|_| "unknown".to_string());

        conn.execute(
            "INSERT INTO state_history (session_id, from_state, to_state, event, timestamp)
             VALUES (?1, ?2, ?3, ?4, ?5)",
            params![
                info.session_id,
                from.to_string(),
                to.to_string(),
                event_str,
                Utc::now().to_rfc3339(),
            ],
        )?;

        // Keep only last 1000 history entries
        conn.execute(
            "DELETE FROM state_history WHERE id NOT IN (
                SELECT id FROM state_history ORDER BY id DESC LIMIT 1000
            )",
            [],
        )?;

        Ok(())
    }

    /// Process an event and transition state
    pub fn process_event(&self, event: SessionEvent) -> Result<SessionState> {
        let mut info = self.info.lock().map_err(|e| anyhow::anyhow!("Lock error: {}", e))?;
        let current_state = info.state;

        let (new_state, should_record) = match (&current_state, &event) {
            // Disconnected transitions
            (SessionState::Disconnected, SessionEvent::Connect) => {
                info.started_at = Some(Utc::now());
                self.reconnect_attempts.store(0, Ordering::Relaxed);
                (SessionState::Connecting, true)
            }

            // Connecting transitions
            (SessionState::Connecting, SessionEvent::ConnectionSuccess) => {
                info.last_connected_at = Some(Utc::now());
                info.last_error = None;
                let mut connected_since = self.connected_since.lock().unwrap();
                *connected_since = Some(Instant::now());
                (SessionState::Connected, true)
            }
            (SessionState::Connecting, SessionEvent::ConnectionFailure { reason }) => {
                info.last_error = Some(reason.clone());
                let attempts = self.reconnect_attempts.fetch_add(1, Ordering::Relaxed) + 1;
                info.reconnect_attempts = attempts;

                if attempts >= self.backoff.max_retries {
                    (SessionState::Error, true)
                } else {
                    (SessionState::Reconnecting, true)
                }
            }

            // Connected transitions
            (SessionState::Connected, SessionEvent::Disconnect) => {
                let mut connected_since = self.connected_since.lock().unwrap();
                if let Some(since) = *connected_since {
                    info.uptime_seconds = Some(since.elapsed().as_secs());
                }
                *connected_since = None;
                (SessionState::Disconnected, true)
            }
            (SessionState::Connected, SessionEvent::NetworkError { reason }) => {
                info.last_error = Some(reason.clone());
                let mut connected_since = self.connected_since.lock().unwrap();
                *connected_since = None;
                self.reconnect_attempts.store(0, Ordering::Relaxed);
                (SessionState::Reconnecting, true)
            }

            // Reconnecting transitions
            (SessionState::Reconnecting, SessionEvent::RetryTick) => {
                // No state change, just increment counter
                let attempts = self.reconnect_attempts.fetch_add(1, Ordering::Relaxed) + 1;
                info.reconnect_attempts = attempts;

                if attempts >= self.backoff.max_retries {
                    (SessionState::Error, true)
                } else {
                    (SessionState::Reconnecting, false) // Same state, don't record
                }
            }
            (SessionState::Reconnecting, SessionEvent::ConnectionSuccess) => {
                info.last_connected_at = Some(Utc::now());
                info.last_error = None;
                self.reconnect_attempts.store(0, Ordering::Relaxed);
                info.reconnect_attempts = 0;
                let mut connected_since = self.connected_since.lock().unwrap();
                *connected_since = Some(Instant::now());
                (SessionState::Connected, true)
            }
            (SessionState::Reconnecting, SessionEvent::MaxRetriesExceeded) => {
                (SessionState::Error, true)
            }
            (SessionState::Reconnecting, SessionEvent::Disconnect) => {
                (SessionState::Disconnected, true)
            }

            // Error transitions
            (SessionState::Error, SessionEvent::Reset) => {
                info.last_error = None;
                self.reconnect_attempts.store(0, Ordering::Relaxed);
                info.reconnect_attempts = 0;
                (SessionState::Disconnected, true)
            }
            (SessionState::Error, SessionEvent::Connect) => {
                // Allow reconnection from error state
                info.last_error = None;
                self.reconnect_attempts.store(0, Ordering::Relaxed);
                info.reconnect_attempts = 0;
                info.started_at = Some(Utc::now());
                (SessionState::Connecting, true)
            }

            // Invalid transitions - stay in current state
            _ => {
                debug!(
                    "Invalid transition: {:?} on event {:?}, staying in {:?}",
                    current_state, event, current_state
                );
                (current_state, false)
            }
        };

        if new_state != current_state {
            info.state = new_state;
            info.state_changed_at = Utc::now();

            // Drop info lock before recording
            drop(info);

            if should_record {
                if let Err(e) = self.record_transition(current_state, new_state, &event) {
                    warn!("Failed to record state transition: {}", e);
                }
            }

            if let Err(e) = self.persist_session() {
                warn!("Failed to persist session state: {}", e);
            }

            info!(
                "Session state transition: {} -> {} (event: {:?})",
                current_state, new_state, event
            );
        }

        Ok(new_state)
    }

    /// Get current session info
    pub fn get_info(&self) -> SessionInfo {
        let mut info = self.info.lock().unwrap().clone();

        // Calculate uptime if connected
        if info.state == SessionState::Connected {
            if let Some(since) = *self.connected_since.lock().unwrap() {
                info.uptime_seconds = Some(since.elapsed().as_secs());
            }
        }

        info
    }

    /// Get current state
    pub fn get_state(&self) -> SessionState {
        self.info.lock().unwrap().state
    }

    /// Set server URL
    pub fn set_server_url(&self, url: &str) {
        let mut info = self.info.lock().unwrap();
        info.server_url = url.to_string();
        drop(info);
        let _ = self.persist_session();
    }

    /// Get reconnection delay for current attempt
    pub fn get_reconnect_delay(&self) -> Duration {
        let attempts = self.reconnect_attempts.load(Ordering::Relaxed);
        self.backoff.delay_for_attempt(attempts)
    }

    /// Check if should retry
    pub fn should_retry(&self) -> bool {
        let attempts = self.reconnect_attempts.load(Ordering::Relaxed);
        attempts < self.backoff.max_retries
    }

    /// Get state history
    pub fn get_history(&self, limit: usize) -> Result<Vec<StateHistoryEntry>> {
        let info = self.info.lock().map_err(|e| anyhow::anyhow!("Lock error: {}", e))?;
        let conn = self.conn.lock().map_err(|e| anyhow::anyhow!("Lock error: {}", e))?;

        let mut stmt = conn.prepare(
            "SELECT from_state, to_state, event, timestamp
             FROM state_history
             WHERE session_id = ?1
             ORDER BY id DESC
             LIMIT ?2"
        )?;

        let entries = stmt.query_map(params![info.session_id, limit as i64], |row| {
            Ok(StateHistoryEntry {
                from_state: parse_state(&row.get::<_, String>(0)?),
                to_state: parse_state(&row.get::<_, String>(1)?),
                event: row.get(2)?,
                timestamp: row.get(3)?,
            })
        })?
        .filter_map(|r| r.ok())
        .collect();

        Ok(entries)
    }

    /// Reset session ID (for new session)
    pub fn new_session(&self) {
        let mut info = self.info.lock().unwrap();
        info.session_id = generate_session_id();
        info.started_at = None;
        info.last_connected_at = None;
        info.uptime_seconds = None;
        self.reconnect_attempts.store(0, Ordering::Relaxed);
        info.reconnect_attempts = 0;
        drop(info);
        let _ = self.persist_session();
    }
}

/// State history entry
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StateHistoryEntry {
    pub from_state: SessionState,
    pub to_state: SessionState,
    pub event: String,
    pub timestamp: String,
}

/// Parse state from string
fn parse_state(s: &str) -> SessionState {
    match s {
        "disconnected" => SessionState::Disconnected,
        "connecting" => SessionState::Connecting,
        "connected" => SessionState::Connected,
        "reconnecting" => SessionState::Reconnecting,
        "error" => SessionState::Error,
        _ => SessionState::Disconnected,
    }
}

/// Generate unique session ID
fn generate_session_id() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let timestamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis();
    format!("ses_{:x}_{:04x}", timestamp, rand_u16())
}

/// Simple random u16
fn rand_u16() -> u16 {
    use std::time::{SystemTime, UNIX_EPOCH};
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .subsec_nanos();
    (nanos % 65536) as u16
}

// ═══════════════════════════════════════════════════════════════
// GLOBAL INSTANCE
// ═══════════════════════════════════════════════════════════════

static SESSION_STATE: std::sync::OnceLock<SessionStateMachine> = std::sync::OnceLock::new();

pub fn get_session_state() -> &'static SessionStateMachine {
    SESSION_STATE.get_or_init(|| {
        SessionStateMachine::new().unwrap_or_else(|e| {
            error!("Failed to initialize session state: {}", e);
            panic!("Session state initialization failed")
        })
    })
}

// ═══════════════════════════════════════════════════════════════
// TAURI COMMANDS
// ═══════════════════════════════════════════════════════════════

#[tauri::command]
pub fn get_session_info() -> Result<SessionInfo, String> {
    Ok(get_session_state().get_info())
}

#[tauri::command]
pub fn get_session_state_value() -> Result<String, String> {
    Ok(get_session_state().get_state().to_string())
}

#[tauri::command]
pub fn session_connect(server_url: Option<String>) -> Result<String, String> {
    let state = get_session_state();

    if let Some(url) = server_url {
        state.set_server_url(&url);
    }

    state.process_event(SessionEvent::Connect)
        .map(|s| s.to_string())
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub fn session_disconnect() -> Result<String, String> {
    get_session_state()
        .process_event(SessionEvent::Disconnect)
        .map(|s| s.to_string())
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub fn session_reset() -> Result<String, String> {
    get_session_state()
        .process_event(SessionEvent::Reset)
        .map(|s| s.to_string())
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub fn get_session_history(limit: Option<usize>) -> Result<Vec<StateHistoryEntry>, String> {
    get_session_state()
        .get_history(limit.unwrap_or(50))
        .map_err(|e| e.to_string())
}

/*
 * Nexus coordinates. Nexus persists. Nexus recovers.
 * h(x) >= 0. Always.
 */
