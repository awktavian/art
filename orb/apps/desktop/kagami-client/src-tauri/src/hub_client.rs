//! Hub Client — Desktop-to-Hub Communication
//!
//! Enables the Desktop app to connect to Kagami Hub for:
//! - Registration and authentication
//! - Receiving remote commands from Hub
//! - Streaming screen content to Hub
//! - Bidirectional WebSocket communication
//!
//! ## Discovery
//!
//! Uses mDNS to discover Hubs on the local network:
//! - Service type: `_kagami-desktop._tcp.local.`
//!
//! ## Security
//!
//! - Ed25519 identity for authentication
//! - X25519 key exchange for encryption
//! - Challenge-response authentication
//!
//! Colony: Nexus (e4) — Integration
//!
//! h(x) >= 0. Always.

use kagami_mesh_sdk::{
    generate_x25519_keypair, MeshConnection, MeshIdentity, WebSocketClient, WebSocketEvent,
    WebSocketMessage, X25519KeyPair,
};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
// Tauri imports - currently unused but kept for future event emission
#[allow(unused_imports)]
use tauri::{AppHandle, Emitter, Runtime};
use thiserror::Error;
use tokio::sync::{broadcast, mpsc, RwLock};
use tracing::{debug, error, info, warn};

// =============================================================================
// Constants
// =============================================================================

/// mDNS service type for Hub discovery
pub const HUB_SERVICE_TYPE: &str = "_kagami-desktop._tcp.local.";

/// Default Hub port
pub const DEFAULT_HUB_PORT: u16 = 8080;

/// Connection timeout in seconds
const CONNECT_TIMEOUT_SECS: u64 = 10;

/// Heartbeat interval
const HEARTBEAT_INTERVAL_MS: u64 = 15000;

// =============================================================================
// Errors
// =============================================================================

#[derive(Debug, Error)]
pub enum HubClientError {
    #[error("Not connected to Hub")]
    NotConnected,

    #[error("Connection failed: {0}")]
    ConnectionFailed(String),

    #[error("Authentication failed: {0}")]
    AuthenticationFailed(String),

    #[error("Registration failed: {0}")]
    RegistrationFailed(String),

    #[error("Command execution failed: {0}")]
    CommandFailed(String),

    #[error("Hub not found")]
    HubNotFound,

    #[error("Invalid response: {0}")]
    InvalidResponse(String),

    #[error("Timeout")]
    Timeout,
}

// =============================================================================
// Types
// =============================================================================

/// Information about a discovered Hub
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiscoveredHub {
    /// Hub ID
    pub hub_id: String,
    /// Human-readable name
    pub name: String,
    /// IP address
    pub address: String,
    /// Port
    pub port: u16,
    /// Capabilities
    pub capabilities: Vec<String>,
}

/// Registration request to Hub
#[derive(Debug, Serialize)]
struct RegistrationRequest {
    peer_id: String,
    name: String,
    hostname: String,
    os: String,
    encryption_key: String,
    capabilities: DesktopCapabilities,
}

/// Registration response from Hub
#[derive(Debug, Deserialize)]
struct RegistrationResponse {
    success: bool,
    hub_peer_id: String,
    hub_encryption_key: String,
    challenge: Option<AuthChallenge>,
    error: Option<String>,
}

/// Authentication challenge from Hub
#[derive(Debug, Deserialize)]
struct AuthChallenge {
    challenge: String,
    nonce: String,
    timestamp: u64,
    hub_id: String,
}

/// Authentication response to Hub
#[derive(Debug, Serialize)]
struct AuthResponse {
    challenge: String,
    nonce: String,
    timestamp: u64,
    signature: String,
    peer_id: String,
}

/// Desktop capabilities we advertise to Hub
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct DesktopCapabilities {
    pub screen_share: bool,
    pub remote_control: bool,
    pub input_simulation: bool,
    pub audio_stream: bool,
    pub clipboard: bool,
    pub file_access: bool,
    pub screen_resolution: Option<(u32, u32)>,
    pub display_count: Option<u32>,
}

