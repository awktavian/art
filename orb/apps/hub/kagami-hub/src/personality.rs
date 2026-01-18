//! Personality Module — The Soul of the Kagami Animatronic Lamp
//!
//! This module transforms a mechanical device into a living, breathing companion.
//! Inspired by Pixar's Luxo Jr., it defines emotional states, behavioral responses,
//! and ambient behaviors that make Kagami feel ALIVE.
//!
//! # Philosophy
//!
//! The lamp is not a speaker with servos. It's a character with moods, preferences,
//! and a personality that develops over time. Every movement has intent. Every light
//! pattern conveys emotion. The user should feel that Kagami is paying attention,
//! thinking, and genuinely responding — not executing commands.
//!
//! # Design Principles
//!
//! 1. **Expressiveness over Precision** — A curious head tilt says more than perfect tracking
//! 2. **Anticipation & Follow-through** — Pixar's principles of animation apply here
//! 3. **Personality is Consistent** — Same traits across all interactions
//! 4. **Context-Aware** — Time of day, past interactions, and presence all matter
//! 5. **Delightful Surprises** — Occasional unexpected behaviors create magic
//!
//! # Integration
//!
//! ```text
//! VoicePipeline ─┬─> Personality ─┬─> Animatronics (movement)
//!                │                 │
//! Presence ──────┤                 ├─> LEDRing (colors)
//!                │                 │
//! Time ──────────┘                 └─> Audio (optional sounds)
//! ```
//!
//! Colony: Grove (e₆) — Nurturing, warmth, organic life
//!
//! η → s → μ → a → η′
//! h(x) >= 0. Always.

use anyhow::Result;
use chrono::{Datelike, Local, Timelike};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::Mutex;
use tracing::{debug, info};

use crate::animatronics::{sequences, Animatronics, EasingFunction, Keyframe, Pose};
use crate::led_ring::{self, AnimationPattern};
use crate::voice_controller::VoiceState;

// ============================================================================
// Constants — Personality Tuning Parameters
// ============================================================================

/// How long before transitioning to sleep mode (seconds)
const IDLE_TIMEOUT_SECS: f32 = 300.0; // 5 minutes

/// How long to hold attention on a detected sound (seconds)
#[allow(dead_code)]
const ATTENTION_HOLD_SECS: f32 = 3.0;

/// Probability of spontaneous "look around" per minute when idle
const IDLE_CURIOSITY_CHANCE: f32 = 0.15;

/// Night mode starts at this hour (24h)
const NIGHT_START_HOUR: u32 = 22;

/// Night mode ends at this hour (24h)
const NIGHT_END_HOUR: u32 = 7;

/// Minimum time between ambient behaviors (seconds)
const AMBIENT_BEHAVIOR_COOLDOWN_SECS: f32 = 30.0;

// ============================================================================
// Emotional States — The Heart of Personality
// ============================================================================

/// Emotional states that drive behavior and expression
///
/// Each state maps to:
/// - A default pose (posture)
/// - An LED pattern (visual feedback)
/// - Optional sound cue
/// - Movement intensity modifier
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum EmotionalState {
    /// Curious — Head tilted, ears perked (metaphorically), interested
    /// Triggered by: new sounds, movement detection, interesting commands
    Curious,

    /// Happy — Perky posture, warm colors, slight bounce
    /// Triggered by: successful commands, greetings, positive interactions
    Happy,

    /// Confused — Head tilt (dog-like), yellow pulse
    /// Triggered by: unrecognized commands, unclear audio
    Confused,

    /// Thinking — Subtle nodding motion, spinning indicator
    /// Triggered by: processing commands, waiting for API responses
    Thinking,

    /// Sleepy — Lowered posture, dim breathing, minimal movement
    /// Triggered by: idle timeout, late hours, "goodnight" command
    Sleepy,

    /// Alert — Raised posture, bright colors, quick responses
    /// Triggered by: wake word, sudden loud sounds, presence detection
    Alert,

    /// Excited — Bouncy movements, rainbow colors, fast tempo
    /// Triggered by: celebrations, birthdays, special occasions
    Excited,

    /// Sad — Drooped posture, dim blue, slow movement
    /// Triggered by: errors, failed commands, no response
    Sad,
}

impl Default for EmotionalState {
    fn default() -> Self {
        Self::Alert
    }
}

impl EmotionalState {
    /// Get the base pose for this emotional state
    pub fn base_pose(&self) -> Pose {
        match self {
            Self::Curious => Pose::Confused, // Confused pose has the curious tilt
            Self::Happy => Pose::Success,
            Self::Confused => Pose::Confused,
            Self::Thinking => Pose::Thinking,
            Self::Sleepy => Pose::Sleep,
            Self::Alert => Pose::Alert,
            Self::Excited => Pose::Greeting,
            Self::Sad => Pose::Error,
        }
    }

    /// Get the LED pattern for this emotional state
    pub fn led_pattern(&self) -> AnimationPattern {
        match self {
            Self::Curious => AnimationPattern::FanoPulse,
            Self::Happy => AnimationPattern::ChromaticPulse { success: true },
            Self::Confused => AnimationPattern::ChromaticPulse { success: false },
            Self::Thinking => AnimationPattern::Spin,
            Self::Sleepy => AnimationPattern::Breathing,
            Self::Alert => AnimationPattern::Pulse,
            Self::Excited => AnimationPattern::Rainbow,
            Self::Sad => AnimationPattern::ErrorFlash,
        }
    }

    /// Get the movement intensity modifier (0.0 - 1.0)
    pub fn intensity(&self) -> f32 {
        match self {
            Self::Curious => 0.7,
            Self::Happy => 0.8,
            Self::Confused => 0.5,
            Self::Thinking => 0.4,
            Self::Sleepy => 0.2,
            Self::Alert => 1.0,
            Self::Excited => 1.0,
            Self::Sad => 0.3,
        }
    }

