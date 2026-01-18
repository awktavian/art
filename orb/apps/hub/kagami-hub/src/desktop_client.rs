//! Desktop Client Management
//!
//! Enables bidirectional communication between Hub and Desktop clients:
//! - Desktop registration with Hub
//! - Remote command execution (Hub → Desktop)
//! - Screen sharing (Desktop → Hub)
//! - Secure authentication via mesh auth
//!
//! ## Protocol
//!
//! 1. Desktop discovers Hub via mDNS (`_kagami-desktop._tcp.local.`)
//! 2. Desktop registers with Hub, providing:
//!    - Peer ID (Ed25519 public key)
//!    - X25519 public key for encryption
//!    - Capabilities (screen_share, remote_control, etc.)
//! 3. Hub authenticates Desktop via challenge-response
//! 4. Bidirectional WebSocket established for commands
//!
//! ## Remote Control Commands
//!
//! Hub can send to Desktop:
//! - `ExecuteShell` - Run shell commands
//! - `CaptureScreen` - Request screenshot
//! - `StartScreenShare` - Begin screen streaming
//! - `TypeText` - Simulate keyboard input
//! - `MouseMove/Click` - Simulate mouse
//!
//! Colony: Nexus (e₄) — Connection and integration
//!
//! η → s → μ → a → η′
//! h(x) ≥ 0. Always.

use std::collections::HashMap;
use std::sync::Arc;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use axum::{
    extract::{
        ws::{Message, WebSocket, WebSocketUpgrade},
        State,
    },
    http::StatusCode,
    response::IntoResponse,
    routing::{get, post},
    Json, Router,
};
use futures_util::{SinkExt, StreamExt};
use serde::{Deserialize, Serialize};
use tokio::sync::{broadcast, mpsc, RwLock};
use tracing::{debug, error, info, warn};

use crate::mesh::MeshAuth;

// =============================================================================
// Constants
// =============================================================================

/// mDNS service type for desktop client discovery
pub const DESKTOP_SERVICE_TYPE: &str = "_kagami-desktop._tcp.local.";

/// Maximum time without heartbeat before considering a client disconnected
const CLIENT_TIMEOUT_SECS: u64 = 60;

/// Heartbeat interval for connected clients
const HEARTBEAT_INTERVAL_SECS: u64 = 15;

/// Maximum command payload size (1MB)
const MAX_COMMAND_SIZE: usize = 1024 * 1024;

/// Command execution timeout
const COMMAND_TIMEOUT_SECS: u64 = 30;

// =============================================================================
// Types
// =============================================================================

/// A connected desktop client
#[derive(Debug, Clone, Serialize)]
pub struct DesktopClient {
    /// Unique peer ID (Ed25519 public key hex)
    pub peer_id: String,

    /// Human-readable name (e.g., "Tim's MacBook Pro")
    pub name: String,

    /// Client hostname
    pub hostname: String,

    /// Operating system
    pub os: String,

    /// Client capabilities
    pub capabilities: DesktopCapabilities,

    /// X25519 public key for encryption (hex)
    pub encryption_key: String,

    /// When the client registered
    pub registered_at: u64,

    /// Last heartbeat time
    #[serde(skip)]
    pub last_heartbeat: Instant,

    /// Whether the client is authenticated
    pub authenticated: bool,

    /// Active WebSocket connection (internal)
    #[serde(skip)]
    pub connected: bool,
}

/// Desktop client capabilities
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct DesktopCapabilities {
    /// Can capture and share screen
    pub screen_share: bool,

    /// Can execute remote commands
    pub remote_control: bool,

    /// Can simulate keyboard/mouse input
    pub input_simulation: bool,

    /// Can stream audio
    pub audio_stream: bool,

    /// Can access clipboard
    pub clipboard: bool,

    /// Can manage files
    pub file_access: bool,

    /// Screen resolution (width x height)
    pub screen_resolution: Option<(u32, u32)>,

    /// Number of displays
    pub display_count: Option<u32>,
}

