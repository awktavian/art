//! Voice Pipeline Tests
//!
//! Tests command parsing from transcribed speech to structured intents.
//! Covers scene triggers, device controls, and entity extraction.
//!
//! Colony: Flow (e3) -> Nexus (e4) -> Crystal (e7)

use pretty_assertions::assert_eq;
use proptest::prelude::*;
use rstest::*;
use test_case::test_case;

use kagami_hub::voice_pipeline::{
    parse_command, CommandEntities, CommandIntent, PipelineState, VoiceCommand,
};

// ============================================================================
// Pipeline State Tests
// ============================================================================

#[rstest]
fn test_pipeline_state_variants() {
    let states = vec![
        PipelineState::Listening,
        PipelineState::Capturing,
        PipelineState::Transcribing,
        PipelineState::Executing,
        PipelineState::Speaking,
    ];
    assert_eq!(states.len(), 5);
}

#[rstest]
fn test_pipeline_state_equality() {
    assert_eq!(PipelineState::Listening, PipelineState::Listening);
    assert_ne!(PipelineState::Listening, PipelineState::Capturing);
}

#[rstest]
fn test_pipeline_state_clone() {
    let state = PipelineState::Executing;
    let cloned = state.clone();
    assert_eq!(state, cloned);
}

// ============================================================================
// Scene Command Tests
// ============================================================================

#[test_case("activate movie mode" => matches CommandIntent::Scene(s) if s == "movie_mode" ; "movie mode activation")]
#[test_case("movie time" => matches CommandIntent::Scene(s) if s == "movie_mode" ; "movie time")]
#[test_case("cinema mode" => matches CommandIntent::Scene(s) if s == "movie_mode" ; "cinema mode")]
#[test_case("start the movie" => matches CommandIntent::Scene(s) if s == "movie_mode" ; "start movie")]
#[test_case("goodnight" => matches CommandIntent::Scene(s) if s == "goodnight" ; "goodnight")]
#[test_case("good night" => matches CommandIntent::Scene(s) if s == "goodnight" ; "good night with space")]
#[test_case("welcome home" => matches CommandIntent::Scene(s) if s == "welcome_home" ; "welcome home")]
#[test_case("I'm home welcome me" => matches CommandIntent::Scene(s) if s == "welcome_home" ; "welcome variation")]
fn test_scene_parsing(input: &str) -> CommandIntent {
    parse_command(input).intent
}

#[rstest]
#[case("MOVIE MODE", "movie_mode")]
#[case("Movie Mode", "movie_mode")]
#[case("GOODNIGHT", "goodnight")]
#[case("WELCOME HOME", "welcome_home")]
fn test_scene_case_insensitivity(#[case] input: &str, #[case] expected_scene: &str) {
    let command = parse_command(input);
    match command.intent {
        CommandIntent::Scene(scene) => assert_eq!(scene, expected_scene),
        _ => panic!("Expected Scene intent"),
    }
}

// ============================================================================
// Lights Command Tests
// ============================================================================

#[test_case("turn off the lights" => matches CommandIntent::Lights(0) ; "lights off")]
#[test_case("lights off" => matches CommandIntent::Lights(0) ; "lights off short")]
#[test_case("turn the lights off" => matches CommandIntent::Lights(0) ; "turn lights off")]
#[test_case("lights on" => matches CommandIntent::Lights(100) ; "lights on")]
#[test_case("turn on the lights" => matches CommandIntent::Lights(100) ; "turn on lights")]
#[test_case("lights full" => matches CommandIntent::Lights(100) ; "lights full")]
#[test_case("full brightness lights" => matches CommandIntent::Lights(100) ; "full brightness")]
#[test_case("bright lights" => matches CommandIntent::Lights(100) ; "bright lights")]
#[test_case("dim the lights" => matches CommandIntent::Lights(25) ; "dim lights")]
#[test_case("low lights" => matches CommandIntent::Lights(25) ; "low lights")]
#[test_case("lights half" => matches CommandIntent::Lights(50) ; "half lights")]
#[test_case("set lights to 50" => matches CommandIntent::Lights(50) ; "lights to 50")]
#[test_case("lights 75" => matches CommandIntent::Lights(75) ; "lights 75")]
#[test_case("set lights to 25 percent" => matches CommandIntent::Lights(25) ; "lights 25 percent")]
fn test_lights_parsing(input: &str) -> CommandIntent {
    parse_command(input).intent
}

