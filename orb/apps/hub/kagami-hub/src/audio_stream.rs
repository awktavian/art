//! Low-Latency Audio Streaming Client
//!
//! WebSocket client for receiving and playing audio from the Kagami API.
//!
//! ARCHITECTURE:
//! =============
//!
//!     ┌─────────────────────────────────────────────────────────────────┐
//!     │                    AudioStreamClient                             │
//!     │                                                                  │
//!     │   WebSocket Connection                                          │
//!     │   - Connects to /hub/audio/stream                               │
//!     │   - Receives earcon cache at startup                            │
//!     │   - Receives audio events in real-time                          │
//!     │                                                                  │
//!     │   Earcon Cache                                                   │
//!     │   - Pre-loaded sounds stored in memory                          │
//!     │   - Instant playback (<20ms)                                    │
//!     │                                                                  │
//!     │   Stream Buffer                                                  │
//!     │   - Reassembles out-of-order chunks                             │
//!     │   - Jitter buffer for smooth playback                           │
//!     │   - Gap detection and concealment                               │
//!     │                                                                  │
//!     │   Audio Player                                                   │
//!     │   - cpal-based playback                                         │
//!     │   - Handles earcons, events, and streams                        │
//!     │                                                                  │
//!     └─────────────────────────────────────────────────────────────────┘
//!
//! LATENCY TARGETS:
//! ================
//!
//!     Earcon:      <20ms  (play from cache)
//!     AudioEvent:  <50ms  (decode and play)
//!     Stream:      <100ms (buffer and start)
//!
//! STREAMING PROTOCOL:
//! ===================
//!
//!     Server → StreamStart { stream_id, metadata, total_duration_ms }
//!            → StreamChunk { stream_id, sequence: 0, audio_data }
//!            → StreamChunk { stream_id, sequence: 1, audio_data }
//!            → ...
//!            → StreamEnd   { stream_id, total_chunks, total_duration_ms }
//!
//!     Chunks may arrive out-of-order due to network conditions.
//!     The jitter buffer holds JITTER_BUFFER_MS of audio before playback starts.
//!
//! Created: January 4, 2026
//! Colony: Forge (e2) — Building for speed
//!
//! h(x) >= 0. Always.

use anyhow::{Context, Result};
use base64::Engine;
use futures_util::{SinkExt, StreamExt};
use lru::LruCache;
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, HashMap, HashSet};
use std::num::NonZeroUsize;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use tokio::sync::mpsc;
use tokio_tungstenite::{connect_async, tungstenite::Message};
use tracing::{debug, error, info, warn};

#[cfg(feature = "audio")]
use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};

// ============================================================================
// Configuration Constants
// ============================================================================

// Reconnection parameters (exponential backoff)
const INITIAL_RECONNECT_DELAY_MS: u64 = 500;
const MAX_RECONNECT_DELAY_MS: u64 = 30000;
const RECONNECT_MULTIPLIER: f64 = 1.2;

// Streaming buffer parameters

/// Jitter buffer size in milliseconds - hold this much audio before starting playback.
///
/// # Design Tradeoff
/// 80ms is a compromise between:
/// - **Lower values (20-40ms)**: Faster time-to-first-audio but more susceptible
///   to network jitter causing playback stutters
/// - **Higher values (150-300ms)**: More resilient to jitter but noticeable delay
///   between server sending audio and user hearing it
///
/// At 80ms, we tolerate typical WiFi jitter (~20-50ms) while keeping latency
/// under our 100ms target for streaming audio. This matches the latency of
/// most real-time voice applications (Zoom, Discord use 60-100ms buffers).
const JITTER_BUFFER_MS: u64 = 80;

/// Maximum time to wait for missing chunks before gap concealment (ms).
const GAP_TIMEOUT_MS: u64 = 200;

/// Maximum number of concurrent streams (prevent resource exhaustion).
///
/// # Design Tradeoff
/// 4 concurrent streams is a constraint chosen to balance:
/// - **Resource usage**: Each stream buffers audio data (~10-50KB typical),
///   maintains BTreeMap of chunks, and may spawn playback threads
/// - **Practical use cases**: Home audio rarely needs >4 simultaneous
///   streams (e.g., TTS + earcon + background music + alert)
/// - **Priority management**: With >4 streams, priority eviction becomes
///   complex and error-prone
///
/// If exceeded, the lowest-priority stream is evicted to make room.
const MAX_CONCURRENT_STREAMS: usize = 4;
/// Maximum number of earcons to cache (LRU eviction when exceeded)
/// Typical earcon is ~1-2KB (100ms at 16kHz mono), so 64 earcons ≈ 128KB max
const MAX_EARCON_CACHE_SIZE: usize = 64;

// ============================================================================
// Active Stream Management
// ============================================================================

/// State of an active audio stream being received
#[derive(Debug)]
pub struct ActiveStream {
    /// Unique stream identifier
    pub stream_id: String,
    /// Audio metadata (sample rate, channels, format)
    pub metadata: AudioMetadata,
    /// Expected total duration (if known)
    pub total_duration_ms: Option<f64>,
    /// Priority level (higher = more important)
    pub priority: u8,
    /// Volume multiplier
    pub volume: f32,
    /// Target room (None = all rooms)
    pub room: Option<String>,
    /// Request ID for correlation
    pub request_id: String,
    /// Timestamp when stream started
    pub start_time: Instant,
    /// Chunks received, indexed by sequence number (BTreeMap keeps them sorted)
    pub chunks: BTreeMap<u32, Vec<f32>>,
    /// Highest sequence number received
    pub highest_sequence: u32,
    /// Next sequence number to play
    pub next_play_sequence: u32,
    /// Expected total chunks (set when StreamEnd received)
    pub expected_total_chunks: Option<u32>,
    /// Has playback started?
    pub playback_started: bool,
    /// Total samples buffered (for jitter calculation)
    pub samples_buffered: usize,
    /// Timestamp of last chunk received
    pub last_chunk_time: Instant,
    /// Has stream ended (StreamEnd received)?
    pub stream_ended: bool,
    /// Gaps detected but not yet concealed (missing sequence numbers).
    /// Uses HashSet for O(1) lookup performance during gap detection.
    /// When a late chunk arrives, it's removed from this set.
    pub detected_gaps: HashSet<u32>,
    /// Gaps that have been concealed with silence (for metrics/debugging).
    /// These sequence numbers had missing chunks that timed out and were
    /// replaced with silence. Tracked separately from detected_gaps to
    /// distinguish between "waiting for chunk" and "gave up and concealed".
    pub concealed_gaps: HashSet<u32>,
}