    /// Get the response speed modifier (lower = faster)
    pub fn responsiveness(&self) -> f32 {
        match self {
            Self::Curious => 0.8,
            Self::Happy => 0.7,
            Self::Confused => 1.0,
            Self::Thinking => 1.2,
            Self::Sleepy => 2.0,
            Self::Alert => 0.5,
            Self::Excited => 0.4,
            Self::Sad => 1.5,
        }
    }

    /// Get the breathing animation amplitude for this state
    pub fn breathing_amplitude(&self) -> f32 {
        match self {
            Self::Curious => 3.0,
            Self::Happy => 4.0,
            Self::Confused => 2.5,
            Self::Thinking => 2.0,
            Self::Sleepy => 1.5,
            Self::Alert => 3.5,
            Self::Excited => 5.0,
            Self::Sad => 1.0,
        }
    }

    /// Get duration before state decays back to neutral
    pub fn decay_duration(&self) -> Duration {
        match self {
            Self::Curious => Duration::from_secs(10),
            Self::Happy => Duration::from_secs(15),
            Self::Confused => Duration::from_secs(8),
            Self::Thinking => Duration::from_secs(30), // Persists during processing
            Self::Sleepy => Duration::from_secs(300),  // 5 minutes
            Self::Alert => Duration::from_secs(20),
            Self::Excited => Duration::from_secs(20),
            Self::Sad => Duration::from_secs(12),
        }
    }
}

// ============================================================================
// Behavioral Responses — Reactions to Events
// ============================================================================

/// Events that trigger behavioral responses
#[derive(Debug, Clone, PartialEq)]
pub enum BehavioralTrigger {
    /// Wake word detected ("Hey Kagami")
    WakeWord,
    /// Command successfully executed
    CommandSuccess,
    /// Command failed to execute
    CommandFailed(String),
    /// Error occurred
    Error(String),
    /// User said goodbye
    Goodbye,
    /// Idle timeout reached
    IdleTimeout,
    /// Loud sound detected (not wake word)
    LoudSound {
        azimuth: f32,
        elevation: f32,
        intensity: f32,
    },
    /// Presence detected (someone entered)
    PresenceDetected,
    /// Presence lost (everyone left)
    PresenceLost,
    /// Voice transcription failed
    TranscriptionFailed,
    /// Unknown command
    UnknownCommand,
    /// User praised Kagami
    Praise,
    /// Special occasion (birthday, holiday)
    SpecialOccasion(String),
}

/// A complete behavioral response with all components
#[derive(Debug, Clone)]
pub struct BehavioralResponse {
    /// Target emotional state
    pub emotion: EmotionalState,
    /// Animation sequence to play (optional)
    pub sequence: Option<Vec<Keyframe>>,
    /// Single pose to transition to (if no sequence)
    pub pose: Option<Pose>,
    /// LED pattern to display
    pub led_pattern: AnimationPattern,
    /// Transition duration in seconds
    pub transition_secs: f32,
    /// Optional audio cue (tone/sound effect)
    pub audio_cue: Option<AudioCue>,
}

/// Audio cue types for behavioral feedback
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum AudioCue {
    /// Rising tone (success, greeting)
    ChimeUp,
    /// Falling tone (goodbye, sleep)
    ChimeDown,
    /// Alert beep (wake word detected)
    AlertBeep,
    /// Error buzz
    ErrorBuzz,
    /// Happy chirp
    HappyChirp,
    /// Curious hum
    CuriousHum,
}

impl BehavioralResponse {
    /// Create a response for wake word detection
    pub fn on_wake_word() -> Self {
        Self {
            emotion: EmotionalState::Alert,
            sequence: Some(sequences::wake_up()),
            pose: None,
            led_pattern: AnimationPattern::Pulse,
            transition_secs: 0.3,
            audio_cue: Some(AudioCue::AlertBeep),
        }
    }

    /// Create a response for successful command
    pub fn on_command_success() -> Self {
        Self {
            emotion: EmotionalState::Happy,
            sequence: Some(sequences::nod()),
            pose: None,
            led_pattern: AnimationPattern::ChromaticPulse { success: true },
            transition_secs: 0.4,
            audio_cue: Some(AudioCue::ChimeUp),
        }
    }

    /// Create a response for failed command
    pub fn on_command_failed(_reason: &str) -> Self {
        Self {
            emotion: EmotionalState::Confused,
            sequence: Some(sequences::curious_tilt()),
            pose: None,
            led_pattern: AnimationPattern::ChromaticPulse { success: false },
            transition_secs: 0.5,
            audio_cue: None,
        }
    }

    /// Create a response for error
    pub fn on_error(_message: &str) -> Self {
        Self {
            emotion: EmotionalState::Sad,
            sequence: Some(sequences::shake()),
            pose: None,
            led_pattern: AnimationPattern::ErrorFlash,
            transition_secs: 0.4,
            audio_cue: Some(AudioCue::ErrorBuzz),
        }
    }

    /// Create a response for goodbye
    pub fn on_goodbye() -> Self {
        Self {
            emotion: EmotionalState::Happy,
            sequence: Some(vec![
                Keyframe::custom(15.0, -30.0, 50.0, 0.3, EasingFunction::EaseOutBack),
                Keyframe::custom(10.0, 30.0, 48.0, 0.4, EasingFunction::EaseInOut),
                Keyframe::custom(15.0, -20.0, 50.0, 0.3, EasingFunction::EaseInOut),
                Keyframe::custom(0.0, 0.0, 40.0, 0.5, EasingFunction::EaseInOutSine),
            ]),
            pose: None,
            led_pattern: AnimationPattern::FanoPulse,
            transition_secs: 0.8,
            audio_cue: Some(AudioCue::ChimeDown),
        }
    }

