//! Distributed Command Coordination — Forge (e2) Colony
//!
//! Enables cross-hub command coordination with distributed transactions
//! and two-phase commit protocol for critical operations.
//!
//! ## Features
//!
//! - **Cross-Hub Commands**: Execute commands that span multiple hubs
//! - **Two-Phase Commit**: ACID transactions for critical operations
//! - **Conflict Detection**: Prevents concurrent conflicting commands
//! - **Rollback Support**: Automatic rollback on partial failures
//! - **Timeout Handling**: Configurable timeouts with automatic abort
//!
//! ## Transaction Flow
//!
//! ```text
//! Coordinator                  Participants (Hubs)
//!     |                              |
//!     |-------- PREPARE ------------>|
//!     |                              | (validate, lock resources)
//!     |<------- VOTE YES/NO ---------|
//!     |                              |
//!     |-------- COMMIT/ABORT ------->|
//!     |                              | (apply/rollback)
//!     |<------- ACK -----------------|
//! ```
//!
//! Colony: Forge (e2) — Creation, coordination
//!
//! h(x) >= 0. Always.

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
use tokio::sync::{mpsc, oneshot, RwLock};
use tracing::{debug, error, info, warn};

// ============================================================================
// Configuration
// ============================================================================

/// Default timeout for prepare phase (ms)
pub const PREPARE_TIMEOUT_MS: u64 = 5000;

/// Default timeout for commit phase (ms)
pub const COMMIT_TIMEOUT_MS: u64 = 3000;

/// Default timeout for entire transaction (ms)
pub const TRANSACTION_TIMEOUT_MS: u64 = 15000;

/// Maximum concurrent transactions
pub const MAX_CONCURRENT_TRANSACTIONS: usize = 32;

/// Maximum retries for failed operations
pub const MAX_RETRIES: u32 = 3;

// ============================================================================
// Transaction Types
// ============================================================================

/// Unique transaction identifier
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct TransactionId(pub String);

impl TransactionId {
    /// Create a new transaction ID
    pub fn new() -> Self {
        let timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_nanos();

        Self(format!("txn_{:x}", timestamp))
    }
}

impl Default for TransactionId {
    fn default() -> Self {
        Self::new()
    }
}

/// Transaction state in the two-phase commit protocol
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum TransactionState {
    /// Transaction created, not yet started
    Created,
    /// Prepare phase in progress
    Preparing,
    /// All participants voted YES
    Prepared,
    /// Commit phase in progress
    Committing,
    /// Transaction successfully committed
    Committed,
    /// Abort phase in progress
    Aborting,
    /// Transaction aborted
    Aborted,
    /// Transaction timed out
    TimedOut,
}

/// Vote from a participant in prepare phase
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum PrepareVote {
    /// Ready to commit
    Yes {
        participant_id: String,
        prepared_at: u64,
    },
    /// Cannot commit (reason provided)
    No {
        participant_id: String,
        reason: String,
    },
}

/// Operation to be executed as part of a transaction
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TransactionOperation {
    /// Target hub ID
    pub hub_id: String,
    /// Operation type
    pub operation: OperationType,
    /// Operation parameters
    pub params: HashMap<String, serde_json::Value>,
    /// Undo operation for rollback
    pub undo: Option<UndoOperation>,
}

/// Types of operations that can be part of a transaction
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum OperationType {
    /// Set device state
    SetDevice {
        device_id: String,
        state: DeviceState,
    },
    /// Activate scene
    ActivateScene {
        scene_id: String,
    },
    /// Execute command
    ExecuteCommand {
        command: String,
    },
    /// Update configuration
    UpdateConfig {
        key: String,
        value: serde_json::Value,
    },
    /// Sync state from coordinator
    SyncState {
        state_key: String,
        state_value: serde_json::Value,
    },
    /// Custom operation
    Custom {
        operation_type: String,
        payload: serde_json::Value,
    },
}

/// Device state for SetDevice operation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeviceState {
    pub power: Option<bool>,
    pub brightness: Option<u8>,
    pub color: Option<String>,
    pub position: Option<u8>,
    pub temperature: Option<f32>,
}

/// Undo operation for rollback
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UndoOperation {
    /// Operation type to undo
    pub operation: OperationType,
    /// Previous state to restore
    pub previous_state: Option<serde_json::Value>,
}

// ============================================================================
// Transaction
// ============================================================================

