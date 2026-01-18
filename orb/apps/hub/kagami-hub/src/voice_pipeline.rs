//! Voice processing pipeline for Kagami Hub
//!
//! This module implements the core voice command pipeline:
//!
//! ```text
//! ┌────────────┐   ┌─────────┐   ┌─────────┐   ┌─────┐   ┌─────┐
//! │ Wake Word  │ → │   STT   │ → │ Parser  │ → │ API │ → │ TTS │
//! └────────────┘   └─────────┘   └─────────┘   └─────┘   └─────┘
//!      Flow           Flow         Nexus       Crystal   Beacon
//!      (e₃)           (e₃)         (e₄)        (e₇)      (e₅)
//! ```
//!
//! ## Pipeline States
//!
//! The voice pipeline operates as a state machine with the following states:
//!
//! 1. **Listening** - Idle, waiting for wake word detection
//! 2. **Capturing** - Wake word detected, recording user speech
//! 3. **Transcribing** - Converting speech to text via Whisper STT
//! 4. **Executing** - Parsing command and calling Kagami API
//! 5. **Speaking** - Playing TTS response to user
//!
//! ## Command Parsing
//!
//! Commands are parsed from natural language into structured [`VoiceCommand`]
//! objects containing an [`CommandIntent`] and optional [`CommandEntities`].
//!
//! ### Supported Commands
//!
//! | Voice Pattern | Intent | Example |
//! |--------------|--------|---------|
//! | "movie mode" | Scene | `CommandIntent::Scene("movie_mode")` |
//! | "goodnight" | Scene | `CommandIntent::Scene("goodnight")` |
//! | "lights 50" | Lights | `CommandIntent::Lights(50)` |
//! | "fireplace on" | Fireplace | `CommandIntent::Fireplace(true)` |
//! | "shades open" | Shades | `CommandIntent::Shades("open")` |
//! | "tv down" | TV | `CommandIntent::TV("lower")` |
//!
//! ## Usage
//!
//! ```rust,ignore
//! use kagami_hub::voice_pipeline::{parse_command, CommandIntent};
//!
//! let cmd = parse_command("lights fifty percent in the living room");
//! assert_eq!(cmd.intent, CommandIntent::Lights(50));
//! assert!(cmd.entities.rooms.is_some());
//! ```
//!
//! ## Colony Mapping
//!
//! - **Flow (e₃)**: Audio capture and wake word detection
//! - **Nexus (e₄)**: Command parsing and entity extraction
//! - **Crystal (e₇)**: API execution and response generation

use regex::Regex;
use std::sync::LazyLock;

// Word boundary regex patterns for avoiding false positives
// e.g., "arm" should not match "harm", "farm", "charm"
static WORD_ARM: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"\barm\b").unwrap());
static WORD_LOCK: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"\block\b").unwrap());
static WORD_FIRE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"\bfire\b").unwrap());
static WORD_RAIN: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"\brain\b").unwrap());

/// Check if a word matches with word boundaries (not as part of another word)
fn has_word(text: &str, pattern: &Regex) -> bool {
    pattern.is_match(text)
}

/// Voice pipeline state machine
///
/// Represents the current state of the voice processing pipeline.
/// State transitions are driven by external events (wake word detection,
/// transcription completion, etc.).
///
/// # State Diagram
///
/// ```text
/// ┌──────────────┐
/// │  Listening   │◄─────────────────────────────────┐
/// └──────┬───────┘                                  │
///        │ wake word detected                       │
///        ▼                                          │
/// ┌──────────────┐                                  │
/// │  Capturing   │                                  │
/// └──────┬───────┘                                  │
///        │ silence detected                         │
///        ▼                                          │
/// ┌──────────────┐                                  │
/// │ Transcribing │                                  │
/// └──────┬───────┘                                  │
///        │ text ready                               │
///        ▼                                          │
/// ┌──────────────┐                                  │
/// │  Executing   │                                  │
/// └──────┬───────┘                                  │
///        │ response ready                           │
///        ▼                                          │
/// ┌──────────────┐                                  │
/// │   Speaking   │──────────────────────────────────┘
/// └──────────────┘      audio complete
/// ```
#[derive(Debug, Clone, PartialEq)]
pub enum PipelineState {
    /// Listening for wake word (e.g., "Hey Kagami")
    ///
    /// In this state, the hub is passively monitoring audio input
    /// through the wake word detector. LED ring shows idle animation.
    Listening,

    /// Wake word detected, capturing user speech
    ///
    /// Audio is being recorded until silence is detected or a
    /// timeout occurs. LED ring shows listening animation.
    Capturing,

    /// Transcribing captured speech via Whisper STT
    ///
    /// Audio buffer is being processed by the speech-to-text engine.
    /// LED ring shows processing animation.
    Transcribing,

