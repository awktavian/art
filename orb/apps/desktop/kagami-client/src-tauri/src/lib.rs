//! Kagami Desktop Client Library
//!
//! Exports public modules and re-exports key types for the Tauri application.
//!
//! Architecture:
//!   Commands -> MeshCommandRouter (primary) -> Hub via Mesh
//!            -> KagamiApi (fallback) -> HTTP Backend
//!
//! Migration Note (Jan 2026):
//!   Commands now route through MeshCommandRouter with Ed25519 signatures.

// Allow dead_code during development - modules will be wired up incrementally
#![allow(dead_code)]
#![allow(unused_imports)]
#![allow(unused_variables)]
//!   HTTP fallback is maintained for backward compatibility during migration.
//!
//! Colony: Nexus (e₄) — Coordination, integration
//!
//! η → s → μ → a → η′
//! h(x) ≥ 0. Always.

// Core modules
pub mod accessibility;
pub mod api_client;
pub mod app;
pub mod autostart;
pub mod cache;
pub mod commands;
pub mod desktop_control;
pub mod haptics;
pub mod health;
pub mod hotkeys;
pub mod hub_client;
pub mod keychain;
pub mod mesh_router;
pub mod realtime;
pub mod shared;
pub mod tray;
pub mod vision;

#[cfg(feature = "world-model")]
pub mod world_model;

// Re-export commonly used types
pub use api_client::{ApiError, ApiHealth, KagamiApi};
pub use cache::{ApiCache, CacheStats};
// Re-export from kagami-mesh-sdk for backward compatibility
pub use kagami_mesh_sdk::{CircuitBreaker, CircuitState, get_circuit_breaker};
pub use commands::error::CommandError;
pub use health::{HealthMetrics, HealthPlatform, SharedHealthState};
pub use hotkeys::{register_hotkeys, ActionRecord};
pub use keychain::{get_credential, set_credential, delete_credential, credential_exists, KeychainError};
pub use mesh_router::{MeshCommand, MeshCommandRouter, MeshCommandResponse, get_mesh_router, initialize_mesh_router};
pub use realtime::{RealtimeClient, KagamiState};
pub use tray::setup_tray;
pub use haptics::{DesktopHaptics, HapticPattern, play_haptic, play_haptic_with_intensity, init_haptics};
pub use autostart::{get_autostart, set_autostart, toggle_autostart_cmd, AutoStartState};
pub use hub_client::{
    HubClient, HubCommand, HubCommandResponse, HubClientEvent, DesktopCapabilities,
    DiscoveredHub, get_hub_client, discover_hubs, connect_to_hub, disconnect_from_hub,
    is_hub_connected, get_hub_peer_id,
};
