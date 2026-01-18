//! API Client Tests with HTTP Mocking (wiremock)
//!
//! Tests the KagamiAPI client against mocked HTTP endpoints.
//! Follows patterns from feedback.rs tests.
//!
//! Colony: Crystal (e7) - Verification through testing

use pretty_assertions::assert_eq;
use rstest::*;
use wiremock::{
    matchers::{body_json, method, path},
    Mock, MockServer, ResponseTemplate,
};

// Re-export the main crate for testing
// Note: In integration tests, the crate is available as `kagami_hub`
use kagami_hub::api_client::{HealthResponse, KagamiAPI};

// ============================================================================
// Health Check Tests
// ============================================================================

#[rstest]
#[tokio::test]
async fn test_health_check_success() {
    let mock_server = MockServer::start().await;

    Mock::given(method("GET"))
        .and(path("/health"))
        .respond_with(ResponseTemplate::new(200).set_body_json(serde_json::json!({
            "status": "healthy",
            "h_x": 1.0,
            "uptime_ms": 12345
        })))
        .mount(&mock_server)
        .await;

    let api = KagamiAPI::new(&mock_server.uri());
    let health = api.health().await.expect("Health check should succeed");

    assert_eq!(health.status, "healthy");
    assert_eq!(health.safety_score, Some(1.0));
    assert_eq!(health.uptime_ms, Some(12345));
}

#[rstest]
#[tokio::test]
async fn test_health_check_minimal_response() {
    let mock_server = MockServer::start().await;

    Mock::given(method("GET"))
        .and(path("/health"))
        .respond_with(ResponseTemplate::new(200).set_body_json(serde_json::json!({
            "status": "ok"
        })))
        .mount(&mock_server)
        .await;

    let api = KagamiAPI::new(&mock_server.uri());
    let health = api.health().await.expect("Health check should succeed");

    assert_eq!(health.status, "ok");
    assert_eq!(health.safety_score, None);
    assert_eq!(health.uptime_ms, None);
}

#[rstest]
#[tokio::test]
async fn test_health_check_server_error() {
    let mock_server = MockServer::start().await;

    Mock::given(method("GET"))
        .and(path("/health"))
        .respond_with(ResponseTemplate::new(500))
        .mount(&mock_server)
        .await;

    let api = KagamiAPI::new(&mock_server.uri());
    let result = api.health().await;

    assert!(result.is_err(), "Health check should fail on 500");
}

#[rstest]
#[tokio::test]
async fn test_health_check_connection_error() {
    // Use an invalid URL to simulate connection failure
    let api = KagamiAPI::new("http://localhost:59999");
    let result = api.health().await;

    assert!(
        result.is_err(),
        "Health check should fail on connection error"
    );
}

// ============================================================================
// Scene Execution Tests
// ============================================================================

#[rstest]
#[case("movie_mode", "/home/movie-mode/enter")]
#[case("goodnight", "/home/goodnight")]
#[case("welcome_home", "/home/welcome-home")]
#[tokio::test]
async fn test_execute_scene_success(#[case] scene: &str, #[case] expected_path: &str) {
    let mock_server = MockServer::start().await;

    Mock::given(method("POST"))
        .and(path(expected_path))
        .respond_with(ResponseTemplate::new(200))
        .expect(1)
        .mount(&mock_server)
        .await;

    let api = KagamiAPI::new(&mock_server.uri());
    let result = api.execute_scene(scene).await;

    assert!(result.is_ok(), "Scene execution should succeed");
}

#[rstest]
#[tokio::test]
async fn test_execute_unknown_scene() {
    let mock_server = MockServer::start().await;
    let api = KagamiAPI::new(&mock_server.uri());

    let result = api.execute_scene("unknown_scene").await;

    assert!(result.is_err(), "Unknown scene should return error");
    assert!(
        result.unwrap_err().to_string().contains("Unknown scene"),
        "Error should mention unknown scene"
    );
}

#[rstest]
#[tokio::test]
async fn test_execute_scene_server_error() {
    let mock_server = MockServer::start().await;

    Mock::given(method("POST"))
        .and(path("/home/movie-mode/enter"))
        .respond_with(ResponseTemplate::new(503))
        .mount(&mock_server)
        .await;

    let api = KagamiAPI::new(&mock_server.uri());
    let result = api.execute_scene("movie_mode").await;

    assert!(result.is_err(), "Scene execution should fail on 503");
}

// ============================================================================
// Lights Control Tests
// ============================================================================

#[rstest]
#[case(0, None)]
#[case(50, None)]
#[case(100, None)]
#[case(75, Some(vec!["Living Room".to_string()]))]
#[tokio::test]
async fn test_set_lights(#[case] level: i32, #[case] rooms: Option<Vec<String>>) {
    let mock_server = MockServer::start().await;

    Mock::given(method("POST"))
        .and(path("/home/lights/set"))
        .respond_with(ResponseTemplate::new(200))
        .expect(1)
        .mount(&mock_server)
        .await;

    let api = KagamiAPI::new(&mock_server.uri());
    let result = api.set_lights(level, rooms).await;

    assert!(result.is_ok(), "Set lights should succeed");
}