impl ActiveStream {
    /// Create a new active stream from StreamStart message
    pub fn new(
        stream_id: String,
        metadata: AudioMetadata,
        total_duration_ms: Option<f64>,
        priority: u8,
        volume: f32,
        room: Option<String>,
        request_id: String,
    ) -> Self {
        let now = Instant::now();
        Self {
            stream_id,
            metadata,
            total_duration_ms,
            priority,
            volume,
            room,
            request_id,
            start_time: now,
            chunks: BTreeMap::new(),
            highest_sequence: 0,
            next_play_sequence: 0,
            expected_total_chunks: None,
            playback_started: false,
            samples_buffered: 0,
            last_chunk_time: now,
            stream_ended: false,
            detected_gaps: HashSet::new(),
            concealed_gaps: HashSet::new(),
        }
    }

    /// Add a chunk to the buffer.
    ///
    /// Returns `true` if the chunk was added successfully, `false` if it was
    /// a duplicate (already received). Handles out-of-order delivery by
    /// tracking gaps and removing them when late chunks arrive.
    pub fn add_chunk(&mut self, sequence: u32, samples: Vec<f32>) -> bool {
        if self.chunks.contains_key(&sequence) {
            debug!(
                "Stream {}: Duplicate chunk seq={}, ignoring",
                self.stream_id, sequence
            );
            return false;
        }

        // Track highest sequence and detect gaps
        if sequence > self.highest_sequence {
            if self.highest_sequence > 0 && sequence > self.highest_sequence + 1 {
                for gap_seq in (self.highest_sequence + 1)..sequence {
                    if self.detected_gaps.insert(gap_seq) {
                        debug!("Stream {}: Gap detected at seq={}", self.stream_id, gap_seq);
                    }
                }
            }
            self.highest_sequence = sequence;
        }

        // Remove from gaps if this was a missing chunk that arrived late (O(1) with HashSet)
        self.detected_gaps.remove(&sequence);

        self.samples_buffered += samples.len();
        self.last_chunk_time = Instant::now();
        self.chunks.insert(sequence, samples);

        debug!(
            "Stream {}: Added chunk seq={}, buffer={} samples, gaps={:?}",
            self.stream_id, sequence, self.samples_buffered, self.detected_gaps
        );
        true
    }

    /// Calculate buffered duration in milliseconds.
    ///
    /// Returns 0.0 if sample_rate or channels are invalid (zero).
    /// This prevents division by zero and handles malformed metadata gracefully.
    pub fn buffered_duration_ms(&self) -> f64 {
        // Validate metadata to prevent division by zero
        if self.metadata.sample_rate == 0 {
            warn!(
                "Stream {}: Invalid sample_rate=0, cannot calculate duration",
                self.stream_id
            );
            return 0.0;
        }
        if self.metadata.channels == 0 {
            warn!(
                "Stream {}: Invalid channels=0, cannot calculate duration",
                self.stream_id
            );
            return 0.0;
        }

        let samples_per_ms =
            (self.metadata.sample_rate as f64 * self.metadata.channels as f64) / 1000.0;
        // samples_per_ms is guaranteed non-zero since both inputs are non-zero
        self.samples_buffered as f64 / samples_per_ms
    }

    /// Check if we have enough buffer to start playback
    pub fn ready_to_play(&self) -> bool {
        self.buffered_duration_ms() >= JITTER_BUFFER_MS as f64 || self.stream_ended
    }

    /// Extract contiguous samples starting from next_play_sequence
    pub fn extract_contiguous_samples(&mut self) -> Vec<f32> {
        let mut samples = Vec::new();
        while let Some(chunk_samples) = self.chunks.remove(&self.next_play_sequence) {
            self.samples_buffered = self.samples_buffered.saturating_sub(chunk_samples.len());
            samples.extend(chunk_samples);
            self.next_play_sequence += 1;
        }
        samples
    }

    /// Check if stream is complete (all chunks received and played)
    pub fn is_complete(&self) -> bool {
        if let Some(total) = self.expected_total_chunks {
            self.stream_ended && self.next_play_sequence >= total && self.chunks.is_empty()
        } else {
            false
        }
    }

    /// Get gaps that have timed out and should be concealed.
    ///
    /// Returns sequence numbers of chunks that have been missing for longer
    /// than `GAP_TIMEOUT_MS`. These should be filled with silence to allow
    /// playback to continue without waiting indefinitely.
    pub fn get_timed_out_gaps(&self) -> Vec<u32> {
        let timeout = Duration::from_millis(GAP_TIMEOUT_MS);
        if self.last_chunk_time.elapsed() > timeout {
            self.detected_gaps.iter().copied().collect()
        } else {
            Vec::new()
        }
    }

    /// Conceal a gap by inserting silence.
    ///
    /// When a chunk is missing for too long, we insert silence to allow
    /// playback to continue. The silence duration is estimated from the
    /// average chunk size of existing chunks.
    ///
    /// Concealed gaps are tracked separately in `concealed_gaps` for metrics
    /// and debugging purposes, allowing us to distinguish between:
    /// - Gaps waiting for late chunks (in `detected_gaps`)
    /// - Gaps that timed out and were filled with silence (in `concealed_gaps`)
    pub fn conceal_gap(&mut self, sequence: u32) {
        if self.chunks.contains_key(&sequence) {
            return;
        }

        // Estimate chunk size from existing chunks
        let avg_chunk_size = if self.chunks.is_empty() {
            (self.metadata.sample_rate as usize * self.metadata.channels as usize) / 50
        } else {
            let total: usize = self.chunks.values().map(|c| c.len()).sum();
            total / self.chunks.len()
        };

        let silence = vec![0.0f32; avg_chunk_size];
        self.chunks.insert(sequence, silence);
        self.samples_buffered += avg_chunk_size;

        // Move from detected to concealed (O(1) operations with HashSet)
        self.detected_gaps.remove(&sequence);
        self.concealed_gaps.insert(sequence);

        warn!(
            "Stream {}: Gap concealed at seq={} with {} samples of silence (total concealed: {})",
            self.stream_id, sequence, avg_chunk_size, self.concealed_gaps.len()
        );
    }

    /// Get count of gaps that have been concealed with silence.
    ///
    /// This is useful for quality metrics - high concealed gap counts indicate
    /// network issues or packet loss.
    pub fn concealed_gap_count(&self) -> usize {
        self.concealed_gaps.len()
    }

    /// Get count of gaps still waiting for late chunks.
    pub fn pending_gap_count(&self) -> usize {
        self.detected_gaps.len()
    }
}

/// Manager for active streams
#[derive(Debug, Default)]
pub struct StreamManager {
    streams: HashMap<String, ActiveStream>,
}

impl StreamManager {
    pub fn new() -> Self {
        Self {
            streams: HashMap::new(),
        }
    }

