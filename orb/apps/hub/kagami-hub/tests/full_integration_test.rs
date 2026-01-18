//! Full Voice-to-Action Integration Tests — Crystal (e7) Colony
//!
//! Comprehensive integration tests that validate the complete voice pipeline:
//! STT -> NLU -> Execution -> Response
//!
//! ## Test Categories
//!
//! - **Pipeline Tests**: Full voice command flow
//! - **Mock Backend Tests**: Simulated home automation API
//! - **LED Ring Verification**: Visual feedback state machine
//! - **Error Handling**: Graceful degradation and recovery
//! - **Performance Tests**: Latency and throughput validation
//!
//! Colony: Crystal (e7) — Verification, validation
//!
//! h(x) >= 0. Always.

use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, AtomicU32, AtomicU64, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};

use tokio::sync::{mpsc, oneshot, RwLock};

use kagami_hub::circuit_breaker::{CircuitBreaker, CircuitBreakerConfig, CircuitState};
use kagami_hub::dialogue::{DialogueState, DialogueStateMachine};
use kagami_hub::nlu::{Intent, LightAction, MediaAction, NluEngine, ShadeAction};
use kagami_hub::telemetry;
use kagami_hub::voice_pipeline::{parse_command, CommandIntent, MusicAction};

// ============================================================================
// Mock Home Automation Backend
// ============================================================================

/// Mock home automation backend for integration testing
pub struct MockHomeBackend {
    /// Device states
    devices: Arc<RwLock<HashMap<String, DeviceState>>>,
    /// Scenes
    scenes: Arc<RwLock<HashMap<String, Vec<DeviceAction>>>>,
    /// Request log
    request_log: Arc<RwLock<Vec<BackendRequest>>>,
    /// Simulated latency (ms)
    latency_ms: AtomicU32,
    /// Failure mode
    fail_mode: AtomicBool,
    /// Failure probability (0-100)
    fail_probability: AtomicU32,
    /// Request counter
    request_count: AtomicU64,
}

/// Device state in the mock backend
#[derive(Debug, Clone)]
pub struct DeviceState {
    pub device_id: String,
    pub device_type: String,
    pub room: String,
    pub power: bool,
    pub brightness: Option<u8>,
    pub color: Option<String>,
    pub position: Option<u8>,
    pub temperature: Option<f32>,
    pub last_updated: Instant,
}

/// Action to perform on a device
#[derive(Debug, Clone)]
pub struct DeviceAction {
    pub device_id: String,
    pub action: String,
    pub value: Option<serde_json::Value>,
}

/// Logged backend request
#[derive(Debug, Clone)]
pub struct BackendRequest {
    pub timestamp: Instant,
    pub action: String,
    pub params: HashMap<String, String>,
    pub success: bool,
    pub latency_ms: u64,
}

impl MockHomeBackend {
    /// Create a new mock backend with standard test devices
    pub fn new() -> Self {
        let backend = Self {
            devices: Arc::new(RwLock::new(HashMap::new())),
            scenes: Arc::new(RwLock::new(HashMap::new())),
            request_log: Arc::new(RwLock::new(Vec::new())),
            latency_ms: AtomicU32::new(50),
            fail_mode: AtomicBool::new(false),
            fail_probability: AtomicU32::new(0),
            request_count: AtomicU64::new(0),
        };

        // Initialize with standard test devices
        tokio::runtime::Handle::current().block_on(async {
            backend.setup_test_devices().await;
        });

        backend
    }

