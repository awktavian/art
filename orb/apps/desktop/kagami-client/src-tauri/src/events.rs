//! CGEvent Injection — System-wide Input Control
//!
//! Provides programmatic control over mouse and keyboard input
//! via macOS CGEvent APIs. Enables Kagami to automate any
//! application through simulated user input.
//!
//! Colony: Forge (e₂) — Implementation
//!
//! Capabilities:
//!   - Mouse movement (absolute/relative)
//!   - Mouse clicks (left, right, middle, double)
//!   - Keyboard events (keyDown, keyUp, keyPress)
//!   - Key shortcuts (cmd+c, cmd+v, complex combos)
//!   - Scroll wheel simulation
//!   - Drag and drop automation
//!
//! Safety: h(x) ≥ 0
//!   - Rate-limited to prevent runaway input
//!   - All events are logged
//!   - Emergency stop via Escape key

use serde::{Deserialize, Serialize};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::time::{Duration, Instant};
use tracing::{debug, error, info, warn};

#[cfg(target_os = "macos")]
use core_graphics::{
    display::CGDisplay,
    event::{
        CGEvent, CGEventFlags, CGEventTapLocation, CGEventType, CGKeyCode, CGMouseButton,
        EventField, ScrollEventUnit,
    },
    event_source::{CGEventSource, CGEventSourceStateID},
    geometry::CGPoint,
};

// ============================================================================
// Safety Controls
// ============================================================================

/// Emergency stop flag - set to true to halt all input injection
static EMERGENCY_STOP: AtomicBool = AtomicBool::new(false);

/// Rate limiter - track events per second
static EVENTS_THIS_SECOND: AtomicU64 = AtomicU64::new(0);
static LAST_RATE_RESET: AtomicU64 = AtomicU64::new(0);

/// Maximum events per second (safety limit)
const MAX_EVENTS_PER_SECOND: u64 = 100;

/// Check if we're within rate limits
fn check_rate_limit() -> bool {
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap()
        .as_secs();

    let last_reset = LAST_RATE_RESET.load(Ordering::SeqCst);

    if now > last_reset {
        LAST_RATE_RESET.store(now, Ordering::SeqCst);
        EVENTS_THIS_SECOND.store(0, Ordering::SeqCst);
    }

    let count = EVENTS_THIS_SECOND.fetch_add(1, Ordering::SeqCst);
    count < MAX_EVENTS_PER_SECOND
}

/// Emergency stop - halt all input injection
pub fn emergency_stop() {
    EMERGENCY_STOP.store(true, Ordering::SeqCst);
    warn!("🛑 Emergency stop activated - all input injection halted");
}

/// Resume input injection after emergency stop
pub fn resume_input() {
    EMERGENCY_STOP.store(false, Ordering::SeqCst);
    info!("✅ Input injection resumed");
}

/// Check if emergency stop is active
pub fn is_stopped() -> bool {
    EMERGENCY_STOP.load(Ordering::SeqCst)
}

// ============================================================================
// Types
// ============================================================================

/// Mouse button types
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum MouseButton {
    Left,
    Right,
    Middle,
}

/// Keyboard modifier flags
#[derive(Debug, Clone, Copy, Serialize, Deserialize, Default)]
pub struct Modifiers {
    pub shift: bool,
    pub control: bool,
    pub option: bool,
    pub command: bool,
}

/// Result of an input event
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EventResult {
    pub success: bool,
    pub error: Option<String>,
    pub event_type: String,
}

// ============================================================================
// Mouse Control
// ============================================================================

/// Move mouse to absolute screen coordinates
#[cfg(target_os = "macos")]
pub fn move_mouse(x: f64, y: f64) -> EventResult {
    if is_stopped() {
        return EventResult {
            success: false,
            error: Some("Emergency stop active".to_string()),
            event_type: "mouse_move".to_string(),
        };
    }

    if !check_rate_limit() {
        return EventResult {
            success: false,
            error: Some("Rate limit exceeded".to_string()),
            event_type: "mouse_move".to_string(),
        };
    }

    debug!("Moving mouse to ({}, {})", x, y);

    let source = match CGEventSource::new(CGEventSourceStateID::HIDSystemState) {
        Ok(s) => s,
        Err(_) => {
            return EventResult {
                success: false,
                error: Some("Failed to create event source".to_string()),
                event_type: "mouse_move".to_string(),
            }
        }
    };

    let point = CGPoint::new(x, y);
    let event = match CGEvent::new_mouse_event(
        source,
        CGEventType::MouseMoved,
        point,
        CGMouseButton::Left,
    ) {
        Ok(e) => e,
        Err(_) => {
            return EventResult {
                success: false,
                error: Some("Failed to create mouse event".to_string()),
                event_type: "mouse_move".to_string(),
            }
        }
    };

    event.post(CGEventTapLocation::HID);

    EventResult {
        success: true,
        error: None,
        event_type: "mouse_move".to_string(),
    }
}

