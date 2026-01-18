//! Feedback System — Spoken Confirmations + Audio Cues
//!
//! Addresses audit finding: Hub Informed score (55) needs spoken confirmations.
//! James (elderly caregiver) persona requires verbal feedback for safety.
//!
//! Colony: Crystal (e7) — Verification through auditory feedback

use anyhow::Result;
use tracing::{debug, info, warn};

use crate::api_client::KagamiAPI;
use crate::voice_pipeline::{
    BedAction, CommandIntent, MusicAction, OutdoorAction, SecurityAction, TeslaAction,
};

/// Confirmation messages for each command type
/// Designed for clarity and brevity (ubicomp "glanceable" principles applied to audio)
pub struct FeedbackGenerator;

impl FeedbackGenerator {
    /// Generate spoken confirmation for a command
    pub fn confirmation_for(intent: &CommandIntent) -> String {
        match intent {
            CommandIntent::Scene(scene) => match scene.as_str() {
                "movie_mode" => "Movie mode activated.".to_string(),
                "goodnight" => "Goodnight. All secure.".to_string(),
                "welcome_home" => "Welcome home.".to_string(),
                "romance" => "Romance mode activated.".to_string(),
                "party" => "Party mode activated.".to_string(),
                _ => format!("{} scene activated.", scene.replace('_', " ")),
            },
            CommandIntent::Lights(level) => match *level {
                0 => "Lights off.".to_string(),
                100 => "Lights on.".to_string(),
                l => format!("Lights set to {}%.", l),
            },
            CommandIntent::Fireplace(on) => {
                if *on {
                    "Fireplace on.".to_string()
                } else {
                    "Fireplace off.".to_string()
                }
            }
            CommandIntent::Shades(action) => {
                if action == "open" {
                    "Shades opening.".to_string()
                } else {
                    "Shades closing.".to_string()
                }
            }
            CommandIntent::TV(action) => {
                if action == "raise" {
                    "TV rising.".to_string()
                } else {
                    "TV lowering.".to_string()
                }
            }
            CommandIntent::Lock(locked) => {
                if *locked {
                    "Doors locked.".to_string()
                } else {
                    "Doors unlocked.".to_string()
                }
            }
            CommandIntent::Temperature(temp) => {
                format!("Temperature set to {} degrees.", temp)
            }
            CommandIntent::Music(action) => match action {
                MusicAction::Play(Some(playlist)) => format!("Playing {} playlist.", playlist),
                MusicAction::Play(None) => "Playing music.".to_string(),
                MusicAction::Pause => "Music paused.".to_string(),
                MusicAction::Resume => "Music resumed.".to_string(),
                MusicAction::Skip => "Skipping to next track.".to_string(),
                MusicAction::VolumeUp => "Volume up.".to_string(),
                MusicAction::VolumeDown => "Volume down.".to_string(),
                MusicAction::SetVolume(level) => format!("Volume set to {}%.", level),
            },
            CommandIntent::Announce(msg) => {
                format!("Announcing: {}", msg)
            }
            CommandIntent::Status => "Here is your status.".to_string(),
            CommandIntent::Help => "Here's what I can do.".to_string(),
            CommandIntent::Cancel => "Cancelled.".to_string(),

            // Tesla commands
            CommandIntent::Tesla(action) => match action {
                TeslaAction::Climate(Some(temp)) => {
                    format!("Tesla climate set to {} degrees.", temp)
                }
                TeslaAction::Climate(None) => "Tesla climate activated.".to_string(),
                TeslaAction::Lock => "Tesla locked.".to_string(),
                TeslaAction::Unlock => "Tesla unlocked.".to_string(),
                TeslaAction::ChargeStatus => "Here's your Tesla charge status.".to_string(),
                TeslaAction::StartCharge => "Tesla charging started.".to_string(),
                TeslaAction::StopCharge => "Tesla charging stopped.".to_string(),
                TeslaAction::SentryOn => "Tesla sentry mode enabled.".to_string(),
                TeslaAction::SentryOff => "Tesla sentry mode disabled.".to_string(),
                TeslaAction::OpenFrunk => "Tesla frunk opening.".to_string(),
                TeslaAction::Location => "Here's your Tesla location.".to_string(),
            },

            // Bed/Eight Sleep commands (uses levels -100 to +100, not temperature degrees)
            CommandIntent::Bed(action) => match action {
                BedAction::SetTemp(level) => {
                    if *level < 0 {
                        format!("Bed cooling set to level {}.", level.abs())
                    } else if *level > 0 {
                        format!("Bed warming set to level {}.", level)
                    } else {
                        "Bed set to neutral.".to_string()
                    }
                }
                BedAction::SetSideTemp { side, level } => {
                    let side_name = if side == "left" { "Left" } else { "Right" };
                    if *level < 0 {
                        format!("{} side cooling set to level {}.", side_name, level.abs())
                    } else if *level > 0 {
                        format!("{} side warming set to level {}.", side_name, level)
                    } else {
                        format!("{} side set to neutral.", side_name)
                    }
                }
                BedAction::Off => "Bed turned off.".to_string(),
                BedAction::SleepStatus => "Here's your sleep data.".to_string(),
            },

            // Outdoor lights (Oelo)
            CommandIntent::Outdoor(action) => match action {
                OutdoorAction::On => "Outdoor lights on.".to_string(),
                OutdoorAction::Off => "Outdoor lights off.".to_string(),
                OutdoorAction::Color(color) => format!("Outdoor lights set to {}.", color),
                OutdoorAction::Pattern(pattern) => format!("Outdoor pattern set to {}.", pattern),
                OutdoorAction::Christmas => "Christmas lights activated.".to_string(),
                OutdoorAction::Party => "Party lights activated.".to_string(),
                OutdoorAction::Welcome => "Welcome lights activated.".to_string(),
            },

            // Security/Alarm
            CommandIntent::Security(action) => match action {
                SecurityAction::Arm => "Alarm armed.".to_string(),
                SecurityAction::ArmStay => "Alarm armed in stay mode.".to_string(),
                SecurityAction::Disarm => "Alarm disarmed.".to_string(),
                SecurityAction::Status => "Here's your security status.".to_string(),
            },

            // Presence, weather, find
            CommandIntent::Presence => "Here's who's home.".to_string(),
            CommandIntent::Weather => "Here's the weather.".to_string(),
            CommandIntent::FindDevice(device) => format!("Finding your {}.", device),

            // Automation modes
            CommandIntent::VacationMode(enabled) => {
                if *enabled {
                    "Vacation mode enabled.".to_string()
                } else {
                    "Vacation mode disabled.".to_string()
                }
            }
            CommandIntent::GuestMode(enabled) => {
                if *enabled {
                    "Guest mode enabled.".to_string()
                } else {
                    "Guest mode disabled.".to_string()
                }
            }

            // Climate zones
            CommandIntent::ClimateZone { room, temp } => {
                format!("{} set to {} degrees.", room, temp)
            }
            CommandIntent::HvacMode { room, mode } => {
                if let Some(r) = room {
                    format!("{} HVAC set to {}.", r, mode)
                } else {
                    format!("HVAC set to {}.", mode)
                }
            }

            CommandIntent::Unknown => "I didn't understand that command.".to_string(),
        }
    }

