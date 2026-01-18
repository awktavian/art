//! WebSocket client implementation with automatic reconnection.
//!
//! Provides a high-level WebSocket client that handles:
//! - Connection establishment
//! - Automatic reconnection with backoff
//! - Ping/pong keepalive
//! - Message serialization

use super::connection::{
    ConnectionConfig, ConnectionEvent, ConnectionState, ConnectionStateMachine,
};
use futures_util::{SinkExt, StreamExt};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use std::time::Duration;
use thiserror::Error;
use tokio::sync::{mpsc, RwLock};
use tokio::time::{interval, timeout};
use tokio_tungstenite::{
    connect_async,
    tungstenite::{protocol::Message, Error as TungsteniteError},
};

/// Errors that can occur during WebSocket operations.
#[derive(Debug, Error)]
pub enum WebSocketError {
    #[error("Connection failed: {0}")]
    ConnectionFailed(String),

    #[error("Send failed: {0}")]
    SendFailed(String),

    #[error("Receive failed: {0}")]
    ReceiveFailed(String),

    #[error("Not connected")]
    NotConnected,

    #[error("Channel closed")]
    ChannelClosed,

    #[error("Serialization error: {0}")]
    SerializationError(String),

    #[error("Connection timeout")]
    Timeout,

    #[error("Invalid URL: {0}")]
    InvalidUrl(String),

    #[error("TLS error: {0}")]
    TlsError(String),

    #[error("Insecure connection rejected: {0}")]
    InsecureConnection(String),
}

/// Security: Validate WebSocket URL scheme
///
/// Returns the URL unchanged if secure (wss://), or warns and rejects if insecure.
/// In production, only WSS connections should be used. HTTP/WS connections
/// are vulnerable to man-in-the-middle attacks.
fn validate_ws_url(url: &str, allow_insecure: bool) -> Result<String, WebSocketError> {
    let url_lower = url.to_lowercase();

    // Check for secure WebSocket
    if url_lower.starts_with("wss://") {
        return Ok(url.to_string());
    }

    // Check for insecure WebSocket
    if url_lower.starts_with("ws://") {
        if allow_insecure {
            tracing::warn!(
                "⚠️ SECURITY WARNING: Using insecure WebSocket connection (ws://). \
                 This connection is vulnerable to man-in-the-middle attacks. \
                 Use wss:// in production."
            );
            return Ok(url.to_string());
        }
        return Err(WebSocketError::InsecureConnection(
            "ws:// connections are not allowed. Use wss:// for secure WebSocket connections.".to_string()
        ));
    }

    // Try to auto-upgrade http/https to ws/wss
    if url_lower.starts_with("https://") {
        let ws_url = format!("wss://{}", &url[8..]);
        tracing::debug!("Auto-upgraded https:// to wss://");
        return Ok(ws_url);
    }

    if url_lower.starts_with("http://") {
        if allow_insecure {
            tracing::warn!(
                "⚠️ SECURITY WARNING: Auto-upgrading http:// to ws:// (insecure). \
                 Use https:// or wss:// in production."
            );
            let ws_url = format!("ws://{}", &url[7..]);
            return Ok(ws_url);
        }
        return Err(WebSocketError::InsecureConnection(
            "http:// connections cannot be upgraded to secure WebSocket. \
             Use https:// or wss:// for secure connections.".to_string()
        ));
    }

    Err(WebSocketError::InvalidUrl(format!(
        "Invalid WebSocket URL scheme. Expected ws://, wss://, http://, or https://. Got: {}",
        url
    )))
}

impl From<TungsteniteError> for WebSocketError {
    fn from(err: TungsteniteError) -> Self {
        match err {
            TungsteniteError::ConnectionClosed => WebSocketError::NotConnected,
            TungsteniteError::Io(e) => WebSocketError::ConnectionFailed(e.to_string()),
            TungsteniteError::Tls(e) => WebSocketError::TlsError(e.to_string()),
            _ => WebSocketError::ConnectionFailed(err.to_string()),
        }
    }
}

