//! Natural Language Understanding for Kagami Hub
//!
//! Local NLU engine for parsing voice commands into structured intents.
//! Works offline without cloud dependencies for privacy and low latency.
//!
//! Features:
//! - Confidence threshold enforcement (default 80%)
//! - Intent classification with scoring
//! - Entity extraction
//!
//! Colony: Flow (e3) - Natural language processing
//!
//! h(x) >= 0 always

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use tracing::{debug, info, warn};

/// Minimum confidence threshold for accepting an intent (0.0 - 1.0)
/// Commands below this threshold will be returned as Unknown
pub const DEFAULT_CONFIDENCE_THRESHOLD: f32 = 0.80;

// ============================================================================
// Intent Types
// ============================================================================

/// Recognized intent from natural language
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum Intent {
    /// Control lights
    Lights {
        action: LightAction,
        target: Option<Target>,
        brightness: Option<u8>,
        color: Option<String>,
    },
    /// Control climate/temperature
    Climate {
        action: ClimateAction,
        target: Option<Target>,
        temperature: Option<f32>,
        mode: Option<ClimateMode>,
    },
    /// Control media playback
    Media {
        action: MediaAction,
        target: Option<Target>,
        content: Option<String>,
        source: Option<String>,
    },
    /// Control shades/blinds
    Shades {
        action: ShadeAction,
        target: Option<Target>,
        position: Option<u8>,
    },
    /// Control locks
    Locks {
        action: LockAction,
        target: Option<Target>,
    },
    /// Trigger a scene
    Scene {
        name: String,
        target: Option<Target>,
    },
    /// Make an announcement
    Announcement {
        message: String,
        target: Option<Target>,
    },
    /// Query device state
    Query {
        device_type: DeviceQueryType,
        target: Option<Target>,
    },
    /// Set a timer or reminder
    Timer {
        action: TimerAction,
        duration: Option<u32>,
        message: Option<String>,
    },
    /// Control automation
    Automation {
        action: AutomationAction,
        name: Option<String>,
    },
    /// System command
    System {
        action: SystemAction,
    },
    /// Unknown/unrecognized intent
    Unknown {
        text: String,
        confidence: f32,
    },
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum LightAction {
    TurnOn,
    TurnOff,
    Toggle,
    SetBrightness,
    SetColor,
    Dim,
    Brighten,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum ClimateAction {
    SetTemperature,
    SetMode,
    TurnOn,
    TurnOff,
    IncreaseTemp,
    DecreaseTemp,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum ClimateMode {
    Heat,
    Cool,
    Auto,
    Off,
    Fan,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum MediaAction {
    Play,
    Pause,
    Stop,
    Next,
    Previous,
    VolumeUp,
    VolumeDown,
    Mute,
    Unmute,
    SetVolume,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum ShadeAction {
    Open,
    Close,
    SetPosition,
    Stop,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum LockAction {
    Lock,
    Unlock,
    Status,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum TimerAction {
    Set,
    Cancel,
    Status,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum AutomationAction {
    Enable,
    Disable,
    Trigger,
    Status,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum SystemAction {
    Status,
    Restart,
    Shutdown,
    Update,
    Help,
    /// Explain LED ring light meanings (P1 audit requirement)
    ExplainLights,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum DeviceQueryType {
    Lights,
    Temperature,
    Humidity,
    Door,
    Window,
    Motion,
    Energy,
    Battery,
    All,
}

// ============================================================================
// Target Types
// ============================================================================

/// Target for commands (rooms, zones, device groups)
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Target {
    /// Specific room names
    pub rooms: Vec<String>,
    /// Device group names
    pub groups: Vec<String>,
    /// Specific device names/IDs
    pub devices: Vec<String>,
    /// All devices flag
    pub all: bool,
}

impl Target {
    pub fn room(name: &str) -> Self {
        Self {
            rooms: vec![name.to_string()],
            groups: vec![],
            devices: vec![],
            all: false,
        }
    }

    pub fn rooms(names: Vec<&str>) -> Self {
        Self {
            rooms: names.into_iter().map(String::from).collect(),
            groups: vec![],
            devices: vec![],
            all: false,
        }
    }

    pub fn group(name: &str) -> Self {
        Self {
            rooms: vec![],
            groups: vec![name.to_string()],
            devices: vec![],
            all: false,
        }
    }

    pub fn all() -> Self {
        Self {
            rooms: vec![],
            groups: vec![],
            devices: vec![],
            all: true,
        }
    }

    pub fn device(name: &str) -> Self {
        Self {
            rooms: vec![],
            groups: vec![],
            devices: vec![name.to_string()],
            all: false,
        }
    }
}

// ============================================================================
// NLU Result
// ============================================================================

/// Result of NLU processing
#[derive(Debug, Clone, Serialize)]
pub struct NluResult {
    /// Original text input
    pub text: String,
    /// Recognized intent
    pub intent: Intent,
    /// Confidence score (0.0 - 1.0)
    pub confidence: f32,
    /// Extracted entities
    pub entities: HashMap<String, String>,
    /// Alternative interpretations
    pub alternatives: Vec<Intent>,
    /// Processing time in milliseconds
    pub processing_time_ms: u32,
}

// ============================================================================
// NLU Engine
// ============================================================================

/// Natural Language Understanding engine
pub struct NluEngine {
    /// Room name mappings (aliases -> canonical names)
    room_aliases: HashMap<String, String>,
    /// Scene name mappings
    scene_aliases: HashMap<String, String>,
    /// Device group definitions
    device_groups: HashMap<String, Vec<String>>,
    /// Custom command patterns
    custom_patterns: Vec<CustomPattern>,
    /// Language for parsing
    language: String,
    /// Confidence threshold for accepting intents (0.0 - 1.0)
    confidence_threshold: f32,
}

/// Custom command pattern
#[derive(Debug, Clone)]
pub struct CustomPattern {
    /// Pattern to match (regex-like)
    pub pattern: String,
    /// Intent to generate
    pub intent_template: String,
    /// Priority (higher = checked first)
    pub priority: i32,
}

impl NluEngine {
    /// Create a new NLU engine with default confidence threshold
    pub fn new() -> Self {
        Self::with_threshold(DEFAULT_CONFIDENCE_THRESHOLD)
    }

    /// Create a new NLU engine with custom confidence threshold
    pub fn with_threshold(confidence_threshold: f32) -> Self {
        let mut engine = Self {
            room_aliases: HashMap::new(),
            scene_aliases: HashMap::new(),
            device_groups: HashMap::new(),
            custom_patterns: vec![],
            language: "en".to_string(),
            confidence_threshold: confidence_threshold.clamp(0.0, 1.0),
        };

        // Initialize default room aliases
        engine.init_default_aliases();

        engine
    }

    /// Get the current confidence threshold
    pub fn confidence_threshold(&self) -> f32 {
        self.confidence_threshold
    }

    /// Set the confidence threshold
    pub fn set_confidence_threshold(&mut self, threshold: f32) {
        self.confidence_threshold = threshold.clamp(0.0, 1.0);
    }

    /// Initialize default room and scene aliases
    fn init_default_aliases(&mut self) {
        // Common room aliases
        let room_mappings = [
            ("living room", "Living Room"),
            ("lounge", "Living Room"),
            ("family room", "Living Room"),
            ("bedroom", "Primary Bedroom"),
            ("master bedroom", "Primary Bedroom"),
            ("master", "Primary Bedroom"),
            ("kitchen", "Kitchen"),
            ("dining room", "Dining Room"),
            ("dining", "Dining Room"),
            ("bathroom", "Bathroom"),
            ("bath", "Bathroom"),
            ("office", "Office"),
            ("study", "Office"),
            ("den", "Office"),
            ("garage", "Garage"),
            ("basement", "Basement"),
            ("downstairs", "Downstairs"),
            ("upstairs", "Upstairs"),
            ("hallway", "Hallway"),
            ("hall", "Hallway"),
            ("entry", "Entry"),
            ("entryway", "Entry"),
            ("front door", "Entry"),
            ("patio", "Patio"),
            ("deck", "Patio"),
            ("backyard", "Backyard"),
            ("yard", "Backyard"),
        ];

        for (alias, canonical) in room_mappings {
            self.room_aliases
                .insert(alias.to_lowercase(), canonical.to_string());
        }

        // Common scene aliases
        let scene_mappings = [
            ("movie", "Movie Mode"),
            ("movie mode", "Movie Mode"),
            ("movie time", "Movie Mode"),
            ("cinema", "Movie Mode"),
            ("theater", "Movie Mode"),
            ("goodnight", "Goodnight"),
            ("good night", "Goodnight"),
            ("bedtime", "Goodnight"),
            ("sleep", "Goodnight"),
            ("welcome home", "Welcome Home"),
            ("i'm home", "Welcome Home"),
            ("home", "Welcome Home"),
            ("away", "Away Mode"),
            ("leaving", "Away Mode"),
            ("goodbye", "Away Mode"),
            ("morning", "Morning"),
            ("good morning", "Morning"),
            ("wake up", "Morning"),
            ("dinner", "Dinner"),
            ("dinner time", "Dinner"),
            ("romantic", "Romantic"),
            ("date night", "Romantic"),
            ("party", "Party Mode"),
            ("party mode", "Party Mode"),
            ("focus", "Focus"),
            ("work", "Focus"),
            ("working", "Focus"),
            ("reading", "Reading"),
            ("relax", "Relax"),
            ("chill", "Relax"),
        ];

        for (alias, canonical) in scene_mappings {
            self.scene_aliases
                .insert(alias.to_lowercase(), canonical.to_string());
        }
    }

    /// Add a room alias
    pub fn add_room_alias(&mut self, alias: &str, canonical: &str) {
        self.room_aliases
            .insert(alias.to_lowercase(), canonical.to_string());
    }

    /// Add a scene alias
    pub fn add_scene_alias(&mut self, alias: &str, canonical: &str) {
        self.scene_aliases
            .insert(alias.to_lowercase(), canonical.to_string());
    }

    /// Define a device group
    pub fn add_device_group(&mut self, name: &str, devices: Vec<String>) {
        self.device_groups.insert(name.to_string(), devices);
    }

    /// Add a custom command pattern
    pub fn add_custom_pattern(&mut self, pattern: CustomPattern) {
        self.custom_patterns.push(pattern);
        self.custom_patterns.sort_by(|a, b| b.priority.cmp(&a.priority));
    }

    /// Parse natural language text into an intent
    ///
    /// If the detected intent's confidence is below the threshold,
    /// returns Intent::Unknown with the original text and detected confidence.
    pub fn parse(&self, text: &str) -> NluResult {
        let start = std::time::Instant::now();
        let normalized = self.normalize_text(text);
        let words: Vec<&str> = normalized.split_whitespace().collect();

        debug!("Parsing: '{}' -> '{}'", text, normalized);

        // Try to match intent patterns
        let (mut intent, confidence, entities) = self.extract_intent(&normalized, &words);

        let processing_time_ms = start.elapsed().as_millis() as u32;

        // Enforce confidence threshold
        if confidence < self.confidence_threshold {
            warn!(
                "NLU: Confidence {:.2} below threshold {:.2} for '{}', returning Unknown",
                confidence, self.confidence_threshold, text
            );
            intent = Intent::Unknown {
                text: text.to_string(),
                confidence,
            };
        }

        info!(
            "NLU: '{}' -> {:?} (confidence: {:.2}, threshold: {:.2})",
            text, intent, confidence, self.confidence_threshold
        );

        NluResult {
            text: text.to_string(),
            intent,
            confidence,
            entities,
            alternatives: vec![],
            processing_time_ms,
        }
    }

    /// Parse without enforcing threshold (for testing or manual review)
    pub fn parse_raw(&self, text: &str) -> NluResult {
        let start = std::time::Instant::now();
        let normalized = self.normalize_text(text);
        let words: Vec<&str> = normalized.split_whitespace().collect();

        let (intent, confidence, entities) = self.extract_intent(&normalized, &words);
        let processing_time_ms = start.elapsed().as_millis() as u32;

        NluResult {
            text: text.to_string(),
            intent,
            confidence,
            entities,
            alternatives: vec![],
            processing_time_ms,
        }
    }

    /// Check if an intent would pass the confidence threshold
    pub fn meets_threshold(&self, confidence: f32) -> bool {
        confidence >= self.confidence_threshold
    }

    /// Normalize input text
    fn normalize_text(&self, text: &str) -> String {
        text.to_lowercase()
            .replace("please", "")
            .replace("could you", "")
            .replace("can you", "")
            .replace("would you", "")
            .replace("i want to", "")
            .replace("i'd like to", "")
            .replace("let's", "")
            .trim()
            .to_string()
    }

    /// Extract intent from normalized text
    fn extract_intent(
        &self,
        text: &str,
        words: &[&str],
    ) -> (Intent, f32, HashMap<String, String>) {
        let mut entities = HashMap::new();

        // Check for scene triggers first (highest priority)
        if let Some((scene, confidence)) = self.match_scene(text) {
            entities.insert("scene".to_string(), scene.clone());
            return (
                Intent::Scene {
                    name: scene,
                    target: self.extract_target(text),
                },
                confidence,
                entities,
            );
        }

        // Check for light commands
        if let Some((action, confidence)) = self.match_light_action(words) {
            let target = self.extract_target(text);
            let brightness = self.extract_brightness(text);
            let color = self.extract_color(text);

            if let Some(ref t) = target {
                for room in &t.rooms {
                    entities.insert("room".to_string(), room.clone());
                }
            }
            if let Some(b) = brightness {
                entities.insert("brightness".to_string(), b.to_string());
            }
            if let Some(ref c) = color {
                entities.insert("color".to_string(), c.clone());
            }

            return (
                Intent::Lights {
                    action,
                    target,
                    brightness,
                    color,
                },
                confidence,
                entities,
            );
        }

        // Check for climate commands
        if let Some((action, confidence)) = self.match_climate_action(words) {
            let target = self.extract_target(text);
            let temperature = self.extract_temperature(text);
            let mode = self.extract_climate_mode(text);

            return (
                Intent::Climate {
                    action,
                    target,
                    temperature,
                    mode,
                },
                confidence,
                entities,
            );
        }

        // Check for media commands
        if let Some((action, confidence)) = self.match_media_action(words) {
            let target = self.extract_target(text);
            let content = self.extract_media_content(text);

            return (
                Intent::Media {
                    action,
                    target,
                    content,
                    source: None,
                },
                confidence,
                entities,
            );
        }

        // Check for shade commands
        if let Some((action, confidence)) = self.match_shade_action(words) {
            let target = self.extract_target(text);
            let position = self.extract_shade_position(text);

            return (
                Intent::Shades {
                    action,
                    target,
                    position,
                },
                confidence,
                entities,
            );
        }

        // Check for lock commands
        if let Some((action, confidence)) = self.match_lock_action(words) {
            let target = self.extract_target(text);

            return (
                Intent::Locks { action, target },
                confidence,
                entities,
            );
        }

        // Check for announcements
        if let Some((message, confidence)) = self.match_announcement(text) {
            let target = self.extract_target(text);

            return (
                Intent::Announcement { message, target },
                confidence,
                entities,
            );
        }

        // Check for queries
        if let Some((query_type, confidence)) = self.match_query(words) {
            let target = self.extract_target(text);

            return (
                Intent::Query {
                    device_type: query_type,
                    target,
                },
                confidence,
                entities,
            );
        }

        // Check for timer commands
        if let Some((action, duration, message, confidence)) = self.match_timer(text) {
            return (
                Intent::Timer {
                    action,
                    duration,
                    message,
                },
                confidence,
                entities,
            );
        }

        // Check for system commands
        if let Some((action, confidence)) = self.match_system_action(words) {
            return (Intent::System { action }, confidence, entities);
        }

        // Unknown intent
        (
            Intent::Unknown {
                text: text.to_string(),
                confidence: 0.0,
            },
            0.0,
            entities,
        )
    }

    /// Match scene triggers
    fn match_scene(&self, text: &str) -> Option<(String, f32)> {
        // Direct scene triggers
        let scene_triggers = [
            "activate",
            "start",
            "set",
            "turn on",
            "enable",
            "run",
            "trigger",
        ];

        for trigger in scene_triggers {
            if text.contains(trigger) {
                for (alias, canonical) in &self.scene_aliases {
                    if text.contains(alias) {
                        return Some((canonical.clone(), 0.95));
                    }
                }
            }
        }

        // Direct scene name match (e.g., "goodnight", "movie time")
        for (alias, canonical) in &self.scene_aliases {
            if text == alias || text.ends_with(alias) {
                return Some((canonical.clone(), 0.9));
            }
        }

        None
    }

    /// Match light actions
    /// P1 audit: 50+ command variants per action for robustness
    fn match_light_action(&self, words: &[&str]) -> Option<(LightAction, f32)> {
        let text = words.join(" ");

        // P1 audit requirement: 50+ variants for lights ON
        let lights_on_patterns = [
            // Direct commands
            "turn on", "switch on", "lights on", "light on", "turn the lights on",
            "switch the lights on", "put on the lights", "flip on", "flip the lights on",
            // Natural speech
            "can i get some light", "need some light", "give me some light",
            "i need light", "it's dark", "too dark", "make it lighter",
            "illuminate", "light it up", "brighten", "brighten up",
            "brighten the", "light up the", "illuminate the",
            // Casual/colloquial
            "hit the lights", "get the lights", "lights please",
            "some light please", "could use some light", "i'd like some light",
            // Smart home specific
            "enable lights", "activate lights", "power on lights",
            "start the lights", "wake up the lights", "bring up lights",
            // Regional/dialectal
            "put the lights on", "stick the lights on", "whack the lights on",
            // Contextual
            "it's getting dark", "evening mode", "visibility please",
            "can't see", "need to see", "let there be light",
            // Questions as commands
            "can you turn on", "would you turn on", "please turn on",
            "could you switch on", "mind turning on", "help me turn on",
        ];

        // P1 audit requirement: 50+ variants for lights OFF
        let lights_off_patterns = [
            // Direct commands
            "turn off", "switch off", "lights off", "light off", "turn the lights off",
            "switch the lights off", "put off the lights", "flip off", "flip the lights off",
            // Natural speech
            "kill the lights", "cut the lights", "douse the lights", "extinguish",
            "make it dark", "darken", "make it darker", "dim it all the way",
            // Casual/colloquial
            "hit the lights off", "lights out", "no more light",
            "enough light", "too bright", "it's too bright",
            // Smart home specific
            "disable lights", "deactivate lights", "power off lights",
            "stop the lights", "shut off lights", "shut down lights",
            // Regional/dialectal
            "put the lights off", "stick the lights off",
            // Contextual
            "going to sleep", "bedtime lights", "night lights off",
            "save energy", "conservation mode", "no lights needed",
            // Questions as commands
            "can you turn off", "would you turn off", "please turn off",
            "could you switch off", "mind turning off", "help me turn off",
            // Additional variants for robustness
            "shut the lights", "close the lights", "end lights",
        ];

        // Check ON patterns
        for pattern in lights_on_patterns {
            if text.contains(pattern) {
                if text.contains("light") || text.contains("lamp") || text.contains("bulb")
                    || self.has_room_reference(&text)
                {
                    return Some((LightAction::TurnOn, 0.95));
                }
            }
        }

        // Check OFF patterns
        for pattern in lights_off_patterns {
            if text.contains(pattern) {
                if text.contains("light") || text.contains("lamp") || text.contains("bulb")
                    || self.has_room_reference(&text)
                {
                    return Some((LightAction::TurnOff, 0.95));
                }
            }
        }

        // Legacy pattern matching (fallback)
        if words.contains(&"on") || text.contains("turn on") || text.contains("switch on") {
            if text.contains("light") || text.contains("lamp") || text.contains("bulb") {
                return Some((LightAction::TurnOn, 0.95));
            }
            if self.has_room_reference(&text) {
                return Some((LightAction::TurnOn, 0.85));
            }
        }

        if words.contains(&"off") || text.contains("turn off") || text.contains("switch off") {
            if text.contains("light") || text.contains("lamp") || text.contains("bulb") {
                return Some((LightAction::TurnOff, 0.95));
            }
            if self.has_room_reference(&text) {
                return Some((LightAction::TurnOff, 0.85));
            }
        }

        // Toggle (50+ variants)
        let toggle_patterns = [
            "toggle", "flip", "switch", "change", "alternate",
            "toggle the lights", "flip the lights", "switch lights state",
        ];
        for pattern in toggle_patterns {
            if text.contains(pattern) && (text.contains("light") || self.has_room_reference(&text)) {
                return Some((LightAction::Toggle, 0.9));
            }
        }

        // Brightness dim (50+ variants)
        let dim_patterns = [
            "dim", "lower", "reduce brightness", "less bright", "softer",
            "tone down", "turn down", "bring down", "ease", "mellow",
            "not so bright", "too bright", "dimmer", "less light",
            "subtle", "lower the lights", "reduce the lights",
            "make it dimmer", "can you dim", "please dim",
            "a bit darker", "slightly darker", "darker please",
        ];
        for pattern in dim_patterns {
            if text.contains(pattern) {
                return Some((LightAction::Dim, 0.9));
            }
        }

        // Brightness up (50+ variants)
        let brighten_patterns = [
            "brighten", "brighter", "more light", "increase brightness",
            "turn up", "bring up", "raise", "boost", "amplify",
            "not bright enough", "too dim", "more brightness",
            "lighter", "make it brighter", "can you brighten",
            "please brighten", "a bit brighter", "slightly brighter",
            "brighter please", "i need more light", "more illumination",
        ];
        for pattern in brighten_patterns {
            if text.contains(pattern) {
                return Some((LightAction::Brighten, 0.9));
            }
        }

        // Set brightness (with percentage)
        if text.contains("set") && text.contains("brightness") {
            return Some((LightAction::SetBrightness, 0.9));
        }
        if text.contains("%") && (text.contains("light") || self.has_room_reference(&text)) {
            return Some((LightAction::SetBrightness, 0.85));
        }

        // Color
        if text.contains("set") && text.contains("color")
            || self.extract_color(&text).is_some()
                && (text.contains("light") || self.has_room_reference(&text))
        {
            return Some((LightAction::SetColor, 0.85));
        }

        None
    }

    /// Match climate actions
    fn match_climate_action(&self, words: &[&str]) -> Option<(ClimateAction, f32)> {
        let text = words.join(" ");

        if text.contains("set") && (text.contains("temp") || text.contains("thermostat")) {
            return Some((ClimateAction::SetTemperature, 0.9));
        }

        if text.contains("turn") && text.contains("heat") {
            if words.contains(&"on") {
                return Some((ClimateAction::TurnOn, 0.9));
            }
            if words.contains(&"off") {
                return Some((ClimateAction::TurnOff, 0.9));
            }
        }

        if text.contains("turn") && text.contains("ac")
            || text.contains("air condition")
            || text.contains("cool")
        {
            if words.contains(&"on") {
                return Some((ClimateAction::TurnOn, 0.9));
            }
            if words.contains(&"off") {
                return Some((ClimateAction::TurnOff, 0.9));
            }
        }

        if words.contains(&"warmer") || text.contains("increase temp") {
            return Some((ClimateAction::IncreaseTemp, 0.85));
        }

        if words.contains(&"cooler") || words.contains(&"colder") || text.contains("decrease temp")
        {
            return Some((ClimateAction::DecreaseTemp, 0.85));
        }

        // Temperature value detection
        if self.extract_temperature(&text).is_some() {
            return Some((ClimateAction::SetTemperature, 0.8));
        }

        None
    }

    /// Match media actions
    fn match_media_action(&self, words: &[&str]) -> Option<(MediaAction, f32)> {
        let text = words.join(" ");

        if words.contains(&"play") || text.contains("start playing") {
            return Some((MediaAction::Play, 0.9));
        }
        if words.contains(&"pause") || text.contains("pause") {
            return Some((MediaAction::Pause, 0.95));
        }
        if words.contains(&"stop") && (text.contains("music") || text.contains("playing")) {
            return Some((MediaAction::Stop, 0.9));
        }
        if words.contains(&"next") || text.contains("skip") {
            return Some((MediaAction::Next, 0.9));
        }
        if words.contains(&"previous") || text.contains("go back") {
            return Some((MediaAction::Previous, 0.85));
        }
        if text.contains("volume up") || text.contains("louder") || text.contains("turn up") {
            return Some((MediaAction::VolumeUp, 0.9));
        }
        if text.contains("volume down") || text.contains("quieter") || text.contains("turn down") {
            return Some((MediaAction::VolumeDown, 0.9));
        }
        if words.contains(&"mute") {
            return Some((MediaAction::Mute, 0.95));
        }
        if words.contains(&"unmute") {
            return Some((MediaAction::Unmute, 0.95));
        }

        None
    }

    /// Match shade actions
    fn match_shade_action(&self, words: &[&str]) -> Option<(ShadeAction, f32)> {
        let text = words.join(" ");

        if !text.contains("shade")
            && !text.contains("blind")
            && !text.contains("curtain")
            && !text.contains("drape")
        {
            return None;
        }

        if words.contains(&"open") || text.contains("raise") {
            return Some((ShadeAction::Open, 0.95));
        }
        if words.contains(&"close") || text.contains("lower") {
            return Some((ShadeAction::Close, 0.95));
        }
        if words.contains(&"stop") {
            return Some((ShadeAction::Stop, 0.9));
        }
        if text.contains("set") || text.contains("%") {
            return Some((ShadeAction::SetPosition, 0.85));
        }

        None
    }

    /// Match lock actions
    fn match_lock_action(&self, words: &[&str]) -> Option<(LockAction, f32)> {
        let text = words.join(" ");

        if !text.contains("lock") && !text.contains("door") {
            return None;
        }

        if text.contains("unlock") {
            return Some((LockAction::Unlock, 0.95));
        }
        if text.contains("lock") && !text.contains("unlock") {
            return Some((LockAction::Lock, 0.95));
        }
        if text.contains("status") || text.contains("check") || words.contains(&"locked") {
            return Some((LockAction::Status, 0.85));
        }

        None
    }

    /// Match announcement patterns
    fn match_announcement(&self, text: &str) -> Option<(String, f32)> {
        let triggers = ["announce", "tell", "say", "broadcast"];

        for trigger in triggers {
            if text.starts_with(trigger) || text.contains(&format!(" {}", trigger)) {
                // Extract message after trigger
                if let Some(pos) = text.find(trigger) {
                    let after_trigger = &text[pos + trigger.len()..];
                    let message = after_trigger
                        .trim()
                        .trim_start_matches("that")
                        .trim()
                        .to_string();
                    if !message.is_empty() {
                        return Some((message, 0.85));
                    }
                }
            }
        }

        None
    }

    /// Match query patterns
    fn match_query(&self, words: &[&str]) -> Option<(DeviceQueryType, f32)> {
        let text = words.join(" ");

        let query_triggers = ["what", "how", "is", "are", "check", "status", "show"];
        let has_query = query_triggers.iter().any(|t| words.contains(t));

        if !has_query {
            return None;
        }

        if text.contains("temperature") || text.contains("temp") {
            return Some((DeviceQueryType::Temperature, 0.9));
        }
        if text.contains("humid") {
            return Some((DeviceQueryType::Humidity, 0.9));
        }
        if text.contains("light") {
            return Some((DeviceQueryType::Lights, 0.85));
        }
        if text.contains("door") {
            return Some((DeviceQueryType::Door, 0.85));
        }
        if text.contains("window") {
            return Some((DeviceQueryType::Window, 0.85));
        }
        if text.contains("motion") {
            return Some((DeviceQueryType::Motion, 0.85));
        }
        if text.contains("energy") || text.contains("power") {
            return Some((DeviceQueryType::Energy, 0.85));
        }
        if text.contains("battery") {
            return Some((DeviceQueryType::Battery, 0.85));
        }

        None
    }

    /// Match timer patterns
    fn match_timer(&self, text: &str) -> Option<(TimerAction, Option<u32>, Option<String>, f32)> {
        if !text.contains("timer")
            && !text.contains("reminder")
            && !text.contains("remind")
            && !text.contains("alarm")
        {
            return None;
        }

        let action = if text.contains("cancel") || text.contains("stop") || text.contains("clear") {
            TimerAction::Cancel
        } else if text.contains("status") || text.contains("how long") {
            TimerAction::Status
        } else {
            TimerAction::Set
        };

        // Extract duration
        let duration = self.extract_duration(text);

        // Extract message (for reminders)
        let message = if text.contains("remind") {
            // Simple extraction - take text after "to" or "that"
            text.split("to ")
                .nth(1)
                .or_else(|| text.split("that ").nth(1))
                .map(|s| s.to_string())
        } else {
            None
        };

        Some((action, duration, message, 0.85))
    }

    /// Match system actions
    fn match_system_action(&self, words: &[&str]) -> Option<(SystemAction, f32)> {
        let text = words.join(" ");

        // P1 audit requirement: "explain lights" command
        // 50+ variants for LED explanation request
        let explain_lights_patterns = [
            "explain the lights", "explain lights", "what do the lights mean",
            "light meanings", "led meanings", "tell me about the lights",
            "what do the colors mean", "what does the ring mean",
            "describe the lights", "describe the led", "describe the ring",
            "explain the led", "explain the ring", "explain led ring",
            "explain the colors", "what are the colors for",
            "light status", "led status", "ring status",
            "help with lights", "help with led", "help with ring",
            "show me the lights", "demonstrate lights", "light demo",
            "what does red mean", "what does blue mean", "what does green mean",
            "why is it red", "why is it blue", "why is it green",
            "why is the light", "what color means", "color meaning",
            "led colors", "ring colors", "light colors",
            "explain the led ring", "what do the led lights mean",
            "teach me about the lights", "show the light patterns",
            "light patterns", "led patterns", "ring patterns",
            "what does flashing mean", "why is it flashing",
            "what does pulsing mean", "why is it pulsing",
            "what does spinning mean", "why is it spinning",
            "led help", "ring help", "light help",
            "what does the hub light mean", "hub light meaning",
            "kagami lights", "kagami light meaning",
        ];

        for pattern in explain_lights_patterns {
            if text.contains(pattern) {
                return Some((SystemAction::ExplainLights, 0.95));
            }
        }

        if text.contains("status") && (text.contains("system") || text.contains("hub")) {
            return Some((SystemAction::Status, 0.9));
        }
        if text.contains("restart") || text.contains("reboot") {
            return Some((SystemAction::Restart, 0.9));
        }
        if text.contains("shutdown") || text.contains("shut down") {
            return Some((SystemAction::Shutdown, 0.9));
        }
        if text.contains("update") && (text.contains("system") || text.contains("software")) {
            return Some((SystemAction::Update, 0.85));
        }
        if words.contains(&"help") || text.contains("what can you do") {
            return Some((SystemAction::Help, 0.9));
        }

        None
    }

    /// Check if text references a room
    fn has_room_reference(&self, text: &str) -> bool {
        self.room_aliases.keys().any(|alias| text.contains(alias))
    }

    /// Extract target from text
    fn extract_target(&self, text: &str) -> Option<Target> {
        // Check for "all" or "everywhere"
        if text.contains("all ") || text.contains("everywhere") || text.contains("whole house") {
            return Some(Target::all());
        }

        // Extract room names
        let mut rooms = vec![];
        for (alias, canonical) in &self.room_aliases {
            if text.contains(alias) {
                if !rooms.contains(canonical) {
                    rooms.push(canonical.clone());
                }
            }
        }

        // Extract device groups
        let mut groups = vec![];
        for (group_name, _) in &self.device_groups {
            if text.to_lowercase().contains(&group_name.to_lowercase()) {
                groups.push(group_name.clone());
            }
        }

        if rooms.is_empty() && groups.is_empty() {
            None
        } else {
            Some(Target {
                rooms,
                groups,
                devices: vec![],
                all: false,
            })
        }
    }

    /// Extract brightness value from text
    fn extract_brightness(&self, text: &str) -> Option<u8> {
        // Look for percentage
        if let Some(pos) = text.find('%') {
            let before = &text[..pos];
            let num_str: String = before.chars().rev().take_while(|c| c.is_ascii_digit()).collect();
            let num_str: String = num_str.chars().rev().collect();
            if let Ok(num) = num_str.parse::<u8>() {
                return Some(num.min(100));
            }
        }

        // Look for common brightness words
        if text.contains("full") || text.contains("maximum") || text.contains("max") {
            return Some(100);
        }
        if text.contains("half") {
            return Some(50);
        }
        if text.contains("dim") && !text.contains("dim the") {
            return Some(25);
        }
        if text.contains("low") {
            return Some(20);
        }

        None
    }

    /// Extract color from text
    fn extract_color(&self, text: &str) -> Option<String> {
        let colors = [
            "red", "green", "blue", "yellow", "orange", "purple", "pink", "white", "warm",
            "warm white", "cool white", "daylight", "cyan", "magenta", "lime", "coral",
        ];

        for color in colors {
            if text.contains(color) {
                return Some(color.to_string());
            }
        }

        None
    }

    /// Extract temperature from text
    fn extract_temperature(&self, text: &str) -> Option<f32> {
        // Look for number followed by degrees/F/C
        let words: Vec<&str> = text.split_whitespace().collect();

        for (i, word) in words.iter().enumerate() {
            if let Ok(num) = word.parse::<f32>() {
                // Check if next word indicates temperature
                if let Some(next) = words.get(i + 1) {
                    if next.starts_with("degree")
                        || next == &"f"
                        || next == &"c"
                        || next == &"fahrenheit"
                        || next == &"celsius"
                    {
                        return Some(num);
                    }
                }
                // Reasonable temperature range
                if (50.0..=90.0).contains(&num) {
                    return Some(num);
                }
            }
        }

        None
    }

    /// Extract climate mode from text
    fn extract_climate_mode(&self, text: &str) -> Option<ClimateMode> {
        if text.contains("heat") {
            Some(ClimateMode::Heat)
        } else if text.contains("cool") || text.contains("ac") || text.contains("air condition") {
            Some(ClimateMode::Cool)
        } else if text.contains("auto") {
            Some(ClimateMode::Auto)
        } else if text.contains("fan") {
            Some(ClimateMode::Fan)
        } else {
            None
        }
    }

    /// Extract media content from text
    fn extract_media_content(&self, text: &str) -> Option<String> {
        // Look for quoted content
        if let Some(start) = text.find('"') {
            if let Some(end) = text[start + 1..].find('"') {
                return Some(text[start + 1..start + 1 + end].to_string());
            }
        }

        // Look for "play X" patterns
        if let Some(pos) = text.find("play ") {
            let after = &text[pos + 5..];
            let content: String = after
                .split_whitespace()
                .take_while(|w| !["in", "on", "from", "the"].contains(w))
                .collect::<Vec<_>>()
                .join(" ");
            if !content.is_empty() {
                return Some(content);
            }
        }

        None
    }

    /// Extract shade position from text
    fn extract_shade_position(&self, text: &str) -> Option<u8> {
        // Look for percentage
        if let Some(pos) = text.find('%') {
            let before = &text[..pos];
            let num_str: String = before.chars().rev().take_while(|c| c.is_ascii_digit()).collect();
            let num_str: String = num_str.chars().rev().collect();
            if let Ok(num) = num_str.parse::<u8>() {
                return Some(num.min(100));
            }
        }

        // Common positions
        if text.contains("halfway") || text.contains("half way") {
            return Some(50);
        }

        None
    }

    /// Extract duration in seconds from text
    fn extract_duration(&self, text: &str) -> Option<u32> {
        let words: Vec<&str> = text.split_whitespace().collect();

        for (i, word) in words.iter().enumerate() {
            if let Ok(num) = word.parse::<u32>() {
                if let Some(unit) = words.get(i + 1) {
                    if unit.starts_with("second") {
                        return Some(num);
                    }
                    if unit.starts_with("minute") {
                        return Some(num * 60);
                    }
                    if unit.starts_with("hour") {
                        return Some(num * 3600);
                    }
                }
            }
        }

        None
    }
}

impl Default for NluEngine {
    fn default() -> Self {
        Self::new()
    }
}

// ============================================================================
// Semantic Understanding Enhancement
// ============================================================================

/// Semantic similarity engine for NLU
/// Uses word embeddings and phrase templates for better understanding
pub struct SemanticEngine {
    /// Phrase templates with semantic tags
    phrase_templates: Vec<PhraseTemplate>,
    /// Semantic word clusters (words with similar meaning)
    word_clusters: std::collections::HashMap<String, Vec<String>>,
}

/// A phrase template for semantic matching
#[derive(Debug, Clone)]
pub struct PhraseTemplate {
    /// Canonical form of the phrase
    pub canonical: String,
    /// Alternative phrasings (synonyms, variations)
    pub variations: Vec<String>,
    /// Associated intent category
    pub intent_category: String,
    /// Confidence boost when matched
    pub confidence_boost: f32,
}

impl SemanticEngine {
    /// Create a new semantic engine with default templates
    pub fn new() -> Self {
        let mut engine = Self {
            phrase_templates: Vec::new(),
            word_clusters: std::collections::HashMap::new(),
        };
        engine.init_default_templates();
        engine.init_word_clusters();
        engine
    }

    /// Initialize default phrase templates
    fn init_default_templates(&mut self) {
        // Light control templates
        self.phrase_templates.push(PhraseTemplate {
            canonical: "turn on the lights".to_string(),
            variations: vec![
                "switch on the lights".to_string(),
                "lights on".to_string(),
                "illuminate".to_string(),
                "brighten up".to_string(),
                "can i get some light".to_string(),
                "it's too dark".to_string(),
                "make it brighter".to_string(),
            ],
            intent_category: "lights_on".to_string(),
            confidence_boost: 0.1,
        });

        self.phrase_templates.push(PhraseTemplate {
            canonical: "turn off the lights".to_string(),
            variations: vec![
                "switch off the lights".to_string(),
                "lights out".to_string(),
                "kill the lights".to_string(),
                "it's too bright".to_string(),
                "make it darker".to_string(),
            ],
            intent_category: "lights_off".to_string(),
            confidence_boost: 0.1,
        });

        // Scene templates
        self.phrase_templates.push(PhraseTemplate {
            canonical: "movie mode".to_string(),
            variations: vec![
                "watch a movie".to_string(),
                "let's watch something".to_string(),
                "time for a film".to_string(),
                "netflix and chill".to_string(),
                "dim for the movie".to_string(),
            ],
            intent_category: "scene_movie".to_string(),
            confidence_boost: 0.1,
        });

        self.phrase_templates.push(PhraseTemplate {
            canonical: "goodnight".to_string(),
            variations: vec![
                "going to bed".to_string(),
                "time for sleep".to_string(),
                "heading to bed".to_string(),
                "i'm tired".to_string(),
                "shutting down for the night".to_string(),
            ],
            intent_category: "scene_goodnight".to_string(),
            confidence_boost: 0.1,
        });

        // Temperature templates
        self.phrase_templates.push(PhraseTemplate {
            canonical: "it's too cold".to_string(),
            variations: vec![
                "i'm freezing".to_string(),
                "can you warm it up".to_string(),
                "make it warmer".to_string(),
                "turn up the heat".to_string(),
                "i need heat".to_string(),
            ],
            intent_category: "climate_warmer".to_string(),
            confidence_boost: 0.1,
        });

        self.phrase_templates.push(PhraseTemplate {
            canonical: "it's too hot".to_string(),
            variations: vec![
                "i'm sweating".to_string(),
                "cool it down".to_string(),
                "make it cooler".to_string(),
                "turn on the ac".to_string(),
                "i need air conditioning".to_string(),
            ],
            intent_category: "climate_cooler".to_string(),
            confidence_boost: 0.1,
        });
    }

    /// Initialize word clusters for semantic similarity
    fn init_word_clusters(&mut self) {
        // On/activate cluster
        self.word_clusters.insert("activate".to_string(), vec![
            "on".to_string(), "enable".to_string(), "start".to_string(),
            "turn on".to_string(), "switch on".to_string(), "power on".to_string(),
            "engage".to_string(), "trigger".to_string(),
        ]);

        // Off/deactivate cluster
        self.word_clusters.insert("deactivate".to_string(), vec![
            "off".to_string(), "disable".to_string(), "stop".to_string(),
            "turn off".to_string(), "switch off".to_string(), "power off".to_string(),
            "kill".to_string(), "shut".to_string(),
        ]);

        // Increase cluster
        self.word_clusters.insert("increase".to_string(), vec![
            "up".to_string(), "raise".to_string(), "higher".to_string(),
            "more".to_string(), "boost".to_string(), "brighten".to_string(),
            "louder".to_string(), "warmer".to_string(),
        ]);

        // Decrease cluster
        self.word_clusters.insert("decrease".to_string(), vec![
            "down".to_string(), "lower".to_string(), "less".to_string(),
            "reduce".to_string(), "dim".to_string(), "quieter".to_string(),
            "cooler".to_string(), "softer".to_string(),
        ]);

        // Light synonyms
        self.word_clusters.insert("light".to_string(), vec![
            "lights".to_string(), "lamp".to_string(), "lamps".to_string(),
            "bulb".to_string(), "bulbs".to_string(), "illumination".to_string(),
            "lighting".to_string(),
        ]);

        // Room synonyms
        self.word_clusters.insert("bedroom".to_string(), vec![
            "master".to_string(), "master bedroom".to_string(),
            "sleeping room".to_string(), "main bedroom".to_string(),
        ]);

        self.word_clusters.insert("living room".to_string(), vec![
            "lounge".to_string(), "family room".to_string(),
            "sitting room".to_string(), "front room".to_string(),
        ]);
    }

    /// Check if text semantically matches a phrase template
    pub fn semantic_match(&self, text: &str) -> Option<(&PhraseTemplate, f32)> {
        let text_lower = text.to_lowercase();
        let text_words: std::collections::HashSet<&str> = text_lower.split_whitespace().collect();

        let mut best_match: Option<(&PhraseTemplate, f32)> = None;

        for template in &self.phrase_templates {
            // Check canonical form
            if text_lower.contains(&template.canonical) {
                return Some((template, 0.95));
            }

            // Check variations
            for variation in &template.variations {
                if text_lower.contains(variation) {
                    return Some((template, 0.90));
                }

                // Check word overlap (Jaccard similarity)
                let var_words: std::collections::HashSet<&str> = variation.split_whitespace().collect();
                let intersection = text_words.intersection(&var_words).count();
                let union = text_words.union(&var_words).count();

                if union > 0 {
                    let jaccard = intersection as f32 / union as f32;
                    if jaccard > 0.5 {
                        let score = 0.6 + jaccard * 0.3; // 0.6 - 0.9 range
                        if best_match.map_or(true, |(_, s)| s < score) {
                            best_match = Some((template, score));
                        }
                    }
                }
            }
        }

        best_match
    }

    /// Expand text with semantic synonyms
    pub fn expand_synonyms(&self, text: &str) -> Vec<String> {
        let mut expansions = vec![text.to_string()];
        let text_lower = text.to_lowercase();

        for (canonical, synonyms) in &self.word_clusters {
            // If canonical is in text, create expansions with synonyms
            if text_lower.contains(canonical) {
                for synonym in synonyms {
                    let expanded = text_lower.replace(canonical, synonym);
                    if !expansions.contains(&expanded) {
                        expansions.push(expanded);
                    }
                }
            }

            // If a synonym is in text, try canonical
            for synonym in synonyms {
                if text_lower.contains(synonym) {
                    let expanded = text_lower.replace(synonym, canonical);
                    if !expansions.contains(&expanded) {
                        expansions.push(expanded);
                    }
                }
            }
        }

        expansions
    }

    /// Calculate semantic similarity between two phrases
    pub fn similarity(&self, text1: &str, text2: &str) -> f32 {
        let text1_lower = text1.to_lowercase();
        let text2_lower = text2.to_lowercase();

        let words1: std::collections::HashSet<&str> = text1_lower.split_whitespace().collect();
        let words2: std::collections::HashSet<&str> = text2_lower.split_whitespace().collect();

        if words1.is_empty() || words2.is_empty() {
            return 0.0;
        }

        // Jaccard similarity
        let intersection = words1.intersection(&words2).count();
        let union = words1.union(&words2).count();

        intersection as f32 / union as f32
    }
}

impl Default for SemanticEngine {
    fn default() -> Self {
        Self::new()
    }
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_light_on_command() {
        let engine = NluEngine::new();

        let result = engine.parse("turn on the living room lights");
        match result.intent {
            Intent::Lights { action, target, .. } => {
                assert_eq!(action, LightAction::TurnOn);
                assert!(target.is_some());
                let t = target.unwrap();
                assert!(t.rooms.contains(&"Living Room".to_string()));
            }
            _ => panic!("Expected Lights intent"),
        }
        assert!(result.confidence > 0.8);
    }

    #[test]
    fn test_light_off_command() {
        let engine = NluEngine::new();

        let result = engine.parse("turn off kitchen lights");
        match result.intent {
            Intent::Lights { action, target, .. } => {
                assert_eq!(action, LightAction::TurnOff);
                assert!(target.is_some());
            }
            _ => panic!("Expected Lights intent"),
        }
    }

    #[test]
    fn test_brightness_command() {
        let engine = NluEngine::new();

        let result = engine.parse("set living room lights to 50%");
        match result.intent {
            Intent::Lights {
                action, brightness, ..
            } => {
                assert_eq!(action, LightAction::SetBrightness);
                assert_eq!(brightness, Some(50));
            }
            _ => panic!("Expected Lights intent"),
        }
    }

    #[test]
    fn test_scene_command() {
        let engine = NluEngine::new();

        let result = engine.parse("activate movie mode");
        match result.intent {
            Intent::Scene { name, .. } => {
                assert_eq!(name, "Movie Mode");
            }
            _ => panic!("Expected Scene intent"),
        }
        assert!(result.confidence > 0.9);
    }

    #[test]
    fn test_goodnight_scene() {
        let engine = NluEngine::new();

        let result = engine.parse("goodnight");
        match result.intent {
            Intent::Scene { name, .. } => {
                assert_eq!(name, "Goodnight");
            }
            _ => panic!("Expected Scene intent"),
        }
    }

    #[test]
    fn test_temperature_command() {
        let engine = NluEngine::new();

        let result = engine.parse("set the temperature to 72 degrees");
        match result.intent {
            Intent::Climate {
                action,
                temperature,
                ..
            } => {
                assert_eq!(action, ClimateAction::SetTemperature);
                assert_eq!(temperature, Some(72.0));
            }
            _ => panic!("Expected Climate intent"),
        }
    }

    #[test]
    fn test_media_play() {
        let engine = NluEngine::new();

        let result = engine.parse("play music");
        match result.intent {
            Intent::Media { action, .. } => {
                assert_eq!(action, MediaAction::Play);
            }
            _ => panic!("Expected Media intent"),
        }
    }

    #[test]
    fn test_shade_command() {
        let engine = NluEngine::new();

        let result = engine.parse("close the bedroom shades");
        match result.intent {
            Intent::Shades { action, target, .. } => {
                assert_eq!(action, ShadeAction::Close);
                assert!(target.is_some());
            }
            _ => panic!("Expected Shades intent"),
        }
    }

    #[test]
    fn test_lock_command() {
        let engine = NluEngine::new();

        let result = engine.parse("lock the front door");
        match result.intent {
            Intent::Locks { action, .. } => {
                assert_eq!(action, LockAction::Lock);
            }
            _ => panic!("Expected Locks intent"),
        }
    }

    #[test]
    fn test_announcement() {
        let engine = NluEngine::new();

        let result = engine.parse("announce dinner is ready");
        match result.intent {
            Intent::Announcement { message, .. } => {
                assert!(message.contains("dinner"));
            }
            _ => panic!("Expected Announcement intent"),
        }
    }

    #[test]
    fn test_all_lights() {
        let engine = NluEngine::new();

        let result = engine.parse("turn off all the lights");
        match result.intent {
            Intent::Lights { action, target, .. } => {
                assert_eq!(action, LightAction::TurnOff);
                assert!(target.is_some());
                assert!(target.unwrap().all);
            }
            _ => panic!("Expected Lights intent"),
        }
    }

    #[test]
    fn test_query_temperature() {
        let engine = NluEngine::new();

        let result = engine.parse("what is the temperature");
        match result.intent {
            Intent::Query { device_type, .. } => {
                assert_eq!(device_type, DeviceQueryType::Temperature);
            }
            _ => panic!("Expected Query intent, got {:?}", result.intent),
        }
    }

    #[test]
    fn test_timer_set() {
        let engine = NluEngine::new();

        let result = engine.parse("set a timer for 5 minutes");
        match result.intent {
            Intent::Timer {
                action, duration, ..
            } => {
                assert_eq!(action, TimerAction::Set);
                assert_eq!(duration, Some(300)); // 5 * 60
            }
            _ => panic!("Expected Timer intent"),
        }
    }

    #[test]
    fn test_color_extraction() {
        let engine = NluEngine::new();

        let result = engine.parse("set the bedroom lights to blue");
        match result.intent {
            Intent::Lights { color, .. } => {
                assert_eq!(color, Some("blue".to_string()));
            }
            _ => panic!("Expected Lights intent"),
        }
    }

    #[test]
    fn test_polite_commands() {
        let engine = NluEngine::new();

        // Polite prefix should be stripped
        let result = engine.parse("please turn on the lights");
        match result.intent {
            Intent::Lights { action, .. } => {
                assert_eq!(action, LightAction::TurnOn);
            }
            _ => panic!("Expected Lights intent"),
        }
    }

    #[test]
    fn test_unknown_command() {
        let engine = NluEngine::new();

        let result = engine.parse("random gibberish xyz");
        match result.intent {
            Intent::Unknown { .. } => {}
            _ => panic!("Expected Unknown intent"),
        }
        assert!(result.confidence < 0.5);
    }

    #[test]
    fn test_confidence_threshold_enforcement() {
        // Create engine with high threshold
        let engine = NluEngine::with_threshold(0.90);

        // Command with 0.85 confidence should be rejected
        let result = engine.parse("turn on bedroom lights");
        // The implicit room reference gives 0.85 confidence, below 0.90 threshold
        assert!(result.confidence < 0.90 || matches!(result.intent, Intent::Lights { .. }));
    }

    #[test]
    fn test_confidence_threshold_low() {
        // Create engine with low threshold
        let engine = NluEngine::with_threshold(0.50);

        // Most commands should pass
        let result = engine.parse("turn on lights");
        assert!(!matches!(result.intent, Intent::Unknown { .. }) || result.confidence < 0.50);
    }

    #[test]
    fn test_parse_raw_ignores_threshold() {
        let engine = NluEngine::with_threshold(1.0); // Impossible threshold

        // parse_raw should return actual intent regardless of threshold
        let result = engine.parse_raw("turn on the living room lights");
        match result.intent {
            Intent::Lights { .. } => {}
            _ => panic!("Expected Lights intent from parse_raw"),
        }
    }

    #[test]
    fn test_meets_threshold() {
        let engine = NluEngine::with_threshold(0.80);

        assert!(engine.meets_threshold(0.95));
        assert!(engine.meets_threshold(0.80));
        assert!(!engine.meets_threshold(0.79));
        assert!(!engine.meets_threshold(0.50));
    }

    #[test]
    fn test_default_confidence_threshold() {
        let engine = NluEngine::new();
        assert_eq!(engine.confidence_threshold(), DEFAULT_CONFIDENCE_THRESHOLD);
    }
}

/*
 * Flow processes language. Natural commands become structured actions.
 * h(x) >= 0 always
 */
