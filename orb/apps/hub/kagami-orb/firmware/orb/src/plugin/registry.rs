//! Plugin Registry
//!
//! Manages installed plugins and provides discovery.

use super::manifest::{PluginManifest, Category};
use heapless::{String, Vec};
use log::*;

/// Plugin registry entry
#[derive(Debug, Clone)]
pub struct RegistryEntry {
    /// Plugin manifest
    pub manifest: PluginManifest,
    /// Installation path
    pub path: String<128>,
    /// Whether plugin is enabled
    pub enabled: bool,
    /// Trust level
    pub trust: TrustLevel,
}

/// Trust levels for plugins
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TrustLevel {
    /// Factory-installed, always trusted
    Builtin,
    /// Kagami team verified
    Verified,
    /// Community reviewed
    Community,
    /// User-installed, not reviewed
    User,
}

/// Plugin registry
pub struct PluginRegistry {
    /// Registered plugins
    entries: Vec<RegistryEntry, 64>,
}

impl PluginRegistry {
    /// Create a new registry
    pub fn new() -> anyhow::Result<Self> {
        info!("Initializing plugin registry...");

        let mut registry = Self {
            entries: Vec::new(),
        };

        // Scan plugin directories
        registry.scan_builtin()?;
        registry.scan_user()?;
        registry.scan_community()?;

        info!("Plugin registry initialized with {} plugins", registry.entries.len());

        Ok(registry)
    }

    /// Scan builtin plugins
    fn scan_builtin(&mut self) -> anyhow::Result<()> {
        // TODO: Scan /kagami/plugins/builtin/
        // For now, register placeholder entries

        // HID Keyboard plugin (builtin)
        let entry = RegistryEntry {
            manifest: PluginManifest {
                name: String::try_from("hid_keyboard").unwrap(),
                version: String::try_from("1.0.0").unwrap(),
                author: String::try_from("Kagami").unwrap(),
                description: String::try_from("Basic keyboard HID functionality").unwrap(),
                permissions: Vec::new(),
                entry_point: String::try_from("hid_keyboard.wasm").unwrap(),
                signature: String::new(),
                min_firmware: String::try_from("1.0.0").unwrap(),
                category: Category::Productivity,
            },
            path: String::try_from("/kagami/plugins/builtin/hid_keyboard/").unwrap(),
            enabled: true,
            trust: TrustLevel::Builtin,
        };
        self.entries.push(entry).ok();

        // Presentation mode plugin (builtin)
        let entry = RegistryEntry {
            manifest: PluginManifest {
                name: String::try_from("presentation_mode").unwrap(),
                version: String::try_from("1.0.0").unwrap(),
                author: String::try_from("Kagami").unwrap(),
                description: String::try_from("Wireless presentation controller").unwrap(),
                permissions: Vec::new(),
                entry_point: String::try_from("presentation.wasm").unwrap(),
                signature: String::new(),
                min_firmware: String::try_from("1.0.0").unwrap(),
                category: Category::Productivity,
            },
            path: String::try_from("/kagami/plugins/builtin/presentation/").unwrap(),
            enabled: true,
            trust: TrustLevel::Builtin,
        };
        self.entries.push(entry).ok();

        Ok(())
    }

    /// Scan user plugins
    fn scan_user(&mut self) -> anyhow::Result<()> {
        // TODO: Scan /kagami/plugins/user/
        Ok(())
    }

    /// Scan community plugins
    fn scan_community(&mut self) -> anyhow::Result<()> {
        // TODO: Scan /kagami/plugins/community/
        Ok(())
    }

    /// List all plugins
    pub fn list(&self) -> impl Iterator<Item = &RegistryEntry> {
        self.entries.iter()
    }

    /// List plugins by category
    pub fn list_by_category(&self, category: Category) -> impl Iterator<Item = &RegistryEntry> {
        self.entries.iter().filter(move |e| e.manifest.category == category)
    }

    /// List enabled plugins
    pub fn list_enabled(&self) -> impl Iterator<Item = &RegistryEntry> {
        self.entries.iter().filter(|e| e.enabled)
    }

    /// Find a plugin by name
    pub fn find(&self, name: &str) -> Option<&RegistryEntry> {
        self.entries.iter().find(|e| e.manifest.name.as_str() == name)
    }

    /// Enable a plugin
    pub fn enable(&mut self, name: &str) -> bool {
        if let Some(entry) = self.entries.iter_mut().find(|e| e.manifest.name.as_str() == name) {
            entry.enabled = true;
            info!("Plugin {} enabled", name);
            true
        } else {
            false
        }
    }

    /// Disable a plugin
    pub fn disable(&mut self, name: &str) -> bool {
        if let Some(entry) = self.entries.iter_mut().find(|e| e.manifest.name.as_str() == name) {
            entry.enabled = false;
            info!("Plugin {} disabled", name);
            true
        } else {
            false
        }
    }

    /// Install a plugin from manifest
    pub fn install(&mut self, manifest: PluginManifest, path: String<128>, trust: TrustLevel) -> anyhow::Result<()> {
        // Check if already installed
        if self.find(manifest.name.as_str()).is_some() {
            anyhow::bail!("Plugin {} is already installed", manifest.name);
        }

        let entry = RegistryEntry {
            manifest,
            path,
            enabled: false, // New plugins start disabled
            trust,
        };

        self.entries.push(entry)
            .map_err(|_| anyhow::anyhow!("Plugin registry full"))?;

        Ok(())
    }

    /// Uninstall a plugin
    pub fn uninstall(&mut self, name: &str) -> bool {
        if let Some(pos) = self.entries.iter().position(|e| e.manifest.name.as_str() == name) {
            // Don't allow uninstalling builtin plugins
            if self.entries[pos].trust == TrustLevel::Builtin {
                warn!("Cannot uninstall builtin plugin: {}", name);
                return false;
            }

            self.entries.swap_remove(pos);
            info!("Plugin {} uninstalled", name);
            true
        } else {
            false
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_registry_creation() {
        let registry = PluginRegistry::new().unwrap();
        assert!(registry.entries.len() >= 2); // At least builtin plugins
    }

    #[test]
    fn test_find_plugin() {
        let registry = PluginRegistry::new().unwrap();
        let plugin = registry.find("hid_keyboard");
        assert!(plugin.is_some());
    }

    #[test]
    fn test_enable_disable() {
        let mut registry = PluginRegistry::new().unwrap();

        registry.disable("hid_keyboard");
        assert!(!registry.find("hid_keyboard").unwrap().enabled);

        registry.enable("hid_keyboard");
        assert!(registry.find("hid_keyboard").unwrap().enabled);
    }
}
