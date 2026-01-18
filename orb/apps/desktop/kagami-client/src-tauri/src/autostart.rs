//! Auto-Start on Login Management for Kagami Desktop
//!
//! Provides cross-platform functionality to enable/disable auto-start on login.
//!
//! Platform implementations:
//! - macOS: LaunchAgent plist in ~/Library/LaunchAgents/
//! - Windows: Registry entry in HKCU\Software\Microsoft\Windows\CurrentVersion\Run
//! - Linux: Desktop entry in ~/.config/autostart/
//!
//! Colony: Nexus (e₄) — Integration and persistence
//!
//! η → s → μ → a → η′
//! h(x) ≥ 0. Always.

use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use tracing::{debug, error, info, warn};

/// Auto-start configuration state
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AutoStartState {
    /// Whether auto-start is currently enabled
    pub enabled: bool,
    /// Path to the auto-start configuration file
    pub config_path: Option<String>,
    /// Whether the platform supports auto-start
    pub platform_supported: bool,
}

/// Auto-start manager errors
#[derive(Debug, thiserror::Error)]
pub enum AutoStartError {
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),
    #[error("Platform not supported")]
    PlatformNotSupported,
    #[error("Failed to get executable path")]
    ExecutablePathNotFound,
    #[error("Failed to get home directory")]
    HomeDirectoryNotFound,
    #[cfg(windows)]
    #[error("Registry error: {0}")]
    Registry(String),
}

const APP_NAME: &str = "com.kagami.client";
const APP_DISPLAY_NAME: &str = "Kagami";

/// Get the path to the current executable
fn get_executable_path() -> Result<PathBuf, AutoStartError> {
    std::env::current_exe().map_err(|_| AutoStartError::ExecutablePathNotFound)
}

/// Get the user's home directory
fn get_home_dir() -> Result<PathBuf, AutoStartError> {
    dirs::home_dir().ok_or(AutoStartError::HomeDirectoryNotFound)
}

// ═══════════════════════════════════════════════════════════════════════════
// macOS Implementation
// ═══════════════════════════════════════════════════════════════════════════

#[cfg(target_os = "macos")]
mod platform {
    use super::*;

    /// Get the LaunchAgent plist path
    pub fn get_autostart_path() -> Result<PathBuf, AutoStartError> {
        let home = get_home_dir()?;
        Ok(home
            .join("Library")
            .join("LaunchAgents")
            .join(format!("{}.plist", APP_NAME)))
    }

    /// Generate the LaunchAgent plist content
    fn generate_plist(exe_path: &str) -> String {
        format!(
            r#"<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>ProcessType</key>
    <string>Interactive</string>
    <key>StandardOutPath</key>
    <string>/tmp/kagami-client.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/kagami-client.err</string>
</dict>
</plist>"#,
            APP_NAME, exe_path
        )
    }

    /// Enable auto-start on macOS
    pub fn enable() -> Result<(), AutoStartError> {
        let plist_path = get_autostart_path()?;
        let exe_path = get_executable_path()?;

        // Ensure LaunchAgents directory exists
        if let Some(parent) = plist_path.parent() {
            std::fs::create_dir_all(parent)?;
        }

        // Generate and write plist
        let plist_content = generate_plist(exe_path.to_string_lossy().as_ref());
        std::fs::write(&plist_path, plist_content)?;

        info!("Auto-start enabled: {:?}", plist_path);
        Ok(())
    }

    /// Disable auto-start on macOS
    pub fn disable() -> Result<(), AutoStartError> {
        let plist_path = get_autostart_path()?;

        if plist_path.exists() {
            std::fs::remove_file(&plist_path)?;
            info!("Auto-start disabled: {:?}", plist_path);
        } else {
            debug!("Auto-start plist not found, nothing to disable");
        }

        Ok(())
    }