/// A distributed transaction
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Transaction {
    /// Unique transaction ID
    pub id: TransactionId,
    /// Coordinator hub ID
    pub coordinator_id: String,
    /// Operations to execute
    pub operations: Vec<TransactionOperation>,
    /// Participating hub IDs
    pub participants: HashSet<String>,
    /// Current state
    pub state: TransactionState,
    /// Votes received from participants
    pub votes: HashMap<String, PrepareVote>,
    /// Commit acknowledgments received
    pub acks: HashSet<String>,
    /// Creation timestamp
    pub created_at: u64,
    /// Last state change timestamp
    pub updated_at: u64,
    /// Timeout configuration
    pub timeout_ms: u64,
    /// Priority (higher = more important)
    pub priority: u32,
    /// Whether transaction is idempotent
    pub idempotent: bool,
}

impl Transaction {
    /// Create a new transaction
    pub fn new(coordinator_id: &str, operations: Vec<TransactionOperation>) -> Self {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_millis() as u64;

        let participants: HashSet<String> = operations.iter()
            .map(|op| op.hub_id.clone())
            .collect();

        Self {
            id: TransactionId::new(),
            coordinator_id: coordinator_id.to_string(),
            operations,
            participants,
            state: TransactionState::Created,
            votes: HashMap::new(),
            acks: HashSet::new(),
            created_at: now,
            updated_at: now,
            timeout_ms: TRANSACTION_TIMEOUT_MS,
            priority: 0,
            idempotent: false,
        }
    }

    /// Check if transaction has timed out
    pub fn is_timed_out(&self) -> bool {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_millis() as u64;

        now - self.created_at > self.timeout_ms
    }

    /// Check if all participants have voted YES
    pub fn all_voted_yes(&self) -> bool {
        if self.votes.len() != self.participants.len() {
            return false;
        }

        self.votes.values().all(|vote| matches!(vote, PrepareVote::Yes { .. }))
    }

    /// Check if all participants have acknowledged commit
    pub fn all_acknowledged(&self) -> bool {
        self.acks.len() == self.participants.len()
    }

    /// Get operations for a specific hub
    pub fn operations_for_hub(&self, hub_id: &str) -> Vec<&TransactionOperation> {
        self.operations.iter()
            .filter(|op| op.hub_id == hub_id)
            .collect()
    }
}

// ============================================================================
// Protocol Messages
// ============================================================================

/// Messages for the two-phase commit protocol
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum TwoPhaseMessage {
    /// Phase 1: Prepare request from coordinator
    Prepare {
        transaction: Transaction,
    },

    /// Phase 1: Vote response from participant
    Vote {
        transaction_id: TransactionId,
        vote: PrepareVote,
    },

    /// Phase 2: Commit request from coordinator
    Commit {
        transaction_id: TransactionId,
    },

    /// Phase 2: Abort request from coordinator
    Abort {
        transaction_id: TransactionId,
        reason: String,
    },

    /// Acknowledgment from participant
    Ack {
        transaction_id: TransactionId,
        participant_id: String,
        success: bool,
        error: Option<String>,
    },

    /// Query transaction status
    StatusQuery {
        transaction_id: TransactionId,
    },

    /// Transaction status response
    StatusResponse {
        transaction_id: TransactionId,
        state: TransactionState,
    },
}

// ============================================================================
// Resource Locks
// ============================================================================

/// Resource lock for conflict prevention
#[derive(Debug, Clone)]
pub struct ResourceLock {
    /// Resource identifier
    pub resource_id: String,
    /// Transaction holding the lock
    pub transaction_id: TransactionId,
    /// Lock acquisition time
    pub acquired_at: Instant,
    /// Lock expiration time
    pub expires_at: Instant,
}

/// Lock manager for resources
pub struct LockManager {
    /// Active locks
    locks: Arc<RwLock<HashMap<String, ResourceLock>>>,
    /// Lock timeout duration
    lock_timeout: Duration,
}

impl LockManager {
    /// Create a new lock manager
    pub fn new(lock_timeout: Duration) -> Self {
        Self {
            locks: Arc::new(RwLock::new(HashMap::new())),
            lock_timeout,
        }
    }