impl DesktopCapabilities {
    /// Create default capabilities for this platform
    pub fn current() -> Self {
        // Get screen info
        let (width, height, displays) = get_screen_info();

        Self {
            screen_share: true,
            remote_control: true,
            input_simulation: true,
            audio_stream: true,
            clipboard: true,
            file_access: false, // Opt-in for security
            screen_resolution: Some((width, height)),
            display_count: Some(displays),
        }
    }
}

/// Commands received from Hub
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", content = "data")]
pub enum HubCommand {
    /// Request a screenshot
    CaptureScreen {
        display: Option<u32>,
        format: String,
        quality: Option<u8>,
    },

    /// Start screen sharing
    StartScreenShare {
        display: Option<u32>,
        fps: u32,
        quality: u8,
    },

    /// Stop screen sharing
    StopScreenShare,

    /// Execute a shell command
    ExecuteShell {
        command: String,
        cwd: Option<String>,
        env: Option<HashMap<String, String>>,
        timeout_secs: Option<u64>,
    },

    /// Type text
    TypeText { text: String, delay_ms: Option<u32> },

    /// Key press
    KeyPress { keys: String },

    /// Move mouse
    MouseMove { x: i32, y: i32, absolute: bool },

    /// Mouse click
    MouseClick {
        button: String,
        click_type: String,
        x: Option<i32>,
        y: Option<i32>,
    },

    /// Get clipboard
    GetClipboard,

    /// Set clipboard
    SetClipboard { text: String },

    /// Open URL or application
    Open { target: String },

    /// Get system info
    GetSystemInfo,

    /// Ping
    Ping,
}

/// Response to Hub commands
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", content = "data")]
pub enum HubCommandResponse {
    Screenshot {
        image_base64: String,
        format: String,
        width: u32,
        height: u32,
    },
    ScreenShareStarted {
        stream_id: String,
    },
    ScreenShareStopped,
    ScreenFrame {
        frame_base64: String,
        timestamp: u64,
    },
    ShellResult {
        exit_code: i32,
        stdout: String,
        stderr: String,
        duration_ms: u64,
    },
    InputComplete {
        success: bool,
    },
    ClipboardContent {
        text: Option<String>,
        has_image: bool,
    },
    SystemInfo {
        os: String,
        os_version: String,
        hostname: String,
        cpu_usage: f32,
        memory_usage: f32,
        disk_usage: f32,
        displays: Vec<DisplayInfo>,
    },
    Pong {
        timestamp: u64,
    },
    Error {
        message: String,
        code: String,
    },
}

/// Display information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DisplayInfo {
    pub index: u32,
    pub width: u32,
    pub height: u32,
    pub is_primary: bool,
    pub name: String,
}

/// WebSocket envelope for messages
#[derive(Debug, Serialize, Deserialize)]
struct WsEnvelope {
    id: String,
    msg_type: String,
    payload: serde_json::Value,
    timestamp: u64,
}

/// Events emitted by the Hub client
#[derive(Debug, Clone, Serialize)]
#[serde(tag = "type", content = "data")]
pub enum HubClientEvent {
    /// Discovered a Hub on the network
    HubDiscovered { hub: DiscoveredHub },

    /// Connected to Hub
    Connected { hub_id: String, hub_name: String },

    /// Disconnected from Hub
    Disconnected { reason: String },

    /// Authenticated with Hub
    Authenticated,

    /// Command received from Hub
    CommandReceived { command_type: String },

    /// Connection error
    Error { message: String },
}

// =============================================================================
// Hub Client
// =============================================================================

/// Client for connecting to Kagami Hub
pub struct HubClient {
    /// Our mesh identity
    identity: MeshIdentity,

    /// Our X25519 keypair
    x25519_keys: X25519KeyPair,

    /// Connection state tracker
    connection: MeshConnection,

    /// Currently connected Hub
    connected_hub: Arc<RwLock<Option<ConnectedHub>>>,

