//! Context Engine — Theory of Mind for Desktop
//!
//! Models Tim's intentions based on time, location, and activity.
//! Surfaces optimal actions and adapts UI accordingly.
//!
//! Theory of Mind:
//!   Tim is a single occupant in a luxury smart home.
//!   He values efficiency, minimal interaction, intelligent defaults.
//!   Context (time, location, activity) determines optimal actions.
//!
//! η → s → μ → a → η′
//! h(x) ≥ 0. Always.

use chrono::Datelike;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::debug;

// ═══════════════════════════════════════════════════════════════
// TIME CONTEXT
// ═══════════════════════════════════════════════════════════════

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum TimeContext {
    EarlyMorning,  // 5-7am: Just woke up
    Morning,       // 7-9am: Getting ready
    WorkDay,       // 9am-5pm: Working
    Evening,       // 5-8pm: Winding down
    LateEvening,   // 8-10pm: Relaxing
    Night,         // 10pm-12am: Bedtime
    LateNight,     // 12-5am: Should be sleeping
}

impl TimeContext {
    pub fn current() -> Self {
        let hour = chrono::Local::now().hour();
        match hour {
            5..=6 => Self::EarlyMorning,
            7..=8 => Self::Morning,
            9..=16 => Self::WorkDay,
            17..=19 => Self::Evening,
            20..=21 => Self::LateEvening,
            22..=23 => Self::Night,
            _ => Self::LateNight,
        }
    }

    pub fn greeting(&self) -> &'static str {
        match self {
            Self::EarlyMorning => "Good morning",
            Self::Morning => "Morning",
            Self::WorkDay => "",
            Self::Evening => "Welcome home",
            Self::LateEvening => "Relaxing",
            Self::Night => "Good night",
            Self::LateNight => "Rest well",
        }
    }

    pub fn primary_action(&self) -> SuggestedAction {
        match self {
            Self::EarlyMorning | Self::Morning => SuggestedAction {
                id: "start_day".into(),
                icon: "☀️".into(),
                label: "Start Day".into(),
                short_label: "Start".into(),
                action: ActionType::LightsOn,
                priority: 10,
            },
            Self::WorkDay => SuggestedAction {
                id: "focus".into(),
                icon: "🎯".into(),
                label: "Focus Mode".into(),
                short_label: "Focus".into(),
                action: ActionType::FocusMode,
                priority: 5,
            },
            Self::Evening | Self::LateEvening => SuggestedAction {
                id: "movie".into(),
                icon: "🎬".into(),
                label: "Movie Mode".into(),
                short_label: "Movie".into(),
                action: ActionType::MovieMode,
                priority: 10,
            },
            Self::Night | Self::LateNight => SuggestedAction {
                id: "goodnight".into(),
                icon: "🌙".into(),
                label: "Goodnight".into(),
                short_label: "Night".into(),
                action: ActionType::Goodnight,
                priority: 10,
            },
        }
    }

    pub fn secondary_actions(&self) -> Vec<SuggestedAction> {
        match self {
            Self::EarlyMorning | Self::Morning => vec![
                SuggestedAction {
                    id: "coffee".into(),
                    icon: "☕".into(),
                    label: "Coffee Time".into(),
                    short_label: "Coffee".into(),
                    action: ActionType::Coffee,
                    priority: 8,
                },
            ],
            Self::WorkDay => vec![
                SuggestedAction {
                    id: "dim".into(),
                    icon: "🌙".into(),
                    label: "Dim Lights".into(),
                    short_label: "Dim".into(),
                    action: ActionType::LightsDim,
                    priority: 4,
                },
            ],
            Self::Evening | Self::LateEvening => vec![
                SuggestedAction {
                    id: "fireplace".into(),
                    icon: "🔥".into(),
                    label: "Fireplace".into(),
                    short_label: "Fire".into(),
                    action: ActionType::Fireplace,
                    priority: 8,
                },
                SuggestedAction {
                    id: "relax".into(),
                    icon: "🛋️".into(),
                    label: "Relax Mode".into(),
                    short_label: "Relax".into(),
                    action: ActionType::RelaxMode,
                    priority: 6,
                },
            ],
            Self::Night | Self::LateNight => vec![
                SuggestedAction {
                    id: "lights_off".into(),
                    icon: "💤".into(),
                    label: "Lights Off".into(),
                    short_label: "Off".into(),
                    action: ActionType::LightsOff,
                    priority: 8,
                },
            ],
        }
    }
}

