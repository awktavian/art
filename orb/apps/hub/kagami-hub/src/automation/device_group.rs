//! Device Group Management
//!
//! Groups of devices that can be controlled together as a unit.
//! Supports different group types (lights, climate, shades, etc.)
//!
//! Colony: Beacon (e5) - Orchestration and coordination
//!
//! h(x) >= 0 always

use serde::{Deserialize, Serialize};

// ============================================================================
// Device Groups
// ============================================================================

/// A group of devices that can be controlled together
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeviceGroup {
    /// Unique group identifier
    pub id: String,
    /// Human-readable name
    pub name: String,
    /// Description
    pub description: Option<String>,
    /// Device IDs in this group
    pub device_ids: Vec<String>,
    /// Room associations
    pub rooms: Vec<String>,
    /// Group type
    pub group_type: GroupType,
    /// Icon for UI
    pub icon: Option<String>,
    /// Is group enabled
    pub enabled: bool,
    /// Creation timestamp
    pub created_at: u64,
    /// Last modified timestamp
    pub updated_at: u64,
}

/// Type of device group
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum GroupType {
    /// Lights group
    Lights,
    /// Climate devices
    Climate,
    /// Shades/blinds
    Shades,
    /// Media devices
    Media,
    /// Security devices
    Security,
    /// All device types
    Mixed,
    /// Custom group
    Custom,
}

impl DeviceGroup {
    /// Create a new device group
    pub fn new(id: &str, name: &str, group_type: GroupType) -> Self {
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();

        Self {
            id: id.to_string(),
            name: name.to_string(),
            description: None,
            device_ids: vec![],
            rooms: vec![],
            group_type,
            icon: None,
            enabled: true,
            created_at: now,
            updated_at: now,
        }
    }

    /// Add a device to the group
    pub fn add_device(&mut self, device_id: &str) {
        if !self.device_ids.contains(&device_id.to_string()) {
            self.device_ids.push(device_id.to_string());
            self.touch();
        }
    }

    /// Remove a device from the group
    pub fn remove_device(&mut self, device_id: &str) {
        self.device_ids.retain(|id| id != device_id);
        self.touch();
    }

    /// Add a room association
    pub fn add_room(&mut self, room: &str) {
        if !self.rooms.contains(&room.to_string()) {
            self.rooms.push(room.to_string());
            self.touch();
        }
    }

    /// Get the number of devices in the group
    pub fn device_count(&self) -> usize {
        self.device_ids.len()
    }

    /// Check if the group contains a specific device
    pub fn contains_device(&self, device_id: &str) -> bool {
        self.device_ids.iter().any(|id| id == device_id)
    }

    /// Update modified timestamp
    pub(crate) fn touch(&mut self) {
        self.updated_at = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
    }
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_device_group_creation() {
        let mut group = DeviceGroup::new("lights-living", "Living Room Lights", GroupType::Lights);
        assert_eq!(group.id, "lights-living");
        assert!(group.device_ids.is_empty());

        group.add_device("light-1");
        group.add_device("light-2");
        assert_eq!(group.device_ids.len(), 2);

        group.remove_device("light-1");
        assert_eq!(group.device_ids.len(), 1);
    }

    #[test]
    fn test_device_group_duplicate_prevention() {
        let mut group = DeviceGroup::new("test", "Test Group", GroupType::Lights);
        group.add_device("light-1");
        group.add_device("light-1"); // Duplicate
        assert_eq!(group.device_ids.len(), 1);
    }

    #[test]
    fn test_device_group_contains() {
        let mut group = DeviceGroup::new("test", "Test Group", GroupType::Lights);
        group.add_device("light-1");
        assert!(group.contains_device("light-1"));
        assert!(!group.contains_device("light-2"));
    }

    #[test]
    fn test_device_group_room_association() {
        let mut group = DeviceGroup::new("test", "Test Group", GroupType::Mixed);
        group.add_room("Living Room");
        group.add_room("Kitchen");
        group.add_room("Living Room"); // Duplicate
        assert_eq!(group.rooms.len(), 2);
    }
}