    /// WebSocket send channel
    ws_tx: Arc<RwLock<Option<mpsc::Sender<String>>>>,

    /// Event broadcast channel
    event_tx: broadcast::Sender<HubClientEvent>,

    /// Command handler
    command_handler: Arc<dyn CommandHandler + Send + Sync>,

    /// Shutdown signal
    shutdown_tx: Arc<RwLock<Option<mpsc::Sender<()>>>>,
}

/// Information about the connected Hub
#[derive(Debug, Clone)]
struct ConnectedHub {
    hub_id: String,
    name: String,
    address: String,
    port: u16,
    encryption_key: String,
}

/// Trait for handling commands from Hub
pub trait CommandHandler: Send + Sync {
    /// Handle a command from Hub
    fn handle_command(
        &self,
        command: HubCommand,
    ) -> std::pin::Pin<Box<dyn std::future::Future<Output = HubCommandResponse> + Send>>;
}

impl HubClient {
    /// Create a new Hub client
    pub fn new(handler: Arc<dyn CommandHandler + Send + Sync>) -> Self {
        let (event_tx, _) = broadcast::channel(64);

        Self {
            identity: MeshIdentity::new(),
            x25519_keys: generate_x25519_keypair(),
            connection: MeshConnection::new(),
            connected_hub: Arc::new(RwLock::new(None)),
            ws_tx: Arc::new(RwLock::new(None)),
            event_tx,
            command_handler: handler,
            shutdown_tx: Arc::new(RwLock::new(None)),
        }
    }

    /// Get our peer ID
    pub fn peer_id(&self) -> String {
        self.identity.peer_id()
    }

    /// Subscribe to events
    pub fn subscribe(&self) -> broadcast::Receiver<HubClientEvent> {
        self.event_tx.subscribe()
    }

    /// Check if connected to a Hub
    pub async fn is_connected(&self) -> bool {
        self.connected_hub.read().await.is_some() && self.connection.is_connected()
    }

    /// Discover Hubs on the local network via mDNS
    #[cfg(feature = "mdns")]
    pub async fn discover_hubs(&self, timeout: Duration) -> Vec<DiscoveredHub> {
        use mdns_sd::ServiceDaemon;

        let mut hubs = Vec::new();

        let mdns = match ServiceDaemon::new() {
            Ok(m) => m,
            Err(e) => {
                warn!("Failed to create mDNS daemon: {}", e);
                return hubs;
            }
        };

        let browse_handle = match mdns.browse(HUB_SERVICE_TYPE) {
            Ok(h) => h,
            Err(e) => {
                warn!("Failed to browse mDNS: {}", e);
                return hubs;
            }
        };

        let deadline = tokio::time::Instant::now() + timeout;

        loop {
            tokio::select! {
                _ = tokio::time::sleep_until(deadline) => break,
                event = tokio::task::spawn_blocking({
                    let handle = browse_handle.clone();
                    move || handle.recv_timeout(Duration::from_millis(100))
                }) => {
                    if let Ok(Ok(event)) = event {
                        use mdns_sd::ServiceEvent;
                        if let ServiceEvent::ServiceResolved(info) = event {
                            let hub_id = info.get_property_val_str("hub_id")
                                .unwrap_or_default()
                                .to_string();

                            if hub_id.is_empty() {
                                continue;
                            }

                            let address = info.get_addresses()
                                .iter()
                                .next()
                                .map(|a| a.to_string())
                                .unwrap_or_default();

                            if address.is_empty() {
                                continue;
                            }

                            let capabilities: Vec<String> = info.get_property_val_str("capabilities")
                                .unwrap_or_default()
                                .split(',')
                                .map(|s| s.to_string())
                                .collect();

                            let hub = DiscoveredHub {
                                hub_id,
                                name: info.get_fullname().to_string(),
                                address,
                                port: info.get_port(),
                                capabilities,
                            };

                            info!("Discovered Hub: {} at {}:{}", hub.name, hub.address, hub.port);

                            let _ = self.event_tx.send(HubClientEvent::HubDiscovered { hub: hub.clone() });
                            hubs.push(hub);
                        }
                    }
                }
            }
        }

        hubs
    }