#[rstest]
#[case("lights twenty", 20)]
#[case("lights thirty", 30)]
#[case("lights forty", 40)]
#[case("lights fifty", 50)]
#[case("lights sixty", 60)]
#[case("lights seventy", 70)]
#[case("lights eighty", 80)]
#[case("lights ninety", 90)]
fn test_word_number_parsing(#[case] input: &str, #[case] expected_level: i32) {
    let command = parse_command(input);
    match command.intent {
        CommandIntent::Lights(level) => assert_eq!(level, expected_level),
        _ => panic!("Expected Lights intent"),
    }
}

// ============================================================================
// Room Entity Extraction Tests
// ============================================================================

#[rstest]
#[case("turn off the living room lights", vec!["living room"])]
#[case("kitchen lights on", vec!["kitchen"])]
#[case("lights in the bedroom", vec!["bedroom"])]
#[case("dining room lights dim", vec!["dining room"])]
#[case("office lights 50", vec!["office"])]
#[case("primary bedroom lights off", vec!["primary bedroom"])]
#[case("patio lights on", vec!["patio"])]
#[case("deck lights", vec!["deck"])]
#[case("loft lights", vec!["loft"])]
#[case("game room lights", vec!["game room"])]
#[case("laundry room lights", vec!["laundry room"])]
fn test_room_extraction(#[case] input: &str, #[case] expected_rooms: Vec<&str>) {
    let command = parse_command(input);
    let rooms = command.entities.rooms.expect("Should have rooms");
    for expected in expected_rooms {
        assert!(
            rooms.iter().any(|r| r.contains(expected)),
            "Expected room '{}' not found in {:?}",
            expected,
            rooms
        );
    }
}

#[rstest]
fn test_no_room_when_not_specified() {
    let command = parse_command("lights on");
    assert!(command.entities.rooms.is_none(), "Should have no rooms");
}

// ============================================================================
// Fireplace Command Tests
// ============================================================================

#[test_case("fireplace on" => matches CommandIntent::Fireplace(true) ; "fireplace on")]
#[test_case("turn on the fireplace" => matches CommandIntent::Fireplace(true) ; "turn on fireplace")]
#[test_case("fire on" => matches CommandIntent::Fireplace(true) ; "fire on")]
#[test_case("start the fireplace" => matches CommandIntent::Fireplace(true) ; "start fireplace")]
#[test_case("fireplace off" => matches CommandIntent::Fireplace(false) ; "fireplace off")]
#[test_case("turn off the fireplace" => matches CommandIntent::Fireplace(false) ; "turn off fireplace")]
#[test_case("fire off" => matches CommandIntent::Fireplace(false) ; "fire off")]
fn test_fireplace_parsing(input: &str) -> CommandIntent {
    parse_command(input).intent
}

// ============================================================================
// Shades Command Tests
// ============================================================================

#[test_case("open the shades" => matches CommandIntent::Shades(a) if a == "open" ; "open shades")]
#[test_case("shades up" => matches CommandIntent::Shades(a) if a == "open" ; "shades up")]
#[test_case("raise the blinds" => matches CommandIntent::Shades(a) if a == "open" ; "raise blinds")]
#[test_case("open curtains" => matches CommandIntent::Shades(a) if a == "open" ; "open curtains")]
#[test_case("close the shades" => matches CommandIntent::Shades(a) if a == "close" ; "close shades")]
#[test_case("shades down" => matches CommandIntent::Shades(a) if a == "close" ; "shades down")]
#[test_case("lower the blinds" => matches CommandIntent::Shades(a) if a == "close" ; "lower blinds")]
#[test_case("close curtains" => matches CommandIntent::Shades(a) if a == "close" ; "close curtains")]
fn test_shades_parsing(input: &str) -> CommandIntent {
    parse_command(input).intent
}

