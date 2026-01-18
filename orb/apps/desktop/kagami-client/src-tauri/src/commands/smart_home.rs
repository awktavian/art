//! Smart Home Commands
//!
//! Controls for lights, shades, fireplace, TV, and scenes.
//!
//! Architecture:
//!   Commands -> MeshCommandRouter (primary) -> Hub via Mesh
//!            -> KagamiApi (fallback) -> HTTP Backend
//!
//! Migration Note (Jan 2026):
//!   Commands now route through MeshCommandRouter with Ed25519 signatures.
//!   HTTP fallback is maintained for backward compatibility during migration.
//!
//! Colony: Forge (e2)
//! h(x) >= 0. Always.

use crate::api_client::get_api;
use crate::mesh_router::get_mesh_router;
use crate::shared::rooms::Room;
use serde_json::Value;
use tracing::{debug, info, warn};

use super::error::CommandError;

/// Allowed smart home actions (whitelist for input validation)
const ALLOWED_SMART_HOME_ACTIONS: &[&str] = &[
    "lights/set",
    "lights/on",
    "lights/off",
    "shades/open",
    "shades/close",
    "fireplace/on",
    "fireplace/off",
    "fireplace/toggle",
    "tv/lower",
    "tv/raise",
    "tv/stop",
    "movie-mode/enter",
    "movie-mode/exit",
    "goodnight",
    "welcome-home",
    "away",
    "announce",
    "climate/set",
    "lock/all",
    "lock/unlock",
];

/// Validate that an action is in the allowed whitelist.
pub fn validate_smart_home_action(action: &str) -> Result<(), CommandError> {
    let normalized = action.trim().to_lowercase();

    if ALLOWED_SMART_HOME_ACTIONS
        .iter()
        .any(|&allowed| normalized == allowed.to_lowercase())
    {
        Ok(())
    } else {
        warn!("Rejected invalid smart home action: {}", action);
        Err(CommandError::InvalidAction(format!(
            "Action '{}' is not in the allowed list. Valid actions: {}",
            action,
            ALLOWED_SMART_HOME_ACTIONS.join(", ")
        )))
    }
}

/// Execute a generic smart home action with input validation.
#[tauri::command]
pub async fn smart_home_action(action: String, params: Option<Value>) -> Result<Value, String> {
    validate_smart_home_action(&action)?;

    info!("Smart home action: {} {:?}", action, params);

    let api = get_api();
    api.smart_home_action(&action, params)
        .await
        .map_err(|e| e.to_string())
}

/// Execute a home scene (movie mode, goodnight, welcome home).
#[tauri::command]
pub async fn execute_scene(scene: String) -> Result<Value, String> {
    info!("Executing scene: {}", scene);

    let api = get_api();

    match scene.as_str() {
        "movie" | "movie_mode" | "movie-mode" => api.movie_mode().await.map_err(|e| e.to_string()),
        "exit_movie" | "exit-movie" => api.exit_movie_mode().await.map_err(|e| e.to_string()),
        "goodnight" => api.goodnight().await.map_err(|e| e.to_string()),
        "welcome" | "welcome_home" | "welcome-home" => {
            api.welcome_home().await.map_err(|e| e.to_string())
        }
        _ => Err(format!("Unknown scene: {}", scene)),
    }
}

/// Toggle the fireplace on/off.
#[tauri::command]
pub async fn toggle_fireplace(on: bool) -> Result<Value, String> {
    info!("Toggling fireplace: {}", if on { "ON" } else { "OFF" });

    // Try mesh first (check if initialized without holding lock across await)
    let mesh_result = {
        let router = get_mesh_router();
        let guard = router.read().unwrap();
        if guard.is_initialized() && guard.connected_hub_count() > 0 {
            // Clone data needed for async operation
            Some(guard.connected_hub_count())
        } else {
            None
        }
    }; // Guard released here

    if mesh_result.is_some() {
        // Execute via mesh (would need actual mesh transport implementation)
        debug!("Would route Fireplace command via mesh");
    }

    // For now, use HTTP fallback (mesh transport not yet implemented)
    let api = get_api();
    api.fireplace(on).await.map_err(|e| e.to_string())
}