    /// Executing parsed command via Kagami API
    ///
    /// Command has been parsed and is being sent to the smart home
    /// API for execution. LED ring shows colony-specific animation.
    Executing,

    /// Speaking TTS response to user
    ///
    /// Response audio is being played through the speaker.
    /// LED ring shows speaking animation.
    Speaking,
}

/// Voice command parsed from speech
///
/// Contains the structured representation of a user's voice command,
/// including the original transcription, parsed intent, and extracted entities.
///
/// # Fields
///
/// - `raw_text` - The original transcribed text from STT
/// - `intent` - The parsed [`CommandIntent`] (what action to take)
/// - `entities` - Extracted [`CommandEntities`] (rooms, levels, etc.)
///
/// # Example
///
/// ```rust,ignore
/// let cmd = parse_command("turn on the living room lights to fifty percent");
/// println!("Intent: {:?}", cmd.intent);        // Lights(50)
/// println!("Rooms: {:?}", cmd.entities.rooms); // Some(["living room"])
/// ```
#[derive(Debug)]
pub struct VoiceCommand {
    /// Original transcribed text from speech-to-text
    pub raw_text: String,
    /// Parsed command intent
    pub intent: CommandIntent,
    /// Extracted entities (rooms, levels, etc.)
    pub entities: CommandEntities,
}

/// Music control actions
///
/// Actions for controlling music playback through the smart home system.
/// These are typically forwarded to the Spotify integration.
#[derive(Debug, Clone, PartialEq)]
pub enum MusicAction {
    /// Start playback, optionally with a specific playlist name
    Play(Option<String>),
    /// Pause current playback
    Pause,
    /// Resume paused playback
    Resume,
    /// Skip to next track
    Skip,
    /// Increase volume by default increment
    VolumeUp,
    /// Decrease volume by default increment
    VolumeDown,
    /// Set volume to specific level (0-100)
    SetVolume(i32),
}

/// Tesla vehicle actions
#[derive(Debug, Clone, PartialEq)]
pub enum TeslaAction {
    /// Pre-condition climate to target temperature
    Climate(Option<i32>),
    /// Lock vehicle doors
    Lock,
    /// Unlock vehicle doors
    Unlock,
    /// Check charge level
    ChargeStatus,
    /// Start charging
    StartCharge,
    /// Stop charging
    StopCharge,
    /// Enable sentry mode
    SentryOn,
    /// Disable sentry mode
    SentryOff,
    /// Open frunk
    OpenFrunk,
    /// Check vehicle location
    Location,
}

/// Eight Sleep bed actions
#[derive(Debug, Clone, PartialEq)]
pub enum BedAction {
    /// Set bed temperature (-100 to +100, negative = cooling)
    SetTemp(i32),
    /// Set specific side temperature
    SetSideTemp { side: String, level: i32 },
    /// Turn bed off
    Off,
    /// Get sleep data
    SleepStatus,
}

/// Outdoor lighting actions (Oelo)
#[derive(Debug, Clone, PartialEq)]
pub enum OutdoorAction {
    /// Turn outdoor lights on
    On,
    /// Turn outdoor lights off
    Off,
    /// Set color (e.g., "red", "blue", "#FF0000")
    Color(String),
    /// Activate a preset pattern
    Pattern(String),
    /// Christmas theme
    Christmas,
    /// Party theme
    Party,
    /// Welcome theme
    Welcome,
}

/// Security/alarm actions
#[derive(Debug, Clone, PartialEq)]
pub enum SecurityAction {
    /// Arm the alarm system
    Arm,
    /// Arm in stay mode (perimeter only)
    ArmStay,
    /// Disarm the alarm
    Disarm,
    /// Get alarm status
    Status,
}

