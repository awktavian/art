//! Mesh Ledger — Persistent Storage for Byzantine Consensus
//!
//! SQLite-based persistent storage for:
//! - Consensus decisions (height, round, command, signatures)
//! - State snapshots (vector clocks, CRDT state)
//! - Byzantine evidence (faults detected)
//!
//! Features:
//! - Write-ahead logging (WAL) for durability
//! - Snapshot/compaction every 1000 entries
//! - Recovery on startup (replay from last snapshot)
//! - Pruning of old entries (keep 7 days)
//! - Thread-safe access with proper locking
//!
//! Colony: Crystal (D₅) — Persistent consensus verification
//!
//! η → s → μ → a → η′
//! h(x) ≥ 0. Always.

use anyhow::{Context, Result};
use rusqlite::{params, Connection, OptionalExtension, Transaction};
use serde::{Deserialize, Serialize};
use std::path::Path;
use std::sync::Arc;
use tokio::sync::{Mutex, RwLock};
use tracing::{debug, error, info, warn};

use super::sync::{CRDTState, VectorClock};
use crate::byzantine::{ByzantineEvidence, ByzantineFaultType};

// ============================================================================
// Configuration
// ============================================================================

/// Entries between snapshots for compaction
pub const SNAPSHOT_INTERVAL: u64 = 1000;

/// Days to keep old entries before pruning
pub const PRUNE_AGE_DAYS: i32 = 7;

/// Maximum signatures to store per decision
pub const MAX_SIGNATURES_PER_DECISION: usize = 100;

/// Database schema version for migrations
pub const LEDGER_SCHEMA_VERSION: i32 = 1;

// ============================================================================
// Schema
// ============================================================================

/// SQL schema for mesh ledger
const LEDGER_SCHEMA: &str = r#"
-- Consensus decisions
CREATE TABLE IF NOT EXISTS consensus_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    height INTEGER NOT NULL,
    round INTEGER NOT NULL,
    leader_id TEXT NOT NULL,
    command TEXT,
    command_hash BLOB,
    decided_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(height, round)
);

CREATE INDEX IF NOT EXISTS idx_decisions_height ON consensus_decisions(height);
CREATE INDEX IF NOT EXISTS idx_decisions_decided_at ON consensus_decisions(decided_at);

-- Decision signatures (multiple per decision)
CREATE TABLE IF NOT EXISTS decision_signatures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id INTEGER NOT NULL,
    voter_id TEXT NOT NULL,
    signature BLOB NOT NULL,
    public_key BLOB,
    signed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (decision_id) REFERENCES consensus_decisions(id) ON DELETE CASCADE,
    UNIQUE(decision_id, voter_id)
);

CREATE INDEX IF NOT EXISTS idx_signatures_decision ON decision_signatures(decision_id);

-- State snapshots (periodic CRDT state snapshots)
CREATE TABLE IF NOT EXISTS state_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_height INTEGER NOT NULL UNIQUE,
    vector_clock_json TEXT NOT NULL,
    crdt_state_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    checksum BLOB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_snapshots_height ON state_snapshots(snapshot_height);

-- Transaction log (write-ahead log entries)
CREATE TABLE IF NOT EXISTS transaction_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    log_sequence INTEGER NOT NULL UNIQUE,
    operation TEXT NOT NULL,
    data_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    applied INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_txlog_sequence ON transaction_log(log_sequence);
CREATE INDEX IF NOT EXISTS idx_txlog_applied ON transaction_log(applied);

-- Byzantine evidence records
CREATE TABLE IF NOT EXISTS byzantine_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    peer_id TEXT NOT NULL,
    fault_type TEXT NOT NULL,
    fault_data_json TEXT NOT NULL,
    evidence_hash BLOB NOT NULL,
    detected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved INTEGER NOT NULL DEFAULT 0,
    resolved_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_evidence_peer ON byzantine_evidence(peer_id);
CREATE INDEX IF NOT EXISTS idx_evidence_resolved ON byzantine_evidence(resolved);
CREATE INDEX IF NOT EXISTS idx_evidence_detected ON byzantine_evidence(detected_at);

-- Ledger metadata
CREATE TABLE IF NOT EXISTS ledger_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"#;

// ============================================================================
// Types
// ============================================================================

/// Consensus decision record
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConsensusDecision {
    /// Decision ID (database primary key)
    pub id: Option<i64>,
    /// Consensus height (block number)
    pub height: u64,
    /// Round within height
    pub round: u32,
    /// Elected leader ID
    pub leader_id: String,
    /// Command that was decided (if any)
    pub command: Option<String>,
    /// Hash of the command
    pub command_hash: Option<Vec<u8>>,
    /// When the decision was made
    pub decided_at: String,
    /// Signatures from validators
    pub signatures: Vec<DecisionSignature>,
}

/// Signature on a consensus decision
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DecisionSignature {
    /// Voter's hub ID
    pub voter_id: String,
    /// Ed25519 signature
    pub signature: Vec<u8>,
    /// Voter's public key (for verification)
    pub public_key: Option<Vec<u8>>,
    /// When signed
    pub signed_at: String,
}

