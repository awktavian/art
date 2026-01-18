//! 鏡 Kagami Hub — Voice-First Embedded Home Assistant
//!
//! A Raspberry Pi-based always-listening AI assistant with:
//! - Wake word detection ("Hey Kagami")
//! - Speech-to-text via Whisper
//! - Smart home control via Kagami API
//! - LED ring showing colony status (HAL 9000 inspired)
//! - Phone app integration for configuration and voice proxy
//!
//! η → s → μ → a → η′
//! h(x) ≥ 0. Always.

use anyhow::Result;
use std::sync::Arc;
use tracing::{debug, error, info, warn};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

// Use the library crate
use kagami_hub::api_client;
use kagami_hub::config::HubConfig;
#[cfg(feature = "rpi")]
use kagami_hub::led_ring;
use kagami_hub::realtime::{RealtimeConnection, RealtimeEvent};
use kagami_hub::voice_controller::VoiceController;
use kagami_hub::web_server::HubWebServer;

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize tracing
    tracing_subscriber::registry()
        .with(tracing_subscriber::EnvFilter::new(
            std::env::var("RUST_LOG").unwrap_or_else(|_| "info,kagami_hub=debug".into()),
        ))
        .with(tracing_subscriber::fmt::layer())
        .init();

    info!("╔═══════════════════════════════════════╗");
    info!("║               鏡                       ║");
    info!("║   Kagami Hub — Voice-First Assistant  ║");
    info!("╚═══════════════════════════════════════╝");
    info!("");
    info!("η → s → μ → a → η′");
    info!("h(x) ≥ 0. Always.");
    info!("");

    // Load configuration
    let config = HubConfig::load("config/hub.toml")?;
    info!("Configuration loaded: {}", config.general.name);
    info!("API URL: {}", config.general.api_url);

    // Initialize components
    let api = api_client::KagamiAPI::new(&config.general.api_url)?;

    // Check API connection
    match api.health().await {
        Ok(health) => {
            info!("✓ Connected to Kagami API");
            info!("  Status: {}", health.status);
            if let Some(h_x) = health.safety_score {
                info!("  h(x) = {:.2}", h_x);
            }
        }
        Err(e) => {
            warn!("⚠ Could not connect to API: {}", e);
            warn!("  Hub will retry on voice commands");
        }
    }

    // Initialize voice controller with speaker identification
    info!("Initializing voice controller...");
    let voice_controller = match VoiceController::new(&config) {
        Ok(vc) => {
            info!("✓ Voice controller initialized");
            Some(vc)
        }
        Err(e) => {
            warn!("⚠ Voice controller failed: {}", e);
            None
        }
    };

    // Load voice profiles for speaker identification
    if let Some(ref vc) = voice_controller {
        match vc.load_voice_profiles().await {
            Ok(_) => info!("✓ Voice profiles loaded for speaker ID"),
            Err(e) => warn!("⚠ Could not load voice profiles: {}", e),
        }
    }

    // Initialize LED ring if enabled
    #[cfg(feature = "rpi")]
    if config.led_ring.enabled {
        info!(
            "Initializing LED ring ({} LEDs on GPIO {})",
            config.led_ring.count, config.led_ring.pin
        );
        led_ring::init(&config.led_ring)?;
        led_ring::show_idle();
    }

    // Start real-time WebSocket connection for low-latency updates
    info!("Starting real-time connection...");
    let (mut rt_conn, mut rt_events) = RealtimeConnection::new(&config.general.api_url);
    if let Err(e) = rt_conn.start().await {
        warn!("Could not start real-time connection: {}", e);
        warn!("Falling back to polling mode");
    }

    // Start web server for phone configuration
    let web_server = Arc::new(HubWebServer::from_hub_config(&config));
    let web_server_clone = web_server.clone();
    let web_port = std::env::var("HUB_WEB_PORT")
        .ok()
        .and_then(|p| p.parse().ok())
        .unwrap_or(8080);

    tokio::spawn(async move {
        if let Err(e) = web_server_clone.run(web_port).await {
            error!("Web server error: {}", e);
        }
    });

    // Start voice pipeline loop in separate task
    info!("Starting voice pipeline...");
    info!("Wake phrase: \"{}\"", config.wake_word.phrase);

    // Voice controller (kept for potential future use via API endpoints)
    // Note: VoiceController contains non-Send types (cpal::Stream, dyn WakeWordDetector)
    // so it must be used from the main thread or via a dedicated single-threaded runtime.
    // For now, voice processing is triggered via the web API or realtime events.
    let _voice_controller = voice_controller;
    if _voice_controller.is_some() {
        info!("🎤 Voice controller ready (trigger via /voice/listen endpoint)");
    } else {
        warn!("⚠ Voice controller not available, voice commands disabled");
    }

    // Main loop — event-driven with real-time updates
    info!("🏠 Hub ready, entering main loop");
    info!("📱 Phone config available at http://0.0.0.0:{}", web_port);
    loop {
        tokio::select! {
            // Handle real-time events (low latency)
            Some(event) = rt_events.recv() => {
                match event {
                    RealtimeEvent::Connected => {
                        info!("🔗 Real-time WebSocket connected");
                        web_server.update_status(|s| s.api_connected = true).await;
                        #[cfg(feature = "rpi")]
                        if config.led_ring.enabled {
                            led_ring::show_idle();
                        }
                    }
                    RealtimeEvent::Disconnected => {
                        warn!("⚡ Real-time WebSocket disconnected");
                        web_server.update_status(|s| s.api_connected = false).await;
                        #[cfg(feature = "rpi")]
                        if config.led_ring.enabled {
                            led_ring::show_error();
                        }
                    }
                    RealtimeEvent::ColonyActivity { colony, action } => {
                        debug!("🐝 Colony activity: {} → {}", colony, action);
                        let colony_name = colony.clone();
                        web_server.update_status(|s| s.current_colony = Some(colony_name)).await;
                        #[cfg(feature = "rpi")]
                        if config.led_ring.enabled {
                            // Highlight the active colony on LED ring
                            let idx = match colony.as_str() {
                                "spark" => 0, "forge" => 1, "flow" => 2,
                                "nexus" => 3, "beacon" => 4, "grove" => 5,
                                "crystal" => 6, _ => 0,
                            };
                            led_ring::highlight_colony(idx);
                        }
                    }
                    RealtimeEvent::SafetyUpdate { h_x } => {
                        debug!("🔐 Safety: h(x) = {:.2}", h_x);
                        web_server.update_status(|s| s.safety_score = Some(h_x)).await;
                        #[cfg(feature = "rpi")]
                        if config.led_ring.enabled {
                            led_ring::set_safety_status(h_x);
                        }
                    }
                    RealtimeEvent::HomeUpdate(state) => {
                        debug!("🏠 Home: movie={}, fireplace={}, rooms={:?}",
                            state.movie_mode, state.fireplace_on, state.occupied_rooms);
                    }
                    RealtimeEvent::StateUpdate(state) => {
                        debug!("📊 State update: {:?}", state);
                    }
                    // Orb interaction from another client (flash LED ring)
                    RealtimeEvent::OrbInteraction(interaction) => {
                        info!("🔮 Orb interaction from {}: {}", interaction.client, interaction.action);
                        #[cfg(feature = "rpi")]
                        if config.led_ring.enabled {
                            // Flash the LED ring in response to cross-client orb tap
                            led_ring::orb_flash(&interaction.action, None);
                        }
                    }
                    // Orb state changed (update LED colors)
                    RealtimeEvent::OrbStateChanged(orb_state) => {
                        debug!("🔮 Orb state: {} (colony: {:?})", orb_state.activity, orb_state.active_colony);
                        #[cfg(feature = "rpi")]
                        if config.led_ring.enabled {
                            // Update LED ring color to match canonical orb color
                            led_ring::set_orb_color(&orb_state.color_hex);
                        }
                    }
                    RealtimeEvent::Error(err) => {
                        warn!("⚠️ Realtime error: {}", err);
                    }
                }
            }

            // Fallback polling (only when WebSocket disconnected)
            _ = tokio::time::sleep(tokio::time::Duration::from_secs(30)) => {
                if !rt_conn.is_connected() {
                    debug!("Polling API (WebSocket disconnected)...");
                    #[cfg(feature = "rpi")]
                    if let Ok(health) = api.health().await {
                        if config.led_ring.enabled {
                            led_ring::update_status(health.safety_score);
                        }
                    }
                }
            }
        }
    }
}
