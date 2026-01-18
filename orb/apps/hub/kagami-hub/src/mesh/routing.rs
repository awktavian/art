//! Cross-Hub Command Routing
//!
//! Routes commands between hubs based on room/zone ownership.
//! Enables "turn on lights in kitchen" from office hub to kitchen hub.
//!
//! Flow:
//! 1. Hub receives voice command
//! 2. Extract target room/zone
//! 3. Determine which hub owns that room
//! 4. Route to appropriate hub (or execute locally)
//! 5. Return acknowledgment
//!
//! Colony: Nexus (e₄) — Command distribution
//!
//! η → s → μ → a → η′
//! h(x) ≥ 0. Always.

use std::collections::HashMap;
use std::sync::Arc;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tokio::sync::{broadcast, RwLock};
use tracing::{debug, info, warn, error};
use serde::{Deserialize, Serialize};

use super::Peer;

// ============================================================================
// Command Types
// ============================================================================

/// A routable command between hubs
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MeshCommand {
    /// Unique command ID
    pub id: String,
    /// Command type
    pub command_type: CommandType,
    /// Target rooms (if applicable)
    pub target_rooms: Option<Vec<String>>,
    /// Command parameters
    pub params: HashMap<String, serde_json::Value>,
    /// Originating hub ID
    pub origin_hub: String,
    /// Timestamp
    pub timestamp: u64,
    /// Acknowledgment required?
    pub requires_ack: bool,
}

/// Types of commands that can be routed
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum CommandType {
    /// Light control
    Lights { level: i32 },
    /// Shade control
    Shades { action: String },
    /// Scene activation
    Scene { name: String },
    /// Fireplace control
    Fireplace { on: bool },
    /// Lock control
    Lock { lock: bool },
    /// Announce message
    Announce { message: String },
    /// Query status
    Query { target: String },
    /// Custom command
    Custom { action: String },
}

/// Command acknowledgment
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CommandAck {
    /// Command ID being acknowledged
    pub command_id: String,
    /// Hub that executed the command
    pub executor_hub: String,
    /// Success or failure
    pub success: bool,
    /// Result message
    pub message: String,
    /// Execution time (ms)
    pub execution_time_ms: u64,
    /// Timestamp
    pub timestamp: u64,
}

// ============================================================================
// Room Ownership
// ============================================================================

/// Mapping of rooms to their owning hubs
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RoomOwnership {
    /// Room name -> Hub ID
    pub rooms: HashMap<String, String>,
    /// Default hub for unknown rooms
    pub default_hub: String,
    /// Last update timestamp
    pub updated_at: u64,
}

impl RoomOwnership {
    /// Create new room ownership
    pub fn new(default_hub: String) -> Self {
        Self {
            rooms: HashMap::new(),
            default_hub,
            updated_at: current_timestamp(),
        }
    }

    /// Assign a room to a hub
    pub fn assign(&mut self, room: String, hub_id: String) {
        self.rooms.insert(room, hub_id);
        self.updated_at = current_timestamp();
    }

    /// Get the hub that owns a room
    pub fn get_owner(&self, room: &str) -> &str {
        self.rooms.get(room).map(|s| s.as_str()).unwrap_or(&self.default_hub)
    }

    /// Get all rooms owned by a hub
    pub fn get_rooms_for_hub(&self, hub_id: &str) -> Vec<String> {
        self.rooms.iter()
            .filter(|(_, hid)| *hid == hub_id)
            .map(|(room, _)| room.clone())
            .collect()
    }
}

// ============================================================================
// Routing Events
// ============================================================================

/// Events emitted by the command router
#[derive(Debug, Clone)]
pub enum RoutingEvent {
    /// Command received for routing
    CommandReceived { command_id: String, target_rooms: Vec<String> },
    /// Command routed to another hub
    CommandRouted { command_id: String, target_hub: String },
    /// Command executed locally
    CommandExecuted { command_id: String, success: bool },
    /// Acknowledgment received
    AckReceived { command_id: String, from_hub: String },
    /// Routing failed
    RoutingFailed { command_id: String, reason: String },
}

// ============================================================================
// Command Router
// ============================================================================