/// Registration request from a desktop client
#[derive(Debug, Deserialize)]
pub struct DesktopRegistrationRequest {
    /// Client's peer ID (Ed25519 public key hex)
    pub peer_id: String,

    /// Human-readable name
    pub name: String,

    /// Client hostname
    pub hostname: String,

    /// Operating system
    pub os: String,

    /// X25519 public key for encryption
    pub encryption_key: String,

    /// Client capabilities
    pub capabilities: DesktopCapabilities,
}

/// Registration response
#[derive(Debug, Serialize)]
pub struct DesktopRegistrationResponse {
    /// Success status
    pub success: bool,

    /// Hub's peer ID
    pub hub_peer_id: String,

    /// Hub's X25519 public key
    pub hub_encryption_key: String,

    /// Authentication challenge
    pub challenge: Option<AuthChallengeData>,

    /// Error message if failed
    pub error: Option<String>,
}

/// Authentication challenge data
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuthChallengeData {
    /// Challenge bytes (hex)
    pub challenge: String,

    /// Nonce (hex)
    pub nonce: String,

    /// Timestamp
    pub timestamp: u64,

    /// Hub ID for binding
    pub hub_id: String,
}

/// Authentication response from client
#[derive(Debug, Deserialize)]
pub struct AuthResponseData {
    /// Original challenge (hex)
    pub challenge: String,

    /// Original nonce (hex)
    pub nonce: String,

    /// Timestamp
    pub timestamp: u64,

    /// Signature (hex)
    pub signature: String,

    /// Client's peer ID
    pub peer_id: String,
}

/// Commands that can be sent to a desktop client
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", content = "data")]
pub enum DesktopCommand {
    /// Request a screenshot
    CaptureScreen {
        /// Optional display index
        display: Option<u32>,
        /// Image format (png, jpeg)
        format: String,
        /// Quality (1-100 for jpeg)
        quality: Option<u8>,
    },

    /// Start screen sharing stream
    StartScreenShare {
        /// Target display
        display: Option<u32>,
        /// Frame rate
        fps: u32,
        /// Quality (1-100)
        quality: u8,
    },

    /// Stop screen sharing
    StopScreenShare,

    /// Execute a shell command
    ExecuteShell {
        /// Command to execute
        command: String,
        /// Working directory
        cwd: Option<String>,
        /// Environment variables
        env: Option<HashMap<String, String>>,
        /// Timeout in seconds
        timeout_secs: Option<u64>,
    },

    /// Type text (simulate keyboard)
    TypeText {
        /// Text to type
        text: String,
        /// Delay between keystrokes (ms)
        delay_ms: Option<u32>,
    },

    /// Key press (single key or combo)
    KeyPress {
        /// Key(s) to press (e.g., "cmd+shift+a")
        keys: String,
    },

    /// Move mouse
    MouseMove {
        /// X coordinate
        x: i32,
        /// Y coordinate
        y: i32,
        /// Absolute or relative movement
        absolute: bool,
    },

    /// Mouse click
    MouseClick {
        /// Button (left, right, middle)
        button: String,
        /// Click type (single, double, down, up)
        click_type: String,
        /// Optional position
        x: Option<i32>,
        y: Option<i32>,
    },

    /// Read clipboard
    GetClipboard,

    /// Write to clipboard
    SetClipboard {
        /// Text content
        text: String,
    },

    /// Open URL or application
    Open {
        /// URL or path to open
        target: String,
    },

    /// Get system info
    GetSystemInfo,

    /// Heartbeat/ping
    Ping,
}

/// Response from a desktop command
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", content = "data")]
pub enum DesktopCommandResponse {
    /// Screenshot captured
    Screenshot {
        /// Image data (base64)
        image_base64: String,
        /// Image format
        format: String,
        /// Width
        width: u32,
        /// Height
        height: u32,
    },

    /// Screen share started
    ScreenShareStarted {
        /// Stream ID
        stream_id: String,
    },