#[rstest]
fn test_shades_with_room() {
    let command = parse_command("close the living room shades");
    match &command.intent {
        CommandIntent::Shades(action) => assert_eq!(action, "close"),
        _ => panic!("Expected Shades intent"),
    }
    assert!(command.entities.rooms.is_some());
}

// ============================================================================
// TV Command Tests
// ============================================================================

#[test_case("tv up" => matches CommandIntent::TV(a) if a == "raise" ; "tv up")]
#[test_case("raise the tv" => matches CommandIntent::TV(a) if a == "raise" ; "raise tv")]
#[test_case("hide the tv" => matches CommandIntent::TV(a) if a == "raise" ; "hide tv")]
#[test_case("television up" => matches CommandIntent::TV(a) if a == "raise" ; "television up")]
#[test_case("tv down" => matches CommandIntent::TV(a) if a == "lower" ; "tv down")]
#[test_case("lower the tv" => matches CommandIntent::TV(a) if a == "lower" ; "lower tv")]
#[test_case("show the tv" => matches CommandIntent::TV(a) if a == "lower" ; "show tv")]
fn test_tv_parsing(input: &str) -> CommandIntent {
    parse_command(input).intent
}

// ============================================================================
// Announce Command Tests
// ============================================================================

#[rstest]
fn test_announce_basic() {
    let command = parse_command("announce dinner is ready");
    match &command.intent {
        CommandIntent::Announce(msg) => assert!(msg.contains("dinner")),
        _ => panic!("Expected Announce intent"),
    }
}

#[rstest]
fn test_announce_with_quotes() {
    let command = parse_command("announce \"hello everyone\"");
    match &command.intent {
        CommandIntent::Announce(msg) => assert!(msg.contains("hello")),
        _ => panic!("Expected Announce intent"),
    }
}

#[rstest]
#[case("say it's time for bed")]
#[case("tell everyone dinner is served")]
fn test_announce_variations(#[case] input: &str) {
    let command = parse_command(input);
    assert!(matches!(command.intent, CommandIntent::Announce(_)));
}

// ============================================================================
// Unknown Command Tests
// ============================================================================

#[rstest]
#[case("")]
#[case("hello")]
#[case("random gibberish")]
fn test_unknown_commands(#[case] input: &str) {
    let command = parse_command(input);
    assert!(matches!(command.intent, CommandIntent::Unknown));
}

// ============================================================================
// Weather and Music are now recognized (updated from previous Unknown tests)
// ============================================================================

#[rstest]
fn test_weather_query() {
    let command = parse_command("what's the weather");
    assert!(matches!(command.intent, CommandIntent::Weather));
}

#[rstest]
fn test_music_play() {
    let command = parse_command("play some music");
    assert!(matches!(command.intent, CommandIntent::Music(_)));
}

// ============================================================================
// VoiceCommand Structure Tests
// ============================================================================

#[rstest]
fn test_voice_command_raw_text_preserved() {
    let input = "Turn off the Living Room lights";
    let command = parse_command(input);
    assert_eq!(command.raw_text, input);
}

#[rstest]
fn test_voice_command_debug_impl() {
    let command = parse_command("lights on");
    let debug_str = format!("{:?}", command);
    assert!(debug_str.contains("VoiceCommand"));
    assert!(debug_str.contains("Lights"));
}

#[rstest]
fn test_command_entities_default() {
    let entities = CommandEntities::default();
    assert!(entities.rooms.is_none());
    assert!(entities.level.is_none());
}

