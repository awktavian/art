//! Real-Time Audio Pipeline
//!
//! Low-latency voice capture and playback for Kagami client.
//! Integrates with backend Whisper STT and Parler-TTS.
//!
//! Performance targets:
//! - Voice capture latency: < 100ms
//! - STT processing: < 500ms
//! - TTS playback start: < 200ms
//!
//! Colony: Flow (e₃) — Sensing, adaptation

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use tokio::sync::mpsc;
use tracing::info;

// Audio configuration
const SAMPLE_RATE: u32 = 16000;  // Whisper prefers 16kHz
const CHANNELS: u16 = 1;         // Mono for speech
const CHUNK_SIZE_MS: u32 = 100;  // 100ms chunks for streaming

/// Voice activity detection state
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum VoiceState {
    Idle,
    Listening,
    Processing,
    Speaking,
}

/// Audio pipeline manager
pub struct AudioPipeline {
    state: Arc<std::sync::RwLock<VoiceState>>,
    is_recording: Arc<AtomicBool>,
    audio_tx: Option<mpsc::Sender<AudioChunk>>,
}

#[derive(Debug, Clone)]
pub struct AudioChunk {
    pub samples: Vec<i16>,
    pub timestamp_ms: u64,
}

impl Default for AudioPipeline {
    fn default() -> Self {
        Self::new()
    }
}

impl AudioPipeline {
    pub fn new() -> Self {
        Self {
            state: Arc::new(std::sync::RwLock::new(VoiceState::Idle)),
            is_recording: Arc::new(AtomicBool::new(false)),
            audio_tx: None,
        }
    }

    /// Get current voice state
    pub fn state(&self) -> VoiceState {
        self.state
            .read()
            .map(|guard| *guard)
            .unwrap_or(VoiceState::Idle)
    }

    /// Check if recording
    pub fn is_recording(&self) -> bool {
        self.is_recording.load(Ordering::Relaxed)
    }

    /// Start voice capture
    pub async fn start_capture(&mut self) -> Result<()> {
        if self.is_recording() {
            return Ok(());
        }

        info!("Starting voice capture...");
        self.is_recording.store(true, Ordering::Relaxed);
        if let Ok(mut guard) = self.state.write() {
            *guard = VoiceState::Listening;
        }

        // In full implementation, this would start audio capture
        // using cpal or platform-specific APIs

        Ok(())
    }

    /// Stop voice capture and return audio data
    pub async fn stop_capture(&mut self) -> Result<Vec<i16>> {
        if !self.is_recording() {
            return Ok(vec![]);
        }

        info!("Stopping voice capture...");
        self.is_recording.store(false, Ordering::Relaxed);
        if let Ok(mut guard) = self.state.write() {
            *guard = VoiceState::Processing;
        }

        // In full implementation, this would return captured audio
        Ok(vec![])
    }

    /// Send audio to backend for transcription
    pub async fn transcribe(&self, audio: &[i16]) -> Result<String> {
        if audio.is_empty() {
            return Ok(String::new());
        }

        info!("Transcribing {} samples...", audio.len());

        // Convert to WAV bytes
        let wav_data = self.samples_to_wav(audio)?;

        // Send to API
        let client = reqwest::Client::new();
        let form = reqwest::multipart::Form::new()
            .part("audio", reqwest::multipart::Part::bytes(wav_data)
                .file_name("recording.wav")
                .mime_str("audio/wav")?
            );

        let response: reqwest::Response = client
            .post("https://api.awkronos.com/audio/transcribe")
            .multipart(form)
            .send()
            .await
            .context("Failed to send audio")?;

        if !response.status().is_success() {
            return Err(anyhow::anyhow!("Transcription failed: {}", response.status()));
        }

        #[derive(Deserialize)]
        struct TranscribeResponse {
            text: String,
        }

        let result: TranscribeResponse = response.json().await?;
        if let Ok(mut guard) = self.state.write() {
            *guard = VoiceState::Idle;
        }

        Ok(result.text)
    }

    /// Trigger TTS via backend
    pub async fn speak(&self, text: &str, colony: Option<&str>, rooms: Option<Vec<String>>) -> Result<()> {
        if text.is_empty() {
            return Ok(());
        }

        info!("Speaking: '{}'", text);
        if let Ok(mut guard) = self.state.write() {
            *guard = VoiceState::Speaking;
        }

        let api = crate::api_client::get_api();
        api.announce(text, rooms, colony).await?;

        if let Ok(mut guard) = self.state.write() {
            *guard = VoiceState::Idle;
        }

        Ok(())
    }

