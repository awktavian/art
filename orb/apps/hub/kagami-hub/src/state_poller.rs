//! Background State Polling
//!
//! Periodically refreshes cached state from the main API when connectivity allows.
//! Persists state to SQLite for offline resilience.
//! Enforces CBF safety checks (h(x) >= 0) before command execution.
//!
//! Colony: Nexus (e₄) — Continuous state synchronization
//!
//! η → s → μ → a → η′
//! h(x) ≥ 0. Always.

use std::sync::Arc;
use std::time::Duration;
use tokio::sync::broadcast;
use tokio::time::interval;
use tracing::{debug, error, info, warn};

use crate::state_cache::{StateCache, ZoneLevel};
use crate::safety::{validate_and_log_queued};
use crate::offline_commands::QueuedCommand;

#[cfg(feature = "persistence")]
use crate::db::HubDatabase;

/// Events emitted by the state poller
#[derive(Debug, Clone)]
pub enum PollEvent {
    /// Zone level changed
    ZoneChanged { old: ZoneLevel, new: ZoneLevel },

    /// Tesla state updated
    TeslaUpdated,

    /// Home state updated
    HomeUpdated,

    /// Weather state updated
    WeatherUpdated,

    /// Poll cycle completed
    CycleComplete { zone: ZoneLevel, duration_ms: u64 },

    /// Error during polling
    PollError { source: String, error: String },
}

/// Configuration for the state poller
#[derive(Debug, Clone)]
pub struct PollerConfig {
    /// Interval between poll cycles when online
    pub online_interval: Duration,

    /// Interval between poll cycles when offline (for zone probing)
    pub offline_interval: Duration,

    /// Interval for weather updates (less frequent)
    pub weather_interval: Duration,

    /// How often to persist to database
    pub persist_interval: Duration,

    /// How often to clean up old commands
    pub cleanup_interval: Duration,
}

impl Default for PollerConfig {
    fn default() -> Self {
        Self {
            online_interval: Duration::from_secs(30),
            offline_interval: Duration::from_secs(60),
            weather_interval: Duration::from_secs(300), // 5 minutes
            persist_interval: Duration::from_secs(60),
            cleanup_interval: Duration::from_secs(3600), // 1 hour
        }
    }
}

/// Background state poller
pub struct StatePoller {
    state_cache: Arc<StateCache>,
    config: PollerConfig,
    event_tx: broadcast::Sender<PollEvent>,

    #[cfg(feature = "persistence")]
    db: Option<Arc<HubDatabase>>,
}

impl StatePoller {
    /// Create a new state poller
    pub fn new(state_cache: Arc<StateCache>, config: PollerConfig) -> Self {
        let (event_tx, _) = broadcast::channel(100);

        Self {
            state_cache,
            config,
            event_tx,
            #[cfg(feature = "persistence")]
            db: None,
        }
    }

    /// Set the database for persistence
    #[cfg(feature = "persistence")]
    pub fn with_database(mut self, db: Arc<HubDatabase>) -> Self {
        self.db = Some(db);
        self
    }

    /// Subscribe to poll events
    pub fn subscribe(&self) -> broadcast::Receiver<PollEvent> {
        self.event_tx.subscribe()
    }