    /// Start a new stream
    pub fn start_stream(&mut self, stream: ActiveStream) -> Result<()> {
        if self.streams.len() >= MAX_CONCURRENT_STREAMS {
            let lowest_priority = self
                .streams
                .iter()
                .min_by_key(|(_, s)| s.priority)
                .map(|(id, _)| id.clone());

            if let Some(id) = lowest_priority {
                warn!("Max streams reached, evicting stream {}", id);
                self.streams.remove(&id);
            }
        }

        let stream_id = stream.stream_id.clone();
        self.streams.insert(stream_id.clone(), stream);
        info!("Started stream: {}", stream_id);
        Ok(())
    }

    /// Add chunk to a stream
    pub fn add_chunk(&mut self, stream_id: &str, sequence: u32, samples: Vec<f32>) -> Result<bool> {
        if let Some(stream) = self.streams.get_mut(stream_id) {
            Ok(stream.add_chunk(sequence, samples))
        } else {
            warn!("Chunk for unknown stream: {}", stream_id);
            Ok(false)
        }
    }

    /// Mark stream as ended
    pub fn end_stream(&mut self, stream_id: &str, total_chunks: u32) -> Option<&mut ActiveStream> {
        if let Some(stream) = self.streams.get_mut(stream_id) {
            stream.stream_ended = true;
            stream.expected_total_chunks = Some(total_chunks);
            Some(stream)
        } else {
            None
        }
    }

    /// Get a stream by ID
    pub fn get_stream(&self, stream_id: &str) -> Option<&ActiveStream> {
        self.streams.get(stream_id)
    }

    /// Get mutable stream by ID
    pub fn get_stream_mut(&mut self, stream_id: &str) -> Option<&mut ActiveStream> {
        self.streams.get_mut(stream_id)
    }

    /// Remove a completed stream
    pub fn remove_stream(&mut self, stream_id: &str) -> Option<ActiveStream> {
        self.streams.remove(stream_id)
    }

    /// Get all streams ready to play
    pub fn streams_ready_to_play(&self) -> Vec<&str> {
        self.streams
            .iter()
            .filter(|(_, s)| s.ready_to_play() && !s.playback_started)
            .map(|(id, _)| id.as_str())
            .collect()
    }

    /// Get stream count
    pub fn stream_count(&self) -> usize {
        self.streams.len()
    }
}

/// Cached earcon audio data
#[derive(Debug, Clone)]
pub struct CachedEarcon {
    pub name: String,
    pub samples: Vec<f32>,
    pub sample_rate: u32,
    pub channels: u16,
    pub duration_ms: f32,
}

/// Audio message types from the server
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type")]
pub enum AudioMessage {
    #[serde(rename = "earcon")]
    Earcon {
        name: String,
        priority: u8,
        volume: f32,
        room: Option<String>,
        request_id: String,
        timestamp: f64,
    },

    #[serde(rename = "audio_event")]
    AudioEvent {
        audio_url: Option<String>,
        audio_data: Option<String>,
        metadata: AudioMetadata,
        text: Option<String>,
        priority: u8,
        volume: f32,
        room: Option<String>,
        request_id: String,
        timestamp: f64,
    },

    #[serde(rename = "stream_start")]
    StreamStart {
        stream_id: String,
        metadata: AudioMetadata,
        total_duration_ms: Option<f64>,
        priority: u8,
        volume: f32,
        room: Option<String>,
        request_id: String,
        timestamp: f64,
    },

    #[serde(rename = "stream_chunk")]
    StreamChunk {
        stream_id: String,
        sequence: u32,
        audio_data: String,
        timestamp: f64,
    },

    #[serde(rename = "stream_end")]
    StreamEnd {
        stream_id: String,
        total_chunks: u32,
        total_duration_ms: f64,
        timestamp: f64,
    },

    #[serde(rename = "stop")]
    Stop {
        stream_id: Option<String>,
        reason: String,
        timestamp: f64,
    },

    #[serde(rename = "volume")]
    Volume {
        volume: f32,
        room: Option<String>,
        timestamp: f64,
    },

    #[serde(rename = "cache_earcon")]
    CacheEarcon {
        name: String,
        audio_data: String,
        metadata: AudioMetadata,
        timestamp: f64,
    },

    #[serde(rename = "pong")]
    Pong { timestamp: f64 },
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct AudioMetadata {
    pub sample_rate: u32,
    pub channels: u16,
    pub format: String,
    pub duration_ms: Option<f64>,
    pub spatial: Option<serde_json::Value>,
}

/// Statistics for audio streaming
#[derive(Debug, Clone, Default)]
pub struct AudioStreamStats {
    pub earcons_cached: u32,
    pub earcons_played: u64,
    pub events_played: u64,
    pub streams_played: u64,
    pub avg_latency_ms: f64,
    pub last_play_time: u64,
}

/// Audio event emitted to the application
#[derive(Debug, Clone)]
pub enum AudioEvent {
    Connected,
    Disconnected,
    EarconCached {
        name: String,
        duration_ms: f32,
    },
    AudioPlayed {
        request_id: String,
        duration_ms: f32,
    },
    Error(String),
}

/// Low-latency audio streaming client
pub struct AudioStreamClient {
    api_url: String,
    hub_id: String,
    auth_token: Option<String>,

    // Connection state
    connected: Arc<AtomicBool>,
    last_message_time_ms: Arc<AtomicU64>,
    start_instant: Instant,

    // Earcon cache (LRU bounded to prevent memory exhaustion)
    earcon_cache: Arc<Mutex<LruCache<String, CachedEarcon>>>,

    // Stream manager for active audio streams
    stream_manager: Arc<Mutex<StreamManager>>,

    // Event channel
    event_tx: mpsc::Sender<AudioEvent>,

    // Control channels
    shutdown_tx: Option<mpsc::Sender<()>>,

    // Stats
    stats: Arc<Mutex<AudioStreamStats>>,

    // Volume
    master_volume: Arc<std::sync::atomic::AtomicU32>,
}

impl AudioStreamClient {
    /// Create a new audio stream client
    pub fn new(api_url: &str, hub_id: &str) -> (Self, mpsc::Receiver<AudioEvent>) {
        let (event_tx, event_rx) = mpsc::channel(256);

        // Create bounded LRU cache for earcons
        // NonZeroUsize is safe because MAX_EARCON_CACHE_SIZE is a non-zero constant
        let cache_size = NonZeroUsize::new(MAX_EARCON_CACHE_SIZE)
            .expect("MAX_EARCON_CACHE_SIZE must be non-zero");

        (
            Self {
                api_url: api_url.to_string(),
                hub_id: hub_id.to_string(),
                auth_token: None,
                connected: Arc::new(AtomicBool::new(false)),
                last_message_time_ms: Arc::new(AtomicU64::new(0)),
                start_instant: Instant::now(),
                earcon_cache: Arc::new(Mutex::new(LruCache::new(cache_size))),
                stream_manager: Arc::new(Mutex::new(StreamManager::new())),
                event_tx,
                shutdown_tx: None,
                stats: Arc::new(Mutex::new(AudioStreamStats::default())),
                master_volume: Arc::new(std::sync::atomic::AtomicU32::new(f32::to_bits(1.0))),
            },
            event_rx,
        )
    }