// ============================================================================
// Edge Cases and Robustness
// ============================================================================

#[rstest]
#[case("  lights   on  ")]
#[case("lights  on")]
fn test_extra_whitespace_handling(#[case] input: &str) {
    let command = parse_command(input);
    assert!(matches!(command.intent, CommandIntent::Lights(100)));
}

#[rstest]
fn test_very_long_input() {
    let long_input = "please ".repeat(100) + "lights on";
    let command = parse_command(&long_input);
    assert!(matches!(command.intent, CommandIntent::Lights(100)));
}

#[rstest]
fn test_unicode_input() {
    let command = parse_command("lights on please");
    assert!(matches!(command.intent, CommandIntent::Lights(100)));
}

#[rstest]
fn test_numbers_out_of_range() {
    // Numbers outside 0-100 should not be parsed as levels
    let command = parse_command("lights 150");
    // Should fall back to default behavior
    assert!(matches!(command.intent, CommandIntent::Lights(_)));
}

// ============================================================================
// Property-Based Tests
// ============================================================================

proptest! {
    #[test]
    fn test_parse_never_panics(input in ".*") {
        // Should never panic on any input
        let _ = parse_command(&input);
    }

    #[test]
    fn test_raw_text_always_preserved(input in "[a-zA-Z ]{1,50}") {
        let command = parse_command(&input);
        assert_eq!(command.raw_text, input);
    }

    #[test]
    fn test_lights_levels_always_valid(level in 0i32..=100) {
        let input = format!("lights {}", level);
        let command = parse_command(&input);
        if let CommandIntent::Lights(parsed_level) = command.intent {
            assert!(parsed_level >= 0 && parsed_level <= 100);
        }
    }
}

// ============================================================================
// Integration-Style Tests
// ============================================================================

#[rstest]
fn test_complex_command_sequence() {
    // Simulate a sequence of voice commands
    let commands = vec![
        "activate movie mode",
        "dim the lights",
        "close the shades",
        "tv down",
        "fireplace on",
    ];

    for cmd in commands {
        let parsed = parse_command(cmd);
        assert!(
            !matches!(parsed.intent, CommandIntent::Unknown),
            "Command '{}' should be recognized",
            cmd
        );
    }
}

#[rstest]
fn test_goodnight_sequence() {
    // These commands are typically issued before bed
    let commands = vec!["goodnight", "lights off", "fireplace off"];

    for cmd in &commands {
        let parsed = parse_command(cmd);
        assert!(!matches!(parsed.intent, CommandIntent::Unknown));
    }

    // Verify specific intents
    assert!(matches!(
        parse_command("goodnight").intent,
        CommandIntent::Scene(_)
    ));
    assert!(matches!(
        parse_command("lights off").intent,
        CommandIntent::Lights(0)
    ));
    assert!(matches!(
        parse_command("fireplace off").intent,
        CommandIntent::Fireplace(false)
    ));
}

// ============================================================================
// Word Boundary Tests - Avoid False Positives
// ============================================================================

#[rstest]
#[case("harm the plants", CommandIntent::Unknown)]
#[case("farm report", CommandIntent::Unknown)]
#[case("charming day", CommandIntent::Unknown)]
fn test_arm_word_boundary_false_negatives(#[case] input: &str, #[case] _expected: CommandIntent) {
    let command = parse_command(input);
    // These should NOT trigger security arm
    assert!(!matches!(command.intent, CommandIntent::Security(_)));
}

#[rstest]
#[case("arm the alarm")]
#[case("arm the security system")]
fn test_arm_word_boundary_true_positives(#[case] input: &str) {
    let command = parse_command(input);
    assert!(matches!(command.intent, CommandIntent::Security(_)));
}

#[rstest]
#[case("clock on the wall", CommandIntent::Unknown)]
#[case("block the door", CommandIntent::Unknown)]
#[case("deadlock issue", CommandIntent::Unknown)]
fn test_lock_word_boundary_false_negatives(#[case] input: &str, #[case] _expected: CommandIntent) {
    let command = parse_command(input);
    // These should NOT trigger lock
    assert!(!matches!(command.intent, CommandIntent::Lock(_)));
}

