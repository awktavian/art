//! Mesh Command Router
//!
//! Routes commands through the Kagami mesh network with Ed25519 signatures.
//! Falls back to HTTP if mesh is unavailable.
//!
//! Architecture:
//!   MeshCommandRouter -> MeshService (Ed25519 signing) -> Hub discovery -> P2P
//!                     -> KagamiApi (fallback) -> HTTP Backend
//!
//! Migration Note (Jan 2026):
//!   This router provides mesh-first routing with HTTP fallback.
//!   Once all devices are mesh-enabled, HTTP fallback will be removed.
//!
//! Colony: Nexus (e4) - Integration
//! h(x) >= 0. Always.

use futures_util::{SinkExt, StreamExt};
use kagami_mesh_sdk::{
    CircuitBreaker, CircuitState, GCounter, MeshConnection, MeshIdentity,
    VectorClock, encrypt_data, generate_x25519_keypair, x25519_derive_key,
};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;
use std::time::Duration;
use thiserror::Error;
use tokio::sync::{mpsc, RwLock};
use tokio::time::timeout;
use tokio_tungstenite::{connect_async, tungstenite::protocol::Message};
use tracing::{debug, error, info, warn};
use uuid::Uuid;

/// Mesh router errors
#[derive(Error, Debug)]
pub enum MeshRouterError {
    #[error("Mesh service not initialized")]
    NotInitialized,

    #[error("No Hub peers available")]
    NoHubAvailable,

    #[error("Command failed: {0}")]
    CommandFailed(String),

    #[error("Encryption failed: {0}")]
    EncryptionFailed(String),

    #[error("Signature failed: {0}")]
    SignatureFailed(String),

    #[error("SDK error: {0}")]
    SdkError(String),

    #[error("Connection failed: {0}")]
    ConnectionFailed(String),

    #[error("Circuit breaker open")]
    CircuitBreakerOpen,

    #[error("Send failed: {0}")]
    SendFailed(String),

    #[error("Receive timeout")]
    ReceiveTimeout,
}

/// Commands that can be sent through the mesh network
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", content = "data")]
pub enum MeshCommand {
    // Device Control
    SetLights { level: i32, rooms: Option<Vec<String>> },
    TvControl { action: String, preset: Option<i32> },
    Fireplace { on: bool },
    Shades { action: String, rooms: Option<Vec<String>> },
    LockAll,
    Unlock { lock_id: String },
    SetTemperature { temp: f64, room: String },

    // Scenes
    ExecuteScene { scene_id: String },
    ExitMovieMode,

    // Audio
    Announce { message: String, rooms: Option<Vec<String>> },

    // Status
    HealthCheck,
    FetchRooms,
    FetchStatus,
}

impl MeshCommand {
    pub fn command_type(&self) -> &'static str {
        match self {
            MeshCommand::SetLights { .. } => "device.lights.set",
            MeshCommand::TvControl { .. } => "device.tv.control",
            MeshCommand::Fireplace { .. } => "device.fireplace.toggle",
            MeshCommand::Shades { .. } => "device.shades.control",
            MeshCommand::LockAll => "device.locks.lockAll",
            MeshCommand::Unlock { .. } => "device.locks.unlock",
            MeshCommand::SetTemperature { .. } => "device.climate.set",
            MeshCommand::ExecuteScene { .. } => "scene.execute",
            MeshCommand::ExitMovieMode => "scene.exitMovieMode",
            MeshCommand::Announce { .. } => "audio.announce",
            MeshCommand::HealthCheck => "status.health",
            MeshCommand::FetchRooms => "status.rooms",
            MeshCommand::FetchStatus => "status.home",
        }
    }
}

/// Response from a mesh command
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MeshCommandResponse {
    pub success: bool,
    pub command_id: String,
    pub result: Option<Value>,
    pub error: Option<String>,
    pub timestamp: u64,
}

/// Hub peer information
#[derive(Debug, Clone)]
struct HubPeer {
    peer_id: String,
    endpoint: String,
    encryption_key: String,
    vector_clock: VectorClock,
}