/// State snapshot for recovery
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StateSnapshot {
    /// Snapshot ID
    pub id: Option<i64>,
    /// Height at which snapshot was taken
    pub snapshot_height: u64,
    /// Vector clock state
    pub vector_clock: VectorClock,
    /// Full CRDT state
    pub crdt_state: CRDTState,
    /// When snapshot was created
    pub created_at: String,
    /// Checksum for integrity verification
    pub checksum: Vec<u8>,
}

/// Transaction log entry for WAL
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TransactionLogEntry {
    /// Log entry ID
    pub id: Option<i64>,
    /// Sequence number (monotonic)
    pub log_sequence: u64,
    /// Operation type
    pub operation: TransactionOperation,
    /// Operation data
    pub data: serde_json::Value,
    /// When logged
    pub created_at: String,
    /// Whether applied to state
    pub applied: bool,
}

/// Transaction operation types
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TransactionOperation {
    /// New consensus decision
    Decision,
    /// State update (CRDT merge)
    StateUpdate,
    /// Peer added
    PeerJoined,
    /// Peer removed
    PeerLeft,
    /// Byzantine fault recorded
    ByzantineFault,
    /// Configuration change
    ConfigChange,
}

impl std::fmt::Display for TransactionOperation {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            TransactionOperation::Decision => write!(f, "DECISION"),
            TransactionOperation::StateUpdate => write!(f, "STATE_UPDATE"),
            TransactionOperation::PeerJoined => write!(f, "PEER_JOINED"),
            TransactionOperation::PeerLeft => write!(f, "PEER_LEFT"),
            TransactionOperation::ByzantineFault => write!(f, "BYZANTINE_FAULT"),
            TransactionOperation::ConfigChange => write!(f, "CONFIG_CHANGE"),
        }
    }
}

impl std::str::FromStr for TransactionOperation {
    type Err = anyhow::Error;

    fn from_str(s: &str) -> Result<Self> {
        match s {
            "DECISION" => Ok(TransactionOperation::Decision),
            "STATE_UPDATE" => Ok(TransactionOperation::StateUpdate),
            "PEER_JOINED" => Ok(TransactionOperation::PeerJoined),
            "PEER_LEFT" => Ok(TransactionOperation::PeerLeft),
            "BYZANTINE_FAULT" => Ok(TransactionOperation::ByzantineFault),
            "CONFIG_CHANGE" => Ok(TransactionOperation::ConfigChange),
            _ => Err(anyhow::anyhow!("Unknown operation: {}", s)),
        }
    }
}

/// Byzantine evidence record for persistence
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ByzantineEvidenceRecord {
    /// Record ID
    pub id: Option<i64>,
    /// Peer that committed the fault
    pub peer_id: String,
    /// Type of fault
    pub fault_type: String,
    /// Full fault data as JSON
    pub fault_data: serde_json::Value,
    /// Evidence hash for deduplication
    pub evidence_hash: Vec<u8>,
    /// When detected
    pub detected_at: String,
    /// Whether resolved
    pub resolved: bool,
    /// When resolved (if applicable)
    pub resolved_at: Option<String>,
}

/// Ledger statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LedgerStats {
    /// Total consensus decisions
    pub total_decisions: u64,
    /// Latest decision height
    pub latest_height: u64,
    /// Total snapshots
    pub total_snapshots: u64,
    /// Latest snapshot height
    pub latest_snapshot_height: u64,
    /// Pending WAL entries
    pub pending_wal_entries: u64,
    /// Total Byzantine evidence records
    pub total_evidence: u64,
    /// Unresolved Byzantine evidence
    pub unresolved_evidence: u64,
    /// Entries needing pruning
    pub entries_to_prune: u64,
}

// ============================================================================
// Mesh Ledger
// ============================================================================

/// Persistent ledger for mesh consensus
pub struct MeshLedger {
    /// Database connection (protected by mutex for thread safety)
    conn: Arc<Mutex<Connection>>,
    /// Current log sequence number
    log_sequence: Arc<RwLock<u64>>,
    /// Entries since last snapshot
    entries_since_snapshot: Arc<RwLock<u64>>,
    /// This hub's ID for logging
    hub_id: String,
}