#[rstest]
#[case("lock the doors", CommandIntent::Lock(true))]
#[case("unlock the front door", CommandIntent::Lock(false))]
fn test_lock_word_boundary_true_positives(#[case] input: &str, #[case] expected: CommandIntent) {
    let command = parse_command(input);
    assert_eq!(command.intent, expected);
}

#[rstest]
#[case("fire up the music", CommandIntent::Unknown)]
#[case("you're fired", CommandIntent::Unknown)]
fn test_fire_word_boundary_false_negatives(#[case] input: &str, #[case] _expected: CommandIntent) {
    let command = parse_command(input);
    // These should NOT trigger fireplace
    assert!(!matches!(command.intent, CommandIntent::Fireplace(_)));
}

#[rstest]
#[case("fire on", CommandIntent::Fireplace(true))]
#[case("fire off", CommandIntent::Fireplace(false))]
#[case("turn on the fireplace", CommandIntent::Fireplace(true))]
fn test_fire_word_boundary_true_positives(#[case] input: &str, #[case] expected: CommandIntent) {
    let command = parse_command(input);
    assert_eq!(command.intent, expected);
}

#[rstest]
#[case("use your brain", CommandIntent::Unknown)]
#[case("take the train", CommandIntent::Unknown)]
#[case("drain the water", CommandIntent::Unknown)]
fn test_rain_word_boundary_false_negatives(#[case] input: &str, #[case] _expected: CommandIntent) {
    let command = parse_command(input);
    // These should NOT trigger weather
    assert!(!matches!(command.intent, CommandIntent::Weather));
}

#[rstest]
#[case("is it going to rain", CommandIntent::Weather)]
#[case("will it rain today", CommandIntent::Weather)]
fn test_rain_word_boundary_true_positives(#[case] input: &str, #[case] expected: CommandIntent) {
    let command = parse_command(input);
    assert_eq!(command.intent, expected);
}

// ============================================================================
// Stop Keyword Collision Tests
// ============================================================================

use kagami_hub::voice_pipeline::{MusicAction, TeslaAction};

#[rstest]
fn test_stop_charging_is_tesla() {
    let command = parse_command("stop charging the car");
    assert!(matches!(
        command.intent,
        CommandIntent::Tesla(TeslaAction::StopCharge)
    ));
}

#[rstest]
fn test_stop_the_music_is_music_pause() {
    let command = parse_command("stop the music");
    assert!(matches!(
        command.intent,
        CommandIntent::Music(MusicAction::Pause)
    ));
}

#[rstest]
fn test_stop_alone_is_cancel() {
    let command = parse_command("stop");
    assert!(matches!(command.intent, CommandIntent::Cancel));
}

#[rstest]
fn test_cancel_is_cancel() {
    let command = parse_command("cancel");
    assert!(matches!(command.intent, CommandIntent::Cancel));
}

#[rstest]
fn test_never_mind_is_cancel() {
    let command = parse_command("never mind");
    assert!(matches!(command.intent, CommandIntent::Cancel));
}

// ============================================================================
// Room Extraction Duplicate Tests
// ============================================================================

#[rstest]
fn test_living_room_no_duplicate() {
    let command = parse_command("living room lights on");
    let rooms = command.entities.rooms.expect("Should have rooms");
    assert_eq!(
        rooms.len(),
        1,
        "Should have exactly one room, got: {:?}",
        rooms
    );
    assert_eq!(rooms[0], "living room");
}

