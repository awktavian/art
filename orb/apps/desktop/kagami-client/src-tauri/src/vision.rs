//! Screen Capture & Visual Intelligence
//!
//! Provides screen capture capabilities for visual understanding.
//! Enables Kagami to see what's on screen and extract text via OCR.
//!
//! Colony: Grove (e₆) — Research, Observation
//!
//! Capabilities:
//!   - Full screen capture
//!   - Window-specific capture
//!   - Region capture
//!   - Display enumeration
//!   - Image encoding (PNG, JPEG)
//!
//! Safety: h(x) ≥ 0
//!   - Requires explicit Screen Recording permission
//!   - All captures logged
//!   - No automatic credential detection

use base64::{engine::general_purpose::STANDARD as BASE64, Engine};
use serde::{Deserialize, Serialize};
use std::sync::atomic::{AtomicBool, Ordering};
use tracing::{debug, error, info, warn};

#[cfg(target_os = "macos")]
use core_graphics::display::CGDisplay;

// ============================================================================
// Permission State
// ============================================================================

/// Track if screen recording permission is granted
static SCREEN_RECORDING_AUTHORIZED: AtomicBool = AtomicBool::new(false);

// ============================================================================
// Types
// ============================================================================

/// Information about a display
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DisplayInfo {
    pub id: u32,
    pub width: u32,
    pub height: u32,
    pub is_main: bool,
    pub is_builtin: bool,
    pub scale_factor: f64,
}

/// Captured image data
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CaptureResult {
    pub success: bool,
    pub error: Option<String>,
    /// Base64-encoded image data
    pub data: Option<String>,
    /// Image format (png, jpeg)
    pub format: String,
    pub width: u32,
    pub height: u32,
}

/// Region for capture
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CaptureRegion {
    pub x: f64,
    pub y: f64,
    pub width: f64,
    pub height: f64,
}

/// Window information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WindowCaptureInfo {
    pub window_id: u32,
    pub owner_name: String,
    pub window_name: Option<String>,
    pub bounds: CaptureRegion,
    pub layer: i32,
}

// ============================================================================
// Permission Checking
// ============================================================================

/// Check if screen recording permission is granted
#[cfg(target_os = "macos")]
pub fn check_screen_recording_permission() -> bool {
    use std::process::Command;

    // Try a minimal capture using screencapture to test permission
    let temp_path = "/tmp/kagami_permission_test.png";

    let output = Command::new("screencapture")
        .args(["-x", "-R", "0,0,1,1", temp_path])
        .output();

    let authorized = match output {
        Ok(out) => out.status.success(),
        Err(_) => false,
    };

    // Clean up temp file
    let _ = std::fs::remove_file(temp_path);

    SCREEN_RECORDING_AUTHORIZED.store(authorized, Ordering::SeqCst);
    authorized
}

#[cfg(not(target_os = "macos"))]
pub fn check_screen_recording_permission() -> bool {
    false
}

/// Request screen recording permission (opens System Preferences)
#[cfg(target_os = "macos")]
pub fn request_screen_recording_permission() {
    use std::process::Command;

    info!("Opening Screen Recording preferences...");

    // Open System Preferences to Privacy > Screen Recording
    let _ = Command::new("open")
        .arg("x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture")
        .spawn();
}

#[cfg(not(target_os = "macos"))]
pub fn request_screen_recording_permission() {
    warn!("Screen recording permission request not supported on this platform");
}

// ============================================================================
// Display Enumeration
// ============================================================================

/// Get all connected displays
#[cfg(target_os = "macos")]
pub fn get_displays() -> Vec<DisplayInfo> {
    let displays = CGDisplay::active_displays().unwrap_or_default();

    displays
        .into_iter()
        .map(|id| {
            let display = CGDisplay::new(id);
            // Calculate scale factor from pixel dimensions vs logical dimensions
            // On Retina displays, pixels_wide > width in points
            let scale = if display.bounds().size.width > 0.0 {
                display.pixels_wide() as f64 / display.bounds().size.width
            } else {
                1.0
            };
            DisplayInfo {
                id,
                width: display.pixels_wide() as u32,
                height: display.pixels_high() as u32,
                is_main: display.is_main(),
                is_builtin: display.is_builtin(),
                scale_factor: scale,
            }
        })
        .collect()
}