    /// Get active stream count
    pub fn active_stream_count(&self) -> usize {
        self.stream_manager.lock().unwrap().stream_count()
    }

    /// Create client with authentication
    pub fn with_auth(
        api_url: &str,
        hub_id: &str,
        auth_token: &str,
    ) -> (Self, mpsc::Receiver<AudioEvent>) {
        let (mut client, rx) = Self::new(api_url, hub_id);
        client.auth_token = Some(auth_token.to_string());
        (client, rx)
    }

    /// Check if connected
    pub fn is_connected(&self) -> bool {
        self.connected.load(Ordering::Relaxed)
    }

    /// Get number of cached earcons
    pub fn earcon_count(&self) -> usize {
        self.earcon_cache.lock().unwrap().len()
    }

    /// Get list of cached earcon names
    pub fn earcon_names(&self) -> Vec<String> {
        self.earcon_cache.lock().unwrap().iter().map(|(k, _)| k.clone()).collect()
    }

    /// Get statistics
    pub fn stats(&self) -> AudioStreamStats {
        self.stats.lock().unwrap().clone()
    }

    /// Set master volume (0.0-1.0)
    ///
    /// Uses SeqCst ordering to ensure volume changes are immediately visible
    /// across all threads, preventing race conditions where audio might be
    /// played at an inconsistent volume level.
    pub fn set_volume(&self, volume: f32) {
        let clamped = volume.clamp(0.0, 1.0);
        self.master_volume
            .store(f32::to_bits(clamped), Ordering::SeqCst);
    }

    /// Get master volume
    ///
    /// Uses SeqCst ordering for consistent reads across threads.
    pub fn volume(&self) -> f32 {
        f32::from_bits(self.master_volume.load(Ordering::SeqCst))
    }

    /// Start the audio stream connection
    pub async fn start(&mut self) -> Result<()> {
        let (shutdown_tx, mut shutdown_rx) = mpsc::channel::<()>(1);
        self.shutdown_tx = Some(shutdown_tx);

        let api_url = self.api_url.clone();
        let hub_id = self.hub_id.clone();
        let auth_token = self.auth_token.clone();
        let connected = Arc::clone(&self.connected);
        let last_message_time_ms = Arc::clone(&self.last_message_time_ms);
        let start_instant = self.start_instant;
        let earcon_cache = Arc::clone(&self.earcon_cache);
        let stream_manager = Arc::clone(&self.stream_manager);
        let event_tx = self.event_tx.clone();
        let stats = Arc::clone(&self.stats);
        let master_volume = Arc::clone(&self.master_volume);

        tokio::spawn(async move {
            let mut reconnect_delay = Duration::from_millis(INITIAL_RECONNECT_DELAY_MS);

            loop {
                tokio::select! {
                    _ = shutdown_rx.recv() => {
                        info!("Audio stream shutdown requested");
                        break;
                    }
                    result = Self::connect_and_run(
                        &api_url,
                        &hub_id,
                        auth_token.as_deref(),
                        &connected,
                        &last_message_time_ms,
                        start_instant,
                        &earcon_cache,
                        &stream_manager,
                        &event_tx,
                        &stats,
                        &master_volume,
                    ) => {
                        if let Err(e) = result {
                            warn!("Audio stream error: {}", e);
                        }

                        connected.store(false, Ordering::Relaxed);
                        let _ = event_tx.try_send(AudioEvent::Disconnected);

                        // Exponential backoff
                        info!("Reconnecting audio stream in {:?}", reconnect_delay);
                        tokio::time::sleep(reconnect_delay).await;

                        reconnect_delay = Duration::from_millis(
                            (reconnect_delay.as_millis() as f64 * RECONNECT_MULTIPLIER) as u64
                        ).min(Duration::from_millis(MAX_RECONNECT_DELAY_MS));
                    }
                }
            }
        });

        Ok(())
    }

    /// Stop the audio stream connection
    pub async fn stop(&mut self) {
        if let Some(tx) = self.shutdown_tx.take() {
            let _ = tx.send(()).await;
        }
    }

    /// Connect and run the WebSocket loop
    async fn connect_and_run(
        api_url: &str,
        hub_id: &str,
        auth_token: Option<&str>,
        connected: &AtomicBool,
        last_message_time_ms: &AtomicU64,
        start_instant: Instant,
        earcon_cache: &Arc<Mutex<LruCache<String, CachedEarcon>>>,
        stream_manager: &Arc<Mutex<StreamManager>>,
        event_tx: &mpsc::Sender<AudioEvent>,
        stats: &Arc<Mutex<AudioStreamStats>>,
        master_volume: &std::sync::atomic::AtomicU32,
    ) -> Result<()> {
        // Build WebSocket URL
        let ws_url = if api_url.starts_with("https://") {
            api_url.replace("https://", "wss://")
        } else {
            api_url.replace("http://", "ws://")
        };

        let mut url = format!("{}/hub/audio/stream?hub_id={}", ws_url, hub_id);
        if let Some(token) = auth_token {
            url = format!("{}&token={}", url, token);
        }

        info!("Connecting to audio stream: {}", url);

        let (ws_stream, _) = connect_async(&url)
            .await
            .context("Failed to connect to audio stream")?;

        let (mut write, mut read) = ws_stream.split();

        connected.store(true, Ordering::Relaxed);
        let _ = event_tx.try_send(AudioEvent::Connected);
        info!("Audio stream connected");

        // Main message loop
        while let Some(msg) = read.next().await {
            let msg = msg.context("WebSocket read error")?;

            // Record message time
            let now = start_instant.elapsed().as_millis() as u64;
            last_message_time_ms.store(now, Ordering::Relaxed);

            match msg {
                Message::Text(text) => {
                    if let Err(e) = Self::handle_message(
                        &text,
                        earcon_cache,
                        stream_manager,
                        event_tx,
                        stats,
                        master_volume,
                    )
                    .await
                    {
                        warn!("Error handling audio message: {}", e);
                    }
                }
                Message::Binary(data) => {
                    debug!("Received binary audio data: {} bytes", data.len());
                    // Binary audio could be handled here for raw streaming
                }
                Message::Ping(data) => {
                    let _ = write.send(Message::Pong(data)).await;
                }
                Message::Close(_) => {
                    info!("Audio stream closed by server");
                    break;
                }
                _ => {}
            }
        }

        Ok(())
    }