// ============================================================================
// Fireplace Control Tests
// ============================================================================

#[rstest]
#[case(true, "/home/fireplace/on")]
#[case(false, "/home/fireplace/off")]
#[tokio::test]
async fn test_fireplace_control(#[case] on: bool, #[case] expected_path: &str) {
    let mock_server = MockServer::start().await;

    Mock::given(method("POST"))
        .and(path(expected_path))
        .respond_with(ResponseTemplate::new(200))
        .expect(1)
        .mount(&mock_server)
        .await;

    let api = KagamiAPI::new(&mock_server.uri());
    let result = api.fireplace(on).await;

    assert!(result.is_ok(), "Fireplace control should succeed");
}

// ============================================================================
// Shades Control Tests
// ============================================================================

#[rstest]
#[case("open", None)]
#[case("close", None)]
#[case("open", Some(vec!["Primary Bedroom".to_string()]))]
#[tokio::test]
async fn test_shades_control(#[case] action: &str, #[case] rooms: Option<Vec<String>>) {
    let mock_server = MockServer::start().await;

    Mock::given(method("POST"))
        .and(path(format!("/home/shades/{}", action)))
        .respond_with(ResponseTemplate::new(200))
        .expect(1)
        .mount(&mock_server)
        .await;

    let api = KagamiAPI::new(&mock_server.uri());
    let result = api.shades(action, rooms).await;

    assert!(result.is_ok(), "Shades control should succeed");
}

// ============================================================================
// TV Control Tests
// ============================================================================

#[rstest]
#[case("raise")]
#[case("lower")]
#[tokio::test]
async fn test_tv_control(#[case] action: &str) {
    let mock_server = MockServer::start().await;

    Mock::given(method("POST"))
        .and(path(format!("/home/tv/{}", action)))
        .respond_with(ResponseTemplate::new(200))
        .expect(1)
        .mount(&mock_server)
        .await;

    let api = KagamiAPI::new(&mock_server.uri());
    let result = api.tv(action).await;

    assert!(result.is_ok(), "TV control should succeed");
}

// ============================================================================
// Announce Tests
// ============================================================================

#[rstest]
#[tokio::test]
async fn test_announce_all_rooms() {
    let mock_server = MockServer::start().await;

    Mock::given(method("POST"))
        .and(path("/home/announce"))
        .respond_with(ResponseTemplate::new(200))
        .expect(1)
        .mount(&mock_server)
        .await;

    let api = KagamiAPI::new(&mock_server.uri());
    let result = api.announce("Dinner is ready", None, None).await;

    assert!(result.is_ok(), "Announce should succeed");
}

#[rstest]
#[tokio::test]
async fn test_announce_specific_rooms() {
    let mock_server = MockServer::start().await;

    Mock::given(method("POST"))
        .and(path("/home/announce"))
        .respond_with(ResponseTemplate::new(200))
        .expect(1)
        .mount(&mock_server)
        .await;

    let api = KagamiAPI::new(&mock_server.uri());
    let result = api
        .announce(
            "Movie starting",
            Some(vec!["Living Room".to_string()]),
            Some("kagami"),
        )
        .await;

    assert!(result.is_ok(), "Announce should succeed");
}

// ============================================================================
// Timeout and Retry Tests
// ============================================================================

#[rstest]
#[tokio::test]
async fn test_request_timeout() {
    let mock_server = MockServer::start().await;

    Mock::given(method("GET"))
        .and(path("/health"))
        .respond_with(
            ResponseTemplate::new(200)
                .set_body_json(serde_json::json!({"status": "ok"}))
                .set_delay(std::time::Duration::from_secs(15)), // Longer than timeout
        )
        .mount(&mock_server)
        .await;

    let api = KagamiAPI::new(&mock_server.uri());
    let result = api.health().await;

    assert!(result.is_err(), "Request should timeout");
}

// ============================================================================
// Edge Cases
// ============================================================================

#[rstest]
#[tokio::test]
async fn test_empty_response_body() {
    let mock_server = MockServer::start().await;

    Mock::given(method("POST"))
        .and(path("/home/goodnight"))
        .respond_with(ResponseTemplate::new(204)) // No content
        .mount(&mock_server)
        .await;

    let api = KagamiAPI::new(&mock_server.uri());
    let result = api.execute_scene("goodnight").await;

    assert!(result.is_ok(), "Empty response should be OK");
}

#[rstest]
#[tokio::test]
async fn test_malformed_json_response() {
    let mock_server = MockServer::start().await;

    Mock::given(method("GET"))
        .and(path("/health"))
        .respond_with(ResponseTemplate::new(200).set_body_string("not json"))
        .mount(&mock_server)
        .await;

    let api = KagamiAPI::new(&mock_server.uri());
    let result = api.health().await;

    assert!(result.is_err(), "Malformed JSON should fail");
}

/*
 * Kagami API Client Tests
 * Colony: Crystal (e7) - Verification through HTTP mocking
 */