    /// Check if auto-start is enabled on macOS
    pub fn is_enabled() -> bool {
        get_autostart_path()
            .map(|path| path.exists())
            .unwrap_or(false)
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// Windows Implementation
// ═══════════════════════════════════════════════════════════════════════════

#[cfg(target_os = "windows")]
mod platform {
    use super::*;
    use winreg::enums::*;
    use winreg::RegKey;

    const REGISTRY_KEY: &str = r"Software\Microsoft\Windows\CurrentVersion\Run";

    /// Get the registry path (for display purposes)
    pub fn get_autostart_path() -> Result<PathBuf, AutoStartError> {
        Ok(PathBuf::from(format!("HKCU\\{}", REGISTRY_KEY)))
    }

    /// Enable auto-start on Windows
    pub fn enable() -> Result<(), AutoStartError> {
        let exe_path = get_executable_path()?;
        let exe_str = exe_path.to_string_lossy();

        let hkcu = RegKey::predef(HKEY_CURRENT_USER);
        let (key, _) = hkcu
            .create_subkey(REGISTRY_KEY)
            .map_err(|e| AutoStartError::Registry(e.to_string()))?;

        // Add quotes around the path to handle spaces
        key.set_value(APP_DISPLAY_NAME, &format!("\"{}\"", exe_str))
            .map_err(|e| AutoStartError::Registry(e.to_string()))?;

        info!("Auto-start enabled in registry");
        Ok(())
    }

    /// Disable auto-start on Windows
    pub fn disable() -> Result<(), AutoStartError> {
        let hkcu = RegKey::predef(HKEY_CURRENT_USER);

        if let Ok(key) = hkcu.open_subkey_with_flags(REGISTRY_KEY, KEY_WRITE) {
            let _ = key.delete_value(APP_DISPLAY_NAME);
            info!("Auto-start disabled in registry");
        } else {
            debug!("Registry key not found, nothing to disable");
        }

        Ok(())
    }

    /// Check if auto-start is enabled on Windows
    pub fn is_enabled() -> bool {
        let hkcu = RegKey::predef(HKEY_CURRENT_USER);

        if let Ok(key) = hkcu.open_subkey(REGISTRY_KEY) {
            key.get_value::<String, _>(APP_DISPLAY_NAME).is_ok()
        } else {
            false
        }
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// Linux Implementation
// ═══════════════════════════════════════════════════════════════════════════

#[cfg(target_os = "linux")]
mod platform {
    use super::*;

    /// Get the XDG autostart desktop entry path
    pub fn get_autostart_path() -> Result<PathBuf, AutoStartError> {
        let home = get_home_dir()?;
        Ok(home
            .join(".config")
            .join("autostart")
            .join(format!("{}.desktop", APP_NAME)))
    }

    /// Generate the desktop entry content
    fn generate_desktop_entry(exe_path: &str) -> String {
        format!(
            r#"[Desktop Entry]
Type=Application
Name={}
Exec={}
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Comment=Kagami AI Assistant
"#,
            APP_DISPLAY_NAME, exe_path
        )
    }

    /// Enable auto-start on Linux
    pub fn enable() -> Result<(), AutoStartError> {
        let desktop_path = get_autostart_path()?;
        let exe_path = get_executable_path()?;

        // Ensure autostart directory exists
        if let Some(parent) = desktop_path.parent() {
            std::fs::create_dir_all(parent)?;
        }

        // Generate and write desktop entry
        let desktop_content = generate_desktop_entry(exe_path.to_string_lossy().as_ref());
        std::fs::write(&desktop_path, desktop_content)?;

        info!("Auto-start enabled: {:?}", desktop_path);
        Ok(())
    }

    /// Disable auto-start on Linux
    pub fn disable() -> Result<(), AutoStartError> {
        let desktop_path = get_autostart_path()?;

        if desktop_path.exists() {
            std::fs::remove_file(&desktop_path)?;
            info!("Auto-start disabled: {:?}", desktop_path);
        } else {
            debug!("Desktop entry not found, nothing to disable");
        }

        Ok(())
    }

    /// Check if auto-start is enabled on Linux
    pub fn is_enabled() -> bool {
        get_autostart_path()
            .map(|path| path.exists())
            .unwrap_or(false)
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// Fallback for unsupported platforms
// ═══════════════════════════════════════════════════════════════════════════

#[cfg(not(any(target_os = "macos", target_os = "windows", target_os = "linux")))]
mod platform {
    use super::*;

    pub fn get_autostart_path() -> Result<PathBuf, AutoStartError> {
        Err(AutoStartError::PlatformNotSupported)
    }

    pub fn enable() -> Result<(), AutoStartError> {
        Err(AutoStartError::PlatformNotSupported)
    }

    pub fn disable() -> Result<(), AutoStartError> {
        Err(AutoStartError::PlatformNotSupported)
    }

    pub fn is_enabled() -> bool {
        false
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// Public API
// ═══════════════════════════════════════════════════════════════════════════

/// Enable auto-start on login
pub fn enable_autostart() -> Result<(), AutoStartError> {
    platform::enable()
}

/// Disable auto-start on login
pub fn disable_autostart() -> Result<(), AutoStartError> {
    platform::disable()
}

/// Check if auto-start is currently enabled
pub fn is_autostart_enabled() -> bool {
    platform::is_enabled()
}

/// Get the current auto-start state
pub fn get_autostart_state() -> AutoStartState {
    let enabled = platform::is_enabled();
    let config_path = platform::get_autostart_path()
        .ok()
        .map(|p| p.to_string_lossy().into_owned());

    AutoStartState {
        enabled,
        config_path,
        platform_supported: cfg!(any(
            target_os = "macos",
            target_os = "windows",
            target_os = "linux"
        )),
    }
}

/// Toggle auto-start state
pub fn toggle_autostart() -> Result<bool, AutoStartError> {
    if is_autostart_enabled() {
        disable_autostart()?;
        Ok(false)
    } else {
        enable_autostart()?;
        Ok(true)
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// Tauri Commands
// ═══════════════════════════════════════════════════════════════════════════

/// Get auto-start state (Tauri command)
#[tauri::command]
pub fn get_autostart() -> AutoStartState {
    get_autostart_state()
}

/// Set auto-start enabled/disabled (Tauri command)
#[tauri::command]
pub fn set_autostart(enabled: bool) -> Result<AutoStartState, String> {
    let result = if enabled {
        enable_autostart()
    } else {
        disable_autostart()
    };

    match result {
        Ok(_) => Ok(get_autostart_state()),
        Err(e) => {
            error!("Failed to set autostart: {}", e);
            Err(e.to_string())
        }
    }
}

/// Toggle auto-start (Tauri command)
#[tauri::command]
pub fn toggle_autostart_cmd() -> Result<AutoStartState, String> {
    match toggle_autostart() {
        Ok(_) => Ok(get_autostart_state()),
        Err(e) => {
            error!("Failed to toggle autostart: {}", e);
            Err(e.to_string())
        }
    }
}

/*
 * 鏡
 * Always present. Always ready.
 * h(x) ≥ 0. Always.
 */
