//! Offline Command Pattern Matching
//!
//! When in SlowZone or UnthinkingDepths, we can't reach the cloud LLM.
//! This module provides pattern-based command recognition for common
//! home automation and Tesla control commands.
//!
//! Colony: Nexus (e₄) — Local intelligence bridge
//!
//! η → s → μ → a → η′
//! h(x) ≥ 0. Always.

use serde::{Deserialize, Serialize};
use tracing::{debug, info};

/// Commands that can be executed immediately using cached state
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum CachedCommand {
    // Lighting
    LightsOn { rooms: Option<Vec<String>> },
    LightsOff { rooms: Option<Vec<String>> },
    LightsDim { level: u8, rooms: Option<Vec<String>> },

    // Shades
    ShadesOpen { rooms: Option<Vec<String>> },
    ShadesClose { rooms: Option<Vec<String>> },

    // Scenes
    SceneGoodnight,
    SceneWelcome,
    SceneMovie,

    // Lock
    LockAll,
}

/// Commands that need to be queued for when connectivity returns
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum QueuedCommand {
    // Tesla
    TeslaClimate { on: bool },
    TeslaLock { lock: bool },
    TeslaFrunk,
    TeslaTrunk,
    TeslaHonk,
    TeslaFlash,

    // Home
    SetThermostat { temp: f32 },
    Announce { message: String, rooms: Option<Vec<String>> },

    // Music/Spotify
    SpotifyPlay { playlist: Option<String> },
    SpotifyPause,
    SpotifySkip,
    SpotifyPrevious,
    SpotifyVolume { level: u8 },
}

/// Queries that can be answered from cached state
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum CachedQuery {
    // Tesla
    TeslaBattery,
    TeslaRange,
    TeslaLocation,
    TeslaClimateStatus,
    TeslaLockStatus,

    // Home
    LightStatus { room: Option<String> },
    ShadeStatus { room: Option<String> },
    DoorStatus,
    SecurityStatus,
    Temperature { room: Option<String> },

    // General
    Weather,
    Time,
}

/// Result of offline command matching
#[derive(Debug, Clone)]
pub enum OfflineAction {
    /// Execute immediately using cached state
    Execute(CachedCommand),

    /// Queue for later execution when connectivity returns
    Queue(QueuedCommand),

    /// Answer from cached state
    Query(CachedQuery),

    /// Unable to process offline - needs full LLM
    RequiresCloud(String),
}

