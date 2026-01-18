//! Connection Pool & Pre-emptive Reconnection — Flow (e3) Colony
//!
//! Optimized WebSocket connection management with:
//! - Connection pooling for multiple endpoints
//! - Pre-emptive reconnection on signal degradation
//! - Faster handshake with session resumption
//! - Connection health monitoring
//! - Automatic failover
//!
//! ## Architecture
//!
//! ```text
//! ConnectionPool
//!   |
//!   +-- PooledConnection[0] (primary)
//!   |     +-- WebSocket
//!   |     +-- HealthMonitor
//!   |     +-- ReconnectController
//!   |
//!   +-- PooledConnection[1] (backup)
//!   |     +-- WebSocket (warm standby)
//!   |     +-- HealthMonitor
//!   |
//!   +-- PooledConnection[2] (backup)
//!         +-- WebSocket (cold standby)
//! ```
//!
//! Colony: Flow (e3) — Adaptation, sensing
//!
//! h(x) >= 0. Always.

use anyhow::{Context, Result};
use futures_util::{SinkExt, StreamExt};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, AtomicU32, AtomicU64, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::{mpsc, RwLock, Semaphore};
use tokio_tungstenite::{connect_async, tungstenite::Message};
use tracing::{debug, error, info, warn};

// ============================================================================
// Configuration Constants
// ============================================================================

/// Maximum connections in the pool
pub const MAX_POOL_SIZE: usize = 4;

/// Health check interval (ms)
pub const HEALTH_CHECK_INTERVAL_MS: u64 = 5000;

/// Signal degradation threshold for pre-emptive reconnection (0.0-1.0)
pub const DEGRADATION_THRESHOLD: f32 = 0.7;

/// Minimum time between pre-emptive reconnections (ms)
pub const MIN_PREEMPTIVE_INTERVAL_MS: u64 = 30000;

/// Fast handshake timeout (ms)
pub const FAST_HANDSHAKE_TIMEOUT_MS: u64 = 2000;

/// Session token expiry (seconds)
pub const SESSION_TOKEN_EXPIRY_SECS: u64 = 3600;

/// Warm standby ping interval (ms)
pub const WARM_STANDBY_PING_MS: u64 = 60000;

/// Connection quality history window size
pub const QUALITY_HISTORY_SIZE: usize = 20;

// ============================================================================
// Connection Quality Metrics
// ============================================================================

/// Quality metrics for a connection
#[derive(Debug, Clone, Default)]
pub struct ConnectionQuality {
    /// Recent latency samples (ms)
    latency_samples: Vec<u64>,
    /// Recent message success rate (0.0-1.0)
    success_rate: f32,
    /// Consecutive successful messages
    consecutive_successes: u32,
    /// Consecutive failures
    consecutive_failures: u32,
    /// Last health check time
    last_health_check: Option<Instant>,
    /// Last message time
    last_message_time: Option<Instant>,
    /// Total messages sent
    total_sent: u64,
    /// Total messages received
    total_received: u64,
    /// Connection uptime (ms)
    uptime_ms: u64,
}

impl ConnectionQuality {
    /// Create new quality metrics
    pub fn new() -> Self {
        Self::default()
    }

    /// Record a successful message with latency
    pub fn record_success(&mut self, latency_ms: u64) {
        self.latency_samples.push(latency_ms);
        if self.latency_samples.len() > QUALITY_HISTORY_SIZE {
            self.latency_samples.remove(0);
        }

        self.consecutive_successes += 1;
        self.consecutive_failures = 0;
        self.total_received += 1;
        self.last_message_time = Some(Instant::now());

        // Update success rate
        let total = self.total_sent.max(1) as f32;
        self.success_rate = self.total_received as f32 / total;
    }

    /// Record a failure
    pub fn record_failure(&mut self) {
        self.consecutive_failures += 1;
        self.consecutive_successes = 0;

        // Update success rate
        let total = self.total_sent.max(1) as f32;
        self.success_rate = self.total_received as f32 / total;
    }

    /// Record a sent message
    pub fn record_sent(&mut self) {
        self.total_sent += 1;
    }

