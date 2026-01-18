//! Real-Time Integration — WebSocket + SSE
//!
//! Provides low-latency, bidirectional communication with the Kagami API.
//! Implements the Markov blanket loop: η → s → μ → a → η′
//!
//! Performance targets:
//! - State sync latency: < 50ms
//! - Event propagation: < 100ms
//! - Reconnection: < 1s
//!
//! Colony: Nexus (e₄) × Flow (e₃) → Crystal (e₇)

use anyhow::{Context, Result};
use futures_util::{SinkExt, StreamExt};
use serde::{Deserialize, Serialize};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};
use tauri::{AppHandle, Emitter, Runtime};
use tokio::sync::{broadcast, mpsc, RwLock};
use tokio_tungstenite::{connect_async, tungstenite::Message};
use tracing::{debug, error, info, warn};

const WS_BASE: &str = "wss://ws.awkronos.com";

/// Event batching interval (16ms = 60fps)
const BATCH_INTERVAL_MS: u64 = 16;

/// Initial reconnect delay in milliseconds
const RECONNECT_DELAY_BASE_MS: u64 = 1000;
/// Maximum reconnect delay (30 seconds)
const RECONNECT_DELAY_MAX_MS: u64 = 30_000;
/// Jitter factor (0.0-1.0) to prevent thundering herd
const RECONNECT_JITTER: f64 = 0.3;
/// Heartbeat/ping interval
const HEARTBEAT_INTERVAL_MS: u64 = 5000;
/// Maximum consecutive reconnect attempts before longer pause
const MAX_RECONNECT_ATTEMPTS: u32 = 10;

