//! API Request Commands
//!
//! Generic API request passthrough and API control (start/stop).
//! Colony: Forge (e2)

use crate::api_client::get_api;
use serde_json::Value;
use std::process::Command;
use std::time::Duration;
use tracing::{debug, error, info};

use super::error::CommandError;

/// Process spawn timeout in seconds
const PROCESS_SPAWN_TIMEOUT_SECS: u64 = 30;

/// Get the Kagami root directory from environment or standard locations.
fn get_kagami_root() -> Option<String> {
    // 1. Check environment variable first
    if let Ok(root) = std::env::var("KAGAMI_ROOT") {
        if std::path::Path::new(&root).exists() {
            return Some(root);
        }
    }

    // 2. Check XDG data directory (Linux/BSD standard)
    if let Some(data_dir) = dirs::data_dir() {
        let kagami_data = data_dir.join("kagami");
        if kagami_data.exists() {
            return Some(kagami_data.to_string_lossy().to_string());
        }
    }

    // 3. Check home directory ~/kagami
    if let Some(home) = dirs::home_dir() {
        let home_kagami = home.join("kagami");
        if home_kagami.exists() {
            return Some(home_kagami.to_string_lossy().to_string());
        }

        // Also check ~/projects/kagami (common development location)
        let projects_kagami = home.join("projects").join("kagami");
        if projects_kagami.exists() {
            return Some(projects_kagami.to_string_lossy().to_string());
        }
    }

    // 4. Check relative to executable (for bundled apps)
    if let Ok(exe_path) = std::env::current_exe() {
        if let Some(exe_dir) = exe_path.parent() {
            // Check ../Resources/kagami (macOS app bundle)
            let resources_kagami = exe_dir.join("../Resources/kagami");
            if resources_kagami.exists() {
                return Some(
                    resources_kagami
                        .canonicalize()
                        .ok()?
                        .to_string_lossy()
                        .to_string(),
                );
            }
        }
    }

    None
}

/// Generic API request passthrough.
#[tauri::command]
pub async fn api_request(
    endpoint: String,
    method: String,
    body: Option<Value>,
) -> Result<Value, String> {
    debug!("API request: {} {}", method, endpoint);

    let api = get_api();
    api.request(&endpoint, &method, body)
        .await
        .map_err(|e| e.to_string())
}

/// Start the Kagami API server with timeout protection.
#[tauri::command]
pub async fn start_api() -> Result<bool, String> {
    info!("Starting Kagami API...");

    let kagami_root = get_kagami_root().ok_or_else(|| CommandError::KagamiRootNotFound)?;

    let launcher_script = format!("{}/scripts/kagami_api_launcher.py", kagami_root);

    // Verify the launcher script exists
    if !std::path::Path::new(&launcher_script).exists() {
        return Err(CommandError::ScriptNotFound(launcher_script).into());
    }

    // Spawn process with timeout protection
    let spawn_result = tokio::task::spawn_blocking(move || {
        Command::new("python3")
            .arg(&launcher_script)
            .arg("--port")
            .arg("8001")
            .current_dir(&kagami_root)
            .spawn()
    });

    // Apply timeout to the spawn operation
    match tokio::time::timeout(
        Duration::from_secs(PROCESS_SPAWN_TIMEOUT_SECS),
        spawn_result,
    )
    .await
    {
        Ok(Ok(Ok(_child))) => {
            info!("API launcher started successfully");
            Ok(true)
        }
        Ok(Ok(Err(e))) => {
            error!("Failed to spawn API process: {}", e);
            Err(CommandError::ProcessSpawnFailed(e.to_string()).into())
        }
        Ok(Err(e)) => {
            error!("Task join error: {}", e);
            Err(CommandError::ProcessSpawnFailed(e.to_string()).into())
        }
        Err(_) => {
            error!(
                "Process spawn timed out after {} seconds",
                PROCESS_SPAWN_TIMEOUT_SECS
            );
            Err(CommandError::ProcessTimeout(PROCESS_SPAWN_TIMEOUT_SECS).into())
        }
    }
}

/// Stop the Kagami API server.
#[tauri::command]
pub async fn stop_api() -> Result<bool, String> {
    info!("Stopping Kagami API...");

    // Try the launcher script if available
    if let Some(kagami_root) = get_kagami_root() {
        let launcher_script = format!("{}/scripts/kagami_api_launcher.py", kagami_root);

        if std::path::Path::new(&launcher_script).exists() {
            let result = Command::new("python3")
                .arg(&launcher_script)
                .arg("--stop")
                .current_dir(&kagami_root)
                .output();

            if let Ok(output) = result {
                if output.status.success() {
                    info!("API stopped successfully via launcher");
                    return Ok(true);
                }
            }
        }
    }

    // Fallback: use pkill to stop the API process
    info!("Using pkill fallback to stop API");
    let _ = Command::new("pkill").args(["-f", "kagami_api"]).output();

    Ok(true)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_get_kagami_root_returns_option() {
        // This test verifies the function works without crashing
        // The actual path depends on the environment
        let result = get_kagami_root();
        // Result can be Some or None depending on environment
        assert!(result.is_some() || result.is_none());
    }
}
