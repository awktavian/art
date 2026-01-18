//! Real-Time State Sync for Kagami Hub
//!
//! WebSocket connection to the Kagami API for:
//! - Colony activity updates
//! - Home state changes
//! - Training status
//!
//! Features:
//! - Exponential backoff with jitter for reconnection
//! - Heartbeat/keepalive mechanism
//! - Connection state tracking
//!
//! Colony: Nexus (e₄) × Flow (e₃) → Crystal (e₇)

use anyhow::{Context, Result};
use futures_util::{SinkExt, StreamExt};
use serde::{Deserialize, Serialize};
use std::sync::atomic::{AtomicBool, AtomicU32, AtomicU64, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::mpsc;
use tokio_tungstenite::{connect_async, tungstenite::Message};
use tracing::{debug, error, info, warn};

// Connection parameters (P1 audit: reduced backoff aggression)
// - Initial delay reduced from 1s to 500ms for faster recovery
// - Max delay capped at 30s (from 60s) per audit requirement
// - Multiplier reduced from 1.5 to 1.2 for gentler exponential growth
const INITIAL_RECONNECT_DELAY_MS: u64 = 500; // Was 1000ms
const MAX_RECONNECT_DELAY_MS: u64 = 30000; // Was 60000ms (capped at 30s)
const RECONNECT_MULTIPLIER: f64 = 1.2; // Was 1.5
const RECONNECT_JITTER: f64 = 0.3; // 30% jitter
const HEARTBEAT_INTERVAL_MS: u64 = 30000; // 30 seconds
const HEARTBEAT_TIMEOUT_MS: u64 = 10000; // 10 seconds timeout for pong
const MAX_CONSECUTIVE_FAILURES: u32 = 10;

/// State received from WebSocket
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct KagamiState {
    pub connected: bool,
    pub safety_score: Option<f64>,
    pub active_colonies: Vec<String>,
    pub home_status: Option<HomeState>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct HomeState {
    pub movie_mode: bool,
    pub fireplace_on: bool,
    pub occupied_rooms: Vec<String>,
}

/// Orb interaction event from cross-client sync
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct OrbInteraction {
    pub client: String,
    pub action: String,
    pub context: std::collections::HashMap<String, String>,
}

/// Orb state from API
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct OrbState {
    pub active_colony: Option<String>,
    pub activity: String,
    pub safety_score: f64,
    pub color_hex: String,
}

/// Event types from the WebSocket stream
#[derive(Debug, Clone)]
pub enum RealtimeEvent {
    Connected,
    Disconnected,
    StateUpdate(KagamiState),
    ColonyActivity { colony: String, action: String },
    HomeUpdate(HomeState),
    SafetyUpdate { h_x: f64 },
    /// Orb interaction from another client (flash LED ring)
    OrbInteraction(OrbInteraction),
    /// Orb state changed (update LED colors)
    OrbStateChanged(OrbState),
    Error(String),
}

/// Connection health metrics
#[derive(Debug, Clone)]
pub struct ConnectionHealth {
    pub connected: bool,
    pub consecutive_failures: u32,
    pub last_message_age_ms: u64,
    pub reconnect_attempts: u32,
}

/// Real-time connection manager with exponential backoff
pub struct RealtimeConnection {
    api_url: String,
    connected: Arc<AtomicBool>,
    consecutive_failures: Arc<AtomicU32>,
    reconnect_attempts: Arc<AtomicU32>,
    /// Timestamp (millis since process start) of last received message
    last_message_time_ms: Arc<AtomicU64>,
    /// Process start time for calculating message age
    start_instant: Instant,
    event_tx: mpsc::Sender<RealtimeEvent>,
    shutdown_tx: Option<mpsc::Sender<()>>,
    reconnect_now_tx: Option<mpsc::Sender<()>>,
    auth_token: Option<String>,
}

impl RealtimeConnection {
    pub fn new(api_url: &str) -> (Self, mpsc::Receiver<RealtimeEvent>) {
        let (event_tx, event_rx) = mpsc::channel(256);
        let start_instant = Instant::now();

        (
            Self {
                api_url: api_url.to_string(),
                connected: Arc::new(AtomicBool::new(false)),
                consecutive_failures: Arc::new(AtomicU32::new(0)),
                reconnect_attempts: Arc::new(AtomicU32::new(0)),
                last_message_time_ms: Arc::new(AtomicU64::new(0)),
                start_instant,
                event_tx,
                shutdown_tx: None,
                reconnect_now_tx: None,
                auth_token: None,
            },
            event_rx,
        )
    }

    /// Create connection with authentication token
    pub fn with_auth(api_url: &str, auth_token: &str) -> (Self, mpsc::Receiver<RealtimeEvent>) {
        let (mut conn, rx) = Self::new(api_url);
        conn.auth_token = Some(auth_token.to_string());
        (conn, rx)
    }

    /// Check if connected
    pub fn is_connected(&self) -> bool {
        self.connected.load(Ordering::Relaxed)
    }

    /// Get connection health metrics
    pub fn health(&self) -> ConnectionHealth {
        let last_msg_time = self.last_message_time_ms.load(Ordering::Relaxed);
        let current_time = self.start_instant.elapsed().as_millis() as u64;
        let last_message_age_ms = if last_msg_time > 0 {
            current_time.saturating_sub(last_msg_time)
        } else {
            // No message received yet
            current_time
        };

        ConnectionHealth {
            connected: self.connected.load(Ordering::Relaxed),
            consecutive_failures: self.consecutive_failures.load(Ordering::Relaxed),
            last_message_age_ms,
            reconnect_attempts: self.reconnect_attempts.load(Ordering::Relaxed),
        }
    }

    /// Record that a message was received (call from message handling)
    pub fn record_message_received(&self) {
        let now = self.start_instant.elapsed().as_millis() as u64;
        self.last_message_time_ms.store(now, Ordering::Relaxed);
    }

    /// Start the WebSocket connection with automatic reconnection
    pub async fn start(&mut self) -> Result<()> {
        info!("Starting real-time connection to {}", self.api_url);

        let (shutdown_tx, shutdown_rx) = mpsc::channel(1);
        let (reconnect_now_tx, reconnect_now_rx) = mpsc::channel(1);
        self.shutdown_tx = Some(shutdown_tx);
        self.reconnect_now_tx = Some(reconnect_now_tx);

        let api_url = self.api_url.clone();
        let connected = self.connected.clone();
        let consecutive_failures = self.consecutive_failures.clone();
        let reconnect_attempts = self.reconnect_attempts.clone();
        let event_tx = self.event_tx.clone();
        let auth_token = self.auth_token.clone();

        tokio::spawn(async move {
            realtime_loop(
                api_url,
                connected,
                consecutive_failures,
                reconnect_attempts,
                event_tx,
                shutdown_rx,
                reconnect_now_rx,
                auth_token,
            )
            .await
        });

        Ok(())
    }

    /// Force immediate reconnection attempt (CLI option: reconnect now)
    /// Resets backoff and immediately attempts to connect
    pub async fn reconnect_now(&self) {
        // Reset reconnect attempts to get minimal backoff
        self.reconnect_attempts.store(0, Ordering::Relaxed);
        self.consecutive_failures.store(0, Ordering::Relaxed);

        // Signal the loop to break out of backoff wait
        if let Some(ref tx) = self.reconnect_now_tx {
            let _ = tx.send(()).await;
        }

        info!("Forced immediate reconnection requested");
    }

    /// Stop the connection gracefully
    pub async fn stop(&mut self) {
        if let Some(tx) = self.shutdown_tx.take() {
            let _ = tx.send(()).await;
        }
        self.connected.store(false, Ordering::Relaxed);
        info!("Real-time connection stopped");
    }
}

/// Calculate reconnection delay with exponential backoff and jitter
fn calculate_backoff(attempt: u32) -> Duration {
    // Base delay with exponential growth
    let base_delay =
        INITIAL_RECONNECT_DELAY_MS as f64 * RECONNECT_MULTIPLIER.powi(attempt.min(10) as i32);

    // Cap at max delay
    let capped_delay = base_delay.min(MAX_RECONNECT_DELAY_MS as f64);

    // Add jitter (random factor between -jitter and +jitter)
    let jitter_factor = 1.0 + (rand_jitter() * RECONNECT_JITTER * 2.0 - RECONNECT_JITTER);
    let final_delay = (capped_delay * jitter_factor) as u64;

    Duration::from_millis(final_delay)
}

/// Simple pseudo-random jitter using time-based seed
fn rand_jitter() -> f64 {
    let nanos = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .subsec_nanos();

    (nanos % 1000) as f64 / 1000.0
}

async fn realtime_loop(
    api_url: String,
    connected: Arc<AtomicBool>,
    consecutive_failures: Arc<AtomicU32>,
    reconnect_attempts: Arc<AtomicU32>,
    event_tx: mpsc::Sender<RealtimeEvent>,
    mut shutdown_rx: mpsc::Receiver<()>,
    mut reconnect_now_rx: mpsc::Receiver<()>,
    auth_token: Option<String>,
) {
    loop {
        // Check for shutdown signal
        if shutdown_rx.try_recv().is_ok() {
            info!("Real-time loop shutting down");
            break;
        }

        let current_attempt = reconnect_attempts.load(Ordering::Relaxed);

        match connect_websocket(&api_url, &connected, &event_tx, &auth_token).await {
            Ok(_) => {
                // Connection was successful and then closed normally
                consecutive_failures.store(0, Ordering::Relaxed);
                reconnect_attempts.store(0, Ordering::Relaxed);
            }
            Err(e) => {
                error!("WebSocket error: {}", e);
                let _ = event_tx.send(RealtimeEvent::Error(e.to_string())).await;

                let failures = consecutive_failures.fetch_add(1, Ordering::Relaxed) + 1;
                reconnect_attempts.fetch_add(1, Ordering::Relaxed);

                // If too many consecutive failures, notify and slow down significantly
                if failures >= MAX_CONSECUTIVE_FAILURES {
                    warn!(
                        "Max consecutive failures ({}) reached, connection degraded",
                        failures
                    );
                    // Reset counter but keep the high backoff
                    consecutive_failures.store(0, Ordering::Relaxed);
                }
            }
        }

        // Update connection state
        connected.store(false, Ordering::Relaxed);
        let _ = event_tx.send(RealtimeEvent::Disconnected).await;

        // Calculate backoff delay
        let delay = calculate_backoff(current_attempt);
        debug!(
            "Reconnecting in {:?} (attempt {})",
            delay,
            current_attempt + 1
        );

        // Wait with the ability to be interrupted by shutdown or reconnect_now
        tokio::select! {
            _ = tokio::time::sleep(delay) => {}
            _ = shutdown_rx.recv() => {
                info!("Shutdown received during backoff");
                break;
            }
            _ = reconnect_now_rx.recv() => {
                info!("Immediate reconnection requested, skipping backoff");
                // Continue immediately to next iteration
            }
        }
    }
}

async fn connect_websocket(
    api_url: &str,
    connected: &Arc<AtomicBool>,
    event_tx: &mpsc::Sender<RealtimeEvent>,
    auth_token: &Option<String>,
) -> Result<()> {
    // Convert HTTP URL to WebSocket URL
    let ws_url = api_url
        .replace("http://", "ws://")
        .replace("https://", "wss://");
    let url = format!("{}/api/colonies/stream", ws_url);

    info!("Connecting to {}", url);

    let (ws_stream, _) = connect_async(&url)
        .await
        .context("Failed to connect to WebSocket")?;

    let (mut write, mut read) = ws_stream.split();

    // Send authentication message
    let subscribe_topics = vec!["colonies", "home", "safety"];
    let auth_msg = if let Some(token) = auth_token {
        serde_json::json!({
            "type": "auth",
            "token": token,
            "subscribe": subscribe_topics
        })
    } else {
        serde_json::json!({
            "type": "auth",
            "token": "hub-local",
            "subscribe": subscribe_topics
        })
    };
    write.send(Message::Text(auth_msg.to_string())).await?;

    connected.store(true, Ordering::Relaxed);
    let _ = event_tx.send(RealtimeEvent::Connected).await;
    info!("WebSocket connected");

    // Set up heartbeat interval
    let mut heartbeat_interval =
        tokio::time::interval(Duration::from_millis(HEARTBEAT_INTERVAL_MS));
    let mut last_pong = std::time::Instant::now();
    let mut awaiting_pong = false;

    loop {
        tokio::select! {
            // Heartbeat tick
            _ = heartbeat_interval.tick() => {
                // Check if we're waiting for a pong and it's been too long
                if awaiting_pong && last_pong.elapsed() > Duration::from_millis(HEARTBEAT_TIMEOUT_MS) {
                    warn!("Heartbeat timeout - no pong received");
                    break;
                }

                // Send ping
                if let Err(e) = write.send(Message::Ping(vec![])).await {
                    error!("Failed to send ping: {}", e);
                    break;
                }
                awaiting_pong = true;
                debug!("Sent heartbeat ping");
            }

            // Message from server
            msg = read.next() => {
                match msg {
                    Some(Ok(Message::Text(text))) => {
                        if let Ok(json) = serde_json::from_str::<serde_json::Value>(&text) {
                            handle_message(&json, event_tx).await;
                        }
                    }
                    Some(Ok(Message::Pong(_))) => {
                        awaiting_pong = false;
                        last_pong = std::time::Instant::now();
                        debug!("Received pong");
                    }
                    Some(Ok(Message::Ping(data))) => {
                        // Respond to server pings
                        if let Err(e) = write.send(Message::Pong(data)).await {
                            error!("Failed to send pong: {}", e);
                            break;
                        }
                    }
                    Some(Ok(Message::Close(frame))) => {
                        if let Some(f) = frame {
                            info!("WebSocket closed by server: {} - {}", f.code, f.reason);
                        } else {
                            info!("WebSocket closed by server");
                        }
                        break;
                    }
                    Some(Err(e)) => {
                        error!("WebSocket error: {}", e);
                        break;
                    }
                    None => {
                        info!("WebSocket stream ended");
                        break;
                    }
                    _ => {}
                }
            }
        }
    }

    connected.store(false, Ordering::Relaxed);
    Ok(())
}

async fn handle_message(json: &serde_json::Value, event_tx: &mpsc::Sender<RealtimeEvent>) {
    let msg_type = json.get("type").and_then(|v| v.as_str()).unwrap_or("");

    match msg_type {
        "state_sync" | "state" => {
            let state = KagamiState {
                connected: true,
                safety_score: json.get("safety_score").and_then(|v| v.as_f64()),
                active_colonies: json
                    .get("active_colonies")
                    .and_then(|v| v.as_array())
                    .map(|a| {
                        a.iter()
                            .filter_map(|v| v.as_str().map(String::from))
                            .collect()
                    })
                    .unwrap_or_default(),
                home_status: None,
            };
            let _ = event_tx.send(RealtimeEvent::StateUpdate(state)).await;
        }

        "colony_activity" => {
            let colony = json
                .get("colony")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            let action = json
                .get("action")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            let _ = event_tx
                .send(RealtimeEvent::ColonyActivity { colony, action })
                .await;
        }

        "home_update" => {
            let state = HomeState {
                movie_mode: json
                    .get("movie_mode")
                    .and_then(|v| v.as_bool())
                    .unwrap_or(false),
                fireplace_on: json
                    .get("fireplace")
                    .and_then(|v| v.as_bool())
                    .unwrap_or(false),
                occupied_rooms: json
                    .get("occupied_rooms")
                    .and_then(|v| v.as_array())
                    .map(|a| {
                        a.iter()
                            .filter_map(|v| v.as_str().map(String::from))
                            .collect()
                    })
                    .unwrap_or_default(),
            };
            let _ = event_tx.send(RealtimeEvent::HomeUpdate(state)).await;
        }

        "safety_update" => {
            if let Some(h_x) = json.get("h_x").and_then(|v| v.as_f64()) {
                let _ = event_tx.send(RealtimeEvent::SafetyUpdate { h_x }).await;
            }
        }

        "auth_success" => {
            info!("WebSocket authentication successful");
        }

        "auth_error" => {
            let msg = json
                .get("message")
                .and_then(|v| v.as_str())
                .unwrap_or("Authentication failed");
            error!("WebSocket authentication failed: {}", msg);
            let _ = event_tx.send(RealtimeEvent::Error(msg.to_string())).await;
        }

        // Orb interaction from another client - flash the LED ring
        "orb_interaction" => {
            let interaction = OrbInteraction {
                client: json
                    .get("client")
                    .and_then(|v| v.as_str())
                    .unwrap_or("unknown")
                    .to_string(),
                action: json
                    .get("action")
                    .and_then(|v| v.as_str())
                    .unwrap_or("tap")
                    .to_string(),
                context: json
                    .get("context")
                    .and_then(|v| v.as_object())
                    .map(|obj| {
                        obj.iter()
                            .filter_map(|(k, v)| {
                                v.as_str().map(|s| (k.clone(), s.to_string()))
                            })
                            .collect()
                    })
                    .unwrap_or_default(),
            };
            info!(
                "🔮 Orb interaction from {}: {}",
                interaction.client, interaction.action
            );
            let _ = event_tx.send(RealtimeEvent::OrbInteraction(interaction)).await;
        }

        // Orb state changed - update LED colors
        "orb_state" | "orb_state_changed" => {
            let orb_state = OrbState {
                active_colony: json
                    .get("active_colony")
                    .and_then(|v| v.as_str())
                    .map(String::from),
                activity: json
                    .get("activity")
                    .and_then(|v| v.as_str())
                    .unwrap_or("idle")
                    .to_string(),
                safety_score: json
                    .get("safety_score")
                    .and_then(|v| v.as_f64())
                    .unwrap_or(1.0),
                color_hex: json
                    .get("color")
                    .and_then(|v| v.get("hex"))
                    .and_then(|v| v.as_str())
                    .unwrap_or("#E0E0E0")
                    .to_string(),
            };
            debug!("🔮 Orb state: {} ({:?})", orb_state.activity, orb_state.active_colony);
            let _ = event_tx.send(RealtimeEvent::OrbStateChanged(orb_state)).await;
        }

        "error" => {
            let msg = json
                .get("message")
                .and_then(|v| v.as_str())
                .unwrap_or("Unknown error");
            warn!("Server error: {}", msg);
            let _ = event_tx.send(RealtimeEvent::Error(msg.to_string())).await;
        }

        "pong" => {
            // Server-level pong (in addition to WebSocket-level)
            debug!("Received server pong");
        }

        _ => {
            debug!("Unknown message type: {}", msg_type);
        }
    }
}

/*
 * 鏡
 * η → s → μ → a → η′
 * Real-time is the heartbeat.
 */