/// Parsed command intent from voice input
///
/// Represents what action the user wants to perform. Each variant
/// corresponds to a category of smart home control.
///
/// # Variant Mapping
///
/// | Intent | Trigger Words | API Endpoint |
/// |--------|---------------|--------------|
/// | Scene | "movie", "goodnight", "welcome", "away", "working" | `/scene/{name}` |
/// | Lights | "lights", "light" | `/lights` |
/// | Fireplace | "fireplace", "fire" | `/fireplace` |
/// | Shades | "shade", "blind", "curtain" | `/shades` |
/// | TV | "tv", "television" | `/tv/mount` |
/// | Music | "play", "pause", "skip" | `/spotify/*` |
/// | Announce | "announce", "say", "tell" | `/announce` |
/// | Lock | "lock", "unlock" | `/locks` |
/// | Temperature | "temperature", "thermostat", "degrees" | `/climate` |
/// | Tesla | "car", "tesla", "vehicle" | `/tesla/*` |
/// | Bed | "bed", "mattress", "eight sleep" | `/bed/*` |
/// | Outdoor | "outdoor", "christmas", "patio lights" | `/outdoor/*` |
/// | Security | "alarm", "arm", "disarm" | `/security/*` |
/// | Presence | "anyone home", "who's here" | `/presence` |
/// | Weather | "weather", "temperature outside" | `/weather` |
/// | FindDevice | "find my", "where's my" | `/findmy/*` |
/// | VacationMode | "vacation mode" | `/automation/vacation` |
/// | GuestMode | "guest mode" | `/automation/guest` |
#[derive(Debug, Clone, PartialEq)]
pub enum CommandIntent {
    /// Activate a predefined scene (e.g., "movie_mode", "goodnight", "away", "working")
    Scene(String),
    /// Set light level (0-100) in specified rooms
    Lights(i32),
    /// Turn fireplace on (true) or off (false)
    Fireplace(bool),
    /// Open or close shades ("open" or "close")
    Shades(String),
    /// Raise or lower TV mount ("raise" or "lower")
    TV(String),
    /// Lock (true) or unlock (false) all doors
    Lock(bool),
    /// Set thermostat to target temperature (Fahrenheit)
    Temperature(i32),
    /// Music control action
    Music(MusicAction),
    /// Broadcast announcement message to speakers
    Announce(String),
    /// Request system status summary
    Status,
    /// Request help/available commands
    Help,
    /// Cancel current operation
    Cancel,

    // ═══════════════════════════════════════════════════════════════════════
    // NEW INTENTS - Full Smart Home Coverage
    // ═══════════════════════════════════════════════════════════════════════
    /// Tesla vehicle control
    Tesla(TeslaAction),
    /// Eight Sleep bed control
    Bed(BedAction),
    /// Outdoor lights (Oelo)
    Outdoor(OutdoorAction),
    /// Security/alarm system
    Security(SecurityAction),
    /// Query presence (who's home)
    Presence,
    /// Get weather information
    Weather,
    /// Find a device (Find My)
    FindDevice(String),
    /// Enable/disable vacation mode
    VacationMode(bool),
    /// Enable/disable guest mode
    GuestMode(bool),
    /// Climate control for specific room
    ClimateZone { room: String, temp: i32 },
    /// Per-room HVAC mode
    HvacMode { room: Option<String>, mode: String },

    /// Unrecognized command
    Unknown,
}

/// Extracted entities from voice command
///
/// Contains optional contextual information extracted from the user's
/// voice command, such as room names and numeric levels.
///
/// # Room Detection
///
/// Supports the following room names (case-insensitive):
/// - living room, kitchen, dining, bedroom, primary
/// - office, bathroom, garage, patio, deck
/// - loft, game room, laundry
///
/// # Level Extraction
///
/// Levels can be specified as:
/// - Numeric: "lights 50", "lights to 75"
/// - Keywords: "off" (0), "dim" (25), "half" (50), "full" (100)
/// - Word numbers: "fifty", "seventy", etc.
#[derive(Debug, Default)]
pub struct CommandEntities {
    /// Target room(s) for the command
    pub rooms: Option<Vec<String>>,
    /// Numeric level (0-100) for lights, volume, etc.
    pub level: Option<i32>,
}