/// A WebSocket message that can be sent or received.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum WebSocketMessage {
    /// Text message.
    Text(String),

    /// Binary message.
    Binary(Vec<u8>),

    /// Ping message.
    Ping(Vec<u8>),

    /// Pong message.
    Pong(Vec<u8>),

    /// Close message with optional code and reason.
    Close(Option<(u16, String)>),
}

impl WebSocketMessage {
    /// Create a text message.
    pub fn text(s: impl Into<String>) -> Self {
        Self::Text(s.into())
    }

    /// Create a binary message.
    pub fn binary(data: Vec<u8>) -> Self {
        Self::Binary(data)
    }

    /// Create a JSON message from a serializable value.
    pub fn json<T: Serialize>(value: &T) -> Result<Self, WebSocketError> {
        let json = serde_json::to_string(value)
            .map_err(|e| WebSocketError::SerializationError(e.to_string()))?;
        Ok(Self::Text(json))
    }

    /// Parse a text message as JSON.
    pub fn parse_json<T: for<'de> Deserialize<'de>>(&self) -> Result<T, WebSocketError> {
        match self {
            WebSocketMessage::Text(s) => serde_json::from_str(s)
                .map_err(|e| WebSocketError::SerializationError(e.to_string())),
            _ => Err(WebSocketError::SerializationError(
                "Expected text message for JSON parsing".to_string(),
            )),
        }
    }

    /// Convert to tungstenite message.
    fn to_tungstenite(&self) -> Message {
        match self {
            WebSocketMessage::Text(s) => Message::Text(s.clone().into()),
            WebSocketMessage::Binary(b) => Message::Binary(b.clone().into()),
            WebSocketMessage::Ping(b) => Message::Ping(b.clone().into()),
            WebSocketMessage::Pong(b) => Message::Pong(b.clone().into()),
            WebSocketMessage::Close(info) => {
                if let Some((code, reason)) = info {
                    Message::Close(Some(tokio_tungstenite::tungstenite::protocol::CloseFrame {
                        code: (*code).into(),
                        reason: reason.clone().into(),
                    }))
                } else {
                    Message::Close(None)
                }
            }
        }
    }

    /// Convert from tungstenite message.
    fn from_tungstenite(msg: Message) -> Option<Self> {
        match msg {
            Message::Text(s) => Some(WebSocketMessage::Text(s.to_string())),
            Message::Binary(b) => Some(WebSocketMessage::Binary(b.to_vec())),
            Message::Ping(b) => Some(WebSocketMessage::Ping(b.to_vec())),
            Message::Pong(b) => Some(WebSocketMessage::Pong(b.to_vec())),
            Message::Close(frame) => Some(WebSocketMessage::Close(
                frame.map(|f| (f.code.into(), f.reason.to_string())),
            )),
            Message::Frame(_) => None,
        }
    }
}

/// Commands sent to the WebSocket task.
enum Command {
    Send(WebSocketMessage),
    Disconnect,
}

/// Events from the WebSocket task.
#[derive(Debug, Clone)]
pub enum WebSocketEvent {
    /// Connected to the server.
    Connected,

    /// Disconnected from the server.
    Disconnected(String),

    /// Message received.
    Message(WebSocketMessage),

    /// Error occurred.
    Error(String),

    /// Reconnecting after failure.
    Reconnecting { attempt: u32, backoff_ms: u64 },
}

/// A WebSocket client with automatic reconnection.
pub struct WebSocketClient {
    /// The URL to connect to.
    url: String,

    /// Connection state machine.
    state_machine: Arc<RwLock<ConnectionStateMachine>>,

    /// Channel to send commands to the WebSocket task.
    command_tx: Option<mpsc::Sender<Command>>,

    /// Connection configuration.
    config: ConnectionConfig,

    /// Whether to allow insecure (ws://) connections
    allow_insecure: bool,
}