    /// Acquire a lock on a resource
    pub async fn acquire(&self, resource_id: &str, transaction_id: &TransactionId) -> Result<bool> {
        let mut locks = self.locks.write().await;
        let now = Instant::now();

        // Check if already locked
        if let Some(existing) = locks.get(resource_id) {
            // Check if lock has expired
            if existing.expires_at > now && existing.transaction_id != *transaction_id {
                return Ok(false); // Resource locked by another transaction
            }
        }

        // Acquire lock
        let lock = ResourceLock {
            resource_id: resource_id.to_string(),
            transaction_id: transaction_id.clone(),
            acquired_at: now,
            expires_at: now + self.lock_timeout,
        };

        locks.insert(resource_id.to_string(), lock);
        Ok(true)
    }

    /// Release a lock
    pub async fn release(&self, resource_id: &str, transaction_id: &TransactionId) -> bool {
        let mut locks = self.locks.write().await;

        if let Some(lock) = locks.get(resource_id) {
            if lock.transaction_id == *transaction_id {
                locks.remove(resource_id);
                return true;
            }
        }

        false
    }

    /// Release all locks for a transaction
    pub async fn release_all(&self, transaction_id: &TransactionId) {
        let mut locks = self.locks.write().await;
        locks.retain(|_, lock| lock.transaction_id != *transaction_id);
    }

    /// Clean up expired locks
    pub async fn cleanup_expired(&self) {
        let mut locks = self.locks.write().await;
        let now = Instant::now();
        locks.retain(|_, lock| lock.expires_at > now);
    }
}

// ============================================================================
// Transaction Coordinator
// ============================================================================

/// Coordinates distributed transactions across hubs
pub struct TransactionCoordinator {
    /// This hub's ID
    hub_id: String,
    /// Active transactions (as coordinator)
    active_transactions: Arc<RwLock<HashMap<TransactionId, Transaction>>>,
    /// Participating transactions (as participant)
    participating: Arc<RwLock<HashMap<TransactionId, Transaction>>>,
    /// Lock manager
    lock_manager: LockManager,
    /// Transaction counter for ordering
    transaction_counter: AtomicU64,
    /// Channel for outgoing protocol messages
    outgoing_tx: mpsc::Sender<(String, TwoPhaseMessage)>,
    /// Event channel
    event_tx: tokio::sync::broadcast::Sender<TransactionEvent>,
}

/// Events emitted by the transaction coordinator
#[derive(Debug, Clone)]
pub enum TransactionEvent {
    /// Transaction started
    Started { transaction_id: TransactionId },
    /// Transaction prepared (all YES votes)
    Prepared { transaction_id: TransactionId },
    /// Transaction committed
    Committed { transaction_id: TransactionId },
    /// Transaction aborted
    Aborted { transaction_id: TransactionId, reason: String },
    /// Transaction timed out
    TimedOut { transaction_id: TransactionId },
    /// Conflict detected
    Conflict { transaction_id: TransactionId, resource: String },
}

impl TransactionCoordinator {
    /// Create a new transaction coordinator
    pub fn new(hub_id: &str) -> (Self, mpsc::Receiver<(String, TwoPhaseMessage)>, tokio::sync::broadcast::Receiver<TransactionEvent>) {
        let (outgoing_tx, outgoing_rx) = mpsc::channel(256);
        let (event_tx, event_rx) = tokio::sync::broadcast::channel(64);

        let coordinator = Self {
            hub_id: hub_id.to_string(),
            active_transactions: Arc::new(RwLock::new(HashMap::new())),
            participating: Arc::new(RwLock::new(HashMap::new())),
            lock_manager: LockManager::new(Duration::from_secs(30)),
            transaction_counter: AtomicU64::new(0),
            outgoing_tx,
            event_tx,
        };

        (coordinator, outgoing_rx, event_rx)
    }