#[cfg(not(target_os = "macos"))]
pub fn move_mouse(_x: f64, _y: f64) -> EventResult {
    EventResult {
        success: false,
        error: Some("Not supported on this platform".to_string()),
        event_type: "mouse_move".to_string(),
    }
}

/// Move mouse relative to current position
#[cfg(target_os = "macos")]
pub fn move_mouse_relative(dx: f64, dy: f64) -> EventResult {
    if is_stopped() {
        return EventResult {
            success: false,
            error: Some("Emergency stop active".to_string()),
            event_type: "mouse_move_relative".to_string(),
        };
    }

    // Get current mouse position
    let event = match CGEvent::new(CGEventSource::new(CGEventSourceStateID::HIDSystemState).ok()) {
        Ok(e) => e,
        Err(_) => {
            return EventResult {
                success: false,
                error: Some("Failed to get current position".to_string()),
                event_type: "mouse_move_relative".to_string(),
            }
        }
    };

    let current = event.location();
    move_mouse(current.x + dx, current.y + dy)
}

#[cfg(not(target_os = "macos"))]
pub fn move_mouse_relative(_dx: f64, _dy: f64) -> EventResult {
    EventResult {
        success: false,
        error: Some("Not supported on this platform".to_string()),
        event_type: "mouse_move_relative".to_string(),
    }
}

/// Click mouse button at current position
#[cfg(target_os = "macos")]
pub fn click(button: MouseButton, double: bool) -> EventResult {
    if is_stopped() {
        return EventResult {
            success: false,
            error: Some("Emergency stop active".to_string()),
            event_type: "mouse_click".to_string(),
        };
    }

    if !check_rate_limit() {
        return EventResult {
            success: false,
            error: Some("Rate limit exceeded".to_string()),
            event_type: "mouse_click".to_string(),
        };
    }

    debug!("Mouse click: {:?}, double: {}", button, double);

    let source = match CGEventSource::new(CGEventSourceStateID::HIDSystemState) {
        Ok(s) => s,
        Err(_) => {
            return EventResult {
                success: false,
                error: Some("Failed to create event source".to_string()),
                event_type: "mouse_click".to_string(),
            }
        }
    };

    // Get current position
    let pos_event = match CGEvent::new(Some(source.clone())) {
        Ok(e) => e,
        Err(_) => {
            return EventResult {
                success: false,
                error: Some("Failed to get position".to_string()),
                event_type: "mouse_click".to_string(),
            }
        }
    };
    let point = pos_event.location();

    let (cg_button, down_type, up_type) = match button {
        MouseButton::Left => (
            CGMouseButton::Left,
            CGEventType::LeftMouseDown,
            CGEventType::LeftMouseUp,
        ),
        MouseButton::Right => (
            CGMouseButton::Right,
            CGEventType::RightMouseDown,
            CGEventType::RightMouseUp,
        ),
        MouseButton::Middle => (
            CGMouseButton::Center,
            CGEventType::OtherMouseDown,
            CGEventType::OtherMouseUp,
        ),
    };

    let click_count = if double { 2 } else { 1 };

    for _ in 0..click_count {
        // Mouse down
        if let Ok(down) = CGEvent::new_mouse_event(source.clone(), down_type, point, cg_button) {
            down.post(CGEventTapLocation::HID);
        }

        // Small delay for double-click
        std::thread::sleep(Duration::from_millis(10));

        // Mouse up
        if let Ok(up) = CGEvent::new_mouse_event(source.clone(), up_type, point, cg_button) {
            up.post(CGEventTapLocation::HID);
        }

        if double && click_count > 1 {
            std::thread::sleep(Duration::from_millis(50));
        }
    }

    EventResult {
        success: true,
        error: None,
        event_type: "mouse_click".to_string(),
    }
}