impl MeshLedger {
    /// Open or create ledger at the given path
    pub fn new(path: impl AsRef<Path>, hub_id: String) -> Result<Self> {
        let path = path.as_ref();

        // Ensure parent directory exists
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)?;
        }

        let conn = Connection::open(path)
            .with_context(|| format!("Failed to open ledger: {}", path.display()))?;

        // Enable WAL mode for write-ahead logging
        conn.pragma_update(None, "journal_mode", "WAL")?;

        // Enable foreign keys
        conn.pragma_update(None, "foreign_keys", "ON")?;

        // Apply schema
        conn.execute_batch(LEDGER_SCHEMA)?;

        let ledger = Self {
            conn: Arc::new(Mutex::new(conn)),
            log_sequence: Arc::new(RwLock::new(0)),
            entries_since_snapshot: Arc::new(RwLock::new(0)),
            hub_id,
        };

        info!("📒 Mesh ledger opened: {}", path.display());

        Ok(ledger)
    }

    /// Create an in-memory ledger (for testing)
    pub fn in_memory(hub_id: String) -> Result<Self> {
        let conn = Connection::open_in_memory()?;

        // Enable foreign keys
        conn.pragma_update(None, "foreign_keys", "ON")?;

        conn.execute_batch(LEDGER_SCHEMA)?;

        Ok(Self {
            conn: Arc::new(Mutex::new(conn)),
            log_sequence: Arc::new(RwLock::new(0)),
            entries_since_snapshot: Arc::new(RwLock::new(0)),
            hub_id,
        })
    }

    /// Initialize ledger state from database on startup
    pub async fn initialize(&self) -> Result<()> {
        let conn = self.conn.lock().await;

        // Get current log sequence
        let max_sequence: Option<i64> = conn.query_row(
            "SELECT MAX(log_sequence) FROM transaction_log",
            [],
            |row| row.get(0),
        ).optional()?.flatten();

        let sequence = max_sequence.unwrap_or(0) as u64;
        *self.log_sequence.write().await = sequence;

        // Count entries since last snapshot
        let latest_snapshot: Option<i64> = conn.query_row(
            "SELECT MAX(snapshot_height) FROM state_snapshots",
            [],
            |row| row.get(0),
        ).optional()?.flatten();

        let latest_decision: Option<i64> = conn.query_row(
            "SELECT MAX(height) FROM consensus_decisions",
            [],
            |row| row.get(0),
        ).optional()?.flatten();

        let entries_since = match (latest_snapshot, latest_decision) {
            (Some(snap), Some(dec)) => (dec - snap).max(0) as u64,
            (None, Some(dec)) => dec as u64,
            _ => 0,
        };

        *self.entries_since_snapshot.write().await = entries_since;

        info!(
            "📒 Ledger initialized: sequence={}, entries_since_snapshot={}",
            sequence, entries_since
        );

        Ok(())
    }

    // ========================================================================
    // Consensus Decisions
    // ========================================================================

    /// Record a new consensus decision
    pub async fn record_decision(&self, decision: &ConsensusDecision) -> Result<i64> {
        let conn = self.conn.lock().await;

        // Start transaction
        let tx = conn.unchecked_transaction()?;

        // Insert decision
        tx.execute(
            "INSERT INTO consensus_decisions (height, round, leader_id, command, command_hash, decided_at)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
            params![
                decision.height as i64,
                decision.round as i64,
                decision.leader_id,
                decision.command,
                decision.command_hash,
                decision.decided_at,
            ],
        )?;

        let decision_id = tx.last_insert_rowid();

        // Insert signatures
        for sig in &decision.signatures {
            tx.execute(
                "INSERT INTO decision_signatures (decision_id, voter_id, signature, public_key, signed_at)
                 VALUES (?1, ?2, ?3, ?4, ?5)",
                params![
                    decision_id,
                    sig.voter_id,
                    sig.signature,
                    sig.public_key,
                    sig.signed_at,
                ],
            )?;
        }

        // Write to transaction log
        let sequence = self.next_sequence().await;
        let log_data = serde_json::json!({
            "height": decision.height,
            "round": decision.round,
            "leader_id": decision.leader_id,
        });

        tx.execute(
            "INSERT INTO transaction_log (log_sequence, operation, data_json, applied)
             VALUES (?1, ?2, ?3, 1)",
            params![
                sequence as i64,
                TransactionOperation::Decision.to_string(),
                log_data.to_string(),
            ],
        )?;

        tx.commit()?;

        // Update counters
        self.increment_entries_since_snapshot().await;

        debug!(
            "📒 Recorded decision: h={} r={} leader={}",
            decision.height, decision.round, decision.leader_id
        );

        // Check if snapshot needed
        self.maybe_create_snapshot().await?;

        Ok(decision_id)
    }

    /// Get decision by height and round
    pub async fn get_decision(&self, height: u64, round: u32) -> Result<Option<ConsensusDecision>> {
        let conn = self.conn.lock().await;

        let row: Option<(i64, String, Option<String>, Option<Vec<u8>>, String)> = conn.query_row(
            "SELECT id, leader_id, command, command_hash, decided_at
             FROM consensus_decisions WHERE height = ?1 AND round = ?2",
            params![height as i64, round as i64],
            |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?, row.get(3)?, row.get(4)?)),
        ).optional()?;

        match row {
            Some((id, leader_id, command, command_hash, decided_at)) => {
                // Get signatures
                let signatures = self.get_decision_signatures_internal(&conn, id)?;

                Ok(Some(ConsensusDecision {
                    id: Some(id),
                    height,
                    round,
                    leader_id,
                    command,
                    command_hash,
                    decided_at,
                    signatures,
                }))
            }
            None => Ok(None),
        }
    }

    /// Get decision signatures (internal, conn already locked)
    fn get_decision_signatures_internal(
        &self,
        conn: &Connection,
        decision_id: i64,
    ) -> Result<Vec<DecisionSignature>> {
        let mut stmt = conn.prepare(
            "SELECT voter_id, signature, public_key, signed_at
             FROM decision_signatures WHERE decision_id = ?1",
        )?;

        let signatures = stmt.query_map(params![decision_id], |row| {
            Ok(DecisionSignature {
                voter_id: row.get(0)?,
                signature: row.get(1)?,
                public_key: row.get(2)?,
                signed_at: row.get(3)?,
            })
        })?
        .collect::<std::result::Result<Vec<_>, _>>()?;

        Ok(signatures)
    }

    /// Get latest decision height
    pub async fn get_latest_height(&self) -> Result<u64> {
        let conn = self.conn.lock().await;

        let height: Option<i64> = conn.query_row(
            "SELECT MAX(height) FROM consensus_decisions",
            [],
            |row| row.get(0),
        ).optional()?.flatten();

        Ok(height.unwrap_or(0) as u64)
    }

    /// Get decisions in height range
    pub async fn get_decisions_range(
        &self,
        from_height: u64,
        to_height: u64,
    ) -> Result<Vec<ConsensusDecision>> {
        let conn = self.conn.lock().await;

        let mut stmt = conn.prepare(
            "SELECT id, height, round, leader_id, command, command_hash, decided_at
             FROM consensus_decisions
             WHERE height >= ?1 AND height <= ?2
             ORDER BY height ASC, round ASC",
        )?;

        let rows = stmt.query_map(params![from_height as i64, to_height as i64], |row| {
            Ok((
                row.get::<_, i64>(0)?,
                row.get::<_, i64>(1)?,
                row.get::<_, i64>(2)?,
                row.get::<_, String>(3)?,
                row.get::<_, Option<String>>(4)?,
                row.get::<_, Option<Vec<u8>>>(5)?,
                row.get::<_, String>(6)?,
            ))
        })?;

        let mut decisions = Vec::new();
        for row in rows {
            let (id, height, round, leader_id, command, command_hash, decided_at) = row?;
            let signatures = self.get_decision_signatures_internal(&conn, id)?;

            decisions.push(ConsensusDecision {
                id: Some(id),
                height: height as u64,
                round: round as u32,
                leader_id,
                command,
                command_hash,
                decided_at,
                signatures,
            });
        }

        Ok(decisions)
    }

    // ========================================================================
    // State Snapshots
    // ========================================================================

    /// Create a state snapshot
    pub async fn create_snapshot(
        &self,
        height: u64,
        vector_clock: &VectorClock,
        crdt_state: &CRDTState,
    ) -> Result<i64> {
        let conn = self.conn.lock().await;

        let clock_json = serde_json::to_string(vector_clock)?;
        let state_json = serde_json::to_string(crdt_state)?;

        // Calculate checksum
        let checksum = self.calculate_checksum(&clock_json, &state_json);

        conn.execute(
            "INSERT INTO state_snapshots (snapshot_height, vector_clock_json, crdt_state_json, checksum)
             VALUES (?1, ?2, ?3, ?4)",
            params![height as i64, clock_json, state_json, checksum],
        )?;

        let snapshot_id = conn.last_insert_rowid();

        // Reset entries counter
        *self.entries_since_snapshot.write().await = 0;

        info!("📸 Created snapshot at height {}", height);

        Ok(snapshot_id)
    }

    /// Get latest snapshot
    pub async fn get_latest_snapshot(&self) -> Result<Option<StateSnapshot>> {
        let conn = self.conn.lock().await;

        let row: Option<(i64, i64, String, String, String, Vec<u8>)> = conn.query_row(
            "SELECT id, snapshot_height, vector_clock_json, crdt_state_json, created_at, checksum
             FROM state_snapshots ORDER BY snapshot_height DESC LIMIT 1",
            [],
            |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?, row.get(3)?, row.get(4)?, row.get(5)?)),
        ).optional()?;

        match row {
            Some((id, height, clock_json, state_json, created_at, checksum)) => {
                // Verify checksum
                let calculated = self.calculate_checksum(&clock_json, &state_json);
                if calculated != checksum {
                    error!("📒 Snapshot checksum mismatch at height {}!", height);
                    return Err(anyhow::anyhow!("Snapshot checksum mismatch"));
                }

                let vector_clock: VectorClock = serde_json::from_str(&clock_json)?;
                let crdt_state: CRDTState = serde_json::from_str(&state_json)?;

                Ok(Some(StateSnapshot {
                    id: Some(id),
                    snapshot_height: height as u64,
                    vector_clock,
                    crdt_state,
                    created_at,
                    checksum,
                }))
            }
            None => Ok(None),
        }
    }

    /// Get snapshot by height
    pub async fn get_snapshot_at_height(&self, height: u64) -> Result<Option<StateSnapshot>> {
        let conn = self.conn.lock().await;

        let row: Option<(i64, String, String, String, Vec<u8>)> = conn.query_row(
            "SELECT id, vector_clock_json, crdt_state_json, created_at, checksum
             FROM state_snapshots WHERE snapshot_height = ?1",
            params![height as i64],
            |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?, row.get(3)?, row.get(4)?)),
        ).optional()?;

        match row {
            Some((id, clock_json, state_json, created_at, checksum)) => {
                let vector_clock: VectorClock = serde_json::from_str(&clock_json)?;
                let crdt_state: CRDTState = serde_json::from_str(&state_json)?;

                Ok(Some(StateSnapshot {
                    id: Some(id),
                    snapshot_height: height,
                    vector_clock,
                    crdt_state,
                    created_at,
                    checksum,
                }))
            }
            None => Ok(None),
        }
    }

    /// Maybe create snapshot if interval reached
    async fn maybe_create_snapshot(&self) -> Result<()> {
        let entries = *self.entries_since_snapshot.read().await;

        if entries >= SNAPSHOT_INTERVAL {
            // We need CRDT state to create a snapshot
            // This would typically be called by the mesh coordinator
            // with the current state. For now, just log that it's needed.
            debug!(
                "📒 Snapshot needed: {} entries since last snapshot",
                entries
            );
        }

        Ok(())
    }

    // ========================================================================
    // Transaction Log (WAL)
    // ========================================================================

    /// Append to transaction log
    pub async fn append_log(
        &self,
        operation: TransactionOperation,
        data: serde_json::Value,
    ) -> Result<u64> {
        let conn = self.conn.lock().await;
        let sequence = self.next_sequence().await;

        conn.execute(
            "INSERT INTO transaction_log (log_sequence, operation, data_json)
             VALUES (?1, ?2, ?3)",
            params![sequence as i64, operation.to_string(), data.to_string()],
        )?;

        debug!("📒 WAL: {} #{}", operation, sequence);

        Ok(sequence)
    }

    /// Get unapplied log entries
    pub async fn get_pending_log_entries(&self) -> Result<Vec<TransactionLogEntry>> {
        let conn = self.conn.lock().await;

        let mut stmt = conn.prepare(
            "SELECT id, log_sequence, operation, data_json, created_at, applied
             FROM transaction_log WHERE applied = 0 ORDER BY log_sequence ASC",
        )?;

        let entries = stmt.query_map([], |row| {
            let op_str: String = row.get(2)?;
            Ok(TransactionLogEntry {
                id: Some(row.get(0)?),
                log_sequence: row.get::<_, i64>(1)? as u64,
                operation: op_str.parse().unwrap_or(TransactionOperation::Decision),
                data: serde_json::from_str(&row.get::<_, String>(3)?).unwrap_or_default(),
                created_at: row.get(4)?,
                applied: row.get::<_, i64>(5)? != 0,
            })
        })?
        .collect::<std::result::Result<Vec<_>, _>>()?;

        Ok(entries)
    }

    /// Mark log entry as applied
    pub async fn mark_log_applied(&self, sequence: u64) -> Result<()> {
        let conn = self.conn.lock().await;

        conn.execute(
            "UPDATE transaction_log SET applied = 1 WHERE log_sequence = ?1",
            params![sequence as i64],
        )?;

        Ok(())
    }

    /// Get next sequence number
    async fn next_sequence(&self) -> u64 {
        let mut seq = self.log_sequence.write().await;
        *seq += 1;
        *seq
    }

    /// Increment entries since snapshot counter
    async fn increment_entries_since_snapshot(&self) {
        let mut entries = self.entries_since_snapshot.write().await;
        *entries += 1;
    }

    // ========================================================================
    // Byzantine Evidence
    // ========================================================================

    /// Record Byzantine evidence
    pub async fn record_evidence(&self, evidence: &ByzantineEvidence) -> Result<i64> {
        let conn = self.conn.lock().await;

        let fault_type_str = format!("{:?}", evidence.fault_type);
        let fault_data = serde_json::to_value(&evidence.fault_type)?;

        conn.execute(
            "INSERT INTO byzantine_evidence (peer_id, fault_type, fault_data_json, evidence_hash, detected_at)
             VALUES (?1, ?2, ?3, ?4, datetime(?5, 'unixepoch'))",
            params![
                evidence.peer_id,
                fault_type_str,
                fault_data.to_string(),
                evidence.evidence_hash,
                evidence.detected_at as i64,
            ],
        )?;

        let id = conn.last_insert_rowid();

        // Also write to WAL
        drop(conn);
        self.append_log(
            TransactionOperation::ByzantineFault,
            serde_json::json!({
                "peer_id": evidence.peer_id,
                "fault_type": fault_type_str,
            }),
        ).await?;

        warn!(
            "📒 Recorded Byzantine evidence: peer={} type={}",
            evidence.peer_id, fault_type_str
        );

        Ok(id)
    }

    /// Get unresolved evidence for a peer
    pub async fn get_peer_evidence(&self, peer_id: &str) -> Result<Vec<ByzantineEvidenceRecord>> {
        let conn = self.conn.lock().await;

        let mut stmt = conn.prepare(
            "SELECT id, peer_id, fault_type, fault_data_json, evidence_hash, detected_at, resolved, resolved_at
             FROM byzantine_evidence WHERE peer_id = ?1 ORDER BY detected_at DESC",
        )?;

        let records = stmt.query_map(params![peer_id], |row| {
            Ok(ByzantineEvidenceRecord {
                id: Some(row.get(0)?),
                peer_id: row.get(1)?,
                fault_type: row.get(2)?,
                fault_data: serde_json::from_str(&row.get::<_, String>(3)?).unwrap_or_default(),
                evidence_hash: row.get(4)?,
                detected_at: row.get(5)?,
                resolved: row.get::<_, i64>(6)? != 0,
                resolved_at: row.get(7)?,
            })
        })?
        .collect::<std::result::Result<Vec<_>, _>>()?;

        Ok(records)
    }

    /// Mark evidence as resolved
    pub async fn resolve_evidence(&self, evidence_id: i64) -> Result<()> {
        let conn = self.conn.lock().await;

        conn.execute(
            "UPDATE byzantine_evidence SET resolved = 1, resolved_at = CURRENT_TIMESTAMP
             WHERE id = ?1",
            params![evidence_id],
        )?;

        info!("📒 Resolved Byzantine evidence #{}", evidence_id);

        Ok(())
    }

    /// Get all unresolved evidence
    pub async fn get_unresolved_evidence(&self) -> Result<Vec<ByzantineEvidenceRecord>> {
        let conn = self.conn.lock().await;

        let mut stmt = conn.prepare(
            "SELECT id, peer_id, fault_type, fault_data_json, evidence_hash, detected_at, resolved, resolved_at
             FROM byzantine_evidence WHERE resolved = 0 ORDER BY detected_at DESC",
        )?;

        let records = stmt.query_map([], |row| {
            Ok(ByzantineEvidenceRecord {
                id: Some(row.get(0)?),
                peer_id: row.get(1)?,
                fault_type: row.get(2)?,
                fault_data: serde_json::from_str(&row.get::<_, String>(3)?).unwrap_or_default(),
                evidence_hash: row.get(4)?,
                detected_at: row.get(5)?,
                resolved: row.get::<_, i64>(6)? != 0,
                resolved_at: row.get(7)?,
            })
        })?
        .collect::<std::result::Result<Vec<_>, _>>()?;

        Ok(records)
    }

    // ========================================================================
    // Recovery
    // ========================================================================

    /// Recover state from ledger on startup
    pub async fn recover(&self) -> Result<RecoveryResult> {
        info!("📒 Starting ledger recovery...");

        // 1. Get latest snapshot
        let snapshot = self.get_latest_snapshot().await?;

        let (start_height, vector_clock, crdt_state) = match snapshot {
            Some(snap) => {
                info!("📒 Found snapshot at height {}", snap.snapshot_height);
                (snap.snapshot_height, Some(snap.vector_clock), Some(snap.crdt_state))
            }
            None => {
                info!("📒 No snapshot found, recovering from genesis");
                (0, None, None)
            }
        };

        // 2. Get decisions since snapshot
        let latest_height = self.get_latest_height().await?;
        let decisions = if latest_height > start_height {
            self.get_decisions_range(start_height + 1, latest_height).await?
        } else {
            Vec::new()
        };

        // 3. Get pending log entries
        let pending_entries = self.get_pending_log_entries().await?;

        // 4. Get unresolved Byzantine evidence
        let unresolved_evidence = self.get_unresolved_evidence().await?;

        info!(
            "📒 Recovery complete: snapshot_height={}, decisions_to_replay={}, pending_wal={}, unresolved_evidence={}",
            start_height,
            decisions.len(),
            pending_entries.len(),
            unresolved_evidence.len()
        );

        Ok(RecoveryResult {
            snapshot_height: start_height,
            vector_clock,
            crdt_state,
            decisions_to_replay: decisions,
            pending_log_entries: pending_entries,
            unresolved_evidence,
        })
    }

    // ========================================================================
    // Pruning
    // ========================================================================

    /// Prune old entries (keep last 7 days by default)
    pub async fn prune(&self, days: Option<i32>) -> Result<PruneResult> {
        let days = days.unwrap_or(PRUNE_AGE_DAYS);
        let conn = self.conn.lock().await;

        // Get latest snapshot height (we need to keep at least one)
        let latest_snapshot: Option<i64> = conn.query_row(
            "SELECT MAX(snapshot_height) FROM state_snapshots",
            [],
            |row| row.get(0),
        ).optional()?.flatten();

        let cutoff_sql = format!("-{} days", days);

        // Prune old decisions (but keep at least up to latest snapshot)
        let decisions_pruned = if let Some(snap_height) = latest_snapshot {
            conn.execute(
                "DELETE FROM consensus_decisions
                 WHERE height < ?1 AND decided_at < datetime('now', ?2)",
                params![snap_height, cutoff_sql],
            )?
        } else {
            0
        };

        // Prune old snapshots (keep at least 2)
        let snapshots_pruned = conn.execute(
            "DELETE FROM state_snapshots
             WHERE id NOT IN (
                SELECT id FROM state_snapshots ORDER BY snapshot_height DESC LIMIT 2
             )
             AND created_at < datetime('now', ?1)",
            params![cutoff_sql],
        )?;

        // Prune old log entries (keep applied entries for 1 day, unapplied forever)
        let log_pruned = conn.execute(
            "DELETE FROM transaction_log
             WHERE applied = 1 AND created_at < datetime('now', '-1 day')",
            [],
        )?;

        // Prune resolved Byzantine evidence older than cutoff
        let evidence_pruned = conn.execute(
            "DELETE FROM byzantine_evidence
             WHERE resolved = 1 AND detected_at < datetime('now', ?1)",
            params![cutoff_sql],
        )?;

        info!(
            "📒 Pruned: {} decisions, {} snapshots, {} log entries, {} evidence records",
            decisions_pruned, snapshots_pruned, log_pruned, evidence_pruned
        );

        Ok(PruneResult {
            decisions_pruned: decisions_pruned as u64,
            snapshots_pruned: snapshots_pruned as u64,
            log_entries_pruned: log_pruned as u64,
            evidence_pruned: evidence_pruned as u64,
        })
    }

    // ========================================================================
    // Statistics
    // ========================================================================

    /// Get ledger statistics
    pub async fn get_stats(&self) -> Result<LedgerStats> {
        let conn = self.conn.lock().await;

        let total_decisions: i64 = conn.query_row(
            "SELECT COUNT(*) FROM consensus_decisions",
            [],
            |row| row.get(0),
        )?;

        let latest_height: i64 = conn.query_row(
            "SELECT COALESCE(MAX(height), 0) FROM consensus_decisions",
            [],
            |row| row.get(0),
        )?;

        let total_snapshots: i64 = conn.query_row(
            "SELECT COUNT(*) FROM state_snapshots",
            [],
            |row| row.get(0),
        )?;

        let latest_snapshot_height: i64 = conn.query_row(
            "SELECT COALESCE(MAX(snapshot_height), 0) FROM state_snapshots",
            [],
            |row| row.get(0),
        )?;

        let pending_wal: i64 = conn.query_row(
            "SELECT COUNT(*) FROM transaction_log WHERE applied = 0",
            [],
            |row| row.get(0),
        )?;

        let total_evidence: i64 = conn.query_row(
            "SELECT COUNT(*) FROM byzantine_evidence",
            [],
            |row| row.get(0),
        )?;

        let unresolved_evidence: i64 = conn.query_row(
            "SELECT COUNT(*) FROM byzantine_evidence WHERE resolved = 0",
            [],
            |row| row.get(0),
        )?;

        // Count entries that would be pruned
        let cutoff_sql = format!("-{} days", PRUNE_AGE_DAYS);
        let entries_to_prune: i64 = conn.query_row(
            "SELECT COUNT(*) FROM consensus_decisions WHERE decided_at < datetime('now', ?1)",
            params![cutoff_sql],
            |row| row.get(0),
        )?;

        Ok(LedgerStats {
            total_decisions: total_decisions as u64,
            latest_height: latest_height as u64,
            total_snapshots: total_snapshots as u64,
            latest_snapshot_height: latest_snapshot_height as u64,
            pending_wal_entries: pending_wal as u64,
            total_evidence: total_evidence as u64,
            unresolved_evidence: unresolved_evidence as u64,
            entries_to_prune: entries_to_prune as u64,
        })
    }

    // ========================================================================
    // Utilities
    // ========================================================================

    /// Calculate checksum for snapshot integrity
    fn calculate_checksum(&self, clock_json: &str, state_json: &str) -> Vec<u8> {
        // Simple djb2 hash (for integrity, not cryptographic security)
        let combined = format!("{}{}", clock_json, state_json);
        let mut hash: u64 = 5381;
        for byte in combined.bytes() {
            hash = hash.wrapping_mul(33).wrapping_add(byte as u64);
        }
        hash.to_le_bytes().to_vec()
    }

    /// Force checkpoint for WAL (flush to main database)
    pub async fn checkpoint(&self) -> Result<()> {
        let conn = self.conn.lock().await;
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)", [])?;
        info!("📒 WAL checkpoint completed");
        Ok(())
    }

    /// Get database file size
    pub async fn get_db_size(&self) -> Result<u64> {
        let conn = self.conn.lock().await;
        let page_count: i64 = conn.query_row("PRAGMA page_count", [], |row| row.get(0))?;
        let page_size: i64 = conn.query_row("PRAGMA page_size", [], |row| row.get(0))?;
        Ok((page_count * page_size) as u64)
    }
}