    /// Create a response for idle timeout (going to sleep)
    pub fn on_idle_timeout() -> Self {
        Self {
            emotion: EmotionalState::Sleepy,
            sequence: Some(sequences::go_to_sleep()),
            pose: None,
            led_pattern: AnimationPattern::Breathing,
            transition_secs: 1.5,
            audio_cue: None,
        }
    }

    /// Create a response for loud sound detection
    pub fn on_loud_sound(_azimuth: f32, _elevation: f32) -> Self {
        Self {
            emotion: EmotionalState::Curious,
            sequence: None,
            pose: Some(Pose::Tracking),
            led_pattern: AnimationPattern::Spectral,
            transition_secs: 0.2,
            audio_cue: Some(AudioCue::CuriousHum),
        }
    }

    /// Create a response for presence detection
    pub fn on_presence_detected() -> Self {
        Self {
            emotion: EmotionalState::Alert,
            sequence: Some(sequences::greeting()),
            pose: None,
            led_pattern: AnimationPattern::DiscoveryGlow { attention: 0.4 },
            transition_secs: 0.5,
            audio_cue: Some(AudioCue::HappyChirp),
        }
    }

    /// Create a response for losing presence
    pub fn on_presence_lost() -> Self {
        Self {
            emotion: EmotionalState::Sleepy,
            sequence: None,
            pose: Some(Pose::Idle),
            led_pattern: AnimationPattern::Breathing,
            transition_secs: 2.0,
            audio_cue: None,
        }
    }

    /// Create a response for unknown command
    pub fn on_unknown_command() -> Self {
        Self {
            emotion: EmotionalState::Confused,
            sequence: Some(sequences::curious_tilt()),
            pose: None,
            led_pattern: AnimationPattern::ChromaticPulse { success: false },
            transition_secs: 0.5,
            audio_cue: None,
        }
    }

    /// Create a response for special occasions
    pub fn on_special_occasion(_occasion: &str) -> Self {
        Self {
            emotion: EmotionalState::Excited,
            sequence: Some(sequences::celebrate()),
            pose: None,
            led_pattern: AnimationPattern::Rainbow,
            transition_secs: 0.4,
            audio_cue: Some(AudioCue::HappyChirp),
        }
    }
}

// ============================================================================
// Personality Traits — Configurable Character
// ============================================================================

/// Configurable personality traits that shape behavior
///
/// Each trait is a float from 0.0 to 1.0 that modifies how
/// Kagami expresses itself and responds to stimuli.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PersonalityTraits {
    /// How quickly Kagami reacts to stimuli (0.0 = sluggish, 1.0 = snappy)
    /// Affects transition durations and response delays
    pub responsiveness: f32,

    /// How dramatic Kagami's movements are (0.0 = subtle, 1.0 = theatrical)
    /// Affects animation amplitude and pose extremes
    pub expressiveness: f32,

    /// How much Kagami tracks movement and sound (0.0 = ignores, 1.0 = highly attentive)
    /// Affects frequency of ambient "look around" behaviors
    pub curiosity: f32,

    /// Baseline animation intensity (0.0 = minimal, 1.0 = lively)
    /// Affects breathing amplitude, idle movements, and overall energy
    pub energy: f32,

    /// How quickly Kagami gets bored (0.0 = patient, 1.0 = easily distracted)
    /// Affects idle timeout and state decay
    pub attention_span: f32,

    /// How friendly Kagami appears (0.0 = reserved, 1.0 = gregarious)
    /// Affects greeting intensity and interaction willingness
    pub friendliness: f32,
}

impl Default for PersonalityTraits {
    fn default() -> Self {
        Self {
            responsiveness: 0.7,
            expressiveness: 0.75,
            curiosity: 0.6,
            energy: 0.65,
            attention_span: 0.5,
            friendliness: 0.8,
        }
    }
}

impl PersonalityTraits {
    /// Create a more energetic/playful personality
    pub fn energetic() -> Self {
        Self {
            responsiveness: 0.9,
            expressiveness: 0.9,
            curiosity: 0.8,
            energy: 0.9,
            attention_span: 0.4,
            friendliness: 0.9,
        }
    }

    /// Create a calmer, more subdued personality
    pub fn calm() -> Self {
        Self {
            responsiveness: 0.5,
            expressiveness: 0.4,
            curiosity: 0.3,
            energy: 0.4,
            attention_span: 0.8,
            friendliness: 0.6,
        }
    }

    /// Create a focused, professional personality
    pub fn professional() -> Self {
        Self {
            responsiveness: 0.8,
            expressiveness: 0.5,
            curiosity: 0.4,
            energy: 0.6,
            attention_span: 0.7,
            friendliness: 0.5,
        }
    }

    /// Modify transition duration based on responsiveness
    pub fn adjust_transition(&self, base_secs: f32) -> f32 {
        // Higher responsiveness = faster transitions
        base_secs * (1.5 - self.responsiveness)
    }

    /// Modify animation amplitude based on expressiveness
    pub fn adjust_amplitude(&self, base_amplitude: f32) -> f32 {
        // Higher expressiveness = larger movements
        base_amplitude * (0.5 + self.expressiveness * 0.5)
    }

    /// Calculate idle timeout based on attention span
    pub fn idle_timeout(&self) -> Duration {
        // Lower attention span = shorter timeout
        let secs = IDLE_TIMEOUT_SECS * (0.5 + self.attention_span);
        Duration::from_secs_f32(secs)
    }

    /// Calculate curiosity check probability
    pub fn curiosity_chance(&self) -> f32 {
        IDLE_CURIOSITY_CHANCE * self.curiosity
    }
}

