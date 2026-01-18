//! Voice Controller — Full Pipeline Orchestration
//!
//! Integrates all voice components into a cohesive pipeline:
//! Wake Word → Audio Capture → STT → Speaker ID → Command Parse → API → TTS → Playback
//!
//! UNIFIED PIPELINE: This controller implements the Rust side of the UnifiedVoicePipeline.
//! The Python side (kagami.core.voice) handles TTS output via the voice effector.
//! Speaker identification uses embeddings matched against household voice profiles.
//!
//! Colony: All colonies collaborate on voice processing
//!   - Flow (e₃): Audio sensing, STT
//!   - Nexus (e₄): Speaker ID, API integration
//!   - Crystal (e₇): Speech output
//!
//! η → s → μ → a → η′
//! h(x) ≥ 0. Always.

use anyhow::Result;
use chrono::Timelike;
use std::sync::Arc;
use tokio::sync::Mutex;
use tracing::{debug, error, info, warn};

use crate::api_client::KagamiAPI;
use crate::audio::{detect_silence, AudioCapture, AudioConfig, AudioPlayback};
use crate::config::HubConfig;
use crate::feedback::FeedbackGenerator;
use crate::speaker_id::{generate_personalized_greeting, SpeakerIdentifier, SpeakerMatch};
use crate::stt::{STTConfig, STTEngine};
use crate::tts::{generate_confirmation_tone, generate_error_tone, TTSConfig, TTSEngine};
use crate::voice_pipeline::{parse_command, CommandIntent};
use crate::wake_word::{create_detector, WakeWordDetector};

#[cfg(feature = "rpi")]
use crate::led_ring;

/// Voice controller state
#[derive(Debug, Clone, PartialEq)]
pub enum VoiceState {
    /// Idle, listening for wake word
    Idle,
    /// Wake word detected, waiting for command
    Listening,
    /// Processing speech
    Processing,
    /// Executing command via API
    Executing,
    /// Speaking response
    Speaking,
    /// Error state
    Error(String),
}

/// Voice controller configuration
#[derive(Debug, Clone)]
pub struct VoiceControllerConfig {
    /// Wake word phrase
    pub wake_phrase: String,
    /// Wake word sensitivity (0.0 - 1.0)
    pub wake_sensitivity: f32,
    /// Maximum recording duration in seconds
    pub max_record_secs: f32,
    /// Silence threshold for end-of-speech detection
    pub silence_threshold: i16,
    /// Duration of silence to end recording (seconds)
    pub silence_duration: f32,
    /// Sample rate
    pub sample_rate: u32,
}

impl Default for VoiceControllerConfig {
    fn default() -> Self {
        Self {
            wake_phrase: "hey kagami".to_string(),
            wake_sensitivity: 0.5,
            max_record_secs: 10.0,
            silence_threshold: 500,
            silence_duration: 1.5,
            sample_rate: 16000,
        }
    }
}

/// Main voice controller
pub struct VoiceController {
    config: VoiceControllerConfig,
    state: Arc<Mutex<VoiceState>>,
    api: KagamiAPI,
    audio_capture: Option<AudioCapture>,
    audio_playback: Option<AudioPlayback>,
    stt_engine: Option<STTEngine>,
    tts_engine: Option<TTSEngine>,
    wake_detector: Option<Box<dyn WakeWordDetector>>,
    /// Speaker identification for personalized responses
    speaker_identifier: Arc<Mutex<SpeakerIdentifier>>,
    /// Last identified speaker for personalization
    current_speaker: Arc<Mutex<Option<SpeakerMatch>>>,
}