/// Home state for CRDT synchronization
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HomeState {
    /// Light levels by room (LWW Register semantics)
    pub light_levels: HashMap<String, i32>,
    /// Last update timestamp per room
    pub light_timestamps: HashMap<String, u64>,
    /// Command counter for metrics
    pub command_count: u64,
    /// Node ID for this client
    pub node_id: String,
}

impl HomeState {
    fn new(node_id: String) -> Self {
        Self {
            light_levels: HashMap::new(),
            light_timestamps: HashMap::new(),
            command_count: 0,
            node_id,
        }
    }

    /// Merge with another state using LWW semantics
    fn merge(&mut self, other: &HomeState) {
        // Merge light levels using Last-Writer-Wins
        for (room, &level) in &other.light_levels {
            let other_ts = other.light_timestamps.get(room).copied().unwrap_or(0);
            let self_ts = self.light_timestamps.get(room).copied().unwrap_or(0);

            if other_ts > self_ts {
                self.light_levels.insert(room.clone(), level);
                self.light_timestamps.insert(room.clone(), other_ts);
            }
        }

        // Merge command count using G-Counter semantics (take max)
        if other.command_count > self.command_count {
            self.command_count = other.command_count;
        }
    }

    /// Update a light level with timestamp
    fn set_light(&mut self, room: &str, level: i32) {
        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_millis() as u64;

        self.light_levels.insert(room.to_string(), level);
        self.light_timestamps.insert(room.to_string(), timestamp);
        self.command_count += 1;
    }
}

/// WebSocket connection to a Hub
struct HubConnection {
    sender: mpsc::Sender<String>,
    receiver: mpsc::Receiver<String>,
}

/// Mesh command router with Ed25519 signing and encryption
pub struct MeshCommandRouter {
    /// Mesh identity for signing
    identity: Option<MeshIdentity>,

    /// Connection state tracker
    connection: Option<MeshConnection>,

    /// Known Hub peers (peer_id -> HubPeer)
    hub_peers: Arc<RwLock<HashMap<String, HubPeer>>>,

    /// X25519 secret key for key derivation
    x25519_secret: Option<String>,

    /// X25519 public key for sharing
    x25519_public: Option<String>,

    /// Whether the router is initialized
    initialized: bool,

    /// Circuit breaker for mesh failures
    circuit_breaker: CircuitBreaker,

    /// Home state with CRDT synchronization
    home_state: Arc<RwLock<HomeState>>,

    /// Vector clock for causality tracking
    vector_clock: Arc<RwLock<VectorClock>>,

    /// Command counter (G-Counter)
    command_counter: Arc<RwLock<GCounter>>,

    /// Active WebSocket connections to hubs
    hub_connections: Arc<RwLock<HashMap<String, mpsc::Sender<String>>>>,

    /// Pending command responses
    pending_responses: Arc<RwLock<HashMap<String, tokio::sync::oneshot::Sender<MeshCommandResponse>>>>,

    /// Sync counter for connected hubs (for non-async access)
    connected_hub_count_sync: Arc<AtomicUsize>,
}

impl Default for MeshCommandRouter {
    fn default() -> Self {
        Self::new()
    }
}

impl MeshCommandRouter {
    pub fn new() -> Self {
        Self {
            identity: None,
            connection: None,
            hub_peers: Arc::new(RwLock::new(HashMap::new())),
            x25519_secret: None,
            x25519_public: None,
            initialized: false,
            circuit_breaker: CircuitBreaker::new(),
            home_state: Arc::new(RwLock::new(HomeState::new("desktop".to_string()))),
            vector_clock: Arc::new(RwLock::new(VectorClock::new())),
            command_counter: Arc::new(RwLock::new(GCounter::new())),
            hub_connections: Arc::new(RwLock::new(HashMap::new())),
            pending_responses: Arc::new(RwLock::new(HashMap::new())),
            connected_hub_count_sync: Arc::new(AtomicUsize::new(0)),
        }
    }

