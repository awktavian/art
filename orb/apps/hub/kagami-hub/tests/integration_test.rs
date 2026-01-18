//! Integration Tests - Full Voice Command Flow
//!
//! Tests the complete pipeline from voice command parsing through
//! API execution and feedback generation.
//!
//! Colony: Flow (e3) -> Nexus (e4) -> Crystal (e7)

use pretty_assertions::assert_eq;
use rstest::*;
use std::time::Duration;
use wiremock::{
    matchers::{method, path},
    Mock, MockServer, ResponseTemplate,
};

use kagami_hub::api_client::KagamiAPI;
use kagami_hub::config::LEDRingConfig;
use kagami_hub::feedback::FeedbackGenerator;
use kagami_hub::led_ring::{AnimationPattern, LEDRing, CRYSTAL};
use kagami_hub::voice_pipeline::{parse_command, CommandIntent};

// ============================================================================
// End-to-End Voice Command Flow Tests
// ============================================================================

/// Test the complete flow: Voice -> Parse -> API -> Feedback
#[rstest]
#[tokio::test]
async fn test_movie_mode_voice_flow() {
    // 1. Set up mock API server
    let mock_server = MockServer::start().await;

    Mock::given(method("POST"))
        .and(path("/home/movie-mode/enter"))
        .respond_with(ResponseTemplate::new(200))
        .expect(1)
        .mount(&mock_server)
        .await;

    // 2. Parse voice command
    let voice_input = "activate movie mode";
    let command = parse_command(voice_input);

    // 3. Verify intent was parsed correctly
    match &command.intent {
        CommandIntent::Scene(scene) => {
            assert_eq!(scene, "movie_mode");
        }
        _ => panic!("Expected Scene intent"),
    }

    // 4. Execute API call
    let api = KagamiAPI::new(&mock_server.uri());
    let result = api.execute_scene("movie_mode").await;
    assert!(result.is_ok(), "API call should succeed");

    // 5. Generate feedback
    let confirmation = FeedbackGenerator::confirmation_for(&command.intent);
    assert!(
        confirmation.contains("Movie mode"),
        "Confirmation should mention movie mode"
    );
}

/// Test goodnight sequence: Parse -> API -> Safety feedback
#[rstest]
#[tokio::test]
async fn test_goodnight_voice_flow() {
    let mock_server = MockServer::start().await;

    Mock::given(method("POST"))
        .and(path("/home/goodnight"))
        .respond_with(ResponseTemplate::new(200))
        .expect(1)
        .mount(&mock_server)
        .await;

    let voice_input = "goodnight";
    let command = parse_command(voice_input);

    assert!(matches!(command.intent, CommandIntent::Scene(ref s) if s == "goodnight"));

    let api = KagamiAPI::new(&mock_server.uri());
    let result = api.execute_scene("goodnight").await;
    assert!(result.is_ok());

    // Generate safety summary
    let summary = FeedbackGenerator::goodnight_summary(true, true, true);
    assert!(summary.contains("secure"));
}

/// Test lights control flow
#[rstest]
#[tokio::test]
async fn test_lights_voice_flow() {
    let mock_server = MockServer::start().await;

    Mock::given(method("POST"))
        .and(path("/home/lights/set"))
        .respond_with(ResponseTemplate::new(200))
        .expect(1)
        .mount(&mock_server)
        .await;

    let voice_input = "set the living room lights to 50";
    let command = parse_command(voice_input);

    match &command.intent {
        CommandIntent::Lights(level) => {
            assert_eq!(*level, 50);
        }
        _ => panic!("Expected Lights intent"),
    }

    assert!(command.entities.rooms.is_some());

    let api = KagamiAPI::new(&mock_server.uri());
    let result = api.set_lights(50, command.entities.rooms).await;
    assert!(result.is_ok());

    let confirmation = FeedbackGenerator::confirmation_for(&command.intent);
    assert!(confirmation.contains("50%"));
}

/// Test fireplace control flow
#[rstest]
#[tokio::test]
async fn test_fireplace_voice_flow() {
    let mock_server = MockServer::start().await;

    Mock::given(method("POST"))
        .and(path("/home/fireplace/on"))
        .respond_with(ResponseTemplate::new(200))
        .expect(1)
        .mount(&mock_server)
        .await;

    let voice_input = "turn on the fireplace";
    let command = parse_command(voice_input);

    assert!(matches!(command.intent, CommandIntent::Fireplace(true)));

    let api = KagamiAPI::new(&mock_server.uri());
    let result = api.fireplace(true).await;
    assert!(result.is_ok());

    let confirmation = FeedbackGenerator::confirmation_for(&command.intent);
    assert!(confirmation.contains("Fireplace on"));
}