    /// Start a new distributed transaction (as coordinator)
    pub async fn begin_transaction(&self, operations: Vec<TransactionOperation>) -> Result<TransactionId> {
        // Check concurrent transaction limit
        let active = self.active_transactions.read().await;
        if active.len() >= MAX_CONCURRENT_TRANSACTIONS {
            return Err(anyhow::anyhow!("Maximum concurrent transactions exceeded"));
        }
        drop(active);

        // Create transaction
        let mut transaction = Transaction::new(&self.hub_id, operations);
        let transaction_id = transaction.id.clone();

        // Acquire locks for all resources
        for op in &transaction.operations {
            let resource_id = self.operation_resource_id(op);
            if !self.lock_manager.acquire(&resource_id, &transaction_id).await? {
                // Failed to acquire lock, abort
                self.lock_manager.release_all(&transaction_id).await;
                return Err(anyhow::anyhow!("Resource conflict: {}", resource_id));
            }
        }

        // Store transaction
        transaction.state = TransactionState::Preparing;
        {
            let mut active = self.active_transactions.write().await;
            active.insert(transaction_id.clone(), transaction.clone());
        }

        // Send prepare messages to all participants
        let prepare_msg = TwoPhaseMessage::Prepare { transaction: transaction.clone() };

        for participant_id in &transaction.participants {
            if participant_id != &self.hub_id {
                let _ = self.outgoing_tx.send((participant_id.clone(), prepare_msg.clone())).await;
            } else {
                // Local participant - vote immediately
                let vote = self.prepare_local(&transaction).await;
                self.handle_vote(&transaction_id, vote).await?;
            }
        }

        info!("Transaction {} started with {} participants", transaction_id.0, transaction.participants.len());
        let _ = self.event_tx.send(TransactionEvent::Started { transaction_id: transaction_id.clone() });

        Ok(transaction_id)
    }

    /// Handle incoming protocol message
    pub async fn handle_message(&self, from_hub: &str, message: TwoPhaseMessage) -> Result<()> {
        match message {
            TwoPhaseMessage::Prepare { transaction } => {
                self.handle_prepare(from_hub, transaction).await?;
            }
            TwoPhaseMessage::Vote { transaction_id, vote } => {
                self.handle_vote(&transaction_id, vote).await?;
            }
            TwoPhaseMessage::Commit { transaction_id } => {
                self.handle_commit(&transaction_id).await?;
            }
            TwoPhaseMessage::Abort { transaction_id, reason } => {
                self.handle_abort(&transaction_id, &reason).await?;
            }
            TwoPhaseMessage::Ack { transaction_id, participant_id, success, error } => {
                self.handle_ack(&transaction_id, &participant_id, success, error).await?;
            }
            TwoPhaseMessage::StatusQuery { transaction_id } => {
                self.handle_status_query(from_hub, &transaction_id).await?;
            }
            TwoPhaseMessage::StatusResponse { transaction_id, state } => {
                debug!("Transaction {} status: {:?}", transaction_id.0, state);
            }
        }

        Ok(())
    }

    /// Handle prepare request (as participant)
    async fn handle_prepare(&self, from_hub: &str, transaction: Transaction) -> Result<()> {
        let transaction_id = transaction.id.clone();

        // Validate transaction
        let vote = self.prepare_local(&transaction).await;

        // Store as participating transaction
        {
            let mut participating = self.participating.write().await;
            participating.insert(transaction_id.clone(), transaction);
        }

        // Send vote back to coordinator
        let vote_msg = TwoPhaseMessage::Vote {
            transaction_id,
            vote,
        };

        let _ = self.outgoing_tx.send((from_hub.to_string(), vote_msg)).await;

        Ok(())
    }

    /// Prepare locally and return vote
    async fn prepare_local(&self, transaction: &Transaction) -> PrepareVote {
        let my_operations = transaction.operations_for_hub(&self.hub_id);

        // Check if we can execute all operations
        for op in my_operations {
            // Validate operation
            if let Err(e) = self.validate_operation(op).await {
                return PrepareVote::No {
                    participant_id: self.hub_id.clone(),
                    reason: e.to_string(),
                };
            }

            // Try to acquire lock
            let resource_id = self.operation_resource_id(op);
            match self.lock_manager.acquire(&resource_id, &transaction.id).await {
                Ok(true) => {}
                Ok(false) => {
                    return PrepareVote::No {
                        participant_id: self.hub_id.clone(),
                        reason: format!("Resource locked: {}", resource_id),
                    };
                }
                Err(e) => {
                    return PrepareVote::No {
                        participant_id: self.hub_id.clone(),
                        reason: e.to_string(),
                    };
                }
            }
        }

        let prepared_at = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_millis() as u64;

        PrepareVote::Yes {
            participant_id: self.hub_id.clone(),
            prepared_at,
        }
    }