    /// Setup standard test devices
    async fn setup_test_devices(&self) {
        let mut devices = self.devices.write().await;

        // Living room lights
        devices.insert(
            "light_lr_1".to_string(),
            DeviceState {
                device_id: "light_lr_1".to_string(),
                device_type: "light".to_string(),
                room: "Living Room".to_string(),
                power: false,
                brightness: Some(0),
                color: None,
                position: None,
                temperature: None,
                last_updated: Instant::now(),
            },
        );

        // Kitchen lights
        devices.insert(
            "light_kit_1".to_string(),
            DeviceState {
                device_id: "light_kit_1".to_string(),
                device_type: "light".to_string(),
                room: "Kitchen".to_string(),
                power: false,
                brightness: Some(0),
                color: None,
                position: None,
                temperature: None,
                last_updated: Instant::now(),
            },
        );

        // Bedroom lights
        devices.insert(
            "light_bed_1".to_string(),
            DeviceState {
                device_id: "light_bed_1".to_string(),
                device_type: "light".to_string(),
                room: "Primary Bedroom".to_string(),
                power: false,
                brightness: Some(0),
                color: None,
                position: None,
                temperature: None,
                last_updated: Instant::now(),
            },
        );

        // Living room shades
        devices.insert(
            "shade_lr_1".to_string(),
            DeviceState {
                device_id: "shade_lr_1".to_string(),
                device_type: "shade".to_string(),
                room: "Living Room".to_string(),
                power: false,
                brightness: None,
                color: None,
                position: Some(100), // Fully open
                temperature: None,
                last_updated: Instant::now(),
            },
        );

        // Front door lock
        devices.insert(
            "lock_front".to_string(),
            DeviceState {
                device_id: "lock_front".to_string(),
                device_type: "lock".to_string(),
                room: "Entry".to_string(),
                power: true, // Locked
                brightness: None,
                color: None,
                position: None,
                temperature: None,
                last_updated: Instant::now(),
            },
        );

        // Thermostat
        devices.insert(
            "thermostat_main".to_string(),
            DeviceState {
                device_id: "thermostat_main".to_string(),
                device_type: "thermostat".to_string(),
                room: "Living Room".to_string(),
                power: true,
                brightness: None,
                color: None,
                position: None,
                temperature: Some(72.0),
                last_updated: Instant::now(),
            },
        );

        // Fireplace
        devices.insert(
            "fireplace_lr".to_string(),
            DeviceState {
                device_id: "fireplace_lr".to_string(),
                device_type: "fireplace".to_string(),
                room: "Living Room".to_string(),
                power: false,
                brightness: None,
                color: None,
                position: None,
                temperature: None,
                last_updated: Instant::now(),
            },
        );

        drop(devices);

        // Setup scenes
        let mut scenes = self.scenes.write().await;

        scenes.insert(
            "movie_mode".to_string(),
            vec![
                DeviceAction {
                    device_id: "light_lr_1".to_string(),
                    action: "dim".to_string(),
                    value: Some(serde_json::json!(20)),
                },
                DeviceAction {
                    device_id: "shade_lr_1".to_string(),
                    action: "close".to_string(),
                    value: None,
                },
            ],
        );

        scenes.insert(
            "goodnight".to_string(),
            vec![
                DeviceAction {
                    device_id: "light_lr_1".to_string(),
                    action: "off".to_string(),
                    value: None,
                },
                DeviceAction {
                    device_id: "light_kit_1".to_string(),
                    action: "off".to_string(),
                    value: None,
                },
                DeviceAction {
                    device_id: "light_bed_1".to_string(),
                    action: "off".to_string(),
                    value: None,
                },
                DeviceAction {
                    device_id: "lock_front".to_string(),
                    action: "lock".to_string(),
                    value: None,
                },
            ],
        );

        scenes.insert(
            "welcome_home".to_string(),
            vec![
                DeviceAction {
                    device_id: "light_lr_1".to_string(),
                    action: "on".to_string(),
                    value: Some(serde_json::json!(75)),
                },
                DeviceAction {
                    device_id: "light_kit_1".to_string(),
                    action: "on".to_string(),
                    value: Some(serde_json::json!(50)),
                },
            ],
        );
    }

    /// Set simulated latency
    pub fn set_latency(&self, ms: u32) {
        self.latency_ms.store(ms, Ordering::SeqCst);
    }

    /// Enable/disable failure mode
    pub fn set_fail_mode(&self, fail: bool) {
        self.fail_mode.store(fail, Ordering::SeqCst);
    }

    /// Set failure probability (0-100)
    pub fn set_fail_probability(&self, probability: u32) {
        self.fail_probability
            .store(probability.min(100), Ordering::SeqCst);
    }

    /// Get request count
    pub fn request_count(&self) -> u64 {
        self.request_count.load(Ordering::SeqCst)
    }

    /// Get request log
    pub async fn get_request_log(&self) -> Vec<BackendRequest> {
        self.request_log.read().await.clone()
    }

    /// Clear request log
    pub async fn clear_request_log(&self) {
        self.request_log.write().await.clear();
    }