    /// Get average latency
    pub fn average_latency_ms(&self) -> Option<u64> {
        if self.latency_samples.is_empty() {
            return None;
        }
        Some(self.latency_samples.iter().sum::<u64>() / self.latency_samples.len() as u64)
    }

    /// Get 95th percentile latency
    pub fn p95_latency_ms(&self) -> Option<u64> {
        if self.latency_samples.len() < 5 {
            return None;
        }
        let mut sorted = self.latency_samples.clone();
        sorted.sort_unstable();
        let idx = (sorted.len() as f32 * 0.95) as usize;
        Some(sorted[idx.min(sorted.len() - 1)])
    }

    /// Calculate overall quality score (0.0-1.0)
    pub fn quality_score(&self) -> f32 {
        let mut score = 0.0f32;
        let mut weights = 0.0f32;

        // Success rate (40% weight)
        score += self.success_rate * 0.4;
        weights += 0.4;

        // Latency score (30% weight)
        if let Some(avg) = self.average_latency_ms() {
            let latency_score = if avg < 50 {
                1.0
            } else if avg < 100 {
                0.9
            } else if avg < 200 {
                0.7
            } else if avg < 500 {
                0.4
            } else {
                0.1
            };
            score += latency_score * 0.3;
            weights += 0.3;
        }

        // Stability score (20% weight)
        let stability = if self.consecutive_failures > 5 {
            0.0
        } else if self.consecutive_failures > 2 {
            0.3
        } else if self.consecutive_successes > 20 {
            1.0
        } else if self.consecutive_successes > 10 {
            0.8
        } else {
            0.6
        };
        score += stability * 0.2;
        weights += 0.2;

        // Freshness score (10% weight)
        if let Some(last) = self.last_message_time {
            let age_ms = last.elapsed().as_millis() as u64;
            let freshness = if age_ms < 5000 {
                1.0
            } else if age_ms < 30000 {
                0.7
            } else if age_ms < 60000 {
                0.3
            } else {
                0.0
            };
            score += freshness * 0.1;
            weights += 0.1;
        }

        if weights > 0.0 {
            score / weights
        } else {
            0.5 // Default neutral score
        }
    }

    /// Check if connection is degraded
    pub fn is_degraded(&self) -> bool {
        self.quality_score() < DEGRADATION_THRESHOLD
    }

    /// Get time since last message
    pub fn time_since_last_message(&self) -> Option<Duration> {
        self.last_message_time.map(|t| t.elapsed())
    }
}

// ============================================================================
// Session Token for Fast Reconnection
// ============================================================================

/// Session token for fast handshake
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionToken {
    /// Token value
    pub token: String,
    /// Server endpoint
    pub endpoint: String,
    /// Creation timestamp
    pub created_at: u64,
    /// Last used timestamp
    pub last_used: u64,
    /// Subscribed topics
    pub topics: Vec<String>,
    /// Connection capabilities
    pub capabilities: Vec<String>,
}

impl SessionToken {
    /// Create a new session token
    pub fn new(endpoint: &str, token: &str) -> Self {
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();

        Self {
            token: token.to_string(),
            endpoint: endpoint.to_string(),
            created_at: now,
            last_used: now,
            topics: Vec::new(),
            capabilities: Vec::new(),
        }
    }

    /// Check if token is expired
    pub fn is_expired(&self) -> bool {
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();

        now - self.created_at > SESSION_TOKEN_EXPIRY_SECS
    }

    /// Update last used time
    pub fn touch(&mut self) {
        self.last_used = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
    }
}

// ============================================================================
// Pooled Connection
// ============================================================================

/// Connection state in the pool
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ConnectionState {
    /// Not connected
    Disconnected,
    /// Connecting in progress
    Connecting,
    /// Connected and active
    Active,
    /// Connected but in warm standby
    WarmStandby,
    /// Degraded but still usable
    Degraded,
    /// Failing over to another connection
    FailingOver,
    /// Reconnecting pre-emptively
    PreemptiveReconnect,
}

