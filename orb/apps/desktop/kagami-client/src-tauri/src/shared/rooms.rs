//! Room Definitions
//!
//! Centralized room data used by commands, tray, and context modules.
//! Source of truth for 7331 W Green Lake Dr N.

use serde::{Deserialize, Serialize};

/// Room definition with Control4 ID
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Room {
    pub id: String,
    pub name: String,
    pub floor: Option<String>,
}

/// Room definitions for menu/tray (internal_id, control4_id, display_name, floor)
///
/// Floor naming convention (canonical from Python room.py):
/// - "Main" (was "1st") - Ground floor living areas
/// - "Upper" (was "2nd") - Second floor bedrooms/office
/// - "Lower" (was "Basement") - Basement areas
pub const ROOM_DEFINITIONS: &[(&str, &str, &str, Option<&str>)] = &[
    ("living_room", "57", "Living Room", Some("Main")),
    ("kitchen", "59", "Kitchen", Some("Main")),
    ("dining", "58", "Dining Room", Some("Main")),
    ("office", "47", "Office", Some("Upper")),
    ("primary_bedroom", "36", "Primary Bedroom", Some("Upper")),
    ("primary_bath", "37", "Primary Bath", Some("Upper")),
    ("bedroom_3", "46", "Bedroom 3", Some("Upper")),
    ("loft", "48", "Loft", Some("Upper")),
    ("game_room", "39", "Game Room", Some("Lower")),
    ("gym", "41", "Gym", Some("Lower")),
];

/// Get room display name by internal ID
pub fn get_room_display_name(internal_id: &str) -> Option<&'static str> {
    ROOM_DEFINITIONS
        .iter()
        .find(|(id, _, _, _)| *id == internal_id)
        .map(|(_, _, name, _)| *name)
}

/// Get room Control4 ID by internal ID
pub fn get_room_control4_id(internal_id: &str) -> Option<&'static str> {
    ROOM_DEFINITIONS
        .iter()
        .find(|(id, _, _, _)| *id == internal_id)
        .map(|(_, c4_id, _, _)| *c4_id)
}

/// Get room definitions for tray menu (internal_id, display_name)
pub fn get_tray_rooms() -> Vec<(&'static str, &'static str)> {
    ROOM_DEFINITIONS
        .iter()
        .map(|(id, _, name, _)| (*id, *name))
        .collect()
}

/// Get default room list (for API fallback)
pub fn get_default_rooms() -> Vec<Room> {
    ROOM_DEFINITIONS
        .iter()
        .map(|(_, c4_id, name, floor)| Room {
            id: c4_id.to_string(),
            name: name.to_string(),
            floor: floor.map(|f| f.to_string()),
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_get_room_display_name() {
        assert_eq!(get_room_display_name("living_room"), Some("Living Room"));
        assert_eq!(get_room_display_name("office"), Some("Office"));
        assert_eq!(get_room_display_name("nonexistent"), None);
    }

    #[test]
    fn test_get_room_control4_id() {
        assert_eq!(get_room_control4_id("living_room"), Some("57"));
        assert_eq!(get_room_control4_id("kitchen"), Some("59"));
        assert_eq!(get_room_control4_id("nonexistent"), None);
    }

    #[test]
    fn test_get_tray_rooms() {
        let rooms = get_tray_rooms();
        assert!(rooms.len() >= 10);
        assert!(rooms.iter().any(|(id, _)| *id == "living_room"));
    }

    #[test]
    fn test_get_default_rooms() {
        let rooms = get_default_rooms();
        assert!(rooms.len() >= 10);

        let living_room = rooms.iter().find(|r| r.id == "57");
        assert!(living_room.is_some());
        assert_eq!(living_room.unwrap().name, "Living Room");
        assert_eq!(living_room.unwrap().floor, Some("Main".to_string()));
    }

    #[test]
    fn test_room_floors_are_valid() {
        let rooms = get_default_rooms();
        // Canonical floor names from Python room.py
        let valid_floors = ["Main", "Upper", "Lower", "Garage", "Outdoor"];

        for room in rooms {
            if let Some(floor) = &room.floor {
                assert!(
                    valid_floors.contains(&floor.as_str()),
                    "Invalid floor '{}' for room '{}'",
                    floor,
                    room.name
                );
            }
        }
    }

    #[test]
    fn test_all_rooms_have_valid_ids() {
        let rooms = get_default_rooms();

        for room in rooms {
            assert!(!room.id.is_empty(), "Room {} has empty ID", room.name);
            assert!(!room.name.is_empty(), "Room with ID {} has empty name", room.id);
        }
    }
}