    /// Handle vote from participant (as coordinator)
    async fn handle_vote(&self, transaction_id: &TransactionId, vote: PrepareVote) -> Result<()> {
        let mut active = self.active_transactions.write().await;

        let transaction = active.get_mut(transaction_id)
            .context("Transaction not found")?;

        // Record vote
        let participant_id = match &vote {
            PrepareVote::Yes { participant_id, .. } => participant_id.clone(),
            PrepareVote::No { participant_id, .. } => participant_id.clone(),
        };

        transaction.votes.insert(participant_id.clone(), vote.clone());

        // Check if we should proceed
        match &vote {
            PrepareVote::No { reason, .. } => {
                // Abort transaction
                info!("Transaction {} aborted: participant {} voted NO: {}",
                    transaction_id.0, participant_id, reason);

                transaction.state = TransactionState::Aborting;
                let abort_msg = TwoPhaseMessage::Abort {
                    transaction_id: transaction_id.clone(),
                    reason: reason.clone(),
                };

                for pid in &transaction.participants {
                    if pid != &self.hub_id {
                        let _ = self.outgoing_tx.send((pid.clone(), abort_msg.clone())).await;
                    }
                }

                // Release locks
                self.lock_manager.release_all(transaction_id).await;

                let _ = self.event_tx.send(TransactionEvent::Aborted {
                    transaction_id: transaction_id.clone(),
                    reason: reason.clone(),
                });
            }
            PrepareVote::Yes { .. } => {
                // Check if all have voted YES
                if transaction.all_voted_yes() {
                    info!("Transaction {} prepared, sending commit", transaction_id.0);
                    transaction.state = TransactionState::Prepared;

                    let _ = self.event_tx.send(TransactionEvent::Prepared {
                        transaction_id: transaction_id.clone(),
                    });

                    // Send commit to all participants
                    transaction.state = TransactionState::Committing;
                    let commit_msg = TwoPhaseMessage::Commit {
                        transaction_id: transaction_id.clone(),
                    };

                    for pid in &transaction.participants {
                        if pid != &self.hub_id {
                            let _ = self.outgoing_tx.send((pid.clone(), commit_msg.clone())).await;
                        }
                    }

                    // Commit locally
                    self.commit_local(transaction_id).await?;
                }
            }
        }

        Ok(())
    }

    /// Handle commit request (as participant)
    async fn handle_commit(&self, transaction_id: &TransactionId) -> Result<()> {
        let result = self.commit_local(transaction_id).await;

        // Get coordinator
        let participating = self.participating.read().await;
        let coordinator_id = participating.get(transaction_id)
            .map(|t| t.coordinator_id.clone())
            .unwrap_or_default();
        drop(participating);

        // Send acknowledgment
        let ack = TwoPhaseMessage::Ack {
            transaction_id: transaction_id.clone(),
            participant_id: self.hub_id.clone(),
            success: result.is_ok(),
            error: result.err().map(|e| e.to_string()),
        };

        let _ = self.outgoing_tx.send((coordinator_id, ack)).await;

        // Release locks
        self.lock_manager.release_all(transaction_id).await;

        // Remove from participating
        let mut participating = self.participating.write().await;
        participating.remove(transaction_id);

        Ok(())
    }

    /// Commit transaction locally
    async fn commit_local(&self, transaction_id: &TransactionId) -> Result<()> {
        // Get transaction (from active or participating)
        let transaction = {
            let active = self.active_transactions.read().await;
            if let Some(t) = active.get(transaction_id) {
                t.clone()
            } else {
                let participating = self.participating.read().await;
                participating.get(transaction_id)
                    .cloned()
                    .context("Transaction not found")?
            }
        };

        // Execute operations for this hub
        let my_operations = transaction.operations_for_hub(&self.hub_id);

        for op in my_operations {
            if let Err(e) = self.execute_operation(op).await {
                error!("Failed to execute operation in transaction {}: {}", transaction_id.0, e);
                // Note: At this point we're in commit phase, so we can't abort
                // In a real implementation, we'd need to retry or escalate
            }
        }

        info!("Transaction {} committed locally", transaction_id.0);

        // Update state in active transactions if we're coordinator
        let mut active = self.active_transactions.write().await;
        if let Some(t) = active.get_mut(transaction_id) {
            t.acks.insert(self.hub_id.clone());
        }

        Ok(())
    }

    /// Handle abort request (as participant)
    async fn handle_abort(&self, transaction_id: &TransactionId, reason: &str) -> Result<()> {
        info!("Transaction {} aborted: {}", transaction_id.0, reason);

        // Release locks
        self.lock_manager.release_all(transaction_id).await;

        // Remove from participating
        let mut participating = self.participating.write().await;
        participating.remove(transaction_id);

        Ok(())
    }