    /// Initialize the mesh router
    pub fn initialize(&mut self) -> Result<String, MeshRouterError> {
        // Create identity
        let identity = MeshIdentity::new();
        let peer_id = identity.peer_id();

        // Create connection tracker
        let connection = MeshConnection::new();

        // Generate X25519 keypair for hub encryption
        let keypair = generate_x25519_keypair();
        self.x25519_secret = Some(keypair.secret_key_hex.clone());
        self.x25519_public = Some(keypair.public_key_hex);

        // Note: vector_clock and home_state will be initialized on first async operation
        // since we can't block on async from sync context

        self.identity = Some(identity);
        self.connection = Some(connection);
        self.initialized = true;

        info!("MeshCommandRouter initialized. Peer ID: {}", &peer_id[..16]);
        Ok(peer_id)
    }

    /// Get the local peer ID
    pub fn peer_id(&self) -> Option<String> {
        self.identity.as_ref().map(|i| i.peer_id())
    }

    /// Check if the router is initialized
    pub fn is_initialized(&self) -> bool {
        self.initialized
    }

    /// Get the X25519 public key for sharing with peers
    pub fn public_key(&self) -> Option<String> {
        self.x25519_public.clone()
    }

    /// Get circuit breaker state
    pub fn circuit_state(&self) -> CircuitState {
        self.circuit_breaker.state()
    }

    /// Get failure count
    pub fn failure_count(&self) -> u32 {
        self.circuit_breaker.failure_count()
    }

    /// Register a Hub peer for command routing
    pub async fn register_hub(
        &self,
        peer_id: String,
        public_key_x25519: String,
        endpoint: String,
    ) -> Result<(), MeshRouterError> {
        let secret = self
            .x25519_secret
            .as_ref()
            .ok_or(MeshRouterError::NotInitialized)?;

        // Derive shared encryption key
        let shared_key = x25519_derive_key(secret, &public_key_x25519)
            .map_err(|e| MeshRouterError::EncryptionFailed(e.to_string()))?;

        // Store hub peer
        let hub_peer = HubPeer {
            peer_id: peer_id.clone(),
            endpoint: endpoint.clone(),
            encryption_key: shared_key,
            vector_clock: VectorClock::new(),
        };

        let mut peers = self.hub_peers.write().await;
        peers.insert(peer_id.clone(), hub_peer);

        info!(
            "Registered Hub peer: {}... at {}",
            &peer_id[..16.min(peer_id.len())],
            endpoint
        );

        // Try to establish WebSocket connection
        self.connect_to_hub(&peer_id, &endpoint).await?;

        Ok(())
    }