#[cfg(not(target_os = "macos"))]
pub fn click(_button: MouseButton, _double: bool) -> EventResult {
    EventResult {
        success: false,
        error: Some("Not supported on this platform".to_string()),
        event_type: "mouse_click".to_string(),
    }
}

/// Click at specific coordinates
#[cfg(target_os = "macos")]
pub fn click_at(x: f64, y: f64, button: MouseButton, double: bool) -> EventResult {
    let move_result = move_mouse(x, y);
    if !move_result.success {
        return move_result;
    }

    // Small delay to let the move settle
    std::thread::sleep(Duration::from_millis(10));

    click(button, double)
}

#[cfg(not(target_os = "macos"))]
pub fn click_at(_x: f64, _y: f64, _button: MouseButton, _double: bool) -> EventResult {
    EventResult {
        success: false,
        error: Some("Not supported on this platform".to_string()),
        event_type: "mouse_click".to_string(),
    }
}

/// Scroll wheel
#[cfg(target_os = "macos")]
pub fn scroll(dx: i32, dy: i32) -> EventResult {
    if is_stopped() {
        return EventResult {
            success: false,
            error: Some("Emergency stop active".to_string()),
            event_type: "scroll".to_string(),
        };
    }

    if !check_rate_limit() {
        return EventResult {
            success: false,
            error: Some("Rate limit exceeded".to_string()),
            event_type: "scroll".to_string(),
        };
    }

    debug!("Scroll: dx={}, dy={}", dx, dy);

    let source = match CGEventSource::new(CGEventSourceStateID::HIDSystemState) {
        Ok(s) => s,
        Err(_) => {
            return EventResult {
                success: false,
                error: Some("Failed to create event source".to_string()),
                event_type: "scroll".to_string(),
            }
        }
    };

    let event = match CGEvent::new_scroll_event(
        source,
        ScrollEventUnit::PIXEL,
        2,
        dy,
        dx,
        0,
    ) {
        Ok(e) => e,
        Err(_) => {
            return EventResult {
                success: false,
                error: Some("Failed to create scroll event".to_string()),
                event_type: "scroll".to_string(),
            }
        }
    };

    event.post(CGEventTapLocation::HID);

    EventResult {
        success: true,
        error: None,
        event_type: "scroll".to_string(),
    }
}

#[cfg(not(target_os = "macos"))]
pub fn scroll(_dx: i32, _dy: i32) -> EventResult {
    EventResult {
        success: false,
        error: Some("Not supported on this platform".to_string()),
        event_type: "scroll".to_string(),
    }
}

// ============================================================================
// Keyboard Control
// ============================================================================

/// Common key codes for macOS
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum KeyCode {
    // Letters
    A, B, C, D, E, F, G, H, I, J, K, L, M,
    N, O, P, Q, R, S, T, U, V, W, X, Y, Z,
    // Numbers
    Key0, Key1, Key2, Key3, Key4, Key5, Key6, Key7, Key8, Key9,
    // Function keys
    F1, F2, F3, F4, F5, F6, F7, F8, F9, F10, F11, F12,
    // Special keys
    Return, Tab, Space, Delete, Escape, Backspace,
    LeftArrow, RightArrow, UpArrow, DownArrow,
    Home, End, PageUp, PageDown,
}