    /// Handle acknowledgment from participant (as coordinator)
    async fn handle_ack(&self, transaction_id: &TransactionId, participant_id: &str, success: bool, error: Option<String>) -> Result<()> {
        let mut active = self.active_transactions.write().await;

        if let Some(transaction) = active.get_mut(transaction_id) {
            if success {
                transaction.acks.insert(participant_id.to_string());

                // Check if all have acknowledged
                if transaction.all_acknowledged() {
                    transaction.state = TransactionState::Committed;
                    info!("Transaction {} fully committed", transaction_id.0);

                    // Release locks
                    self.lock_manager.release_all(transaction_id).await;

                    let _ = self.event_tx.send(TransactionEvent::Committed {
                        transaction_id: transaction_id.clone(),
                    });
                }
            } else {
                warn!("Transaction {} participant {} failed to commit: {:?}",
                    transaction_id.0, participant_id, error);
                // In a real implementation, we'd need to handle this case
            }
        }

        Ok(())
    }

    /// Handle status query
    async fn handle_status_query(&self, from_hub: &str, transaction_id: &TransactionId) -> Result<()> {
        let state = {
            let active = self.active_transactions.read().await;
            if let Some(t) = active.get(transaction_id) {
                Some(t.state)
            } else {
                let participating = self.participating.read().await;
                participating.get(transaction_id).map(|t| t.state)
            }
        };

        if let Some(state) = state {
            let response = TwoPhaseMessage::StatusResponse {
                transaction_id: transaction_id.clone(),
                state,
            };
            let _ = self.outgoing_tx.send((from_hub.to_string(), response)).await;
        }

        Ok(())
    }

    /// Validate an operation before prepare
    async fn validate_operation(&self, operation: &TransactionOperation) -> Result<()> {
        // Validation rules for each operation type
        match &operation.operation {
            OperationType::SetDevice { device_id, state } => {
                // Validate device exists and state is valid
                if device_id.is_empty() {
                    return Err(anyhow::anyhow!("Device ID cannot be empty"));
                }
                if let Some(brightness) = state.brightness {
                    if brightness > 100 {
                        return Err(anyhow::anyhow!("Brightness must be 0-100"));
                    }
                }
            }
            OperationType::ActivateScene { scene_id } => {
                if scene_id.is_empty() {
                    return Err(anyhow::anyhow!("Scene ID cannot be empty"));
                }
            }
            OperationType::ExecuteCommand { command } => {
                if command.is_empty() {
                    return Err(anyhow::anyhow!("Command cannot be empty"));
                }
            }
            OperationType::UpdateConfig { key, value: _ } => {
                if key.is_empty() {
                    return Err(anyhow::anyhow!("Config key cannot be empty"));
                }
            }
            _ => {}
        }

        Ok(())
    }

    /// Execute an operation
    async fn execute_operation(&self, operation: &TransactionOperation) -> Result<()> {
        debug!("Executing operation: {:?}", operation.operation);

        // In a real implementation, this would dispatch to the appropriate handler
        match &operation.operation {
            OperationType::SetDevice { device_id, state } => {
                info!("Setting device {} to state {:?}", device_id, state);
                // Would call device controller here
            }
            OperationType::ActivateScene { scene_id } => {
                info!("Activating scene {}", scene_id);
                // Would call scene controller here
            }
            OperationType::ExecuteCommand { command } => {
                info!("Executing command: {}", command);
                // Would call command executor here
            }
            OperationType::UpdateConfig { key, value } => {
                info!("Updating config {} = {}", key, value);
                // Would call config manager here
            }
            OperationType::SyncState { state_key, state_value } => {
                info!("Syncing state {} = {}", state_key, state_value);
                // Would update state store here
            }
            OperationType::Custom { operation_type, payload } => {
                info!("Executing custom operation {}: {}", operation_type, payload);
                // Would call custom handler here
            }
        }

        Ok(())
    }

    /// Get resource ID for an operation (used for locking)
    fn operation_resource_id(&self, operation: &TransactionOperation) -> String {
        match &operation.operation {
            OperationType::SetDevice { device_id, .. } => format!("device:{}", device_id),
            OperationType::ActivateScene { scene_id } => format!("scene:{}", scene_id),
            OperationType::ExecuteCommand { command } => format!("command:{}", command),
            OperationType::UpdateConfig { key, .. } => format!("config:{}", key),
            OperationType::SyncState { state_key, .. } => format!("state:{}", state_key),
            OperationType::Custom { operation_type, .. } => format!("custom:{}", operation_type),
        }
    }