    /// Screen share stopped
    ScreenShareStopped,

    /// Screen frame (during streaming)
    ScreenFrame {
        /// Frame data (base64)
        frame_base64: String,
        /// Timestamp
        timestamp: u64,
    },

    /// Shell command result
    ShellResult {
        /// Exit code
        exit_code: i32,
        /// Stdout
        stdout: String,
        /// Stderr
        stderr: String,
        /// Execution time (ms)
        duration_ms: u64,
    },

    /// Input action completed
    InputComplete {
        /// Success
        success: bool,
    },

    /// Clipboard content
    ClipboardContent {
        /// Text content
        text: Option<String>,
        /// Has image
        has_image: bool,
    },

    /// System information
    SystemInfo {
        /// OS name
        os: String,
        /// OS version
        os_version: String,
        /// Hostname
        hostname: String,
        /// CPU usage (0-100)
        cpu_usage: f32,
        /// Memory usage (0-100)
        memory_usage: f32,
        /// Disk usage (0-100)
        disk_usage: f32,
        /// Displays
        displays: Vec<DisplayInfo>,
    },

    /// Pong response
    Pong {
        /// Server timestamp
        timestamp: u64,
    },

    /// Error response
    Error {
        /// Error message
        message: String,
        /// Error code
        code: String,
    },
}

/// Display information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DisplayInfo {
    /// Display index
    pub index: u32,
    /// Width
    pub width: u32,
    /// Height
    pub height: u32,
    /// Is primary display
    pub is_primary: bool,
    /// Display name
    pub name: String,
}

/// WebSocket message envelope
#[derive(Debug, Serialize, Deserialize)]
pub struct WsEnvelope {
    /// Message ID for request/response correlation
    pub id: String,
    /// Message type
    pub msg_type: String,
    /// Payload
    pub payload: serde_json::Value,
    /// Timestamp
    pub timestamp: u64,
}

/// Events emitted by the desktop client manager
#[derive(Debug, Clone)]
pub enum DesktopClientEvent {
    /// New client registered
    ClientRegistered { peer_id: String, name: String },
    /// Client authenticated
    ClientAuthenticated { peer_id: String },
    /// Client disconnected
    ClientDisconnected { peer_id: String },
    /// Command sent
    CommandSent { peer_id: String, command_type: String },
    /// Response received
    ResponseReceived { peer_id: String, response_type: String },
}

// =============================================================================
// Desktop Client Manager
// =============================================================================

/// Manages desktop client connections and commands
pub struct DesktopClientManager {
    /// This hub's ID
    hub_id: String,

    /// Mesh authentication
    auth: Arc<MeshAuth>,

    /// Connected clients (peer_id -> client)
    clients: Arc<RwLock<HashMap<String, DesktopClient>>>,

    /// Command senders per client (peer_id -> sender)
    command_senders: Arc<RwLock<HashMap<String, mpsc::Sender<DesktopCommand>>>>,

    /// Pending command responses (request_id -> response sender)
    pending_responses: Arc<RwLock<HashMap<String, tokio::sync::oneshot::Sender<DesktopCommandResponse>>>>,

    /// Event channel
    event_tx: broadcast::Sender<DesktopClientEvent>,

    /// Hub's X25519 keys
    x25519_public_key: String,
    #[allow(dead_code)]
    x25519_secret_key: String,
}

impl DesktopClientManager {
    /// Create a new desktop client manager
    pub fn new(hub_id: String, auth: Arc<MeshAuth>) -> Self {
        let (event_tx, _) = broadcast::channel(100);

        // Generate X25519 keypair for encryption
        let keypair = kagami_mesh_sdk::generate_x25519_keypair();

        Self {
            hub_id,
            auth,
            clients: Arc::new(RwLock::new(HashMap::new())),
            command_senders: Arc::new(RwLock::new(HashMap::new())),
            pending_responses: Arc::new(RwLock::new(HashMap::new())),
            event_tx,
            x25519_public_key: keypair.public_key_hex,
            x25519_secret_key: keypair.secret_key_hex,
        }
    }