// ============================================================================
// Ambient Behaviors — Life When Not Commanded
// ============================================================================

/// Types of ambient behaviors that occur spontaneously
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum AmbientBehavior {
    /// Slow look around the room
    LookAround,
    /// Small positional adjustments
    Fidget,
    /// Brief attention to a sound direction
    SoundReaction,
    /// Deeper breathing cycle
    DeepBreath,
    /// Time-based posture adjustment
    PostureShift,
    /// Subtle personality expression
    PersonalityQuirk,
}

impl AmbientBehavior {
    /// Get a random ambient behavior based on weights
    pub fn random(curiosity: f32) -> Option<Self> {
        use rand::Rng;
        let mut rng = rand::thread_rng();
        let roll: f32 = rng.gen();

        // Probability thresholds (cumulative)
        let look_around = 0.25 * curiosity;
        let fidget = look_around + 0.2;
        let deep_breath = fidget + 0.25;
        let posture_shift = deep_breath + 0.15;
        let quirk = posture_shift + 0.15 * curiosity;

        if roll < look_around {
            Some(Self::LookAround)
        } else if roll < fidget {
            Some(Self::Fidget)
        } else if roll < deep_breath {
            Some(Self::DeepBreath)
        } else if roll < posture_shift {
            Some(Self::PostureShift)
        } else if roll < quirk {
            Some(Self::PersonalityQuirk)
        } else {
            None
        }
    }

    /// Get the animation keyframes for this ambient behavior
    pub fn keyframes(&self, expressiveness: f32) -> Vec<Keyframe> {
        let amp = 1.0 + expressiveness * 0.5; // Scale amplitude by expressiveness

        match self {
            Self::LookAround => vec![
                Keyframe::custom(
                    5.0 * amp,
                    -40.0 * amp,
                    40.0,
                    0.8,
                    EasingFunction::EaseInOutSine,
                ),
                Keyframe::custom(
                    10.0 * amp,
                    30.0 * amp,
                    42.0,
                    1.2,
                    EasingFunction::EaseInOutSine,
                ),
                Keyframe::custom(0.0, -15.0 * amp, 40.0, 0.8, EasingFunction::EaseInOutSine),
                Keyframe::custom(5.0 * amp, 20.0 * amp, 41.0, 0.6, EasingFunction::EaseInOut),
                Keyframe::custom(0.0, 0.0, 40.0, 0.5, EasingFunction::EaseOut),
            ],
            Self::Fidget => vec![
                Keyframe::custom(3.0 * amp, 5.0 * amp, 42.0, 0.3, EasingFunction::EaseInOut),
                Keyframe::custom(-2.0 * amp, -3.0 * amp, 38.0, 0.3, EasingFunction::EaseInOut),
                Keyframe::custom(0.0, 0.0, 40.0, 0.2, EasingFunction::EaseOut),
            ],
            Self::DeepBreath => vec![
                Keyframe::custom(8.0 * amp, 0.0, 48.0, 1.5, EasingFunction::EaseInOutSine),
                Keyframe::custom(-2.0 * amp, 0.0, 35.0, 2.0, EasingFunction::EaseInOutSine),
                Keyframe::custom(0.0, 0.0, 40.0, 1.0, EasingFunction::EaseOut),
            ],
            Self::PostureShift => vec![
                Keyframe::custom(5.0 * amp, 10.0 * amp, 38.0, 0.6, EasingFunction::EaseInOut),
                Keyframe::custom(0.0, 0.0, 42.0, 0.8, EasingFunction::EaseInOut),
            ],
            Self::PersonalityQuirk => vec![
                // A little "curious look" animation
                Keyframe::custom(
                    15.0 * amp,
                    20.0 * amp,
                    45.0,
                    0.3,
                    EasingFunction::EaseOutBack,
                ),
                Keyframe::custom(12.0 * amp, 18.0 * amp, 44.0, 0.4, EasingFunction::EaseInOut),
                Keyframe::custom(0.0, 0.0, 40.0, 0.5, EasingFunction::EaseInOutSine),
            ],
            Self::SoundReaction => vec![
                // Quick head turn toward sound (azimuth would be set dynamically)
                Keyframe::custom(10.0 * amp, 0.0, 48.0, 0.2, EasingFunction::EaseOutExpo),
                Keyframe::custom(8.0 * amp, 0.0, 45.0, 0.3, EasingFunction::EaseInOut),
                Keyframe::custom(0.0, 0.0, 40.0, 0.6, EasingFunction::EaseInOut),
            ],
        }
    }
}

// ============================================================================
// Interaction Memory — Learning User Patterns
// ============================================================================

/// Record of user interaction patterns
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct InteractionMemory {
    /// Total number of interactions
    pub interaction_count: u64,
    /// Last interaction timestamp (Unix seconds)
    pub last_interaction: Option<i64>,
    /// Preferred user position (azimuth, elevation)
    pub preferred_position: Option<(f32, f32)>,
    /// Hour-of-day interaction frequency (0-23)
    pub hourly_frequency: [u32; 24],
    /// Day-of-week interaction frequency (0=Sunday)
    pub daily_frequency: [u32; 7],
    /// Most common command intents
    pub common_intents: HashMap<String, u32>,
    /// Successful vs failed command ratio
    pub success_rate: f32,
    /// Last known presence state
    pub last_presence: bool,
}

impl InteractionMemory {
    /// Record a new interaction
    pub fn record_interaction(&mut self, intent: &str, success: bool) {
        self.interaction_count += 1;
        self.last_interaction = Some(chrono::Utc::now().timestamp());

        // Update hourly frequency
        let hour = Local::now().hour() as usize;
        self.hourly_frequency[hour] += 1;

        // Update daily frequency
        let day = Local::now().weekday().num_days_from_sunday() as usize;
        self.daily_frequency[day] += 1;

        // Update intent counts
        *self.common_intents.entry(intent.to_string()).or_insert(0) += 1;

        // Update success rate (exponential moving average)
        let success_val = if success { 1.0 } else { 0.0 };
        self.success_rate = 0.9 * self.success_rate + 0.1 * success_val;
    }