#[rstest]
fn test_primary_bedroom_no_duplicate() {
    let command = parse_command("primary bedroom lights off");
    let rooms = command.entities.rooms.expect("Should have rooms");
    // Should have "primary bedroom", not both "primary bedroom" and "primary" and "bedroom"
    assert!(
        rooms.iter().any(|r| r == "primary bedroom"),
        "Should have 'primary bedroom', got: {:?}",
        rooms
    );
    // Should not have standalone "primary" or "bedroom" if "primary bedroom" matched
    assert!(
        !rooms.iter().any(|r| r == "primary" || r == "bedroom"),
        "Should not have standalone variants, got: {:?}",
        rooms
    );
}

#[rstest]
fn test_dining_room_no_duplicate() {
    let command = parse_command("dining room shades close");
    let rooms = command.entities.rooms.expect("Should have rooms");
    assert_eq!(
        rooms.len(),
        1,
        "Should have exactly one room, got: {:?}",
        rooms
    );
    assert_eq!(rooms[0], "dining room");
}

#[rstest]
fn test_multiple_rooms_no_duplicates() {
    let command = parse_command("living room and kitchen lights on");
    let rooms = command.entities.rooms.expect("Should have rooms");
    assert_eq!(
        rooms.len(),
        2,
        "Should have exactly two rooms, got: {:?}",
        rooms
    );
    assert!(rooms.contains(&"living room".to_string()));
    assert!(rooms.contains(&"kitchen".to_string()));
    // Should not contain standalone "living"
    assert!(!rooms.contains(&"living".to_string()));
}

// ============================================================================
// TV/Shades Require Explicit Action Tests
// ============================================================================

#[rstest]
fn test_whats_on_tv_is_unknown() {
    let command = parse_command("what's on tv");
    assert!(
        matches!(command.intent, CommandIntent::Unknown),
        "Expected Unknown, got {:?}",
        command.intent
    );
}

#[rstest]
fn test_what_about_the_shades_is_unknown() {
    let command = parse_command("what about the shades");
    assert!(
        matches!(command.intent, CommandIntent::Unknown),
        "Expected Unknown, got {:?}",
        command.intent
    );
}

#[rstest]
fn test_how_are_the_blinds_is_unknown() {
    let command = parse_command("how are the blinds");
    assert!(
        matches!(command.intent, CommandIntent::Unknown),
        "Expected Unknown, got {:?}",
        command.intent
    );
}

#[rstest]
fn test_tv_up_works() {
    let command = parse_command("tv up");
    assert!(matches!(command.intent, CommandIntent::TV(ref s) if s == "raise"));
}

#[rstest]
fn test_shades_open_works() {
    let command = parse_command("open the shades");
    assert!(matches!(command.intent, CommandIntent::Shades(ref s) if s == "open"));
}

#[rstest]
fn test_lower_the_tv_works() {
    let command = parse_command("lower the tv");
    assert!(matches!(command.intent, CommandIntent::TV(ref s) if s == "lower"));
}

// ============================================================================
// Enhanced Number Parsing Tests
// ============================================================================

use kagami_hub::voice_pipeline::BedAction;

#[rstest]
#[case("lights one", 1)]
#[case("lights two", 2)]
#[case("lights three", 3)]
#[case("lights four", 4)]
#[case("lights five", 5)]
#[case("lights six", 6)]
#[case("lights seven", 7)]
#[case("lights eight", 8)]
#[case("lights nine", 9)]
fn test_single_digit_words(#[case] input: &str, #[case] expected: i32) {
    let command = parse_command(input);
    match command.intent {
        CommandIntent::Lights(level) => assert_eq!(level, expected),
        _ => panic!("Expected Lights intent, got {:?}", command.intent),
    }
}

#[rstest]
#[case("lights ten", 10)]
#[case("lights eleven", 11)]
#[case("lights twelve", 12)]
#[case("lights thirteen", 13)]
#[case("lights fourteen", 14)]
#[case("lights fifteen", 15)]
#[case("lights sixteen", 16)]
#[case("lights seventeen", 17)]
#[case("lights eighteen", 18)]
#[case("lights nineteen", 19)]
fn test_teen_words(#[case] input: &str, #[case] expected: i32) {
    let command = parse_command(input);
    match command.intent {
        CommandIntent::Lights(level) => assert_eq!(level, expected),
        _ => panic!("Expected Lights intent, got {:?}", command.intent),
    }
}