/// Match transcribed text to an offline action
///
/// This uses simple pattern matching optimized for common commands.
/// When in Transcend/Beyond zones, we use the cloud LLM for full understanding.
pub fn match_offline_command(text: &str) -> OfflineAction {
    let lower = text.to_lowercase();
    let _words: Vec<&str> = lower.split_whitespace().collect();

    debug!("Offline matching: \"{}\"", text);

    // ========================================================================
    // Lighting Commands
    // ========================================================================

    // "lights on" / "turn on the lights" / "lights on in living room" / "turn on the kitchen lights"
    // Also match "turn on the X lights" pattern
    if contains_any(&lower, &["lights on", "turn on the lights", "turn on lights"])
       || (lower.contains("turn on") && lower.contains("lights")) {
        let rooms = extract_rooms(&lower);
        info!("Matched: LightsOn {:?}", rooms);
        return OfflineAction::Execute(CachedCommand::LightsOn { rooms });
    }

    // "lights off" / "turn off the lights"
    if contains_any(&lower, &["lights off", "turn off the lights", "turn off lights"]) {
        let rooms = extract_rooms(&lower);
        info!("Matched: LightsOff {:?}", rooms);
        return OfflineAction::Execute(CachedCommand::LightsOff { rooms });
    }

    // "dim the lights" / "lights to 50" / "set lights to 30 percent"
    if let Some(level) = extract_dim_level(&lower) {
        let rooms = extract_rooms(&lower);
        info!("Matched: LightsDim {}% {:?}", level, rooms);
        return OfflineAction::Execute(CachedCommand::LightsDim { level, rooms });
    }

    // ========================================================================
    // Shade Commands
    // ========================================================================

    // "open shades" / "raise the blinds"
    if contains_any(&lower, &["open shades", "raise shades", "open blinds", "raise blinds", "shades up"]) {
        let rooms = extract_rooms(&lower);
        info!("Matched: ShadesOpen {:?}", rooms);
        return OfflineAction::Execute(CachedCommand::ShadesOpen { rooms });
    }

    // "close shades" / "lower the blinds"
    if contains_any(&lower, &["close shades", "lower shades", "close blinds", "lower blinds", "shades down"]) {
        let rooms = extract_rooms(&lower);
        info!("Matched: ShadesClose {:?}", rooms);
        return OfflineAction::Execute(CachedCommand::ShadesClose { rooms });
    }

    // ========================================================================
    // Scene Commands
    // ========================================================================

    // "goodnight" / "good night" / "bedtime"
    if contains_any(&lower, &["goodnight", "good night", "bedtime", "going to bed", "night mode"]) {
        info!("Matched: SceneGoodnight");
        return OfflineAction::Execute(CachedCommand::SceneGoodnight);
    }

    // "welcome home" / "i'm home" / "arrived"
    if contains_any(&lower, &["welcome home", "i'm home", "im home", "arrived home", "home mode"]) {
        info!("Matched: SceneWelcome");
        return OfflineAction::Execute(CachedCommand::SceneWelcome);
    }

    // "movie mode" / "movie time" / "start movie"
    if contains_any(&lower, &["movie mode", "movie time", "watch a movie", "start movie", "cinema"]) {
        info!("Matched: SceneMovie");
        return OfflineAction::Execute(CachedCommand::SceneMovie);
    }

    // ========================================================================
    // Lock Commands
    // ========================================================================

    // "lock everything" / "lock all doors" / "lock up"
    if contains_any(&lower, &["lock everything", "lock all", "lock up", "lock the doors", "secure the house"]) {
        info!("Matched: LockAll");
        return OfflineAction::Execute(CachedCommand::LockAll);
    }

    // ========================================================================
    // Tesla Commands (Queued - need API)
    // ========================================================================

    // "warm up the car" / "preheat tesla" / "start climate"
    if contains_any(&lower, &["warm up", "preheat", "heat the car", "start climate", "car climate on"])
       && contains_any(&lower, &["car", "tesla", "vehicle", ""]) {
        info!("Matched: TeslaClimate on (queued)");
        return OfflineAction::Queue(QueuedCommand::TeslaClimate { on: true });
    }

    // "cool down the car" / "turn off car climate"
    if contains_any(&lower, &["cool off", "stop climate", "climate off", "turn off climate"]) {
        info!("Matched: TeslaClimate off (queued)");
        return OfflineAction::Queue(QueuedCommand::TeslaClimate { on: false });
    }

    // "lock the car" / "lock tesla"
    if contains_any(&lower, &["lock the car", "lock tesla", "lock vehicle", "car lock"]) {
        info!("Matched: TeslaLock (queued)");
        return OfflineAction::Queue(QueuedCommand::TeslaLock { lock: true });
    }

    // "unlock the car" / "unlock tesla"
    if contains_any(&lower, &["unlock the car", "unlock tesla", "unlock vehicle", "car unlock"]) {
        info!("Matched: TeslaUnlock (queued)");
        return OfflineAction::Queue(QueuedCommand::TeslaLock { lock: false });
    }

    // "open frunk" / "pop the frunk"
    if contains_any(&lower, &["open frunk", "pop frunk", "frunk open", "front trunk"]) {
        info!("Matched: TeslaFrunk (queued)");
        return OfflineAction::Queue(QueuedCommand::TeslaFrunk);
    }

    // "open trunk" / "pop the trunk"
    if contains_any(&lower, &["open trunk", "pop trunk", "trunk open"])
       && !lower.contains("frunk") && !lower.contains("front") {
        info!("Matched: TeslaTrunk (queued)");
        return OfflineAction::Queue(QueuedCommand::TeslaTrunk);
    }

    // "honk" / "honk the horn"
    if contains_any(&lower, &["honk", "horn", "beep"]) {
        info!("Matched: TeslaHonk (queued)");
        return OfflineAction::Queue(QueuedCommand::TeslaHonk);
    }

    // "flash lights" / "flash the car"
    if contains_any(&lower, &["flash lights", "flash the car", "blink lights"]) {
        info!("Matched: TeslaFlash (queued)");
        return OfflineAction::Queue(QueuedCommand::TeslaFlash);
    }

    // ========================================================================
    // Music/Spotify Commands (Queued - need API)
    // ========================================================================

    // "play music" / "play some music" / "start spotify" / "play jazz"
    if contains_any(&lower, &["play music", "play some music", "start spotify", "start music"]) {
        let playlist = extract_playlist(&lower);
        info!("Matched: SpotifyPlay {:?} (queued)", playlist);
        return OfflineAction::Queue(QueuedCommand::SpotifyPlay { playlist });
    }

    // "play [genre] music" / "play [playlist name]"
    if lower.starts_with("play ") && !contains_any(&lower, &["lights", "car", "tesla", "video"]) {
        let playlist = extract_playlist(&lower);
        if playlist.is_some() {
            info!("Matched: SpotifyPlay {:?} (queued)", playlist);
            return OfflineAction::Queue(QueuedCommand::SpotifyPlay { playlist });
        }
    }

    // "pause music" / "stop the music" / "pause spotify"
    if contains_any(&lower, &["pause music", "pause the music", "stop music", "stop the music", "pause spotify", "stop spotify", "music off"]) {
        info!("Matched: SpotifyPause (queued)");
        return OfflineAction::Queue(QueuedCommand::SpotifyPause);
    }

    // "next song" / "skip" / "next track"
    if contains_any(&lower, &["next song", "skip song", "skip", "next track", "skip track"]) {
        info!("Matched: SpotifySkip (queued)");
        return OfflineAction::Queue(QueuedCommand::SpotifySkip);
    }

    // "previous song" / "go back" / "last song"
    if contains_any(&lower, &["previous song", "go back", "last song", "previous track"]) {
        info!("Matched: SpotifyPrevious (queued)");
        return OfflineAction::Queue(QueuedCommand::SpotifyPrevious);
    }

    // "volume up" / "louder" / "turn up the music"
    if contains_any(&lower, &["volume up", "louder", "turn up", "music louder"]) && !lower.contains("tv") {
        info!("Matched: SpotifyVolume up (queued)");
        return OfflineAction::Queue(QueuedCommand::SpotifyVolume { level: 80 });
    }

    // "volume down" / "quieter" / "turn down the music"
    if contains_any(&lower, &["volume down", "quieter", "turn down", "music quieter"]) && !lower.contains("tv") {
        info!("Matched: SpotifyVolume down (queued)");
        return OfflineAction::Queue(QueuedCommand::SpotifyVolume { level: 40 });
    }

    // ========================================================================
    // Status Queries (From Cache)
    // ========================================================================

    // "how much battery" / "what's the charge" / "battery level"
    if contains_any(&lower, &["battery", "charge level", "how charged", "percent charge"]) {
        info!("Matched: TeslaBattery query");
        return OfflineAction::Query(CachedQuery::TeslaBattery);
    }

    // "how far can I go" / "range" / "miles left"
    if contains_any(&lower, &["range", "miles left", "how far", "distance remaining"]) {
        info!("Matched: TeslaRange query");
        return OfflineAction::Query(CachedQuery::TeslaRange);
    }

    // "where's the car" / "car location"
    if contains_any(&lower, &["where's the car", "where is the car", "car location", "find my car", "locate car"]) {
        info!("Matched: TeslaLocation query");
        return OfflineAction::Query(CachedQuery::TeslaLocation);
    }

    // "what's the weather" / "weather forecast"
    if contains_any(&lower, &["weather", "forecast", "temperature outside", "what's it like outside"]) {
        info!("Matched: Weather query");
        return OfflineAction::Query(CachedQuery::Weather);
    }

    // "what time is it" / "current time"
    if contains_any(&lower, &["what time", "current time", "tell me the time"]) {
        info!("Matched: Time query");
        return OfflineAction::Query(CachedQuery::Time);
    }

    // "are the lights on" / "light status"
    if contains_any(&lower, &["are the lights", "light status", "lights on or off"]) {
        let room = extract_single_room(&lower);
        info!("Matched: LightStatus query {:?}", room);
        return OfflineAction::Query(CachedQuery::LightStatus { room });
    }

    // "is the car locked" / "car lock status"
    if contains_any(&lower, &["car locked", "is the car locked", "tesla locked", "vehicle locked"]) {
        info!("Matched: TeslaLockStatus query");
        return OfflineAction::Query(CachedQuery::TeslaLockStatus);
    }

    // "are the doors locked" / "door status" (home)
    if contains_any(&lower, &["doors locked", "door status", "is the house locked"]) {
        info!("Matched: DoorStatus query");
        return OfflineAction::Query(CachedQuery::DoorStatus);
    }

    // ========================================================================
    // Fallback - Needs Cloud
    // ========================================================================

    info!("No offline match for: \"{}\"", text);
    OfflineAction::RequiresCloud(text.to_string())
}

