//! Unified API Module for Kagami
//!
//! This module provides cross-platform API types and client implementation
//! that eliminate ~3,900 lines of duplicated code across iOS, Android, and Desktop.
//!
//! # Architecture
//!
//! ```text
//! ┌─────────────────────────────────────────────────────────────────┐
//! │                    kagami-mesh-sdk                               │
//! │                                                                  │
//! │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
//! │  │   types.rs  │  │  client.rs  │  │   mod.rs    │              │
//! │  │             │  │             │  │  (this)     │              │
//! │  │  • Light    │  │ • ApiClient │  │             │              │
//! │  │  • Shade    │  │ • Config    │  │  Re-exports │              │
//! │  │  • Room     │  │ • State     │  │  all types  │              │
//! │  │  • etc.     │  │ • Helpers   │  │             │              │
//! │  └──────┬──────┘  └──────┬──────┘  └─────────────┘              │
//! │         │                │                                       │
//! │         └────────────────┼───────────────────────────────────────┤
//! │                          ▼                                       │
//! │                    UniFFI Bindings                               │
//! └──────────────────────────┬───────────────────────────────────────┘
//!                            │
//!            ┌───────────────┼───────────────┐
//!            ▼               ▼               ▼
//!     ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
//!     │   Swift     │ │   Kotlin    │ │ TypeScript  │
//!     │   (iOS/     │ │  (Android)  │ │  (Desktop)  │
//!     │  visionOS)  │ │             │ │             │
//!     └─────────────┘ └─────────────┘ └─────────────┘
//! ```
//!
//! # Platform Usage
//!
//! ## Swift (iOS/visionOS/watchOS/tvOS)
//!
//! ```swift
//! import KagamiMeshSDK
//!
//! // Create client
//! let client = KagamiApiClient(
//!     clientType: .ios,
//!     deviceName: UIDevice.current.name,
//!     appVersion: "1.0.0"
//! )
//!
//! // Build URLs
//! let healthUrl = client.healthUrl()
//!
//! // Parse responses
//! let health = try client.parseHealthResponse(jsonString)
//!
//! // Use shared types
//! let room: RoomModel = ...
//! let avgLight = room.avgLightLevel()
//! ```
//!
//! ## Kotlin (Android/WearOS)
//!
//! ```kotlin
//! import com.kagami.mesh.sdk.*
//!
//! // Create client
//! val client = KagamiApiClient(
//!     clientType = ClientType.ANDROID,
//!     deviceName = Build.MODEL,
//!     appVersion = "1.0.0"
//! )
//!
//! // Build URLs
//! val healthUrl = client.healthUrl()
//!
//! // Parse responses
//! val health = client.parseHealthResponse(jsonString)
//!
//! // Use shared types
//! val room: RoomModel = ...
//! val avgLight = room.avgLightLevel()
//! ```
//!
//! ## TypeScript (Desktop/Tauri)
//!
//! See `api.d.ts` for TypeScript type definitions that mirror these Rust types.
//!
//! # Binding Generation
//!
//! Swift and Kotlin bindings are generated automatically by UniFFI.
//! Run the binding generator:
//!
//! ```bash
//! # Generate Swift bindings
//! cargo run --features bindgen -- generate --library target/release/libkagami_mesh_sdk.dylib \
//!     --language swift --out-dir bindings/swift
//!
//! # Generate Kotlin bindings
//! cargo run --features bindgen -- generate --library target/release/libkagami_mesh_sdk.so \
//!     --language kotlin --out-dir bindings/kotlin
//! ```
//!
//! # Safety
//!
//! ```text
//! h(x) >= 0 always
//! ```

pub mod client;
pub mod types;

// Re-export all public types for convenience
pub use client::*;
pub use types::*;

/*
 * 鏡
 * Unified API: One source of truth for all platforms.
 * h(x) >= 0. Always.
 */