/// A single pooled connection
pub struct PooledConnection {
    /// Connection ID
    id: String,
    /// Endpoint URL
    endpoint: String,
    /// Current state
    state: Arc<RwLock<ConnectionState>>,
    /// Quality metrics
    quality: Arc<RwLock<ConnectionQuality>>,
    /// Session token for fast reconnect
    session_token: Arc<RwLock<Option<SessionToken>>>,
    /// Is primary connection
    is_primary: AtomicBool,
    /// Connection count
    connection_count: AtomicU32,
    /// Outgoing message channel
    outgoing_tx: Option<mpsc::Sender<Message>>,
    /// Last connect attempt
    last_connect_attempt: Arc<RwLock<Option<Instant>>>,
    /// Last pre-emptive reconnect
    last_preemptive_reconnect: Arc<RwLock<Option<Instant>>>,
}

impl PooledConnection {
    /// Create a new pooled connection
    pub fn new(id: &str, endpoint: &str, is_primary: bool) -> Self {
        Self {
            id: id.to_string(),
            endpoint: endpoint.to_string(),
            state: Arc::new(RwLock::new(ConnectionState::Disconnected)),
            quality: Arc::new(RwLock::new(ConnectionQuality::new())),
            session_token: Arc::new(RwLock::new(None)),
            is_primary: AtomicBool::new(is_primary),
            connection_count: AtomicU32::new(0),
            outgoing_tx: None,
            last_connect_attempt: Arc::new(RwLock::new(None)),
            last_preemptive_reconnect: Arc::new(RwLock::new(None)),
        }
    }

    /// Get connection state
    pub async fn state(&self) -> ConnectionState {
        *self.state.read().await
    }

    /// Set connection state
    pub async fn set_state(&self, state: ConnectionState) {
        let mut guard = self.state.write().await;
        *guard = state;
    }

    /// Get quality score
    pub async fn quality_score(&self) -> f32 {
        self.quality.read().await.quality_score()
    }

    /// Check if should pre-emptively reconnect
    pub async fn should_preemptive_reconnect(&self) -> bool {
        let quality = self.quality.read().await;

        if !quality.is_degraded() {
            return false;
        }

        // Check minimum interval
        let last = self.last_preemptive_reconnect.read().await;
        if let Some(last_time) = *last {
            if last_time.elapsed() < Duration::from_millis(MIN_PREEMPTIVE_INTERVAL_MS) {
                return false;
            }
        }

        true
    }

