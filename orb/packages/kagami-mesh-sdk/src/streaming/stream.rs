//! Voice streaming client for real-time audio communication.
//!
//! This module provides a WebSocket-based voice streaming client that handles:
//! - Audio data streaming to backend (STT)
//! - Receiving transcription results
//! - Receiving TTS audio responses
//! - Automatic reconnection with Fibonacci backoff
//! - Buffer management
//!
//! Colony: Beacon (e5) -- Communication
//!
//! h(x) >= 0. Always.

use super::types::{
    AudioChunk, AudioFormat, TranscriptionResult, TtsResponse, VoiceConfig, VoiceMessage,
    VoiceStreamState,
};
use base64::{engine::general_purpose::STANDARD as BASE64, Engine as _};
use crate::transport::{WebSocketClient, WebSocketError, WebSocketEvent, WebSocketMessage};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};
use thiserror::Error;
use tokio::sync::{mpsc, watch, RwLock};
use tracing::{debug, error, info, warn};

// ============================================================================
// Error Categories
// ============================================================================

/// Error source category for diagnostic and recovery purposes.
///
/// This categorization helps identify the root cause and recovery strategy:
/// - **Network**: Connection, timeout, send failures - typically recoverable via retry
/// - **Protocol**: State machine violations - indicates logic error in client code
/// - **Server**: Server-side errors - may require backend investigation
/// - **Encoding**: Data format errors - typically recoverable by format adjustment
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum StreamErrorCategory {
    /// Network-related errors (connection, timeout, send failures)
    Network,
    /// Protocol/state errors (not connected, invalid state)
    Protocol,
    /// Server-side errors (session, processing failures)
    Server,
    /// Encoding/format errors (JSON, base64, audio format)
    Encoding,
}

// ============================================================================
// Voice Stream Errors
// ============================================================================

/// Errors that can occur during voice streaming.
///
/// Each variant is categorized for easier error handling and recovery:
/// - Network errors can often be recovered by reconnection
/// - Protocol errors indicate invalid client state transitions
/// - Server errors may require backend investigation
/// - Encoding errors can sometimes be recovered by format adjustment
#[derive(Debug, Error, Clone, uniffi::Error)]
pub enum VoiceStreamError {
    /// Not connected to server.
    /// Category: Protocol - must connect before performing operations.
    #[error("[Protocol] Not connected to voice server")]
    NotConnected,

    /// Connection failed.
    /// Category: Network - check endpoint URL, network connectivity.
    #[error("[Network] Connection failed: {message}")]
    ConnectionFailed { message: String },

    /// Connection timeout.
    /// Category: Network - server unreachable or too slow to respond.
    #[error("[Network] Connection timeout")]
    Timeout,

    /// Send failed.
    /// Category: Network - connection may have dropped.
    #[error("[Network] Send failed: {message}")]
    SendFailed { message: String },

    /// Invalid configuration.
    /// Category: Protocol - check VoiceConfig before connecting.
    #[error("[Protocol] Invalid configuration: {message}")]
    InvalidConfig { message: String },

    /// Session error.
    /// Category: Server - session state mismatch on backend.
    #[error("[Server] Session error: {message}")]
    SessionError { message: String },

    /// Server error.
    /// Category: Server - backend processing failure.
    #[error("[Server] Server error: {message}")]
    ServerError { message: String },

    /// Encoding error.
    /// Category: Encoding - JSON/base64/audio format issue.
    #[error("[Encoding] Encoding error: {message}")]
    EncodingError { message: String },
}

impl VoiceStreamError {
    /// Returns the error category for this error.
    ///
    /// Use this for programmatic error handling and recovery decisions.
    pub fn category(&self) -> StreamErrorCategory {
        match self {
            Self::NotConnected => StreamErrorCategory::Protocol,
            Self::ConnectionFailed { .. } => StreamErrorCategory::Network,
            Self::Timeout => StreamErrorCategory::Network,
            Self::SendFailed { .. } => StreamErrorCategory::Network,
            Self::InvalidConfig { .. } => StreamErrorCategory::Protocol,
            Self::SessionError { .. } => StreamErrorCategory::Server,
            Self::ServerError { .. } => StreamErrorCategory::Server,
            Self::EncodingError { .. } => StreamErrorCategory::Encoding,
        }
    }

    /// Returns true if this error might be recoverable by reconnection.
    pub fn is_recoverable(&self) -> bool {
        matches!(
            self.category(),
            StreamErrorCategory::Network | StreamErrorCategory::Server
        )
    }
}

