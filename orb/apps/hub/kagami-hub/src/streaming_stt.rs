//! Streaming Speech-to-Text with Ring Buffer
//!
//! Low-latency STT implementation using a ring buffer for audio capture.
//! Targets <500ms end-to-end latency for responsive voice interaction.
//!
//! Features:
//! - 500ms sliding window ring buffer
//! - Voice Activity Detection (VAD)
//! - Silence detection for endpoint determination
//! - Streaming transcription (no batching)
//! - Configurable sample rate and chunk size
//!
//! Colony: Flow (e3) - Sensing, adaptation
//!
//! h(x) >= 0. Always.

use anyhow::{Context, Result};
use std::collections::VecDeque;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::{mpsc, Mutex};
use tracing::{debug, info, warn};

// ============================================================================
// Configuration
// ============================================================================

/// Streaming STT configuration
#[derive(Debug, Clone)]
pub struct StreamingSTTConfig {
    /// Audio sample rate in Hz
    pub sample_rate: u32,
    /// Chunk size in samples (for processing)
    pub chunk_size: usize,
    /// Ring buffer duration in milliseconds
    pub buffer_duration_ms: u32,
    /// Silence threshold (RMS below this = silence)
    pub silence_threshold: f32,
    /// Minimum speech duration to trigger transcription (ms)
    pub min_speech_duration_ms: u32,
    /// Maximum silence duration before endpoint (ms)
    pub max_silence_duration_ms: u32,
    /// Target end-to-end latency (ms)
    pub target_latency_ms: u32,
    /// Enable VAD (Voice Activity Detection)
    pub vad_enabled: bool,
}

impl Default for StreamingSTTConfig {
    fn default() -> Self {
        Self {
            sample_rate: 16000,           // 16kHz standard for STT
            chunk_size: 512,              // ~32ms chunks at 16kHz
            buffer_duration_ms: 500,      // 500ms ring buffer (P1 requirement)
            silence_threshold: 0.01,      // RMS threshold for silence
            min_speech_duration_ms: 100,  // Min speech before processing
            max_silence_duration_ms: 300, // Max silence before endpoint
            target_latency_ms: 500,       // Target <500ms e2e (P1 requirement)
            vad_enabled: true,
        }
    }
}

// ============================================================================
// Ring Buffer
// ============================================================================

/// Audio ring buffer for streaming capture
/// Implements a fixed-size circular buffer for audio samples
pub struct AudioRingBuffer {
    /// Internal buffer (VecDeque for efficient push/pop)
    buffer: VecDeque<f32>,
    /// Maximum buffer capacity in samples
    capacity: usize,
    /// Sample rate
    sample_rate: u32,
    /// Current write position timestamp
    write_timestamp_ms: u64,
}

impl AudioRingBuffer {
    /// Create a new ring buffer with specified duration
    pub fn new(duration_ms: u32, sample_rate: u32) -> Self {
        let capacity = (duration_ms as usize * sample_rate as usize) / 1000;

        Self {
            buffer: VecDeque::with_capacity(capacity),
            capacity,
            sample_rate,
            write_timestamp_ms: 0,
        }
    }

    /// Push audio samples into the buffer
    /// Older samples are automatically evicted when capacity is exceeded
    pub fn push(&mut self, samples: &[f32]) {
        for &sample in samples {
            if self.buffer.len() >= self.capacity {
                self.buffer.pop_front();
            }
            self.buffer.push_back(sample);
        }

        // Update timestamp
        let samples_ms = (samples.len() as u64 * 1000) / self.sample_rate as u64;
        self.write_timestamp_ms += samples_ms;
    }

    /// Get all samples in the buffer
    pub fn get_all(&self) -> Vec<f32> {
        self.buffer.iter().copied().collect()
    }

    /// Get the last N milliseconds of audio
    pub fn get_last_ms(&self, duration_ms: u32) -> Vec<f32> {
        let samples_needed = (duration_ms as usize * self.sample_rate as usize) / 1000;
        let samples_to_take = samples_needed.min(self.buffer.len());

        self.buffer.iter()
            .skip(self.buffer.len().saturating_sub(samples_to_take))
            .copied()
            .collect()
    }

    /// Get current buffer length in samples
    pub fn len(&self) -> usize {
        self.buffer.len()
    }

    /// Check if buffer is empty
    pub fn is_empty(&self) -> bool {
        self.buffer.is_empty()
    }