/// Routes commands between hubs
pub struct CommandRouter {
    /// This hub's ID
    hub_id: String,
    /// Known peers
    peers: Arc<RwLock<Vec<Peer>>>,
    /// Room ownership
    ownership: Arc<RwLock<RoomOwnership>>,
    /// Pending commands waiting for ack
    pending: Arc<RwLock<HashMap<String, PendingCommand>>>,
    /// HTTP client
    client: reqwest::Client,
    /// Event channel
    event_tx: broadcast::Sender<RoutingEvent>,
}

/// A command waiting for acknowledgment
#[derive(Debug, Clone)]
struct PendingCommand {
    command: MeshCommand,
    sent_to: Vec<String>,
    acks: Vec<CommandAck>,
    sent_at: SystemTime,
}

impl CommandRouter {
    /// Create a new command router
    pub fn new(hub_id: String, peers: Arc<RwLock<Vec<Peer>>>) -> Self {
        let (event_tx, _) = broadcast::channel(100);

        Self {
            ownership: Arc::new(RwLock::new(RoomOwnership::new(hub_id.clone()))),
            hub_id,
            peers,
            pending: Arc::new(RwLock::new(HashMap::new())),
            client: reqwest::Client::builder()
                .timeout(Duration::from_secs(10))
                .build()
                .expect("Failed to create HTTP client"),
            event_tx,
        }
    }

    /// Subscribe to routing events
    pub fn subscribe(&self) -> broadcast::Receiver<RoutingEvent> {
        self.event_tx.subscribe()
    }

    /// Route a command to the appropriate hub(s)
    pub async fn route(&self, command: MeshCommand) -> anyhow::Result<RouteResult> {
        info!(
            "🔀 Routing command {} ({:?}) to {:?}",
            command.id, command.command_type, command.target_rooms
        );

        let _ = self.event_tx.send(RoutingEvent::CommandReceived {
            command_id: command.id.clone(),
            target_rooms: command.target_rooms.clone().unwrap_or_default(),
        });

        // Determine target hubs
        let target_hubs = self.determine_targets(&command).await;

        if target_hubs.is_empty() {
            // Execute locally
            return self.execute_locally(command).await;
        }

        // Check if only local
        if target_hubs.len() == 1 && target_hubs[0] == self.hub_id {
            return self.execute_locally(command).await;
        }

        // Route to remote hubs
        let mut results = Vec::new();
        let mut local_execution = false;

        for hub_id in &target_hubs {
            if hub_id == &self.hub_id {
                local_execution = true;
            } else {
                match self.route_to_hub(&command, hub_id).await {
                    Ok(ack) => results.push(ack),
                    Err(e) => {
                        warn!("Failed to route to {}: {}", hub_id, e);
                        let _ = self.event_tx.send(RoutingEvent::RoutingFailed {
                            command_id: command.id.clone(),
                            reason: e.to_string(),
                        });
                    }
                }
            }
        }

        // Execute locally if needed
        if local_execution {
            let local_result = self.execute_locally(command.clone()).await?;
            results.push(CommandAck {
                command_id: command.id.clone(),
                executor_hub: self.hub_id.clone(),
                success: matches!(local_result, RouteResult::Executed { .. }),
                message: match &local_result {
                    RouteResult::Executed { message } => message.clone(),
                    _ => "Executed".to_string(),
                },
                execution_time_ms: 0,
                timestamp: current_timestamp(),
            });
        }

        // Store pending if requires ack
        if command.requires_ack {
            let mut pending = self.pending.write().await;
            pending.insert(command.id.clone(), PendingCommand {
                command: command.clone(),
                sent_to: target_hubs.clone(),
                acks: results.clone(),
                sent_at: SystemTime::now(),
            });
        }

        Ok(RouteResult::Routed {
            hubs: target_hubs,
            acks: results,
        })
    }

    /// Determine which hubs should handle this command
    async fn determine_targets(&self, command: &MeshCommand) -> Vec<String> {
        let ownership = self.ownership.read().await;

        match &command.target_rooms {
            Some(rooms) if !rooms.is_empty() => {
                // Get unique hub IDs for all target rooms
                let mut hubs: Vec<String> = rooms.iter()
                    .map(|room| ownership.get_owner(room).to_string())
                    .collect();
                hubs.sort();
                hubs.dedup();
                hubs
            }
            _ => {
                // No specific rooms - execute on leader or local
                vec![self.hub_id.clone()]
            }
        }
    }