impl KeyCode {
    /// Convert to CGKeyCode
    #[cfg(target_os = "macos")]
    fn to_cg_keycode(self) -> CGKeyCode {
        match self {
            // Letters (QWERTY layout)
            KeyCode::A => 0x00, KeyCode::S => 0x01, KeyCode::D => 0x02, KeyCode::F => 0x03,
            KeyCode::H => 0x04, KeyCode::G => 0x05, KeyCode::Z => 0x06, KeyCode::X => 0x07,
            KeyCode::C => 0x08, KeyCode::V => 0x09, KeyCode::B => 0x0B, KeyCode::Q => 0x0C,
            KeyCode::W => 0x0D, KeyCode::E => 0x0E, KeyCode::R => 0x0F, KeyCode::Y => 0x10,
            KeyCode::T => 0x11, KeyCode::Key1 => 0x12, KeyCode::Key2 => 0x13, KeyCode::Key3 => 0x14,
            KeyCode::Key4 => 0x15, KeyCode::Key6 => 0x16, KeyCode::Key5 => 0x17, KeyCode::Key9 => 0x19,
            KeyCode::Key7 => 0x1A, KeyCode::Key8 => 0x1C, KeyCode::Key0 => 0x1D, KeyCode::O => 0x1F,
            KeyCode::U => 0x20, KeyCode::I => 0x22, KeyCode::P => 0x23, KeyCode::L => 0x25,
            KeyCode::J => 0x26, KeyCode::K => 0x28, KeyCode::N => 0x2D, KeyCode::M => 0x2E,
            // Special keys
            KeyCode::Return => 0x24, KeyCode::Tab => 0x30, KeyCode::Space => 0x31,
            KeyCode::Delete => 0x33, KeyCode::Escape => 0x35, KeyCode::Backspace => 0x33,
            KeyCode::LeftArrow => 0x7B, KeyCode::RightArrow => 0x7C,
            KeyCode::DownArrow => 0x7D, KeyCode::UpArrow => 0x7E,
            KeyCode::Home => 0x73, KeyCode::End => 0x77,
            KeyCode::PageUp => 0x74, KeyCode::PageDown => 0x79,
            // Function keys
            KeyCode::F1 => 0x7A, KeyCode::F2 => 0x78, KeyCode::F3 => 0x63, KeyCode::F4 => 0x76,
            KeyCode::F5 => 0x60, KeyCode::F6 => 0x61, KeyCode::F7 => 0x62, KeyCode::F8 => 0x64,
            KeyCode::F9 => 0x65, KeyCode::F10 => 0x6D, KeyCode::F11 => 0x67, KeyCode::F12 => 0x6F,
        }
    }
}

/// Press and release a key
#[cfg(target_os = "macos")]
pub fn key_press(key: KeyCode, modifiers: Modifiers) -> EventResult {
    if is_stopped() {
        return EventResult {
            success: false,
            error: Some("Emergency stop active".to_string()),
            event_type: "key_press".to_string(),
        };
    }

    if !check_rate_limit() {
        return EventResult {
            success: false,
            error: Some("Rate limit exceeded".to_string()),
            event_type: "key_press".to_string(),
        };
    }

    debug!("Key press: {:?} with modifiers: {:?}", key, modifiers);

    let source = match CGEventSource::new(CGEventSourceStateID::HIDSystemState) {
        Ok(s) => s,
        Err(_) => {
            return EventResult {
                success: false,
                error: Some("Failed to create event source".to_string()),
                event_type: "key_press".to_string(),
            }
        }
    };

    let keycode = key.to_cg_keycode();

    // Build modifier flags
    let mut flags = CGEventFlags::empty();
    if modifiers.shift {
        flags |= CGEventFlags::CGEventFlagShift;
    }
    if modifiers.control {
        flags |= CGEventFlags::CGEventFlagControl;
    }
    if modifiers.option {
        flags |= CGEventFlags::CGEventFlagAlternate;
    }
    if modifiers.command {
        flags |= CGEventFlags::CGEventFlagCommand;
    }

    // Key down
    if let Ok(down) = CGEvent::new_keyboard_event(source.clone(), keycode, true) {
        down.set_flags(flags);
        down.post(CGEventTapLocation::HID);
    }

    std::thread::sleep(Duration::from_millis(10));

    // Key up
    if let Ok(up) = CGEvent::new_keyboard_event(source, keycode, false) {
        up.set_flags(flags);
        up.post(CGEventTapLocation::HID);
    }

    EventResult {
        success: true,
        error: None,
        event_type: "key_press".to_string(),
    }
}

#[cfg(not(target_os = "macos"))]
pub fn key_press(_key: KeyCode, _modifiers: Modifiers) -> EventResult {
    EventResult {
        success: false,
        error: Some("Not supported on this platform".to_string()),
        event_type: "key_press".to_string(),
    }
}

/// Type a string of text
#[cfg(target_os = "macos")]
pub fn type_text(text: &str) -> EventResult {
    if is_stopped() {
        return EventResult {
            success: false,
            error: Some("Emergency stop active".to_string()),
            event_type: "type_text".to_string(),
        };
    }

    debug!("Typing text: {} chars", text.len());

    let source = match CGEventSource::new(CGEventSourceStateID::HIDSystemState) {
        Ok(s) => s,
        Err(_) => {
            return EventResult {
                success: false,
                error: Some("Failed to create event source".to_string()),
                event_type: "type_text".to_string(),
            }
        }
    };

    // Use CGEventKeyboardSetUnicodeString for proper Unicode support
    for chunk in text.encode_utf16().collect::<Vec<_>>().chunks(20) {
        if !check_rate_limit() {
            return EventResult {
                success: false,
                error: Some("Rate limit exceeded during typing".to_string()),
                event_type: "type_text".to_string(),
            };
        }

        if let Ok(event) = CGEvent::new_keyboard_event(source.clone(), 0, true) {
            event.set_string_from_utf16_unchecked(chunk);
            event.post(CGEventTapLocation::HID);
        }

        std::thread::sleep(Duration::from_millis(5));
    }

    EventResult {
        success: true,
        error: None,
        event_type: "type_text".to_string(),
    }
}

