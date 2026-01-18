//! Shared Application Setup
//!
//! Common initialization logic for both main.rs (desktop) and lib.rs (mobile).
//! This module reduces code duplication by extracting shared setup routines.

use tauri::App;
use tracing::info;

use crate::health;

/// Initialize Sentry crash reporting if DSN is configured
pub fn init_sentry() -> Option<sentry::ClientInitGuard> {
    const SENTRY_DSN_ENV: &str = "KAGAMI_SENTRY_DSN";

    std::env::var(SENTRY_DSN_ENV).ok().map(|dsn| {
        sentry::init((
            dsn,
            sentry::ClientOptions {
                release: sentry::release_name!(),
                environment: Some(
                    std::env::var("KAGAMI_ENV")
                        .unwrap_or_else(|_| "development".to_string())
                        .into(),
                ),
                ..Default::default()
            },
        ))
    })
}

/// Setup the Tauri application with common plugins and handlers
pub fn setup_app(app: &mut App) -> Result<(), Box<dyn std::error::Error>> {
    info!("Setting up Kagami...");

    #[cfg(desktop)]
    {
        let handle = app.handle();

        // Initialize the system tray (desktop only)
        crate::tray::setup_tray(&handle)?;

        // Register global hotkeys (desktop only)
        crate::hotkeys::register_hotkeys(&handle)?;
    }

    info!("Kagami ready. h(x) >= 0.");
    Ok(())
}

/// Create and manage health state
pub fn create_health_state() -> health::SharedHealthState {
    health::create_health_state()
}

/// Get the list of all Tauri command handlers
///
/// This macro invocation is shared between main.rs and lib.rs
#[macro_export]
macro_rules! kagami_invoke_handler {
    () => {
        tauri::generate_handler![
            crate::commands::show_quick_entry,
            crate::commands::hide_quick_entry,
            crate::commands::smart_home_action,
            crate::commands::api_request,
            crate::commands::get_api_status,
            crate::commands::get_system_info,
            crate::commands::start_api,
            crate::commands::stop_api,
            crate::commands::execute_scene,
            crate::commands::toggle_fireplace,
            crate::commands::set_lights,
            crate::commands::control_shades,
            crate::commands::control_tv,
            crate::commands::announce,
            // Real-time commands
            crate::realtime::connect_realtime,
            crate::realtime::disconnect_realtime,
            crate::realtime::get_realtime_state,
            crate::realtime::get_realtime_latency,
            // Cache commands
            crate::cache::get_cache_stats,
            crate::cache::clear_cache,
            // Audio commands
            crate::audio::get_audio_state,
            crate::audio::get_ambient_audio_state,
            crate::audio::start_voice_capture,
            crate::audio::stop_voice_capture,
            crate::audio::speak_text,
            // Context commands
            crate::context::get_context_state,
            crate::context::get_sensory_context,
            crate::context::get_suggestions,
            crate::context::execute_action,
            // Health commands
            crate::health::health_available,
            crate::health::health_platform_name,
            crate::health::get_health_metrics,
            crate::health::is_health_authorized,
            crate::health::sync_health_data,
            crate::health::fetch_health_status,
            // Filesystem commands (HAL integration)
            crate::commands::search_files,
            crate::commands::read_file_preview,
            crate::commands::list_directory,
            crate::commands::get_rooms,
            // Hotkey history
            crate::hotkeys::get_action_history,
            // Keychain commands
            crate::commands::keychain::keychain_get,
            crate::commands::keychain::keychain_set,
            crate::commands::keychain::keychain_delete,
            crate::commands::keychain::keychain_exists,
            // Auto-start commands
            crate::autostart::get_autostart,
            crate::autostart::set_autostart,
            crate::autostart::toggle_autostart_cmd,
            // Desktop control commands (mouse, keyboard, clipboard, process)
            crate::desktop_control::desktop_mouse_move,
            crate::desktop_control::desktop_mouse_click,
            crate::desktop_control::desktop_mouse_scroll,
            crate::desktop_control::desktop_type_text,
            crate::desktop_control::desktop_hotkey,
            crate::desktop_control::desktop_key_press,
            crate::desktop_control::desktop_clipboard_get,
            crate::desktop_control::desktop_clipboard_set,
            crate::desktop_control::desktop_list_processes,
            crate::desktop_control::desktop_kill_process,
            crate::desktop_control::desktop_start_process,
            crate::desktop_control::desktop_system_info,
            // Vision commands (screen capture)
            crate::vision::vision_check_permission,
            crate::vision::vision_request_permission,
            crate::vision::vision_get_displays,
            crate::vision::vision_capture_screen,
            crate::vision::vision_capture_region,
            crate::vision::vision_get_windows,
            crate::vision::vision_capture_window,
            // Accessibility commands
            crate::accessibility::check_accessibility,
            crate::accessibility::get_focused_application,
            crate::accessibility::get_applications,
            crate::accessibility::get_element_at,
            crate::accessibility::accessibility_action,
            crate::accessibility::accessibility_focus,
        ]
    };
}

/// Get the list of all Tauri plugins
pub fn configure_plugins<R: tauri::Runtime>(
    builder: tauri::Builder<R>,
) -> tauri::Builder<R> {
    builder
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_deep_link::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_clipboard_manager::init())
}