    /// Clear the buffer
    pub fn clear(&mut self) {
        self.buffer.clear();
        self.write_timestamp_ms = 0;
    }

    /// Get buffer duration in milliseconds
    pub fn duration_ms(&self) -> u32 {
        ((self.buffer.len() as u64 * 1000) / self.sample_rate as u64) as u32
    }
}

// ============================================================================
// Voice Activity Detection
// ============================================================================

/// Voice Activity Detection state
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum VadState {
    /// No speech detected
    Silence,
    /// Possible speech (below threshold duration)
    MaybeSpeech,
    /// Confirmed speech
    Speech,
    /// Speech ending (silence after speech)
    Ending,
}

/// Voice Activity Detector
pub struct VoiceActivityDetector {
    config: StreamingSTTConfig,
    state: VadState,
    speech_start_time: Option<Instant>,
    silence_start_time: Option<Instant>,
    /// RMS history for smoothing
    rms_history: VecDeque<f32>,
}

impl VoiceActivityDetector {
    /// Create a new VAD with config
    pub fn new(config: &StreamingSTTConfig) -> Self {
        Self {
            config: config.clone(),
            state: VadState::Silence,
            speech_start_time: None,
            silence_start_time: None,
            rms_history: VecDeque::with_capacity(10),
        }
    }

    /// Process audio chunk and update VAD state
    /// Returns (state, speech_detected, endpoint_detected)
    pub fn process(&mut self, samples: &[f32]) -> (VadState, bool, bool) {
        let rms = calculate_rms(samples);

        // Smooth RMS with history
        self.rms_history.push_back(rms);
        if self.rms_history.len() > 10 {
            self.rms_history.pop_front();
        }
        let smoothed_rms: f32 = self.rms_history.iter().sum::<f32>() / self.rms_history.len() as f32;

        let is_speech = smoothed_rms > self.config.silence_threshold;
        let mut speech_detected = false;
        let mut endpoint_detected = false;

        match self.state {
            VadState::Silence => {
                if is_speech {
                    self.state = VadState::MaybeSpeech;
                    self.speech_start_time = Some(Instant::now());
                }
            }
            VadState::MaybeSpeech => {
                if is_speech {
                    if let Some(start) = self.speech_start_time {
                        if start.elapsed().as_millis() >= self.config.min_speech_duration_ms as u128 {
                            self.state = VadState::Speech;
                            speech_detected = true;
                            debug!("VAD: Speech confirmed after {:?}", start.elapsed());
                        }
                    }
                } else {
                    // False positive, reset
                    self.state = VadState::Silence;
                    self.speech_start_time = None;
                }
            }
            VadState::Speech => {
                if !is_speech {
                    self.state = VadState::Ending;
                    self.silence_start_time = Some(Instant::now());
                }
            }
            VadState::Ending => {
                if is_speech {
                    // Speech resumed
                    self.state = VadState::Speech;
                    self.silence_start_time = None;
                } else {
                    if let Some(start) = self.silence_start_time {
                        if start.elapsed().as_millis() >= self.config.max_silence_duration_ms as u128 {
                            // Endpoint detected
                            self.state = VadState::Silence;
                            self.speech_start_time = None;
                            self.silence_start_time = None;
                            endpoint_detected = true;
                            debug!("VAD: Endpoint detected after {:?} silence", start.elapsed());
                        }
                    }
                }
            }
        }

        (self.state, speech_detected, endpoint_detected)
    }

    /// Reset VAD state
    pub fn reset(&mut self) {
        self.state = VadState::Silence;
        self.speech_start_time = None;
        self.silence_start_time = None;
        self.rms_history.clear();
    }

    /// Get current state
    pub fn state(&self) -> VadState {
        self.state
    }

    /// Check if currently in speech
    pub fn is_speech(&self) -> bool {
        matches!(self.state, VadState::Speech | VadState::Ending)
    }
}

// ============================================================================
// Streaming STT Engine
// ============================================================================

/// Streaming STT transcription result
#[derive(Debug, Clone)]
pub struct StreamingResult {
    /// Partial or final transcription
    pub text: String,
    /// Is this a final result?
    pub is_final: bool,
    /// Confidence score (0.0 - 1.0)
    pub confidence: f32,
    /// Latency from speech end to result (ms)
    pub latency_ms: u64,
    /// Audio duration processed (ms)
    pub audio_duration_ms: u32,
}