// ============================================================================
// Recovery Result
// ============================================================================

/// Result of ledger recovery
#[derive(Debug)]
pub struct RecoveryResult {
    /// Height of the last snapshot
    pub snapshot_height: u64,
    /// Vector clock from snapshot (if any)
    pub vector_clock: Option<VectorClock>,
    /// CRDT state from snapshot (if any)
    pub crdt_state: Option<CRDTState>,
    /// Decisions to replay after snapshot
    pub decisions_to_replay: Vec<ConsensusDecision>,
    /// Pending log entries to process
    pub pending_log_entries: Vec<TransactionLogEntry>,
    /// Unresolved Byzantine evidence
    pub unresolved_evidence: Vec<ByzantineEvidenceRecord>,
}

/// Result of pruning operation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PruneResult {
    pub decisions_pruned: u64,
    pub snapshots_pruned: u64,
    pub log_entries_pruned: u64,
    pub evidence_pruned: u64,
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;
    use crate::state_cache::ZoneLevel;

    fn create_test_decision(height: u64, round: u32) -> ConsensusDecision {
        ConsensusDecision {
            id: None,
            height,
            round,
            leader_id: format!("hub-{}", height % 3),
            command: Some("test_command".to_string()),
            command_hash: Some(vec![1, 2, 3, 4]),
            decided_at: chrono::Utc::now().to_rfc3339(),
            signatures: vec![
                DecisionSignature {
                    voter_id: "hub-1".to_string(),
                    signature: vec![1; 64],
                    public_key: Some(vec![2; 32]),
                    signed_at: chrono::Utc::now().to_rfc3339(),
                },
            ],
        }
    }

    #[tokio::test]
    async fn test_create_ledger() {
        let ledger = MeshLedger::in_memory("test-hub".to_string()).unwrap();
        ledger.initialize().await.unwrap();

        let stats = ledger.get_stats().await.unwrap();
        assert_eq!(stats.total_decisions, 0);
        assert_eq!(stats.latest_height, 0);
    }

    #[tokio::test]
    async fn test_record_and_get_decision() {
        let ledger = MeshLedger::in_memory("test-hub".to_string()).unwrap();
        ledger.initialize().await.unwrap();

        let decision = create_test_decision(1, 0);
        let id = ledger.record_decision(&decision).await.unwrap();
        assert!(id > 0);

        let retrieved = ledger.get_decision(1, 0).await.unwrap();
        assert!(retrieved.is_some());

        let retrieved = retrieved.unwrap();
        assert_eq!(retrieved.height, 1);
        assert_eq!(retrieved.round, 0);
        assert_eq!(retrieved.leader_id, "hub-1");
        assert_eq!(retrieved.signatures.len(), 1);
    }

    #[tokio::test]
    async fn test_decision_range() {
        let ledger = MeshLedger::in_memory("test-hub".to_string()).unwrap();
        ledger.initialize().await.unwrap();

        // Record multiple decisions
        for h in 1..=5 {
            let decision = create_test_decision(h, 0);
            ledger.record_decision(&decision).await.unwrap();
        }

        let range = ledger.get_decisions_range(2, 4).await.unwrap();
        assert_eq!(range.len(), 3);
        assert_eq!(range[0].height, 2);
        assert_eq!(range[2].height, 4);
    }

    #[tokio::test]
    async fn test_snapshot() {
        let ledger = MeshLedger::in_memory("test-hub".to_string()).unwrap();
        ledger.initialize().await.unwrap();

        let clock = VectorClock::new();
        let state = CRDTState::new("test-hub".to_string());

        let id = ledger.create_snapshot(100, &clock, &state).await.unwrap();
        assert!(id > 0);

        let snapshot = ledger.get_latest_snapshot().await.unwrap();
        assert!(snapshot.is_some());

        let snapshot = snapshot.unwrap();
        assert_eq!(snapshot.snapshot_height, 100);
    }

    #[tokio::test]
    async fn test_transaction_log() {
        let ledger = MeshLedger::in_memory("test-hub".to_string()).unwrap();
        ledger.initialize().await.unwrap();

        let seq = ledger
            .append_log(
                TransactionOperation::PeerJoined,
                serde_json::json!({"peer_id": "new-peer"}),
            )
            .await
            .unwrap();
        assert_eq!(seq, 1);

        let pending = ledger.get_pending_log_entries().await.unwrap();
        assert_eq!(pending.len(), 1);

        ledger.mark_log_applied(seq).await.unwrap();

        let pending = ledger.get_pending_log_entries().await.unwrap();
        assert_eq!(pending.len(), 0);
    }

    #[tokio::test]
    async fn test_byzantine_evidence() {
        let ledger = MeshLedger::in_memory("test-hub".to_string()).unwrap();
        ledger.initialize().await.unwrap();

        let evidence = ByzantineEvidence::new(
            "bad-peer".to_string(),
            crate::byzantine::ByzantineFaultType::InvalidSignature {
                message_type: "proposal".to_string(),
                message_hash: vec![1, 2, 3],
            },
        );

        let id = ledger.record_evidence(&evidence).await.unwrap();
        assert!(id > 0);

        let records = ledger.get_peer_evidence("bad-peer").await.unwrap();
        assert_eq!(records.len(), 1);
        assert!(!records[0].resolved);

        ledger.resolve_evidence(id).await.unwrap();

        let records = ledger.get_peer_evidence("bad-peer").await.unwrap();
        assert!(records[0].resolved);
    }

    #[tokio::test]
    async fn test_recovery() {
        let ledger = MeshLedger::in_memory("test-hub".to_string()).unwrap();
        ledger.initialize().await.unwrap();

        // Create some state
        for h in 1..=5 {
            let decision = create_test_decision(h, 0);
            ledger.record_decision(&decision).await.unwrap();
        }

        // Create snapshot at height 3
        let clock = VectorClock::new();
        let state = CRDTState::new("test-hub".to_string());
        ledger.create_snapshot(3, &clock, &state).await.unwrap();

        // Add more decisions
        for h in 6..=8 {
            let decision = create_test_decision(h, 0);
            ledger.record_decision(&decision).await.unwrap();
        }

        // Test recovery
        let result = ledger.recover().await.unwrap();
        assert_eq!(result.snapshot_height, 3);
        assert!(result.vector_clock.is_some());
        assert!(result.crdt_state.is_some());
        // Decisions 4, 5, 6, 7, 8 should need replay
        assert_eq!(result.decisions_to_replay.len(), 5);
    }

    #[tokio::test]
    async fn test_stats() {
        let ledger = MeshLedger::in_memory("test-hub".to_string()).unwrap();
        ledger.initialize().await.unwrap();

        // Record decisions
        for h in 1..=10 {
            let decision = create_test_decision(h, 0);
            ledger.record_decision(&decision).await.unwrap();
        }

        let stats = ledger.get_stats().await.unwrap();
        assert_eq!(stats.total_decisions, 10);
        assert_eq!(stats.latest_height, 10);
    }
}

/*
 * 鏡
 * The ledger remembers. Consensus persists. Byzantine faults are recorded.
 * h(x) ≥ 0. Always.
 */