    /// Handle an incoming audio message
    async fn handle_message(
        text: &str,
        earcon_cache: &Arc<Mutex<LruCache<String, CachedEarcon>>>,
        stream_manager: &Arc<Mutex<StreamManager>>,
        event_tx: &mpsc::Sender<AudioEvent>,
        stats: &Arc<Mutex<AudioStreamStats>>,
        master_volume: &std::sync::atomic::AtomicU32,
    ) -> Result<()> {
        let msg: AudioMessage =
            serde_json::from_str(text).context("Failed to parse audio message")?;

        let volume = f32::from_bits(master_volume.load(Ordering::SeqCst));

        match msg {
            AudioMessage::Earcon {
                name,
                volume: msg_vol,
                request_id,
                ..
            } => {
                let effective_volume = volume * msg_vol;
                Self::play_earcon(
                    &name,
                    effective_volume,
                    earcon_cache,
                    event_tx,
                    stats,
                    &request_id,
                )
                .await?;
            }

            AudioMessage::AudioEvent {
                audio_data,
                metadata,
                volume: msg_vol,
                request_id,
                ..
            } => {
                if let Some(data) = audio_data {
                    let effective_volume = volume * msg_vol;
                    Self::play_audio_data(
                        &data,
                        &metadata,
                        effective_volume,
                        event_tx,
                        stats,
                        &request_id,
                    )
                    .await?;
                }
            }

            AudioMessage::CacheEarcon {
                name,
                audio_data,
                metadata,
                ..
            } => {
                Self::cache_earcon(&name, &audio_data, &metadata, earcon_cache, event_tx, stats)?;
            }

            AudioMessage::Stop {
                stream_id, reason, ..
            } => {
                info!("Stop audio: stream={:?}, reason={}", stream_id, reason);
                if let Some(id) = stream_id {
                    let mut manager = stream_manager.lock().unwrap();
                    if let Some(_stream) = manager.remove_stream(&id) {
                        info!("Stream {} stopped: {}", id, reason);
                    }
                }
            }

            AudioMessage::Volume {
                volume: new_vol, ..
            } => {
                master_volume.store(f32::to_bits(new_vol), Ordering::SeqCst);
                info!("Volume set to {}", new_vol);
            }

            AudioMessage::StreamStart {
                stream_id,
                metadata,
                total_duration_ms,
                priority,
                volume: msg_vol,
                room,
                request_id,
                ..
            } => {
                info!(
                    "Stream start: {} (sample_rate={}, channels={}, duration={:?}ms)",
                    stream_id, metadata.sample_rate, metadata.channels, total_duration_ms
                );

                let stream = ActiveStream::new(
                    stream_id.clone(),
                    metadata,
                    total_duration_ms,
                    priority,
                    volume * msg_vol,
                    room,
                    request_id,
                );

                let mut manager = stream_manager.lock().unwrap();
                if let Err(e) = manager.start_stream(stream) {
                    warn!("Failed to start stream {}: {}", stream_id, e);
                }
            }

            AudioMessage::StreamChunk {
                stream_id,
                sequence,
                audio_data,
                ..
            } => {
                // Decode base64 audio data to f32 samples
                let bytes = base64::engine::general_purpose::STANDARD
                    .decode(&audio_data)
                    .context("Failed to decode stream chunk")?;

                // Validate that audio data is properly aligned for f32 (4 bytes per sample)
                if bytes.len() % 4 != 0 {
                    warn!(
                        "Stream {}: Malformed audio chunk at seq={}, {} bytes is not divisible by 4. Truncating {} trailing bytes.",
                        stream_id,
                        sequence,
                        bytes.len(),
                        bytes.len() % 4
                    );
                }

                // Handle empty or too-small chunks gracefully
                if bytes.len() < 4 {
                    warn!(
                        "Stream {}: Empty or insufficient audio data at seq={} ({} bytes), skipping",
                        stream_id, sequence, bytes.len()
                    );
                    return Ok(());
                }

                let samples: Vec<f32> = bytes
                    .chunks_exact(4)
                    .map(|chunk| f32::from_le_bytes([chunk[0], chunk[1], chunk[2], chunk[3]]))
                    .collect();

                debug!(
                    "Stream chunk: {} seq={} samples={}",
                    stream_id,
                    sequence,
                    samples.len()
                );

                // Add chunk to stream buffer
                let should_play = {
                    let mut manager = stream_manager.lock().unwrap();
                    let _ = manager.add_chunk(&stream_id, sequence, samples);

                    // Check if any streams are ready to start playback
                    if let Some(stream) = manager.get_stream_mut(&stream_id) {
                        // Handle any timed-out gaps
                        let timed_out_gaps = stream.get_timed_out_gaps();
                        for gap in timed_out_gaps {
                            stream.conceal_gap(gap);
                        }

                        // Check if ready to play and hasn't started yet
                        stream.ready_to_play() && !stream.playback_started
                    } else {
                        false
                    }
                };

                // Start playback if ready
                if should_play {
                    Self::play_buffered_stream(&stream_id, stream_manager, event_tx, stats, volume)
                        .await?;
                }
            }

            AudioMessage::StreamEnd {
                stream_id,
                total_chunks,
                total_duration_ms,
                ..
            } => {
                info!(
                    "Stream end: {} ({} chunks, {}ms)",
                    stream_id, total_chunks, total_duration_ms
                );

                let should_finalize = {
                    let mut manager = stream_manager.lock().unwrap();
                    if let Some(stream) = manager.end_stream(&stream_id, total_chunks) {
                        // Conceal any remaining gaps before final playback
                        // Collect to Vec to avoid borrow issues during mutation
                        let gaps: Vec<u32> = stream.detected_gaps.iter().copied().collect();
                        for gap in gaps {
                            stream.conceal_gap(gap);
                        }
                        !stream.playback_started
                    } else {
                        false
                    }
                };

                // Play any remaining buffered audio
                if should_finalize {
                    Self::play_buffered_stream(&stream_id, stream_manager, event_tx, stats, volume)
                        .await?;
                }

                // Clean up completed stream
                {
                    let mut manager = stream_manager.lock().unwrap();
                    if let Some(stream) = manager.get_stream(&stream_id) {
                        if stream.is_complete() {
                            manager.remove_stream(&stream_id);
                            info!("Stream {} completed and cleaned up", stream_id);
                        }
                    }
                }
            }

            AudioMessage::Pong { .. } => {
                debug!("Pong received");
            }
        }

        Ok(())
    }

