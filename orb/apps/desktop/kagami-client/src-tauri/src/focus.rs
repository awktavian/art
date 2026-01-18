//! macOS Focus Mode Integration
//!
//! Detects when Do Not Disturb or Focus modes are active and
//! suppresses notifications accordingly.
//!
//! Colony: Sentinel (e1) - Awareness, sensing
//!
//! macOS Focus modes include:
//! - Do Not Disturb
//! - Sleep
//! - Work
//! - Personal
//! - Custom Focus modes
//!
//! When Focus is active:
//! - Suppress non-critical notifications
//! - Still allow safety alerts (h(x) < 0)
//! - Update tray status to show [Focus] indicator

use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use tracing::debug;

/// Cached Focus mode state (to avoid frequent system calls)
static FOCUS_ACTIVE: AtomicBool = AtomicBool::new(false);
static LAST_CHECK_MS: AtomicU64 = AtomicU64::new(0);

/// Cache duration for Focus mode state (milliseconds)
const CACHE_DURATION_MS: u64 = 5000;

/// Check if Focus mode is currently active (cached)
pub fn is_focus_active() -> bool {
    let now_ms = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as u64;

    let last_check = LAST_CHECK_MS.load(Ordering::Relaxed);

    // Use cached value if recent
    if now_ms - last_check < CACHE_DURATION_MS {
        return FOCUS_ACTIVE.load(Ordering::Relaxed);
    }

    // Update cache
    let active = check_focus_mode_impl();
    FOCUS_ACTIVE.store(active, Ordering::Relaxed);
    LAST_CHECK_MS.store(now_ms, Ordering::Relaxed);

    active
}

/// Force refresh Focus mode state
pub fn refresh_focus_state() -> bool {
    let active = check_focus_mode_impl();
    FOCUS_ACTIVE.store(active, Ordering::Relaxed);
    let now_ms = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as u64;
    LAST_CHECK_MS.store(now_ms, Ordering::Relaxed);
    active
}