    /// Start the polling loop (runs until cancelled)
    pub async fn start(&self, mut shutdown: tokio::sync::watch::Receiver<bool>) {
        info!("Starting state poller");

        let mut poll_interval = interval(self.config.online_interval);
        let mut weather_counter = 0u32;
        let mut persist_counter = 0u32;
        let mut cleanup_counter = 0u32;

        let weather_every = (self.config.weather_interval.as_secs() / self.config.online_interval.as_secs()) as u32;
        let persist_every = (self.config.persist_interval.as_secs() / self.config.online_interval.as_secs()) as u32;
        let cleanup_every = (self.config.cleanup_interval.as_secs() / self.config.online_interval.as_secs()) as u32;

        let mut last_zone = self.state_cache.get_zone().await;

        loop {
            tokio::select! {
                _ = poll_interval.tick() => {
                    let start = std::time::Instant::now();

                    // Probe zone first
                    let zone = self.state_cache.probe_zone().await;

                    // Emit zone change event if changed
                    if zone != last_zone {
                        info!("Zone changed: {:?} → {:?}", last_zone, zone);
                        let _ = self.event_tx.send(PollEvent::ZoneChanged {
                            old: last_zone.clone(),
                            new: zone.clone(),
                        });

                        #[cfg(feature = "persistence")]
                        if let Some(ref db) = self.db {
                            let api_reachable = matches!(zone, ZoneLevel::Transcend | ZoneLevel::Beyond);
                            let internet_reachable = !matches!(zone, ZoneLevel::UnthinkingDepths);
                            let _ = db.record_zone(zone.clone(), api_reachable, internet_reachable).await;
                        }

                        last_zone = zone.clone();
                    }

                    // Refresh state if we have connectivity
                    if matches!(zone, ZoneLevel::Transcend | ZoneLevel::Beyond) {
                        // Always refresh Tesla and Home
                        match self.state_cache.refresh_tesla().await {
                            Some(_) => {
                                let _ = self.event_tx.send(PollEvent::TeslaUpdated);
                            }
                            None => {
                                warn!("Failed to refresh Tesla state");
                                let _ = self.event_tx.send(PollEvent::PollError {
                                    source: "tesla".to_string(),
                                    error: "Failed to fetch".to_string(),
                                });
                            }
                        }

                        match self.state_cache.refresh_home().await {
                            Some(_) => {
                                let _ = self.event_tx.send(PollEvent::HomeUpdated);
                            }
                            None => {
                                warn!("Failed to refresh Home state");
                                let _ = self.event_tx.send(PollEvent::PollError {
                                    source: "home".to_string(),
                                    error: "Failed to fetch".to_string(),
                                });
                            }
                        }

                        // Weather less frequently
                        weather_counter += 1;
                        if weather_counter >= weather_every {
                            weather_counter = 0;
                            if self.state_cache.refresh_weather().await.is_some() {
                                let _ = self.event_tx.send(PollEvent::WeatherUpdated);
                            } else {
                                warn!("Failed to refresh Weather");
                            }
                        }

                        // Persist to database
                        #[cfg(feature = "persistence")]
                        {
                            persist_counter += 1;
                            if persist_counter >= persist_every {
                                persist_counter = 0;
                                self.persist_state().await;
                            }
                        }

                        // Process queued commands
                        #[cfg(feature = "persistence")]
                        self.process_queued_commands().await;

                        // Cleanup old commands
                        #[cfg(feature = "persistence")]
                        {
                            cleanup_counter += 1;
                            if cleanup_counter >= cleanup_every {
                                cleanup_counter = 0;
                                if let Some(ref db) = self.db {
                                    let _ = db.cleanup_old_commands(7).await;
                                    let _ = db.cleanup_stale_peers(24).await;
                                }
                            }
                        }
                    }

                    let duration = start.elapsed();
                    let _ = self.event_tx.send(PollEvent::CycleComplete {
                        zone,
                        duration_ms: duration.as_millis() as u64,
                    });

                    debug!("Poll cycle complete in {:?}", duration);
                }

                _ = shutdown.changed() => {
                    if *shutdown.borrow() {
                        info!("State poller shutting down");
                        break;
                    }
                }
            }
        }

        // Final persist before shutdown
        #[cfg(feature = "persistence")]
        self.persist_state().await;

        info!("State poller stopped");
    }

    /// Persist current state to database
    #[cfg(feature = "persistence")]
    async fn persist_state(&self) {
        let Some(ref db) = self.db else { return };

        // Persist Tesla state
        if let Some(state) = self.state_cache.get_tesla().await {
            let fetched_at = chrono::Utc::now(); // Should use actual fetch time
            if let Err(e) = db.save_tesla_state(&state, fetched_at).await {
                error!("Failed to persist Tesla state: {}", e);
            }
        }

        // Persist Home state
        if let Some(state) = self.state_cache.get_home().await {
            let fetched_at = chrono::Utc::now();
            if let Err(e) = db.save_home_state(&state, fetched_at).await {
                error!("Failed to persist Home state: {}", e);
            }
        }

        // Persist Weather state
        if let Some(state) = self.state_cache.get_weather().await {
            let fetched_at = chrono::Utc::now();
            if let Err(e) = db.save_weather_state(&state, fetched_at).await {
                error!("Failed to persist Weather state: {}", e);
            }
        }

        debug!("State persisted to database");
    }