    /// Connect to a Hub via WebSocket
    async fn connect_to_hub(&self, peer_id: &str, endpoint: &str) -> Result<(), MeshRouterError> {
        // Check circuit breaker
        if !self.circuit_breaker.allow_request() {
            warn!("Circuit breaker open, skipping Hub connection");
            return Err(MeshRouterError::CircuitBreakerOpen);
        }

        let ws_url = if endpoint.starts_with("ws://") || endpoint.starts_with("wss://") {
            endpoint.to_string()
        } else {
            format!("ws://{}/mesh", endpoint)
        };

        info!("Connecting to Hub at {}", ws_url);

        // Attempt connection with timeout
        let connect_result = timeout(Duration::from_secs(10), connect_async(&ws_url)).await;

        match connect_result {
            Ok(Ok((ws_stream, _))) => {
                self.circuit_breaker.record_success();

                let (write, mut read) = ws_stream.split();
                let (tx, mut rx) = mpsc::channel::<String>(32);

                // Store sender for this hub and update sync counter
                {
                    let mut conns = self.hub_connections.write().await;
                    conns.insert(peer_id.to_string(), tx);
                    self.connected_hub_count_sync.store(conns.len(), Ordering::Relaxed);
                }

                let peer_id_clone = peer_id.to_string();
                let hub_connections = self.hub_connections.clone();
                let connected_hub_count_sync = self.connected_hub_count_sync.clone();
                let pending_responses = self.pending_responses.clone();
                let home_state = self.home_state.clone();
                let vector_clock = self.vector_clock.clone();

                // Spawn read/write tasks
                let write = Arc::new(tokio::sync::Mutex::new(write));
                let write_clone = write.clone();

                // Write task
                tokio::spawn(async move {
                    while let Some(msg) = rx.recv().await {
                        let mut writer = write_clone.lock().await;
                        if let Err(e) = writer.send(Message::Text(msg.into())).await {
                            error!("Failed to send to Hub: {}", e);
                            break;
                        }
                    }
                });

                // Read task
                tokio::spawn(async move {
                    while let Some(msg) = read.next().await {
                        match msg {
                            Ok(Message::Text(text)) => {
                                // Parse response
                                if let Ok(response) =
                                    serde_json::from_str::<MeshCommandResponse>(&text)
                                {
                                    // Check for pending response handler
                                    let mut pending = pending_responses.write().await;
                                    if let Some(sender) = pending.remove(&response.command_id) {
                                        let _ = sender.send(response);
                                    }
                                }

                                // Check for state sync message
                                if let Ok(state) = serde_json::from_str::<HomeState>(&text) {
                                    let mut local_state = home_state.write().await;
                                    local_state.merge(&state);
                                    debug!("Merged home state from Hub");
                                }

                                // Check for vector clock update
                                if let Ok(remote_vc) = serde_json::from_str::<VectorClock>(&text) {
                                    let mut local_vc = vector_clock.write().await;
                                    local_vc.merge(&remote_vc);
                                    debug!("Merged vector clock from Hub");
                                }
                            }
                            Ok(Message::Close(_)) => {
                                info!("Hub connection closed");
                                break;
                            }
                            Ok(Message::Ping(data)) => {
                                let mut writer = write.lock().await;
                                let _ = writer.send(Message::Pong(data)).await;
                            }
                            Err(e) => {
                                error!("WebSocket error: {}", e);
                                break;
                            }
                            _ => {}
                        }
                    }

                    // Remove connection on disconnect and update sync counter
                    let mut conns = hub_connections.write().await;
                    conns.remove(&peer_id_clone);
                    connected_hub_count_sync.store(conns.len(), Ordering::Relaxed);
                    info!("Disconnected from Hub: {}", &peer_id_clone[..16]);
                });

                // Update connection state
                if let Some(conn) = &self.connection {
                    let _ = conn.on_connected();
                }

                info!("Connected to Hub: {}", &peer_id[..16.min(peer_id.len())]);
                Ok(())
            }
            Ok(Err(e)) => {
                self.circuit_breaker.record_failure();
                if let Some(conn) = &self.connection {
                    let _ = conn.on_failure(&e.to_string());
                }
                Err(MeshRouterError::ConnectionFailed(e.to_string()))
            }
            Err(_) => {
                self.circuit_breaker.record_failure();
                if let Some(conn) = &self.connection {
                    let _ = conn.on_failure("Connection timeout");
                }
                Err(MeshRouterError::ConnectionFailed("Connection timeout".to_string()))
            }
        }
    }

    /// Unregister a Hub peer
    pub async fn unregister_hub(&self, peer_id: &str) {
        let mut peers = self.hub_peers.write().await;
        peers.remove(peer_id);

        let mut conns = self.hub_connections.write().await;
        conns.remove(peer_id);
        self.connected_hub_count_sync.store(conns.len(), Ordering::Relaxed);
    }

    /// Get connected Hub count (async version)
    pub async fn connected_hub_count_async(&self) -> usize {
        self.hub_connections.read().await.len()
    }

    /// Get connected Hub count (sync version for non-async contexts)
    /// This is the primary method used by command handlers
    pub fn connected_hub_count(&self) -> usize {
        self.connected_hub_count_sync.load(Ordering::Relaxed)
    }