    /// Execute a command
    pub async fn execute(&self, intent: &CommandIntent) -> Result<CommandResult, BackendError> {
        let start = Instant::now();
        self.request_count.fetch_add(1, Ordering::SeqCst);

        // Simulate latency
        let latency = self.latency_ms.load(Ordering::SeqCst);
        if latency > 0 {
            tokio::time::sleep(Duration::from_millis(latency as u64)).await;
        }

        // Check failure mode
        if self.fail_mode.load(Ordering::SeqCst) {
            return Err(BackendError::SimulatedFailure);
        }

        // Check failure probability
        let fail_prob = self.fail_probability.load(Ordering::SeqCst);
        if fail_prob > 0 {
            let random = (start.elapsed().as_nanos() % 100) as u32;
            if random < fail_prob {
                return Err(BackendError::RandomFailure);
            }
        }

        let result = match intent {
            CommandIntent::Lights(level) => self.set_lights(*level as u8, None).await,
            CommandIntent::Scene(name) => self.activate_scene(name).await,
            CommandIntent::Fireplace(on) => self.set_fireplace(*on).await,
            CommandIntent::Shades(action) => self.set_shades(action).await,
            CommandIntent::Lock(locked) => self.set_lock(*locked).await,
            CommandIntent::Temperature(temp) => self.set_temperature(*temp as f32).await,
            CommandIntent::Music(action) => {
                // Music doesn't affect device state, just acknowledge
                Ok(CommandResult {
                    success: true,
                    message: format!("Music action: {:?}", action),
                    affected_devices: vec![],
                })
            }
            CommandIntent::TV(action) => Ok(CommandResult {
                success: true,
                message: format!("TV {}", action),
                affected_devices: vec!["tv_lr".to_string()],
            }),
            CommandIntent::Announce(msg) => Ok(CommandResult {
                success: true,
                message: format!("Announced: {}", msg),
                affected_devices: vec![],
            }),
            CommandIntent::Status => self.get_status().await,
            CommandIntent::Help => Ok(CommandResult {
                success: true,
                message: "I can control lights, scenes, shades, locks, thermostat, and more."
                    .to_string(),
                affected_devices: vec![],
            }),
            CommandIntent::Cancel => Ok(CommandResult {
                success: true,
                message: "Operation cancelled".to_string(),
                affected_devices: vec![],
            }),
            CommandIntent::Unknown => Err(BackendError::UnknownCommand),
        };

        let elapsed = start.elapsed();

        // Log request
        let mut log = self.request_log.write().await;
        log.push(BackendRequest {
            timestamp: start,
            action: format!("{:?}", intent),
            params: HashMap::new(),
            success: result.is_ok(),
            latency_ms: elapsed.as_millis() as u64,
        });

        result
    }

    /// Set lights in a room or all rooms
    async fn set_lights(
        &self,
        brightness: u8,
        room: Option<&str>,
    ) -> Result<CommandResult, BackendError> {
        let mut devices = self.devices.write().await;
        let mut affected = Vec::new();

        for device in devices.values_mut() {
            if device.device_type == "light" {
                if room.is_none() || room == Some(&device.room) {
                    device.power = brightness > 0;
                    device.brightness = Some(brightness);
                    device.last_updated = Instant::now();
                    affected.push(device.device_id.clone());
                }
            }
        }

        Ok(CommandResult {
            success: true,
            message: format!("Set {} light(s) to {}%", affected.len(), brightness),
            affected_devices: affected,
        })
    }

    /// Activate a scene
    async fn activate_scene(&self, scene_name: &str) -> Result<CommandResult, BackendError> {
        let scenes = self.scenes.read().await;
        let scene = scenes
            .get(scene_name)
            .ok_or(BackendError::SceneNotFound)?
            .clone();
        drop(scenes);

        let mut devices = self.devices.write().await;
        let mut affected = Vec::new();

        for action in &scene {
            if let Some(device) = devices.get_mut(&action.device_id) {
                match action.action.as_str() {
                    "on" => {
                        device.power = true;
                        if let Some(serde_json::Value::Number(n)) = &action.value {
                            device.brightness = n.as_u64().map(|v| v as u8);
                        } else {
                            device.brightness = Some(100);
                        }
                    }
                    "off" => {
                        device.power = false;
                        device.brightness = Some(0);
                    }
                    "dim" => {
                        device.power = true;
                        if let Some(serde_json::Value::Number(n)) = &action.value {
                            device.brightness = n.as_u64().map(|v| v as u8);
                        }
                    }
                    "close" => {
                        device.position = Some(0);
                    }
                    "open" => {
                        device.position = Some(100);
                    }
                    "lock" => {
                        device.power = true;
                    }
                    "unlock" => {
                        device.power = false;
                    }
                    _ => {}
                }
                device.last_updated = Instant::now();
                affected.push(device.device_id.clone());
            }
        }

        Ok(CommandResult {
            success: true,
            message: format!("Activated scene: {}", scene_name),
            affected_devices: affected,
        })
    }

    /// Set fireplace state
    async fn set_fireplace(&self, on: bool) -> Result<CommandResult, BackendError> {
        let mut devices = self.devices.write().await;

        if let Some(device) = devices.get_mut("fireplace_lr") {
            device.power = on;
            device.last_updated = Instant::now();
            Ok(CommandResult {
                success: true,
                message: format!("Fireplace turned {}", if on { "on" } else { "off" }),
                affected_devices: vec!["fireplace_lr".to_string()],
            })
        } else {
            Err(BackendError::DeviceNotFound)
        }
    }