#[cfg(not(target_os = "macos"))]
pub fn get_displays() -> Vec<DisplayInfo> {
    vec![]
}

/// Get the main display
pub fn get_main_display() -> Option<DisplayInfo> {
    get_displays().into_iter().find(|d| d.is_main)
}

// ============================================================================
// Screen Capture
// ============================================================================

/// Capture the full screen (main display)
#[cfg(target_os = "macos")]
pub fn capture_screen() -> CaptureResult {
    use std::process::Command;
    use std::fs;

    if !check_screen_recording_permission() {
        return CaptureResult {
            success: false,
            error: Some("Screen recording permission not granted".to_string()),
            data: None,
            format: "png".to_string(),
            width: 0,
            height: 0,
        };
    }

    debug!("Capturing full screen");

    let temp_path = format!("/tmp/kagami_fullscreen_{}.png", std::process::id());

    // Use screencapture for full screen capture (-x = silent)
    let output = Command::new("screencapture")
        .args(["-x", &temp_path])
        .output();

    match output {
        Ok(out) if out.status.success() => {
            match fs::read(&temp_path) {
                Ok(png_data) => {
                    let _ = fs::remove_file(&temp_path);

                    // Get dimensions from display info
                    let main_display = CGDisplay::main();
                    let width = main_display.pixels_wide() as u32;
                    let height = main_display.pixels_high() as u32;

                    let base64_data = BASE64.encode(&png_data);
                    CaptureResult {
                        success: true,
                        error: None,
                        data: Some(base64_data),
                        format: "png".to_string(),
                        width,
                        height,
                    }
                }
                Err(e) => {
                    let _ = fs::remove_file(&temp_path);
                    CaptureResult {
                        success: false,
                        error: Some(format!("Failed to read capture file: {}", e)),
                        data: None,
                        format: "png".to_string(),
                        width: 0,
                        height: 0,
                    }
                }
            }
        }
        Ok(out) => {
            let _ = fs::remove_file(&temp_path);
            CaptureResult {
                success: false,
                error: Some(format!("screencapture failed: {}", String::from_utf8_lossy(&out.stderr))),
                data: None,
                format: "png".to_string(),
                width: 0,
                height: 0,
            }
        }
        Err(e) => CaptureResult {
            success: false,
            error: Some(format!("Failed to run screencapture: {}", e)),
            data: None,
            format: "png".to_string(),
            width: 0,
            height: 0,
        },
    }
}

#[cfg(not(target_os = "macos"))]
pub fn capture_screen() -> CaptureResult {
    CaptureResult {
        success: false,
        error: Some("Not supported on this platform".to_string()),
        data: None,
        format: "png".to_string(),
        width: 0,
        height: 0,
    }
}

/// Capture a specific region of the screen
#[cfg(target_os = "macos")]
pub fn capture_region(region: CaptureRegion) -> CaptureResult {
    if !check_screen_recording_permission() {
        return CaptureResult {
            success: false,
            error: Some("Screen recording permission not granted".to_string()),
            data: None,
            format: "png".to_string(),
            width: 0,
            height: 0,
        };
    }

    debug!(
        "Capturing region: ({}, {}) {}x{}",
        region.x, region.y, region.width, region.height
    );

    capture_region_impl(region.x, region.y, region.width as u32, region.height as u32)
}

#[cfg(not(target_os = "macos"))]
pub fn capture_region(_region: CaptureRegion) -> CaptureResult {
    CaptureResult {
        success: false,
        error: Some("Not supported on this platform".to_string()),
        data: None,
        format: "png".to_string(),
        width: 0,
        height: 0,
    }
}