impl WebSocketClient {
    /// Create a new WebSocket client.
    ///
    /// By default, only secure (wss://) connections are allowed.
    /// Use `with_insecure()` for development/testing with ws://.
    pub fn new(url: impl Into<String>) -> Self {
        Self::with_config(url, ConnectionConfig::default())
    }

    /// Create a new WebSocket client with custom configuration.
    ///
    /// By default, only secure (wss://) connections are allowed.
    pub fn with_config(url: impl Into<String>, config: ConnectionConfig) -> Self {
        Self {
            url: url.into(),
            state_machine: Arc::new(RwLock::new(ConnectionStateMachine::new(config.clone()))),
            command_tx: None,
            config,
            allow_insecure: false,
        }
    }

    /// Allow insecure (ws://) connections.
    ///
    /// **WARNING**: This should only be used for local development and testing.
    /// Insecure connections are vulnerable to man-in-the-middle attacks.
    /// Always use wss:// in production environments.
    pub fn with_insecure(mut self) -> Self {
        tracing::warn!(
            "⚠️ SECURITY: WebSocket client configured to allow insecure connections. \
             Do not use in production!"
        );
        self.allow_insecure = true;
        self
    }

    /// Get the current connection state.
    pub async fn state(&self) -> ConnectionState {
        self.state_machine.read().await.state()
    }

    /// Check if currently connected.
    pub async fn is_connected(&self) -> bool {
        self.state_machine.read().await.is_connected()
    }

    /// Connect to the WebSocket server.
    ///
    /// Returns a receiver for WebSocket events.
    ///
    /// By default, only secure (wss://) connections are allowed.
    /// This method will return an error if an insecure URL is provided
    /// and `with_insecure()` was not called.
    pub async fn connect(&mut self) -> Result<mpsc::Receiver<WebSocketEvent>, WebSocketError> {
        // Security: Validate URL scheme before connecting
        let validated_url = validate_ws_url(&self.url, self.allow_insecure)?;

        // Create channels
        let (command_tx, command_rx) = mpsc::channel(32);
        let (event_tx, event_rx) = mpsc::channel(64);

        self.command_tx = Some(command_tx);

        // Spawn the WebSocket task
        let state_machine = self.state_machine.clone();
        let config = self.config.clone();

        tokio::spawn(async move {
            websocket_task(validated_url, state_machine, command_rx, event_tx, config).await;
        });

        // Trigger connection
        {
            let mut sm = self.state_machine.write().await;
            let _ = sm.process_event(ConnectionEvent::Connect);
        }

        Ok(event_rx)
    }

    /// Send a message.
    pub async fn send(&self, message: WebSocketMessage) -> Result<(), WebSocketError> {
        if let Some(tx) = &self.command_tx {
            tx.send(Command::Send(message))
                .await
                .map_err(|_| WebSocketError::ChannelClosed)
        } else {
            Err(WebSocketError::NotConnected)
        }
    }

    /// Send a text message.
    pub async fn send_text(&self, text: impl Into<String>) -> Result<(), WebSocketError> {
        self.send(WebSocketMessage::text(text)).await
    }

    /// Send a binary message.
    pub async fn send_binary(&self, data: Vec<u8>) -> Result<(), WebSocketError> {
        self.send(WebSocketMessage::binary(data)).await
    }

    /// Send a JSON message.
    pub async fn send_json<T: Serialize>(&self, value: &T) -> Result<(), WebSocketError> {
        let message = WebSocketMessage::json(value)?;
        self.send(message).await
    }

    /// Disconnect from the server.
    pub async fn disconnect(&self) -> Result<(), WebSocketError> {
        if let Some(tx) = &self.command_tx {
            tx.send(Command::Disconnect)
                .await
                .map_err(|_| WebSocketError::ChannelClosed)?;

            let mut sm = self.state_machine.write().await;
            let _ = sm.process_event(ConnectionEvent::Disconnect);
        }
        Ok(())
    }
}