// ============================================================================
// Helper Functions
// ============================================================================

/// Check if text contains any of the patterns
fn contains_any(text: &str, patterns: &[&str]) -> bool {
    patterns.iter().any(|p| text.contains(p))
}

/// Extract room names from text
fn extract_rooms(text: &str) -> Option<Vec<String>> {
    let room_keywords = [
        ("living room", "Living Room"),
        ("kitchen", "Kitchen"),
        ("dining", "Dining"),
        ("bedroom", "Primary Bedroom"),
        ("primary", "Primary Bedroom"),
        ("master", "Primary Bedroom"),
        ("office", "Office"),
        ("bathroom", "Primary Bath"),
        ("bath", "Primary Bath"),
        ("entry", "Entry"),
        ("garage", "Garage"),
        ("game room", "Game Room"),
        ("basement", "Game Room"),
        ("gym", "Gym"),
        ("laundry", "Laundry"),
        ("loft", "Loft"),
        ("everywhere", "__ALL__"),
        ("all rooms", "__ALL__"),
        ("whole house", "__ALL__"),
    ];

    let mut found_rooms = Vec::new();

    for (keyword, room_name) in room_keywords {
        if text.contains(keyword) {
            if room_name == "__ALL__" {
                return None; // None means all rooms
            }
            found_rooms.push(room_name.to_string());
        }
    }

    if found_rooms.is_empty() {
        None // Default to all rooms if none specified
    } else {
        Some(found_rooms)
    }
}