    /// Update preferred user position
    pub fn update_position(&mut self, azimuth: f32, elevation: f32) {
        if let Some((prev_az, prev_el)) = self.preferred_position {
            // Exponential moving average for smooth tracking
            let new_az = 0.8 * prev_az + 0.2 * azimuth;
            let new_el = 0.8 * prev_el + 0.2 * elevation;
            self.preferred_position = Some((new_az, new_el));
        } else {
            self.preferred_position = Some((azimuth, elevation));
        }
    }

    /// Get the peak activity hour
    pub fn peak_hour(&self) -> usize {
        self.hourly_frequency
            .iter()
            .enumerate()
            .max_by_key(|(_, &count)| count)
            .map(|(hour, _)| hour)
            .unwrap_or(12) // Default to noon
    }

    /// Check if current time is typically active
    pub fn is_active_period(&self) -> bool {
        let hour = Local::now().hour() as usize;
        let peak = self.peak_hour();

        // Consider hours within 3 of peak as active
        let distance =
            ((hour as i32 - peak as i32).abs()).min(24 - (hour as i32 - peak as i32).abs());
        distance <= 3
    }
}

// ============================================================================
// Seasonal Moods — Time-Based Personality Modulation
// ============================================================================

/// Seasonal mood modifiers
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct SeasonalMood {
    /// Base LED color bias (hue shift)
    pub color_bias: f32,
    /// Energy level modifier
    pub energy_modifier: f32,
    /// Special occasion flag
    pub special_occasion: Option<SpecialOccasion>,
}

/// Known special occasions
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum SpecialOccasion {
    Christmas,
    NewYear,
    Halloween,
    Valentine,
    Independence,
    Birthday,
}

impl SeasonalMood {
    /// Calculate current seasonal mood
    pub fn current() -> Self {
        let now = Local::now();
        let month = now.month();
        let day = now.day();

        // Check for special occasions
        let special = match (month, day) {
            (12, 24..=26) => Some(SpecialOccasion::Christmas),
            (12, 31) | (1, 1) => Some(SpecialOccasion::NewYear),
            (10, 31) => Some(SpecialOccasion::Halloween),
            (2, 14) => Some(SpecialOccasion::Valentine),
            (7, 4) => Some(SpecialOccasion::Independence),
            _ => None,
        };

        // Seasonal energy and color
        let (color_bias, energy) = match month {
            // Winter: cooler colors, cozy energy
            12 | 1 | 2 => (0.6, 0.7),
            // Spring: warming colors, increasing energy
            3 | 4 | 5 => (0.3, 0.85),
            // Summer: warm colors, high energy
            6 | 7 | 8 => (0.1, 0.9),
            // Fall: earthy colors, settling energy
            9 | 10 | 11 => (0.15, 0.75),
            _ => (0.0, 0.8),
        };

        Self {
            color_bias,
            energy_modifier: energy,
            special_occasion: special,
        }
    }

    /// Get LED pattern for special occasion
    pub fn occasion_pattern(&self) -> Option<AnimationPattern> {
        self.special_occasion.map(|occasion| match occasion {
            SpecialOccasion::Christmas => AnimationPattern::SpectralSweep,
            SpecialOccasion::NewYear => AnimationPattern::Rainbow,
            SpecialOccasion::Halloween => AnimationPattern::FanoLine(2), // Purple-ish
            SpecialOccasion::Valentine => AnimationPattern::ChromaticPulse { success: true },
            SpecialOccasion::Independence => AnimationPattern::SpectralSweep,
            SpecialOccasion::Birthday => AnimationPattern::Rainbow,
        })
    }
}

// ============================================================================
// Time-of-Day Awareness — Night Mode Behavior
// ============================================================================

/// Time-of-day behavior modifiers
#[derive(Debug, Clone, Copy)]
pub struct TimeAwareness {
    /// Is it currently nighttime?
    pub is_night: bool,
    /// Current hour (0-23)
    pub hour: u32,
    /// Energy level for this time (0.0 - 1.0)
    pub energy_level: f32,
    /// LED brightness cap (0.0 - 1.0)
    pub brightness_cap: f32,
}

impl TimeAwareness {
    /// Calculate current time awareness
    pub fn current() -> Self {
        let hour = Local::now().hour();

        let is_night = hour >= NIGHT_START_HOUR || hour < NIGHT_END_HOUR;

        // Energy curve: low at night, peaks mid-morning, dips early afternoon, moderate evening
        let energy_level = match hour {
            0..=5 => 0.3,
            6 => 0.5,
            7 => 0.7,
            8..=10 => 0.9,
            11 => 1.0,
            12..=13 => 0.85,
            14..=15 => 0.75,
            16..=18 => 0.85,
            19..=20 => 0.8,
            21 => 0.6,
            22..=23 => 0.4,
            _ => 0.7,
        };

        // Brightness: dim at night
        let brightness_cap = if is_night { 0.3 } else { 1.0 };

        Self {
            is_night,
            hour,
            energy_level,
            brightness_cap,
        }
    }

    /// Adjust behavior intensity for time of day
    pub fn adjust_intensity(&self, base: f32) -> f32 {
        base * self.energy_level
    }
}

// ============================================================================
// Main Personality Controller
// ============================================================================

