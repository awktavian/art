//! System tray integration for Kagami Desktop
//!
//! Provides quick access to common actions without opening the main window.
//!
//! Colony: Flow (e₃) — Sensing, adaptation
//!
//! η → s → μ → a → η′
//! h(x) ≥ 0. Always.

use tauri::{
    menu::{Menu, MenuItem, CheckMenuItem},
    tray::{TrayIcon, TrayIconBuilder},
    AppHandle, Emitter, Manager,
};
use tracing::{debug, info, warn};

use crate::autostart;

/// Create and configure the system tray
pub fn setup_tray(app: &AppHandle) -> Result<TrayIcon, tauri::Error> {
    info!("Setting up system tray");

    // Check current auto-start state
    let autostart_enabled = autostart::is_autostart_enabled();

    let menu = Menu::with_items(
        app,
        &[
            &MenuItem::with_id(app, "show", "Show Kagami", true, None::<&str>)?,
            &MenuItem::with_id(app, "movie_mode", "Movie Mode", true, None::<&str>)?,
            &MenuItem::with_id(app, "goodnight", "Goodnight", true, None::<&str>)?,
            &MenuItem::with_id(app, "separator1", "─────────", false, None::<&str>)?,
            &CheckMenuItem::with_id(app, "start_at_login", "Start at Login", true, autostart_enabled, None::<&str>)?,
            &MenuItem::with_id(app, "separator2", "─────────", false, None::<&str>)?,
            &MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?,
        ],
    )?;

    TrayIconBuilder::new()
        .icon(app.default_window_icon().unwrap().clone())
        .menu(&menu)
        .on_menu_event(|app, event| {
            let id = event.id.as_ref();
            debug!(menu_id = id, "Tray menu event");

            match id {
                "show" => {
                    if let Some(window) = app.get_webview_window("main") {
                        let _ = window.show();
                        let _ = window.set_focus();
                        info!("Showed main window");
                    }
                }
                "movie_mode" => {
                    // Emit event to frontend to trigger movie mode
                    if let Err(e) = app.emit("tray:movie_mode", ()) {
                        warn!(error = %e, "Failed to emit movie mode event");
                    }
                    info!("Movie mode triggered from tray");
                }
                "goodnight" => {
                    // Emit event to frontend to trigger goodnight
                    if let Err(e) = app.emit("tray:goodnight", ()) {
                        warn!(error = %e, "Failed to emit goodnight event");
                    }
                    info!("Goodnight triggered from tray");
                }
                "start_at_login" => {
                    // Toggle auto-start setting
                    match autostart::toggle_autostart() {
                        Ok(enabled) => {
                            info!("Auto-start toggled: {}", enabled);
                            // Emit event to frontend
                            if let Err(e) = app.emit("tray:autostart_changed", enabled) {
                                warn!(error = %e, "Failed to emit autostart event");
                            }
                        }
                        Err(e) => {
                            warn!(error = %e, "Failed to toggle auto-start");
                        }
                    }
                }
                "quit" => {
                    info!("Quitting application from tray");
                    app.exit(0);
                }
                _ => {}
            }
        })
        .build(app)
}