/// Extract single room for queries
fn extract_single_room(text: &str) -> Option<String> {
    extract_rooms(text).and_then(|rooms| rooms.into_iter().next())
}

/// Extract playlist/genre from music commands
fn extract_playlist(text: &str) -> Option<String> {
    // Known playlists/genres to match
    let playlists = [
        ("jazz", "Jazz"),
        ("classical", "Classical"),
        ("focus", "Focus"),
        ("chill", "Chill"),
        ("workout", "Workout"),
        ("party", "Party"),
        ("dinner", "Dinner Music"),
        ("morning", "Morning Coffee"),
        ("evening", "Evening Chill"),
        ("rock", "Rock"),
        ("pop", "Pop"),
        ("indie", "Indie"),
        ("electronic", "Electronic"),
        ("ambient", "Ambient"),
        ("lofi", "Lo-Fi Beats"),
        ("lo-fi", "Lo-Fi Beats"),
        ("lo fi", "Lo-Fi Beats"),
        ("hip hop", "Hip Hop"),
        ("hip-hop", "Hip Hop"),
        ("rnb", "R&B"),
        ("r&b", "R&B"),
        ("country", "Country"),
        ("folk", "Folk"),
        ("blues", "Blues"),
        ("soul", "Soul"),
        ("metal", "Metal"),
        ("punk", "Punk"),
        ("reggae", "Reggae"),
        ("latin", "Latin"),
        ("k-pop", "K-Pop"),
        ("kpop", "K-Pop"),
        ("anime", "Anime"),
        ("gaming", "Gaming"),
        ("sleep", "Sleep"),
        ("meditation", "Meditation"),
        ("yoga", "Yoga"),
        ("studying", "Studying"),
        ("coding", "Coding"),
        ("cooking", "Cooking"),
        ("cleaning", "Cleaning"),
        ("relax", "Relax"),
        ("calm", "Calm"),
        ("happy", "Happy"),
        ("sad", "Sad"),
        ("energetic", "Energetic"),
        ("romantic", "Romantic"),
    ];

    for (keyword, playlist_name) in playlists {
        if text.contains(keyword) {
            return Some(playlist_name.to_string());
        }
    }

    // Try to extract quoted playlist name
    if let Some(start) = text.find('"') {
        if let Some(end) = text[start+1..].find('"') {
            let playlist = &text[start+1..start+1+end];
            if !playlist.is_empty() {
                return Some(playlist.to_string());
            }
        }
    }

    None
}