/// Parse transcribed text into a structured command
///
/// Takes the raw text output from the STT engine and converts it into
/// a structured [`VoiceCommand`] with intent and entities.
///
/// # Arguments
///
/// * `text` - The transcribed text from speech-to-text
///
/// # Returns
///
/// A [`VoiceCommand`] containing the parsed intent and extracted entities.
/// If the command is not recognized, returns `CommandIntent::Unknown`.
///
/// # Examples
///
/// ```rust,ignore
/// // Scene activation
/// let cmd = parse_command("start movie mode");
/// assert_eq!(cmd.intent, CommandIntent::Scene("movie_mode".to_string()));
///
/// // Light control with level
/// let cmd = parse_command("living room lights to fifty");
/// assert_eq!(cmd.intent, CommandIntent::Lights(50));
/// assert_eq!(cmd.entities.rooms, Some(vec!["living room".to_string()]));
///
/// // Fireplace toggle
/// let cmd = parse_command("turn on the fireplace");
/// assert_eq!(cmd.intent, CommandIntent::Fireplace(true));
///
/// // Unrecognized command
/// let cmd = parse_command("do something random");
/// assert_eq!(cmd.intent, CommandIntent::Unknown);
/// ```
///
/// # Note
///
/// This is a simple rule-based parser. For more sophisticated NLU,
/// consider integrating with an external service or ML model.
pub fn parse_command(text: &str) -> VoiceCommand {
    let lowered = text.to_lowercase();
    let mut entities = CommandEntities::default();

    let intent =
    // ═══════════════════════════════════════════════════════════════════════
    // SCENES - Predefined automation sequences
    // ═══════════════════════════════════════════════════════════════════════
    if lowered.contains("movie") || lowered.contains("cinema") {
        CommandIntent::Scene("movie_mode".to_string())
    } else if lowered.contains("goodnight") || lowered.contains("good night") {
        CommandIntent::Scene("goodnight".to_string())
    } else if lowered.contains("welcome") && lowered.contains("home") {
        CommandIntent::Scene("welcome_home".to_string())
    } else if lowered.contains("away") && (lowered.contains("mode") || lowered.contains("leaving")) {
        CommandIntent::Scene("away".to_string())
    } else if lowered.contains("working") || lowered.contains("work mode") || lowered.contains("focus mode") {
        CommandIntent::Scene("working".to_string())
    } else if lowered.contains("morning") && lowered.contains("routine") {
        CommandIntent::Scene("morning".to_string())
    }

    // ═══════════════════════════════════════════════════════════════════════
    // LOCK/UNLOCK - Door security
    // Use word boundary matching to avoid "clock", "block", etc.
    // ═══════════════════════════════════════════════════════════════════════
    else if (has_word(&lowered, &WORD_LOCK) || lowered.contains("unlock")) && !lowered.contains("car") && !lowered.contains("tesla") {
        let unlock = lowered.contains("unlock");
        CommandIntent::Lock(!unlock)
    }

    // ═══════════════════════════════════════════════════════════════════════
    // TEMPERATURE/CLIMATE - HVAC control
    // ═══════════════════════════════════════════════════════════════════════
    else if (lowered.contains("temperature") || lowered.contains("thermostat") || lowered.contains("degrees"))
            && !lowered.contains("outside") && !lowered.contains("weather") && !lowered.contains("bed") {
        let temp = extract_number(&lowered).unwrap_or(72);
        let rooms = extract_rooms(&lowered);
        if let Some(ref room_list) = rooms {
            if let Some(room) = room_list.first() {
                entities.rooms = rooms.clone();
                CommandIntent::ClimateZone { room: room.clone(), temp }
            } else {
                CommandIntent::Temperature(temp)
            }
        } else {
            CommandIntent::Temperature(temp)
        }
    }
    else if lowered.contains("hvac") || (lowered.contains("set") && (lowered.contains("heat") || lowered.contains("cool") || lowered.contains("auto"))) {
        let mode = if lowered.contains("heat") {
            "heat"
        } else if lowered.contains("cool") {
            "cool"
        } else if lowered.contains("auto") {
            "auto"
        } else {
            "auto"
        };
        entities.rooms = extract_rooms(&lowered);
        CommandIntent::HvacMode { room: entities.rooms.as_ref().and_then(|r| r.first().cloned()), mode: mode.to_string() }
    }

    // ═══════════════════════════════════════════════════════════════════════
    // STATUS/HELP/CANCEL - Meta commands
    // Note: "stop" is handled later to avoid collision with "stop the music", "stop charging"
    // ═══════════════════════════════════════════════════════════════════════
    else if lowered.contains("status") || lowered.contains("what's going on") || lowered.contains("how's the house") {
        CommandIntent::Status
    }
    else if lowered.contains("help") || lowered.contains("what can you do") || lowered.contains("commands") {
        CommandIntent::Help
    }
    else if lowered.contains("cancel") || lowered.contains("never mind") {
        // Note: "stop" moved to end to avoid collision with "stop the music", "stop charging the car"
        CommandIntent::Cancel
    }

    // ═══════════════════════════════════════════════════════════════════════
    // ANNOUNCE - Must come before BED to avoid "bed" collision in "time for bed"
    // Use raw text (not lowered) to preserve capitalization
    // ═══════════════════════════════════════════════════════════════════════
    else if lowered.contains("announce") || (lowered.contains("say") && !lowered.contains("what")) ||
            (lowered.contains("tell") && lowered.contains("everyone")) {
        let message = extract_announcement(text);
        CommandIntent::Announce(message)
    }

    // ═══════════════════════════════════════════════════════════════════════
    // TESLA - Vehicle control
    // Also check for "charging" to handle "stop charging" without explicit "car"
    // ═══════════════════════════════════════════════════════════════════════
    else if lowered.contains("car") || lowered.contains("tesla") || lowered.contains("vehicle") ||
            (lowered.contains("charging") && lowered.contains("stop")) {
        if lowered.contains("warm") || lowered.contains("heat") || lowered.contains("cool") || lowered.contains("climate") {
            let temp = extract_number(&lowered);
            CommandIntent::Tesla(TeslaAction::Climate(temp))
        } else if lowered.contains("lock") {
            CommandIntent::Tesla(TeslaAction::Lock)
        } else if lowered.contains("unlock") {
            CommandIntent::Tesla(TeslaAction::Unlock)
        } else if (lowered.contains("charge") || lowered.contains("charging")) && lowered.contains("start") {
            CommandIntent::Tesla(TeslaAction::StartCharge)
        } else if (lowered.contains("charge") || lowered.contains("charging")) && lowered.contains("stop") {
            CommandIntent::Tesla(TeslaAction::StopCharge)
        } else if lowered.contains("charge") || lowered.contains("charging") || lowered.contains("battery") {
            CommandIntent::Tesla(TeslaAction::ChargeStatus)
        } else if lowered.contains("sentry") && lowered.contains("off") {
            CommandIntent::Tesla(TeslaAction::SentryOff)
        } else if lowered.contains("sentry") {
            CommandIntent::Tesla(TeslaAction::SentryOn)
        } else if lowered.contains("frunk") || lowered.contains("front trunk") {
            CommandIntent::Tesla(TeslaAction::OpenFrunk)
        } else if lowered.contains("where") || lowered.contains("location") || lowered.contains("find") {
            CommandIntent::Tesla(TeslaAction::Location)
        } else {
            CommandIntent::Tesla(TeslaAction::ChargeStatus) // Default: check status
        }
    }

    // ═══════════════════════════════════════════════════════════════════════
    // BED - Eight Sleep control (avoid matching "bedroom")
    // ═══════════════════════════════════════════════════════════════════════
    else if (lowered.contains("bed") && !lowered.contains("bedroom")) || lowered.contains("mattress") || lowered.contains("eight sleep") {
        if lowered.contains("off") {
            CommandIntent::Bed(BedAction::Off)
        } else if lowered.contains("sleep") && (lowered.contains("how") || lowered.contains("score") || lowered.contains("last night")) {
            CommandIntent::Bed(BedAction::SleepStatus)
        } else if lowered.contains("my side") || lowered.contains("tim") {
            let level = extract_number(&lowered).unwrap_or(50);
            CommandIntent::Bed(BedAction::SetSideTemp { side: "left".to_string(), level })
        } else if lowered.contains("jill") || lowered.contains("her side") {
            let level = extract_number(&lowered).unwrap_or(50);
            CommandIntent::Bed(BedAction::SetSideTemp { side: "right".to_string(), level })
        } else {
            let level = extract_number(&lowered).unwrap_or(50);
            CommandIntent::Bed(BedAction::SetTemp(level))
        }
    }

    // ═══════════════════════════════════════════════════════════════════════
    // OUTDOOR LIGHTS - Oelo
    // ═══════════════════════════════════════════════════════════════════════
    else if lowered.contains("christmas") && (lowered.contains("light") || lowered.contains("outdoor") || lowered.contains("outside")) {
        CommandIntent::Outdoor(OutdoorAction::Christmas)
    }
    else if lowered.contains("party") && lowered.contains("light") {
        CommandIntent::Outdoor(OutdoorAction::Party)
    }
    else if (lowered.contains("outdoor") || lowered.contains("outside")) && lowered.contains("light") {
        if lowered.contains("off") {
            CommandIntent::Outdoor(OutdoorAction::Off)
        } else if lowered.contains("red") {
            CommandIntent::Outdoor(OutdoorAction::Color("red".to_string()))
        } else if lowered.contains("blue") {
            CommandIntent::Outdoor(OutdoorAction::Color("blue".to_string()))
        } else if lowered.contains("green") {
            CommandIntent::Outdoor(OutdoorAction::Color("green".to_string()))
        } else if lowered.contains("white") {
            CommandIntent::Outdoor(OutdoorAction::Color("white".to_string()))
        } else {
            CommandIntent::Outdoor(OutdoorAction::On)
        }
    }

    // ═══════════════════════════════════════════════════════════════════════
    // SECURITY - Alarm system
    // Use word boundary for "arm" to avoid "harm", "farm", "charm"
    // ═══════════════════════════════════════════════════════════════════════
    else if lowered.contains("alarm") || lowered.contains("disarm") ||
            (has_word(&lowered, &WORD_ARM) && !lowered.contains("warm")) || lowered.contains("security") {
        if lowered.contains("disarm") || lowered.contains("off") {
            CommandIntent::Security(SecurityAction::Disarm)
        } else if lowered.contains("stay") || lowered.contains("home") {
            CommandIntent::Security(SecurityAction::ArmStay)
        } else if lowered.contains("status") || lowered.contains("check") {
            CommandIntent::Security(SecurityAction::Status)
        } else {
            CommandIntent::Security(SecurityAction::Arm)
        }
    }

    // ═══════════════════════════════════════════════════════════════════════
    // PRESENCE - Who's home
    // ═══════════════════════════════════════════════════════════════════════
    else if lowered.contains("anyone home") || lowered.contains("anybody home") ||
            lowered.contains("who's home") || lowered.contains("who is home") ||
            lowered.contains("who's here") || lowered.contains("is anyone") {
        CommandIntent::Presence
    }

    // ═══════════════════════════════════════════════════════════════════════
    // WEATHER
    // Use word boundary for "rain" to avoid "brain", "train", "drain"
    // ═══════════════════════════════════════════════════════════════════════
    else if lowered.contains("weather") || (lowered.contains("temperature") && lowered.contains("outside")) ||
            lowered.contains("forecast") || has_word(&lowered, &WORD_RAIN) {
        CommandIntent::Weather
    }

    // ═══════════════════════════════════════════════════════════════════════
    // FIND MY DEVICE
    // ═══════════════════════════════════════════════════════════════════════
    else if lowered.contains("find my") || lowered.contains("where's my") || lowered.contains("where is my") {
        let device = extract_device_name(&lowered);
        CommandIntent::FindDevice(device)
    }

    // ═══════════════════════════════════════════════════════════════════════
    // VACATION MODE
    // ═══════════════════════════════════════════════════════════════════════
    else if lowered.contains("vacation") && lowered.contains("mode") {
        let enabled = !lowered.contains("off") && !lowered.contains("disable") && !lowered.contains("end");
        CommandIntent::VacationMode(enabled)
    }

    // ═══════════════════════════════════════════════════════════════════════
    // GUEST MODE
    // ═══════════════════════════════════════════════════════════════════════
    else if lowered.contains("guest") && lowered.contains("mode") {
        let enabled = !lowered.contains("off") && !lowered.contains("disable") && !lowered.contains("end");
        CommandIntent::GuestMode(enabled)
    }

    // ═══════════════════════════════════════════════════════════════════════
    // MUSIC - Spotify control
    // Note: "stop the music" handled here to avoid Cancel collision
    // ═══════════════════════════════════════════════════════════════════════
    else if lowered.contains("play") && (lowered.contains("music") || lowered.contains("playlist") || lowered.contains("spotify")) {
        let playlist = extract_playlist_name(&lowered);
        CommandIntent::Music(MusicAction::Play(playlist))
    }
    else if (lowered.contains("pause") || lowered.contains("stop")) && lowered.contains("music") {
        CommandIntent::Music(MusicAction::Pause)
    }
    else if lowered.contains("pause") && !lowered.contains("shade") {
        CommandIntent::Music(MusicAction::Pause)
    }
    else if lowered.contains("resume") && lowered.contains("music") {
        CommandIntent::Music(MusicAction::Resume)
    }
    else if lowered.contains("skip") || lowered.contains("next song") || lowered.contains("next track") {
        CommandIntent::Music(MusicAction::Skip)
    }
    else if lowered.contains("volume") && lowered.contains("up") {
        CommandIntent::Music(MusicAction::VolumeUp)
    }
    else if lowered.contains("volume") && lowered.contains("down") {
        CommandIntent::Music(MusicAction::VolumeDown)
    }

    // ═══════════════════════════════════════════════════════════════════════
    // EXISTING: LIGHTS
    // Check for numeric level first, then fall back to keyword-based levels
    // ═══════════════════════════════════════════════════════════════════════
    else if lowered.contains("light") && !lowered.contains("christmas") && !lowered.contains("outdoor") {
        // Try to extract a number first (handles "lights one", "lights fifty", etc.)
        let level = if let Some(num) = extract_number(&lowered) {
            num.clamp(0, 100)
        } else if lowered.contains("off") {
            0
        } else if lowered.contains("dim") || lowered.contains("low") {
            25
        } else if lowered.contains("half") {
            50
        } else if lowered.contains("on") || lowered.contains("full") || lowered.contains("bright") {
            100
        } else {
            100 // default to full brightness
        };
        entities.level = Some(level);
        entities.rooms = extract_rooms(&lowered);
        CommandIntent::Lights(level)
    }

    // ═══════════════════════════════════════════════════════════════════════
    // EXISTING: FIREPLACE
    // Use word boundary for "fire" to avoid "fire up the music"
    // ═══════════════════════════════════════════════════════════════════════
    else if lowered.contains("fireplace") ||
            (has_word(&lowered, &WORD_FIRE) && !lowered.contains("alarm") && !lowered.contains("up the")) {
        let on = !lowered.contains("off");
        CommandIntent::Fireplace(on)
    }

    // ═══════════════════════════════════════════════════════════════════════
    // EXISTING: SHADES
    // Require explicit action words to avoid "what about the shades" -> Unknown
    // ═══════════════════════════════════════════════════════════════════════
    else if (lowered.contains("shade") || lowered.contains("blind") || lowered.contains("curtain")) &&
            (lowered.contains("open") || lowered.contains("close") || lowered.contains("up") ||
             lowered.contains("down") || lowered.contains("raise") || lowered.contains("lower")) {
        let action = if lowered.contains("open") || lowered.contains("up") || lowered.contains("raise") {
            "open"
        } else {
            "close"
        };
        entities.rooms = extract_rooms(&lowered);
        CommandIntent::Shades(action.to_string())
    }

    // ═══════════════════════════════════════════════════════════════════════
    // EXISTING: TV MOUNT
    // Require explicit action words to avoid "what's on tv" -> Unknown
    // ═══════════════════════════════════════════════════════════════════════
    else if (lowered.contains("tv") || lowered.contains("television")) &&
            (lowered.contains("up") || lowered.contains("down") || lowered.contains("raise") ||
             lowered.contains("lower") || lowered.contains("hide") || lowered.contains("show")) {
        let action = if lowered.contains("up") || lowered.contains("raise") || lowered.contains("hide") {
            "raise"
        } else {
            "lower"
        };
        CommandIntent::TV(action.to_string())
    }

    // ═══════════════════════════════════════════════════════════════════════
    // STOP - Fallback for "stop" when not handled by Tesla/Music above
    // Placed here to avoid collision with "stop charging the car", "stop the music"
    // ═══════════════════════════════════════════════════════════════════════
    else if lowered.contains("stop") {
        CommandIntent::Cancel
    }

    // ═══════════════════════════════════════════════════════════════════════
    // FALLBACK
    // ═══════════════════════════════════════════════════════════════════════
    else {
        CommandIntent::Unknown
    };

    VoiceCommand {
        raw_text: text.to_string(),
        intent,
        entities,
    }
}