    /// Set shades
    async fn set_shades(&self, action: &str) -> Result<CommandResult, BackendError> {
        let mut devices = self.devices.write().await;
        let mut affected = Vec::new();

        for device in devices.values_mut() {
            if device.device_type == "shade" {
                device.position = Some(if action == "open" { 100 } else { 0 });
                device.last_updated = Instant::now();
                affected.push(device.device_id.clone());
            }
        }

        Ok(CommandResult {
            success: true,
            message: format!("Shades {}", action),
            affected_devices: affected,
        })
    }

    /// Set lock state
    async fn set_lock(&self, locked: bool) -> Result<CommandResult, BackendError> {
        let mut devices = self.devices.write().await;
        let mut affected = Vec::new();

        for device in devices.values_mut() {
            if device.device_type == "lock" {
                device.power = locked;
                device.last_updated = Instant::now();
                affected.push(device.device_id.clone());
            }
        }

        Ok(CommandResult {
            success: true,
            message: format!("Doors {}", if locked { "locked" } else { "unlocked" }),
            affected_devices: affected,
        })
    }

    /// Set thermostat temperature
    async fn set_temperature(&self, temp: f32) -> Result<CommandResult, BackendError> {
        let mut devices = self.devices.write().await;

        if let Some(device) = devices.get_mut("thermostat_main") {
            device.temperature = Some(temp);
            device.last_updated = Instant::now();
            Ok(CommandResult {
                success: true,
                message: format!("Temperature set to {}F", temp),
                affected_devices: vec!["thermostat_main".to_string()],
            })
        } else {
            Err(BackendError::DeviceNotFound)
        }
    }

    /// Get system status
    async fn get_status(&self) -> Result<CommandResult, BackendError> {
        let devices = self.devices.read().await;

        let lights_on = devices
            .values()
            .filter(|d| d.device_type == "light" && d.power)
            .count();

        let locked = devices
            .values()
            .find(|d| d.device_type == "lock")
            .map(|d| d.power)
            .unwrap_or(false);

        let temp = devices
            .values()
            .find(|d| d.device_type == "thermostat")
            .and_then(|d| d.temperature)
            .unwrap_or(72.0);

        Ok(CommandResult {
            success: true,
            message: format!(
                "{} lights on. Doors {}. Temperature {}F.",
                lights_on,
                if locked { "locked" } else { "unlocked" },
                temp
            ),
            affected_devices: vec![],
        })
    }

    /// Get device state (for verification)
    pub async fn get_device(&self, device_id: &str) -> Option<DeviceState> {
        let devices = self.devices.read().await;
        devices.get(device_id).cloned()
    }
}

/// Command execution result
#[derive(Debug, Clone)]
pub struct CommandResult {
    pub success: bool,
    pub message: String,
    pub affected_devices: Vec<String>,
}

/// Backend error types
#[derive(Debug, Clone)]
pub enum BackendError {
    SimulatedFailure,
    RandomFailure,
    DeviceNotFound,
    SceneNotFound,
    UnknownCommand,
    Timeout,
}

impl std::fmt::Display for BackendError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            BackendError::SimulatedFailure => write!(f, "Simulated failure"),
            BackendError::RandomFailure => write!(f, "Random failure"),
            BackendError::DeviceNotFound => write!(f, "Device not found"),
            BackendError::SceneNotFound => write!(f, "Scene not found"),
            BackendError::UnknownCommand => write!(f, "Unknown command"),
            BackendError::Timeout => write!(f, "Request timeout"),
        }
    }
}

impl std::error::Error for BackendError {}

// ============================================================================
// Mock LED Ring
// ============================================================================

/// Mock LED ring for state verification
pub struct MockLedRing {
    /// Current state
    state: Arc<RwLock<LedState>>,
    /// State history
    history: Arc<RwLock<Vec<LedStateChange>>>,
}

/// LED ring state
#[derive(Debug, Clone, PartialEq)]
pub struct LedState {
    pub pattern: LedPattern,
    pub color: (u8, u8, u8),
    pub brightness: u8,
    pub active: bool,
}

/// LED pattern types
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum LedPattern {
    Off,
    Idle,
    Listening,
    Processing,
    Speaking,
    Success,
    Error,
    Weather,
    Music,
    Custom,
}

/// LED state change record
#[derive(Debug, Clone)]
pub struct LedStateChange {
    pub timestamp: Instant,
    pub from: LedState,
    pub to: LedState,
    pub trigger: String,
}