/// Extract dim level percentage from text
fn extract_dim_level(text: &str) -> Option<u8> {
    // Try to extract explicit numeric percentage FIRST
    // Patterns: "50 percent", "to 50", "at 30%"
    let words: Vec<&str> = text.split_whitespace().collect();

    for (i, word) in words.iter().enumerate() {
        // Check for "percent" or "%" following a number
        if *word == "percent" || word.ends_with('%') {
            if i > 0 {
                if let Ok(num) = words[i - 1].parse::<u8>() {
                    if num <= 100 {
                        return Some(num);
                    }
                }
            }
        }
    }

    // Try to parse standalone numbers with context
    for word in words.iter() {
        if let Ok(num) = word.trim_end_matches('%').parse::<u8>() {
            if num <= 100 {
                // Verify it's in a light context
                if text.contains("light") || text.contains("dim") || text.contains("set") {
                    return Some(num);
                }
            }
        }
    }

    // Fall back to named levels
    let patterns = [
        ("dimmer", 20),  // More specific first
        ("dim", 30),
        ("brighter", 100),
        ("bright", 80),
        ("half", 50),
        ("low", 25),
        ("medium", 50),
        ("high", 80),
    ];

    for (pattern, level) in patterns {
        if text.contains(pattern) {
            return Some(level);
        }
    }

    None
}

// ============================================================================
// Response Generation (for TTS)
// ============================================================================

/// Generate spoken response for a cached query
pub fn generate_query_response(query: &CachedQuery, state: &QueryState) -> String {
    match query {
        CachedQuery::TeslaBattery => {
            if let Some(level) = state.tesla_battery {
                format!("The car is at {} percent.", level)
            } else {
                "I don't have current battery information.".to_string()
            }
        }
        CachedQuery::TeslaRange => {
            if let Some(range) = state.tesla_range {
                format!("You have about {} miles of range.", range as i32)
            } else {
                "I don't have current range information.".to_string()
            }
        }
        CachedQuery::TeslaLocation => {
            if let Some(ref loc) = state.tesla_location {
                format!("The car is at {}.", loc)
            } else {
                "I don't have current location information.".to_string()
            }
        }
        CachedQuery::Weather => {
            if let Some(ref weather) = state.weather {
                format!("It's currently {} degrees and {}.",
                    weather.temp as i32, weather.condition)
            } else {
                "I don't have current weather information.".to_string()
            }
        }
        CachedQuery::Time => {
            let now = chrono::Local::now();
            format!("It's {}.", now.format("%l:%M %p"))
        }
        CachedQuery::LightStatus { room } => {
            if let Some(ref status) = state.lights_on {
                if *status {
                    if let Some(ref r) = room {
                        format!("The {} lights are on.", r)
                    } else {
                        "The lights are on.".to_string()
                    }
                } else {
                    if let Some(ref r) = room {
                        format!("The {} lights are off.", r)
                    } else {
                        "The lights are off.".to_string()
                    }
                }
            } else {
                "I don't have current light status.".to_string()
            }
        }
        CachedQuery::TeslaLockStatus => {
            if let Some(locked) = state.tesla_locked {
                if locked {
                    "The car is locked.".to_string()
                } else {
                    "The car is unlocked.".to_string()
                }
            } else {
                "I don't have current lock status.".to_string()
            }
        }
        CachedQuery::DoorStatus => {
            if let Some(locked) = state.doors_locked {
                if locked {
                    "All doors are locked.".to_string()
                } else {
                    "Some doors may be unlocked.".to_string()
                }
            } else {
                "I don't have current door status.".to_string()
            }
        }
        _ => "I'm not sure about that.".to_string()
    }
}

/// State snapshot for query responses
#[derive(Debug, Default)]
pub struct QueryState {
    pub tesla_battery: Option<u8>,
    pub tesla_range: Option<f32>,
    pub tesla_location: Option<String>,
    pub tesla_locked: Option<bool>,
    pub lights_on: Option<bool>,
    pub doors_locked: Option<bool>,
    pub weather: Option<WeatherInfo>,
}