    /// Play buffered stream audio through the speaker
    async fn play_buffered_stream(
        stream_id: &str,
        stream_manager: &Arc<Mutex<StreamManager>>,
        event_tx: &mpsc::Sender<AudioEvent>,
        stats: &Arc<Mutex<AudioStreamStats>>,
        master_volume: f32,
    ) -> Result<()> {
        // Extract stream info and samples
        let (samples, metadata, request_id, stream_volume) = {
            let mut manager = stream_manager.lock().unwrap();
            if let Some(stream) = manager.get_stream_mut(stream_id) {
                stream.playback_started = true;

                let samples = stream.extract_contiguous_samples();
                let metadata = stream.metadata.clone();
                let request_id = stream.request_id.clone();
                let stream_volume = stream.volume;

                (samples, metadata, request_id, stream_volume)
            } else {
                return Ok(());
            }
        };

        if samples.is_empty() {
            debug!("Stream {}: No samples to play", stream_id);
            return Ok(());
        }

        let effective_volume = master_volume * stream_volume;
        let duration_ms = (samples.len() as f32 / metadata.channels as f32)
            / metadata.sample_rate as f32
            * 1000.0;

        info!(
            "Playing stream {}: {} samples, {}ms at volume {}",
            stream_id,
            samples.len(),
            duration_ms,
            effective_volume
        );

        // Play the audio
        #[cfg(feature = "audio")]
        Self::play_samples(
            &samples,
            metadata.sample_rate,
            metadata.channels,
            effective_volume,
        )?;

        // Update stats
        {
            let mut s = stats.lock().unwrap();
            s.streams_played += 1;
            s.last_play_time = std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_millis() as u64;
        }

        let _ = event_tx.try_send(AudioEvent::AudioPlayed {
            request_id,
            duration_ms,
        });

        Ok(())
    }

    /// Play an earcon from cache
    async fn play_earcon(
        name: &str,
        volume: f32,
        earcon_cache: &Arc<Mutex<LruCache<String, CachedEarcon>>>,
        event_tx: &mpsc::Sender<AudioEvent>,
        stats: &Arc<Mutex<AudioStreamStats>>,
        request_id: &str,
    ) -> Result<()> {
        let earcon = {
            // LruCache::get requires &mut self to update LRU order
            let mut cache = earcon_cache.lock().unwrap();
            cache.get(name).cloned()
        };

        if let Some(earcon) = earcon {
            let duration_ms = earcon.duration_ms;

            // Play audio
            #[cfg(feature = "audio")]
            Self::play_samples(&earcon.samples, earcon.sample_rate, earcon.channels, volume)?;

            // Update stats
            {
                let mut s = stats.lock().unwrap();
                s.earcons_played += 1;
                s.last_play_time = std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap()
                    .as_millis() as u64;
            }

            let _ = event_tx.try_send(AudioEvent::AudioPlayed {
                request_id: request_id.to_string(),
                duration_ms,
            });

            debug!("Played earcon '{}' ({}ms)", name, duration_ms);
        } else {
            warn!("Earcon '{}' not found in cache", name);
        }

        Ok(())
    }

    /// Play raw audio data
    async fn play_audio_data(
        audio_data: &str,
        metadata: &AudioMetadata,
        volume: f32,
        event_tx: &mpsc::Sender<AudioEvent>,
        stats: &Arc<Mutex<AudioStreamStats>>,
        request_id: &str,
    ) -> Result<()> {
        // Validate metadata before processing
        if metadata.sample_rate == 0 {
            return Err(anyhow::anyhow!(
                "Invalid audio metadata: sample_rate cannot be 0"
            ));
        }
        if metadata.channels == 0 {
            return Err(anyhow::anyhow!(
                "Invalid audio metadata: channels cannot be 0"
            ));
        }

        // Decode base64
        let bytes = base64::engine::general_purpose::STANDARD
            .decode(audio_data)
            .context("Failed to decode audio data")?;

        // Validate audio data alignment
        if bytes.len() % 4 != 0 {
            warn!(
                "Malformed audio data: {} bytes is not divisible by 4, truncating {} trailing bytes",
                bytes.len(),
                bytes.len() % 4
            );
        }

        if bytes.len() < 4 {
            warn!(
                "Audio data too small ({} bytes), cannot play",
                bytes.len()
            );
            return Ok(());
        }

        // Convert to f32 samples
        let samples: Vec<f32> = bytes
            .chunks_exact(4)
            .map(|chunk| f32::from_le_bytes([chunk[0], chunk[1], chunk[2], chunk[3]]))
            .collect();

        let duration_ms = (samples.len() as f32 / metadata.channels as f32)
            / metadata.sample_rate as f32
            * 1000.0;

        // Play audio
        #[cfg(feature = "audio")]
        Self::play_samples(&samples, metadata.sample_rate, metadata.channels, volume)?;

        // Update stats
        {
            let mut s = stats.lock().unwrap();
            s.events_played += 1;
            s.last_play_time = std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_millis() as u64;
        }

        let _ = event_tx.try_send(AudioEvent::AudioPlayed {
            request_id: request_id.to_string(),
            duration_ms,
        });

        debug!("Played audio event ({}ms)", duration_ms);

        Ok(())
    }

    /// Cache an earcon
    fn cache_earcon(
        name: &str,
        audio_data: &str,
        metadata: &AudioMetadata,
        earcon_cache: &Arc<Mutex<LruCache<String, CachedEarcon>>>,
        event_tx: &mpsc::Sender<AudioEvent>,
        stats: &Arc<Mutex<AudioStreamStats>>,
    ) -> Result<()> {
        // Validate metadata
        if metadata.sample_rate == 0 {
            return Err(anyhow::anyhow!(
                "Invalid earcon metadata: sample_rate cannot be 0"
            ));
        }
        if metadata.channels == 0 {
            return Err(anyhow::anyhow!(
                "Invalid earcon metadata: channels cannot be 0"
            ));
        }

        // Decode base64
        let bytes = base64::engine::general_purpose::STANDARD
            .decode(audio_data)
            .context("Failed to decode earcon audio")?;

        // Validate audio data alignment
        if bytes.len() % 4 != 0 {
            warn!(
                "Earcon '{}': Malformed audio data, {} bytes is not divisible by 4",
                name,
                bytes.len()
            );
        }

        if bytes.is_empty() {
            warn!("Earcon '{}': Empty audio data, skipping cache", name);
            return Ok(());
        }

        // Convert to f32 samples
        let samples: Vec<f32> = bytes
            .chunks_exact(4)
            .map(|chunk| f32::from_le_bytes([chunk[0], chunk[1], chunk[2], chunk[3]]))
            .collect();

        if samples.is_empty() {
            warn!(
                "Earcon '{}': No valid samples after decoding ({} bytes)",
                name,
                bytes.len()
            );
            return Ok(());
        }

        let duration_ms = (samples.len() as f32 / metadata.channels as f32)
            / metadata.sample_rate as f32
            * 1000.0;

        let earcon = CachedEarcon {
            name: name.to_string(),
            samples,
            sample_rate: metadata.sample_rate,
            channels: metadata.channels,
            duration_ms,
        };

        {
            let mut cache = earcon_cache.lock().unwrap();
            // LruCache::push returns the evicted entry if cache was full
            if let Some((evicted_name, _)) = cache.push(name.to_string(), earcon) {
                debug!(
                    "Earcon cache full ({} entries), evicted '{}' to make room for '{}'",
                    MAX_EARCON_CACHE_SIZE, evicted_name, name
                );
            }
        }

        {
            let mut s = stats.lock().unwrap();
            s.earcons_cached += 1;
        }

        let _ = event_tx.try_send(AudioEvent::EarconCached {
            name: name.to_string(),
            duration_ms,
        });

        debug!("Cached earcon '{}' ({}ms)", name, duration_ms);

        Ok(())
    }