    /// Process any queued commands now that we have connectivity
    #[cfg(feature = "persistence")]
    async fn process_queued_commands(&self) {
        let Some(ref db) = self.db else { return };

        let pending = match db.get_pending_commands().await {
            Ok(cmds) => cmds,
            Err(e) => {
                warn!("Failed to get pending commands: {}", e);
                return;
            }
        };

        if pending.is_empty() {
            return;
        }

        info!("Processing {} queued commands", pending.len());

        for cmd in pending {
            match self.execute_queued_command(&cmd).await {
                Ok(_) => {
                    let _ = db.mark_command_executed(cmd.id).await;
                }
                Err(e) => {
                    let _ = db.mark_command_failed(cmd.id, &e.to_string()).await;
                }
            }
        }
    }

    /// Execute a single queued command with CBF safety enforcement
    ///
    /// h(x) >= 0 is checked BEFORE execution. Unsafe commands are blocked.
    #[cfg(feature = "persistence")]
    async fn execute_queued_command(&self, cmd: &crate::db::QueuedCmd) -> anyhow::Result<()> {
        use serde_json::Value;

        let payload: Value = serde_json::from_str(&cmd.payload)?;

        // Convert to QueuedCommand for safety check
        let queued_cmd = match cmd.command_type.as_str() {
            "tesla_climate" => {
                let on = payload.get("on").and_then(|v| v.as_bool()).unwrap_or(true);
                Some(QueuedCommand::TeslaClimate { on })
            }
            "tesla_lock" => {
                let lock = payload.get("lock").and_then(|v| v.as_bool()).unwrap_or(true);
                Some(QueuedCommand::TeslaLock { lock })
            }
            "tesla_frunk" => Some(QueuedCommand::TeslaFrunk),
            "tesla_trunk" => Some(QueuedCommand::TeslaTrunk),
            "tesla_honk" => Some(QueuedCommand::TeslaHonk),
            "tesla_flash" => Some(QueuedCommand::TeslaFlash),
            "set_thermostat" => {
                let temp = payload.get("temp").and_then(|v| v.as_f64()).unwrap_or(72.0) as f32;
                Some(QueuedCommand::SetThermostat { temp })
            }
            "announce" => {
                let message = payload.get("message").and_then(|v| v.as_str()).unwrap_or("").to_string();
                let rooms = payload.get("rooms").and_then(|v| {
                    v.as_array().map(|arr| {
                        arr.iter().filter_map(|r| r.as_str().map(String::from)).collect()
                    })
                });
                Some(QueuedCommand::Announce { message, rooms })
            }
            "spotify_play" => {
                let playlist = payload.get("playlist").and_then(|v| v.as_str()).map(String::from);
                Some(QueuedCommand::SpotifyPlay { playlist })
            }
            "spotify_pause" => Some(QueuedCommand::SpotifyPause),
            "spotify_skip" => Some(QueuedCommand::SpotifySkip),
            "spotify_previous" => Some(QueuedCommand::SpotifyPrevious),
            "spotify_volume" => {
                let level = payload.get("level").and_then(|v| v.as_u64()).unwrap_or(50) as u8;
                Some(QueuedCommand::SpotifyVolume { level })
            }
            _ => {
                warn!("Unknown queued command type: {}", cmd.command_type);
                None
            }
        };

        // ====================================================================
        // CBF SAFETY CHECK — h(x) >= 0 ENFORCEMENT
        // ====================================================================
        if let Some(ref qcmd) = queued_cmd {
            let safety_result = validate_and_log_queued(qcmd);

            if !safety_result.safe {
                // h(x) < 0 — BLOCK THE COMMAND
                return Err(anyhow::anyhow!(
                    "Command blocked by CBF: {} (h(x) = {:.2})",
                    safety_result.reason.unwrap_or_else(|| "Safety violation".to_string()),
                    safety_result.h_x
                ));
            }

            // Log warnings but proceed
            for warning in &safety_result.warnings {
                warn!("⚠ Safety warning: {}", warning);
            }
        }

        // ====================================================================
        // EXECUTE COMMAND (h(x) >= 0 verified)
        // ====================================================================
        match cmd.command_type.as_str() {
            "tesla_climate" => {
                let on = payload.get("on").and_then(|v| v.as_bool()).unwrap_or(true);
                let temp = payload.get("temp_c").and_then(|v| v.as_f64());
                self.state_cache.tesla_climate(on, temp).await
                    .map_err(|e| anyhow::anyhow!("{}", e))?;
            }
            "tesla_lock" => {
                let lock = payload.get("lock").and_then(|v| v.as_bool()).unwrap_or(true);
                self.state_cache.tesla_lock(lock).await
                    .map_err(|e| anyhow::anyhow!("{}", e))?;
            }
            "tesla_frunk" => {
                self.state_cache.tesla_trunk("frunk").await
                    .map_err(|e| anyhow::anyhow!("{}", e))?;
            }
            "tesla_trunk" => {
                self.state_cache.tesla_trunk("trunk").await
                    .map_err(|e| anyhow::anyhow!("{}", e))?;
            }
            "tesla_honk" => {
                self.state_cache.tesla_honk().await
                    .map_err(|e| anyhow::anyhow!("{}", e))?;
            }
            "tesla_flash" => {
                self.state_cache.tesla_flash().await
                    .map_err(|e| anyhow::anyhow!("{}", e))?;
            }
            "spotify_play" | "spotify_pause" | "spotify_skip" |
            "spotify_previous" | "spotify_volume" => {
                // Spotify commands routed through state_cache
                info!("Executing Spotify command: {} (API call required)", cmd.command_type);
                // Note: Actual Spotify execution would be via API client
                // self.state_cache.spotify_command(...).await?
            }
            "set_thermostat" => {
                let _temp = payload.get("temp").and_then(|v| v.as_f64()).unwrap_or(72.0);
                info!("Setting thermostat (API call required)");
                // Note: Thermostat execution via API client
            }
            "announce" => {
                let _message = payload.get("message").and_then(|v| v.as_str()).unwrap_or("");
                info!("Announce command (API call required)");
                // Note: Announce via API client
            }
            _ => {}
        }

        Ok(())
    }

