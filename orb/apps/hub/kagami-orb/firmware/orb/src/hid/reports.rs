//! HID Report Structures
//!
//! USB HID report descriptors for keyboard, mouse, consumer control, and gamepad.

use serde::{Deserialize, Serialize};

/// Keyboard HID Report (8 bytes)
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct KeyboardReport {
    /// Modifier keys (Ctrl, Shift, Alt, GUI)
    pub modifier: u8,
    /// Reserved byte
    pub reserved: u8,
    /// Pressed keycodes (up to 6 simultaneous)
    pub keycodes: [u8; 6],
}

impl KeyboardReport {
    pub const MODIFIER_LEFT_CTRL: u8 = 0x01;
    pub const MODIFIER_LEFT_SHIFT: u8 = 0x02;
    pub const MODIFIER_LEFT_ALT: u8 = 0x04;
    pub const MODIFIER_LEFT_GUI: u8 = 0x08;
    pub const MODIFIER_RIGHT_CTRL: u8 = 0x10;
    pub const MODIFIER_RIGHT_SHIFT: u8 = 0x20;
    pub const MODIFIER_RIGHT_ALT: u8 = 0x40;
    pub const MODIFIER_RIGHT_GUI: u8 = 0x80;

    /// Create a report with a single key press
    pub fn key(modifier: u8, keycode: u8) -> Self {
        Self {
            modifier,
            reserved: 0,
            keycodes: [keycode, 0, 0, 0, 0, 0],
        }
    }

    /// Create an empty (release) report
    pub fn release() -> Self {
        Self::default()
    }

    /// Convert to bytes for HID transmission
    pub fn to_bytes(&self) -> [u8; 8] {
        [
            self.modifier,
            self.reserved,
            self.keycodes[0],
            self.keycodes[1],
            self.keycodes[2],
            self.keycodes[3],
            self.keycodes[4],
            self.keycodes[5],
        ]
    }
}

/// Mouse HID Report (5 bytes)
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct MouseReport {
    /// Button state (bit 0 = left, bit 1 = right, bit 2 = middle)
    pub buttons: u8,
    /// X movement (-127 to 127)
    pub x: i8,
    /// Y movement (-127 to 127)
    pub y: i8,
    /// Vertical scroll wheel
    pub wheel: i8,
    /// Horizontal pan
    pub pan: i8,
}

impl MouseReport {
    pub const BUTTON_LEFT: u8 = 0x01;
    pub const BUTTON_RIGHT: u8 = 0x02;
    pub const BUTTON_MIDDLE: u8 = 0x04;
    pub const BUTTON_BACK: u8 = 0x08;
    pub const BUTTON_FORWARD: u8 = 0x10;

    /// Create a movement report
    pub fn move_to(x: i8, y: i8) -> Self {
        Self {
            buttons: 0,
            x,
            y,
            wheel: 0,
            pan: 0,
        }
    }

    /// Create a click report
    pub fn click(button: u8) -> Self {
        Self {
            buttons: button,
            x: 0,
            y: 0,
            wheel: 0,
            pan: 0,
        }
    }

    /// Create a scroll report
    pub fn scroll(wheel: i8) -> Self {
        Self {
            buttons: 0,
            x: 0,
            y: 0,
            wheel,
            pan: 0,
        }
    }

    /// Convert to bytes for HID transmission
    pub fn to_bytes(&self) -> [u8; 5] {
        [
            self.buttons,
            self.x as u8,
            self.y as u8,
            self.wheel as u8,
            self.pan as u8,
        ]
    }
}

/// Consumer Control HID Report (2 bytes)
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ConsumerReport {
    /// Consumer control usage code
    pub usage: u16,
}

impl ConsumerReport {
    // Media keys
    pub const PLAY_PAUSE: u16 = 0x00CD;
    pub const STOP: u16 = 0x00B7;
    pub const NEXT_TRACK: u16 = 0x00B5;
    pub const PREV_TRACK: u16 = 0x00B6;
    pub const VOLUME_UP: u16 = 0x00E9;
    pub const VOLUME_DOWN: u16 = 0x00EA;
    pub const MUTE: u16 = 0x00E2;