/// Extract a numeric level from text
///
/// Handles both numeric digits ("50", "75") and word-form numbers
/// ("fifty", "seventy", "twenty five"). Returns `None` if no valid number is found.
///
/// # Supported Formats
///
/// - Digit form: "50", "100", "0", "-50"
/// - Single digits: "one" through "nine"
/// - Teens: "ten" through "nineteen"
/// - Word form (tens): "twenty", "thirty", ..., "ninety"
/// - Compound numbers: "twenty five" => 25, "thirty two" => 32
/// - Negative: "minus fifty" => -50, "negative twenty" => -20
///
/// # Arguments
///
/// * `text` - Lowercase text to search for numbers
///
/// # Returns
///
/// `Some(level)` if a valid number is found, `None` otherwise.
/// Note: For bed temperature, range is -100 to +100, so we allow negatives.
fn extract_number(text: &str) -> Option<i32> {
    // Check for negative prefix
    let is_negative = text.contains("minus") || text.contains("negative");

    // Simple number extraction from digit form (including negative)
    for word in text.split_whitespace() {
        if let Ok(n) = word.parse::<i32>() {
            // Allow -100 to 100 range for bed temperature
            if (-100..=100).contains(&n) {
                return Some(n);
            }
        }
    }

    // Single digit words - ordered by word length (longer first) to avoid "nine" in "ninety"
    let ones = [
        ("seven", 7),
        ("three", 3),
        ("eight", 8),
        ("four", 4),
        ("five", 5),
        ("nine", 9),
        ("zero", 0),
        ("one", 1),
        ("two", 2),
        ("six", 6),
    ];

    // Teen words - check these before tens to avoid false matches
    let teens = [
        ("seventeen", 17),
        ("thirteen", 13),
        ("fourteen", 14),
        ("nineteen", 19),
        ("fifteen", 15),
        ("sixteen", 16),
        ("eighteen", 18),
        ("eleven", 11),
        ("twelve", 12),
        ("ten", 10),
    ];

    // Tens words
    let tens = [
        ("seventy", 70),
        ("thirty", 30),
        ("eighty", 80),
        ("ninety", 90),
        ("twenty", 20),
        ("forty", 40),
        ("fifty", 50),
        ("sixty", 60),
    ];

    // Check for teens first (must come before tens check since "eighteen" contains "eight")
    // and before single digits since "thirteen" contains "three"
    for (teen_word, teen_val) in &teens {
        if text.contains(teen_word) {
            return Some(if is_negative { -*teen_val } else { *teen_val });
        }
    }

    // Check for compound numbers (e.g., "twenty five" = 25)
    for (tens_word, tens_val) in &tens {
        if let Some(tens_pos) = text.find(tens_word) {
            let mut result = *tens_val;

            // Check for a ones digit following the tens word
            let after_tens = &text[tens_pos + tens_word.len()..];
            for (ones_word, ones_val) in &ones {
                if *ones_val > 0 && after_tens.contains(ones_word) {
                    result += ones_val;
                    break;
                }
            }

            return Some(if is_negative { -result } else { result });
        }
    }

    // Check for single digits (only if no tens/teens found)
    for (ones_word, ones_val) in &ones {
        if text.contains(ones_word) {
            return Some(if is_negative { -*ones_val } else { *ones_val });
        }
    }

    // Handle "hundred" for 100
    if text.contains("hundred") {
        return Some(if is_negative { -100 } else { 100 });
    }

    None
}