    /// Create the Axum router for desktop client endpoints
    pub fn router(self: Arc<Self>) -> Router {
        Router::new()
            .route("/desktop/register", post(handle_registration))
            .route("/desktop/auth", post(handle_auth_response))
            .route("/desktop/ws", get(handle_websocket))
            .route("/desktop/clients", get(list_clients))
            .route("/desktop/command/:peer_id", post(send_command))
            .with_state(self)
    }

    /// Subscribe to events
    pub fn subscribe(&self) -> broadcast::Receiver<DesktopClientEvent> {
        self.event_tx.subscribe()
    }

    /// Get connected client count
    pub async fn client_count(&self) -> usize {
        self.clients.read().await.len()
    }

    /// Get all connected clients
    pub async fn get_clients(&self) -> Vec<DesktopClient> {
        self.clients.read().await.values().cloned().collect()
    }

    /// Get a specific client
    pub async fn get_client(&self, peer_id: &str) -> Option<DesktopClient> {
        self.clients.read().await.get(peer_id).cloned()
    }

    /// Send a command to a desktop client
    pub async fn send_command(
        &self,
        peer_id: &str,
        command: DesktopCommand,
    ) -> Result<DesktopCommandResponse, String> {
        let senders = self.command_senders.read().await;
        let sender = senders
            .get(peer_id)
            .ok_or_else(|| format!("Client {} not connected", peer_id))?;

        // Create response channel
        let (resp_tx, resp_rx) = tokio::sync::oneshot::channel();
        let request_id = uuid::Uuid::new_v4().to_string();

        // Store response handler
        {
            let mut pending = self.pending_responses.write().await;
            pending.insert(request_id.clone(), resp_tx);
        }

        // Send command
        sender
            .send(command.clone())
            .await
            .map_err(|_| "Failed to send command")?;

        // Emit event
        let command_type = match &command {
            DesktopCommand::CaptureScreen { .. } => "CaptureScreen",
            DesktopCommand::StartScreenShare { .. } => "StartScreenShare",
            DesktopCommand::StopScreenShare => "StopScreenShare",
            DesktopCommand::ExecuteShell { .. } => "ExecuteShell",
            DesktopCommand::TypeText { .. } => "TypeText",
            DesktopCommand::KeyPress { .. } => "KeyPress",
            DesktopCommand::MouseMove { .. } => "MouseMove",
            DesktopCommand::MouseClick { .. } => "MouseClick",
            DesktopCommand::GetClipboard => "GetClipboard",
            DesktopCommand::SetClipboard { .. } => "SetClipboard",
            DesktopCommand::Open { .. } => "Open",
            DesktopCommand::GetSystemInfo => "GetSystemInfo",
            DesktopCommand::Ping => "Ping",
        };
        let _ = self.event_tx.send(DesktopClientEvent::CommandSent {
            peer_id: peer_id.to_string(),
            command_type: command_type.to_string(),
        });

        // Wait for response with timeout
        tokio::time::timeout(Duration::from_secs(COMMAND_TIMEOUT_SECS), resp_rx)
            .await
            .map_err(|_| "Command timed out".to_string())?
            .map_err(|_| "Response channel closed".to_string())
    }