    // System keys
    pub const BRIGHTNESS_UP: u16 = 0x006F;
    pub const BRIGHTNESS_DOWN: u16 = 0x0070;
    pub const SCREEN_LOCK: u16 = 0x019E;

    // Application launch
    pub const CALCULATOR: u16 = 0x0192;
    pub const BROWSER: u16 = 0x0196;
    pub const EMAIL: u16 = 0x018A;

    pub fn new(usage: u16) -> Self {
        Self { usage }
    }

    pub fn release() -> Self {
        Self { usage: 0 }
    }

    pub fn to_bytes(&self) -> [u8; 2] {
        self.usage.to_le_bytes()
    }
}

/// Gamepad HID Report (7 bytes)
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct GamepadReport {
    /// Left stick X axis
    pub lx: i16,
    /// Left stick Y axis
    pub ly: i16,
    /// Right stick X axis
    pub rx: i16,
    /// Right stick Y axis
    pub ry: i16,
    /// D-pad (hat switch, 0-8, 0 = centered)
    pub hat: u8,
    /// Button state (16 buttons)
    pub buttons: u16,
}

impl GamepadReport {
    // D-pad values
    pub const HAT_CENTER: u8 = 0;
    pub const HAT_UP: u8 = 1;
    pub const HAT_UP_RIGHT: u8 = 2;
    pub const HAT_RIGHT: u8 = 3;
    pub const HAT_DOWN_RIGHT: u8 = 4;
    pub const HAT_DOWN: u8 = 5;
    pub const HAT_DOWN_LEFT: u8 = 6;
    pub const HAT_LEFT: u8 = 7;
    pub const HAT_UP_LEFT: u8 = 8;

    // Buttons
    pub const BUTTON_A: u16 = 0x0001;
    pub const BUTTON_B: u16 = 0x0002;
    pub const BUTTON_X: u16 = 0x0004;
    pub const BUTTON_Y: u16 = 0x0008;
    pub const BUTTON_LB: u16 = 0x0010;
    pub const BUTTON_RB: u16 = 0x0020;
    pub const BUTTON_LT: u16 = 0x0040;
    pub const BUTTON_RT: u16 = 0x0080;
    pub const BUTTON_SELECT: u16 = 0x0100;
    pub const BUTTON_START: u16 = 0x0200;
    pub const BUTTON_L3: u16 = 0x0400;
    pub const BUTTON_R3: u16 = 0x0800;

    pub fn to_bytes(&self) -> [u8; 11] {
        let lx = self.lx.to_le_bytes();
        let ly = self.ly.to_le_bytes();
        let rx = self.rx.to_le_bytes();
        let ry = self.ry.to_le_bytes();
        let buttons = self.buttons.to_le_bytes();
        [
            lx[0], lx[1],
            ly[0], ly[1],
            rx[0], rx[1],
            ry[0], ry[1],
            self.hat,
            buttons[0], buttons[1],
        ]
    }
}