/// Streaming STT Engine
pub struct StreamingSTT {
    config: StreamingSTTConfig,
    ring_buffer: Arc<Mutex<AudioRingBuffer>>,
    vad: Arc<Mutex<VoiceActivityDetector>>,
    /// Flag indicating if currently processing
    processing: Arc<AtomicBool>,
    /// Total latency tracking
    total_latency_ms: Arc<AtomicU64>,
    /// Result sender channel
    result_tx: Option<mpsc::Sender<StreamingResult>>,
}

impl StreamingSTT {
    /// Create a new streaming STT engine
    pub fn new(config: StreamingSTTConfig) -> (Self, mpsc::Receiver<StreamingResult>) {
        let (result_tx, result_rx) = mpsc::channel(64);

        let ring_buffer = AudioRingBuffer::new(config.buffer_duration_ms, config.sample_rate);
        let vad = VoiceActivityDetector::new(&config);

        (
            Self {
                config: config.clone(),
                ring_buffer: Arc::new(Mutex::new(ring_buffer)),
                vad: Arc::new(Mutex::new(vad)),
                processing: Arc::new(AtomicBool::new(false)),
                total_latency_ms: Arc::new(AtomicU64::new(0)),
                result_tx: Some(result_tx),
            },
            result_rx,
        )
    }

    /// Create with default configuration
    pub fn new_default() -> (Self, mpsc::Receiver<StreamingResult>) {
        Self::new(StreamingSTTConfig::default())
    }

    /// Process incoming audio chunk (non-blocking)
    /// Call this for each audio chunk from the microphone
    pub async fn process_audio(&self, samples: &[f32]) -> Result<()> {
        let process_start = Instant::now();

        // Add to ring buffer
        {
            let mut buffer = self.ring_buffer.lock().await;
            buffer.push(samples);
        }

        // Run VAD
        let (state, speech_detected, endpoint_detected) = {
            let mut vad = self.vad.lock().await;
            vad.process(samples)
        };

        // If speech detected and not already processing, start transcription
        if speech_detected && !self.processing.load(Ordering::Relaxed) {
            debug!("Speech detected, starting transcription stream");
        }

        // If endpoint detected, finalize transcription
        if endpoint_detected {
            let audio_data = {
                let buffer = self.ring_buffer.lock().await;
                buffer.get_all()
            };

            if !audio_data.is_empty() {
                // Calculate latency
                let latency = process_start.elapsed().as_millis() as u64;
                self.total_latency_ms.store(latency, Ordering::Relaxed);

                // Send for transcription
                self.transcribe_audio(&audio_data, true, latency).await?;

                // Clear buffer for next utterance
                let mut buffer = self.ring_buffer.lock().await;
                buffer.clear();
            }
        }

        // Check latency target
        let elapsed_ms = process_start.elapsed().as_millis() as u32;
        if elapsed_ms > self.config.target_latency_ms / 4 {
            warn!(
                "Audio processing took {}ms (target chunk: {}ms)",
                elapsed_ms,
                self.config.target_latency_ms / 4
            );
        }

        Ok(())
    }

    /// Transcribe audio data
    async fn transcribe_audio(&self, audio: &[f32], is_final: bool, latency_ms: u64) -> Result<()> {
        self.processing.store(true, Ordering::Relaxed);

        // Calculate audio duration
        let audio_duration_ms = ((audio.len() as u64 * 1000) / self.config.sample_rate as u64) as u32;

        // In production: Send to Whisper/Deepgram/etc.
        // For now, placeholder transcription
        let result = StreamingResult {
            text: "[transcription placeholder]".to_string(),
            is_final,
            confidence: 0.9,
            latency_ms,
            audio_duration_ms,
        };

        // Send result
        if let Some(ref tx) = self.result_tx {
            tx.send(result).await.context("Failed to send STT result")?;
        }

        self.processing.store(false, Ordering::Relaxed);
        Ok(())
    }

    /// Get current VAD state
    pub async fn vad_state(&self) -> VadState {
        let vad = self.vad.lock().await;
        vad.state()
    }

    /// Check if speech is currently detected
    pub async fn is_speech(&self) -> bool {
        let vad = self.vad.lock().await;
        vad.is_speech()
    }

