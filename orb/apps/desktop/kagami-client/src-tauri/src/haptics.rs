//! Desktop Haptics — Gamepad rumble and visual feedback fallback
//!
//! Colony: 💎 Crystal (e7) — Verification & Polish
//!
//! Provides haptic-like feedback on desktop through:
//! - Gamepad rumble (if controller connected via gilrs)
//! - Visual pulse feedback via Tauri events (fallback)
//! - Screen flash for urgent notifications
//!
//! Pattern parity with iOS KagamiHaptics.swift and Android KagamiHaptics.kt
//!
//! h(x) >= 0. Always.

use serde::{Deserialize, Serialize};
use std::sync::Arc;
use std::time::Duration;
use tauri::{AppHandle, Emitter, Manager, Runtime};
use tokio::sync::RwLock;

// ============================================================================
// Haptic Pattern Types
// ============================================================================

/// Semantic haptic feedback types matching iOS/Android
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum HapticPattern {
    // Core patterns
    Success,
    Error,
    Warning,
    Selection,

    // Impact patterns
    LightImpact,
    MediumImpact,
    HeavyImpact,
    SoftImpact,
    RigidImpact,

    // Discovery effects (Prismorphism)
    DiscoveryGlance,
    DiscoveryInterest,
    DiscoveryFocus,
    DiscoveryEngage,

    // Compound patterns
    DoubleTap,
    LongPress,
    Tick,

    // Scene-specific
    SceneActivated,
    LightsChanged,
    LockEngaged,

    // Safety
    SafetyViolation,
}

/// Visual feedback event sent to frontend
#[derive(Debug, Clone, Serialize)]
pub struct VisualFeedbackEvent {
    /// The pattern being played
    pub pattern: HapticPattern,
    /// Intensity (0.0 - 1.0)
    pub intensity: f32,
    /// Duration in milliseconds
    pub duration_ms: u32,
    /// CSS animation class to apply
    pub animation_class: String,
    /// Optional screen flash for urgent feedback
    pub screen_flash: bool,
}

/// Gamepad rumble parameters
#[derive(Debug, Clone, Copy)]
pub struct RumbleParams {
    /// Strong motor intensity (0.0 - 1.0)
    pub strong: f32,
    /// Weak motor intensity (0.0 - 1.0)
    pub weak: f32,
    /// Duration in milliseconds
    pub duration_ms: u64,
}

// ============================================================================
// Haptics Service
// ============================================================================

/// Desktop haptics service with gamepad rumble and visual fallback
pub struct DesktopHaptics {
    /// Whether gamepad is available
    gamepad_available: Arc<RwLock<bool>>,
    /// Current haptic settings
    enabled: Arc<RwLock<bool>>,
}

impl Default for DesktopHaptics {
    fn default() -> Self {
        Self::new()
    }
}

impl DesktopHaptics {
    /// Create a new haptics service
    pub fn new() -> Self {
        Self {
            gamepad_available: Arc::new(RwLock::new(false)),
            enabled: Arc::new(RwLock::new(true)),
        }
    }

    /// Initialize the haptics service
    pub async fn initialize(&self) {
        // Check for gamepad support
        // Note: gilrs crate would be used here for actual gamepad support
        // For now, we'll rely on visual feedback
        let mut available = self.gamepad_available.write().await;
        *available = Self::check_gamepad_support();

        if *available {
            tracing::info!("🎮 Gamepad haptics available");
        } else {
            tracing::info!("🖥️ Using visual feedback (no gamepad)");
        }
    }

    /// Check if gamepad is available (stub - would use gilrs)
    fn check_gamepad_support() -> bool {
        // In a full implementation, use gilrs crate:
        // gilrs::Gilrs::new().ok().map(|g| g.gamepads().count() > 0).unwrap_or(false)
        false
    }

    /// Play a haptic pattern
    pub async fn play<R: Runtime>(&self, app: &AppHandle<R>, pattern: HapticPattern) {
        let enabled = *self.enabled.read().await;
        if !enabled {
            return;
        }

        let gamepad_available = *self.gamepad_available.read().await;

        if gamepad_available {
            self.play_gamepad_rumble(pattern).await;
        }

        // Always send visual feedback (frontend decides whether to use it)
        self.send_visual_feedback(app, pattern, 1.0).await;
    }