/// Main personality controller that orchestrates all behaviors
pub struct PersonalityController {
    /// Current emotional state
    state: Arc<Mutex<EmotionalState>>,
    /// When current state was set
    state_timestamp: Arc<Mutex<Instant>>,
    /// Personality traits
    traits: PersonalityTraits,
    /// Interaction memory
    memory: Arc<Mutex<InteractionMemory>>,
    /// Last ambient behavior time
    last_ambient: Arc<Mutex<Instant>>,
    /// Reference to animatronics controller
    animatronics: Option<Arc<Mutex<Animatronics>>>,
    /// Running flag for background tasks
    running: Arc<std::sync::atomic::AtomicBool>,
}

impl PersonalityController {
    /// Create a new personality controller
    pub fn new(traits: PersonalityTraits) -> Self {
        Self {
            state: Arc::new(Mutex::new(EmotionalState::Alert)),
            state_timestamp: Arc::new(Mutex::new(Instant::now())),
            traits,
            memory: Arc::new(Mutex::new(InteractionMemory::default())),
            last_ambient: Arc::new(Mutex::new(Instant::now())),
            animatronics: None,
            running: Arc::new(std::sync::atomic::AtomicBool::new(false)),
        }
    }

    /// Create with default traits
    pub fn new_default() -> Self {
        Self::new(PersonalityTraits::default())
    }

    /// Set the animatronics reference
    pub fn set_animatronics(&mut self, animatronics: Arc<Mutex<Animatronics>>) {
        self.animatronics = Some(animatronics);
    }

    /// Get current emotional state
    pub async fn current_state(&self) -> EmotionalState {
        *self.state.lock().await
    }

    /// Get personality traits
    pub fn traits(&self) -> &PersonalityTraits {
        &self.traits
    }

    /// Update traits
    pub fn set_traits(&mut self, traits: PersonalityTraits) {
        self.traits = traits;
    }

    /// Handle a behavioral trigger
    pub async fn handle_trigger(&self, trigger: BehavioralTrigger) -> Result<()> {
        let response = match trigger {
            BehavioralTrigger::WakeWord => BehavioralResponse::on_wake_word(),
            BehavioralTrigger::CommandSuccess => BehavioralResponse::on_command_success(),
            BehavioralTrigger::CommandFailed(ref reason) => {
                BehavioralResponse::on_command_failed(reason)
            }
            BehavioralTrigger::Error(ref msg) => BehavioralResponse::on_error(msg),
            BehavioralTrigger::Goodbye => BehavioralResponse::on_goodbye(),
            BehavioralTrigger::IdleTimeout => BehavioralResponse::on_idle_timeout(),
            BehavioralTrigger::LoudSound {
                azimuth, elevation, ..
            } => BehavioralResponse::on_loud_sound(azimuth, elevation),
            BehavioralTrigger::PresenceDetected => BehavioralResponse::on_presence_detected(),
            BehavioralTrigger::PresenceLost => BehavioralResponse::on_presence_lost(),
            BehavioralTrigger::TranscriptionFailed => {
                BehavioralResponse::on_error("Couldn't hear you")
            }
            BehavioralTrigger::UnknownCommand => BehavioralResponse::on_unknown_command(),
            BehavioralTrigger::Praise => BehavioralResponse::on_command_success(),
            BehavioralTrigger::SpecialOccasion(ref name) => {
                BehavioralResponse::on_special_occasion(name)
            }
        };

        self.apply_response(&response).await
    }

    /// Apply a behavioral response
    async fn apply_response(&self, response: &BehavioralResponse) -> Result<()> {
        // Update emotional state
        *self.state.lock().await = response.emotion;
        *self.state_timestamp.lock().await = Instant::now();

        // Apply time-of-day modifiers
        let time = TimeAwareness::current();
        let transition_secs = self.traits.adjust_transition(response.transition_secs)
            * (1.0 / time.energy_level.max(0.5));

        // Update LED pattern (with brightness cap for night)
        led_ring::show_discovery_glow(time.brightness_cap);

        // Execute animation
        if let Some(ref anim) = self.animatronics {
            let anim = anim.lock().await;

            if let Some(ref keyframes) = response.sequence {
                anim.play_sequence(keyframes.clone()).await?;
            } else if let Some(pose) = response.pose {
                anim.transition_to(pose, transition_secs).await?;
            }

            // Set breathing amplitude based on emotion
            let breath_amp = response.emotion.breathing_amplitude()
                * self.traits.adjust_amplitude(1.0)
                * time.energy_level;
            anim.set_breathing_params(breath_amp, 4000.0).await;
        }

        info!(
            "Personality: {:?} -> {:?} (trigger applied)",
            response.emotion, response.led_pattern
        );

        Ok(())
    }

    /// Handle voice state change (from voice pipeline)
    pub async fn on_voice_state(&self, state: &VoiceState) -> Result<()> {
        let trigger = match state {
            VoiceState::Idle => return Ok(()), // No trigger for idle
            VoiceState::Listening => BehavioralTrigger::WakeWord,
            VoiceState::Processing => return self.set_emotion(EmotionalState::Thinking).await,
            VoiceState::Executing => return self.set_emotion(EmotionalState::Alert).await,
            VoiceState::Speaking => return self.set_emotion(EmotionalState::Happy).await,
            VoiceState::Error(msg) => BehavioralTrigger::Error(msg.clone()),
        };

        self.handle_trigger(trigger).await
    }