/// Implementation of Focus mode detection
#[cfg(target_os = "macos")]
fn check_focus_mode_impl() -> bool {
    use std::process::Command;

    // Method 1: Check Focus mode via notification center
    // The assertionstate indicates if Focus/DND is active
    let result = Command::new("sh")
        .args(["-c", r#"
            # Check for active Focus mode assertions
            # The DoNotDisturb daemon stores assertion state
            if [ -f ~/Library/DoNotDisturb/DB/Assertions.json ]; then
                if plutil -convert json -o - ~/Library/DoNotDisturb/DB/Assertions.json 2>/dev/null | grep -q '"storeAssertionRecords"'; then
                    # Has assertions, check if any are active
                    plutil -convert json -o - ~/Library/DoNotDisturb/DB/Assertions.json 2>/dev/null | grep -c 'assertionUUID' || echo 0
                else
                    echo 0
                fi
            else
                echo 0
            fi
        "#])
        .output();

    if let Ok(output) = result {
        let stdout = String::from_utf8_lossy(&output.stdout);
        if let Ok(count) = stdout.trim().parse::<i32>() {
            if count > 0 {
                debug!("Focus mode active (assertion count: {})", count);
                return true;
            }
        }
    }

    // Method 2: Check ModeConfigurations for active modes
    let result2 = Command::new("sh")
        .args(["-c", r#"
            if [ -f ~/Library/DoNotDisturb/DB/ModeConfigurations.json ]; then
                plutil -convert json -o - ~/Library/DoNotDisturb/DB/ModeConfigurations.json 2>/dev/null | grep -c '"isActive" *: *true' || echo 0
            else
                echo 0
            fi
        "#])
        .output();

    if let Ok(output) = result2 {
        let stdout = String::from_utf8_lossy(&output.stdout);
        if let Ok(count) = stdout.trim().parse::<i32>() {
            if count > 0 {
                debug!("Focus mode active (mode configuration)");
                return true;
            }
        }
    }

    // Method 3: Check Control Center status item visibility
    let result3 = Command::new("defaults")
        .args(["read", "com.apple.controlcenter", "NSStatusItem Visible FocusModes"])
        .output();

    if let Ok(output) = result3 {
        let stdout = String::from_utf8_lossy(&output.stdout);
        if stdout.trim() == "1" {
            // Focus indicator is visible, but this doesn't mean Focus is ON
            // It just means the user has chosen to show it in menu bar
            // We need the other methods to confirm actual Focus state
            debug!("Focus menu bar item visible");
        }
    }

    false
}

/// Windows Focus Assist detection
#[cfg(target_os = "windows")]
fn check_focus_mode_impl() -> bool {
    use std::process::Command;

    // Query Windows Focus Assist status via PowerShell
    // Focus Assist is stored in the registry
    let result = Command::new("powershell")
        .args(["-Command", r#"
            try {
                $path = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\CloudStore\Store\DefaultAccount\Current\default$windows.data.shell.quiethours\windows.data.shell.quiethours'
                if (Test-Path $path) {
                    $data = (Get-ItemProperty -Path $path -Name 'Data' -ErrorAction SilentlyContinue).Data
                    if ($data -and $data.Length -gt 12) {
                        # Focus Assist state is stored in byte 12
                        $state = $data[12]
                        if ($state -eq 1 -or $state -eq 2) {
                            Write-Output 'active'
                            exit
                        }
                    }
                }
                Write-Output 'inactive'
            } catch {
                Write-Output 'inactive'
            }
        "#])
        .output();

    if let Ok(output) = result {
        let stdout = String::from_utf8_lossy(&output.stdout);
        if stdout.trim() == "active" {
            tracing::debug!("Windows Focus Assist is active");
            return true;
        }
    }

    false
}

/// Linux Focus mode detection (GNOME Do Not Disturb)
#[cfg(target_os = "linux")]
fn check_focus_mode_impl() -> bool {
    use std::process::Command;

    // Check GNOME Do Not Disturb setting
    let result = Command::new("gsettings")
        .args(["get", "org.gnome.desktop.notifications", "show-banners"])
        .output();

    if let Ok(output) = result {
        let stdout = String::from_utf8_lossy(&output.stdout);
        // show-banners=false means DND is on
        if stdout.trim() == "false" {
            tracing::debug!("Linux DND (GNOME) is active");
            return true;
        }
    }

    // Check KDE Do Not Disturb
    let kde_result = Command::new("qdbus")
        .args(["org.freedesktop.Notifications", "/org/freedesktop/Notifications", "org.freedesktop.Notifications.Inhibited"])
        .output();

    if let Ok(output) = kde_result {
        let stdout = String::from_utf8_lossy(&output.stdout);
        if stdout.trim() == "true" {
            tracing::debug!("Linux DND (KDE) is active");
            return true;
        }
    }

    false
}

/// Fallback for other platforms
#[cfg(not(any(target_os = "macos", target_os = "windows", target_os = "linux")))]
fn check_focus_mode_impl() -> bool {
    false
}

/// Notification priority levels
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum NotificationPriority {
    /// Low priority: suppress during Focus
    Low,
    /// Normal priority: suppress during Focus
    Normal,
    /// High priority: show during Focus (for important alerts)
    High,
    /// Critical priority: always show (safety alerts)
    Critical,
}

/// Check if a notification should be shown based on Focus mode and priority
pub fn should_show_notification(priority: NotificationPriority) -> bool {
    let focus_active = is_focus_active();

    if !focus_active {
        // No Focus mode, show all notifications
        return true;
    }

    // Focus mode is active, check priority
    match priority {
        NotificationPriority::Low | NotificationPriority::Normal => {
            debug!("Suppressing notification (Focus mode active, priority: {:?})", priority);
            false
        }
        NotificationPriority::High | NotificationPriority::Critical => {
            debug!("Allowing notification despite Focus mode (priority: {:?})", priority);
            true
        }
    }
}

/// Get the current Focus mode name (if any)
#[cfg(target_os = "macos")]
pub fn get_focus_mode_name() -> Option<String> {
    use std::process::Command;

    let result = Command::new("sh")
        .args(["-c", r#"
            if [ -f ~/Library/DoNotDisturb/DB/ModeConfigurations.json ]; then
                # Extract active mode name
                plutil -convert json -o - ~/Library/DoNotDisturb/DB/ModeConfigurations.json 2>/dev/null | \
                    grep -A5 '"isActive" *: *true' | \
                    grep '"name"' | \
                    head -1 | \
                    sed 's/.*"name" *: *"\([^"]*\)".*/\1/'
            fi
        "#])
        .output();

    if let Ok(output) = result {
        let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
        if !stdout.is_empty() {
            return Some(stdout);
        }
    }

    None
}

#[cfg(not(target_os = "macos"))]
pub fn get_focus_mode_name() -> Option<String> {
    None
}

/// Focus mode configuration
#[derive(Debug, Clone)]
pub struct FocusConfig {
    /// Whether to suppress notifications during Focus
    pub suppress_notifications: bool,
    /// Whether to suppress audio announcements during Focus
    pub suppress_audio: bool,
    /// Whether to show Focus indicator in tray
    pub show_indicator: bool,
    /// Minimum priority to show during Focus
    pub min_priority: NotificationPriority,
}

impl Default for FocusConfig {
    fn default() -> Self {
        Self {
            suppress_notifications: true,
            suppress_audio: true,
            show_indicator: true,
            min_priority: NotificationPriority::High,
        }
    }
}