    /// Play a haptic pattern with custom intensity
    pub async fn play_with_intensity<R: Runtime>(
        &self,
        app: &AppHandle<R>,
        pattern: HapticPattern,
        intensity: f32,
    ) {
        let enabled = *self.enabled.read().await;
        if !enabled {
            return;
        }

        let clamped = intensity.clamp(0.0, 1.0);

        let gamepad_available = *self.gamepad_available.read().await;
        if gamepad_available {
            self.play_gamepad_rumble_with_intensity(pattern, clamped).await;
        }

        self.send_visual_feedback(app, pattern, clamped).await;
    }

    /// Enable or disable haptics
    pub async fn set_enabled(&self, enabled: bool) {
        let mut e = self.enabled.write().await;
        *e = enabled;
    }

    /// Check if haptics are enabled
    pub async fn is_enabled(&self) -> bool {
        *self.enabled.read().await
    }

    // ========================================================================
    // Gamepad Rumble
    // ========================================================================

    async fn play_gamepad_rumble(&self, pattern: HapticPattern) {
        let params = Self::pattern_to_rumble(pattern);
        self.execute_rumble(params).await;
    }

    async fn play_gamepad_rumble_with_intensity(&self, pattern: HapticPattern, intensity: f32) {
        let mut params = Self::pattern_to_rumble(pattern);
        params.strong *= intensity;
        params.weak *= intensity;
        self.execute_rumble(params).await;
    }

    async fn execute_rumble(&self, params: RumbleParams) {
        // In a full implementation with gilrs:
        // if let Some(gamepad) = self.get_connected_gamepad() {
        //     gamepad.set_rumble(params.weak as u16 * 65535, params.strong as u16 * 65535, params.duration_ms);
        // }
        tracing::debug!(
            "Rumble: strong={:.2}, weak={:.2}, duration={}ms",
            params.strong,
            params.weak,
            params.duration_ms
        );
    }

    /// Convert pattern to gamepad rumble parameters
    fn pattern_to_rumble(pattern: HapticPattern) -> RumbleParams {
        match pattern {
            HapticPattern::Success => RumbleParams {
                strong: 0.5,
                weak: 0.3,
                duration_ms: 100,
            },
            HapticPattern::Error => RumbleParams {
                strong: 0.8,
                weak: 0.6,
                duration_ms: 200,
            },
            HapticPattern::Warning => RumbleParams {
                strong: 0.7,
                weak: 0.4,
                duration_ms: 150,
            },
            HapticPattern::Selection => RumbleParams {
                strong: 0.2,
                weak: 0.1,
                duration_ms: 30,
            },
            HapticPattern::LightImpact => RumbleParams {
                strong: 0.3,
                weak: 0.2,
                duration_ms: 50,
            },
            HapticPattern::MediumImpact => RumbleParams {
                strong: 0.5,
                weak: 0.3,
                duration_ms: 70,
            },
            HapticPattern::HeavyImpact => RumbleParams {
                strong: 0.8,
                weak: 0.5,
                duration_ms: 100,
            },
            HapticPattern::SoftImpact => RumbleParams {
                strong: 0.2,
                weak: 0.3,
                duration_ms: 80,
            },
            HapticPattern::RigidImpact => RumbleParams {
                strong: 0.7,
                weak: 0.2,
                duration_ms: 40,
            },
            HapticPattern::DiscoveryGlance => RumbleParams {
                strong: 0.15,
                weak: 0.1,
                duration_ms: 30,
            },
            HapticPattern::DiscoveryInterest => RumbleParams {
                strong: 0.25,
                weak: 0.15,
                duration_ms: 50,
            },
            HapticPattern::DiscoveryFocus => RumbleParams {
                strong: 0.4,
                weak: 0.25,
                duration_ms: 70,
            },
            HapticPattern::DiscoveryEngage => RumbleParams {
                strong: 0.5,
                weak: 0.3,
                duration_ms: 80,
            },
            HapticPattern::DoubleTap => RumbleParams {
                strong: 0.4,
                weak: 0.2,
                duration_ms: 40,
            },
            HapticPattern::LongPress => RumbleParams {
                strong: 0.3,
                weak: 0.2,
                duration_ms: 200,
            },
            HapticPattern::Tick => RumbleParams {
                strong: 0.1,
                weak: 0.1,
                duration_ms: 20,
            },
            HapticPattern::SceneActivated => RumbleParams {
                strong: 0.6,
                weak: 0.4,
                duration_ms: 120,
            },
            HapticPattern::LightsChanged => RumbleParams {
                strong: 0.3,
                weak: 0.2,
                duration_ms: 80,
            },
            HapticPattern::LockEngaged => RumbleParams {
                strong: 0.7,
                weak: 0.3,
                duration_ms: 100,
            },
            HapticPattern::SafetyViolation => RumbleParams {
                strong: 1.0,
                weak: 0.8,
                duration_ms: 400,
            },
        }
    }