impl From<WebSocketError> for VoiceStreamError {
    fn from(err: WebSocketError) -> Self {
        match err {
            WebSocketError::NotConnected => VoiceStreamError::NotConnected,
            WebSocketError::ConnectionFailed(msg) => VoiceStreamError::ConnectionFailed { message: msg },
            WebSocketError::Timeout => VoiceStreamError::Timeout,
            WebSocketError::SendFailed(msg) => VoiceStreamError::SendFailed { message: msg },
            _ => VoiceStreamError::ConnectionFailed {
                message: err.to_string(),
            },
        }
    }
}

// ============================================================================
// Fibonacci Backoff
// ============================================================================

/// Fibonacci-based reconnection backoff.
///
/// Uses Fibonacci sequence for more natural-feeling reconnection delays:
/// 89ms, 144ms, 233ms, 377ms, 610ms, 987ms, 1597ms, ...
#[derive(Debug, Clone)]
pub struct FibonacciBackoff {
    current: u64,
    previous: u64,
    max_ms: u64,
    initial_ms: u64,
}

impl Default for FibonacciBackoff {
    fn default() -> Self {
        Self::new(89, 30000) // Start at 89ms, max 30s
    }
}

impl FibonacciBackoff {
    /// Create a new Fibonacci backoff.
    pub fn new(initial_ms: u64, max_ms: u64) -> Self {
        Self {
            current: initial_ms,
            previous: 0,
            max_ms,
            initial_ms,
        }
    }

    /// Get the next backoff duration.
    pub fn next(&mut self) -> Duration {
        let next = self.current + self.previous;
        self.previous = self.current;
        self.current = next.min(self.max_ms);
        Duration::from_millis(self.current)
    }

    /// Reset the backoff to initial state.
    pub fn reset(&mut self) {
        self.current = self.initial_ms;
        self.previous = 0;
    }

    /// Get current backoff duration without advancing.
    pub fn current(&self) -> Duration {
        Duration::from_millis(self.current)
    }
}

// ============================================================================
// Voice Stream Events
// ============================================================================

/// Events emitted by the voice stream client.
#[derive(Debug, Clone)]
pub enum VoiceStreamEvent {
    /// State changed
    StateChanged(VoiceStreamState),

    /// Connected to server
    Connected { session_id: Option<String> },

    /// Disconnected from server
    Disconnected { reason: String },

    /// Reconnecting
    Reconnecting { attempt: u32, delay_ms: u64 },

    /// Partial transcription received
    TranscriptUpdate { text: String, is_final: bool },

    /// Final transcription received
    TranscriptFinal(TranscriptionResult),

    /// Response text received
    ResponseText { text: String, intent: Option<String> },

    /// TTS audio received
    TtsAudio(TtsResponse),

    /// Error occurred
    Error(VoiceStreamError),
}

// ============================================================================
// Audio Buffer
// ============================================================================

/// Ring buffer for audio data with overflow handling.
pub struct AudioBuffer {
    data: Vec<AudioChunk>,
    max_size: usize,
    total_bytes: usize,
    max_bytes: usize,
}

impl AudioBuffer {
    /// Create a new audio buffer.
    pub fn new(max_chunks: usize, max_bytes: usize) -> Self {
        Self {
            data: Vec::with_capacity(max_chunks),
            max_size: max_chunks,
            total_bytes: 0,
            max_bytes,
        }
    }

    /// Push a chunk to the buffer.
    pub fn push(&mut self, chunk: AudioChunk) -> bool {
        let chunk_bytes = chunk.data.len();

        // Check if we need to make room
        while self.data.len() >= self.max_size || self.total_bytes + chunk_bytes > self.max_bytes {
            if let Some(removed) = self.data.first() {
                self.total_bytes = self.total_bytes.saturating_sub(removed.data.len());
                self.data.remove(0);
            } else {
                break;
            }
        }

        self.total_bytes += chunk_bytes;
        self.data.push(chunk);
        true
    }

    /// Take all chunks from the buffer.
    pub fn take_all(&mut self) -> Vec<AudioChunk> {
        self.total_bytes = 0;
        std::mem::take(&mut self.data)
    }

    /// Get number of chunks in buffer.
    pub fn len(&self) -> usize {
        self.data.len()
    }

    /// Check if buffer is empty.
    pub fn is_empty(&self) -> bool {
        self.data.is_empty()
    }

