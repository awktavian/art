//! Auto-Update Module for Kagami Desktop Client
//!
//! Colony: Flow (e₃) — Operations & Adaptation
//!
//! Features:
//! - Automatic update checking on launch
//! - Background download with progress
//! - User notification for updates
//! - Seamless restart after update

use tauri::{AppHandle, Manager};
use tauri_plugin_updater::{Update, UpdaterExt};
use tracing::{info, warn, error};

/// Check for updates in the background
pub async fn check_for_updates(app: AppHandle) -> Result<Option<Update>, String> {
    info!("Checking for updates...");

    match app.updater() {
        Ok(updater) => {
            match updater.check().await {
                Ok(update) => {
                    if let Some(ref u) = update {
                        info!("Update available: {} -> {}", u.current_version, u.version);

                        // Notify the frontend
                        let _ = app.emit("update-available", UpdateInfo {
                            current_version: u.current_version.to_string(),
                            new_version: u.version.to_string(),
                            body: u.body.clone(),
                        });
                    } else {
                        info!("Already on latest version");
                    }
                    Ok(update)
                }
                Err(e) => {
                    warn!("Update check failed: {}", e);
                    Err(e.to_string())
                }
            }
        }
        Err(e) => {
            error!("Failed to get updater: {}", e);
            Err(e.to_string())
        }
    }
}

/// Download and install an update
pub async fn download_and_install(app: AppHandle, update: Update) -> Result<(), String> {
    info!("Downloading update v{}...", update.version);

    // Download with progress updates
    let downloaded = update.download(
        |chunk_length, content_length| {
            let progress = content_length
                .map(|total| (chunk_length as f64 / total as f64) * 100.0)
                .unwrap_or(0.0);

            info!("Download progress: {:.1}%", progress);

            // Emit progress to frontend
            let _ = app.emit("update-progress", UpdateProgress {
                downloaded: chunk_length,
                total: content_length,
                progress,
            });
        },
        || {
            info!("Download complete");
        }
    ).await;

    match downloaded {
        Ok(bytes) => {
            info!("Downloaded {} bytes, installing...", bytes.len());

            // Install the update
            if let Err(e) = update.install(bytes) {
                error!("Installation failed: {}", e);
                return Err(e.to_string());
            }

            info!("Update installed successfully");

            // Notify frontend to restart
            let _ = app.emit("update-ready", ());

            Ok(())
        }
        Err(e) => {
            error!("Download failed: {}", e);
            Err(e.to_string())
        }
    }
}

/// Restart the application to apply the update
pub fn restart_app(app: AppHandle) {
    info!("Restarting application to apply update...");
    app.restart();
}

// Event payloads
#[derive(Clone, serde::Serialize)]
struct UpdateInfo {
    current_version: String,
    new_version: String,
    body: Option<String>,
}

#[derive(Clone, serde::Serialize)]
struct UpdateProgress {
    downloaded: usize,
    total: Option<u64>,
    progress: f64,
}

// Tauri commands for frontend
#[tauri::command]
pub async fn check_update(app: AppHandle) -> Result<bool, String> {
    match check_for_updates(app).await {
        Ok(Some(_)) => Ok(true),
        Ok(None) => Ok(false),
        Err(e) => Err(e),
    }
}

#[tauri::command]
pub async fn install_update(app: AppHandle) -> Result<(), String> {
    let updater = app.updater().map_err(|e| e.to_string())?;
    let update = updater.check().await.map_err(|e| e.to_string())?;

    if let Some(update) = update {
        download_and_install(app, update).await
    } else {
        Err("No update available".to_string())
    }
}

#[tauri::command]
pub fn restart_for_update(app: AppHandle) {
    restart_app(app);
}

/*
 * 鏡
 * Updates flow like water.
 * Adapt, evolve, improve.
 */