/// USB HID Keycodes (USB HID Usage Tables 1.3)
#[allow(dead_code)]
pub mod keycode {
    pub const KEY_NONE: u8 = 0x00;
    pub const KEY_A: u8 = 0x04;
    pub const KEY_B: u8 = 0x05;
    pub const KEY_C: u8 = 0x06;
    pub const KEY_D: u8 = 0x07;
    pub const KEY_E: u8 = 0x08;
    pub const KEY_F: u8 = 0x09;
    pub const KEY_G: u8 = 0x0A;
    pub const KEY_H: u8 = 0x0B;
    pub const KEY_I: u8 = 0x0C;
    pub const KEY_J: u8 = 0x0D;
    pub const KEY_K: u8 = 0x0E;
    pub const KEY_L: u8 = 0x0F;
    pub const KEY_M: u8 = 0x10;
    pub const KEY_N: u8 = 0x11;
    pub const KEY_O: u8 = 0x12;
    pub const KEY_P: u8 = 0x13;
    pub const KEY_Q: u8 = 0x14;
    pub const KEY_R: u8 = 0x15;
    pub const KEY_S: u8 = 0x16;
    pub const KEY_T: u8 = 0x17;
    pub const KEY_U: u8 = 0x18;
    pub const KEY_V: u8 = 0x19;
    pub const KEY_W: u8 = 0x1A;
    pub const KEY_X: u8 = 0x1B;
    pub const KEY_Y: u8 = 0x1C;
    pub const KEY_Z: u8 = 0x1D;
    pub const KEY_1: u8 = 0x1E;
    pub const KEY_2: u8 = 0x1F;
    pub const KEY_3: u8 = 0x20;
    pub const KEY_4: u8 = 0x21;
    pub const KEY_5: u8 = 0x22;
    pub const KEY_6: u8 = 0x23;
    pub const KEY_7: u8 = 0x24;
    pub const KEY_8: u8 = 0x25;
    pub const KEY_9: u8 = 0x26;
    pub const KEY_0: u8 = 0x27;
    pub const KEY_ENTER: u8 = 0x28;
    pub const KEY_ESCAPE: u8 = 0x29;
    pub const KEY_BACKSPACE: u8 = 0x2A;
    pub const KEY_TAB: u8 = 0x2B;
    pub const KEY_SPACE: u8 = 0x2C;
    pub const KEY_MINUS: u8 = 0x2D;
    pub const KEY_EQUAL: u8 = 0x2E;
    pub const KEY_LEFT_BRACKET: u8 = 0x2F;
    pub const KEY_RIGHT_BRACKET: u8 = 0x30;
    pub const KEY_BACKSLASH: u8 = 0x31;
    pub const KEY_SEMICOLON: u8 = 0x33;
    pub const KEY_APOSTROPHE: u8 = 0x34;
    pub const KEY_GRAVE: u8 = 0x35;
    pub const KEY_COMMA: u8 = 0x36;
    pub const KEY_PERIOD: u8 = 0x37;
    pub const KEY_SLASH: u8 = 0x38;
    pub const KEY_CAPS_LOCK: u8 = 0x39;
    pub const KEY_F1: u8 = 0x3A;
    pub const KEY_F2: u8 = 0x3B;
    pub const KEY_F3: u8 = 0x3C;
    pub const KEY_F4: u8 = 0x3D;
    pub const KEY_F5: u8 = 0x3E;
    pub const KEY_F6: u8 = 0x3F;
    pub const KEY_F7: u8 = 0x40;
    pub const KEY_F8: u8 = 0x41;
    pub const KEY_F9: u8 = 0x42;
    pub const KEY_F10: u8 = 0x43;
    pub const KEY_F11: u8 = 0x44;
    pub const KEY_F12: u8 = 0x45;
    pub const KEY_PRINT_SCREEN: u8 = 0x46;
    pub const KEY_SCROLL_LOCK: u8 = 0x47;
    pub const KEY_PAUSE: u8 = 0x48;
    pub const KEY_INSERT: u8 = 0x49;
    pub const KEY_HOME: u8 = 0x4A;
    pub const KEY_PAGE_UP: u8 = 0x4B;
    pub const KEY_DELETE: u8 = 0x4C;
    pub const KEY_END: u8 = 0x4D;
    pub const KEY_PAGE_DOWN: u8 = 0x4E;
    pub const KEY_RIGHT_ARROW: u8 = 0x4F;
    pub const KEY_LEFT_ARROW: u8 = 0x50;
    pub const KEY_DOWN_ARROW: u8 = 0x51;
    pub const KEY_UP_ARROW: u8 = 0x52;
    pub const KEY_NUM_LOCK: u8 = 0x53;
}