    /// Generate error message for failed commands
    pub fn error_for(intent: &CommandIntent, error: &str) -> String {
        // Simplify error messages for speech - remove technical details
        let simple_error = if error.contains("timeout") {
            "Connection timed out."
        } else if error.contains("401") || error.contains("403") || error.contains("auth") {
            "Not authorized."
        } else if error.contains("404") {
            "Not found."
        } else if error.contains("500") {
            "Server error."
        } else if error.len() > 50 {
            "An error occurred."
        } else {
            error
        };

        match intent {
            CommandIntent::Scene(scene) => {
                format!(
                    "Could not activate {} scene. {}",
                    scene.replace('_', " "),
                    simple_error
                )
            }
            CommandIntent::Lights(_) => format!("Could not change lights. {}", simple_error),
            CommandIntent::Fireplace(_) => {
                format!("Could not control fireplace. {}", simple_error)
            }
            CommandIntent::Shades(_) => format!("Could not control shades. {}", simple_error),
            CommandIntent::TV(_) => format!("Could not control TV. {}", simple_error),
            CommandIntent::Lock(_) => format!("Could not control locks. {}", simple_error),
            CommandIntent::Temperature(_) => {
                format!("Could not set temperature. {}", simple_error)
            }
            CommandIntent::Music(_) => format!("Could not control music. {}", simple_error),
            CommandIntent::Announce(_) => {
                format!("Could not make announcement. {}", simple_error)
            }
            CommandIntent::Status => format!("Could not get status. {}", simple_error),
            CommandIntent::Help => "Sorry, I encountered an error.".to_string(),
            CommandIntent::Cancel => "Cancelled.".to_string(),

            // Tesla errors
            CommandIntent::Tesla(_) => format!("Could not control Tesla. {}", simple_error),

            // Bed/Eight Sleep errors
            CommandIntent::Bed(_) => format!("Could not control bed. {}", simple_error),

            // Outdoor lights errors
            CommandIntent::Outdoor(_) => {
                format!("Could not control outdoor lights. {}", simple_error)
            }

            // Security errors
            CommandIntent::Security(_) => format!("Could not control alarm. {}", simple_error),

            // Presence, weather, find errors
            CommandIntent::Presence => format!("Could not check presence. {}", simple_error),
            CommandIntent::Weather => format!("Could not get weather. {}", simple_error),
            CommandIntent::FindDevice(_) => format!("Could not find device. {}", simple_error),

            // Automation mode errors
            CommandIntent::VacationMode(_) => {
                format!("Could not set vacation mode. {}", simple_error)
            }
            CommandIntent::GuestMode(_) => format!("Could not set guest mode. {}", simple_error),

            // Climate zone errors
            CommandIntent::ClimateZone { .. } => {
                format!("Could not set room temperature. {}", simple_error)
            }
            CommandIntent::HvacMode { .. } => format!("Could not set HVAC mode. {}", simple_error),

            CommandIntent::Unknown => "I didn't understand that command.".to_string(),
        }
    }