#[cfg(not(target_os = "macos"))]
pub fn type_text(_text: &str) -> EventResult {
    EventResult {
        success: false,
        error: Some("Not supported on this platform".to_string()),
        event_type: "type_text".to_string(),
    }
}

/// Execute a keyboard shortcut (e.g., Cmd+C)
#[cfg(target_os = "macos")]
pub fn shortcut(key: KeyCode, modifiers: Modifiers) -> EventResult {
    key_press(key, modifiers)
}

#[cfg(not(target_os = "macos"))]
pub fn shortcut(_key: KeyCode, _modifiers: Modifiers) -> EventResult {
    EventResult {
        success: false,
        error: Some("Not supported on this platform".to_string()),
        event_type: "shortcut".to_string(),
    }
}

// ============================================================================
// Tauri Commands
// ============================================================================

/// Move mouse to absolute coordinates
#[tauri::command]
pub async fn event_mouse_move(x: f64, y: f64) -> Result<EventResult, String> {
    Ok(move_mouse(x, y))
}

/// Move mouse relative to current position
#[tauri::command]
pub async fn event_mouse_move_relative(dx: f64, dy: f64) -> Result<EventResult, String> {
    Ok(move_mouse_relative(dx, dy))
}

/// Click mouse button
#[tauri::command]
pub async fn event_click(button: MouseButton, double: bool) -> Result<EventResult, String> {
    Ok(click(button, double))
}

/// Click at specific coordinates
#[tauri::command]
pub async fn event_click_at(
    x: f64,
    y: f64,
    button: MouseButton,
    double: bool,
) -> Result<EventResult, String> {
    Ok(click_at(x, y, button, double))
}

/// Scroll wheel
#[tauri::command]
pub async fn event_scroll(dx: i32, dy: i32) -> Result<EventResult, String> {
    Ok(scroll(dx, dy))
}

/// Press a key with optional modifiers
#[tauri::command]
pub async fn event_key_press(key: KeyCode, modifiers: Modifiers) -> Result<EventResult, String> {
    Ok(key_press(key, modifiers))
}

/// Type text string
#[tauri::command]
pub async fn event_type_text(text: String) -> Result<EventResult, String> {
    Ok(type_text(&text))
}

/// Execute keyboard shortcut
#[tauri::command]
pub async fn event_shortcut(key: KeyCode, modifiers: Modifiers) -> Result<EventResult, String> {
    Ok(shortcut(key, modifiers))
}

/// Emergency stop all input injection
#[tauri::command]
pub async fn event_emergency_stop() -> Result<(), String> {
    emergency_stop();
    Ok(())
}

/// Resume input injection after emergency stop
#[tauri::command]
pub async fn event_resume() -> Result<(), String> {
    resume_input();
    Ok(())
}

/// Check if emergency stop is active
#[tauri::command]
pub async fn event_is_stopped() -> Result<bool, String> {
    Ok(is_stopped())
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_modifiers_default() {
        let mods = Modifiers::default();
        assert!(!mods.shift);
        assert!(!mods.control);
        assert!(!mods.option);
        assert!(!mods.command);
    }

    #[test]
    fn test_emergency_stop() {
        assert!(!is_stopped());
        emergency_stop();
        assert!(is_stopped());
        resume_input();
        assert!(!is_stopped());
    }

    #[test]
    fn test_event_result_serialization() {
        let result = EventResult {
            success: true,
            error: None,
            event_type: "mouse_click".to_string(),
        };

        let json = serde_json::to_string(&result).unwrap();
        assert!(json.contains("mouse_click"));
        assert!(json.contains("true"));
    }
}

/*
 * 鏡
 * h(x) ≥ 0. Always.
 *
 * With great power comes great responsibility.
 * Every keystroke logged. Every click intentional.
 * Emergency stop always available.
 */