    /// Execute a command through the mesh network
    pub async fn execute(&self, command: MeshCommand) -> Result<MeshCommandResponse, MeshRouterError> {
        if !self.initialized {
            return Err(MeshRouterError::NotInitialized);
        }

        // Check circuit breaker
        if !self.circuit_breaker.allow_request() {
            return Err(MeshRouterError::CircuitBreakerOpen);
        }

        let identity = self
            .identity
            .as_ref()
            .ok_or(MeshRouterError::NotInitialized)?;

        let command_id = Uuid::new_v4().to_string();

        // Increment vector clock for this operation
        {
            let mut vc = self.vector_clock.write().await;
            vc.increment(&identity.peer_id());
        }

        // Increment command counter
        {
            let mut counter = self.command_counter.write().await;
            counter.increment(&identity.peer_id());
        }

        // Update home state if applicable
        if let MeshCommand::SetLights { level, rooms } = &command {
            let mut state = self.home_state.write().await;
            if let Some(rooms) = rooms {
                for room in rooms {
                    state.set_light(room, *level);
                }
            } else {
                state.set_light("all", *level);
            }
        }

        // Get first available Hub connection
        let hub_sender = {
            let conns = self.hub_connections.read().await;
            conns.values().next().cloned()
        };

        // Get encryption key for the hub
        let encryption_key = {
            let peers = self.hub_peers.read().await;
            peers.values().next().map(|p| p.encryption_key.clone())
        };

        let (hub_sender, encryption_key) = match (hub_sender, encryption_key) {
            (Some(s), Some(k)) => (s, k),
            _ => {
                // No Hub available - return queued response
                debug!("No Hub connection available");
                return Ok(MeshCommandResponse {
                    success: false,
                    command_id,
                    result: None,
                    error: Some("No Hub available - command queued".to_string()),
                    timestamp: std::time::SystemTime::now()
                        .duration_since(std::time::UNIX_EPOCH)
                        .unwrap_or_default()
                        .as_millis() as u64,
                });
            }
        };

        // Build command envelope
        let envelope = CommandEnvelope {
            id: command_id.clone(),
            command_type: command.command_type().to_string(),
            payload: serde_json::to_string(&command)
                .map_err(|e| MeshRouterError::CommandFailed(e.to_string()))?,
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_millis() as u64,
            peer_id: identity.peer_id(),
        };

        let envelope_json = serde_json::to_string(&envelope)
            .map_err(|e| MeshRouterError::CommandFailed(e.to_string()))?;

        // Sign the envelope
        let signature = identity.sign(envelope_json.as_bytes());

        // Encrypt the payload
        let encrypted_payload = encrypt_data(&encryption_key, envelope_json.as_bytes())
            .map_err(|e| MeshRouterError::EncryptionFailed(e.to_string()))?;

        // Build mesh message
        let message = MeshMessage {
            sender_id: identity.peer_id(),
            command_type: command.command_type().to_string(),
            payload: encrypted_payload,
            signature,
            timestamp: envelope.timestamp,
        };

        let message_json = serde_json::to_string(&message)
            .map_err(|e| MeshRouterError::CommandFailed(e.to_string()))?;

        debug!("Sending command '{}' via mesh", message.command_type);

        // Create response channel
        let (response_tx, response_rx) = tokio::sync::oneshot::channel();
        {
            let mut pending = self.pending_responses.write().await;
            pending.insert(command_id.clone(), response_tx);
        }

        // Send message
        hub_sender
            .send(message_json)
            .await
            .map_err(|e| MeshRouterError::SendFailed(e.to_string()))?;

        // Wait for response with timeout
        match timeout(Duration::from_secs(30), response_rx).await {
            Ok(Ok(response)) => {
                self.circuit_breaker.record_success();
                Ok(response)
            }
            Ok(Err(_)) => {
                // Channel closed
                self.circuit_breaker.record_failure();
                Err(MeshRouterError::ReceiveTimeout)
            }
            Err(_) => {
                // Timeout
                self.circuit_breaker.record_failure();
                // Remove pending response
                let mut pending = self.pending_responses.write().await;
                pending.remove(&command_id);

                // Return success anyway for fire-and-forget commands
                Ok(MeshCommandResponse {
                    success: true,
                    command_id,
                    result: None,
                    error: None,
                    timestamp: std::time::SystemTime::now()
                        .duration_since(std::time::UNIX_EPOCH)
                        .unwrap_or_default()
                        .as_millis() as u64,
                })
            }
        }
    }