    #[cfg(not(feature = "mdns"))]
    pub async fn discover_hubs(&self, _timeout: Duration) -> Vec<DiscoveredHub> {
        warn!("mDNS discovery disabled (compile with --features mdns)");
        Vec::new()
    }

    /// Connect to a Hub
    pub async fn connect(&self, hub_address: &str, hub_port: u16) -> Result<(), HubClientError> {
        info!("Connecting to Hub at {}:{}", hub_address, hub_port);

        // Step 1: Register with Hub
        let registration = self.register(hub_address, hub_port).await?;

        // Step 2: Authenticate if challenge provided
        if let Some(challenge) = registration.challenge {
            self.authenticate(hub_address, hub_port, challenge).await?;
        }

        // Step 3: Establish WebSocket connection
        self.establish_websocket(hub_address, hub_port, &registration.hub_peer_id)
            .await?;

        // Store connected Hub info
        {
            let mut hub = self.connected_hub.write().await;
            *hub = Some(ConnectedHub {
                hub_id: registration.hub_peer_id.clone(),
                name: format!("Hub@{}:{}", hub_address, hub_port),
                address: hub_address.to_string(),
                port: hub_port,
                encryption_key: registration.hub_encryption_key,
            });
        }

        let _ = self.event_tx.send(HubClientEvent::Connected {
            hub_id: registration.hub_peer_id,
            hub_name: format!("Hub@{}:{}", hub_address, hub_port),
        });

        info!("Connected to Hub at {}:{}", hub_address, hub_port);
        Ok(())
    }

    /// Register with Hub
    async fn register(
        &self,
        hub_address: &str,
        hub_port: u16,
    ) -> Result<RegistrationResponse, HubClientError> {
        let client = reqwest::Client::new();

        let hostname = hostname::get()
            .map(|h| h.to_string_lossy().to_string())
            .unwrap_or_else(|_| "unknown".to_string());

        let request = RegistrationRequest {
            peer_id: self.identity.peer_id(),
            name: format!("{} Desktop", whoami::realname()),
            hostname,
            os: std::env::consts::OS.to_string(),
            encryption_key: self.x25519_keys.public_key_hex.clone(),
            capabilities: DesktopCapabilities::current(),
        };

        let url = format!("http://{}:{}/desktop/register", hub_address, hub_port);

        let response = client
            .post(&url)
            .json(&request)
            .timeout(Duration::from_secs(CONNECT_TIMEOUT_SECS))
            .send()
            .await
            .map_err(|e| HubClientError::ConnectionFailed(e.to_string()))?;

        let registration: RegistrationResponse = response
            .json()
            .await
            .map_err(|e| HubClientError::InvalidResponse(e.to_string()))?;

        if !registration.success {
            return Err(HubClientError::RegistrationFailed(
                registration.error.unwrap_or_else(|| "Unknown error".to_string()),
            ));
        }

        Ok(registration)
    }

    /// Authenticate with Hub using challenge-response
    async fn authenticate(
        &self,
        hub_address: &str,
        hub_port: u16,
        challenge: AuthChallenge,
    ) -> Result<(), HubClientError> {
        let client = reqwest::Client::new();

        // Sign the challenge
        let mut signing_data = Vec::new();
        signing_data.extend(hex::decode(&challenge.challenge).unwrap_or_default());
        signing_data.extend(hex::decode(&challenge.nonce).unwrap_or_default());
        signing_data.extend(&challenge.timestamp.to_be_bytes());
        signing_data.extend(challenge.hub_id.as_bytes());
        signing_data.extend(self.identity.peer_id().as_bytes());

        let signature = self.identity.sign(&signing_data);

        let response = AuthResponse {
            challenge: challenge.challenge,
            nonce: challenge.nonce,
            timestamp: challenge.timestamp,
            signature,
            peer_id: self.identity.peer_id(),
        };

        let url = format!("http://{}:{}/desktop/auth", hub_address, hub_port);

        let result = client
            .post(&url)
            .json(&response)
            .timeout(Duration::from_secs(CONNECT_TIMEOUT_SECS))
            .send()
            .await
            .map_err(|e| HubClientError::ConnectionFailed(e.to_string()))?;

        if !result.status().is_success() {
            return Err(HubClientError::AuthenticationFailed("Invalid signature".to_string()));
        }

        let _ = self.event_tx.send(HubClientEvent::Authenticated);
        info!("Authenticated with Hub");

        Ok(())
    }