    /// Register a new client
    async fn register_client(&self, req: DesktopRegistrationRequest) -> DesktopRegistrationResponse {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();

        // Create challenge for authentication
        let challenge = self.auth.generate_challenge(&req.peer_id);

        let challenge_data = AuthChallengeData {
            challenge: hex::encode(&challenge.challenge),
            nonce: hex::encode(&challenge.nonce),
            timestamp: challenge.timestamp,
            hub_id: self.hub_id.clone(),
        };

        // Create client record (not yet authenticated)
        let client = DesktopClient {
            peer_id: req.peer_id.clone(),
            name: req.name.clone(),
            hostname: req.hostname,
            os: req.os,
            capabilities: req.capabilities,
            encryption_key: req.encryption_key,
            registered_at: now,
            last_heartbeat: Instant::now(),
            authenticated: false,
            connected: false,
        };

        // Store client
        {
            let mut clients = self.clients.write().await;
            clients.insert(req.peer_id.clone(), client);
        }

        info!("📱 Desktop client registered: {} ({})", req.name, req.peer_id);

        let _ = self.event_tx.send(DesktopClientEvent::ClientRegistered {
            peer_id: req.peer_id,
            name: req.name,
        });

        DesktopRegistrationResponse {
            success: true,
            hub_peer_id: self.hub_id.clone(),
            hub_encryption_key: self.x25519_public_key.clone(),
            challenge: Some(challenge_data),
            error: None,
        }
    }

    /// Verify authentication response
    async fn verify_auth(&self, resp: AuthResponseData) -> Result<(), String> {
        // Reconstruct the challenge
        let challenge_bytes = hex::decode(&resp.challenge)
            .map_err(|_| "Invalid challenge format")?;
        let nonce_bytes = hex::decode(&resp.nonce)
            .map_err(|_| "Invalid nonce format")?;

        let challenge = crate::mesh::auth::AuthChallenge {
            challenge: challenge_bytes,
            nonce: nonce_bytes,
            timestamp: resp.timestamp,
            challenger_hub_id: self.hub_id.clone(),
            responder_hub_id: resp.peer_id.clone(),
        };

        // Get client's public key from registration
        let client = {
            let clients = self.clients.read().await;
            clients.get(&resp.peer_id).cloned()
        };

        let client = client.ok_or("Client not registered")?;

        // Verify signature
        let signature = hex::decode(&resp.signature)
            .map_err(|_| "Invalid signature format")?;

        let public_key = hex::decode(&client.encryption_key)
            .map_err(|_| "Invalid public key format")?;

        // Create auth response for verification
        let auth_response = crate::mesh::auth::AuthResponse {
            challenge: challenge.challenge.clone(),
            nonce: challenge.nonce.clone(),
            timestamp: challenge.timestamp,
            signature,
            public_key,
            responder_hub_id: resp.peer_id.clone(),
            challenger_hub_id: self.hub_id.clone(),
        };

        // Verify
        match self.auth.verify_response(&auth_response) {
            crate::mesh::auth::AuthResult::Success { .. } => {
                // Mark client as authenticated
                {
                    let mut clients = self.clients.write().await;
                    if let Some(client) = clients.get_mut(&resp.peer_id) {
                        client.authenticated = true;
                    }
                }

                info!("✓ Desktop client authenticated: {}", resp.peer_id);
                let _ = self.event_tx.send(DesktopClientEvent::ClientAuthenticated {
                    peer_id: resp.peer_id,
                });

                Ok(())
            }
            result => {
                warn!("✗ Desktop client auth failed: {:?}", result);
                Err(format!("Authentication failed: {:?}", result))
            }
        }
    }

