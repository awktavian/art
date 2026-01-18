//! HID (Human Interface Device) Module
//!
//! Provides Bluetooth and USB HID profiles for keyboard, mouse, and gamepad.
//!
//! h(x) >= 0. Always.

pub mod ble;
pub mod usb;
pub mod reports;
pub mod rate_limiter;

#[cfg(feature = "duckyscript")]
pub mod ducky;

pub use ble::BleHid;
pub use usb::UsbHid;
pub use reports::*;
pub use rate_limiter::RateLimiter;

/// HID Report types
#[derive(Debug, Clone)]
pub enum HidReport {
    Keyboard(KeyboardReport),
    Mouse(MouseReport),
    Consumer(ConsumerReport),
    Gamepad(GamepadReport),
}