impl MockLedRing {
    /// Create a new mock LED ring
    pub fn new() -> Self {
        Self {
            state: Arc::new(RwLock::new(LedState {
                pattern: LedPattern::Off,
                color: (0, 0, 0),
                brightness: 0,
                active: false,
            })),
            history: Arc::new(RwLock::new(Vec::new())),
        }
    }

    /// Set LED state
    pub async fn set_state(
        &self,
        pattern: LedPattern,
        color: (u8, u8, u8),
        brightness: u8,
        trigger: &str,
    ) {
        let mut state = self.state.write().await;
        let old_state = state.clone();

        state.pattern = pattern;
        state.color = color;
        state.brightness = brightness;
        state.active = pattern != LedPattern::Off;

        let new_state = state.clone();
        drop(state);

        let mut history = self.history.write().await;
        history.push(LedStateChange {
            timestamp: Instant::now(),
            from: old_state,
            to: new_state,
            trigger: trigger.to_string(),
        });
    }

    /// Show idle state
    pub async fn show_idle(&self) {
        self.set_state(LedPattern::Idle, (0, 128, 255), 30, "idle")
            .await;
    }

    /// Show listening state
    pub async fn show_listening(&self) {
        self.set_state(LedPattern::Listening, (0, 255, 128), 80, "listening")
            .await;
    }

    /// Show processing state
    pub async fn show_processing(&self) {
        self.set_state(LedPattern::Processing, (128, 128, 255), 100, "processing")
            .await;
    }

    /// Show speaking state
    pub async fn show_speaking(&self) {
        self.set_state(LedPattern::Speaking, (255, 200, 0), 80, "speaking")
            .await;
    }

    /// Show success state
    pub async fn show_success(&self) {
        self.set_state(LedPattern::Success, (0, 255, 0), 100, "success")
            .await;
    }

    /// Show error state
    pub async fn show_error(&self) {
        self.set_state(LedPattern::Error, (255, 0, 0), 100, "error")
            .await;
    }

    /// Turn off LEDs
    pub async fn off(&self) {
        self.set_state(LedPattern::Off, (0, 0, 0), 0, "off").await;
    }

    /// Get current state
    pub async fn current_state(&self) -> LedState {
        self.state.read().await.clone()
    }

    /// Get state history
    pub async fn get_history(&self) -> Vec<LedStateChange> {
        self.history.read().await.clone()
    }

    /// Clear history
    pub async fn clear_history(&self) {
        self.history.write().await.clear();
    }

    /// Verify state transition sequence
    pub async fn verify_sequence(&self, expected: &[LedPattern]) -> bool {
        let history = self.history.read().await;
        let patterns: Vec<LedPattern> = history.iter().map(|h| h.to.pattern).collect();

        if patterns.len() < expected.len() {
            return false;
        }

        let start = patterns.len() - expected.len();
        &patterns[start..] == expected
    }
}

// ============================================================================
// Integration Test Harness
// ============================================================================

/// Complete test harness for integration testing
pub struct TestHarness {
    pub backend: Arc<MockHomeBackend>,
    pub led_ring: Arc<MockLedRing>,
    pub nlu_engine: NluEngine,
    pub circuit_breaker: CircuitBreaker,
    pub dialogue: DialogueStateMachine,
}

impl TestHarness {
    /// Create a new test harness
    pub fn new() -> Self {
        Self {
            backend: Arc::new(MockHomeBackend::new()),
            led_ring: Arc::new(MockLedRing::new()),
            nlu_engine: NluEngine::new(),
            circuit_breaker: CircuitBreaker::with_config(
                "test",
                CircuitBreakerConfig {
                    failure_threshold: 3,
                    reset_timeout: Duration::from_millis(100),
                    success_threshold: 1,
                    half_open_max_requests: 1,
                },
            ),
            dialogue: DialogueStateMachine::new(),
        }
    }