/// The main WebSocket task that handles connection and reconnection.
async fn websocket_task(
    url: String,
    state_machine: Arc<RwLock<ConnectionStateMachine>>,
    mut command_rx: mpsc::Receiver<Command>,
    event_tx: mpsc::Sender<WebSocketEvent>,
    config: ConnectionConfig,
) {
    loop {
        // Check if we should connect
        let should_connect = {
            let sm = state_machine.read().await;
            sm.should_connect()
        };

        if !should_connect {
            // Wait a bit and check for commands
            tokio::select! {
                cmd = command_rx.recv() => {
                    match cmd {
                        Some(Command::Disconnect) | None => {
                            return;
                        }
                        _ => continue,
                    }
                }
                _ = tokio::time::sleep(Duration::from_millis(100)) => {
                    // Check circuit breaker recovery
                    let should_recover = {
                        let sm = state_machine.read().await;
                        sm.should_attempt_recovery()
                    };
                    if should_recover {
                        let mut sm = state_machine.write().await;
                        let _ = sm.process_event(ConnectionEvent::CircuitBreakerRecovery);
                    }
                    continue;
                }
            }
        }

        // Get backoff duration
        let backoff = {
            let sm = state_machine.read().await;
            sm.backoff_duration()
        };

        // Notify reconnecting
        let attempt = {
            let sm = state_machine.read().await;
            sm.reconnect_attempts()
        };

        if attempt > 0 {
            let _ = event_tx
                .send(WebSocketEvent::Reconnecting {
                    attempt,
                    backoff_ms: backoff.as_millis() as u64,
                })
                .await;
            tokio::time::sleep(backoff).await;
        }

        // Attempt connection
        {
            let mut sm = state_machine.write().await;
            let _ = sm.process_event(ConnectionEvent::Connect);
        }

        match timeout(Duration::from_secs(30), connect_async(&url)).await {
            Ok(Ok((ws_stream, _))) => {
                // Connection successful
                {
                    let mut sm = state_machine.write().await;
                    let _ = sm.process_event(ConnectionEvent::Connected);
                }
                let _ = event_tx.send(WebSocketEvent::Connected).await;

                // Handle the connection
                let (write, read) = ws_stream.split();
                let write = Arc::new(tokio::sync::Mutex::new(write));
                let write_clone = write.clone();

                // Message receive task
                let event_tx_clone = event_tx.clone();
                let state_machine_clone = state_machine.clone();

                let mut read = read;
                let mut ping_interval = interval(config.ping_interval);
                ping_interval.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Delay);

                loop {
                    tokio::select! {
                        // Incoming message
                        msg = read.next() => {
                            match msg {
                                Some(Ok(msg)) => {
                                    // Handle pong specially
                                    if matches!(msg, Message::Pong(_)) {
                                        let mut sm = state_machine_clone.write().await;
                                        let _ = sm.process_event(ConnectionEvent::PongReceived);
                                    }

                                    if let Some(ws_msg) = WebSocketMessage::from_tungstenite(msg) {
                                        let _ = event_tx_clone.send(WebSocketEvent::Message(ws_msg)).await;
                                    }
                                }
                                Some(Err(e)) => {
                                    let _ = event_tx_clone.send(WebSocketEvent::Error(e.to_string())).await;
                                    break;
                                }
                                None => {
                                    break;
                                }
                            }
                        }

                        // Outgoing command
                        cmd = command_rx.recv() => {
                            match cmd {
                                Some(Command::Send(msg)) => {
                                    let mut writer = write_clone.lock().await;
                                    if let Err(e) = writer.send(msg.to_tungstenite()).await {
                                        let _ = event_tx_clone.send(WebSocketEvent::Error(e.to_string())).await;
                                    }
                                }
                                Some(Command::Disconnect) | None => {
                                    let mut writer = write_clone.lock().await;
                                    let _ = writer.send(Message::Close(None)).await;
                                    return;
                                }
                            }
                        }

                        // Ping keepalive
                        _ = ping_interval.tick() => {
                            let mut writer = write_clone.lock().await;
                            if let Err(e) = writer.send(Message::Ping(vec![].into())).await {
                                let _ = event_tx_clone.send(WebSocketEvent::Error(e.to_string())).await;
                                break;
                            }
                        }
                    }
                }

                // Connection lost
                {
                    let mut sm = state_machine.write().await;
                    let _ = sm.process_event(ConnectionEvent::Disconnected(
                        "Connection closed".to_string(),
                    ));
                }
                let _ = event_tx
                    .send(WebSocketEvent::Disconnected(
                        "Connection closed".to_string(),
                    ))
                    .await;
            }

            Ok(Err(e)) => {
                // Connection failed
                {
                    let mut sm = state_machine.write().await;
                    let _ = sm.process_event(ConnectionEvent::ConnectionFailed(e.to_string()));
                }
                let _ = event_tx.send(WebSocketEvent::Error(e.to_string())).await;
            }

            Err(_) => {
                // Timeout
                {
                    let mut sm = state_machine.write().await;
                    let _ = sm.process_event(ConnectionEvent::ConnectionFailed(
                        "Connection timeout".to_string(),
                    ));
                }
                let _ = event_tx
                    .send(WebSocketEvent::Error("Connection timeout".to_string()))
                    .await;
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_message_json_roundtrip() {
        #[derive(Debug, Serialize, Deserialize, PartialEq)]
        struct TestMsg {
            field: String,
            number: i32,
        }

        let original = TestMsg {
            field: "hello".to_string(),
            number: 42,
        };

        let ws_msg = WebSocketMessage::json(&original).unwrap();
        let recovered: TestMsg = ws_msg.parse_json().unwrap();

        assert_eq!(original, recovered);
    }

    #[test]
    fn test_message_text() {
        let msg = WebSocketMessage::text("hello");
        assert!(matches!(msg, WebSocketMessage::Text(s) if s == "hello"));
    }

    #[test]
    fn test_message_binary() {
        let msg = WebSocketMessage::binary(vec![1, 2, 3]);
        assert!(matches!(msg, WebSocketMessage::Binary(b) if b == vec![1, 2, 3]));
    }

    #[test]
    fn test_client_creation() {
        let client = WebSocketClient::new("wss://localhost:8080");
        assert_eq!(client.url, "wss://localhost:8080");
        assert!(!client.allow_insecure);
    }

    #[test]
    fn test_client_with_config() {
        let config = ConnectionConfig {
            failure_threshold: 10,
            ..Default::default()
        };
        let client = WebSocketClient::with_config("wss://localhost:8080", config);
        assert_eq!(client.config.failure_threshold, 10);
    }

    #[test]
    fn test_url_validation_secure() {
        assert!(validate_ws_url("wss://example.com", false).is_ok());
        assert!(validate_ws_url("WSS://example.com", false).is_ok());
    }

    #[test]
    fn test_url_validation_insecure_rejected() {
        assert!(matches!(
            validate_ws_url("ws://example.com", false),
            Err(WebSocketError::InsecureConnection(_))
        ));
    }

    #[test]
    fn test_url_validation_insecure_allowed() {
        assert!(validate_ws_url("ws://localhost:8080", true).is_ok());
    }

    #[test]
    fn test_url_validation_https_upgrade() {
        let result = validate_ws_url("https://example.com/path", false).unwrap();
        assert_eq!(result, "wss://example.com/path");
    }

    #[test]
    fn test_url_validation_invalid_scheme() {
        assert!(matches!(
            validate_ws_url("ftp://example.com", false),
            Err(WebSocketError::InvalidUrl(_))
        ));
    }

    #[test]
    fn test_client_with_insecure() {
        let client = WebSocketClient::new("ws://localhost:8080").with_insecure();
        assert!(client.allow_insecure);
    }
}
