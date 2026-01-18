//! Plugin Manifest
//!
//! Defines the structure of plugin.yaml files that describe plugin capabilities.

use heapless::{String, Vec};
use serde::{Deserialize, Serialize};

/// Plugin manifest (from plugin.yaml)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PluginManifest {
    /// Plugin name (unique identifier)
    pub name: String<64>,

    /// Semantic version (e.g., "1.0.0")
    pub version: String<16>,

    /// Author name or organization
    pub author: String<64>,

    /// Description of what the plugin does
    pub description: String<256>,

    /// Required permissions
    pub permissions: Vec<Permission, 16>,

    /// Entry point (WASM file path)
    pub entry_point: String<128>,

    /// Ed25519 signature over the manifest (hex-encoded)
    pub signature: String<128>,

    /// Minimum firmware version required
    #[serde(default)]
    pub min_firmware: String<16>,

    /// Plugin category for marketplace
    #[serde(default)]
    pub category: Category,
}

/// Plugin permissions
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Permission {
    /// Access to HID keyboard
    HidKeyboard,
    /// Access to HID mouse
    HidMouse,
    /// Access to HID consumer control
    HidConsumer,
    /// Access to HID gamepad
    HidGamepad,
    /// Access to IMU sensor
    ImuAccess,
    /// Access to LED ring
    LedRing,
    /// Plugin-specific storage
    Storage,
    /// Read plugin settings
    SettingsRead,
    /// Write plugin settings
    SettingsWrite,
    /// Network access (restricted)
    Network,
}

/// Plugin category
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
pub enum Category {
    #[default]
    Automation,
    Accessibility,
    Productivity,
    Entertainment,
    Developer,
    Security,
}

impl PluginManifest {
    /// Parse a manifest from YAML
    pub fn from_yaml(yaml: &str) -> Result<Self, serde_yaml::Error> {
        serde_yaml::from_str(yaml)
    }

    /// Serialize to YAML
    pub fn to_yaml(&self) -> Result<std::string::String, serde_yaml::Error> {
        serde_yaml::to_string(self)
    }

    /// Check if this plugin requires a specific permission
    pub fn requires(&self, permission: Permission) -> bool {
        self.permissions.contains(&permission)
    }

    /// Get the data to be signed (everything except signature field)
    pub fn signable_data(&self) -> Vec<u8, 1024> {
        let mut data = Vec::new();
        data.extend_from_slice(self.name.as_bytes()).ok();
        data.extend_from_slice(self.version.as_bytes()).ok();
        data.extend_from_slice(self.author.as_bytes()).ok();
        data.extend_from_slice(self.description.as_bytes()).ok();
        data.extend_from_slice(self.entry_point.as_bytes()).ok();
        data
    }
}

/// Example manifest for a spatial mouse plugin
#[cfg(test)]
mod example {
    use super::*;

    fn spatial_mouse_manifest() -> PluginManifest {
        PluginManifest {
            name: String::try_from("spatial_mouse").unwrap(),
            version: String::try_from("1.0.0").unwrap(),
            author: String::try_from("kagami-community").unwrap(),
            description: String::try_from("Use the Orb as a spatial mouse controller by tilting").unwrap(),
            permissions: {
                let mut p = Vec::new();
                p.push(Permission::ImuAccess).ok();
                p.push(Permission::HidMouse).ok();
                p.push(Permission::SettingsWrite).ok();
                p
            },
            entry_point: String::try_from("spatial_mouse.wasm").unwrap(),
            signature: String::try_from("0000000000000000000000000000000000000000000000000000000000000000").unwrap(),
            min_firmware: String::try_from("2.0.0").unwrap(),
            category: Category::Productivity,
        }
    }

    #[test]
    fn test_manifest_yaml() {
        let manifest = spatial_mouse_manifest();
        let yaml = manifest.to_yaml().unwrap();
        assert!(yaml.contains("spatial_mouse"));
    }
}
