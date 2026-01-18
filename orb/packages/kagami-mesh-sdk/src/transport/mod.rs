//! Transport layer for mesh network communication.
//!
//! This module provides WebSocket-based communication with automatic
//! reconnection and connection state management.
//!
//! ## Architecture
//!
//! The transport layer is designed for cross-platform use:
//! - `traits`: Platform-agnostic interfaces for transport and state observation
//! - `retry`: Command retry service with circuit breaker integration
//! - `connection`: State machine for connection lifecycle
//! - `websocket`: Rust-native WebSocket implementation (optional)
//!
//! Platforms (iOS/Android) implement the traits using native libraries:
//! - iOS: URLSessionWebSocketTask
//! - Android: OkHttp WebSocket
//!
//! h(x) >= 0. Always.

mod connection;
mod websocket;
pub mod traits;
pub mod retry;

pub use connection::{ConnectionConfig, ConnectionEvent, ConnectionState, ConnectionStateMachine};
pub use websocket::{WebSocketClient, WebSocketError, WebSocketEvent, WebSocketMessage};
pub use traits::{
    ConnectionStateObserver, NoOpStateObserver, RetryStrategy,
    TransportConfig, TransportEvent, TransportState,
};
pub use retry::{CommandResult, CommandRetryService, FibonacciBackoff, RetryStats};