    /// Play audio samples through the default output device
    #[cfg(feature = "audio")]
    fn play_samples(samples: &[f32], sample_rate: u32, channels: u16, volume: f32) -> Result<()> {
        use std::sync::mpsc;

        let host = cpal::default_host();
        let device = host
            .default_output_device()
            .ok_or_else(|| anyhow::anyhow!("No output device available"))?;

        let config = cpal::StreamConfig {
            channels,
            sample_rate: cpal::SampleRate(sample_rate),
            buffer_size: cpal::BufferSize::Default,
        };

        // Apply volume and clone for the closure
        let samples: Vec<f32> = samples.iter().map(|s| s * volume).collect();
        let sample_idx = Arc::new(Mutex::new(0usize));
        let (done_tx, done_rx) = mpsc::channel();

        let stream = device.build_output_stream(
            &config,
            move |data: &mut [f32], _: &cpal::OutputCallbackInfo| {
                let mut idx = sample_idx.lock().unwrap();
                for sample in data.iter_mut() {
                    if *idx < samples.len() {
                        *sample = samples[*idx];
                        *idx += 1;
                    } else {
                        *sample = 0.0;
                    }
                }
                if *idx >= samples.len() {
                    let _ = done_tx.send(());
                }
            },
            move |err| {
                error!("Audio output error: {}", err);
            },
            None,
        )?;

        stream.play()?;

        // Wait for playback to complete (with timeout)
        let _ = done_rx.recv_timeout(Duration::from_secs(30));

        Ok(())
    }

    #[cfg(not(feature = "audio"))]
    fn play_samples(
        _samples: &[f32],
        _sample_rate: u32,
        _channels: u16,
        _volume: f32,
    ) -> Result<()> {
        warn!("Audio playback not available (audio feature disabled)");
        Ok(())
    }
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    fn create_test_metadata() -> AudioMetadata {
        AudioMetadata {
            sample_rate: 48000,
            channels: 2,
            format: "f32le".to_string(),
            duration_ms: Some(1000.0),
            spatial: None,
        }
    }

    #[test]
    fn test_active_stream_creation() {
        let metadata = create_test_metadata();
        let stream = ActiveStream::new(
            "test-stream-1".to_string(),
            metadata,
            Some(1000.0),
            5,
            0.8,
            Some("Living Room".to_string()),
            "req-123".to_string(),
        );

        assert_eq!(stream.stream_id, "test-stream-1");
        assert_eq!(stream.priority, 5);
        assert_eq!(stream.volume, 0.8);
        assert_eq!(stream.highest_sequence, 0);
        assert_eq!(stream.next_play_sequence, 0);
        assert!(!stream.playback_started);
        assert!(!stream.stream_ended);
        assert!(stream.chunks.is_empty());
    }

    #[test]
    fn test_add_chunk_sequential() {
        let metadata = create_test_metadata();
        let mut stream = ActiveStream::new(
            "test-stream".to_string(),
            metadata,
            None,
            5,
            1.0,
            None,
            "req-1".to_string(),
        );

        // Add chunks in order
        let chunk0 = vec![0.1f32; 960]; // 10ms at 48kHz stereo
        let chunk1 = vec![0.2f32; 960];
        let chunk2 = vec![0.3f32; 960];

        assert!(stream.add_chunk(0, chunk0));
        assert!(stream.add_chunk(1, chunk1));
        assert!(stream.add_chunk(2, chunk2));

        assert_eq!(stream.highest_sequence, 2);
        assert_eq!(stream.chunks.len(), 3);
        assert!(stream.detected_gaps.is_empty());
        assert_eq!(stream.samples_buffered, 960 * 3);
    }

    #[test]
    fn test_add_chunk_out_of_order() {
        let metadata = create_test_metadata();
        let mut stream = ActiveStream::new(
            "test-stream".to_string(),
            metadata,
            None,
            5,
            1.0,
            None,
            "req-1".to_string(),
        );

        // Add chunk 0
        stream.add_chunk(0, vec![0.1f32; 100]);
        // Skip chunk 1, add chunk 2
        stream.add_chunk(2, vec![0.3f32; 100]);

        assert_eq!(stream.highest_sequence, 2);
        assert!(stream.detected_gaps.contains(&1));

        // Now add the missing chunk 1 (late arrival)
        stream.add_chunk(1, vec![0.2f32; 100]);
        assert!(!stream.detected_gaps.contains(&1));
        assert_eq!(stream.chunks.len(), 3);
    }

    #[test]
    fn test_add_chunk_duplicate_rejected() {
        let metadata = create_test_metadata();
        let mut stream = ActiveStream::new(
            "test-stream".to_string(),
            metadata,
            None,
            5,
            1.0,
            None,
            "req-1".to_string(),
        );

        assert!(stream.add_chunk(0, vec![0.1f32; 100]));
        // Duplicate should be rejected
        assert!(!stream.add_chunk(0, vec![0.9f32; 100]));
        assert_eq!(stream.chunks.len(), 1);
    }

    #[test]
    fn test_buffered_duration_calculation() {
        let metadata = create_test_metadata();
        let mut stream = ActiveStream::new(
            "test-stream".to_string(),
            metadata,
            None,
            5,
            1.0,
            None,
            "req-1".to_string(),
        );

        // 48000 samples/sec * 2 channels = 96000 samples/sec
        // 9600 samples = 100ms
        stream.add_chunk(0, vec![0.0f32; 9600]);

        let duration = stream.buffered_duration_ms();
        assert!((duration - 100.0).abs() < 1.0);
    }

    #[test]
    fn test_ready_to_play_jitter_buffer() {
        let metadata = create_test_metadata();
        let mut stream = ActiveStream::new(
            "test-stream".to_string(),
            metadata,
            None,
            5,
            1.0,
            None,
            "req-1".to_string(),
        );

        // Not enough buffer (JITTER_BUFFER_MS = 80)
        stream.add_chunk(0, vec![0.0f32; 4800]); // 50ms
        assert!(!stream.ready_to_play());

        // Add more to exceed jitter buffer
        stream.add_chunk(1, vec![0.0f32; 4800]); // +50ms = 100ms total
        assert!(stream.ready_to_play());
    }

    #[test]
    fn test_ready_to_play_stream_ended() {
        let metadata = create_test_metadata();
        let mut stream = ActiveStream::new(
            "test-stream".to_string(),
            metadata,
            None,
            5,
            1.0,
            None,
            "req-1".to_string(),
        );

        // Small buffer, not ready yet
        stream.add_chunk(0, vec![0.0f32; 100]);
        assert!(!stream.ready_to_play());

        // Mark as ended - should be ready regardless of buffer size
        stream.stream_ended = true;
        assert!(stream.ready_to_play());
    }