use chrono::Timelike;

// ═══════════════════════════════════════════════════════════════
// LOCATION CONTEXT
// ═══════════════════════════════════════════════════════════════

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum LocationContext {
    Home,
    Away,
    Arriving,    // Tesla entering geofence
    Leaving,
    Unknown,
}

impl Default for LocationContext {
    fn default() -> Self {
        Self::Home  // Assume home for desktop client
    }
}

// ═══════════════════════════════════════════════════════════════
// ACTIVITY INFERENCE
// ═══════════════════════════════════════════════════════════════

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ActivityInference {
    Sleeping,    // Eight Sleep says in bed
    Waking,      // Just got up
    Working,     // At desk, using computer
    Cooking,     // Kitchen activity
    Relaxing,    // Living room, evening
    Watching,    // Movie mode active
    Hosting,     // Multiple people detected
    Idle,        // No specific activity
}

impl Default for ActivityInference {
    fn default() -> Self {
        Self::Idle
    }
}

// ═══════════════════════════════════════════════════════════════
// SUGGESTED ACTION
// ═══════════════════════════════════════════════════════════════

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SuggestedAction {
    pub id: String,
    pub icon: String,
    pub label: String,
    pub short_label: String,
    pub action: ActionType,
    pub priority: i32,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ActionType {
    MovieMode,
    Goodnight,
    WelcomeHome,
    Away,
    LightsOn,
    LightsOff,
    LightsDim,
    Fireplace,
    Coffee,
    FocusMode,
    RelaxMode,
}

impl ActionType {
    pub fn api_endpoint(&self) -> &'static str {
        match self {
            Self::MovieMode => "/home/movie-mode/enter",
            Self::Goodnight => "/home/goodnight",
            Self::WelcomeHome => "/home/welcome-home",
            Self::Away => "/home/away",
            Self::LightsOn => "/home/lights/set",
            Self::LightsOff => "/home/lights/set",
            Self::LightsDim => "/home/lights/set",
            Self::Fireplace => "/home/fireplace/toggle",
            Self::Coffee => "/home/lights/set",
            Self::FocusMode => "/home/lights/set",
            Self::RelaxMode => "/home/lights/set",
        }
    }

    pub fn lights_level(&self) -> Option<i32> {
        match self {
            Self::LightsOn => Some(80),
            Self::LightsOff => Some(0),
            Self::LightsDim => Some(30),
            Self::Coffee => Some(100),
            Self::FocusMode => Some(60),
            Self::RelaxMode => Some(40),
            _ => None,
        }
    }
}