    // ========================================================================
    // Visual Feedback
    // ========================================================================

    async fn send_visual_feedback<R: Runtime>(
        &self,
        app: &AppHandle<R>,
        pattern: HapticPattern,
        intensity: f32,
    ) {
        let (animation_class, duration_ms, screen_flash) = Self::pattern_to_visual(pattern);

        let event = VisualFeedbackEvent {
            pattern,
            intensity,
            duration_ms,
            animation_class,
            screen_flash,
        };

        if let Err(e) = app.emit("haptic-feedback", &event) {
            tracing::warn!("Failed to emit haptic feedback event: {}", e);
        }
    }

    /// Convert pattern to visual feedback parameters
    fn pattern_to_visual(pattern: HapticPattern) -> (String, u32, bool) {
        match pattern {
            HapticPattern::Success => ("pulse-success".into(), 300, false),
            HapticPattern::Error => ("shake-error".into(), 400, true),
            HapticPattern::Warning => ("pulse-warning".into(), 350, false),
            HapticPattern::Selection => ("pulse-subtle".into(), 150, false),
            HapticPattern::LightImpact => ("pulse-light".into(), 100, false),
            HapticPattern::MediumImpact => ("pulse-medium".into(), 150, false),
            HapticPattern::HeavyImpact => ("pulse-heavy".into(), 200, false),
            HapticPattern::SoftImpact => ("pulse-soft".into(), 120, false),
            HapticPattern::RigidImpact => ("pulse-rigid".into(), 80, false),
            HapticPattern::DiscoveryGlance => ("glow-subtle".into(), 200, false),
            HapticPattern::DiscoveryInterest => ("glow-interest".into(), 300, false),
            HapticPattern::DiscoveryFocus => ("glow-focus".into(), 400, false),
            HapticPattern::DiscoveryEngage => ("glow-engage".into(), 250, false),
            HapticPattern::DoubleTap => ("pulse-double".into(), 200, false),
            HapticPattern::LongPress => ("pulse-building".into(), 500, false),
            HapticPattern::Tick => ("tick".into(), 50, false),
            HapticPattern::SceneActivated => ("pulse-scene".into(), 400, false),
            HapticPattern::LightsChanged => ("glow-lights".into(), 300, false),
            HapticPattern::LockEngaged => ("pulse-lock".into(), 250, false),
            HapticPattern::SafetyViolation => ("shake-safety".into(), 600, true),
        }
    }
}

// ============================================================================
// Tauri Commands
// ============================================================================

/// Tauri command to play haptic feedback
#[tauri::command]
pub async fn play_haptic<R: Runtime>(
    app: AppHandle<R>,
    pattern: HapticPattern,
) -> Result<(), String> {
    let haptics = app
        .try_state::<Arc<DesktopHaptics>>()
        .ok_or("Haptics not initialized")?;

    haptics.play(&app, pattern).await;
    Ok(())
}

/// Tauri command to play haptic with intensity
#[tauri::command]
pub async fn play_haptic_with_intensity<R: Runtime>(
    app: AppHandle<R>,
    pattern: HapticPattern,
    intensity: f32,
) -> Result<(), String> {
    let haptics = app
        .try_state::<Arc<DesktopHaptics>>()
        .ok_or("Haptics not initialized")?;

    haptics.play_with_intensity(&app, pattern, intensity).await;
    Ok(())
}

/// Tauri command to enable/disable haptics
#[tauri::command]
pub async fn set_haptics_enabled<R: Runtime>(
    app: AppHandle<R>,
    enabled: bool,
) -> Result<(), String> {
    let haptics = app
        .try_state::<Arc<DesktopHaptics>>()
        .ok_or("Haptics not initialized")?;

    haptics.set_enabled(enabled).await;
    Ok(())
}

// ============================================================================
// Plugin Setup
// ============================================================================

/// Initialize desktop haptics and register with app state
pub fn init_haptics<R: Runtime>(app: &AppHandle<R>) {
    let haptics = Arc::new(DesktopHaptics::new());
    let haptics_clone = haptics.clone();

    // Initialize in background
    tauri::async_runtime::spawn(async move {
        haptics_clone.initialize().await;
    });

    app.manage(haptics);
}

/*
 * Mirror 鏡
 * Visual feedback provides accessibility when haptics unavailable.
 * Consistent patterns build user intuition across platforms.
 * h(x) >= 0. Always.
 */