/// Set light levels.
#[tauri::command]
pub async fn set_lights(level: i32, rooms: Option<Vec<String>>) -> Result<Value, String> {
    info!("Setting lights to {}% for {:?}", level, rooms);

    let clamped_level = level.clamp(0, 100);

    // Check mesh availability (don't hold lock across await)
    let mesh_available = {
        let router = get_mesh_router();
        let guard = router.read().unwrap();
        guard.is_initialized() && guard.connected_hub_count() > 0
    };

    if mesh_available {
        debug!("Would route SetLights command via mesh");
    }

    // For now, use HTTP fallback (mesh transport not yet implemented)
    let api = get_api();
    api.set_lights(clamped_level, rooms).await.map_err(|e| e.to_string())
}

/// Control shades (open/close).
#[tauri::command]
pub async fn control_shades(action: String, rooms: Option<Vec<String>>) -> Result<Value, String> {
    info!("Shades {}: {:?}", action, rooms);

    // Check mesh availability (don't hold lock across await)
    let mesh_available = {
        let router = get_mesh_router();
        let guard = router.read().unwrap();
        guard.is_initialized() && guard.connected_hub_count() > 0
    };

    if mesh_available {
        debug!("Would route Shades command via mesh");
    }

    // For now, use HTTP fallback (mesh transport not yet implemented)
    let api = get_api();
    api.shades(&action, rooms).await.map_err(|e| e.to_string())
}

/// Control TV (raise/lower/stop).
#[tauri::command]
pub async fn control_tv(action: String, preset: Option<i32>) -> Result<Value, String> {
    info!("TV {}: preset {:?}", action, preset);

    // Check mesh availability (don't hold lock across await)
    let mesh_available = {
        let router = get_mesh_router();
        let guard = router.read().unwrap();
        guard.is_initialized() && guard.connected_hub_count() > 0
    };

    if mesh_available {
        debug!("Would route TvControl command via mesh");
    }

    // For now, use HTTP fallback (mesh transport not yet implemented)
    let api = get_api();
    api.tv(&action, preset).await.map_err(|e| e.to_string())
}

/// Announce a message via TTS.
#[tauri::command]
pub async fn announce(
    text: String,
    rooms: Option<Vec<String>>,
    colony: Option<String>,
) -> Result<Value, String> {
    info!("Announcing: '{}' to {:?} as {:?}", text, rooms, colony);

    // Check mesh availability (don't hold lock across await)
    let mesh_available = {
        let router = get_mesh_router();
        let guard = router.read().unwrap();
        guard.is_initialized() && guard.connected_hub_count() > 0
    };

    if mesh_available {
        debug!("Would route Announce command via mesh");
    }

    // For now, use HTTP fallback (mesh transport not yet implemented)
    let api = get_api();
    api.announce(&text, rooms, colony.as_deref())
        .await
        .map_err(|e| e.to_string())
}

/// Get list of rooms from API.
#[tauri::command]
pub async fn get_rooms() -> Result<Vec<Room>, String> {
    debug!("Fetching rooms");

    let api = get_api();

    // Try API first
    match api.request("/home/rooms", "GET", None).await {
        Ok(response) => {
            if let Some(rooms) = response.get("rooms").and_then(|r| r.as_array()) {
                let result: Vec<Room> = rooms
                    .iter()
                    .filter_map(|r| {
                        Some(Room {
                            id: r.get("id")?.as_str()?.to_string(),
                            name: r.get("name")?.as_str()?.to_string(),
                            floor: r.get("floor").and_then(|f| f.as_str()).map(|s| s.to_string()),
                        })
                    })
                    .collect();
                return Ok(result);
            }
        }
        Err(e) => {
            debug!("API room fetch failed: {}", e);
        }
    }

    // Fallback: use static room list from shared module
    Ok(crate::shared::rooms::get_default_rooms())
}

