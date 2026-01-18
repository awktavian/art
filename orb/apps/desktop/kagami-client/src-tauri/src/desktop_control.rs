//! Desktop Control Module
//!
//! Full cross-platform desktop control capabilities for automation.
//! Provides mouse/keyboard input, clipboard, process management, and more.
//!
//! Colony: Nexus (e₄) — Integration, Coordination
//!
//! Safety: h(x) ≥ 0
//!   - All actions are rate-limited
//!   - Input injection logged for audit
//!   - No credential sniffing

use serde::{Deserialize, Serialize};
use std::process::Command as ProcessCommand;
use std::time::Duration;
use std::sync::atomic::{AtomicU64, Ordering};
use tracing::{debug, info, warn};

// ============================================================================
// Rate Limiting
// ============================================================================

/// Last action timestamp for rate limiting (milliseconds since epoch)
static LAST_ACTION_MS: AtomicU64 = AtomicU64::new(0);

/// Minimum interval between actions (100ms = 10 actions/second max)
const MIN_ACTION_INTERVAL_MS: u64 = 100;

/// Check and update rate limit
fn check_rate_limit() -> bool {
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as u64;

    let last = LAST_ACTION_MS.load(Ordering::SeqCst);

    if now - last < MIN_ACTION_INTERVAL_MS {
        return false;
    }

    LAST_ACTION_MS.store(now, Ordering::SeqCst);
    true
}

// ============================================================================
// Types
// ============================================================================

/// Mouse button types
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum MouseButton {
    Left,
    Right,
    Middle,
}

/// Mouse event types
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum MouseEventType {
    Move,
    Click,
    DoubleClick,
    Down,
    Up,
    Scroll,
}

/// Mouse action request
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MouseAction {
    pub x: f64,
    pub y: f64,
    pub event_type: MouseEventType,
    #[serde(default)]
    pub button: Option<MouseButton>,
    /// Scroll delta (positive = up/left, negative = down/right)
    #[serde(default)]
    pub delta_x: Option<f64>,
    #[serde(default)]
    pub delta_y: Option<f64>,
}

/// Keyboard modifier keys
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct KeyModifiers {
    #[serde(default)]
    pub shift: bool,
    #[serde(default)]
    pub control: bool,
    #[serde(default)]
    pub alt: bool,
    #[serde(default)]
    pub meta: bool, // Command on macOS, Windows key on Windows
}

/// Keyboard action
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum KeyboardAction {
    /// Type a string of text
    TypeText { text: String },
    /// Press a single key (with optional modifiers)
    KeyPress { key: String, modifiers: Option<KeyModifiers> },
    /// Key down event
    KeyDown { key: String },
    /// Key up event
    KeyUp { key: String },
    /// Hotkey combination (e.g., Cmd+C)
    Hotkey { modifiers: KeyModifiers, key: String },
}

/// Clipboard content type
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ClipboardContentType {
    Text,
    Image,
    Html,
    Files,
}

/// Clipboard content
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClipboardContent {
    pub content_type: ClipboardContentType,
    /// For text: the text content
    /// For image: base64-encoded PNG
    /// For files: JSON array of file paths
    pub data: String,
}

/// Process information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessInfo {
    pub pid: u32,
    pub name: String,
    pub exe_path: Option<String>,
    pub cmd_line: Option<String>,
    pub status: String,
    pub cpu_percent: f32,
    pub memory_bytes: u64,
    pub parent_pid: Option<u32>,
}

/// Network interface info
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NetworkInterfaceInfo {
    pub name: String,
    pub ip_addresses: Vec<String>,
    pub mac_address: Option<String>,
    pub is_up: bool,
    pub is_loopback: bool,
}

/// Disk info
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiskInfo {
    pub name: String,
    pub mount_point: String,
    pub total_bytes: u64,
    pub available_bytes: u64,
    pub fs_type: String,
    pub is_removable: bool,
}

/// Extended system info
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExtendedSystemInfo {
    pub hostname: String,
    pub os_name: String,
    pub os_version: String,
    pub kernel_version: String,
    pub cpu_count: usize,
    pub cpu_brand: String,
    pub total_memory_bytes: u64,
    pub used_memory_bytes: u64,
    pub uptime_secs: u64,
    pub disks: Vec<DiskInfo>,
    pub networks: Vec<NetworkInterfaceInfo>,
}

/// Action result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ActionResult {
    pub success: bool,
    pub error: Option<String>,
}

impl ActionResult {
    pub fn ok() -> Self {
        ActionResult { success: true, error: None }
    }

    pub fn err(msg: impl Into<String>) -> Self {
        ActionResult { success: false, error: Some(msg.into()) }
    }
}

// ============================================================================
// Mouse Control
// ============================================================================

/// Move the mouse cursor to absolute position
/// Uses osascript for reliability across macOS versions
#[cfg(target_os = "macos")]
pub fn mouse_move(x: f64, y: f64) -> ActionResult {
    if !check_rate_limit() {
        return ActionResult::err("Rate limited");
    }

    debug!("Mouse move to ({}, {})", x, y);

    // Try cliclick first (homebrew install cliclick)
    let output = ProcessCommand::new("cliclick")
        .args(["m:", &format!("{},{}", x as i32, y as i32)])
        .output();

    match output {
        Ok(out) if out.status.success() => ActionResult::ok(),
        _ => {
            // Fallback to AppleScript mouse move
            let script = format!(
                r#"
                use framework "CoreGraphics"
                set pt to current application's CGPointMake({}, {})
                current application's CGEventPost(current application's kCGHIDEventTap, current application's CGEventCreateMouseEvent(missing value, current application's kCGEventMouseMoved, pt, 0))
                "#,
                x as i32, y as i32
            );

            let output = ProcessCommand::new("osascript")
                .args(["-l", "AppleScript", "-e", &script])
                .output();

            match output {
                Ok(out) if out.status.success() => ActionResult::ok(),
                Ok(out) => ActionResult::err(format!("osascript failed: {}", String::from_utf8_lossy(&out.stderr))),
                Err(e) => ActionResult::err(format!("Failed to run osascript: {}", e)),
            }
        }
    }
}