/// Internal implementation for region capture using screencapture command
/// This is more reliable than using CGImage APIs directly
#[cfg(target_os = "macos")]
fn capture_region_impl(x: f64, y: f64, width: u32, height: u32) -> CaptureResult {
    use std::process::Command;
    use std::fs;

    let temp_path = format!("/tmp/kagami_capture_{}.png", std::process::id());

    // Use screencapture with region flag: -R x,y,width,height
    let region_arg = format!("{},{},{},{}", x as i32, y as i32, width, height);

    let output = Command::new("screencapture")
        .args(["-x", "-R", &region_arg, &temp_path])
        .output();

    match output {
        Ok(out) if out.status.success() => {
            // Read the captured file
            match fs::read(&temp_path) {
                Ok(png_data) => {
                    let _ = fs::remove_file(&temp_path);
                    let base64_data = BASE64.encode(&png_data);
                    CaptureResult {
                        success: true,
                        error: None,
                        data: Some(base64_data),
                        format: "png".to_string(),
                        width,
                        height,
                    }
                }
                Err(e) => {
                    let _ = fs::remove_file(&temp_path);
                    CaptureResult {
                        success: false,
                        error: Some(format!("Failed to read capture file: {}", e)),
                        data: None,
                        format: "png".to_string(),
                        width: 0,
                        height: 0,
                    }
                }
            }
        }
        Ok(out) => {
            let _ = fs::remove_file(&temp_path);
            CaptureResult {
                success: false,
                error: Some(format!("screencapture failed: {}", String::from_utf8_lossy(&out.stderr))),
                data: None,
                format: "png".to_string(),
                width: 0,
                height: 0,
            }
        }
        Err(e) => CaptureResult {
            success: false,
            error: Some(format!("Failed to run screencapture: {}", e)),
            data: None,
            format: "png".to_string(),
            width: 0,
            height: 0,
        },
    }
}

// ============================================================================
// Window Capture
// ============================================================================

/// Get list of capturable windows using AppleScript
/// This approach avoids complex CoreFoundation type issues
#[cfg(target_os = "macos")]
pub fn get_windows() -> Vec<WindowCaptureInfo> {
    use std::process::Command;

    let mut windows = Vec::new();

    // Use AppleScript to get window list - more reliable and simpler
    let script = r#"
        tell application "System Events"
            set windowList to {}
            repeat with proc in (every process whose visible is true)
                try
                    repeat with win in (every window of proc)
                        set winName to name of win
                        set winPos to position of win
                        set winSize to size of win
                        set procName to name of proc
                        set end of windowList to procName & "|||" & winName & "|||" & (item 1 of winPos as string) & "|||" & (item 2 of winPos as string) & "|||" & (item 1 of winSize as string) & "|||" & (item 2 of winSize as string)
                    end repeat
                end try
            end repeat
            return windowList
        end tell
    "#;

    let output = Command::new("osascript")
        .arg("-e")
        .arg(script)
        .output();

    if let Ok(out) = output {
        if out.status.success() {
            let stdout = String::from_utf8_lossy(&out.stdout);
            let mut window_id: u32 = 1;

            // Parse the output format: "procName|||winName|||x|||y|||w|||h, ..."
            for part in stdout.split(", ") {
                let fields: Vec<&str> = part.trim().split("|||").collect();
                if fields.len() >= 6 {
                    let owner_name = fields[0].to_string();
                    let window_name = if fields[1].is_empty() {
                        None
                    } else {
                        Some(fields[1].to_string())
                    };

                    let x: f64 = fields[2].parse().unwrap_or(0.0);
                    let y: f64 = fields[3].parse().unwrap_or(0.0);
                    let width: f64 = fields[4].parse().unwrap_or(0.0);
                    let height: f64 = fields[5].parse().unwrap_or(0.0);

                    windows.push(WindowCaptureInfo {
                        window_id,
                        owner_name,
                        window_name,
                        bounds: CaptureRegion { x, y, width, height },
                        layer: 0,
                    });

                    window_id += 1;
                }
            }
        }
    }

    windows
}