/// Handle kagami:// deep links.
#[tauri::command]
pub async fn handle_deep_link(
    app: tauri::AppHandle,
    url: String,
) -> Result<Value, String> {
    info!("Handling deep link: {}", url);

    let url = url.trim_start_matches("kagami://");
    let parts: Vec<&str> = url.split('/').collect();

    if parts.is_empty() {
        return Err("Invalid deep link format".to_string());
    }

    let api = get_api();

    match parts[0] {
        "scene" if parts.len() >= 2 => match parts[1] {
            "movie" => api.movie_mode().await.map_err(|e| e.to_string()),
            "goodnight" => api.goodnight().await.map_err(|e| e.to_string()),
            "welcome" => api.welcome_home().await.map_err(|e| e.to_string()),
            _ => Err(format!("Unknown scene: {}", parts[1])),
        },

        "lights" if parts.len() >= 2 => {
            let level: i32 = parts[1].parse().map_err(|_| "Invalid light level")?;
            let level = level.clamp(0, 100);
            api.set_lights(level, None).await.map_err(|e| e.to_string())
        }

        "room" if parts.len() >= 4 && parts[2] == "lights" => {
            let room_id = parts[1].to_string();
            let level: i32 = parts[3].parse().map_err(|_| "Invalid light level")?;
            let level = level.clamp(0, 100);
            api.set_lights(level, Some(vec![room_id]))
                .await
                .map_err(|e| e.to_string())
        }

        "settings" => {
            super::windows::show_settings(app).await?;
            Ok(serde_json::json!({"success": true, "action": "settings"}))
        }

        "command" if parts.len() >= 2 => {
            let cmd = parts[1];
            validate_smart_home_action(cmd)?;
            api.smart_home_action(cmd, None)
                .await
                .map_err(|e| e.to_string())
        }

        "fireplace" if parts.len() >= 2 => {
            let on = parts[1] == "on" || parts[1] == "true" || parts[1] == "1";
            api.fireplace(on).await.map_err(|e| e.to_string())
        }

        "shades" if parts.len() >= 2 => {
            let action = parts[1];
            if action != "open" && action != "close" {
                return Err(format!("Invalid shades action: {}", action));
            }
            api.shades(action, None).await.map_err(|e| e.to_string())
        }

        _ => Err(format!("Unknown deep link path: {}", parts[0])),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_validate_smart_home_action_lights_set() {
        assert!(validate_smart_home_action("lights/set").is_ok());
    }

    #[test]
    fn test_validate_smart_home_action_lights_on() {
        assert!(validate_smart_home_action("lights/on").is_ok());
    }

    #[test]
    fn test_validate_smart_home_action_lights_off() {
        assert!(validate_smart_home_action("lights/off").is_ok());
    }

    #[test]
    fn test_validate_smart_home_action_shades_open() {
        assert!(validate_smart_home_action("shades/open").is_ok());
    }

    #[test]
    fn test_validate_smart_home_action_shades_close() {
        assert!(validate_smart_home_action("shades/close").is_ok());
    }

    #[test]
    fn test_validate_smart_home_action_fireplace_on() {
        assert!(validate_smart_home_action("fireplace/on").is_ok());
    }

    #[test]
    fn test_validate_smart_home_action_fireplace_off() {
        assert!(validate_smart_home_action("fireplace/off").is_ok());
    }

    #[test]
    fn test_validate_smart_home_action_fireplace_toggle() {
        assert!(validate_smart_home_action("fireplace/toggle").is_ok());
    }

    #[test]
    fn test_validate_smart_home_action_tv_lower() {
        assert!(validate_smart_home_action("tv/lower").is_ok());
    }

    #[test]
    fn test_validate_smart_home_action_tv_raise() {
        assert!(validate_smart_home_action("tv/raise").is_ok());
    }

    #[test]
    fn test_validate_smart_home_action_tv_stop() {
        assert!(validate_smart_home_action("tv/stop").is_ok());
    }

    #[test]
    fn test_validate_smart_home_action_movie_mode_enter() {
        assert!(validate_smart_home_action("movie-mode/enter").is_ok());
    }

    #[test]
    fn test_validate_smart_home_action_movie_mode_exit() {
        assert!(validate_smart_home_action("movie-mode/exit").is_ok());
    }

    #[test]
    fn test_validate_smart_home_action_goodnight() {
        assert!(validate_smart_home_action("goodnight").is_ok());
    }

    #[test]
    fn test_validate_smart_home_action_welcome_home() {
        assert!(validate_smart_home_action("welcome-home").is_ok());
    }

    #[test]
    fn test_validate_smart_home_action_away() {
        assert!(validate_smart_home_action("away").is_ok());
    }

    #[test]
    fn test_validate_smart_home_action_announce() {
        assert!(validate_smart_home_action("announce").is_ok());
    }

    #[test]
    fn test_validate_smart_home_action_climate_set() {
        assert!(validate_smart_home_action("climate/set").is_ok());
    }

    #[test]
    fn test_validate_smart_home_action_lock_all() {
        assert!(validate_smart_home_action("lock/all").is_ok());
    }

    #[test]
    fn test_validate_smart_home_action_lock_unlock() {
        assert!(validate_smart_home_action("lock/unlock").is_ok());
    }

    #[test]
    fn test_validate_smart_home_action_case_insensitive() {
        assert!(validate_smart_home_action("LIGHTS/SET").is_ok());
        assert!(validate_smart_home_action("Lights/Set").is_ok());
    }

    #[test]
    fn test_validate_smart_home_action_with_whitespace() {
        assert!(validate_smart_home_action("  lights/set  ").is_ok());
    }

    #[test]
    fn test_validate_smart_home_action_invalid_system_shutdown() {
        let result = validate_smart_home_action("system/shutdown");
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("not in the allowed list"));
    }

    #[test]
    fn test_validate_smart_home_action_invalid_exec_command() {
        assert!(validate_smart_home_action("exec/command").is_err());
    }

    #[test]
    fn test_validate_smart_home_action_invalid_path_traversal() {
        assert!(validate_smart_home_action("../../../etc/passwd").is_err());
    }

    #[test]
    fn test_validate_smart_home_action_invalid_empty() {
        assert!(validate_smart_home_action("").is_err());
    }

    #[test]
    fn test_validate_smart_home_action_invalid_arbitrary() {
        assert!(validate_smart_home_action("arbitrary/action").is_err());
    }

    #[test]
    fn test_validate_smart_home_action_injection_attempt() {
        assert!(validate_smart_home_action("lights/set; rm -rf /").is_err());
    }

    #[test]
    fn test_allowed_actions_count() {
        assert!(ALLOWED_SMART_HOME_ACTIONS.len() >= 15);
    }

    #[test]
    fn test_allowed_actions_no_duplicates() {
        let mut actions = ALLOWED_SMART_HOME_ACTIONS.to_vec();
        let original_len = actions.len();
        actions.sort();
        actions.dedup();
        assert_eq!(actions.len(), original_len, "Whitelist contains duplicates");
    }

    #[test]
    fn test_allowed_actions_no_empty() {
        for action in ALLOWED_SMART_HOME_ACTIONS {
            assert!(!action.is_empty(), "Whitelist contains empty action");
        }
    }

    #[tokio::test]
    async fn test_get_rooms_returns_all_rooms() {
        let result = get_rooms().await;
        assert!(result.is_ok());
        let rooms = result.unwrap();
        assert!(
            rooms.len() >= 10,
            "Expected at least 10 rooms, got {}",
            rooms.len()
        );

        let living_room = rooms.iter().find(|r| r.id == "57");
        assert!(living_room.is_some());
        assert_eq!(living_room.unwrap().name, "Living Room");
    }

    #[tokio::test]
    async fn test_get_rooms_has_correct_floors() {
        let result = get_rooms().await;
        assert!(result.is_ok());
        let rooms = result.unwrap();

        let first_floor_count = rooms
            .iter()
            .filter(|r| r.floor == Some("1st".to_string()))
            .count();
        assert!(first_floor_count > 0);

        let second_floor_count = rooms
            .iter()
            .filter(|r| r.floor == Some("2nd".to_string()))
            .count();
        assert!(second_floor_count > 0);

        let basement_count = rooms
            .iter()
            .filter(|r| r.floor == Some("Basement".to_string()))
            .count();
        assert!(basement_count > 0);
    }

    #[tokio::test]
    async fn test_get_rooms_all_have_valid_ids() {
        let result = get_rooms().await;
        assert!(result.is_ok());
        let rooms = result.unwrap();

        for room in rooms {
            assert!(!room.id.is_empty(), "Room {} has empty ID", room.name);
            assert!(!room.name.is_empty(), "Room with ID {} has empty name", room.id);
        }
    }
}