    /// Execute a voice command through the full pipeline
    pub async fn execute_voice_command(&mut self, transcript: &str) -> PipelineResult {
        let start = Instant::now();

        // 1. Show listening state
        self.led_ring.show_listening().await;

        // 2. NLU parsing
        let nlu_start = Instant::now();
        let nlu_result = self.nlu_engine.parse(transcript);
        let nlu_duration = nlu_start.elapsed();

        // 3. Show processing state
        self.led_ring.show_processing().await;

        // 4. Convert NLU intent to CommandIntent
        let command_intent = self.convert_nlu_to_command(&nlu_result.intent);

        // 5. Update dialogue state
        self.dialogue.start_listening();
        let resolved = self
            .dialogue
            .process_input(transcript, command_intent.clone());

        // 6. Check circuit breaker
        if !self.circuit_breaker.allow_request() {
            self.led_ring.show_error().await;
            return PipelineResult {
                success: false,
                transcript: transcript.to_string(),
                intent: command_intent,
                backend_result: None,
                error: Some("Circuit breaker open".to_string()),
                nlu_duration,
                execution_duration: Duration::ZERO,
                total_duration: start.elapsed(),
            };
        }

        // 7. Execute against backend
        let exec_start = Instant::now();
        let backend_result = self.backend.execute(&resolved).await;
        let exec_duration = exec_start.elapsed();

        // 8. Record circuit breaker result
        match &backend_result {
            Ok(_) => {
                self.circuit_breaker.record_success();
                self.dialogue.record_result(
                    true,
                    backend_result.as_ref().ok().map(|r| r.message.clone()),
                );
                self.led_ring.show_success().await;
            }
            Err(_) => {
                self.circuit_breaker.record_failure();
                self.dialogue.record_result(false, None);
                self.led_ring.show_error().await;
            }
        }

        // 9. Return to idle
        tokio::time::sleep(Duration::from_millis(100)).await;
        self.led_ring.show_idle().await;

        let (ok_result, err_result) = match backend_result {
            Ok(res) => (Some(res), None),
            Err(e) => (None, Some(e.to_string())),
        };

        PipelineResult {
            success: ok_result.is_some(),
            transcript: transcript.to_string(),
            intent: resolved,
            backend_result: ok_result,
            error: err_result,
            nlu_duration,
            execution_duration: exec_duration,
            total_duration: start.elapsed(),
        }
    }

    /// Convert NLU Intent to CommandIntent
    fn convert_nlu_to_command(&self, intent: &Intent) -> CommandIntent {
        match intent {
            Intent::Lights {
                action, brightness, ..
            } => {
                let level = match action {
                    LightAction::TurnOn => brightness.unwrap_or(100) as i32,
                    LightAction::TurnOff => 0,
                    LightAction::SetBrightness => brightness.unwrap_or(50) as i32,
                    LightAction::Dim => brightness.unwrap_or(25) as i32,
                    LightAction::Brighten => brightness.unwrap_or(75) as i32,
                    _ => brightness.unwrap_or(100) as i32,
                };
                CommandIntent::Lights(level)
            }
            Intent::Scene { name, .. } => {
                let scene_name = name.to_lowercase().replace(" ", "_");
                CommandIntent::Scene(scene_name)
            }
            Intent::Media { action, .. } => {
                let music_action = match action {
                    MediaAction::Play => MusicAction::Play(None),
                    MediaAction::Pause => MusicAction::Pause,
                    MediaAction::Stop => MusicAction::Pause,
                    MediaAction::Next => MusicAction::Skip,
                    MediaAction::VolumeUp => MusicAction::VolumeUp,
                    MediaAction::VolumeDown => MusicAction::VolumeDown,
                    _ => MusicAction::Play(None),
                };
                CommandIntent::Music(music_action)
            }
            Intent::Shades { action, .. } => {
                let shade_action = match action {
                    ShadeAction::Open => "open",
                    ShadeAction::Close => "close",
                    _ => "open",
                };
                CommandIntent::Shades(shade_action.to_string())
            }
            Intent::Locks { action, .. } => {
                let locked = matches!(action, kagami_hub::nlu::LockAction::Lock);
                CommandIntent::Lock(locked)
            }
            Intent::Climate { temperature, .. } => {
                CommandIntent::Temperature(temperature.unwrap_or(72.0) as i32)
            }
            Intent::System { action } => match action {
                kagami_hub::nlu::SystemAction::Status => CommandIntent::Status,
                kagami_hub::nlu::SystemAction::Help => CommandIntent::Help,
                _ => CommandIntent::Unknown,
            },
            Intent::Unknown { .. } => CommandIntent::Unknown,
            _ => CommandIntent::Unknown,
        }
    }
}

/// Pipeline execution result
#[derive(Debug)]
pub struct PipelineResult {
    pub success: bool,
    pub transcript: String,
    pub intent: CommandIntent,
    pub backend_result: Option<CommandResult>,
    pub error: Option<String>,
    pub nlu_duration: Duration,
    pub execution_duration: Duration,
    pub total_duration: Duration,
}

// ============================================================================
// Integration Tests
// ============================================================================

#[tokio::test]
async fn test_full_pipeline_lights_on() {
    let mut harness = TestHarness::new();

    let result = harness.execute_voice_command("turn on the lights").await;

    assert!(result.success);
    assert!(matches!(result.intent, CommandIntent::Lights(100)));

    // Verify device state changed
    let device = harness.backend.get_device("light_lr_1").await.unwrap();
    assert!(device.power);
    assert_eq!(device.brightness, Some(100));
}