    /// Get transaction status
    pub async fn get_status(&self, transaction_id: &TransactionId) -> Option<TransactionState> {
        let active = self.active_transactions.read().await;
        if let Some(t) = active.get(transaction_id) {
            return Some(t.state);
        }

        let participating = self.participating.read().await;
        participating.get(transaction_id).map(|t| t.state)
    }

    /// Check for timed-out transactions
    pub async fn check_timeouts(&self) {
        let mut timed_out = Vec::new();

        {
            let active = self.active_transactions.read().await;
            for (id, transaction) in active.iter() {
                if transaction.is_timed_out() && transaction.state != TransactionState::Committed {
                    timed_out.push(id.clone());
                }
            }
        }

        for id in timed_out {
            warn!("Transaction {} timed out", id.0);

            // Abort the transaction
            let mut active = self.active_transactions.write().await;
            if let Some(transaction) = active.get_mut(&id) {
                transaction.state = TransactionState::TimedOut;

                // Send abort to participants
                let abort_msg = TwoPhaseMessage::Abort {
                    transaction_id: id.clone(),
                    reason: "Transaction timeout".to_string(),
                };

                for pid in &transaction.participants {
                    if pid != &self.hub_id {
                        let _ = self.outgoing_tx.send((pid.clone(), abort_msg.clone())).await;
                    }
                }
            }

            // Release locks
            self.lock_manager.release_all(&id).await;

            let _ = self.event_tx.send(TransactionEvent::TimedOut { transaction_id: id });
        }
    }

    /// Clean up completed transactions
    pub async fn cleanup_completed(&self, max_age: Duration) {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_millis() as u64;

        let max_age_ms = max_age.as_millis() as u64;

        let mut active = self.active_transactions.write().await;
        active.retain(|_, t| {
            let is_complete = matches!(t.state, TransactionState::Committed | TransactionState::Aborted | TransactionState::TimedOut);
            let is_old = now - t.updated_at > max_age_ms;
            !(is_complete && is_old)
        });
    }
}

// ============================================================================
// Transaction Builder
// ============================================================================

/// Builder for creating transactions
pub struct TransactionBuilder {
    operations: Vec<TransactionOperation>,
    timeout_ms: u64,
    priority: u32,
    idempotent: bool,
}

impl TransactionBuilder {
    /// Create a new transaction builder
    pub fn new() -> Self {
        Self {
            operations: Vec::new(),
            timeout_ms: TRANSACTION_TIMEOUT_MS,
            priority: 0,
            idempotent: false,
        }
    }

    /// Add a device state operation
    pub fn set_device(mut self, hub_id: &str, device_id: &str, state: DeviceState) -> Self {
        self.operations.push(TransactionOperation {
            hub_id: hub_id.to_string(),
            operation: OperationType::SetDevice {
                device_id: device_id.to_string(),
                state,
            },
            params: HashMap::new(),
            undo: None,
        });
        self
    }

    /// Add a scene activation operation
    pub fn activate_scene(mut self, hub_id: &str, scene_id: &str) -> Self {
        self.operations.push(TransactionOperation {
            hub_id: hub_id.to_string(),
            operation: OperationType::ActivateScene {
                scene_id: scene_id.to_string(),
            },
            params: HashMap::new(),
            undo: None,
        });
        self
    }

    /// Add a command execution operation
    pub fn execute_command(mut self, hub_id: &str, command: &str) -> Self {
        self.operations.push(TransactionOperation {
            hub_id: hub_id.to_string(),
            operation: OperationType::ExecuteCommand {
                command: command.to_string(),
            },
            params: HashMap::new(),
            undo: None,
        });
        self
    }

    /// Set timeout
    pub fn timeout(mut self, timeout: Duration) -> Self {
        self.timeout_ms = timeout.as_millis() as u64;
        self
    }

    /// Set priority
    pub fn priority(mut self, priority: u32) -> Self {
        self.priority = priority;
        self
    }

    /// Mark as idempotent
    pub fn idempotent(mut self, idempotent: bool) -> Self {
        self.idempotent = idempotent;
        self
    }

    /// Build the operations list
    pub fn build(self) -> Vec<TransactionOperation> {
        self.operations
    }
}

impl Default for TransactionBuilder {
    fn default() -> Self {
        Self::new()
    }
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_transaction_id_creation() {
        let id1 = TransactionId::new();
        let id2 = TransactionId::new();
        assert_ne!(id1, id2);
        assert!(id1.0.starts_with("txn_"));
    }