    /// Generate status announcement for state queries
    pub fn status_announcement(h_x: f64, connected: bool) -> String {
        let safety = if h_x >= 0.5 {
            "All systems safe"
        } else if h_x >= 0.0 {
            "Caution advisory active"
        } else {
            "Safety alert"
        };

        let connection = if connected { "connected" } else { "offline" };

        format!("Kagami is {}. {}.", connection, safety)
    }

    /// Generate goodnight safety summary
    pub fn goodnight_summary(doors_locked: bool, lights_off: bool, fireplace_off: bool) -> String {
        let mut issues = Vec::new();

        if !doors_locked {
            issues.push("doors unlocked");
        }
        if !lights_off {
            issues.push("some lights on");
        }
        if !fireplace_off {
            issues.push("fireplace on");
        }

        if issues.is_empty() {
            "Goodnight. All secure. Doors locked, lights off, fireplace off.".to_string()
        } else {
            format!("Goodnight. Note: {}.", issues.join(", "))
        }
    }

    /// Generate help message listing available commands
    pub fn help_message() -> String {
        "I can control lights, shades, fireplace, TV, locks, temperature, music, and outdoor lights. \
         I can check the weather, see who's home, and find your devices. \
         I can also control your Tesla and bed, arm the alarm, and activate scenes like movie mode or goodnight. \
         Just tell me what you'd like."
            .to_string()
    }

    /// Generate welcome message on startup
    pub fn startup_message() -> String {
        "Kagami is ready.".to_string()
    }

    /// Generate shutdown message
    pub fn shutdown_message() -> String {
        "Kagami going offline.".to_string()
    }
}

/// TTS announcement via Kagami API
pub struct TTSFeedback {
    api: KagamiAPI,
    enabled: bool,
    volume: f32,
}

impl TTSFeedback {
    pub fn new(api_url: &str, enabled: bool, volume: f32) -> Result<Self> {
        Ok(Self {
            api: KagamiAPI::new(api_url)?,
            enabled,
            volume,
        })
    }

    /// Check if TTS is enabled
    pub fn is_enabled(&self) -> bool {
        self.enabled
    }

    /// Set TTS enabled state
    pub fn set_enabled(&mut self, enabled: bool) {
        self.enabled = enabled;
    }