#[tokio::test]
async fn test_full_pipeline_lights_off() {
    let mut harness = TestHarness::new();

    // First turn on
    harness.execute_voice_command("turn on the lights").await;

    // Then turn off
    let result = harness.execute_voice_command("turn off the lights").await;

    assert!(result.success);
    assert!(matches!(result.intent, CommandIntent::Lights(0)));

    let device = harness.backend.get_device("light_lr_1").await.unwrap();
    assert!(!device.power);
}

#[tokio::test]
async fn test_full_pipeline_scene_activation() {
    let mut harness = TestHarness::new();

    let result = harness.execute_voice_command("activate movie mode").await;

    assert!(result.success);
    assert!(matches!(result.intent, CommandIntent::Scene(ref s) if s == "movie_mode"));

    // Verify scene effects
    let light = harness.backend.get_device("light_lr_1").await.unwrap();
    assert_eq!(light.brightness, Some(20));

    let shade = harness.backend.get_device("shade_lr_1").await.unwrap();
    assert_eq!(shade.position, Some(0)); // Closed
}

#[tokio::test]
async fn test_full_pipeline_goodnight_scene() {
    let mut harness = TestHarness::new();

    // First turn on some lights
    harness.execute_voice_command("turn on the lights").await;

    // Then goodnight
    let result = harness.execute_voice_command("goodnight").await;

    assert!(result.success);

    // Verify all lights off
    let light = harness.backend.get_device("light_lr_1").await.unwrap();
    assert!(!light.power);

    // Verify door locked
    let lock = harness.backend.get_device("lock_front").await.unwrap();
    assert!(lock.power); // Locked
}

#[tokio::test]
async fn test_full_pipeline_shades() {
    let mut harness = TestHarness::new();

    let result = harness.execute_voice_command("close the shades").await;

    assert!(result.success);
    assert!(matches!(result.intent, CommandIntent::Shades(ref a) if a == "close"));

    let shade = harness.backend.get_device("shade_lr_1").await.unwrap();
    assert_eq!(shade.position, Some(0));
}

#[tokio::test]
async fn test_full_pipeline_lock() {
    let mut harness = TestHarness::new();

    let result = harness.execute_voice_command("unlock the front door").await;

    assert!(result.success);
    assert!(matches!(result.intent, CommandIntent::Lock(false)));

    let lock = harness.backend.get_device("lock_front").await.unwrap();
    assert!(!lock.power); // Unlocked
}

#[tokio::test]
async fn test_full_pipeline_thermostat() {
    let mut harness = TestHarness::new();

    let result = harness
        .execute_voice_command("set the temperature to 68 degrees")
        .await;

    assert!(result.success);
    assert!(matches!(result.intent, CommandIntent::Temperature(68)));

    let thermostat = harness.backend.get_device("thermostat_main").await.unwrap();
    assert_eq!(thermostat.temperature, Some(68.0));
}

#[tokio::test]
async fn test_full_pipeline_status() {
    let mut harness = TestHarness::new();

    let result = harness.execute_voice_command("what's the status").await;

    assert!(result.success);
    assert!(matches!(result.intent, CommandIntent::Status));
    assert!(result.backend_result.is_some());
}

#[tokio::test]
async fn test_led_ring_state_sequence() {
    let mut harness = TestHarness::new();

    harness.led_ring.clear_history().await;

    harness.execute_voice_command("turn on the lights").await;

    // Verify LED sequence: listening -> processing -> success -> idle
    let verified = harness
        .led_ring
        .verify_sequence(&[
            LedPattern::Listening,
            LedPattern::Processing,
            LedPattern::Success,
            LedPattern::Idle,
        ])
        .await;

    assert!(
        verified,
        "LED sequence should be: listening -> processing -> success -> idle"
    );
}

#[tokio::test]
async fn test_led_ring_error_state() {
    let mut harness = TestHarness::new();

    // Enable failure mode
    harness.backend.set_fail_mode(true);
    harness.led_ring.clear_history().await;

    let result = harness.execute_voice_command("turn on the lights").await;

    assert!(!result.success);

    // Verify error state was shown
    let history = harness.led_ring.get_history().await;
    assert!(history.iter().any(|h| h.to.pattern == LedPattern::Error));
}

#[tokio::test]
async fn test_circuit_breaker_opens_on_failures() {
    let mut harness = TestHarness::new();

    // Enable failure mode
    harness.backend.set_fail_mode(true);

    // Execute commands until circuit opens
    for _ in 0..5 {
        let _ = harness.execute_voice_command("turn on the lights").await;
    }

    // Circuit should be open now
    assert!(!harness.circuit_breaker.allow_request());

    // Next command should fail immediately due to circuit breaker
    let result = harness.execute_voice_command("turn on the lights").await;
    assert!(!result.success);
    assert!(result
        .error
        .as_ref()
        .map(|e| e.contains("Circuit breaker"))
        .unwrap_or(false));
}