    /// Handle WebSocket connection from a desktop client
    async fn handle_ws(&self, peer_id: String, mut socket: WebSocket) {
        // Verify client is registered and authenticated
        let client = {
            let clients = self.clients.read().await;
            clients.get(&peer_id).cloned()
        };

        let client = match client {
            Some(c) if c.authenticated => c,
            Some(_) => {
                warn!("WebSocket rejected: client {} not authenticated", peer_id);
                let _ = socket.send(Message::Close(None)).await;
                return;
            }
            None => {
                warn!("WebSocket rejected: client {} not registered", peer_id);
                let _ = socket.send(Message::Close(None)).await;
                return;
            }
        };

        info!("📱 Desktop client connected via WebSocket: {}", client.name);

        // Mark as connected
        {
            let mut clients = self.clients.write().await;
            if let Some(c) = clients.get_mut(&peer_id) {
                c.connected = true;
                c.last_heartbeat = Instant::now();
            }
        }

        // Create command channel for this client
        let (cmd_tx, mut cmd_rx) = mpsc::channel::<DesktopCommand>(32);
        {
            let mut senders = self.command_senders.write().await;
            senders.insert(peer_id.clone(), cmd_tx);
        }

        // Handle messages
        let mut heartbeat_interval =
            tokio::time::interval(Duration::from_secs(HEARTBEAT_INTERVAL_SECS));

        loop {
            tokio::select! {
                // Incoming message from client
                msg = socket.recv() => {
                    match msg {
                        Some(Ok(Message::Text(text))) => {
                            // Parse envelope
                            if let Ok(envelope) = serde_json::from_str::<WsEnvelope>(&text) {
                                // Update heartbeat
                                {
                                    let mut clients = self.clients.write().await;
                                    if let Some(c) = clients.get_mut(&peer_id) {
                                        c.last_heartbeat = Instant::now();
                                    }
                                }

                                // Handle response
                                if envelope.msg_type == "response" {
                                    if let Ok(response) = serde_json::from_value::<DesktopCommandResponse>(envelope.payload) {
                                        // Find pending request
                                        let resp_tx = {
                                            let mut pending = self.pending_responses.write().await;
                                            pending.remove(&envelope.id)
                                        };

                                        if let Some(tx) = resp_tx {
                                            let _ = tx.send(response.clone());
                                        }

                                        // Emit event
                                        let response_type = match &response {
                                            DesktopCommandResponse::Screenshot { .. } => "Screenshot",
                                            DesktopCommandResponse::ScreenShareStarted { .. } => "ScreenShareStarted",
                                            DesktopCommandResponse::ScreenShareStopped => "ScreenShareStopped",
                                            DesktopCommandResponse::ScreenFrame { .. } => "ScreenFrame",
                                            DesktopCommandResponse::ShellResult { .. } => "ShellResult",
                                            DesktopCommandResponse::InputComplete { .. } => "InputComplete",
                                            DesktopCommandResponse::ClipboardContent { .. } => "ClipboardContent",
                                            DesktopCommandResponse::SystemInfo { .. } => "SystemInfo",
                                            DesktopCommandResponse::Pong { .. } => "Pong",
                                            DesktopCommandResponse::Error { .. } => "Error",
                                        };
                                        let _ = self.event_tx.send(DesktopClientEvent::ResponseReceived {
                                            peer_id: peer_id.clone(),
                                            response_type: response_type.to_string(),
                                        });
                                    }
                                }
                            }
                        }
                        Some(Ok(Message::Pong(_))) => {
                            // Update heartbeat
                            let mut clients = self.clients.write().await;
                            if let Some(c) = clients.get_mut(&peer_id) {
                                c.last_heartbeat = Instant::now();
                            }
                        }
                        Some(Ok(Message::Close(_))) | None => {
                            break;
                        }
                        Some(Err(e)) => {
                            warn!("WebSocket error from {}: {}", peer_id, e);
                            break;
                        }
                        _ => {}
                    }
                }

                // Outgoing command to client
                Some(command) = cmd_rx.recv() => {
                    let envelope = WsEnvelope {
                        id: uuid::Uuid::new_v4().to_string(),
                        msg_type: "command".to_string(),
                        payload: serde_json::to_value(&command).unwrap_or_default(),
                        timestamp: SystemTime::now()
                            .duration_since(UNIX_EPOCH)
                            .unwrap_or_default()
                            .as_millis() as u64,
                    };

                    if let Ok(json) = serde_json::to_string(&envelope) {
                        if socket.send(Message::Text(json)).await.is_err() {
                            break;
                        }
                    }
                }

                // Heartbeat ping
                _ = heartbeat_interval.tick() => {
                    if socket.send(Message::Ping(vec![])).await.is_err() {
                        break;
                    }
                }
            }
        }

        // Clean up on disconnect
        info!("📱 Desktop client disconnected: {}", peer_id);

        {
            let mut clients = self.clients.write().await;
            if let Some(c) = clients.get_mut(&peer_id) {
                c.connected = false;
            }
        }

        {
            let mut senders = self.command_senders.write().await;
            senders.remove(&peer_id);
        }

        let _ = self.event_tx.send(DesktopClientEvent::ClientDisconnected {
            peer_id,
        });
    }