// ═══════════════════════════════════════════════════════════════
// CONTEXT STATE
// ═══════════════════════════════════════════════════════════════

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ContextState {
    pub time_context: TimeContext,
    pub location: LocationContext,
    pub activity: ActivityInference,
    pub home_status: Option<HomeStatus>,
    pub primary_action: SuggestedAction,
    pub secondary_actions: Vec<SuggestedAction>,
    pub safety_score: Option<f64>,
    pub is_connected: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct HomeStatus {
    pub movie_mode: bool,
    pub fireplace_on: bool,
    pub occupied_rooms: Vec<String>,
    pub temperature: Option<f64>,
}

impl Default for ContextState {
    fn default() -> Self {
        let time = TimeContext::current();
        Self {
            time_context: time,
            location: LocationContext::Home,
            activity: ActivityInference::Idle,
            home_status: None,
            primary_action: time.primary_action(),
            secondary_actions: time.secondary_actions(),
            safety_score: None,
            is_connected: false,
        }
    }
}

// ═══════════════════════════════════════════════════════════════
// CONTEXT ENGINE
// ═══════════════════════════════════════════════════════════════

pub struct ContextEngine {
    state: Arc<RwLock<ContextState>>,
}

impl Default for ContextEngine {
    fn default() -> Self {
        Self::new()
    }
}

impl ContextEngine {
    pub fn new() -> Self {
        Self {
            state: Arc::new(RwLock::new(ContextState::default())),
        }
    }

    /// Get current context state
    pub async fn get_state(&self) -> ContextState {
        self.state.read().await.clone()
    }

    /// Update context from real-time state
    pub async fn update_from_realtime(&self, rt_state: &crate::realtime::KagamiState) {
        let mut state = self.state.write().await;

        state.safety_score = rt_state.safety_score;
        state.is_connected = rt_state.connected;

        // Update time context
        state.time_context = TimeContext::current();

        // Infer activity from home status
        if let Some(ref home) = rt_state.home_status {
            state.home_status = Some(HomeStatus {
                movie_mode: home.movie_mode,
                fireplace_on: home.fireplace_on,
                occupied_rooms: home.occupied_rooms.clone(),
                temperature: home.temperature,
            });

            // Override activity if movie mode
            if home.movie_mode {
                state.activity = ActivityInference::Watching;
            }
        }

        // Recalculate suggested actions
        self.recalculate_actions(&mut state);

        debug!("Context updated: {:?}", state.time_context);
    }

    /// Update from API status
    pub async fn update_from_api(&self, home_status: Option<HomeStatus>, safety: Option<f64>, connected: bool) {
        let mut state = self.state.write().await;

        state.home_status = home_status;
        state.safety_score = safety;
        state.is_connected = connected;
        state.time_context = TimeContext::current();

        self.recalculate_actions(&mut state);
    }

    fn recalculate_actions(&self, state: &mut ContextState) {
        // Priority 1: Current mode overrides
        if let Some(ref home) = state.home_status {
            if home.movie_mode {
                // In movie mode - suggest exit
                state.primary_action = SuggestedAction {
                    id: "exit_movie".into(),
                    icon: "🎬".into(),
                    label: "Exit Movie".into(),
                    short_label: "Exit".into(),
                    action: ActionType::WelcomeHome,  // Exits movie mode
                    priority: 10,
                };
                state.secondary_actions = vec![
                    SuggestedAction {
                        id: "lights_dim".into(),
                        icon: "💡".into(),
                        label: "Lights Up".into(),
                        short_label: "Lights".into(),
                        action: ActionType::LightsDim,
                        priority: 5,
                    },
                ];
                return;
            }
        }

        // Priority 2: Location-based
        if state.location == LocationContext::Away {
            state.primary_action = SuggestedAction {
                id: "welcome".into(),
                icon: "🏠".into(),
                label: "Welcome Home".into(),
                short_label: "Home".into(),
                action: ActionType::WelcomeHome,
                priority: 10,
            };
            state.secondary_actions = vec![];
            return;
        }

        // Priority 3: Time-based
        state.primary_action = state.time_context.primary_action();
        state.secondary_actions = state.time_context.secondary_actions();
    }

    /// Get menu bar title based on context
    pub async fn get_tray_title(&self) -> String {
        let state = self.state.read().await;

        if !state.is_connected {
            return "⚠️".to_string();
        }

        if let Some(ref home) = state.home_status {
            if home.movie_mode {
                return "🎬".to_string();
            }
        }

        // Time-based icon
        match state.time_context {
            TimeContext::EarlyMorning | TimeContext::Morning => "☀️".to_string(),
            TimeContext::WorkDay => "鏡".to_string(),
            TimeContext::Evening | TimeContext::LateEvening => "🏠".to_string(),
            TimeContext::Night | TimeContext::LateNight => "🌙".to_string(),
        }
    }

    /// Get suggestions for quick entry
    pub async fn get_quick_suggestions(&self) -> Vec<SuggestedAction> {
        let state = self.state.read().await;

        let mut suggestions = vec![state.primary_action.clone()];
        suggestions.extend(state.secondary_actions.clone());

        // Add common actions based on home status
        if let Some(ref home) = state.home_status {
            if !home.fireplace_on && matches!(state.time_context, TimeContext::Evening | TimeContext::LateEvening | TimeContext::Night) {
                suggestions.push(SuggestedAction {
                    id: "fireplace".into(),
                    icon: "🔥".into(),
                    label: "Fireplace".into(),
                    short_label: "Fire".into(),
                    action: ActionType::Fireplace,
                    priority: 7,
                });
            }
        }

        // Sort by priority
        suggestions.sort_by(|a, b| b.priority.cmp(&a.priority));
        suggestions
    }
}

// ═══════════════════════════════════════════════════════════════
// GLOBAL INSTANCE
// ═══════════════════════════════════════════════════════════════

static CONTEXT: std::sync::OnceLock<ContextEngine> = std::sync::OnceLock::new();

pub fn get_context() -> &'static ContextEngine {
    CONTEXT.get_or_init(ContextEngine::new)
}

// ═══════════════════════════════════════════════════════════════
// TAURI COMMANDS
// ═══════════════════════════════════════════════════════════════