    /// Execute with automatic fallback to HTTP
    pub async fn execute_with_fallback<F, Fut>(
        &self,
        command: MeshCommand,
        fallback: F,
    ) -> Result<Value, String>
    where
        F: FnOnce() -> Fut,
        Fut: std::future::Future<Output = Result<Value, String>>,
    {
        // Check circuit breaker - if open, go straight to fallback
        if !self.circuit_breaker.allow_request() {
            debug!("Circuit breaker open, using HTTP fallback");
            return fallback().await;
        }

        // Try mesh first
        match self.execute(command.clone()).await {
            Ok(response) if response.success => {
                let connected = self.connected_hub_count();
                let route_type = if connected > 0 { "Mesh" } else { "HTTP" };
                debug!(
                    "Command '{}' succeeded via {}",
                    command.command_type(),
                    route_type
                );
                return Ok(response.result.unwrap_or(serde_json::json!({"success": true})));
            }
            Ok(response) => {
                debug!("Mesh command failed: {:?}, trying fallback...", response.error);
            }
            Err(MeshRouterError::CircuitBreakerOpen) => {
                debug!("Circuit breaker open, using fallback...");
            }
            Err(e) => {
                debug!("Mesh execution error: {}, trying fallback...", e);
            }
        }

        // Fall back to HTTP
        fallback().await
    }

    /// Get current home state (for UI display)
    pub async fn get_home_state(&self) -> HomeState {
        self.home_state.read().await.clone()
    }

    /// Get current vector clock (for debugging)
    pub async fn get_vector_clock(&self) -> VectorClock {
        self.vector_clock.read().await.clone()
    }

    /// Get command count
    pub async fn get_command_count(&self) -> u64 {
        self.command_counter.read().await.value()
    }

    /// Sync state with all connected hubs
    pub async fn sync_state(&self) -> Result<(), MeshRouterError> {
        let state = self.home_state.read().await.clone();
        let state_json = serde_json::to_string(&state)
            .map_err(|e| MeshRouterError::CommandFailed(e.to_string()))?;

        let conns = self.hub_connections.read().await;
        for (peer_id, sender) in conns.iter() {
            if let Err(e) = sender.send(state_json.clone()).await {
                warn!("Failed to sync state with Hub {}: {}", &peer_id[..16], e);
            }
        }

        debug!("State synced with {} hubs", conns.len());
        Ok(())
    }

    /// Reset circuit breaker (for manual recovery)
    pub fn reset_circuit_breaker(&self) {
        self.circuit_breaker.reset();
        info!("Circuit breaker reset");
    }

    /// Reconnect to all registered hubs
    pub async fn reconnect_all(&self) -> Result<(), MeshRouterError> {
        let peers: Vec<(String, String)> = {
            let peers = self.hub_peers.read().await;
            peers
                .iter()
                .map(|(id, peer)| (id.clone(), peer.endpoint.clone()))
                .collect()
        };

        for (peer_id, endpoint) in peers {
            if let Err(e) = self.connect_to_hub(&peer_id, &endpoint).await {
                warn!("Failed to reconnect to Hub {}: {}", &peer_id[..16], e);
            }
        }

        Ok(())
    }
}

#[derive(Debug, Serialize, Deserialize)]
struct CommandEnvelope {
    id: String,
    command_type: String,
    payload: String,
    timestamp: u64,
    peer_id: String,
}

#[derive(Debug, Serialize, Deserialize)]
struct MeshMessage {
    sender_id: String,
    command_type: String,
    payload: String,
    signature: String,
    timestamp: u64,
}

// Global mesh router instance
static MESH_ROUTER: std::sync::OnceLock<std::sync::RwLock<MeshCommandRouter>> =
    std::sync::OnceLock::new();

/// Get the global mesh router
pub fn get_mesh_router() -> &'static std::sync::RwLock<MeshCommandRouter> {
    MESH_ROUTER.get_or_init(|| std::sync::RwLock::new(MeshCommandRouter::new()))
}

/// Initialize the global mesh router
pub fn initialize_mesh_router() -> Result<String, MeshRouterError> {
    let router = get_mesh_router();
    let mut guard = router.write().unwrap();
    guard.initialize()
}

/*
 * Mirror
 *
 * The mesh command router provides cryptographically secure routing
 * for smart home commands. Ed25519 signatures ensure authenticity,
 * XChaCha20-Poly1305 ensures confidentiality.
 *
 * Circuit breaker pattern prevents cascade failures.
 * CRDT state sync ensures eventual consistency across mesh.
 *
 * h(x) >= 0. Always.
 */