    /// Establish WebSocket connection for bidirectional communication
    async fn establish_websocket(
        &self,
        hub_address: &str,
        hub_port: u16,
        _hub_id: &str,
    ) -> Result<(), HubClientError> {
        let url = format!(
            "ws://{}:{}/desktop/ws?peer_id={}",
            hub_address,
            hub_port,
            self.identity.peer_id()
        );

        let mut ws_client = WebSocketClient::new(&url);
        let mut events = ws_client
            .connect()
            .await
            .map_err(|e| HubClientError::ConnectionFailed(e.to_string()))?;

        // Create channels for sending/receiving
        let (ws_tx, mut ws_rx) = mpsc::channel::<String>(32);
        let (shutdown_tx, mut shutdown_rx) = mpsc::channel::<()>(1);

        {
            let mut tx = self.ws_tx.write().await;
            *tx = Some(ws_tx);
        }
        {
            let mut stx = self.shutdown_tx.write().await;
            *stx = Some(shutdown_tx);
        }

        // Spawn WebSocket handler task
        let event_tx = self.event_tx.clone();
        let command_handler = self.command_handler.clone();
        let ws_client = Arc::new(tokio::sync::Mutex::new(ws_client));

        tokio::spawn(async move {
            loop {
                tokio::select! {
                    // Shutdown signal
                    _ = shutdown_rx.recv() => {
                        info!("WebSocket shutdown requested");
                        break;
                    }

                    // Outgoing message
                    Some(msg) = ws_rx.recv() => {
                        let client = ws_client.lock().await;
                        if let Err(e) = client.send_text(&msg).await {
                            error!("Failed to send WebSocket message: {}", e);
                        }
                    }

                    // Incoming event
                    Some(event) = events.recv() => {
                        match event {
                            WebSocketEvent::Connected => {
                                debug!("WebSocket connected");
                            }
                            WebSocketEvent::Disconnected(reason) => {
                                warn!("WebSocket disconnected: {}", reason);
                                let _ = event_tx.send(HubClientEvent::Disconnected { reason });
                                break;
                            }
                            WebSocketEvent::Message(WebSocketMessage::Text(text)) => {
                                // Parse envelope
                                if let Ok(envelope) = serde_json::from_str::<WsEnvelope>(&text) {
                                    if envelope.msg_type == "command" {
                                        // Parse and handle command
                                        if let Ok(command) = serde_json::from_value::<HubCommand>(envelope.payload) {
                                            let command_type = match &command {
                                                HubCommand::CaptureScreen { .. } => "CaptureScreen",
                                                HubCommand::StartScreenShare { .. } => "StartScreenShare",
                                                HubCommand::StopScreenShare => "StopScreenShare",
                                                HubCommand::ExecuteShell { .. } => "ExecuteShell",
                                                HubCommand::TypeText { .. } => "TypeText",
                                                HubCommand::KeyPress { .. } => "KeyPress",
                                                HubCommand::MouseMove { .. } => "MouseMove",
                                                HubCommand::MouseClick { .. } => "MouseClick",
                                                HubCommand::GetClipboard => "GetClipboard",
                                                HubCommand::SetClipboard { .. } => "SetClipboard",
                                                HubCommand::Open { .. } => "Open",
                                                HubCommand::GetSystemInfo => "GetSystemInfo",
                                                HubCommand::Ping => "Ping",
                                            };

                                            let _ = event_tx.send(HubClientEvent::CommandReceived {
                                                command_type: command_type.to_string(),
                                            });

                                            // Execute command
                                            let response = command_handler.handle_command(command).await;

                                            // Send response
                                            let response_envelope = WsEnvelope {
                                                id: envelope.id,
                                                msg_type: "response".to_string(),
                                                payload: serde_json::to_value(&response).unwrap_or_default(),
                                                timestamp: SystemTime::now()
                                                    .duration_since(UNIX_EPOCH)
                                                    .unwrap_or_default()
                                                    .as_millis() as u64,
                                            };

                                            if let Ok(json) = serde_json::to_string(&response_envelope) {
                                                let client = ws_client.lock().await;
                                                if let Err(e) = client.send_text(&json).await {
                                                    error!("Failed to send response: {}", e);
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                            WebSocketEvent::Error(err) => {
                                error!("WebSocket error: {}", err);
                                let _ = event_tx.send(HubClientEvent::Error { message: err });
                            }
                            _ => {}
                        }
                    }
                }
            }
        });

        Ok(())
    }

    /// Disconnect from Hub
    pub async fn disconnect(&self) {
        if let Some(tx) = self.shutdown_tx.write().await.take() {
            let _ = tx.send(()).await;
        }

        let mut hub = self.connected_hub.write().await;
        *hub = None;

        let mut ws = self.ws_tx.write().await;
        *ws = None;

        info!("Disconnected from Hub");
    }
}

// =============================================================================
// Default Command Handler
// =============================================================================

/// Default implementation of command handler
pub struct DefaultCommandHandler;

impl CommandHandler for DefaultCommandHandler {
    fn handle_command(
        &self,
        command: HubCommand,
    ) -> std::pin::Pin<Box<dyn std::future::Future<Output = HubCommandResponse> + Send>> {
        Box::pin(async move {
            match command {
                HubCommand::Ping => HubCommandResponse::Pong {
                    timestamp: SystemTime::now()
                        .duration_since(UNIX_EPOCH)
                        .unwrap_or_default()
                        .as_millis() as u64,
                },

                HubCommand::GetSystemInfo => {
                    let (width, height, displays) = get_screen_info();
                    HubCommandResponse::SystemInfo {
                        os: std::env::consts::OS.to_string(),
                        os_version: os_info::get().version().to_string(),
                        hostname: hostname::get()
                            .map(|h| h.to_string_lossy().to_string())
                            .unwrap_or_default(),
                        cpu_usage: 0.0,    // TODO: Implement
                        memory_usage: 0.0, // TODO: Implement
                        disk_usage: 0.0,   // TODO: Implement
                        displays: vec![DisplayInfo {
                            index: 0,
                            width,
                            height,
                            is_primary: true,
                            name: "Primary".to_string(),
                        }],
                    }
                }

                HubCommand::ExecuteShell {
                    command,
                    cwd,
                    env,
                    timeout_secs,
                } => {
                    // SECURITY: This is a sensitive operation
                    // In production, this should require explicit user approval
                    let start = std::time::Instant::now();

                    let mut cmd = if cfg!(target_os = "windows") {
                        let mut c = std::process::Command::new("cmd");
                        c.args(["/C", &command]);
                        c
                    } else {
                        let mut c = std::process::Command::new("sh");
                        c.args(["-c", &command]);
                        c
                    };

                    if let Some(dir) = cwd {
                        cmd.current_dir(dir);
                    }

                    if let Some(env_vars) = env {
                        for (k, v) in env_vars {
                            cmd.env(k, v);
                        }
                    }

                    match cmd.output() {
                        Ok(output) => HubCommandResponse::ShellResult {
                            exit_code: output.status.code().unwrap_or(-1),
                            stdout: String::from_utf8_lossy(&output.stdout).to_string(),
                            stderr: String::from_utf8_lossy(&output.stderr).to_string(),
                            duration_ms: start.elapsed().as_millis() as u64,
                        },
                        Err(e) => HubCommandResponse::Error {
                            message: e.to_string(),
                            code: "EXEC_FAILED".to_string(),
                        },
                    }
                }

                HubCommand::GetClipboard => {
                    // TODO: Implement clipboard access using arboard crate
                    HubCommandResponse::ClipboardContent {
                        text: None,
                        has_image: false,
                    }
                }

                HubCommand::SetClipboard { text } => {
                    // TODO: Implement clipboard access using arboard crate
                    HubCommandResponse::InputComplete { success: false }
                }

                HubCommand::Open { target } => {
                    match open::that(&target) {
                        Ok(_) => HubCommandResponse::InputComplete { success: true },
                        Err(e) => HubCommandResponse::Error {
                            message: e.to_string(),
                            code: "OPEN_FAILED".to_string(),
                        },
                    }
                }

                // Screen capture commands - require additional implementation
                HubCommand::CaptureScreen { display, format, quality } => {
                    // TODO: Implement screen capture using screenshots crate
                    HubCommandResponse::Error {
                        message: "Screen capture not yet implemented".to_string(),
                        code: "NOT_IMPLEMENTED".to_string(),
                    }
                }

                HubCommand::StartScreenShare { .. } => HubCommandResponse::Error {
                    message: "Screen sharing not yet implemented".to_string(),
                    code: "NOT_IMPLEMENTED".to_string(),
                },

                HubCommand::StopScreenShare => HubCommandResponse::ScreenShareStopped,

                // Input simulation commands - require additional implementation
                HubCommand::TypeText { .. }
                | HubCommand::KeyPress { .. }
                | HubCommand::MouseMove { .. }
                | HubCommand::MouseClick { .. } => {
                    // TODO: Implement using enigo or similar crate
                    HubCommandResponse::Error {
                        message: "Input simulation not yet implemented".to_string(),
                        code: "NOT_IMPLEMENTED".to_string(),
                    }
                }
            }
        })
    }
}

// =============================================================================
// Helpers
// =============================================================================

/// Get screen resolution and display count
fn get_screen_info() -> (u32, u32, u32) {
    // TODO: Implement proper screen enumeration
    // For now, return reasonable defaults
    (1920, 1080, 1)
}

// =============================================================================
// Tauri Commands
// =============================================================================

/// Global Hub client instance
static HUB_CLIENT: std::sync::OnceLock<tokio::sync::RwLock<HubClient>> = std::sync::OnceLock::new();

/// Get or create the global Hub client
pub fn get_hub_client() -> &'static tokio::sync::RwLock<HubClient> {
    HUB_CLIENT.get_or_init(|| {
        tokio::sync::RwLock::new(HubClient::new(Arc::new(DefaultCommandHandler)))
    })
}

#[tauri::command]
pub async fn discover_hubs() -> Result<Vec<DiscoveredHub>, String> {
    let client = get_hub_client().read().await;
    Ok(client.discover_hubs(Duration::from_secs(5)).await)
}

#[tauri::command]
pub async fn connect_to_hub(address: String, port: u16) -> Result<bool, String> {
    let client = get_hub_client().read().await;
    client
        .connect(&address, port)
        .await
        .map(|_| true)
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn disconnect_from_hub() -> Result<bool, String> {
    let client = get_hub_client().read().await;
    client.disconnect().await;
    Ok(true)
}

#[tauri::command]
pub async fn is_hub_connected() -> Result<bool, String> {
    let client = get_hub_client().read().await;
    Ok(client.is_connected().await)
}

#[tauri::command]
pub async fn get_hub_peer_id() -> Result<String, String> {
    let client = get_hub_client().read().await;
    Ok(client.peer_id())
}

/*
 * 鏡
 * Desktop connects to Hub. Hub controls Desktop.
 * Bidirectional, secure, unified.
 * h(x) >= 0. Always.
 */
