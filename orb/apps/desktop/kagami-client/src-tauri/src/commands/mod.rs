//! Tauri Commands — IPC handlers for frontend communication.
//!
//! These commands bridge the GENUX frontend with the Rust backend
//! and the Kagami API server.
//!
//! Colony: Forge (e2) — Implementation, construction

pub mod api;
pub mod error;
pub mod filesystem;
pub mod keychain;
pub mod smart_home;
pub mod system;
pub mod windows;

/*
 * Module Structure:
 *
 * commands/
 *   mod.rs         - This file
 *   error.rs       - CommandError and error types
 *   windows.rs     - Window management (quick entry, settings, onboarding)
 *   smart_home.rs  - Smart home controls (lights, shades, fireplace, TV, scenes)
 *   filesystem.rs  - File operations (search, preview, list directory)
 *   api.rs         - API control (start, stop, generic requests)
 *   system.rs      - System info (CPU, memory, GPU, API health)
 *   keychain.rs    - Secure credential storage (get, set, delete)
 *
 * Usage:
 *   Commands are referenced via submodule paths in generate_handler![]:
 *   - commands::windows::show_quick_entry
 *   - commands::smart_home::set_lights
 *   - commands::api::api_request
 *   - commands::keychain::keychain_get
 *   - etc.
 */