    /// Get total bytes in buffer.
    pub fn total_bytes(&self) -> usize {
        self.total_bytes
    }

    /// Clear the buffer.
    pub fn clear(&mut self) {
        self.data.clear();
        self.total_bytes = 0;
    }
}

// ============================================================================
// Voice Stream Client
// ============================================================================

/// WebSocket client for voice streaming.
///
/// Handles bidirectional audio streaming with automatic reconnection.
pub struct VoiceStreamClient {
    /// Configuration
    config: VoiceConfig,
    /// Current state
    state: Arc<RwLock<VoiceStreamState>>,
    /// State watch channel
    state_tx: watch::Sender<VoiceStreamState>,
    /// WebSocket client
    ws_client: Option<WebSocketClient>,
    /// Event sender
    event_tx: mpsc::Sender<VoiceStreamEvent>,
    /// Audio buffer for pending chunks
    audio_buffer: Arc<RwLock<AudioBuffer>>,
    /// Sequence counter for audio chunks
    sequence: AtomicU64,
    /// Session start time
    session_start: Option<Instant>,
    /// Current session ID
    session_id: Option<String>,
    /// Reconnection backoff
    backoff: FibonacciBackoff,
    /// Reconnect attempt counter
    reconnect_attempts: u32,
}

impl VoiceStreamClient {
    /// Create a new voice stream client.
    pub fn new(config: VoiceConfig) -> (Self, mpsc::Receiver<VoiceStreamEvent>) {
        let (event_tx, event_rx) = mpsc::channel(64);
        let (state_tx, _) = watch::channel(VoiceStreamState::Idle);

        let client = Self {
            config,
            state: Arc::new(RwLock::new(VoiceStreamState::Idle)),
            state_tx,
            ws_client: None,
            event_tx,
            audio_buffer: Arc::new(RwLock::new(AudioBuffer::new(100, 1024 * 1024))), // 100 chunks, 1MB max
            sequence: AtomicU64::new(0),
            session_start: None,
            session_id: None,
            backoff: FibonacciBackoff::default(),
            reconnect_attempts: 0,
        };

        (client, event_rx)
    }

    /// Get current state.
    pub async fn state(&self) -> VoiceStreamState {
        *self.state.read().await
    }

    /// Subscribe to state changes.
    pub fn subscribe_state(&self) -> watch::Receiver<VoiceStreamState> {
        self.state_tx.subscribe()
    }

    /// Check if connected.
    pub async fn is_connected(&self) -> bool {
        self.state().await.is_connected()
    }

    /// Set state and notify.
    async fn set_state(&self, new_state: VoiceStreamState) {
        let mut state = self.state.write().await;
        if *state != new_state {
            *state = new_state;
            let _ = self.state_tx.send(new_state);
            let _ = self
                .event_tx
                .send(VoiceStreamEvent::StateChanged(new_state))
                .await;
        }
    }

    /// Connect to the voice server.
    pub async fn connect(&mut self) -> Result<(), VoiceStreamError> {
        if self.config.endpoint.is_empty() {
            return Err(VoiceStreamError::InvalidConfig {
                message: "No endpoint configured".to_string(),
            });
        }

        self.set_state(VoiceStreamState::Connecting).await;
        info!(
            "Connecting to voice server: {}",
            self.config.websocket_url()
        );

        let mut ws = WebSocketClient::new(self.config.websocket_url());
        let event_rx = ws.connect().await?;

        self.ws_client = Some(ws);
        self.backoff.reset();
        self.reconnect_attempts = 0;

        // Spawn message handler
        let state = self.state.clone();
        let event_tx = self.event_tx.clone();
        let state_tx = self.state_tx.clone();

        tokio::spawn(async move {
            handle_websocket_events(event_rx, state, event_tx, state_tx).await;
        });

        self.set_state(VoiceStreamState::Ready).await;
        let _ = self
            .event_tx
            .send(VoiceStreamEvent::Connected { session_id: None })
            .await;

        Ok(())
    }

    /// Disconnect from the voice server.
    pub async fn disconnect(&mut self) -> Result<(), VoiceStreamError> {
        if let Some(ws) = &self.ws_client {
            ws.disconnect().await?;
        }
        self.ws_client = None;
        self.session_id = None;
        self.set_state(VoiceStreamState::Disconnected).await;

        let _ = self
            .event_tx
            .send(VoiceStreamEvent::Disconnected {
                reason: "User requested".to_string(),
            })
            .await;

        Ok(())
    }

