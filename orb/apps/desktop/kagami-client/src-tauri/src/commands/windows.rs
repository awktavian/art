//! Window Management Commands
//!
//! Handles Quick Entry, Settings, and Onboarding windows.
//! Colony: Forge (e2)

use tauri::{AppHandle, Manager};
use tracing::{debug, info};

use super::error::CommandError;

/// Show the Quick Entry overlay window.
#[tauri::command]
pub async fn show_quick_entry(app: AppHandle) -> Result<(), String> {
    info!("Showing Quick Entry overlay");

    if let Some(window) = app.get_webview_window("quick-entry") {
        window.center().map_err(|e| e.to_string())?;
        window.show().map_err(|e| e.to_string())?;
        window.set_focus().map_err(|e| e.to_string())?;
        Ok(())
    } else {
        Err(CommandError::WindowNotFound("quick-entry".to_string()).into())
    }
}

/// Hide the Quick Entry overlay window.
#[tauri::command]
pub async fn hide_quick_entry(app: AppHandle) -> Result<(), String> {
    debug!("Hiding Quick Entry overlay");

    if let Some(window) = app.get_webview_window("quick-entry") {
        window.hide().map_err(|e| e.to_string())?;
        Ok(())
    } else {
        Err(CommandError::WindowNotFound("quick-entry".to_string()).into())
    }
}

/// Show the settings window.
#[tauri::command]
pub async fn show_settings(app: AppHandle) -> Result<(), String> {
    info!("Showing Settings window");

    if let Some(window) = app.get_webview_window("settings") {
        window.show().map_err(|e| e.to_string())?;
        window.set_focus().map_err(|e| e.to_string())?;
        Ok(())
    } else {
        Err(CommandError::WindowNotFound("settings".to_string()).into())
    }
}

/// Show the onboarding window for first-run setup.
#[tauri::command]
pub async fn show_onboarding(app: AppHandle) -> Result<(), String> {
    info!("Showing Onboarding window");

    if let Some(window) = app.get_webview_window("onboarding") {
        window.center().map_err(|e| e.to_string())?;
        window.show().map_err(|e| e.to_string())?;
        window.set_focus().map_err(|e| e.to_string())?;
        Ok(())
    } else {
        Err(CommandError::WindowNotFound("onboarding".to_string()).into())
    }
}

#[cfg(test)]
mod tests {
    // Window tests require a Tauri context, tested via integration tests
}
