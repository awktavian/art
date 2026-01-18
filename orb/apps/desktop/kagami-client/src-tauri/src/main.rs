//! Kagami Client — The Mirror Operating System
//!
//! A HAL-aware AI assistant interface with smart home integration.
//! Built with Tauri 2.0 for cross-platform deployment.
//!
//! Architecture:
//!   world -> sense -> process -> act -> world'
//!
//! h(x) >= 0. Always.

// Allow dead_code during development - modules will be wired up incrementally
#![allow(dead_code)]
#![allow(unused_imports)]
#![allow(unused_variables)]

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod agents;
mod api_client;
mod app;
mod audio;
mod autostart;
mod cache;
mod commands;
mod context;
mod focus;
mod health;
mod hotkeys;
mod i18n;
mod keychain;
mod mesh_router;
mod realtime;
mod shared;
mod tray;

use std::fs;
use std::io::{Read, Write};
use std::path::PathBuf;
use tracing::{info, warn, error};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

/// PID file location
fn pid_file_path() -> PathBuf {
    dirs::runtime_dir()
        .or_else(|| dirs::cache_dir())
        .unwrap_or_else(|| PathBuf::from("/tmp"))
        .join("kagami-client.pid")
}

/// Check if another instance is running and acquire PID lock
fn acquire_pid_lock() -> Result<(), String> {
    let pid_path = pid_file_path();
    let current_pid = std::process::id();

    // Check if PID file exists
    if pid_path.exists() {
        // Read existing PID
        let mut file = fs::File::open(&pid_path)
            .map_err(|e| format!("Failed to open PID file: {}", e))?;
        let mut contents = String::new();
        file.read_to_string(&mut contents)
            .map_err(|e| format!("Failed to read PID file: {}", e))?;

        if let Ok(existing_pid) = contents.trim().parse::<u32>() {
            // Check if process is still running
            #[cfg(unix)]
            {
                use std::process::Command;
                let output = Command::new("kill")
                    .args(["-0", &existing_pid.to_string()])
                    .output();

                if output.map(|o| o.status.success()).unwrap_or(false) {
                    return Err(format!(
                        "Another instance is already running (PID {}). Exiting.",
                        existing_pid
                    ));
                }
            }

            #[cfg(windows)]
            {
                // On Windows, check if process exists via tasklist
                let output = std::process::Command::new("tasklist")
                    .args(["/FI", &format!("PID eq {}", existing_pid)])
                    .output();

                if let Ok(out) = output {
                    let stdout = String::from_utf8_lossy(&out.stdout);
                    if stdout.contains(&existing_pid.to_string()) {
                        return Err(format!(
                            "Another instance is already running (PID {}). Exiting.",
                            existing_pid
                        ));
                    }
                }
            }

            // Stale PID file, process not running
            warn!("Removing stale PID file (PID {} no longer running)", existing_pid);
        }
    }

    // Write our PID
    let mut file = fs::File::create(&pid_path)
        .map_err(|e| format!("Failed to create PID file: {}", e))?;
    file.write_all(current_pid.to_string().as_bytes())
        .map_err(|e| format!("Failed to write PID file: {}", e))?;

    info!("PID lock acquired: {} -> {:?}", current_pid, pid_path);
    Ok(())
}

/// Release PID lock on exit
fn release_pid_lock() {
    let pid_path = pid_file_path();
    if pid_path.exists() {
        if let Err(e) = fs::remove_file(&pid_path) {
            warn!("Failed to remove PID file: {}", e);
        } else {
            info!("PID lock released");
        }
    }
}

fn main() {
    // Initialize Sentry crash reporting (optional, requires KAGAMI_SENTRY_DSN env var)
    let _sentry_guard = app::init_sentry();

    // Initialize tracing
    tracing_subscriber::registry()
        .with(tracing_subscriber::EnvFilter::new(
            std::env::var("RUST_LOG").unwrap_or_else(|_| "info,kagami_client=debug".into()),
        ))
        .with(tracing_subscriber::fmt::layer())
        .init();

    info!("Kagami Client starting...");

    // Acquire PID lock - exit if another instance is running
    if let Err(e) = acquire_pid_lock() {
        error!("{}", e);
        std::process::exit(1);
    }

    // Register cleanup handler for clean shutdown
    ctrlc::set_handler(move || {
        info!("Received shutdown signal");
        release_pid_lock();
        std::process::exit(0);
    }).ok();

    // Initialize health state
    let health_state = app::create_health_state();

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_deep_link::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .manage(health_state)
        .setup(|app| {
            info!("Setting up Kagami...");

            let handle = app.handle();

            // Initialize the system tray
            tray::setup_tray(&handle)?;

            // Register global hotkeys
            hotkeys::register_hotkeys(&handle)?;

            info!("Kagami ready. h(x) >= 0.");
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            // Window management
            commands::windows::show_quick_entry,
            commands::windows::hide_quick_entry,
            commands::windows::show_settings,
            commands::windows::show_onboarding,
            // Smart home controls
            commands::smart_home::smart_home_action,
            commands::smart_home::execute_scene,
            commands::smart_home::toggle_fireplace,
            commands::smart_home::set_lights,
            commands::smart_home::control_shades,
            commands::smart_home::control_tv,
            commands::smart_home::announce,
            commands::smart_home::get_rooms,
            commands::smart_home::handle_deep_link,
            // API commands
            commands::api::api_request,
            commands::api::start_api,
            commands::api::stop_api,
            // System commands
            commands::system::get_api_status,
            commands::system::get_system_info,
            // Filesystem commands
            commands::filesystem::search_files,
            commands::filesystem::read_file_preview,
            commands::filesystem::list_directory,
            // Real-time commands
            realtime::connect_realtime,
            realtime::disconnect_realtime,
            realtime::get_realtime_state,
            realtime::get_realtime_latency,
            // Cache commands
            cache::get_cache_stats,
            cache::clear_cache,
            // Audio commands
            audio::get_audio_state,
            audio::get_ambient_audio_state,
            audio::start_voice_capture,
            audio::stop_voice_capture,
            audio::speak_text,
            // Context commands
            context::get_context_state,
            context::get_sensory_context,
            context::get_suggestions,
            context::execute_action,
            // Health commands
            health::health_available,
            health::health_platform_name,
            health::get_health_metrics,
            health::is_health_authorized,
            health::sync_health_data,
            health::fetch_health_status,
            // Hotkey history
            hotkeys::get_action_history,
            // Agent commands
            agents::list_agents,
            agents::get_agent,
            agents::open_agent,
            agents::close_agent,
            agents::get_agents_directory,
            agents::install_default_agents,
            // Keychain commands
            commands::keychain::keychain_get,
            commands::keychain::keychain_set,
            commands::keychain::keychain_delete,
            commands::keychain::keychain_exists,
            // Auto-start commands
            autostart::get_autostart,
            autostart::set_autostart,
            autostart::toggle_autostart_cmd,
        ])
        .run(tauri::generate_context!())
        .map_err(|e| {
            error!("Failed to run Kagami client: {}", e);
            release_pid_lock();
            e
        })
        .unwrap_or_else(|e| {
            eprintln!("Fatal error: {}", e);
            std::process::exit(1);
        });

    // Clean up PID lock on exit
    release_pid_lock();
}