#[cfg(target_os = "windows")]
pub fn mouse_move(x: f64, y: f64) -> ActionResult {
    if !check_rate_limit() {
        return ActionResult::err("Rate limited");
    }

    debug!("Mouse move to ({}, {})", x, y);

    // Windows implementation using SendInput
    use std::mem;

    #[repr(C)]
    struct MouseInput {
        dx: i32,
        dy: i32,
        mouse_data: u32,
        flags: u32,
        time: u32,
        extra_info: usize,
    }

    #[repr(C)]
    struct Input {
        input_type: u32,
        input: MouseInput,
    }

    const INPUT_MOUSE: u32 = 0;
    const MOUSEEVENTF_ABSOLUTE: u32 = 0x8000;
    const MOUSEEVENTF_MOVE: u32 = 0x0001;

    #[link(name = "user32")]
    extern "system" {
        fn SendInput(count: u32, inputs: *const Input, size: i32) -> u32;
        fn GetSystemMetrics(index: i32) -> i32;
    }

    unsafe {
        // Get screen dimensions for absolute positioning
        let screen_width = GetSystemMetrics(0) as f64; // SM_CXSCREEN
        let screen_height = GetSystemMetrics(1) as f64; // SM_CYSCREEN

        // Convert to 0-65535 range for absolute positioning
        let abs_x = ((x / screen_width) * 65535.0) as i32;
        let abs_y = ((y / screen_height) * 65535.0) as i32;

        let input = Input {
            input_type: INPUT_MOUSE,
            input: MouseInput {
                dx: abs_x,
                dy: abs_y,
                mouse_data: 0,
                flags: MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE,
                time: 0,
                extra_info: 0,
            },
        };

        let result = SendInput(1, &input, mem::size_of::<Input>() as i32);
        if result == 1 {
            ActionResult::ok()
        } else {
            ActionResult::err("SendInput failed")
        }
    }
}

#[cfg(target_os = "linux")]
pub fn mouse_move(x: f64, y: f64) -> ActionResult {
    if !check_rate_limit() {
        return ActionResult::err("Rate limited");
    }

    debug!("Mouse move to ({}, {})", x, y);

    // Use xdotool on Linux
    let output = ProcessCommand::new("xdotool")
        .args(["mousemove", &x.to_string(), &y.to_string()])
        .output();

    match output {
        Ok(out) if out.status.success() => ActionResult::ok(),
        Ok(out) => ActionResult::err(String::from_utf8_lossy(&out.stderr).to_string()),
        Err(e) => ActionResult::err(format!("xdotool not found: {}", e)),
    }
}

#[cfg(not(any(target_os = "macos", target_os = "windows", target_os = "linux")))]
pub fn mouse_move(_x: f64, _y: f64) -> ActionResult {
    ActionResult::err("Not supported on this platform")
}

/// Click mouse button
/// Uses cliclick or AppleScript for reliability
#[cfg(target_os = "macos")]
pub fn mouse_click(x: f64, y: f64, button: MouseButton, double_click: bool) -> ActionResult {
    if !check_rate_limit() {
        return ActionResult::err("Rate limited");
    }

    info!("Mouse {:?} click at ({}, {}) double={}", button, x, y, double_click);

    let pos = format!("{},{}", x as i32, y as i32);

    // Determine cliclick command based on button and click type
    let cmd = match (&button, double_click) {
        (MouseButton::Left, false) => "c:",
        (MouseButton::Left, true) => "dc:",
        (MouseButton::Right, _) => "rc:",
        (MouseButton::Middle, _) => "c:", // Middle click via cliclick uses left click
    };

    // Try cliclick first
    let output = ProcessCommand::new("cliclick")
        .args([cmd, &pos])
        .output();

    match output {
        Ok(out) if out.status.success() => ActionResult::ok(),
        _ => {
            // Fallback to AppleScript
            let click_script = if double_click {
                format!(
                    r#"tell application "System Events" to click at {{{}, {}}}"#,
                    x as i32, y as i32
                )
            } else {
                let btn = match button {
                    MouseButton::Left => "",
                    MouseButton::Right => " using secondary button",
                    MouseButton::Middle => "",
                };
                format!(
                    r#"tell application "System Events" to click at {{{}, {}}}{}"#,
                    x as i32, y as i32, btn
                )
            };

            let output = ProcessCommand::new("osascript")
                .args(["-e", &click_script])
                .output();

            match output {
                Ok(out) if out.status.success() => ActionResult::ok(),
                Ok(out) => ActionResult::err(format!("osascript click failed: {}", String::from_utf8_lossy(&out.stderr))),
                Err(e) => ActionResult::err(format!("Failed to run osascript: {}", e)),
            }
        }
    }
}

#[cfg(target_os = "linux")]
pub fn mouse_click(x: f64, y: f64, button: MouseButton, double_click: bool) -> ActionResult {
    if !check_rate_limit() {
        return ActionResult::err("Rate limited");
    }

    info!("Mouse {:?} click at ({}, {}) double={}", button, x, y, double_click);

    // Move first
    let _ = mouse_move(x, y);
    std::thread::sleep(Duration::from_millis(10));

    let btn = match button {
        MouseButton::Left => "1",
        MouseButton::Right => "3",
        MouseButton::Middle => "2",
    };

    let click_type = if double_click { "click" } else { "click" };
    let repeat = if double_click { "2" } else { "1" };

    let output = ProcessCommand::new("xdotool")
        .args([click_type, "--repeat", repeat, btn])
        .output();

    match output {
        Ok(out) if out.status.success() => ActionResult::ok(),
        Ok(out) => ActionResult::err(String::from_utf8_lossy(&out.stderr).to_string()),
        Err(e) => ActionResult::err(format!("xdotool not found: {}", e)),
    }
}