    /// Start a voice session (begin listening).
    pub async fn start_session(&mut self) -> Result<(), VoiceStreamError> {
        if !self.is_connected().await {
            return Err(VoiceStreamError::NotConnected);
        }

        self.session_start = Some(Instant::now());
        self.sequence.store(0, Ordering::Relaxed);
        self.audio_buffer.write().await.clear();
        self.set_state(VoiceStreamState::Listening).await;

        info!("Voice session started");
        Ok(())
    }

    /// End the voice session (stop listening, signal end of speech).
    pub async fn end_session(&mut self) -> Result<(), VoiceStreamError> {
        if !self.state().await.is_active() {
            return Ok(());
        }

        // Send end of speech signal
        self.send_end_of_speech().await?;
        self.set_state(VoiceStreamState::Processing).await;

        info!("Voice session ended, processing...");
        Ok(())
    }

    /// Send an audio chunk.
    pub async fn send_audio(&self, chunk: AudioChunk) -> Result<(), VoiceStreamError> {
        let state = self.state().await;
        if state != VoiceStreamState::Listening {
            // Buffer the chunk if not actively listening
            self.audio_buffer.write().await.push(chunk);
            return Ok(());
        }

        self.send_chunk_internal(&chunk).await
    }

    /// Send audio chunk internally.
    async fn send_chunk_internal(&self, chunk: &AudioChunk) -> Result<(), VoiceStreamError> {
        let ws = self
            .ws_client
            .as_ref()
            .ok_or(VoiceStreamError::NotConnected)?;

        let message = VoiceMessage::audio_chunk(chunk);
        let json = message
            .to_json()
            .map_err(|e| VoiceStreamError::EncodingError {
                message: e.to_string(),
            })?;

        ws.send_text(json).await?;
        Ok(())
    }

    /// Send end of speech signal.
    async fn send_end_of_speech(&self) -> Result<(), VoiceStreamError> {
        let ws = self
            .ws_client
            .as_ref()
            .ok_or(VoiceStreamError::NotConnected)?;

        let message = VoiceMessage::end_of_speech();
        let json = message
            .to_json()
            .map_err(|e| VoiceStreamError::EncodingError {
                message: e.to_string(),
            })?;

        ws.send_text(json).await?;
        Ok(())
    }

    /// Send raw audio samples.
    pub async fn send_samples(&self, samples: &[i16]) -> Result<(), VoiceStreamError> {
        let sequence = self.sequence.fetch_add(1, Ordering::Relaxed);
        let timestamp_ms = self
            .session_start
            .map(|s| s.elapsed().as_millis() as u64)
            .unwrap_or(0);

        let data: Vec<u8> = samples.iter().flat_map(|&s| s.to_le_bytes()).collect();

        let chunk = AudioChunk::new(data, timestamp_ms, sequence);
        self.send_audio(chunk).await
    }

    /// Flush buffered audio.
    pub async fn flush_buffer(&self) -> Result<(), VoiceStreamError> {
        let chunks = self.audio_buffer.write().await.take_all();
        for chunk in chunks {
            self.send_chunk_internal(&chunk).await?;
        }
        Ok(())
    }

    /// Get buffered audio count.
    pub async fn buffered_chunks(&self) -> usize {
        self.audio_buffer.read().await.len()
    }

    /// Attempt reconnection with Fibonacci backoff.
    pub async fn reconnect(&mut self) -> Result<(), VoiceStreamError> {
        if !self.config.auto_reconnect {
            return Err(VoiceStreamError::NotConnected);
        }

        if self.config.max_reconnect_attempts > 0
            && self.reconnect_attempts >= self.config.max_reconnect_attempts
        {
            error!("Max reconnection attempts reached");
            return Err(VoiceStreamError::ConnectionFailed {
                message: "Max reconnection attempts reached".to_string(),
            });
        }

        self.reconnect_attempts += 1;
        let delay = self.backoff.next();

        info!(
            "Reconnecting in {:?} (attempt {})",
            delay, self.reconnect_attempts
        );

        let _ = self
            .event_tx
            .send(VoiceStreamEvent::Reconnecting {
                attempt: self.reconnect_attempts,
                delay_ms: delay.as_millis() as u64,
            })
            .await;

        tokio::time::sleep(delay).await;
        self.connect().await
    }
}

// ============================================================================
// WebSocket Event Handler
// ============================================================================