// ============================================================================
// LED Ring Integration with Voice Pipeline
// ============================================================================

/// Test LED ring states match voice pipeline states
#[rstest]
fn test_led_ring_pipeline_state_mapping() {
    let config = LEDRingConfig {
        enabled: true,
        count: 7,
        pin: 18,
        brightness: 1.0,
        animation_speed: 1.0,
    };
    let mut ring = LEDRing::new(&config).unwrap();

    // Idle state -> Breathing
    ring.set_pattern(AnimationPattern::Breathing);
    assert_eq!(ring.pattern(), AnimationPattern::Breathing);

    // Listening state -> Pulse (Flow color)
    ring.pulse_listening();
    assert_eq!(ring.pattern(), AnimationPattern::Pulse);

    // Processing state -> Spin
    ring.set_pattern(AnimationPattern::Spin);
    assert_eq!(ring.pattern(), AnimationPattern::Spin);

    // Executing state -> Cascade
    ring.set_pattern(AnimationPattern::Cascade);
    assert_eq!(ring.pattern(), AnimationPattern::Cascade);

    // Speaking state -> Highlight Crystal
    ring.highlight_colony(CRYSTAL);
    assert_eq!(ring.pattern(), AnimationPattern::Highlight(CRYSTAL));

    // Error state -> ErrorFlash
    ring.show_error();
    assert_eq!(ring.pattern(), AnimationPattern::ErrorFlash);

    // Success state -> Flash
    ring.show_success();
    assert_eq!(ring.pattern(), AnimationPattern::Flash);
}

// ============================================================================
// Error Handling Flow Tests
// ============================================================================

/// Test error handling when API fails
#[rstest]
#[tokio::test]
async fn test_api_error_generates_correct_feedback() {
    let mock_server = MockServer::start().await;

    Mock::given(method("POST"))
        .and(path("/home/movie-mode/enter"))
        .respond_with(ResponseTemplate::new(500))
        .expect(1)
        .mount(&mock_server)
        .await;

    let voice_input = "movie mode";
    let command = parse_command(voice_input);

    let api = KagamiAPI::new(&mock_server.uri());
    let result = api.execute_scene("movie_mode").await;

    assert!(result.is_err(), "API should fail on 500");

    // Generate error feedback
    let error_msg = FeedbackGenerator::error_for(&command.intent, "500 Internal Server Error");
    assert!(error_msg.contains("Could not"));
    assert!(error_msg.contains("Server error"));
}

/// Test timeout error handling
#[rstest]
#[tokio::test]
async fn test_timeout_error_feedback() {
    let command = parse_command("lights on");

    let error_msg = FeedbackGenerator::error_for(&command.intent, "request timeout");
    assert!(error_msg.contains("timed out"));
}

/// Test authentication error handling
#[rstest]
#[tokio::test]
async fn test_auth_error_feedback() {
    let command = parse_command("fireplace on");

    let error_msg = FeedbackGenerator::error_for(&command.intent, "401 Unauthorized");
    assert!(error_msg.contains("Not authorized"));
}

// ============================================================================
// Safety Status Flow Tests
// ============================================================================

/// Test safety status announcement flow
#[rstest]
fn test_safety_status_flow() {
    let config = LEDRingConfig {
        enabled: true,
        count: 7,
        pin: 18,
        brightness: 1.0,
        animation_speed: 1.0,
    };
    let mut ring = LEDRing::new(&config).unwrap();

    // Test safe status (h_x >= 0.5)
    ring.set_safety_status(1.0);
    let announcement = FeedbackGenerator::status_announcement(1.0, true);
    assert!(announcement.contains("connected"));
    assert!(announcement.contains("safe"));

    // Test caution status (0 <= h_x < 0.5)
    ring.set_safety_status(0.25);
    let announcement = FeedbackGenerator::status_announcement(0.25, true);
    assert!(announcement.contains("Caution"));

    // Test violation status (h_x < 0)
    ring.set_safety_status(-0.5);
    let announcement = FeedbackGenerator::status_announcement(-0.5, true);
    assert!(announcement.contains("alert"));
}

// ============================================================================
// Complete Command Sequence Tests
// ============================================================================