// ═══════════════════════════════════════════════════════════════
// STATE TYPES
// ═══════════════════════════════════════════════════════════════

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct KagamiState {
    pub connected: bool,
    pub safety_score: Option<f64>,
    pub active_colonies: Vec<String>,
    pub api_uptime_ms: Option<u64>,
    pub home_status: Option<HomeState>,
    pub training_status: Option<TrainingState>,
    pub health_status: Option<HealthState>,
    pub latency_ms: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct HealthState {
    pub heart_rate: Option<f64>,
    pub resting_heart_rate: Option<f64>,
    pub hrv: Option<f64>,
    pub steps: Option<i32>,
    pub active_calories: Option<i32>,
    pub exercise_minutes: Option<i32>,
    pub blood_oxygen: Option<f64>,
    pub sleep_hours: Option<f64>,
    pub last_sync: Option<String>,
    pub source: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct HomeState {
    pub movie_mode: bool,
    pub fireplace_on: bool,
    pub occupied_rooms: Vec<String>,
    pub temperature: Option<f64>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct TrainingState {
    pub running: bool,
    pub epoch: i32,
    pub step: i32,
    pub loss: Option<f64>,
    pub progress: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ColonyActivity {
    pub colony: String,
    pub action: String,
    pub timestamp_ms: u64,
    pub metadata: Option<serde_json::Value>,
}

// ═══════════════════════════════════════════════════════════════
// REAL-TIME CLIENT
// ═══════════════════════════════════════════════════════════════

pub struct RealtimeClient {
    state: Arc<RwLock<KagamiState>>,
    event_tx: broadcast::Sender<ColonyActivity>,
    connected: Arc<AtomicBool>,
    last_latency_ms: Arc<AtomicU64>,
    shutdown_tx: Option<mpsc::Sender<()>>,
}

impl RealtimeClient {
    pub fn new() -> Self {
        let (event_tx, _) = broadcast::channel(256);

        Self {
            state: Arc::new(RwLock::new(KagamiState {
                connected: false,
                safety_score: None,
                active_colonies: vec![],
                api_uptime_ms: None,
                home_status: None,
                training_status: None,
                health_status: None,
                latency_ms: 0,
            })),
            event_tx,
            connected: Arc::new(AtomicBool::new(false)),
            last_latency_ms: Arc::new(AtomicU64::new(0)),
            shutdown_tx: None,
        }
    }

    /// Get the current state
    pub async fn get_state(&self) -> KagamiState {
        self.state.read().await.clone()
    }

    /// Check if connected
    pub fn is_connected(&self) -> bool {
        self.connected.load(Ordering::Relaxed)
    }

    /// Get current latency
    pub fn get_latency(&self) -> u64 {
        self.last_latency_ms.load(Ordering::Relaxed)
    }

    /// Subscribe to colony events
    pub fn subscribe_events(&self) -> broadcast::Receiver<ColonyActivity> {
        self.event_tx.subscribe()
    }

    /// Start the real-time connection
    pub async fn start<R: Runtime>(&mut self, app: AppHandle<R>) -> Result<()> {
        info!("Starting real-time connection...");

        let (shutdown_tx, shutdown_rx) = mpsc::channel(1);
        self.shutdown_tx = Some(shutdown_tx);

        let state = self.state.clone();
        let event_tx = self.event_tx.clone();
        let connected = self.connected.clone();
        let last_latency = self.last_latency_ms.clone();

        // Spawn WebSocket handler
        tokio::spawn(async move {
            realtime_loop(
                app,
                state,
                event_tx,
                connected,
                last_latency,
                shutdown_rx,
            ).await
        });

        Ok(())
    }

    /// Stop the real-time connection
    pub async fn stop(&mut self) {
        if let Some(tx) = self.shutdown_tx.take() {
            let _ = tx.send(()).await;
        }
        self.connected.store(false, Ordering::Relaxed);
    }
}

// ═══════════════════════════════════════════════════════════════
// REAL-TIME LOOP
// ═══════════════════════════════════════════════════════════════

async fn realtime_loop<R: Runtime>(
    app: AppHandle<R>,
    state: Arc<RwLock<KagamiState>>,
    event_tx: broadcast::Sender<ColonyActivity>,
    connected: Arc<AtomicBool>,
    last_latency: Arc<AtomicU64>,
    mut shutdown_rx: mpsc::Receiver<()>,
) {
    let mut reconnect_attempts = 0;

    loop {
        // Check for shutdown
        if shutdown_rx.try_recv().is_ok() {
            info!("Real-time loop shutting down");
            break;
        }

        // Attempt connection
        match connect_websocket(&state, &event_tx, &connected, &last_latency, &app).await {
            Ok(_) => {
                reconnect_attempts = 0;
            }
            Err(e) => {
                error!("WebSocket error: {}", e);
                connected.store(false, Ordering::Relaxed);

                // Emit disconnected state
                let _ = app.emit("kagami-state", serde_json::json!({
                    "connected": false,
                    "error": e.to_string()
                }));
            }
        }

        // Exponential backoff with jitter before reconnect
        reconnect_attempts += 1;

        let delay = if reconnect_attempts > MAX_RECONNECT_ATTEMPTS {
            warn!(
                "Max reconnect attempts ({}) reached, resetting counter and using max delay",
                MAX_RECONNECT_ATTEMPTS
            );
            reconnect_attempts = 0;
            RECONNECT_DELAY_MAX_MS
        } else {
            // Calculate exponential backoff: base * 2^attempts, capped at max
            let exponential_delay =
                RECONNECT_DELAY_BASE_MS * (1u64 << reconnect_attempts.min(6));
            exponential_delay.min(RECONNECT_DELAY_MAX_MS)
        };

        // Add jitter to prevent thundering herd
        let jitter_range = (delay as f64 * RECONNECT_JITTER) as u64;
        let jitter = if jitter_range > 0 {
            use std::time::{SystemTime, UNIX_EPOCH};
            // Use unwrap_or_default to handle potential clock issues gracefully
            let seed = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap_or_default()
                .subsec_nanos() as u64;
            seed % jitter_range
        } else {
            0
        };
        let final_delay = delay + jitter;

        info!(
            "Reconnecting in {}ms (attempt {}, base {}ms + jitter {}ms)",
            final_delay, reconnect_attempts, delay, jitter
        );
        tokio::time::sleep(Duration::from_millis(final_delay)).await;
    }
}

async fn connect_websocket<R: Runtime>(
    state: &Arc<RwLock<KagamiState>>,
    event_tx: &broadcast::Sender<ColonyActivity>,
    connected: &Arc<AtomicBool>,
    last_latency: &Arc<AtomicU64>,
    app: &AppHandle<R>,
) -> Result<()> {
    let url = format!("{}/api/colonies/stream", WS_BASE);
    info!("Connecting to {}", url);

    let (ws_stream, _) = connect_async(&url)
        .await
        .context("Failed to connect to WebSocket")?;

    let (mut write, mut read) = ws_stream.split();

    // Send initial auth
    let auth_msg = serde_json::json!({
        "type": "auth",
        "token": "local-dev",
        "subscribe": ["colonies", "training", "home", "safety"]
    });
    write.send(Message::Text(auth_msg.to_string())).await?;

    connected.store(true, Ordering::Relaxed);
    info!("WebSocket connected");

    // Emit connected state
    let _ = app.emit("kagami-connected", serde_json::json!({"connected": true}));

    let mut heartbeat_interval = tokio::time::interval(Duration::from_millis(HEARTBEAT_INTERVAL_MS));

    loop {
        tokio::select! {
            // Heartbeat
            _ = heartbeat_interval.tick() => {
                let ping_start = Instant::now();
                if let Err(e) = write.send(Message::Ping(vec![])).await {
                    error!("Failed to send ping: {}", e);
                    break;
                }
                // Latency measured on pong response
                last_latency.store(ping_start.elapsed().as_millis() as u64, Ordering::Relaxed);
            }

            // Incoming messages
            msg = read.next() => {
                match msg {
                    Some(Ok(Message::Text(text))) => {
                        if let Err(e) = handle_message(&text, state, event_tx, app).await {
                            warn!("Failed to handle message: {}", e);
                        }
                    }
                    Some(Ok(Message::Pong(_))) => {
                        // Update latency
                        let mut s = state.write().await;
                        s.latency_ms = last_latency.load(Ordering::Relaxed);
                    }
                    Some(Ok(Message::Close(_))) => {
                        info!("WebSocket closed by server");
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
    let _ = app.emit("kagami-disconnected", serde_json::json!({}));

    Ok(())
}

async fn handle_message<R: Runtime>(
    text: &str,
    state: &Arc<RwLock<KagamiState>>,
    event_tx: &broadcast::Sender<ColonyActivity>,
    app: &AppHandle<R>,
) -> Result<()> {
    let msg: serde_json::Value = serde_json::from_str(text)?;

    let msg_type = msg.get("type").and_then(|v| v.as_str()).unwrap_or("");

    match msg_type {
        "state_sync" | "state" => {
            // Full state update
            let mut s = state.write().await;

            if let Some(safety) = msg.get("safety_score").and_then(|v| v.as_f64()) {
                s.safety_score = Some(safety);
            }

            if let Some(colonies) = msg.get("active_colonies").and_then(|v| v.as_array()) {
                s.active_colonies = colonies
                    .iter()
                    .filter_map(|v| v.as_str().map(String::from))
                    .collect();
            }

            if let Some(uptime) = msg.get("uptime_ms").and_then(|v| v.as_u64()) {
                s.api_uptime_ms = Some(uptime);
            }

            s.connected = true;

            // Emit to frontend
            let _ = app.emit("kagami-state", serde_json::to_value(&*s)?);
        }

        "colony_activity" => {
            // Colony event
            let activity = ColonyActivity {
                colony: msg.get("colony").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                action: msg.get("action").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                timestamp_ms: msg.get("timestamp").and_then(|v| v.as_u64()).unwrap_or(0),
                metadata: msg.get("metadata").cloned(),
            };

            // Update active colonies
            {
                let mut s = state.write().await;
                if !s.active_colonies.contains(&activity.colony) {
                    s.active_colonies.push(activity.colony.clone());
                }
            }

            // Broadcast to subscribers
            let _ = event_tx.send(activity.clone());

            // Emit to frontend
            let _ = app.emit("colony-activity", serde_json::to_value(&activity)?);
        }

        "training_update" => {
            let mut s = state.write().await;
            s.training_status = Some(TrainingState {
                running: msg.get("running").and_then(|v| v.as_bool()).unwrap_or(false),
                epoch: msg.get("epoch").and_then(|v| v.as_i64()).unwrap_or(0) as i32,
                step: msg.get("step").and_then(|v| v.as_i64()).unwrap_or(0) as i32,
                loss: msg.get("loss").and_then(|v| v.as_f64()),
                progress: msg.get("progress").and_then(|v| v.as_f64()).unwrap_or(0.0) as f32,
            });

            let _ = app.emit("training-update", &s.training_status);
        }

        "home_update" => {
            let mut s = state.write().await;
            s.home_status = Some(HomeState {
                movie_mode: msg.get("movie_mode").and_then(|v| v.as_bool()).unwrap_or(false),
                fireplace_on: msg.get("fireplace").and_then(|v| v.as_bool()).unwrap_or(false),
                occupied_rooms: msg.get("occupied_rooms")
                    .and_then(|v| v.as_array())
                    .map(|a| a.iter().filter_map(|v| v.as_str().map(String::from)).collect())
                    .unwrap_or_default(),
                temperature: msg.get("temperature").and_then(|v| v.as_f64()),
            });

            let _ = app.emit("home-update", &s.home_status);
        }

        "safety_update" => {
            let mut s = state.write().await;
            s.safety_score = msg.get("h_x").and_then(|v| v.as_f64());

            let _ = app.emit("safety-update", serde_json::json!({
                "h_x": s.safety_score
            }));
        }

        "heartbeat" | "pong" => {
            debug!("Heartbeat received");
        }

        _ => {
            debug!("Unknown message type: {}", msg_type);
        }
    }

    Ok(())
}

// ═══════════════════════════════════════════════════════════════
// EVENT BATCHER (16ms / 60fps)
// ═══════════════════════════════════════════════════════════════

/// Batches state updates to reduce frontend render load
pub struct EventBatcher {
    pending_state: Arc<RwLock<Option<KagamiState>>>,
    pending_activities: Arc<RwLock<Vec<ColonyActivity>>>,
}

impl EventBatcher {
    pub fn new() -> Self {
        Self {
            pending_state: Arc::new(RwLock::new(None)),
            pending_activities: Arc::new(RwLock::new(Vec::new())),
        }
    }

    /// Queue a state update for batched emission
    pub async fn queue_state(&self, state: KagamiState) {
        let mut pending = self.pending_state.write().await;
        *pending = Some(state);
    }

    /// Queue a colony activity for batched emission
    pub async fn queue_activity(&self, activity: ColonyActivity) {
        let mut activities = self.pending_activities.write().await;
        activities.push(activity);
    }

    /// Start the batch emission loop
    pub fn start<R: Runtime>(&self, app: AppHandle<R>) {
        let pending_state = self.pending_state.clone();
        let pending_activities = self.pending_activities.clone();

        tokio::spawn(async move {
            let mut interval = tokio::time::interval(Duration::from_millis(BATCH_INTERVAL_MS));
            interval.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Skip);

            loop {
                interval.tick().await;

                // Emit batched state update
                {
                    let mut state = pending_state.write().await;
                    if let Some(s) = state.take() {
                        if let Ok(value) = serde_json::to_value(&s) {
                            let _ = app.emit("kagami-state", value);
                        }
                    }
                }

                // Emit batched activities (deduplicated by colony)
                {
                    let mut activities = pending_activities.write().await;
                    if !activities.is_empty() {
                        // Deduplicate: keep only latest activity per colony
                        let mut seen = std::collections::HashMap::new();
                        for activity in activities.drain(..) {
                            seen.insert(activity.colony.clone(), activity);
                        }
                        for (_, activity) in seen {
                            if let Ok(value) = serde_json::to_value(&activity) {
                                let _ = app.emit("colony-activity", value);
                            }
                        }
                    }
                }
            }
        });
    }
}

impl Default for EventBatcher {
    fn default() -> Self {
        Self::new()
    }
}

// Global event batcher
static EVENT_BATCHER: std::sync::OnceLock<EventBatcher> = std::sync::OnceLock::new();

pub fn get_event_batcher() -> &'static EventBatcher {
    EVENT_BATCHER.get_or_init(EventBatcher::new)
}

// ═══════════════════════════════════════════════════════════════
// GLOBAL INSTANCE
// ═══════════════════════════════════════════════════════════════

static REALTIME: std::sync::OnceLock<tokio::sync::RwLock<RealtimeClient>> = std::sync::OnceLock::new();

pub fn get_realtime() -> &'static tokio::sync::RwLock<RealtimeClient> {
    REALTIME.get_or_init(|| tokio::sync::RwLock::new(RealtimeClient::new()))
}

// ═══════════════════════════════════════════════════════════════
// TAURI COMMANDS
// ═══════════════════════════════════════════════════════════════

#[tauri::command]
pub async fn connect_realtime<R: Runtime>(app: AppHandle<R>) -> Result<bool, String> {
    // Start the event batcher (16ms interval for 60fps)
    get_event_batcher().start(app.clone());

    let mut client = get_realtime().write().await;
    client.start(app).await.map_err(|e| e.to_string())?;
    Ok(true)
}

#[tauri::command]
pub async fn disconnect_realtime() -> Result<bool, String> {
    let mut client = get_realtime().write().await;
    client.stop().await;
    Ok(true)
}

#[tauri::command]
pub async fn get_realtime_state() -> Result<KagamiState, String> {
    let client = get_realtime().read().await;
    Ok(client.get_state().await)
}

#[tauri::command]
pub async fn get_realtime_latency() -> Result<u64, String> {
    let client = get_realtime().read().await;
    Ok(client.get_latency())
}

/*
 * 鏡
 * η → s → μ → a → η′
 * Real-time is the heartbeat of the mirror.
 */