impl VoiceController {
    /// Create a new voice controller
    pub fn new(hub_config: &HubConfig) -> Result<Self> {
        let config = VoiceControllerConfig {
            wake_phrase: hub_config.wake_word.phrase.clone(),
            wake_sensitivity: hub_config.wake_word.sensitivity,
            ..Default::default()
        };

        let api = KagamiAPI::new(&hub_config.general.api_url)?;

        // Initialize audio (may fail on systems without audio)
        let audio_config = AudioConfig {
            sample_rate: config.sample_rate,
            channels: 1,
            buffer_size: 512,
        };

        let audio_capture = AudioCapture::new(audio_config.clone()).ok();
        let audio_playback = Some(AudioPlayback::new(audio_config));

        // Initialize STT (Whisper)
        // Map from config.STTConfig to stt::STTConfig
        let stt_config = STTConfig {
            model_path: format!("models/{}.bin", hub_config.stt.model),
            language: hub_config.stt.language.clone(),
            ..Default::default()
        };
        let stt_engine = STTEngine::new(stt_config).ok();

        // Initialize TTS (Piper)
        // Map from config.TTSConfig to tts::TTSConfig
        // Note: hub_config.tts.use_api means prefer API over local TTS
        let tts_engine = if hub_config.tts.use_api {
            // When using API TTS, we don't need a local TTS engine
            None
        } else {
            let tts_config = TTSConfig {
                model_path: "models/en_US-amy-medium.onnx".to_string(), // Default Piper model
                ..Default::default()
            };
            TTSEngine::new(tts_config).ok()
        };

        // Initialize wake word detector
        let wake_detector = create_detector(
            &hub_config.wake_word.engine,
            &config.wake_phrase,
            config.wake_sensitivity,
        )
        .ok();

        // Initialize speaker identification
        let speaker_identifier = SpeakerIdentifier::new();

        info!("Voice controller initialized:");
        info!(
            "  Audio capture: {}",
            if audio_capture.is_some() {
                "✓"
            } else {
                "✗"
            }
        );
        info!(
            "  STT (Whisper): {}",
            if stt_engine.is_some() { "✓" } else { "✗" }
        );
        info!(
            "  TTS (Piper): {}",
            if tts_engine.is_some() { "✓" } else { "✗" }
        );
        info!(
            "  Wake word: {}",
            if wake_detector.is_some() {
                "✓"
            } else {
                "✗"
            }
        );
        info!("  Speaker ID: ✓");

        Ok(Self {
            config,
            state: Arc::new(Mutex::new(VoiceState::Idle)),
            api,
            audio_capture,
            audio_playback,
            stt_engine,
            tts_engine,
            wake_detector,
            speaker_identifier: Arc::new(Mutex::new(speaker_identifier)),
            current_speaker: Arc::new(Mutex::new(None)),
        })
    }

    /// Get current state
    pub async fn state(&self) -> VoiceState {
        self.state.lock().await.clone()
    }

    /// Set state and update LED ring
    async fn set_state(&self, state: VoiceState) {
        *self.state.lock().await = state.clone();

        #[cfg(feature = "rpi")]
        match state {
            VoiceState::Idle => led_ring::show_idle(),
            VoiceState::Listening => led_ring::show_listening(),
            VoiceState::Processing => led_ring::show_processing(),
            VoiceState::Executing => led_ring::show_processing(),
            VoiceState::Speaking => led_ring::show_speaking(),
            VoiceState::Error(_) => led_ring::show_error(),
        }

        debug!("Voice state: {:?}", state);
    }

    /// Process wake word detection on audio samples
    pub fn check_wake_word(&mut self, samples: &[i16]) -> bool {
        if let Some(detector) = &mut self.wake_detector {
            detector.process(samples).detected
        } else {
            false
        }
    }

    /// Record audio until silence detected or timeout
    pub async fn record_command(&mut self) -> Result<Vec<i16>> {
        self.set_state(VoiceState::Listening).await;

        let capture = self
            .audio_capture
            .as_mut()
            .ok_or_else(|| anyhow::anyhow!("Audio capture not available"))?;

        capture.start()?;

        let max_samples = (self.config.max_record_secs * self.config.sample_rate as f32) as usize;
        let silence_samples =
            (self.config.silence_duration * self.config.sample_rate as f32) as usize;

        let mut consecutive_silence = 0usize;
        let check_interval = std::time::Duration::from_millis(100);

        info!("🎤 Listening for command...");

        loop {
            tokio::time::sleep(check_interval).await;

            let buffer_len = capture.buffer_length();

            // Check for timeout
            if buffer_len >= max_samples {
                warn!("Recording timeout reached");
                break;
            }

            // Check for silence (end of speech)
            let samples = capture.take_samples();
            if detect_silence(
                &samples[samples.len().saturating_sub(1600)..],
                self.config.silence_threshold,
            ) {
                consecutive_silence += samples.len();
                if consecutive_silence >= silence_samples && buffer_len > silence_samples * 2 {
                    debug!("Silence detected, ending recording");
                    break;
                }
            } else {
                consecutive_silence = 0;
            }
        }

        capture.stop();
        let samples = capture.take_samples();

        info!(
            "📼 Recorded {} samples ({:.2}s)",
            samples.len(),
            samples.len() as f32 / self.config.sample_rate as f32
        );

        Ok(samples)
    }