/// Test a typical evening sequence
#[rstest]
#[tokio::test]
async fn test_evening_sequence() {
    let mock_server = MockServer::start().await;

    // Set up all expected API calls
    Mock::given(method("POST"))
        .and(path("/home/movie-mode/enter"))
        .respond_with(ResponseTemplate::new(200))
        .mount(&mock_server)
        .await;

    Mock::given(method("POST"))
        .and(path("/home/lights/set"))
        .respond_with(ResponseTemplate::new(200))
        .mount(&mock_server)
        .await;

    Mock::given(method("POST"))
        .and(path("/home/shades/close"))
        .respond_with(ResponseTemplate::new(200))
        .mount(&mock_server)
        .await;

    Mock::given(method("POST"))
        .and(path("/home/fireplace/on"))
        .respond_with(ResponseTemplate::new(200))
        .mount(&mock_server)
        .await;

    let api = KagamiAPI::new(&mock_server.uri());

    // Sequence of commands
    let sequence = vec![
        "movie mode",
        "dim the lights",
        "close the shades",
        "fireplace on",
    ];

    for voice_input in sequence {
        let command = parse_command(voice_input);
        assert!(
            !matches!(command.intent, CommandIntent::Unknown),
            "Command '{}' should be recognized",
            voice_input
        );

        // Execute based on intent
        let result = match &command.intent {
            CommandIntent::Scene(scene) => api.execute_scene(scene).await,
            CommandIntent::Lights(level) => api.set_lights(*level, None).await,
            CommandIntent::Shades(action) => api.shades(action, None).await,
            CommandIntent::Fireplace(on) => api.fireplace(*on).await,
            _ => Ok(()),
        };

        assert!(result.is_ok(), "Command '{}' should execute", voice_input);
    }
}

/// Test bedtime sequence
#[rstest]
#[tokio::test]
async fn test_bedtime_sequence() {
    let mock_server = MockServer::start().await;

    Mock::given(method("POST"))
        .and(path("/home/goodnight"))
        .respond_with(ResponseTemplate::new(200))
        .mount(&mock_server)
        .await;

    Mock::given(method("POST"))
        .and(path("/home/fireplace/off"))
        .respond_with(ResponseTemplate::new(200))
        .mount(&mock_server)
        .await;

    let api = KagamiAPI::new(&mock_server.uri());

    // Parse and execute goodnight
    let command = parse_command("goodnight");
    api.execute_scene("goodnight").await.unwrap();

    // Verify safety summary
    let summary = FeedbackGenerator::goodnight_summary(true, true, true);
    assert!(summary.contains("Goodnight"));
    assert!(summary.contains("secure"));
}

// ============================================================================
// Feedback Verification Tests
// ============================================================================

/// Test all feedback messages are generated correctly
#[rstest]
fn test_feedback_completeness() {
    // Test all command intents generate feedback
    let intents = vec![
        CommandIntent::Scene("movie_mode".to_string()),
        CommandIntent::Scene("goodnight".to_string()),
        CommandIntent::Scene("welcome_home".to_string()),
        CommandIntent::Lights(0),
        CommandIntent::Lights(50),
        CommandIntent::Lights(100),
        CommandIntent::Fireplace(true),
        CommandIntent::Fireplace(false),
        CommandIntent::Shades("open".to_string()),
        CommandIntent::Shades("close".to_string()),
        CommandIntent::TV("raise".to_string()),
        CommandIntent::TV("lower".to_string()),
        CommandIntent::Announce("test message".to_string()),
        CommandIntent::Unknown,
    ];

    for intent in intents {
        let confirmation = FeedbackGenerator::confirmation_for(&intent);
        assert!(
            !confirmation.is_empty(),
            "Confirmation for {:?} should not be empty",
            intent
        );

        let error = FeedbackGenerator::error_for(&intent, "test error");
        assert!(
            !error.is_empty(),
            "Error message for {:?} should not be empty",
            intent
        );
    }
}

// ============================================================================
// Concurrent Command Tests
// ============================================================================

/// Test handling multiple commands rapidly
#[rstest]
#[tokio::test]
async fn test_rapid_command_sequence() {
    let mock_server = MockServer::start().await;

    Mock::given(method("POST"))
        .respond_with(ResponseTemplate::new(200))
        .mount(&mock_server)
        .await;

    let api = KagamiAPI::new(&mock_server.uri());

    // Send multiple commands concurrently
    let commands = vec![
        "lights on",
        "lights off",
        "lights dim",
        "lights half",
        "lights full",
    ];

    let handles: Vec<_> = commands
        .iter()
        .map(|cmd| {
            let api_clone = KagamiAPI::new(&mock_server.uri());
            let command = parse_command(cmd);
            tokio::spawn(async move {
                if let CommandIntent::Lights(level) = command.intent {
                    api_clone.set_lights(level, None).await
                } else {
                    Ok(())
                }
            })
        })
        .collect();

    // All should complete
    for handle in handles {
        let result = handle.await.unwrap();
        assert!(result.is_ok());
    }
}

/*
 * Kagami Integration Tests
 * Colony: Flow (e3) -> Nexus (e4) -> Crystal (e7)
 *
 * Voice -> Parse -> Execute -> Feedback
 */