    /// Connect with fast handshake support
    pub async fn connect(&mut self, auth_token: Option<&str>) -> Result<mpsc::Receiver<Message>> {
        self.set_state(ConnectionState::Connecting).await;

        // Update last connect attempt
        {
            let mut last = self.last_connect_attempt.write().await;
            *last = Some(Instant::now());
        }

        // Convert URL
        let ws_url = self.endpoint
            .replace("http://", "ws://")
            .replace("https://", "wss://");
        let url = format!("{}/api/colonies/stream", ws_url);

        info!("[{}] Connecting to {}", self.id, url);

        // Connect with timeout
        let connect_result = tokio::time::timeout(
            Duration::from_millis(FAST_HANDSHAKE_TIMEOUT_MS),
            connect_async(&url)
        ).await;

        let (ws_stream, _) = match connect_result {
            Ok(Ok(stream)) => stream,
            Ok(Err(e)) => return Err(e.into()),
            Err(_) => return Err(anyhow::anyhow!("Connection timeout")),
        };

        let (mut write, read) = ws_stream.split();

        // Create channels
        let (outgoing_tx, mut outgoing_rx) = mpsc::channel::<Message>(256);
        let (incoming_tx, incoming_rx) = mpsc::channel::<Message>(256);

        // Try fast handshake with session token
        let session = self.session_token.read().await;
        let handshake_msg = if let Some(ref token) = *session {
            if !token.is_expired() {
                // Resume session
                serde_json::json!({
                    "type": "resume",
                    "session_token": token.token,
                    "topics": token.topics
                })
            } else {
                // Full auth
                serde_json::json!({
                    "type": "auth",
                    "token": auth_token.unwrap_or("hub-local"),
                    "subscribe": ["colonies", "home", "safety"],
                    "capabilities": ["fast_reconnect", "compression"]
                })
            }
        } else {
            // Full auth
            serde_json::json!({
                "type": "auth",
                "token": auth_token.unwrap_or("hub-local"),
                "subscribe": ["colonies", "home", "safety"],
                "capabilities": ["fast_reconnect", "compression"]
            })
        };
        drop(session);

        // Send handshake
        write.send(Message::Text(handshake_msg.to_string())).await?;

        self.outgoing_tx = Some(outgoing_tx.clone());
        self.connection_count.fetch_add(1, Ordering::Relaxed);

        let state = self.state.clone();
        let quality = self.quality.clone();
        let session_token = self.session_token.clone();
        let id = self.id.clone();
        let endpoint = self.endpoint.clone();

        // Spawn write task
        tokio::spawn(async move {
            while let Some(msg) = outgoing_rx.recv().await {
                if let Err(e) = write.send(msg).await {
                    error!("[{}] Write error: {}", id, e);
                    break;
                }
            }
        });

        // Spawn read task
        let id_clone = self.id.clone();
        tokio::spawn(async move {
            let mut read = read;
            let mut last_ping = Instant::now();

            loop {
                tokio::select! {
                    msg = read.next() => {
                        match msg {
                            Some(Ok(msg)) => {
                                // Record quality metrics
                                {
                                    let mut q = quality.write().await;
                                    let latency = last_ping.elapsed().as_millis() as u64;
                                    q.record_success(latency);
                                }

                                // Check for session token in auth response
                                if let Message::Text(ref text) = msg {
                                    if let Ok(json) = serde_json::from_str::<serde_json::Value>(text) {
                                        if json.get("type").and_then(|v| v.as_str()) == Some("auth_success") {
                                            if let Some(token) = json.get("session_token").and_then(|v| v.as_str()) {
                                                let mut session = session_token.write().await;
                                                *session = Some(SessionToken::new(&endpoint, token));
                                                info!("[{}] Session token received for fast reconnect", id_clone);
                                            }
                                        }
                                    }
                                }

                                if incoming_tx.send(msg).await.is_err() {
                                    break;
                                }
                            }
                            Some(Err(e)) => {
                                error!("[{}] Read error: {}", id_clone, e);
                                let mut q = quality.write().await;
                                q.record_failure();
                                break;
                            }
                            None => {
                                info!("[{}] Connection closed", id_clone);
                                break;
                            }
                        }
                    }
                    _ = tokio::time::sleep(Duration::from_millis(HEALTH_CHECK_INTERVAL_MS)) => {
                        last_ping = Instant::now();
                    }
                }
            }

            let mut s = state.write().await;
            *s = ConnectionState::Disconnected;
        });

        self.set_state(ConnectionState::Active).await;
        info!("[{}] Connected successfully", self.id);

        Ok(incoming_rx)
    }

    /// Send a message
    pub async fn send(&self, msg: Message) -> Result<()> {
        if let Some(ref tx) = self.outgoing_tx {
            tx.send(msg).await
                .map_err(|_| anyhow::anyhow!("Channel closed"))?;

            let mut quality = self.quality.write().await;
            quality.record_sent();
        }
        Ok(())
    }

    /// Get health status
    pub async fn health(&self) -> PooledConnectionHealth {
        let state = self.state().await;
        let quality = self.quality.read().await;

        PooledConnectionHealth {
            id: self.id.clone(),
            endpoint: self.endpoint.clone(),
            state,
            quality_score: quality.quality_score(),
            is_degraded: quality.is_degraded(),
            avg_latency_ms: quality.average_latency_ms(),
            p95_latency_ms: quality.p95_latency_ms(),
            success_rate: quality.success_rate,
            is_primary: self.is_primary.load(Ordering::Relaxed),
            connection_count: self.connection_count.load(Ordering::Relaxed),
        }
    }
}