#[derive(Debug)]
pub struct WeatherInfo {
    pub temp: f32,
    pub condition: String,
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_lights_on() {
        match match_offline_command("turn on the lights") {
            OfflineAction::Execute(CachedCommand::LightsOn { rooms }) => {
                assert!(rooms.is_none()); // All rooms
            }
            _ => panic!("Expected LightsOn"),
        }
    }

    #[test]
    fn test_lights_on_room() {
        match match_offline_command("turn on the kitchen lights") {
            OfflineAction::Execute(CachedCommand::LightsOn { rooms }) => {
                assert_eq!(rooms, Some(vec!["Kitchen".to_string()]));
            }
            _ => panic!("Expected LightsOn with Kitchen"),
        }
    }

    #[test]
    fn test_lights_off() {
        match match_offline_command("lights off") {
            OfflineAction::Execute(CachedCommand::LightsOff { .. }) => {}
            _ => panic!("Expected LightsOff"),
        }
    }

    #[test]
    fn test_dim_level() {
        match match_offline_command("dim the lights to 50 percent") {
            OfflineAction::Execute(CachedCommand::LightsDim { level, .. }) => {
                assert_eq!(level, 50);
            }
            _ => panic!("Expected LightsDim"),
        }
    }

    #[test]
    fn test_goodnight() {
        match match_offline_command("goodnight") {
            OfflineAction::Execute(CachedCommand::SceneGoodnight) => {}
            _ => panic!("Expected SceneGoodnight"),
        }
    }

    #[test]
    fn test_tesla_climate() {
        match match_offline_command("warm up the car") {
            OfflineAction::Queue(QueuedCommand::TeslaClimate { on: true }) => {}
            _ => panic!("Expected TeslaClimate on"),
        }
    }

    #[test]
    fn test_battery_query() {
        match match_offline_command("how much battery does the car have") {
            OfflineAction::Query(CachedQuery::TeslaBattery) => {}
            _ => panic!("Expected TeslaBattery query"),
        }
    }

    #[test]
    fn test_weather_query() {
        match match_offline_command("what's the weather like") {
            OfflineAction::Query(CachedQuery::Weather) => {}
            _ => panic!("Expected Weather query"),
        }
    }

    #[test]
    fn test_unknown_command() {
        match match_offline_command("do something weird and complex") {
            OfflineAction::RequiresCloud(_) => {}
            _ => panic!("Expected RequiresCloud for unknown command"),
        }
    }

    #[test]
    fn test_play_music() {
        match match_offline_command("play some music") {
            OfflineAction::Queue(QueuedCommand::SpotifyPlay { playlist }) => {
                assert!(playlist.is_none()); // No specific playlist
            }
            _ => panic!("Expected SpotifyPlay"),
        }
    }

    #[test]
    fn test_play_jazz() {
        match match_offline_command("play jazz music") {
            OfflineAction::Queue(QueuedCommand::SpotifyPlay { playlist }) => {
                assert_eq!(playlist, Some("Jazz".to_string()));
            }
            _ => panic!("Expected SpotifyPlay with Jazz"),
        }
    }

    #[test]
    fn test_pause_music() {
        match match_offline_command("pause the music") {
            OfflineAction::Queue(QueuedCommand::SpotifyPause) => {}
            _ => panic!("Expected SpotifyPause"),
        }
    }

    #[test]
    fn test_skip_song() {
        match match_offline_command("skip this song") {
            OfflineAction::Queue(QueuedCommand::SpotifySkip) => {}
            _ => panic!("Expected SpotifySkip"),
        }
    }

    #[test]
    fn test_volume_up() {
        match match_offline_command("turn up the music") {
            OfflineAction::Queue(QueuedCommand::SpotifyVolume { level }) => {
                assert_eq!(level, 80);
            }
            _ => panic!("Expected SpotifyVolume"),
        }
    }

    #[test]
    fn test_extract_rooms_multiple() {
        let rooms = extract_rooms("living room and kitchen");
        assert!(rooms.is_some());
        let rooms = rooms.unwrap();
        assert!(rooms.contains(&"Living Room".to_string()));
        assert!(rooms.contains(&"Kitchen".to_string()));
    }

    #[test]
    fn test_extract_rooms_all() {
        let rooms = extract_rooms("turn on lights everywhere");
        assert!(rooms.is_none()); // None = all rooms
    }
}

/*
 * 鏡
 * Pattern matching for the depths where clouds don't reach.
 */