/// Handle WebSocket events and convert to voice events.
async fn handle_websocket_events(
    mut event_rx: mpsc::Receiver<WebSocketEvent>,
    state: Arc<RwLock<VoiceStreamState>>,
    event_tx: mpsc::Sender<VoiceStreamEvent>,
    state_tx: watch::Sender<VoiceStreamState>,
) {
    while let Some(event) = event_rx.recv().await {
        match event {
            WebSocketEvent::Connected => {
                debug!("WebSocket connected");
                let mut s = state.write().await;
                *s = VoiceStreamState::Ready;
                let _ = state_tx.send(VoiceStreamState::Ready);
            }

            WebSocketEvent::Disconnected(reason) => {
                warn!("WebSocket disconnected: {}", reason);
                let mut s = state.write().await;
                *s = VoiceStreamState::Disconnected;
                let _ = state_tx.send(VoiceStreamState::Disconnected);
                let _ = event_tx
                    .send(VoiceStreamEvent::Disconnected { reason })
                    .await;
            }

            WebSocketEvent::Message(msg) => {
                if let WebSocketMessage::Text(text) = msg {
                    if let Ok(voice_msg) = VoiceMessage::from_json(&text) {
                        handle_voice_message(voice_msg, &state, &event_tx, &state_tx).await;
                    }
                } else if let WebSocketMessage::Binary(data) = msg {
                    // Binary message is TTS audio
                    let response = TtsResponse {
                        audio_data: data,
                        format: AudioFormat::tts_playback(),
                        text: String::new(),
                        duration_ms: 0,
                    };
                    let _ = event_tx.send(VoiceStreamEvent::TtsAudio(response)).await;
                }
            }

            WebSocketEvent::Error(err) => {
                error!("WebSocket error: {}", err);
                let _ = event_tx
                    .send(VoiceStreamEvent::Error(VoiceStreamError::ConnectionFailed {
                        message: err,
                    }))
                    .await;
            }

            WebSocketEvent::Reconnecting { attempt, backoff_ms } => {
                let _ = event_tx
                    .send(VoiceStreamEvent::Reconnecting {
                        attempt,
                        delay_ms: backoff_ms,
                    })
                    .await;
            }
        }
    }
}

/// Handle a voice protocol message.
async fn handle_voice_message(
    msg: VoiceMessage,
    state: &Arc<RwLock<VoiceStreamState>>,
    event_tx: &mpsc::Sender<VoiceStreamEvent>,
    state_tx: &watch::Sender<VoiceStreamState>,
) {
    match msg {
        VoiceMessage::Transcript { text, is_final } => {
            let _ = event_tx
                .send(VoiceStreamEvent::TranscriptUpdate { text, is_final })
                .await;
        }

        VoiceMessage::FinalTranscript { text } => {
            let result = TranscriptionResult {
                text,
                is_final: true,
                confidence: None,
                language: None,
                duration_ms: 0,
            };
            let _ = event_tx
                .send(VoiceStreamEvent::TranscriptFinal(result))
                .await;
        }

        VoiceMessage::Response { text, intent } => {
            let _ = event_tx
                .send(VoiceStreamEvent::ResponseText { text, intent })
                .await;
        }

        VoiceMessage::TtsAudio { data, format } => {
            if let Ok(audio_data) = BASE64.decode(&data) {
                let response = TtsResponse {
                    audio_data,
                    format: format.unwrap_or_else(AudioFormat::tts_playback),
                    text: String::new(),
                    duration_ms: 0,
                };
                // Update state to speaking
                let mut s = state.write().await;
                *s = VoiceStreamState::Speaking;
                let _ = state_tx.send(VoiceStreamState::Speaking);
                let _ = event_tx.send(VoiceStreamEvent::TtsAudio(response)).await;
            }
        }

        VoiceMessage::Error { message, code } => {
            error!("Server error: {} ({:?})", message, code);
            let _ = event_tx
                .send(VoiceStreamEvent::Error(VoiceStreamError::ServerError {
                    message,
                }))
                .await;
        }

        VoiceMessage::SessionStart { session_id } => {
            info!("Session started: {}", session_id);
            let _ = event_tx
                .send(VoiceStreamEvent::Connected {
                    session_id: Some(session_id),
                })
                .await;
        }

        VoiceMessage::SessionEnd {
            session_id,
            duration_ms,
        } => {
            info!("Session ended: {} ({}ms)", session_id, duration_ms);
            let mut s = state.write().await;
            *s = VoiceStreamState::Ready;
            let _ = state_tx.send(VoiceStreamState::Ready);
        }

        VoiceMessage::Pong { .. } => {
            debug!("Pong received");
        }

        _ => {}
    }
}