    /// Reset the engine state
    pub async fn reset(&self) {
        let mut buffer = self.ring_buffer.lock().await;
        buffer.clear();

        let mut vad = self.vad.lock().await;
        vad.reset();

        self.processing.store(false, Ordering::Relaxed);
        debug!("Streaming STT reset");
    }

    /// Get average latency
    pub fn average_latency_ms(&self) -> u64 {
        self.total_latency_ms.load(Ordering::Relaxed)
    }

    /// Get configuration
    pub fn config(&self) -> &StreamingSTTConfig {
        &self.config
    }
}

// ============================================================================
// Audio Processing Utilities
// ============================================================================

/// Calculate RMS (Root Mean Square) of audio samples
fn calculate_rms(samples: &[f32]) -> f32 {
    if samples.is_empty() {
        return 0.0;
    }

    let sum_sq: f32 = samples.iter().map(|s| s * s).sum();
    (sum_sq / samples.len() as f32).sqrt()
}

/// Convert i16 PCM samples to f32
pub fn i16_to_f32(samples: &[i16]) -> Vec<f32> {
    samples.iter().map(|&s| s as f32 / 32768.0).collect()
}

/// Convert f32 samples to i16 PCM
pub fn f32_to_i16(samples: &[f32]) -> Vec<i16> {
    samples.iter().map(|&s| (s * 32768.0) as i16).collect()
}

// ============================================================================
// Module-Level API
// ============================================================================

use std::sync::OnceLock;

static STREAMING_STT: OnceLock<Arc<Mutex<StreamingSTT>>> = OnceLock::new();

/// Initialize global streaming STT
pub fn init(config: StreamingSTTConfig) -> mpsc::Receiver<StreamingResult> {
    let (stt, rx) = StreamingSTT::new(config);
    let _ = STREAMING_STT.set(Arc::new(Mutex::new(stt)));
    info!("Streaming STT initialized with 500ms ring buffer");
    rx
}

/// Initialize with default configuration
pub fn init_default() -> mpsc::Receiver<StreamingResult> {
    init(StreamingSTTConfig::default())
}

/// Process audio chunk globally
pub async fn process_audio(samples: &[f32]) -> Result<()> {
    if let Some(stt) = STREAMING_STT.get() {
        let stt = stt.lock().await;
        stt.process_audio(samples).await
    } else {
        Err(anyhow::anyhow!("Streaming STT not initialized"))
    }
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ring_buffer_push() {
        let mut buffer = AudioRingBuffer::new(100, 16000); // 100ms at 16kHz

        // Push some samples
        let samples: Vec<f32> = (0..800).map(|i| (i as f32) / 800.0).collect();
        buffer.push(&samples);

        assert_eq!(buffer.len(), 800);
    }

    #[test]
    fn test_ring_buffer_overflow() {
        let mut buffer = AudioRingBuffer::new(50, 16000); // 50ms = 800 samples

        // Push more than capacity
        let samples: Vec<f32> = vec![1.0; 1600]; // 100ms worth
        buffer.push(&samples);

        // Should only keep last 800 samples
        assert_eq!(buffer.len(), 800);
    }

    #[test]
    fn test_rms_calculation() {
        let samples = vec![0.5, -0.5, 0.5, -0.5];
        let rms = calculate_rms(&samples);
        assert!((rms - 0.5).abs() < 0.001);
    }

    #[test]
    fn test_rms_silence() {
        let samples = vec![0.0; 100];
        let rms = calculate_rms(&samples);
        assert_eq!(rms, 0.0);
    }

    #[test]
    fn test_vad_initial_state() {
        let config = StreamingSTTConfig::default();
        let vad = VoiceActivityDetector::new(&config);
        assert_eq!(vad.state(), VadState::Silence);
    }

    #[test]
    fn test_i16_f32_conversion() {
        let i16_samples: Vec<i16> = vec![0, 16384, -16384, 32767, -32768];
        let f32_samples = i16_to_f32(&i16_samples);

        assert!((f32_samples[0] - 0.0).abs() < 0.001);
        assert!((f32_samples[1] - 0.5).abs() < 0.001);
        assert!((f32_samples[2] - -0.5).abs() < 0.001);
    }
}

/*
 * Flow (e3) - Sensing, adaptation
 * Listen in real-time. Respond immediately.
 * Target: <500ms end-to-end latency
 * h(x) >= 0. Always.
 */