#[tokio::test]
async fn test_unknown_command_handling() {
    let mut harness = TestHarness::new();

    let result = harness
        .execute_voice_command("flibbertigibbet wobbledy woo")
        .await;

    assert!(!result.success);
    assert!(matches!(result.intent, CommandIntent::Unknown));
}

#[tokio::test]
async fn test_dialogue_state_machine_flow() {
    let mut harness = TestHarness::new();

    // Initial state
    assert_eq!(harness.dialogue.state(), DialogueState::Idle);

    // Execute command
    let _ = harness.execute_voice_command("turn on the lights").await;

    // Should be awaiting follow-up after successful command
    assert_eq!(harness.dialogue.state(), DialogueState::AwaitingFollowUp);
}

#[tokio::test]
async fn test_multiple_sequential_commands() {
    let mut harness = TestHarness::new();

    // Execute multiple commands
    let commands = [
        "turn on the lights",
        "close the shades",
        "set the temperature to 70 degrees",
        "lock the door",
    ];

    for cmd in commands {
        let result = harness.execute_voice_command(cmd).await;
        assert!(result.success, "Command '{}' failed", cmd);
    }

    // Verify final states
    let light = harness.backend.get_device("light_lr_1").await.unwrap();
    assert!(light.power);

    let shade = harness.backend.get_device("shade_lr_1").await.unwrap();
    assert_eq!(shade.position, Some(0));

    let thermostat = harness.backend.get_device("thermostat_main").await.unwrap();
    assert_eq!(thermostat.temperature, Some(70.0));

    let lock = harness.backend.get_device("lock_front").await.unwrap();
    assert!(lock.power);
}

#[tokio::test]
async fn test_latency_measurement() {
    let mut harness = TestHarness::new();

    // Set known latency
    harness.backend.set_latency(100);

    let result = harness.execute_voice_command("turn on the lights").await;

    assert!(result.success);
    assert!(result.execution_duration >= Duration::from_millis(100));
    assert!(result.total_duration >= Duration::from_millis(100));
}

#[tokio::test]
async fn test_request_logging() {
    let mut harness = TestHarness::new();

    harness.backend.clear_request_log().await;

    harness.execute_voice_command("turn on the lights").await;
    harness.execute_voice_command("turn off the lights").await;

    let log = harness.backend.get_request_log().await;
    assert_eq!(log.len(), 2);
    assert!(log[0].success);
    assert!(log[1].success);
}

#[tokio::test]
async fn test_nlu_confidence_threshold() {
    let harness = TestHarness::new();

    // Clear command should have high confidence
    let result = harness.nlu_engine.parse("turn on the living room lights");
    assert!(result.confidence >= 0.8);

    // Ambiguous command should have lower confidence
    let result = harness.nlu_engine.parse("maybe do something with stuff");
    assert!(result.confidence < 0.8);
}

#[tokio::test]
async fn test_performance_under_load() {
    let mut harness = TestHarness::new();

    // Execute many commands quickly
    let start = Instant::now();
    let num_commands = 50;

    for i in 0..num_commands {
        let cmd = if i % 2 == 0 {
            "turn on the lights"
        } else {
            "turn off the lights"
        };
        let result = harness.execute_voice_command(cmd).await;
        assert!(result.success);
    }

    let elapsed = start.elapsed();
    let avg_ms = elapsed.as_millis() as f64 / num_commands as f64;

    // Should average under 200ms per command (with 50ms simulated latency)
    assert!(
        avg_ms < 200.0,
        "Average command time {}ms exceeds 200ms threshold",
        avg_ms
    );

    assert_eq!(harness.backend.request_count(), num_commands);
}

#[tokio::test]
async fn test_concurrent_command_handling() {
    let harness = Arc::new(tokio::sync::Mutex::new(TestHarness::new()));

    let mut handles = Vec::new();

    for i in 0..10 {
        let harness = harness.clone();
        let cmd = if i % 2 == 0 {
            "turn on the lights"
        } else {
            "close the shades"
        };

        handles.push(tokio::spawn(async move {
            let mut h = harness.lock().await;
            h.execute_voice_command(cmd).await
        }));
    }

    let results: Vec<Result<PipelineResult, _>> = futures::future::join_all(handles).await;

    for result in results {
        let pipeline_result: PipelineResult = result.unwrap();
        assert!(pipeline_result.success);
    }
}

/*
 * Crystal verifies. Tests ensure correctness.
 * Mock backends simulate real systems.
 * LED states confirm user feedback.
 *
 * h(x) >= 0. Always.
 */