// ============================================================================
// UniFFI Object Wrapper
// ============================================================================

/// UniFFI-compatible voice stream client wrapper.
#[derive(uniffi::Object)]
pub struct MeshVoiceStream {
    config: VoiceConfig,
    state: Arc<RwLock<VoiceStreamState>>,
}

#[uniffi::export]
impl MeshVoiceStream {
    /// Create a new voice stream.
    #[uniffi::constructor]
    pub fn new(endpoint: String) -> Self {
        Self {
            config: VoiceConfig::with_endpoint(endpoint),
            state: Arc::new(RwLock::new(VoiceStreamState::Idle)),
        }
    }

    /// Create with full config.
    #[uniffi::constructor]
    pub fn with_config(config: VoiceConfig) -> Self {
        Self {
            config,
            state: Arc::new(RwLock::new(VoiceStreamState::Idle)),
        }
    }

    /// Get current state.
    pub fn get_state(&self) -> VoiceStreamState {
        tokio::task::block_in_place(|| {
            tokio::runtime::Handle::current()
                .block_on(async { *self.state.read().await })
        })
    }

    /// Get the endpoint URL.
    pub fn endpoint(&self) -> String {
        self.config.endpoint.clone()
    }

    /// Get the WebSocket URL.
    pub fn websocket_url(&self) -> String {
        self.config.websocket_url()
    }

    /// Check if connected.
    pub fn is_connected(&self) -> bool {
        self.get_state().is_connected()
    }

    /// Check if active.
    pub fn is_active(&self) -> bool {
        self.get_state().is_active()
    }
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_fibonacci_backoff() {
        let mut backoff = FibonacciBackoff::new(89, 30000);

        // First few Fibonacci numbers starting at 89
        assert_eq!(backoff.next().as_millis(), 89);
        assert_eq!(backoff.next().as_millis(), 178); // 89 + 89
        assert_eq!(backoff.next().as_millis(), 267); // 89 + 178
        assert_eq!(backoff.next().as_millis(), 445); // 178 + 267
    }

    #[test]
    fn test_fibonacci_backoff_max() {
        let mut backoff = FibonacciBackoff::new(89, 500);

        // Should cap at max
        for _ in 0..20 {
            let delay = backoff.next();
            assert!(delay.as_millis() <= 500);
        }
    }

    #[test]
    fn test_fibonacci_backoff_reset() {
        let mut backoff = FibonacciBackoff::new(89, 30000);

        backoff.next();
        backoff.next();
        backoff.next();

        backoff.reset();
        assert_eq!(backoff.next().as_millis(), 89);
    }

    #[test]
    fn test_audio_buffer() {
        let mut buffer = AudioBuffer::new(3, 1024);

        // Add chunks
        buffer.push(AudioChunk::new(vec![1, 2, 3], 0, 0));
        buffer.push(AudioChunk::new(vec![4, 5, 6], 100, 1));
        buffer.push(AudioChunk::new(vec![7, 8, 9], 200, 2));

        assert_eq!(buffer.len(), 3);
        assert_eq!(buffer.total_bytes(), 9);

        // Add one more - should evict oldest
        buffer.push(AudioChunk::new(vec![10, 11, 12], 300, 3));
        assert_eq!(buffer.len(), 3);

        // Take all
        let chunks = buffer.take_all();
        assert_eq!(chunks.len(), 3);
        assert!(buffer.is_empty());
    }

    #[test]
    fn test_voice_stream_state() {
        assert!(!VoiceStreamState::Idle.is_active());
        assert!(!VoiceStreamState::Connecting.is_active());
        assert!(!VoiceStreamState::Ready.is_active());
        assert!(VoiceStreamState::Listening.is_active());
        assert!(VoiceStreamState::Processing.is_active());
        assert!(VoiceStreamState::Speaking.is_active());
        assert!(!VoiceStreamState::Error.is_active());
        assert!(!VoiceStreamState::Disconnected.is_active());
    }

    #[tokio::test]
    async fn test_voice_stream_client_creation() {
        let config = VoiceConfig::with_endpoint("ws://localhost:8080/ws/voice");
        let (client, _rx) = VoiceStreamClient::new(config);

        assert_eq!(client.state().await, VoiceStreamState::Idle);
        assert!(!client.is_connected().await);
    }
}

/*
 * kagami
 * Voice flows through the mesh.
 * h(x) >= 0. Always.
 */