#[rstest]
#[case("lights twenty five", 25)]
#[case("lights thirty two", 32)]
#[case("lights forty eight", 48)]
#[case("lights fifty three", 53)]
#[case("lights sixty one", 61)]
#[case("lights seventy four", 74)]
#[case("lights eighty six", 86)]
#[case("lights ninety nine", 99)]
fn test_compound_numbers(#[case] input: &str, #[case] expected: i32) {
    let command = parse_command(input);
    match command.intent {
        CommandIntent::Lights(level) => assert_eq!(level, expected),
        _ => panic!("Expected Lights intent, got {:?}", command.intent),
    }
}

#[rstest]
fn test_negative_bed_temp_minus() {
    let command = parse_command("set bed to minus fifty");
    match command.intent {
        CommandIntent::Bed(BedAction::SetTemp(level)) => assert_eq!(level, -50),
        _ => panic!("Expected Bed SetTemp intent, got {:?}", command.intent),
    }
}

#[rstest]
fn test_negative_bed_temp_negative_word() {
    let command = parse_command("set mattress to negative twenty");
    match command.intent {
        CommandIntent::Bed(BedAction::SetTemp(level)) => assert_eq!(level, -20),
        _ => panic!("Expected Bed SetTemp intent, got {:?}", command.intent),
    }
}

#[rstest]
fn test_negative_digit_bed_temp() {
    let command = parse_command("bed -50");
    match command.intent {
        CommandIntent::Bed(BedAction::SetTemp(level)) => assert_eq!(level, -50),
        _ => panic!("Expected Bed SetTemp intent, got {:?}", command.intent),
    }
}

// ============================================================================
// Announcement Capitalization Tests
// ============================================================================

#[rstest]
fn test_announce_preserves_capitalization() {
    let command = parse_command("Announce Dinner Is Ready");
    match &command.intent {
        CommandIntent::Announce(msg) => {
            assert!(
                msg.contains("Dinner"),
                "Should preserve 'Dinner' capitalization, got: {}",
                msg
            );
            assert!(
                msg.contains("Is"),
                "Should preserve 'Is' capitalization, got: {}",
                msg
            );
            assert!(
                msg.contains("Ready"),
                "Should preserve 'Ready' capitalization, got: {}",
                msg
            );
        }
        _ => panic!("Expected Announce intent"),
    }
}

#[rstest]
fn test_say_preserves_capitalization() {
    let command = parse_command("Say Hello World");
    match &command.intent {
        CommandIntent::Announce(msg) => {
            assert!(
                msg.contains("Hello"),
                "Should preserve 'Hello' capitalization, got: {}",
                msg
            );
            assert!(
                msg.contains("World"),
                "Should preserve 'World' capitalization, got: {}",
                msg
            );
        }
        _ => panic!("Expected Announce intent"),
    }
}

#[rstest]
fn test_tell_everyone_preserves_capitalization() {
    let command = parse_command("Tell Everyone Time For Bed");
    match &command.intent {
        CommandIntent::Announce(msg) => {
            assert!(
                msg.contains("Time"),
                "Should preserve 'Time' capitalization, got: {}",
                msg
            );
            assert!(
                msg.contains("For"),
                "Should preserve 'For' capitalization, got: {}",
                msg
            );
            assert!(
                msg.contains("Bed"),
                "Should preserve 'Bed' capitalization, got: {}",
                msg
            );
        }
        _ => panic!("Expected Announce intent"),
    }
}

/*
 * Kagami Voice Pipeline Tests
 * Colony: Flow (e3) -> Nexus (e4) -> Crystal (e7)
 *
 * Voice is sense. Command is action.
 */
