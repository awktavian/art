//! Hub discovery abstraction for mesh network.
//!
//! Provides platform-agnostic hub discovery interface.
//! iOS uses Bonjour/NWBrowser, Android uses NsdManager.
//!
//! The Rust SDK defines the interface and manages discovered hubs.
//! Platforms implement the actual mDNS discovery.
//!
//! h(x) >= 0. Always.

mod hub_discovery;

pub use hub_discovery::*;