    /// Get current volume
    pub fn volume(&self) -> f32 {
        self.volume
    }

    /// Set volume (0.0 - 1.0)
    pub fn set_volume(&mut self, volume: f32) {
        self.volume = volume.clamp(0.0, 1.0);
    }

    /// Speak confirmation after command execution
    pub async fn speak(&self, text: &str) -> Result<()> {
        if !self.enabled {
            debug!("TTS disabled, skipping: {}", text);
            return Ok(());
        }

        info!("TTS: {}", text);

        // Use the Hub's local speaker (not whole-house announcement)
        // In full implementation, this would use local audio output
        // For now, we use the announce endpoint with specific room targeting
        self.api
            .announce(text, Some(vec!["Hub".to_string()]), Some("kagami"))
            .await
    }

    /// Speak confirmation for a command result
    pub async fn confirm_command(
        &self,
        intent: &CommandIntent,
        success: bool,
        error: Option<&str>,
    ) {
        let message = if success {
            FeedbackGenerator::confirmation_for(intent)
        } else {
            FeedbackGenerator::error_for(intent, error.unwrap_or("Unknown error"))
        };

        if let Err(e) = self.speak(&message).await {
            warn!("Failed to speak confirmation: {}", e);
        }
    }
}

/// Audio cues (non-verbal feedback)
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AudioCue {
    /// Short rising tone - wake word detected
    WakeDetected,
    /// Double beep - command understood
    CommandAccepted,
    /// Pleasant chime - action succeeded
    Success,
    /// Descending tone - action failed
    Error,
    /// Soft pulse - thinking/processing
    Processing,
    /// Alert tone - safety warning
    SafetyAlert,
    /// Notification tone - new message/alert
    Notification,
    /// Low battery warning
    LowBattery,
}

impl AudioCue {
    /// Frequency pattern for the cue (Hz, duration_ms)
    /// 0 Hz = silence (rest)
    pub fn pattern(&self) -> Vec<(u32, u32)> {
        match self {
            // Rising two-tone: C5 -> E5 (wake acknowledgment)
            AudioCue::WakeDetected => vec![(523, 100), (659, 150)],

            // Double high beep: A5 x2 (understood)
            AudioCue::CommandAccepted => vec![(880, 50), (0, 30), (880, 50)],

            // Major chord arpeggio: C5 -> E5 -> G5 (success/positive)
            AudioCue::Success => vec![(523, 100), (659, 100), (784, 150)],

            // Descending minor: A4 -> F4 (error/negative)
            AudioCue::Error => vec![(440, 150), (349, 200)],

            // Single soft tone: A4 (processing/thinking)
            AudioCue::Processing => vec![(440, 50)],

            // Alert: High A5 with pause (attention-getting)
            AudioCue::SafetyAlert => vec![(880, 200), (0, 100), (880, 200)],

            // Notification: G5 -> C6 (gentle attention)
            AudioCue::Notification => vec![(784, 100), (1047, 150)],

            // Low battery: Descending B4 -> E4 -> B3 (urgent)
            AudioCue::LowBattery => vec![(494, 200), (330, 200), (247, 300)],
        }
    }

    /// Get total duration of the cue in milliseconds
    pub fn duration_ms(&self) -> u32 {
        self.pattern().iter().map(|(_, d)| d).sum()
    }

    /// Get the primary frequency (first non-zero)
    pub fn primary_frequency(&self) -> u32 {
        self.pattern()
            .iter()
            .find(|(f, _)| *f > 0)
            .map(|(f, _)| *f)
            .unwrap_or(440)
    }
}

/// Play audio cue through local speaker
pub async fn play_cue(cue: AudioCue) {
    debug!("Audio cue: {:?} ({}ms)", cue, cue.duration_ms());

    // Full implementation with cpal/rodio:
    //
    // use rodio::{OutputStream, Sink, source::SineWave};
    //
    // let (_stream, stream_handle) = OutputStream::try_default().unwrap();
    // let sink = Sink::try_new(&stream_handle).unwrap();
    //
    // for (freq, duration_ms) in cue.pattern() {
    //     if freq > 0 {
    //         let source = SineWave::new(freq as f32)
    //             .take_duration(Duration::from_millis(duration_ms as u64))
    //             .amplify(0.3);
    //         sink.append(source);
    //     } else {
    //         // Silence/rest
    //         std::thread::sleep(Duration::from_millis(duration_ms as u64));
    //     }
    // }
    //
    // sink.sleep_until_end();

    // Placeholder: simulate cue playback with sleep
    tokio::time::sleep(std::time::Duration::from_millis(cue.duration_ms() as u64)).await;
}