/// Sensory context for predictive suggestions (Claude Code style)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SensoryContext {
    pub time: TimeInfo,
    pub home: HomeInfo,
    pub weather: WeatherInfo,
    pub calendar: CalendarInfo,
    pub recent_actions: Vec<RecentAction>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TimeInfo {
    pub hour: u32,
    pub period: String,
    pub is_weekend: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HomeInfo {
    pub occupied_rooms: Vec<String>,
    pub active_lights: Vec<String>,
    pub active_scenes: Vec<String>,
    pub movie_mode: bool,
    pub fireplace_on: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WeatherInfo {
    pub condition: String,
    pub temperature: Option<f64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CalendarInfo {
    pub next_event: Option<String>,
    pub minutes_until: Option<i32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RecentAction {
    pub action_type: String,
    pub room: Option<String>,
    pub timestamp: i64,
}

impl SensoryContext {
    pub async fn gather() -> Self {
        let now = chrono::Local::now();
        let hour = now.hour();
        let day_of_week = now.weekday().num_days_from_sunday();

        let period = match hour {
            0..=5 => "night",
            6..=11 => "morning",
            12..=16 => "afternoon",
            17..=20 => "evening",
            _ => "night",
        };

        // Get home status from real-time state if connected
        let ctx = get_context().get_state().await;
        let home_status = ctx.home_status.unwrap_or_default();

        Self {
            time: TimeInfo {
                hour,
                period: period.to_string(),
                is_weekend: day_of_week == 0 || day_of_week == 6,
            },
            home: HomeInfo {
                occupied_rooms: home_status.occupied_rooms,
                active_lights: vec![], // TODO: populate from API
                active_scenes: if home_status.movie_mode {
                    vec!["movie".to_string()]
                } else {
                    vec![]
                },
                movie_mode: home_status.movie_mode,
                fireplace_on: home_status.fireplace_on,
            },
            weather: WeatherInfo {
                condition: "unknown".to_string(),
                temperature: home_status.temperature,
            },
            calendar: CalendarInfo {
                next_event: None,  // TODO: fetch from calendar
                minutes_until: None,
            },
            recent_actions: vec![], // TODO: populate from action log
        }
    }
}

/// Get sensory context for predictive suggestions
#[tauri::command]
pub async fn get_sensory_context() -> Result<SensoryContext, String> {
    Ok(SensoryContext::gather().await)
}

#[tauri::command]
pub async fn get_context_state() -> Result<ContextState, String> {
    Ok(get_context().get_state().await)
}

#[tauri::command]
pub async fn get_suggestions() -> Result<Vec<SuggestedAction>, String> {
    Ok(get_context().get_quick_suggestions().await)
}

#[tauri::command]
pub async fn execute_action(action_type: ActionType) -> Result<bool, String> {
    let api = crate::api_client::get_api();

    match action_type {
        ActionType::MovieMode => api.movie_mode().await.map(|_| true).map_err(|e| e.to_string()),
        ActionType::Goodnight => api.goodnight().await.map(|_| true).map_err(|e| e.to_string()),
        ActionType::WelcomeHome => api.welcome_home().await.map(|_| true).map_err(|e| e.to_string()),
        ActionType::Fireplace => api.fireplace(true).await.map(|_| true).map_err(|e| e.to_string()),
        ActionType::LightsOn | ActionType::Coffee => {
            api.set_lights(action_type.lights_level().unwrap_or(80), None)
                .await
                .map(|_| true)
                .map_err(|e| e.to_string())
        }
        ActionType::LightsOff => {
            api.set_lights(0, None).await.map(|_| true).map_err(|e| e.to_string())
        }
        ActionType::LightsDim | ActionType::RelaxMode => {
            api.set_lights(action_type.lights_level().unwrap_or(30), None)
                .await
                .map(|_| true)
                .map_err(|e| e.to_string())
        }
        ActionType::FocusMode => {
            api.set_lights(60, Some(vec!["Office".to_string()]))
                .await
                .map(|_| true)
                .map_err(|e| e.to_string())
        }
        ActionType::Away => {
            api.smart_home_action("away", None)
                .await
                .map(|_| true)
                .map_err(|e| e.to_string())
        }
    }
}

/*
 * 鏡
 *
 * Theory of Mind:
 *   I model Tim's intentions from context.
 *   Time + Location + Activity = Optimal Action
 *
 * The desktop is presence. Context is the interface.
 */