    /// Start mDNS advertisement for desktop discovery
    #[cfg(feature = "mdns")]
    pub async fn advertise_mdns(&self, port: u16) -> anyhow::Result<()> {
        use mdns_sd::{ServiceDaemon, ServiceInfo};

        let mdns = ServiceDaemon::new()
            .map_err(|e| anyhow::anyhow!("Failed to create mDNS daemon: {}", e))?;

        let hostname = hostname::get()
            .map(|h| h.to_string_lossy().to_string())
            .unwrap_or_else(|_| "kagami-hub".to_string());

        let mut properties = std::collections::HashMap::new();
        properties.insert("hub_id".to_string(), self.hub_id.clone());
        properties.insert("version".to_string(), env!("CARGO_PKG_VERSION").to_string());
        properties.insert("capabilities".to_string(), "remote_control,screen_share".to_string());

        let service = ServiceInfo::new(
            DESKTOP_SERVICE_TYPE,
            "Kagami Hub Desktop Control",
            &format!("{}.local.", hostname),
            (),
            port,
            properties,
        )
        .map_err(|e| anyhow::anyhow!("Failed to create service info: {}", e))?;

        mdns.register(service)
            .map_err(|e| anyhow::anyhow!("Failed to register mDNS service: {}", e))?;

        info!("📡 Advertising desktop control via mDNS: {} on port {}", DESKTOP_SERVICE_TYPE, port);

        Ok(())
    }

    #[cfg(not(feature = "mdns"))]
    pub async fn advertise_mdns(&self, _port: u16) -> anyhow::Result<()> {
        warn!("mDNS advertisement disabled (compile with --features mdns)");
        Ok(())
    }
}

// =============================================================================
// Axum Handlers
// =============================================================================

type AppState = Arc<DesktopClientManager>;

async fn handle_registration(
    State(manager): State<AppState>,
    Json(req): Json<DesktopRegistrationRequest>,
) -> impl IntoResponse {
    let response = manager.register_client(req).await;
    Json(response)
}

async fn handle_auth_response(
    State(manager): State<AppState>,
    Json(req): Json<AuthResponseData>,
) -> impl IntoResponse {
    match manager.verify_auth(req).await {
        Ok(()) => (StatusCode::OK, Json(serde_json::json!({"success": true}))),
        Err(e) => (
            StatusCode::UNAUTHORIZED,
            Json(serde_json::json!({"success": false, "error": e})),
        ),
    }
}

async fn handle_websocket(
    ws: WebSocketUpgrade,
    State(manager): State<AppState>,
    axum::extract::Query(params): axum::extract::Query<HashMap<String, String>>,
) -> impl IntoResponse {
    let peer_id = params.get("peer_id").cloned().unwrap_or_default();
    ws.on_upgrade(move |socket| async move {
        manager.handle_ws(peer_id, socket).await;
    })
}

async fn list_clients(State(manager): State<AppState>) -> impl IntoResponse {
    let clients = manager.get_clients().await;
    Json(clients)
}

#[derive(Deserialize)]
struct SendCommandRequest {
    command: DesktopCommand,
}

async fn send_command(
    State(manager): State<AppState>,
    axum::extract::Path(peer_id): axum::extract::Path<String>,
    Json(req): Json<SendCommandRequest>,
) -> impl IntoResponse {
    match manager.send_command(&peer_id, req.command).await {
        Ok(response) => (StatusCode::OK, Json(serde_json::to_value(response).unwrap_or_default())),
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(serde_json::json!({"error": e})),
        ),
    }
}

/*
 * 鏡
 * Desktop and Hub, connected as one.
 * h(x) ≥ 0. Always.
 */
