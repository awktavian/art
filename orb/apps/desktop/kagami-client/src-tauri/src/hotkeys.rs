//! Global hotkey registration for Kagami Desktop
//!
//! Enables quick access via keyboard shortcuts system-wide.
//!
//! Colony: Spark (e₁) — Initiative, generation
//!
//! η → s → μ → a → η′
//! h(x) ≥ 0. Always.

use serde::{Deserialize, Serialize};
use std::collections::VecDeque;
use std::sync::Mutex;
use tauri::AppHandle;
use tauri::{Emitter, Manager};
use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut};
use tracing::{debug, info, warn};

/// Maximum actions to keep in history
const MAX_HISTORY: usize = 100;

/// Action record for history
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ActionRecord {
    pub action: String,
    pub timestamp: String,
    pub success: bool,
}

/// Global action history
static ACTION_HISTORY: Mutex<Option<VecDeque<ActionRecord>>> = Mutex::new(None);

/// Register global hotkeys for the application
///
/// # Hotkeys
/// - `Cmd+Shift+K` (macOS) / `Ctrl+Shift+K` (Windows/Linux): Show quick entry
/// - `Cmd+Shift+M` (macOS) / `Ctrl+Shift+M` (Windows/Linux): Toggle movie mode
pub fn register_hotkeys(app: &AppHandle) -> Result<(), Box<dyn std::error::Error>> {
    info!("Registering global hotkeys");

    // Quick entry shortcut: Cmd/Ctrl+Shift+K
    let quick_entry = Shortcut::new(Some(Modifiers::SUPER | Modifiers::SHIFT), Code::KeyK);

    app.global_shortcut().register(quick_entry)?;
    let _ = app.global_shortcut().on_shortcut(quick_entry, |app, _, _| {
        debug!("Quick entry hotkey pressed");
        if let Some(window) = app.get_webview_window("quick-entry") {
            let _ = window.show();
            let _ = window.set_focus();
            info!("Showed quick entry window");
        } else {
            warn!("Quick entry window not found");
        }
    });

    // Movie mode shortcut: Cmd/Ctrl+Shift+M
    let movie_mode = Shortcut::new(Some(Modifiers::SUPER | Modifiers::SHIFT), Code::KeyM);

    app.global_shortcut().register(movie_mode)?;
    let _ = app.global_shortcut().on_shortcut(movie_mode, |app, _, _| {
        debug!("Movie mode hotkey pressed");
        if let Err(e) = app.emit("hotkey:movie_mode", ()) {
            warn!(error = %e, "Failed to emit movie mode event");
        }
        info!("Movie mode triggered from hotkey");
    });

    info!("Global hotkeys registered successfully");
    Ok(())
}

/// Record an action in the history
pub fn record_action(action: &str, success: bool) {
    let mut history = ACTION_HISTORY.lock().unwrap();
    if history.is_none() {
        *history = Some(VecDeque::with_capacity(MAX_HISTORY));
    }

    if let Some(queue) = history.as_mut() {
        if queue.len() >= MAX_HISTORY {
            queue.pop_front();
        }
        queue.push_back(ActionRecord {
            action: action.to_string(),
            timestamp: chrono::Utc::now().to_rfc3339(),
            success,
        });
    }
}

/// Get action history
#[tauri::command]
pub fn get_action_history() -> Vec<ActionRecord> {
    let history = ACTION_HISTORY.lock().unwrap();
    history
        .as_ref()
        .map(|q| q.iter().cloned().collect())
        .unwrap_or_default()
}