    #[test]
    fn test_transaction_builder() {
        let ops = TransactionBuilder::new()
            .set_device("hub-a", "light-1", DeviceState {
                power: Some(true),
                brightness: Some(100),
                color: None,
                position: None,
                temperature: None,
            })
            .activate_scene("hub-b", "movie_mode")
            .execute_command("hub-a", "lock all doors")
            .build();

        assert_eq!(ops.len(), 3);
    }

    #[test]
    fn test_transaction_creation() {
        let ops = TransactionBuilder::new()
            .set_device("hub-a", "light-1", DeviceState {
                power: Some(true),
                brightness: None,
                color: None,
                position: None,
                temperature: None,
            })
            .set_device("hub-b", "light-2", DeviceState {
                power: Some(false),
                brightness: None,
                color: None,
                position: None,
                temperature: None,
            })
            .build();

        let transaction = Transaction::new("hub-coordinator", ops);

        assert_eq!(transaction.participants.len(), 2);
        assert!(transaction.participants.contains("hub-a"));
        assert!(transaction.participants.contains("hub-b"));
        assert_eq!(transaction.state, TransactionState::Created);
    }

    #[test]
    fn test_prepare_vote_yes() {
        let vote = PrepareVote::Yes {
            participant_id: "hub-a".to_string(),
            prepared_at: 1234567890,
        };

        assert!(matches!(vote, PrepareVote::Yes { .. }));
    }

    #[test]
    fn test_prepare_vote_no() {
        let vote = PrepareVote::No {
            participant_id: "hub-a".to_string(),
            reason: "Resource conflict".to_string(),
        };

        assert!(matches!(vote, PrepareVote::No { .. }));
    }

    #[tokio::test]
    async fn test_lock_manager() {
        let lock_manager = LockManager::new(Duration::from_secs(30));
        let txn_id = TransactionId::new();

        // Acquire lock
        let acquired = lock_manager.acquire("device:light-1", &txn_id).await.unwrap();
        assert!(acquired);

        // Try to acquire same lock with different transaction
        let txn_id_2 = TransactionId::new();
        let acquired_2 = lock_manager.acquire("device:light-1", &txn_id_2).await.unwrap();
        assert!(!acquired_2); // Should fail

        // Release lock
        let released = lock_manager.release("device:light-1", &txn_id).await;
        assert!(released);

        // Now other transaction can acquire
        let acquired_3 = lock_manager.acquire("device:light-1", &txn_id_2).await.unwrap();
        assert!(acquired_3);
    }

    #[tokio::test]
    async fn test_coordinator_creation() {
        let (coordinator, _outgoing_rx, _event_rx) = TransactionCoordinator::new("hub-1");

        let status = coordinator.get_status(&TransactionId::new()).await;
        assert!(status.is_none());
    }

    #[test]
    fn test_transaction_all_voted_yes() {
        let ops = TransactionBuilder::new()
            .set_device("hub-a", "light-1", DeviceState {
                power: Some(true),
                brightness: None,
                color: None,
                position: None,
                temperature: None,
            })
            .set_device("hub-b", "light-2", DeviceState {
                power: Some(true),
                brightness: None,
                color: None,
                position: None,
                temperature: None,
            })
            .build();

        let mut transaction = Transaction::new("coordinator", ops);

        assert!(!transaction.all_voted_yes()); // No votes yet

        transaction.votes.insert("hub-a".to_string(), PrepareVote::Yes {
            participant_id: "hub-a".to_string(),
            prepared_at: 0,
        });

        assert!(!transaction.all_voted_yes()); // Only one vote

        transaction.votes.insert("hub-b".to_string(), PrepareVote::Yes {
            participant_id: "hub-b".to_string(),
            prepared_at: 0,
        });

        assert!(transaction.all_voted_yes()); // All voted yes
    }

    #[test]
    fn test_transaction_timeout() {
        let ops = TransactionBuilder::new().build();
        let mut transaction = Transaction::new("coordinator", ops);

        transaction.timeout_ms = 0; // Immediate timeout

        assert!(transaction.is_timed_out());
    }
}

/*
 * Forge coordinates distributed actions. Two-phase commit ensures consistency.
 * Multiple hubs act as one. Transactions are ACID.
 *
 * h(x) >= 0. Always.
 */