/// Generate sine wave samples for a frequency
#[allow(dead_code)]
fn generate_tone(frequency: u32, duration_ms: u32, sample_rate: u32, volume: f32) -> Vec<i16> {
    let num_samples = (sample_rate * duration_ms / 1000) as usize;
    let angular_freq = 2.0 * std::f32::consts::PI * frequency as f32 / sample_rate as f32;

    (0..num_samples)
        .map(|i| {
            let sample = (angular_freq * i as f32).sin() * volume * 32767.0;
            sample as i16
        })
        .collect()
}

/// Generate audio cue as PCM samples
#[allow(dead_code)]
pub fn generate_cue_samples(cue: AudioCue, sample_rate: u32, volume: f32) -> Vec<i16> {
    let mut samples = Vec::new();

    for (freq, duration_ms) in cue.pattern() {
        if freq > 0 {
            samples.extend(generate_tone(freq, duration_ms, sample_rate, volume));
        } else {
            // Silence
            let num_samples = (sample_rate * duration_ms / 1000) as usize;
            samples.extend(vec![0i16; num_samples]);
        }
    }

    // Apply fade in/out to avoid clicks
    let fade_samples = (sample_rate / 100) as usize; // 10ms fade
    if samples.len() > fade_samples * 2 {
        // Fade in
        for i in 0..fade_samples {
            let factor = i as f32 / fade_samples as f32;
            samples[i] = (samples[i] as f32 * factor) as i16;
        }
        // Fade out
        let len = samples.len();
        for i in 0..fade_samples {
            let factor = i as f32 / fade_samples as f32;
            samples[len - 1 - i] = (samples[len - 1 - i] as f32 * factor) as i16;
        }
    }

    samples
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_confirmation_messages() {
        assert_eq!(
            FeedbackGenerator::confirmation_for(&CommandIntent::Lights(0)),
            "Lights off."
        );
        assert_eq!(
            FeedbackGenerator::confirmation_for(&CommandIntent::Lights(100)),
            "Lights on."
        );
        assert_eq!(
            FeedbackGenerator::confirmation_for(&CommandIntent::Lights(50)),
            "Lights set to 50%."
        );
        assert_eq!(
            FeedbackGenerator::confirmation_for(&CommandIntent::Fireplace(true)),
            "Fireplace on."
        );
        assert_eq!(
            FeedbackGenerator::confirmation_for(&CommandIntent::Lock(true)),
            "Doors locked."
        );
    }

    #[test]
    fn test_error_messages() {
        let error = FeedbackGenerator::error_for(&CommandIntent::Lights(50), "timeout");
        assert!(error.contains("timed out"));

        let error = FeedbackGenerator::error_for(&CommandIntent::Lights(50), "401 Unauthorized");
        assert!(error.contains("Not authorized"));
    }

    #[test]
    fn test_audio_cue_patterns() {
        let wake = AudioCue::WakeDetected;
        assert_eq!(wake.pattern().len(), 2);
        assert!(wake.duration_ms() > 0);

        let success = AudioCue::Success;
        assert_eq!(success.pattern().len(), 3);
    }

    #[test]
    fn test_generate_tone() {
        let samples = generate_tone(440, 100, 16000, 0.5);
        assert_eq!(samples.len(), 1600); // 16000 * 100 / 1000
    }

    #[test]
    fn test_status_announcement() {
        let status = FeedbackGenerator::status_announcement(1.0, true);
        assert!(status.contains("connected"));
        assert!(status.contains("safe"));

        let status = FeedbackGenerator::status_announcement(-0.5, false);
        assert!(status.contains("offline"));
        assert!(status.contains("alert"));
    }
}

/*
 * Kagami Feedback System
 * Crystal (e7) — Verification through auditory feedback
 *
 * Every action echoes back.
 * James knows his home is secure.
 */