    /// Transcribe audio to text
    pub async fn transcribe(&self, samples: &[i16]) -> Result<String> {
        self.set_state(VoiceState::Processing).await;

        let stt = self
            .stt_engine
            .as_ref()
            .ok_or_else(|| anyhow::anyhow!("STT engine not available"))?;

        stt.transcribe(samples)
    }

    /// Execute a command via API
    pub async fn execute_command(&self, intent: &CommandIntent) -> Result<String> {
        self.set_state(VoiceState::Executing).await;

        // Serialize intent to string for API call
        let intent_str = format!("{:?}", intent); // Simple debug format for now

        // Use the process_command method which handles all intent types
        match self.api.process_command(&intent_str).await {
            Ok(result) if result.success => {
                // Return the message if provided, otherwise generate confirmation
                Ok(result
                    .message
                    .unwrap_or_else(|| FeedbackGenerator::confirmation_for(intent)))
            }
            Ok(result) => {
                // Return error message or generate one
                let error_msg = result.error.unwrap_or_else(|| "Command failed".to_string());
                Ok(FeedbackGenerator::error_for(intent, &error_msg))
            }
            Err(e) => Ok(FeedbackGenerator::error_for(intent, &e.to_string())),
        }
    }

    /// Speak a response
    pub async fn speak(&self, text: &str) -> Result<()> {
        self.set_state(VoiceState::Speaking).await;

        info!("🔊 Speaking: \"{}\"", text);

        let samples = if let Some(tts) = &self.tts_engine {
            tts.synthesize(text)?
        } else {
            // Fallback to confirmation tone
            generate_confirmation_tone(22050, 200)
        };

        if let Some(playback) = &self.audio_playback {
            playback.play(&samples)?;
        }

        self.set_state(VoiceState::Idle).await;
        Ok(())
    }

    /// Speak an error
    pub async fn speak_error(&self, message: &str) -> Result<()> {
        self.set_state(VoiceState::Error(message.to_string())).await;

        error!("❌ Voice error: {}", message);

        // Play error tone
        if let Some(playback) = &self.audio_playback {
            let tone = generate_error_tone(22050, 300);
            playback.play(&tone)?;
        }

        // Reset to idle after brief delay
        tokio::time::sleep(std::time::Duration::from_secs(2)).await;
        self.set_state(VoiceState::Idle).await;

        Ok(())
    }

    // =========================================================================
    // SPEAKER IDENTIFICATION
    // =========================================================================

    /// Load voice profiles from the Kagami API
    pub async fn load_voice_profiles(&self) -> Result<()> {
        let api_url = self.api.base_url();
        let mut identifier = self.speaker_identifier.lock().await;
        identifier.load_profiles(api_url).await?;
        info!(
            "🎤 Loaded {} voice profiles",
            identifier.get_all_speakers().len()
        );
        Ok(())
    }

    /// Identify the speaker from audio samples
    ///
    /// This extracts a voice embedding and matches against registered profiles.
    /// Returns the identified speaker or None.
    pub async fn identify_speaker(&self, samples: &[i16]) -> SpeakerMatch {
        // Extract voice embedding from audio
        // In production, this would use a speaker recognition model
        // For now, we use a simple placeholder that returns a dummy embedding
        let embedding = self.extract_voice_embedding(samples);

        let identifier = self.speaker_identifier.lock().await;
        let speaker_match = identifier.identify(&embedding);

        // Store current speaker for personalization
        *self.current_speaker.lock().await = Some(speaker_match.clone());

        if speaker_match.is_identified {
            info!(
                "🎤 Speaker identified: {} (confidence: {:.0}%)",
                speaker_match
                    .speaker
                    .as_ref()
                    .map(|s| s.name.as_str())
                    .unwrap_or("unknown"),
                speaker_match.confidence * 100.0
            );
        } else {
            debug!("🎤 Speaker not identified");
        }

        speaker_match
    }