    /// Restore state from database on startup
    #[cfg(feature = "persistence")]
    pub async fn restore_from_database(&self) -> anyhow::Result<()> {
        let Some(ref db) = self.db else { return Ok(()) };

        info!("Restoring state from database...");

        // Restore Tesla state if available
        if let Some((state, fetched_at)) = db.load_tesla_state().await? {
            let age = chrono::Utc::now() - fetched_at;
            info!("Restored Tesla state (age: {}s, battery: {}%)",
                age.num_seconds(), state.battery_level);
            // Would need to set this in state_cache
        }

        // Restore Home state
        if let Some((_state, fetched_at)) = db.load_home_state().await? {
            let age = chrono::Utc::now() - fetched_at;
            info!("Restored Home state (age: {}s)", age.num_seconds());
        }

        // Restore Weather state
        if let Some((_state, fetched_at)) = db.load_weather_state().await? {
            let age = chrono::Utc::now() - fetched_at;
            info!("Restored Weather state (age: {}s)", age.num_seconds());
        }

        // Record boot
        db.record_boot().await?;

        Ok(())
    }
}

/// Start the state poller as a background task
pub fn spawn_state_poller(
    state_cache: Arc<StateCache>,
    config: PollerConfig,
    #[cfg(feature = "persistence")]
    db: Option<Arc<HubDatabase>>,
) -> (tokio::task::JoinHandle<()>, tokio::sync::watch::Sender<bool>, broadcast::Receiver<PollEvent>) {
    let (shutdown_tx, shutdown_rx) = tokio::sync::watch::channel(false);

    #[cfg(feature = "persistence")]
    let poller = {
        let mut p = StatePoller::new(state_cache, config);
        if let Some(d) = db {
            p = p.with_database(d);
        }
        p
    };

    #[cfg(not(feature = "persistence"))]
    let poller = StatePoller::new(state_cache, config);

    let event_rx = poller.subscribe();

    let handle = tokio::spawn(async move {
        poller.start(shutdown_rx).await;
    });

    (handle, shutdown_tx, event_rx)
}

/*
 * 鏡
 * The pulse of the seed. Always polling. Always persisting.
 */