    /// Convert i16 samples to WAV bytes
    fn samples_to_wav(&self, samples: &[i16]) -> Result<Vec<u8>> {
        let mut wav = Vec::new();

        // WAV header
        let data_size = samples.len() * 2;
        let file_size = 36 + data_size;

        // RIFF header
        wav.extend_from_slice(b"RIFF");
        wav.extend_from_slice(&(file_size as u32).to_le_bytes());
        wav.extend_from_slice(b"WAVE");

        // fmt chunk
        wav.extend_from_slice(b"fmt ");
        wav.extend_from_slice(&16u32.to_le_bytes()); // chunk size
        wav.extend_from_slice(&1u16.to_le_bytes());  // PCM format
        wav.extend_from_slice(&CHANNELS.to_le_bytes());
        wav.extend_from_slice(&SAMPLE_RATE.to_le_bytes());
        wav.extend_from_slice(&(SAMPLE_RATE * 2).to_le_bytes()); // byte rate
        wav.extend_from_slice(&2u16.to_le_bytes()); // block align
        wav.extend_from_slice(&16u16.to_le_bytes()); // bits per sample

        // data chunk
        wav.extend_from_slice(b"data");
        wav.extend_from_slice(&(data_size as u32).to_le_bytes());

        for sample in samples {
            wav.extend_from_slice(&sample.to_le_bytes());
        }

        Ok(wav)
    }
}

// Global instance
static AUDIO: std::sync::OnceLock<tokio::sync::RwLock<AudioPipeline>> = std::sync::OnceLock::new();

pub fn get_audio() -> &'static tokio::sync::RwLock<AudioPipeline> {
    AUDIO.get_or_init(|| tokio::sync::RwLock::new(AudioPipeline::new()))
}

// ═══════════════════════════════════════════════════════════════
// TAURI COMMANDS
// ═══════════════════════════════════════════════════════════════

/// Ambient noise/audio level monitoring
pub struct AmbientAudioMonitor {
    pub current_level_db: f32,
    pub is_speaking_detected: bool,
    pub last_update: std::time::Instant,
}

impl Default for AmbientAudioMonitor {
    fn default() -> Self {
        Self {
            current_level_db: -60.0,  // Very quiet
            is_speaking_detected: false,
            last_update: std::time::Instant::now(),
        }
    }
}

impl AmbientAudioMonitor {
    /// Update ambient level from audio samples
    pub fn update_from_samples(&mut self, samples: &[i16]) {
        if samples.is_empty() {
            return;
        }

        // Calculate RMS (Root Mean Square) amplitude
        let sum_squares: f64 = samples.iter()
            .map(|&s| (s as f64) * (s as f64))
            .sum();
        let rms = (sum_squares / samples.len() as f64).sqrt();

        // Convert to dB (relative to max i16 value)
        let max_amplitude = i16::MAX as f64;
        let level_db = if rms > 0.0 {
            20.0 * (rms / max_amplitude).log10()
        } else {
            -100.0
        };

        // Smoothing: exponential moving average
        let alpha = 0.3;
        self.current_level_db = (alpha * level_db + (1.0 - alpha) * self.current_level_db as f64) as f32;

        // Simple voice activity detection
        // Speaking is typically -30 to -10 dB range
        self.is_speaking_detected = self.current_level_db > -35.0;

        self.last_update = std::time::Instant::now();
    }

    /// Get current ambient audio state
    pub fn get_state(&self) -> AmbientAudioState {
        AmbientAudioState {
            level_db: self.current_level_db,
            is_speaking: self.is_speaking_detected,
            age_ms: self.last_update.elapsed().as_millis() as u64,
        }
    }
}

// Global ambient monitor
static AMBIENT_MONITOR: std::sync::OnceLock<std::sync::RwLock<AmbientAudioMonitor>> = std::sync::OnceLock::new();

pub fn get_ambient_monitor() -> &'static std::sync::RwLock<AmbientAudioMonitor> {
    AMBIENT_MONITOR.get_or_init(|| std::sync::RwLock::new(AmbientAudioMonitor::default()))
}

#[derive(Debug, Serialize)]
pub struct AudioState {
    pub state: String,
    pub is_recording: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct AmbientAudioState {
    pub level_db: f32,
    pub is_speaking: bool,
    pub age_ms: u64,
}

#[tauri::command]
pub async fn get_audio_state() -> Result<AudioState, String> {
    let audio = get_audio().read().await;
    Ok(AudioState {
        state: format!("{:?}", audio.state()),
        is_recording: audio.is_recording(),
    })
}

#[tauri::command]
pub async fn get_ambient_audio_state() -> Result<AmbientAudioState, String> {
    let monitor = get_ambient_monitor().read().map_err(|e| e.to_string())?;
    Ok(monitor.get_state())
}

#[tauri::command]
pub async fn start_voice_capture() -> Result<(), String> {
    let mut audio = get_audio().write().await;
    audio.start_capture().await.map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn stop_voice_capture() -> Result<String, String> {
    let mut audio = get_audio().write().await;
    let samples = audio.stop_capture().await.map_err(|e| e.to_string())?;
    audio.transcribe(&samples).await.map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn speak_text(
    text: String,
    colony: Option<String>,
    rooms: Option<Vec<String>>,
) -> Result<(), String> {
    let audio = get_audio().read().await;
    audio.speak(&text, colony.as_deref(), rooms).await.map_err(|e| e.to_string())
}

/*
 * 鏡
 * Voice is presence. Sound is connection.
 */