/// Room names recognized by the voice command parser
/// Ordered by length (longest first) to ensure proper matching
const KNOWN_ROOMS: &[&str] = &[
    "primary bedroom",
    "living room",
    "dining room",
    "game room",
    "laundry room",
    "family room",
    "master bedroom",
    "living",
    "kitchen",
    "dining",
    "bedroom",
    "primary",
    "office",
    "bathroom",
    "garage",
    "patio",
    "deck",
    "loft",
    "laundry",
    "master",
    "guest",
];

/// Extract room names mentioned in text
///
/// Searches for known room names in the text and returns them as a list.
/// Multiple rooms can be mentioned in a single command.
///
/// # Arguments
///
/// * `text` - Lowercase text to search for room names
///
/// # Returns
///
/// `Some(Vec<String>)` with detected rooms, or `None` if no rooms found.
///
/// # Note
///
/// KNOWN_ROOMS is ordered longest-first, so "living room" matches before "living".
/// Once a longer room name is matched, we skip shorter variants that are substrings.
///
/// # Example
///
/// ```rust,ignore
/// let rooms = extract_rooms("turn off living room and office lights");
/// assert_eq!(rooms, Some(vec!["living room".to_string(), "office".to_string()]));
/// ```
fn extract_rooms(text: &str) -> Option<Vec<String>> {
    let mut rooms = Vec::new();
    let mut matched_positions: Vec<(usize, usize)> = Vec::new();

    // KNOWN_ROOMS is sorted longest-first, so we match longer names before shorter ones
    for room in KNOWN_ROOMS {
        if let Some(start) = text.find(room) {
            let end = start + room.len();

            // Check if this position overlaps with an already-matched longer room name
            let overlaps = matched_positions.iter().any(|(s, e)| {
                // Overlap if ranges intersect
                start < *e && end > *s
            });

            if !overlaps {
                rooms.push((*room).to_string());
                matched_positions.push((start, end));
            }
        }
    }

    if rooms.is_empty() {
        None
    } else {
        Some(rooms)
    }
}