    #[test]
    fn test_extract_contiguous_samples() {
        let metadata = create_test_metadata();
        let mut stream = ActiveStream::new(
            "test-stream".to_string(),
            metadata,
            None,
            5,
            1.0,
            None,
            "req-1".to_string(),
        );

        stream.add_chunk(0, vec![0.1f32; 100]);
        stream.add_chunk(1, vec![0.2f32; 100]);
        stream.add_chunk(2, vec![0.3f32; 100]);

        let samples = stream.extract_contiguous_samples();
        assert_eq!(samples.len(), 300);
        assert_eq!(stream.next_play_sequence, 3);
        assert!(stream.chunks.is_empty());
        assert_eq!(stream.samples_buffered, 0);
    }

    #[test]
    fn test_extract_stops_at_gap() {
        let metadata = create_test_metadata();
        let mut stream = ActiveStream::new(
            "test-stream".to_string(),
            metadata,
            None,
            5,
            1.0,
            None,
            "req-1".to_string(),
        );

        stream.add_chunk(0, vec![0.1f32; 100]);
        // Skip chunk 1
        stream.add_chunk(2, vec![0.3f32; 100]);
        stream.add_chunk(3, vec![0.4f32; 100]);

        // Should only extract chunk 0
        let samples = stream.extract_contiguous_samples();
        assert_eq!(samples.len(), 100);
        assert_eq!(stream.next_play_sequence, 1);
        assert_eq!(stream.chunks.len(), 2); // chunks 2 and 3 remain
    }

    #[test]
    fn test_gap_concealment() {
        let metadata = create_test_metadata();
        let mut stream = ActiveStream::new(
            "test-stream".to_string(),
            metadata,
            None,
            5,
            1.0,
            None,
            "req-1".to_string(),
        );

        stream.add_chunk(0, vec![0.1f32; 100]);
        stream.add_chunk(2, vec![0.3f32; 100]); // Gap at 1

        assert!(stream.detected_gaps.contains(&1));

        // Conceal the gap
        stream.conceal_gap(1);

        assert!(!stream.detected_gaps.contains(&1));
        assert!(stream.chunks.contains_key(&1));

        // Now extraction should work continuously
        let samples = stream.extract_contiguous_samples();
        assert_eq!(samples.len(), 300); // All three chunks
    }

    #[test]
    fn test_stream_is_complete() {
        let metadata = create_test_metadata();
        let mut stream = ActiveStream::new(
            "test-stream".to_string(),
            metadata,
            None,
            5,
            1.0,
            None,
            "req-1".to_string(),
        );

        stream.add_chunk(0, vec![0.1f32; 100]);
        stream.add_chunk(1, vec![0.2f32; 100]);

        // Not complete yet
        assert!(!stream.is_complete());

        // Mark ended with total_chunks
        stream.stream_ended = true;
        stream.expected_total_chunks = Some(2);

        // Still not complete (chunks not played)
        assert!(!stream.is_complete());

        // Extract all
        stream.extract_contiguous_samples();

        // Now complete
        assert!(stream.is_complete());
    }

    #[test]
    fn test_stream_manager_start_stream() {
        let mut manager = StreamManager::new();
        let metadata = create_test_metadata();

        let stream = ActiveStream::new(
            "stream-1".to_string(),
            metadata,
            None,
            5,
            1.0,
            None,
            "req-1".to_string(),
        );

        assert!(manager.start_stream(stream).is_ok());
        assert_eq!(manager.stream_count(), 1);
        assert!(manager.get_stream("stream-1").is_some());
    }

    #[test]
    fn test_stream_manager_max_streams() {
        let mut manager = StreamManager::new();

        // Add MAX_CONCURRENT_STREAMS streams
        for i in 0..MAX_CONCURRENT_STREAMS {
            let metadata = create_test_metadata();
            let stream = ActiveStream::new(
                format!("stream-{}", i),
                metadata,
                None,
                (i + 1) as u8, // Higher priority for later streams
                1.0,
                None,
                format!("req-{}", i),
            );
            assert!(manager.start_stream(stream).is_ok());
        }

        assert_eq!(manager.stream_count(), MAX_CONCURRENT_STREAMS);

        // Add one more - should evict lowest priority (stream-0 with priority 1)
        let metadata = create_test_metadata();
        let stream = ActiveStream::new(
            "stream-new".to_string(),
            metadata,
            None,
            10,
            1.0,
            None,
            "req-new".to_string(),
        );
        assert!(manager.start_stream(stream).is_ok());

        assert_eq!(manager.stream_count(), MAX_CONCURRENT_STREAMS);
        assert!(manager.get_stream("stream-0").is_none()); // Evicted
        assert!(manager.get_stream("stream-new").is_some());
    }

    #[test]
    fn test_stream_manager_add_chunk() {
        let mut manager = StreamManager::new();
        let metadata = create_test_metadata();

        let stream = ActiveStream::new(
            "stream-1".to_string(),
            metadata,
            None,
            5,
            1.0,
            None,
            "req-1".to_string(),
        );
        manager.start_stream(stream).unwrap();

        assert!(manager.add_chunk("stream-1", 0, vec![0.1f32; 100]).unwrap());
        assert!(manager.add_chunk("stream-1", 1, vec![0.2f32; 100]).unwrap());

        // Chunk for unknown stream
        assert!(!manager
            .add_chunk("unknown-stream", 0, vec![0.0f32; 100])
            .unwrap());
    }

    #[test]
    fn test_stream_manager_end_stream() {
        let mut manager = StreamManager::new();
        let metadata = create_test_metadata();

        let stream = ActiveStream::new(
            "stream-1".to_string(),
            metadata,
            None,
            5,
            1.0,
            None,
            "req-1".to_string(),
        );
        manager.start_stream(stream).unwrap();

        let stream_ref = manager.end_stream("stream-1", 10).unwrap();
        assert!(stream_ref.stream_ended);
        assert_eq!(stream_ref.expected_total_chunks, Some(10));
    }

    #[test]
    fn test_stream_manager_streams_ready_to_play() {
        let mut manager = StreamManager::new();
        let metadata = create_test_metadata();

        let stream = ActiveStream::new(
            "stream-1".to_string(),
            metadata,
            None,
            5,
            1.0,
            None,
            "req-1".to_string(),
        );
        manager.start_stream(stream).unwrap();

        // Not ready yet (empty buffer)
        assert!(manager.streams_ready_to_play().is_empty());

        // Add enough buffer
        manager
            .add_chunk("stream-1", 0, vec![0.0f32; 9600])
            .unwrap(); // 100ms

        assert_eq!(manager.streams_ready_to_play().len(), 1);
    }
}

/*
 * Forge (e2) - Building for speed
 * The voice of the mirror, delivered instantly.
 * h(x) >= 0. Always.
 */
