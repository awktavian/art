//! 鏡 Kagami Hub Library — Voice-First Embedded Home Assistant
//!
//! This library crate exposes the hub's core functionality for testing
//! and potential embedding in other applications.
//!
//! # Modules
//!
//! - [`api_client`] - HTTP client for Kagami API
//! - [`config`] - Configuration loading and structures
//! - [`feedback`] - Spoken confirmations and audio cues
//! - [`household`] - Household member management with CRDT sync
//! - [`led_ring`] - LED ring controller with animation patterns
//! - [`realtime`] - WebSocket connection for real-time updates
//! - [`vm`] - Virtual machine management across hypervisors
//! - [`voice_pipeline`] - Voice command parsing and intent extraction
//! - [`wake_word`] - Wake word detection
//! - [`web_server`] - Configuration web server
//!
//! # Safety
//!
//! ```text
//! h(x) >= 0 always
//! ```
//!
//! All operations maintain the safety invariant.
//!
//! # Example
//!
//! ```rust,no_run
//! use kagami_hub::voice_pipeline::parse_command;
//! use kagami_hub::feedback::FeedbackGenerator;
//!
//! let command = parse_command("turn on the lights");
//! let confirmation = FeedbackGenerator::confirmation_for(&command.intent);
//! println!("{}", confirmation);
//! ```

pub mod agent_bridge;
pub mod animatronics;
pub mod api_client;
pub mod audio;
pub mod audio_stream;
pub mod byzantine;
pub mod config;
pub mod db;
pub mod desktop_client;
pub mod diagnostics;
pub mod feedback;
pub mod household;
pub mod led_ring;
pub mod mesh;
pub mod personality;
pub mod realtime;
pub mod speaker_id;
pub mod state_cache;
pub mod stt;
pub mod telemetry;
pub mod tts;
pub mod vm;
pub mod voice_controller;
pub mod voice_pipeline;
pub mod wake_word;
pub mod web_server;

#[cfg(feature = "world-model")]
pub mod world_model;

// Design tokens modules
pub mod design_tokens;
#[path = "design_tokens.generated.rs"]
pub mod design_tokens_generated;

// Re-export commonly used types at the crate root
pub use animatronics::{Animatronics, AnimatronicsConfig, Pose, SoundSource};
pub use api_client::KagamiAPI;
pub use config::HubConfig;
pub use desktop_client::{
    DesktopClient, DesktopClientManager, DesktopCapabilities, DesktopCommand,
    DesktopCommandResponse, DesktopClientEvent, DESKTOP_SERVICE_TYPE,
};
pub use household::{
    AccessibilityProfile, AuthorityLevel, CulturalPreferences, Household, HouseholdMember,
    HouseholdType, MemberRole, ScheduleProfile,
};
pub use personality::{
    AmbientBehavior, BehavioralResponse, BehavioralTrigger, EmotionalState, InteractionMemory,
    PersonalityController, PersonalityTraits, SeasonalMood, TimeAwareness,
};
pub use vm::{
    VMController, VMConfig, VMInfo, VMState, VMError, VMResult,
    vm_router, CommandResult, SnapshotInfo, OSType,
};
pub use voice_pipeline::{parse_command, CommandIntent, MusicAction, VoiceCommand};

/*
 * 鏡
 * η → s → μ → a → η′
 * h(x) ≥ 0. Always.
 */
