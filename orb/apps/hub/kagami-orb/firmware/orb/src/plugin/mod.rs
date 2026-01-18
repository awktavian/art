//! Plugin System
//!
//! Enables capability growth through loadable plugins.
//! Plugins run in a WASM sandbox with restricted APIs.
//!
//! h(x) >= 0. Always.

pub mod manifest;
pub mod sandbox;
pub mod registry;
pub mod wasm_sandbox;

use log::*;
use manifest::PluginManifest;

/// Plugin Manager
pub struct PluginManager {
    #[cfg(feature = "plugin_system")]
    plugins: heapless::Vec<LoadedPlugin, 16>,

    #[cfg(feature = "plugin_system")]
    registry: registry::PluginRegistry,
}

/// A loaded plugin instance
#[cfg(feature = "plugin_system")]
pub struct LoadedPlugin {
    pub id: u32,
    pub manifest: PluginManifest,
    pub state: PluginState,
    // WASM instance would go here
}

/// Plugin execution state
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PluginState {
    /// Plugin is loaded but not initialized
    Loaded,
    /// Plugin is initialized and ready
    Ready,
    /// Plugin is currently executing
    Running,
    /// Plugin is suspended
    Suspended,
    /// Plugin encountered an error
    Error,
}

impl PluginManager {
    /// Create a new plugin manager
    #[cfg(feature = "plugin_system")]
    pub fn new() -> anyhow::Result<Self> {
        info!("Initializing plugin system...");

        let registry = registry::PluginRegistry::new()?;

        info!("Plugin system initialized");

        Ok(Self {
            plugins: heapless::Vec::new(),
            registry,
        })
    }

    /// Create a stub plugin manager (when plugin_system feature is disabled)
    #[cfg(not(feature = "plugin_system"))]
    pub fn stub() -> Self {
        Self {}
    }

    /// Load a plugin from its manifest
    #[cfg(feature = "plugin_system")]
    pub fn load(&mut self, manifest: PluginManifest) -> anyhow::Result<u32> {
        info!("Loading plugin: {} v{}", manifest.name, manifest.version);

        // Verify signature
        if !self.verify_signature(&manifest) {
            anyhow::bail!("Plugin signature verification failed");
        }

        // Check permissions
        if !self.check_permissions(&manifest) {
            anyhow::bail!("Plugin requires unavailable permissions");
        }

        // Allocate ID
        let id = self.next_plugin_id();

        // Create plugin instance
        let plugin = LoadedPlugin {
            id,
            manifest,
            state: PluginState::Loaded,
        };

        // Add to list
        self.plugins.push(plugin)
            .map_err(|_| anyhow::anyhow!("Too many plugins loaded"))?;

        info!("Plugin {} loaded with ID {}", self.plugins.last().unwrap().manifest.name, id);

        Ok(id)
    }

    /// Unload a plugin
    #[cfg(feature = "plugin_system")]
    pub fn unload(&mut self, id: u32) {
        if let Some(pos) = self.plugins.iter().position(|p| p.id == id) {
            let plugin = self.plugins.swap_remove(pos);
            info!("Plugin {} unloaded", plugin.manifest.name);
        }
    }

    /// Initialize a loaded plugin
    #[cfg(feature = "plugin_system")]
    pub fn initialize(&mut self, id: u32) -> anyhow::Result<()> {
        let plugin = self.plugins.iter_mut()
            .find(|p| p.id == id)
            .ok_or_else(|| anyhow::anyhow!("Plugin not found"))?;

        if plugin.state != PluginState::Loaded {
            anyhow::bail!("Plugin is not in Loaded state");
        }

        // TODO: Initialize WASM instance
        // 1. Parse WASM module
        // 2. Instantiate with sandbox restrictions
        // 3. Call plugin's initialize() export

        plugin.state = PluginState::Ready;
        info!("Plugin {} initialized", plugin.manifest.name);

        Ok(())
    }

    /// Execute a plugin command
    #[cfg(feature = "plugin_system")]
    pub fn execute(&mut self, id: u32, command: &str, args: &[u8]) -> anyhow::Result<heapless::Vec<u8, 1024>> {
        let plugin = self.plugins.iter_mut()
            .find(|p| p.id == id)
            .ok_or_else(|| anyhow::anyhow!("Plugin not found"))?;

        if plugin.state != PluginState::Ready {
            anyhow::bail!("Plugin is not ready");
        }

        plugin.state = PluginState::Running;

        // TODO: Execute WASM function
        // 1. Write args to WASM memory
        // 2. Call plugin's execute() export
        // 3. Read result from WASM memory

        plugin.state = PluginState::Ready;

        Ok(heapless::Vec::new())
    }

    /// List loaded plugins
    #[cfg(feature = "plugin_system")]
    pub fn list(&self) -> impl Iterator<Item = &LoadedPlugin> {
        self.plugins.iter()
    }

    #[cfg(feature = "plugin_system")]
    fn next_plugin_id(&self) -> u32 {
        self.plugins.iter()
            .map(|p| p.id)
            .max()
            .unwrap_or(0) + 1
    }

    #[cfg(feature = "plugin_system")]
    fn verify_signature(&self, manifest: &PluginManifest) -> bool {
        // TODO: Verify Ed25519 signature
        // For now, trust all manifests (development mode)
        true
    }

    #[cfg(feature = "plugin_system")]
    fn check_permissions(&self, manifest: &PluginManifest) -> bool {
        // TODO: Check if all requested permissions are available
        true
    }
}

/// Plugin API available to WASM modules
pub mod api {
    use super::*;

    /// Send a keyboard HID report
    pub fn hid_keyboard(modifier: u8, keycode: u8) {
        // Delegated to main firmware
        todo!()
    }

    /// Send a mouse HID report
    pub fn hid_mouse(buttons: u8, x: i8, y: i8) {
        todo!()
    }

    /// Read IMU data
    pub fn imu_read() -> (i16, i16, i16, i16, i16, i16) {
        // (accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z)
        todo!()
    }

    /// Set LED pattern
    pub fn led_pattern(pattern: u8) {
        todo!()
    }

    /// Set specific LED color
    pub fn led_color(index: u8, r: u8, g: u8, b: u8, w: u8) {
        todo!()
    }

    /// Read plugin storage
    pub fn storage_read(key: &str) -> Option<heapless::Vec<u8, 256>> {
        todo!()
    }

    /// Write plugin storage
    pub fn storage_write(key: &str, value: &[u8]) -> bool {
        todo!()
    }

    /// Log a message
    pub fn log(level: u8, message: &str) {
        match level {
            0 => trace!("[plugin] {}", message),
            1 => debug!("[plugin] {}", message),
            2 => info!("[plugin] {}", message),
            3 => warn!("[plugin] {}", message),
            _ => error!("[plugin] {}", message),
        }
    }
}