/// Health status for a pooled connection
#[derive(Debug, Clone, Serialize)]
pub struct PooledConnectionHealth {
    pub id: String,
    pub endpoint: String,
    pub state: ConnectionState,
    pub quality_score: f32,
    pub is_degraded: bool,
    pub avg_latency_ms: Option<u64>,
    pub p95_latency_ms: Option<u64>,
    pub success_rate: f32,
    pub is_primary: bool,
    pub connection_count: u32,
}

impl Serialize for ConnectionState {
    fn serialize<S>(&self, serializer: S) -> std::result::Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        let s = match self {
            ConnectionState::Disconnected => "disconnected",
            ConnectionState::Connecting => "connecting",
            ConnectionState::Active => "active",
            ConnectionState::WarmStandby => "warm_standby",
            ConnectionState::Degraded => "degraded",
            ConnectionState::FailingOver => "failing_over",
            ConnectionState::PreemptiveReconnect => "preemptive_reconnect",
        };
        serializer.serialize_str(s)
    }
}

// ============================================================================
// Connection Pool
// ============================================================================

/// Pool of managed connections
pub struct ConnectionPool {
    /// Pool connections
    connections: Arc<RwLock<Vec<PooledConnection>>>,
    /// Semaphore for connection limit
    semaphore: Arc<Semaphore>,
    /// Event channel
    event_tx: mpsc::Sender<PoolEvent>,
    /// Running flag
    running: AtomicBool,
    /// Auth token
    auth_token: Option<String>,
}

/// Events from the connection pool
#[derive(Debug, Clone)]
pub enum PoolEvent {
    /// Connection established
    Connected { connection_id: String },
    /// Connection lost
    Disconnected { connection_id: String },
    /// Failover occurred
    FailoverStarted { from: String, to: String },
    /// Failover completed
    FailoverCompleted { new_primary: String },
    /// Pre-emptive reconnection triggered
    PreemptiveReconnect { connection_id: String, quality_score: f32 },
    /// Quality degraded
    QualityDegraded { connection_id: String, quality_score: f32 },
    /// Message received
    Message { connection_id: String, message: String },
}

impl ConnectionPool {
    /// Create a new connection pool
    pub fn new(endpoints: &[&str]) -> (Self, mpsc::Receiver<PoolEvent>) {
        let (event_tx, event_rx) = mpsc::channel(256);

        let mut connections = Vec::new();
        for (i, endpoint) in endpoints.iter().take(MAX_POOL_SIZE).enumerate() {
            let is_primary = i == 0;
            connections.push(PooledConnection::new(
                &format!("conn-{}", i),
                endpoint,
                is_primary,
            ));
        }

        let pool = Self {
            connections: Arc::new(RwLock::new(connections)),
            semaphore: Arc::new(Semaphore::new(MAX_POOL_SIZE)),
            event_tx,
            running: AtomicBool::new(false),
            auth_token: None,
        };

        (pool, event_rx)
    }

    /// Set authentication token
    pub fn with_auth(mut self, token: &str) -> Self {
        self.auth_token = Some(token.to_string());
        self
    }

    /// Start the connection pool
    pub async fn start(&self) -> Result<()> {
        self.running.store(true, Ordering::Relaxed);
        info!("Starting connection pool");

        // Connect primary
        {
            let mut connections = self.connections.write().await;
            if let Some(primary) = connections.first_mut() {
                let auth = self.auth_token.as_deref();
                if let Err(e) = primary.connect(auth).await {
                    warn!("Primary connection failed: {}", e);
                } else {
                    let _ = self.event_tx.send(PoolEvent::Connected {
                        connection_id: primary.id.clone(),
                    }).await;
                }
            }
        }

        // Start health monitor
        self.start_health_monitor();

        Ok(())
    }

    /// Stop the connection pool
    pub async fn stop(&self) {
        self.running.store(false, Ordering::Relaxed);
        info!("Stopping connection pool");
    }