#[cfg(not(target_os = "macos"))]
pub fn get_windows() -> Vec<WindowCaptureInfo> {
    vec![]
}

/// Capture a specific window by ID
/// Since we use AppleScript for window listing (which generates synthetic IDs),
/// we capture by region using the window bounds
#[cfg(target_os = "macos")]
pub fn capture_window(window_id: u32) -> CaptureResult {
    if !check_screen_recording_permission() {
        return CaptureResult {
            success: false,
            error: Some("Screen recording permission not granted".to_string()),
            data: None,
            format: "png".to_string(),
            width: 0,
            height: 0,
        };
    }

    debug!("Capturing window: {}", window_id);

    // Find the window bounds
    let windows = get_windows();
    let window = windows.iter().find(|w| w.window_id == window_id);

    match window {
        Some(w) => {
            // Capture the region where the window is located
            capture_region_impl(
                w.bounds.x,
                w.bounds.y,
                w.bounds.width as u32,
                w.bounds.height as u32,
            )
        }
        None => CaptureResult {
            success: false,
            error: Some(format!("Window {} not found", window_id)),
            data: None,
            format: "png".to_string(),
            width: 0,
            height: 0,
        },
    }
}

#[cfg(not(target_os = "macos"))]
pub fn capture_window(_window_id: u32) -> CaptureResult {
    CaptureResult {
        success: false,
        error: Some("Not supported on this platform".to_string()),
        data: None,
        format: "png".to_string(),
        width: 0,
        height: 0,
    }
}

// ============================================================================
// Tauri Commands
// ============================================================================

/// Check screen recording permission
#[tauri::command]
pub async fn vision_check_permission() -> Result<bool, String> {
    Ok(check_screen_recording_permission())
}

/// Request screen recording permission
#[tauri::command]
pub async fn vision_request_permission() -> Result<(), String> {
    request_screen_recording_permission();
    Ok(())
}

/// Get all displays
#[tauri::command]
pub async fn vision_get_displays() -> Result<Vec<DisplayInfo>, String> {
    Ok(get_displays())
}

/// Capture the full screen
#[tauri::command]
pub async fn vision_capture_screen() -> Result<CaptureResult, String> {
    Ok(capture_screen())
}

/// Capture a region of the screen
#[tauri::command]
pub async fn vision_capture_region(region: CaptureRegion) -> Result<CaptureResult, String> {
    Ok(capture_region(region))
}

/// Get list of windows
#[tauri::command]
pub async fn vision_get_windows() -> Result<Vec<WindowCaptureInfo>, String> {
    Ok(get_windows())
}

/// Capture a specific window
#[tauri::command]
pub async fn vision_capture_window(window_id: u32) -> Result<CaptureResult, String> {
    Ok(capture_window(window_id))
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_display_info_serialization() {
        let display = DisplayInfo {
            id: 1,
            width: 2560,
            height: 1440,
            is_main: true,
            is_builtin: false,
            scale_factor: 2.0,
        };

        let json = serde_json::to_string(&display).unwrap();
        assert!(json.contains("2560"));
        assert!(json.contains("is_main"));
    }

    #[test]
    fn test_capture_region_serialization() {
        let region = CaptureRegion {
            x: 100.0,
            y: 200.0,
            width: 800.0,
            height: 600.0,
        };

        let json = serde_json::to_string(&region).unwrap();
        assert!(json.contains("100"));
        assert!(json.contains("600"));
    }

    #[test]
    fn test_capture_result_error() {
        let result = CaptureResult {
            success: false,
            error: Some("Test error".to_string()),
            data: None,
            format: "png".to_string(),
            width: 0,
            height: 0,
        };

        assert!(!result.success);
        assert!(result.error.is_some());
        assert!(result.data.is_none());
    }
}

/*
 * 鏡
 * h(x) ≥ 0. Always.
 *
 * Vision is understanding.
 * Capture with permission.
 * See with intention.
 */