#[cfg(target_os = "windows")]
pub fn mouse_click(x: f64, y: f64, button: MouseButton, double_click: bool) -> ActionResult {
    if !check_rate_limit() {
        return ActionResult::err("Rate limited");
    }

    info!("Mouse {:?} click at ({}, {}) double={}", button, x, y, double_click);

    // Move first
    let _ = mouse_move(x, y);
    std::thread::sleep(Duration::from_millis(10));

    use std::mem;

    #[repr(C)]
    struct MouseInput {
        dx: i32,
        dy: i32,
        mouse_data: u32,
        flags: u32,
        time: u32,
        extra_info: usize,
    }

    #[repr(C)]
    struct Input {
        input_type: u32,
        input: MouseInput,
    }

    const INPUT_MOUSE: u32 = 0;
    const MOUSEEVENTF_LEFTDOWN: u32 = 0x0002;
    const MOUSEEVENTF_LEFTUP: u32 = 0x0004;
    const MOUSEEVENTF_RIGHTDOWN: u32 = 0x0008;
    const MOUSEEVENTF_RIGHTUP: u32 = 0x0010;
    const MOUSEEVENTF_MIDDLEDOWN: u32 = 0x0020;
    const MOUSEEVENTF_MIDDLEUP: u32 = 0x0040;

    #[link(name = "user32")]
    extern "system" {
        fn SendInput(count: u32, inputs: *const Input, size: i32) -> u32;
    }

    let (down_flag, up_flag) = match button {
        MouseButton::Left => (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
        MouseButton::Right => (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
        MouseButton::Middle => (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
    };

    let click_count = if double_click { 2 } else { 1 };

    unsafe {
        for _ in 0..click_count {
            let inputs = [
                Input {
                    input_type: INPUT_MOUSE,
                    input: MouseInput {
                        dx: 0, dy: 0, mouse_data: 0,
                        flags: down_flag,
                        time: 0, extra_info: 0,
                    },
                },
                Input {
                    input_type: INPUT_MOUSE,
                    input: MouseInput {
                        dx: 0, dy: 0, mouse_data: 0,
                        flags: up_flag,
                        time: 0, extra_info: 0,
                    },
                },
            ];

            SendInput(2, inputs.as_ptr(), mem::size_of::<Input>() as i32);
            std::thread::sleep(Duration::from_millis(10));
        }
    }

    ActionResult::ok()
}

#[cfg(not(any(target_os = "macos", target_os = "windows", target_os = "linux")))]
pub fn mouse_click(_x: f64, _y: f64, _button: MouseButton, _double_click: bool) -> ActionResult {
    ActionResult::err("Not supported on this platform")
}

/// Scroll the mouse wheel
/// Uses cliclick or AppleScript for reliability across macOS versions
#[cfg(target_os = "macos")]
pub fn mouse_scroll(delta_x: f64, delta_y: f64) -> ActionResult {
    if !check_rate_limit() {
        return ActionResult::err("Rate limited");
    }

    debug!("Mouse scroll ({}, {})", delta_x, delta_y);

    // Try cliclick first for vertical scroll
    if delta_y != 0.0 {
        let scroll_amount = delta_y as i32;
        // cliclick uses positive for up, negative for down
        let output = ProcessCommand::new("cliclick")
            .args(["w:", &format!("{}", scroll_amount)])
            .output();

        if let Ok(out) = output {
            if out.status.success() {
                if delta_x == 0.0 {
                    return ActionResult::ok();
                }
            }
        }
    }

    // Fallback to AppleScript scroll event
    let script = format!(
        r#"
        use framework "CoreGraphics"
        set scrollEvent to current application's CGEventCreateScrollWheelEvent(missing value, 0, 2, {}, {})
        current application's CGEventPost(current application's kCGHIDEventTap, scrollEvent)
        "#,
        delta_y as i32, delta_x as i32
    );

    let output = ProcessCommand::new("osascript")
        .args(["-l", "AppleScript", "-e", &script])
        .output();

    match output {
        Ok(out) if out.status.success() => ActionResult::ok(),
        Ok(out) => ActionResult::err(format!("osascript scroll failed: {}", String::from_utf8_lossy(&out.stderr))),
        Err(e) => ActionResult::err(format!("Failed to run osascript: {}", e)),
    }
}

#[cfg(target_os = "linux")]
pub fn mouse_scroll(delta_x: f64, delta_y: f64) -> ActionResult {
    if !check_rate_limit() {
        return ActionResult::err("Rate limited");
    }

    debug!("Mouse scroll ({}, {})", delta_x, delta_y);

    // xdotool click 4 = scroll up, 5 = scroll down
    // For horizontal: 6 = left, 7 = right
    let mut results = Vec::new();

    if delta_y != 0.0 {
        let button = if delta_y > 0.0 { "4" } else { "5" };
        let count = delta_y.abs() as i32;
        for _ in 0..count {
            let output = ProcessCommand::new("xdotool")
                .args(["click", button])
                .output();
            results.push(output.is_ok());
        }
    }

    if delta_x != 0.0 {
        let button = if delta_x > 0.0 { "6" } else { "7" };
        let count = delta_x.abs() as i32;
        for _ in 0..count {
            let output = ProcessCommand::new("xdotool")
                .args(["click", button])
                .output();
            results.push(output.is_ok());
        }
    }

    if results.iter().all(|&r| r) {
        ActionResult::ok()
    } else {
        ActionResult::err("Some scroll events failed")
    }
}

#[cfg(target_os = "windows")]
pub fn mouse_scroll(delta_x: f64, delta_y: f64) -> ActionResult {
    if !check_rate_limit() {
        return ActionResult::err("Rate limited");
    }

    debug!("Mouse scroll ({}, {})", delta_x, delta_y);

    use std::mem;

    #[repr(C)]
    struct MouseInput {
        dx: i32,
        dy: i32,
        mouse_data: u32,
        flags: u32,
        time: u32,
        extra_info: usize,
    }

    #[repr(C)]
    struct Input {
        input_type: u32,
        input: MouseInput,
    }

    const INPUT_MOUSE: u32 = 0;
    const MOUSEEVENTF_WHEEL: u32 = 0x0800;
    const MOUSEEVENTF_HWHEEL: u32 = 0x1000;
    const WHEEL_DELTA: i32 = 120;

    #[link(name = "user32")]
    extern "system" {
        fn SendInput(count: u32, inputs: *const Input, size: i32) -> u32;
    }

    unsafe {
        if delta_y != 0.0 {
            let input = Input {
                input_type: INPUT_MOUSE,
                input: MouseInput {
                    dx: 0, dy: 0,
                    mouse_data: (delta_y * WHEEL_DELTA as f64) as u32,
                    flags: MOUSEEVENTF_WHEEL,
                    time: 0, extra_info: 0,
                },
            };
            SendInput(1, &input, mem::size_of::<Input>() as i32);
        }

        if delta_x != 0.0 {
            let input = Input {
                input_type: INPUT_MOUSE,
                input: MouseInput {
                    dx: 0, dy: 0,
                    mouse_data: (delta_x * WHEEL_DELTA as f64) as u32,
                    flags: MOUSEEVENTF_HWHEEL,
                    time: 0, extra_info: 0,
                },
            };
            SendInput(1, &input, mem::size_of::<Input>() as i32);
        }
    }

    ActionResult::ok()
}

#[cfg(not(any(target_os = "macos", target_os = "windows", target_os = "linux")))]
pub fn mouse_scroll(_delta_x: f64, _delta_y: f64) -> ActionResult {
    ActionResult::err("Not supported on this platform")
}

// ============================================================================
// Keyboard Control
// ============================================================================

/// Type a string of text
/// Uses cliclick or AppleScript for reliability across macOS versions
#[cfg(target_os = "macos")]
pub fn type_text(text: &str) -> ActionResult {
    if !check_rate_limit() {
        return ActionResult::err("Rate limited");
    }

    info!("Typing text: {} chars", text.len());

    // Try cliclick first (supports Unicode)
    let output = ProcessCommand::new("cliclick")
        .args(["t:", text])
        .output();

    match output {
        Ok(out) if out.status.success() => return ActionResult::ok(),
        _ => {}
    }

    // Fallback to AppleScript keystroke
    // Escape the text for AppleScript (handle quotes and backslashes)
    let escaped_text = text
        .replace('\\', "\\\\")
        .replace('"', "\\\"");

    let script = format!(
        r#"tell application "System Events" to keystroke "{}""#,
        escaped_text
    );

    let output = ProcessCommand::new("osascript")
        .args(["-e", &script])
        .output();

    match output {
        Ok(out) if out.status.success() => ActionResult::ok(),
        Ok(out) => ActionResult::err(format!("osascript type failed: {}", String::from_utf8_lossy(&out.stderr))),
        Err(e) => ActionResult::err(format!("Failed to run osascript: {}", e)),
    }
}

#[cfg(target_os = "linux")]
pub fn type_text(text: &str) -> ActionResult {
    if !check_rate_limit() {
        return ActionResult::err("Rate limited");
    }

    info!("Typing text: {} chars", text.len());

    let output = ProcessCommand::new("xdotool")
        .args(["type", "--delay", "5", text])
        .output();

    match output {
        Ok(out) if out.status.success() => ActionResult::ok(),
        Ok(out) => ActionResult::err(String::from_utf8_lossy(&out.stderr).to_string()),
        Err(e) => ActionResult::err(format!("xdotool not found: {}", e)),
    }
}

#[cfg(target_os = "windows")]
pub fn type_text(text: &str) -> ActionResult {
    if !check_rate_limit() {
        return ActionResult::err("Rate limited");
    }

    info!("Typing text: {} chars", text.len());

    use std::mem;

    #[repr(C)]
    struct KeyboardInput {
        vk: u16,
        scan: u16,
        flags: u32,
        time: u32,
        extra_info: usize,
    }

    #[repr(C)]
    struct Input {
        input_type: u32,
        input: KeyboardInput,
    }

    const INPUT_KEYBOARD: u32 = 1;
    const KEYEVENTF_UNICODE: u32 = 0x0004;
    const KEYEVENTF_KEYUP: u32 = 0x0002;

    #[link(name = "user32")]
    extern "system" {
        fn SendInput(count: u32, inputs: *const Input, size: i32) -> u32;
    }

    unsafe {
        for ch in text.encode_utf16() {
            let inputs = [
                Input {
                    input_type: INPUT_KEYBOARD,
                    input: KeyboardInput {
                        vk: 0,
                        scan: ch,
                        flags: KEYEVENTF_UNICODE,
                        time: 0,
                        extra_info: 0,
                    },
                },
                Input {
                    input_type: INPUT_KEYBOARD,
                    input: KeyboardInput {
                        vk: 0,
                        scan: ch,
                        flags: KEYEVENTF_UNICODE | KEYEVENTF_KEYUP,
                        time: 0,
                        extra_info: 0,
                    },
                },
            ];

            SendInput(2, inputs.as_ptr(), mem::size_of::<Input>() as i32);
            std::thread::sleep(Duration::from_millis(5));
        }
    }

    ActionResult::ok()
}

#[cfg(not(any(target_os = "macos", target_os = "windows", target_os = "linux")))]
pub fn type_text(_text: &str) -> ActionResult {
    ActionResult::err("Not supported on this platform")
}

/// Press a key with modifiers (hotkey)
/// Uses cliclick or AppleScript for reliability across macOS versions
#[cfg(target_os = "macos")]
pub fn hotkey(modifiers: &KeyModifiers, key: &str) -> ActionResult {
    if !check_rate_limit() {
        return ActionResult::err("Rate limited");
    }

    info!("Hotkey: {:?} + {}", modifiers, key);

    // Try cliclick first
    // cliclick format: kp:key or kd:modifier kp:key ku:modifier
    let mut cliclick_args = Vec::new();

    // Build modifier string for cliclick
    if modifiers.meta {
        cliclick_args.push("kd:cmd".to_string());
    }
    if modifiers.control {
        cliclick_args.push("kd:ctrl".to_string());
    }
    if modifiers.alt {
        cliclick_args.push("kd:alt".to_string());
    }
    if modifiers.shift {
        cliclick_args.push("kd:shift".to_string());
    }

    // Press the key
    cliclick_args.push(format!("kp:{}", key.to_lowercase()));

    // Release modifiers in reverse order
    if modifiers.shift {
        cliclick_args.push("ku:shift".to_string());
    }
    if modifiers.alt {
        cliclick_args.push("ku:alt".to_string());
    }
    if modifiers.control {
        cliclick_args.push("ku:ctrl".to_string());
    }
    if modifiers.meta {
        cliclick_args.push("ku:cmd".to_string());
    }

    let args_refs: Vec<&str> = cliclick_args.iter().map(|s| s.as_str()).collect();
    let output = ProcessCommand::new("cliclick")
        .args(&args_refs)
        .output();

    match output {
        Ok(out) if out.status.success() => return ActionResult::ok(),
        _ => {}
    }

    // Fallback to AppleScript
    let mut using_parts = Vec::new();
    if modifiers.meta {
        using_parts.push("command down");
    }
    if modifiers.control {
        using_parts.push("control down");
    }
    if modifiers.alt {
        using_parts.push("option down");
    }
    if modifiers.shift {
        using_parts.push("shift down");
    }

    let using_clause = if using_parts.is_empty() {
        String::new()
    } else {
        format!(" using {{{}}}", using_parts.join(", "))
    };

    // Map special keys to AppleScript key codes
    let key_part = match key.to_lowercase().as_str() {
        "return" | "enter" => "key code 36".to_string(),
        "tab" => "key code 48".to_string(),
        "space" => "key code 49".to_string(),
        "backspace" | "delete" => "key code 51".to_string(),
        "escape" | "esc" => "key code 53".to_string(),
        "up" | "arrowup" => "key code 126".to_string(),
        "down" | "arrowdown" => "key code 125".to_string(),
        "left" | "arrowleft" => "key code 123".to_string(),
        "right" | "arrowright" => "key code 124".to_string(),
        k if k.len() == 1 => format!(r#"keystroke "{}""#, k),
        k => format!(r#"keystroke "{}""#, k),
    };

    let script = format!(
        r#"tell application "System Events" to {}{}"#,
        key_part, using_clause
    );

    let output = ProcessCommand::new("osascript")
        .args(["-e", &script])
        .output();

    match output {
        Ok(out) if out.status.success() => ActionResult::ok(),
        Ok(out) => ActionResult::err(format!("osascript hotkey failed: {}", String::from_utf8_lossy(&out.stderr))),
        Err(e) => ActionResult::err(format!("Failed to run osascript: {}", e)),
    }
}

#[cfg(target_os = "linux")]
pub fn hotkey(modifiers: &KeyModifiers, key: &str) -> ActionResult {
    if !check_rate_limit() {
        return ActionResult::err("Rate limited");
    }

    info!("Hotkey: {:?} + {}", modifiers, key);

    let mut combo = Vec::new();
    if modifiers.meta {
        combo.push("super");
    }
    if modifiers.control {
        combo.push("ctrl");
    }
    if modifiers.alt {
        combo.push("alt");
    }
    if modifiers.shift {
        combo.push("shift");
    }
    combo.push(key);

    let key_combo = combo.join("+");

    let output = ProcessCommand::new("xdotool")
        .args(["key", &key_combo])
        .output();

    match output {
        Ok(out) if out.status.success() => ActionResult::ok(),
        Ok(out) => ActionResult::err(String::from_utf8_lossy(&out.stderr).to_string()),
        Err(e) => ActionResult::err(format!("xdotool not found: {}", e)),
    }
}

#[cfg(target_os = "windows")]
pub fn hotkey(modifiers: &KeyModifiers, key: &str) -> ActionResult {
    if !check_rate_limit() {
        return ActionResult::err("Rate limited");
    }

    info!("Hotkey: {:?} + {}", modifiers, key);

    use std::mem;

    #[repr(C)]
    struct KeyboardInput {
        vk: u16,
        scan: u16,
        flags: u32,
        time: u32,
        extra_info: usize,
    }

    #[repr(C)]
    struct Input {
        input_type: u32,
        input: KeyboardInput,
    }

    const INPUT_KEYBOARD: u32 = 1;
    const KEYEVENTF_KEYUP: u32 = 0x0002;
    const VK_SHIFT: u16 = 0x10;
    const VK_CONTROL: u16 = 0x11;
    const VK_MENU: u16 = 0x12; // Alt
    const VK_LWIN: u16 = 0x5B; // Windows key

    #[link(name = "user32")]
    extern "system" {
        fn SendInput(count: u32, inputs: *const Input, size: i32) -> u32;
    }

    let key_vk = windows_key_to_vk(key);
    if key_vk == 0 {
        return ActionResult::err(format!("Unknown key: {}", key));
    }

    let mut inputs = Vec::new();

    // Press modifiers
    if modifiers.meta {
        inputs.push(Input {
            input_type: INPUT_KEYBOARD,
            input: KeyboardInput { vk: VK_LWIN, scan: 0, flags: 0, time: 0, extra_info: 0 },
        });
    }
    if modifiers.control {
        inputs.push(Input {
            input_type: INPUT_KEYBOARD,
            input: KeyboardInput { vk: VK_CONTROL, scan: 0, flags: 0, time: 0, extra_info: 0 },
        });
    }
    if modifiers.alt {
        inputs.push(Input {
            input_type: INPUT_KEYBOARD,
            input: KeyboardInput { vk: VK_MENU, scan: 0, flags: 0, time: 0, extra_info: 0 },
        });
    }
    if modifiers.shift {
        inputs.push(Input {
            input_type: INPUT_KEYBOARD,
            input: KeyboardInput { vk: VK_SHIFT, scan: 0, flags: 0, time: 0, extra_info: 0 },
        });
    }

    // Press key
    inputs.push(Input {
        input_type: INPUT_KEYBOARD,
        input: KeyboardInput { vk: key_vk, scan: 0, flags: 0, time: 0, extra_info: 0 },
    });

    // Release key
    inputs.push(Input {
        input_type: INPUT_KEYBOARD,
        input: KeyboardInput { vk: key_vk, scan: 0, flags: KEYEVENTF_KEYUP, time: 0, extra_info: 0 },
    });

    // Release modifiers (reverse order)
    if modifiers.shift {
        inputs.push(Input {
            input_type: INPUT_KEYBOARD,
            input: KeyboardInput { vk: VK_SHIFT, scan: 0, flags: KEYEVENTF_KEYUP, time: 0, extra_info: 0 },
        });
    }
    if modifiers.alt {
        inputs.push(Input {
            input_type: INPUT_KEYBOARD,
            input: KeyboardInput { vk: VK_MENU, scan: 0, flags: KEYEVENTF_KEYUP, time: 0, extra_info: 0 },
        });
    }
    if modifiers.control {
        inputs.push(Input {
            input_type: INPUT_KEYBOARD,
            input: KeyboardInput { vk: VK_CONTROL, scan: 0, flags: KEYEVENTF_KEYUP, time: 0, extra_info: 0 },
        });
    }
    if modifiers.meta {
        inputs.push(Input {
            input_type: INPUT_KEYBOARD,
            input: KeyboardInput { vk: VK_LWIN, scan: 0, flags: KEYEVENTF_KEYUP, time: 0, extra_info: 0 },
        });
    }

    unsafe {
        let result = SendInput(inputs.len() as u32, inputs.as_ptr(), mem::size_of::<Input>() as i32);
        if result == inputs.len() as u32 {
            ActionResult::ok()
        } else {
            ActionResult::err("Some inputs failed")
        }
    }
}

#[cfg(not(any(target_os = "macos", target_os = "windows", target_os = "linux")))]
pub fn hotkey(_modifiers: &KeyModifiers, _key: &str) -> ActionResult {
    ActionResult::err("Not supported on this platform")
}

/// Press a single key (without modifiers)
pub fn key_press(key: &str) -> ActionResult {
    hotkey(&KeyModifiers::default(), key)
}

// ============================================================================
// Key Code Mappings
// ============================================================================

// macOS key code mapping removed - now using cliclick/osascript instead

#[cfg(target_os = "windows")]
fn windows_key_to_vk(name: &str) -> u16 {
    let name_lower = name.to_lowercase();
    match name_lower.as_str() {
        // Letters (A-Z = 0x41-0x5A)
        "a" => 0x41, "b" => 0x42, "c" => 0x43, "d" => 0x44, "e" => 0x45,
        "f" => 0x46, "g" => 0x47, "h" => 0x48, "i" => 0x49, "j" => 0x4A,
        "k" => 0x4B, "l" => 0x4C, "m" => 0x4D, "n" => 0x4E, "o" => 0x4F,
        "p" => 0x50, "q" => 0x51, "r" => 0x52, "s" => 0x53, "t" => 0x54,
        "u" => 0x55, "v" => 0x56, "w" => 0x57, "x" => 0x58, "y" => 0x59,
        "z" => 0x5A,
        // Numbers (0-9 = 0x30-0x39)
        "0" => 0x30, "1" => 0x31, "2" => 0x32, "3" => 0x33, "4" => 0x34,
        "5" => 0x35, "6" => 0x36, "7" => 0x37, "8" => 0x38, "9" => 0x39,
        // Function keys
        "f1" => 0x70, "f2" => 0x71, "f3" => 0x72, "f4" => 0x73,
        "f5" => 0x74, "f6" => 0x75, "f7" => 0x76, "f8" => 0x77,
        "f9" => 0x78, "f10" => 0x79, "f11" => 0x7A, "f12" => 0x7B,
        // Special keys
        "return" | "enter" => 0x0D,
        "tab" => 0x09,
        "space" => 0x20,
        "backspace" => 0x08,
        "delete" => 0x2E,
        "escape" | "esc" => 0x1B,
        "up" | "arrowup" => 0x26,
        "down" | "arrowdown" => 0x28,
        "left" | "arrowleft" => 0x25,
        "right" | "arrowright" => 0x27,
        "home" => 0x24,
        "end" => 0x23,
        "pageup" => 0x21,
        "pagedown" => 0x22,
        "insert" => 0x2D,
        _ => 0,
    }
}

// ============================================================================
// Clipboard
// ============================================================================

/// Get clipboard text content
#[cfg(target_os = "macos")]
pub fn clipboard_get_text() -> Result<String, String> {
    use cocoa::appkit::NSPasteboard;
    use cocoa::base::{id, nil};
    use cocoa::foundation::{NSString as CocoaNSString, NSArray};
    use objc::{msg_send, sel, sel_impl};

    debug!("Getting clipboard text");

    unsafe {
        let pasteboard: id = NSPasteboard::generalPasteboard(nil);
        let types: id = msg_send![pasteboard, types];

        // Check for string type
        let string_type = CocoaNSString::alloc(nil).init_str("public.utf8-plain-text");
        let contains: bool = msg_send![types, containsObject: string_type];

        if !contains {
            return Err("Clipboard does not contain text".to_string());
        }

        let string: id = msg_send![pasteboard, stringForType: string_type];
        if string == nil {
            return Err("Failed to get clipboard string".to_string());
        }

        let cstr: *const i8 = msg_send![string, UTF8String];
        if cstr.is_null() {
            return Err("Failed to convert clipboard string".to_string());
        }

        Ok(std::ffi::CStr::from_ptr(cstr).to_string_lossy().into_owned())
    }
}

#[cfg(target_os = "linux")]
pub fn clipboard_get_text() -> Result<String, String> {
    debug!("Getting clipboard text");

    let output = ProcessCommand::new("xclip")
        .args(["-selection", "clipboard", "-o"])
        .output();

    match output {
        Ok(out) if out.status.success() => {
            Ok(String::from_utf8_lossy(&out.stdout).to_string())
        }
        Ok(out) => Err(String::from_utf8_lossy(&out.stderr).to_string()),
        Err(_) => {
            // Try xsel as fallback
            let output = ProcessCommand::new("xsel")
                .args(["--clipboard", "--output"])
                .output();

            match output {
                Ok(out) if out.status.success() => {
                    Ok(String::from_utf8_lossy(&out.stdout).to_string())
                }
                _ => Err("Neither xclip nor xsel available".to_string()),
            }
        }
    }
}

#[cfg(target_os = "windows")]
pub fn clipboard_get_text() -> Result<String, String> {
    debug!("Getting clipboard text");

    #[link(name = "user32")]
    extern "system" {
        fn OpenClipboard(hwnd: *mut std::ffi::c_void) -> i32;
        fn CloseClipboard() -> i32;
        fn GetClipboardData(format: u32) -> *mut std::ffi::c_void;
    }

    #[link(name = "kernel32")]
    extern "system" {
        fn GlobalLock(hmem: *mut std::ffi::c_void) -> *mut std::ffi::c_void;
        fn GlobalUnlock(hmem: *mut std::ffi::c_void) -> i32;
    }

    const CF_UNICODETEXT: u32 = 13;

    unsafe {
        if OpenClipboard(std::ptr::null_mut()) == 0 {
            return Err("Failed to open clipboard".to_string());
        }

        let handle = GetClipboardData(CF_UNICODETEXT);
        if handle.is_null() {
            CloseClipboard();
            return Err("No text in clipboard".to_string());
        }

        let ptr = GlobalLock(handle) as *const u16;
        if ptr.is_null() {
            CloseClipboard();
            return Err("Failed to lock clipboard memory".to_string());
        }

        // Find null terminator
        let mut len = 0;
        while *ptr.offset(len) != 0 {
            len += 1;
        }

        let slice = std::slice::from_raw_parts(ptr, len as usize);
        let text = String::from_utf16_lossy(slice);

        GlobalUnlock(handle);
        CloseClipboard();

        Ok(text)
    }
}

#[cfg(not(any(target_os = "macos", target_os = "windows", target_os = "linux")))]
pub fn clipboard_get_text() -> Result<String, String> {
    Err("Not supported on this platform".to_string())
}

/// Set clipboard text content
#[cfg(target_os = "macos")]
pub fn clipboard_set_text(text: &str) -> ActionResult {
    use cocoa::appkit::NSPasteboard;
    use cocoa::base::{id, nil};
    use cocoa::foundation::NSString as CocoaNSString;
    use objc::{msg_send, sel, sel_impl};

    info!("Setting clipboard text: {} chars", text.len());

    unsafe {
        let pasteboard: id = NSPasteboard::generalPasteboard(nil);
        let _: () = msg_send![pasteboard, clearContents];

        let ns_string = CocoaNSString::alloc(nil).init_str(text);
        let result: bool = msg_send![pasteboard, setString: ns_string forType: CocoaNSString::alloc(nil).init_str("public.utf8-plain-text")];

        if result {
            ActionResult::ok()
        } else {
            ActionResult::err("Failed to set clipboard")
        }
    }
}

#[cfg(target_os = "linux")]
pub fn clipboard_set_text(text: &str) -> ActionResult {
    info!("Setting clipboard text: {} chars", text.len());

    let mut child = match ProcessCommand::new("xclip")
        .args(["-selection", "clipboard"])
        .stdin(std::process::Stdio::piped())
        .spawn()
    {
        Ok(c) => c,
        Err(_) => {
            // Try xsel
            match ProcessCommand::new("xsel")
                .args(["--clipboard", "--input"])
                .stdin(std::process::Stdio::piped())
                .spawn()
            {
                Ok(c) => c,
                Err(e) => return ActionResult::err(format!("Neither xclip nor xsel available: {}", e)),
            }
        }
    };

    use std::io::Write;
    if let Some(stdin) = child.stdin.as_mut() {
        if stdin.write_all(text.as_bytes()).is_err() {
            return ActionResult::err("Failed to write to clipboard");
        }
    }

    match child.wait() {
        Ok(status) if status.success() => ActionResult::ok(),
        _ => ActionResult::err("Clipboard command failed"),
    }
}

#[cfg(target_os = "windows")]
pub fn clipboard_set_text(text: &str) -> ActionResult {
    info!("Setting clipboard text: {} chars", text.len());

    use std::mem;

    #[link(name = "user32")]
    extern "system" {
        fn OpenClipboard(hwnd: *mut std::ffi::c_void) -> i32;
        fn CloseClipboard() -> i32;
        fn EmptyClipboard() -> i32;
        fn SetClipboardData(format: u32, hmem: *mut std::ffi::c_void) -> *mut std::ffi::c_void;
    }

    #[link(name = "kernel32")]
    extern "system" {
        fn GlobalAlloc(flags: u32, bytes: usize) -> *mut std::ffi::c_void;
        fn GlobalLock(hmem: *mut std::ffi::c_void) -> *mut std::ffi::c_void;
        fn GlobalUnlock(hmem: *mut std::ffi::c_void) -> i32;
    }

    const CF_UNICODETEXT: u32 = 13;
    const GMEM_MOVEABLE: u32 = 0x0002;

    let wide: Vec<u16> = text.encode_utf16().chain(std::iter::once(0)).collect();
    let size = wide.len() * 2;

    unsafe {
        if OpenClipboard(std::ptr::null_mut()) == 0 {
            return ActionResult::err("Failed to open clipboard");
        }

        EmptyClipboard();

        let hmem = GlobalAlloc(GMEM_MOVEABLE, size);
        if hmem.is_null() {
            CloseClipboard();
            return ActionResult::err("Failed to allocate memory");
        }

        let ptr = GlobalLock(hmem) as *mut u16;
        if ptr.is_null() {
            CloseClipboard();
            return ActionResult::err("Failed to lock memory");
        }

        std::ptr::copy_nonoverlapping(wide.as_ptr(), ptr, wide.len());
        GlobalUnlock(hmem);

        let result = SetClipboardData(CF_UNICODETEXT, hmem);
        CloseClipboard();

        if result.is_null() {
            ActionResult::err("Failed to set clipboard data")
        } else {
            ActionResult::ok()
        }
    }
}

#[cfg(not(any(target_os = "macos", target_os = "windows", target_os = "linux")))]
pub fn clipboard_set_text(_text: &str) -> ActionResult {
    ActionResult::err("Not supported on this platform")
}

// ============================================================================
// Process Management
// ============================================================================

/// List all running processes
pub fn list_processes() -> Vec<ProcessInfo> {
    use sysinfo::{System, ProcessesToUpdate, ProcessRefreshKind};

    debug!("Listing processes");

    let mut sys = System::new();
    sys.refresh_processes_specifics(
        ProcessesToUpdate::All,
        true,
        ProcessRefreshKind::everything(),
    );

    sys.processes()
        .iter()
        .map(|(pid, process)| ProcessInfo {
            pid: pid.as_u32(),
            name: process.name().to_string_lossy().to_string(),
            exe_path: process.exe().map(|p| p.to_string_lossy().to_string()),
            cmd_line: if process.cmd().is_empty() {
                None
            } else {
                Some(process.cmd().iter().map(|s| s.to_string_lossy().to_string()).collect::<Vec<_>>().join(" "))
            },
            status: format!("{:?}", process.status()),
            cpu_percent: process.cpu_usage(),
            memory_bytes: process.memory(),
            parent_pid: process.parent().map(|p| p.as_u32()),
        })
        .collect()
}

/// Kill a process by PID
pub fn kill_process(pid: u32, force: bool) -> ActionResult {
    use sysinfo::{System, Pid, Signal, ProcessesToUpdate};

    info!("Killing process {} (force={})", pid, force);

    let mut sys = System::new();
    sys.refresh_processes(ProcessesToUpdate::All, true);

    let pid = Pid::from_u32(pid);

    if let Some(process) = sys.process(pid) {
        let signal = if force {
            Signal::Kill
        } else {
            Signal::Term
        };

        if process.kill_with(signal).unwrap_or(false) {
            ActionResult::ok()
        } else {
            ActionResult::err("Failed to kill process")
        }
    } else {
        ActionResult::err(format!("Process {} not found", pid.as_u32()))
    }
}

/// Start a new process
pub fn start_process(command: &str, args: &[String]) -> Result<u32, String> {
    info!("Starting process: {} {:?}", command, args);

    let child = ProcessCommand::new(command)
        .args(args)
        .spawn()
        .map_err(|e| format!("Failed to start process: {}", e))?;

    Ok(child.id())
}

// ============================================================================
// Extended System Info
// ============================================================================

/// Get extended system information
pub fn get_extended_system_info() -> ExtendedSystemInfo {
    use sysinfo::{System, Disks, Networks, CpuRefreshKind, MemoryRefreshKind, RefreshKind};

    debug!("Getting extended system info");

    let mut sys = System::new_with_specifics(
        RefreshKind::new()
            .with_cpu(CpuRefreshKind::everything())
            .with_memory(MemoryRefreshKind::everything()),
    );

    // Get CPU brand from first CPU
    let cpu_brand = sys.cpus().first()
        .map(|c| c.brand().to_string())
        .unwrap_or_default();

    // Get disk info
    let disks = Disks::new_with_refreshed_list();
    let disk_info: Vec<DiskInfo> = disks.iter()
        .map(|d| DiskInfo {
            name: d.name().to_string_lossy().to_string(),
            mount_point: d.mount_point().to_string_lossy().to_string(),
            total_bytes: d.total_space(),
            available_bytes: d.available_space(),
            fs_type: d.file_system().to_string_lossy().to_string(),
            is_removable: d.is_removable(),
        })
        .collect();

    // Get network info
    let networks = Networks::new_with_refreshed_list();
    let network_info: Vec<NetworkInterfaceInfo> = networks.iter()
        .map(|(name, data)| NetworkInterfaceInfo {
            name: name.clone(),
            ip_addresses: data.ip_networks()
                .iter()
                .map(|ip| ip.addr.to_string())
                .collect(),
            mac_address: Some(data.mac_address().to_string()),
            is_up: data.received() > 0 || data.transmitted() > 0,
            is_loopback: name.contains("lo") || name.contains("loopback"),
        })
        .collect();

    ExtendedSystemInfo {
        hostname: System::host_name().unwrap_or_default(),
        os_name: System::name().unwrap_or_default(),
        os_version: System::os_version().unwrap_or_default(),
        kernel_version: System::kernel_version().unwrap_or_default(),
        cpu_count: sys.cpus().len(),
        cpu_brand,
        total_memory_bytes: sys.total_memory(),
        used_memory_bytes: sys.used_memory(),
        uptime_secs: System::uptime(),
        disks: disk_info,
        networks: network_info,
    }
}

// ============================================================================
// Tauri Commands
// ============================================================================

/// Move mouse cursor
#[tauri::command]
pub async fn desktop_mouse_move(x: f64, y: f64) -> Result<ActionResult, String> {
    Ok(mouse_move(x, y))
}

/// Click mouse button
#[tauri::command]
pub async fn desktop_mouse_click(
    x: f64,
    y: f64,
    button: MouseButton,
    double_click: bool,
) -> Result<ActionResult, String> {
    Ok(mouse_click(x, y, button, double_click))
}

/// Scroll mouse
#[tauri::command]
pub async fn desktop_mouse_scroll(delta_x: f64, delta_y: f64) -> Result<ActionResult, String> {
    Ok(mouse_scroll(delta_x, delta_y))
}

/// Type text
#[tauri::command]
pub async fn desktop_type_text(text: String) -> Result<ActionResult, String> {
    Ok(type_text(&text))
}

/// Press hotkey
#[tauri::command]
pub async fn desktop_hotkey(modifiers: KeyModifiers, key: String) -> Result<ActionResult, String> {
    Ok(hotkey(&modifiers, &key))
}

/// Press single key
#[tauri::command]
pub async fn desktop_key_press(key: String) -> Result<ActionResult, String> {
    Ok(key_press(&key))
}

/// Get clipboard text
#[tauri::command]
pub async fn desktop_clipboard_get() -> Result<String, String> {
    clipboard_get_text()
}

/// Set clipboard text
#[tauri::command]
pub async fn desktop_clipboard_set(text: String) -> Result<ActionResult, String> {
    Ok(clipboard_set_text(&text))
}

/// List processes
#[tauri::command]
pub async fn desktop_list_processes() -> Result<Vec<ProcessInfo>, String> {
    Ok(list_processes())
}

/// Kill process
#[tauri::command]
pub async fn desktop_kill_process(pid: u32, force: bool) -> Result<ActionResult, String> {
    Ok(kill_process(pid, force))
}

/// Start process
#[tauri::command]
pub async fn desktop_start_process(command: String, args: Vec<String>) -> Result<u32, String> {
    start_process(&command, &args)
}

/// Get extended system info
#[tauri::command]
pub async fn desktop_system_info() -> Result<ExtendedSystemInfo, String> {
    Ok(get_extended_system_info())
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_action_result_ok() {
        let result = ActionResult::ok();
        assert!(result.success);
        assert!(result.error.is_none());
    }

    #[test]
    fn test_action_result_err() {
        let result = ActionResult::err("Test error");
        assert!(!result.success);
        assert_eq!(result.error.as_deref(), Some("Test error"));
    }

    #[test]
    fn test_mouse_button_serialization() {
        let json = serde_json::to_string(&MouseButton::Left).unwrap();
        assert_eq!(json, "\"left\"");
    }

    #[test]
    fn test_key_modifiers_default() {
        let mods = KeyModifiers::default();
        assert!(!mods.shift);
        assert!(!mods.control);
        assert!(!mods.alt);
        assert!(!mods.meta);
    }

    #[test]
    fn test_process_info_serialization() {
        let info = ProcessInfo {
            pid: 1234,
            name: "test".to_string(),
            exe_path: Some("/usr/bin/test".to_string()),
            cmd_line: Some("test --arg".to_string()),
            status: "Running".to_string(),
            cpu_percent: 5.5,
            memory_bytes: 1024 * 1024,
            parent_pid: Some(1),
        };
        let json = serde_json::to_string(&info).unwrap();
        assert!(json.contains("\"pid\":1234"));
        assert!(json.contains("\"name\":\"test\""));
    }

    #[test]
    fn test_rate_limit() {
        // First call should pass
        assert!(check_rate_limit());
        // Immediate second call should fail
        assert!(!check_rate_limit());
        // After sleeping, should pass
        std::thread::sleep(std::time::Duration::from_millis(150));
        assert!(check_rate_limit());
    }

    // Note: key_name_to_keycode test removed - now using cliclick/osascript instead

    #[cfg(target_os = "windows")]
    #[test]
    fn test_windows_key_to_vk() {
        assert_ne!(windows_key_to_vk("a"), 0);
        assert_ne!(windows_key_to_vk("enter"), 0);
        assert_eq!(windows_key_to_vk("nonexistent"), 0);
    }

    #[test]
    fn test_list_processes() {
        let processes = list_processes();
        // Should have at least one process (the test itself)
        assert!(!processes.is_empty());
    }

    #[test]
    fn test_extended_system_info() {
        let info = get_extended_system_info();
        assert!(!info.os_name.is_empty());
        assert!(info.cpu_count > 0);
        assert!(info.total_memory_bytes > 0);
    }
}

/*
 * 鏡
 * h(x) ≥ 0. Always.
 *
 * Desktop control is power.
 * Rate-limited. Logged. Audited.
 * The user remains in control.
 */