    /// Route command to a specific hub
    async fn route_to_hub(&self, command: &MeshCommand, hub_id: &str) -> anyhow::Result<CommandAck> {
        let peers = self.peers.read().await;

        let peer = peers.iter()
            .find(|p| p.hub_id == hub_id)
            .ok_or_else(|| anyhow::anyhow!("Hub {} not found in peers", hub_id))?;

        let url = format!("{}/api/mesh/command", peer.api_url());

        let start = std::time::Instant::now();

        let response = self.client
            .post(&url)
            .json(command)
            .send()
            .await?;

        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().await.unwrap_or_default();
            return Err(anyhow::anyhow!("Hub {} rejected command: {} - {}", hub_id, status, body));
        }

        let ack: CommandAck = response.json().await?;

        let _ = self.event_tx.send(RoutingEvent::CommandRouted {
            command_id: command.id.clone(),
            target_hub: hub_id.to_string(),
        });

        info!(
            "✓ Routed command {} to {} ({:.0}ms)",
            command.id, hub_id, start.elapsed().as_millis()
        );

        Ok(ack)
    }

    /// Execute a command locally
    async fn execute_locally(&self, command: MeshCommand) -> anyhow::Result<RouteResult> {
        info!("⚡ Executing command {} locally", command.id);

        // This would actually execute the command via the voice pipeline
        // For now, we return a placeholder result

        let message = match &command.command_type {
            CommandType::Lights { level } => format!("Lights set to {}%", level),
            CommandType::Shades { action } => format!("Shades {}", action),
            CommandType::Scene { name } => format!("Scene {} activated", name),
            CommandType::Fireplace { on } => if *on { "Fireplace on" } else { "Fireplace off" }.to_string(),
            CommandType::Lock { lock } => if *lock { "Locked" } else { "Unlocked" }.to_string(),
            CommandType::Announce { message } => format!("Announced: {}", message),
            CommandType::Query { target } => format!("Queried {}", target),
            CommandType::Custom { action } => format!("Executed {}", action),
        };

        let _ = self.event_tx.send(RoutingEvent::CommandExecuted {
            command_id: command.id.clone(),
            success: true,
        });

        Ok(RouteResult::Executed { message })
    }

    /// Handle an incoming routed command from another hub
    pub async fn handle_incoming(&self, command: MeshCommand) -> CommandAck {
        info!(
            "📥 Received routed command {} from {}",
            command.id, command.origin_hub
        );

        let start = std::time::Instant::now();

        // Execute the command
        let result = self.execute_locally(command.clone()).await;

        let (success, message) = match result {
            Ok(RouteResult::Executed { message }) => (true, message),
            Ok(RouteResult::Routed { .. }) => (true, "Routed".to_string()),
            Err(e) => (false, e.to_string()),
        };

        CommandAck {
            command_id: command.id,
            executor_hub: self.hub_id.clone(),
            success,
            message,
            execution_time_ms: start.elapsed().as_millis() as u64,
            timestamp: current_timestamp(),
        }
    }

    /// Handle an incoming acknowledgment
    pub async fn handle_ack(&self, ack: CommandAck) {
        info!(
            "📫 Received ack for command {} from {}",
            ack.command_id, ack.executor_hub
        );

        let _ = self.event_tx.send(RoutingEvent::AckReceived {
            command_id: ack.command_id.clone(),
            from_hub: ack.executor_hub.clone(),
        });

        // Update pending
        let mut pending = self.pending.write().await;
        if let Some(p) = pending.get_mut(&ack.command_id) {
            p.acks.push(ack);
        }
    }

    /// Assign room ownership
    pub async fn assign_room(&self, room: String, hub_id: String) {
        let mut ownership = self.ownership.write().await;
        ownership.assign(room.clone(), hub_id.clone());
        info!("Assigned room '{}' to hub '{}'", room, hub_id);
    }

    /// Get room ownership
    pub async fn get_room_owner(&self, room: &str) -> String {
        let ownership = self.ownership.read().await;
        ownership.get_owner(room).to_string()
    }

    /// Get all rooms for a hub
    pub async fn get_rooms_for_hub(&self, hub_id: &str) -> Vec<String> {
        let ownership = self.ownership.read().await;
        ownership.get_rooms_for_hub(hub_id)
    }

    /// Clean up old pending commands
    pub async fn cleanup_pending(&self, max_age: Duration) {
        let mut pending = self.pending.write().await;
        let now = SystemTime::now();

        pending.retain(|_, p| {
            now.duration_since(p.sent_at).unwrap_or(Duration::ZERO) < max_age
        });
    }
}

