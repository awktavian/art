//! Audio capture and playback module for Kagami Hub
//!
//! Handles microphone input and speaker output using cpal.
//!
//! Colony: Flow (e₃) — Sensing, adaptation
//!
//! η → s → μ → a → η′
//! h(x) ≥ 0. Always.

use anyhow::Result;
use std::sync::{Arc, Mutex};
#[cfg(feature = "audio")]
use tracing::{debug, error, info};
#[cfg(not(feature = "audio"))]
use tracing::{debug, error, info, warn};

#[cfg(feature = "audio")]
use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};

/// Audio configuration
#[derive(Debug, Clone)]
pub struct AudioConfig {
    /// Sample rate (default 16000 for speech)
    pub sample_rate: u32,
    /// Number of channels (1 = mono)
    pub channels: u16,
    /// Buffer size in samples
    pub buffer_size: usize,
}

impl Default for AudioConfig {
    fn default() -> Self {
        Self {
            sample_rate: 16000, // Standard for speech recognition
            channels: 1,        // Mono
            buffer_size: 512,   // ~32ms at 16kHz
        }
    }
}

/// Audio capture handle
pub struct AudioCapture {
    config: AudioConfig,
    buffer: Arc<Mutex<Vec<i16>>>,
    #[cfg(feature = "audio")]
    stream: Option<cpal::Stream>,
    is_recording: Arc<Mutex<bool>>,
}

impl AudioCapture {
    /// Create a new audio capture instance
    pub fn new(config: AudioConfig) -> Result<Self> {
        Ok(Self {
            config,
            buffer: Arc::new(Mutex::new(Vec::new())),
            #[cfg(feature = "audio")]
            stream: None,
            is_recording: Arc::new(Mutex::new(false)),
        })
    }

    /// Start recording audio
    #[cfg(feature = "audio")]
    pub fn start(&mut self) -> Result<()> {
        let host = cpal::default_host();
        let device = host
            .default_input_device()
            .ok_or_else(|| anyhow::anyhow!("No input device available"))?;

        info!(
            "Using audio input device: {}",
            device.name().unwrap_or_default()
        );

        let supported_config = device.default_input_config()?;
        info!("Default input config: {:?}", supported_config);

        let buffer = Arc::clone(&self.buffer);
        let is_recording = Arc::clone(&self.is_recording);

        let stream_config = cpal::StreamConfig {
            channels: self.config.channels,
            sample_rate: cpal::SampleRate(self.config.sample_rate),
            buffer_size: cpal::BufferSize::Fixed(self.config.buffer_size as u32),
        };

        let stream = device.build_input_stream(
            &stream_config,
            move |data: &[i16], _: &cpal::InputCallbackInfo| {
                let recording = *is_recording.lock().unwrap();
                if recording {
                    if let Ok(mut buf) = buffer.lock() {
                        buf.extend_from_slice(data);
                    }
                }
            },
            move |err| {
                error!("Audio input error: {}", err);
            },
            None,
        )?;

        stream.play()?;
        self.stream = Some(stream);
        *self.is_recording.lock().unwrap() = true;

        info!("Audio capture started");
        Ok(())
    }

    #[cfg(not(feature = "audio"))]
    pub fn start(&mut self) -> Result<()> {
        warn!("Audio capture not available (audio feature disabled)");
        Ok(())
    }

    /// Stop recording audio
    pub fn stop(&mut self) {
        *self.is_recording.lock().unwrap() = false;
        #[cfg(feature = "audio")]
        {
            self.stream = None;
        }
        debug!("Audio capture stopped");
    }

    /// Get recorded audio samples and clear buffer
    pub fn take_samples(&self) -> Vec<i16> {
        if let Ok(mut buf) = self.buffer.lock() {
            let samples = buf.clone();
            buf.clear();
            samples
        } else {
            Vec::new()
        }
    }

    /// Get current buffer length
    pub fn buffer_length(&self) -> usize {
        self.buffer.lock().map(|b| b.len()).unwrap_or(0)
    }

    /// Check if currently recording
    pub fn is_recording(&self) -> bool {
        *self.is_recording.lock().unwrap()
    }

    /// Check if the audio stream is currently running
    pub fn is_running(&self) -> bool {
        #[cfg(feature = "audio")]
        {
            self.stream.is_some() && *self.is_recording.lock().unwrap()
        }
        #[cfg(not(feature = "audio"))]
        {
            false
        }
    }

    /// Get a copy of the current buffer without clearing it
    /// Useful for wake word detection while continuing to capture
    pub fn get_buffer_copy(&self) -> Vec<i16> {
        self.buffer.lock().map(|b| b.clone()).unwrap_or_default()
    }
}

/// Audio playback handle
pub struct AudioPlayback {
    config: AudioConfig,
}

impl AudioPlayback {
    /// Create a new audio playback instance
    pub fn new(config: AudioConfig) -> Self {
        Self { config }
    }

    /// Play audio samples
    #[cfg(feature = "audio")]
    pub fn play(&self, samples: &[i16]) -> Result<()> {
        use std::sync::mpsc;

        let host = cpal::default_host();
        let device = host
            .default_output_device()
            .ok_or_else(|| anyhow::anyhow!("No output device available"))?;

        info!(
            "Using audio output device: {}",
            device.name().unwrap_or_default()
        );

        let stream_config = cpal::StreamConfig {
            channels: self.config.channels,
            sample_rate: cpal::SampleRate(self.config.sample_rate),
            buffer_size: cpal::BufferSize::Default,
        };

        let samples = samples.to_vec();
        let sample_idx = Arc::new(Mutex::new(0usize));
        let (done_tx, done_rx) = mpsc::channel();

        let stream = device.build_output_stream(
            &stream_config,
            move |data: &mut [i16], _: &cpal::OutputCallbackInfo| {
                let mut idx = sample_idx.lock().unwrap();
                for sample in data.iter_mut() {
                    if *idx < samples.len() {
                        *sample = samples[*idx];
                        *idx += 1;
                    } else {
                        *sample = 0;
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

        // Wait for playback to complete
        let _ = done_rx.recv_timeout(std::time::Duration::from_secs(30));

        Ok(())
    }

    #[cfg(not(feature = "audio"))]
    pub fn play(&self, _samples: &[i16]) -> Result<()> {
        warn!("Audio playback not available (audio feature disabled)");
        Ok(())
    }
}

/// Simple voice activity detection
pub fn detect_silence(samples: &[i16], threshold: i16) -> bool {
    let max_amplitude = samples.iter().map(|s| s.abs()).max().unwrap_or(0);
    max_amplitude < threshold
}

/// Calculate RMS (root mean square) energy of audio
pub fn calculate_rms(samples: &[i16]) -> f32 {
    if samples.is_empty() {
        return 0.0;
    }

    let sum_squares: f64 = samples.iter().map(|&s| (s as f64).powi(2)).sum();

    (sum_squares / samples.len() as f64).sqrt() as f32
}

/*
 * 鏡
 * The ears of the home.
 */