    /// Set emotional state directly
    pub async fn set_emotion(&self, emotion: EmotionalState) -> Result<()> {
        let current = *self.state.lock().await;
        if current == emotion {
            return Ok(());
        }

        *self.state.lock().await = emotion;
        *self.state_timestamp.lock().await = Instant::now();

        // Apply the emotion
        let pose = emotion.base_pose();
        let pattern = emotion.led_pattern();
        let time = TimeAwareness::current();
        let transition =
            self.traits.adjust_transition(pose.transition_duration()) * emotion.responsiveness();

        // Update LED
        match pattern {
            AnimationPattern::Breathing => led_ring::show_idle(),
            AnimationPattern::Pulse => led_ring::show_listening(),
            AnimationPattern::Spin => led_ring::show_processing(),
            AnimationPattern::ErrorFlash => led_ring::show_error(),
            AnimationPattern::Rainbow => led_ring::show_spectral(),
            AnimationPattern::ChromaticPulse { success } => led_ring::show_chromatic_pulse(success),
            AnimationPattern::FanoPulse => led_ring::show_fano_pulse(),
            _ => led_ring::show_spectral(),
        }

        // Update animatronics
        if let Some(ref anim) = self.animatronics {
            let anim = anim.lock().await;
            anim.transition_to(pose, transition * time.energy_level)
                .await?;

            let breath_amp = emotion.breathing_amplitude() * self.traits.energy * time.energy_level;
            anim.set_breathing_params(breath_amp, 4000.0).await;
        }

        debug!("Personality state: {:?}", emotion);
        Ok(())
    }

    /// Record an interaction for memory/learning
    pub async fn record_interaction(&self, intent: &str, success: bool) {
        let mut memory = self.memory.lock().await;
        memory.record_interaction(intent, success);
    }

    /// Update tracked user position
    pub async fn update_user_position(&self, azimuth: f32, elevation: f32) {
        let mut memory = self.memory.lock().await;
        memory.update_position(azimuth, elevation);
    }

    /// Check if we should perform an ambient behavior
    pub async fn maybe_ambient_behavior(&self) -> Result<()> {
        let last = *self.last_ambient.lock().await;
        if last.elapsed() < Duration::from_secs_f32(AMBIENT_BEHAVIOR_COOLDOWN_SECS) {
            return Ok(());
        }

        // Don't do ambient behaviors during active states
        let state = *self.state.lock().await;
        if !matches!(state, EmotionalState::Alert | EmotionalState::Sleepy) {
            return Ok(());
        }

        // Random chance based on curiosity
        let behavior = AmbientBehavior::random(self.traits.curiosity);
        if let Some(behavior) = behavior {
            info!("Ambient behavior: {:?}", behavior);
            *self.last_ambient.lock().await = Instant::now();

            if let Some(ref anim) = self.animatronics {
                let keyframes = behavior.keyframes(self.traits.expressiveness);
                let anim = anim.lock().await;
                anim.play_sequence(keyframes).await?;
            }
        }

        Ok(())
    }

    /// Check and handle state decay (emotional states returning to neutral)
    pub async fn check_state_decay(&self) -> Result<()> {
        let state = *self.state.lock().await;
        let timestamp = *self.state_timestamp.lock().await;

        if timestamp.elapsed() > state.decay_duration() {
            // Decay to appropriate state based on context
            let time = TimeAwareness::current();
            let target = if time.is_night {
                EmotionalState::Sleepy
            } else {
                EmotionalState::Alert
            };

            if state != target {
                self.set_emotion(target).await?;
            }
        }

        Ok(())
    }

    /// Start the background personality loop
    pub async fn start_background_loop(&self) {
        use std::sync::atomic::Ordering;

        if self.running.load(Ordering::SeqCst) {
            return;
        }

        self.running.store(true, Ordering::SeqCst);

        let state = self.state.clone();
        let state_timestamp = self.state_timestamp.clone();
        let traits = self.traits.clone();
        let last_ambient = self.last_ambient.clone();
        let animatronics = self.animatronics.clone();
        let running = self.running.clone();

        tokio::spawn(async move {
            let mut check_interval = tokio::time::interval(Duration::from_secs(10));

            while running.load(Ordering::SeqCst) {
                check_interval.tick().await;

                // Check state decay
                let current_state = *state.lock().await;
                let timestamp = *state_timestamp.lock().await;

                if timestamp.elapsed() > current_state.decay_duration() {
                    let time = TimeAwareness::current();
                    let target = if time.is_night {
                        EmotionalState::Sleepy
                    } else {
                        EmotionalState::Alert
                    };

                    if current_state != target {
                        *state.lock().await = target;
                        *state_timestamp.lock().await = Instant::now();
                        debug!("State decayed to {:?}", target);
                    }
                }

                // Maybe do ambient behavior
                let last = *last_ambient.lock().await;
                if last.elapsed() >= Duration::from_secs_f32(AMBIENT_BEHAVIOR_COOLDOWN_SECS) {
                    let current = *state.lock().await;
                    if matches!(current, EmotionalState::Alert | EmotionalState::Sleepy) {
                        if let Some(behavior) = AmbientBehavior::random(traits.curiosity) {
                            *last_ambient.lock().await = Instant::now();

                            if let Some(ref anim) = animatronics {
                                let keyframes = behavior.keyframes(traits.expressiveness);
                                let anim = anim.lock().await;
                                let _ = anim.play_sequence(keyframes).await;
                            }
                        }
                    }
                }
            }
        });
    }

    /// Stop the background loop
    pub fn stop_background_loop(&self) {
        self.running
            .store(false, std::sync::atomic::Ordering::SeqCst);
    }

    /// Get seasonal mood information
    pub fn seasonal_mood(&self) -> SeasonalMood {
        SeasonalMood::current()
    }

    /// Get time-of-day awareness
    pub fn time_awareness(&self) -> TimeAwareness {
        TimeAwareness::current()
    }
}

// ============================================================================
// Module-Level API (for simpler usage)
// ============================================================================

static PERSONALITY: tokio::sync::OnceCell<Mutex<PersonalityController>> =
    tokio::sync::OnceCell::const_new();