// ============================================================================
// Route Result
// ============================================================================

/// Result of routing a command
#[derive(Debug, Clone)]
pub enum RouteResult {
    /// Command was executed locally
    Executed { message: String },
    /// Command was routed to remote hub(s)
    Routed { hubs: Vec<String>, acks: Vec<CommandAck> },
}

// ============================================================================
// Command Builder
// ============================================================================

/// Builder for creating mesh commands
pub struct CommandBuilder {
    command_type: CommandType,
    target_rooms: Option<Vec<String>>,
    params: HashMap<String, serde_json::Value>,
    requires_ack: bool,
}

impl CommandBuilder {
    /// Create a lights command
    pub fn lights(level: i32) -> Self {
        Self {
            command_type: CommandType::Lights { level },
            target_rooms: None,
            params: HashMap::new(),
            requires_ack: false,
        }
    }

    /// Create a shades command
    pub fn shades(action: impl Into<String>) -> Self {
        Self {
            command_type: CommandType::Shades { action: action.into() },
            target_rooms: None,
            params: HashMap::new(),
            requires_ack: false,
        }
    }

    /// Create a scene command
    pub fn scene(name: impl Into<String>) -> Self {
        Self {
            command_type: CommandType::Scene { name: name.into() },
            target_rooms: None,
            params: HashMap::new(),
            requires_ack: false,
        }
    }

    /// Create an announce command
    pub fn announce(message: impl Into<String>) -> Self {
        Self {
            command_type: CommandType::Announce { message: message.into() },
            target_rooms: None,
            params: HashMap::new(),
            requires_ack: false,
        }
    }

    /// Target specific rooms
    pub fn rooms(mut self, rooms: Vec<String>) -> Self {
        self.target_rooms = Some(rooms);
        self
    }

    /// Require acknowledgment
    pub fn require_ack(mut self) -> Self {
        self.requires_ack = true;
        self
    }

    /// Build the command
    pub fn build(self, origin_hub: String) -> MeshCommand {
        MeshCommand {
            id: generate_command_id(),
            command_type: self.command_type,
            target_rooms: self.target_rooms,
            params: self.params,
            origin_hub,
            timestamp: current_timestamp(),
            requires_ack: self.requires_ack,
        }
    }
}

// ============================================================================
// Utility Functions
// ============================================================================

/// Get current Unix timestamp
fn current_timestamp() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs()
}

/// Generate a unique command ID
fn generate_command_id() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let ts = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    format!("cmd-{:x}", ts)
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_room_ownership() {
        let mut ownership = RoomOwnership::new("hub-1".to_string());

        ownership.assign("kitchen".to_string(), "hub-2".to_string());

        assert_eq!(ownership.get_owner("kitchen"), "hub-2");
        assert_eq!(ownership.get_owner("unknown"), "hub-1");
    }

    #[test]
    fn test_command_builder() {
        let cmd = CommandBuilder::lights(75)
            .rooms(vec!["living room".to_string()])
            .require_ack()
            .build("hub-1".to_string());

        assert!(matches!(cmd.command_type, CommandType::Lights { level: 75 }));
        assert_eq!(cmd.target_rooms.as_ref().unwrap().len(), 1);
        assert!(cmd.requires_ack);
    }

    #[test]
    fn test_command_id_uniqueness() {
        let id1 = generate_command_id();
        std::thread::sleep(std::time::Duration::from_nanos(100));
        let id2 = generate_command_id();

        assert_ne!(id1, id2);
    }
}

/*
 * 鏡
 * Commands flow across the mesh. Each hub serves its zone.
 */