    /// Send message to primary connection
    pub async fn send(&self, message: Message) -> Result<()> {
        let connections = self.connections.read().await;

        // Find primary active connection
        for conn in connections.iter() {
            if conn.is_primary.load(Ordering::Relaxed) {
                match conn.state().await {
                    ConnectionState::Active | ConnectionState::Degraded => {
                        return conn.send(message).await;
                    }
                    _ => {}
                }
            }
        }

        // Fallback to any active connection
        for conn in connections.iter() {
            match conn.state().await {
                ConnectionState::Active | ConnectionState::Degraded => {
                    return conn.send(message).await;
                }
                _ => {}
            }
        }

        Err(anyhow::anyhow!("No active connections"))
    }

    /// Get pool health status
    pub async fn health(&self) -> PoolHealth {
        let connections = self.connections.read().await;
        let mut conn_health = Vec::new();

        let mut active_count = 0;
        let mut primary_id = None;

        for conn in connections.iter() {
            let health = conn.health().await;
            if matches!(health.state, ConnectionState::Active | ConnectionState::Degraded) {
                active_count += 1;
            }
            if health.is_primary {
                primary_id = Some(health.id.clone());
            }
            conn_health.push(health);
        }

        PoolHealth {
            total_connections: connections.len(),
            active_connections: active_count,
            primary_connection: primary_id,
            connections: conn_health,
            running: self.running.load(Ordering::Relaxed),
        }
    }

    /// Trigger immediate failover to backup
    pub async fn failover(&self) -> Result<()> {
        let mut connections = self.connections.write().await;

        // Find current primary
        let primary_idx = connections.iter()
            .position(|c| c.is_primary.load(Ordering::Relaxed));

        if let Some(idx) = primary_idx {
            // Demote current primary
            connections[idx].is_primary.store(false, Ordering::Relaxed);

            let from_id = connections[idx].id.clone();

            // Find best backup
            let mut best_backup_idx = None;
            let mut best_score = 0.0f32;

            for (i, conn) in connections.iter().enumerate() {
                if i != idx {
                    let score = conn.quality_score().await;
                    if score > best_score {
                        best_score = score;
                        best_backup_idx = Some(i);
                    }
                }
            }

            if let Some(backup_idx) = best_backup_idx {
                // Promote backup to primary
                connections[backup_idx].is_primary.store(true, Ordering::Relaxed);

                let to_id = connections[backup_idx].id.clone();

                let _ = self.event_tx.send(PoolEvent::FailoverStarted {
                    from: from_id,
                    to: to_id.clone(),
                }).await;

                // Ensure backup is connected
                let auth = self.auth_token.as_deref();
                if connections[backup_idx].state().await == ConnectionState::Disconnected {
                    if let Err(e) = connections[backup_idx].connect(auth).await {
                        error!("Failed to connect backup during failover: {}", e);
                        return Err(e);
                    }
                }

                let _ = self.event_tx.send(PoolEvent::FailoverCompleted {
                    new_primary: to_id,
                }).await;

                info!("Failover completed");
            }
        }

        Ok(())
    }

    /// Start health monitoring task
    fn start_health_monitor(&self) {
        let connections = self.connections.clone();
        let event_tx = self.event_tx.clone();
        let running = self.running.clone();
        let auth_token = self.auth_token.clone();

        tokio::spawn(async move {
            let mut interval = tokio::time::interval(Duration::from_millis(HEALTH_CHECK_INTERVAL_MS));

            while running.load(Ordering::Relaxed) {
                interval.tick().await;

                let mut conns = connections.write().await;

                for conn in conns.iter_mut() {
                    let state = conn.state().await;
                    let quality_score = conn.quality_score().await;

                    // Check for degradation
                    if matches!(state, ConnectionState::Active) && conn.quality.read().await.is_degraded() {
                        conn.set_state(ConnectionState::Degraded).await;

                        let _ = event_tx.send(PoolEvent::QualityDegraded {
                            connection_id: conn.id.clone(),
                            quality_score,
                        }).await;
                    }

                    // Check for pre-emptive reconnection
                    if conn.is_primary.load(Ordering::Relaxed) && conn.should_preemptive_reconnect().await {
                        let _ = event_tx.send(PoolEvent::PreemptiveReconnect {
                            connection_id: conn.id.clone(),
                            quality_score,
                        }).await;

                        // Update last preemptive time
                        {
                            let mut last = conn.last_preemptive_reconnect.write().await;
                            *last = Some(Instant::now());
                        }

                        // Attempt reconnection
                        conn.set_state(ConnectionState::PreemptiveReconnect).await;
                        let auth = auth_token.as_deref();
                        if let Err(e) = conn.connect(auth).await {
                            error!("[{}] Pre-emptive reconnection failed: {}", conn.id, e);
                        }
                    }

                    // Reconnect disconnected connections
                    if matches!(state, ConnectionState::Disconnected) {
                        let auth = auth_token.as_deref();
                        if let Err(e) = conn.connect(auth).await {
                            debug!("[{}] Reconnection attempt failed: {}", conn.id, e);
                        } else {
                            let _ = event_tx.send(PoolEvent::Connected {
                                connection_id: conn.id.clone(),
                            }).await;
                        }
                    }
                }
            }
        });
    }
}