    /// Extract voice embedding from audio samples
    ///
    /// TODO: In production, use a speaker recognition model like:
    /// - SpeechBrain (speaker-recognition model)
    /// - Resemblyzer (d-vector embeddings)
    /// - Pyannote (speaker diarization)
    fn extract_voice_embedding(&self, samples: &[i16]) -> Vec<f32> {
        // Placeholder: compute simple audio features
        // Real implementation would use a neural network
        let len = samples.len() as f32;
        let mean = samples.iter().map(|&s| s as f32).sum::<f32>() / len;
        let variance = samples
            .iter()
            .map(|&s| {
                let diff = s as f32 - mean;
                diff * diff
            })
            .sum::<f32>()
            / len;

        // Return a simple feature vector
        // In production, this would be a 192-512 dimensional embedding
        vec![
            mean / 32768.0,
            variance.sqrt() / 32768.0,
            samples.len() as f32 / 16000.0, // Duration in seconds
            0.0,                            // Placeholder dimensions
        ]
    }

    /// Get personalized greeting based on current speaker and time
    pub async fn get_personalized_greeting(&self) -> String {
        let speaker = self.current_speaker.lock().await;
        let hour = chrono::Local::now().hour();

        match speaker.as_ref() {
            Some(s) => generate_personalized_greeting(s, hour),
            None => {
                // Default greeting when no speaker identified
                if hour < 12 {
                    "Good morning".to_string()
                } else if hour < 17 {
                    "Good afternoon".to_string()
                } else {
                    "Good evening".to_string()
                }
            }
        }
    }

    /// Get current speaker name if identified
    pub async fn get_current_speaker_name(&self) -> Option<String> {
        let speaker = self.current_speaker.lock().await;
        speaker
            .as_ref()
            .and_then(|s| s.speaker.as_ref().map(|p| p.name.clone()))
    }

    // =========================================================================
    // VOICE INTERACTION LOOP
    // =========================================================================

    /// Run the full voice interaction loop
    ///
    /// This processes a single voice command from start to finish:
    /// Wake Word → Record → Identify Speaker → Transcribe → Parse → Execute → Speak
    pub async fn process_voice_interaction(&mut self) -> Result<()> {
        // 1. Record command audio
        let samples = self.record_command().await?;

        if samples.len() < 8000 {
            // Less than 0.5 seconds, probably noise
            warn!("Recording too short, ignoring");
            self.set_state(VoiceState::Idle).await;
            return Ok(());
        }

        // 2. Identify speaker (parallel with transcription)
        let speaker_match = self.identify_speaker(&samples).await;

        // 3. Transcribe to text
        let transcript = match self.transcribe(&samples).await {
            Ok(t) if !t.is_empty() => t,
            Ok(_) => {
                self.speak_error("I didn't catch that").await?;
                return Ok(());
            }
            Err(e) => {
                self.speak_error(&format!("Transcription failed: {}", e))
                    .await?;
                return Ok(());
            }
        };

        info!("📝 Heard: \"{}\"", transcript);
        if let Some(name) = speaker_match.speaker.as_ref().map(|s| &s.name) {
            info!("👤 Speaker: {}", name);
        }

        // 4. Parse command intent
        let command = parse_command(&transcript);
        info!("🎯 Intent: {:?}", command.intent);

        // 5. Execute via API
        let response = match self.execute_command(&command.intent).await {
            Ok(r) => r,
            Err(e) => {
                self.speak_error(&format!("Command failed: {}", e)).await?;
                return Ok(());
            }
        };

        // 6. Personalize response if speaker identified
        let personalized_response = if speaker_match.is_identified {
            let greeting = self.get_personalized_greeting().await;
            if response.starts_with("Done") || response.starts_with("OK") {
                format!("{}, {}", greeting, response.to_lowercase())
            } else {
                response
            }
        } else {
            response
        };

        // 7. Speak response
        self.speak(&personalized_response).await?;

        Ok(())
    }
}

/*
 * 鏡
 * The voice of the home, orchestrated.
 *
 * Wake → Listen → Identify → Process → Act → Respond (personalized)
 * h(x) ≥ 0. Always.
 */

/*
 * 鏡
 * The voice of the home, orchestrated.
 *
 * Wake → Listen → Process → Act → Respond
 * h(x) ≥ 0. Always.
 */