/// Extract the message content from an announcement command
///
/// Removes command trigger words ("announce", "say", "tell") and
/// cleans up the remaining text for broadcast.
/// Preserves original capitalization from the raw text.
///
/// # Arguments
///
/// * `text` - The full command text (preserves capitalization)
///
/// # Returns
///
/// The extracted message to announce, with leading/trailing quotes removed.
///
/// # Example
///
/// ```rust,ignore
/// let msg = extract_announcement("Announce Dinner Is Ready");
/// assert_eq!(msg, "Dinner Is Ready");
///
/// let msg = extract_announcement("say \"Hello Everyone\"");
/// assert_eq!(msg, "Hello Everyone");
/// ```
fn extract_announcement(text: &str) -> String {
    // Remove command trigger words case-insensitively while preserving original case
    let lowered = text.to_lowercase();

    // Find and remove trigger words by position
    let mut result = text.to_string();

    // Remove "tell everyone" first (longer phrase)
    if let Some(pos) = lowered.find("tell everyone") {
        result = format!("{}{}", &result[..pos], &result[pos + 13..]);
    }
    // Remove "announce"
    else if let Some(pos) = lowered.find("announce") {
        result = format!("{}{}", &result[..pos], &result[pos + 8..]);
    }
    // Remove "say" (but be careful with position)
    else if let Some(pos) = lowered.find("say") {
        result = format!("{}{}", &result[..pos], &result[pos + 3..]);
    }
    // Remove "tell"
    else if let Some(pos) = lowered.find("tell") {
        result = format!("{}{}", &result[..pos], &result[pos + 4..]);
    }

    // Trim whitespace and quotes
    result
        .trim()
        .trim_matches(|c| c == '"' || c == '\'')
        .to_string()
}

/// Known device names for Find My
const KNOWN_DEVICES: &[&str] = &[
    "iphone", "phone", "airpods", "watch", "ipad", "macbook", "laptop", "keys", "wallet", "airtag",
];

/// Extract device name from "find my X" command
fn extract_device_name(text: &str) -> String {
    for device in KNOWN_DEVICES {
        if text.contains(device) {
            return (*device).to_string();
        }
    }
    // Default to phone if no device specified
    "phone".to_string()
}

/// Known playlist names
const KNOWN_PLAYLISTS: &[&str] = &[
    "focus",
    "chill",
    "workout",
    "morning",
    "dinner",
    "party",
    "jazz",
    "classical",
    "rock",
    "pop",
    "sleep",
    "work",
];

/// Extract playlist name from music command
fn extract_playlist_name(text: &str) -> Option<String> {
    for playlist in KNOWN_PLAYLISTS {
        if text.contains(playlist) {
            return Some((*playlist).to_string());
        }
    }
    None
}

/*
 * 鏡
 * Voice is sense. Command is action.
 */