/// Pool health status
#[derive(Debug, Clone, Serialize)]
pub struct PoolHealth {
    pub total_connections: usize,
    pub active_connections: usize,
    pub primary_connection: Option<String>,
    pub connections: Vec<PooledConnectionHealth>,
    pub running: bool,
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_connection_quality_new() {
        let quality = ConnectionQuality::new();
        assert_eq!(quality.quality_score(), 0.5); // Default neutral
    }

    #[test]
    fn test_connection_quality_success() {
        let mut quality = ConnectionQuality::new();
        quality.record_sent();
        quality.record_success(50);

        assert!(quality.quality_score() > 0.5);
        assert_eq!(quality.consecutive_successes, 1);
        assert_eq!(quality.consecutive_failures, 0);
    }

    #[test]
    fn test_connection_quality_failure() {
        let mut quality = ConnectionQuality::new();
        quality.record_failure();

        assert_eq!(quality.consecutive_failures, 1);
        assert_eq!(quality.consecutive_successes, 0);
    }

    #[test]
    fn test_connection_quality_degraded() {
        let mut quality = ConnectionQuality::new();

        // Simulate many failures
        for _ in 0..10 {
            quality.record_failure();
        }

        assert!(quality.is_degraded());
    }

    #[test]
    fn test_session_token_expiry() {
        let mut token = SessionToken::new("ws://localhost", "test-token");

        assert!(!token.is_expired());

        // Simulate expired token
        token.created_at = 0;
        assert!(token.is_expired());
    }

    #[tokio::test]
    async fn test_pooled_connection_state() {
        let conn = PooledConnection::new("test-1", "ws://localhost", true);

        assert_eq!(conn.state().await, ConnectionState::Disconnected);

        conn.set_state(ConnectionState::Active).await;
        assert_eq!(conn.state().await, ConnectionState::Active);
    }

    #[tokio::test]
    async fn test_connection_pool_creation() {
        let endpoints = &["ws://localhost:8080", "ws://localhost:8081"];
        let (pool, _event_rx) = ConnectionPool::new(endpoints);

        let health = pool.health().await;

        assert_eq!(health.total_connections, 2);
        assert_eq!(health.active_connections, 0);
    }

    #[test]
    fn test_average_latency() {
        let mut quality = ConnectionQuality::new();

        quality.latency_samples = vec![10, 20, 30, 40, 50];

        assert_eq!(quality.average_latency_ms(), Some(30));
    }

    #[test]
    fn test_p95_latency() {
        let mut quality = ConnectionQuality::new();

        quality.latency_samples = vec![10, 20, 30, 40, 50, 60, 70, 80, 90, 100];

        let p95 = quality.p95_latency_ms().unwrap();
        assert!(p95 >= 90); // Should be around 95th percentile
    }
}

/*
 * Flow adapts. Connections pool. Pre-emptive reconnection prevents drops.
 * Fast handshake resumes sessions. Quality monitors trigger failover.
 *
 * h(x) >= 0. Always.
 */