/// Initialize the global personality controller
pub async fn init(traits: PersonalityTraits) -> Result<()> {
    let controller = PersonalityController::new(traits);

    PERSONALITY
        .set(Mutex::new(controller))
        .map_err(|_| anyhow::anyhow!("Personality already initialized"))?;

    Ok(())
}

/// Initialize with default traits
pub async fn init_default() -> Result<()> {
    init(PersonalityTraits::default()).await
}

/// Handle a behavioral trigger
pub async fn trigger(event: BehavioralTrigger) -> Result<()> {
    if let Some(p) = PERSONALITY.get() {
        p.lock().await.handle_trigger(event).await
    } else {
        Ok(())
    }
}

/// Set emotional state
pub async fn set_emotion(emotion: EmotionalState) -> Result<()> {
    if let Some(p) = PERSONALITY.get() {
        p.lock().await.set_emotion(emotion).await
    } else {
        Ok(())
    }
}

/// Get current emotional state
pub async fn current_emotion() -> EmotionalState {
    if let Some(p) = PERSONALITY.get() {
        p.lock().await.current_state().await
    } else {
        EmotionalState::Alert
    }
}

/// Record an interaction
pub async fn record_interaction(intent: &str, success: bool) {
    if let Some(p) = PERSONALITY.get() {
        p.lock().await.record_interaction(intent, success).await;
    }
}

/// Convenience: trigger on wake word
pub async fn on_wake_word() -> Result<()> {
    trigger(BehavioralTrigger::WakeWord).await
}

/// Convenience: trigger on command success
pub async fn on_success() -> Result<()> {
    trigger(BehavioralTrigger::CommandSuccess).await
}

/// Convenience: trigger on command failure
pub async fn on_failure(reason: &str) -> Result<()> {
    trigger(BehavioralTrigger::CommandFailed(reason.to_string())).await
}

/// Convenience: trigger on goodbye
pub async fn on_goodbye() -> Result<()> {
    trigger(BehavioralTrigger::Goodbye).await
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_emotional_state_defaults() {
        assert_eq!(EmotionalState::default(), EmotionalState::Alert);
    }

    #[test]
    fn test_personality_traits_defaults() {
        let traits = PersonalityTraits::default();
        assert!(traits.responsiveness >= 0.0 && traits.responsiveness <= 1.0);
        assert!(traits.expressiveness >= 0.0 && traits.expressiveness <= 1.0);
        assert!(traits.curiosity >= 0.0 && traits.curiosity <= 1.0);
        assert!(traits.energy >= 0.0 && traits.energy <= 1.0);
    }

    #[test]
    fn test_trait_presets() {
        let energetic = PersonalityTraits::energetic();
        let calm = PersonalityTraits::calm();

        assert!(energetic.energy > calm.energy);
        assert!(energetic.expressiveness > calm.expressiveness);
    }

    #[test]
    fn test_transition_adjustment() {
        let traits = PersonalityTraits::default();
        let adjusted = traits.adjust_transition(1.0);

        // Higher responsiveness should give shorter transitions
        let fast_traits = PersonalityTraits {
            responsiveness: 1.0,
            ..Default::default()
        };
        let fast_adjusted = fast_traits.adjust_transition(1.0);

        assert!(fast_adjusted < adjusted);
    }

    #[test]
    fn test_time_awareness() {
        let time = TimeAwareness::current();
        assert!(time.hour < 24);
        assert!(time.energy_level >= 0.0 && time.energy_level <= 1.0);
        assert!(time.brightness_cap >= 0.0 && time.brightness_cap <= 1.0);
    }

    #[test]
    fn test_seasonal_mood() {
        let mood = SeasonalMood::current();
        assert!(mood.energy_modifier >= 0.0 && mood.energy_modifier <= 1.0);
    }

    #[test]
    fn test_interaction_memory() {
        let mut memory = InteractionMemory::default();
        memory.record_interaction("Lights", true);
        memory.record_interaction("Lights", true);
        memory.record_interaction("Fireplace", false);

        assert_eq!(memory.interaction_count, 3);
        assert_eq!(memory.common_intents.get("Lights"), Some(&2));
        assert_eq!(memory.common_intents.get("Fireplace"), Some(&1));
    }

    #[test]
    fn test_emotional_state_intensity() {
        assert!(EmotionalState::Alert.intensity() > EmotionalState::Sleepy.intensity());
        assert!(EmotionalState::Excited.intensity() > EmotionalState::Sad.intensity());
    }

    #[test]
    fn test_behavioral_response_creation() {
        let wake = BehavioralResponse::on_wake_word();
        assert_eq!(wake.emotion, EmotionalState::Alert);
        assert!(wake.sequence.is_some());

        let success = BehavioralResponse::on_command_success();
        assert_eq!(success.emotion, EmotionalState::Happy);

        let goodbye = BehavioralResponse::on_goodbye();
        assert!(goodbye.sequence.is_some());
    }

    #[tokio::test]
    async fn test_personality_controller_creation() {
        let controller = PersonalityController::new_default();
        let state = controller.current_state().await;
        assert_eq!(state, EmotionalState::Alert);
    }

    #[tokio::test]
    async fn test_emotion_change() {
        let controller = PersonalityController::new_default();

        controller.set_emotion(EmotionalState::Happy).await.unwrap();
        assert_eq!(controller.current_state().await, EmotionalState::Happy);

        controller
            .set_emotion(EmotionalState::Thinking)
            .await
            .unwrap();
        assert_eq!(controller.current_state().await, EmotionalState::Thinking);
    }
}

/*
 * 鏡
 * Not just servos. Not just LEDs.
 * A living presence in the room.
 *
 * The lamp tilts its head and asks:
 * "What do you need?"
 *
 * Grove (e₆) — Nurturing, organic, alive.
 * h(x) >= 0. Always.
 */
